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

from local.lib.common.timekeeper_utils import datetime_to_isoformat_string

from local.lib.file_access_utils.threaded_read_write import Threaded_JPG_and_JSON_Saver
from local.lib.file_access_utils.threaded_read_write import Nonthreaded_JPG_and_JSON_Saver
from local.lib.file_access_utils.threaded_read_write import Threaded_Compressed_JSON_Saver
from local.lib.file_access_utils.threaded_read_write import Nonthreaded_Compressed_JSON_Saver


# ---------------------------------------------------------------------------------------------------------------------
#%% Classes

class Background_Report_Data_Saver:
    
    '''
    Helper class which simply selects between different types (e.g. threaded/non-threaded) of saving
    implementation for background data. Also handles save pathing.
    Note this class is also responsible for enabling/disabling saving
    '''
    
    # .................................................................................................................
    
    def __init__(self, cameras_folder_path, camera_select, user_select, 
                 saving_enabled = True, threading_enabled = True):
        
        # Store inputs
        self.cameras_folder_path = cameras_folder_path
        self.camera_select = camera_select
        self.user_select = user_select
        self.saving_enabled = saving_enabled
        self.threading_enabled = threading_enabled
        
        # Build saving paths
        pathing_args = (cameras_folder_path, camera_select, user_select)
        self.image_save_folder_path = build_background_image_report_path(*pathing_args)
        self.metadata_save_folder_path = build_background_metadata_report_path(*pathing_args)
        
        # Initialize saver object & pathing as needed
        self._data_saver = None
        if self.saving_enabled:
            
            # Make sure the save folders exist
            os.makedirs(self.image_save_folder_path, exist_ok = True)
            os.makedirs(self.metadata_save_folder_path, exist_ok = True)
            
            # Select between different types of saving implementations
            if self.threading_enabled:
                self._data_saver = Threaded_JPG_and_JSON_Saver(thread_name = "backgrounds-report",
                                                               jpg_folder_path = self.image_save_folder_path,
                                                               json_folder_path = self.metadata_save_folder_path)
            else:
                self._data_saver = Nonthreaded_JPG_and_JSON_Saver(jpg_folder_path = self.image_save_folder_path,
                                                                  json_folder_path = self.metadata_save_folder_path)
        
        pass
    
    # .................................................................................................................
    
    def save_data(self, *, file_save_name_no_ext, image_data, metadata_dict, jpg_quality_0_to_100, 
                  json_double_precision = 0):
        
        # Only save data if enabled
        if self.saving_enabled:
            self._data_saver.save_data(file_save_name_no_ext, image_data, metadata_dict,
                                       jpg_quality_0_to_100, json_double_precision)
        
        return
    
    # .................................................................................................................
    
    def close(self):
        
        # Close data saver if needed
        if self.saving_enabled:
            self._data_saver.close()
        
        return
    
    # .................................................................................................................
    # .................................................................................................................


# =====================================================================================================================
# =====================================================================================================================


class Object_Report_Data_Saver:
    
    '''
    Helper class which simply selects between different types (e.g. threaded/non-threaded) of saving
    implementation for object data. Also handles save pathing.
    Note this class is also responsible for enabling/disabling saving
    '''
    
    # .................................................................................................................
    
    def __init__(self, cameras_folder_path, camera_select, user_select, 
                 saving_enabled = True, threading_enabled = True):
        
        # Store inputs
        self.cameras_folder_path = cameras_folder_path
        self.camera_select = camera_select
        self.user_select = user_select
        self.saving_enabled = saving_enabled
        self.threading_enabled = threading_enabled
        
        # Build saving paths
        pathing_args = (cameras_folder_path, camera_select, user_select)
        self.metadata_save_folder_path = build_object_metadata_report_path(*pathing_args)
        
        # Initialize saver object & pathing as needed
        self._data_saver = None
        if self.saving_enabled:
            
            # Make sure the save folder exists
            os.makedirs(self.metadata_save_folder_path, exist_ok = True)
            
            # Select between different types of saving implementations
            if self.threading_enabled:
                self._data_saver = Threaded_Compressed_JSON_Saver(thread_name = "objects",
                                                                  jsongz_folder_path = self.metadata_save_folder_path)
            else:
                self._data_saver = Nonthreaded_Compressed_JSON_Saver(jsongz_folder_path = self.metadata_save_folder_path)
        
        pass
    
    # .................................................................................................................
    
    def save_data(self, *, file_save_name_no_ext, metadata_dict, json_double_precision = 3):
        
        # Only save data if enabled
        if self.saving_enabled:
            self._data_saver.save_data(file_save_name_no_ext, metadata_dict, json_double_precision)
        
        return
    
    # .................................................................................................................
    
    def close(self):
        
        # Close data saver if needed
        if self.saving_enabled:
            self._data_saver.close()
        
        return
    
    # .................................................................................................................
    # .................................................................................................................


# =====================================================================================================================
# =====================================================================================================================


class Snapshot_Report_Data_Saver:
    
    '''
    Helper class which simply selects between different types (e.g. threaded/non-threaded) of saving
    implementation for snapshot data. Also handles save pathing.
    Note this class is also responsible for enabling/disabling saving
    '''
    
    # .................................................................................................................
    
    def __init__(self, cameras_folder_path, camera_select, user_select, 
                 saving_enabled = True, threading_enabled = True):
        
        # Store inputs
        self.cameras_folder_path = cameras_folder_path
        self.camera_select = camera_select
        self.user_select = user_select
        self.saving_enabled = saving_enabled
        self.threading_enabled = threading_enabled
        
        # Build saving paths
        pathing_args = (cameras_folder_path, camera_select, user_select)
        self.image_save_folder_path = build_snapshot_image_report_path(*pathing_args)
        self.metadata_save_folder_path = build_snapshot_metadata_report_path(*pathing_args)
        
        # Initialize saver object & pathing as needed
        self._data_saver = None
        if self.saving_enabled:
            
            # Make sure the save folders exist
            os.makedirs(self.image_save_folder_path, exist_ok = True)
            os.makedirs(self.metadata_save_folder_path, exist_ok = True)
            
            # Select between different types of saving implementations
            if self.threading_enabled:
                self._data_saver = Threaded_JPG_and_JSON_Saver(thread_name = "snapshots",
                                                               jpg_folder_path = self.image_save_folder_path,
                                                               json_folder_path = self.metadata_save_folder_path)
            else:
                self._data_saver = Nonthreaded_JPG_and_JSON_Saver(jpg_folder_path = self.image_save_folder_path,
                                                                  json_folder_path = self.metadata_save_folder_path)
        
        pass
    
    # .................................................................................................................
    
    def save_data(self, *, file_save_name_no_ext, image_data, metadata_dict, jpg_quality_0_to_100, 
                  json_double_precision = 0):
        
        # Only save data if enabled
        if self.saving_enabled:
            self._data_saver.save_data(file_save_name_no_ext, image_data, metadata_dict,
                                       jpg_quality_0_to_100, json_double_precision)
        
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

def build_camera_info_metadata_report_path(cameras_folder, camera_select, user_select, *path_joins):
    return build_metadata_report_path(cameras_folder, camera_select, user_select, "camera_info", *path_joins)

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

def build_object_metadata_report_path(cameras_folder, camera_select, user_select):
    return build_metadata_report_path(cameras_folder, camera_select, user_select, "objects")

# .....................................................................................................................

def build_after_database_report_path(cameras_folder, camera_select, user_select, *path_joins):
    return build_user_report_path(cameras_folder, camera_select, user_select, "after_database", *path_joins)

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Helper functions

# .....................................................................................................................

def create_image_metadata(current_frame_index, current_epoch_ms, current_datetime):
    
    '''
    Helper function used to provide consistent metadata formatting for saved images (snaps & backgrounds)
    Returns a dictionary representing a single metadata entry for an image at the given time
    '''
    
    datetime_isoformat = datetime_to_isoformat_string(current_datetime)    
    metadata_dict = {"_id": current_epoch_ms,
                     "datetime_isoformat": datetime_isoformat,
                     "frame_index": current_frame_index,
                     "epoch_ms": current_epoch_ms}
    
    return metadata_dict

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Demo

if __name__ == "__main__":
    pass

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap


