#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Apr 30 16:59:14 2020

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

import datetime as dt

import requests

from local.lib.common.timekeeper_utils import parse_isoformat_string, get_local_datetime
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

def parse_cleandb_args(debug_print = False):
    
    # Set defaults
    default_protocol = get_dbserver_protocol()
    
    # Set arg help text
    protocol_help_text = "Specify the access protocol of the db server\n(Default: {})".format(default_protocol)
    
    # Set script arguments for running files
    args_list = [{"protocol": {"default": default_protocol, "help_text": protocol_help_text}}]
    
    # Provide some extra information when accessing help text
    script_description = "Delete data, by a cut-off date, at a specific site, for a single camera."
    
    # Build & evaluate script arguments!
    ap_result = script_arg_builder(args_list,
                                   description = script_description,
                                   debug_print = debug_print)
    
    return ap_result

# .....................................................................................................................

def build_request_url(server_url, *route_addons):
    
    # Force all add-ons to be strings
    addon_strs = [str(each_addon) for each_addon in route_addons]
    
    # Remove any leading/trails slashes from add-ons
    clean_addons = [each_addon.strip("/") for each_addon in addon_strs]
    
    # Combine add-ons to server url
    request_url = "/".join([server_url, *clean_addons])
    
    return request_url

# .....................................................................................................................

def build_delete_url(server_url, camera_select, collection_name, days_to_keep):
    
    ''' Helper function which just builds the deletion url for a given camera + collection + day cutoff '''
    
    days_to_keep_int = int(days_to_keep)
    delete_url = build_request_url(server_url, camera_select, collection_name, "delete", "by-cutoff", days_to_keep_int)
    
    return delete_url

# .....................................................................................................................

def build_delete_camerainfo_url(server_url, camera_select, days_to_keep = 5):
    return build_delete_url(server_url, camera_select, "camerainfo", days_to_keep)

# .....................................................................................................................

def build_delete_backgrounds_url(server_url, camera_select, days_to_keep = 5):
    return build_delete_url(server_url, camera_select, "backgrounds", days_to_keep)

# .....................................................................................................................

def build_delete_snapshots_url(server_url, camera_select, days_to_keep = 5):
    return build_delete_url(server_url, camera_select, "snapshots", days_to_keep)

# .....................................................................................................................

def build_delete_objects_url(server_url, camera_select, days_to_keep = 5):
    return build_delete_url(server_url, camera_select, "objects", days_to_keep)

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Network Functions

# .....................................................................................................................

def get_json(request_url, message_on_error = "Error requesting data!"):
    
    # Request data from the server
    post_response = requests.get(request_url)
    if post_response.status_code != 200:
        raise SystemError("{}\n@ {}".format(message_on_error, request_url))
    
    # Convert json response data to python data type
    return_data = post_response.json()
    
    return return_data

# .....................................................................................................................

def request_camera_list(server_url):
    
    # Build route for requesting camera names and make request
    request_url = build_request_url(server_url, "get-all-camera-names")
    camera_names_list = get_json(request_url)
    
    return camera_names_list

# .....................................................................................................................

def request_bounding_times(server_url, camera_select):
    
    # Build route for requesting the bounding times for the snapshots of the given camera
    request_url = build_request_url(server_url, camera_select, "snapshots", "get-bounding-times")
    snapshot_bounding_times_dict = get_json(request_url)
    
    return snapshot_bounding_times_dict

# .....................................................................................................................

def print_response_feedback(response_dict, collection_name):
    
    '''
    Helper function for printing deletion feedback 
    Assumes responses formatted as follows (as an example):
        {
           "deletion_datetime":"2020-04-27 16:57:53",
           "deletion_epoch_ms":1588021073069,
           "time_taken_ms":1,
           "mongo_response": {
                                "acknowledged":true,
                                "deleted_count":0,
                                "raw_result": {
                                                 "n":0,
                                                 "ok":1.0
                                              }
                             }
        }
    '''
    
    # Pull out the raw data we want to print
    delete_datetime = response_dict.get("deletion_datetime", "unknown delete date!")
    time_taken_ms = response_dict.get("time_taken_ms", -1)
    num_deleted = response_dict.get("mongo_response", {}).get("deleted_count", -1)
    
    # Print in nicer format
    print("",
          "Results for {}:".format(collection_name),
          "  Deletion cut-off date: {}".format(delete_datetime),
          "  Number of files deleted: {}".format(num_deleted),
          "  Took {} ms".format(time_taken_ms),
          sep = "\n")
    
    return

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Get system pathing info

# Create selector to handle camera selection & project pathing
selector = Resource_Selector()
project_root_path, cameras_folder_path = selector.get_project_pathing()
user_select = "live"


# ---------------------------------------------------------------------------------------------------------------------
#%% Parse script args

# Get script arguments
ap_result = parse_cleandb_args()
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

# First get a list of available cameras from the server
camera_names_list = request_camera_list(server_url)

# Prompt user to select which camera they'd like to delete data from
select_idx, camera_select = cli_select_from_list(camera_names_list, "Select camera:")

# Request info about the time range from the database
snap_bounding_times_dict = request_bounding_times(server_url, camera_select)
bounding_start_dt = parse_isoformat_string(snap_bounding_times_dict["min_datetime_isoformat"])
bounding_end_dt = parse_isoformat_string(snap_bounding_times_dict["max_datetime_isoformat"])
print("",
      "Data at {} ranges from:".format(camera_select),
      "{} (start)".format(bounding_start_dt),
      "{} (end)".format(bounding_end_dt),
      sep = "\n")

# Prompt for the number of days to keep
days_to_keep = cli_prompt_with_defaults("Number of days to keep: ", default_value = 5, return_type = int)

# Finally, confirm the deletion, since it's kinda permanent!
selected_deletion_dt = get_local_datetime() - dt.timedelta(days = days_to_keep)
seconds_to_be_deleted = (selected_deletion_dt - bounding_start_dt).total_seconds()
days_to_be_deleted = max(0, (seconds_to_be_deleted / (60 * 60 * 24)))
user_confirm_delete = cli_confirm("Will delete {:.1f} days of data. Are you sure?".format(days_to_be_deleted))
if not user_confirm_delete:
    print("", "Deletion at {} cancelled!".format(camera_select))
    ide_quit()
    

# ---------------------------------------------------------------------------------------------------------------------
#%% Start sending deletion requests!

# Bundle shared parhing/selection args
url_args = (server_url, camera_select, days_to_keep)

# Build urls
caminfo_url = build_delete_camerainfo_url(*url_args)
backgrounds_url = build_delete_backgrounds_url(*url_args)
object_url = build_delete_objects_url(*url_args)
snapshots_url = build_delete_snapshots_url(*url_args)

# Start requesting deletes!
print("", "Deleting camera info...", sep = "\n")
caminfo_delete_response = get_json(caminfo_url, "Error deleting camera info")
print_response_feedback(caminfo_delete_response, "camera info")

print("", "Deleting backgrounds...", sep = "\n")
backgrounds_delete_response = get_json(backgrounds_url, "Error deleting backgrounds")
print_response_feedback(backgrounds_delete_response, "backgrounds")

print("", "Deleting objects...", sep = "\n")
objects_delete_response = get_json(object_url, "Error deleting objects")
print_response_feedback(objects_delete_response, "objects")

print("", "Deleting snapshots...", sep = "\n")
snapshots_delete_response = get_json(snapshots_url, "Error deleting snapshots")
print_response_feedback(snapshots_delete_response, "snapshots")


# ---------------------------------------------------------------------------------------------------------------------
#%% Clean up
    
# Add a blank space at the end for aesthetics
print("")

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap


