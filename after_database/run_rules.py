#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Jan 24 15:29:03 2020

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

from local.lib.file_access_utils.rules import build_rule_adb_metadata_report_path
from local.lib.file_access_utils.rules import build_rule_adb_info_report_path
from local.lib.file_access_utils.rules import load_all_rule_configs, save_rule_info

from local.offline_database.file_database import launch_file_db, close_dbs_if_missing_data

from local.configurables.configurable_template import configurable_dot_path

from local.eolib.utils.files import get_total_folder_size
from local.eolib.utils.function_helpers import dynamic_import_from_module
from local.eolib.utils.cli_tools import cli_confirm
from local.eolib.utils.quitters import ide_quit

# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

# .....................................................................................................................
    
def import_rule_class(access_info_dict):
    
    # Pull out info needed to import the rule class
    script_name = access_info_dict["script_name"]
    class_name = access_info_dict["class_name"]
    
    # Programmatically import the target class
    dot_path = configurable_dot_path("after_database", "rules", script_name)
    Imported_Rule_Class = dynamic_import_from_module(dot_path, class_name)
    
    return Imported_Rule_Class

# .....................................................................................................................

def load_all_rules_configured(cameras_folder_path, camera_select, user_select, frame_wh):
    
    # Load all existing rule configurations
    all_rule_configs_dict = load_all_rule_configs(cameras_folder_path, camera_select, user_select, 
                                                  target_rule_type = None)
    
    rule_refs_dict = {}
    for each_rule_name, each_config_dict in all_rule_configs_dict.items():
        
        # Pull out configuration data
        access_info_dict = each_config_dict.get("access_info", None)
        setup_data_dict = each_config_dict.get("setup_data", None)
        
        # Bail if configuration data is missing
        if access_info_dict is None:
            print("",
                  "WARNING:",
                  "  Skipping rule {} since there no access info could be found!".format(each_rule_name),
                  sep = "\n")
            continue
        if setup_data_dict is None:
            print("",
                  "WARNING:",
                  "  Skipping rule {} since there no setup data could be found!".format(each_rule_name),
                  sep = "\n")
            continue
        
        # If we get here, import the rule and configure it
        Imported_Rule_Class = import_rule_class(access_info_dict)
        configured_rule = Imported_Rule_Class(cameras_folder_path, camera_select, user_select, frame_wh)
        configured_rule.reconfigure(setup_data_dict)
        
        # Store the configured rules by name
        rule_refs_dict[each_rule_name] = configured_rule
    
    return rule_refs_dict

# .....................................................................................................................

def delete_existing_rule_data(enable_deletion_prompt, 
                              cameras_folder_path,
                              camera_select, 
                              user_select, 
                              save_and_keep):
    
    # If prompt is skipped and deletion is disabled, don't do anything
    if (not enable_deletion_prompt) and save_and_keep:
        print("", "Existing files are not being deleted!", sep = "\n")
        return
    
    # Build pathing to rule data
    rule_metadata_report_folder = build_rule_adb_metadata_report_path(cameras_folder_path, camera_select, user_select)
    os.makedirs(rule_metadata_report_folder, exist_ok = True)
    
    # Build pathing to rule info data
    rule_info_report_folder = build_rule_adb_info_report_path(cameras_folder_path, camera_select, user_select)
    os.makedirs(rule_info_report_folder, exist_ok = True)
    
    # Check if data already exists
    existing_metadata_file_count, _, total_metadata_file_size_mb, _ = get_total_folder_size(rule_metadata_report_folder)
    existing_info_file_count, _, total_info_file_size_mb, _ = get_total_folder_size(rule_info_report_folder)
    existing_file_count = (existing_metadata_file_count + existing_info_file_count)
    total_file_size_mb = (total_metadata_file_size_mb + total_info_file_size_mb)
    saved_data_exists = (existing_file_count > 0)
    
    # Provide prompt (if enabled) to allow user to avoid deleting existing data
    if saved_data_exists and enable_deletion_prompt:
        confirm_msg = "Saved data already exists! Delete? ({:.1f} MB)".format(total_file_size_mb)
        confirm_data_delete = cli_confirm(confirm_msg, default_response = True)
        if not confirm_data_delete:
            return
    
    # If we get here, delete the files!
    rel_info_path = os.path.relpath(rule_info_report_folder, cameras_folder_path)
    rel_metadata_path = os.path.relpath(rule_metadata_report_folder, cameras_folder_path)
    print("", "Deleting files:",
          "@ {}".format(rel_info_path),
          "@ {}".format(rel_metadata_path),
          sep="\n")
    rmtree(rule_info_report_folder)
    rmtree(rule_metadata_report_folder)

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

cinfo_db, rinfo_db, snap_db, obj_db, _, _, rule_db = \
launch_file_db(cameras_folder_path, camera_select, user_select,
               launch_snapshot_db = True,
               launch_object_db = True,
               launch_classification_db = False,
               launch_summary_db = False,
               launch_rule_db = True)

# Catch missing data
rinfo_db.close()
close_dbs_if_missing_data(snap_db, obj_db)

# Get frame sizing, for rule configuration
frame_wh = cinfo_db.get_snap_frame_wh()


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
#%% Load & configure rules

# Get all configured rules for evaluation
rule_refs_dict = load_all_rules_configured(cameras_folder_path, camera_select, user_select, frame_wh)

# Register rule names with the rule db, so it know about them & where to save results
rule_names_list = list(rule_refs_dict.keys())


# ---------------------------------------------------------------------------------------------------------------------
#%% Clear existing data

# Don't save/clear the rule files unless the user agrees!
saving_enabled = cli_confirm("Save results?", default_response = True)
if saving_enabled:
    enable_deletion = True
    save_and_keep = False
    delete_existing_rule_data(enable_deletion, cameras_folder_path, camera_select, user_select, save_and_keep)


# ---------------------------------------------------------------------------------------------------------------------
#%% Run rules

# Some feedback & timing
total_rules = len(rule_refs_dict)
total_objs = len(obj_id_list)
print("", "Running {} rules on {} objects...".format(total_rules, total_objs), sep = "\n")
t_start = perf_counter()

# Save rule info, if needed
save_rule_info(cameras_folder_path, camera_select, user_select, rule_refs_dict, saving_enabled)

# Create progress bar for better feedback
cli_prog_bar = tqdm(total = total_objs, mininterval = 0.5)

for each_obj_id in obj_id_list:
    
    # Load object metadata
    object_metadata = obj_db.load_metadata_by_id(each_obj_id)
    
    # Loop over alll rules and have them evaluate the current object
    for each_rule_name, each_rule_ref in rule_refs_dict.items():
        
        rule_results_dict, rule_results_list = each_rule_ref.run(each_obj_id, object_metadata, snap_db)
        
        # Save results if needed
        if saving_enabled:
            rule_db.save_entry(each_rule_name, each_rule_ref.get_rule_type(), each_obj_id, 
                               rule_results_dict, rule_results_list)
    
    # Provide some progress feedback (based on objects, not rules!)
    cli_prog_bar.update()

# Shutdown all rules
for _, each_rule_ref in rule_refs_dict.items():
    each_rule_ref.close()

# Clean up progress bar feedback
cli_prog_bar.close()
print("")

# Some timing feedback
t_end = perf_counter()
print_time_taken_ms(t_start, t_end)


# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap



