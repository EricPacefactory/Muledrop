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

from local.lib.file_access_utils.configurables import unpack_config_data, unpack_access_info
from local.lib.file_access_utils.after_database import build_after_database_configs_folder_path
from local.lib.file_access_utils.reporting import build_after_database_report_path
from local.lib.file_access_utils.json_read_write import load_config_json, save_config_json
from local.lib.file_access_utils.metadata_read_write import save_jsongz_metadata

from local.eolib.utils.files import get_file_list
from local.eolib.utils.cli_tools import cli_confirm, cli_select_from_list, cli_prompt_with_defaults


# ---------------------------------------------------------------------------------------------------------------------
#%% General Pathing functions

# .....................................................................................................................

def build_rule_config_folder_path(location_select_folder_path, camera_select, *path_joins):
    return build_after_database_configs_folder_path(location_select_folder_path, camera_select, "rules", *path_joins)
    
# .....................................................................................................................

def build_rule_config_file_path(location_select_folder_path, camera_select, rule_name):
    save_name = create_rule_config_file_name(rule_name)
    return build_rule_config_folder_path(location_select_folder_path, camera_select, save_name)

# .....................................................................................................................

def build_rule_adb_info_report_path(location_select_folder_path, camera_select, *path_joins):
    return build_after_database_report_path(location_select_folder_path, camera_select, "rule_info", *path_joins)

# .....................................................................................................................

def build_rule_adb_metadata_report_path(location_select_folder_path, camera_select, *path_joins):
    return build_after_database_report_path(location_select_folder_path, camera_select, "rules", *path_joins)

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% File naming functions

# .....................................................................................................................

def create_rule_config_file_name(rule_name):
    return "{}.json".format(create_safe_rule_name(rule_name))

# .....................................................................................................................

def create_safe_rule_name(rule_name):
    return rule_name.strip().replace(" ", "_")

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Data access functions

# .....................................................................................................................
    
def save_rule_info(location_select_folder_path, camera_select, rule_refs_dict, saving_enabled):
    
    # Don't do anything if saving isn't enabled
    if not saving_enabled:
        return
    
    # Save the rule info for every rule
    for each_rule_name, each_rule_ref in rule_refs_dict.items():
        
        # Get rule info to save
        rule_info_dict = each_rule_ref.get_rule_info(each_rule_name)
        
        # Get pathing to where to save each rule's info file & save it!
        save_path = build_rule_adb_info_report_path(location_select_folder_path, camera_select)
        save_jsongz_metadata(save_path, rule_info_dict)
    
    return

# .....................................................................................................................

def get_rule_type(access_info_dict):
    
    ''' Helper function which determines the rule type (i.e. script name) from a given rule config '''
    
    # Pull out the script name, and be sure to remove any .py extensions (just in case)
    script_name, _ = unpack_access_info(access_info_dict)
    clean_rule_type, _ = os.path.splitext(script_name)
    
    return clean_rule_type

# .....................................................................................................................

def save_rule_report_data(location_select_folder_path, camera_select, rule_name,
                          rule_type, object_full_id, rule_results_dict, rule_results_list):
    
    ''' Function which saves rule reporting data (as opposed to config data!) '''
    
    # Build pathing to save
    save_file_path = build_rule_adb_metadata_report_path(location_select_folder_path, camera_select, rule_name)
    
    # Bundle data and save
    save_data = new_rule_report_entry(object_full_id, rule_type, rule_results_dict, rule_results_list)
    save_jsongz_metadata(save_file_path, save_data)
    
# .....................................................................................................................
    
def new_rule_report_entry(object_full_id, rule_type, rule_results_dict, rule_results_list):
    
    ''' Helper function for creating properly formatted evalutaed rule entries '''
    rule_break_timing_ems = None
    return {"_id": object_full_id,
            "full_id": object_full_id,
            "rule_type": rule_type,
            "num_violations": len(rule_results_list),
            "rule_results_dict": rule_results_dict,
            "rule_results_list": rule_results_list}

# .....................................................................................................................
# .....................................................................................................................


# .....................................................................................................................
#%% Configuration Access functions

# .....................................................................................................................

def path_to_configuration_file(rule_name, configurable_ref):
    
    ''' 
    Function which generates the path to a configuration path,
    given a rule name and configurable object as an input 
    '''
    
    # Get major pathing info from the configurable
    location_select_folder_path = configurable_ref.location_select_folder_path
    camera_select = configurable_ref.camera_select
    
    return build_rule_config_file_path(location_select_folder_path, camera_select, rule_name)

# .....................................................................................................................

def load_all_rule_configs(location_select_folder_path, camera_select, target_rule_type = None):
    
    # First get pathing to config folder, where all rule configs live
    rule_config_folder_path = build_rule_config_folder_path(location_select_folder_path, camera_select)
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
        rule_name, _ = os.path.splitext(each_file_name)
        config_file_path, config_data_dict = load_rule_config(location_select_folder_path,
                                                              camera_select,
                                                              rule_name)
        
        # Get the rule type, in case we need to filter things down
        access_info_dict, setup_data_dict = unpack_config_data(config_data_dict)
        rule_type = get_rule_type(access_info_dict)
        
        # Skip non-target rule types, if needed
        if check_target_rule_type and (rule_type != target_rule_type):
            continue
        
        # If we get this far, store the rule configuration data!
        rule_configs_dict[rule_name] = config_data_dict
    
    return rule_configs_dict

# .................................................................................................................
    
def load_rule_config(location_select_folder_path, camera_select, rule_name):
    
    '''  Function which loads configuration files for individual rules '''
    
    # Get path to the config file
    config_file_path = build_rule_config_file_path(location_select_folder_path, camera_select, rule_name)
    
    # Load json data and split into file access info & setup configuration data
    config_data_dict = load_config_json(config_file_path)
    
    return config_file_path, config_data_dict

# .....................................................................................................................

def save_rule_config(rule_name, configurable_ref, file_dunder):
    
    # Get file access info & current configuration data for saving
    save_data_dict = configurable_ref.get_save_data_dict(file_dunder)
    
    # Build pathing to existing configuration file
    save_path = path_to_configuration_file(rule_name, configurable_ref)
    save_config_json(save_path, save_data_dict)
    relative_save_path = os.path.relpath(save_path, configurable_ref.location_select_folder_path)
    
    return save_path, relative_save_path

# .....................................................................................................................
# .....................................................................................................................


# .....................................................................................................................
#%% CLI Functions

# .....................................................................................................................

def select_rule_to_load(rule_ref):
    
    # Get major pathing info from the configurable
    location_select_folder_path = rule_ref.location_select_folder_path
    camera_select = rule_ref.camera_select
    
    # Get the rule type, so we only try to load matching types
    rule_type = rule_ref.get_rule_type()
    
    # Get list of all rule configs
    all_rule_configs = load_all_rule_configs(location_select_folder_path, camera_select, target_rule_type = rule_type)
    
    # Provide prompt to load existing rule, or create a new one
    creation_option = "Create new rule"
    rule_load_list = [creation_option, *all_rule_configs.keys()]
    select_idx, loaded_rule_name = cli_select_from_list(rule_load_list,
                                                        "Select rule to load:",
                                                        default_selection = creation_option,
                                                        zero_indexed = True)
    
    # Grab the correct setup data, based on the user config selection
    load_from_existing_config = (select_idx > 0)
    loaded_setup_data = {}
    if load_from_existing_config:
        loaded_rule_config_data = all_rule_configs[loaded_rule_name]["config_data_dict"]
        _, loaded_setup_data = unpack_config_data(loaded_rule_config_data)
    
    return load_from_existing_config, loaded_rule_name, loaded_setup_data

# .....................................................................................................................

def prompt_for_rule_name(load_from_existing, loaded_rule_name):
    
    ''' 
    Function which provides a cli prompt to have a user enter a rule name for a new rule.
    The prompt will only occur if a new rule is being created,
    as opposed to loading a rule which already has a name
    '''
    
    # Decide if we need to ask the user for the rule name, or use the loading selection
    creating_new_rule = (not load_from_existing)
    save_rule_name = loaded_rule_name
    if creating_new_rule:
        save_rule_name = cli_prompt_with_defaults("Enter rule name: ", return_type = str)
    
    return save_rule_name

# .....................................................................................................................

def cli_save_rule(rule_ref, load_from_existing_config, loaded_rule_name, *, file_dunder):
    
    '''
    Function which provides a prompt to have a user confirm saving a rule configuration.
    Handles rule name input (if needed)
    Also handles the actual saving I/O
    '''
    
    # Allocate output
    save_rule_name = None
    
    # Ask user if they would like to save
    user_confirm_save = cli_confirm("Save rule config?", default_response = False)
    if user_confirm_save:
        save_rule_name = prompt_for_rule_name(load_from_existing_config, loaded_rule_name)
        _, rel_save_path = save_rule_config(save_rule_name, rule_ref, __file__)
        
        # Print out additional indicator if the rule was saved for the first time
        if (not load_from_existing_config):
            print("", "Saved!", "@ {}".format(rel_save_path), sep = "\n")
        
    return save_rule_name

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap

