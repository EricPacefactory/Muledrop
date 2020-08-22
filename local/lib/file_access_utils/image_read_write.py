#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu May 21 17:19:38 2020

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


# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes


# ---------------------------------------------------------------------------------------------------------------------
#%% Define encode/decode functions

# .....................................................................................................................

def encode_png_data(image_data, png_compression_0_to_9):
    
    # Build the (somewhat obscure) png compression argument
    png_params = (cv2.IMWRITE_PNG_COMPRESSION, png_compression_0_to_9)
    _, encoded_png_data = cv2.imencode(".png", image_data, png_params)
    
    return encoded_png_data

# .....................................................................................................................

def encode_jpg_data(image_data, jpg_quality_0_to_100):
    
    # Encode image data for saving
    jpg_params = (cv2.IMWRITE_JPEG_QUALITY, jpg_quality_0_to_100)
    _, encoded_jpg_data = cv2.imencode(".jpg", image_data, jpg_params)
    
    return encoded_jpg_data

# .....................................................................................................................

def decode_image_data(encoded_image_data):
    
    ''' Simple helper function which wraps around cv2.imdecode. Assuming color image data. Works for jpg or png '''
    
    return cv2.imdecode(encoded_image_data, cv2.IMREAD_COLOR)

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Define writing functions

# .....................................................................................................................

def _write_encoded_image_data(save_folder_path, save_name_no_ext, file_extension, encoded_image_data):
    
    ''' Generic function used to write encoded image data to disk '''
    
    save_name = "{}{}".format(save_name_no_ext, file_extension)
    save_path = os.path.join(save_folder_path, save_name)
    with open(save_path, "wb") as out_file:
        out_file.write(encoded_image_data)
    
    return save_path

# .....................................................................................................................

def write_encoded_jpg(save_folder_path, save_name_no_ext, encoded_jpg_data):
    return _write_encoded_image_data(save_folder_path, save_name_no_ext, ".jpg", encoded_jpg_data)

# .....................................................................................................................

def write_encoded_png(save_folder_path, save_name_no_ext, encoded_png_data):
    return _write_encoded_image_data(save_folder_path, save_name_no_ext, ".png", encoded_png_data)

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Define reading functions

# .....................................................................................................................

def _read_encoded_image_data(load_folder_path, load_name_no_ext, file_extension):
    
    ''' Generic function used to read encoded image data from disk '''
    
    # Build load path and get the image data
    load_name = "{}{}".format(load_name_no_ext, file_extension)
    load_path = os.path.join(load_folder_path, load_name)
    with open(load_path, "rb") as in_file:
        encoded_image_bytes = in_file.read()
    
    # Convert to numpy array so we can manipulate the data using opencv
    encoded_image_data = np.frombuffer(encoded_image_bytes, dtype = np.uint8)
    
    # Note:
    # This approach of using 'with open(...)' followed by numpy conversion is
    # (surprisingly) faster than using the more direct: np.fromfile(...)
    # not sure why?
    
    return encoded_image_data

# .....................................................................................................................

def read_encoded_jpg(load_folder_path, load_name_no_ext):
    return _read_encoded_image_data(load_folder_path, load_name_no_ext, ".jpg")

# .....................................................................................................................

def read_encoded_png(load_folder_path, load_name_no_ext):
    return _read_encoded_image_data(load_folder_path, load_name_no_ext, ".png")

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Define composite functions

# .....................................................................................................................

def save_png_image(save_folder_path, save_name_no_ext, image_data, png_compression_0_to_9 = 0):
    
    '''
    Helper function which just combines encoding/writing of image data in png format.
    Acts the same as cv2.imwrite(...), but makes use of separate encode/write steps,
    so that there is some consistency with (threaded) systems that may perform these steps at different times
    '''
    
    encoded_data = encode_png_data(image_data, png_compression_0_to_9)
    save_path = write_encoded_png(save_folder_path, save_name_no_ext, encoded_data)
    
    return save_path

# .....................................................................................................................

def save_jpg_image(save_folder_path, save_name_no_ext, image_data, jpg_quality_0_to_100 = 85):
    
    '''
    Helper function which just combines encoding/writing of image data in jpg format.
    Acts the same as cv2.imwrite(...), but makes use of separate encode/write steps,
    so that there is some consistency with (threaded) systems that may perform these steps at different times
    '''
    
    encoded_data = encode_jpg_data(image_data, jpg_quality_0_to_100)
    save_path = write_encoded_jpg(save_folder_path, save_name_no_ext, encoded_data)
    
    return save_path

# .....................................................................................................................

def load_png_image(load_folder_path, load_name_no_ext):
    
    '''
    Helper function which combines reading/decoding of image data in png format
    Acts the same as cv2.imread(...), but makes use of separate read/decode steps,
    so that there is some consistency with (threaded) systems that may perform these steps at different times
    '''
    
    encoded_data = read_encoded_png(load_folder_path, load_name_no_ext)
    png_image = decode_image_data(encoded_data)
    
    return png_image

# .....................................................................................................................

def load_jpg_image(load_folder_path, load_name_no_ext):
    
    '''
    Helper function which combines reading/decoding of image data in jpg format
    Acts the same as cv2.imread(...), but makes use of separate read/decode steps,
    so that there is some consistency with (threaded) systems that may perform these steps at different times
    '''
    
    encoded_data = read_encoded_jpg(load_folder_path, load_name_no_ext)
    jpg_image = decode_image_data(encoded_data)
    
    return jpg_image

# .....................................................................................................................
# .....................................................................................................................
        

# ---------------------------------------------------------------------------------------------------------------------
#%% Demo

if __name__ == "__main__":
    pass


# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap


