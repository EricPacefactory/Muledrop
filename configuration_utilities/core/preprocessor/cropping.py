#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Oct 21 14:01:18 2019

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

from local.lib.launcher_utils.configuration_loaders import Reconfigurable_Core_Stage_Loader
from local.lib.launcher_utils.video_processing_loops import Reconfigurable_Video_Loop

from local.lib.ui_utils.display_specification import Display_Window_Specification
from local.lib.ui_utils.display_specification import Preprocessed_Display

from local.eolib.video.text_rendering import simple_text


# ---------------------------------------------------------------------------------------------------------------------
#%% Define displays

class Custom_Input(Display_Window_Specification):
    
    # .................................................................................................................
    
    def __init__(self, layout_index, num_rows, num_columns,
                 initial_display = False,
                 window_name = "Input"):
    
        # Inherit from parent class
        super().__init__(window_name, layout_index, num_rows, num_columns,
                         initial_display = initial_display,
                         provide_mouse_xy = False,
                         drawing_json = None,
                         limit_wh = False)
        
        # Allocate storage for frame sizing
        self._frame_w = None
        self._frame_h = None
        self._xy_center = None
        
        # Allocate storage for holding crop co-ords for drawing
        self._crop_w = None
        self._crop_h = None
        self._crop_rect_pt1 = None
        self._crop_rect_pt2 = None
        
        # Allocate storage for warping parameters
        self._rotation_angle_deg = None
        self._translate_x = None
        self._translate_y = None
        self._x_map = None
        self._y_map = None
        
    # .................................................................................................................
        
    def display(self, stage_outputs, configurable_ref, mouse_xy,
                current_frame_index, current_epoch_ms, current_datetime):
        
        # Get input display frame, then draw the cropped region over top of it
        display_frame = stage_outputs["video_capture_input"]["video_frame"].copy()
        
        # Update internal values, if needed
        self._update_settings(display_frame, configurable_ref)
        
        # Apply warping to display frame
        display_frame = cv2.remap(display_frame, self._x_map, self._y_map, cv2.INTER_NEAREST)
        
        # Only draw crop region if we actually are cropping
        if configurable_ref.enable_transform:
            cv2.rectangle(display_frame, self._crop_rect_pt1, self._crop_rect_pt2, (255, 0, 255), 2)
        
        return display_frame
    
    # .................................................................................................................
    
    def _update_settings(self, display_frame, configurable_ref):
        
        ''' Function used to (re)-generate mappings as the configurable changes '''
        
        # Check for variable changes
        w_change = (self._crop_w != configurable_ref.crop_width_norm)
        h_change = (self._crop_h != configurable_ref.crop_height_norm)
        tx_change = (self._translate_x != configurable_ref.translate_x_px)
        ty_change = (self._translate_y != configurable_ref.translate_y_px)
        rot_change = (self._rotation_angle_deg != configurable_ref.rotation_angle_deg)
        var_changed = any((w_change, h_change, tx_change, ty_change, rot_change))
        
        # Only update the mappings if a variable actually changed (since it's expensive!)
        if var_changed:
            
            # Store frame sizing
            frame_height, frame_width = display_frame.shape[0:2]
            self._frame_w = frame_width
            self._frame_h = frame_height
            self._xy_center = np.float32([frame_width - 1, frame_height - 1]) / 2.0
            
            # Get crop co-ords
            self._crop_w = configurable_ref.crop_width_norm
            self._crop_h = configurable_ref.crop_height_norm
            left_edge_px, right_edge_px, top_edge_px, bot_edge_px = configurable_ref._calculate_base_crop_points()
            self._crop_rect_pt1 = (int(round(left_edge_px)), int(round(top_edge_px)))
            self._crop_rect_pt2 = (int(round(right_edge_px)), int(round(bot_edge_px)))
            
            # Store updated values
            self._translate_x = configurable_ref.translate_x_px
            self._translate_y = configurable_ref.translate_y_px
            self._rotation_angle_deg = configurable_ref.rotation_angle_deg            
            self._build_mapping()
        
        
        return
    
    # .................................................................................................................
    
    def _build_mapping(self):
        
        ''' Function used to build rotation + translation mapping applied to input image display '''
        
        # Create initial pixel co-ordinate mapping
        x_samples = np.linspace(0, self._frame_w - 1, self._frame_w, dtype = np.float32)
        y_samples = np.linspace(0, self._frame_h, self._frame_h, dtype = np.float32)
        base_x_mesh, base_y_mesh = np.meshgrid(x_samples, y_samples)
        base_xy_mesh  = np.dstack((base_x_mesh, base_y_mesh))
        
        # Calculate rotation matrix
        rotation_angle_radians = np.radians(self._rotation_angle_deg)
        cos_ang = np.cos(rotation_angle_radians)
        sin_ang = np.sin(rotation_angle_radians)
        rotation_matrix = np.float32([(cos_ang, -sin_ang),
                                      (sin_ang, cos_ang)])
        
        # Apply rotation
        rotated_mesh = np.tensordot((base_xy_mesh - self._xy_center), rotation_matrix, axes = 1) + self._xy_center
        
        # Calculate & apply translation (taking into account rotation)
        invert_y = np.float32([1.0, -1.0])
        translate_vec = np.float32([self._translate_x, self._translate_y]) * invert_y
        rotated_translate_vec = np.matmul(rotation_matrix, translate_vec) * invert_y
        rotated_mesh = rotated_mesh + rotated_translate_vec
        
        # Finally, store mappings
        self._x_map = rotated_mesh[:,:,0]
        self._y_map = rotated_mesh[:,:,1]
        
        return

    # .................................................................................................................
    # .................................................................................................................
    
    

class Cropping_Info(Display_Window_Specification):
    
    # .................................................................................................................
    
    def __init__(self, layout_index, num_rows, num_columns, initial_display = False):
        
        # Inherit from parent class
        super().__init__("Cropping Info", layout_index, num_rows, num_columns,
                         initial_display = initial_display,
                         limit_wh = False)
        
        # Allocate storage for blank image used to draw info on
        self._info_frame = np.full((150, 400, 3), (40,40,40), dtype=np.uint8)
        
    # .................................................................................................................
        
    def display(self, stage_outputs, configurable_ref, mouse_xy,
                current_frame_index, current_epoch_ms, current_datetime):
        
        # Create a blank frame for drawing
        display_frame = self._info_frame.copy()
        
        # Get sizing info
        input_width, input_height = configurable_ref.input_wh
        output_height, output_width = configurable_ref.x_mapping.shape
        
        # Get aspect ratios
        in_ar = input_width / input_height
        out_ar = output_width / output_height
        
        # Build strings for printing
        input_scale_text =\
        " Input dimensions (px): {:.0f} x {:.0f}  ~  {:.3f}".format(input_width, input_height, in_ar)
        output_text = \
        "Output dimensions (px): {:.0f} x {:.0f}  ~  {:.3f}".format(output_width, output_height, out_ar)
        
        # Write scaling info text into the image
        simple_text(display_frame, "--- Scaling Info ---", (200, 15), center_text = True)
        simple_text(display_frame, input_scale_text, (5, 70))
        simple_text(display_frame, output_text, (5, 110))
        
        return display_frame
    
    # .................................................................................................................
    # .................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions


# ---------------------------------------------------------------------------------------------------------------------
#%% Main

# For clarity
target_core_stage_name = "preprocessor"
target_script_name = "cropping_preprocessor"

# Make all required selections
loader = Reconfigurable_Core_Stage_Loader(target_core_stage_name, target_script_name)
arg_selections = loader.parse_standard_args()
loader.selections(*arg_selections)

# Set up video capture, processing stages & playback control
configurable_ref = loader.setup_all(__file__)

# Set up object to handle all video processing
main_process = \
Reconfigurable_Video_Loop(loader,
                          ordered_display_list = [Custom_Input(0, 2, 2),
                                                  Preprocessed_Display(1, 2, 2, limit_wh = False),
                                                  Cropping_Info(3, 2, 2),])

# Most of the work is done here!
main_process.loop()

# Ask user to save config
loader.ask_to_save_configurable_cli(__file__, configurable_ref)


# ---------------------------------------------------------------------------------------------------------------------
#%% For debugging

# Access results for debugging
final_frame = main_process.debug_frame
final_fed_time_args = main_process.debug_fed_time_args
debug_dict = main_process.debug_dict


# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap


# TODO
# - Consider making cropping a drawing interface (instead of sliders)

