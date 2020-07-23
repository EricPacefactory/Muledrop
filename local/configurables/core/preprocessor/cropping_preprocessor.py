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

import numpy as np

from local.configurables.core.preprocessor.reference_preprocessor import Reference_Preprocessor


# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes
    

class Preprocessor_Stage(Reference_Preprocessor):
    
    # .................................................................................................................
    
    def __init__(self, location_select_folder_path, camera_select, input_wh):
        
        # Inherit reference functionality
        super().__init__(location_select_folder_path, camera_select, input_wh, file_dunder = __file__)
        
        # Allocate storage for calculated values
        self._output_w = None
        self._output_h = None
        self._enable_cropping = True
        self._crop_y1y2x1x2 = None
        
        # .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  . Control Group 1 .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .
        
        self.ctrl_spec.new_control_group("Scaling Controls")
        
        self.enable_transform = \
        self.ctrl_spec.attach_toggle(
                "enable_transform", 
                label = "Enable Transform", 
                default_value = True,
                visible = True)
        
        # .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  . Control Group 2 .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .
        
        self.ctrl_spec.new_control_group("Width Cropping Controls")
        
        self.left_edge_crop = \
        self.ctrl_spec.attach_slider(
                "left_edge_crop", 
                label = "Left Edge", 
                default_value = 0.0,
                min_value = 0.0, max_value = 1.0, step_size = 1/1000,
                return_type = float,
                zero_referenced = True,
                units = "normalized",
                tooltip = "Location of the left edge (after cropping) relative to the input frame")
        
        self.right_edge_crop = \
        self.ctrl_spec.attach_slider(
                "right_edge_crop", 
                label = "Right Edge", 
                default_value = 1.0,
                min_value = 0.0, max_value = 1.0, step_size = 1/1000,
                return_type = float,
                zero_referenced = True,
                units = "normalized",
                tooltip = "Location of the right edge (after cropping) relative to the input frame")
        
        # .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  . Control Group 3 .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .
        
        self.ctrl_spec.new_control_group("Height Cropping Controls")
        
        self.top_edge_crop = \
        self.ctrl_spec.attach_slider(
                "top_edge_crop", 
                label = "Top Edge", 
                default_value = 0.0,
                min_value = 0.0, max_value = 1.0, step_size = 1/1000,
                return_type = float,
                zero_referenced = True,
                units = "normalized",
                tooltip = "Location of the top edge (after cropping) relative to the input frame")
        
        self.bot_edge_crop = \
        self.ctrl_spec.attach_slider(
                "bot_edge_crop", 
                label = "Bottom Edge", 
                default_value = 1.0,
                min_value = 0.0, max_value = 1.0, step_size = 1/1000,
                return_type = float,
                zero_referenced = True,
                units = "normalized",
                tooltip = "Location of the bottom edge (after cropping) relative to the input frame")
        
        
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
        
        
        # Convert (normalized) crop values to pixel co-ordinates
        input_width, input_height = self.input_wh
        
        x1_px = int(round(self.left_edge_crop * (input_width - 1)))
        x2_px = int(round(self.right_edge_crop * (input_width - 1)))
        y1_px = int(round(self.top_edge_crop * (input_height - 1)))
        y2_px = int(round(self.bot_edge_crop * (input_height - 1)))
        
        # Make sure boundaries are ordered correctly and that there is a minimum sized frame after cropping
        x1 = min(x1_px, input_width - 10 - 1)
        x2 = max(x1_px + 10, x2_px) + 1
        y1 = min(y1_px, input_height - 10 - 1)
        y2 = max(y1_px + 10, y2_px) + 1
        
        # Bundle cropping co-ords for convenience
        self._crop_y1y2x1x2 = [y1, y2, x1, x2]
        
        # Figure out the output sizing, and decide if we need to enable cropping
        output_width = (x2 - x1)
        output_height = (y2 - y1)
        self._enable_cropping = (output_width != input_width) or (output_height != input_height)
        
        # Finally, store the output sizing for the next stage
        self._output_w = output_width
        self._output_h = output_height        
    
    # .................................................................................................................
    
    def apply_transformation(self, frame):
        
        # Short-cut transformation if it's been disabled
        if not self.enable_transform:
            return frame
        
        try:
            
            # Only crop if we have cropping co-ords!
            if self._enable_cropping:
                y1, y2, x1, x2 = self._crop_y1y2x1x2
                return frame[y1:y2, x1:x2]
            return frame
        
        except IndexError as err:
            self.log("INDEXING ERROR ({})".format(self.script_name))
            if self.configure_mode:
                raise err
        
        return frame
    
    # .................................................................................................................
    
    def unwarp_required(self):
        # Only need to unwarp if cropping is enabled
        return self._enable_cropping
    
    # .................................................................................................................

    def unwarp_xy(self, warped_normalized_xy_npfloat32):
        
        # Get important crop scaling values
        input_width, input_height = self.input_wh
        crop_width, crop_height = self.output_wh
        crop_y1, _, crop_x1, _ = self._crop_y1y2x1x2
        
        # If we do crop, the unwarp is handled 
        new_x = ((warped_normalized_xy_npfloat32[:, 0] * (crop_width - 1) + crop_x1) / (input_width - 1))
        new_y = ((warped_normalized_xy_npfloat32[:, 1] * (crop_height - 1) + crop_y1) / (input_height - 1))
        
        return np.vstack((new_x, new_y)).T
        
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

