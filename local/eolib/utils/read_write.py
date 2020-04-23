#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Aug 22 10:43:01 2019

@author: eo
"""


# ---------------------------------------------------------------------------------------------------------------------
#%% Imports

import os
import json
import gzip
import csv

import numpy as np


# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes



# ---------------------------------------------------------------------------------------------------------------------
#%% Shared Functions

# .....................................................................................................................

def name_ext(file_path, special_exts = [".json.gz", ".csv.gz"]):
    
    '''
    Function which takes an input file name or full path and returns the name only and file extension 
    For example:
        name_ext("/path/to/some_file.json") -> ("some_file", ".json")
        
    The function also takes a 'special_exts' input argument to deal with detecting special file extensions
    (typically compounded extensions like .json.gz), which might not be properly interpretted otherwise
    '''
    
    # Remove folder pathing, if present
    basename = os.path.basename(file_path)
    
    # Catch any special extension cases
    for each_special_ext in special_exts:
        if basename.endswith(each_special_ext):
            special_ext_split_idx = -len(each_special_ext)
            name_only = basename[:special_ext_split_idx]
            file_ext = each_special_ext            
            return name_only, file_ext
    
    # If no special extension was found, use regular os.path... splitting
    name_only, file_ext = os.path.splitext(basename)
    
    return name_only, file_ext

# .....................................................................................................................

def build_target_path(file_path, *, target_folder = None, target_name = None, target_ext = None):
    
    '''
    Function for generating modified pathing given an input file path
    Inputs:
        file_path -> String. Represents a path to a file or a filename
        
        target_folder -> If not None, the folder pathing will be renamed to the target_folder
        
        target_name -> If not None, the file will be renamed to the target_name
        
        target_ext -> If not None, the file extension will be renamed to the target_ext. 
                      (Should include "." ex. ".json")
                      
    Outputs:
        save_path -> Full pathing after replacing (non-None) target values
    '''
    
    # Split the given file path into pieces so we can re-assemble with desired output structure
    file_folder = os.path.dirname(file_path)
    name_only, file_ext = name_ext(file_path)
    
    # Select appropriate save values
    save_folder = file_folder if target_folder is None else target_folder
    save_name = name_only if target_name is None else target_name
    save_ext = file_ext if target_ext is None else target_ext
    
    # Build saving path based on selections
    save_path = os.path.join(save_folder, "{}{}".format(save_name, save_ext))
    
    return save_path

# .....................................................................................................................

def numpy_array_to_list(input_data):
    
    ''' Function used to convert numpy array data to lists, intended for saving in json format '''    
    
    # Convert numpy arrays to lists before saving (so that data is json serializable)
    if type(input_data) is np.ndarray:
        return input_data.tolist()
    
    # Convert lists of numpy arrays to lists of lists
    if type(input_data) in (list, tuple):
        output_data = []
        for each_entry in input_data:
            entry_is_array = (type(each_entry) is np.ndarray)
            output_data.append(each_entry.tolist() if entry_is_array else each_entry)
        return output_data
            
    return input_data

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% JSON Functions

# .....................................................................................................................

def convert_integer_json_keys(json_data):
    
    '''
    Function which (recursively) converts json integer keys (stored as strings) to python integers
    Works on positive and negative integers. Will not convert floats!
    '''
    
    # Only convert dictionary keys, not values
    if type(json_data) is not dict:
        return json_data
    
    # Allocate storage for output dictionary with integer keys
    converted_dict = {}
    for each_key, each_value in json_data.items():
        
        # Convert numeric keys by trying int conversion, and reverting to original key if that fails
        # Works for negative integers, but won't convert floats!
        try:
            converted_key = int(each_key)
        except ValueError:
            converted_key = each_key
            
        # Recursively apply conversion to any internal dictionaries, before adding to the output dictionary
        converted_values = convert_integer_json_keys(each_value)
        converted_dict.update({converted_key: converted_values})
    
    return converted_dict

# .....................................................................................................................
    
def get_json_path(load_path, error_if_missing = True):
    
    '''
    Function which takes in a load_path that can have a .json or .json.gz extension, or no extension,
    and generates a path to a real json file with the correct extension (assuming the file exists).
    
    For example, assuming a file exists at "/path/to/file.json.gz", then
        get_json_path("/path/to/file") returns "/path/to/file.json.gz"
    
    A a FileNotFoundError is raised if there is no file with a .json or .json.gz extension at 
    the provided path and error_if_missing is true. Otherwise, the function returns None.
    '''
    
    # If the provided load path is not a file, check if a .json or .json.gz extension leads to a file
    path_exists = lambda path: os.path.exists(path)
    if not path_exists(load_path):
        
        # Build pathing to .json and .json.gz paths to see if those exist
        json_ext_load_path = build_target_path(load_path, target_ext = ".json")
        jsongz_ext_load_path = build_target_path(load_path, target_ext = ".json.gz")
        
        # Try .json, then .json.gz loading paths, if we still don't find anything, we'll have to raise an error
        if path_exists(json_ext_load_path):
            load_path = json_ext_load_path
        elif path_exists(jsongz_ext_load_path):
            load_path = jsongz_ext_load_path
        else:
            if error_if_missing:
                raise FileNotFoundError("Couldn't find a file @ {}".format(load_path))
            load_path = None
    
    return load_path

# .....................................................................................................................

def load_json(load_path, convert_integer_keys = False, error_if_missing = True):
    
    '''
    Function which loads a json file from a specified loading path.
    Inputs:
        load_path -> String. Path to file to be loaded. Accepts files ending with .json or .json.gz.
                     If a file extension isn't provided, the function will search first for a
                     .json file and if that doesn't exist, then a .json.gz file. If neither exists,
                     a FileNotFoundError will be raised or the function will return None,
                     depending on other input arguments.
                     
        convert_integer_keys -> Boolean. JSON files store all keys as strings, including numeric values.
                                If this argument is true, the function will attempt to convert all json
                                keys to integers before returning the data
                                
        error_if_missing -> Boolean. If true, a FileNotFound error is raised if the file cannot be found.
                            Otherwise the function returns None
    '''
    
    # Get a usable loading path, in case the provided path is missing an extension
    load_path = get_json_path(load_path, error_if_missing)
    if load_path is None:
        return None
    
    # Decide if we have to use gzip
    use_gzip = load_path.endswith(".json.gz")
    
    # Use gzip to unzip the json data before loading, if needed
    if use_gzip:
        with gzip.open(load_path, 'rt') as in_file:
            json_data = json.load(in_file)
    else:        
        with open(load_path, "r") as in_file:
            json_data = json.load(in_file)
    
    # JSON files cannot save numeric keys (but these are valid in python dictionaries). So convert if needed
    if convert_integer_keys:
        json_data = convert_integer_json_keys(json_data)
    
    return json_data

# .....................................................................................................................
    
def save_json(save_path, json_data, indent = 2, sort_keys = False, check_validity = False, use_gzip = False,
              create_missing_folder_path = False):
    
    '''
    Function which saves json files. Will automatically add ".json" or ".json.gz" extension, 
    depending on input arguments
    Inputs:
        save_path -> String. Path to where the json file should be saved. 
                     This is interpretted as a file path, even if no extension is provided!
                     
        json_data -> Dictionary. Data to be saved, must be valid json (e.g. use .tolist() on numpy arrays)
        
        indent -> None or Int. If none, data will be saved in a single line.
                  Otherwise it is pretty-printed, with nesting indenting spaces equal to this argument
                  
        sort_keys -> Boolean. If true, json_data keys will be sorted in storage.
        
        check_validity -> Boolean. If true, will first attempt to convert data to a string (within python)
                          This may fail (as a TypeError for example). This prevents the creation of an
                          invalid/incomplete json file, which would cause errors on loading otherwise.
                          However, this will have a detrimental effect on performance!
        
        use_gzip -> Boolean. If true, the json file will be compressed using gzip. 
                    Indenting and sorting arguments are ignored when compressing, along with using compact separators
        
        create_missing_folder_path -> Boolean. If true, the folder pathing to the given file will be checked,
                                      and if missing, will be created
    Outputs:
        actual_save_path
    '''
    
    # Build save path
    save_ext = ".json.gz" if use_gzip else ".json"
    modified_save_path = build_target_path(save_path, target_ext = save_ext)
    
    # Try converting to json to watch for errors, if needed
    if check_validity:
        _ = json.dumps(json_data)
    
    # Create the parent folder, if needed
    if create_missing_folder_path:
        parent_folder = os.path.dirname(modified_save_path)
        os.makedirs(parent_folder, exist_ok = True)
        
    # Use gzip compression if needed
    if use_gzip:
        with gzip.open(modified_save_path, "wt", encoding = "ascii") as out_file:
            json.dump(json_data, out_file, separators = (",", ":"))
    else:
        with open(modified_save_path, "w") as out_file:
            json.dump(json_data, out_file, indent = indent, sort_keys = sort_keys)
    
    return modified_save_path

# .....................................................................................................................

def update_json(save_path, new_json_data, indent = 2, sort_keys = False, check_validity = False, 
                convert_integer_keys = False):
    
    '''
    Function which will first (try to) load any existing json data at the save path, 
    and then merge the new data with existing json data. If a file does not already exist, this function
    will act as a saving function. 
    
    For help on input arguments, see the docstrings for the load_json(...) and save_json(...) functions!
    '''
    
    # Try to load existing data. If a file doesn't already exist, we'll assume it's empty data
    existing_data = {}
    load_path = get_json_path(save_path, error_if_missing = False)
    if load_path is not None:
        existing_data = load_json(load_path, convert_integer_keys)
    
    # Make sure the loaded data is a dictionary, since updated doesn't make sense otherwise!
    if type(existing_data) is not dict:
        raise TypeError("Existing data is not a dictionary! ({})".format(os.path.basename(save_path)))
    
    # Figure out if we need to save with gzip
    provided_path_is_plain_json = save_path.endswith(".json")
    provided_path_is_gzipped = save_path.endswith(".json.gz")
    gzip_path_exists = os.path.exists(build_target_path(save_path, target_ext = ".json.gz"))
    use_gzip = (provided_path_is_gzipped or gzip_path_exists) and not provided_path_is_plain_json
    
    # Replace existing data with new json data, and then re-save it
    updated_json = {**existing_data, **new_json_data}
    modified_save_path = save_json(save_path, updated_json, 
                                   indent = indent, 
                                   sort_keys = sort_keys, 
                                   check_validity = check_validity, 
                                   use_gzip = use_gzip)
    
    return modified_save_path, updated_json

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% CSV Functions

def save_csv_dict(save_path, data_dict, string_formatting_dict = None, fit_to_longest = False, use_gzip = False):
        
    '''
    Function which takes a dictionary of data label/data list key:value pairs and saves a csv file.
    The csv file will print each dictionary key at the top as a header string, with the corresponding data 
    saved as rows under each heading.
    
    Inputs:
        save_path -> String. Path to save csv file
        
        data_dict -> Dictionary. Keys should represent the label of a dataset, and corresponding values should
                     be lists of data to store as a single column.
                     
        string_formatting_dict -> Dictionary. Optionally, a string formatting dictionary can be provided to 
                                modify how data is formatted in the output. The dictionary should have keys
                                matching those found in data_dict, with values being string formatting entries,
                                For example, string_formatting_dict = {"some_data": "{:.3f}", "more_data": "{:.0f}"}
                                
        fit_to_longest -> If true, the csv file wil record up to the longest dataset, with shorter datasets being
                          left empty after they run out of data to store. If false, the csv file will store
                          data up to the shortest dataset
                          
        use_gzip -> If true, the csv file will be compressed with gzip (and have a '.csv.gz' extension)
        
    Outputs:
        save_path -> String. Full path to where the file was saved (including any file ext modifications)
    '''
    
    # Build save path
    save_ext = ".csv.gz" if use_gzip else ".csv"
    modified_save_path = build_target_path(save_path, target_ext = save_ext)
    
    # Set up different file opening arguments, depending on gzip usage
    open_args = {"mode": "wt" if use_gzip else "w",
                 "encoding": "ascii" if use_gzip else None}
    open_func = gzip.open if use_gzip else open
    
    # Build the header for the csv file
    header_strs = sorted(list(data_dict.keys()))
    
    # Get the length of each dataset to help with printout indexing and to figure out how many rows to print
    length_lut = {each_label: len(each_data) for each_label, each_data in data_dict.items()}
    num_rows = max(length_lut.values()) if fit_to_longest else min(length_lut.values())
    
    # Create complete string formatting dictionary, in case there are missing entries
    format_lut = {each_label: "{}" for each_label in header_strs}
    format_lut.update(string_formatting_dict if string_formatting_dict is not None else {})
    print("FORMAT LUT:", format_lut)
    
    # Some helper functions for accessing & string formatting the data
    get_data = lambda label, idx: data_dict.get(label)[idx] if length_lut.get(label) >= 1 + idx else ""
    str_format = lambda label, value: format_lut.get(label).format(value)
    str_data = lambda label, idx: str_format(label, get_data(label, idx))
    
    # Write the csv file!
    with open_func(modified_save_path, **open_args) as csv_file:
        
        # Create the csv writing object and write the first row (heading strings)
        csv_writer = csv.writer(csv_file)
        csv_writer.writerow(header_strs)
        
        # Look through every data index, and write a (string) entry for each data set
        for data_idx in range(num_rows):
            row_strs = [str_data(each_label, data_idx) for each_label in header_strs]
            csv_writer.writerow(row_strs)
            
    return modified_save_path

# .....................................................................................................................

def save_csv_list(save_path, data_list, header_label = None, string_formatting = "{}", use_gzip = False):
    
    '''
    Function which takes a list of data values (and optionally a header label) 
    and writes a csv file, with rows of entries for each entry in the input data_list
    '''
    
    # Build save path
    save_ext = ".csv.gz" if use_gzip else ".csv"
    modified_save_path = build_target_path(save_path, target_ext = save_ext)
    
    # Set up different file opening arguments, depending on gzip usage
    open_args = {"mode": "wt" if use_gzip else "w",
                 "encoding": "ascii" if use_gzip else None}
    open_func = gzip.open if use_gzip else open
    
    # Write the csv file!
    with open_func(modified_save_path, **open_args) as csv_file:
        
        # Create the csv writing object and write the first row (heading string) if needed
        csv_writer = csv.writer(csv_file)        
        if header_label is not None:
            csv_writer.writerow(header_label)
        
        # Look through every data value and write a (string) entry for each row
        for each_value in data_list:
            data_str = string_formatting.format(each_value)
            csv_writer.writerow(data_str)
            
    return modified_save_path

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Demo

if __name__ == "__main__":
    
    pass

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap

