#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Sep 11 15:12:18 2019

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

from shutil import rmtree

from local.lib.file_access_utils.threaded_read_write import Threaded_PNG_Saver
from local.lib.file_access_utils.threaded_read_write import Nonthreaded_PNG_Saver

from local.eolib.utils.files import get_file_list_by_age

# ---------------------------------------------------------------------------------------------------------------------
#%% Classes


class Background_Resources_Data_Saver:
    
    '''
    Helper class which simply selects between different types (e.g. threaded/non-threaded) of saving
    implementation for background resource data. Also handles save pathing.
    Note this class is also responsible for enabling/disabling saving
    '''
    
    # .................................................................................................................
    
    def __init__(self, location_select_folder_path, camera_select,
                 saving_enabled = True, threading_enabled = True):
        
        # Store inputs
        self.location_select_folder_path = location_select_folder_path
        self.camera_select = camera_select
        self.saving_enabled = saving_enabled
        self.threading_enabled = threading_enabled
        
        # Build saving path
        self.image_save_folder_path = build_background_capture_folder_path(location_select_folder_path, camera_select)
        
        # Initialize saver object & pathing as needed
        self._data_saver = None
        if self.saving_enabled:
            
            # Make sure the save folder exists
            os.makedirs(self.image_save_folder_path, exist_ok = True)
            
            # Select between different types of saving implementations
            if self.threading_enabled:
                self._data_saver = Threaded_PNG_Saver(thread_name = "backgrounds-captures",
                                                      png_folder_path = self.image_save_folder_path)
            else:
                self._data_saver = Nonthreaded_PNG_Saver(png_folder_path = self.image_save_folder_path)
        
        pass
    
    # .................................................................................................................
    
    def save_data(self, *, file_save_name_no_ext, image_data, png_compression_0_to_9 = 0):
        
        # Only save data if enabled
        if self.saving_enabled:
            self._data_saver.save_data(file_save_name_no_ext, image_data, png_compression_0_to_9)
        
        return
    
    # .................................................................................................................
    
    def close(self):
        
        # Close data saver if needed
        if self.saving_enabled:
            self._data_saver.close()
        
        return
    
    # .................................................................................................................
    # .................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Load & Save functions

# .....................................................................................................................

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% General pathing functions

# .....................................................................................................................

def build_base_resources_path(location_select_folder_path, camera_select, *path_joins):
    ''' Build path to base resources folder for a given camera '''
    return os.path.join(location_select_folder_path, camera_select, "resources", *path_joins)

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Pathing functions

# .....................................................................................................................

def build_background_capture_folder_path(location_select_folder_path, camera_select):    
    return build_base_resources_path(location_select_folder_path, camera_select, "backgrounds", "captures")

# .....................................................................................................................

def build_background_generate_folder_path(location_select_folder_path, camera_select):
    return build_base_resources_path(location_select_folder_path, camera_select, "backgrounds", "generated")

# .....................................................................................................................

def reset_capture_folder(location_select_folder_path, camera_select):
    
    # Build path to captures folder, delete it, then remake it
    capture_folder_path = build_background_capture_folder_path(location_select_folder_path, camera_select)
    if os.path.exists(capture_folder_path):
        rmtree(capture_folder_path)
    os.makedirs(capture_folder_path, exist_ok = True)
    
    return capture_folder_path

# .....................................................................................................................

def reset_generate_folder(location_select_folder_path, camera_select):
    
    # Build path to generate folder, delete it, then remake it
    generate_folder_path = build_background_generate_folder_path(location_select_folder_path, camera_select)
    if os.path.exists(generate_folder_path):
        rmtree(generate_folder_path)
    os.makedirs(generate_folder_path, exist_ok = True)
    
    return generate_folder_path

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% File i/o functions

# .....................................................................................................................

def save_captured_image(location_select_folder_path, camera_select, image_data,
                        image_index = 0, png_compression_0_to_9 = 0):
    
    # Build save path
    save_folder_path = build_background_capture_folder_path(location_select_folder_path, camera_select)
    save_name = "{}.png".format(image_index) 
    save_path = os.path.join(save_folder_path, save_name)
    
    png_params = (cv2.IMWRITE_PNG_COMPRESSION, png_compression_0_to_9)
    cv2.imwrite(save_path, image_data, png_params)

# .....................................................................................................................

def save_generated_image(location_select_folder_path, camera_select, image_data,
                         image_index = 0, png_compression_0_to_9 = 0):
    
    # Build save path
    save_folder_path = build_background_generate_folder_path(location_select_folder_path, camera_select)
    save_name = "{}.png".format(image_index) 
    save_path = os.path.join(save_folder_path, save_name)
    
    png_params = (cv2.IMWRITE_PNG_COMPRESSION, png_compression_0_to_9)
    cv2.imwrite(save_path, image_data, png_params)

# .....................................................................................................................

def load_newest_generated_background(location_select_folder_path, camera_select,
                                     error_if_no_backgrounds = True):
    
    '''
    Function which loads the newest available background image for a given camera
    By default if no background is available, a FileNotFound error will be raised
    If erroring is disabled (through function args), then a 'None' value will be return if no background exists
    '''
    
    # First build pathing to the generated backgrounds folder & list out all the available files
    load_folder_path = build_background_generate_folder_path(location_select_folder_path, camera_select)
    _, background_file_paths = get_file_list_by_age(load_folder_path,
                                                    newest_first = True,
                                                    show_hidden_files = False,
                                                    create_missing_folder = True,
                                                    return_full_path = True,
                                                    allowable_exts_list = [".png", ".jpg"])
    
    # Make sure some files exist before trying to load the newest one
    num_background_files = len(background_file_paths)
    if num_background_files == 0:
        if error_if_no_backgrounds:
            raise FileNotFoundError("No background image data was found!")
        return None
    
    # If we get here, we should be safe to load the newest image file
    newest_file_path = background_file_paths[0]
    newest_background_image = cv2.imread(newest_file_path)
    
    return newest_background_image

# .....................................................................................................................

def load_background_captures_iter(location_select_folder_path, camera_select):
    
    '''
    Function which returns an iterator that will load the capture data, newest first, for a given camera
    Note that because this function returns an iterator, the image data won't be immediately available until
    the iterator has been 'consumed' (which can be done immediately by converting it to a list, for example).
    Keep in mind that loading many frames into memory all at once may consume a large amount of RAM!
    
    Also note that new captures may be saved (and old ones overwritten) if loading is performed 'too slowly'!!!
    
    Inputs:
        location_select_folder_path --> (String) Folder containing data for all cameras for the selected location
        
        camera_select --> (String) The specific camera to load capture data from
        
    Outputs:
        number_of_captures --> (Integer) The number of capture files available
        
        capture_image_iter --> (Generator of np.array data) A generator that yeilds capture image data
    '''
    
    # Get all of the capture image file paths
    load_folder_path = build_background_capture_folder_path(location_select_folder_path, camera_select)
    _, capture_file_paths = get_file_list_by_age(load_folder_path,
                                                 newest_first = True,
                                                 show_hidden_files = False,
                                                 create_missing_folder = True,
                                                 return_full_path = True,
                                                 allowable_exts_list = [".png"])
    
    # Build outputs
    number_of_captures = len(capture_file_paths)
    capture_image_iter = _load_image_generator(capture_file_paths)
    
    return number_of_captures, capture_image_iter

# .....................................................................................................................

def load_background_generates_iter(location_select_folder_path, camera_select):
    
    '''
    Function which returns an iterator that will load existing generated background data,
    newest first, for a given camera
    Note that because this function returns an iterator, the image data won't be immediately available until
    the iterator has been 'consumed' (which can be done immediately by converting it to a list, for example).
    Keep in mind that loading many frames into memory all at once may consume a large amount of RAM!
    
    Inputs:
        location_select_folder_path --> (String) Folder containing data for all cameras for the selected location
        
        camera_select --> (String) The specific camera to load capture data from
        
    Outputs:
        number_of_generates --> (Integer) The number of generated files available
        
        generate_image_iter --> (Generator of np.array data) A generator that yeilds generated image data
    '''
    
    # Get all of the generated image file paths
    load_folder_path = build_background_generate_folder_path(location_select_folder_path, camera_select)
    _, generate_file_paths = get_file_list_by_age(load_folder_path,
                                                  newest_first = True,
                                                  show_hidden_files = False,
                                                  create_missing_folder = True,
                                                  return_full_path = True,
                                                  allowable_exts_list = [".png"])
    
    # Build outputs
    number_of_generates = len(generate_file_paths)
    generate_image_iter = _load_image_generator(generate_file_paths)
    
    return number_of_generates, generate_image_iter

# .....................................................................................................................

def _load_image_generator(image_file_paths):
    
    ''' Simple generator for loading image data '''
    
    for each_path in image_file_paths:
        yield cv2.imread(each_path)
    
    return

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Demo

if __name__ == "__main__":
    
    example_location_select_folder_path = "/path/to/nowhere"
    example_camera_select = "fake_camera"
    print("",
          "Example resource folder path:",
          build_base_resources_path(example_location_select_folder_path, example_camera_select),
          sep = "\n")

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap


