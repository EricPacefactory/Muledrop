#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Aug 23 15:22:40 2019

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
import base64
import numpy as np
import datetime as dt

from time import sleep
from shutil import copytree
from itertools import cycle

from flask import Flask, render_template, jsonify, Response
from flask import request as flask_request

from local.lib.selection_utils import Resource_Selector
from local.lib.file_access_utils.reporting import build_base_report_path, build_image_report_path
from local.lib.file_access_utils.classifier import build_dataset_path, build_model_path
from local.lib.file_access_utils.classifier import build_supervised_labels_folder_path
from local.lib.file_access_utils.classifier import load_label_lut_tuple

from eolib.utils.files import get_file_list, get_folder_list, get_total_folder_size
from eolib.utils.cli_tools import cli_confirm, cli_select_from_list, clear_terminal
from eolib.utils.read_write import load_json, update_json

# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes


# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

# .....................................................................................................................

def spyder_catcher():
    if any(["spyder" in env_var.lower() for env_var in os.environ]):
        raise SystemExit("Can't run flask from Spyder IDE! Use terminal...")

# .....................................................................................................................



# ---------------------------------------------------------------------------------------------------------------------
#%% Select camera/user/task

enable_debug_mode = False

# Create selector so we can access existing report data
selector = Resource_Selector()
project_root_path, cameras_folder_path = selector.get_project_pathing()

# Select the camera/user/task to show data for (needs to have saved report data already!)
camera_select, camera_path = selector.camera(debug_mode=enable_debug_mode)
user_select, _ = selector.user(camera_select, debug_mode=enable_debug_mode)
task_select, _ = selector.task(camera_select, user_select, debug_mode=enable_debug_mode)

# ---------------------------------------------------------------------------------------------------------------------
#%% Catalog existing snapshot data

STOPPED HERE
- WHEN CATALOGING DATA, NEED TO GRAB FROM CLASSIFICATION STORAGE, NOT REPORTING FOLDERS!

# Start 'fake' database for accessing snapshot/object data
snap_db = Snap_DB(cameras_folder_path, camera_select, user_select, load_from_dataset = True)
obj_db = Object_DB(cameras_folder_path, camera_select, user_select, task_select)
class_db = Classification_DB(cameras_folder_path, camera_select, user_select, task_select)

# Post snapshot/object/classification data to the databases on start-up
post_snapshot_report_metadata(cameras_folder_path, camera_select, user_select, snap_db)
post_object_report_metadata(cameras_folder_path, camera_select, user_select, task_select, obj_db)
post_object_classification_data(cameras_folder_path, camera_select, user_select, task_select, class_db)

# ---------------------------------------------------------------------------------------------------------------------
#%% Ask user for time window

# Get the maximum range of the data (based on the snapshots, because all we can show)
earliest_datetime, latest_datetime = snap_db.get_bounding_datetimes()

# Ask the user for the range of datetimes to use for selecting data
start_dt, end_dt, _, _ = user_input_datetime_range(earliest_datetime, 
                                                   latest_datetime, 
                                                   enable_debug_mode)

# Get all the snapshot times we'll need for animation
snap_times = snap_db.get_all_snapshot_times_by_time_range(start_dt, end_dt)
num_snaps = len(snap_times)

# ---------------------------------------------------------------------------------------------------------------------
#%% Load object data

# Get object metadata from the server
obj_metadata_generator = obj_db.load_metadata_by_time_range(task_select, start_dt_isoformat, end_dt_isoformat)

# Create list of 'reconstructed' objects based on object metadata, so we can work/interact with the object data
obj_list = Obj_Recon.create_reconstruction_list(obj_metadata_generator,
                                                snap_wh,
                                                start_dt_isoformat, 
                                                end_dt_isoformat,
                                                smoothing_factor = 0.005)

# Load in classification data, if any
set_object_classification_and_colors(class_db, task_select, obj_list)


# ---------------------------------------------------------------------------------------------------------------------
#%% Define routes

# Crash spyder IDE before creating the server, since it doesn't work in the IDE!
spyder_catcher()
server = Flask(__name__)