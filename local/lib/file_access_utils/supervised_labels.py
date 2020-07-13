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

from local.lib.file_access_utils.reporting import build_after_database_report_path
from local.lib.file_access_utils.classifier import reserved_unclassified_label, reserved_notrain_label
from local.lib.file_access_utils.json_read_write import save_config_json, load_config_json


# ---------------------------------------------------------------------------------------------------------------------
#%% General Pathing functions

# .....................................................................................................................

def build_supervised_labels_folder_path(cameras_folder_path, camera_select):
    return build_after_database_report_path(cameras_folder_path, camera_select, "supervised_labels")

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Naming functions

# .....................................................................................................................

def create_supervised_labels_folder_name(data_start_datetime):
    
    # Build standard folder path name based on dataset start timing
    supervised_labels_folder_name = data_start_datetime.strftime("%Y%m%d_%H%M%S")
    
    return supervised_labels_folder_name

# .....................................................................................................................

def create_supervised_label_file_name(object_full_id):
    return "svlabel-{}.json.gz".format(object_full_id)

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Supervised labeling helpers

# .....................................................................................................................

def get_labels_to_skip():
    
    ''' Returns a set of labels that are meant to be skipped when training a classifier '''
    
    # Grab the reserved labels that are used in supervision to denote non-assignable classes
    unclassified_label, _ = reserved_unclassified_label()
    notrain_label, _ = reserved_notrain_label()
    
    skip_labels_set = {unclassified_label, notrain_label}
    
    return skip_labels_set

# .....................................................................................................................

def create_supervised_label_entry(object_id, topclass_label, subclass_label = "", attributes_dict = None):
    
    ''' Helper function used to ensure consistent formatting of supervised label entries '''
    
    # Avoid mutability shenanigans
    if attributes_dict is None:
        attributes_dict = {}
    
    return {"full_id": object_id, 
            "topclass_label": topclass_label, 
            "subclass_label": subclass_label, 
            "attributes_dict": attributes_dict}

# .....................................................................................................................

def get_svlabel_topclass_label(supervised_labels_dict, object_id = None):
    
    ''' Helper function for getting the topclass label from the supervised labels, for a given object id '''
    
    # If an object id isn't provided, assume we're dealing with a label entry directly (i.e. not nested by id)
    if object_id is None:
        return supervised_labels_dict["topclass_label"]
    
    return supervised_labels_dict[object_id]["topclass_label"]

# .....................................................................................................................

def get_svlabel_subclass_label(supervised_labels_dict, object_id = None):
    
    ''' Helper function for getting the topclass label from the supervised labels, for a given object id '''
    
    # If an object id isn't provided, assume we're dealing with a label entry directly (i.e. not nested by id)
    if object_id is None:
        return supervised_labels_dict["subclass_label"]
    
    return supervised_labels_dict[object_id]["subclass_label"]

# .....................................................................................................................

def get_svlabel_attributes_dict(supervised_labels_dict, object_id = None):
    
    ''' Helper function for getting the attributes dictionary from the supervised labels, for a given object id '''
    
    # If an object id isn't provided, assume we're dealing with a label entry directly (i.e. not nested by id)
    if object_id is None:
        return supervised_labels_dict["attributes_dict"]
    
    return supervised_labels_dict[object_id]["attributes_dict"]

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% File I/O

# .....................................................................................................................

def save_single_supervised_label(cameras_folder_path, camera_select, supervised_label_entry):
    
    # Build parent folder path
    svlabels_folder_path = build_supervised_labels_folder_path(cameras_folder_path, camera_select)
    os.makedirs(svlabels_folder_path, exist_ok = True)
    
    # Build path to save target object data
    object_full_id = supervised_label_entry["full_id"]
    save_name = create_supervised_label_file_name(object_full_id)
    save_path = os.path.join(svlabels_folder_path, save_name)
    
    return save_config_json(save_path, supervised_label_entry)

# .....................................................................................................................
    
def load_single_supervised_label(cameras_folder_path, camera_select, object_id,
                                 default_label_if_missing = None, return_nested = False):
    
    '''
    Function which loads a single supervised label entry for a given object id
    If the object id doesn't have an entry, this function will return a default (empty) entry
    
    Inputs:
        cameras_folder_path --> (string) Folder pathing to the cameras folder
        
        camera_select --> (string) The selected camera name
        
        object_id --> (integer) The object ID to load
        
        default_label_if_missing --> (string) Topclass label to associate with an object, if no data exists
        
        return_nested --> (boolean) If true, the returned data will be nested in a dictionary under the
                          given object ID: {object_id: {<normal_return>}}
    
    Outputs:
        single_object_entry (dictionary)
    
    Note: 
        Based on the function inputs, the output will either be formatted the same as the return value from the 
        create_supervised_label_entry(...) function, or will be nested under it's own object ID
    '''
    
    # Set the default label if needed
    if default_label_if_missing is None:
        default_label_if_missing, _ = reserved_unclassified_label()
    
    # Build parent folder path
    svlabels_folder_path = build_supervised_labels_folder_path(cameras_folder_path, camera_select)
    
    # Build pathing to target object data
    load_file_name = create_supervised_label_file_name(object_id)
    load_file_path = os.path.join(svlabels_folder_path, load_file_name)
    file_exists = (os.path.exists(load_file_path))
    
    # Load the supervised labelling data, if present, otherwise use the default
    if file_exists:
        single_object_entry = load_config_json(load_file_path)
    else:
        single_object_entry = create_supervised_label_entry(object_id, default_label_if_missing)
    
    # Nest the object data under it's own ID, if needed. Generally more useful if loading many objects
    if return_nested:
        single_object_entry = {object_id: single_object_entry}
    
    return single_object_entry

# .....................................................................................................................
    
def load_all_supervised_labels(cameras_folder_path, camera_select, object_id_list):
    
    ''' Function which loads all '''
    
    # Build parent folder path
    svlabels_folder_path = build_supervised_labels_folder_path(cameras_folder_path, camera_select)
    os.makedirs(svlabels_folder_path, exist_ok = True)
    
    # Get label to use as default, if nothing is available
    default_label_if_missing, _ = reserved_unclassified_label()
    
    # Load all of target object IDs labelling data into a dictionary
    nested_svlabels_dict = {}
    for each_full_id in object_id_list:
        
        # Get a single object labeling entry
        single_object_entry = load_single_supervised_label(cameras_folder_path, camera_select,
                                                           each_full_id, default_label_if_missing)
        
        # Bundle all object IDs together
        nested_svlabels_dict[each_full_id] = single_object_entry
    
    return nested_svlabels_dict

# .....................................................................................................................

def check_supervised_labels_exist(cameras_folder_path, camera_select):
    
    '''
    Helper function used to check if any supervised label data already exists 
    Returns:
        files_exist (boolean)
    '''
    
    # Initialize output
    files_exist = False
    
    # Build pathing to where the labels would be stored (if they exist)
    sv_labels_folder = build_supervised_labels_folder_path(cameras_folder_path, camera_select)
    sv_labels_folder_exists = os.path.exists(sv_labels_folder)
    if not sv_labels_folder_exists:
        return files_exist
    
    # Get listing of files (if any)
    sv_label_files = os.listdir(sv_labels_folder)
    files_exist = (len(sv_label_files) > 0)
    
    return files_exist

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap
