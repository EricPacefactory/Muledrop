#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue May 28 16:30:57 2019

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

import numpy as np

from local.lib.launcher_utils.configuration_loaders import Reconfigurable_Core_Stage_Loader
from local.lib.launcher_utils.video_processing_loops import Reconfigurable_Video_Loop

from local.lib.ui_utils.display_specification import Display_Window_Specification
from local.lib.ui_utils.display_specification import Input_Display
from local.lib.ui_utils.display_specification import Preprocessed_Display

from local.eolib.video.text_rendering import simple_text

# ---------------------------------------------------------------------------------------------------------------------
#%% Define displays

class Scaling_Info(Display_Window_Specification):
    
    # .................................................................................................................
    
    def __init__(self, layout_index, num_rows, num_columns, initial_display = False):
        
        # Inherit from parent class
        super().__init__("Scaling Info", layout_index, num_rows, num_columns, 
                         initial_display = initial_display, 
                         limit_wh = False)
        
        # Allocate storage for blank image used to draw info on
        self._info_frame = np.full((150, 400, 3), (40,40,40), dtype=np.uint8)
        
    # .................................................................................................................
        
    def display(self, stage_outputs, configurable_ref, mouse_xy,
                current_frame_index, current_epoch_ms, current_datetime):
        
        # Create a blank frame for drawing
        display_frame = self._info_frame.copy()
        
        # Get sizing info
        input_width, input_height = configurable_ref.input_wh
        output_width, output_height = configurable_ref._output_w, configurable_ref._output_h
        
        # Get aspect ratios
        in_ar = input_width / input_height
        out_ar = output_width / output_height
        
        # Build strings for printing
        input_scale_text =\
        " Input dimensions (px): {:.0f} x {:.0f}  ~  {:.3f}".format(input_width, input_height, in_ar)
        output_text = \
        "Output dimensions (px): {:.0f} x {:.0f}  ~  {:.3f}".format(output_width, output_height, out_ar)
        
        # Write scaling info text into the image
        simple_text(display_frame, "--- Scaling Info ---", (200, 15), center_text = True)
        simple_text(display_frame, input_scale_text, (5, 70))
        simple_text(display_frame, output_text, (5, 110))
        
        return display_frame
    
    # .................................................................................................................
    # .................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions


# ---------------------------------------------------------------------------------------------------------------------
#%% Main

# Make all required selections
loader = Reconfigurable_Core_Stage_Loader("preprocessor", "scaling_preprocessor", "Preprocessor_Stage")
arg_selections = loader.parse_standard_args()
loader.selections(*arg_selections)

# Set up video capture, processing stages & playback control
configurable_ref = loader.setup_all(__file__)

# Set up object to handle all video processing
main_process = \
Reconfigurable_Video_Loop(loader,
                          ordered_display_list = [Input_Display(2, 3, 2),
                                                  Preprocessed_Display(3, 3, 2, limit_wh = False),
                                                  Scaling_Info(1, 3, 2)])

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



