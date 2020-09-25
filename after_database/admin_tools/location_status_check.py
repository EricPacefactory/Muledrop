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

from local.lib.common.environment import get_dbserver_protocol
from local.lib.common.timekeeper_utils import isoformat_to_datetime, get_local_datetime

from local.lib.ui_utils.cli_selections import Resource_Selector
from local.lib.ui_utils.script_arguments import script_arg_builder

from local.online_database.request_from_dbserver import Server_Access, Camerainfo, Snapshots

from local.lib.file_access_utils.locations import load_location_info_dict, unpack_location_info_dict

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

# Confirm that we have a connection to the server
server_ref = Server_Access(host_ip, dbserver_port, is_secured = False)
connection_is_valid = server_ref.check_server_connection()
if not connection_is_valid:
    ide_quit("Couldn't connect to data server! ({})".format(server_ref.server_url))


# ---------------------------------------------------------------------------------------------------------------------
#%% Get camera listing from the database

# Get camera names to check
camera_names_list = server_ref.get_all_camera_names()
longest_name_len = max([len(each_name) for each_name in camera_names_list])

# Set up all data access objects
caminfo_dict = {}
snaps_dict = {}
for each_camera_name in camera_names_list:
    caminfo_dict[each_camera_name] = Camerainfo(server_ref, location_path, each_camera_name)
    snaps_dict[each_camera_name] = Snapshots(server_ref, location_path, each_camera_name)


# ---------------------------------------------------------------------------------------------------------------------
#%% Print server info

# Get basic info about the state of the server
server_memory_dict = server_ref.get_memory_usage()
server_disk_dict = server_ref.get_disk_usage()
print("",
      "{} ({})".format(location_select.upper(), host_ip),
      "  Disk Usage: {}%".format(server_disk_dict.get("percent_usage", "unknown")),
      "   RAM Usage: {}%".format(server_memory_dict.get("ram_percent_usage", "unknown")),
      sep = "\n")


# ---------------------------------------------------------------------------------------------------------------------
#%% Print camera lifetimes

# For clarity
seconds_per_hour = (60.0 * 60.0)

# Print out camera lifetime data as a group for comparison
print("", "Camera lifetimes:", sep = "\n")
for each_camera_name in camera_names_list:
    
    # For convenience
    camera_name_to_print = each_camera_name.rjust(longest_name_len)
    
    # Try to get newest metadata
    newest_caminfo_metadata = caminfo_dict[each_camera_name].get_newest_metadata(raise_errors = False)
    if newest_caminfo_metadata is None:
        print("  {}: error retrieving metadata...".format(camera_name_to_print))
        continue
    
    # Get timing info from newest metadata
    camera_start_dt_isoformat = newest_caminfo_metadata["start_datetime_isoformat"]
    camera_start_dt = isoformat_to_datetime(camera_start_dt_isoformat)
    
    # Get 'time since' newest entries
    current_dt = get_local_datetime()
    camera_lifetime_sec = max(0, (current_dt - camera_start_dt).total_seconds())
    
    # Convert times to more readable format & print
    camera_lifetime_hrs = int((camera_lifetime_sec / seconds_per_hour))
    print("  {}: {:.0f} hrs".format(camera_name_to_print, camera_lifetime_hrs))


# ---------------------------------------------------------------------------------------------------------------------
#%% Print snapshot ages

# Print out snapshot age data as a group for easier comparison
print("", "Most recent snapshot:", sep = "\n")
for each_camera_name in camera_names_list:
    
    # For convenience
    camera_name_to_print = each_camera_name.rjust(longest_name_len)
    
    # Try to get newest metadata
    newest_snap_metadata = snaps_dict[each_camera_name].get_newest_metadata(raise_errors = False)
    if newest_snap_metadata is None:
        print("  {}: error retrieving metadata...".format(camera_name_to_print))
        continue
    
    # Get timing info from newest metadata
    snap_dt_isoformat = newest_snap_metadata["datetime_isoformat"]
    snap_dt = isoformat_to_datetime(snap_dt_isoformat)
    
    # Get 'time since' newest entry
    current_dt = get_local_datetime()
    snap_age_sec = max(0, (current_dt - snap_dt).total_seconds())
    
    # Convert times to more readable format & print
    print("  {}: {:.0f} sec".format(camera_name_to_print, snap_age_sec))

# Add a blank space at the end for aesthetics
print("")


# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap

# TODO
# - add coloring to indicate good/bad status
# - add additional info (warn about overly large video width/height compared to snap width/height)
# 
