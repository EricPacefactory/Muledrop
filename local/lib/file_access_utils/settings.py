#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Apr 12 12:49:38 2019

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

import platform

from local.lib.file_access_utils.json_read_write import load_or_create_config_json, update_config_json


# ---------------------------------------------------------------------------------------------------------------------
#%% Define pathing functions

# .....................................................................................................................

def build_path_to_settings_folder(project_root_path, *path_joins):
    return os.path.join(project_root_path, "settings", *path_joins)

# .....................................................................................................................

def build_path_to_selection_history(project_root_path):    
    return build_path_to_settings_folder(project_root_path, "selection_history.json")

# .....................................................................................................................

def build_path_to_screen_info(project_root_path):
    return build_path_to_settings_folder(project_root_path, "screen_info.json")

# .....................................................................................................................

def build_path_to_locations_pathing_info(project_root_path):
    return build_path_to_settings_folder(project_root_path, "locations_pathing_info.json")

# .....................................................................................................................

def build_path_to_recording_info(project_root_path):
    return build_path_to_settings_folder(project_root_path, "recording_info.json")

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Define selection history functions
    
# .....................................................................................................................

def load_history(project_root_path, enable = True):
    
    # Create default config entries
    default_config = {"location_select": None, "camera_select": None, "video_select": None, "station_select": None}
    
    # Return empty selections if disabled
    if not enable:
        return default_config
    
    # First create history path, then load the history file
    history_path = build_path_to_selection_history(project_root_path)
    history_config = load_or_create_config_json(history_path, default_config,
                                                creation_printout = "Creating selection history file:")
    
    return history_config

# .....................................................................................................................

def save_history(project_root_path, new_config, enable = True):
    
    # Don't do anything if disabled
    if not enable:
        return
    
    # Create history path and the load existing history data, replace with new config and re-save
    history_path = build_path_to_selection_history(project_root_path)
    update_config_json(history_path, new_config)

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Define info loading functions

# .....................................................................................................................

def load_screen_info(project_root_path):
    
    # Build default parameters for different use cases
    default_screen = {"width": 1920,  "height": 1080, "x_offset": 0, "y_offset": 0}
    default_controls = {"max_columns": 3,  "max_width": 500, "column_spacing": 20, "row_spacing": 250,
                        "x_padding": 20, "y_padding": 20, "empty_height": 30}
    default_displays = {"max_width": 1280, "max_height": 720, 
                        "top_left_x": 40, "top_left_y": 175, "reserved_vertical": 150}
    default_feedback = {"width": 300, "x_padding": 20, "y_padding": 20, "row_spacing": 20}
    
    # Bundle all the default parameters
    default_config = {"screen": default_screen,
                      "controls": default_controls,
                      "displays": default_displays,
                      "feedback": default_feedback}
    
    # First create history path, then load the history file
    file_path = build_path_to_screen_info(project_root_path)
    screen_info_config = load_or_create_config_json(file_path, default_config,
                                                    creation_printout = "Creating screen info file:")
    
    return screen_info_config

# .....................................................................................................................

def load_locations_pathing_info(project_root_path):
    
    ''' Function which tries to load saved locations pathing info which points to the locations folder '''
    
    # Set the default paths in case we can't load anything
    parent_of_root_folder_path = os.path.dirname((project_root_path))
    default_all_locations_folder_path = os.path.join(parent_of_root_folder_path, "locations")
    default_empty_path = ""
    
    # Load or create the locations pathing info file, as needed
    default_locations_pathing_info_dict = {}
    locations_pathing_info_file_path = build_path_to_locations_pathing_info(project_root_path)
    locations_pathing_info_dict = \
    load_or_create_config_json(locations_pathing_info_file_path,
                               default_locations_pathing_info_dict,
                               creation_printout = "Creating locations pathing info file:")
    
    # Determine computer name, and check if we need to add the computer to the locations pathing info file
    computer_name = platform.uname().node
    need_to_update = (computer_name not in locations_pathing_info_dict)
    if need_to_update:
        default_computer_entry_dict = {computer_name: default_empty_path}
        locations_pathing_info_dict.update(default_computer_entry_dict)
        update_config_json(locations_pathing_info_file_path, locations_pathing_info_dict)
    
    # Finally, get the pathing to the locations folder for this computer
    saved_locations_pathing = locations_pathing_info_dict.get(computer_name, default_empty_path)
    expanded_locations_pathing = os.path.expanduser(saved_locations_pathing)
    
    # Return the default locations pathing if the loaded path is empty or not valid
    path_exists = (os.path.exists(expanded_locations_pathing))
    final_camera_path = expanded_locations_pathing if path_exists else default_all_locations_folder_path
    
    return final_camera_path

# .....................................................................................................................

def load_recording_info(project_root_path):
    
    # Set default parameters
    default_codec = "avc1"
    default_file_ext = "mp4"
    
    # Bundle all the default parameters
    default_config = {"codec": default_codec,
                      "file_extension": default_file_ext}
    
    # Build pathing to recording file and try to load it (or otherwise create default file)
    file_path = build_path_to_recording_info(project_root_path)
    recording_info_config = load_or_create_config_json(file_path, default_config,
                                                       creation_printout = "Creating recording info file:")
    
    return recording_info_config

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap
