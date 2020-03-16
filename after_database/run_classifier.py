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

from shutil import rmtree
from time import perf_counter

from tqdm import tqdm

from local.lib.ui_utils.cli_selections import Resource_Selector

from local.lib.file_access_utils.classifier import build_classifier_adb_metadata_report_path
from local.lib.file_access_utils.classifier import load_classifier_config

from local.offline_database.file_database import launch_file_db, close_dbs_if_missing_data

from local.configurables.configurable_template import configurable_dot_path

from eolib.utils.files import get_total_folder_size
from eolib.utils.function_helpers import dynamic_import_from_module
from eolib.utils.cli_tools import cli_confirm
from eolib.utils.quitters import ide_quit

# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

# .................................................................................................................
    
def import_classifier_class(cameras_folder_path, camera_select, user_select):
    
    # Check configuration file to see which script/class to load from & get configuration data
    pathing_args = (cameras_folder_path, camera_select, user_select)
    _, file_access_dict, setup_data_dict = load_classifier_config(*pathing_args)
    script_name = file_access_dict["script_name"]
    class_name = file_access_dict["class_name"]
    
    # Programmatically import the target class
    dot_path = configurable_dot_path("after_database", "classifier", script_name)
    Imported_Classifier_Class = dynamic_import_from_module(dot_path, class_name)
    
    return Imported_Classifier_Class, setup_data_dict

# .....................................................................................................................

def delete_existing_classification_data(enable_deletion_prompt, 
                                        cameras_folder_path,
                                        camera_select, 
                                        user_select, 
                                        save_and_keep):
    
    # If prompt is skipped and deletion is disabled, don't do anything
    if (not enable_deletion_prompt) and save_and_keep:
        print("", "Existing files are not being deleted!", sep = "\n")
        return
    
    # Build pathing to classification data
    class_data_folder = build_classifier_adb_metadata_report_path(cameras_folder_path, camera_select, user_select)
    os.makedirs(class_data_folder, exist_ok = True)
    
    # Check if data already exists
    existing_file_count, _, total_file_size_mb, _ = get_total_folder_size(class_data_folder)
    saved_data_exists = (existing_file_count > 0)
    
    # Provide prompt (if enabled) to allow user to avoid deleting existing data
    if saved_data_exists and enable_deletion_prompt:
        confirm_msg = "Saved data already exists! Delete? ({:.1f} MB)".format(total_file_size_mb)
        confirm_data_delete = cli_confirm(confirm_msg, default_response = True)
        if not confirm_data_delete:
            return
    
    # If we get here, delete the files!
    rel_data_folder = os.path.relpath(class_data_folder, cameras_folder_path)
    print("", "Deleting files:", "@ {}".format(rel_data_folder), sep="\n")
    rmtree(class_data_folder)

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
close_dbs_if_missing_data(snap_db, obj_db)


# ---------------------------------------------------------------------------------------------------------------------
#%% Get object IDs to classify

# Get the maximum range of the data (based on the snapshots, because that's the most we could show)
earliest_datetime, latest_datetime = snap_db.get_bounding_datetimes()
obj_id_list = obj_db.get_object_ids_by_time_range(earliest_datetime, latest_datetime)

# Bail if we have no object data!
no_object_data = (len(obj_id_list) == 0)
if no_object_data:
    print("", "No object data found!", "  Quitting...", "", sep = "\n")
    ide_quit()


# ---------------------------------------------------------------------------------------------------------------------
#%% Load & configure classifier

# Programmatically import the target classifier class
pathing_args = (cameras_folder_path, camera_select, user_select)
Imported_Classifier_Class, setup_data_dict = import_classifier_class(*pathing_args)
classifier_ref = Imported_Classifier_Class(*pathing_args)
classifier_ref.reconfigure(setup_data_dict)


# ---------------------------------------------------------------------------------------------------------------------
#%% Clear existing data

# Don't update the classification file unless the user agrees!
saving_enabled = cli_confirm("Save results?", default_response = True)
if saving_enabled:
    # Delete existing classification data, if needed
    enable_deletion = True
    save_and_keep = False
    delete_existing_classification_data(enable_deletion, cameras_folder_path, camera_select, user_select, save_and_keep)


# ---------------------------------------------------------------------------------------------------------------------
#%% Run classification

# Allocate storage for results feedback
class_count_dict = {}
update_class_count = lambda update_class_label: 1 + class_count_dict.get(update_class_label, 0)

# Some feedback & timing
print("", "Running classification...", sep = "\n")
t_start = perf_counter()

# Create progress bar for better feedback
total_objs = len(obj_id_list)
cli_prog_bar = tqdm(total = total_objs, mininterval = 0.5)

for each_obj_id in obj_id_list:
    
    # Run the classifier on the selected dataset
    class_label, score_pct, subclass, attributes_dict = classifier_ref.run(each_obj_id, obj_db, snap_db)
    
    # Keep track of class counts for feedback
    class_count_dict[class_label] = update_class_count(class_label)
    
    # Save results, if needed
    if saving_enabled:
        class_db.save_entry(each_obj_id, class_label, score_pct,subclass, attributes_dict)

    # Provide some progress feedback
    cli_prog_bar.update()

# Clean up
classifier_ref.close()
cli_prog_bar.close()
print("")

# Some timing feedback
t_end = perf_counter()
total_processing_time_sec = (t_end - t_start)
print("", "Finished! Took {:.1f} seconds".format(total_processing_time_sec), sep = "\n")

# Some feedback about class counts
longest_class_name = max([len(each_label) for each_label in class_count_dict.keys()])
print("", 
      "Classification results:", 
      *["  {}: {}".format(each_label.rjust(longest_class_name), each_count) \
        for each_label, each_count in class_count_dict.items()],
      "", sep = "\n")


# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap


