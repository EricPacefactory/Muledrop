#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Mar 31 15:15:23 2020

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

from time import perf_counter

from local.lib.ui_utils.cli_selections import Resource_Selector

from local.offline_database.file_database import launch_file_db, close_dbs_if_missing_data
from local.offline_database.object_reconstruction import Smooth_Hover_Object_Reconstruction as Obj_Recon
from local.offline_database.object_reconstruction import Hover_Mapping
from local.offline_database.object_reconstruction import create_trail_frame_from_object_reconstruction
from local.offline_database.snapshot_reconstruction import median_background_from_snapshots
from local.offline_database.classification_reconstruction import create_object_class_dict

from local.lib.file_access_utils.classifier import build_supervised_labels_folder_path, load_supervised_labels

from local.lib.ui_utils.local_ui.windows_base import Simple_Window

from local.eolib.utils.cli_tools import Datetime_Input_Parser as DTIP

# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes


# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

# .....................................................................................................................

def get_sample_data(obj_recon_ref, frame_idx):
    
    # From raw data
    # x, y, dx, dy, w, h, area, ar
    
    # Get object sample index for the given frame index
    rel_idx = obj_recon_ref._rel_index(frame_idx)
    
    # Get x/y position info
    x_cen, y_cen = obj_recon_ref._real_trail_xy[rel_idx]
    
    # Try to calculate the x/y velocity
    try:
        x_futr, y_futr = obj_recon_ref._real_trail_xy[rel_idx + 1]
        x_prev, y_prev = obj_recon_ref._real_trail_xy[rel_idx - 1]
        dx_norm = (x_futr - x_prev)
        dy_norm = (y_futr - y_prev)
    except IndexError:
        dx_norm = 0.0
        dy_norm = 0.0
    
    # Get width/height info
    (x1, y1), (x2, y2) = obj_recon_ref.get_box_tlbr(frame_idx)
    width_norm = (x2 - x1)
    height_norm = (y2 - y1)
    
    # Get area/aspect ratio
    area_norm = (width_norm * height_norm)
    aspect_ratio = width_norm / height_norm    
    
    # Bundle for clarity
    output_entries = (x_cen, y_cen, dx_norm, dy_norm, width_norm, height_norm, area_norm, aspect_ratio)
    
    return output_entries

# .....................................................................................................................

def generate_training_data(objclass_dict, supervised_obj_labels_dict, 
                           num_subsamples = 10, 
                           start_inset = 0.02,
                           end_inset = 0.02,
                           print_feedback = True):
    
    # Initialize output. Should contain keys for each object id, storing all input data in lists
    obj_data_lists_dict = {}
    
    # Start timing and provide feedback
    t1 = perf_counter()
    if print_feedback:
        print("", "Generating training data tables...", sep = "\n")
    
    # Loop over every object (of every class) and get all data pair samples
    for each_class_label, each_obj_dict in objclass_dict.items():
        
        # Loop over all object ids
        for each_obj_id, each_obj_recon in each_obj_dict.items():
            
            # Get the start/end frame index of each object
            start_idx = each_obj_recon.start_idx
            end_idx = each_obj_recon.end_idx
            num_idx = (end_idx - start_idx)
            
            # Calculate a reduced set of samples to select training data from
            inset_start_idx = int(round(start_idx + start_inset * num_idx))
            inset_end_idx = int(round(end_idx - end_inset * num_idx))
            num_inset_idx = (inset_end_idx - inset_start_idx)
            
            # Skip this object if we don't have enough data for sampling
            if num_inset_idx < num_subsamples:
                continue
            
            # Grab some subset of samples to use for training
            subsample_indices = np.int32(np.round(np.linspace(inset_start_idx, inset_end_idx, num_subsamples)))
            
            # Grab every data pair for each object id
            supervised_label = supervised_obj_labels_dict[each_obj_id]["class_label"]
            new_data_list = [get_sample_data(each_obj_recon, each_idx) for each_idx in subsample_indices]
            obj_data_lists_dict[each_obj_id] = {"input": new_data_list,
                                                "output": [supervised_label] * len(new_data_list),
                                                "headings": ["x", "y", "dx", "dy", "w", "h", "area", "aspectratio"]}
    
    # End timing and provide final feedback
    t2 = perf_counter()
    if print_feedback:
        print("  Done! Took {:.0f} ms".format(1000 * (t2 - t1)))
    
    return obj_data_lists_dict

# .....................................................................................................................

def creating_training_arrays(training_data_dict):
    
    '''
    Takes an input dictionary with keys representing object ids, values store another dictionary,
    which has keys 'input', 'output' and 'headings' 
    the 'headings' key and data are just for documenting the data, not important
    the 'input' key represents lists of lists of data to be used as input for training
    the 'output' key represents the target output and holds a string representing the target class
    
    This function needs to output the input data, for all objects, as one large array.
    It must also output a single large array which contains the corresponding output data (mapped to integers ?)
    '''
    STOPPED HERE
    pass

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Select camera/user

enable_debug_mode = True

# Create selector so we can access existing report data
selector = Resource_Selector()
project_root_path, cameras_folder_path = selector.get_project_pathing()

# Select the camera/user to show data for (needs to have saved report data already!)
camera_select, camera_path = selector.camera(debug_mode=enable_debug_mode)
user_select, _ = selector.user(camera_select, debug_mode=enable_debug_mode)


# ---------------------------------------------------------------------------------------------------------------------
#%% Catalog existing data

cinfo_db, rinfo_db, snap_db, obj_db, class_db, _, _ = \
launch_file_db(cameras_folder_path, camera_select, user_select,
               launch_snapshot_db = True,
               launch_object_db = True,
               launch_classification_db = True,
               launch_summary_db = False,
               launch_rule_db = False)

# Catch missing data
cinfo_db.close()
rinfo_db.close()
close_dbs_if_missing_data(snap_db, error_message_if_missing = "No snapshot data in the database!")
close_dbs_if_missing_data(obj_db, error_message_if_missing = "No object trail data in the database!")


# ---------------------------------------------------------------------------------------------------------------------
#%% Ask user for time window

# Get the maximum range of the data (based on the snapshots, because all we can show)
earliest_datetime, latest_datetime = snap_db.get_bounding_datetimes()

# Ask the user for the range of datetimes to use for selecting data
user_start_dt, user_end_dt = DTIP.cli_prompt_start_end_datetimes(earliest_datetime, latest_datetime,
                                                                 print_help_before_prompt = False,
                                                                 debug_mode = enable_debug_mode)


# ---------------------------------------------------------------------------------------------------------------------
#%% Create background frame

# Ask database for several snapshot images, so we can 'average' them to make a background frame for display
bg_frame = median_background_from_snapshots(snap_db, user_start_dt, user_end_dt, 10)
frame_height, frame_width = bg_frame.shape[0:2]
frame_wh = (frame_width, frame_height)


# ---------------------------------------------------------------------------------------------------------------------
#%% Load object data

# Get object metadata from the server
obj_metadata_generator = obj_db.load_metadata_by_time_range(user_start_dt, user_end_dt)

# Create list of 'reconstructed' objects based on object metadata, so we can work/interact with the object data
obj_list = Obj_Recon.create_reconstruction_list(obj_metadata_generator,
                                                frame_wh,
                                                user_start_dt, 
                                                user_end_dt)

# Organize objects by class label -> then by object id (nested dictionaries)
objclass_dict = create_object_class_dict(class_db, obj_list)

# Generate trail hover mapping, for quicker mouse-to-trail lookup
hover_map = Hover_Mapping(objclass_dict)


# ---------------------------------------------------------------------------------------------------------------------
#%% Generate training data

# Load supervised data
sv_labels_folder = build_supervised_labels_folder_path(cameras_folder_path, camera_select, user_select)
obj_id_list = [each_obj_recon.full_id for each_obj_recon in obj_list]
sv_labels_dict = load_supervised_labels(sv_labels_folder, obj_id_list)

# Build training data set
training_data_dict = generate_training_data(objclass_dict, sv_labels_dict, num_subsamples = 10)
input_data_array, output_data_array = creating_training_arrays(training_data_dict)


from sklearn.model_selection import train_test_split
from sklearn.tree import DecisionTreeClassifier

X_train, X_test, y_train, y_test = train_test_split(input_data_array, output_data_array, test_size=0.20)

classifier = DecisionTreeClassifier()
classifier.fit(X_train, y_train)

# ---------------------------------------------------------------------------------------------------------------------
#%% Create initial images

# Generate the background display frame, containing all object trails
trails_background = create_trail_frame_from_object_reconstruction(bg_frame, obj_list)


# ---------------------------------------------------------------------------------------------------------------------
#%% Interaction loop

# Close any previously open windows
cv2.destroyAllWindows()

# Set up main display window
disp_window = Simple_Window("Display")
disp_window.move_corner_pixels(50, 50)
print("", "Press Esc to close", "", sep="\n")

while True:
    
    # Make clean copies of the frames to display, so we don't muddy up the originals
    display_frame = trails_background.copy()
    
    # Show final display
    winexist = disp_window.imshow(display_frame)
    if not winexist:
        break
    
    # Break on esc key
    keypress = cv2.waitKey(50)
    if keypress == 27:
        break


# Some clean up
cv2.destroyAllWindows()

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap


