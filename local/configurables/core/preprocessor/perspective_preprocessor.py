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
    

class Configurable(Reference_Preprocessor):
    
    # .................................................................................................................
    
    def __init__(self, location_select_folder_path, camera_select, input_wh):
        
        # Inherit reference functionality
        super().__init__(location_select_folder_path, camera_select, input_wh, file_dunder = __file__)
        
        # Allocate storage for calculated mapping
        self.x_mapping = None
        self.y_mapping = None
        self._in_to_out_matrix = None
        self._out_to_in_matrix = None
        
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
        
        self.width_scale_factor = \
        self.ctrl_spec.attach_slider(
                "width_scale_factor", 
                label = "Width Scaling Factor", 
                default_value = 1.0,
                min_value = 0.05, max_value = 1.0, step_size = 1/100,
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
                min_value = 0.05, max_value = 1.0, step_size = 1/100,
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
        
        self.ctrl_spec.new_control_group("Extension Controls")
        
        self.extend_left = \
        self.ctrl_spec.attach_slider(
                "extend_left", 
                label = "Extend Left", 
                default_value = 0.0,
                min_value = -0.5, max_value = 2.0, step_size = 1/100,
                return_type = float,
                zero_referenced = False,
                units = "normalized",
                tooltip = "")
        
        self.extend_right = \
        self.ctrl_spec.attach_slider(
                "extend_right", 
                label = "Extend Right", 
                default_value = 0.0,
                min_value = -0.5, max_value = 2.0, step_size = 1/100,
                return_type = float,
                zero_referenced = False,
                units = "normalized",
                tooltip = "")
        
        self.extend_top = \
        self.ctrl_spec.attach_slider(
                "extend_top", 
                label = "Extend Top", 
                default_value = 0.0,
                min_value = -0.5, max_value = 2.0, step_size = 1/100,
                return_type = float,
                zero_referenced = False,
                units = "normalized",
                tooltip = "")
        
        self.extend_bottom = \
        self.ctrl_spec.attach_slider(
                "extend_bottom", 
                label = "Extend Bottom", 
                default_value = 0.0,
                min_value = -0.5, max_value = 2.0, step_size = 1/100,
                return_type = float,
                zero_referenced = False,
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
        zone_tl, zone_tr, zone_br, zone_bl = self._get_zone_orientation_px()
        output_w, output_h = self._get_output_dimensions(zone_tl, zone_tr, zone_br, zone_bl)
        
        # Store sizing info
        self._output_w = output_w
        self._output_h = output_h
        self.set_output_wh()
        
        # Get warping matrix
        self._in_to_out_matrix, self._out_to_in_matrix = \
        self.get_warp_matrices(output_w, output_h, zone_tl, zone_tr, zone_br, zone_bl)
        
        # Build the x/y sampling maps needed by remap function
        self.x_mapping, self.y_mapping = self.build_mapping(self._out_to_in_matrix, output_w, output_h)
    
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
    
    def get_warp_matrices(self, output_width, output_height, tl, tr, br, bl):
        
        # Bundle the input region co-ordinates in the required format
        input_region = np.float32((tl,tr,br,bl))
        
        # Build a matching 'output region' that we want our input co-ords to map to
        output_region = np.float32([(0, 0), 
                                    (output_width - 1, 0), 
                                    (output_width - 1, output_height - 1),
                                    (0, output_height - 1)])
            
        # Use OpenCV function to get the warping matrix, which maps input -> output, and also generate inverse
        in_to_out_warp_matrix = cv2.getPerspectiveTransform(input_region, output_region)
        out_to_in_warp_matrix = np.linalg.inv(in_to_out_warp_matrix)
        
        return in_to_out_warp_matrix, out_to_in_warp_matrix
    
    # .................................................................................................................
    
    def build_mapping(self, out_to_in_warp_matrix, output_width, output_height):
        
        '''
        Function which generates the x/y pixel sampling maps, needed by the cv2.remap(...) function
        Takes in an in-to-out matrix, found by inverting the result from the cv2.getPerspectiveTransform(...) function
        
        Inputs:
            out_to_in_warp_matrix: (matrix) Warping matrix, obtained by inverting the result from
                                    calling cv2.getPerspectiveTransform(...)
                                    
            output_width: (integer) Target width of the output image (after unwarping)
            
            output_height: (integer) Target height of the output image (after unwarping)
            
        Returns:
            x_mapping, y_mapping 
            (float32 arrays with shape output_width x output_height)
        
        Note:
        The use of remap (with x/y mappings) 
        and warpPerspective (with in_to_out_warp_matrix) 
        give the same result:
          cv2.remap(frame, x_mapping, y_mapping) == cv2.warpPerspective(frame, in_to_out_warp_matrix, out_wh)
        
        However, the remap approach is noticeably faster and allows for chained transformations in the future
        '''
        
        # See the following link for more info:
        # https://docs.opencv.org/3.4/da/d54/group__imgproc__transform.html#gaf73673a7e8e18ec6963e3774e6a94b87
        #
        # The warpPerspective function calculates: output(x, y) = input( u(x,y), v(x,y) )
        # Where:
        #   u = A / D
        #   v = B / D
        #
        # The values for A, B and D are given by:
        #   A = W11 * x + W12 * y + W13
        #   B = W21 * x + W22 * y + W23
        #   D = W31 * x + W32 * y + W33
        # Where W is the inverse of the matrix obtained from the cv2.getPerspectiveTransform(...) function
        # Notice that we can write this as a matrix/vector multiplication:
        #   ABD = W x XY1
        # Where ABD is a vector holding the [A, B, D] terms we wish to calculate,
        # W is a matrix holding the Wij terms
        # and XY1 is a vector holding the [x, y, 1] values representing a single pixel location
        # These values need to be calculated for every single x/y pixel location!        
        
        # Generate input pixel sampling indices for the output image
        x_indices = np.arange(0, output_width)
        y_indices = np.arange(0, output_height)
        x_index_mesh, y_index_mesh = np.meshgrid(x_indices, y_indices)
        ones_mesh = np.ones_like(x_index_mesh)
        
        # The output(x, y) and A/B/D values can be calculated using the 'tensordot' function
        # which can perform a 'matrix multiply' along the depth of an input tensor.
        # So if we bundle the x & y pixel locations, along with a matrix of ones,
        # we can perform the calculation for A, B and D for every pixel in a single shot!
        output_xy1_mesh = np.stack((x_index_mesh, y_index_mesh, ones_mesh))
        x_numerator, y_numerator, shared_denominator = np.tensordot(out_to_in_warp_matrix, output_xy1_mesh, axes = 1)
        
        # Finally, we just calculate the x/y mappings from the A, B, D calculation results
        convert_to_remap_units = lambda np_array: np.float32(np_array)
        x_mapping = convert_to_remap_units(x_numerator / shared_denominator)
        y_mapping = convert_to_remap_units(y_numerator / shared_denominator)
        
        return x_mapping, y_mapping
        
    # .................................................................................................................
    
    def _get_zone_orientation_px(self):
        
        # Get input frame size for pixelization
        in_width, in_height = self.input_wh
        frame_scaling = np.float32((in_width - 1, in_height - 1))
        
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
    
    def alt_unwarp_xy(self, warped_normalized_xy_npfloat32):
        
        ''' 
        Test to try to handle unwarping using direct equations, instead of LUT lookups 
        Need to compare speed to LUT option...
        '''
        
        # For convenience
        outw, outh = self.output_wh
        inw, inh = self.input_wh
        out_to_in = self._out_to_in_matrix
        
        # Get scaling factors
        out_scaling = np.float32((outw - 1, outh - 1))
        in_scaling = np.float32((1 / (inw - 1), 1 / (inh - 1)))
        
        # Warp 'output' co-ordinates back into the input image co-ordinates
        warped_xy_to_px = warped_normalized_xy_npfloat32 * out_scaling
        xy1_px = np.append(warped_xy_to_px, 1)
        x_numerator, y_numerator, shared_denominator = np.matmul(out_to_in, xy1_px)
        
        out_x = (x_numerator / shared_denominator)
        out_y = (y_numerator / shared_denominator)
        
        out_xy_px = np.float32((out_x, out_y))
        out_xy_norm = out_xy_px * in_scaling
        
        return out_xy_norm    
    
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

# .................................................................................................................

def draw_warped_grid(unwarped_frame, configurable_ref,
                     grid_line_color = (255, 255, 255), thickness = 2, line_type = cv2.LINE_AA):
    
    '''
    Function which draws a grid onto the unwarped image, based on the warping applied by the preprocessor
    '''
    
    # Get frame size, so we can draw using normalized co-ords
    frame_height, frame_width = unwarped_frame.shape[0:2]
    frame_scaling = np.float32((frame_width - 1, frame_height - 1))
    
    # For clarity
    is_closed = False
    
    # Generate (warped) grid points
    x_points = np.linspace(0, 1, 8)
    y_points = np.linspace(0, 1, 20)
    num_y = len(y_points)
    num_x = len(x_points)
    
    for each_y_point in y_points:
        
        xys_array = np.vstack((x_points, np.repeat(each_y_point, num_x))).T
        xy_unwarped_norm = configurable_ref.unwarp_xy(xys_array)
        xy_unwarped_px = np.int32(np.round(xy_unwarped_norm * frame_scaling))
        cv2.polylines(unwarped_frame, [xy_unwarped_px], is_closed, grid_line_color, thickness, line_type)
        
    for each_x_point in x_points:
        
        xys_array = np.vstack((np.repeat(each_x_point, num_y), y_points)).T
        xy_unwarped_norm = configurable_ref.unwarp_xy(xys_array)
        xy_unwarped_px = np.int32(np.round(xy_unwarped_norm * frame_scaling))
        cv2.polylines(unwarped_frame, [xy_unwarped_px], is_closed, grid_line_color, thickness, line_type)
        
        
    return unwarped_frame

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Demo
    
if __name__ == "__main__":
    pass
    

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap

# TODO:
# - implement more efficient unwarping, using transformation matrix directly!
# - consider combining this with fov correction!!!

