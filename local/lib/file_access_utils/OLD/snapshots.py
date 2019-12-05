#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Jul  2 11:15:32 2019

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

from local.lib.file_access_utils.shared import copy_from_defaults
from local.lib.file_access_utils.shared import full_replace_save

from local.lib.file_access_utils.externals import build_externals_folder_path

from local.lib.file_access_utils.reporting import build_image_report_path, build_metadata_report_path

# ---------------------------------------------------------------------------------------------------------------------
#%% Pathing functions

# .....................................................................................................................

def build_snapshot_folder_paths(cameras_folder, camera_select, user_select):
    
    # Build shared names/pathing
    snapshot_folder_name = "snapshots"
    image_folder_path = build_image_report_path(cameras_folder, camera_select, user_select, snapshot_folder_name)
    metadata_folder_path = build_metadata_report_path(cameras_folder, camera_select, user_select, snapshot_folder_name)
    
    return image_folder_path, metadata_folder_path

# .....................................................................................................................

def build_snapshots_config_file_path(cameras_folder, camera_select, user_select, config_file_name = "snapshots.json"):
    return build_externals_folder_path(cameras_folder, camera_select, user_select, config_file_name)

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Config functions

# .....................................................................................................................

def create_default_snapshot_config(project_root_path, user_folder_path):
    
    # Pull default json config files out of the defaults folder, and copy in to the user folder
    copy_from_defaults(project_root_path, 
                       target_defaults_folder = "externals",
                       copy_to_path = user_folder_path)

# .....................................................................................................................
    
def save_snapshot_config(cameras_folder, camera_select, user_select, 
                         script_name, class_name, config_data, confirm_save = True):
    
    # Build save pathing
    config_file_path = build_snapshots_config_file_path(cameras_folder, camera_select, user_select)
    
    # Build the data structure for the config data
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
