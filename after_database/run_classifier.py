#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Oct 30 15:22:01 2019

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

from time import perf_counter

from local.lib.selection_utils import Resource_Selector

from local.offline_database.file_database import Snap_DB, Object_DB, Classification_DB
from local.offline_database.file_database import post_snapshot_report_metadata, post_object_report_metadata
from local.offline_database.file_database import post_object_classification_data

from local.lib.file_access_utils.shared import configurable_dot_path
from eolib.utils.function_helpers import dynamic_import_from_module

from eolib.utils.cli_tools import cli_confirm
from eolib.utils.read_write import load_json

# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

# .................................................................................................................
    
def import_classifier_class(cameras_folder_path, camera_select, user_select, task_select):
    
    # Check configuration file to see which script/class to load from & get configuration data
    pathing_args = (cameras_folder_path, camera_select, user_select, task_select)
    _, file_access_dict, setup_data_dict = _load_classifier_config_data(*pathing_args)
    script_name = file_access_dict.get("script_name")
    class_name = file_access_dict.get("class_name")
    
    # Programmatically import the target class
    dot_path = configurable_dot_path("after_database", "classifier", script_name)
    Imported_Classifier_Class = dynamic_import_from_module(dot_path, class_name)
    
    return Imported_Classifier_Class, setup_data_dict
    
# .................................................................................................................
    
def _load_classifier_config_data(cameras_folder_path, camera_select, user_select, task_select):
    
    ''' 
    Function which finds and loads pre-saved configuration files for a classifier
    '''
    
    # Get path to the config file
    path_to_config = os.path.join(cameras_folder_path, 
                                  camera_select, 
                                  "users", 
                                  user_select,
                                  "tasks",
                                  task_select,
                                  "classifier", "classifier.json")
    
    # Load json data and split into file access info & setup configuration data
    config_dict = load_json(path_to_config)
    access_info_dict = config_dict.get("access_info")
    setup_data_dict = config_dict.get("setup_data")
    
    return path_to_config, access_info_dict, setup_data_dict

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
task_select, _ = selector.task(camera_select, user_select, debug_mode=enable_debug_mode)

# ---------------------------------------------------------------------------------------------------------------------
#%% Catalog existing snapshot data

# Start 'fake' database for accessing snapshot/object data
snap_db = Snap_DB(cameras_folder_path, camera_select, user_select)
obj_db = Object_DB(cameras_folder_path, camera_select, user_select, task_select)
class_db = Classification_DB(cameras_folder_path, camera_select, user_select, task_select)

# Post snapshot/object/classification data to the databases on start-up
post_snapshot_report_metadata(cameras_folder_path, camera_select, user_select, snap_db)
post_object_report_metadata(cameras_folder_path, camera_select, user_select, task_select, obj_db)
post_object_classification_data(cameras_folder_path, camera_select, user_select, task_select, class_db)


# ---------------------------------------------------------------------------------------------------------------------
#%% Load & configure classifier

'''
#import torch
#from local.lib.classifier_models.squeezenet_variants import Truncated_SqueezeNet
from local.lib.classifier_models.squeezenet_variants import Full_SqueezeNet_112x112
from local.offline_database.object_reconstruction import Object_Reconstruction as Obj_Recon

#ordered_class_names = class_db.ordered_class_names()
#classifier_model = Truncated_SqueezeNet(ordered_class_names)
#load_path = "/home/wrk/Desktop/pytorch_saved_models/truncated_squeezenet_112x112_state_dict_wip.pt"

load_path = "/home/wrk/Desktop/pytorch_saved_models"
load_name = "full_sn_112x112_wip"
classifier_model = Full_SqueezeNet_112x112.load_model_from_path(load_path, load_name)
classifier_model.set_to_inference_mode()
'''

# Programmatically import the target classifier class
pathing_args = (cameras_folder_path, camera_select, user_select, task_select)
Imported_Classifier_Class, setup_data_dict = import_classifier_class(*pathing_args)
classifier_ref = Imported_Classifier_Class(*pathing_args)
classifier_ref.reconfigure(setup_data_dict)
classifier_ref.set_to_inference_mode()


STOPPED HERE
- IMPORTED LOADING IS WORKING!
- NEED TO CREATE CONFIG UTIL TO SAVE CONFIG IN THE FIRST PLACE!!!
    - CONFIG UTIL ALSO HAS TO CREATE DEFAULT FILE, IF MISSING...
        - SHOULD PROBABLY CREATE A TEMPORARY FILE ONLY, IN CASE THE USER DOESNT SAVE (AND DELETE IF THEY DONT SAVE!)
    - SHOULD HAVE INITIAL MENU ASKING HOW TO USE MODEL:
        - USE EXISTING MODEL (NO TRAINING)
        - TRAIN WHOLE MODEL ON EXISTING CURATED DATASET
        - FINE-TUNE TRAIN MODEL (ONLY LAST LAYERS?) ON CURATED DATA
        - RESET TO ORIGINAL MODEL
    - IF TRAINING IS SELECTED, THIS SHOULD RUN BEFORE THE REST OF THE UI POPS UP!
    - ONCE AT REAL UI, SHOULD PRESENT WINDOW ANIMATING OBJECT
        - CLASSIFIER SHOULD RUN ON EVERY FRAME, WITH RESULT SHOWN AS TIMEBAR TYPE VISUAL
        - NEED ABILITY TO SWITCH TO OTHER OBJECTS (SLIDER)
        - ALSO NEED TO BE ABLE TO CONTROL PLAYBACK? EITHER ARROW KEY BACK/FORWARD OR SPACEBAR PAUSE...?
    - SHOULD ALSO SHOW WINDOW OF CROPPED IMAGE USED FOR CLASSIFICATION
    - ALSO SHOW WINDOW INDICATING CLASSIFICATION LEGEND (COLORS)
    - SHOULD HAVE A WINDOW SHOWING THE CLASSIFICATION BREAKDOWN  (I.E. WHAT PERCENT FOR EACH CLASS) FOR EVERY FRAME


# ---------------------------------------------------------------------------------------------------------------------
#%% Get data for classification

# Get the maximum range of the data (based on the snapshots, because that's the most we could show)
earliest_datetime, latest_datetime = snap_db.get_bounding_datetimes()
snap_wh = snap_db.get_snap_frame_wh()

# Create a list of objects, according to the classifier's requirements
obj_metadata_generator = classifier_ref.request_object_data(obj_db, task_select, earliest_datetime, latest_datetime)
obj_list = classifier_ref.create_object_list(obj_metadata_generator, snap_wh, earliest_datetime, latest_datetime)

# Some feedback & timing
print("", "Running classification...", sep = "\n")
t_start = perf_counter()

# Run the classifier on the selected dataset
classification_dict = classifier_ref.run(obj_list, snap_db, enable_progress_bar = True)
classifier_ref.close()

# Some final feedback & timing
t_end = perf_counter()
total_processing_time_sec = t_end - t_start
print("", "Finished! Took {:.1f} seconds".format(total_processing_time_sec), sep = "\n")


# ---------------------------------------------------------------------------------------------------------------------
#%% Update local classification file

# Don't update the classification file unless the user agrees!
user_confirm = cli_confirm("Update local classification file?", default_response = False)
if user_confirm:

    # Update the classification database with new object classification!
    for each_obj_id, each_result_dict in classification_dict.items():
        class_db.update_entry(task_select, each_obj_id, 
                              new_class_label = each_result_dict["class_label"],
                              new_score_pct = each_result_dict["score_pct"])
        
    # Finally, update the local classification file to permanently save the changes
    class_db.update_classification_file(task_select)


# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap


