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

import ujson
import gzip


# ---------------------------------------------------------------------------------------------------------------------
#%% Define utility functions

# .....................................................................................................................

def fast_dict_to_json(data_dict):
    
    ''' 
    Helper function which can be used to avoid importing json in places that don't need file i/o,
    same as 'dict_to_human_readable_output' but intended for internal use. Should be faster
    '''
    
    return ujson.dumps(data_dict)

# .....................................................................................................................

def fast_json_to_dict(json_string_data):
    
    ''' 
    Helper function which can be used to avoid importing json in places that don't need file i/o.
    Converts python data to json strings. Does not perform data type conversions!
    '''
    
    return ujson.loads(json_string_data)

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Define encoding functions

# .....................................................................................................................

def encode_json_data(metadata_dict, json_double_precision):
    
    # Encode json data for saving
    encd_json_data = ujson.dumps(metadata_dict, sort_keys = False, double_precision = json_double_precision)
    
    return encd_json_data

# .....................................................................................................................

def encode_jsongz_data(metadata_dict, json_double_precision):
    
    # Encode gzipped json data for saving
    encd_json_data = encode_json_data(metadata_dict, json_double_precision)
    encd_jsongz_data = gzip.compress(bytes(encd_json_data, "ascii"))
    
    return encd_jsongz_data

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Define decoding functions

# .....................................................................................................................

def decode_jsongz_data(jsongz_byte_data):
    
    ''' Function which takes in gzipped json byte data and converts it back to python data types '''
    
    json_bytes = gzip.decompress(jsongz_byte_data)
    python_data = ujson.loads(json_bytes.decode("ascii"))
    
    return python_data

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Define writing functions

# .....................................................................................................................

def write_encoded_json(save_folder_path, save_name_no_ext, encoded_json_data):
    
    ''' Helper function used to write encoded json data to disk '''
    
    save_name = "{}.json".format(save_name_no_ext)
    save_path = os.path.join(save_folder_path, save_name)
    with open(save_path, "w") as out_file:
        out_file.write(encoded_json_data)
    
    return save_path

# .....................................................................................................................

def write_encoded_jsongz(save_folder_path, save_name_no_ext, encoded_jsongz_data):
    
    ''' Helper function used to write encoded gzipped json data to disk '''
    
    save_name = "{}.json.gz".format(save_name_no_ext)
    save_path = os.path.join(save_folder_path, save_name)
    with open(save_path, "wb") as out_file:
        out_file.write(encoded_jsongz_data)
    
    return save_path

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Define composite functions

# .....................................................................................................................

def save_json_metadata(save_folder_path, metadata_dict, json_double_precision = 3):
    
    '''
    Helper function which encodes + writes metadata as json files
    Note: This function assumes the metadata contains an '_id' entry (i.e. intended for database entry)
    and will save the file name using the _id value
    '''
    
    # Get name + data to write
    save_name_no_ext = metadata_dict["_id"]
    encd_json = encode_json_data(metadata_dict, json_double_precision)
    
    return write_encoded_json(save_folder_path, save_name_no_ext, encd_json)

# .....................................................................................................................

def save_jsongz_metadata(save_folder_path, metadata_dict, json_double_precision = 3):
    
    '''
    Helper function which encodes + writes metadata as gzipped json files
    Note: This function assumes the metadata contains an '_id' entry (i.e. intended for database entry)
    and will save the file name using the _id value
    '''
    
    # Get name + data to write
    save_name_no_ext = metadata_dict["_id"]
    encd_jsongz = encode_jsongz_data(metadata_dict, json_double_precision)
    
    return write_encoded_jsongz(save_folder_path, save_name_no_ext, encd_jsongz)

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Define loading functions

# .....................................................................................................................

def load_json_metadata(load_path):
    
    '''
    Function which loads a json metadata file from a specified loading path
    Does not check if the pathing is valid
    
    Inputs:
        load_path -> String. Path to file to be loaded. Expects json files (i.e. ending with .json)
        
    Outputs:
        loaded_data (dictionary)
    '''
    
    # Assume the file exists and load it's contents
    with open(load_path, "r") as in_file:
        loaded_data = ujson.load(in_file)
        
    return loaded_data

# .....................................................................................................................

def load_jsongz_metadata(load_path):
    
    '''
    Function which loads a gzipped json file from a specified loading path
    Does not check if the pathing is valid
    
    Inputs:
        load_path -> String. Path to file to be loaded. Expects gzipped json files (i.e. ending with .json.gz!)
    
    Outputs:
        loaded_data (dictionary)
    '''
    
    # Use gzip to unzip the json data before loading
    with gzip.open(load_path, 'rt') as in_file:
        loaded_data = ujson.load(in_file)
    
    return loaded_data

# .....................................................................................................................

def load_metadata(load_path):
    
    '''
    Helper function which handles loading of metadata in both .json and .json.gz formats
    
    Inputs:
        load_path -> String. Path to file to be loaded. Expects either .json or .json.gz files
    
    Outputs:
        loaded_data (dictionary)
    '''
    
    is_gzipped = load_path.endswith("gz")
    return load_jsongz_metadata(load_path) if is_gzipped else load_json_metadata(load_path)

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap


