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

from eolib.utils.read_write import load_json, save_json

# ---------------------------------------------------------------------------------------------------------------------
#%% General Pathing functions

# .....................................................................................................................

def build_summary_config_path(cameras_folder_path, camera_select, user_select, *path_joins):
    return build_after_database_configs_folder_path(cameras_folder_path, camera_select, user_select, 
                                                    "summary", "summary.json")

# .....................................................................................................................

def build_summary_adb_metadata_report_path(cameras_folder_path, camera_select, user_select, *path_joins):
    return build_after_database_report_path(cameras_folder_path, camera_select, user_select, "summary")

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% File naming functions

# .....................................................................................................................

def create_summary_file_name(object_full_id):
    return "summary-{}.json.gz".format(object_full_id)

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Data access functions

# .....................................................................................................................

def save_summary_data(cameras_folder_path, camera_select, user_select, object_full_id, summary_data_dict):
    
    # Build pathing to save
    save_file_name = create_summary_file_name(object_full_id)
    save_folder_path = build_summary_adb_metadata_report_path(cameras_folder_path, camera_select, user_select)
    save_file_path = os.path.join(save_folder_path, save_file_name)
    
    # Bundle data and save
    save_data = new_summary_entry(object_full_id, summary_data_dict)
    save_json(save_file_path, save_data, use_gzip = True, create_missing_folder_path = True)
    
# .....................................................................................................................
    
def new_summary_entry(object_full_id, summary_data_dict):
    
    ''' Helper function for creating properly formatted summary entries '''
    
    return {"full_id": object_full_id, **summary_data_dict}

# .................................................................................................................
    
def load_summary_config(cameras_folder_path, camera_select, user_select):
    
    ''' 
    Function which loads configuration files for a summary
    '''
    
    # Get path to the config file
    config_file_path = build_summary_config_path(cameras_folder_path, camera_select, user_select)
    
    # Load json data and split into file access info & setup configuration data
    config_dict = load_json(config_file_path)
    access_info_dict = config_dict["access_info"]
    setup_data_dict = config_dict["setup_data"]
    
    return config_file_path, access_info_dict, setup_data_dict

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap
