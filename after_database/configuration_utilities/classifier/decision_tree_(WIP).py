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

from sklearn.model_selection import train_test_split

from local.lib.ui_utils.cli_selections import Resource_Selector


from local.configurables.after_database.classifier.decisiontree_classifier import Classifier_Stage
from local.configurables.after_database.classifier.decisiontree_classifier import save_classifier_resources
from local.configurables.after_database.classifier.decisiontree_classifier import load_classifier_resources
from local.configurables.after_database.classifier.decisiontree_classifier import sample_data_from_object

from local.offline_database.file_database import launch_file_db, close_dbs_if_missing_data

from local.offline_database.object_reconstruction import Hover_Mapping
from local.offline_database.object_reconstruction import create_trail_frame_from_object_reconstruction

from local.offline_database.snapshot_reconstruction import median_background_from_snapshots

from local.lib.file_access_utils.classifier import load_matching_config
from local.lib.file_access_utils.classifier import save_classifier_config
from local.lib.file_access_utils.classifier import get_highest_score_label

from local.lib.file_access_utils.supervised_labels import load_all_supervised_labels
from local.lib.file_access_utils.supervised_labels import check_supervised_labels_exist
from local.lib.file_access_utils.supervised_labels import get_svlabel_topclass_label, get_labels_to_skip

from local.lib.ui_utils.local_ui.windows_base import Simple_Window

from local.eolib.utils.quitters import ide_quit
from local.eolib.utils.cli_tools import Datetime_Input_Parser as DTIP
from local.eolib.utils.cli_tools import cli_confirm, cli_select_from_list


# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes


# ---------------------------------------------------------------------------------------------------------------------
#%% Define helper functions

def check_for_existing_resources(cameras_folder_path, camera_select):
    
    # Try to load existing classifier resources
    _, loaded_lut = load_classifier_resources(cameras_folder_path, camera_select, error_if_missing = False)
    resources_exist = (loaded_lut is not None)
    
    return resources_exist

# ---------------------------------------------------------------------------------------------------------------------
#%% Define training functions

# .....................................................................................................................

def generate_training_data(object_list, supervised_obj_labels_dict, 
                           num_subsamples = 10, 
                           start_inset = 0.02,
                           end_inset = 0.02,
                           print_feedback = True):
    
    # Initialize output. Should contain keys for each object id, storing all input data in lists
    obj_data_lists_dict = {}
    
    # Get skippable labels, which aren't meant for training
    skip_labels_set = get_labels_to_skip()
    
    # Start timing and provide feedback
    t1 = perf_counter()
    if print_feedback:
        print("", "Generating training data tables...", sep = "\n")
    
    # Loop over all object reconstructions
    for each_obj_recon in object_list:
        
        # Get the object id info & target class
        each_obj_id = each_obj_recon.full_id
        supervised_label = get_svlabel_topclass_label(supervised_obj_labels_dict, each_obj_id)
        
        # Skip certain entries
        if supervised_label in skip_labels_set:
            print("Skipped object {}, flagged as '{}'".format(each_obj_id, supervised_label))
            continue
        
        # Get object data samples
        data_order, obj_data_list = sample_data_from_object(each_obj_recon, num_subsamples, start_inset, end_inset)
        
        # Handle case where object doesn't have enough samples
        not_enough_data = (len(obj_data_list) < num_subsamples)
        if not_enough_data:
            print("DEBUG: Skipped object {} ({}), not enough sample data!".format(each_obj_id, supervised_label))
            continue
        
        # Construct target output data (as a list, corresponding to the subsampled data)
        target_output_list = [supervised_label] * len(obj_data_list)
        
        # Bundle everything together for convenience
        obj_data_lists_dict[each_obj_id] = {"input": obj_data_list,
                                            "output": target_output_list}
    
    # End timing and provide final feedback
    t2 = perf_counter()
    if print_feedback:
        print("  Done! Took {:.0f} ms".format(1000 * (t2 - t1)))
    
    return data_order, obj_data_lists_dict

# .....................................................................................................................

def creating_training_arrays(training_data_dict):
    
    '''
    Takes an input dictionary with keys representing object ids, values store another dictionary,
    which has keys 'input', 'output' and 'headings' 
    the 'headings' key and data are just for documenting the data, not important
    the 'input' key represents lists of lists of data to be used as input for training
    the 'output' key represents the target output and holds a string representing the target class
    
    This function needs to output the input data, for all objects, as one large array.
    It must also output a single large array which contains the corresponding target output data (mapped to integers ?)
    '''
    
    # Storage for handling the mapping between target labels & integer/id representations
    target_label_to_id_dict = {}
    
    # Storage for entire input/output data
    full_input_data_list = []
    full_output_id_list = []
    
    for each_obj_id, each_data_dict in training_data_dict.items():
        
        # Extract the relevant training data
        input_data_lists = each_data_dict["input"]
        output_label_list = each_data_dict["output"]
        
        # Convert output labels to ids
        output_id_list = []
        for each_output_entry in output_label_list:
            
            # Add output entries to the label-to-id mapping dictionary
            if each_output_entry not in target_label_to_id_dict.keys():
                num_current_labels = len(target_label_to_id_dict)
                target_label_to_id_dict[each_output_entry] = 1 + num_current_labels
                
            # Build the output id list
            id_of_label = target_label_to_id_dict[each_output_entry]
            output_id_list.append(id_of_label)
        
        # Add entries to the 'full' outputs
        full_input_data_list += input_data_lists
        full_output_id_list += output_id_list
        
    # Convert to arrays for faster processing
    input_data_array = np.float32(full_input_data_list)
    output_data_array = np.int32(full_output_id_list)
        
    return input_data_array, output_data_array, target_label_to_id_dict

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Select camera/user

enable_debug_mode = False

# Create selector so we can access existing report data
selector = Resource_Selector()
project_root_path, cameras_folder_path = selector.get_project_pathing()

# Select the camera/user to show data for (needs to have saved report data already!)
camera_select, camera_path = selector.camera(debug_mode=enable_debug_mode)
user_select, _ = selector.user(camera_select, debug_mode=enable_debug_mode)

# Bundle pathing args for convenience
pathing_args = (cameras_folder_path, camera_select, user_select)


# ---------------------------------------------------------------------------------------------------------------------
#%% Check for existing resources

# Check if existing decision tree resources exist
resources_already_exist = check_for_existing_resources(cameras_folder_path, camera_select)

# Print some feedback about finding resources
print("",
      "Existing classifier found!" if resources_already_exist else "No existing classifier found!",
      "", sep = "\n")

# Prompt use to choose between using existing or training a new classifier, if resources already exist
if resources_already_exist:    
    print("", "DEBUG: HACKY IMPLEMENTATION. Need to fix...", "", sep = "\n")
    use_existing_prompt = "Use existing classifier"
    train_new_prompt = "Train new classifier"
    selection_list = [use_existing_prompt, train_new_prompt]
    selected_idx, selected_entry = cli_select_from_list(selection_list, 
                                                        "What would you like to do?", 
                                                        default_selection = use_existing_prompt)
    
    # If use existing was chosen, prompt to save classifier 'config' and then we're done!
    if selected_entry == use_existing_prompt:
        user_confirm_save = cli_confirm("Save decision tree classifier config?", default_response = False)
        if user_confirm_save:            
            # Update the classifier config for the selected camera/user
            classifier_ref = Classifier_Stage(cameras_folder_path, camera_select, user_select)
            save_classifier_config(classifier_ref, __file__)
        ide_quit("Saved classifier config. Done!" if user_confirm_save else "Save cancelled...")


# ---------------------------------------------------------------------------------------------------------------------
#%% Check for supervised label data

sv_labels_exist = check_supervised_labels_exist(cameras_folder_path, camera_select, user_select)
if not sv_labels_exist:
    print("", 
          "No supervised labels were found for:",
          "  camera: {}".format(camera_select),
          "    user: {}".format(user_select),
          "",
          "Cannot train decision tree without labeled data!",
          "  -> Please use the supervised labeling tool to generate labeled data",
          sep = "\n")
    ide_quit()


# ---------------------------------------------------------------------------------------------------------------------
#%% Catalog existing data

cinfo_db, snap_db, obj_db, class_db, summary_db = \
launch_file_db(cameras_folder_path, camera_select, user_select,
               launch_snapshot_db = True,
               launch_object_db = True,
               launch_classification_db = True,
               launch_summary_db = False)

# Catch missing data
cinfo_db.close()
close_dbs_if_missing_data(snap_db, error_message_if_missing = "No snapshot data in the database!")


# ---------------------------------------------------------------------------------------------------------------------
#%% Ask user for time window

# Get the maximum range of the data (based on the snapshots, because all we can show)
earliest_datetime, latest_datetime = snap_db.get_bounding_datetimes()

# Ask the user for the range of datetimes to use for selecting data
user_start_dt, user_end_dt = DTIP.cli_prompt_start_end_datetimes(earliest_datetime, latest_datetime,
                                                                 print_help_before_prompt = False,
                                                                 debug_mode = enable_debug_mode)

# Provide feedback about the selected time range
DTIP.print_start_end_time_range(user_start_dt, user_end_dt)


# ---------------------------------------------------------------------------------------------------------------------
#%% Create background frame

# Ask database for several snapshot images, so we can 'average' them to make a background frame for display
bg_frame = median_background_from_snapshots(snap_db, user_start_dt, user_end_dt, 10)
frame_height, frame_width = bg_frame.shape[0:2]
frame_wh = (frame_width, frame_height)


# ---------------------------------------------------------------------------------------------------------------------
#%% Set up the classifier

# Load configurable class for this config utility
classifier_ref = Classifier_Stage(cameras_folder_path, camera_select, user_select)

# Load existing config settings, if available
initial_setup_data_dict = load_matching_config(classifier_ref)
classifier_ref.reconfigure(initial_setup_data_dict)


# ---------------------------------------------------------------------------------------------------------------------
#%% Load object data

# Get object ids from the server
obj_id_list = obj_db.get_object_ids_by_time_range(user_start_dt, user_end_dt)

# Load supervised data for each object
sv_labels_dict = load_all_supervised_labels(*pathing_args, obj_id_list)

# Use classifier to generate object data for training, to match real-use case
obj_list = []
for each_obj_id in obj_id_list:
    obj_recon = classifier_ref.request_object_data(each_obj_id, obj_db)
    obj_list.append(obj_recon)



# ---------------------------------------------------------------------------------------------------------------------
#%% Generate training data

# Build training data set
data_column_names_list, training_data_dict = generate_training_data(obj_list, sv_labels_dict, num_subsamples = 10)
input_data_array, output_data_array, label_to_id_dict = creating_training_arrays(training_data_dict)

# Split data so we can running training and check accuracy
X_train, X_test, y_train, y_test = train_test_split(input_data_array, output_data_array, test_size=0.20)

# Train classifier!
classifier_ref.train(data_column_names_list, label_to_id_dict, X_train, y_train)


# ---------------------------------------------------------------------------------------------------------------------
#%% Apply classifier to all data for visualization

# Get visualization colors
_, _, all_label_colors_dict = class_db.get_label_color_luts()
missing_label_color = (255, 255, 255)

# Storage for accuracy results
skip_labels_set = get_labels_to_skip()
total_correct = 0
total_error = 0

print("DEBUG: NEED TO FIX FRAME SCALING HACK")

# Classify each object
objclass_dict = {each_label: {} for each_label in label_to_id_dict.keys()}
for each_obj_ref in obj_list:
    
    # Get object id for lookups
    each_obj_id = each_obj_ref.full_id
    
    # Get classifier predictions
    topclass_dict, subclass_dict, attributes_dict = classifier_ref.classify_one_object(each_obj_ref, snap_db)
    
    # Generate single label predictions
    predicted_topclass, _ = get_highest_score_label(topclass_dict)
    predicted_subclass, _ = get_highest_score_label(subclass_dict)
    actual_topclass = get_svlabel_topclass_label(sv_labels_dict, each_obj_id)
    
    if actual_topclass not in skip_labels_set:
        correct_prediction = (predicted_topclass == actual_topclass)
        total_correct += int(correct_prediction)
        total_error += 1 - int(correct_prediction)
        
        if not correct_prediction:
            print("Error - Predicted {}, actually {}".format(predicted_topclass, actual_topclass))
    
    # Update the object reconstruction so that it is colored correctly
    object_label_color = all_label_colors_dict.get(predicted_topclass, missing_label_color)
    each_obj_ref.set_classification(predicted_topclass, predicted_subclass, attributes_dict)
    each_obj_ref.set_graphics(object_label_color)
    
    # HACK
    each_obj_ref.frame_wh = frame_wh
    each_obj_ref.frame_scaling_array = np.float32(frame_wh) - np.float32((1, 1))
    
    # Finally, store the results
    if predicted_topclass not in objclass_dict:
        objclass_dict[predicted_topclass] = {}
    objclass_dict[predicted_topclass][each_obj_id] = each_obj_ref


# Some feedback about accuracy
total_classified = (total_correct + total_error)
print("",
      "Total objects classified: {}".format(total_classified),
      "  Total correct: {} ({:.0f}%)".format(total_correct, 100 * total_correct / total_classified),
      "   Total errors: {} ({:.0f}%)".format(total_error, 100 * total_error / total_classified),
      sep = "\n")

# Generate trail hover mapping, for quicker mouse-to-trail lookup
hover_map = Hover_Mapping(objclass_dict)


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
#%% Save classifier

user_confirm_save = cli_confirm("Save decision tree classifier config?", default_response = False)
if user_confirm_save:
    
    # Save model/lut data
    save_classifier_resources(classifier_ref)
    
    # Update the classifier config for the selected camera/user
    save_classifier_config(classifier_ref, __file__)


# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap

print("DEBUG: D-TREE UNFINISHED WORK! LEFT OFF HERE. See todo list...")
'''
STOPPED HERE
- NEED TO CLEAN UP LOADING PROCESS (AND NOT CHECK FOR EXISTING?)
    - NEED TO ADD CHECK FOR EXISTING RESOURCES
    - IF MODEL ALREADY EXISTS, PROMPT TO SAVE CLASSIFIER CONFIG ONLY, DON'T TRAIN NEW MODEL
- UPDATE TRAINING DATA TO USE ALL SAMPLES
- INCLUDE CALCULATIONS FOR AVG SPEED, OBJ LIFETIME, RELATIVE LIFE POSITION OF EACH SAMPLE, TOTAL TRAVEL DIST ETC.
- UPDATE TRAINING TO USE WEIGHTING TO BALANCE (NON-RESERVED) CLASS LABEL FREQUENCIES!
- NEED TO ADD METHOD FOR SELECTING WHAT DATA GETS USED IN TREE (IDEALLY WITH TOGGLE CONTROLS!)
- NEED TO ADD ACCURACY REPORT -> Need to add breakdown by class (e.g. confusion matrix)
- NEED TO CLEAN UP TRAINING DATA CONSTRUCTION -> Some parts need to be sharable between other systems (esp. notrain)
- NEED TO CLEAN UP FRAME SIZING STUPIDITY
    - really need to redo how classifier + coloring is handled on objects...
    - also need to consider switching to objclass_dict as default way to do things
        - would need to return other dicts tho (an id order dict + id-to-label-dict)
- NEED TO TEST OUT 'RUN_CLASSIFIER' AFTER SAVING!
- NEED TO MAKE RANDOM FOREST VERSION OF ALL THIS!
- THEN THINK ABOUT GETTING ALL THIS WORKING 'ONLINE' WITH REAL DATABASE AND SERVER...
'''
