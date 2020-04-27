#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Jan 30 14:35:26 2020

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

from itertools import chain, tee

from local.configurables.after_database.rules.reference_rule import Reference_Rule

from local.offline_database.object_reconstruction import Smoothed_Object_Reconstruction


# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes

class Zoneoccupation_Rule(Reference_Rule):
    
    # .................................................................................................................
    
    def __init__(self, cameras_folder_path, camera_select, user_select, input_wh):
        
        # Inherit from base class
        super().__init__(cameras_folder_path, camera_select, user_select, input_wh, file_dunder = __file__)
        
        # Allocate storage for mask data
        self._zones_mask = None
        self._mask_scaling = None
        self._index_clipping = None
        
        # .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  . Drawing Controls  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .
        
        self.zone_entity_list = \
        self.ctrl_spec.attach_drawing(
                "zone_entity_list",
                default_value = [[(0.25, 0.45), (0.75, 0.15), (0.75, 0.55), (0.25, 0.85)]],
                min_max_entities = (0, None),
                min_max_points = (3, None),
                entity_type = "polygon",
                drawing_style = "zone")
        
        # .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  . Control Group 1 .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .
        
        self.ctrl_spec.new_control_group("Zone Controls")
        
        self.invert_zones = \
        self.ctrl_spec.attach_toggle(
                "invert_zones", 
                label = "Invert Zones", 
                default_value = False,
                tooltip = ["Flips the interpretation of the zones, so that objects falling inside drawn regions",
                           "register as being 'outside' the zone."])
    
        self.trail_smoothing_factor = \
        self.ctrl_spec.attach_slider(
                "trail_smoothing_factor", 
                label = "Trail Smoothing Factor", 
                default_value = 0.115,
                min_value = 0.000, max_value = 0.100, step_size = 0.005,
                return_type = float,
                units = "weighting",
                tooltip = "Controls trail smoothing before evaluating zone occupation.")
    
    # .................................................................................................................
    
    def setup(self, variables_changed_dict):
        
        # Generate a lookup mask for evaluating whether objects fall in/out of the defined zones
        zones_mask, mask_scaling = self._generate_zones_mask(self.zone_entity_list, self.invert_zones)
        
        # Store mask & scaling for use when evaluating rules
        self._zones_mask = zones_mask
        self._mask_scaling = mask_scaling
        self._index_clipping = ([0, 0], np.int32(np.round(mask_scaling)).tolist())
    
    # .................................................................................................................
    
    def process_object_metadata(self, object_id, object_metadata, frame_wh):
        
        # Create dummy data to fill out reconstruction
        global_start_time = 0.0
        global_end_time = 1.0
        
        # Use object reconstruction, so we can get access to existing data manipulation functions
        object_data = Smoothed_Object_Reconstruction(object_metadata, frame_wh, global_start_time, global_end_time,
                                                     smoothing_factor = self.trail_smoothing_factor)
        
        return object_data
    
    # .................................................................................................................
    
    def evaluate_one_object(self, object_data, snapshot_database, frame_wh):
        
        # Convert object trail to pixel co-ordinates, so we can index the zone mask
        mask_scaling = self._mask_scaling
        index_clipping = self._index_clipping
        trail_xy_px = np.clip(np.int32(np.round(mask_scaling * object_data.trail_xy)), *index_clipping)
        
        # Look up the mask pixel value at every trail point
        in_zone_pixels = self._zones_mask[trail_xy_px[:, 1], trail_xy_px[:, 0]]
        
        # Build rule outputs
        rule_results_dict = self._calculate_rule_results_dict(object_data, in_zone_pixels)
        rule_results_list = self._calculate_rule_results_list(object_data, in_zone_pixels, snapshot_database)
        
        return rule_results_dict, rule_results_list
    
    # .................................................................................................................
    
    @staticmethod
    def _calculate_rule_results_dict(object_data, in_zone_pixels):
        
        # Get the count of points inside the zone(s) versus outside the zone(s)
        total_count = object_data.num_samples
        in_count = np.sum(in_zone_pixels)
        in_frac = (in_count / total_count)
        
        # Calculate more meaningful values for output
        in_pct = int(round(100.0 * in_frac))
        out_pct = int(100 - in_pct)        
        in_time_ms = int(round(object_data.lifetime_ms * in_frac))
        out_time_ms = int(object_data.lifetime_ms - in_time_ms)
        
        # Figure out whether the object entered/exited the scene in or out of the zone(s)
        entered_in_zone = bool(in_zone_pixels[0] == 1)
        exited_in_zone = bool(in_zone_pixels[-1] == 1)
        
        # Build rule dictionary output
        rule_results_dict = {"in_percent": in_pct,
                             "out_percent": out_pct,
                             "in_time_ms": in_time_ms,
                             "out_time_ms": out_time_ms,
                             "entered_in_zone": entered_in_zone,
                             "exited_in_zone": exited_in_zone}
        
        return rule_results_dict
    
    # .................................................................................................................
    
    @staticmethod
    def _calculate_rule_results_list(object_data, in_zone_pixels, snapshot_database):
        
        # Get object lifetime, so we can say how long each in/out event lasts
        first_epoch_ms = object_data.start_ems
        object_lifetime_ms = object_data.lifetime_ms
        total_samples = object_data.num_samples
        lifetime_ms_per_sample = (object_lifetime_ms / total_samples)
        trail_index_to_epoch_ms = object_lifetime_ms / (total_samples - 1)
        
        # Get first index of each new block of 1's or 0's from the in_zone_pixels values
        inner_state_change_indices = (1 + np.nonzero(np.diff(in_zone_pixels))[0])
        
        # Add 'artificial' starting and ending state change indices, so we can process everything in one shot
        full_stage_change_indices = chain([0], inner_state_change_indices, [total_samples])
        
        # Loop through all zone entry/exit events and build rule result entries
        rule_results_list = []
        for first_index, final_index_plus_one in pairs_of(full_stage_change_indices):
            
            # Determine the state of each zone entry/exit event
            current_state = in_zone_pixels[first_index]
            state_str = "in" if (current_state == 1) else "out"
            
            # Determine the time spent in/out of the zone
            num_event_samples = (final_index_plus_one - first_index)
            time_elapsed_ms = int(round(num_event_samples * lifetime_ms_per_sample))
            
            # Determine the first/last frame indices
            first_trail_index = int(first_index)
            final_trail_index = int(final_index_plus_one - 1)
            
            # Determine the first/last closest snapshot epoch times
            approx_first_epoch_ms = first_epoch_ms + int(first_trail_index * trail_index_to_epoch_ms)
            approx_final_epoch_ms = first_epoch_ms + int(final_trail_index * trail_index_to_epoch_ms)
            
            # Build each entry and add to the output list
            new_rule_result_entry = {"state": state_str,
                                     "time_elapsed_ms": time_elapsed_ms,
                                     "first_trail_index": first_trail_index,
                                     "final_trail_index": final_trail_index,
                                     "approximate_first_epoch_ms": approx_first_epoch_ms,
                                     "approximate_final_epoch_ms": approx_final_epoch_ms}
            rule_results_list.append(new_rule_result_entry)
        
        return rule_results_list
    
    # .................................................................................................................
    
    @staticmethod
    def _generate_zones_mask(zone_entity_list, invert_zones, line_type = cv2.LINE_4):
        
        ''' 
        Helper function, used to generate the 'zone mask' that acts as a lookup table when checking
        if objects are occupying the zone or not
        '''
        
        # Decide on the mask sizing
        mask_width = 2560
        mask_height = 2560
        mask_scaling = np.float32((mask_width - 1, mask_height - 1))
        
        # Generate a mask image based on the zones, which we'll use as a quick lookup to evaluate the rule
        zones_mask = np.zeros((mask_height, mask_width), dtype=np.uint8)
        for each_zone_entity in zone_entity_list:
            zone_array_px = np.int32(np.round(mask_scaling * np.float32(each_zone_entity)))
            cv2.fillPoly(zones_mask, [zone_array_px], 1, line_type)
        
        return zones_mask, mask_scaling
    
    # .................................................................................................................
    # .................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

# .....................................................................................................................

def pairs_of(input_iterable):
    
    ''''
    Function intended as a for-loop helper.
    Takes in an iterable of elements and returns an iterable of pairs of elements, from the original inputs
    
    Example:
         input: [1,2,3,4,5]
        output: [(1, 2), (2, 3), (3, 4), (4, 5)]
    
    Taken from python itertools recipes:
        https://docs.python.org/3/library/itertools.html
    '''
    
    # Duplicate the input iterable, then advance one copy forward and combine to get sequential pairs of the input
    iter_copy1, iter_copy2 = tee(input_iterable)
    next(iter_copy2, None)
    
    return zip(iter_copy1, iter_copy2)

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Demo

if __name__ == "__main__":
    pass

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap


