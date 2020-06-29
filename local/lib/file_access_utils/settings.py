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

from local.lib.common.environment import get_dbserver_port, get_control_server_port


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

def build_path_to_pathing_info(project_root_path):
    return build_path_to_settings_folder(project_root_path, "pathing_info.json")

# .....................................................................................................................

def build_path_to_recording_info(project_root_path):
    return build_path_to_settings_folder(project_root_path, "recording_info.json")

# .....................................................................................................................

def build_path_to_locations_info(project_root_path):
    return build_path_to_settings_folder(project_root_path, "locations_info.json")

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Define selection history functions
    
# .....................................................................................................................

def load_history(project_root_path, enable = True):
    
    # Create default config entries
    default_config = {"camera_select": None, "video_select": None}
    
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
#%% Define screen info functions

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
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Define pathing info functions

# .....................................................................................................................

def load_pathing_info(project_root_path):
    
    # Set the default path (empty) and the fallback (used if a loaded path is not valid), in case we need it
    fallback_camera_path = os.path.join(project_root_path, "cameras")
    default_empty_path = ""
    default_pathing_info_dict = {}
    
    # Get path to the pathing info file and load/create it as needed
    pathing_info_file_path = build_path_to_pathing_info(project_root_path)
    pathing_info_dict = load_or_create_config_json(pathing_info_file_path, default_pathing_info_dict,
                                                   creation_printout = "Creating pathing info file:")
    
    # Determine computer name, and check if we need to add the computer to the pathing info file
    computer_name = platform.uname().node
    need_to_update = (computer_name not in pathing_info_dict)
    if need_to_update:
        default_computer_entry_dict = {computer_name: default_empty_path}
        pathing_info_dict.update(default_computer_entry_dict)
        update_config_json(pathing_info_file_path, pathing_info_dict)
    
    # Finally, get the pathing to the camera, for this computer
    saved_camera_pathing = pathing_info_dict.get(computer_name, default_empty_path)
    expanded_camera_pathing = os.path.expanduser(saved_camera_pathing)
            
    # Return the project root based pathing if the loaded path is empty or not valid
    path_exists = (os.path.exists(expanded_camera_pathing))
    final_camera_path = expanded_camera_pathing if path_exists else fallback_camera_path
    
    return final_camera_path

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Define recording info functions

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
#%% Define locations info functions

# .....................................................................................................................

def create_new_locations_entry(location_name, host,
                               dbserver_port = None, control_server_port = None,
                               ssh_username = None, ssh_password = None):
    
    ''' Helper function used to create new location entries in the locations settings file '''
    
    # Make sure variables have the correct data types before saving
    location_name_str = str(location_name)
    host_str = str(host)
    dbserver_port_int = int(dbserver_port if dbserver_port is not None else get_dbserver_port())
    control_server_port_int = int(control_server_port if control_server_port is not None else get_control_server_port())
    
    # Build location entry data
    location_data_dict = {"host": host_str,
                          "dbserver_port": dbserver_port_int,
                          "control_server_port": control_server_port_int,
                          "ssh_username": ssh_username,
                          "ssh_password": ssh_password}
    new_location_entry = {location_name_str: location_data_dict}
    
    return new_location_entry

# .....................................................................................................................

def update_locations_info(project_root_path, new_locations_entry):
    
    # First load the existing locations data
    locations_info_dict = load_locations_info(project_root_path)
    
    # Make sure we don't already have an existing location with the same name as the new entry
    existing_location_names = locations_info_dict.keys()
    new_location_names = new_locations_entry.keys()
    for each_new_name in new_location_names:
        if each_new_name in existing_location_names:
            raise NameError("Can't add new location ({}) name already in use!".format(each_new_name))
    
    # If we get here, we're good to update the locations info
    save_path = build_path_to_locations_info(project_root_path)
    update_config_json(save_path, new_locations_entry)

# .....................................................................................................................

def load_locations_info(project_root_path):
    
    # Set default location entry
    default_local_location = create_new_locations_entry("local", "localhost")
    
    # Build pathing to locations file and try to load it (or otherwise create default file)
    file_path = build_path_to_locations_info(project_root_path)
    locations_info_config = load_or_create_config_json(file_path, default_local_location,
                                                       creation_printout = "Creating locations info file:")
    
    return locations_info_config

# .....................................................................................................................

def get_nice_location_names_list(locations_info_dict):
    
    ''' Helper function which sorts location names, and will try to place the 'local' entry at the top of the list '''
    
    # Separate any 'local' names from the given locations info
    location_names_set = set(locations_info_dict.keys())
    possible_local_names_set = {"local", "localhost", "0.0.0.0"}
    local_set = location_names_set.intersection(possible_local_names_set)
    remote_set = location_names_set.difference(local_set)
        
    # Now build a nicely sorted list of location names, with 'local' at the top
    local_names_list = sorted(list(local_set))
    remote_names_list = sorted(list(remote_set))
    nice_location_names_list = local_names_list + remote_names_list
    
    return nice_location_names_list

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap
