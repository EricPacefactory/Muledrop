#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Oct 14 11:39:51 2019

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

from local.lib.file_access_utils.after_database import build_after_database_configs_folder_path
from local.lib.file_access_utils.reporting import build_after_database_report_path
from local.lib.file_access_utils.resources import build_base_resources_path
from local.lib.file_access_utils.read_write import load_config_json, save_jgz, load_jgz


# ---------------------------------------------------------------------------------------------------------------------
#%% General Pathing functions

# .....................................................................................................................

def build_classifier_config_path(cameras_folder_path, camera_select, user_select, *path_joins):
    return build_after_database_configs_folder_path(cameras_folder_path, camera_select, user_select, "classifier.json")

# .....................................................................................................................

def build_classifier_adb_metadata_report_path(cameras_folder_path, camera_select, user_select, *path_joins):
    return build_after_database_report_path(cameras_folder_path, camera_select, user_select, "classifier")

# .....................................................................................................................

def build_classifier_resources_path(cameras_folder_path, camera_select, *path_joins):
    return build_base_resources_path(cameras_folder_path, camera_select, "classifier", *path_joins)
    
# .....................................................................................................................

def build_model_path(cameras_folder_path, camera_select, *path_joins):
    classifier_folder_path = build_classifier_resources_path(cameras_folder_path, camera_select)
    return os.path.join(classifier_folder_path, "models", *path_joins)

# .....................................................................................................................

def build_labels_lut_path(cameras_folder_path, camera_select): 
    return build_classifier_resources_path(cameras_folder_path, camera_select, "class_label_lut.json")

# .....................................................................................................................

def build_supervised_labels_folder_path(cameras_folder_path, camera_select, user_select):
    return build_after_database_report_path(cameras_folder_path, camera_select, user_select, "supervised_labels")

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% File naming functions

# .....................................................................................................................

def create_classifier_report_file_name(object_full_id):
    return "class-{}.json.gz".format(object_full_id)

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Data access functions

# .....................................................................................................................

def save_classifier_data(cameras_folder_path, camera_select, user_select, 
                         object_full_id, class_label, score_pct, subclass, attributes_dict):
    
    # Build pathing to save
    save_file_name = create_classifier_report_file_name(object_full_id)
    save_folder_path = build_classifier_adb_metadata_report_path(cameras_folder_path, camera_select, user_select)
    save_file_path = os.path.join(save_folder_path, save_file_name)
    
    # Bundle data and save
    save_data = new_classifier_report_entry(object_full_id, class_label, score_pct, subclass, attributes_dict)
    save_jgz(save_file_path, save_data, create_missing_folder_path = True)

# .....................................................................................................................
    
def new_classifier_report_entry(object_full_id, 
                                class_label = "unclassified", 
                                score_pct = 0, 
                                subclass = "", 
                                attributes_dict = None):
    
    ''' Helper function for creating properly formatted classification entries '''
    
    # Avoid funny mutability stuff
    attributes_dict = {} if attributes_dict is None else attributes_dict
    
    return {"full_id": object_full_id,
            "class_label": class_label,
            "score_pct": score_pct,
            "subclass": subclass,
            "attributes": attributes_dict}

# .....................................................................................................................
    
def default_label_lut():
    
    ''' 
    NOT CALLED ANYWHERE! KEPT FOR REFERENCE UNTIL FILE STRUCTURE IS FINALIZED... 
    COULD DELETE ONCE CLASSIFICATION SYSTEM IS WORKING
    '''
    
    # Hard-code the default classification lookup table
    default_lut = {"unclassified": {"class_index": -2, "trail_color": [255, 255, 0], "outline_color": [0, 255, 0]},
                   "ignore": {"class_index": -1, "trail_color": [0, 0, 0], "outline_color": [0, 255, 0]},
                   "background": {"class_index": 0, "trail_color": [255, 255, 255], "outline_color": [0, 255, 0]},
                   "pedestrian": {"class_index": 1, "trail_color": [0, 255, 0], "outline_color": [0, 255, 0]},
                   "vehicle": {"class_index": 2, "trail_color": [0, 255, 255], "outline_color": [0, 255, 0]},
                   "other": {"class_index": 3, "trail_color": [175, 50, 200], "outline_color": [0, 255, 0]},
                   "mixed": {"class_index": 4, "trail_color": [210, 90, 15]}, "outline_color": [0, 255, 0]}
    
    return default_lut

# .................................................................................................................
    
def load_classifier_config(cameras_folder_path, camera_select, user_select):
    
    ''' 
    Function which loads configuration files for a classifier
    '''
    
    # Get path to the config file
    config_file_path = build_classifier_config_path(cameras_folder_path, camera_select, user_select)
    
    # Load json data and split into file access info & setup configuration data
    config_dict = load_config_json(config_file_path)
    access_info_dict = config_dict["access_info"]
    setup_data_dict = config_dict["setup_data"]
    
    return config_file_path, access_info_dict, setup_data_dict

# .....................................................................................................................
    
def load_label_lut_tuple(cameras_folder_path, camera_select):
    
    '''
    Function which loads the label lookup table, for classification
    Returns:
        label_lut_dict (dict), label_to_index_lut (dict)
        
    The label_lut_dict has keys representing class labels, and values which are dicts containing settings
    The label_to_index_lut is a shortcut version of the label lut, which maps labels to indices directly
    '''
    
    # Build the pathing to the labelling lut file & load it
    label_lut_file_path = build_labels_lut_path(cameras_folder_path, camera_select)
    label_lut_dict = load_config_json(label_lut_file_path)
    
    # Create handy alternative versions of the data for convenience
    get_idx = lambda label: label_lut_dict[label]["class_index"]
    label_to_index_lut = {each_label: get_idx(each_label) for each_label in label_lut_dict.keys()}
    
    return label_lut_dict, label_to_index_lut

# .....................................................................................................................

def filter_labelling_results(supervised_labels_dict, remove_labels_list):
    
    # Don't do anything if the removal list is empty
    no_filtering_needed = (remove_labels_list == [])
    if no_filtering_needed:
        return supervised_labels_dict
    
    # Go through all labelling data, and get rid of unclassified/ignored entries
    filtered_labelling_dict = {}
    for each_obj_id, each_class_label in supervised_labels_dict.items():
        
        # Skip target entries
        if each_class_label in remove_labels_list:
            continue
        
        # Add all other entries to the filtered output
        new_filtered_entry = {each_obj_id: each_class_label}
        filtered_labelling_dict.update(new_filtered_entry)
        
    return filtered_labelling_dict

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Supervised labelling helpers

# .....................................................................................................................

def create_supervised_labels_folder_name(user_select, data_start_datetime):
    
    # Build standard folder path name based on dataset start timing & user
    datetime_name = data_start_datetime.strftime("%Y%m%d_%H%M%S")
    supervised_labels_folder_name = "{}-{}".format(user_select, datetime_name)
    
    return supervised_labels_folder_name

# .....................................................................................................................

def create_supervised_label_file_name(object_full_id):
    return "supervlabel-{}.json.gz".format(object_full_id)

# .....................................................................................................................

def create_supervised_label_data(object_id, class_label):
    
    ''' Helper function used to ensure consistent formatting of supervised label data '''
    
    return {"full_id": object_id, "class_label": class_label}

# .....................................................................................................................

def save_supervised_label(supervised_labels_folder_path, object_full_id, supervised_label_dict):
    
    # Build path to save target object data
    save_name = create_supervised_label_file_name(object_full_id)
    save_path = os.path.join(supervised_labels_folder_path, save_name)
    
    return save_jgz(save_path, supervised_label_dict, check_validity = True)

# .....................................................................................................................
    
def load_supervised_labels(supervised_labels_folder_path, object_id_list, default_label_if_missing = "unclassified"):
    
    # Make sure the folder path exists
    os.makedirs(supervised_labels_folder_path, exist_ok = True)
    
    # Load all of target object ID labelling data into a dictionary
    labelling_results_dict = {}
    for each_full_id in object_id_list:
        
        # Build pathing to target object data
        load_file_name = create_supervised_label_file_name(each_full_id)
        load_file_path = os.path.join(supervised_labels_folder_path, load_file_name)
        
        # Load the supervised labelling data, if present, otherwise use the default
        object_entry = create_supervised_label_data(each_full_id, default_label_if_missing)
        file_exists = (os.path.exists(load_file_path))
        if file_exists:
            supervised_labelling_data = load_jgz(load_file_path)
            object_entry = supervised_labelling_data
        labelling_results_dict.update({each_full_id: object_entry})
    
    return labelling_results_dict

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap
