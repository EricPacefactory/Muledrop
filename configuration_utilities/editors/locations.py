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

from local.lib.ui_utils.cli_selections import Resource_Selector
from local.lib.ui_utils.editor_lib import warn_for_reserved_name, warn_for_name_taken
from local.lib.ui_utils.editor_lib import select_from_list, prompt_with_defaults, confirm, quit_if_none

from local.lib.file_access_utils.shared import url_safe_name
from local.lib.file_access_utils.locations import load_location_info_dict, save_location_info_dict
from local.lib.file_access_utils.locations import build_location_info_dict, unpack_location_info_dict
from local.lib.file_access_utils.locations import build_location_list, get_printable_location_info
from local.lib.file_access_utils.locations import create_new_location_folder
from local.lib.file_access_utils.cameras import build_camera_list

from local.eolib.utils.files import replace_user_home_pathing
from local.eolib.utils.network import check_valid_ip, check_connection
from local.eolib.utils.misc import blank_str_to_none, none_to_blank_str


# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

# .....................................................................................................................

def validate_location_name(all_locations_folder_path, given_location_name):
    
    # First convert given name to standardized 'safe' name
    safe_location_name = url_safe_name(given_location_name)
    
    # Prevent names that start with 'local', since this will be treated as a reserved name
    warn_for_reserved_name(safe_location_name, safe_location_name.startswith("local"))
    
    # Make sure the given name isn't already taken
    location_name_list, _ = build_location_list(all_locations_folder_path, show_hidden_locations = True)
    warn_for_name_taken(safe_location_name, location_name_list, quit_if_name_is_taken = True)
    
    return safe_location_name

# .....................................................................................................................

def check_host_connection(host_ip):
    
    '''
    Helper function which checks a connection to a host IP.
    First checks if the IP is itself valid, then checks http port, followed by ssh port on failure
    '''
    
    # For clarity
    ip_is_valid = False
    connection_success = False
    http_port = 80
    ssh_port = 22
    
    # First check if the provided ip is valid
    ip_is_valid = check_valid_ip(host_ip)
    if not ip_is_valid:
        return ip_is_valid, connection_success
    
    # Assuming IP is ok, check connection with port fallback if needed
    connection_success = check_connection(host_ip, port = http_port)
    if not connection_success:
        connection_success = check_connection(host_ip, port = ssh_port)
    
    return ip_is_valid, connection_success

# .....................................................................................................................

def prompt_for_location_rename(all_locations_folder_path, location_select):
    
    # Bail if the user selected the localhost entry, which shouldn't be renamed!
    selected_localhost = (location_select == "localhost")
    if selected_localhost:
        print("", "Can't rename localhost entry!", "", sep = "\n")
        return
    
    # Prompt for new name entry
    user_new_name = prompt_with_defaults("Enter new location name: ",
                                         default_value = location_select,
                                         return_type = str)
    
    # Make sure the new name is valid (i.e. safe & not already taken)
    new_safe_location_name = validate_location_name(all_locations_folder_path, user_new_name)
    
    # Check if the user just picked the default (in which case, don't both trying to rename!)
    no_change_to_name = (new_safe_location_name == location_select)
    if no_change_to_name:
        return
    
    # If we get here, the user entered a different name from default, so update it
    original_location_folder_path = os.path.join(all_locations_folder_path, location_select)
    new_location_folder_path = os.path.join(all_locations_folder_path, new_safe_location_name)
    os.rename(original_location_folder_path, new_location_folder_path)
    
    # Finally, provide feedback about renaming
    print("", "Done! Renamed:", "'{}' -> '{}'".format(location_select, new_safe_location_name), "", sep = "\n")
    
    return

# .....................................................................................................................

def prompt_for_modify_info(all_locations_folder_path, location_select):
    
    # First load existing ip info, if present & get default server ports from environment
    location_info_dict = load_location_info_dict(all_locations_folder_path, location_select, error_if_missing = False)
    
    # Unpack current location info to use as default values
    curr_host, curr_ssh_user, curr_ssh_pass, curr_dbserver_port, curr_ctrlserver_port = \
    unpack_location_info_dict(location_info_dict)
    
    # Convert empty entries
    default_host_ip = blank_str_to_none(curr_host)
    default_ssh_user = blank_str_to_none(curr_ssh_user)
    default_ssh_pass = blank_str_to_none(curr_ssh_pass)
    default_dbserver_port = blank_str_to_none(curr_dbserver_port)
    default_ctrlserver_port = blank_str_to_none(curr_ctrlserver_port)
    
    # Provide some indication of what's happening
    print("",
          "------------------------",
          "  Enter location info:  ",
          "(use . to clear entries)",
          "------------------------",
          "", sep = "\n")
    
    # Ask user for each location info entry
    ui_host_ip =         prompt_with_defaults("        Enter host ip: ", default_host_ip, dot_response = "")
    ui_ssh_user =        prompt_with_defaults("   Enter ssh username: ", default_ssh_user, dot_response = "")
    ui_ssh_pass =        prompt_with_defaults("   Enter ssh password: ", default_ssh_pass, dot_response = "")
    ui_dbserver_port =   prompt_with_defaults("  Enter dbserver port: ", default_dbserver_port)
    ui_ctrlserver_port = prompt_with_defaults("Enter ctrlserver port: ", default_ctrlserver_port)
    
    # Clean up inputs (replace None with empty strings)
    new_host_ip = none_to_blank_str(ui_host_ip)
    new_ssh_user = none_to_blank_str(ui_ssh_user)
    new_ssh_pass = none_to_blank_str(ui_ssh_pass)
    new_dbserver_port = none_to_blank_str(ui_dbserver_port)
    new_ctrlserver_port = none_to_blank_str(ui_ctrlserver_port)
    
    # Create new location info data based on user response
    new_location_info_dict = build_location_info_dict(new_host_ip,
                                                      new_ssh_user,
                                                      new_ssh_pass,
                                                      new_dbserver_port,
                                                      new_ctrlserver_port)
    
    # Prompt to confirm saving of new location info
    user_confirm_save = confirm("Save new IP address?", default_response = False)
    if user_confirm_save:
        save_location_info_dict(all_locations_folder_path, location_select, new_location_info_dict)
        print("",
              "Done! Updated location info ({})".format(location_select),
              "",
              *get_printable_location_info(new_location_info_dict),
              sep = "\n")
    
    return new_location_info_dict

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Setup

# Set up resource selector
selector = Resource_Selector(load_selection_history = False,
                             save_selection_history = False,
                             show_hidden_resources = True,
                             create_folder_structure_on_select = True)

# Get important pathing info
project_root_path, all_locations_folder_path = selector.get_shared_pathing()

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
view_option = "View"
options_menu_list = [new_option, update_option, delete_option, view_option]
select_idx, select_entry = select_from_list(options_menu_list,
                                            prompt_heading = "Select an option ({})".format(this_file_name),
                                            default_selection = None)

# For convenience/clarity
selected_new = (select_entry == new_option)
selected_update = (select_entry == update_option)
selected_delete = (select_entry == delete_option)
selected_view = (select_entry == view_option)


# ---------------------------------------------------------------------------------------------------------------------
#%% Handle 'New' selection


if selected_new:
    
    # Ask user for new location name
    user_response = prompt_with_defaults("Enter new location name: ", default_value = None, return_type = str)
    quit_if_none(user_response, "No location name provided!")
    
    # Make sure the given name is valid (i.e. safe & not already taken)
    safe_location_name = validate_location_name(all_locations_folder_path, user_response)
    
    # Prompt for location ip address & ssh username, ssh password    
    location_ip_address = prompt_with_defaults("Enter ip address: ", default_value = None, return_type = str)
    location_ssh_username = prompt_with_defaults("Enter ssh username: ", default_value = None, return_type = str)
    location_ssh_password = prompt_with_defaults("Enter ssh password: ", default_value = None, return_type = str)
    
    # Create the new location entry
    create_new_location_folder(all_locations_folder_path,
                               safe_location_name,
                               location_ip_address,
                               location_ssh_username,
                               location_ssh_password)
    
    # Provide some feedback
    has_ip_address = (location_ip_address not in [None, ""])
    ip_feedback = "@ {}".format(location_ip_address) if has_ip_address else "  -> No ip address specified!"
    print("",
          "Done! New location added ({})".format(safe_location_name),
          ip_feedback,
          "",
          "Don't forget to add cameras using the other editor tools!",
          sep = "\n")
    
    # Save new location as a default selection for convenience
    selector.save_location_select(safe_location_name)


# ---------------------------------------------------------------------------------------------------------------------
#%% Handle 'Update' selection

if selected_update:
    
    # First ask user to select an existing location to update
    location_select, location_path = selector.location()
    
    # Provide prompt to select what to update
    rename_option = "Rename location"
    modify_option = "Modify location info"
    options_menu_list = [rename_option, modify_option]
    select_idx, select_entry = select_from_list(options_menu_list,
                                                prompt_heading = "What would you like to do?",
                                                default_selection = None)
    
    # For convenience
    selected_rename = (select_entry == rename_option)
    selected_modify = (select_entry == modify_option)
    pathing_args = (all_locations_folder_path, location_select)
    
    # Handle different update options
    if selected_rename:
        prompt_for_location_rename(*pathing_args)
    elif selected_modify:
        prompt_for_modify_info(*pathing_args)
    
    # Save new location as a default selection for convenience
    selector.save_location_select(location_select)


# ---------------------------------------------------------------------------------------------------------------------
#%% Handle 'Delete' selection

if selected_delete:
    
    # First ask user to select an existing location to delete
    location_select, location_path = selector.location()
    
    # Confirm with user that they want to delete the selected location
    user_confirm = confirm("Are you sure you want to delete {}?".format(location_select), default_response = False)
    if user_confirm:
        
        # Check if there are camera entries for the selected location
        location_select_folder_path = selector.get_location_select_folder_path(location_select)
        camera_names_list, _ = build_camera_list(location_select_folder_path, show_hidden_cameras = True)
        location_has_camera_data = (len(camera_names_list) > 0)
        
        # If camera entries exist at the given location, prompt again to warn about deletion!
        user_secondary_confirm = False
        if location_has_camera_data:
            warning_msg = "{} has existing camera data which will also be deleted! Continue?".format(location_select)
            user_secondary_confirm = confirm(warning_msg, default_response = False)
        
        # Delete the entire location folder if confirmed!
        if user_secondary_confirm or (not location_has_camera_data):
            
            # Load location info (if possible) to print out with deletion (to minimize accidental data loss)
            location_info_dict = load_location_info_dict(all_locations_folder_path, location_select)
            
            # Delete the location folder & all contents!
            rmtree(location_path)
            
            # Provide some feedback
            printable_path = replace_user_home_pathing(location_path)
            print("",
                  "Done! Location deleted ({})".format(location_select),
                  "@ {}".format(printable_path),
                  "",
                  *get_printable_location_info(location_info_dict),
                  sep = "\n")
    
    pass


# ---------------------------------------------------------------------------------------------------------------------
#%% Handle 'View' selection

if selected_view:
    
    # First ask user to select an existing location to view
    location_select, location_path = selector.location()
    
    # Load existing info & print it out nicely for display
    location_info_dict = load_location_info_dict(all_locations_folder_path, location_select)
    print("",
          "Location info for {}".format(location_select),
          "",
          *get_printable_location_info(location_info_dict),
          sep = "\n")
    
    # Prompt to test ip connection
    user_confirm_test_ip = confirm("Test host address?", default_response = False)
    if user_confirm_test_ip:
        
        # Get host ip info
        host_ip, *_ = unpack_location_info_dict(location_info_dict)
        
        # Check if the connection is ok
        ip_is_valid, connection_success = check_host_connection(host_ip)
        
        # Feedback for bad ip
        if not ip_is_valid:
            display_ip = "({})".format(host_ip) if host_ip != "" else "(no address)"
            print("", "IP Address is not valid!", display_ip, "", sep = "\n")
        
        # Feedback if connection attempt succeeds
        if connection_success:
            print("", "Connection attempt was successful!", sep = "\n")
    
    # Save new location as a default selection for convenience
    selector.save_location_select(location_select)


# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap

'''
STOPPED HERE
- WILL NEED TO UPDATE 'CAMERAS TREE' FUNCTIONALITY TO REQUIRE A LOCATION SELECTION
    - DONT FORGET TO FIX OTHER DEPENDENCIES ON THIS CALL!!!
    - also need to look at build-location-tree (and build camera tree) functions in structures library
- FIRST THING TO UPDATE IS 'ADMIN TOOLS', SINCE THESE MAKE USE OF (CURRENTLY HACKY) LOCATION DATA
- THEN UPDATE OTHER EDITOR TOOLS! WILL NEED TO HAVE LOCATION SELECT ADDED TO EACH
- THEN LOOK INTO CLI SELECTIONS UPDATES AND STANDARD RUN/ARG PARSING EVERYWHERE ELSE
'''