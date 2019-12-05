#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Sep 16 13:22:47 2019

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

from local.configurables.externals.object_capture.reference_objectcapture import Reference_Object_Capture


# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes

class Object_Capture(Reference_Object_Capture):
    
    # .................................................................................................................
    
    def __init__(self, cameras_folder_path, camera_select, user_select, task_select, 
                 video_select, video_wh):
        
        # Inherit from base class
        super().__init__(cameras_folder_path, camera_select, user_select, task_select, 
                         video_select, video_wh, file_dunder = __file__)
        
        # .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  . Control Group 1 .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .
        
        self.ctrl_spec.new_control_group("Object Capture Controls")
        
        self.minimum_object_lifetime_sec = \
        self.ctrl_spec.attach_slider(
                "minimum_object_lifetime_sec", 
                label = "Minimum Object Lifetime", 
                default_value = 3.5,
                min_value = 0.0, max_value = 15.0, step_size = 1/1000,
                return_type = float,
                zero_referenced = True,
                units = "seconds",
                tooltip = "Amount of time an object must live for before it's data is saved.")

    
    # .................................................................................................................
    
    def reset(self):
        # No storage, so nothing to reset
        pass
    
    # .................................................................................................................
    
    def setup(self, values_changed_dict):
        pass
    
    # .................................................................................................................
    
    def dying_save_condition(self, object_metadata, partition_index,
                             current_frame_index, current_time_sec, current_datetime):
        
        # Only save objects that have existed for a while
        object_lifetime_sec = object_metadata.get("lifetime_sec")        
        save_object_data = (object_lifetime_sec > self.minimum_object_lifetime_sec)
        
        return save_object_data
    
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


