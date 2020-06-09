#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Aug 23 09:42:47 2019

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

from local.lib.common.launch_helpers import save_data_prompt, delete_existing_report_data, check_missing_main_selections
from local.lib.common.feedback import print_time_taken

from local.lib.ui_utils.script_arguments import script_arg_builder, get_selections_from_script_args

from local.lib.launcher_utils.configuration_loaders import File_Configuration_Loader
from local.lib.launcher_utils.video_processing_loops import Video_Processing_Loop


# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

# .....................................................................................................................

def parse_run_args(debug_print = False):
    
    # Set script arguments for running files
    args_list = ["camera",
                 "user",
                 "video",
                 "display",
                 "disable_saving",
                 "delete_existing_data",
                 "unthreaded_video",
                 "threaded_save",
                 "disable_prompts"]
    
    # Provide some extra information when accessing help text
    script_description = "Capture snapshot & tracking data from a recorded video file"
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

# Parse script arguments in case we're running automated
ap_result = parse_run_args()
threaded_video = (not ap_result.get("unthreaded_video", True))
threaded_save = (ap_result.get("threaded_save", False))
enable_display = ap_result.get("display", False)
allow_saving = (not ap_result.get("disable_saving", True))
delete_existing_data = ap_result.get("delete_existing_data", False)
provide_prompts = (not ap_result.get("disable_prompts", False))

# Get camera/user selections from arguments
arg_camera_select, arg_user_select, arg_video_select = get_selections_from_script_args(ap_result)

# Catch missing inputs, if prompts are disabled
check_missing_main_selections(arg_camera_select, arg_user_select, arg_video_select,
                              error_if_missing = (not provide_prompts),
                              error_message = "Prompts disabled, but not all selections were specified!")


# ---------------------------------------------------------------------------------------------------------------------
#%% Setup

# Make all required selections and setup/configure everything
loader = File_Configuration_Loader()
loader.selections(arg_camera_select, arg_user_select, arg_video_select, threaded_video)
loader.set_script_name(__file__)

# Get shared pathing settings
cameras_folder_path, camera_select, user_select = loader.get_camera_pathing()

# Ask user about saved data and delete existing data (if enabled)
enable_saving = save_data_prompt(enable_save_prompt = provide_prompts, save_by_default = allow_saving)
if enable_saving:
    check_delete_existing_data = (provide_prompts or delete_existing_data)
    delete_existing_report_data(cameras_folder_path, camera_select, user_select,
                                enable_deletion = check_delete_existing_data,
                                enable_deletion_prompt = provide_prompts)

# Turn on/off saving & threaded saving
loader.toggle_saving(enable_saving)
loader.toggle_threaded_saving(threaded_save)

# Configure everything!
start_timestamp = loader.setup_all()

# Set up object to handle all video processing
main_process = Video_Processing_Loop(loader, enable_display)


# ---------------------------------------------------------------------------------------------------------------------
#%% *** Main loop ***

# Feedback on launch
enable_disable_txt = ("enabled" if enable_saving else "disabled")
enable_thread_save_txt = ("" if not enable_saving else (" ({})".format("threaded" if threaded_save else "nothread")))
print("", "{}  |  Saving {}{}".format(start_timestamp, enable_disable_txt, enable_thread_save_txt), sep = "\n")

# Most of the work is done here!
total_processing_time_sec = main_process.loop(enable_progress_bar = True)
print_time_taken(0, total_processing_time_sec)


# ---------------------------------------------------------------------------------------------------------------------
#%% Clean up


# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap


