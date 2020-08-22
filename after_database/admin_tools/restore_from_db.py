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

from time import perf_counter
from tqdm import tqdm

from local.lib.common.feedback import print_time_taken
from local.lib.common.timekeeper_utils import isoformat_to_datetime, datetime_to_epoch_ms, get_local_datetime
from local.lib.common.launch_helpers import delete_existing_report_data
from local.lib.common.environment import get_dbserver_protocol

from local.lib.ui_utils.cli_selections import Resource_Selector
from local.lib.ui_utils.script_arguments import script_arg_builder

from local.online_database.request_from_dbserver import Server_Access
from local.online_database.request_from_dbserver import Camerainfo, Configinfo, Backgrounds
from local.online_database.request_from_dbserver import Snapshots, Objects, Stations

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
from local.lib.file_access_utils.image_read_write import write_encoded_jpg

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
    
    # Add argument for enabling gzip on requests
    ap_obj.add_argument("-z", "--gzip", default = False, action = "store_true",
                        help = "\n".join(["Enable gzip on requests",
                                          "Use this to reduce download time,",
                                          "at the expense of more heavily loading the server itself."]))
    
    # Evaluate args now
    ap_result = vars(ap_obj.parse_args())
    
    return ap_result

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Parse script args

# Get script arguments
ap_result = parse_restore_args()
n_snapshots = ap_result["n_snapshots"]
dbserver_protocol = ap_result["protocol"]
req_gzip = ap_result["gzip"]


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

# Confirm that we have a connection to the server
server_ref = Server_Access(dbserver_protocol, host_ip, dbserver_port)
connection_is_valid = server_ref.check_server_connection()
if not connection_is_valid:
    ide_quit("Couldn't connect to data server! ({})".format(server_ref.server_url))
print("  --> Success")


# ---------------------------------------------------------------------------------------------------------------------
#%% Set camera selection

# First get a list of available cameras from the server
camera_names_list = server_ref.get_all_camera_names()

# Prompt user to select which camera they'd like to download data for
select_idx, camera_select = cli_select_from_list(camera_names_list, "Select camera:")

# Set up all data access objects
access_args = (server_ref, camera_select)
caminfo = Camerainfo(*access_args)
cfginfo = Configinfo(*access_args)
backgrounds = Backgrounds(*access_args)
snapshots = Snapshots(*access_args)
objects = Objects(*access_args)
stations = Stations(*access_args)


# ---------------------------------------------------------------------------------------------------------------------
#%% Get time range for download

# Request info about the time range from the database
snap_bounding_times_dict = snapshots.get_bounding_times()
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

# Get all data set counts
time_range_args = (start_epoch_ms, end_epoch_ms)
camerainfo_count = caminfo.get_count_by_time_range(*time_range_args)
configinfo_count = cfginfo.get_count_by_time_range(*time_range_args)
background_count = backgrounds.get_count_by_time_range(*time_range_args)
snapshot_count = snapshots.get_count_by_time_range(*time_range_args)
object_count = objects.get_count_by_time_range(*time_range_args)
station_count = stations.get_count_by_time_range(*time_range_args)

# Calculate the number of snapshots if we're downsampling
use_snapshot_downsampling = (0 < n_snapshots < snapshot_count)
snapshot_count_str = "{} snapshots".format(snapshot_count)
if use_snapshot_downsampling:
    snapshot_count_str = "{} snapshots (downsampled from {})".format(n_snapshots, snapshot_count)

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
      "  {}".format(snapshot_count_str),
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


# For convenience
report_path_args = (location_select_folder_path, camera_select)


# ---------------------------------------------------------------------------------------------------------------------
#%% Download & save data

# Start timing
start_time_sec = perf_counter()

# Get camera info data
if camerainfo_count > 0:
    
    # Get the save folder for camerainfo metadata
    caminfo_save_folder = build_camera_info_metadata_report_path(*report_path_args)
    create_missing_folder_path(caminfo_save_folder)
    
    # Download & save metadata
    print("", "Saving camera info metadata", sep = "\n", flush = True)
    caminfo_md_list = caminfo.get_many_metadata_by_time_range(*time_range_args)
    for each_cam_md_dict in tqdm(caminfo_md_list):
        save_jsongz_metadata(caminfo_save_folder, each_cam_md_dict)
    
    pass

# Get config info data
if configinfo_count > 0:
    
    # Get the save folder for configinfo metadata
    cfginfo_save_folder = build_config_info_metadata_report_path(*report_path_args)
    create_missing_folder_path(cfginfo_save_folder)
    
    # Download & save metadata
    print("", "Saving config info metadata", sep = "\n", flush = True)
    cfginfo_md_list = cfginfo.get_many_metadata_by_time_range(*time_range_args)
    for each_cfg_md_dict in tqdm(cfginfo_md_list):
        save_jsongz_metadata(cfginfo_save_folder, each_cfg_md_dict)
    
    pass

# Get background data
if background_count > 0:
    
    # Get save folders for background data
    bg_md_save_folder = build_background_metadata_report_path(*report_path_args)
    bg_img_save_folder = build_background_image_report_path(*report_path_args)
    
    # Make sure the save folders exist!
    create_missing_folder_path(bg_md_save_folder)
    create_missing_folder_path(bg_img_save_folder)
    
    # Ask server for every target ems, then download & save each metadata/image separately
    print("", "Saving background data", sep = "\n", flush = True)
    bg_ems_list = backgrounds.get_ems_list_by_time_range(*time_range_args, use_gzip = req_gzip)
    bg_md_list = (backgrounds.get_one_metadata_by_ems(each_ems) for each_ems in bg_ems_list)
    for each_bg_md in tqdm(bg_md_list, total = len(bg_ems_list)):
        
        # Download image data
        each_bg_ems = each_bg_md["epoch_ms"]
        one_bg_jpg = backgrounds.get_one_image_by_ems(each_bg_ems)
        
        # Save data
        save_json_metadata(bg_md_save_folder, each_bg_md)
        write_encoded_jpg(bg_img_save_folder, each_bg_ems, one_bg_jpg)
    
    pass

# Get object data
if object_count > 0:
    
    # Get save folder for object data
    obj_save_folder = build_object_metadata_report_path(*report_path_args)
    create_missing_folder_path(obj_save_folder)
    
    # Ask server for every object id, then download & save each metadata entry
    print("", "Saving object data", sep = "\n", flush = True)
    obj_id_list = objects.get_ids_list_by_time_range(*time_range_args)
    for each_obj_id in tqdm(obj_id_list):
        
        # Download & save data
        one_obj_md = objects.get_one_metadata_by_id(each_obj_id, use_gzip = req_gzip)
        save_jsongz_metadata(obj_save_folder, one_obj_md)
    
    pass

# Get station info
if station_count > 0:
    
    # Get save folder for station data
    stn_save_folder = build_station_metadata_report_path(*report_path_args)
    create_missing_folder_path(stn_save_folder)
    
    # Ask server for every station entry, then download & save each metadata entry
    print("", "Saving station data", sep = "\n", flush = True)
    stn_id_list = stations.get_ids_list_by_time_range(*time_range_args)
    for each_stn_id in tqdm(stn_id_list):
        
        # Download & save data
        one_stn_md = stations.get_one_metadata_by_id(each_stn_id, use_gzip = req_gzip)
        save_jsongz_metadata(stn_save_folder, one_stn_md)
    
    pass

# Get snapshot data
if snapshot_count > 0:
    
    # Get save folders for snapshot data
    snap_md_save_folder = build_snapshot_metadata_report_path(*report_path_args)
    snap_img_save_folder = build_snapshot_image_report_path(*report_path_args)
    
    # Make sure the save folders exist!
    create_missing_folder_path(snap_md_save_folder)
    create_missing_folder_path(snap_img_save_folder)
    
    # Some feedback about downloading/save snapshot data
    print("", "Saving snapshot data", sep = "\n", flush = True)
    
    # Decide how we'll get snap metadata listing based on the amount of data we're expecting
    small_number_of_snapshots = (snapshot_count < 2000)
    snap_md_list = []
    if use_snapshot_downsampling:
        # If downsampling, use the dedicated n-samples route
        snap_md_list = snapshots.get_many_metadata_by_time_range_n_samples(*time_range_args, n_snapshots,
                                                                           use_gzip = req_gzip)
        total_snaps = len(snap_md_list)
        
    elif small_number_of_snapshots:
        # If not 'too many' snapshots are requested, grab the metadata as a single bundle
        snap_md_list = snapshots.get_many_metadata_by_time_range(*time_range_args, use_gzip = req_gzip)
        total_snaps = len(snap_md_list)
        
    else:
        # If we're not downsampling and we're getting a lot of images, pull them one-by-one
        snap_ems_list = snapshots.get_ems_list_by_time_range(*time_range_args, use_gzip = req_gzip)
        snap_md_list = (snapshots.get_one_metadata_by_ems(each_ems) for each_ems in snap_ems_list)
        total_snaps = len(snap_ems_list)
    
    # Save each metadata entry + corresponding image data
    for each_snap_md in tqdm(snap_md_list, total = total_snaps):
        
        # Download image data
        each_snap_ems = each_snap_md["epoch_ms"]
        one_snap_jpg = snapshots.get_one_image_by_ems(each_snap_ems)
        
        # Save data
        save_json_metadata(snap_md_save_folder, each_snap_md)
        write_encoded_jpg(snap_img_save_folder, each_snap_ems, one_snap_jpg)
    
    pass


# ---------------------------------------------------------------------------------------------------------------------
#%% Clean up

# Finish timing with feedback
end_time_sec = perf_counter()
total_time_sec = (end_time_sec - start_time_sec)
print_time_taken(start_time_sec, end_time_sec)
print("")


# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap

