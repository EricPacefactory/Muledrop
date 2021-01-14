#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Jan 13 16:36:25 2021

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

from local.configurables.after_database.classifier.copy_classifier import Configurable

from local.offline_database.file_database import launch_dbs, close_dbs_if_missing_data

from local.lib.file_access_utils.supervised_labels import load_all_supervised_labels
from local.lib.file_access_utils.supervised_labels import check_supervised_labels_exist
from local.lib.file_access_utils.supervised_labels import get_svlabel_topclass_label

from local.eolib.utils.cli_tools import cli_confirm
from local.eolib.utils.quitters import ide_quit


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

# Bundle pathing args for convenience
pathing_args = (location_select_folder_path, camera_select)


# ---------------------------------------------------------------------------------------------------------------------
#%% Check for supervised label data

sv_labels_exist = check_supervised_labels_exist(*pathing_args)
if not sv_labels_exist:
    print("",
          "No supervised labels were found for:",
          "  camera: {}".format(camera_select),
          "",
          "Cannot create copy mapping with labels!",
          "  -> Please use the supervised labeling tool to generate labeled data",
          sep = "\n")
    ide_quit()


# ---------------------------------------------------------------------------------------------------------------------
#%% Catalog existing data

obj_db = launch_dbs(*pathing_args, "objects")

# Catch missing data
close_dbs_if_missing_data(obj_db, error_message_if_missing = "No object trail data in the database!")


# ---------------------------------------------------------------------------------------------------------------------
#%% Set up the classifier

# Load configurable class for this config utility
classifier_ref = Configurable(location_select_folder_path, camera_select)

# Load existing config settings, if available
initial_setup_data_dict = load_matching_config(classifier_ref)
classifier_ref.reconfigure(initial_setup_data_dict)


# ---------------------------------------------------------------------------------------------------------------------
#%% Set up id-to-label map

# Get all object ids from the server
obj_id_list = obj_db.get_all_object_ids()

# Load supervised data for each object
sv_labels_dict = load_all_supervised_labels(*pathing_args, obj_id_list)

# Create label mapping
id_to_label_mapping_dict = {}
for each_obj_id, each_obj_svlabel_dict in sv_labels_dict.items():
    id_to_label_mapping_dict[each_obj_id] = get_svlabel_topclass_label(each_obj_svlabel_dict)

# Store mapping with classifier
classifier_ref.set_id_to_label_mapping(id_to_label_mapping_dict)


# ---------------------------------------------------------------------------------------------------------------------
#%% Save classifier

user_confirm_save = cli_confirm("Save copy assignment classifier config?", default_response = False)
if user_confirm_save:
    save_classifier_config(classifier_ref, __file__)


# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap

