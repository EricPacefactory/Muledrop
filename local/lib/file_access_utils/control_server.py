#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Aug 26 11:03:04 2020

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

from local.lib.file_access_utils.cameras import build_camera_list
from local.lib.file_access_utils.json_read_write import save_config_json, load_config_json


# ---------------------------------------------------------------------------------------------------------------------
#%% Classes

class Autolaunch_Settings:
    
    # .................................................................................................................
    
    def __init__(self, location_select_folder_path, load_on_startup = True):
        
        '''
        Class used to manage camera autolaunch settings
        Note, this class does not handle the actual auto-launching of cameras, just the settings
        Reads/writes to a autolaunch settings file located in the selected location folder
        '''
        
        # Store inputs
        self.location_select_folder_path = location_select_folder_path
        
        # Allocate storage for holding autolaunch settings (per camera)
        self._autolaunch_dict = {}
        
        # Load existing autolaunch settings, if possible
        if load_on_startup:
            self.load_settings()
    
    # .................................................................................................................
    
    def load_settings(self, create_if_missing = True):
        
        ''' Function which loads existing autolaunch settings off the file system '''
        
        self._autolaunch_dict = load_autolaunch_settings(self.location_select_folder_path, create_if_missing)
        self.prune()
        
        return self._autolaunch_dict
    
    # .................................................................................................................
    
    def save_settings(self):
        
        ''' Function which saves autolaunch settings to a settings file '''
        
        save_autolaunch_settings(self.location_select_folder_path, self._autolaunch_dict)
        
        return self._autolaunch_dict
    
    # .................................................................................................................
    
    def set_autolaunch(self, camera_select, enable_autolaunch):
        
        ''' Function which sets/updates a camera's autolaunch setting, also saves autolaunch file '''
        
        # Create/update camera autolaunch setting
        self._autolaunch_dict[camera_select] = enable_autolaunch
        
        # Re-save settings file
        self.save_settings()
        
        return self._autolaunch_dict
    
    # .................................................................................................................
    
    def get_autolaunch(self, camera_select):
        ''' Function which gets a camera's current autolaunch setting. If none is available, defaults to False '''
        return self._autolaunch_dict.get(camera_select, False)
    
    # .................................................................................................................
    
    def get_enabled_cameras_list(self):
        ''' Function which returns a list of cameras with autolaunch enabled '''
        return [each_camera for each_camera, is_enabled in self._autolaunch_dict.items() if is_enabled == True]
    
    # .................................................................................................................
    
    def get_disabled_cameras_list(self):
        ''' Function which returns a list of cameras with autolaunch disabled '''
        return [each_camera for each_camera, is_enabled in self._autolaunch_dict.items() if is_enabled == False]
    
    # .................................................................................................................
    
    def prune(self):
        
        ''' Function which removes autolaunch camera entries no longer found on the system '''
        
        self._autolaunch_dict = prune_autolaunch(self.location_select_folder_path, self._autolaunch_dict)
        self.save_settings()
        
        return self._autolaunch_dict
    
    # .................................................................................................................
    # .................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% General pathing functions

# .....................................................................................................................

def build_autolaunch_settings_file_path(location_select_folder_path):
    return os.path.join(location_select_folder_path, ".autolaunch.json")

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Saving/loading functions

# .....................................................................................................................

def get_existing_camera_names_list(location_select_folder_path):
    
    ''' Helper function for getting a list of available camera names '''
    
    camera_names_list, _ = build_camera_list(location_select_folder_path,
                                             show_hidden_cameras = False,
                                             must_have_rtsp = True)
    
    return sorted(camera_names_list)

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Saving/loading functions

# .....................................................................................................................

def save_autolaunch_settings(location_select_folder_path, autolaunch_dict):
    
    '''
    Function which saves autolaunch settings for a given location.
    autolaunch_dict is expected to be of the form:
        {
          "camera_a": True,
          "camera_b": True,
          "camera_c": False,
          "camera_d": True,
          etc.
        }
    Where each key is a camera name and each corresponding value indicates if the camera should autolaunch or not
    '''
    
    # Build save pathing
    save_path = build_autolaunch_settings_file_path(location_select_folder_path)
    
    return save_config_json(save_path, autolaunch_dict)

# .....................................................................................................................

def load_autolaunch_settings(location_select_folder_path, create_if_missing = True):
    
    '''
    Function which loads autolaunch settings file for a given location
    Returns a dictionary, which is expected to be of the form:
        {
          "camera_a": True,
          "camera_b": True,
          "camera_c": False,
          "camera_d": True,
          etc.
        }
    Where each key is a camera name and each corresponding value indicates if the camera should autolaunch or not
    Defaults to an empty dictionary if there is no existing settings file!
    '''
    
    # Build load pathing
    load_path = build_autolaunch_settings_file_path(location_select_folder_path)
    
    # Load the autolaunch settings if they exist
    if os.path.exists(load_path):
        return load_config_json(load_path)
    
    # If we get here, there is no autolaunch file, so create one
    default_autolaunch_dict = {}
    if create_if_missing:
        save_autolaunch_settings(location_select_folder_path, default_autolaunch_dict)
    
    return default_autolaunch_dict

# .....................................................................................................................

def prune_autolaunch(location_select_folder_path, autolaunch_dict):
    
    '''
    Function which removes autolaunch entries for cameras that don't exist in the system
    Note that this function does not directly alter the file system, it simply
    returns a (potentially) modified copy of the provided autolaunch_dict
    '''
    
    # Get available cameras, so we can remove any cameras that no longer exist
    camera_names_list = get_existing_camera_names_list(location_select_folder_path)
    
    # Build a new autolaunch dictionary with only the existing camera names
    pruned_autolaunch_dict = {each_name: autolaunch_dict.get(each_name, False) for each_name in camera_names_list}
    
    return pruned_autolaunch_dict

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Demo

if __name__ == "__main__":
    
    pass

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap


