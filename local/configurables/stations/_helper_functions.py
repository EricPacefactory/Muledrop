#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Jun 30 14:40:12 2020

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

import cv2
import numpy as np

from local.lib.ui_utils.display_specification import Display_Window_Specification

from local.eolib.video.imaging import crop_y1y2x1x2_from_zones_list, make_cropmask_1ch, image_to_channel_column_vector


# ---------------------------------------------------------------------------------------------------------------------
#%% Define configuration displays




# ---------------------------------------------------------------------------------------------------------------------
#%% Define crop helpers

# .....................................................................................................................

def inmask_pixels_1ch(frame_1ch, mask_logical_1ch):
    
    '''
    Function which applies a mask to a single-channel frame and returns only the masked-in values
    This is useful when doing stats-based calculations on the pixels,
    since it avoids including the masked off values in the calculation.
    
    Note however that because the masked-off pixels are removed, 
    the output is not suitable for any processing requiring spatial information!
    
    Inputs:
        frame_1ch -> (Image Data/Numpy array) A single-channel (e.g. grayscale) frame
        
        mask_logical_1ch -> (Numpy array) A single-channel logical mask to apply to the given frame.
                            Areas that should be kept (i.e. 'mask-in') should have values of True/1,
                            while areas to mask out should have values of False/0
    
    Outputs:
        inmask_pixels_1d_array (numpy array)
    
    Note: The shape of the output will be M x 1, where M is the number of mask-in pixels
    '''
    
    # First convert the input frame to 1d data
    frame_1d = np.ravel(frame_1ch)
    
    # Now use logical mask to index only the in-mask pixels
    inmask_pixels_1d_array = frame_1d[mask_logical_1ch]
    
    return inmask_pixels_1d_array

# .....................................................................................................................

def inmask_pixels_3ch(frame_3ch, mask_logical_1ch):
    
    '''
    Function which applies a mask to a 3-channel frame and returns only the masked-in values
    This is useful when doing stats-based calculations on the pixels,
    since it avoids including the masked off values in the calculation.
    
    Note however that because the masked-off pixels are removed, 
    the output is not suitable for any processing requiring spatial information!
    
    Inputs:
        frame_3ch -> (Image Data/Numpy array) A 3-channel (e.g. color) frame
        
        mask_logical_1ch -> (Numpy array) A single-channel logical mask to apply to the given frame.
                            Areas that should be kept (i.e. 'mask-in') should have values of True/1,
                            while areas to mask out should have values of False/0
    
    Outputs:
        inmask_pixels_1d_array (numpy array)
        
    Note: The shape of the output will be M x 3, where M is the number of mask-in pixels
    '''
    
    # First convert the input frame to 1d data
    num_pixels = np.prod(frame_3ch.shape[0:2])
    frame_1d = np.reshape(frame_3ch, (num_pixels, 3))
    
    # Now use logical mask to index only the in-mask pixels
    inmask_pixels_1d_array = frame_1d[mask_logical_1ch]
    
    return inmask_pixels_1d_array

# .....................................................................................................................

def build_cropping_dataset(frame_wh, station_zones_list):
    
    # Get cropping co-ordinates
    crop_y1y2x1x2_list, _ = crop_y1y2x1x2_from_zones_list(frame_wh,
                                                          station_zones_list,
                                                          zones_are_normalized = True,
                                                          error_if_no_zones = False)
    
    # Get 2D & logical 1D cropmask data
    cropmask_2d_list = []
    logical_cropmask_1d_list = []
    for each_crop_y1y2x1x2, each_zone in zip(crop_y1y2x1x2_list, station_zones_list):
        
        # Generate the single-channel 2d cropmasks
        cropmask_1ch = make_cropmask_1ch(frame_wh, each_zone, each_crop_y1y2x1x2)
        cropmask_2d_list.append(cropmask_1ch)
        
        # From the 2d cropmasks, generate the 1d logical cropmasks
        cropmask_1ch_as_col_vector = image_to_channel_column_vector(cropmask_1ch)
        logical_cropmask_1d = (cropmask_1ch_as_col_vector[:,0] > 127)
        logical_cropmask_1d_list.append(logical_cropmask_1d)
    
    return crop_y1y2x1x2_list, cropmask_2d_list, logical_cropmask_1d_list

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Demo
    
if __name__ == "__main__":
    pass
    

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap


