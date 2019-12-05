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

from local.lib.file_access_utils.shared import copy_from_defaults

from local.lib.file_access_utils.reporting import build_object_metadata_report_path, build_classification_file_path

from eolib.utils.cli_tools import cli_folder_list_select
from eolib.utils.files import get_file_list
from eolib.utils.read_write import load_json, save_json

# ---------------------------------------------------------------------------------------------------------------------
#%% General Pathing functions

# .....................................................................................................................

def build_classifier_resources_path(cameras_folder_path, camera_select, *path_joins):
    return os.path.join(cameras_folder_path, camera_select, "resources", "classifier", *path_joins)

# .....................................................................................................................

def build_dataset_path(cameras_folder_path, camera_select, *path_joins):
    classifier_folder_path = build_classifier_resources_path(cameras_folder_path, camera_select)
    return os.path.join(classifier_folder_path, "datasets", *path_joins)

# .....................................................................................................................

def build_model_path(cameras_folder_path, camera_select, *path_joins):
    classifier_folder_path = build_classifier_resources_path(cameras_folder_path, camera_select)
    return os.path.join(classifier_folder_path, "models", *path_joins)

# .....................................................................................................................

def build_supervised_labels_folder_path(cameras_folder_path, camera_select, dataset_select, *path_joins):
    return build_dataset_path(cameras_folder_path, camera_select, dataset_select, "supervised_labels", *path_joins)

# .....................................................................................................................

def build_curation_folder_path(cameras_folder_path, camera_select, dataset_select, *path_joins):
    return build_dataset_path(cameras_folder_path, camera_select, dataset_select, "supervised_curation", *path_joins)

# .....................................................................................................................

def build_labels_lut_path(cameras_folder_path, camera_select): 
    return build_classifier_resources_path(cameras_folder_path, camera_select, "class_label_lut.json")

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Dataset Pathing functions

# .....................................................................................................................

def build_snapshot_image_dataset_path(cameras_folder_path, camera_select, dataset_select):
    return build_dataset_path(cameras_folder_path, camera_select, dataset_select, "images", "snapshots")

# .....................................................................................................................

def build_snapshot_metadata_dataset_path(cameras_folder_path, camera_select, dataset_select):
    return build_dataset_path(cameras_folder_path, camera_select, dataset_select, "metadata", "snapshots")

# .....................................................................................................................

def build_object_metadata_dataset_path(cameras_folder_path, camera_select, task_select, dataset_select):
    object_folder_name = "objects-({})".format(task_select)
    return build_dataset_path(cameras_folder_path, camera_select, dataset_select, "metadata", object_folder_name)

# .....................................................................................................................
    
def build_crop_folder_save_paths(cameras_folder_path, camera_select, dataset_select, class_label):
    return build_dataset_path(cameras_folder_path, camera_select, dataset_select, "cropped", class_label)

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Data access functions
        
# .....................................................................................................................

def create_default_classifier_configs(project_root_path, classifier_resources_path):
    
    # Only copy defaults if no files are present
    file_list = os.listdir(classifier_resources_path)
    json_files = [each_file for each_file in file_list if "json" in os.path.splitext(each_file)[1]]
    no_configs = (len(json_files) == 0)
    
    # Pull default json config files out of the defaults folder, and copy in to the target task path
    if no_configs:
        copy_from_defaults(project_root_path, 
                           target_defaults_folder = "classifier",
                           copy_to_path = classifier_resources_path)

# .....................................................................................................................

def create_blank_classification_file(cameras_folder, camera_select, user_select, task_select,
                                     default_class_label = "unclassified",
                                     default_score_pct = 0,
                                     default_subclass = "",
                                     default_attributes = {}):
    
    ''' 
    Function used to initialize a classification file when running locally
    This file is meant to replicate the use of a classification database
    '''
    
    # Get pathing to corresponding object metadata, so we can create a blank entry for all object ids
    obj_metadata_report_folder = build_object_metadata_report_path(cameras_folder, 
                                                                   camera_select,
                                                                   user_select,
                                                                   task_select)
    
    # Allocate storage for the blank classification dictionary
    blank_class_dict = {}
    blank_entry =  {"class_label": default_class_label, 
                    "score_pct": default_score_pct,
                    "subclass": default_subclass,  
                    "attributes_dict": default_attributes}
    
    # Get all reported object metadata files
    obj_md_file_paths = get_file_list(obj_metadata_report_folder, return_full_path = True, sort_list = False)
    for each_path in obj_md_file_paths:
        
        # Grab the object id from it's metadata, and nothing else 
        # (inefficient... would be nice to use the file name but maybe not safe in the long term?)
        obj_md = load_json(each_path)
        obj_full_id = obj_md["full_id"]
        
        # Add object id with blank classification to the output dictionary
        new_blank_entry = new_classification_entry(obj_full_id, **blank_entry)
        blank_class_dict.update(new_blank_entry)
    
    # Build pathing to the classification file (and create the folder if needed)
    class_file_path = build_classification_file_path(cameras_folder, camera_select, user_select, task_select)
    class_folder_path = os.path.dirname(class_file_path)
    os.makedirs(class_folder_path, exist_ok = True)
    
    # Save the completed blank file
    save_json(class_file_path, blank_class_dict, use_gzip = True)
    
    return blank_class_dict

# .....................................................................................................................
    
def new_classification_entry(object_full_id, class_label, score_pct, subclass, attributes_dict):
    
    ''' Helper function for creating properly formatted classification entries '''
    
    return {object_full_id: {"class_label": class_label,
                             "score_pct": score_pct,
                             "subclass": subclass,
                             "attributes": attributes_dict}}

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

# .....................................................................................................................
    
def load_label_lut_tuple(cameras_folder_path, camera_select):
    
    # Build the pathing to the labelling lut file & load it
    label_lut_file_path = build_labels_lut_path(cameras_folder_path, camera_select)
    label_lut_dict = load_json(label_lut_file_path, convert_integer_keys = True)
    
    # Create handy alternative versions of the data for convenience
    get_idx = lambda label: label_lut_dict.get(label).get("class_index")
    label_to_index_lut = {each_label: get_idx(each_label) for each_label in label_lut_dict.keys()}
    
    return label_lut_dict, label_to_index_lut

# .....................................................................................................................

def load_supervised_labels(cameras_folder_path, camera_select, dataset_select, 
                           remove_labels_list = []):
    
    # First build pathing to where the supervised label files are located
    supervised_labels_folder = build_supervised_labels_folder_path(cameras_folder_path, camera_select, dataset_select)
    
    # Get pathing to each file (one for each task)
    labelling_file_paths = get_file_list(supervised_labels_folder, 
                                         return_full_path = True,
                                         sort_list = False, 
                                         allowable_exts_list = [".json"])
    
    # Loop over all task files and load the labelling, with filtering if needed
    filter_results = (remove_labels_list != [])
    task_supervised_labels = {}
    for each_path in labelling_file_paths:
        
        # Figure out task from loading path
        file_name = os.path.basename(each_path)
        each_task, _ = os.path.splitext(file_name)
        
        # Load the target labelling data
        supervised_labels_dict = load_json(each_path, convert_integer_keys = True)
        
        # Filter out unclassified/ignored results if needed
        if filter_results:
            supervised_labels_dict = filter_labelling_results(supervised_labels_dict, remove_labels_list)
            
            # Skip this task if there is no data left after filtering
            no_filtered_data = len(supervised_labels_dict) == 0
            if no_filtered_data:
                continue
        
        # Add labellnig results to a dictionary containing all tasks labelling results
        task_supervised_labels.update({each_task: supervised_labels_dict})
    
    # Create a list of task names for convenience as well
    task_name_list = list(task_supervised_labels.keys())
    
    return task_name_list, task_supervised_labels

# .....................................................................................................................
    
def load_local_classification_file(cameras_folder_path, camera_select, user_select, task_select):
    
    # First get pathing to the classification file, if it exists
    class_file_path = build_classification_file_path(cameras_folder_path, camera_select, user_select, task_select)
    
    # If the class file doesn't already exist, create a blank (all objects are unclassified) one
    class_file_doesnt_exist = (not os.path.exists(class_file_path))
    if class_file_doesnt_exist:
        create_blank_classification_file(cameras_folder_path, camera_select, user_select, task_select)
    
    # Load the classification file data
    class_labels_dict = load_json(class_file_path, convert_integer_keys = True)
    
    return class_labels_dict

# .....................................................................................................................

def update_local_classification_file(cameras_folder_path, camera_select, user_select, task_select, update_dict):
    
    # Build pathing to the classification file
    class_file_path = build_classification_file_path(cameras_folder_path, camera_select, user_select, task_select)
    
    # Load data and update json
    class_labels_dict = load_json(class_file_path, convert_integer_keys = True)
    class_labels_dict.update(update_dict)
    
    # Re-save file
    save_json(class_file_path, class_labels_dict, use_gzip = True)

# .....................................................................................................................

def select_classification_dataset(cameras_folder_path, camera_select, enable_debug_mode = False):
    
    # Get listing of all available datasets
    all_dataset_folders_path = build_dataset_path(cameras_folder_path, camera_select)
    
    # Ask user to select from the available dataset folders
    dataset_folder_path, dataset_select, _ = cli_folder_list_select(all_dataset_folders_path, 
                                                                    prompt_heading = "Select a classification dataset", 
                                                                    debug_mode = enable_debug_mode)
    
    return dataset_folder_path, dataset_select

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

def get_object_id_metadata_paths(object_metadata_folder):
    
    '''
    Function which bundles object ids, by integer, into a dictionary whose values 
    represent the metadata file path for loading the given object id
    Really intended as a temporary loading/indexing solution prior to having database implemented!
    '''
    
    # First get all files
    obj_id_file_list = get_file_list(object_metadata_folder, return_full_path = False, sort_list = False)
    
    obj_id_path_lut = {}
    for each_file in obj_id_file_list:
        
        # First check if the file contains more than 1 partition (i.e. must be loaded in parts)
        # Example file format: 772019130-0.json.gz 
        #                  --> Object id 77, captured on the 130th day of 2019, partition index 0
        obj_id_str, obj_data_info = each_file.split("-")
        partition_index_str = obj_data_info.split(".")[0]
        
        # Handle future error, where object data may be stored across indexed files
        partition_index_too_high = (int(partition_index_str) > 0)
        if partition_index_too_high:
            err_msgs = ["Partition index > 0 found", 
                        "@ {}".format(object_metadata_folder),
                        "Feature not yet implemented!"]
            raise NotImplementedError("\n".join(err_msgs))
        
        # Create bundled output values
        obj_id_int = int(obj_id_str)
        obj_id_path = os.path.join(object_metadata_folder, each_file)
        
        # Add entry to dictionary
        new_entry = {obj_id_int: obj_id_path}
        obj_id_path_lut.update(new_entry)
        
    return obj_id_path_lut

# .....................................................................................................................

def get_snapshot_count_paths(snapshot_metadata_folder):
    
    '''
    Function which bundles snapshot counts, by integer, into a dictionary whose values
    represent the metadata/image file paths for loading the given snapshot data
    Really intended as a temporary loading/indexing solution prior to having database implemented!
    '''
    
    # First get all files
    snapshot_file_list = get_file_list(snapshot_metadata_folder, return_full_path = False, sort_list = True)
    
    count_starts_at = 1
    snap_count_path_lut = {}
    for each_idx, each_file in enumerate(snapshot_file_list):
        
        # Assume first snapshot is count zero and snaps are in counting order... (HACKY!)
        snap_count_int = count_starts_at + each_idx
        snap_file_path = os.path.join(snapshot_metadata_folder, each_file)
        
        # Add new entry to the dictionary
        new_entry = {snap_count_int: snap_file_path}
        snap_count_path_lut.update(new_entry)
    
    return snap_count_path_lut

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap
