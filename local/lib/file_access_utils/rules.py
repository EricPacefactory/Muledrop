#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Jan 27 11:39:49 2020

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

from local.lib.file_access_utils.after_database import build_after_database_configs_folder_path
from local.lib.file_access_utils.reporting import build_after_database_report_path

from eolib.utils.read_write import load_json, save_json
from eolib.utils.files import get_file_list

# ---------------------------------------------------------------------------------------------------------------------
#%% General Pathing functions

# .....................................................................................................................

def build_rule_config_folder_path(cameras_folder_path, camera_select, user_select, *path_joins):
    return build_after_database_configs_folder_path(cameras_folder_path, camera_select, user_select,
                                                    "rules", *path_joins)
    
# .....................................................................................................................

def build_rule_config_file_path(cameras_folder_path, camera_select, user_select, rule_name, *path_joins):
    rule_save_name = create_rule_save_name(rule_name, ".json")
    return build_rule_config_folder_path(cameras_folder_path, camera_select, user_select, rule_save_name)

# .....................................................................................................................

def build_rule_adb_metadata_report_path(cameras_folder_path, camera_select, user_select, rule_name, *path_joins):
    rule_name_no_spaces = create_rule_save_name(rule_name)
    return build_after_database_report_path(cameras_folder_path, camera_select, user_select, rule_name_no_spaces)

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% File naming functions

# .....................................................................................................................

def create_rule_report_file_name(object_full_id):
    return "rule-{}.json.gz".format(object_full_id)

# .....................................................................................................................

def create_rule_save_name(rule_name, save_extension = None):
    
    ''' Helper function for generating (consistent) save names for a given rule name '''
    
    # Create proper extension add-on, if needed
    add_ext = ""
    if save_extension is not None:
        has_leading_dot = (save_extension[0] == ".")
        add_ext = save_extension if has_leading_dot else ("." + save_extension)
    
    # Build save name by removing spaces and prepending 'rule-' to the rule name. Also add an extension if provided
    rule_name_no_spaces = rule_name.replace(" ", "_")
    name_missing_rule_prepend = (rule_name_no_spaces[0:4] != "rule")
    name_prepend = "rule-" if name_missing_rule_prepend else ""
    rule_save_name = "{}{}{}".format(name_prepend, rule_name_no_spaces, add_ext)
    
    return rule_save_name

# .....................................................................................................................

def extract_name_from_rule_save_name(rule_save_name):
    
    ''' Helper function which restores the proper rule name from a rule_save_name format '''
    
    # Remove any directory pathing and file extensions, if present
    file_name = os.path.basename(rule_save_name)
    file_name_only, _ = os.path.splitext(file_name)
    
    # Remove prepended 'rule-' component, if present
    cleaned_rule_name = file_name_only
    has_prepended_rule = (file_name_only[0:5] == "rule-")
    if has_prepended_rule:
        cleaned_rule_name = cleaned_rule_name[5:]
    
    return cleaned_rule_name

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Data access functions

# .....................................................................................................................

def get_rule_type(access_info_dict):
    
    ''' Helper function which determines the rule type (i.e. script name) from a given rule config '''
    
    # Pull out the script name, and be sure to remove any .py extensions (just in case)
    rule_type = access_info_dict["script_name"]
    clean_rule_type, _ = os.path.splitext(rule_type)
    
    return clean_rule_type

# .....................................................................................................................

def save_rule_report_data(cameras_folder_path, camera_select, user_select, rule_name, 
                          rule_type, object_full_id, rule_data_dict):
    
    ''' Function which saves rule reporting data (as opposed to config data!) '''
    
    # Build pathing to save
    save_file_name = create_rule_report_file_name(object_full_id)
    save_folder_path = build_rule_adb_metadata_report_path(cameras_folder_path, camera_select, user_select, rule_name)
    save_file_path = os.path.join(save_folder_path, save_file_name)
    
    # Bundle data and save
    save_data = new_rule_report_entry(object_full_id, rule_type, rule_data_dict)
    save_json(save_file_path, save_data, use_gzip = True, create_missing_folder_path = True)
    
# .....................................................................................................................
    
def new_rule_report_entry(object_full_id, rule_type, rule_data_dict):
    
    ''' Helper function for creating properly formatted evalutaed rule entries '''
    
    return {"full_id": object_full_id, "rule_type": rule_type, **rule_data_dict}

# .................................................................................................................
    
def load_rule_config(cameras_folder_path, camera_select, user_select, rule_name):
    
    '''  Function which loads configuration files for individual rules '''
    
    # Get path to the config file
    config_file_path = build_rule_config_file_path(cameras_folder_path, camera_select, user_select, rule_name)
    
    # Load json data and split into file access info & setup configuration data
    config_dict = load_json(config_file_path)
    access_info_dict = config_dict["access_info"]
    setup_data_dict = config_dict["setup_data"]
    
    return config_file_path, access_info_dict, setup_data_dict

# .....................................................................................................................

def load_all_rule_configs(cameras_folder_path, camera_select, user_select, target_rule_type = None):
    
    # First get pathing to config folder, where all rule configs live
    rule_config_folder_path = build_rule_config_folder_path(cameras_folder_path, camera_select, user_select)
    all_rule_config_file_names = get_file_list(rule_config_folder_path, 
                                               show_hidden_files = False, 
                                               create_missing_folder = True, 
                                               return_full_path = False, 
                                               sort_list = False, 
                                               allowable_exts_list=[".json"])
    
    # Load each config
    check_target_rule_type = (target_rule_type is not None)
    rule_configs_dict = {}
    for each_file_name in all_rule_config_file_names:
        
        # Get the rule name from the file, and load it's data
        rule_name = extract_name_from_rule_save_name(each_file_name)
        config_file_path, access_info_dict, setup_data_dict = load_rule_config(cameras_folder_path, 
                                                                               camera_select, 
                                                                               user_select, 
                                                                               rule_name)
        
        # Get the rule type, in case we need to filter things down
        rule_type = get_rule_type(access_info_dict)
        
        # Skip non-target rule types, if needed
        if check_target_rule_type and (rule_type != target_rule_type):
            continue
        
        # If we get this far, store the rule configuration data!
        rule_configs_dict[rule_name] = {"config_file_path": config_file_path,
                                        "access_info": access_info_dict,
                                        "setup_data": setup_data_dict}
    
    return rule_configs_dict

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap
