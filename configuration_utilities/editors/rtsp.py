#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Jun 23 11:46:35 2020

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

import cv2

from local.lib.ui_utils.cli_selections import Resource_Selector
from local.lib.ui_utils.editor_lib import select_from_list, prompt_with_defaults, confirm

from local.lib.file_access_utils.video import create_new_rtsp_config, unpack_rtsp_config
from local.lib.file_access_utils.video import load_rtsp_config, save_rtsp_config

from local.eolib.utils.network import build_rtsp_string, check_connection
from local.eolib.utils.cli_tools import Color
from local.eolib.utils.misc import blank_str_to_none, none_to_blank_str


# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

def print_rtsp_info(camera_select, rtsp_config_dict):
    
    '''
    Helper function which prints out rtsp components and full rtsp string
    Meant to allow user to review rtsp configuration
    
    Inputs:
        camera_select -> (String) Name of camera for which the RTSP info is being display
        
        rtsp_config_dict -> (Dictionary) Provided RTSP configuration to be printed
    
    Outputs:
        rtsp_string_is_valid (boolean)
    '''
    
    # Build list of strings for each rtsp component
    print_keys = ["IP Address", "Username", "Password", "Port", "Route"]
    ip_address, username, password, port, route = unpack_rtsp_config(rtsp_config_dict)
    longest_key = max([len(each_key) for each_key in print_keys])
    key_name_list = [each_key.rjust(longest_key) for each_key in print_keys]
    zipped_data = zip(key_name_list, [ip_address, username, password, port, route])
    rtsp_component_list = ["  {}: {}".format(each_name, each_val) for each_name, each_val in zipped_data]
    
    # Also build full rtsp string for display
    invalid_indicator = "(invalid)"
    rtsp_string = build_rtsp_string(**rtsp_config_dict, when_ip_is_bad_return = invalid_indicator)
    rtsp_string_is_valid = (rtsp_string != invalid_indicator)
    
    # Print out rtsp configuration data
    print("",
          "",
          Color("RTSP info for: {}".format(camera_select)).bold,
          "",
          Color("Components:").underline,
          "\n".join(rtsp_component_list),
          "",
          Color("URL:").underline,
          "  {}".format(rtsp_string),
          "", sep="\n")
    
    return rtsp_string_is_valid

# .....................................................................................................................

def prompt_to_enter_rtsp_components(camera_select, current_rtsp_dict):
    
    # Unpack current rtsp configuration to use as default values
    curr_ip_address, curr_username, curr_password, curr_port, curr_route = unpack_rtsp_config(current_rtsp_dict)
    
    # Convert empty entries
    default_ip_address = blank_str_to_none(curr_ip_address)
    default_username = blank_str_to_none(curr_username)
    default_password = blank_str_to_none(curr_password)
    default_route = blank_str_to_none(curr_route)
    
    # Don't bother asking the user for the port, just copy existing data or set to 554 if not provided
    hardcoded_port = 554 if curr_port is None else curr_port
    
    # Provide some indication of what's happening
    print("",
          "------------------------",
          " Enter RTSP components: ",
          "(use . to clear entries)",
          "------------------------",
          "", sep = "\n")
    
    # Ask user for each rtsp component
    ui_ip_address = prompt_with_defaults("Enter ip address: ", default_ip_address, dot_response = "")
    ui_username =   prompt_with_defaults("  Enter username: ", default_username, dot_response = "")
    ui_password =   prompt_with_defaults("  Enter password: ", default_password, dot_response = "")
    ui_route =      prompt_with_defaults("     Enter route: ", default_route, dot_response = "")
    
    # Clean up inputs (replace None with empty strings)
    new_ip_address = none_to_blank_str(ui_ip_address)
    new_username = none_to_blank_str(ui_username)
    new_password = none_to_blank_str(ui_password)
    new_port = hardcoded_port
    new_route = none_to_blank_str(ui_route)
    
    # Build new rtsp config
    new_rtsp_dict = create_new_rtsp_config(new_ip_address, new_username, new_password, new_port, new_route)
    
    return new_rtsp_dict

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Get pathing

# Set up resource selector
selector = Resource_Selector(load_selection_history = True,
                             save_selection_history = True,
                             show_hidden_resources = False,
                             create_folder_structure_on_select = True)

project_root_path, cameras_folder_path = selector.get_cameras_root_pathing()

# Get this script name for display
this_script_path = os.path.abspath(__file__)
this_script_name = os.path.basename(this_script_path)
this_file_name, _ = os.path.splitext(this_script_name)


# ---------------------------------------------------------------------------------------------------------------------
#%% Provide top-level options

# Prompt for options
entry_option = "Enter info"
view_option = "View string"
test_option = "Test connection"
options_menu_list = [entry_option, view_option, test_option]
select_idx, select_entry = select_from_list(options_menu_list,
                                            prompt_heading = "Select an option ({})".format(this_file_name),
                                            default_selection = None)

# For convenience/clarity
selected_entry = (select_entry == entry_option)
selected_view = (select_entry == view_option)
selected_test = (select_entry == test_option)


# ---------------------------------------------------------------------------------------------------------------------
#%% Handle 'Entry' selection

if selected_entry:
    
    # First ask user to select a camera
    camera_select, camera_path = selector.camera()
    
    # Load rtsp info
    curr_rtsp_dict, curr_rtsp_string = load_rtsp_config(cameras_folder_path, camera_select)
    
    # Prompt to enter new RTSP components
    new_rtsp_dict = prompt_to_enter_rtsp_components(camera_select, curr_rtsp_dict)
    
    # Display full string for user examination
    rtsp_is_valid = print_rtsp_info(camera_select, new_rtsp_dict)
    
    # Have user confirm saving
    if rtsp_is_valid:
        user_confirm = confirm("Save this configuration?", default_response = True)
        if user_confirm:
            save_rtsp_config(cameras_folder_path, camera_select, new_rtsp_dict)
    
    pass
    

# ---------------------------------------------------------------------------------------------------------------------
#%% Handle 'View' selection

if selected_view:
    
    # First ask user to select a camera
    camera_select, camera_path = selector.camera()
    
    # Load rtsp info
    rtsp_config_dict, rtsp_string = load_rtsp_config(cameras_folder_path, camera_select)
    
    # Build full RTSP string and display for examination
    print_rtsp_info(camera_select, rtsp_config_dict)


# ---------------------------------------------------------------------------------------------------------------------
#%% Handle 'Test' selection

if selected_test:
    
    # First ask user to select a camera
    camera_select, camera_path = selector.camera()
    
    # Load rtsp info
    rtsp_config_dict, rtsp_string = load_rtsp_config(cameras_folder_path, camera_select)
    
    # First check the ip/port connection is valid
    ip_address, _, _, port, _ = unpack_rtsp_config(rtsp_config_dict)
    print("", "Checking address ({}:{})".format(ip_address, port), sep = "\n")
    address_is_valid = check_connection(ip_address, port)
    print("  Success" if address_is_valid else "  Bad address or connection!")
    
    # If the initial attempt worked, try a video capture connection, to see if we can access the image data
    if address_is_valid:
        print("", "Checking video stream...", "  {}".format(rtsp_string), sep="\n")
        try:
            vcap = cv2.VideoCapture(rtsp_string)
            (got_frame, frame) = vcap.read()
            vcap.release()
            
            # It's possible (when unauthorized for example) to get through here without errors
            # However, if the connection worked, we should have gotten frame data
            if got_frame:
                print("", "Success!", "", sep="\n")
            else:
                print("",
                      "Error connecting to video stream!",
                      "  Possibly a bad username/password",
                      "  or otherwise a bad route!",
                      "", sep = "\n")
            
        except cv2.error as err:
            print("", "Error connecting to video stream!", "", str(err), sep = "\n")
    
    pass


# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap

