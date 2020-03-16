#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Oct 10 15:03:41 2019

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
    

class Preprocessor_Stage(Reference_Preprocessor):
    
    # .................................................................................................................
    
    def __init__(self, input_wh):
        
        # Inherit reference functionality
        super().__init__(input_wh, file_dunder = __file__)
        
        # Allocate storage for calculated mapping
        self.x_mapping = None
        self.y_mapping = None
        
        # Allocate storage for calculated values
        self._extended_quad_px = None
        self._output_w = None
        self._output_h = None
        
        # .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  . Drawing Controls  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .
        
        self.perspective_quad = \
        self.ctrl_spec.attach_drawing(
                "perspective_quad",
                default_value = [[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]],
                min_max_entities = (1, 1),
                min_max_points = (4, 4),
                entity_type = "polygon",
                drawing_style = "zone")
        
        # .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  . Control Group 1 .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .
        
        self.ctrl_spec.new_control_group("General Controls")
        
        self.enable_transform = \
        self.ctrl_spec.attach_toggle(
                "enable_transform", 
                label = "Enable Transform", 
                default_value = True,
                visible = True)
        
        self.region_orientation_deg = \
        self.ctrl_spec.attach_menu(
                "region_orientation_deg", 
                label = "Orientation", 
                default_value = "Default", 
                option_label_value_list = [("Default", 0),
                                           ("+90 Degrees", 90),
                                           ("+180 Degrees", 180),
                                           ("+270 Degrees", 270),], 
                tooltip = "Alter the orientation of the perspective zone.")
        
        self.scale_factor = \
        self.ctrl_spec.attach_slider(
                "scale_factor", 
                label = "Scaling Factor", 
                default_value = 1.0,
                min_value = 0.05, max_value = 1.0, step_size = 1/100,
                return_type = float,
                zero_referenced = True,
                units = "percentage",
                tooltip = "Scaling factor, relative to video size.")
        
        self.relative_aspect_ratio = \
        self.ctrl_spec.attach_slider(
                "relative_aspect_ratio", 
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
        
        # .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  . Control Group 2 .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .
        
        self.ctrl_spec.new_control_group("Warping Controls")
        
        self.warp_left = \
        self.ctrl_spec.attach_slider(
                "warp_left", 
                label = "Warp Left", 
                default_value = 0.5,
                min_value = 0.0, max_value = 1.0, step_size = 1/100,
                return_type = float,
                zero_referenced = True,
                units = "normalized",
                tooltip = "")
        
        self.warp_right = \
        self.ctrl_spec.attach_slider(
                "warp_right", 
                label = "Warp Right", 
                default_value = 0.5,
                min_value = 0.0, max_value = 1.0, step_size = 1/100,
                return_type = float,
                zero_referenced = True,
                units = "normalized",
                tooltip = "")
        
        self.warp_top = \
        self.ctrl_spec.attach_slider(
                "warp_top", 
                label = "Warp Top", 
                default_value = 0.5,
                min_value = 0.0, max_value = 1.0, step_size = 1/100,
                return_type = float,
                zero_referenced = True,
                units = "normalized",
                tooltip = "")
        
        self.warp_bottom = \
        self.ctrl_spec.attach_slider(
                "warp_bottom", 
                label = "Warp Bottom", 
                default_value = 0.5,
                min_value = 0.0, max_value = 1.0, step_size = 1/100,
                return_type = float,
                zero_referenced = True,
                units = "normalized",
                tooltip = "")
        
        # .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  . Control Group 3 .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .
        
        self.ctrl_spec.new_control_group("Extension Controls")
        
        self.extend_left = \
        self.ctrl_spec.attach_slider(
                "extend_left", 
                label = "Extend Left", 
                default_value = 0.0,
                min_value = 0.0, max_value = 1.0, step_size = 1/100,
                return_type = float,
                zero_referenced = True,
                units = "normalized",
                tooltip = "")
        
        self.extend_right = \
        self.ctrl_spec.attach_slider(
                "extend_right", 
                label = "Extend Right", 
                default_value = 0.0,
                min_value = 0.0, max_value = 1.0, step_size = 1/100,
                return_type = float,
                zero_referenced = True,
                units = "normalized",
                tooltip = "")
        
        self.extend_top = \
        self.ctrl_spec.attach_slider(
                "extend_top", 
                label = "Extend Top", 
                default_value = 0.0,
                min_value = 0.0, max_value = 1.0, step_size = 1/100,
                return_type = float,
                zero_referenced = True,
                units = "normalized",
                tooltip = "")
        
        self.extend_bottom = \
        self.ctrl_spec.attach_slider(
                "extend_bottom", 
                label = "Extend Bottom", 
                default_value = 0.0,
                min_value = 0.0, max_value = 1.0, step_size = 1/100,
                return_type = float,
                zero_referenced = True,
                units = "normalized",
                tooltip = "")
        
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
        
        # Figure out the output orientation and frame sizing first
        zone_tl, zone_tr, zone_br, zone_bl = self._get_zone_orientation()
        self._output_w, self._output_h = self._get_output_dimensions(zone_tl, zone_tr, zone_br, zone_bl)
        
        # Rebuild the x/y transformation mappings
        self.build_mapping(self._output_w, self._output_h,
                           zone_tl, zone_tr, zone_br, zone_bl)
    
    # .................................................................................................................
    
    def apply_transformation(self, frame):
        
        # Short-cut transformation if it's been disabled
        if not self.enable_transform:
            return frame
        
        try:
            return cv2.remap(frame, self.x_mapping, self.y_mapping, self.interpolation_type)
        except Exception as err:
            print("ERROR TRANSFORMING ({})".format(self.script_name))
            if self.configure_mode: 
                raise err
            return frame
    
    # .................................................................................................................
    
    def build_mapping(self, output_width, output_height, tl, tr, br, bl):
        
        # Calculate all (distorted) normalized co-ordinates for horizontal/vertical pixel mappings
        x_strides = self._distort_u(np.linspace(0.0, 1.0, output_width, dtype = np.float32))
        y_strides = self._distort_v(np.linspace(0.0, 1.0, output_height, dtype = np.float32))
        
        # Calculate all top/bot-edge pixel co-ordinates (after distortion)
        upper_xys = tl + np.outer(x_strides, tr - tl)
        lower_xys = bl + np.outer(x_strides, br - bl)
        dxy = lower_xys - upper_xys
        
        # Stack vectors together to make for simpler matrix calculations
        w_mat = np.vstack((np.ones(y_strides.shape, dtype=np.float32), y_strides))            
        x_mat = np.vstack((upper_xys[:, 0], dxy[:, 0]))
        y_mat = np.vstack((upper_xys[:, 1], dxy[:, 1]))
        
        # For a mapping point with co-ords (n, m), the values are calculated as:
        #   x_mapping(n, m) = w_n * dx_m + 1 * upper_x_m  =  <w, 1> * <dx, upper_x>  =  w_mat * x_mat 
        #   y_mapping(n, m) = w_n * dy_m + 1 * upper_y_m  =  <w, 1> * <dy, upper_y>  =  w_mat * y_mat
        self.x_mapping = np.matmul(w_mat.T, x_mat)
        self.y_mapping = np.matmul(w_mat.T, y_mat)
        
    # .................................................................................................................
    
    def _distort_u(self, u):
        #return u
        return (perlin_bias(u, self.warp_right) * u) \
                + (perlin_bias(u, (1 - self.warp_left)) * (1 - u))

    # .................................................................................................................
    
    def _distort_v(self, v):
        #return v
        return (perlin_bias(v,self. warp_bottom) * v) \
                + (perlin_bias(v, (1 - self.warp_top)) * (1 - v))
        
    # .................................................................................................................
    
    def _get_zone_orientation(self):
        
        # Get input frame size for pixelization
        in_width, in_height = self.input_wh
        frame_scaling = np.float32((in_width, in_height))
        
        # Get perspective quad as an array for convenience
        perspective_quad_norm = np.float32(self.perspective_quad[0])
        perspective_quad_px = perspective_quad_norm * frame_scaling
        
        # Re-orient the perspective quad, if needed
        region_roll = int(round(self.region_orientation_deg / 90))
        oriented_quad_px = np.roll(perspective_quad_px, region_roll, axis = 0)
        
        # Apply Extensions, if needed
        tl, tr, br, bl = self._get_extended_quad(oriented_quad_px)
        
        return tl, tr, br, bl
    
    # .................................................................................................................
    
    def _get_extended_quad(self, oriented_quad_px):
        
        # Assume point orientation
        tl, tr, br, bl = oriented_quad_px
        
        # Get more concise extension values for convenience
        ex_l, ex_r, ex_t, ex_b = self.extend_left, self.extend_right, self.extend_top, self.extend_bottom
        
        # Figure out shifting vectors
        tl_shift = tl - (tr, bl)
        tr_shift = tr - (tl, br)
        br_shift = br - (bl, tr)
        bl_shift = bl - (br, tl)
        
        # Shift each point, based on extension values
        extl = tl + np.dot(tl_shift.T, (ex_l, ex_t))
        extr = tr + np.dot(tr_shift.T, (ex_r, ex_t))
        exbr = br + np.dot(br_shift.T, (ex_r, ex_b))
        exbl = bl + np.dot(bl_shift.T, (ex_l, ex_b))
        
        # Bundle extended quad for convenience
        extended_quad_px = np.float32((extl, extr, exbr, exbl))
        self._extended_quad_px = extended_quad_px
        
        return extended_quad_px
    
    # .................................................................................................................
    
    def _get_output_dimensions(self, zone_tl, zone_tr, zone_br, zone_bl):
        
        # Get larger value between top or bottom edge lengths
        top_length = np.linalg.norm(zone_tr - zone_tl)
        bot_length = np.linalg.norm(zone_br - zone_bl)
        output_width = 1 + max(top_length, bot_length)
        
        # Take largest value between left or right edge lengths
        left_length = np.linalg.norm(zone_bl - zone_tl)
        right_length = np.linalg.norm(zone_br - zone_tr)
        output_height = 1 + max(left_length, right_length)
        
        # Apply scaling correction
        scaled_output_width = output_width * self.scale_factor
        scaled_output_height = output_height * self.scale_factor
        scaled_output_area = scaled_output_width * scaled_output_height
        
        # Apply scaling/aspect ratio correction
        adjusted_ar = self._get_aspect_ratio_adjustments()
        ratio_corrected_width = np.sqrt(scaled_output_area * adjusted_ar)
        ratio_corrected_height = scaled_output_area / ratio_corrected_width
        
        return int(round(ratio_corrected_width)), int(round(ratio_corrected_height))
    
    # ................................................................................................................. 
    
    def _get_aspect_ratio_adjustments(self):
        
        # Get input sizing
        input_w, input_h = self.input_wh
        input_ratio = input_w / input_h
        
        # Figure out altered sizing due to aspect ratio adjustment
        adjustment_is_positive = (self.relative_aspect_ratio >= 0.0)
        adjust_intercept = 1.0
        adjust_slope = (input_ratio - adjust_intercept) / 1.0
        new_ratio = abs(self.relative_aspect_ratio * adjust_slope) + adjust_intercept
        adjusted_ratio = new_ratio if adjustment_is_positive else (1 / new_ratio)
        
        return adjusted_ratio
    
    # ................................................................................................................. 
    
    def _draw_extended_quad(self, frame, color = (255, 255, 0), thickness = 1, line_type = cv2.LINE_AA):
        
        if self._extended_quad_px is None:
            return frame
        
        # Draw the extended quad points onto the input frame (assuming it's sized correctly!)
        display_frame = frame.copy()
        ext_quad_px = np.int32(np.round(self._extended_quad_px))
        is_closed = True
        cv2.polylines(display_frame, [ext_quad_px], is_closed, color, thickness, line_type)
        
        return display_frame
    
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

def perlin_bias(x, k):
    # From Mike's perspective transform functions
    return np.power(x, np.log(k) / np.log(0.5))

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Demo
    
if __name__ == "__main__":
    pass
    

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap

