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
                default_value = 0.085,
                min_value = 0, max_value = 0.5, step_size = 1/1000,
                return_type = float,
                zero_referenced = True,
                units = "normalized",
                tooltip = ["Sets the minimum travel distance required for an object to be saved.",
                           "Note that this value is normalized relative to the frame diagonal length.",
                           "Also note that this value is interpretted relative to the tracking frame",
                           "co-ordinate system, so warping effects will be taken into account"])
        
        self.sampling_factor = \
        self.ctrl_spec.attach_slider(
                "sampling_factor",
                label = "Sampling factor",
                default_value = 1 / 10,
                min_value = 1 / 200, max_value = 1.0, step_size = 1/1000,
                return_type = float,
                zero_referenced = True,
                units = "normalized",
                tooltip = ["To avoid heavy computations when determining travel distance",
                           "(particularly for long-lived objects), the object xy co-ordinates can be",
                           "downsampled before checking the travel distance. This also has the effect of",
                           "requiring the object to 'stay' at a far distance for some time to be saved.",
                           "This setting determines what fraction of the samples are used for the computation.",
                           "Increasing this value will result in more accurate travel distance calculations",
                           "for all objects in general, at the expense of slower computation times"])
        
        self.minimum_samples = \
        self.ctrl_spec.attach_slider(
                "minimum_samples",
                label = "Minimum samples",
                default_value = 9,
                min_value = 3, max_value = 50,
                return_type = int,
                zero_referenced = True,
                units = "samples",
                tooltip = ["This setting controls the minimum number of samples used when checking",
                           "the object travel distance. This is meant to counter-act downsampling",
                           "functionality, so that in the case of short-lived objects,",
                           "we don't end up with too few samples!",
                           "Increasing this value will result in more accurate travel distance calculations",
                           "for short-lived objects, at the expense of slower computation times"])
        
        self.maximum_samples = \
        self.ctrl_spec.attach_slider(
                "maximum_samples",
                label = "Maximum samples",
                default_value = 50,
                min_value = 15, max_value = 500,
                return_type = int,
                zero_referenced = True,
                units = "samples",
                tooltip = ["This setting controls the maximum number of samples used when checking",
                           "the object travel distance. This is meant to place an upper limit on sampling",
                           "when dealing with very long-lived objects, which may still have thousands",
                           "of samples even after applying the sampling factor.",
                           "Increasing this value will result in more accurate travel distance calculations",
                           "for long-lived objects, at the expense of slower computation times"])
    
    # .................................................................................................................
    
    def reset(self):
        
        # Reset scaling values
        self._frame_scaling = None
        self._min_travel_distsq_px = 0
    
    # .................................................................................................................
    
    def setup(self, values_changed_dict):
        
        # Reset pre-caluclated scaling values
        self.reset()
        
        # Make sure the min/max downsample values are correctly ordered (i.e. min <= max)
        self.minimum_samples, self.maximum_samples = \
        sorted([self.minimum_samples, self.maximum_samples])
    
    # .................................................................................................................
    
    def dying_save_condition(self, object_metadata,
                             current_frame_index, current_epoch_ms, current_datetime):
        
        # Set up frame scaling data, if needed
        self._update_frame_scaling(object_metadata)
        
        # Figure out the max number of samples to check for travel distance
        num_samples_total = object_metadata["num_samples"]
        num_samples_to_check = int(num_samples_total * self.sampling_factor)
        num_samples_to_check = max(self.minimum_samples, min(self.maximum_samples, num_samples_to_check))
        
        # Generate a sampling step size & sample indices (with min/max bounding for protection)
        sample_idx_step_size = int(num_samples_total / num_samples_to_check)
        sample_idx_step_size = max(1, min(num_samples_total - 1, sample_idx_step_size))
        sample_idxs = np.arange(0, num_samples_total, sample_idx_step_size)
        
        # Grab the down-samples xy points and convert to arrays for speed-up
        object_xy_samples = [object_metadata["tracking"]["xy_center"][each_idx] for each_idx in sample_idxs]
        object_xy_samples_array_px = (np.float32(object_xy_samples) * self._frame_scaling)
        object_initial_xy_px = object_xy_samples_array_px[0, :]
        
        # Check distance travelled relative to object starting point to see if it should be saved
        object_xy_delta = (object_xy_samples_array_px - object_initial_xy_px)
        travel_distsq_px = np.int32(np.round(np.sum(np.square(object_xy_delta), axis = 1)))
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



