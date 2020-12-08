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

from local.lib.common.images import max_dimension_downscale

from local.configurables.core.preprocessor.reference_preprocessor import Reference_Preprocessor

from local.configurables.core.preprocessor._helper_functions import unwarp_from_mapping


# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes
    

class Configurable(Reference_Preprocessor):
    
    # .................................................................................................................
    
    def __init__(self, location_select_folder_path, camera_select, input_wh):
        
        # Inherit reference functionality
        super().__init__(location_select_folder_path, camera_select, input_wh, file_dunder = __file__)
        
        # Pre-calculate input frame sizing info
        input_width, input_height = input_wh
        self.in_width_scale = (input_width - 1)
        self.in_height_scale = (input_height - 1)
        self.in_xy_center = np.float32([self.in_width_scale, self.in_height_scale]) / 2.0
        
        # Allocate storage for calculated mapping
        self.x_mapping = None
        self.y_mapping = None
        
        # .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  . Control Group 1 .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .
        
        self.ctrl_spec.new_control_group("General Controls")
        
        self.enable_transform = \
        self.ctrl_spec.attach_toggle(
                "enable_transform",
                label = "Enable Transform",
                default_value = True,
                visible = True)
        
        self.rotation_angle_deg = \
        self.ctrl_spec.attach_slider(
                "rotation_angle_deg",
                label = "Rotation",
                default_value = 0,
                min_value = 0, max_value = 360, step_size = 1/10,
                return_type = float,
                zero_referenced = True,
                units = "degrees",
                tooltip = "Rotation applied to the image prior to cropping")
        
        self.translate_x_px = \
        self.ctrl_spec.attach_slider(
                "translate_x_px",
                label = "Translate X",
                default_value = 0,
                min_value = -1000, max_value = 1000, step_size = 1,
                return_type = int,
                zero_referenced = False,
                units = "pixels",
                tooltip = "Translation (in x-direction) applied to the rotated image, prior to cropping")
        
        self.translate_y_px = \
        self.ctrl_spec.attach_slider(
                "translate_y_px",
                label = "Translate Y",
                default_value = 0,
                min_value = -1000, max_value = 1000, step_size = 1,
                return_type = float,
                zero_referenced = False,
                units = "pixels",
                tooltip = "Translation (in y-direction) applied to the rotated image, prior to cropping")
        
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
        
        self.ctrl_spec.new_control_group("Cropping Controls")
        
        self.crop_width_norm = \
        self.ctrl_spec.attach_slider(
                "crop_width_norm",
                label = "Crop width",
                default_value = 0.5,
                min_value = 0.05, max_value = 1.0, step_size = 1/1000,
                return_type = float,
                zero_referenced = True,
                units = "normalized",
                tooltip = "Width to crop from the input image")
        
        self.crop_height_norm = \
        self.ctrl_spec.attach_slider(
                "crop_height_norm",
                label = "Crop height",
                default_value = 0.5,
                min_value = 0.05, max_value = 1.0, step_size = 1/1000,
                return_type = float,
                zero_referenced = True,
                units = "normalized",
                tooltip = "Height to crop from the input image")
        
        self.max_dimension_px = \
        self.ctrl_spec.attach_slider(
                "max_dimension_px",
                label = "Max dimension",
                default_value = 640,
                min_value = 100, max_value = 1280,
                units = "pixels",
                return_type = int,
                zero_referenced = True,
                tooltip = "Scale the cropped image so that the maximum dimension is at most this value")
        
        pass
    
    # .................................................................................................................
    
    def set_output_wh(self):
        # OVERRIDING FROM PARENT CLASS
        
        # Get output sizing from x/y mapping
        output_height, output_width = self.x_mapping.shape        
        self.output_wh = (output_width, output_height)
        
    # .................................................................................................................
    
    def reset(self):
        # No data in storage, nothing to reset
        return
    
    # .................................................................................................................
    
    def setup(self, variable_update_dictionary):
        
        self.x_mapping, self.y_mapping = self.build_mapping()
        
        return
    
    # .................................................................................................................
    
    def build_mapping(self):
        
        # Get cropping points (in pixels)
        left_edge_px, right_edge_px, top_edge_px, bot_edge_px = self._calculate_base_crop_points()
        
        # Calculate some output sizing info
        input_crop_width_px = int(round(1 + right_edge_px - left_edge_px))
        input_crop_height_px = int(round(1 + bot_edge_px - top_edge_px))
        input_crop_wh = (input_crop_width_px, input_crop_height_px)
        
        # Scale down cropped segment based on max dimension settings
        _, output_wh = max_dimension_downscale(input_crop_wh, self.max_dimension_px)
        output_width, output_height = output_wh
        
        # Get base x/y mapping (without rotation & translation)
        x_samples_px = np.linspace(left_edge_px, right_edge_px, output_width, dtype = np.float32)
        y_samples_px = np.linspace(top_edge_px, bot_edge_px, output_height, dtype = np.float32)
        base_x_mesh, base_y_mesh = np.meshgrid(x_samples_px, y_samples_px)
        base_xy_mesh  = np.dstack((base_x_mesh, base_y_mesh))
        
        # Calculation rotation
        rotation_matrix = self._build_rotation_matrix(self.rotation_angle_deg)
        
        # Apply rotation
        centered_mesh = (base_xy_mesh - self.in_xy_center)        
        rotated_mesh = np.tensordot(centered_mesh, rotation_matrix, axes = 1)
        
        # Apply translation (taking into account rotation)
        rotated_translate_vec = self._build_translation_vector(rotation_matrix, self.translate_x_px, self.translate_y_px)
        rotated_mesh = rotated_mesh + rotated_translate_vec
        
        # Undo centering to map back to positive co-ordinates
        rotated_mesh = (rotated_mesh + self.in_xy_center)
        
        # Finally, separate the x/y mappings for applying all transformations
        x_mapping = rotated_mesh[:, :, 0]
        y_mapping = rotated_mesh[:, :, 1]
        
        return x_mapping, y_mapping
    
    # .................................................................................................................
    
    def _calculate_base_crop_points(self):
        
        # Contruct left/right bounding box points
        half_crop_width_norm = (self.crop_width_norm / 2.0)
        left_edge_px = (self.in_width_scale * (0.5 - half_crop_width_norm))
        right_edge_px = (self.in_width_scale * (0.5 + half_crop_width_norm))
        
        # Contruct top/bottom bounding box points
        half_crop_height_norm = (self.crop_height_norm / 2.0)
        top_edge_px = (self.in_height_scale * (0.5 - half_crop_height_norm))
        bot_edge_px = (self.in_height_scale * (0.5 + half_crop_height_norm))
        
        return left_edge_px, right_edge_px, top_edge_px, bot_edge_px
    
    # .................................................................................................................
    
    def _build_rotation_matrix(self, rotation_angle_deg):
        
        ''' Calculates a 2D rotation matrix '''
        
        # Calculate 2D rotation matrix
        rotation_angle_radians = np.radians(rotation_angle_deg)
        cos_ang = np.cos(rotation_angle_radians)
        sin_ang = np.sin(rotation_angle_radians)
        rotation_matrix = np.float32([(cos_ang, -sin_ang),
                                      (sin_ang, cos_ang)])
            
        return rotation_matrix
    
    # .................................................................................................................
    
    def _build_translation_vector(self, rotation_matrix, translate_x, translate_y):
        
        ''' Calculates a rotation-corrected translation vector '''
        
        # For clarity. Needed because math y-axis and image y-axis are inverted from one another
        invert_y = np.float32([1.0, -1.0])
        
        # Calculate & apply translation (taking into account rotation)
        translate_vec = np.float32([self.translate_x_px, self.translate_y_px]) * invert_y
        rotated_translate_vec = np.matmul(rotation_matrix, translate_vec) * invert_y
            
        return rotated_translate_vec
    
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

# TODO:
# - clean up implementation (esp. the build mapping)
#   - ideally turn more steps into re-usable functions to be shared by ui if possible (avoids duplication)
    