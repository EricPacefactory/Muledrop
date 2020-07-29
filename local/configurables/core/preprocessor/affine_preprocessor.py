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

from local.configurables.core.preprocessor._helper_functions import unwarp_from_mapping


# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes
    

class Configurable(Reference_Preprocessor):
    
    # .................................................................................................................
    
    def __init__(self, location_select_folder_path, camera_select, input_wh):
        
        # Inherit reference functionality
        super().__init__(location_select_folder_path, camera_select, input_wh, file_dunder = __file__)
        
        # Allocate storage for global enable
        self._enable_transform = None
        
        # Allocate storage for calculated mapping
        self._x_mapping = None
        self._y_mapping = None
        
        # .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  . Control Group 1 .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .
        
        
        self.ctrl_spec.new_control_group("General Controls")
        
        self.enable_resizing = \
        self.ctrl_spec.attach_toggle(
                "enable_resizing",
                label = "Enable Resizing",
                default_value = True)
        
        self.output_w = \
        self.ctrl_spec.attach_slider(
                "output_w",
                label = "Output Width",
                default_value = input_wh[0],
                min_value = 50, max_value = 1280,
                return_type = int,
                zero_referenced = True,
                units = "pixels",
                tooltip = "Width of the output image.")
        
        self.output_h = \
        self.ctrl_spec.attach_slider(
                "output_h",
                label = "Output Height",
                default_value = input_wh[1],
                min_value = 50, max_value = 1280,
                return_type = int,
                zero_referenced = True,
                units = "pixels",
                tooltip = "Height of the output image.")
        
        self.interpolation_type = \
        self.ctrl_spec.attach_menu(
                "interpolation_type",
                label = "Interpolation",
                default_value = "Nearest",
                option_label_value_list = [("Nearest", cv2.INTER_NEAREST),
                                           ("Bilinear", cv2.INTER_LINEAR),
                                           ("Area", cv2.INTER_AREA)],
                tooltip = "Set the interpolation style for pixels sampled at fractional indices",
                visible = True)
        
        # .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  . Control Group 2 .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .
        
        
        self.ctrl_spec.new_control_group("Scaling Controls")
        
        self.enable_scaling = \
        self.ctrl_spec.attach_toggle(
                "enable_scaling",
                label = "Enable Scaling",
                default_value = True)
        
        self.scale_factor_x = \
        self.ctrl_spec.attach_slider(
                "scale_factor_x",
                label = "Horizontal Scaling Factor",
                default_value = 0.0,
                min_value = -4.0, max_value = 4.0, step_size = 1/10,
                return_type = float,
                zero_referenced = False,
                units = "percentage",
                tooltip = "Scaling factor, relative to video size in the x-direction")
        
        self.scale_factor_y = \
        self.ctrl_spec.attach_slider(
                "scale_factor_y",
                label = "Vertical Scaling Factor",
                default_value = 0.0,
                min_value = -4.0, max_value = 4.0, step_size = 1/10,
                return_type = float,
                zero_referenced = False,
                units = "percentage",
                tooltip = "Scaling factor, relative to video size in the y-direction")
        
        # .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  . Control Group 3 .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .
        
        
        self.ctrl_spec.new_control_group("Rotation Controls")
        
        self.enable_rotation = \
        self.ctrl_spec.attach_toggle(
                "enable_rotation",
                label = "Enable Rotation",
                default_value = True)
        
        self.rotation_angle_deg = \
        self.ctrl_spec.attach_slider(
                "rotation_angle_deg",
                label = "Rotation Angle",
                default_value = 0.0,
                min_value = -360.0, max_value = 360.0,
                return_type = float,
                zero_referenced = False,
                units = "degrees",
                tooltip = "Amount of rotation applied to the image.")
        
        
        # .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  . Control Group 4 .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .
        
        
        self.ctrl_spec.new_control_group("Shearing Controls")
        
        self.enable_shearing = \
        self.ctrl_spec.attach_toggle(
                "enable_shearing",
                label = "Enable Shearing",
                default_value = True)
        
        self.shear_factor_x = \
        self.ctrl_spec.attach_slider(
                "shear_factor_x",
                label = "Horizontal Shear Factor",
                default_value = 0.0,
                min_value = -1.0, max_value = 1.0, step_size = 1/100,
                return_type = float,
                zero_referenced = False,
                units = "normalized",
                tooltip = "Amount of shearing applied to the image along the horizontal axis.")
        
        self.shear_factor_y = \
        self.ctrl_spec.attach_slider(
                "shear_factor_y",
                label = "Vertical Shear Factor",
                default_value = 0.0,
                min_value = -1.0, max_value = 1.0, step_size = 1/100,
                return_type = float,
                zero_referenced = False,
                units = "normalized",
                tooltip = "Amount of shearing applied to the image along the vertical axis.")
        
        
        # .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  . Control Group 5 .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .
        
        
        self.ctrl_spec.new_control_group("Translation Controls")
        
        self.enable_translation = \
        self.ctrl_spec.attach_toggle(
                "enable_translation",
                label = "Enable Translation",
                default_value = True)
        
        self.translation_factor_x = \
        self.ctrl_spec.attach_slider(
                "translation_factor_x",
                label = "Horizontal Translation",
                default_value = 0.0,
                min_value = -1.0, max_value = 1.0, step_size = 1/100,
                return_type = float,
                zero_referenced = False,
                units = "normalized",
                tooltip = "Amount of translation applied to the image along the horizontal axis.")
        
        self.translation_factor_y = \
        self.ctrl_spec.attach_slider(
                "translation_factor_y",
                label = "Vertical Translation",
                default_value = 0.0,
                min_value = -1.0, max_value = 1.0, step_size = 1/100,
                return_type = float,
                zero_referenced = False,
                units = "normalized",
                tooltip = "Amount of translation applied to the image along the vertical axis.")
        
    # .................................................................................................................
    
    def set_output_wh(self):
        # OVERRIDING FROM PARENT CLASS
        self.output_wh = (self.output_w, self.output_h)
        
    # .................................................................................................................
    
    def reset(self):
        # No data in storage, nothing to reset
        return
    
    # .................................................................................................................
    
    def setup(self, variable_update_dictionary):
        
        # Get input sizing
        input_w, input_h = self.input_wh
        
        # Set global enable/disable flag
        self._enable_transform = (self.enable_resizing
                                  or self.enable_scaling
                                  or self.enable_rotation 
                                  or self.enable_shearing 
                                  or self.enable_translation)
        
        self.build_mapping()
    
    # .................................................................................................................
    
    def apply_transformation(self, frame):
        
        # Short-cut transformation if it's been disabled
        if not self._enable_transform:
            return frame
        
        try:
            return cv2.remap(frame, self._x_mapping, self._y_mapping, self.interpolation_type)
        
        except cv2.error as err:
            self.log("ERROR TRANSFORMING ({})".format(self.script_name))
            if self.configure_mode:
                raise err
        
        return frame
    
    # .................................................................................................................
    
    def build_mapping(self):
        
        # Based on answer from:
        # https://stackoverflow.com/questions/2446494/skewing-an-image-using-perspective-transforms
        
        # Get output scaling factors for convenience
        input_width, input_height = self.input_wh
        output_width, output_height = input_width, input_height
        if self.enable_resizing: 
            output_width, output_height = self.output_w, self.output_h
        
        # Figure out relative x/y normalization
        max_dimension = max(output_width, output_height)
        max_x, max_y = output_width / max_dimension, output_height / max_dimension  
        
        # Build transformation matrices
        rotation_matrix = self._build_rotation_matrix(max_x, max_y)
        shear_matrix = self._build_shear_matrix(max_x, max_y)
        translation_matrix = self._build_translation_matrix(max_x, max_y)
        scaling_matrix = self._build_scaling_matrix(max_x, max_y)
            
        # Combine all the transformations
        total_transform = rotation_matrix @ shear_matrix @ translation_matrix @ scaling_matrix
        
        # Create initial pixel co-ordinate mapping
        out_x_norm = np.linspace(-max_x, max_x, output_width, dtype=np.float32)
        out_y_norm = np.linspace(-max_y, max_y, output_height, dtype=np.float32)
        out_nx_mesh, out_ny_mesh = np.meshgrid(out_x_norm, out_y_norm)
        out_nz_mesh = np.ones_like(out_nx_mesh)
        xyz_matrix = np.stack((out_nx_mesh, out_ny_mesh, out_nz_mesh))
        
        # Apply transformations to original (normalized) co-ordinate matricies
        out_x_norm_map, out_y_norm_map, _ = np.tensordot(total_transform, xyz_matrix, 1)
        
        # Convert normalized (transformed) co-ordinates back into pixel co-ords
        self._x_mapping = input_width * (max_x + out_x_norm_map) / (2.0 * max_x)
        self._y_mapping = input_height * (max_y + out_y_norm_map) / (2.0 * max_y)
      
    # .................................................................................................................
    
    def _build_identity_matrix(self):
        return np.eye(3, dtype = np.float32)
        
    # .................................................................................................................
    
    def _build_rotation_matrix(self, max_x, max_y):
        
        # Bail if not enabled
        if not self.enable_rotation:
            return self._build_identity_matrix()
        
        # Calculation rotation matrix terms
        rotation_angle_radians = -np.radians(self.rotation_angle_deg)
        cos_ang = np.cos(rotation_angle_radians)
        sin_ang = np.sin(rotation_angle_radians)
        rotation_matrix = np.float32([(cos_ang, -sin_ang, 0),
                                      (sin_ang, cos_ang,  0),
                                      (0,       0,        1)])
            
        return rotation_matrix
    
    # .................................................................................................................
    
    def _build_shear_matrix(self, max_x, max_y):
        
        # Bail if not enabled
        if not self.enable_shearing:
            return self._build_identity_matrix()
        
        # Calculation shear matrix terms
        shx = 1.5 * self.shear_factor_x
        shy = 1.5 * self.shear_factor_y
        shear_matrix = np.float32([(1,   shx, 0),
                                   (shy, 1,   0),
                                   (0,   0,   1)])
            
        return shear_matrix
    
    # .................................................................................................................
    
    def _build_translation_matrix(self, max_x, max_y):
        
        # Bail if not enabled
        if not self.enable_translation:
            return self._build_identity_matrix()
        
        # Calculation translation matrix terms
        tx = -2 * max_x * self.translation_factor_x
        ty = -2 * max_y * self.translation_factor_y
        translation_matrix = np.float32([(1, 0, tx),
                                         (0, 1, ty),
                                         (0, 0, 1)])
            
        return translation_matrix
    
    # .................................................................................................................
    
    def _build_scaling_matrix(self, max_x, max_y):
        
        # Bail if not enabled
        if not self.enable_scaling:
            return self._build_identity_matrix()
        
        # Create some helper functions for clarity
        scale_up = lambda scale_factor: 1 / (1.0 + abs(scale_factor))
        scale_down = lambda scale_factor: 1.0 + abs(scale_factor)
        get_scale = lambda scale_factor: scale_up(scale_factor) if (scale_factor >= 0.0) else scale_down(scale_factor)
        
        # Calculation scaling matrix terms
        sx = get_scale(self.scale_factor_x)
        sy = get_scale(self.scale_factor_y)
        scaling_matrix = np.float32([(sx, 0, 0),
                                     (0, sy, 0),
                                     (0, 0, 1)])
            
        return scaling_matrix
    
    # .................................................................................................................
    
    def unwarp_required(self):
        # Only need to unwarp if the transform is enabled
        return self._enable_transform
    
    # .................................................................................................................

    def unwarp_xy(self, warped_normalized_xy_npfloat32):
        # Standard unwarp implementation
        return unwarp_from_mapping(warped_normalized_xy_npfloat32,
                                   self.input_wh, self.output_wh,
                                   self._x_mapping, self._y_mapping)
        
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

