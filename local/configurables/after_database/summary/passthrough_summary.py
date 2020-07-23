#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Jan 22 15:31:03 2020

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

from local.configurables.after_database.summary.reference_summary import Reference_Summary


# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes

class Summary_Stage(Reference_Summary):
    
    # .................................................................................................................
    
    def __init__(self, location_select_folder_path, camera_select):
        
        # Inherit from reference class
        super().__init__(location_select_folder_path, camera_select, file_dunder = __file__)
    
    # .................................................................................................................
    
    def close(self):
        # Passthrough doesn't open any resources, so nothing to close
        return
    
    # .................................................................................................................
    
    def setup(self, variables_changed_dict):
        # No variables to setup
        pass
    
    # .................................................................................................................
    
    def request_object_data(self, object_id, object_database):
        
        # Passthrough only reports the object id and nothing else!
        object_data = object_id
        
        return object_data
    
    # .................................................................................................................
    
    def summarize_one_object(self, object_data, snapshot_database):
        
        # Passthrough doesn't calculate any summary data!
        summary_data_dict = {}
        
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


