#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Sep 28 18:04:17 2020

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
        
        # Allocate storage for calculated mapping
        self.x_mapping = None
        self.y_mapping = None
        
        # Allocate storage for calculated values
        self._extended_quad_px = None
        self._output_w = None
        self._output_h = None
        
        # .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  . Drawing Controls  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .
        
        self.quad_draw_list = \
        self.ctrl_spec.attach_drawing(
                "quad_draw_list",
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
                visible = True,
                tooltip = "Used to enable/disable the correction. Useful for checking the effect and/or performance")
        
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
        
        self.width_scale_factor = \
        self.ctrl_spec.attach_slider(
                "width_scale_factor",
                label = "Width Scaling Factor",
                default_value = 1.0,
                min_value = 0.05, max_value = 1.0, step_size = 1/1000,
                return_type = float,
                zero_referenced = True,
                units = "percentage",
                tooltip = ["Scales down the width of the warped image relative to the initial (maximum) sizing.",
                           "Can be used in conjuction with height scaling to reduce the overall image size,",
                           "or alternatively if used alone, the aspect ratio of the image can be adjusted."])
        
        self.height_scale_factor = \
        self.ctrl_spec.attach_slider(
                "height_scale_factor",
                label = "Height Scaling Factor",
                default_value = 1.0,
                min_value = 0.05, max_value = 1.0, step_size = 1/1000,
                return_type = float,
                zero_referenced = True,
                units = "percentage",
                tooltip = ["Scales down the height of the warped image relative to the initial (maximum) sizing.",
                           "Can be used in conjuction with width scaling to reduce the overall image size,",
                           "or alternatively if used alone, the aspect ratio of the image can be adjusted."])
        
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
        
        self.ctrl_spec.new_control_group("Warping Controls")
        
        self.w_sampling_factor = \
        self.ctrl_spec.attach_slider(
                "w_sampling_factor", 
                label = "Horizontal Correction Sampling Factor",
                default_value = 1.0,
                min_value = 0.0, max_value = 1.0, step_size = 1/100,
                return_type = float,
                zero_referenced = True,
                units = "normalized",
                tooltip = ["Determines the fraction of pixels (along the columns of output image)",
                           "for which a unique perspective correction will be calculated.",
                           "Included to maintain consistency with original implementation,",
                           "however the maximum value should be fine in most cases"])
        
        self.h_sampling_factor = \
        self.ctrl_spec.attach_slider(
                "h_sampling_factor", 
                label = "Vertical Correction Sampling Factor",
                default_value = 1.0,
                min_value = 0.0, max_value = 1.0, step_size = 1/100,
                return_type = float,
                zero_referenced = True,
                units = "normalized",
                tooltip = ["Determines the fraction of pixels (along the rows of output image)",
                           "for which a unique perspective correction will be calculated.",
                           "Included to maintain consistency with original implementation,",
                           "however the maximum value should be fine in most cases"])
        
        self.warp_left = \
        self.ctrl_spec.attach_slider(
                "warp_left", 
                label = "Warp Left", 
                default_value = 0.5,
                min_value = 0.0, max_value = 1.0, step_size = 1/1000,
                return_type = float,
                zero_referenced = True,
                units = "normalized",
                tooltip = ["Used to re-distribute points in the output image by altering the spacing",
                           "of points near the left side of the image.",
                           "Small values will compress the region, while large values will expand it",
                           "The default value is often fine"])
        
        self.warp_right = \
        self.ctrl_spec.attach_slider(
                "warp_right", 
                label = "Warp Right", 
                default_value = 0.5,
                min_value = 0.0, max_value = 1.0, step_size = 1/1000,
                return_type = float,
                zero_referenced = True,
                units = "normalized",
                tooltip = ["Used to re-distribute points in the output image by altering the spacing",
                           "of points near the right side of the image.",
                           "Small values will compress the region, while large values will expand it",
                           "The default value is often fine"])
        
        self.warp_top = \
        self.ctrl_spec.attach_slider(
                "warp_top", 
                label = "Warp Top", 
                default_value = 0.5,
                min_value = 0.0, max_value = 1.0, step_size = 1/1000,
                return_type = float,
                zero_referenced = True,
                units = "normalized",
                tooltip = ["Used to re-distribute points in the output image by altering the spacing",
                           "of points near the top of the image.",
                           "Small values will compress the region, while large values will expand it",
                           "In common cases (objects moving into the distance as they move bottom-to-top),",
                           "this value should be 'large' compared to the bottom warp"])
        
        self.warp_bottom = \
        self.ctrl_spec.attach_slider(
                "warp_bottom", 
                label = "Warp Bottom", 
                default_value = 0.5,
                min_value = 0.0, max_value = 1.0, step_size = 1/1000,
                return_type = float,
                zero_referenced = True,
                units = "normalized",
                tooltip = ["Used to re-distribute points in the output image by altering the spacing",
                           "of points near the bottom of the image.",
                           "Small values will compress the region, while large values will expand it",
                           "In common cases (objects moving into the distance as they move bottom-to-top),",
                           "this value should be 'small' compared to the top warp"])
        
        # .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  . Control Group 3 .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .
        
        self.ctrl_spec.new_control_group("Extension Controls")
        
        self.extend_left = \
        self.ctrl_spec.attach_slider(
                "extend_left", 
                label = "Extend Left", 
                default_value = 0.0,
                min_value = -0.5, max_value = 2.5, step_size = 1/1000,
                return_type = float,
                zero_referenced = False,
                units = "normalized",
                tooltip = "Allows extension of the left side of the drawn quadrilateral, without re-drawing")
        
        self.extend_right = \
        self.ctrl_spec.attach_slider(
                "extend_right", 
                label = "Extend Right", 
                default_value = 0.0,
                min_value = -0.5, max_value = 2.5, step_size = 1/1000,
                return_type = float,
                zero_referenced = False,
                units = "normalized",
                tooltip = "Allows extension of the right side of the drawn quadrilateral, without re-drawing")
        
        self.extend_top = \
        self.ctrl_spec.attach_slider(
                "extend_top", 
                label = "Extend Top", 
                default_value = 0.0,
                min_value = -0.5, max_value = 2.5, step_size = 1/1000,
                return_type = float,
                zero_referenced = False,
                units = "normalized",
                tooltip = "Allows extension of the top side of the drawn quadrilateral, without re-drawing")
        
        self.extend_bottom = \
        self.ctrl_spec.attach_slider(
                "extend_bottom", 
                label = "Extend Bottom", 
                default_value = 0.0,
                min_value = -0.5, max_value = 2.5, step_size = 1/1000,
                return_type = float,
                zero_referenced = False,
                units = "normalized",
                tooltip = "Allows extension of the bottom side of the drawn quadrilateral, without re-drawing")
        
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
        zone_tl, zone_tr, zone_br, zone_bl = self._get_zone_orientation_px()
        output_w, output_h = self._get_output_dimensions(zone_tl, zone_tr, zone_br, zone_bl)
        
        # Store sizing info
        self._output_w = output_w
        self._output_h = output_h
        self.set_output_wh()
        
        # Rebuild the x/y transformation mappings
        self.x_mapping, self.y_mapping = \
        self.build_mapping(self._output_w, self._output_h, zone_tl, zone_tr, zone_br, zone_bl)
    
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
    
    def build_mapping(self, output_width, output_height, tl, tr, br, bl):
        
        # Figure out downsampling points
        width_samples = int(round((output_width * self.w_sampling_factor)))
        height_samples = int(round(output_height * self.h_sampling_factor))
        
        # Force a minimum of at least 5 samples
        width_samples = max(width_samples, 5)
        height_samples = max(height_samples, 5)
        
        # Calculate all (distorted) normalized co-ordinates for horizontal/vertical pixel mappings
        x_strides = self._distort_u(np.linspace(0.0, 1.0, width_samples, dtype = np.float32))
        y_strides = self._distort_v(np.linspace(0.0, 1.0, height_samples, dtype = np.float32))
        
        # Get vectors describing the step-direction for sampling along the edges of the drawn quad
        top_edge_sampling_vector = (tr - tl)
        bot_edge_sampling_vector = (br - bl)
        
        # Get all of the (x,y) co-ordinates of sampling points along the top/bottom edges of the drawn quad
        # --> Results in vectors with shape: (width_samples, 2)
        top_edge_xy_px = tl + np.outer(x_strides, top_edge_sampling_vector)
        bot_edge_xy_px = bl + np.outer(x_strides, bot_edge_sampling_vector)
        
        # Get the vectors describing the step-directions for sampling vertically, top-to-bottom of the drawn quad
        # --> Results in vector with shape: (width_samples, 2)
        top_to_bot_sampling_vectors = (bot_edge_xy_px - top_edge_xy_px)
        
        # Generate the grid of sampling points for x & y seperately, relative to the top edge of the drawn quad
        # --> Calculated by multiplying every y_stride value by each vertical (top-to-bot) sampling vector
        #   --> y_strides is a 1D vector (one element for each row of output) of length: height_samples
        #   --> Each vertical sampling vector (one vector for each column of output) is of shape: (width_samples, 2)
        # --> So result is grid of shape: (height_samples, width_samples, 2)
        xy_sampling_grid_relative_to_top_edge = np.einsum("h,wd->hwd", y_strides, top_to_bot_sampling_vectors)
        
        # Convert top_edge_xy_px to a grid, so it can be used as an offset for the (relative) sampling grid
        # --> top_edge_xy_px (holds xy offset for every coloumn of output) is of shape: (width_samples, 2)
        #   --> Grid is generated by repeating xy offset values for every row of output (i.e. height_samples)
        # --> So result is a grid of shape: (height_samples, width_samples, 2)
        top_edge_xy_offset_as_grid = np.repeat(np.expand_dims(top_edge_xy_px, axis = 0), height_samples, axis = 0)
        
        # Finally, generate the x/y mappings by adding the top edge offset to the (relative) sampling grid
        # --> Base calculation results in grid of shape: (height_samples, width_samples, 2)
        #   --> To get x/y mappings separately, rollaxis is used to get shape: (2, width_samples, height_samples)
        # --> Results in two grids each with shape: (height_samples, width_samples)
        x_mapping, y_mapping = np.rollaxis(xy_sampling_grid_relative_to_top_edge + top_edge_xy_offset_as_grid, 2)

        # Scale up x/y mappings to the proper output sizes, in case downsampling was used
        grid_height, grid_width = x_mapping.shape
        needs_w_scaling = (grid_width != output_width)
        needs_h_scaling = (grid_height != output_height)
        needs_scaling = (needs_w_scaling or needs_h_scaling)
        if needs_scaling:
            output_wh = (output_width, output_height)
            x_mapping = cv2.resize(x_mapping, dsize = output_wh, interpolation = cv2.INTER_LINEAR)
            y_mapping = cv2.resize(y_mapping, dsize = output_wh, interpolation = cv2.INTER_LINEAR)
        
        return x_mapping, y_mapping
    
    # .................................................................................................................
    
    def _distort_u(self, u):
        #return u
        return (perlin_bias(u, self.warp_right) * u) + (perlin_bias(u, (1 - self.warp_left)) * (1 - u))

    # .................................................................................................................
    
    def _distort_v(self, v):
        #return v
        return (perlin_bias(v,self. warp_bottom) * v) + (perlin_bias(v, (1 - self.warp_top)) * (1 - v))
        
    # .................................................................................................................
    
    def _get_zone_orientation_px(self):
        
        # Get input frame size for pixelization
        in_width, in_height = self.input_wh
        frame_scaling = np.float32((in_width, in_height))
        
        # Get perspective quad as an array for convenience
        perspective_quad_norm = np.float32(self.quad_draw_list[0])
        perspective_quad_px = perspective_quad_norm * frame_scaling
        
        # Re-orient the perspective quad, if needed
        region_roll = int(round(self.region_orientation_deg / 90))
        oriented_quad_px = np.roll(perspective_quad_px, region_roll, axis = 0)
        
        # Apply Extensions, if needed
        tl, tr, br, bl = self._get_extended_quad_px(oriented_quad_px)
        
        return tl, tr, br, bl
    
    # .................................................................................................................
    
    def _get_extended_quad_px(self, oriented_quad_px):
        
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
        scaled_output_width = output_width * self.width_scale_factor
        scaled_output_height = output_height * self.height_scale_factor
        
        return int(round(scaled_output_width)), int(round(scaled_output_height))
    
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

def draw_extended_quad(frame, configurable_ref, color = (255, 255, 0), thickness = 1, line_type = cv2.LINE_AA):
    
    # Don't draw anything if there is no extended quad (somehow?)
    if configurable_ref._extended_quad_px is None:
        return frame
    
    # Don't draw anything if there is no extension
    no_extension = all((configurable_ref.extend_top == 0, configurable_ref.extend_left == 0,
                           configurable_ref.extend_bottom == 0, configurable_ref.extend_right == 0))
    if no_extension:
        return frame
    
    # Draw the extended quad points onto the input frame (assuming it's sized correctly!)
    display_frame = frame.copy()
    ext_quad_px = np.int32(np.round(configurable_ref._extended_quad_px))
    is_closed = True
    cv2.polylines(display_frame, [ext_quad_px], is_closed, color, thickness, line_type)
    
    return display_frame

# .....................................................................................................................

def perlin_bias(x, k):
    
    ''' From Mike's perspective transform functions '''
    
    # Avoid log(0) errors
    if k < 0.001:
        return np.zeros_like(x)
    
    return np.power(x, np.log(k) / np.log(0.5))

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Demo
    
if __name__ == "__main__":
    
    # Example values for testing
    output_width = 900
    output_height = 753
    tl = np.array([545.4261, -4.0055633])
    tr = np.array([1280.,0.])
    br = np.array([1280.,720.])
    bl = np.array([381.29788, 730.01385])
    
    def ex_distort_u(u):
        warp_left, warp_right = 0.5, 0.5
        return (perlin_bias(u, warp_right) * u) + (perlin_bias(u, (1 - warp_left)) * (1 - u))
    
    def ex_distort_v(v):
        warp_top, warp_bottom = 0.5, 0.5
        return (perlin_bias(v, warp_bottom) * v) + (perlin_bias(v, (1 - warp_top)) * (1 - v))
    
    # Calculate all (distorted) normalized co-ordinates for horizontal/vertical pixel mappings
    x_strides = ex_distort_u(np.linspace(0.0, 1.0, output_width, dtype = np.float32))
    y_strides = ex_distort_v(np.linspace(0.0, 1.0, output_height, dtype = np.float32))
    
    # Get vectors describing the step-direction for sampling along the edges of the drawn quad
    top_edge_sampling_vector = (tr - tl)
    bot_edge_sampling_vector = (br - bl)
    
    # Get all of the (x,y) co-ordinates of sampling points along the top/bottom edges of the drawn quad
    # --> Results in vectors with shape: (w, 2)
    top_edge_xy_px = tl + np.outer(x_strides, top_edge_sampling_vector)
    bot_edge_xy_px = bl + np.outer(x_strides, bot_edge_sampling_vector)
    
    # Get the vectors describing the step-directions for sampling vertically, top-to-bottom of the drawn quad
    # --> Results in vector with shape: (w, 2)
    top_to_bot_sampling_vectors = (bot_edge_xy_px - top_edge_xy_px)
    
    # Generate the grid of sampling points for x & y seperately, relative to the top edge of the drawn quad
    # --> (h, w, 2)
    xy_sampling_grid_relative_to_top_edge = np.einsum("h,wd->hwd", y_strides, top_to_bot_sampling_vectors)
    
    # Convert top_edge_xy_px to a grid, so it can be used as an offset for the (relative) sampling grid
    # --> (h, w, 2)
    top_edge_xy_offset_as_grid = np.repeat(np.expand_dims(top_edge_xy_px, axis = 0), output_height, axis = 0)
    
    # Finally, generate the x/y mappings by adding the top edge offset to the (relative) sampling grid
    # --> Each output: (h, w)
    x_mapping, y_mapping = np.rollaxis(xy_sampling_grid_relative_to_top_edge + top_edge_xy_offset_as_grid, 2)


# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap


