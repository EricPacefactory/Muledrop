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

def adjust_aspect_ratio(input_wh, ar_adjustment_factor):
    
    '''
    Function which generates an output width/height value 
    from an input width/height and 'aspect ratio adjustment factor'
    
    The adjustment factor is interpretted as a modification to the original aspect ratio, as follows:
    - If set to +1.0, should return a frame with the same aspect ratio as the input
    - If set to 0.0, should return a frame with square shape (i.e. aspect ratio = 1/1)
    - If set to -1.0, should return a frame with an inverted aspect ratio as the input
    - If set to +/- 2.5 (for example) should return 2.5 * aspect-ratio (or inverted ar, if negative)
    '''
    
    # Get input sizing
    input_w, input_h = input_wh
    input_area = input_w * input_h
    input_ratio = input_w / input_h
    
    # Scale input aspect ratio according to special AR interpretation above
    adjustment_is_positive = (ar_adjustment_factor >= 0.0)
    new_ratio = (abs(ar_adjustment_factor) * (input_ratio - 1.0)) + 1.0
    adjusted_ar = new_ratio if adjustment_is_positive else (1.0 / new_ratio)
    
    # Calculate output sizing using adjusted aspect-ratio
    adjusted_w = np.sqrt(input_area * adjusted_ar)
    adjusted_h = input_area / adjusted_w
    adjusted_wh = (int(round(adjusted_w)), int(round(adjusted_h)))
    
    # Decide whether the adjustment is needed (could check if factor == 1.0, but for numerically stability, check sizes)
    width_needs_adjustment = (input_w != adjusted_wh[0])
    height_needs_adjustment = (input_h != adjusted_wh[1])
    needs_ar_adjustment = (width_needs_adjustment or height_needs_adjustment)
    
    return needs_ar_adjustment, adjusted_wh    
    
# .....................................................................................................................

def max_dimension_downscale(input_wh, max_dimension_px):
    
    '''
    Function used to calculate the (fixed aspect ratio) frame sizing
    where the largest side of the frame is max_dimension_px pixels in length
    
    For example, if given inputs:
        input_wh = (1280, 720)
        max_dimension_px = 640
    
    Then returns:
        needs_downscaling = True, downscale_wh = (640, 360)
    '''
    
    # First figure out how much we would need to independently scale sides to acheive max dimension length
    input_width, input_height = input_wh
    width_rescale_factor = max_dimension_px / input_width
    height_rescale_factor = max_dimension_px / input_height
    
    # Now pick the larger of the two scaling factors and calculate the resulting downscaled size
    shared_rescale_factor = min(1.0, width_rescale_factor, height_rescale_factor)
    downscale_width = int(round(shared_rescale_factor * input_width))
    downscale_height = int(round(shared_rescale_factor * input_height))
    downscale_wh = (downscale_width, downscale_height)

    # Finally, decide where downscaling is actually needed (i.e. in case the input frame is already small enough)
    needs_downscaling = (shared_rescale_factor < 1.0)
    
    return needs_downscaling, downscale_wh

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Demo
    
if __name__ == "__main__":
    pass
    

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap


