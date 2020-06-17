#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Jan 22 16:33:20 2020

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
from local.lib.file_access_utils.json_read_write import load_config_json
from local.lib.file_access_utils.metadata_read_write import save_jsongz_metadata


# ---------------------------------------------------------------------------------------------------------------------
#%% General Pathing functions

# .....................................................................................................................

def build_summary_config_path(cameras_folder_path, camera_select, user_select, *path_joins):
    return build_after_database_configs_folder_path(cameras_folder_path, camera_select, user_select, "summary.json")

# .....................................................................................................................

def build_summary_adb_metadata_report_path(cameras_folder_path, camera_select, user_select, *path_joins):
    return build_after_database_report_path(cameras_folder_path, camera_select, user_select, "summary")

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Data access functions

# .....................................................................................................................

def save_summary_report_data(cameras_folder_path, camera_select, user_select, object_full_id, summary_data_dict):
    
    # Build pathing to save
    save_folder_path = build_summary_adb_metadata_report_path(cameras_folder_path, camera_select, user_select)
    
    # Bundle data and save
    save_data = new_summary_report_entry(object_full_id, summary_data_dict)
    save_jsongz_metadata(save_folder_path, save_data, json_double_precision = 10)
    
# .....................................................................................................................
    
def new_summary_report_entry(object_full_id, summary_data_dict):
    
    ''' Helper function for creating properly formatted summary entries '''
    
    return {"_id": object_full_id, "full_id": object_full_id, **summary_data_dict}

# .................................................................................................................
    
def load_summary_config(cameras_folder_path, camera_select, user_select):
    
    ''' 
    Function which loads configuration files for a summary
    '''
    
    # Get path to the config file
    config_file_path = build_summary_config_path(cameras_folder_path, camera_select, user_select)
    
    # Load json data and split into file access info & setup configuration data
    config_dict = load_config_json(config_file_path)
    access_info_dict = config_dict["access_info"]
    setup_data_dict = config_dict["setup_data"]
    
    return config_file_path, access_info_dict, setup_data_dict

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap
