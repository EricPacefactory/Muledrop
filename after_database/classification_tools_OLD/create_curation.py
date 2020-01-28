#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Oct 21 15:19:47 2019

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

from tqdm import tqdm

from local.lib.ui_utils.cli_selections import Resource_Selector

from local.lib.file_access_utils.classifier import select_classification_dataset
from local.lib.file_access_utils.classifier import build_curation_folder_path
from local.lib.file_access_utils.classifier import load_supervised_labels

from local.offline_database.file_database import Snap_DB, Object_DB
from local.offline_database.file_database import post_snapshot_dataset_metadata, post_object_dataset_metadata
from local.offline_database.object_reconstruction import Object_Reconstruction as Obj_Recon

from local.lib.common.timekeeper_utils import get_isoformat_string

from eolib.utils.read_write import save_json, load_json
from eolib.utils.files import get_file_list


# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes




# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

# .....................................................................................................................

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Select dataset

enable_debug_mode = False

# Create selector to handle camera selection & project pathing
selector = Resource_Selector()
project_root_path, cameras_folder_path = selector.get_project_pathing()
camera_select, camera_path = selector.camera(debug_mode=enable_debug_mode)
user_select, _ = selector.user(camera_select, debug_mode=enable_debug_mode)

# Select dataset
dataset_folder_path, dataset_select = select_classification_dataset(cameras_folder_path, camera_select, 
                                                                    enable_debug_mode)

# Bundle dataset pathing for convenience
dataset_path_args = (cameras_folder_path, camera_select, dataset_select)

# Load labels lookup file & filtered labelling results (from using classifier UI)
task_list, supervised_labels_dict = load_supervised_labels(*dataset_path_args)

# ---------------------------------------------------------------------------------------------------------------------
#%% Catalog data

# Start 'fake' database for accessing snapshot/object data
snap_db = Snap_DB(cameras_folder_path, camera_select, user_select, load_from_dataset = dataset_select)
obj_db = Object_DB(cameras_folder_path, camera_select, user_select, task_select = None)

# Post snapshot data to the database on start-up
post_snapshot_dataset_metadata(cameras_folder_path, camera_select, dataset_select, snap_db)

# Post object data for all tasks on start-up
for each_task in task_list:
    post_object_dataset_metadata(cameras_folder_path, camera_select, each_task, dataset_select, obj_db)
    
    
# ---------------------------------------------------------------------------------------------------------------------
#%% Get time range

# Ask user for input time range
# ...
earliest_datetime, latest_datetime = snap_db.get_bounding_datetimes()

# Check how many snapshots are present, if too many, limit to ... 100? Or ask user???
# ...


# Get the full range of data as datetime strings
start_dt_isoformat = get_isoformat_string(earliest_datetime)
end_dt_isoformat = get_isoformat_string(latest_datetime)

# Get all snapshot times for lookup
all_snap_times = snap_db.get_all_snapshot_times_by_time_range(earliest_datetime, latest_datetime)
num_snaps = len(all_snap_times)


# ---------------------------------------------------------------------------------------------------------------------
#%% Create initial curation files

# Allocate storage for reconstructed objects (per task), which we'll create as needed
obj_recon_dict = {each_task: {} for each_task in task_list}

# Build pathing to each curation folder
curation_folder_path = build_curation_folder_path(*dataset_path_args)
os.makedirs(curation_folder_path, exist_ok = True)

# Some feedback
print("", "Curating data ({} snapshots)".format(num_snaps), sep = "\n")

# Create default curation files for each known snapshot
cli_prog_bar = tqdm(total = num_snaps, mininterval = 0.25)
for each_snap_time in all_snap_times:
    
    # Load snapshot metadata
    snap_md = snap_db.load_snapshot_metadata(each_snap_time)
    snap_name = snap_md["name"]
    snap_frame_index = snap_md["frame_index"]
    snap_wh = (snap_md["snap_width"], snap_md["snap_height"])
    snap_datetime_isoformat = snap_md["datetime_isoformat"]
    
    # Build pathing to each snap curation file
    curation_file_name = "{}.json".format(snap_name)
    curation_save_path = build_curation_folder_path(*dataset_path_args, curation_file_name)
    
    # Load existing data, if available
    empty_task_dict = {each_task: {} for each_task in task_list}
    curation_dict = {"snapshot_metadata": snap_md, "tasks": empty_task_dict}
    if os.path.exists(curation_save_path):
        curation_dict = load_json(curation_save_path, convert_integer_keys = True)
    
    # Add curation data for each task
    for each_task in task_list:
        
        # Get all object ids at the current snapshot time
        no_objs, obj_id_list = obj_db.get_ids_at_target_time(each_task, snap_datetime_isoformat)
        
        # If there aren't any objects on this snapshot (for this task) move onto the next task
        if no_objs:
            continue
        
        # Go through all objects in snapshot and store their outline/bounding box data + class labels
        num_objs = len(obj_id_list)
        for each_obj_id in obj_id_list:
            
            # Skip this object if it's already been looked at
            obj_is_curated = curation_dict["tasks"][each_task].get(each_obj_id, {}).get("user_confirmed", False)
            if obj_is_curated:
                continue
            
            # Get object classification from class labelling file
            class_label = supervised_labels_dict[each_task][each_obj_id]
            
            # Retrieve object reconstruction data, if available, otherwise generate (and store) it now
            obj_ref = obj_recon_dict[each_task][each_obj_id]
            no_obj_ref = (obj_ref is None)
            if no_obj_ref:
                obj_md = obj_db.load_metadata_by_id(each_task, each_obj_id)
                obj_ref = Obj_Recon(obj_md, snap_wh, start_dt_isoformat, end_dt_isoformat)
                obj_recon_dict[each_task][each_obj_id] = obj_ref
            
            # Try getting the object hull at the target frame index
            obj_hull_array = obj_ref.get_hull_array(snap_frame_index)
            
            # If no hull data exists at the given frame, skip the object!
            if obj_hull_array is None:
                continue
            
            # Get bounding box & json-friendly hull
            obj_box_tlbr = obj_ref.get_box_tlbr(snap_frame_index, normalized = True)
            obj_hull = obj_hull_array.tolist()
            
            # Add object curation entry
            new_obj_entry = {"class_label": class_label, 
                             "hull": obj_hull, 
                             "box_tlbr": obj_box_tlbr, 
                             "user_confirmed": False}
            curation_dict["tasks"][each_task][each_obj_id] = new_obj_entry
    
    # Save final curation entry for each snapshot
    save_json(curation_save_path, curation_dict, indent = None)
    cli_prog_bar.update()
    
# Clean up
cli_prog_bar.close()
print("")

# ---------------------------------------------------------------------------------------------------------------------
#%% Inspect results

# Clear any previously opened windows
cv2.destroyAllWindows()

# Play snapshots back as a 'video' with curation bounding boxes overlayed for inspection
curation_folder_path = build_curation_folder_path(*dataset_path_args)
curation_file_paths = get_file_list(curation_folder_path, return_full_path = True)
for each_curation_path in curation_file_paths:
    
    # Load curation data
    loaded_curation_dict = load_json(each_curation_path, convert_integer_keys = True)
    snap_name = loaded_curation_dict["snapshot_metadata"]["name"]
    snap_time = loaded_curation_dict["snapshot_metadata"]["epoch_ms"]
    
    # Load snapshot image
    snap_image, _ = snap_db.load_snapshot_image(snap_time)
    snap_height, snap_width = snap_image.shape[0:2]
    snap_frame_scaling = np.float32((snap_width - 1, snap_height - 1))
    
    # For every task, draw all object bounding boxes with class labels
    task_data = loaded_curation_dict["tasks"]
    for each_task_name, each_task_dict in task_data.items():
        
        for each_obj_id, each_obj_md in each_task_dict.items():
        
            # Draw object bounding box
            pt1, pt2 = np.int32(np.round(each_obj_md["box_tlbr"] * snap_frame_scaling))
            cv2.rectangle(snap_image, tuple(pt1), tuple(pt2), (0, 255, 0), 1)
            
            # Draw class label
            far_from_bottom = (snap_height - pt2[1]) > 30
            label_x = pt1[0]
            label_y = pt2[1] + 10 if far_from_bottom else pt1[1] - 6
            label_xy = (label_x, label_y)
            label_text = each_obj_md["class_label"]
            cv2.putText(snap_image, label_text, label_xy, 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1, cv2.LINE_AA)
    
    # Display the image
    cv2.imshow("INSPECT", snap_image)
    keypress = cv2.waitKey(50)
    if keypress == 27:
        break
    
cv2.destroyAllWindows()


# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap

# TODOs
# - Improve curated inspection (show tiled view of shuffled examples?)
# - Deal with input time range, what happens if tons of inputs are available? Process all of them?
# - What about running over a week of data? Ideally sample N times across long periods...

