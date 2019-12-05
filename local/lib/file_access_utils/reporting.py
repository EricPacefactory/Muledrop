#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Jul  3 10:43:54 2019

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

from local.lib.file_access_utils.runtime_read_write import Image_Saver, Metadata_Saver

# ---------------------------------------------------------------------------------------------------------------------
#%% Classes

class Image_Report_Saver(Image_Saver):
    
    # .................................................................................................................
    
    def __init__(self, cameras_folder_path, camera_select, user_select, image_folder_name = "files",
                 *, lock = None):
        
        # Store special variable used to generate the saving folder path
        self.image_folder_name = image_folder_name
        
        # Inherit from base class
        super().__init__(cameras_folder_path, camera_select, user_select, 
                         task_select = None,
                         saving_enabled = True,
                         threading_enabled = True, 
                         lock = lock)

    # .................................................................................................................
    
    def _build_data_folder_path(self):        
        return build_image_report_path(self.cameras_folder_path,
                                       self.camera_select,
                                       self.user_select,
                                       self.image_folder_name)
    
    # .................................................................................................................
    # .................................................................................................................


# =====================================================================================================================
# =====================================================================================================================

class Image_Metadata_Report_Saver(Metadata_Saver):
    
    # .................................................................................................................
    
    def __init__(self, cameras_folder_path, camera_select, user_select, image_folder_name,
                 *, lock = None):
        
        # Store image folder name, so we create the proper pathing on initialization
        self.image_folder_name = image_folder_name
        
        # Inherit from base class
        super().__init__(cameras_folder_path, camera_select, user_select, 
                         task_select = None,
                         saving_enabled = True,
                         threading_enabled = True,
                         lock = lock)
        
    # .................................................................................................................
    
    def _build_data_folder_path(self):
        return build_metadata_report_path(self.cameras_folder_path, 
                                          self.camera_select, 
                                          self.user_select, 
                                          self.image_folder_name)
        
    # .................................................................................................................
    # .................................................................................................................


# =====================================================================================================================
# =====================================================================================================================


class Object_Metadata_Report_Saver(Metadata_Saver):
    
    # .................................................................................................................
    
    def __init__(self, cameras_folder_path, camera_select, user_select, task_select,
                 threading_enabled = True, saving_enabled = True, *, lock = None):
        
        # Inherit from base class
        super().__init__(cameras_folder_path, camera_select, user_select, task_select,
                         saving_enabled = saving_enabled,
                         threading_enabled = threading_enabled, 
                         lock = lock)
        
    # .................................................................................................................
    
    def _build_data_folder_path(self):
        return build_object_metadata_report_path(self.cameras_folder_path,
                                                 self.camera_select,
                                                 self.user_select,
                                                 self.task_select)
        
    # .................................................................................................................
    # .................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% General pathing functions

# .....................................................................................................................

def build_base_report_path(cameras_folder, camera_select):
    ''' Build path to base reporting folder for a given camera '''    
    return os.path.join(cameras_folder, camera_select, "report")

# .....................................................................................................................

def build_user_report_path(cameras_folder, camera_select, user_select, *path_joins):
    ''' Build path to user-specific reporting folder for a given camera '''
    base_path = build_base_report_path(cameras_folder, camera_select)
    return os.path.join(base_path, user_select, *path_joins)

# .....................................................................................................................
    
def build_image_report_path(cameras_folder, camera_select, user_select, *path_joins):
    ''' Build pathing to user-specific image data reporting folder for a given camera '''
    return build_user_report_path(cameras_folder, camera_select, user_select, "images", *path_joins)

# .....................................................................................................................

def build_metadata_report_path(cameras_folder, camera_select, user_select, *path_joins):
    ''' Build pathing to user-specific metadata reporting folder for a given camera '''
    return build_user_report_path(cameras_folder, camera_select, user_select, "metadata", *path_joins)

# .....................................................................................................................

def build_video_report_path(cameras_folder, camera_select, user_select, *path_joins):
    ''' Build pathing to user-specific video data reporting folder for a given camera '''
    return build_user_report_path(cameras_folder, camera_select, user_select, "videos", *path_joins)

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Specific pathing functions

# .....................................................................................................................
    
def build_snapshot_image_report_path(cameras_folder, camera_select, user_select):
    return build_image_report_path(cameras_folder, camera_select, user_select, "snapshots")

# .....................................................................................................................
    
def build_snapshot_metadata_report_path(cameras_folder, camera_select, user_select):
    return build_metadata_report_path(cameras_folder, camera_select, user_select, "snapshots")

# .....................................................................................................................
    
def build_background_image_report_path(cameras_folder, camera_select, user_select):
    return build_image_report_path(cameras_folder, camera_select, user_select, "backgrounds")

# .....................................................................................................................
    
def build_background_metadata_report_path(cameras_folder, camera_select, user_select):
    return build_metadata_report_path(cameras_folder, camera_select, user_select, "backgrounds")

# .....................................................................................................................
    
def build_object_metadata_report_path(cameras_folder, camera_select, user_select, task_select):
    object_folder_name = "objects-({})".format(task_select)
    return build_metadata_report_path(cameras_folder, camera_select, user_select, object_folder_name)

# .....................................................................................................................

def build_after_database_report_path(cameras_folder, camera_select, user_select, *path_joins):
    return build_user_report_path(cameras_folder, camera_select, user_select, "after_database", *path_joins)

# .....................................................................................................................

def build_classification_file_path(cameras_folder, camera_select, user_select, task_select):
    
    ''' Function for creating pathing to an offline classification file, used to replicate database access'''
    
    # Pathing to folder containing classifications (when running locally)
    classification_file_name = "{}.json.gz".format(task_select)
    classification_file_path = build_after_database_report_path(cameras_folder, camera_select, user_select, 
                                                                "local_classifications", 
                                                                classification_file_name)
    
    return classification_file_path

# .....................................................................................................................
# .....................................................................................................................


    
# ---------------------------------------------------------------------------------------------------------------------
#%% Demo

if __name__ == "__main__":
    
    example_cameras_folder = "/home/wrk/Desktop/example_test"
    example_camera_select = "fake_camera"
    example_user_select = "Nobody"
    example_task_select = "Potato_Farming"
    
    omd_saver = Object_Metadata_Report_Saver(example_cameras_folder, example_camera_select, example_user_select, example_task_select)
    imd_saver = Image_Metadata_Report_Saver(example_cameras_folder, example_camera_select, example_user_select, "snapshots")

    print("Example saving paths:",
          omd_saver._data_folder_path,
          imd_saver._data_folder_path,
          sep="\n")

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap


