#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Mar 29 12:50:40 2019

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

from local.lib.common.images import max_dimension_downscale

from local.configurables.core.preprocessor.reference_preprocessor import Reference_Preprocessor
from local.configurables.core.preprocessor._helper_functions import adjust_aspect_ratio


# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes
    

class Preprocessor_Stage(Reference_Preprocessor):
    
    # .................................................................................................................
    
    def __init__(self, cameras_folder_path, camera_select, user_select, input_wh):
        
        # Inherit reference functionality
        super().__init__(cameras_folder_path, camera_select, user_select, input_wh, file_dunder = __file__)
        
        # Allocate storage for calculated values
        self._output_w = None
        self._output_h = None
        self._enable_scaling = True
        self._scaled_wh = None
        
        # .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  . Control Group 1 .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .
        
        self.ctrl_spec.new_control_group("Scaling Controls")
        
        self.enable_transform = \
        self.ctrl_spec.attach_toggle(
                "enable_transform", 
                label = "Enable Transform", 
                default_value = True,
                visible = True)
        
        self.max_dimension_px = \
        self.ctrl_spec.attach_slider(
                "max_dimension_px", 
                label = "Max Dimension", 
                default_value = 640,
                min_value = 100, max_value = 1280,
                units = "pixels",
                return_type = int,
                zero_referenced = True,
                tooltip = "Resize frame data so that the maximum side length does not exceed this amount.")
        
        self.ar_adjustment_factor = \
        self.ctrl_spec.attach_slider(
                "ar_adjustment_factor", 
                label = "Relative Aspect Ratio", 
                default_value = 1.0,
                min_value = -5.0, max_value = 5.0, step_size = 1/10,
                return_type = float,
                zero_referenced = False,
                units = "normalized",
                tooltip = "Aspect ratio adjustment, relative to input video frame.")
        
        self.interpolation_type = \
        self.ctrl_spec.attach_menu(
                "interpolation_type", 
                label = "Interpolation", 
                default_value = "Nearest Neighbor", 
                option_label_value_list = [("Nearest Neighbor", cv2.INTER_NEAREST),
                                           ("Bilinear", cv2.INTER_LINEAR),
                                           ("Cubic", cv2.INTER_CUBIC)], 
                tooltip = "Set the interpolation style for pixels sampled at fractional indices", 
                visible = True)
        
    # .................................................................................................................
    
    def set_output_wh(self):
        # OVERRIDING FROM PARENT CLASS
        self.output_wh = (self._output_w, self._output_h)
        
    # .................................................................................................................
    
    def reset(self):
        # No data in storage, nothing to reset
        return
    
    # .................................................................................................................
    
    def setup(self, variable_update_dictionary):
        
        # Check aspect-ratio and sizing adjustments
        needs_ar_adjustment, ar_adjusted_wh = adjust_aspect_ratio(self.input_wh, self.ar_adjustment_factor)
        needs_downscale, downscale_wh = max_dimension_downscale(ar_adjusted_wh, self.max_dimension_px)
        
        # Set final scaling!
        self._enable_scaling = (needs_ar_adjustment or needs_downscale)
        self._scaled_wh = downscale_wh if needs_downscale else ar_adjusted_wh
        
        # Set required output sizing info
        self._output_w, self._output_h = self._scaled_wh if self.enable_transform else self.input_wh
    
    # .................................................................................................................
    
    def apply_transformation(self, frame):
        
        # Short-cut transformation if it's been disabled
        if not self.enable_transform:
            return frame
        
        try:
            if self._enable_scaling:
                return cv2.resize(frame, dsize = self._scaled_wh, interpolation = self.interpolation_type)
            return frame
        
        except cv2.error as err:
            self.log("ERROR TRANSFORMING ({})".format(self.script_name))
            if self.configure_mode:
                raise err
        
        return frame
    
    # .................................................................................................................
    
    def unwarp_required(self):
        # No unwarp needed!
        return False
    
    # .................................................................................................................

    def unwarp_xy(self, warped_normalized_xy_npfloat32):
        # No unwarp needed!
        return None
        
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

