#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Jan  5 14:35:35 2021

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

import cv2

from local.lib.launcher_utils.configuration_loaders import Reconfigurable_Core_Stage_Loader
from local.lib.launcher_utils.video_processing_loops import Reconfigurable_Video_Loop

from local.lib.ui_utils.display_specification import Display_Window_Specification, Binary_Display

from local.configurables.core.foreground_extractor._helper_functions import Outlined_Input, Masked_Differences


# ---------------------------------------------------------------------------------------------------------------------
#%% Define displays

class Learned_BG_Display(Display_Window_Specification):
    
    # .................................................................................................................
    
    def __init__(self, layout_index, num_rows, num_columns, initial_display = False, limit_wh = True,
                 window_name = "MoG2 Background"):
        
        # Inherit from parent class
        super().__init__(window_name, layout_index, num_rows, num_columns,
                         initial_display = initial_display,
                         limit_wh = limit_wh)
        
    # .................................................................................................................
        
    def display(self, stage_outputs, configurable_ref, mouse_xy,
                current_frame_index, current_epoch_ms, current_datetime):
        
        # Pull the rolling background out of the configurable
        learned_bg_frame = configurable_ref._bgsubtractor.getBackgroundImage()
        
        # Scale it to the display size
        display_height, display_width = stage_outputs["preprocessor"]["preprocessed_frame"].shape[0:2]
        
        return cv2.resize(learned_bg_frame, dsize = (display_width, display_height),
                          interpolation = cv2.INTER_NEAREST)
        
    # .................................................................................................................
    # .................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Main

# For clarity
target_core_stage_name = "foreground_extractor"
target_script_name = "mog2_fgextractor"

# Make all required selections
loader = Reconfigurable_Core_Stage_Loader(target_core_stage_name, target_script_name)
arg_selections = loader.parse_standard_args()
loader.selections(*arg_selections)

# Set up video capture, processing stages & playback control
configurable_ref = loader.setup_all(__file__)

# Get drawing specification for the given zone variable
zone_drawing_spec = configurable_ref.get_drawing_spec("mask_zone_list")

# Set up object to handle all video processing
main_process = \
Reconfigurable_Video_Loop(loader,
                          ordered_display_list = [Outlined_Input(0, 2, 2, drawing_json = zone_drawing_spec),
                                                  Binary_Display(1, 2, 2),
                                                  Masked_Differences(2, 2, 2),
                                                  Learned_BG_Display(3, 2, 2)])

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


