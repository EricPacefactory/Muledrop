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

from local.lib.common.timekeeper_utils import get_filesafe_date

from local.lib.file_access_utils.shared import build_logging_folder_path


# ---------------------------------------------------------------------------------------------------------------------
#%% General pathing functions

# .....................................................................................................................

def make_log_folder(log_path, make_parent_folder = True):
    
    '''
    Helper function which creates the folder pathing to a log file.
    By default assumes a file path is given, and will try to create the parent folder for the file.
    To create the given path itself, set the 'make_parent_folder' arg to False
    '''
    
    folder_path_to_make = log_path
    if make_parent_folder:
        folder_path_to_make = os.path.dirname(log_path)
    
    os.makedirs(folder_path_to_make, exist_ok = True)
    
    return

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% General pathing functions

# .....................................................................................................................

def build_configurables_log_path(location_select_folder_path, camera_select, *path_joins):
    ''' Build pathing to the configurables logging folder for a given camera '''
    return build_logging_folder_path(location_select_folder_path, camera_select, "configurables", *path_joins)

# .....................................................................................................................

def build_system_log_path(location_select_folder_path, camera_select, *path_joins):
    ''' Build pathing to the system logging folder for a given camera '''
    return build_logging_folder_path(location_select_folder_path, camera_select, "system", *path_joins)

# .....................................................................................................................

def build_post_db_log_path(location_select_folder_path, camera_select, *path_joins):
    ''' Build path to the folder containing logging info for posting to a database, for a given camera '''    
    return build_system_log_path(location_select_folder_path, camera_select, "post_to_db", *path_joins)

# .....................................................................................................................
    
def build_state_file_path(location_select_folder_path, camera_select):
    ''' Build pathing to the file used to store state information for running processes '''
    return build_system_log_path(location_select_folder_path, camera_select, "state", "state.json")

# .....................................................................................................................

def build_stdout_log_file_path(location_select_folder_path, camera_select):
    
    ''' Build pathing to a file used to store stdout log for a running camera '''
    
    # Get the current date, used to organize logs (by calling time)
    current_date_str = get_filesafe_date()
    
    # Get pathing to where we'll want to put the log file
    log_folder_path =  build_system_log_path(location_select_folder_path, camera_select, "stdout", current_date_str)
    make_log_folder(log_folder_path, make_parent_folder = False)
    
    # Decide the file name and build the final path
    num_files = len(os.listdir(log_folder_path))
    new_log_name = "out_{}.log".format(1 + num_files)
    log_file_path = os.path.join(log_folder_path, new_log_name)
    
    return log_file_path

# .....................................................................................................................

def build_stderr_log_file_path(location_select_folder_path, camera_select):
    
    ''' Build pathing to the file used to store stderr logs for a running camera '''
    
    # Get the current date, used to organize logs (by calling time)
    current_date_str = get_filesafe_date()
    
    # Get pathing to where we'll want to put the log file
    log_folder_path =  build_system_log_path(location_select_folder_path, camera_select, "stderr", current_date_str)
    make_log_folder(log_folder_path, make_parent_folder = False)
    
    # Decide the file name and build the final path
    num_files = len(os.listdir(log_folder_path))
    new_log_name = "out_{}.log".format(1 + num_files)
    log_file_path = os.path.join(log_folder_path, new_log_name)
    
    return log_file_path

# .....................................................................................................................

def build_upload_folder_path(location_select_folder_path, camera_select, *path_joins):
    ''' Build pathing to the folder used to store logs from the upload/configuration server '''
    return build_system_log_path(location_select_folder_path, camera_select, "upload_server", *path_joins)

# .....................................................................................................................

def build_upload_new_log_file_path(location_select_folder_path, camera_select):
    ''' Build pathing to the upload server new log file '''
    return build_upload_folder_path(location_select_folder_path, camera_select, "new.log")

# .....................................................................................................................

def build_upload_update_log_file_path(location_select_folder_path, camera_select):
    ''' Build pathing to the upload server update log file '''
    return build_upload_folder_path(location_select_folder_path, camera_select, "update.log")

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Demo

if __name__ == "__main__":
    
    pass

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap


