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

from local.lib.configuration_utils.configuration_loaders import Configuration_Loader
from local.lib.configuration_utils.video_processing_loops import Video_Processing_Loop

from local.lib.file_access_utils.reporting import build_user_report_path

from eolib.utils.files import get_total_folder_size
from eolib.utils.cli_tools import cli_confirm

# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

# .....................................................................................................................

def save_data_prompt(configuration_loader, save_by_default = False):
    
    # Pull out pathing data from loader object
    cameras_folder_path = configuration_loader.cameras_folder_path
    camera_select = configuration_loader.camera_select
    user_select = configuration_loader.user_select
    
    # For testing
    saving_enabled = cli_confirm("Save data?", default_response = save_by_default)
    
    # If data already exists, ask if we should delete it
    report_data_folder = build_user_report_path(cameras_folder_path, camera_select, user_select)
    existing_file_count, _, total_file_size_mb, _ = get_total_folder_size(report_data_folder)
    saved_data_exists = (existing_file_count > 0)
    if saving_enabled and saved_data_exists:
        confirm_msg = "Saved data already exists! Delete? ({:.1f} MB)".format(total_file_size_mb)
        confirm_data_delete = cli_confirm(confirm_msg, default_response = True)
        if confirm_data_delete:
            print("", "Deleting files:", "@ {}".format(report_data_folder), sep="\n")
            rmtree(report_data_folder)
            
    return saving_enabled

# .....................................................................................................................

def enable_display_prompt(saving_enabled = True):    
    default_response = False if saving_enabled else True    
    return cli_confirm("Display processing results (slower)?", default_response = default_response)

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Main

# Make all required selections and setup/configure everything
loader = Configuration_Loader()
loader.selections()

# Ask user about saved data
save_data = save_data_prompt(loader)
loader.toggle_saving(save_data)
loader.toggle_threading(False)  # Disable threading to ensure deterministic timing when running files

# Ask the user about displaying results
enable_display = enable_display_prompt(saving_enabled = save_data)

# Configure everything!
loader.setup_all()

# Set up object to handle all video processing
main_process = \
Video_Processing_Loop(loader)

# Most of the work is done here!
print("", "Running...", sep = "\n")
total_processing_time_sec = main_process.loop(enable_display)
print("", "Finished! Took {:.1f} seconds".format(total_processing_time_sec), sep = "\n")



# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap

'''
TODO:
    - Clean up display implementation, very awkward
        - will need to add script argument for display enabling
        - Maybe add progress bar (tqdm?) when display isn't available (also a script arg? Only needed on files)
        - Would be nice to have opencv progress bar when display is available as well, to indicate time-to-finish
'''


