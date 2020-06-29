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

import json


# ---------------------------------------------------------------------------------------------------------------------
#%% Define general functions

# .....................................................................................................................

def dict_to_human_readable_output(data_dict, sort_keys = True):
    
    ''' Helper function which can be used to avoid importing json in places that don't need file i/o '''
    
    return json.dumps(data_dict, indent = 2, sort_keys = sort_keys)

# .....................................................................................................................

def _create_missing_folders_from_file(file_path):
    
    '''
    Helper function which creates the folder pathing needed for a given file path.
    Redefined specifically for this script, to avoid import loops!
    '''
    
    folder_path = os.path.dirname(file_path)
    os.makedirs(folder_path, exist_ok = True)
    
    return folder_path

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Define config i/o functions

# .....................................................................................................................

def load_config_json(load_path, error_if_missing = True):
    
    ''' 
    Helper function for loading config style json data 
    By default, will throw a FileNotFound error if the file is missing.
    If this is disabled, the function will return None for missing files
    '''
    
    # Check that the file path exists
    file_exists = os.path.exists(load_path)
    
    # If we don't find the file, either raise an error or return nothing
    if (not file_exists):        
        if error_if_missing:
            print("", "",
                  "!" * 42,
                  "Error loading data:",
                  "@ {}".format(load_path),
                  "!" * 42,
                  "", "", sep="\n")
            raise FileNotFoundError("Couldn't find file for loading!")
        return None
    
    # Assuming the file does exist, load it's contents
    with open(load_path, "r") as in_file:
        loaded_data = json.load(in_file)
    
    return loaded_data

# .....................................................................................................................

def save_config_json(save_path, json_data, create_missing_folder_path = False):
    
    '''
    Helper function which saves (and overwrites!) json files, in a human-readable format (i.e. indented)
    Returns nothing
    '''
    
    # Always try converting to json string to watch for errors
    try:
        _ = json.dumps(json_data)
    except TypeError as err:
        print("", 
              "Error saving json data:",
              "@ {}".format(save_path),
              "",
              "Got invalid data?:",
              json_data, 
              "", "", sep = "\n")
        raise err
        
    # Create the parent folder, if needed
    if create_missing_folder_path:
        _create_missing_folders_from_file(save_path)
    
    with open(save_path, "w") as out_file:
        json.dump(json_data, out_file, indent = 2, sort_keys = True)
    
    return

# .....................................................................................................................
    
def create_missing_config_json(save_path, default_json_data, creation_printout = "Creating JSON:", 
                               create_missing_folder_path = True):
    
    '''
    Function which takes a file path and will create a file at that path, if one doesn't already exist.
    Otherwise, the function does nothing.
    
    Inputs:
        save_path (string) -> Path to create/save a new file
        
        default_json_data (dict/list) -> Data saved into the file if created
        
        creation_printout (string or None) -> Feedback that is printed if a file is created (will also print path)
        
        create_missing_folder_path (boolean) -> If true, the parent folder(s) path will be created if missing
        
    Outputs:
        Nothing
    '''
    
    # Create the folder path, if needed
    if create_missing_folder_path:
        _create_missing_folders_from_file(save_path)
    
    # If the file doesn't exist, create it
    file_exists = (os.path.exists(save_path))
    if (not file_exists):
        
        # Only print feedback if we were given something to print!
        if creation_printout:
            print("",
                  creation_printout,
                  "@ {}".format(save_path),
                  sep = "\n")
        
        # Write the default to file
        save_config_json(save_path, default_json_data, create_missing_folder_path)
            
    return

# .....................................................................................................................

def load_or_create_config_json(load_path, default_content, creation_printout = "Creating JSON:"):
    
    '''
    Helper function which will try to load a json config file is possible,
    or otherwise will create a file (along with some printed feedback) if it is missing
    '''
    
    # If the file doesn't exist, create it
    create_missing_config_json(load_path, default_content, creation_printout)
    
    return load_config_json(load_path)

# .....................................................................................................................

def update_config_json(save_path, update_json_entry):
    
    '''
    Function which loads an existing json file, assumed to be holding a dictionary
    The function will update the dictionary based on the 'update_json_entry' input argument,
    then re-save the file back in place (preserving any other data!)
    Returns the updated dictionary data
    '''
    
    # Try to load an existing config file or otherwise create an empty one
    load_dict = load_or_create_config_json(save_path, {}, creation_printout = None)
        
    # Update the loaded data with new dictionary data
    load_dict.update(update_json_entry)
    
    # Now re-save the updated data
    save_config_json(save_path, load_dict)
    
    return load_dict

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap


