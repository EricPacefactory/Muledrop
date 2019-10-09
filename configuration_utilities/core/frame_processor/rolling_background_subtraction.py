#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Aug 23 15:34:41 2019

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

from local.lib.configuration_utils.configuration_loaders import Reconfigurable_Core_Stage_Loader
from local.lib.configuration_utils.video_processing_loops import Reconfigurable_Video_Loop
from local.lib.configuration_utils.display_specification import Display_Window_Specification, Binary_Display

from local.configurables.core.frame_processor._helper_functions import Outlined_Input, Masked_Differences

# ---------------------------------------------------------------------------------------------------------------------
#%% Define displays

class Rolling_BG_Display(Display_Window_Specification):
    
    # .................................................................................................................
    
    def __init__(self, layout_index, num_rows, num_columns, initial_display = False, max_wh = None,
                 window_name = "Rolling Background"):
        
        # Inherit from parent class
        super().__init__(window_name, layout_index, num_rows, num_columns, 
                         initial_display = initial_display, 
                         max_wh = max_wh)
        
    # .................................................................................................................
        
    def display(self, stage_outputs, configurable_ref, mouse_xy,
                current_frame_index, current_time_sec, current_datetime):
        
        # Pull the rolling background out of the configurable
        rolling_background_frame = configurable_ref._rolling_bg_frame_uint8
        
        # Scale it to the display size
        display_height, display_width = stage_outputs.get("preprocessor").get("preprocessed_frame").shape[0:2]
        
        return cv2.resize(rolling_background_frame, dsize = (display_width, display_height), 
                          interpolation = cv2.INTER_NEAREST)
        
    # .................................................................................................................
    # .................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions


# ---------------------------------------------------------------------------------------------------------------------
#%% Main

# Make all required selections and setup/configure everything
loader = Reconfigurable_Core_Stage_Loader("frame_processor", "rolling_bgs_frameprocessor", "Frame_Processor_Stage")
loader.selections()
configurable_ref = loader.setup_all(__file__)

# Get drawing specification for the given zone variable
zone_drawing_spec = configurable_ref.get_drawing_spec("mask_zone_list")

# Set up object to handle all video processing
main_process = \
Reconfigurable_Video_Loop(loader,
                          ordered_display_list = [Outlined_Input(0, 2, 2, drawing_json = zone_drawing_spec),
                                                  Binary_Display(1, 2, 2),
                                                  Masked_Differences(2, 2, 2),
                                                  Rolling_BG_Display(3, 2, 2)])

# Most of the work is done here!
main_process.loop()


# ---------------------------------------------------------------------------------------------------------------------
#%% For debugging

# Access results for debugging
last_frame = main_process.debug_frame
stage_outputs = main_process.debug_stage_outputs
stage_timing = main_process.debug_stage_timing
object_ids_in_frame_dict = main_process.debug_object_ids_in_frame_dict
snapshot_metadata = main_process.debug_current_snapshot_metadata
last_frame_index, last_time_sec, last_datetime = main_process.debug_fsd_time_args

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap


