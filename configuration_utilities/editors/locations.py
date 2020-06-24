#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Jun 22 14:53:40 2020

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

from local.lib.common.environment import get_dbserver_port, get_control_server_port

from local.lib.ui_utils.cli_selections import Resource_Selector
from local.lib.ui_utils.editor_lib import warn_for_name_taken
from local.lib.ui_utils.editor_lib import select_from_list, prompt_with_defaults, confirm, quit_if_none

from local.eolib.utils.files import replace_user_home_pathing


# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

# .....................................................................................................................

def clean_location_name(input_name):
    
    ''' Helper function which cleans up user provided location naming '''
    
    return input_name.strip().lower().replace(" ", "_")

# .....................................................................................................................

def prompt_for_location_ip_address(default_ip = None):
    
    pass

# .....................................................................................................................

def prompt_for_location_ssh_info(default_username = None, default_password = None):
    
    pass

# .....................................................................................................................

def prompt_for_location_server_ports(default_dbserver_port = None, default_control_server_port = None):
    
    pass

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Setup

# Set up resource selector
selector = Resource_Selector(load_selection_history = False,
                             save_selection_history = False,
                             show_hidden_resources = True,
                             create_folder_structure_on_select = True)

project_root_path = selector.get_project_root_pathing()

# Get this script name for display
this_script_path = os.path.abspath(__file__)
this_script_name = os.path.basename(this_script_path)
this_file_name, _ = os.path.splitext(this_script_name)


# ---------------------------------------------------------------------------------------------------------------------
#%% Provide location editing options

# Prompt for options
new_option = "New"
update_option = "Update"
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
    
    # Ask user for new location name
    user_response = prompt_with_defaults("Enter location name: ", default_value = None, return_type = str)
    quit_if_none(user_response, "No location name provided!")
    cleaned_location_name = clean_location_name(user_response)
    
    # Make sure the given name isn't already taken
    location_name_list, _ = build_location_list(project_root_path, show_hidden_locations = True)
    warn_for_name_taken(cleaned_location_name, location_name_list, quit_if_name_is_taken = True)
    
    # Prompt for location ip address & ssh username, ssh password    
    location_ip_address = prompt_with_defaults("Enter ip address: ", default_value = None, return_type = str)
    location_ssh_username = prompt_with_defaults("Enter ssh username: ", default_value = None, return_type = str)
    location_ssh_password = prompt_with_defaults("Enter ssh password: ", default_value = None, return_type = str)
    
    # Assume default server ports on creation (can change from update menu)
    default_dbserver_port = get_dbserver_port()
    default_ctrlserver_port = get_control_server_port()
    
    # Create the new location entry
    create_new_location_folder(project_root_path,
                               cleaned_location_name,
                               location_ip_address,
                               location_ssh_username,
                               location_ssh_password,
                               default_dbserver_port,
                               default_ctrlserver_port)


# ---------------------------------------------------------------------------------------------------------------------
#%% Handle 'Update' selection

if selected_update:
    
    # First ask user to select an existing location to update
    location_select, location_path = selector.location()
    
    # Provide prompt to select what to update
    rename_option = "Rename"
    ip_option = "Update IP"
    ssh_option = "Update SSH"
    server_option = "Update server ports"
    options_menu_list = [rename_option, ip_option, ssh_option, server_option]
    select_idx, select_entry = select_from_list(options_menu_list,
                                                prompt_heading = "What would you like to do?",
                                                default_selection = None)
    
    # For convenience
    selected_rename = (select_entry == rename_option)
    selected_ip = (select_entry == ip_option)
    selected_ssh = (select_entry == ssh_option)
    selected_server = (select_entry == server_option)
    
    # Handle different update options
    if selected_rename:
        pass
    elif selected_ip:
        pass
    elif selected_ssh:
        pass
    elif selected_server:
        pass
    
    pass


# ---------------------------------------------------------------------------------------------------------------------
#%% Handle 'Delete' selection

if selected_delete:
    
    # First ask user to select an existing location to delete
    location_select, location_path = selector.location()
    
    # Confirm with user that they want to delete the selected location
    user_confirm = confirm("Are you sure you want to delete {}?".format(location_select), default_response = False)
    if user_confirm:
        
        # Check if there are camera entries of the location
        # ...
        
        # If camera entries exist at the given location, prompt again to warn about deletion!
        # ...
        
        if user_secondary_confirm:
            rmtree(location_path)
        
            # Provide some feedback
            printable_path = replace_user_home_pathing(location_path)
            print("",
                  "Done! Location deleted ({})".format(location_select),
                  "@ {}".format(printable_path), sep = "\n")
    
    pass


# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap

# TODO:
# - Better error handling on no-select

# location
#   - new
#   - update (name, ip, ssh info, dbserver, control server)
#   - delete
