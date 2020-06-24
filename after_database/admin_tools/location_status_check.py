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

from local.lib.common.timekeeper_utils import isoformat_to_datetime, get_local_datetime
from local.lib.common.environment import get_dbserver_protocol

from local.lib.ui_utils.cli_selections import Resource_Selector
from local.lib.ui_utils.script_arguments import script_arg_builder

from local.online_database.post_to_dbserver import check_server_connection

from local.lib.file_access_utils.settings import load_locations_info, get_nice_location_names_list

from local.eolib.utils.quitters import ide_quit
from local.eolib.utils.cli_tools import cli_select_from_list, cli_confirm, cli_prompt_with_defaults


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
    return build_url(server_url, camera_select, "camerainfo", "get-newest-camera-info")
    # After most recent update
    return build_url(server_url, camera_select, "camerainfo", "get-newest-metadata")

# .....................................................................................................................

def build_newest_snapshot_url(server_url, camera_select):
    return build_url(server_url, camera_select, "snapshots", "get-newest-metadata")

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Feedback Functions

# .....................................................................................................................

def seconds_to_readable_time_string(num_seconds):
    
    # Get time in different units
    num_mins = (num_seconds / 60)
    num_hours = (num_mins / 60)
    num_days = (num_hours / 24)
    
    # Decide what 'scale' to print in
    if num_days > 1.0:
        num_whole_days = int(num_days)
        num_remaining_hours = (num_days - num_whole_days) * 24
        readable_time_string = "{:.0f} days, {:.0f} hours".format(num_whole_days, num_remaining_hours)
        
    elif num_hours > 1.0:
        num_whole_hours = int(num_hours)
        num_remaining_mins = (num_hours - num_whole_hours) * 60
        readable_time_string = "{:.0f} hours, {:.0f} minutes".format(num_whole_hours, num_remaining_mins)
        
    elif num_mins > 1.0:
        num_whole_mins = int(num_mins)
        num_remaining_sec = (num_seconds - (60 * num_whole_mins))
        readable_time_string = "{:.0f} minutes, {:.0f} seconds".format(num_whole_mins, num_remaining_sec)
        
    elif num_seconds > 0.5:
        readable_time_string = "{:.0f} seconds".format(num_seconds)
        
    else:
        num_millis = (num_seconds * 1000)
        readable_time_string = "{:.0f} ms".format(num_millis)
    
    return readable_time_string

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
#%% Get system pathing info

# Create selector to handle camera selection & project pathing
selector = Resource_Selector()
project_root_path = selector.get_project_root_pathing()


# ---------------------------------------------------------------------------------------------------------------------
#%% Parse script args

# Get script arguments
ap_result = parse_statuscheck_args()
dbserver_protocol = ap_result["protocol"]


# ---------------------------------------------------------------------------------------------------------------------
#%% Set up access to data server

# Get user to select the server to download from
locations_info_dict = load_locations_info(project_root_path)
location_names_list = get_nice_location_names_list(locations_info_dict)
_, location_name_select = cli_select_from_list(location_names_list, "Select location:", default_selection = "local")

# Get dbserver access info
location_select_dict = locations_info_dict[location_name_select]
dbserver_host = location_select_dict["host"]
dbserver_port = location_select_dict["dbserver_port"]

# Build server url
server_url = "{}://{}:{}".format(dbserver_protocol, dbserver_host, dbserver_port)

# Check that the server is accessible before we try requesting data from it
connection_is_valid = check_server_connection(server_url)

# Bail if we couldn't connect to the server, with some kind of feedback
if not connection_is_valid:
    ide_quit("Couldn't connect to data server! ({})".format(server_url))
    

# ---------------------------------------------------------------------------------------------------------------------
#%% Get camera list from the database

# Get current time, so we can compare to camera metadata
current_dt = get_local_datetime()

# First get a list of available cameras from the server
camera_names_list = request_camera_list(server_url)

# Run check on every known camera
for each_camera_name in camera_names_list:
    
    # Build urls to request newest data, for each camera
    caminfo_url = build_newest_camerainfo_url(server_url, each_camera_name)
    snap_url = build_newest_snapshot_url(server_url, each_camera_name)
    
    # Download newest data
    newest_caminfo_metadata = get_json(caminfo_url, "Error requesting newest camera info!")
    newest_snap_metadata = get_json(snap_url, "Error requesting newest snapshot info!")
    
    # Get timing info from metadata
    camera_start_dt_isoformat = newest_caminfo_metadata["start_datetime_isoformat"]
    snap_dt_isoformat = newest_snap_metadata["datetime_isoformat"]
    
    # Convert isoformat times to datetime objects for convenience
    camera_start_dt = isoformat_to_datetime(camera_start_dt_isoformat)
    snap_dt = isoformat_to_datetime(snap_dt_isoformat)
    
    # Get 'time since' newest entries
    camera_lifetime_sec = (current_dt - camera_start_dt).total_seconds()
    snap_age_sec = (current_dt - snap_dt).total_seconds()
    
    # Convert times to more readable strings
    camera_lifetime_str = seconds_to_readable_time_string(camera_lifetime_sec)
    snap_age_sec = seconds_to_readable_time_string(snap_age_sec)
    
    # Print info
    print("",
          "{} - Active for {}".format(each_camera_name, camera_lifetime_str),
          "  Recent data: {}".format(snap_age_sec),
          sep = "\n")


# ---------------------------------------------------------------------------------------------------------------------
#%% Clean up
    
# Add a blank space at the end for aesthetics
print("")

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap

# TODO
# - improve print-out aesthetics (better alignment at least?)
# - add coloring to indicate good/bad status
# - add additional info (warn abotu overly large video width/height compared to snap width/height)
# 
