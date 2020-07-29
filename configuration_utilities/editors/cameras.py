#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Jun 22 15:18:49 2020

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

from shutil import rmtree

from local.lib.ui_utils.cli_selections import Resource_Selector
from local.lib.ui_utils.editor_lib import warn_for_name_taken, rename_from_path
from local.lib.ui_utils.editor_lib import select_from_list, prompt_with_defaults, confirm, quit_if_none

from local.lib.file_access_utils.shared import list_default_config_options, url_safe_name
from local.lib.file_access_utils.cameras import create_camera_folder_structure, build_camera_list

from local.eolib.utils.files import replace_user_home_pathing


# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

# .....................................................................................................................

def prompt_for_default_configuration(project_root_path):
    
    # Get list of available default types
    nice_names_list, orig_names_list = list_default_config_options(project_root_path)
    default_selection = nice_names_list[0]
    
    # Have user choose from default types
    select_idx, _ = select_from_list(nice_names_list,
                                     "Select default configuration:",
                                     default_selection = default_selection,
                                     zero_indexed = True)
    
    # Convert user selection to the actual 'original' folder name
    nice_folder_select = nice_names_list[select_idx]
    default_folder_select = orig_names_list[select_idx]
    
    return default_folder_select, nice_folder_select

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Get pathing

# Set up resource selector
selector = Resource_Selector(load_selection_history = False,
                             save_selection_history = False,
                             show_hidden_resources = True,
                             create_folder_structure_on_select = True)

# Get important pathing & select location
project_root_path, all_locations_folder_path = selector.get_shared_pathing()
location_select, location_select_folder_path = selector.location()


# ---------------------------------------------------------------------------------------------------------------------
#%% Provide top-level options

# Prompt for options
new_option = "New"
rename_option = "Rename"
delete_option = "Delete"
options_menu_list = [new_option, rename_option, delete_option]
select_idx, select_entry = select_from_list(options_menu_list,
                                            prompt_heading = "Select an option (cameras)",
                                            default_selection = None)

# For convenience/clarity
selected_new = (select_entry == new_option)
selected_rename = (select_entry == rename_option)
selected_delete = (select_entry == delete_option)


# ---------------------------------------------------------------------------------------------------------------------
#%% Handle 'New' selection

if selected_new:
    
    # Ask user for new camera name
    user_response = prompt_with_defaults("Enter new camera name: ", default_value = None, return_type = str)
    quit_if_none(user_response, "No camera name provided!")
    safe_camera_name = url_safe_name(user_response)
    
    # Make sure the given name isn't already taken
    camera_name_list, _ = build_camera_list(all_locations_folder_path,
                                            show_hidden_cameras = True,
                                            must_have_rtsp = False)
    warn_for_name_taken(safe_camera_name, camera_name_list, quit_if_name_is_taken = True)
    
    # Prompt for default configuration to use as starting point for the new camera
    default_folder_select, nice_default_select = prompt_for_default_configuration(project_root_path)
    
    # Create the new camera entry
    create_camera_folder_structure(project_root_path,
                                   location_select_folder_path,
                                   safe_camera_name,
                                   default_folder_select)
    
    # Provide some feedback
    print("",
          "Done! New camera added ({})".format(safe_camera_name),
          "  -> Using {} configuration".format(nice_default_select),
          "",
          "Don't forget to add videos & rtsp info using the other editor tools!",
          sep = "\n")
    
    # Save new camera as default selection for convenience
    selector.save_camera_select(safe_camera_name)


# ---------------------------------------------------------------------------------------------------------------------
#%% Handle 'Rename' selection

if selected_rename:
    
    # First ask user to select an existing camera to rename
    camera_select, camera_path = selector.camera(location_select)
    
    # Then ask user to enter a new camera name
    new_camera_name = prompt_with_defaults("Enter new camera name: ", default_value = camera_select, return_type = str)
    
    # Make sure the given name isn't already taken
    safe_new_camera_name = url_safe_name(new_camera_name)
    camera_name_list, _ = build_camera_list(location_select_folder_path,
                                            show_hidden_cameras = True,
                                            must_have_rtsp = False)
    warn_for_name_taken(safe_new_camera_name, camera_name_list, quit_if_name_is_taken = True)
    
    # Rename the camera folder
    rename_from_path(camera_path, safe_new_camera_name)
    
    # We're done! Provide some feedback
    print("",
          "Done! Camera renamed:",
          "  {}  ->  {}".format(camera_select, safe_new_camera_name),
          sep = "\n")
    
    # Save renamed camera as default selection for convenience
    selector.save_camera_select(safe_new_camera_name)


# ---------------------------------------------------------------------------------------------------------------------
#%% Handle 'Delete' selection

if selected_delete:
    
    # First ask user to select an existing camera to delete
    camera_select, camera_path = selector.camera(location_select)
    
    # Confirm with user that they want to delete the selected camera
    user_confirm = confirm("Are you sure you want to delete {}?".format(camera_select), default_response = False)
    if user_confirm:
        rmtree(camera_path)
        
        # Provide some feedback
        printable_path = replace_user_home_pathing(camera_path)
        print("",
              "Done! Camera deleted ({})".format(camera_select),
              "@ {}".format(printable_path), sep = "\n")
    
    pass


# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap


