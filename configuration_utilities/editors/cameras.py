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

from local.lib.file_access_utils.shared import list_default_config_options
from local.lib.file_access_utils.structures import build_camera_list, create_camera_folder_structure

from local.eolib.utils.files import replace_user_home_pathing


# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

# .....................................................................................................................

def clean_camera_name(input_name):
    
    ''' Helper function which cleans up user provided camera naming '''
    
    return input_name.strip().lower().replace(" ", "_")

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
    default_folder_select = orig_names_list[select_idx]
    
    return default_folder_select

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
new_option = "New"
update_option = "Rename"
delete_option = "Delete"
options_menu_list = [new_option, update_option, delete_option]
select_idx, select_entry = select_from_list(options_menu_list,
                                            prompt_heading = "Select an option ({})".format(this_file_name),
                                            default_selection = None)

# For convenience/clarity
selected_new = (select_entry == new_option)
selected_update = (select_entry == update_option)
selected_delete = (select_entry == delete_option)


# ---------------------------------------------------------------------------------------------------------------------
#%% Handle 'New' selection

if selected_new:
    
    # Ask user for new camera name
    user_response = prompt_with_defaults("Enter new camera name: ", default_value = None, return_type = str)
    quit_if_none(user_response, "No camera name provided!")
    cleaned_camera_name = clean_camera_name(user_response)
    
    # Make sure the given name isn't already taken
    camera_name_list, _ = build_camera_list(cameras_folder_path, show_hidden_cameras = True, must_have_rtsp = False)
    warn_for_name_taken(cleaned_camera_name, camera_name_list, quit_if_name_is_taken = True)
    
    # Prompt for default configuration to use as starting point for the new camera
    default_folder_select = prompt_for_default_configuration(project_root_path)
    
    # Create the new camera entry
    create_camera_folder_structure(project_root_path,
                                   cameras_folder_path,
                                   cleaned_camera_name,
                                   default_folder_select)
    
    # Provide some feedback
    print("",
          "Done! New camera added ({})".format(cleaned_camera_name),
          "  -> Using {} configuration".format(default_folder_select),
          "",
          "Don't forget to add videos & rtsp info using the other editor tools!",
          sep = "\n")
    
    # Save new camera as default selection for convenience
    selector.save_camera_select(cleaned_camera_name)


# ---------------------------------------------------------------------------------------------------------------------
#%% Handle 'Update' selection

if selected_update:
    
    # First ask user to select an existing camera to rename
    camera_select, camera_path = selector.camera()
    
    # Then ask user to enter a new camera name
    new_camera_name = prompt_with_defaults("Enter new camera name: ", default_value = camera_select, return_type = str)
    
    # Make sure the given name isn't already taken
    cleaned_new_camera_name = clean_camera_name(new_camera_name)
    camera_name_list, _ = build_camera_list(cameras_folder_path, show_hidden_cameras = True, must_have_rtsp = False)
    warn_for_name_taken(cleaned_new_camera_name, camera_name_list, quit_if_name_is_taken = True)
    
    # Rename the camera folder
    rename_from_path(camera_path, cleaned_new_camera_name)
    
    # We're done! Provide some feedback
    print("",
          "Done! Camera renamed:",
          "  {}  ->  {}".format(camera_select, cleaned_new_camera_name),
          sep = "\n")
    
    # Save renamed camera as default selection for convenience
    selector.save_camera_select(cleaned_new_camera_name)


# ---------------------------------------------------------------------------------------------------------------------
#%% Handle 'Delete' selection

if selected_delete:
    
    # First ask user to select an existing camera to delete
    camera_select, camera_path = selector.camera()
    
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


