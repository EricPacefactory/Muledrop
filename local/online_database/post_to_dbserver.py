#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Feb 19 12:40:23 2020

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

import signal
import requests
import ujson
import datetime as dt

from multiprocessing import Process
from itertools import islice
from time import perf_counter, sleep
from random import random as unit_random

from local.lib.common.timekeeper_utils import get_human_readable_timestamp
from local.lib.common.environment import get_dbserver_protocol, get_dbserver_host, get_dbserver_port

from local.lib.ui_utils.cli_selections import Resource_Selector
from local.lib.ui_utils.script_arguments import script_arg_builder

from local.lib.file_access_utils.logging import build_post_db_log_path
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

from local.lib.file_access_utils.read_write import load_jgz

from local.eolib.utils.files import get_file_list_by_age
from local.eolib.utils.logging import Daily_Logger


# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes

# .....................................................................................................................

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Script control

# .....................................................................................................................

def parse_post_args(debug_print = False):
    
    # Get default values
    default_dbserver_protocol = get_dbserver_protocol()
    default_dbserver_host = get_dbserver_host()
    default_dbserver_port = get_dbserver_port()
    default_url = "{}://{}:{}".format(default_dbserver_protocol, default_dbserver_host, default_dbserver_port)
    
    # Set script arguments for posting camera data (manually)
    args_list = ["camera",
                 {"url": {"default": default_url, 
                          "help_text": "Specify the url of the upload server\n(Default: {})".format(default_url)}}]
    
    # Provide some extra information when accessing help text
    script_description = "Manually upload camera data to a target server/database"
    epilog_text = "\n".join(["************************* WARNING *************************",
                             "  Data is deleted after successfully uploading,",
                             "  or if duplicate entries already exist in the database!",
                             "***********************************************************"])
    
    # Build & evaluate script arguments!
    ap_result = script_arg_builder(args_list,
                                   description = script_description,
                                   epilog = epilog_text,
                                   parse_on_call = True,
                                   debug_print = debug_print)
    
    return ap_result

# .....................................................................................................................

def sigterm_quit(signal_number, stack_frame):
    
    '''
    Helper function, intended to be used if the script receives a SIGTERM command from the operating system.
    The function itself only raises a SystemExit error, which allows for SIGTERM events to be
    handled explicitly using a try/except statement!
      -> This is only expected to occur when running the 'scheduled_post(...)'
      function as a parallel process and calling a .terminate() command on it!
    '''
    
    raise SystemExit

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Define pathing functions

# .....................................................................................................................

def build_metadata_post_url(server_url, camera_select, collection_name):
    return "{}/{}/bdb/metadata/{}".format(server_url, camera_select, collection_name)

# .....................................................................................................................

def build_image_post_url(server_url, camera_select, collection_name, image_epoch_ms_str):
    return "/".join([server_url, camera_select, "bdb", "image", collection_name, image_epoch_ms_str])

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Define printing/logging functions

# .....................................................................................................................

def build_response_string_list(server_url, *messages):
    
    ''' Helper function for generating (timestamped!) response strings for printing/logging '''
    
    # Get timestamp
    post_datetime_str = get_human_readable_timestamp()
    
    # Build response list
    response_str_list = \
    ["{} @ {}".format(post_datetime_str, server_url),
     *messages]
    
    return response_str_list

# .....................................................................................................................

def build_response_count_string(data_type, collection_name, 
                                num_pass, num_fail, num_dupe, num_skip, num_total, total_time_ms):
    
    ''' Helper function which builds post response strings for printing/logging '''
    
    # Build strings showing counts of each response outcome
    # Example: "  2 pass,   0 fail,   1 dupe,   1 skip"
    build_count_str = lambda count_label, count: "{:>3} {}".format(count, count_label)
    pass_str = build_count_str("pass", num_pass)
    fail_str = build_count_str("fail", num_fail)
    dupe_str = build_count_str("dupe", num_dupe)
    skip_str = build_count_str("skip", num_skip)
    count_strs = ", ".join([pass_str, fail_str, dupe_str, skip_str])
    
    # Build indicator which includes the total response count + the data type (images/metadata) + collection name
    # Example: "  4 metadata | snapshots  "
    indicator_str = "{:>3} {:<8} | {:<11}".format(num_total, data_type, collection_name)
    
    # Build timing string
    # Example: "   77ms"
    time_str = "{:>5.0f}ms".format(total_time_ms)
    
    # Finally, combine all response data together for a single-line output
    # Example: "  2 pass,   0 fail,   1 dupe,   1 skip  ||    4 metadata | snapshots    ->    77ms"
    response_message = "{}  ||  {}  -> {}".format(count_strs, indicator_str, time_str)
    
    return response_message

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Define posting functions

# .....................................................................................................................

def post_many_metadata_to_server(server_url, camera_select, collection_name, metadata_folder_path, 
                                 minimum_age_sec = 5.0):
    
    '''
    Helper function which bundles all available metadata into a single (big!) json entry for the database
    '''
    
    # Start timing
    t1 = perf_counter()
    
    # Allocate storage for output counts
    num_success = 0
    num_failed = 0
    num_duplicate = 0
    num_ignore = 0
    num_loaded = 0
    
    # First get all the metadata file paths from the target folder path
    sorted_timestamps_list, sorted_paths_list = get_file_list_by_age(metadata_folder_path, 
                                                                     newest_first = False, 
                                                                     show_hidden_files = False, 
                                                                     create_missing_folder = False,
                                                                     return_full_path = True)
    
    # Bail on this if there is no report data, since we'll have nothing to bundle!
    num_files = len(sorted_paths_list)
    no_report_data = (num_files == 0)
    if no_report_data:
        response_msg = "No {} metadata to post!".format(collection_name)
        error_msg = ""
        return response_msg, error_msg
    
    # Figure out which files are 'old enough' to be safe for reading/deleting (i.e. not being actively written)
    current_timestamp = dt.datetime.now().timestamp()
    oldest_allowed_timestamp = (current_timestamp - minimum_age_sec)
    for each_reversed_idx, each_timestamp in enumerate(reversed(sorted_timestamps_list)):
        if each_timestamp < oldest_allowed_timestamp:
            break
    last_valid_entry_index = (num_files - each_reversed_idx)
    
    # Now build up all data into one list for one big insert!
    valid_path_list = []
    error_message_list = []
    data_insert_list = []
    for each_metadata_path in sorted_paths_list[:last_valid_entry_index]:
        try:
            data_insert_list.append(load_jgz(each_metadata_path))
            valid_path_list.append(each_metadata_path)
            
        except Exception as err:
            # In case something goes wrong, just delete the file... Will need better debugging/logging
            remove_if_possible(each_metadata_path)
            error_message_list.append("Metadata loading error:\n{}\n{}".format(each_metadata_path, str(err)))
    
    # For clarity
    post_kwargs = {"headers": {"Content-Type": "application/json"},
                   "auth": ("", ""),
                   "verify": False,
                   "timeout": 10.0}
    
    # Send it all to the server
    post_url = build_metadata_post_url(server_url, camera_select, collection_name)
    post_response = requests.post(post_url, data = ujson.dumps(data_insert_list), **post_kwargs)
    
    # Delete metadata that is successfully posted or already exists on the server
    metadata_posted_successfully = (post_response.status_code == 201)
    metadata_already_exists = (post_response.status_code == 405)
    if metadata_posted_successfully or metadata_already_exists:
        for each_metadata_path in valid_path_list:
            remove_if_possible(each_metadata_path)
            num_success += int(metadata_posted_successfully)
            num_duplicate += int(metadata_already_exists)
            
    # Log bad url pathing
    bad_url = (post_response.status_code == 404)
    if bad_url:
        error_message_list.append("Metadata posting to bad url:\n{}".format(post_url))
    
    # End timing
    t2 = perf_counter()
    total_time_ms = int(round(1000 * (t2 - t1)))
    
    # Finally, tally up the results & build a response string to return
    num_loaded = last_valid_entry_index
    num_ignore = num_files - num_loaded
    num_failed = num_loaded - num_success - num_duplicate
    response_msg = build_response_count_string("metadata", 
                                               collection_name,
                                               num_success, 
                                               num_failed, 
                                               num_duplicate, 
                                               num_ignore, 
                                               num_files, 
                                               total_time_ms)
    
    # Build error message (if present)
    error_msg = "\n".join(error_message_list)
    
    return response_msg, error_msg

# .....................................................................................................................

def post_many_images_to_server(server_url, camera_select, collection_name, image_folder_path, minimum_age_sec = 5.0):
    
    ''' Helper function for posting all the (new enough) images in a given folder to the server '''
    
    # Start timing
    t1 = perf_counter()
    
    # Allocate storage for output counts
    num_success = 0
    num_failed = 0
    num_duplicate = 0
    
    # First get all the image file paths the target folder path
    sorted_timestamps_list, sorted_paths_list = get_file_list_by_age(image_folder_path, 
                                                                     newest_first = False,
                                                                     show_hidden_files = False,
                                                                     create_missing_folder = False,
                                                                     return_full_path = True,
                                                                     allowable_exts_list = [".jpg"])
    
    # Bail on this if there is no image data, since we'll have nothing to bundle!
    num_files = len(sorted_paths_list)
    no_report_data = (num_files == 0)
    if no_report_data:
        response_msg = "No {} images to post!".format(collection_name)
        error_msg = ""
        return response_msg, error_msg
    
    # Figure out which images are 'old enough' to be safe for reading/deleting (i.e. not being actively written)
    current_timestamp = dt.datetime.now().timestamp()
    oldest_allowed_timestamp = (current_timestamp - minimum_age_sec)
    for each_reversed_idx, each_timestamp in enumerate(reversed(sorted_timestamps_list)):
        if each_timestamp < oldest_allowed_timestamp:
            break
    last_valid_entry_index = (num_files - each_reversed_idx)
    
    # For clarity
    post_kwargs = {"headers": {"Content-Type": "image/jpeg"},
                   "auth": ("", ""),
                   "verify": False,
                   "timeout": 10.0}
    
    # Only post the newest images
    error_message_list = []
    load_path_list = islice(sorted_paths_list, last_valid_entry_index)
    for each_image_path in load_path_list:
        
        # Figure out the image post url
        image_filename = os.path.basename(each_image_path)
        image_epoch_ms_str, _ = os.path.splitext(image_filename)
        
        # Build the posting url and send the image
        image_post_url = build_image_post_url(server_url, camera_select, collection_name, image_epoch_ms_str)
        
        try:
            with open(each_image_path, "rb") as image_file:
                post_response = requests.post(image_post_url, data = image_file, **post_kwargs)
                
        except Exception as err:
            
            # In case something goes wrong, just delete the image data... Will need better debugging/logging
            remove_if_possible(each_image_path)
            error_message_list.append("Image posting error:\n{}\n{}".format(each_image_path, str(err)))
            continue
            
        # Delete images that successfully post or already exist on the server
        image_posted_successfully = (post_response.status_code == 201)
        image_already_exists = (post_response.status_code == 405)
        if image_posted_successfully or image_already_exists:
            remove_if_possible(each_image_path)
            num_success += int(image_posted_successfully)
            num_duplicate += int(image_already_exists)
        
        # Handle bad url pathing
        bad_url = (post_response.status_code == 404)
        if bad_url:
            remove_if_possible(each_image_path)
            error_message_list.append("Image posting to bad url:\n{}\n{}".format(each_image_path, image_post_url))
    
    # End timing
    t2 = perf_counter()
    total_time_ms = int(round(1000 * (t2 - t1)))
    
    # Finally, tally up the results & build a response string to return
    num_loaded = last_valid_entry_index
    num_ignore = num_files - num_loaded
    num_failed = num_loaded - num_success - num_duplicate
    response_msg = build_response_count_string("images", 
                                               collection_name,
                                               num_success, 
                                               num_failed, 
                                               num_duplicate, 
                                               num_ignore, 
                                               num_files, 
                                               total_time_ms)
    
    # Build error message (if present)
    error_msg = "\n".join(error_message_list)
    
    return response_msg, error_msg

# .....................................................................................................................

def post_data_to_server(server_url, cameras_folder_path, camera_select, log_to_file = True):
    
    # Start timing
    t1 = perf_counter()
    
    # Bundle pathing args for convenience
    hard_coded_user_select = "live"
    camera_pathing_args = (cameras_folder_path, camera_select, hard_coded_user_select)
    
    # Build pathing to all report data that needs to get to the database
    caminfo_metadata_path = build_camera_info_metadata_report_path(*camera_pathing_args)
    bg_metadata_path = build_background_metadata_report_path(*camera_pathing_args)
    snap_metadata_path = build_snapshot_metadata_report_path(*camera_pathing_args)
    obj_metadata_path = build_object_metadata_report_path(*camera_pathing_args)
    
    # Post report metadata
    url_args = (server_url, camera_select)
    caminfo_md_log, caminfo_md_err = post_many_metadata_to_server(*url_args, "camerainfo", caminfo_metadata_path)
    bg_md_log, bg_mg_err = post_many_metadata_to_server(*url_args, "backgrounds", bg_metadata_path)
    snap_md_log, snap_md_err = post_many_metadata_to_server(*url_args, "snapshots", snap_metadata_path)
    obj_md_log, obj_md_err = post_many_metadata_to_server(*url_args, "objects", obj_metadata_path)
    
    # Finish metadata timing
    t2 = perf_counter()
    
    # Build pathing to all image data that needs to be sent to the database
    bg_image_path = build_background_image_report_path(*camera_pathing_args)
    snap_image_path = build_snapshot_image_report_path(*camera_pathing_args)
    
    # *** Important:
    # *** Images should be posted AFTER metadata
    # *** to ensure available metadata is always 'behind' available image data on the database
    # *** this avoids the situation where metadata is available that points to a non-existent image
    # Post image data
    bg_img_log, bg_img_err = post_many_images_to_server(*url_args, "backgrounds", bg_image_path)
    snap_img_log, snap_img_err = post_many_images_to_server(*url_args, "snapshots", snap_image_path)
    
    # Finish image timing
    t3 = perf_counter()
    
    # Calculate output timing results
    metadata_time_taken_ms = 1000 * (t2 - t1)
    image_time_taken_ms = 1000 * (t3 - t2)
    timing_response_str = "Metadata took {:.0f} ms, images took {:.0f} ms".format(metadata_time_taken_ms,
                                                                                  image_time_taken_ms)
    
    # Build complete response string for feedback/logging
    full_error_msg_list = [caminfo_md_err, bg_mg_err, snap_md_err, obj_md_err, bg_img_err, snap_img_err]
    reduced_error_msg_list = [each_msg for each_msg in full_error_msg_list if each_msg != ""]
    response_list = build_response_string_list(server_url,
                                               caminfo_md_log, bg_md_log, snap_md_log, obj_md_log,
                                               bg_img_log, snap_img_log,
                                               timing_response_str,
                                               *reduced_error_msg_list)
    
    return response_list

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Automation functions

# .....................................................................................................................

def remove_if_possible(file_path_to_remove):
    
    ''' Helper function used to delete files that may have already been deleted '''
    
    file_existed = False
    try:
        os.remove(file_path_to_remove)
        file_existed = True
    except FileNotFoundError:
        pass
    
    return file_existed

# .....................................................................................................................

def create_logger(cameras_folder_path, camera_select, enabled = True):
    
    ''' Helper function to standardize the logger inputs, in case we use it when running this script directly '''
    
    logging_folder_path = build_post_db_log_path(cameras_folder_path, camera_select)
    logger = Daily_Logger(logging_folder_path, log_files_to_keep = 10, enabled = enabled)
    
    return logger

# .....................................................................................................................

def check_server_connection(server_url):
    
    ''' Helper function which checks that a server is accessible (for posting!) '''
    
    # Build server status check url
    status_check_url = "{}/is-alive".format(server_url)
    
    # Request status check from the server
    server_is_alive = False
    try:
        server_response = requests.get(status_check_url, timeout = 10)
        server_is_alive = (server_response.status_code == 200)
    except (requests.ConnectionError, requests.exceptions.ReadTimeout):
        server_is_alive = False
    
    return server_is_alive

# .....................................................................................................................

def scheduled_post(server_url, cameras_folder_path, camera_select,
                   post_period_mins = 2.5,
                   post_on_startup = True,
                   log_to_file = True):
    
    # Bail if we don't get a valid server url
    invalid_url = (server_url in {"", "None", "none", None})
    if invalid_url:
        return
    
    # Register signal handler to catch termination events & exit gracefully
    signal.signal(signal.SIGTERM, sigterm_quit)
    
    # Create logger to handle saving feedback (or printing to terminal)
    logger = create_logger(cameras_folder_path, camera_select, enabled = log_to_file)
    
    # Calculate posting period values
    post_period_sec = (60.0 * post_period_mins)
    random_period_sec = max(20.0, 0.2 * post_period_sec)
    
    # If we aren't posting on startup, we need to have an initial sleep period before posting!
    if not post_on_startup:
        sleep(post_period_sec)
    
    try:
        # Post & sleep & post & sleep & ...
        while True:
                        
            # Post all available data
            response_list = single_post(server_url, cameras_folder_path, camera_select)
            
            # Print or log response
            logger.log_list(response_list)
            
            # Delay posting regardless of server status
            random_sleep_sec = (unit_random() * random_period_sec)
            sleep_time_sec = post_period_sec + random_sleep_sec
            sleep(sleep_time_sec)
            
    except SystemExit:
        
        # Catch SIGTERM signals, in case this is running as parallel process that may be terminated
        response_list = build_response_string_list(server_url, "Kill signal received. Posting has been halted!!")
        logger.log_list(response_list)
        
    return

# .....................................................................................................................

def single_post(server_url, cameras_folder_path, camera_select):
    
    # Check that the server is accessible before we try posting tons of stuff to it
    connection_is_valid = check_server_connection(server_url)
    
    # Bail if we couldn't connect to the server, with some kind of feedback
    if not connection_is_valid:
        response_list = build_response_string_list(server_url, "Could not connect to server!")
        return response_list
    
    # If we get here, try to post the data to the server!
    response_list = post_data_to_server(server_url, cameras_folder_path, camera_select)
    
    return response_list

# .....................................................................................................................

def create_parallel_scheduled_post(server_url, cameras_folder_path, camera_select, 
                                   post_period_mins = 3.0, 
                                   post_on_startup = True,
                                   log_to_file = True,
                                   start_on_call = True):
    
    # Build configuration input for parallel process setup
    config_dict = {"server_url": server_url,
                   "cameras_folder_path": cameras_folder_path,
                   "camera_select": camera_select,
                   "post_period_mins": post_period_mins,
                   "post_on_startup": post_on_startup,
                   "log_to_file": log_to_file}
    
    # Create a parallel process to run the scheduled post function and start it, if needed
    close_when_parent_closes = True
    parallel_post_func = Process(target = scheduled_post, kwargs = config_dict, daemon = close_when_parent_closes)    
    if start_on_call:
        parallel_post_func.start()
    
    return parallel_post_func

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Manual run

if __name__ == "__main__":
    
    # Grab script arguments, only when running manually
    script_args = parse_post_args()
    arg_camera_select = script_args["camera"]
    arg_server_url = script_args["url"]
    
    # Create selector so we can access existing report data
    selector = Resource_Selector()
    project_root_path, cameras_folder_path = selector.get_project_pathing()
    
    # Prompt to select a camera, if it wasn't already selected through script arguments
    camera_select = arg_camera_select
    if camera_select is None:
        camera_select, camera_path = selector.camera()
    
    # Only post once when running directly from this script!
    response_list = single_post(arg_server_url, cameras_folder_path, camera_select)
    
    # Pretend we're logging so we can make use of the same functionality
    logger = create_logger(cameras_folder_path, camera_select, enabled = False)
    logger.log_list(response_list, prepend_empty_line = True)
    

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap


