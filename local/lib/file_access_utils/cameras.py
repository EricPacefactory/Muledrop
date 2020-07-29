#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Jul 21 16:30:57 2020

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

from local.lib.file_access_utils.shared import build_camera_path, copy_from_defaults
from local.lib.file_access_utils.video import check_valid_rtsp_ip

from local.eolib.utils.files import create_folder_structure_from_dictionary, get_folder_list


# ---------------------------------------------------------------------------------------------------------------------
#%% Folder structures

# .....................................................................................................................

def camera_folder_structure():
    
    structure = {
                 "report": {"images", "metadata"},
                 "config": {"after_database", "externals", "core"},
                 "resources": {"videos": {},
                               "backgrounds": {"captures", "generated"},
                               "classifier": {"datasets", "models"}},
                 "logs": {"system", "configurables"}
                 }
    
    return structure

# .....................................................................................................................

def create_camera_folder_structure(project_root_path, location_select_folder_path, camera_select,
                                   default_select = None):
    
    ''' Function which creates the base camera folder structure with required (default) files, if missing '''
    
    # Make sure the base camera folder is created
    camera_path = build_camera_path(location_select_folder_path, camera_select)
    os.makedirs(camera_path, exist_ok = True)
    
    # Build out the rest of the camera folder structure
    camera_folder_structure_dict = camera_folder_structure()
    create_folder_structure_from_dictionary(camera_path, camera_folder_structure_dict)
    
    # Make sure default files are present
    copy_from_defaults(project_root_path, location_select_folder_path, camera_select, default_select)

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Helper functions

# .....................................................................................................................

def build_camera_list(location_select_folder_path, show_hidden_cameras = False, must_have_rtsp = False):
    
    ''' Function which returns all camera names & corresponding folder paths '''
    
    # Find all the camera folders within the 'cameras' folder
    camera_path_list = get_folder_list(location_select_folder_path,
                                       show_hidden_folders = show_hidden_cameras,
                                       create_missing_folder = False,
                                       return_full_path = True)
    camera_name_list = [os.path.basename(each_path) for each_path in camera_path_list]
    
    # Filter out cameras that don't have valid RTSP configs
    if must_have_rtsp:
        
        # Keep only the camera entries that have valid rtsp ip addresses
        filtered_name_list = []
        filtered_path_list = []
        for each_camera_name, each_camera_path in zip(camera_name_list, camera_path_list):
            is_valid_rtsp_ip = check_valid_rtsp_ip(location_select_folder_path, each_camera_name)
            if is_valid_rtsp_ip:
                filtered_name_list.append(each_camera_name)
                filtered_path_list.append(each_camera_path)
        
        # Overwrite existing outputs
        camera_name_list = filtered_name_list
        camera_path_list = filtered_path_list
    
    return camera_name_list, camera_path_list

# .....................................................................................................................

def check_for_existing_camera_name(location_select_folder_path, camera_select,
                                   show_hidden_cameras = True, must_have_rtsp = False):
    
    ''' Helper function used to check if a camera name already exists '''
    
    # Get list of existing camera names
    existing_camera_names_list, _ = build_camera_list(location_select_folder_path,
                                                      show_hidden_cameras = show_hidden_cameras,
                                                      must_have_rtsp = must_have_rtsp)
    
    # Check if the target camera already exists in the list of names
    camera_already_exists = (camera_select in existing_camera_names_list)
    
    return camera_already_exists

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Demo

if __name__ == "__main__":
    
    pass

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap


