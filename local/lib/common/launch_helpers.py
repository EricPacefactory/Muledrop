#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Mar 20 16:23:48 2020

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

from local.lib.file_access_utils.structures import create_missing_folder_path

from local.lib.file_access_utils.reporting import build_user_report_path

from local.eolib.utils.files import get_total_folder_size
from local.eolib.utils.cli_tools import cli_confirm

# ---------------------------------------------------------------------------------------------------------------------
#%% Classes

# .....................................................................................................................

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% General functions

# .....................................................................................................................

def save_data_prompt(save_by_default = False, enable_save_prompt = True):
    
    # If disabled, return the default
    if not enable_save_prompt:
        return save_by_default
    
    # If we get here, provide the save prompt
    save_by_default = False
    saving_enabled = cli_confirm("Save data?", default_response = save_by_default)
            
    return saving_enabled

# .....................................................................................................................

def delete_existing_report_data(cameras_folder_path, camera_select, user_select,
                                enable_deletion = True, enable_deletion_prompt = False):
    
    # If disabled, don't do anything
    if not enable_deletion:
        return
    
    # Build pathing to report data
    report_data_folder = build_user_report_path(cameras_folder_path, camera_select, user_select)
    create_missing_folder_path(report_data_folder)
    
    # Check if data already exists
    existing_file_count, _, total_file_size_mb, _ = get_total_folder_size(report_data_folder)
    saved_data_exists = (existing_file_count > 0)
    
    # Provide prompt (if enabled) to allow user to avoid deleting existing data
    if saved_data_exists:
        
        if enable_deletion_prompt:
            confirm_msg = "Saved data already exists! Delete? ({:.1f} MB)".format(total_file_size_mb)
            confirm_data_delete = cli_confirm(confirm_msg, default_response = True)
            if not confirm_data_delete:
                return
    
        # If we get here, delete the files!
        print("", "Deleting files:", "@ {}".format(report_data_folder), sep="\n")
        rmtree(report_data_folder)
        
    return

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Demo

if __name__ == "__main__":
    
    pass

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap


