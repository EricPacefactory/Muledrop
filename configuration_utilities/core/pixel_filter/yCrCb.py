#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed May 29 11:34:15 2019

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
import numpy as np

from local.lib.launcher_utils.configuration_loaders import Reconfigurable_Core_Stage_Loader
from local.lib.launcher_utils.video_processing_loops import Reconfigurable_Video_Loop

from local.lib.ui_utils.display_specification import Display_Window_Specification, Preprocessed_Display
from local.lib.ui_utils.display_specification import Filtered_Binary_Display

from local.configurables.core.pixel_filter._helper_functions import Color_Filtered

# ---------------------------------------------------------------------------------------------------------------------
#%% Define displays

class Color_Map(Display_Window_Specification):
    
    # .................................................................................................................
    
    def __init__(self, layout_index, num_rows, num_columns, initial_display = False):
        
        # Inherit from parent class
        super().__init__("Color Map", layout_index, num_rows, num_columns, 
                         initial_display = initial_display, 
                         limit_wh = False)
        
        # Create color-space image
        image_size = 256
        self.color_frame_ycrcb, self.color_frame_bgr = create_stacked_ycrcb_image(image_size)
        
        # Hard-code channel indices for safer referencing
        self.l_channel = 0
        self.r_channel = 1
        self.b_channel = 2
    
    # .................................................................................................................
    
    def display(self, stage_outputs, configurable_ref, mouse_xy,
                current_frame_index, current_epoch_ms, current_datetime):        
        
        # Create a masked copy of the full-luma ycrcb color space image
        mask_frame = self._create_color_mask_frame(self.color_frame_bgr, configurable_ref)
        output_frame = cv2.bitwise_and(self.color_frame_bgr, mask_frame)
        
        return output_frame
    
    # .................................................................................................................
    
    def _create_color_mask_frame(self, bgr_color_frame, configurable_ref):
        
        color_filter_1d = configurable_ref._color_filter(bgr_color_frame)
        color_filter_3d = cv2.cvtColor(color_filter_1d, cv2.COLOR_GRAY2BGR)
        
        return color_filter_3d
        
    # .................................................................................................................
    # .................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

# .....................................................................................................................
  
def create_stacked_ycrcb_image(image_size_px):
    
    # Create incrementing mesh frames for color co-orinate systems
    mesh_frame_x, mesh_frame_y = np.meshgrid(np.linspace(0, 255, image_size_px),
                                             np.linspace(0, 255, image_size_px))
    base_ycrcb = np.empty((image_size_px, image_size_px, 3), dtype=np.uint8)
    base_ycrcb[:, :, 0] = 255
    base_ycrcb[:, :, 1] = np.uint8(np.round(mesh_frame_x))
    base_ycrcb[:, :, 2] = np.uint8(np.round(mesh_frame_y))
    
    # Create copies of ycrcb color space so we can draw low/mid/high versions
    low_luma = base_ycrcb.copy()
    mid_luma = base_ycrcb.copy()
    high_luma = base_ycrcb.copy()
    
    # Replace luma channels
    low_luma[:, :, 0] = 15
    mid_luma[:, :, 0] = 127
    high_luma[:, :, 0] = 240

    # Stack low/mid/high color space images together,to help user understand affect of y/cr/cb controls    
    frame_as_ycrcb = np.hstack((low_luma, mid_luma, high_luma))    
    frame_as_bgr = cv2.cvtColor(frame_as_ycrcb, cv2.COLOR_YCrCb2BGR)
    
    return frame_as_ycrcb, frame_as_bgr

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Main

# Make all required selections
loader = Reconfigurable_Core_Stage_Loader("pixel_filter", "ycrcb_pixelfilter", "Pixel_Filter_Stage")
arg_selections = loader.parse_standard_args()
loader.selections(*arg_selections)

# Set up video capture, processing stages & playback control
configurable_ref = loader.setup_all(__file__)

# Set up object to handle all video processing
main_process = \
Reconfigurable_Video_Loop(loader,
                          ordered_display_list = [Preprocessed_Display(0, 2, 2),
                                                  Color_Filtered(1, 2, 2),
                                                  Filtered_Binary_Display(2, 2, 2),
                                                  Color_Map(3, 2, 2)])

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

'''
TODO
- Figure out better way to visualize ycrcb color space...
'''
