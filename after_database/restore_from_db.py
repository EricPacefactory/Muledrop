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

from local.lib.common.timekeeper_utils import parse_isoformat_string, datetime_to_epoch_ms
from local.lib.common.launch_helpers import delete_existing_report_data
from local.lib.common.environment import get_dbserver_protocol, get_dbserver_host, get_dbserver_port

from local.lib.ui_utils.cli_selections import Resource_Selector
from local.lib.ui_utils.script_arguments import script_arg_builder

from local.online_database.post_to_dbserver import check_server_connection

from local.lib.file_access_utils.structures import create_camera_folder_structure
from local.lib.file_access_utils.reporting import build_camera_info_metadata_report_path
from local.lib.file_access_utils.reporting import build_snapshot_metadata_report_path
from local.lib.file_access_utils.reporting import build_object_metadata_report_path
from local.lib.file_access_utils.reporting import build_background_metadata_report_path
from local.lib.file_access_utils.reporting import build_snapshot_image_report_path
from local.lib.file_access_utils.reporting import build_background_image_report_path

from local.lib.file_access_utils.read_write import save_jgz

from local.eolib.utils.quitters import ide_quit
from local.eolib.utils.cli_tools import Datetime_Input_Parser as DTIP
from local.eolib.utils.cli_tools import cli_select_from_list, cli_prompt_with_defaults, cli_confirm


# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes

# .....................................................................................................................

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Define shared functions

# .....................................................................................................................

def parse_restore_args(debug_print = False):
    
    # Set defaults
    default_protocol = get_dbserver_protocol()
    
    # Set arg help text
    protocol_help_text = "Specify the access protocol of the db server\n(Default: {})".format(default_protocol)
    
    # Set script arguments for running files
    args_list = [{"protocol": {"default": default_protocol, "help_text": protocol_help_text}}]
    
    # Provide some extra information when accessing help text
    script_description = "Download report data from the database server, for a single camera."
    
    # Build & evaluate script arguments!
    ap_obj = script_arg_builder(args_list,
                                   description = script_description,
                                   parse_on_call = False,
                                   debug_print = debug_print)
    
    # Add argument for controlling snapshot downsampling
    default_skip_n = 0
    ap_obj.add_argument("-n", "--skip_n", default = default_skip_n, type = int,
                        help = "\n".join(["Number of snapshots to skip when downloading data.",
                                          "Allows image data to be 'downsampled'",
                                          "at the expense of a coarser resolution in time.",
                                          "(Default: {})".format(default_skip_n)]))
    
    # Evaluate args now
    ap_result = vars(ap_obj.parse_args())
    
    return ap_result

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

def get_jpg(request_url, message_on_error = "Error requesting image data!"):
    
    # Request data from the server
    post_response = requests.get(request_url)
    if post_response.status_code != 200:
        raise SystemError("{}\n@ {}".format(message_on_error, request_url))
    
    # Pull image data out of response
    return_data = post_response.content
    
    return return_data

# .....................................................................................................................

def save_jpg(save_path, image_data):
    
    # Save image data directly to file
    with open(save_path, 'wb') as out_file:
        out_file.write(image_data)
    
    # Force clearing of memory... might help garbage collector?
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

# .....................................................................................................................

def create_new_camera_entry(selector, camera_select):
    
    # Check if the camera we're restoring already exists on the system
    camera_already_exists = (camera_select in selector.get_cameras_tree().keys())
    if camera_already_exists:
        return
    
    # If the camera doesn't exist, create a blank folder structure for it (so other tools can read it properly)
    project_root_path, cameras_folder_path = selector.get_project_pathing()
    create_camera_folder_structure(project_root_path, cameras_folder_path, camera_select)

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Camera info functions

# .....................................................................................................................

def request_caminfo_metadata(server_url, camera_select, start_epoch_ms, end_epoch_ms):
    
    # Build route for requesting all camera info metadata
    request_url = build_request_url(server_url, camera_select, "camerainfo", 
                                    "get-many-camera-info", "by-time-range",
                                    start_epoch_ms, end_epoch_ms)
    
    # Grab camera info data
    many_caminfo_metadata_list = get_json(request_url)
    
    return many_caminfo_metadata_list

# .....................................................................................................................

def save_caminfo_metadata(cameras_folder_path, camera_select, user_select, caminfo_metadata_list):
    
    # Make sure the camera info metadata reporting folder exists
    base_save_folder = build_camera_info_metadata_report_path(cameras_folder_path, camera_select, user_select)
    os.makedirs(base_save_folder, exist_ok = True)
    
    # Loop through all the requested metadata and save back into the filesystem
    print("", "Saving camera info metadata", sep = "\n")
    for each_metadata_dict in tqdm(caminfo_metadata_list):
        caminfo_start_epoch_ms = each_metadata_dict["start_epoch_ms"]
        file_name = "dlcaminfo-{}.json.gz".format(caminfo_start_epoch_ms)
        save_path = os.path.join(base_save_folder, file_name)
        save_jgz(save_path, each_metadata_dict)
        
    return

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Background functions

# .....................................................................................................................

def count_backgrounds(server_url, camera_select, start_epoch_ms, end_epoch_ms):
    
    # Build route for requesting count of backgrounds between a start/end time
    request_url = build_request_url(server_url, camera_select, "backgrounds",
                                    "count", "by-time-range",
                                    start_epoch_ms, end_epoch_ms)
    
    # Grab background counts
    count_dict = get_json(request_url)
    background_count = count_dict.get("count", "error")
    
    return background_count

# .....................................................................................................................

def request_background_metadata(server_url, camera_select, start_epoch_ms, end_epoch_ms):
    
    # Build route for requesting all metadata between a start/end time
    request_url = build_request_url(server_url, camera_select, "backgrounds",
                                    "get-many-metadata", "by-time-range", 
                                    start_epoch_ms, end_epoch_ms)
    
    many_background_metadata_list = get_json(request_url)
    
    return many_background_metadata_list

# .....................................................................................................................

def save_background_metadata(cameras_folder_path, camera_select, user_select, background_metadata_list):
    
    # Make sure the background metadata reporting folder exists
    base_save_folder = build_background_metadata_report_path(cameras_folder_path, camera_select, user_select)
    os.makedirs(base_save_folder, exist_ok = True)
    
    # Loop through all the requested metadata and save back into the filesystem
    print("", "Saving background metadata", sep = "\n")
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
    print("", "Saving background images", sep = "\n")
    for each_metadata_dict in tqdm(background_metadata_list):
        
        # Build pathing info
        bg_epoch_ms = each_metadata_dict["epoch_ms"]
        file_name = "{}.jpg".format(bg_epoch_ms)
        save_path = os.path.join(base_save_folder, file_name)
        
        # Build route for requesting one image using an epoch_ms value
        image_request_url = build_request_url(server_url, camera_select, "backgrounds",
                                              "get-one-image", "by-ems", bg_epoch_ms)
        
        # Request image data and save to disk
        image_data = get_jpg(image_request_url)
        save_jpg(save_path, image_data)
        
    return

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Object functions

# .....................................................................................................................

def counts_objects(server_url, camera_select, start_epoch_ms, end_epoch_ms):
    
    # Build route for requesting count of objects between a start/end time
    request_url = build_request_url(server_url, camera_select, "objects",
                                    "count", "by-time-range",
                                    start_epoch_ms, end_epoch_ms)
    
    # Grab object count
    count_dict = get_json(request_url)
    object_count = count_dict.get("count", "error")
    
    return object_count

# .....................................................................................................................

def request_object_metadata(server_url, camera_select, start_epoch_ms, end_epoch_ms):
    
    # Build route for requesting all metadata between a start/end time
    request_url = build_request_url(server_url, camera_select, "objects",
                                    "get-many-metadata", "by-time-range",
                                    start_epoch_ms, end_epoch_ms)
    
    # Grab object data
    many_object_metadata_dict = get_json(request_url)
    
    return many_object_metadata_dict

# .....................................................................................................................

def save_object_metadata(cameras_folder_path, camera_select, user_select, object_metadata_dict):
    
    # Make sure the metadata reporting folder exists
    base_save_folder = build_object_metadata_report_path(cameras_folder_path, camera_select, user_select)
    os.makedirs(base_save_folder, exist_ok = True)
    
    # Loop through all the requested metadata and save back into the filesystem
    print("", "Saving object metadata", sep = "\n")
    for each_obj_id, each_metadata_dict in tqdm(object_metadata_dict.items()):
        file_name = "dlobj-{}.json.gz".format(each_obj_id)
        save_path = os.path.join(base_save_folder, file_name)
        save_jgz(save_path, each_metadata_dict)
        
    return

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Snapshot functions

# .....................................................................................................................

def count_snapshots(server_url, camera_select, start_epoch_ms, end_epoch_ms):
    
    # Build route for requesting count of snapshots between a start/end time
    request_url = build_request_url(server_url, camera_select, "snapshots",
                                    "count", "by-time-range",
                                    start_epoch_ms, end_epoch_ms)
    
    # Grab snapshot counts
    count_dict = get_json(request_url)
    snapshot_count = count_dict.get("count", "error")
    
    return snapshot_count

# .....................................................................................................................
    
def request_snapshot_metadata(server_url, camera_select, start_epoch_ms, end_epoch_ms, skip_n = 0):
    
    # Build route for requesting all metadata between a start/end time
    request_url = build_request_url(server_url, camera_select, "snapshots",
                                    "get-many-metadata", "by-time-range", 
                                    start_epoch_ms, end_epoch_ms)
    
    # If we're skipping snapshots, use a diferent request route
    if skip_n > 0:
        request_url = build_request_url(server_url, camera_select, "snapshots",
                                        "get-many-metadata", "by-time-range",
                                        "skip-n",
                                        start_epoch_ms, end_epoch_ms, skip_n)
    
    # Grab snapshot data
    many_snapshot_metadata_list = get_json(request_url)
    
    return many_snapshot_metadata_list

# .....................................................................................................................

def save_snapshot_metadata(cameras_folder_path, camera_select, user_select, snapshot_metadata_list):
    
    # Make sure the metadata reporting folder exists
    base_save_folder = build_snapshot_metadata_report_path(cameras_folder_path, camera_select, user_select)
    os.makedirs(base_save_folder, exist_ok = True)
    
    # Loop through all the requested metadata and save back into the filesystem
    print("", "Saving snapshot metadata", sep = "\n")
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
    print("", "Saving snapshot images", sep = "\n")
    for each_metadata_dict in tqdm(snapshot_metadata_list):
        
        # Build pathing info
        snap_epoch_ms = each_metadata_dict["epoch_ms"]
        file_name = "{}.jpg".format(snap_epoch_ms)
        save_path = os.path.join(base_save_folder, file_name)
        
        # Build route for requesting one image using an epoch_ms value
        image_request_url = build_request_url(server_url, camera_select, "snapshots", 
                                              "get-one-image", "by-ems", snap_epoch_ms)
        
        # Request image data and save to disk
        image_data = get_jpg(image_request_url)
        save_jpg(save_path, image_data)
        
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
ap_result = parse_restore_args()
skip_n_snapshots = ap_result["skip_n"]
server_protocol = ap_result["protocol"]
default_server_host = get_dbserver_host()
default_server_port = get_dbserver_port()

# Get user to enter server address
server_host = cli_prompt_with_defaults("  Enter server ip: ", default_value = default_server_host, return_type = str)
server_port = cli_prompt_with_defaults("Enter server port: ", default_value = default_server_port, return_type = int)

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
bounding_start_dt = parse_isoformat_string(snap_bounding_times_dict["min_datetime_isoformat"])
bounding_end_dt = parse_isoformat_string(snap_bounding_times_dict["max_datetime_isoformat"])

# Restrict the time range if we get a ton of data
bounding_start_dt, bounding_end_dt = \
DTIP.limit_start_end_range(bounding_start_dt, bounding_end_dt, max_timedelta_hours = 10/60)

# Prompt user to select time range to download
user_start_dt, user_end_dt = DTIP.cli_prompt_start_end_datetimes(bounding_start_dt, bounding_end_dt)

# Convert user input times to epoch values
start_epoch_ms = datetime_to_epoch_ms(user_start_dt)
end_epoch_ms = datetime_to_epoch_ms(user_end_dt)


# ---------------------------------------------------------------------------------------------------------------------
#%% Count data to download

# Request all camera info directly (and count it), since it should be small enough to not matter
many_caminfo_metadata_list = request_caminfo_metadata(server_url, camera_select, start_epoch_ms, end_epoch_ms)

# Request counts for background, snapshots and objects
caminfo_count = len(many_caminfo_metadata_list)
background_count = count_backgrounds(server_url, camera_select, start_epoch_ms, end_epoch_ms)
snapshot_count = count_snapshots(server_url, camera_select, start_epoch_ms, end_epoch_ms)
object_count = counts_objects(server_url, camera_select, start_epoch_ms, end_epoch_ms)

# Calculate the number of snapshots if we're downsampling
downsample_str = ""
use_downsampling = (skip_n_snapshots > 0)
if use_downsampling:
    downsample_str = " (downsampled from {})".format(snapshot_count)
    downsampled_snapshot_count = 1 + ((snapshot_count - 1) // (skip_n_snapshots + 1))

# Provide feedback, in case user doesn't want to download the data
start_dt_str = user_start_dt.strftime(DTIP.datetime_format)
end_dt_str = user_end_dt.strftime(DTIP.datetime_format)
print("","", 
      "--- DATA TO DOWNLOAD ---",
      "",
      "  {} (start)".format(start_dt_str),
      "  {} (end)".format(end_dt_str),
      "",
      "  {} camera info {}".format(caminfo_count, "entries" if caminfo_count > 1 else "entry"),
      "  {} backgrounds".format(background_count),
      "  {} objects".format(object_count),
      "  {} snapshots{}".format(downsampled_snapshot_count if use_downsampling else snapshot_count, downsample_str),
      sep = "\n")

# Give the user a chance to cancel the download, if they don't like the dataset numbers
user_confirm_download = cli_confirm("Download dataset?")
if not user_confirm_download:
    ide_quit("Download cancelled!")


# ---------------------------------------------------------------------------------------------------------------------
#%% Prepare the save folder

# Create the camera folder, if needed
create_new_camera_entry(selector, camera_select)

# Remove existing data, if needed
delete_existing_report_data(cameras_folder_path, camera_select, user_select, 
                            enable_deletion = True, enable_deletion_prompt = True)


# ---------------------------------------------------------------------------------------------------------------------
#%% Get camera info

if caminfo_count > 0:
    
    # Save all camera info metadata (which we already requested earlier)
    save_caminfo_metadata(cameras_folder_path, camera_select, user_select, many_caminfo_metadata_list)


# ---------------------------------------------------------------------------------------------------------------------
#%% Get background info

if background_count > 0:
    
    # Request all background metadata
    many_background_metadata_list = request_background_metadata(server_url, camera_select, start_epoch_ms, end_epoch_ms)
    
    # Save background metadata & request corresponding image data
    save_background_metadata(cameras_folder_path, camera_select, user_select, many_background_metadata_list)
    save_background_images(server_url, cameras_folder_path, camera_select, user_select, many_background_metadata_list)


# ---------------------------------------------------------------------------------------------------------------------
#%% Get object info

if object_count > 0:
    
    # Request all object metadata & save it
    many_object_metadata_dict = request_object_metadata(server_url, camera_select, start_epoch_ms, end_epoch_ms)
    save_object_metadata(cameras_folder_path, camera_select, user_select, many_object_metadata_dict)


# ---------------------------------------------------------------------------------------------------------------------
#%% Get snapshot data

if snapshot_count > 0:

    # Request all snapshot metadata
    many_snapshot_metadata_list = request_snapshot_metadata(server_url, camera_select, 
                                                            start_epoch_ms, end_epoch_ms,
                                                            skip_n_snapshots)
    
    # Save snapshot metadata & request corresponding image data
    save_snapshot_metadata(cameras_folder_path, camera_select, user_select, many_snapshot_metadata_list)
    save_snapshot_images(server_url, cameras_folder_path, camera_select, user_select, many_snapshot_metadata_list)

# ---------------------------------------------------------------------------------------------------------------------
#%% Clean up
    
# Add a blank space at the end for aesthetics
print("")

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap

# TODO
# - Add host selection with saving/history
#   - idea would be to avoid having to input ip address every time
#   - instead select from know set of hosts (including 'local')
#   -> a bit complicated, because this would require a 'create new host' option + ability to edit?
#   -> where does the ip data get saved?
# - improve snapshot subsampling
#   - would be better to not download all data, if subsampling
#   - instead either download all epoch_ms data and subsample that,
#   ... or implement subsampling on the db server itself (seems better!)
