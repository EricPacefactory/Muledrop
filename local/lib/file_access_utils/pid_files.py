#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Mar 12 10:36:43 2020

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

import subprocess
import signal

from time import sleep

from local.lib.file_access_utils.logging import build_pid_folder_path
from local.lib.file_access_utils.json_read_write import save_config_json, load_config_json

# ---------------------------------------------------------------------------------------------------------------------
#%% Classes

# .....................................................................................................................

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% General pathing functions

# .....................................................................................................................
    
def build_pid_file_path(cameras_folder_path, camera_select, pid_value):
    ''' Build pathing to the file used to store PID information for running processes, for a given camera '''
    return build_pid_folder_path(cameras_folder_path, camera_select, "{}.json".format(pid_value))

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Saving/loading functions

# .....................................................................................................................

def save_pid_file(cameras_folder_path, camera_select, pid_value, script_name, start_timestamp_str):
    
    ''' Function which saves a PID logging file, used to keep tracking of running processes '''
    
    # Build data to save
    save_data_dict = {"PID": pid_value,
                      "start_timestamp": start_timestamp_str,
                      "script_name": script_name}
    
    pid_save_path = build_pid_file_path(cameras_folder_path, camera_select, pid_value)
    save_config_json(pid_save_path, save_data_dict, create_missing_folder_path = True)
    
    return pid_save_path

# .....................................................................................................................

def load_pid_files_dict(cameras_folder_path, camera_select):
    
    '''
    Helper function which loads all PID file data (if any) 
    Data is returned as a dictionary, where each key is the pathing to the pid file and values store pid data
    Example:
        {
        "/path/to/pid/file1": {"PID": 1172,
                               "start_timestamp": "...",
                               "script_name": "..."},
        "/path/to/pid/file2": {...}
        }
        
    Note: Having more than 1 pid file should almost never happen, but is supported to avoid errors.
    '''
    
    # Get folder pathing to check PID files
    pid_folder_path = build_pid_folder_path(cameras_folder_path, camera_select)
    os.makedirs(pid_folder_path, exist_ok = True)
    
    # Get file listing in the pid folder
    pid_file_name_list = os.listdir(pid_folder_path)
    pid_file_path_list = [os.path.join(pid_folder_path, each_file_name) for each_file_name in pid_file_name_list]
    
    # Load all data from files    
    pid_data_dict = {}
    for each_path in pid_file_path_list:
        
        # Try to load the PID file data but skip it if the file is missing (it may be cleared while we're reading!)
        loaded_pid_data = load_config_json(each_path, error_if_missing = False)
        if loaded_pid_data is None:
            continue
        pid_data_dict[each_path] = loaded_pid_data
    
    return pid_data_dict


# ---------------------------------------------------------------------------------------------------------------------
#%% PID control functions
    
# .....................................................................................................................

def check_running_camera(cameras_folder_path, camera_select):
    
    ''' Helper functions for checking if a camera is online, using PID files '''
    
    # Initialize outputs
    camera_is_online = False
    start_timestamp_str = ""
    
    # Load all existing PID data and check if any of the files correspond to a running camera
    pid_data_dict = load_pid_files_dict(cameras_folder_path, camera_select)
    for each_pid_file_path, each_data_dict in pid_data_dict.items():
        pid_value = each_data_dict["PID"]
        script_name = each_data_dict["script_name"]
        start_timestamp_str = each_data_dict["start_timestamp"]
        camera_is_online = check_running_pid(pid_value, script_name)
        if camera_is_online:
            break
    
    return camera_is_online, start_timestamp_str

# .....................................................................................................................

def check_running_pid(pid_value, script_name):
    
    # Initialize output
    pid_is_running = False
    
    # Try to check the 'command' output of the ps system function, for the given PID
    try:
        # Check if there is an existing process with the given PID with the target script in the command
        ps_cmd_result = subprocess.check_output(["ps", "-p", str(pid_value), "-o", "cmd"], universal_newlines = True)
        pid_is_running = (script_name in ps_cmd_result)
            
    except subprocess.CalledProcessError:
        # This happens if the PID doesn't exist
        pass
    
    return pid_is_running

# .....................................................................................................................

def kill_running_pid(pid_value, script_name, max_wait_sec = 30.0):
    
    # Calculate the number of re-checks based on max wait time
    sleep_time_sec = 1.5
    num_rechecks = int(max(1, max_wait_sec / sleep_time_sec))
    
    # Check if the PID is running (with the target script name) and if so, kill it
    pid_is_running = check_running_pid(pid_value, script_name)
    if pid_is_running:
        
        # Some feedback
        print("  Killing process: {}".format(pid_value))
        
        # Killing could fail if the process ends before we get to it
        try:
            os.kill(pid_value, signal.SIGTERM)
            for k in range(num_rechecks):
                sleep(sleep_time_sec)
                pid_is_running = check_running_pid(pid_value, script_name)
                if not pid_is_running:
                    break
                
        except ProcessLookupError:
            # Do nothing if the kill fails
            pass
    else:
        print("  Process {} already dead".format(pid_value))
    
    return

# .....................................................................................................................

def clear_one_pid_file(cameras_folder_path, camera_select, pid_value):
    
    ''' Helper function for clearing PID files '''
    
    # Build path to pid file
    pid_file_path = build_pid_file_path(cameras_folder_path, camera_select, pid_value)
    
    # Try to remove the PID file
    # - may fail if the file is cleared before we get to it or if it didn't exist to begin with!
    try:
        os.remove(pid_file_path)
    except FileNotFoundError:
        pass
    
    return

# .....................................................................................................................

def clear_all_pid_files(cameras_folder_path, camera_select, max_retrys = 4):
    
    ''' Function used to clear out previous PID files (& corresponding processes!) '''
    
    # Try to clear PID files several times, if needed
    num_trys = (1 + max(0, max_retrys))
    for k in range(num_trys):
    
        # Load all existing PID data
        pid_data_dict = load_pid_files_dict(cameras_folder_path, camera_select)
        
        # We're done when there are no more PID files
        pids_exist = (len(pid_data_dict) > 0)
        if not pids_exist:
            break
        
        # Provide some feedback about clearing pids
        if k == 0:
            print("", "Clearing existing PIDs - {}".format(camera_select), sep = "\n")
        else:
            print("  --> Clearing existing PIDs - {} | (retry)".format(camera_select))
        
        # Load all PID data and close any PIDs that are still running
        for each_pid_path, each_pid_data in pid_data_dict.items():
            
            # Pull out relevant pid data, so we can check if the PID is still alive
            pid_value = each_pid_data["PID"]
            script_name = each_pid_data["script_name"]
            
            # Kill the target PID, if possible, and clear the pid file
            kill_running_pid(pid_value, script_name)
            clear_one_pid_file(cameras_folder_path, camera_select, pid_value)

    return

# .....................................................................................................................
# .....................................................................................................................
    
# ---------------------------------------------------------------------------------------------------------------------
#%% Demo

if __name__ == "__main__":
    
    pass

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap


