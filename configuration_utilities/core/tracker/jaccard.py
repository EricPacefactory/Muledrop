#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Dec 31 10:47:03 2019

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

from local.lib.launcher_utils.configuration_loaders import Reconfigurable_Core_Stage_Loader
from local.lib.launcher_utils.video_processing_loops import Reconfigurable_Video_Loop
from local.lib.ui_utils.display_specification import Display_Window_Specification
from local.lib.ui_utils.display_specification import Detection_Display, Filtered_Binary_Display
from local.lib.ui_utils.display_specification import draw_objects_on_frame


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
        
        return tracking_frame
    
    # .................................................................................................................
    # ................................................................................................................. 


# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

# .....................................................................................................................

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Main

# Make all required selections
loader = Reconfigurable_Core_Stage_Loader("tracker", "jaccard_tracker", "Tracker_Stage")
arg_selections = loader.parse_standard_args()
loader.selections(*arg_selections)

# Set up video capture, processing stages & playback control
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


