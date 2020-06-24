#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Mar 15 14:58:14 2019

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

from local.configurables.core.preprocessor._helper_functions import unwarp_from_mapping

from local.eolib.math.linear_algebra import rotation_matrix_2D, rotate_around_center


# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes

class Preprocessor_Stage(Reference_Preprocessor):
    
    # .................................................................................................................
    
    def __init__(self, cameras_folder_path, camera_select, input_wh):
        
        # Inherit reference functionality
        super().__init__(cameras_folder_path, camera_select, input_wh, file_dunder = __file__)
        
        # .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  . Control Group 1 .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .
        
        self.ctrl_spec.new_control_group("Transformation Controls")
        
        self.enable_transform = \
        self.ctrl_spec.attach_toggle(
                "enable_transform", 
                label = "Enable Transform", 
                default_value = True,
                tooltip = "Enable or disable all of the transformation properties")
        
        self.x_recenter = \
        self.ctrl_spec.attach_slider(
                "x_recenter", 
                label = "X Center", 
                default_value = 0.5,
                min_value = 0.0, max_value = 1.0, step_size = 1/1000,
                return_type = float,
                units = "normalized",
                tooltip = "")
        
        self.y_recenter = \
        self.ctrl_spec.attach_slider(
                "y_recenter", 
                label = "Y Center", 
                default_value = 0.5,
                min_value = 0.0, max_value = 1.0, step_size = 1/1000,
                return_type = float,
                units = "normalized",
                tooltip = "")
        
        self.rotation_deg = \
        self.ctrl_spec.attach_slider(
                "rotation_deg", 
                label = "Rotation", 
                default_value = 0.0,
                min_value = -180.0, max_value = 180.0, step_size = 1/10,
                zero_referenced = False,
                return_type = float,
                units = "degrees",
                tooltip = "Rotate the output image")
        
        self.x_circle_scale = \
        self.ctrl_spec.attach_numentry(
                "x_circle_scale", 
                label = "X Circle", 
                default_value = 1.0,
                min_value = 0.01, max_value = 1.0, step_size = 1/100,
                zero_referenced = True,
                return_type = float,
                units = "normalized",
                tooltip = "Selects the outer point of the circular mapping, relative to the input image (in x)")
        
        self.y_circle_scale = \
        self.ctrl_spec.attach_numentry(
                "y_circle_scale", 
                label = "Y Circle", 
                default_value = 1.0,
                min_value = 0.01, max_value = 1.0, step_size = 1/100,
                zero_referenced = True,
                return_type = float,
                units = "normalized",
                tooltip = "Selects the outer point of the circular mapping, relative to the input image (in y)")
        
        self.x_length_scale = \
        self.ctrl_spec.attach_slider(
                "x_length_scale", 
                label = "X Scale", 
                default_value = 1.0,
                min_value = 0.01, max_value = 1.41, step_size = 1/100,
                zero_referenced = True,
                return_type = float,
                units = "normalized",
                tooltip = "")
        
        self.y_length_scale = \
        self.ctrl_spec.attach_slider(
                "y_length_scale", 
                label = "Y Scale", 
                default_value = 1.0,
                min_value = 0.01, max_value = 1.41, step_size = 1/100,
                zero_referenced = True,
                return_type = float,
                units = "normalized",
                tooltip = "")
        
        self.interpolation_type = \
        self.ctrl_spec.attach_menu(
                "interpolation_type",
                label = "Interpolation",
                default_value = "Nearest Neighbor", 
                option_label_value_list = [("Nearest Neighbor", cv2.INTER_NEAREST),
                                           ("Bilinear", cv2.INTER_LINEAR),
                                           ("Cubic", cv2.INTER_CUBIC)],
                tooltip = "Set the interpolation style for pixels sampled at fractional indices", 
                visible = False)
        
        
        # .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  . Control Group 2 .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .
        
        self.ctrl_spec.new_control_group("Scaling Controls")
        
        self.output_w = \
        self.ctrl_spec.attach_slider(
                "output_w", 
                label = "Output Width", 
                default_value = input_wh[0],
                min_value = 50, max_value = 1280,
                return_type = int,
                zero_referenced = True,
                units = "pixels",
                tooltip = "Set the output image width, in pixels")
        
        self.output_h = \
        self.ctrl_spec.attach_slider(
                "output_h", 
                label = "Output Height", 
                default_value = input_wh[1],
                min_value = 50, max_value = 1280,
                return_type = int,
                zero_referenced = True,
                units = "pixels",
                tooltip = "Set the output image height, in pixels")
        
    # .................................................................................................................
    
    def set_output_wh(self):
        # OVERRIDING FROM PARENT CLASS
        self.output_wh = (self.output_w, self.output_h)
    
    # .................................................................................................................
    
    def reset(self):
        # No data in storage, nothing to reset
        return
    
    # .................................................................................................................
    
    def setup(self, variables_changed_dict):
        
        # Rebuild the x/y transformation mappings
        self.build_mapping()
        
    # .................................................................................................................
    
    def apply_transformation(self, frame):
        
        # Short-cut transformation if it's been disabled
        if not self.enable_transform:
            return frame
        
        try:
            return cv2.remap(frame, self.x_mapping, self.y_mapping, self.interpolation_type)
        except cv2.error as err:
            self.log("ERROR TRANSFORMING ({})".format(self.script_name))
            if self.configure_mode:
                raise err
            return frame
        
    # .................................................................................................................
    
    def build_mapping(self):
        
        # Mapping from:
        # http://mathproofs.blogspot.com/2005/07/mapping-square-to-circle.html
        # http://squircular.blogspot.com/2015/09/mapping-circle-to-square.html
        
        # Warning if output dimensions weren't set properly
        if self.output_w is None or self.output_h is None:
            raise ValueError("Output width height are not set: ({} x {})".format(self.output_w, self.output_h))
        
        # Get some sizing information for convenience
        input_w, input_h = self.input_wh
        mid_x = (input_w - 1)
        mid_y = (input_h - 1)
        
        # Get normalized rectangular co-ords.
        norm_x = np.linspace(-1, 1, self.output_w, dtype = np.float32) * self.x_length_scale
        norm_y = np.linspace(-1, 1, self.output_h, dtype = np.float32) * self.y_length_scale
        
        # Pre-calculate square-root terms for circle co-ords matrix calculation
        root_x = np.sqrt(1.0 - 0.5 * np.square(norm_x))
        root_y = np.sqrt(1.0 - 0.5 * np.square(norm_y))
        
        # Generate normalized circular co-ordinate mappings (results in matricies) and apply scaling factors
        circ_x = np.outer(root_y, norm_x) * 0.5 * self.x_circle_scale
        circ_y = np.outer(norm_y, root_x) * 0.5 * self.y_circle_scale
        
        # Apply rotation to circular co-ordinates
        rotation_matrix = rotation_matrix_2D(self.rotation_deg, angle_in_radians = False, invert_matrix = True)
        cxy_matrix = np.stack((circ_x, circ_y))
        rot_circ_x, rot_circ_y = np.tensordot(rotation_matrix, cxy_matrix, 1)
        
        # Also rotate the recentering co-ordinates to match image rotation so that intuitive x/y axes are preserved
        rot_x_recenter, rot_y_recenter = rotate_around_center(rotation_matrix, 
                                                              self.x_recenter, self.y_recenter, 
                                                              x_center = 0.5, y_center = 0.5)
        
        # Convert normalized circular co-ordinates back into pixel co-ords
        self.x_mapping = mid_x * (rot_x_recenter + rot_circ_x)
        self.y_mapping = mid_y * (rot_y_recenter + rot_circ_y) 
    
    # .................................................................................................................
    
    def unwarp_required(self):
        # Only need to unwarp if the transform is enabled
        return self.enable_transform
    
    # .................................................................................................................

    def unwarp_xy(self, warped_normalized_xy_npfloat32):
        # Standard unwarp implementation
        return unwarp_from_mapping(warped_normalized_xy_npfloat32, 
                                   self.input_wh, self.output_wh, 
                                   self.x_mapping, self.y_mapping)
        
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



    