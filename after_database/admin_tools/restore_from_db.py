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

from local.lib.common.timekeeper_utils import isoformat_to_datetime, datetime_to_epoch_ms, get_local_datetime
from local.lib.common.launch_helpers import delete_existing_report_data
from local.lib.common.environment import get_dbserver_protocol

from local.lib.ui_utils.cli_selections import Resource_Selector
from local.lib.ui_utils.script_arguments import script_arg_builder

from local.online_database.post_to_dbserver import check_server_connection

from local.lib.file_access_utils.locations import load_location_info_dict, unpack_location_info_dict

from local.lib.file_access_utils.reporting import build_camera_info_metadata_report_path
from local.lib.file_access_utils.reporting import build_config_info_metadata_report_path
from local.lib.file_access_utils.reporting import build_snapshot_metadata_report_path
from local.lib.file_access_utils.reporting import build_object_metadata_report_path
from local.lib.file_access_utils.reporting import build_station_metadata_report_path
from local.lib.file_access_utils.reporting import build_background_metadata_report_path
from local.lib.file_access_utils.reporting import build_snapshot_image_report_path
from local.lib.file_access_utils.reporting import build_background_image_report_path

from local.lib.file_access_utils.metadata_read_write import save_json_metadata, save_jsongz_metadata

from local.eolib.utils.quitters import ide_quit
from local.eolib.utils.cli_tools import Datetime_Input_Parser as DTIP
from local.eolib.utils.cli_tools import cli_select_from_list, cli_confirm
from local.eolib.utils.files import create_missing_folder_path


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
    
    # Add argument for controlling snapshot sampling
    default_n_snapshots = -1
    ap_obj.add_argument("-n", "--n_snapshots", default = default_n_snapshots, type = int,
                        help = "\n".join(["Number of snapshots to download",
                                          "By default, all snapshots in the selected",
                                          "time range will be downloaded. However, this",
                                          "value can be set to download fewer snapshots",
                                          "at the expense of a coarser resolution in time."]))
    
    # Evaluate args now
    ap_result = vars(ap_obj.parse_args())
    
    return ap_result

# .....................................................................................................................

def get_json(request_url, message_on_error = "Error requesting data!"):
    
    # Request data from the server
    post_response = requests.get(request_url)
    if post_response.status_code != 200:
        raise SystemError("{}\n@ {}\n\n{}".format(message_on_error, request_url, post_response.text))
    
    # Convert json response data to python data type
    return_data = post_response.json()
    
    return return_data

# .....................................................................................................................

def get_jpg(request_url, message_on_error = "Error requesting image data!"):
    
    # Request data from the server
    post_response = requests.get(request_url)
    if post_response.status_code != 200:
        raise SystemError("{}\n@ {}\n\n{}".format(message_on_error, request_url, post_response.text))
    
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
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Camera info functions

# .....................................................................................................................

def request_camerainfo_metadata(server_url, camera_select, start_epoch_ms, end_epoch_ms):
    
    # Build route for requesting all camera info metadata
    request_url = build_request_url(server_url, camera_select, "camerainfo",
                                    "get-many-metadata", "by-time-range",
                                    start_epoch_ms, end_epoch_ms)
    
    # Grab camera info data
    try:
        many_camerainfo_metadata_list = get_json(request_url)
        
    except SystemError:
        many_camerainfo_metadata_list = []
        print("", "ERROR RETRIEVING CAMERA INFO...")
    
    return many_camerainfo_metadata_list

# .....................................................................................................................

def save_camerainfo_metadata(location_select_folder_path, camera_select, camerainfo_metadata_list):
    
    # Make sure the camera info metadata reporting folder exists
    base_save_folder = build_camera_info_metadata_report_path(location_select_folder_path, camera_select)
    create_missing_folder_path(base_save_folder)
    
    # Loop through all the requested metadata and save back into the filesystem
    print("", "Saving camera info metadata", sep = "\n")
    for each_metadata_dict in tqdm(camerainfo_metadata_list):
        save_jsongz_metadata(base_save_folder, each_metadata_dict)
    
    return

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Configuration info functions

# .....................................................................................................................

def count_configs(server_url, camera_select, start_epoch_ms, end_epoch_ms):
    
    # Build route for requesting count of config info entries between a start/end time
    request_url = build_request_url(server_url, camera_select, "configinfo",
                                    "count", "by-time-range",
                                    start_epoch_ms, end_epoch_ms)
    
    # Grab config info count
    count_dict = get_json(request_url)
    configinfo_count = count_dict.get("count", "error")
    
    return configinfo_count

# .....................................................................................................................

def request_configinfo_metadata(server_url, camera_select, start_epoch_ms, end_epoch_ms):
    
    # Build route for requesting all config info metadata
    request_url = build_request_url(server_url, camera_select, "configinfo",
                                    "get-many-metadata", "by-time-range",
                                    start_epoch_ms, end_epoch_ms)
    
    # Grab configuration info data
    try:
        many_configinfo_metadata_list = get_json(request_url)
        
    except SystemError:
        many_configinfo_metadata_list = []
        print("", "ERROR RETRIEVING CONFIG INFO...")
    
    return many_configinfo_metadata_list

# .....................................................................................................................

def save_configinfo_metadata(location_select_folder_path, camera_select, configinfo_metadata_list):
    
    # Make sure the config info metadata reporting folder exists
    base_save_folder = build_config_info_metadata_report_path(location_select_folder_path, camera_select)
    create_missing_folder_path(base_save_folder)
    
    # Loop through all the requested metadata and save back into the filesystem
    print("", "Saving configuration info", sep = "\n")
    for each_metadata_dict in tqdm(configinfo_metadata_list):
        save_jsongz_metadata(base_save_folder, each_metadata_dict)
    
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

def save_background_metadata(location_select_folder_path, camera_select, background_metadata_list):
    
    # Make sure the background metadata reporting folder exists
    base_save_folder = build_background_metadata_report_path(location_select_folder_path, camera_select)
    create_missing_folder_path(base_save_folder)
    
    # Loop through all the requested metadata and save back into the filesystem
    print("", "Saving background metadata", sep = "\n")
    for each_metadata_dict in tqdm(background_metadata_list):
        save_json_metadata(base_save_folder, each_metadata_dict)
        
    return

# .....................................................................................................................

def save_background_images(server_url, location_select_folder_path, camera_select, background_metadata_list):
    
    # Make sure the image reporting folder exists
    base_save_folder = build_background_image_report_path(location_select_folder_path, camera_select)
    create_missing_folder_path(base_save_folder)
        
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

def save_object_metadata(location_select_folder_path, camera_select, object_metadata_dict):
    
    # Make sure the metadata reporting folder exists
    base_save_folder = build_object_metadata_report_path(location_select_folder_path, camera_select)
    create_missing_folder_path(base_save_folder)
    
    # Loop through all the requested metadata and save back into the filesystem
    print("", "Saving object metadata", sep = "\n")
    for each_obj_id, each_metadata_dict in tqdm(object_metadata_dict.items()):
        save_jsongz_metadata(base_save_folder, each_metadata_dict)
        
    return

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Station functions

# .....................................................................................................................

def count_station_data(server_url, camera_select, start_epoch_ms, end_epoch_ms):
    
    # Build route for requesting count of objects between a start/end time
    request_url = build_request_url(server_url, camera_select, "stations",
                                    "count", "by-time-range",
                                    start_epoch_ms, end_epoch_ms)
    
    # Grab object count
    count_dict = get_json(request_url)
    object_count = count_dict.get("count", "error")
    
    return object_count

# .....................................................................................................................

def request_station_metadata(server_url, camera_select, start_epoch_ms, end_epoch_ms):
    
    # Build route for requesting all metadata between a start/end time
    request_url = build_request_url(server_url, camera_select, "stations",
                                    "get-many-metadata", "by-time-range",
                                    start_epoch_ms, end_epoch_ms)
    
    # Grab station data
    many_station_metadata_dict = get_json(request_url)
    
    return many_station_metadata_dict

# .....................................................................................................................

def save_station_metadata(location_select_folder_path, camera_select, station_metadata_dict):
    
    # Make sure the metadata reporting folder exists
    base_save_folder = build_station_metadata_report_path(location_select_folder_path, camera_select)
    create_missing_folder_path(base_save_folder)
    
    # Loop through all the requested metadata and save back into the filesystem
    print("", "Saving station metadata", sep = "\n")
    for each_stn_id, each_metadata_dict in tqdm(station_metadata_dict.items()):
        save_jsongz_metadata(base_save_folder, each_metadata_dict)
    
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
    
def request_snapshot_metadata(server_url, camera_select, start_epoch_ms, end_epoch_ms, n_snapshots = -1):
    
    # Build route for requesting all metadata between a start/end time
    request_url = build_request_url(server_url, camera_select, "snapshots",
                                    "get-many-metadata", "by-time-range",
                                    start_epoch_ms, end_epoch_ms)
    
    # If we're sub-sampling snapshots, use a diferent request route
    if n_snapshots > 0:
        request_url = build_request_url(server_url, camera_select, "snapshots",
                                        "get-many-metadata", "by-time-range",
                                        "n-samples",
                                        start_epoch_ms, end_epoch_ms, n_snapshots)
    
    # Grab snapshot data
    many_snapshot_metadata_list = get_json(request_url)
    
    return many_snapshot_metadata_list

# .....................................................................................................................

def save_snapshot_metadata(location_select_folder_path, camera_select, snapshot_metadata_list):
    
    # Make sure the metadata reporting folder exists
    base_save_folder = build_snapshot_metadata_report_path(location_select_folder_path, camera_select)
    create_missing_folder_path(base_save_folder)
    
    # Loop through all the requested metadata and save back into the filesystem
    print("", "Saving snapshot metadata", sep = "\n")
    for each_metadata_dict in tqdm(snapshot_metadata_list):
        save_json_metadata(base_save_folder, each_metadata_dict)
    
    return

# .....................................................................................................................

def save_snapshot_images(server_url, location_select_folder_path, camera_select, snapshot_metadata_list):
    
    # Make sure the image reporting folder exists
    base_save_folder = build_snapshot_image_report_path(location_select_folder_path, camera_select)
    create_missing_folder_path(base_save_folder)
        
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
#%% Parse script args

# Get script arguments
ap_result = parse_restore_args()
n_snapshots = ap_result["n_snapshots"]
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
#%% Get camera list from the database

# First get a list of available cameras from the server
camera_names_list = request_camera_list(server_url)

# Prompt user to select which camera they'd like to download data for
select_idx, camera_select = cli_select_from_list(camera_names_list, "Select camera:")

# Request info about the time range from the database
snap_bounding_times_dict = request_bounding_times(server_url, camera_select)
bounding_start_dt = isoformat_to_datetime(snap_bounding_times_dict["min_datetime_isoformat"])
bounding_end_dt = isoformat_to_datetime(snap_bounding_times_dict["max_datetime_isoformat"])

# We should show the date if it doesn't match the current date (to help indicate a site isn't storing new data)
local_dt = get_local_datetime()
show_date_on_input = (bounding_end_dt.date() != local_dt.date())

# Restrict the time range if we get a ton of data
bounding_start_dt, bounding_end_dt = \
DTIP.limit_start_end_range(bounding_start_dt, bounding_end_dt, max_timedelta_hours = 10/60)

# Prompt user to select time range to download
user_start_dt, user_end_dt = DTIP.cli_prompt_start_end_datetimes(bounding_start_dt, bounding_end_dt,
                                                                 always_show_date = show_date_on_input)

# Convert user input times to epoch values
start_epoch_ms = datetime_to_epoch_ms(user_start_dt)
end_epoch_ms = datetime_to_epoch_ms(user_end_dt)


# ---------------------------------------------------------------------------------------------------------------------
#%% Count data to download

# Request all camera info directly (and count it), since it should be small enough to not matter
many_camerainfo_metadata_list = request_camerainfo_metadata(server_url, camera_select, start_epoch_ms, end_epoch_ms)

# Request counts for background, snapshots and objects
camerainfo_count = len(many_camerainfo_metadata_list)
configinfo_count = count_configs(server_url, camera_select, start_epoch_ms, end_epoch_ms)
background_count = count_backgrounds(server_url, camera_select, start_epoch_ms, end_epoch_ms)
snapshot_count = count_snapshots(server_url, camera_select, start_epoch_ms, end_epoch_ms)
object_count = counts_objects(server_url, camera_select, start_epoch_ms, end_epoch_ms)
station_count = count_station_data(server_url, camera_select, start_epoch_ms, end_epoch_ms)

# Calculate the number of snapshots if we're downsampling
downsample_str = ""
use_downsampling = (0 < n_snapshots < snapshot_count)
if use_downsampling:
    downsample_str = " (downsampled from {})".format(snapshot_count)

# Provide feedback, in case user doesn't want to download the data
start_dt_str = user_start_dt.strftime(DTIP.datetime_format)
end_dt_str = user_end_dt.strftime(DTIP.datetime_format)
print("","",
      "--- DATA TO DOWNLOAD ---",
      "",
      "  {} (start)".format(start_dt_str),
      "  {} (end)".format(end_dt_str),
      "",
      "  {} camera info {}".format(camerainfo_count, "entries" if camerainfo_count > 1 else "entry"),
      "  {} config info {}".format(configinfo_count, "entries" if configinfo_count > 1 else "entry"),
      "  {} backgrounds".format(background_count),
      "  {} objects".format(object_count),
      "  {} station datasets".format(station_count),
      "  {} snapshots{}".format(n_snapshots if use_downsampling else snapshot_count, downsample_str),
      sep = "\n")

# Give the user a chance to cancel the download, if they don't like the dataset numbers
user_confirm_download = cli_confirm("Download dataset?")
if not user_confirm_download:
    ide_quit("Download cancelled!")


# ---------------------------------------------------------------------------------------------------------------------
#%% Prepare the save folder

# Create the camera folder, if needed
location_select_folder_path = selector.get_location_select_folder_path(location_select)
selector.create_empty_camera_folder(location_select, camera_select)

# Save selections for convenience
selector.save_location_select(location_select)
selector.save_camera_select(camera_select)

# Remove existing data, if needed
delete_existing_report_data(location_select_folder_path, camera_select,
                            enable_deletion = True,
                            enable_deletion_prompt = True)

# Get camera info
if camerainfo_count > 0:
    
    # Save all camera info metadata (which we already requested earlier)
    save_camerainfo_metadata(location_select_folder_path, camera_select, many_camerainfo_metadata_list)

# Get config info
if configinfo_count > 0:
    
    # Request all configuration metadata & save it
    many_configinfo_metadata_dict = request_configinfo_metadata(server_url, camera_select, start_epoch_ms, end_epoch_ms)
    save_configinfo_metadata(location_select_folder_path, camera_select, many_configinfo_metadata_dict)

# Get background info
if background_count > 0:
    
    # Request all background metadata
    many_background_metadata_list = request_background_metadata(server_url, camera_select, start_epoch_ms, end_epoch_ms)
    
    # Save background metadata & request corresponding image data
    save_background_metadata(location_select_folder_path, camera_select, many_background_metadata_list)
    save_background_images(server_url, location_select_folder_path, camera_select, many_background_metadata_list)

# Get object info
if object_count > 0:
    
    # Request all object metadata & save it
    many_object_metadata_dict = request_object_metadata(server_url, camera_select, start_epoch_ms, end_epoch_ms)
    save_object_metadata(location_select_folder_path, camera_select, many_object_metadata_dict)

# Get station info
if station_count > 0:
    
    # Request all station metadata & save it
    many_station_metadata_dict = request_station_metadata(server_url, camera_select, start_epoch_ms, end_epoch_ms)
    save_station_metadata(location_select_folder_path, camera_select, many_station_metadata_dict)

# Get snapshot data
if snapshot_count > 0:

    # Request all snapshot metadata
    many_snapshot_metadata_list = request_snapshot_metadata(server_url, camera_select,
                                                            start_epoch_ms, end_epoch_ms,
                                                            n_snapshots)
    
    # Save snapshot metadata & request corresponding image data
    save_snapshot_metadata(location_select_folder_path, camera_select, many_snapshot_metadata_list)
    save_snapshot_images(server_url, location_select_folder_path, camera_select, many_snapshot_metadata_list)


# ---------------------------------------------------------------------------------------------------------------------
#%% Clean up
    
# Add a blank space at the end for aesthetics
print("")


# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap


