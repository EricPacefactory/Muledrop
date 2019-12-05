#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Aug 23 16:43:38 2019

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

from local.lib.selection_utils import Resource_Selector

from eolib.utils.read_write import load_json

# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

# .....................................................................................................................

def load_metadata(path):       
        
    try:
        metadata = load_json(path)        
        
    except Exception:
        # Objects alive at the end of the processed file will appear in the snapshot metadata, 
        # but will not have saved any object metadata, causing an error when trying to load them!
        metadata = None
        
    return metadata

# .....................................................................................................................
    
def load_target_obj_ids(id_path_lut, id_list):
    
    metadata_dict = {}
    for each_id in id_list:
        id_data_path = id_path_lut.get(each_id)
        obj_id_metadata = load_metadata(id_data_path)
        
        # Make sure we loaded metadata. May fail if object data wasn't saved (but appeared in snapshot data)
        if obj_id_metadata:
            metadata_dict.update({each_id: obj_id_metadata})
        
    return metadata_dict

# .....................................................................................................................

def draw_trail(frame, object_metadata, final_plot_index, frame_scaling_array):
    
    # Don't bother trying to draw anything if there aren't any samples!
    num_samples = object_metadata.get("num_samples")
    if num_samples <= final_plot_index:
        return
    
    # Get all trail data
    obj_x_list = object_metadata.get("tracking").get("x_track")
    obj_y_list = object_metadata.get("tracking").get("y_track")
    
    # Take only the data needed for plotting
    obj_x_array = np.float32(obj_x_list[final_plot_index:])
    obj_y_array = np.float32(obj_y_list[final_plot_index:])
    
    # Convert trail data to pixel units and draw as an open polygon
    trail_xy = np.int32(np.round(np.vstack((obj_x_array, obj_y_array)).T * frame_scaling_array))
    cv2.polylines(frame, 
                  pts = [trail_xy],
                  isClosed = False, 
                  color = (0, 255, 255),
                  thickness = 1,
                  lineType = cv2.LINE_AA)

# .....................................................................................................................

def draw_outline(frame, object_metadata, final_plot_index, frame_scaling_array):
    
    # Don't bother trying to draw anything if there aren't any samples!
    num_samples = object_metadata.get("num_samples")
    if num_samples <= final_plot_index:
        return
    
    # Convert outline to pixel units and draw it
    hull = object_metadata.get("tracking").get("hull")
    hull_array = np.int32(np.round(np.float32(hull[final_plot_index]) * frame_scaling_array))
    cv2.polylines(frame, 
                  pts = [hull_array], 
                  isClosed = True, 
                  color = (0, 255, 0),
                  thickness = 1,
                  lineType = cv2.LINE_AA)

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Get report data pathing

# Select the camera/user/task to show data for (needs to have saved report data already!)
selector = Resource_Selector()
camera_select, camera_path = selector.camera()
user_select, _ = selector.user(camera_select)
task_select, _ = selector.task(camera_select, user_select)

# Build base report folder path
report_data_folder_path = os.path.join(camera_path, "report", user_select)

# Folders containing reported data
object_metadata_folder = os.path.join(report_data_folder_path, "metadata", "objects-({})".format(task_select))
snapshot_metadata_folder = os.path.join(report_data_folder_path, "metadata", "snapshots")
snapshot_image_folder = os.path.join(report_data_folder_path, "images", "snapshots")

# Make sure the report data folders exist
check_paths = (object_metadata_folder, snapshot_metadata_folder, snapshot_image_folder)
if not all([os.path.exists(each_path) for each_path in check_paths]):
    raise FileNotFoundError("Couldn't find report data paths!")


# ---------------------------------------------------------------------------------------------------------------------
#%% Get snap/object metadata 

# Some helper functions
sorted_data_paths = lambda folder: [os.path.join(folder, each_file) for each_file in sorted(os.listdir(folder))]
remove_dir = lambda path: os.path.basename(path)
remove_idx = lambda file: file.split("-")[0]
name_path_tuples = lambda paths: [(remove_idx(remove_dir(each_path)), each_path) for each_path in paths]

# Grab list of loading paths for snapshot metadata and a LUT of object IDs and corresponding metadata loading paths
snap_data_paths_list = sorted_data_paths(snapshot_metadata_folder)
obj_data_paths_list = sorted_data_paths(object_metadata_folder)
obj_data_paths_dict = {int(each_id): each_path for each_id, each_path in name_path_tuples(obj_data_paths_list)}

# Handle possible future error (object data stored across multiple indexed files, which currently isn't supported)
find_idx_error = lambda file: (int(file.split(".")[0].split("-")[1]) > 0)
if any((find_idx_error(remove_dir(each_path)) for each_path in obj_data_paths_list)):
    raise ValueError("Found object with non-zero partition index! Replay does not support this (yet)!")

# ---------------------------------------------------------------------------------------------------------------------
#%% Play recorded data

# Create window so can place it
disp_window = "Display"
cv2.namedWindow(disp_window)
cv2.moveWindow(disp_window, x = 20, y = 20)

# For clarity
esc_key = 27

print("", "Press Esc to cancel", sep="\n")
for each_snap_md_path in snap_data_paths_list:
    
    # Separate snapshot metadata into easier to use variables
    snap_metadata = load_metadata(each_snap_md_path)
    snap_frame_idx = snap_metadata.get("frame_index")
    snap_name = snap_metadata.get("name")
    snap_objs_ids_in_frame_dict = snap_metadata.get("object_ids_in_frame")
    
    # Load the appropriate image and determine which objects were in the frame
    snap_image_name = "{}.jpg".format(snap_name)
    snap_image_path = os.path.join(snapshot_image_folder, snap_image_name)
    objs_in_image = snap_objs_ids_in_frame_dict.get(task_select)
    
    # Load the (clean) image data
    display_frame = cv2.imread(snap_image_path)
    frame_height, frame_width = display_frame.shape[0:2]
    frame_scaling = np.float32((frame_width - 1, frame_height - 1))
    
    # Load the object data
    obj_metadata_dict = load_target_obj_ids(obj_data_paths_dict, objs_in_image)
    
    # Annotate the current frame with object metadata
    for each_id, each_obj_md in obj_metadata_dict.items():
        
        # Figure out how much data to use when plotting at the current snapshot
        end_frame_idx = each_obj_md.get("timing").get("last_frame_index")
        final_plot_idx = max(0, end_frame_idx - snap_frame_idx)
        
        # Draw trail (x/y history) and outline
        draw_trail(display_frame, each_obj_md, final_plot_idx, frame_scaling)
        draw_outline(display_frame, each_obj_md, final_plot_idx, frame_scaling)
    
    # Show the frame and close with keypress
    cv2.imshow(disp_window, display_frame)
    keypress = cv2.waitKey(50)
    if keypress == esc_key:
        break

# Clean up
cv2.destroyAllWindows()
print("DONE!", "", sep="\n")


# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap

