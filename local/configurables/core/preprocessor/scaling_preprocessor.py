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
import numpy as np

from local.configurables.core.preprocessor.reference_preprocessor import Reference_Preprocessor

# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes
    

class Preprocessor_Stage(Reference_Preprocessor):
    
    # .................................................................................................................
    
    def __init__(self, input_wh):
        
        # Inherit reference functionality
        super().__init__(input_wh, file_dunder = __file__)
        
        # Allocate storage for calculated values
        self._fx = None
        self._fy = None
        self._output_w = None
        self._output_h = None
        
        # .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  . Control Group 1 .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .
        
        sg = self.controls_manager.new_control_group("Scaling Controls")
        
        self.enable_transform = \
        sg.attach_toggle("enable_transform", 
                         label = "Enable Transform", 
                         default_value = True,
                         visible = True)
        
        self.scale_factor = \
        sg.attach_slider("scale_factor", 
                         label = "Scaling Factor", 
                         default_value = 1.0,
                         min_value = 0.05, max_value = 1.0, step_size = 1/100,
                         return_type = float,
                         zero_referenced = True,
                         units = "percentage",
                         tooltip = "Scaling factor, relative to video size.")
        
        self.relative_aspect_ratio = \
        sg.attach_slider("relative_aspect_ratio", 
                         label = "Relative Aspect Ratio", 
                         default_value = 1.0,
                         min_value = -5.0, max_value = 5.0, step_size = 1/10,
                         return_type = float,
                         zero_referenced = False,
                         units = "normalized",
                         tooltip = "Aspect ratio adjustment, relative to input video frame.")
        
        self.interpolation_type = \
        sg.attach_menu("interpolation_type", 
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
        
        # Get input sizing
        input_w, input_h = self.input_wh
        input_area = input_w * input_h
        input_ratio = input_w / input_h
        
        # Figure out altered sizing
        adjusted_area = self.scale_factor * self.scale_factor * input_area
        adjustment_is_positive = (self.relative_aspect_ratio >= 0.0)
        adjust_intercept = 1.0
        adjust_slope = (input_ratio - adjust_intercept) / 1.0
        new_ratio = abs(self.relative_aspect_ratio * adjust_slope) + adjust_intercept
        adjusted_ratio = new_ratio if adjustment_is_positive else (1 / new_ratio)
        
        # Calculate output pixel values
        output_w = np.sqrt(adjusted_area * adjusted_ratio)
        output_h = adjusted_area / output_w
        
        # Calculate scaling factors
        self._fx = output_w / input_w
        self._fy = output_h / input_h
        
        # Store effective output pixel values
        self._output_w = int(round(self._fx * input_w))
        self._output_h = int(round(self._fy * input_h))
    
    # .................................................................................................................
    
    def apply_transformation(self, frame):
        
        # Short-cut transformation if it's been disabled
        if not self.enable_transform:
            return frame
        
        try:
            return cv2.resize(frame, dsize = None, fx = self._fx, fy = self._fy, 
                              interpolation = self.interpolation_type)
        except Exception as err:
            print("ERROR TRANSFORMING ({})".format(self.script_name))
            print(err)
            #print(self.output_w, self.output_h, self.interpolation_type)
            return frame
        
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

