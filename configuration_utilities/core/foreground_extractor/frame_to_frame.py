#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed May 29 16:02:00 2019

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

from local.lib.launcher_utils.configuration_loaders import Reconfigurable_Core_Stage_Loader
from local.lib.launcher_utils.video_processing_loops import Reconfigurable_Video_Loop

from local.lib.ui_utils.display_specification import Binary_Display

from local.configurables.core.foreground_extractor._helper_functions import Outlined_Input, Masked_Differences

# ---------------------------------------------------------------------------------------------------------------------
#%% Define displays



# ---------------------------------------------------------------------------------------------------------------------
#%% Main

# Make all required selections and setup/configure everything
loader = Reconfigurable_Core_Stage_Loader("foreground_extractor", "ftf_fgextractor", "FG_Extractor_Stage")
configurable_ref = loader.setup_all(__file__)

# Get drawing specification for the given zone variable
zone_drawing_spec = configurable_ref.get_drawing_spec("mask_zone_list")

# Set up object to handle all video processing
main_process = \
Reconfigurable_Video_Loop(loader,
                          ordered_display_list = [Outlined_Input(0, 2, 2, drawing_json = zone_drawing_spec),
                                                  Binary_Display(1, 2, 2),
                                                  Masked_Differences(2, 2, 2)])

# Most of the work is done here!
main_process.loop()


# ---------------------------------------------------------------------------------------------------------------------
#%% For debugging

# Access results for debugging
final_frame = main_process.debug_frame
stage_outputs = main_process.debug_stage_outputs
stage_timing = main_process.debug_stage_timing
snapshot_metadata = main_process.debug_current_snapshot_metadata
final_frame_index, final_epoch_ms, final_datetime = main_process.debug_fed_time_args

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap

'''
TODO:
    - Get internal image storage + retrievable outputs/collage working (also, colored threshold image?!)
    - BUG: Why does difference image flicker when changing parameters after playback reset?
'''