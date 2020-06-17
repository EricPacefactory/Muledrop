#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed May 29 15:08:52 2019

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

from local.configurables.core.pixel_filter.reference_pixelfilter import Reference_Pixel_Filter

# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes

class Pixel_Filter_Stage(Reference_Pixel_Filter):
    
    # .................................................................................................................
    
    def __init__(self, cameras_folder_path, camera_select, user_select, input_wh):
        
        # Inherit reference functionality
        super().__init__(cameras_folder_path, camera_select, user_select, input_wh, file_dunder = __file__)
        
        # Allocate storage for derived variables
        self._lower_tuple = (0, 0, 0)
        self._upper_tuple = (255, 255, 255)
        
        # Allocate storage for the filter mask, mainly for visualization purposes
        self.filter_mask = None
        
        # .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  . Control Group 1 .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .
        
        self.ctrl_spec.new_control_group("Main Controls")
        
        self.enable_filter = \
        self.ctrl_spec.attach_toggle(
                "enable_filter",
                label = "Enable filtering",
                default_value = True)
        
        self.invert_filter = \
        self.ctrl_spec.attach_toggle(
                "invert_filter",
                label = "Invert",
                default_value = False)
        
        # .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  . Control Group 2 .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .
        
        self.ctrl_spec.new_control_group("Red Controls")
        
        self.red_lower = \
        self.ctrl_spec.attach_slider(
                "red_lower", 
                label = "Lower Red", 
                default_value = 0,
                min_value = 0,
                max_value = 255,
                return_type = int)
        
        self.red_upper = \
        self.ctrl_spec.attach_slider(
                "red_upper", 
                label = "Upper Red", 
                default_value = 255,
                min_value = 0,
                max_value = 255,
                return_type = int)
        
        # .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  . Control Group 3 .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .
        
        self.ctrl_spec.new_control_group("Green Controls")
        
        self.green_lower = \
        self.ctrl_spec.attach_slider(
                "green_lower", 
                label = "Lower Green", 
                default_value = 0,
                min_value = 0,
                max_value = 255,
                return_type = int)
        
        self.green_upper = \
        self.ctrl_spec.attach_slider(
                "green_upper", 
                label = "Upper Green", 
                default_value = 255,
                min_value = 0,
                max_value = 255,
                return_type = int)
        
        # .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  . Control Group 4 .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .
        
        self.ctrl_spec.new_control_group("Blue Controls")
        
        self.blue_lower = \
        self.ctrl_spec.attach_slider(
                "blue_lower", 
                label = "Lower Blue", 
                default_value = 0,
                min_value = 0,
                max_value = 255,
                return_type = int)
        
        self.blue_upper = \
        self.ctrl_spec.attach_slider(
                "blue_upper", 
                label = "Upper Blue", 
                default_value = 255,
                min_value = 0,
                max_value = 255,
                return_type = int)
        
    # .................................................................................................................
    
    def reset(self):
        self.filter_mask = None
        
    # .................................................................................................................
    
    def setup(self, variables_changed_dict):
        
        red_low = self.red_lower
        red_high = self.red_upper
        
        green_low = self.green_lower
        green_high = self.green_upper
        
        blue_low = self.blue_lower
        blue_high = self.blue_upper
        
        self._lower_tuple = (blue_low, green_low, red_low)
        self._upper_tuple = (blue_high, green_high, red_high)
    
    # .................................................................................................................
    
    def apply_pixel_filtering(self, binary_frame_1ch, color_frame):
        try:
            
            # Skip masking if not enabled
            if not self.enable_filter:
                return binary_frame_1ch
            
            # Generate filter mask
            scaled_color_frame = cv2.resize(color_frame, dsize = self.input_wh)
            self.filter_mask = self._color_filter(scaled_color_frame)
            
            # Apply color mask to existing binary frame
            new_binary_frame_1ch = cv2.bitwise_and(self.filter_mask, binary_frame_1ch)
            
            return new_binary_frame_1ch
        except Exception as err:
            print("PIXEL PROCESSOR: FRAME ERROR".format(self.script_name))
            print(err)
            return binary_frame_1ch
    
    # .................................................................................................................
    
    def update_background(self, preprocessed_background_frame, bg_update):
        # No background processing        
        return None
    
    # .................................................................................................................
    
    def _color_filter(self, bgr_color_frame):
        
        # Filter out lower/upper bounds from the color frame
        binary_filter_1d = cv2.inRange(bgr_color_frame, self._lower_tuple, self._upper_tuple)
        
        # Invert the filter if needed
        return cv2.bitwise_not(binary_filter_1d) if self.invert_filter else binary_filter_1d 
    
    # .................................................................................................................
    # .................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

# .....................................................................................................................

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Demo
    
if __name__ == "__main__":
    pass
    

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap



    