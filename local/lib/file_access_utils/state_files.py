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

from signal import SIGTERM, SIGKILL

from time import sleep

from local.lib.common.timekeeper_utils import get_human_readable_timestamp

from local.lib.file_access_utils.logging import build_state_file_path
from local.lib.file_access_utils.json_read_write import save_config_json, load_config_json


# ---------------------------------------------------------------------------------------------------------------------
#%% Classes

# .....................................................................................................................

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% General pathing functions

# .....................................................................................................................

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Saving/loading functions

# .....................................................................................................................

def new_state_data(script_name, pid_value, in_standby = False, state_description_str = "online"):
    
    '''
    Helper function used to format state data entries
    
    Inputs:        
        script_name -> (String) Used to indicate the script 'creating' the new process. Note that this
                       data is used to help check on the running script and/or close the script. By storing
                       the script name, we avoid accidentally closing processes that aren't running the target script!
        
        pid_value -> (Integer) The process id value for the running script. Used to check if the process is running
                     after initial launch. Also used to close the process in the future
        
        in_standby -> (Boolean) If true, the camera is running, but not considered to be generating data.
                      This is intended to avoid confusion when the camera may be performing some initialization,
                      or be in a reconnect state, and is therefore active but not generating meaningful output (yet!)
        
        state_description_str -> (String) Simple description of what the camera is doing. Used to provide feedback
                                 to any UI used to present/control the camera state.
    
    Outputs:
        new_state_dict (dictionary)
    '''
    
    # Automatically generate a timestamp everytime we create a new state entry
    timestamp_str = get_human_readable_timestamp()
    
    # Bundle all the state data together in json-friendly format for saving/reading
    new_state_dict = {"PID": pid_value,
                      "script_name": script_name,
                      "in_standby": in_standby,
                      "timestamp_str": timestamp_str,
                      "state_description": state_description_str}
    
    return new_state_dict

# .....................................................................................................................

def save_state_file(cameras_folder_path, camera_select, *, 
                    script_name, pid_value, in_standby, state_description_str):
    
    ''' Function which saves a state logging file, used to keep tracking of running processes '''
    
    # Bundle data & save!
    save_data_dict = new_state_data(script_name, pid_value, in_standby, state_description_str)
    file_save_path = build_state_file_path(cameras_folder_path, camera_select)
    save_config_json(file_save_path, save_data_dict, create_missing_folder_path = True)
    
    return file_save_path

# .....................................................................................................................

def load_state_file(cameras_folder_path, camera_select):
    
    '''
    Function which tries to load existing state file data for a given camera
    If no existing state data exists, the function returns None
    '''
    
    # Build pathing to the state file (if one exists)
    state_file_path = build_state_file_path(cameras_folder_path, camera_select)
    
    # Try to load the state file data but skip it if the file is missing (it may be cleared while we're reading!)
    loaded_state_data = load_config_json(state_file_path, error_if_missing = False)
    no_state_data = (loaded_state_data is None)
    
    return no_state_data, loaded_state_data

# .....................................................................................................................

def delete_state_file(cameras_folder_path, camera_select):
    
    '''
    Helper function for removing the state file of a given camera
    Note: This function does not clear any associated processes! 
          -> The caller is responsible for ensuring that the state file is no longer needed
    '''
    
    # Build path to state file
    state_file_path = build_state_file_path(cameras_folder_path, camera_select)
    
    # Try to remove the state file
    # - may fail if the file is cleared before we get to it or if it didn't exist to begin with!
    try:
        os.remove(state_file_path)
    except FileNotFoundError:
        pass
    
    return

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% state control functions
    
# .....................................................................................................................

def check_running_camera(cameras_folder_path, camera_select):
    
    ''' Helper functions for checking if a camera is online, using state files '''
    
    # Initialize outputs
    camera_is_online = False
    state_data_dict = {}
    
    # Load all existing state data and check if any of the files correspond to a running camera
    no_state_data, state_data_dict = load_state_file(cameras_folder_path, camera_select)
    if no_state_data:
        return camera_is_online, state_data_dict
    
    # Assuming there is state data available, read it from the file
    pid_value = state_data_dict["PID"]
    script_name = state_data_dict["script_name"]
    camera_is_online = check_running_pid(pid_value, script_name)
    
    return camera_is_online, state_data_dict

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

def kill_running_pid(pid_value, script_name, max_wait_sec = 30.0, force_kill_on_timeout = False):
    
    # Calculate the number of re-checks based on max wait time
    sleep_time_sec = 1.5
    force_kill_check = int(force_kill_on_timeout)
    num_rechecks = int(max(1, (max_wait_sec / sleep_time_sec) - force_kill_check))
    
    # Check if the PID is running (with the target script name) and if so, kill it
    pid_is_running = check_running_pid(pid_value, script_name)
    if pid_is_running:
        
        # Some feedback
        print("  Killing process: {}".format(pid_value))
        
        # Killing could fail if the process ends before we get to it
        try:
            os.kill(pid_value, SIGTERM)
            for k in range(num_rechecks):
                sleep(sleep_time_sec)
                pid_is_running = check_running_pid(pid_value, script_name)
                if not pid_is_running:
                    break
            
            # If we get here and the process is still running, try the nuclear option
            if pid_is_running and force_kill_on_timeout:
                os.kill(pid_value, SIGKILL)
                sleep(sleep_time_sec)
                pid_is_running = check_running_pid(pid_value, script_name)
            
        except ProcessLookupError:
            # Do nothing if the kill fails
            pass
    else:
        print("  Process {} already dead".format(pid_value))
    
    return pid_is_running

# .....................................................................................................................

def shutdown_running_camera(cameras_folder_path, camera_select, max_wait_sec = 30.0, force_kill_on_timeout = False):
    
    ''' Function which both ends a running camera process and also clears the camera state file '''
    
    # First check that the camera is actually running
    camera_is_running, state_dict = check_running_camera(cameras_folder_path, camera_select)
    
    # Shutdown the process of the running camera, if needed
    if camera_is_running:
        camera_pid = state_dict["PID"]
        camera_script_name = state_dict["script_name"]
        kill_running_pid(camera_pid, camera_script_name, force_kill_on_timeout)
    
    # Finally, remove the state file
    delete_state_file(cameras_folder_path, camera_select)
    
    return

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Demo

if __name__ == "__main__":
    
    pass

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap


