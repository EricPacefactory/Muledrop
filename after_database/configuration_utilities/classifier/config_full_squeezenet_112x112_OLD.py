#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Nov  6 16:52:36 2019

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

from local.offline_database.file_database import launch_file_db
#from local.offline_database.file_database import post_classifier_report_data

from local.lib.ui_utils.local_ui.windows_base import Simple_Window

from eolib.utils.cli_tools import cli_confirm, cli_select_from_list

#from local.configurables.after_database.classifier.full_squeezenet_112x112 import Image_Based_Classifier_Stage

# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

# .....................................................................................................................

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Define displays


# ---------------------------------------------------------------------------------------------------------------------
#%% Select camera/user

enable_debug_mode = False

# Create selector so we can access existing report data
selector = Resource_Selector()
project_root_path, cameras_folder_path = selector.get_project_pathing()

# Select the camera/user to show data for (needs to have saved report data already!)
camera_select, camera_path = selector.camera(debug_mode=enable_debug_mode)
user_select, _ = selector.user(camera_select, debug_mode=enable_debug_mode)


# ---------------------------------------------------------------------------------------------------------------------
#%% Catalog existing data

cinfo_db, snap_db, obj_db, _, _, _ = launch_file_db(cameras_folder_path, camera_select, user_select, 
                                                    launch_classification_db = False)

# Check if curated data exists
# ...
curated_data_exists = False

# ---------------------------------------------------------------------------------------------------------------------
#%% Model Selection

# Check if a model file already exists
# ...
model_exists = False

# If a model doesn't exist, copy a temporary model file into the camera resources folder
# ...


# If a model exists, ask the user what to do with it
if model_exists:
    
    # Build base options
    model_select_list = ["Configure existing model",
                         "Reset to original model"]
    
    # If a curated data set exists, provide the option to train the model
    if curated_data_exists:
        model_select_list += ["Train entire model",
                              "Fine-tune model"]
    
    # Prompt user for how they want to interact with the model
    idx_select, entry_select = cli_select_from_list(model_select_list, 
                                                    prompt_heading = "Select model interaction:", 
                                                    default_selection = model_select_list[0], 
                                                    debug_mode = enable_debug_mode)

# ---------------------------------------------------------------------------------------------------------------------
#%% Load & configure classifier


if model_exists:
    setup_data_dict = None # Load existing config file...
else:
    setup_data_dict = {"model_file_name_no_ext": "tmp"}

'''
pathing_args = (cameras_folder_path, camera_select, user_select)
classifier_ref = Image_Based_Classifier_Stage(*pathing_args)
classifier_ref.reconfigure(setup_data_dict)
'''

# ---------------------------------------------------------------------------------------------------------------------
#%% Train model (optional)

# If training action selected, run it here...
# ...
#classifier_ref.set_to_full_train_mode(True)
#classifier_ref.set_to_fine_tune_mode(True)


# ---------------------------------------------------------------------------------------------------------------------
#%% Get data for classification

# Get the maximum range of the data (based on the snapshots, because that's the most we could show)
earliest_datetime, latest_datetime = snap_db.get_bounding_datetimes()
snap_wh = cinfo_db.get_snap_frame_wh()

'''
# Create a list of objects, according to the classifier's requirements
obj_metadata_generator = classifier_ref.request_object_data(obj_db, earliest_datetime, latest_datetime)
obj_list = classifier_ref.create_object_list(obj_metadata_generator, snap_wh, earliest_datetime, latest_datetime)
'''

# Get object data (ideally use classifier to do this)
from local.offline_database.object_reconstruction import Smoothed_Object_Reconstruction as Obj_Recon
obj_metadata_generator = obj_db.load_metadata_by_time_range(earliest_datetime, latest_datetime)
obj_list = Obj_Recon.create_reconstruction_list(obj_metadata_generator,
                                                snap_wh,
                                                earliest_datetime, 
                                                latest_datetime,
                                                smoothing_factor = 0.005)

# ---------------------------------------------------------------------------------------------------------------------
#%% Examine model

# Make sure we can use the model in inference mode
#classifier_ref.set_to_inference_mode()

# Create display windows
snap_width, snap_height = snap_wh
main_window = Simple_Window("Objects").move_corner_pixels(50, 50)
score_window = Simple_Window("Scoring").move_corner_pixels(50, 100 + snap_height)
crop_window = Simple_Window("Cropped Image").move_corner_pixels(100 + snap_width, 50)


keypress = -1
while True:
    
    for each_obj in obj_list:
        
        start_time_ems = each_obj.start_ems
        end_time_ems = each_obj.end_ems
        
        snap_times = snap_db.get_all_snapshot_times_by_time_range(start_time_ems, end_time_ems)
        for each_snap_time in snap_times:
        
            # Get each snapshot and draw all outlines/trails for all objects in the frame
            snap_image, snap_frame_idx = snap_db.load_snapshot_image(each_snap_time)
            
            # Create crop image for display
            crop_image = each_obj.crop_image(snap_image, snap_frame_idx, 75, 75)
            
            #  Draw outline/trail for the current object
            main_image = snap_image.copy()
            each_obj.draw_trail(main_image, snap_frame_idx)
            each_obj.draw_outline(main_image, snap_frame_idx)
            
            # Display the snapshot image, but stop if the window is closed
            crop_window.imshow(crop_image)
            winexists = main_window.imshow(main_image)
            if not winexists:
                break
            
            keypress = cv2.waitKey(50)
            if keypress == 27:
                break
        
        if keypress == 27:
            break
        
    if keypress == 27:
        break


# Clean up
cv2.destroyAllWindows()

'''
STOPPED HERE
- NEED TO ADD OBJECT SELECTION TRACKBAR (INSTEAD OF LOOPING THROUGH IMMEDIATELY)
- THEN NEED TO ADD PAUSE/FORWARD/BACKWARD PLAYBACK CONTROLS WHILE VIEWING OBJECT
- THEN ROUGH OUT PLACE FOR SCORING 'TIMEBAR' VISUAL
- ALSO ROUGH OUT SCORING DISPLAY + LEGEND COLORS
- THEN NEED TO GET CLASSIFIER TO RUN ON EVERY FRAME & REPORT RESULTS FOR DISPLAY
    - PASS RESULTS TO SCORING + LEGEND DISPLAY FIRST
    - THEN GET RESULTS FED INTO TIMEBAR VISUAL
    - MAY NEED TO THINK ABOUT HOW TO RUN CLASSIFIER IN THE BACKGROUND TO PREVENT UTIL LOCKUP...
- MAY NEED TO THINK ABOUT HOW CONFIGURABLE CONTROLS GET PRESENTED/UPDATED? (CAN IGNORE FOR NOW)
'''

# ---------------------------------------------------------------------------------------------------------------------
#%% Ask user to save


user_confirm_save = cli_confirm("Save model?", debug_mode = True)


'''
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
    
'''

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap
