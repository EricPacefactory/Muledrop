#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Sep 21 17:15:48 2020

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

from local.lib.launcher_utils.configuration_loaders import Reconfigurable_Object_Capture_Loader
from local.lib.launcher_utils.video_processing_loops import Object_Capture_Video_Loop

from local.lib.ui_utils.display_specification import Display_Window_Specification, Input_Display
from local.lib.ui_utils.display_specification import draw_mouse_centered_circle, draw_objects_on_frame

from local.configurables.externals.object_capture._helper_functions import Dying_Display
    

# ---------------------------------------------------------------------------------------------------------------------
#%% Define displays

class Custom_Travel_Display(Display_Window_Specification):
    
    # .................................................................................................................
    
    def __init__(self, layout_index, num_rows, num_columns, initial_display = False, limit_wh = True):
        
        # Inherit from parent class
        super().__init__("Objects", layout_index, num_rows, num_columns,
                         initial_display = initial_display,
                         provide_mouse_xy = True,
                         drawing_json = None,
                         limit_wh = limit_wh)
        
    # .................................................................................................................
        
    def display(self, stage_outputs, configurable_ref, mouse_xy,
                current_frame_index, current_epoch_ms, current_datetime):
        
        # For clarity
        show_ids = True
        show_outlines = True
        show_bounding_boxes = False
        show_trails = True
        show_decay = False
        outline_color = (0, 255, 0)
        box_color = outline_color
        
        # Get data from core stages
        display_frame = stage_outputs["preprocessor"]["preprocessed_frame"]
        tracking_obj_dict = stage_outputs["tracker"]["tracked_object_dict"]
        
        # Draw all detections into the appropriate output frame
        output_frame = draw_objects_on_frame(display_frame, tracking_obj_dict,
                                             show_ids, show_outlines, show_bounding_boxes,
                                             show_trails, show_decay, current_epoch_ms,
                                             outline_color, box_color)
        output_frame = self._draw_mouse_indicator(output_frame, configurable_ref, mouse_xy)
        
        return output_frame
    
    # .................................................................................................................
    
    def _draw_mouse_indicator(self, display_frame, configurable_ref, mouse_xy):
        
        # Get frame sizing
        frame_height, frame_width = display_frame.shape[0:2]
        frame_diagonal = np.sqrt(np.square(frame_width) + np.square(frame_height))
        
        # Calculate travel distance (in pixels) for display
        travel_dist_px = int(round(configurable_ref.minimum_travel_distance_norm * frame_diagonal))
        draw_mouse_centered_circle(display_frame, mouse_xy, travel_dist_px, (255, 0, 255), line_thickness = 2)
        
        return display_frame
    
    # .................................................................................................................
    # .................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Main

# For clarity
target_script_name = "minimum_travel_objectcapture"

# Make all required selections
loader = Reconfigurable_Object_Capture_Loader(target_script_name)
arg_selections = loader.parse_standard_args()
loader.selections(*arg_selections)

# Set up video capture, processing stages & playback control
configurable_ref = loader.setup_all(__file__)

# Set up object to handle all video processing
main_process = \
Object_Capture_Video_Loop(loader,
                          ordered_display_list = [Input_Display(0, 2, 2, limit_wh = True),
                                                  Custom_Travel_Display(1, 2, 2),
                                                  Dying_Display(2, 2, 2)])

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

