#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Jan 20 11:40:55 2020

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

from random import randint

from local.lib.file_access_utils.classifier import load_label_lut_tuple

from local.configurables.after_database.classifier.reference_classifier import Reference_Classifier

# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes

class Classifier_Stage(Reference_Classifier):
    
    # .................................................................................................................
    
    def __init__(self, cameras_folder_path, camera_select, user_select):
        
        # Inherit from base class
        super().__init__(cameras_folder_path, camera_select, user_select, file_dunder = __file__)
        
        # Get pathing to labels, so we know what to randomly assign!
        _, label_to_index_lut = load_label_lut_tuple(cameras_folder_path, camera_select)
        
        # List out all labels, sorted by index
        idx_label_tuples_list = [(each_idx, each_label) for each_label, each_idx in label_to_index_lut.items()]
        _, sorted_labels = zip(*sorted(idx_label_tuples_list))
        
        # Construct (& store) class label menu from label list
        self._menu_list = [(each_label.capitalize(), each_label) for each_label in sorted_labels]        
        default_menu_select = self._menu_list[0][0]
        
        # .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  . Control Group 1 .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .
        
        self.ctrl_spec.new_control_group("Classification Controls")
        
        self.fixed_class_label = \
        self.ctrl_spec.attach_menu(
                "fixed_class_label", 
                label = "Fixed Class Label", 
                default_value = default_menu_select,
                option_label_value_list = self._menu_list, 
                tooltip = "Set the (fixed) class label to assign to all objects.")
        
        self.fixed_class_score_pct = \
        self.ctrl_spec.attach_slider(
                "fixed_class_score_pct", 
                label = "Fixed Class Score", 
                default_value = 100,
                min_value = 0, max_value = 100,
                return_type = int,
                zero_referenced = True,
                units = "percent",
                tooltip = "Set the (fixed) classification score percentage.")
        
    # .................................................................................................................
    
    def setup(self, variables_changed_dict):
        # No configuration, so don't do anything
        pass
    
    # .................................................................................................................
    
    def classify_one_object(self, object_data, snapshot_database):
        
        # Get class label & score from detection data, leave everything else blank
        class_label = self.fixed_class_label
        score_pct = self.fixed_class_score_pct
        subclass = ""
        attributes_dict = {}
        
        return class_label, score_pct, subclass, attributes_dict

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


