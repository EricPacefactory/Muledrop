#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue May 26 11:11:11 2020

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

from local.lib.launcher_utils.configuration_loaders import Reconfigurable_Background_Capture_Loader
from local.lib.launcher_utils.video_processing_loops import Background_Capture_Video_Loop

from local.lib.ui_utils.display_specification import Input_Display, Background_Display

from local.configurables.externals.background_capture._helper_functions import Stats_Display


# ---------------------------------------------------------------------------------------------------------------------
#%% Define displays

class Custom_Stats_Display(Stats_Display):
    
    # .................................................................................................................
    
    def _max_ram_usage_mb(self, configurable_ref, ram_mb_per_frame):
        
        # Rolling average loads 2 frames (1 capture + 1 newest generated background)
        max_frame_count = 2
        
        return ram_mb_per_frame * max_frame_count

    # .................................................................................................................
    # .................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Main

# For clarity
target_script_name = "rollingaverage_backgroundcapture"

# Make all required selections
loader = Reconfigurable_Background_Capture_Loader(target_script_name)
arg_selections = loader.parse_standard_args()
loader.selections(*arg_selections)

# Ask to clear resources used for background capture/generation
loader.ask_to_reset_resources()

# Set up video capture, processing stages & playback control
configurable_ref = loader.setup_all(__file__)

# Set up object to handle all video processing
main_process = \
Background_Capture_Video_Loop(loader,
                              ordered_display_list = [Input_Display(1, 2, 2, limit_wh = True),
                                                      Background_Display(0, 2, 2, limit_wh = True),
                                                      Custom_Stats_Display(2, 2, 2)])

# Most of the work is done here!
main_process.loop()

# Ask user to save config
loader.ask_to_save_configurable_cli(__file__, configurable_ref)


# ---------------------------------------------------------------------------------------------------------------------
#%% For debugging

# Access results for debugging
final_frame = main_process.debug_frame
final_fed_time_args = main_process.debug_fed_time_args
debug_dict = main_process.debug_dict


# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap


