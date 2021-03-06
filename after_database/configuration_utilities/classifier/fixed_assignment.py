#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Jan 20 11:40:28 2020

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

from local.lib.ui_utils.cli_selections import Resource_Selector

from local.lib.file_access_utils.classifier import load_matching_config, save_classifier_config

from local.configurables.after_database.classifier.fixed_classifier import Configurable

from local.eolib.utils.cli_tools import cli_confirm, cli_select_from_list


# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

# .....................................................................................................................

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Define displays


# ---------------------------------------------------------------------------------------------------------------------
#%% Make selections

enable_debug_mode = False

# Create selector so we can access existing report data
selector = Resource_Selector()

# Select data to run
location_select, location_select_folder_path = selector.location(debug_mode = enable_debug_mode)
camera_select, _ = selector.camera(location_select, debug_mode = enable_debug_mode)


# ---------------------------------------------------------------------------------------------------------------------
#%% Set up the classifier

# Load configurable class for this config utility
classifier_ref = Configurable(location_select_folder_path, camera_select)

# Load existing config settings, if available
initial_setup_data_dict = load_matching_config(classifier_ref)
classifier_ref.reconfigure(initial_setup_data_dict)


# ---------------------------------------------------------------------------------------------------------------------
#%% Provide simple CLI to change configuration

# Figure out cli prompt text
menu_entries_list, variable_value_list = zip(*classifier_ref._menu_list)
default_value_selection = classifier_ref.fixed_class_label
default_selection_idx = variable_value_list.index(default_value_selection)
default_menu_selection = menu_entries_list[default_selection_idx]

# Ask user to set fixed class label assignment
select_idx, _ = cli_select_from_list(menu_entries_list, "Select class assignment:", default_menu_selection)

# Retrieve corresponding value selection (based on menu selection) & update the configurable
value_select = variable_value_list[select_idx]
classifier_ref.reconfigure({"fixed_class_label": value_select})


# ---------------------------------------------------------------------------------------------------------------------
#%% Save classifier

user_confirm_save = cli_confirm("Save fixed assignment classifier config?", default_response = False)
if user_confirm_save:
    save_classifier_config(classifier_ref, __file__)


# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap

