#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Mar 20 15:40:55 2020

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


# ---------------------------------------------------------------------------------------------------------------------
#%% Posting functions

# .....................................................................................................................

def get_autopost_on_startup():
    return bool(int(os.environ.get("AUTOPOST_ON_STARTUP", 1)))

# .....................................................................................................................

def get_autopost_period_mins():
    return float(os.environ.get("AUTOPOST_PERIOD_MINS", 2.5))

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Pathing functions

# .....................................................................................................................

def get_env_cameras_folder():
    return os.environ.get("CAMERAS_FOLDER_PATH", None)

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% MongoDB functions

# .....................................................................................................................

def get_mongo_protocol():
    return os.environ.get("MONGO_PROTOCOL", "mongodb")

# .....................................................................................................................

def get_mongo_host():
    return os.environ.get("MONGO_HOST", "localhost")

# .....................................................................................................................
    
def get_mongo_port():
    return int(os.environ.get("MONGO_PORT", 27017))

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% DB server functions

# .....................................................................................................................

def get_dbserver_protocol():
    return os.environ.get("DBSERVER_PROTOCOL", "http")

# .....................................................................................................................

def get_dbserver_host():
    return os.environ.get("DBSERVER_HOST", "localhost")

# .....................................................................................................................

def get_dbserver_port():
    return int(os.environ.get("DBSERVER_PORT", 8050))

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Upload server functions

# .....................................................................................................................

def get_upserver_protocol():
    return os.environ.get("UPSERVER_PROTOCOL", "http")

# .....................................................................................................................

def get_upserver_host():
    return os.environ.get("UPSERVER_HOST", "0.0.0.0")

# .....................................................................................................................

def get_upserver_port():
    return int(os.environ.get("UPSERVER_PORT", 8181))

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Demo

if __name__ == "__main__":
    
    pass

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap


