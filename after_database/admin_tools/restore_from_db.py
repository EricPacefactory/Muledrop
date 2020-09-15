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
from local.lib.file_access_utils.metadata_read_write import save_jsongz_metadata

from local.eolib.utils.quitters import ide_quit
from local.eolib.utils.cli_tools import Datetime_Input_Parser as DTIP
from local.eolib.utils.cli_tools import cli_select_from_list, cli_confirm


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
    default_n_snapshots = 0
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

# Confirm that we have a connection to the server
server_ref = Server_Access(host_ip, dbserver_port, is_secured = False)
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
access_args = (server_ref, location_path, camera_select)
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


# ---------------------------------------------------------------------------------------------------------------------
#%% Download & save data

# Start timing
start_time_sec = perf_counter()

# Get camera info data
if camerainfo_count > 0:
    
    # Get the save folder for camerainfo metadata
    caminfo_save_folder = caminfo.build_metadata_save_path()
    
    # Download & save metadata
    print("", "Saving camera info metadata", sep = "\n", flush = True)
    caminfo_md_list = caminfo.get_many_metadata_by_time_range(*time_range_args)
    for each_cam_md_dict in tqdm(caminfo_md_list):
        save_jsongz_metadata(caminfo_save_folder, each_cam_md_dict)
    
    pass


# Get config info data
if configinfo_count > 0:
    
    # Get the save folder for configinfo metadata
    cfginfo_save_folder = cfginfo.build_metadata_save_path()
    
    # Download & save metadata
    print("", "Saving config info metadata", sep = "\n", flush = True)
    cfginfo_md_list = cfginfo.get_many_metadata_by_time_range(*time_range_args)
    for each_cfg_md_dict in tqdm(cfginfo_md_list):
        save_jsongz_metadata(cfginfo_save_folder, each_cfg_md_dict)
    
    pass

# Get background data
if background_count > 0:
    print("", "Saving background data", sep = "\n", flush = True)
    backgrounds.save_stream_many_metadata_by_time_range(*time_range_args)

# Get object data (websocket)
if object_count > 0:
    print("", "Saving object data", sep = "\n", flush = True)
    objects.save_stream_many_metadata_by_time_range(*time_range_args)


# Get station info (websocket)
if station_count > 0:
    print("", "Saving station data", sep = "\n", flush = True)
    stations.save_stream_many_metadata_by_time_range(*time_range_args)

# Get snapshot data (websocket)
if snapshot_count > 0:
    print("", "Saving snapshot data", sep = "\n", flush = True)
    snapshots.save_stream_many_metadata_by_time_range_n_samples(*time_range_args, n_snapshots)


# ---------------------------------------------------------------------------------------------------------------------
#%% Clean up

# Finish timing with feedback
end_time_sec = perf_counter()
total_time_sec = (end_time_sec - start_time_sec)
print_time_taken(start_time_sec, end_time_sec)
print("")


# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap

