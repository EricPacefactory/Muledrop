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

from local.lib.configuration_utils.configuration_loaders import Reconfigurable_Core_Stage_Loader
from local.lib.configuration_utils.video_processing_loops import Reconfigurable_Video_Loop
from local.lib.configuration_utils.display_specification import Display_Window_Specification, Preprocessed_Display
from local.lib.configuration_utils.display_specification import Filtered_Binary_Display

from local.configurables.core.pixel_filter._helper_functions import Color_Filtered

# ---------------------------------------------------------------------------------------------------------------------
#%% Define displays


class Color_Map(Display_Window_Specification):
    
    # .................................................................................................................
    
    def __init__(self, layout_index, num_rows, num_columns, initial_display = False):
        
        # Inherit from parent class
        super().__init__("Color Map", layout_index, num_rows, num_columns, 
                         initial_display = initial_display, 
                         max_wh = None)
        
        # Create circular hsv image
        image_size = 360
        self.color_frame_hsv, self.color_frame_bgr = create_circular_hsv_image(image_size)
        
        # Hard-code channel indices for safer referencing
        self.h_channel = 0
        self.s_channel = 1
        self.v_channel = 2
        
    # .................................................................................................................
     
    def display(self, stage_outputs, configurable_ref, mouse_xy,
                current_frame_index, current_time_sec, current_datetime):        
        
        # Get brightness display boundaries
        low_bound = configurable_ref._lower_tuple[self.v_channel]
        upper_bound = configurable_ref._upper_tuple[self.v_channel]
        mid_bound = int(round((low_bound + upper_bound) / 2))
        
        # Create a masked copy of the full-brightness circular-hsv image
        mid_value_frame_as_bgr = self._create_mid_value_frame(self.color_frame_hsv, mid_bound)
        mask_frame = self._create_color_mask_frame(mid_value_frame_as_bgr, configurable_ref)
        output_frame = cv2.bitwise_and(self.color_frame_bgr, mask_frame)
        
        return output_frame
    
    # .................................................................................................................
    
    def _create_mid_value_frame(self, color_frame_as_hsv, mid_value):
        
        # Create a copy of the circular-hsv image with a 'value' that shouldn't be filtered
        color_frame = self.color_frame_hsv.copy()
        color_frame[:, :, self.v_channel] = mid_value
        color_frame_bgr = cv2.cvtColor(color_frame, cv2.COLOR_HSV2BGR_FULL)
        
        return color_frame_bgr
    
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

def create_square_hsv_image(image_size_px, value = 255):
    
    # Create circular hsv image
    mesh_x, mesh_y = np.meshgrid(np.linspace(0, 255, image_size_px, dtype=np.uint8), 
                                 np.linspace(0, 255, image_size_px, dtype=np.uint8))
    
    # Assign hsv channels
    hue_frame = mesh_x
    sat_frame = mesh_y
    val_frame = value * np.ones_like(mesh_x)
    
    # Convert hsv image to uint8 & bgr formats for display
    frame_as_hsv = np.uint8(np.round(np.clip(np.dstack((hue_frame, sat_frame, val_frame)), 0, 255)))
    frame_as_bgr = cv2.cvtColor(frame_as_hsv, cv2.COLOR_HSV2BGR_FULL)
    
    return frame_as_hsv, frame_as_bgr

# .....................................................................................................................

def create_circular_hsv_image(image_size_px):
    
    # Create circular hsv image
    radial_mesh_x, radial_mesh_y = np.meshgrid(np.linspace(-1.0, 1.0, image_size_px), 
                                               np.linspace(-1.0, 1.0, image_size_px))
    hue_frame = 255.0 * (0.5 + (np.arctan2(radial_mesh_y, radial_mesh_x) / (2*np.pi)))
    sat_frame = 255.0 * np.sqrt(np.square(radial_mesh_x) + np.square(radial_mesh_y))
    val_frame = 255.0 * np.ones_like(radial_mesh_x)
    
    # Blank out values beyond 'full saturation'
    circle_mask = (sat_frame > 255.0)
    sat_frame[circle_mask] = 0.0
    val_frame[circle_mask] = 0.0
    
    # Convert hsv image to uint8 & bgr formats for display
    frame_as_hsv = np.uint8(np.round(np.clip(np.dstack((hue_frame, sat_frame, val_frame)), 0, 255)))
    frame_as_bgr = cv2.cvtColor(frame_as_hsv, cv2.COLOR_HSV2BGR_FULL)

    return frame_as_hsv, frame_as_bgr

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Main

# Make all required selections and setup/configure everything
loader = Reconfigurable_Core_Stage_Loader("pixel_filter", "hsv_pixelfilter", "Pixel_Filter_Stage")
loader.selections()
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

'''
TODO
- Add phase option to hue, so that 'inverted' regions can be created, without needing to invert everything
    - Or add inversion to all channels?
- Add brightness bar to color mapping visualization
'''

