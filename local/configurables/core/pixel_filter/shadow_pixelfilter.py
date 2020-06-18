#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Oct  9 11:27:04 2019

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
from local.configurables.core.pixel_filter._helper_functions import inRange_with_colorspace

# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes

class Pixel_Filter_Stage(Reference_Pixel_Filter):
    
    # .................................................................................................................
    
    def __init__(self, cameras_folder_path, camera_select, user_select, input_wh):
        
        # Inherit reference functionality
        super().__init__(cameras_folder_path, camera_select, user_select, input_wh, file_dunder = __file__)
        
        # Allocate space for derived variables
        self._blur_kernel = None
        
        # Allocate storage for the background image, which is needed to find shadows
        self.current_background_bgr = None
        self.current_background_hsv = None
        
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
        
        self.blur_size = \
        self.ctrl_spec.attach_slider(
                "blur_size", 
                label = "Blurriness", 
                default_value = 0,
                min_value = 0,
                max_value = 15,
                return_type = int,
                tooltip = "Amount of blurring to apply to a frame before filtering out shadows.")
        
        self.lower_shadow_threshold = \
        self.ctrl_spec.attach_slider(
                "lower_shadow_threshold", 
                label = "Lower Shadow Threshold", 
                default_value = 0,
                min_value = 0,
                max_value = 255,
                return_type = int)
        
        self.upper_shadow_threshold = \
        self.ctrl_spec.attach_slider(
                "upper_shadow_threshold", 
                label = "Upper Shadow Threshold", 
                default_value = 10,
                min_value = 0,
                max_value = 255,
                return_type = int)
        
    # .................................................................................................................
    
    def reset(self):
        self.filter_mask = None
        
    # .................................................................................................................
    
    def setup(self, variables_changed_dict):
        
        blur_kernel_size = 3 + 2*self.blur_size
        self._blur_kernel = (blur_kernel_size, blur_kernel_size)
    
    # .................................................................................................................
    
    def apply_pixel_filtering(self, binary_frame_1ch, color_frame):
        
        try:
            
            
            hsv_frame = cv2.cvtColor(color_frame, cv2.COLOR_BGR2HSV_FULL)
            diff_frame = cv2.absdiff(hsv_frame, self.current_background_hsv)
            gray_frame = diff_frame[:,:,2]#cv2.cvtColor(diff_frame[:,:,2], cv2.COLOR_BGR2GRAY)
            blur_frame = cv2.blur(gray_frame, self._blur_kernel)
            
            _, lower_thresh_frame = cv2.threshold(blur_frame, self.lower_shadow_threshold, 255, cv2.THRESH_BINARY)
            _, upper_thresh_frame = cv2.threshold(blur_frame, self.upper_shadow_threshold, 255, cv2.THRESH_BINARY_INV)
            thresh_frame = cv2.bitwise_and(lower_thresh_frame, upper_thresh_frame)
            
            return thresh_frame
            
            # Skip masking if not enabled
            if not self.enable_filter:
                return binary_frame_1ch
            
            # Generate filter mask
            scaled_color_frame = cv2.resize(color_frame, dsize = self.input_wh)
            self.filter_mask = self._color_filter(scaled_color_frame)
            
            # Apply color mask to existing binary frame
            new_binary_frame_1ch = cv2.bitwise_and(self.filter_mask, binary_frame_1ch)
            
            return new_binary_frame_1ch
        
        except cv2.error as err:
            self.log("ERROR FILTERING ({})".format(self.script_name))
            if self.configure_mode:
                raise err
        
        return binary_frame_1ch
    
    # .................................................................................................................
    
    def update_background(self, preprocessed_background_frame, bg_update):
        
        # Store backgrounds
        if bg_update or (self.current_background_bgr is None):
            
            # Store the 'clean' background for reference
            self.current_background_bgr = preprocessed_background_frame
            self.current_background_hsv = cv2.cvtColor(self.current_background_bgr, cv2.COLOR_BGR2HSV_FULL)
        
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



    