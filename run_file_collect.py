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

from shutil import rmtree

from local.lib.ui_utils.script_arguments import script_arg_builder

from local.lib.launcher_utils.configuration_loaders import File_Configuration_Loader
from local.lib.launcher_utils.video_processing_loops import Video_Processing_Loop

from local.lib.file_access_utils.reporting import build_user_report_path

from eolib.utils.files import get_total_folder_size
from eolib.utils.cli_tools import cli_confirm

# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

# .....................................................................................................................

def parse_run_args(debug_print = False):
    
    # Set script arguments for running files
    args_list = ["camera",
                 "user", 
                 "video", 
                 "display", 
                 {"threaded_video": {"default": True}}, 
                 "save_and_keep", 
                 "save_and_delete",
                 "skip_save"]
    
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

def save_data_prompt(enable_save_prompt = True, skip_save = False):
    
    # If saving is being skipped, we ignore prompt settings entirely
    if skip_save:
        return False
    
    # If we don't prompt the user to save, assume saving is enabled
    if not enable_save_prompt:
        return True
    
    # For testing
    save_by_default = False
    saving_enabled = cli_confirm("Save data?", default_response = save_by_default)
            
    return saving_enabled

# .....................................................................................................................

def delete_existing_report_data(enable_deletion_prompt, configuration_loader, save_and_keep):
    
    # If prompt is skipped and deletion is disabled, don't do anything
    if (not enable_deletion_prompt) and save_and_keep:
        print("", "Existing files are not being deleted!", sep = "\n")
        return
    
    # Pull out pathing data from loader object
    cameras_folder_path = configuration_loader.cameras_folder_path
    camera_select = configuration_loader.camera_select
    user_select = configuration_loader.user_select
    
    # Build pathing to report data
    report_data_folder = build_user_report_path(cameras_folder_path, camera_select, user_select)
    os.makedirs(report_data_folder, exist_ok = True)
    
    # Check if data already exists
    existing_file_count, _, total_file_size_mb, _ = get_total_folder_size(report_data_folder)
    saved_data_exists = (existing_file_count > 0)
    
    # Provide prompt (if enabled) to allow user to avoid deleting existing data
    if saved_data_exists and enable_deletion_prompt:
        confirm_msg = "Saved data already exists! Delete? ({:.1f} MB)".format(total_file_size_mb)
        confirm_data_delete = cli_confirm(confirm_msg, default_response = True)
        if not confirm_data_delete:
            return
    
    # If we get here, delete the files!
    print("", "Deleting files:", "@ {}".format(report_data_folder), sep="\n")
    rmtree(report_data_folder)

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Parse Arguments

# Parse script arguments in case we're running automated
ap_result = parse_run_args()
save_and_keep = ap_result.get("save_keep", False)
save_and_delete = ap_result.get("save_delete", False)
skip_save = ap_result.get("skip_save", False)
provide_prompts = (not (save_and_keep or save_and_delete))

# ---------------------------------------------------------------------------------------------------------------------
#%% Setup

# Make all required selections and setup/configure everything
loader = File_Configuration_Loader()
loader.selections(ap_result)
loader.set_script_name(__file__)

# Ask user about saved data and delete existing data (if enabled)
save_data = save_data_prompt(provide_prompts, skip_save)
if save_data:
    delete_existing_report_data(provide_prompts, loader, save_and_keep)

# Turn on saving if needed and disable (save) threading to ensure deterministic timing when running files
loader.toggle_saving(save_data)
loader.toggle_threaded_saving(False)

# Configure everything!
start_timestamp = loader.setup_all()

# Set up object to handle all video processing
main_process = Video_Processing_Loop(loader)

# ---------------------------------------------------------------------------------------------------------------------
#%% Main

# Feedback on launch
enable_disable_txt = ("enabled" if save_data else "disabled")
print("", "{}  |  Saving {}".format(start_timestamp, enable_disable_txt), sep = "\n")

# Most of the work is done here!
total_processing_time_sec = main_process.loop(enable_progress_bar = True)
print("", "Finished! Took {:.1f} seconds".format(total_processing_time_sec), sep = "\n")

# ---------------------------------------------------------------------------------------------------------------------
#%% Clean up

# Run any cleanup needed by configured system
loader.clean_up()

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap

