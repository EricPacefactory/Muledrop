#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Apr 12 12:49:38 2019

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

from local.lib.file_access_utils.shared import auto_project_root_path, load_or_create_json, load_replace_save

# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

# .....................................................................................................................

def load_history(project_root_path, history_file_name = ".selection_history", enable = True):
    
    project_root_path = auto_project_root_path(project_root_path)
    
    # Create default config entries
    default_config = {"camera_select": None,
                      "user_select": None,
                      "task_select": None,
                      "rule_select": None,
                      "video_select": None}
    
    # Return empty selections if disabled
    if not enable:
        return default_config
    
    # First create history path, then load the history file
    history_path = os.path.join(project_root_path, history_file_name)
    history_config = load_or_create_json(history_path, default_config,
                                         creation_printout = "Creating selection history file:")
    
    return history_config

# .....................................................................................................................

def save_history(project_root_path, new_config, history_file_name = ".selection_history", enable = True):
    
    project_root_path = auto_project_root_path(project_root_path)
    
    # Don't do anything if disabled
    if not enable:
        return
    
    # Create history path and the load existing history data, replace with new config and re-save
    history_path = os.path.join(project_root_path, history_file_name)
    load_replace_save(history_path, new_config)

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap
