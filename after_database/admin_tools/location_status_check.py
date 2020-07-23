#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu May 14 11:14:08 2020

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

import requests

from collections import OrderedDict

from local.lib.common.environment import get_dbserver_protocol
from local.lib.common.timekeeper_utils import isoformat_to_datetime, get_local_datetime
from local.lib.common.feedback import print_time_taken_sec

from local.lib.ui_utils.cli_selections import Resource_Selector
from local.lib.ui_utils.script_arguments import script_arg_builder

from local.lib.file_access_utils.locations import load_location_info_dict, unpack_location_info_dict

from local.online_database.post_to_dbserver import check_server_connection

from local.eolib.utils.quitters import ide_quit


# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes

# .....................................................................................................................

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Define shared functions

# .....................................................................................................................

def parse_statuscheck_args(debug_print = False):
    
    # Set defaults
    default_protocol = get_dbserver_protocol()
    
    # Set arg help text
    protocol_help_text = "Specify the access protocol of the db server\n(Default: {})".format(default_protocol)
    
    # Set script arguments for running files
    args_list = [{"protocol": {"default": default_protocol, "help_text": protocol_help_text}}]
    
    # Provide some extra information when accessing help text
    script_description = "Run a status check for a given location to see whether cameras are running properly"
    
    # Build & evaluate script arguments!
    ap_result = script_arg_builder(args_list,
                                   description = script_description,
                                   debug_print = debug_print)
    
    return ap_result

# .....................................................................................................................

def build_url(server_url, *route_addons):
    
    # Force all add-ons to be strings
    addon_strs = [str(each_addon) for each_addon in route_addons]
    
    # Remove any leading/trails slashes from add-ons
    clean_addons = [each_addon.strip("/") for each_addon in addon_strs]
    
    # Combine add-ons to server url
    request_url = "/".join([server_url, *clean_addons])
    
    return request_url

# .....................................................................................................................

def build_newest_camerainfo_url(server_url, camera_select):
    return build_url(server_url, camera_select, "camerainfo", "get-newest-metadata")

# .....................................................................................................................

def build_newest_snapshot_url(server_url, camera_select):
    return build_url(server_url, camera_select, "snapshots", "get-newest-metadata")

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Network Functions

# .....................................................................................................................

def get_json(request_url, message_on_error = "Error requesting data!", raise_error = True):
    
    # Request data from the server
    post_response = requests.get(request_url)
    if post_response.status_code != 200:
        if raise_error:
            raise SystemError("{}\n@ {}".format(message_on_error, request_url))
        return None
    
    # Convert json response data to python data type
    return_data = post_response.json()
    
    return return_data

# .....................................................................................................................

def request_camera_list(server_url):
    
    # Build route for requesting camera names and make request
    request_url = build_url(server_url, "get-all-camera-names")
    camera_names_list = get_json(request_url)
    
    return camera_names_list

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Parse script args

# Get script arguments
ap_result = parse_statuscheck_args()
dbserver_protocol = ap_result["protocol"]


# ---------------------------------------------------------------------------------------------------------------------
#%% Get system pathing info

# Create selector to handle project pathing & location selection
selector = Resource_Selector()
project_root_path, all_locations_folder_path = selector.get_shared_pathing()


# ---------------------------------------------------------------------------------------------------------------------
#%% Set up access to data server

# Select location to communicate with
location_select, location_path = selector.location()

# Get location connection info
location_info_dict = load_location_info_dict(all_locations_folder_path, location_select, error_if_missing = True)
host_ip, _, _, dbserver_port, _ = \
unpack_location_info_dict(location_info_dict)

# Build server url & confirm it's accessible before we try to request data from it
server_url = "{}://{}:{}".format(dbserver_protocol, host_ip, dbserver_port)
print("", "Checking connection ({})".format(server_url), sep = "\n")
connection_is_valid = check_server_connection(server_url)
if not connection_is_valid:
    ide_quit("Couldn't connect to data server! ({})".format(server_url))
print("  --> Success")


# ---------------------------------------------------------------------------------------------------------------------
#%% Get camera listing from the database

# Get camera names to check
camera_names_list = request_camera_list(server_url)
longest_name_len = max([len(each_name) for each_name in camera_names_list])

# Get the current time, so we can compare to camera metadata
current_dt = get_local_datetime()


# ---------------------------------------------------------------------------------------------------------------------
#%% Print camera lifetimes

# For clarity
seconds_per_hour = (60.0 * 60.0)

# Print out camera lifetime data as a group for comparison
print("", "Camera lifetimes:", sep = "\n")
for each_camera_name in camera_names_list:
    
    # Build urls to request newest data, for each camera
    caminfo_url = build_newest_camerainfo_url(server_url, each_camera_name)
    
    # Download newest data
    newest_caminfo_metadata = get_json(caminfo_url, "Error requesting newest camera info!")
    
    # Get timing info from metadata
    camera_start_dt_isoformat = newest_caminfo_metadata["start_datetime_isoformat"]
    camera_start_dt = isoformat_to_datetime(camera_start_dt_isoformat)
    
    # Get 'time since' newest entries
    camera_lifetime_sec = (current_dt - camera_start_dt).total_seconds()
    
    # Convert times to more readable format & print
    camera_lifetime_hrs = int((camera_lifetime_sec / seconds_per_hour))
    print("  {}: {:.0f} hrs".format(each_camera_name.rjust(longest_name_len), camera_lifetime_hrs))


# ---------------------------------------------------------------------------------------------------------------------
#%% Print snapshot ages

# Print out snapshot age data as a group for easier comparison
print("", "Most recent snapshot:", sep = "\n")
for each_camera_name in camera_names_list:
    
    # Build url to request snapshot data
    snap_url = build_newest_snapshot_url(server_url, each_camera_name)
    newest_snap_metadata = get_json(snap_url, "Error requesting newest snapshot info!")
    
    # Get timing from metadata
    snap_dt_isoformat = newest_snap_metadata["datetime_isoformat"]
    snap_dt = isoformat_to_datetime(snap_dt_isoformat)
    
    # Get 'time since' newest entry
    snap_age_sec = (current_dt - snap_dt).total_seconds()
    
    # Convert times to more readable format & print
    print("  {}: {:.0f} sec".format(each_camera_name.rjust(longest_name_len), snap_age_sec))

# Add a blank space at the end for aesthetics
print("")


# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap

# TODO
# - add coloring to indicate good/bad status
# - add additional info (warn about overly large video width/height compared to snap width/height)
# 
