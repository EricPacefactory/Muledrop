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
#%% Helper functions

# .....................................................................................................................

def get_env(environment_variable_name, default_value_if_missing = None, return_type = None, convert_none_types = True):
    
    '''
    Helper function which grabs environment variables, with defaults if missing. Can also handle
    conversion to a specific data type if needed, and will replace 'None' or 'Null' entries with
    python-specific None type data
    
    Inputs:
        envasdasd --> (String) Name of environment variable to read
        
        default_value_if_missing --> (Any) Value to return if the environment variable isn't found
        
        return_type --> (Data type or None) If set to None, the return type of the environment variable 
                        or default value will not be altered. If a type is provided, (e.g. str, int, float etc)
                        the returned data will be converted before returning, unless it is None
        
        convert_none_types --> (Boolean) If true, entries such as "None" or "null" will be converted to
                               python None types on return
    
    Outputs:
        environment_variable_value
    '''
    
    # First try to access the environment variable value (or use the default value if missing)
    env_value = os.environ.get(environment_variable_name, default_value_if_missing)
    
    # Correct 'none' entries if needed
    already_none = (env_value is None)
    if convert_none_types and not already_none:
        lowered_var_str = str(env_value).strip().lower()
        replace_with_none = (lowered_var_str in {"none", "null"})
        env_value = None if replace_with_none else env_value
    
    # Apply type casting if needed
    if return_type is bool:
        # Special case for booleans, since bool("0") or bool("False") both evaluate to True!
        env_value_str = str(env_value)
        env_value = (env_value_str.lower() in {"true", "1"})
        
    elif return_type is not None:
        env_value = return_type(env_value)
    
    return env_value

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Posting functions

# .....................................................................................................................

def get_env_autopost_on_startup():
    return get_env("AUTOPOST_ON_STARTUP", 1, bool)

# .....................................................................................................................

def get_env_autopost_period_mins():
    return get_env("AUTOPOST_PERIOD_MINS", 2.5, float)

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Pathing functions

# .....................................................................................................................

def get_env_all_locations_folder():
    return get_env("ALL_LOCATIONS_FOLDER_PATH", None)

# .....................................................................................................................

def get_env_location_select():
    return get_env("LOCATION_SELECT", None)

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% DB server functions

# .....................................................................................................................

def get_dbserver_protocol():
    return get_env("DBSERVER_PROTOCOL", "http", str)

# .....................................................................................................................

def get_dbserver_host():
    return get_env("DBSERVER_HOST", "localhost", str)

# .....................................................................................................................

def get_dbserver_port():
    return get_env("DBSERVER_PORT", 8050, int)

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Control server functions

# .....................................................................................................................

def get_ctrlserver_protocol():
    return get_env("CTRLSERVER_PROTOCOL", "http", str)

# .....................................................................................................................

def get_ctrlserver_host():
    return get_env("CTRLSERVER_HOST", "0.0.0.0", str)

# .....................................................................................................................

def get_ctrlserver_port():
    return get_env("CTRLSERVER_PORT", 8181, int)

# .....................................................................................................................

def get_default_autolaunch():
    return get_env("AUTOLAUNCH_BY_DEFAULT", True, bool)

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Demo

if __name__ == "__main__":
    
    print("",
          "POSTING:",
          "Autpost on startup: {}".format(get_env_autopost_on_startup()),
          "Autopost period (mins): {}".format(get_env_autopost_period_mins()),
          "",
          "PATHING:",
          "All locations: {}".format(get_env_all_locations_folder()),
          "Location select: {}".format(get_env_location_select()),
          "",
          "DBSERVER:",
          get_dbserver_protocol(),
          get_dbserver_host(),
          get_dbserver_port(),
          "",
          "CTRLSERVER:",
          get_ctrlserver_protocol(),
          get_ctrlserver_host(),
          get_ctrlserver_port(),
          "", sep = "\n")
    
    pass

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap


