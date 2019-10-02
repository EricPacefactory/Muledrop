#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Apr 10 10:56:40 2019

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

import numpy as np


# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes


# ---------------------------------------------------------------------------------------------------------------------
#%% Define general functions

# .....................................................................................................................

def avoid_missing_output_wh(input_wh, output_w, output_h, max_side_length = 800):
    
    # Prevent output from being too large
    largest_side_input = max(input_wh)
    largest_side_display = min(max_side_length, largest_side_input) 
    output_scale = largest_side_display / largest_side_input
    
    # Set output based on 'suggested' output size
    suggested_out_w = int(round(input_wh[0] * output_scale))
    suggested_out_h = int(round(input_wh[1] * output_scale))
    
    fixed_output_w = suggested_out_w if output_w is None else output_w
    fixed_output_h = suggested_out_h if output_h is None else output_h
    
    return fixed_output_w, fixed_output_h

# .....................................................................................................................

def constrain_property(obj_ref, property_name, min_value, max_value, 
                       error_if_none = True):
    
    # Get the current value of the property
    var_value = getattr(obj_ref, property_name)
    
    # Handle non-values
    if var_value is None:
        if error_if_none:
            raise ValueError("Variable {} cannot be clipped, because it has no value!".format(property_name))
        return
    
    # Apply min/maxing depending one which boundaries are present ('None' is valid for min/max)
    clipped_val = np.clip(var_value, min_value, max_value)
    setattr(obj_ref, property_name, clipped_val)

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Demo
    
if __name__ == "__main__":
    pass
    

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap


