#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Mar 29 11:19:56 2020

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

from local.lib.ui_utils.local_ui.windows_base import Simple_Window

from local.offline_database.file_database import launch_file_db, close_dbs_if_missing_data
from local.offline_database.object_reconstruction import Smoothed_Object_Reconstruction as Obj_Recon
from local.offline_database.classification_reconstruction import set_object_classification_and_colors

from local.eolib.utils.cli_tools import Datetime_Input_Parser as DTIP

# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes



# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

# .....................................................................................................................

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
rinfo_db.close()
close_dbs_if_missing_data(snap_db, error_message_if_missing = "No snapshot data in the database!")

# Get the maximum range of the data (based on the snapshots, because that's the most we could show)
earliest_datetime, latest_datetime = snap_db.get_bounding_datetimes()
snap_wh = cinfo_db.get_snap_frame_wh()


# ---------------------------------------------------------------------------------------------------------------------
#%% Ask user for time window

# Ask the user for the range of datetimes to use for selecting data
user_start_dt, user_end_dt = DTIP.cli_prompt_start_end_datetimes(earliest_datetime, latest_datetime,
                                                                 print_help_before_prompt = False,
                                                                 debug_mode = enable_debug_mode)

# Get all the snapshot times we'll need for animation
snap_time_ms_list = snap_db.get_all_snapshot_times_by_time_range(user_start_dt, user_end_dt)
num_snaps = len(snap_time_ms_list)


# ---------------------------------------------------------------------------------------------------------------------
#%% Load object data

# Get object metadata from the server
obj_metadata_generator = obj_db.load_metadata_by_time_range(user_start_dt, user_end_dt)

# Create list of 'reconstructed' objects based on object metadata, so we can work/interact with the object data
obj_list = Obj_Recon.create_reconstruction_list(obj_metadata_generator,
                                                snap_wh,
                                                user_start_dt, 
                                                user_end_dt)

# Load in classification data, if any
set_object_classification_and_colors(class_db, obj_list)


# ---------------------------------------------------------------------------------------------------------------------
#%% Data playback

# Create window for display
window_title = "Label"
disp_window = Simple_Window(window_title)

# Set keycode for clarity
esc_key = 27

# Some control feedback
# ...

# Loop over snapshot times to generate the playback video
snap_idx = 0
while True:
    
    # Get the next snap time
    current_snap_time_ms = snap_time_ms_list[snap_idx]
    
    # Load each snapshot image & draw object annoations over top
    snap_image, snap_frame_idx = snap_db.load_snapshot_image(current_snap_time_ms)
    for each_obj in obj_list:
        #each_obj.draw_trail(snap_image, snap_frame_idx, current_snap_time_ms)
        each_obj.draw_outline(snap_image, snap_frame_idx, current_snap_time_ms)
    
    # Display the snapshot image, but stop if the window is closed
    winexists = disp_window.imshow(snap_image)
    if not winexists:
        break
    
    # Awkwardly handle keypresses
    keypress = cv2.waitKey(50)
    if keypress == esc_key:
        break
    
    # Update snap index
    snap_idx += 1
    if snap_idx >= num_snaps:
        snap_idx = 0

# Clean up
cv2.destroyAllWindows()


# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap

# TODO:
# - Add prompt for snap subsampling (i.e. how many snaps to label? Though script should tolerate early stopping)
# - Randomize snap indexing (don't show sequential snaps)
#   - maybe even non-random? Keep splitting intervals in 2, and take mid-point snaps???
#   - would create most separated possible indexing...
# - Draw bboxes, not outlines
# - Add ability to assign labels to bboxes (using number keys: 1,2,3,4,5...) and delete boxes?
# - Add ability to draw bounding boxes (shift + left-click/drag)
# - Add ability to modify bounding boxes (left-click/drag on corners)
# - Add 'memory' so objects will be pre-labelled, based on existing user labels? 
#   - this is very complex if label changes over obj lifetime. Also tough to handle bbox resizing...
# - Need to come up with useful storage format (likely something using json)
# - May want conversion script to create tflow formatted outputs for training
