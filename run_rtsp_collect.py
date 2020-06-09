#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Dec  6 16:53:38 2019

@author: eo
"""


# ---------------------------------------------------------------------------------------------------------------------
#%% Add local path

import os
import sys

def find_path_to_local(target_folder = "local"):
    
    # Skip path finding if we successfully import the dummy file
    try:
        from local.dummy import dummy_func; dummy_func(); return
    except ImportError:
        print("", "Couldn't find local directory!", "Searching for path...", sep="\n")
    
    # Figure out where this file is located so we can work backwards to find the target folder
    file_directory = os.path.dirname(os.path.abspath(__file__))
    path_check = []
    
    # Check parent directories to see if we hit the main project directory containing the target folder
    prev_working_path = working_path = file_directory
    while True:
        
        # If we find the target folder in the given directory, add it to the python path (if it's not already there)
        if target_folder in os.listdir(working_path):
            if working_path not in sys.path:
                tilde_swarm = "~"*(4 + len(working_path))
                print("\n{}\nPython path updated:\n  {}\n{}".format(tilde_swarm, working_path, tilde_swarm))
                sys.path.append(working_path)
            break
        
        # Stop if we hit the filesystem root directory (parent directory isn't changing)
        prev_working_path, working_path = working_path, os.path.dirname(working_path)
        path_check.append(prev_working_path)
        if prev_working_path == working_path:
            print("\nTried paths:", *path_check, "", sep="\n  ")
            raise ImportError("Can't find '{}' directory!".format(target_folder))
            
find_path_to_local()

# ---------------------------------------------------------------------------------------------------------------------
#%% Imports

from local.lib.common.environment import get_dbserver_protocol, get_dbserver_host, get_dbserver_port
from local.lib.common.launch_helpers import save_data_prompt, delete_existing_report_data, check_missing_main_selections
from local.lib.common.feedback import print_time_taken

from local.lib.ui_utils.script_arguments import script_arg_builder, get_selections_from_script_args

from local.lib.launcher_utils.configuration_loaders import RTSP_Configuration_Loader
from local.lib.launcher_utils.video_processing_loops import Video_Processing_Loop

from local.online_database.post_to_dbserver import create_parallel_scheduled_post

from local.eolib.utils.quitters import ide_quit


# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

# .....................................................................................................................

def parse_run_args(debug_print = False):
    
    # Set default database url
    dbserver_protocol = get_dbserver_protocol()
    dbserver_host = get_dbserver_host()
    dbserver_port = get_dbserver_port()
    default_dbserver_url = "{}://{}:{}".format(dbserver_protocol, dbserver_host, dbserver_port)
    url_help_text = "Specify the url of the db server\n(Default: {})".format(default_dbserver_url)
    
    # Set default user for rtsp
    default_user = "live"
    user_help_text = "User select (Default: {})".format(default_user)
    
    # Set script arguments for running on streams
    args_list = ["camera",
                 {"user": {"default": default_user, "help_text": user_help_text}},
                 "display",
                 "enable_prompts",
                 "disable_saving",
                 "delete_existing_data",
                 "unthreaded_save",
                 {"url": {"default": default_dbserver_url,
                          "help_text": url_help_text}}]
    
    # Provide some extra information when accessing help text
    script_description = "Capture snapshot & tracking data from an RTSP stream. Requires RTSP configuration!"
    epilog_text = "\n".join(["Saved data can be manually accessed under:",
                             "  cameras > (camera name) > report > (user name)"])
    
    # Build & evaluate script arguments!
    ap_result = script_arg_builder(args_list,
                                   description = script_description,
                                   epilog = epilog_text,
                                   parse_on_call = True,
                                   debug_print = debug_print)
    
    return ap_result

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Handle script arguments

# Parse script arguments and decide if we need to provide any prompts
ap_result = parse_run_args()
dbserver_url = ap_result.get("url", None)
threaded_save = (not ap_result.get("unthreaded_save", True))
enable_display = ap_result.get("display", False)
allow_saving = (not ap_result.get("disable_saving", True))
delete_existing_data = ap_result.get("delete_existing_data", False)
provide_prompts = ap_result.get("enable_prompts", False)

# Get camera/user selections from arguments
arg_camera_select, arg_user_select, _ = get_selections_from_script_args(ap_result)

# Hard-code some settings for rtsp only
hardcode_video_select = "rtsp"
hardcode_threaded_video = False

# Catch missing inputs, if prompts are disabled
check_missing_main_selections(arg_camera_select, arg_user_select, hardcode_video_select,
                              error_if_missing = (not provide_prompts))


# ---------------------------------------------------------------------------------------------------------------------
#%% Setup

# Make all required selections and setup/configure everything
loader = RTSP_Configuration_Loader()
loader.selections(arg_camera_select, arg_user_select, hardcode_video_select, hardcode_threaded_video)
loader.set_script_name(__file__)

# Get shared pathing settings
cameras_folder_path, camera_select, user_select = loader.get_camera_pathing()

# Make sure we're not already running a camera
loader.shutdown_existing_camera_process()

# Delete existing data if needed. Only provide a prompt if the user asked for it
enable_saving = save_data_prompt(enable_save_prompt = provide_prompts, save_by_default = allow_saving)
if enable_saving:
    check_delete_existing_data = (provide_prompts or delete_existing_data)
    delete_existing_report_data(cameras_folder_path, camera_select, user_select,
                                enable_deletion = check_delete_existing_data,
                                enable_deletion_prompt = provide_prompts)

# Turn on saving if needed and enabled threaded i/o on rtps streams, to avoid blocking
loader.toggle_saving(enable_saving)
loader.toggle_threaded_saving(threaded_save)

# Configure everything!
loader.update_state_file("Initializing")
start_timestamp = loader.setup_all()

# Set up object to handle all video processing
main_process = Video_Processing_Loop(loader, enable_display)

# Start auto-data posting
parallel_post = create_parallel_scheduled_post(dbserver_url, cameras_folder_path, camera_select)


# ---------------------------------------------------------------------------------------------------------------------
#%% *** Main loop ***

# Feedback on launch
enable_disable_txt = ("enabled" if enable_saving else "disabled")
enable_thread_save_txt = ("" if not enable_saving else (" ({})".format("threaded" if threaded_save else "nothread")))
print("", "{}  |  Saving {}{}".format(start_timestamp, enable_disable_txt, enable_thread_save_txt), sep = "\n")

# Most of the work is done here!
loader.update_state_file("Online", in_standby = False)
total_processing_time_sec = main_process.loop(enable_progress_bar = False)
print_time_taken(0, total_processing_time_sec)


# ---------------------------------------------------------------------------------------------------------------------
#%% Clean up

# Clean up parallel post, just in case
loader.update_state_file("Shutting down")
print("", "Closing auto-post background task...", sep = "\n")
parallel_post.terminate()
parallel_post.join(10)
print("Finished!")

# Finally, remove the state file to indicate the camera is offline
loader.clear_state_file()


# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap

