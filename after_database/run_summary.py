#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Jan 22 16:29:31 2020

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

from local.lib.common.feedback import print_time_taken_ms

from local.lib.ui_utils.cli_selections import Resource_Selector

from local.lib.file_access_utils.structures import create_missing_folder_path, unpack_config_data, unpack_access_info
from local.lib.file_access_utils.summary import build_summary_adb_metadata_report_path
from local.lib.file_access_utils.summary import load_summary_config, save_summary_report_data

from local.offline_database.file_database import launch_file_db, close_dbs_if_missing_data

from local.configurables.configurable_template import configurable_dot_path, jsonify_numpy_data

from local.eolib.utils.files import get_total_folder_size
from local.eolib.utils.function_helpers import dynamic_import_from_module
from local.eolib.utils.cli_tools import cli_confirm
from local.eolib.utils.quitters import ide_quit


# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

# .................................................................................................................
    
def import_summary_class(cameras_folder_path, camera_select):
    
    # Check configuration file to see which script/class to load from & get configuration data
    pathing_args = (cameras_folder_path, camera_select)
    _, config_data_dict = load_summary_config(*pathing_args)
    access_info_dict, setup_data_dict = unpack_config_data(config_data_dict)
    script_name, class_name, _ = unpack_access_info(access_info_dict)
    
    # Programmatically import the target class
    dot_path = configurable_dot_path("after_database", "summary", script_name)
    Imported_Summary_Class = dynamic_import_from_module(dot_path, class_name)
    
    return Imported_Summary_Class, setup_data_dict

# .....................................................................................................................

def delete_existing_summary_data(enable_deletion_prompt,
                                 save_and_keep,
                                 cameras_folder_path,
                                 camera_select):
    
    # If prompt is skipped and deletion is disabled, don't do anything
    if (not enable_deletion_prompt) and save_and_keep:
        print("", "Existing files are not being deleted!", sep = "\n")
        return
    
    # Build pathing to summary data
    summary_data_folder = build_summary_adb_metadata_report_path(cameras_folder_path, camera_select)
    create_missing_folder_path(summary_data_folder)
    
    # Check if data already exists
    existing_file_count, _, total_file_size_mb, _ = get_total_folder_size(summary_data_folder)
    saved_data_exists = (existing_file_count > 0)
    
    # Provide prompt (if enabled) to allow user to avoid deleting existing data
    if saved_data_exists and enable_deletion_prompt:
        confirm_msg = "Saved data already exists! Delete? ({:.1f} MB)".format(total_file_size_mb)
        confirm_data_delete = cli_confirm(confirm_msg, default_response = True)
        if not confirm_data_delete:
            return
    
    # If we get here, delete the files!
    rel_data_folder = os.path.relpath(summary_data_folder, cameras_folder_path)
    print("", "Deleting files:", "@ {}".format(rel_data_folder), sep="\n")
    rmtree(summary_data_folder)

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Select dataset

enable_debug_mode = False

# Create selector to handle camera selection & project pathing
selector = Resource_Selector()
project_root_path, cameras_folder_path = selector.get_cameras_root_pathing()
camera_select, camera_path = selector.camera(debug_mode = enable_debug_mode)


# ---------------------------------------------------------------------------------------------------------------------
#%% Catalog existing data

cinfo_db, snap_db, obj_db, class_db, summary_db = \
launch_file_db(cameras_folder_path, camera_select,
               launch_snapshot_db = True,
               launch_object_db = True,
               launch_classification_db = True,
               launch_summary_db = False)

# Catch missing data
cinfo_db.close()
close_dbs_if_missing_data(snap_db, error_message_if_missing = "No snapshot data in the database!")
close_dbs_if_missing_data(obj_db, error_message_if_missing = "No object data in the database!")


# ---------------------------------------------------------------------------------------------------------------------
#%% Get object IDs fro summary

# Get the maximum range of the data (based on the snapshots, because that's the most we could show)
earliest_datetime, latest_datetime = snap_db.get_bounding_datetimes()
obj_id_list = obj_db.get_object_ids_by_time_range(earliest_datetime, latest_datetime)

# Bail if we have no object data!
no_object_data = (len(obj_id_list) == 0)
if no_object_data:
    print("", "No object data found!", "  Quitting...", "", sep = "\n")
    ide_quit()


# ---------------------------------------------------------------------------------------------------------------------
#%% Load & configure summary

# Programmatically import the target summary class
pathing_args = (cameras_folder_path, camera_select)
Imported_Summary_Class, setup_data_dict = import_summary_class(*pathing_args)
summary_ref = Imported_Summary_Class(*pathing_args)
summary_ref.reconfigure(setup_data_dict)


# ---------------------------------------------------------------------------------------------------------------------
#%% Clear existing data

# Don't update the summary files unless the user agrees!
saving_enabled = cli_confirm("Save results?", default_response = True)
if saving_enabled:
    # Delete existing summary data, if needed
    enable_deletion = True
    save_and_keep = False
    delete_existing_summary_data(enable_deletion, save_and_keep, *pathing_args)

    # Make sure folders for each rule exist for saving
    save_folder_path = build_summary_adb_metadata_report_path(*pathing_args)
    create_missing_folder_path(save_folder_path)


# ---------------------------------------------------------------------------------------------------------------------
#%% Run summary

# Allocate storage for results feedback
class_count_dict = {}
update_class_count = lambda update_class_label: 1 + class_count_dict.get(update_class_label, 0)

# Some feedback & timing
print("", "Running summary...", sep = "\n")
t_start = perf_counter()

# Create progress bar for better feedback
total_objs = len(obj_id_list)
cli_prog_bar = tqdm(total = total_objs, mininterval = 0.5)

for each_obj_id in obj_id_list:
    
    # Run the summary on the selected dataset
    summary_data_dict = summary_ref.run(each_obj_id, obj_db, snap_db)
    
    # Save results, if needed
    if saving_enabled:
        summary_data_dict = jsonify_numpy_data(summary_data_dict)
        save_summary_report_data(*pathing_args, each_obj_id, summary_data_dict)

    # Provide some progress feedback
    cli_prog_bar.update()

# Clean up
summary_ref.close()
cli_prog_bar.close()
print("")

# Some timing feedback
t_end = perf_counter()
print_time_taken_ms(t_start, t_end)


# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap



