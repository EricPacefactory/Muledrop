#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Mar  3 16:21:42 2020

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

from tqdm import tqdm

from local.lib.ui_utils.cli_selections import Resource_Selector

from local.online_database.auto_post import check_server_connection

from local.lib.file_access_utils.reporting import build_camera_info_metadata_report_path
from local.lib.file_access_utils.reporting import build_snapshot_metadata_report_path
from local.lib.file_access_utils.reporting import build_object_metadata_report_path
from local.lib.file_access_utils.reporting import build_background_metadata_report_path
from local.lib.file_access_utils.reporting import build_snapshot_image_report_path
from local.lib.file_access_utils.reporting import build_background_image_report_path

'''
from local.lib.file_access_utils.classifier import build_classifier_adb_metadata_report_path
from local.lib.file_access_utils.summary import build_summary_adb_metadata_report_path
from local.lib.file_access_utils.rules import build_rule_adb_info_report_path
from local.lib.file_access_utils.rules import build_rule_adb_metadata_report_path
'''

from local.lib.file_access_utils.read_write import save_jgz

from eolib.utils.quitters import ide_quit
from eolib.utils.cli_tools import cli_select_from_list


# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes

# .....................................................................................................................

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Define posting functions

# .....................................................................................................................

# request snapshot md
# request snapshot images

# request background md
# request background images

# request camerainfo md
# request object md

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Define shared functions

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

def save_network_jpg(request_url, save_path):
    
    image_data = requests.get(request_url)
    with open(save_path, 'wb') as out_file:
        out_file.write(image_data.content)
    del image_data
    
    return

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

# ---------------------------------------------------------------------------------------------------------------------
#%% Camera info functions

# .....................................................................................................................

def request_caminfo_metadata(server_url, camera_select):
    
    # Build route for requesting all camera info metadata
    request_url = build_request_url(server_url, camera_select, "camerainfo", "get-all-camera-info")
    
    # Grab camera info data (with feedback)
    print("", "Downloading camera info metadata...", sep = "\n", end = " ")
    many_caminfo_metadata_list = get_json(request_url)
    
    return many_caminfo_metadata_list

# .....................................................................................................................

def save_caminfo_metadata(cameras_folder_path, camera_select, user_select, caminfo_metadata_list):
    
    # Make sure the camera info metadata reporting folder exists
    base_save_folder = build_camera_info_metadata_report_path(cameras_folder_path, camera_select, user_select)
    os.makedirs(base_save_folder, exist_ok = True)
    
    # Loop through all the requested metadata and save back into the filesystem
    print("Saving object metadata")
    for each_metadata_dict in tqdm(caminfo_metadata_list):
        caminfo_start_epoch_ms = each_metadata_dict["start_epoch_ms"]
        file_name = "dlcaminfo-{}.json.gz".format(caminfo_start_epoch_ms)
        save_path = os.path.join(base_save_folder, file_name)
        save_jgz(save_path, each_metadata_dict)
        
    return

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Backgrounds functions

# .....................................................................................................................

def request_background_metadata(server_url, camera_select, start_epoch_ms, end_epoch_ms):
    
    # Build route for requesting all metadata between a start/end time
    request_url = build_request_url(server_url, camera_select, "backgrounds",
                                    "get-many-metadata", "by-time-range", 
                                    start_epoch_ms, end_epoch_ms)
    
    print("", "Downloading snapshot metadata...", sep = "\n", end = " ")
    many_background_metadata_list = get_json(request_url)
    
    return many_background_metadata_list

# .....................................................................................................................

def save_background_metadata(cameras_folder_path, camera_select, user_select, background_metadata_list):
    
    # Make sure the background metadata reporting folder exists
    base_save_folder = build_background_metadata_report_path(cameras_folder_path, camera_select, user_select)
    os.makedirs(base_save_folder, exist_ok = True)
    
    # Loop through all the requested metadata and save back into the filesystem
    print("Saving background metadata")
    for each_metadata_dict in tqdm(background_metadata_list):
        bg_epoch_ms = each_metadata_dict["epoch_ms"]
        file_name = "dlsnap-{}.json.gz".format(bg_epoch_ms)
        save_path = os.path.join(base_save_folder, file_name)
        save_jgz(save_path, each_metadata_dict)
        
    return

# .....................................................................................................................

def save_background_images(server_url, cameras_folder_path, camera_select, user_select, background_metadata_list):
    
    # Make sure the image reporting folder exists
    base_save_folder = build_background_image_report_path(cameras_folder_path, camera_select, user_select)
    os.makedirs(base_save_folder, exist_ok = True)
        
    # Loop through all the requested metadata and request + save the correspond images
    print("", "Downloading & saving background images", sep = "\n")
    for each_metadata_dict in tqdm(background_metadata_list):
        
        # Build pathing info
        bg_epoch_ms = each_metadata_dict["epoch_ms"]
        file_name = "{}.jpg".format(bg_epoch_ms)
        save_path = os.path.join(base_save_folder, file_name)
        
        # Build route for requesting one image using an epoch_ms value
        image_request_url = build_request_url(server_url, camera_select, "backgrounds",
                                              "get-one-image", "by-ems", bg_epoch_ms)
        
        # Save request data to disk
        save_network_jpg(image_request_url, save_path)
        
    return

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Snapshot functions

# .....................................................................................................................
    
def request_snapshot_metadata(server_url, camera_select, start_epoch_ms, end_epoch_ms):
    
    # Build route for requesting all metadata between a start/end time
    request_url = build_request_url(server_url, camera_select, "snapshots",
                                    "get-many-metadata", "by-time-range", 
                                    start_epoch_ms, end_epoch_ms)
    
    # Grab snapshot data (with feedback)
    print("", "Downloading snapshot metadata...", sep = "\n", end = " ")
    many_snapshot_metadata_list = get_json(request_url)
    
    return many_snapshot_metadata_list

# .....................................................................................................................

def save_snapshot_metadata(cameras_folder_path, camera_select, user_select, snapshot_metadata_list):
    
    # Make sure the metadata reporting folder exists
    base_save_folder = build_snapshot_metadata_report_path(cameras_folder_path, camera_select, user_select)
    os.makedirs(base_save_folder, exist_ok = True)
    
    # Loop through all the requested metadata and save back into the filesystem
    print("Saving snapshot metadata")
    for each_metadata_dict in tqdm(snapshot_metadata_list):
        snap_epoch_ms = each_metadata_dict["epoch_ms"]
        file_name = "dlsnap-{}.json.gz".format(snap_epoch_ms)
        save_path = os.path.join(base_save_folder, file_name)
        save_jgz(save_path, each_metadata_dict)
        
    return

# .....................................................................................................................

def save_snapshot_images(server_url, cameras_folder_path, camera_select, user_select, snapshot_metadata_list):
    
    # Make sure the image reporting folder exists
    base_save_folder = build_snapshot_image_report_path(cameras_folder_path, camera_select, user_select)
    os.makedirs(base_save_folder, exist_ok = True)
        
    # Loop through all the requested metadata and request + save the correspond images
    print("", "Downloading & saving snapshot images", sep = "\n")
    for each_metadata_dict in tqdm(snapshot_metadata_list):
        
        # Build pathing info
        snap_epoch_ms = each_metadata_dict["epoch_ms"]
        file_name = "{}.jpg".format(snap_epoch_ms)
        save_path = os.path.join(base_save_folder, file_name)
        
        # Build route for requesting one image using an epoch_ms value
        image_request_url = build_request_url(server_url, camera_select, "snapshots", 
                                              "get-one-image", "by-ems", snap_epoch_ms)
        
        # Save request data to disk
        save_network_jpg(image_request_url, save_path)
        
    return

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Object function

# .....................................................................................................................

def request_object_metadata(server_url, camera_select, start_epoch_ms, end_epoch_ms):
    
    # Build route for requesting all metadata between a start/end time
    request_url = build_request_url(server_url, camera_select, "objects",
                                    "get-many-metadata", "by-time-range",
                                    start_epoch_ms, end_epoch_ms)
    
    # Grab object data (with feedback)
    print("", "Downloading object metadata...", sep = "\n", end = " ")
    many_object_metadata_dict = get_json(request_url)
    
    return many_object_metadata_dict

# .....................................................................................................................

def save_object_metadata(cameras_folder_path, camera_select, user_select, object_metadata_dict):
    
    # Make sure the metadata reporting folder exists
    base_save_folder = build_object_metadata_report_path(cameras_folder_path, camera_select, user_select)
    os.makedirs(base_save_folder, exist_ok = True)
    
    # Loop through all the requested metadata and save back into the filesystem
    print("Saving object metadata")
    for each_obj_id, each_metadata_dict in tqdm(object_metadata_dict.items()):
        file_name = "dlobj-{}.json.gz".format(each_obj_id)
        save_path = os.path.join(base_save_folder, file_name)
        save_jgz(save_path, each_metadata_dict)
        
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
#%% Set up access to data server

# Set server connection parameters
server_protocol = "http"
server_host = "localhost"
server_port = 8000

# Build server url
server_url = "{}://{}:{}".format(server_protocol, server_host, server_port)

# Check that the server is accessible before we try requesting data from it
connection_is_valid = check_server_connection(server_url)

# Bail if we couldn't connect to the server, with some kind of feedback
if not connection_is_valid:
    ide_quit("Couldn't connect to data server! ({})".format(server_url))
    

# ---------------------------------------------------------------------------------------------------------------------
#%% Get camera list from the database

# First get a list of available cameras from the server
camera_names_list = request_camera_list(server_url)

# Prompt user to select which camera they'd like to download data for
select_idx, camera_select = cli_select_from_list(camera_names_list, "Select camera:")

# Request info about the time range from the database
snap_bounding_times_dict = request_bounding_times(server_url, camera_select)

# Prompt user to select time range to download
# ...
# HARD-CODE FOR NOW
start_epoch_ms = snap_bounding_times_dict["min_epoch_ms"]
end_epoch_ms = snap_bounding_times_dict["max_epoch_ms"]


# ---------------------------------------------------------------------------------------------------------------------
#%% Get camera info

# Request all camera info metadata & save it
many_caminfo_metadata_list = request_caminfo_metadata(server_url, camera_select)
save_caminfo_metadata(cameras_folder_path, camera_select, user_select, many_caminfo_metadata_list)

# ---------------------------------------------------------------------------------------------------------------------
#%% Get background info

# Request all background metadata
many_background_metadata_list = request_background_metadata(server_url, camera_select, start_epoch_ms, end_epoch_ms)

# Save background metadata & request corresponding image data
save_background_metadata(cameras_folder_path, camera_select, user_select, many_background_metadata_list)
save_background_images(server_url, cameras_folder_path, camera_select, user_select, many_background_metadata_list)


# ---------------------------------------------------------------------------------------------------------------------
#%% Get snapshot data

# Request all snapshot metadata
many_snapshot_metadata_list = request_snapshot_metadata(server_url, camera_select, start_epoch_ms, end_epoch_ms)

# Save snapshot metadata & request corresponding image data
save_snapshot_metadata(cameras_folder_path, camera_select, user_select, many_snapshot_metadata_list)
save_snapshot_images(server_url, cameras_folder_path, camera_select, user_select, many_snapshot_metadata_list)


# ---------------------------------------------------------------------------------------------------------------------
#%% Get object info

# Request all object metadata & save it
many_object_metadata_dict = request_object_metadata(server_url, camera_select, start_epoch_ms, end_epoch_ms)
save_object_metadata(cameras_folder_path, camera_select, user_select, many_object_metadata_dict)

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap

