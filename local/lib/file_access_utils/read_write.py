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
#%% File i/o

# .....................................................................................................................
    
def create_json(file_path, json_data, creation_printout = "Creating JSON:", overwrite_existing = False,
                create_missing_folder = True):
    
    # Create the folder path, if needed
    if create_missing_folder:
        folder_path = os.path.dirname(file_path)
        os.makedirs(folder_path, exist_ok = True)
    
    # If the file doesn't exist, create it
    file_doesnt_exist = (not os.path.exists(file_path))
    if file_doesnt_exist or overwrite_existing:
        
        if creation_printout:
            print("")
            print(creation_printout)
            print(" ", file_path)
        
        # Write the default to file
        with open(file_path, "w") as out_file:
            json.dump(json_data, out_file, indent = 2, sort_keys = True)
            
# .....................................................................................................................
            
def load_with_error_if_missing(file_path):
    
    # Check that the file path exists
    if not os.path.exists(file_path):
        print("", "",
              "!" * 42,
              "Error reading data:",
              "@ {}".format(file_path),
              "!" * 42,
              "", "", sep="\n")
        raise FileNotFoundError("Couldn't find file for loading!")
    
    # Assuming the file does exist, load it's contents
    with open(file_path, "r") as in_file:
        load_content = json.load(in_file)
        
    return load_content

# .....................................................................................................................

def load_or_create_json(file_path, default_content, creation_printout = "Creating JSON:"):
    
    # If the file doesn't exist, create it, then load
    create_json(file_path, default_content, creation_printout, overwrite_existing = False)
    return load_with_error_if_missing(file_path)

# .....................................................................................................................

def load_replace_save(file_path, new_dict_data, indent_data = True, create_if_missing = True):
    
    '''
    Loads an existing file, assumed to hold a dictionary of data,
    then updates the dictionary with the newly provided data,
    and re-saves the file
    '''
    
    # Check if the file exists. If it doesn't and we're not allowed to create it if missing, give an error
    file_exists = os.path.exists(file_path)
    if (not file_exists) and (not create_if_missing):
        raise FileNotFoundError("Couldn't replace file, it doesn't exists: {}".format(file_path))
    
    # Load the target data set or assume it's blank if the path isn't valid
    load_data = load_with_error_if_missing(file_path) if file_exists else {}
            
    # Update with any new data
    load_data.update(new_dict_data)
    
    # Now re-save the (updated) data
    full_replace_save(file_path, load_data, indent_data)
    
    return load_data

# .....................................................................................................................

def full_replace_save(file_path, save_data, indent_data = True):
    
    # Save the data
    indent_amount = 2 if indent_data else None
    with open(file_path, "w") as out_file:
        json.dump(save_data, out_file, indent = indent_amount)
    
    return save_data

# .....................................................................................................................
# .....................................................................................................................
    
# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap


