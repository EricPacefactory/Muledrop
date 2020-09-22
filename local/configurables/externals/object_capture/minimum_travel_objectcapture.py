#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Sep 14 11:43:47 2020

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

from local.configurables.externals.object_capture.reference_objectcapture import Reference_Object_Capture


# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes

class Configurable(Reference_Object_Capture):
    
    # .................................................................................................................
    
    def __init__(self, location_select_folder_path, camera_select, video_wh,
                 enable_preprocessor_unwarp, unwarp_function):
        
        # Inherit from base class
        super().__init__(location_select_folder_path, camera_select, video_wh,
                         enable_preprocessor_unwarp, unwarp_function,
                         file_dunder = __file__)
        
        # Allocate storage for pre-calculated values
        self._min_travel_distsq_px = 0
        self._frame_scaling = None
        
        # .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  . Control Group 1 .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .
        
        self.ctrl_spec.new_control_group("Object Capture Controls")
        
        self.minimum_travel_distance_norm = \
        self.ctrl_spec.attach_slider(
                "minimum_travel_distance_norm",
                label = "Minimum Travel Distance",
                default_value = 0.075,
                min_value = 0, max_value = 0.5, step_size = 1/1000,
                return_type = float,
                zero_referenced = True,
                units = "normalized",
                tooltip = ["Sets the minimum travel distance required for an object to be saved.",
                           "Note that this value is normalized relative to the frame diagonal length.",
                           "Also note that this value is interpretted relative to the tracking frame",
                           "co-ordinate system, so warping effects will be taken into account"])
        
    # .................................................................................................................
    
    def reset(self):
        
        # Reset scaling values
        self._frame_scaling = None
        self._min_travel_distsq_px = 0
    
    # .................................................................................................................
    
    def setup(self, values_changed_dict):
        
        # Reset pre-caluclated scaling values
        self.reset()
    
    # .................................................................................................................
    
    def dying_save_condition(self, object_metadata,
                             current_frame_index, current_epoch_ms, current_datetime):
        
        # Set up frame scaling data, if needed
        self._update_frame_scaling(object_metadata)
        
        # Figure out how far the object travelled from it's original starting point
        object_xy_array_px = (np.float32((object_metadata["tracking"]["xy_center"])) * self._frame_scaling)
        object_initial_xy_px = object_xy_array_px[0, :]
        
        # As a short-cut, we'll check the last point to see if it was already far enough
        object_final_xy_px = object_xy_array_px[-1, :]
        final_travel_distsq_px = np.int32(np.round(np.sum(np.square(object_final_xy_px - object_initial_xy_px))))
        save_object_data = (final_travel_distsq_px >= self._min_travel_distsq_px)
        if save_object_data:
            return save_object_data
        
        # As a follow-up shortcut, we'll check if the mid-point was far enough
        num_samples = len(object_xy_array_px)
        mid_point_idx = int(num_samples / 2)
        object_mid_xy_px = object_xy_array_px[mid_point_idx, :]
        mid_travel_distsq_px = np.int32(np.round(np.sum(np.square(object_mid_xy_px - object_initial_xy_px))))
        save_object_data = (mid_travel_distsq_px >= self._min_travel_distsq_px)
        if save_object_data:
            return save_object_data
        
        # If we get this far, we'll have to check all object poitns to see if it travelled far enough to save
        travel_distsq_px = np.int32(np.round(np.sum(np.square(object_xy_array_px - object_initial_xy_px), axis = 1)))
        save_object_data = np.any(travel_distsq_px >= self._min_travel_distsq_px)
        
        return save_object_data
    
    # .................................................................................................................
    
    def _update_frame_scaling(self, object_metadata):
        
        ''' Function which pre-calculates frame scaling & min travel distance values if needed '''
        
        # Get the tracking frame size, so we can convert distances to pixels
        if self._frame_scaling is None:
            tracking_frame_width = object_metadata["tracking"]["frame_width"]
            tracking_frame_height = object_metadata["tracking"]["frame_height"]
            
            # Calculate & store frame scaling so we can convert object xy positions to pixels
            self._frame_scaling = np.float32((tracking_frame_width - 1, tracking_frame_height - 1))
            
            # Pre-calculate the squared distance travelled, so we can avoid sqrt function
            frame_diagonal_px = np.sqrt(np.square(tracking_frame_width) + np.square(tracking_frame_height))
            min_travel_dist = (self.minimum_travel_distance_norm * frame_diagonal_px)
            self._min_travel_distsq_px = np.int32(np.round(np.square(min_travel_dist)))
        
        return
    
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



