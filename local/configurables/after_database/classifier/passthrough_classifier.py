#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Oct 31 14:53:44 2019

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

from local.configurables.after_database.classifier.reference_classifier import Reference_Classifier


# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes

class Classifier_Stage(Reference_Classifier):
    
    # .................................................................................................................
    
    def __init__(self, location_select_folder_path, camera_select):
        
        # Inherit from base class
        super().__init__(location_select_folder_path, camera_select, file_dunder = __file__)
        
    # .................................................................................................................
    
    def setup(self, variables_changed_dict):        
        # No configuration, so don't do anything
        pass
    
    # .................................................................................................................

    def request_object_data(self, object_id, object_database):
        
        # Get object metadata from the server
        object_metadata = object_database.load_metadata_by_id(object_id)
        
        return object_metadata
    
    # .................................................................................................................
    
    def classify_one_object(self, object_data, snapshot_database):
        
        # Get class label & score from detection data, leave everything else blank
        bdb_classification = object_data.get("bdb_classification", {})
        topclass_dict = bdb_classification.get("topclass_dict", {})
        subclass_dict = bdb_classification.get("subclass_dict", {})
        attributes_dict = bdb_classification.get("attributes_dict", {})
        
        return topclass_dict, subclass_dict, attributes_dict

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


