#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Jan 13 16:57:11 2021

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

class Configurable(Reference_Classifier):
    
    # .................................................................................................................
    
    def __init__(self, location_select_folder_path, camera_select):
        
        # Inherit from base class
        super().__init__(location_select_folder_path, camera_select, file_dunder = __file__)
        
        # Allocate space for (hacky) id-mapping dictionary
        self.copy_mapping_dict = None
        
        # .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  . Control Group 1 .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .
        
        self.ctrl_spec.new_control_group("Classification Controls")
        
        '''
        # Hacky approach to store list of object id -to- class label mapping
        self.copy_mapping = \
        self.ctrl_spec.attach_drawing(
                "copy_mapping",
                default_value = [[]],
                min_max_entities = [None, None],
                min_max_points = [None, None],
                visible = False)
        '''
        
        # Hacky approach to store list of object id -to- class label mapping
        self.id_to_label_lut = \
        self.ctrl_spec.attach_norender(
                "id_to_label_lut",
                default_value = {},
                return_type = dict)
        
    # .................................................................................................................
    
    def setup(self, variables_changed_dict):
        
        # Force id-to-label mapping to have integer IDs
        self.set_id_to_label_mapping(self.id_to_label_lut)
        
        return
    
    # .................................................................................................................

    def request_object_data(self, object_id, object_database):
        
        # Just need to pass the object ID along, so we can use it to look up the mapping
        
        return int(object_id)
    
    # .................................................................................................................
    
    def classify_one_object(self, object_data, snapshot_database):
        
        # Get store mapping (if it exists)
        #class_label = self.copy_mapping_dict.get(object_data, "unclassified")
        object_label = self.id_to_label_lut.get(object_data, "unclassified")
        
        # Hard-code outputs
        topclass_dict = {object_label: 1}
        subclass_dict = {}
        attributes_dict = {}
        
        return topclass_dict, subclass_dict, attributes_dict
    
    # .................................................................................................................
    
    def set_id_to_label_mapping(self, objid_to_objlabel_dict):
        
        '''
        Helper function (slightly hacky) used to update the id-to-label control varaible,
        since it is not directly render-able itself using typical UI + setup/reconfigure functions
        Also forces object IDs to be stored as integer values (instead of strings due to JSON formatting)
        '''
        
        # To avoid some potential headaches later, make sure mapping uses integer object IDs!
        id_to_label_lut_as_ints = {}
        for each_obj_id, each_obj_label in objid_to_objlabel_dict.items():            
            objid_int = int(each_obj_id)
            id_to_label_lut_as_ints[objid_int] = each_obj_label
        
        # Store mapping
        self.id_to_label_lut = id_to_label_lut_as_ints
        
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


