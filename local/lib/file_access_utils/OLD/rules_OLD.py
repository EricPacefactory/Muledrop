#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat May 11 11:28:07 2019

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

from local.lib.file_access_utils.shared import build_task_folder_path, copy_from_defaults, full_replace_save

from local.lib.file_access_utils.reporting import build_metadata_report_path

# ---------------------------------------------------------------------------------------------------------------------
#%% Pathing functions

# .....................................................................................................................

def build_rule_folder_path(cameras_folder, camera_select, user_select, task_select):
    return build_task_folder_path(cameras_folder, camera_select, user_select, task_select, "rules")

# .....................................................................................................................

def build_rule_config_file_path(cameras_folder, camera_select, user_select, task_select, rule_name):
    
    rule_folder_path = build_rule_folder_path(cameras_folder, camera_select, user_select, task_select)
    config_file_name = "".join([rule_name, ".json"])
    
    return os.path.join(rule_folder_path, config_file_name)

# .....................................................................................................................

def build_rule_metadata_folder_path(cameras_folder, camera_select, user_select, task_select,
                                    rule_name, rule_type):
    
    rule_container_folder_name = "rules-({})".format(task_select)
    rule_folder_name = "{}-({})".format(rule_name, rule_type)
    
    return build_metadata_report_path(cameras_folder, camera_select, user_select, 
                                      rule_container_folder_name, rule_folder_name)

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Config functions

# .....................................................................................................................

def create_default_rule_configs(project_root_path, task_folder_path):
    
    # Build pathing to where the rule configs are located
    copy_target_folder = os.path.join(task_folder_path, "rules")
    
    # Only copy defaults if no files are present
    file_list = os.listdir(copy_target_folder)
    no_rule_configs = len(file_list) == 0
    
    # Pull default json config files out of the defaults folder, and copy in to the target task path
    if no_rule_configs:
        copy_from_defaults(project_root_path, 
                           target_defaults_folder = "rules",
                           copy_to_path = copy_target_folder)
        
# .....................................................................................................................
    
def save_rule_config(cameras_folder, camera_select, user_select, task_select,
                     rule_name, script_name, class_name, config_data, confirm_save = True):
    
    # Build save pathing
    config_file_path = build_rule_config_file_path(cameras_folder, camera_select, user_select, task_select, rule_name)
    
    # Build the data structure for the rule config data
    save_data = {"access_info": {"script_name": script_name,
                                 "class_name": class_name},
                 "setup_data": config_data}
    
    # Fully overwrite the existing config, if it already exists
    if confirm_save:
        full_replace_save(config_file_path, save_data)
    
    return config_file_path, save_data

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap
