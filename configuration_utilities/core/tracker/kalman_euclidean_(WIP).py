#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Mar  1 15:57:47 2020

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
from local.lib.ui_utils.display_specification import Detection_Display, Filtered_Binary_Display
from local.lib.ui_utils.display_specification import draw_mouse_centered_ellipse, draw_objects_on_frame

# ---------------------------------------------------------------------------------------------------------------------
#%% Define displays


class Custom_Tracking_Display(Display_Window_Specification):
    
    # .................................................................................................................
    
    def __init__(self, layout_index, num_rows, num_columns, 
                 initial_display = False, limit_wh = True,
                 window_name = "Tracking",
                 line_color = (255, 0, 255)):
        
        # Inherit from parent class
        super().__init__(window_name, layout_index, num_rows, num_columns, 
                         initial_display = initial_display,
                         provide_mouse_xy = True,
                         drawing_json = None, 
                         limit_wh = limit_wh)
        
        # Store variables controlling drawing behaviour
        self._validation_color = (255, 0, 255)
        self._tracked_color = (0, 255, 0)
    
    # .................................................................................................................
    
    def display(self, stage_outputs, configurable_ref, mouse_xy, 
                current_frame_index, current_epoch_ms, current_datetime):
        
        # Grab a of the preprocessed image that we can draw on it
        display_frame = stage_outputs["preprocessor"]["preprocessed_frame"]
        tracking_frame = display_frame.copy()
        
        # Grab dictionary of validation & tracked objects so we can draw them
        validation_object_dict = stage_outputs["tracker"]["validation_object_dict"]
        tracked_object_dict = stage_outputs["tracker"]["tracked_object_dict"]
        
        # Draw validation tracking visuals onto the frame
        tracking_frame = draw_objects_on_frame(tracking_frame, validation_object_dict, 
                                               configurable_ref._show_obj_ids, 
                                               configurable_ref._show_outlines, 
                                               configurable_ref._show_bounding_boxes,
                                               configurable_ref._show_trails,
                                               configurable_ref._show_decay,
                                               current_epoch_ms,
                                               outline_color = self._validation_color,
                                               box_color = self._validation_color)
        
        # Draw tracking visuals onto the frame
        tracking_frame = draw_objects_on_frame(tracking_frame, tracked_object_dict, 
                                               configurable_ref._show_obj_ids, 
                                               configurable_ref._show_outlines, 
                                               configurable_ref._show_bounding_boxes,
                                               configurable_ref._show_trails,
                                               configurable_ref._show_decay,
                                               current_epoch_ms,
                                               outline_color = self._tracked_color, 
                                               box_color = self._tracked_color)
        
        
        frame_height, frame_width = tracking_frame.shape[0:2]
        frame_scaling = np.float32((frame_width - 1, frame_height - 1))
        for each_id, each_obj in tracked_object_dict.items():
            
            top_left, bot_right = each_obj._kalman_tracker.get_tlbr_estimate()
            rect_pt1 = tuple(np.int32(np.round(top_left * frame_scaling)))
            rect_pt2 = tuple(np.int32(np.round(bot_right * frame_scaling)))
            
            cv2.rectangle(tracking_frame, rect_pt1, rect_pt2, (0, 127, 255), 2)
            #print(each_id, tl_br)
        
        # Draw mouse following indicator over top of everything else
        draw_mouse_indicator(tracking_frame, configurable_ref, mouse_xy)
        
        return tracking_frame
    
    # .................................................................................................................
    # ................................................................................................................. 


# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

def draw_mouse_indicator(display_frame, configurable_ref, mouse_xy):
    
    # If range indicator is turned off, don't do anything
    if not configurable_ref._show_max_range_indicator:
        return display_frame
    
    # Get frame sizing
    frame_height, frame_width = display_frame.shape[0:2]
    frame_scaling = np.float32((frame_width, frame_height))
    
    # Draw max range indicator, following the mouse
    min_wh_norm = np.float32((configurable_ref.max_match_range_x, configurable_ref.max_match_range_y))
    min_wh_px = (min_wh_norm * frame_scaling) / 2.0
    draw_mouse_centered_ellipse(display_frame, mouse_xy, min_wh_px, (255, 255, 60))
    
    return display_frame

# ---------------------------------------------------------------------------------------------------------------------
#%% Main

# Make all required selections and setup/configure everything
loader = Reconfigurable_Core_Stage_Loader("tracker", "kalman_euclidean_tracker", "Tracker_Stage")
configurable_ref = loader.setup_all(__file__)

# Get drawing specification for the given edge decay variable
edge_drawing_spec = configurable_ref.get_drawing_spec("edge_zones_list")

# Set up object to handle all video processing
main_process = \
Reconfigurable_Video_Loop(loader,
                          ordered_display_list = [Detection_Display(1, 4, 1, 
                                                                    window_name = "Detections & Edge Decay Zones",
                                                                    drawing_json = edge_drawing_spec),
                                                  Custom_Tracking_Display(1, 2, 2),
                                                  Filtered_Binary_Display(3, 2, 2)])

# Most of the work is done here!
main_process.loop()


# ---------------------------------------------------------------------------------------------------------------------
#%% For debugging

# Access results for debugging
final_frame = main_process.debug_frame
stage_outputs = main_process.debug_stage_outputs
stage_timing = main_process.debug_stage_timing
snapshot_metadata = main_process.debug_current_snapshot_metadata
final_frame_index, final_epoch_ms, final_datetime = main_process.debug_fed_time_args


# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap

# TODO
# - update covariance matricies using measured data, over time!
#   - for example, if bounding box is repeatedly larger than prediction, than meas. cov can be reduced
# - also consider global recording of 'best' inital covariance matricies
#   - could even be considered in spatial grid?!?! So different sections of scene have different init. cov matrices...

