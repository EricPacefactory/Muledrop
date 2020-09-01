#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Jul 21 14:18:50 2020

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

from local.lib.common.environment import get_env_location_select, get_dbserver_port, get_ctrlserver_port

from local.lib.file_access_utils.shared import build_location_path, url_safe_name
from local.lib.file_access_utils.json_read_write import save_config_json, load_config_json

from local.eolib.utils.files import get_folder_list
from local.eolib.utils.misc import reorder_list


# ---------------------------------------------------------------------------------------------------------------------
#%% Define pathing functions

# .....................................................................................................................

def build_location_info_file_path(all_locations_folder_path, location_select):
    return build_location_path(all_locations_folder_path, location_select, "location_info.json")

# .....................................................................................................................

def load_location_info_dict(all_locations_folder, location_select, error_if_missing = True):
    
    ''' Function which loads the location info data as a dictionary '''
    
    # Build pathing to the given location info file
    location_info_path = build_location_info_file_path(all_locations_folder, location_select)
    
    # Try to load the location info, if possible
    location_info_dict = load_config_json(location_info_path, error_if_missing)
    if location_info_dict is None:
        location_info_dict = {}
    
    return location_info_dict

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% I/O functions

# .....................................................................................................................

def save_location_info_dict(all_locations_folder_path, location_select, location_info_dict,
                            create_missing_folder_path = True):
    
    '''
    Function which saves location info data for a selected location
    Can optionally create the corresponding location folder if needed
    '''
    
    # Build pathing & save
    save_path = build_location_info_file_path(all_locations_folder_path, location_select)
    save_config_json(save_path, location_info_dict, create_missing_folder_path)
    
    return save_path

# .....................................................................................................................

def create_new_location_folder(all_locations_folder_path, location_name,
                               ip_address, ssh_username, ssh_password,
                               dbserver_port = None, ctrlserver_port = None):
    
    ''' Function which manages creation of new location folders & initializes location info '''
    
    # Create a (default) location info file
    create_location_info_file(all_locations_folder_path,
                              location_name,
                              ip_address,
                              ssh_username,
                              ssh_password,
                              dbserver_port,
                              ctrlserver_port)
    
    # Create default gitignore & readme files, in case the created location is tracked with git
    create_location_gitignore(all_locations_folder_path, location_name)
    create_location_readme(all_locations_folder_path, location_name)
    
    return

# .....................................................................................................................

def create_location_info_file(all_locations_folder_path, location_name,
                              ip_address, ssh_username, ssh_password,
                              dbserver_port = None, ctrlserver_port = None):
    
    '''
    Helper function used to create a location info file, used to store
    location-specific information within a given location folder
    '''
    
    # Get default server ports on creation in case ports aren't provided
    default_dbserver_port = get_dbserver_port()
    default_ctrlserver_port = get_ctrlserver_port()
    
    # Build location info to save with location folder
    location_info_dict = build_location_info_dict(ip_address,
                                                  ssh_username,
                                                  ssh_password,
                                                  dbserver_port if dbserver_port else default_dbserver_port,
                                                  ctrlserver_port if ctrlserver_port else default_ctrlserver_port)
    
    # Save the location info entry
    safe_location_name = url_safe_name(location_name)
    new_location_path = save_location_info_dict(all_locations_folder_path, safe_location_name, location_info_dict)
    
    return new_location_path

# .....................................................................................................................

def create_location_gitignore(all_locations_folder_path, location_name):
    
    ''' Helper function used to create default gitignore files for new locations '''
    
    # Create default gitignore file contents
    gitignore_str_list = ["# Authentication/Access info",
                          "location_info.json",
                          "",
                          "# Local data folders",
                          "*/logs/",
                          "*/report/",
                          "*/resources/videos/",
                          "*/resources/backgrounds/",
                          "", ""]
    
    # Build pathing to gitignore file
    location_gitignore_path = build_location_path(all_locations_folder_path, location_name, ".gitignore")
    
    # Write the contents directly into a file
    gitignore_str_to_write = "\n".join(gitignore_str_list)
    with open(location_gitignore_path, "w") as out_file:
        out_file.write(gitignore_str_to_write)
    
    return location_gitignore_path

# .....................................................................................................................

def create_location_readme(all_locations_folder_path, location_name):
    
    ''' Helper function used to create default readme markdown file for new locations '''
    
    # Create default readme file contents
    readme_str_list = ["# Location: {}".format(location_name),
                       "",
                       "This repo contains all camera configuration files for this location.",
                       "",
                       "---",
                       "",
                       "#### Notes:",
                       "",
                       "- None so far! Please don't store username/passwords here!",
                       "", ""]
    
    # Build pathing to readme file
    location_readme_path = build_location_path(all_locations_folder_path, location_name, "README.md")
    
    # Write the contents directly into a file
    readme_str_to_write = "\n".join(readme_str_list)
    with open(location_readme_path, "w") as out_file:
        out_file.write(readme_str_to_write)
    
    return location_readme_path

# .....................................................................................................................

def build_location_info_dict(host_ip, ssh_username, ssh_password, dbserver_port, ctrlserver_port):
    
    ''' Helper function used to create consistently formatted location info data '''
    
    location_info_dict = {"host": host_ip,
                          "ssh_username": ssh_username,
                          "ssh_password": ssh_password,
                          "dbserver_port": dbserver_port,
                          "ctrlserver_port": ctrlserver_port}
    
    return location_info_dict

# .....................................................................................................................

def unpack_location_info_dict(location_info_dict):
    
    '''
    Helper function which retrieves location info in a consistent order.
    Used to avoid requiring knowledge of keyname/lookups
    
    Inputs:
        location_info_dict -> (Dictionary) A set of location info that should be unpacked
    
    Outputs:
        host, ssh_username, ssh_password, dbserver_port, ctrlserver_port
    
    Note: The ports will be integer values (or None), all others are strings or None
    '''
    
    # Pull out info with defaults
    host_ip = location_info_dict.get("host", None)
    ssh_username = location_info_dict.get("ssh_username", None)
    ssh_password = location_info_dict.get("ssh_password", None)
    dbserver_port = location_info_dict.get("dbserver_port", None)
    ctrlserver_port = location_info_dict.get("ctrlserver_port", None)
    
    return host_ip, ssh_username, ssh_password, dbserver_port, ctrlserver_port

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Helper functions

# .....................................................................................................................

def create_default_location(all_locations_folder_path):
    
    '''
    Helper function used to create a 'default' location folder
    Will only create a folder if no other location folders exist!
    '''
    
    # Check if locations already exist, in which case do nothing
    existing_location_folders, _ = build_location_list(all_locations_folder_path, show_hidden_locations = False)
    locations_already_exist = (len(existing_location_folders) > 0)
    if locations_already_exist:
        return
    
    # Figure out what to use as a default location name
    default_location_name = get_env_location_select()
    if default_location_name is None:
        default_location_name = "localhost"
    
    # Set ssh defaults
    default_host_ip = "localhost"
    default_ssh_username = None
    default_ssh_password = None
    
    # Create the default location folder!
    create_new_location_folder(all_locations_folder_path, default_location_name,
                               ip_address = default_host_ip,
                               ssh_username = default_ssh_username,
                               ssh_password = default_ssh_password)
    
    return

# .....................................................................................................................

def build_location_list(all_locations_folder_path, show_hidden_locations = False):
    
    ''' Function which returns all location names & corresponding folder paths '''
    
    # Find all the location folders within the 'locations' folder
    location_paths_list = get_folder_list(all_locations_folder_path,
                                          show_hidden_folders = show_hidden_locations,
                                          create_missing_folder = False,
                                          return_full_path = True)
    location_name_list = [os.path.basename(each_path) for each_path in location_paths_list]
    
    # Re-order so that localhost is always at the top of the list
    localhost_in_list = ("localhost" in location_name_list)
    if localhost_in_list:
        localhost_index = location_name_list.index("localhost")
        localhost_name = location_name_list.pop(localhost_index)
        localhost_path = location_paths_list.pop(localhost_index)
        location_name_list.insert(0, localhost_name)
        location_paths_list.insert(0, localhost_path)
    
    return location_name_list, location_paths_list

# .....................................................................................................................

def get_printable_location_info(location_info_dict):
    
    # Get location info into a more printable format(i.e. list of key: value)
    nice_order_hints = ["host", "ssh_user", "ssh_pass"]
    nice_key_order = reorder_list(location_info_dict.keys(), nice_order_hints, add_nonmatch_to_end = True)
    longest_key_len = max([len(each_key) for each_key in nice_key_order])
    info_print_str_list = []
    for each_key in nice_key_order:
        padded_key_name = each_key.rjust(longest_key_len)
        new_print_str = "  {}: {}".format(padded_key_name, location_info_dict[each_key])
        info_print_str_list.append(new_print_str)
    
    return info_print_str_list

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Demo

if __name__ == "__main__":
    
    pass

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap


