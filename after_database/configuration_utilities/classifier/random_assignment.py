#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Jan 17 11:41:00 2020

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

from local.lib.file_access_utils.classifier import build_classifier_config_path
from local.lib.file_access_utils.read_write import load_config_json, save_config_json

from local.configurables.after_database.classifier.random_classifier import Classifier_Stage

from eolib.utils.cli_tools import cli_confirm

# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

# .....................................................................................................................

def path_to_configuration_file(configurable_ref):
    
    # Get major pathing info from the configurable
    cameras_folder_path = configurable_ref.cameras_folder_path
    camera_select = configurable_ref.camera_select
    user_select = configurable_ref.user_select
    
    return build_classifier_config_path(cameras_folder_path, camera_select, user_select)

# .....................................................................................................................

def load_matching_config(configurable_ref):
    
    # Build pathing to existing configuration file
    load_path = path_to_configuration_file(configurable_ref)
    
    # Load existing config
    config_data = load_config_json(load_path)
    file_access_dict = config_data["access_info"]
    setup_data_dict = config_data["setup_data"]
    
    # Get target script/class from the configurable, to see if the saved config matches
    target_script_name = configurable_ref.script_name
    target_class_name = configurable_ref.class_name
    
    # Check if file access matches
    script_match = (target_script_name == file_access_dict["script_name"])
    class_match = (target_class_name == file_access_dict["class_name"])
    if script_match and class_match:
        return setup_data_dict
    
    # If file acces doesn't match, return an empty setup dictionary
    no_match_setup_data_dict = {}
    return no_match_setup_data_dict

# .....................................................................................................................

def save_config(configurable_ref, file_dunder = __file__):
    
    # Figure out the name of this configuration script
    config_utility_script_name, _ = os.path.splitext(os.path.basename(file_dunder))
    
    # Get file access info & current configuration data for saving
    file_access_dict, setup_data_dict = configurable_ref.get_data_to_save()
    file_access_dict.update({"configuration_utility": config_utility_script_name})
    save_data = {"access_info": file_access_dict, "setup_data": setup_data_dict}
    
    # Build pathing to existing configuration file
    save_path = path_to_configuration_file(configurable_ref)    
    save_config_json(save_path, save_data)

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Define displays


# ---------------------------------------------------------------------------------------------------------------------
#%% Select camera/user

enable_debug_mode = False

# Create selector so we can access existing report data
selector = Resource_Selector()
project_root_path, cameras_folder_path = selector.get_project_pathing()

# Select the camera/user to show data for (needs to have saved report data already!)
camera_select, _ = selector.camera(debug_mode = enable_debug_mode)
user_select, _ = selector.user(camera_select, debug_mode=enable_debug_mode)

# ---------------------------------------------------------------------------------------------------------------------
#%% Set up the classifier

# Load configurable class for this config utility
classifier_ref = Classifier_Stage(cameras_folder_path, camera_select, user_select)

# Load existing config settings, if available
initial_setup_data_dict = load_matching_config(classifier_ref)
classifier_ref.reconfigure(initial_setup_data_dict)

# ---------------------------------------------------------------------------------------------------------------------
#%% Catalog existing data

user_confirm_save = cli_confirm("Save random classifier config?", default_response = False)
if user_confirm_save:
    save_config(classifier_ref)

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap

'''
TODO:
    - Provide prompt for user to select which classes to enable/disable for random assignment?
    - Run assignment (without saving) and show pop-up window results (e.g. images of what classes were assigned)
'''