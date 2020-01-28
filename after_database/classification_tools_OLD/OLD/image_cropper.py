#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Oct 14 11:06:13 2019

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

import cv2
import numpy as np

from local.lib.ui_utils.cli_selections import Resource_Selector

from local.lib.file_access_utils.classifier import build_dataset_path, build_labels_folder_path, build_labels_lut_path
from local.lib.file_access_utils.classifier import build_path_to_snapshot_metadata, build_path_to_snapshot_images
from local.lib.file_access_utils.classifier import build_path_object_metadata, build_crop_folder_save_paths
from local.lib.file_access_utils.classifier import get_object_id_metadata_paths, get_snapshot_count_paths

from eolib.utils.files import get_file_list
from eolib.utils.cli_tools import cli_folder_list_select
from eolib.utils.read_write import load_json

# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes




# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

# .....................................................................................................................

def filter_labelling_results(labelling_file_paths, label_lut_dict):

    # Build (filtered) labelling lists
    ignoreable_classes = ["unclassified", "ignore"]
    ignoreable_indices = [each_idx for each_idx, each_class in label_lut_dict.items()
                          if each_class in ignoreable_classes]
    
    labelling_results_dict = {}
    for each_path in labelling_file_paths:
        
        # Get task name from labelling file & the labelling data itself
        file_name = os.path.basename(each_path)
        name_only, _ = os.path.splitext(file_name)
        labelling_data = load_json(each_path, convert_integer_keys=True)
        
        # Go through all labelling data, and get rid of unclassified/ignored entries
        filtered_labelling_data = {}
        for each_obj_id, each_class_idx in labelling_data.items():
            
            # Skip ignoreable entries
            if each_class_idx in ignoreable_indices:
                continue
            
            # Add all other entries to the filtered output
            new_fitlered_entry = {each_obj_id: each_class_idx}
            filtered_labelling_data.update(new_fitlered_entry)
        
        # Skip any tasks that have no labelling results after filtering
        no_labelling_data = (len(filtered_labelling_data) == 0)
        if no_labelling_data:
            continue
        
        # Add filtered task entry to the output
        new_entry = {name_only: filtered_labelling_data}
        labelling_results_dict.update(new_entry)
        
    # Raise an error if we have no data after filtering
    no_data_after_filtering = (len(labelling_results_dict) == 0)
    if no_data_after_filtering:
        raise AttributeError("Labelling data contains no labelled results!")
        
    return labelling_results_dict

# .....................................................................................................................

def get_object_id_loading_paths(dataset_folder_path, task_list):
    
    '''
    Function which bundles object id <-> file loading paths dictionary, per task
    '''
    
    obj_metadata_paths_by_task = {}
    for each_task in task_list:
        
        obj_metadata_folder_path = build_path_object_metadata(dataset_folder_path, each_task) 
        new_objid_path_lut = get_object_id_metadata_paths(obj_metadata_folder_path)
    
        obj_metadata_paths_by_task.update({each_task: new_objid_path_lut})
        
    return obj_metadata_paths_by_task

# .....................................................................................................................

def load_object_metadata(object_id, task_select, obj_metadata_paths_by_task):
    load_path = obj_metadata_paths_by_task[task_select][object_id]
    return load_json(load_path)

# .....................................................................................................................

def load_snapshot_metadata(snap_count, snap_count_paths_lut):
    snap_path = snap_count_paths_lut[snap_count]
    return load_json(snap_path)

# .....................................................................................................................

def load_snapshot_image(snapshot_image_folder_path, snapshot_metadata):
    
    snap_name = snapshot_metadata["snapshot_name"]
    snap_image_file = "{}.jpg".format(snap_name)
    snap_image_path = os.path.join(snapshot_image_folder_path, snap_image_file)
    
    return cv2.imread(snap_image_path)

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Select dataset

enable_debug_mode = False

# Create selector to handle camera selection & project pathing
selector = Resource_Selector()
project_root_path, cameras_folder_path = selector.get_project_pathing()
camera_select, camera_path = selector.camera(debug_mode=enable_debug_mode)

# Get listing of all available datasets
all_dataset_folders_path = build_dataset_path(cameras_folder_path, camera_select)

# Select dataset and build folder pathing to the selected dataset
dataset_folder_path, dataset_select, _ = cli_folder_list_select(all_dataset_folders_path, 
                                                                prompt_heading = "Select dataset", 
                                                                debug_mode = enable_debug_mode)


# Load labels lookup file
label_lut_path = build_labels_lut_path(cameras_folder_path, camera_select, dataset_select)
label_lut_dict = load_json(label_lut_path, convert_integer_keys = True)

# Load labelling results (for every task!)
labels_folder = build_labels_folder_path(cameras_folder_path, camera_select, dataset_select)
labelling_file_paths = get_file_list(labels_folder, 
                                     return_full_path = True,
                                     sort_list = False, 
                                     allowable_exts_list = [".json"])

# Load labels results
labelling_results_dict = filter_labelling_results(labelling_file_paths, label_lut_dict)
task_list = list(labelling_results_dict.keys())

# ---------------------------------------------------------------------------------------------------------------------
#%% Get dataset loading paths

# Get pathing to classifier snapshot metadata and list of all snapshot metadata files
snapshot_image_folder_path = build_path_to_snapshot_images(dataset_folder_path)
snapshot_metadata_folder_path = build_path_to_snapshot_metadata(dataset_folder_path)
snap_count_paths_lut = get_snapshot_count_paths(snapshot_metadata_folder_path)

# Get pathing to object metadata, by task
obj_metadata_paths_by_task = get_object_id_loading_paths(dataset_folder_path, task_list)


# ---------------------------------------------------------------------------------------------------------------------
#%% Grab crops of each object

cv2.destroyAllWindows()

for each_task, each_labelling_dict in labelling_results_dict.items():
    
    for each_obj_id, each_label_idx in each_labelling_dict.items():
        
        # Get label string, to place in proper folder
        label_str = label_lut_dict[each_label_idx]
        save_folder_path = build_crop_folder_save_paths(dataset_folder_path, label_str)
        os.makedirs(save_folder_path, exist_ok = True)
        
        
        # Load object metadata
        obj_md = load_object_metadata(each_obj_id, each_task, obj_metadata_paths_by_task)
        obj_first_frame_idx = obj_md["timing"]["first_frame_index"]
        obj_last_frame_idx = obj_md["timing"]["last_frame_index"]
        obj_track_data = obj_md["tracking"]
        obj_hulls = obj_track_data["hull"]
        obj_num_samples = obj_md["num_samples"]
        
        # Get bounding snapshot indices
        first_snap_count = obj_md["snapshots"]["first"]["snapshot_count"]
        last_snap_count = obj_md["snapshots"]["last"]["snapshot_count"]
        
        # Get all cropped snapshots for the given object id
        for snap_count in range(first_snap_count, 1 + last_snap_count):
            
            # Load snapshot metadata & image
            snap_md = load_snapshot_metadata(snap_count, snap_count_paths_lut)
            snap_image = load_snapshot_image(snapshot_image_folder_path, snap_md)
            
            # Get frame sizing
            snap_height, snap_width = snap_image.shape[0:2]
            frame_scaling = np.float32((snap_width - 1, snap_height - 1))
            
            # Get snapshot timing, relative to the object
            snap_frame_idx = snap_md["snapshot_frame_index"]
            
            # Get the data indexing for the corresponding snapshot
            obj_sample_idx = obj_last_frame_idx - snap_frame_idx
            if obj_sample_idx >= obj_num_samples:
                continue
            
            # Find the object bounding box, based on the hull
            obj_hull_norm = np.float32(obj_hulls[obj_sample_idx])
            obj_hull_tl = np.min(obj_hull_norm, axis = 0)
            obj_hull_br = np.max(obj_hull_norm, axis = 0)
            
            # Convert to pixels for cropping
            bbox_tl = np.int32(np.round(obj_hull_tl * frame_scaling))
            bbox_br = np.int32(np.round(obj_hull_br * frame_scaling))
            
            # Crop image data
            x1, y1 = bbox_tl
            x2, y2 = bbox_br
            crop_image = snap_image[y1:y2, x1:x2]
            #cv2.imshow("Crop", crop_image)
            
            # Build final save name & save the cropped image data!
            save_name = "{}-{}_({}).jpg".format(each_obj_id, snap_count, each_task)
            full_save_path = os.path.join(save_folder_path, save_name)
            cv2.imwrite(full_save_path, crop_image)
            
            #cv2.rectangle(snap_image, tuple(bbox_tl), tuple(bbox_br), (0, 255, 0))
            
            '''
            obj_hull_px = np.int32(np.round(obj_hull_norm * frame_scaling))            
            cv2.polylines(snap_image, [obj_hull_px], True, (0, 255, 0), 1, cv2.LINE_AA)
            '''
            
            #cv2.imshow("SNAP", snap_image)
            #cv2.waitKey(10)
        
        #cv2.waitKey(500)
    
    pass

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap



