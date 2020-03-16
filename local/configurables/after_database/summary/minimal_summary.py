#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Jan 22 15:58:26 2020

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

from local.configurables.after_database.summary.reference_summary import Reference_Summary

# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes

class Summary_Stage(Reference_Summary):
    
    # .................................................................................................................
    
    def __init__(self, cameras_folder_path, camera_select, user_select):
        
        # Inherit from reference class
        super().__init__(cameras_folder_path, camera_select, user_select, file_dunder = __file__)
    
    # .................................................................................................................
    
    def close(self):
        # Minimal doesn't open any resources, so nothing to close
        return
    
    # .................................................................................................................
    
    def setup(self, variables_changed_dict):
        # No variables to setup
        pass
    
    # .................................................................................................................
    
    def request_object_data(self, object_id, object_database):
        
        # Will calculate simple positional parameters & speed, so we need the trail data + timing
        object_metadata = object_database.load_metadata_by_id(object_id)
        object_trail_data = object_metadata["tracking"]
        object_lifetime_ms = object_metadata["lifetime_ms"]
        
        return object_trail_data, object_lifetime_ms
    
    # .................................................................................................................
    
    def summarize_one_object(self, object_data, snapshot_database):
        
        # Unpack object data for clarity
        object_trail_data, object_lifetime_ms = object_data
        
        # Bundle trail x/y values for convenience
        trail_xy = np.vstack((object_trail_data["x_center"], object_trail_data["y_center"])).T
        
        # Calculate starting/end points and distance travelled
        start_x, start_y = trail_xy[0, :]
        end_x, end_y = trail_xy[-1, :]
        
        # Calculate direct distance between the start/end points
        round_trip_delta = np.sqrt(np.square(end_x - start_x) + np.square(end_y - start_y))
        
        # Calculate the total path travel distance
        distance_per_frame = np.linalg.norm(np.diff(trail_xy, axis = 0), axis = 1)
        total_path_distance = np.sum(distance_per_frame)
        
        # Calculate speed values (WARNING: NOT CORRECTING FOR ASPECT RATIO!!!)
        obj_lifetime_sec = object_lifetime_ms / 1000.0
        delta_xy_over_delta_t = np.diff(trail_xy, axis = 0) / obj_lifetime_sec
        obj_speed = np.linalg.norm(delta_xy_over_delta_t, axis = 1)
        max_speed = np.max(obj_speed)
        avg_speed = np.mean(obj_speed)
        
        # Bundle calculated results
        summary_data_dict = {"start_x": start_x,
                             "end_x": end_x,
                             "start_y": start_y,
                             "end_y": end_y,
                             "round_trip_delta": round_trip_delta,
                             "total_path_distance": total_path_distance,
                             "max_speed": max_speed,
                             "avg_speed": avg_speed}
        
        return summary_data_dict

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


