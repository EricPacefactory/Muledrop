#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Jun  3 14:45:22 2020

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
#%% Classes

# .....................................................................................................................

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% General functions

# .....................................................................................................................

def max_dimension_downscale(frame_wh, max_dimension_px):
    
    '''
    Function used to calculate the (fixed aspect ratio) frame sizing
    where the largest side of the frame is max_dimension_px pixels in length
    
    For example, if given inputs:
        frame_wh = (1280, 720)
        max_dimension_px = 640
    
    Then returns:
        needs_downscaling = True, downscale_wh = (640, 360)
    '''
    
    # First figure out how much we would need to independently scale sides to acheive max dimension length
    frame_width, frame_height = frame_wh
    width_rescale_factor = max_dimension_px / frame_width
    height_rescale_factor = max_dimension_px / frame_height
    
    # Now pick the larger of the two scaling factors and calculate the resulting downscaled size
    shared_rescale_factor = min(1.0, width_rescale_factor, height_rescale_factor)
    downscale_width = int(round(shared_rescale_factor * frame_width))
    downscale_height = int(round(shared_rescale_factor * frame_height))
    downscale_wh = (downscale_width, downscale_height)

    # Finally, decide where downscaling is actually needed (i.e. in case the input frame is already small enough)
    needs_downscaling = (shared_rescale_factor < 1.0)
    
    return needs_downscaling, downscale_wh

# .....................................................................................................................

def scale_factor_downscale(frame_wh, scale_factor):
    
    ''' 
    Function used to calculate the (fixed aspect ratio) frame sizing
    given an input size and scaling factor (i.e. pre-calculate scaled down pixel values)
    Handles conversion to (rounded) integer values as well
    
    Inputs:
        frame_wh -> (Tuple) The input width/height of the video/frame
        
        scale_factor -> (Float) The amount to scale by, as a number between 0.0 and 1.0 
                        Will also accept other float values, though negative nubmers or numbers greater than 1
                        should be avoided
    
    Outputs:
        scaled_wh
    '''
    
    # Calculate the rounded integer dimensions after applying scale factor
    frame_width, frame_height = frame_wh
    scaled_width = int(round(frame_width * scale_factor))
    scaled_height = int(round(frame_height * scale_factor))
    
    return (scaled_width, scaled_height)

# .....................................................................................................................

def blank_frame_from_frame_wh(frame_wh):
    
    '''
    Helper function which returns a blank single-channel frame matching a given frame_wh (width, height) value
    
    Inputs:
        frame_wh -> (Tuple of integers) The target width/height of the output frame
    
    Outputs:
        blank_frame  (uint8 format image, single channel)
    '''
    
    return np.zeros((frame_wh[1], frame_wh[0]), dtype=np.uint8)

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Demo

if __name__ == "__main__":
    
    pass

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap


