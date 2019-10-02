#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri May 31 15:38:26 2019

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

from local.lib.configuration_utils.configuration_loaders import Reconfigurable_Core_Stage_Loader
from local.lib.configuration_utils.video_processing_loops import Reconfigurable_Video_Loop
from local.lib.configuration_utils.display_specification import Display_Window_Specification
from local.lib.configuration_utils.display_specification import Filtered_Binary_Display

from local.configurables.core.detector.blob_detector import draw_detections

# ---------------------------------------------------------------------------------------------------------------------
#%% Define displays

class Custom_Detections_Display(Display_Window_Specification):
    
    # .................................................................................................................
    
    def __init__(self, layout_index, num_rows, num_columns, initial_display = False):
        
        # Inherit from parent class
        super().__init__("Detections", layout_index, num_rows, num_columns, 
                         initial_display = initial_display, 
                         max_wh = None)
        
    # .................................................................................................................
        
    def display(self, stage_outputs, configurable_ref, current_frame_index, current_time_sec, current_datetime):        
        return draw_detections(stage_outputs, configurable_ref)
        
    # .................................................................................................................
    # .................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Main

# Make all required selections and setup/configure everything
loader = Reconfigurable_Core_Stage_Loader("detector", "blob_detector", "Detector_Stage")
loader.selections()
configurable_ref = loader.setup_all(__file__)

# Set up object to handle all video processing
main_process = \
Reconfigurable_Video_Loop(loader,
                          ordered_display_list = [Custom_Detections_Display(0, 2, 2),
                                                  Filtered_Binary_Display(1, 2, 2)])

# Most of the work is done here!
main_process.loop()


# ---------------------------------------------------------------------------------------------------------------------
#%% For debugging

# Access results for debugging
last_frame = main_process.debug_frame
stage_outputs = main_process.debug_stage_outputs
stage_timing = main_process.debug_stage_timing
object_ids_in_frame_dict = main_process.debug_object_ids_in_frame_dict
snapshot_metadata = main_process.debug_current_snapshot_metadata
last_frame_index, last_time_sec, last_datetime = main_process.debug_fsd_time_args

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap

'''
TODO:
    - 'Shatterfix' or some kind of IoU/Jaccard check to avoid cases where boxes disappear for a frame or two
        - maybe keep a copy of the previous frame/set of detections
        - first pick up all valid detections
        - for rejected detections, try combining with previous frame and check if valid
    - Implement mouse following visualization to show box sizing
'''

