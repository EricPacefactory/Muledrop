#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Jul 15 15:51:17 2020

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

from local.lib.ui_utils.cli_selections import Resource_Selector
from local.lib.ui_utils.editor_lib import warn_for_name_taken, rename_from_path
from local.lib.ui_utils.editor_lib import select_from_list, prompt_with_defaults, confirm

from local.lib.file_access_utils.shared import url_safe_name
from local.lib.file_access_utils.stations import build_station_config_folder_path, get_station_config_paths

from local.eolib.utils.files import replace_user_home_pathing


# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

# .....................................................................................................................

def select_station_config(station_configs_folder_path):
    
    ''' Function used to select a station configuration file '''
    
    # Get existing names/paths
    paths_list, names_list = get_station_config_paths(station_config_folder_path)
    
    # Provide menu to select from existing station names
    select_idx, select_name = select_from_list(names_list, "Select a station:")
    
    # Get the selected station name (no ext) and pathing
    station_path_select = paths_list[select_idx]
    station_select = names_list[select_idx]
    
    return station_select, station_path_select

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Get pathing

# Set up resource selector
selector = Resource_Selector(load_selection_history = False,
                             save_selection_history = False,
                             show_hidden_resources = True,
                             create_folder_structure_on_select = True)

project_root_path, cameras_folder_path = selector.get_cameras_root_pathing()

# Get this script name for display
this_script_path = os.path.abspath(__file__)
this_script_name = os.path.basename(this_script_path)
this_file_name, _ = os.path.splitext(this_script_name)


# ---------------------------------------------------------------------------------------------------------------------
#%% Provide top-level options

# Prompt for options
update_option = "Rename"
delete_option = "Delete"
options_menu_list = [update_option, delete_option]
select_idx, select_entry = select_from_list(options_menu_list,
                                            prompt_heading = "Select an option ({})".format(this_file_name),
                                            default_selection = None)

# For convenience/clarity
selected_rename = (select_entry == update_option)
selected_delete = (select_entry == delete_option)


# ---------------------------------------------------------------------------------------------------------------------
#%% Handle 'Update' selection

if selected_rename:
    
    # First ask user to select an existing camera
    camera_select, _ = selector.camera()
    
    # Select an existing station
    station_config_folder_path = build_station_config_folder_path(cameras_folder_path, camera_select)
    station_name_select, station_config_path = select_station_config(station_config_folder_path)
    
    # Then ask user to enter a new station name
    new_station_name = \
    prompt_with_defaults("Enter new station name: ", default_value = station_name_select, return_type = str)
    
    # Make sure the given name isn't already taken
    _, station_names_list = get_station_config_paths(station_config_folder_path)
    cleaned_new_station_name = url_safe_name(new_station_name)
    warn_for_name_taken(cleaned_new_station_name, station_names_list, quit_if_name_is_taken = True)
    
    # Rename the station config file (with proper extension)
    _, station_ext = os.path.splitext(station_config_path)
    cleaned_save_name = "{}{}".format(cleaned_new_station_name, station_ext)
    rename_from_path(station_config_path, cleaned_save_name)
    
    # We're done! Provide some feedback
    print("",
          "Done! Station renamed:",
          "  {}  ->  {}".format(station_name_select, cleaned_new_station_name),
          sep = "\n")
    
    # Save renamed station as default selection for convenience
    selector.save_station_select(cleaned_new_station_name)


# ---------------------------------------------------------------------------------------------------------------------
#%% Handle 'Delete' selection

if selected_delete:
    
    # First ask user to select an existing camera
    camera_select, _ = selector.camera()
    
    # Select an existing station
    station_config_folder_path = build_station_config_folder_path(cameras_folder_path, camera_select)
    station_select, station_config_path = select_station_config(station_config_folder_path)
    
    # Confirm with user that they want to delete the selected station
    user_confirm = confirm("Are you sure you want to delete {}?".format(station_select), default_response = False)
    if user_confirm:
        os.remove(station_config_path)
        
        # Provide some feedback
        printable_path = replace_user_home_pathing(station_config_path)
        print("",
              "Done! Station deleted ({})".format(station_select),
              "@ {}".format(printable_path), sep = "\n")
    
    pass


# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap


