#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Jul  3 10:43:54 2019

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
#%% Classes

# .....................................................................................................................

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% General pathing functions

# .....................................................................................................................

def build_base_log_path(cameras_folder_path, camera_select, *path_joins):
    ''' Build pathing to logging folder for a given camera '''    
    return os.path.join(cameras_folder_path, camera_select, "logs", *path_joins)

# .....................................................................................................................

def build_configurables_log_path(cameras_folder_path, camera_select, *path_joins):
    ''' Build pathing to the configurables logging folder for a given camera '''
    return build_base_log_path(cameras_folder_path, camera_select, "configurables", *path_joins)

# .....................................................................................................................

def build_system_log_path(cameras_folder_path, camera_select, *path_joins):
    ''' Build pathing to the system logging folder for a given camera '''
    return build_base_log_path(cameras_folder_path, camera_select, "system", *path_joins)

# .....................................................................................................................

def build_post_db_log_path(cameras_folder_path, camera_select, *path_joins):
    ''' Build path to the folder containing logging info for posting to a database, for a given camera '''    
    return build_system_log_path(cameras_folder_path, camera_select, "post_to_db", *path_joins)

# .....................................................................................................................
    
def build_pid_folder_path(cameras_folder_path, camera_select, *path_joins):
    ''' Build pathing to the folder used to store PID information for running processes '''
    return build_system_log_path(cameras_folder_path, camera_select, "pid", *path_joins)

# .....................................................................................................................

def build_stdout_log_path(cameras_folder_path, camera_select, *path_joins):
    ''' Build pathing to the folder used to store stdout logs for running cameras '''
    return build_system_log_path(cameras_folder_path, camera_select, "stdout", *path_joins)

# .....................................................................................................................

def build_stderr_log_path(cameras_folder_path, camera_select, *path_joins):
    ''' Build pathing to the folder used to store stderr logs for running cameras '''
    return build_system_log_path(cameras_folder_path, camera_select, "stderr", *path_joins)

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Demo

if __name__ == "__main__":
    
    pass

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap


