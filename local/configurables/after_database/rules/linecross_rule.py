#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Jan 27 13:10:28 2020

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

from local.configurables.after_database.rules.reference_rule import Reference_Rule

from local.offline_database.object_reconstruction import Smoothed_Object_Reconstruction

from eolib.math.geometry import Fixed_Line_Cross


# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes

class Linecross_Rule(Reference_Rule):
    
    # .................................................................................................................
    
    def __init__(self, cameras_folder_path, camera_select, user_select, input_wh):
        
        # Inherit from base class
        super().__init__(cameras_folder_path, camera_select, user_select, input_wh, file_dunder = __file__)
        
        # Allocate storage for the fixed-line object
        self.fixed_line = None
        
        
        # .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  . Drawing Controls  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .
        
        self.line_entity_list = \
        self.ctrl_spec.attach_drawing(
                "line_entity_list",
                default_value = [[(0.5, 0.15), (0.5, 0.85)]],
                min_max_entities = (1, 1),
                min_max_points = (2, 2),
                entity_type = "line",
                drawing_style = "line")
        
        # .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  . Control Group 1 .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .
        
        self.ctrl_spec.new_control_group("Line Controls")
        
        self.flip_line_orientation = \
        self.ctrl_spec.attach_toggle(
                "flip_line_orientation", 
                label = "Flip Orientation", 
                default_value = False,
                tooltip = "Flips the orientation of the line. Equivalent to swapping the end points of the line.")
        
        self.trail_smoothing_factor = \
        self.ctrl_spec.attach_slider(
                "trail_smoothing_factor", 
                label = "Trail Smoothing Factor", 
                default_value = 0.015,
                min_value = 0.000, max_value = 0.100, step_size = 0.005,
                return_type = float,
                units = "weighting",
                tooltip = "Controls trail smoothing before evaluating pathing intersections.")
    
    # .................................................................................................................
    
    def setup(self, variables_changed_dict):
        
        # Pull out line points from drawing entity
        line_entity = self.line_entity_list[0]        
        line_pt1, line_pt2 = line_entity
        
        # Rebuild the fixed-line object, in case the start/end points of the line have changed
        self.fixed_line = Fixed_Line_Cross(line_pt1, line_pt2, 
                                           flip_orientation = self.flip_line_orientation, 
                                           is_normalized = True)
    
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
        
        # Check if the trail of the object intersects at all with the fixed line
        raw_results_list = self.fixed_line.path_intersection(object_data.trail_xy)
        
        # Convert intersection results to output values
        rule_results_list = self._convert_raw_results_to_rule_results(raw_results_list, object_data, snapshot_database)
        
        # No dictionary result for linecrossing
        rule_results_dict = {}
        
        return rule_results_dict, rule_results_list

    # .................................................................................................................
    
    def _convert_raw_results_to_rule_results(self, raw_results_list, object_data, snapshot_database):
        
        # Pull out some important object info for timing
        first_epoch_ms = object_data.start_ems
        lifetime_ms = object_data.lifetime_ms
        trail_index_to_epoch_ms = lifetime_ms / (object_data.num_samples - 1)
        
        rule_results_list = []
        for each_result_dict in raw_results_list:
            
            # Pull entries from the raw results & convert to final entries
            cross_direction = each_result_dict["cross_direction"]
            intersection_point_list = each_result_dict["intersection_point"].tolist()
            trail_index = int(each_result_dict["path_index"])
            
            # Find the best snapshot timing for displaying each intersection event
            approximate_epoch_ms = first_epoch_ms + int(trail_index * trail_index_to_epoch_ms)
            _, closest_snap_ms, _ = snapshot_database.get_closest_snapshot_epoch(approximate_epoch_ms)
            
            # Build output entry and add to output list
            new_result_dict = {"trail_index": trail_index,
                               "snapshot_epoch_ms": closest_snap_ms,
                               "intersection_point": intersection_point_list,
                               "cross_direction": cross_direction}
            rule_results_list.append(new_result_dict)
        
        return rule_results_list

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


