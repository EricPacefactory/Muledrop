#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat May 11 11:27:09 2019

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

from local.lib.file_access_utils.shared import build_resources_folder_path
from local.lib.file_access_utils.shared import load_from_defaults, load_or_create_json, full_replace_save
from local.lib.file_access_utils.shared import copy_from_defaults
from local.lib.file_access_utils.externals import build_externals_folder_path

from eolib.utils.files import get_file_list_by_age

# ---------------------------------------------------------------------------------------------------------------------
#%% Pathing functions

# .....................................................................................................................

def build_bgcap_config_file_path(cameras_folder, camera_select, user_select, 
                           config_file_name = "background_capture.json"):  
    return build_externals_folder_path(cameras_folder, camera_select, user_select, config_file_name)

# .....................................................................................................................

def build_captures_folder_path(cameras_folder, camera_select):
    return build_resources_folder_path(cameras_folder, camera_select, "background", "captures")

# .....................................................................................................................

def build_generated_folder_path(cameras_folder, camera_select):
    return build_resources_folder_path(cameras_folder, camera_select, "background", "generated")

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Config functions

# .....................................................................................................................
    
def create_default_bg_capture_config(project_root_path, user_path, overwrite_existing = True):
    
    # Pull out the default json configs from the external folder and copy into the user path
    copy_from_defaults(project_root_path, 
                       target_defaults_folder = "externals",
                       copy_to_path = user_path)

# .....................................................................................................................

def load_bg_capture_config(project_root_path, cameras_folder, camera_select, user_select):
    
    # Get pathing to the background capture config file
    bg_capture_config_file_path = build_bgcap_config_file_path(cameras_folder, camera_select, user_select)
    
    # Set default config data
    default_bg_config = load_from_defaults(project_root_path, "externals", "background_capture.json")
    
    # If the file doesn't exist, create an empty file and 'load' it
    bg_config = load_or_create_json(bg_capture_config_file_path, 
                                    default_bg_config, 
                                    creation_printout = "Creating background capture config:")
    
    return bg_config

# .....................................................................................................................

def save_bg_capture_config(cameras_folder, camera_select, user_select, script_name, class_name, config_data):
    
    # Get pathing to the background capture config file
    bg_capture_config_file_path = build_bgcap_config_file_path(cameras_folder, camera_select, user_select)
    
    # Build the data structure for background capture config data
    save_data = {"access_info": {"script_name": script_name,
                                 "class_name": class_name},
                 "setup_data": config_data}
    
    # Fully overwrite the existing config
    full_replace_save(bg_capture_config_file_path, save_data)
    
    return bg_capture_config_file_path

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%%% Image file io
    
# .....................................................................................................................

def load_newest_image(image_folder_path):
    
    # Get a list of the files sorted by age
    sorted_ages, sorted_paths = get_file_list_by_age(image_folder_path, return_full_path = True)
    
    # Allocate outputs
    load_success, img_data = False, None
    
    # Go through each file (newest first) and try to load the image data, until we're successful
    for each_path in sorted_paths:
        
        try:
            img_data = cv2.imread(each_path)        # Can return None without throwing an error!
            load_success = (img_data is not None)
        except:
            load_success = False
        
        # If the file was loaded without errors, we're done!
        if load_success:
            break
    
    return load_success, img_data
    
# .....................................................................................................................

def save_background_image_png(image_folder_path, file_save_name, image_data, compression_level = 0):
    
    # Build file save pathing
    save_file_name = "".join([file_save_name, ".png"])
    save_file_path = os.path.join(image_folder_path, save_file_name)
    
    # Save the background image file 
    # (for 1280x720, testing: takes ~ 50ms for png compression 0, 750ms for png compression 9!)
    cv2.imwrite(save_file_path, image_data, (cv2.IMWRITE_PNG_COMPRESSION, compression_level))
    
    return save_file_path

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap
