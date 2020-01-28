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

from local.lib.file_access_utils.threaded_read_write import Image_Saver, Metadata_Saver, Image_Loader

# ---------------------------------------------------------------------------------------------------------------------
#%% Classes


# =====================================================================================================================
# =====================================================================================================================

class Image_Resources_Loader(Image_Loader):
    
    # .................................................................................................................
    
    def __init__(self, cameras_folder_path, camera_select, user_select, *folder_paths,
                 lock = None):   
        
        # Store image folder name, so we create the proper pathing on initialization
        self.folder_paths = folder_paths
        
        # Inherit from base class
        super().__init__(cameras_folder_path, camera_select, user_select,
                         saving_enabled = True,
                         create_load_folder_if_missing = True,
                         threading_enabled = True,
                         lock = lock)

    # .................................................................................................................
    
    def _build_data_folder_path(self):   
        return build_base_resources_path(self.cameras_folder_path, self.camera_select, *self.folder_paths)
    
    # .................................................................................................................
    # .................................................................................................................


# =====================================================================================================================
# =====================================================================================================================

class Image_Resources_Saver(Image_Saver):
    
    # .................................................................................................................
    
    def __init__(self, cameras_folder_path, camera_select, user_select, *folder_paths,
                 lock = None):
        
        # Store image folder name, so we create the proper pathing on initialization
        self.folder_paths = folder_paths
        
        # Inherit from base class
        super().__init__(cameras_folder_path, camera_select, user_select,
                         saving_enabled = True,
                         create_save_folder_if_missing = True,
                         threading_enabled = True,
                         lock = lock)

    # .................................................................................................................
    
    def _build_data_folder_path(self):   
        return build_base_resources_path(self.cameras_folder_path, self.camera_select, *self.folder_paths)
    
    # .................................................................................................................
    # .................................................................................................................
    
# =====================================================================================================================
# =====================================================================================================================

class Metadata_Resources_Saver(Metadata_Saver):
    
    # .................................................................................................................
    
    def __init__(self, cameras_folder_path, camera_select, user_select, *folder_paths,
                 lock = None):
        
        # Store image folder name, so we create the proper pathing on initialization
        self.folder_paths = folder_paths
        
        # Inherit from base class
        super().__init__(cameras_folder_path, camera_select, user_select,
                         saving_enabled = True,
                         create_save_folder_if_missing = True,
                         threading_enabled = True,
                         lock = lock)

    # .................................................................................................................
    
    def _build_data_folder_path(self):   
        return build_base_resources_path(self.cameras_folder_path, self.camera_select, *self.folder_paths)
    
    # .................................................................................................................
    # .................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Load & Save functions

# .....................................................................................................................

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Pathing functions

# .....................................................................................................................

def build_base_resources_path(cameras_folder, camera_select, *path_joins):
    ''' Build path to base resources folder for a given camera '''
    return os.path.join(cameras_folder, camera_select, "resources", *path_joins)

# .....................................................................................................................
# .....................................................................................................................


    
# ---------------------------------------------------------------------------------------------------------------------
#%% Demo

if __name__ == "__main__":
    
    example_cameras_folder = "/path/to/nowhere"
    example_camera_select = "fake_camera"


# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap


