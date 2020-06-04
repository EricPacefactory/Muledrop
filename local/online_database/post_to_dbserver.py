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

from multiprocessing import Process
from time import perf_counter, sleep
from random import random as unit_random

from local.lib.common.timekeeper_utils import get_human_readable_timestamp, get_local_datetime
from local.lib.common.environment import get_dbserver_protocol, get_dbserver_host, get_dbserver_port
from local.lib.common.environment import get_autopost_on_startup, get_autopost_period_mins

from local.lib.ui_utils.cli_selections import Resource_Selector
from local.lib.ui_utils.script_arguments import script_arg_builder

from local.lib.file_access_utils.logging import build_post_db_log_path
from local.lib.file_access_utils.reporting import build_camera_info_metadata_report_path
from local.lib.file_access_utils.reporting import build_snapshot_metadata_report_path
from local.lib.file_access_utils.reporting import build_object_metadata_report_path
from local.lib.file_access_utils.reporting import build_background_metadata_report_path
from local.lib.file_access_utils.reporting import build_snapshot_image_report_path
from local.lib.file_access_utils.reporting import build_background_image_report_path

from local.lib.file_access_utils.metadata_read_write import load_metadata

from local.eolib.utils.files import get_file_list, split_to_sublists
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

def build_metadata_bulk_post_url(server_url, camera_select, collection_name):
    return "{}/{}/bdb/metadata/{}".format(server_url, camera_select, collection_name)

# .....................................................................................................................

def build_image_post_url(server_url, camera_select, collection_name, image_epoch_ms_str):
    return "/".join([server_url, camera_select, "bdb", "image", collection_name, image_epoch_ms_str])

# .....................................................................................................................

def get_file_paths_to_post(*parent_folder_paths):
    
    ''' Helper function used to get file paths in a consistent style for all data sets '''
    
    # Get all files paths for all parent folders provided
    sorted_file_paths_lists = []
    for each_parent_folder_path in parent_folder_paths:
        new_file_path_list = get_file_list(each_parent_folder_path,
                                           show_hidden_files = False,
                                           create_missing_folder = False,
                                           return_full_path = True,
                                           sort_list = True)
        sorted_file_paths_lists.append(new_file_path_list)
    
    # Special case, return a list of paths directly (rather than list-of-lists of paths) if only one parent given
    if len(parent_folder_paths) == 1:
        return sorted_file_paths_lists[0]
    
    return sorted_file_paths_lists

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
    reduced_message_iter = (each_message for each_message in messages if len(each_message) > 1)
    response_str_list = \
    ["{} @ {}".format(post_datetime_str, server_url),
     *reduced_message_iter]
    
    return response_str_list

# .....................................................................................................................

def build_response_count_string(collection_name, data_type,
                                num_pass, num_dupe, num_total, total_time_ms):
    
    ''' Helper function which builds post response strings for printing/logging '''
    
    # Figure out how many posts failed based on inputs
    num_fail = num_total - num_pass - num_dupe
    
    # Build strings showing counts of each response outcome
    # Example: "   2 pass,    0 fail,    1 dupe"
    build_count_str = lambda count_label, count: "{:>4} {}".format(count, count_label)
    pass_str = build_count_str("pass", num_pass)
    fail_str = build_count_str("fail", num_fail)
    dupe_str = build_count_str("dupe", num_dupe)
    count_strs = ", ".join([pass_str, fail_str, dupe_str])
    
    # Build indicator which includes the total response count + the data type (images/metadata) + collection name
    # Example: "   4 metadata | snapshots  "
    indicator_str = "{:>4} {:<8} | {:<11}".format(num_total, data_type, collection_name)
    
    # Build timing string
    # Example: "   77ms"
    time_str = "{:>6.0f}ms".format(total_time_ms)
    
    # Finally, combine all response data together for a single-line output
    # Example: "   2 pass,   0 fail,   1 dupe  ||     4 metadata | snapshots    ->     77ms"
    response_message = "{}  ||  {}  -> {}".format(count_strs, indicator_str, time_str)
    
    return response_message

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Define posting helpers

# .....................................................................................................................

def bundle_metadata(metadata_file_paths):
    
    '''
    Helper function which bundles all available metadata into
    groups (subsets) of entries to bulk-insert into the database.
    '''
    
    # Now build up all data into one list for a bulk insert
    error_message_list = []
    data_insert_list = []
    for each_metadata_path in metadata_file_paths:
        try:
            data_insert_list.append(load_metadata(each_metadata_path))
            
        except ValueError:
            # Empty/incorrectly saved files raise value errors
            error_message_list.append("Metadata loading error:\n{}\n{}".format(each_metadata_path, "Bad json data"))
            
        except Exception as err:
            # In case something unexpected happens, try to log some info
            error_message_list.append("Metadata loading error:\n{}\n{}".format(each_metadata_path, str(err)))
    
    return data_insert_list, error_message_list

# .....................................................................................................................

def bulk_post_metadata(post_kwargs, data_insert_list):
    
    ''' Helper function which handles bulk metadata posts, with error handling '''
    
    # Initialize outputs
    bad_url = False
    num_success = 0
    num_duplicate = 0
    num_total = len(data_insert_list)
    
    try:
        post_response = requests.post(data = ujson.dumps(data_insert_list), **post_kwargs)
        
        # For clarity
        bad_url = (post_response.status_code == 404)
        posted_successfully = (post_response.status_code == 201)
        posted_with_duplicates = (post_response.status_code == 405)
        
        # Handle success case
        if posted_successfully:
            num_success = num_total
            num_duplicate = 0
        
        # Handle counts in duplicate case
        if posted_with_duplicates:
            response_dict = post_response.json()
            num_success = response_dict.get("mongo_response", {}).get("details", {}).get("nInserted", 0)
            num_duplicate = num_total - num_success
        
    except requests.exceptions.Timeout:
        # Occurs when server doesn't respond in time (timeout value is set in post_kwargs)
        pass
        
    except (requests.ConnectionError, requests.exceptions.ReadTimeout):
        # Occurs when attempt to connect to the server fails
        pass
    
    return bad_url, num_success, num_duplicate

# .....................................................................................................................

def single_post_image(image_post_url, image_path, post_kwargs):
    
    # Initialize outputs
    bad_url = False
    posted_successfully = False
    image_already_exists = False
    
    try:
        
        with open(image_path, "rb") as image_file:
            post_response = requests.post(image_post_url, data = image_file, **post_kwargs)
        
        # Handle expected response codes
        bad_url = (post_response.status_code == 404)
        posted_successfully = (post_response.status_code == 201)
        image_already_exists = (post_response.status_code == 405)
    
    except requests.exceptions.Timeout:
        # Occurs when server doesn't respond in time (timeout value is set in post_kwargs)
        pass
    
    except (requests.ConnectionError, requests.exceptions.ReadTimeout):
        # Occurs when attempt to connect to the server fails
        pass
    
    except Exception:
        pass
    
    return bad_url, posted_successfully, image_already_exists

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Specific posting functions

# .....................................................................................................................

def post_all_camera_info(server_url, cameras_folder_path, camera_select, user_select):
    
    # For clarity
    collection_name = "camerainfo"
    
    # Build pathing to all report data
    md_folder_path = build_camera_info_metadata_report_path(cameras_folder_path, camera_select, user_select)
    md_file_paths = get_file_paths_to_post(md_folder_path)
    
    # Bail if there is no data
    num_md_files = len(md_file_paths)
    no_report_data = (num_md_files == 0)
    if no_report_data:
        empty_msg = ""
        return empty_msg, empty_msg
    
    # Build url & post the data!
    post_url = build_metadata_bulk_post_url(server_url, camera_select, collection_name)
    total_md_success, total_md_duplicate, total_md_time_ms, md_error_message_list = \
    post_all_metadata_to_server(post_url, md_file_paths)
    
    # Build outputs
    error_msg = "\n".join(md_error_message_list)
    response_msg = build_response_count_string(collection_name, "metadata",
                                               total_md_success, total_md_duplicate, num_md_files, total_md_time_ms)
    
    return response_msg, error_msg

# .....................................................................................................................

def post_all_background_data(server_url, cameras_folder_path, camera_select, user_select):
    
    # For clarity
    collection_name = "backgrounds"
    
    # Build pathing to all report data
    md_folder_path = build_background_metadata_report_path(cameras_folder_path, camera_select, user_select)
    img_folder_path = build_background_image_report_path(cameras_folder_path, camera_select, user_select)
    
    # Get all metadata paths before images so that the metadata will lag the images on the db
    # -> This way, we won't have the 'newest' metadata entries posted without corresponding image data!
    md_file_paths, img_file_paths = get_file_paths_to_post(md_folder_path, img_folder_path)
    
    # Bail if there is no data
    num_md_files = len(md_file_paths)
    num_img_files = len(img_file_paths)
    no_report_data = (num_md_files == 0 or num_img_files == 0)
    if no_report_data:
        empty_msg = ""
        return empty_msg, empty_msg, empty_msg
    
    # Post image data first, so metadata is guaranteed to reference valid data
    total_img_success, total_img_duplicate, total_img_time_ms, img_error_message_list = \
    post_all_images_to_server(server_url, camera_select, collection_name, img_file_paths)
    
    # Build metadata url & post the data!
    post_url = build_metadata_bulk_post_url(server_url, camera_select, collection_name)
    total_md_success, total_md_duplicate, total_md_time_ms, md_error_message_list = \
    post_all_metadata_to_server(post_url, md_file_paths)
    
    # Build outputs
    error_msg = "\n".join(img_error_message_list + md_error_message_list)
    img_response_msg = build_response_count_string(collection_name, "images",
                                                   total_img_success,
                                                   total_img_duplicate,
                                                   num_img_files,
                                                   total_img_time_ms)
    md_response_msg = build_response_count_string(collection_name, "metadata",
                                                  total_md_success,
                                                  total_md_duplicate,
                                                  num_md_files,
                                                  total_md_time_ms)
    
    return img_response_msg, md_response_msg, error_msg

# .....................................................................................................................

def post_all_object_data(server_url, cameras_folder_path, camera_select, user_select):
    
    # For clarity
    collection_name = "objects"
    
    # Build pathing to all report data
    md_folder_path = build_object_metadata_report_path(cameras_folder_path, camera_select, user_select)
    md_file_paths = get_file_paths_to_post(md_folder_path)
    
    # Bail if there is no data
    num_md_files = len(md_file_paths)
    no_report_data = (num_md_files == 0)
    if no_report_data:
        empty_msg = ""
        return empty_msg, empty_msg
    
    # Build url & post the data!
    post_url = build_metadata_bulk_post_url(server_url, camera_select, collection_name)
    total_md_success, total_md_duplicate, total_md_time_ms, md_error_message_list = \
    post_all_metadata_to_server(post_url, md_file_paths)
    
    # Build outputs
    error_msg = "\n".join(md_error_message_list)
    response_msg = build_response_count_string(collection_name, "metadata",
                                               total_md_success, total_md_duplicate, num_md_files, total_md_time_ms)
    
    return response_msg, error_msg

# .....................................................................................................................

def post_all_snapshot_data(server_url, cameras_folder_path, camera_select, user_select):
    
    # For clarity
    collection_name = "snapshots"
    
    # Build pathing to all report data
    md_folder_path = build_snapshot_metadata_report_path(cameras_folder_path, camera_select, user_select)
    img_folder_path = build_snapshot_image_report_path(cameras_folder_path, camera_select, user_select)
    
    # Get all metadata paths before images so that the metadata will lag the images on the db
    # -> This way, we won't have the 'newest' metadata entries posted without corresponding image data!
    md_file_paths, img_file_paths = get_file_paths_to_post(md_folder_path, img_folder_path)
    
    # Bail if there is no data
    num_md_files = len(md_file_paths)
    num_img_files = len(img_file_paths)
    no_report_data = (num_md_files == 0 or num_img_files == 0)
    if no_report_data:
        empty_msg = ""
        return empty_msg, empty_msg, empty_msg
    
    # Post image data first, so metadata is guaranteed to reference valid data
    total_img_success, total_img_duplicate, total_img_time_ms, img_error_message_list = \
    post_all_images_to_server(server_url, camera_select, collection_name, img_file_paths)
    
    # Build metadata url & post the data!
    post_url = build_metadata_bulk_post_url(server_url, camera_select, collection_name)
    total_md_success, total_md_duplicate, total_md_time_ms, md_error_message_list = \
    post_all_metadata_to_server(post_url, md_file_paths)
    
    # Build outputs
    error_msg = "\n".join(img_error_message_list + md_error_message_list)
    img_response_msg = build_response_count_string(collection_name, "images",
                                                   total_img_success,
                                                   total_img_duplicate,
                                                   num_img_files,
                                                   total_img_time_ms)
    md_response_msg = build_response_count_string(collection_name, "metadata",
                                                  total_md_success,
                                                  total_md_duplicate,
                                                  num_md_files,
                                                  total_md_time_ms)
    
    return img_response_msg, md_response_msg, error_msg

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Define high-level posting functions

# .....................................................................................................................

def post_all_metadata_to_server(post_url, metadata_file_paths, maximum_subset_size = 500, file_age_buffer_sec = 1.0):
    
    ''' Helper function for posting all the metadata in a given folder to the server '''
    
    # Set up posting info
    per_bundle_timeout_sec = max(10.0, (maximum_subset_size * 0.5))
    post_kwargs = {"url": post_url,
                   "headers": {"Content-Type": "application/json"},
                   "auth": ("", ""),
                   "verify": False,
                   "timeout": per_bundle_timeout_sec}
    
    # Initialize outputs
    total_success = 0
    total_duplicate = 0
    error_message_list = []
    
    # Pause briefly to give the 'newest' files a chance to finish writing
    newest_file_path = metadata_file_paths[-1]
    delay_for_newest_file(newest_file_path, file_age_buffer_sec)
    
    # Start timing
    t1 = perf_counter()
    
    # Post metadata in subsets
    sorted_path_sublists = split_to_sublists(metadata_file_paths, maximum_subset_size)
    for each_path_sublist in sorted_path_sublists:
        
        # Collect groups of metadata entries together for bulk-insert into the database
        data_insert_list, bundle_error_msg_list = bundle_metadata(each_path_sublist)
        error_message_list += bundle_error_msg_list
        
        # Try to post the bundle of data
        bad_url, num_success, num_duplicate = bulk_post_metadata(post_kwargs, data_insert_list)
        total_success += num_success
        total_duplicate += num_duplicate
        
        # If we're posting to a bad url, bail on everything!
        if bad_url:
            bad_url_error_message = "Metadata posting to bad url:\n{}".format(post_url)
            error_message_list.append(bad_url_error_message)
            break
        
        # If we get here, we've reached the db and posted what we could, so now we're done with these files
        for each_metadata_path in each_path_sublist:
            remove_if_possible(each_metadata_path)
    
    # End timing
    t2 = perf_counter()
    total_time_ms = int(round(1000 * (t2 - t1)))
    
    return total_success, total_duplicate, total_time_ms, error_message_list

# .....................................................................................................................

def post_all_images_to_server(server_url, camera_select, collection_name, image_file_paths, file_age_buffer_sec = 1.0):
    
    ''' Helper function for posting all the images in a given folder to the server '''
    
    # Set up posting info
    per_image_timeout_sec = 15.0
    post_kwargs = {"headers": {"Content-Type": "image/jpeg"},
                   "auth": ("", ""),
                   "verify": False,
                   "timeout": per_image_timeout_sec}
    
    # Initialize storage for outputs
    error_message_list = []
    total_success = 0
    total_duplicate = 0
    
    # Pause briefly to give the 'newest' files a chance to finish writing
    newest_file_path = image_file_paths[-1]
    delay_for_newest_file(newest_file_path, file_age_buffer_sec)
    
    # Start timing
    t1 = perf_counter()
    
    # Post all images
    error_message_list = []
    for each_image_path in image_file_paths:
        
        # Figure out the image post url
        image_filename = os.path.basename(each_image_path)
        image_epoch_ms_str, _ = os.path.splitext(image_filename)
        
        # Build the posting url and send the image
        image_post_url = build_image_post_url(server_url, camera_select, collection_name, image_epoch_ms_str)
        bad_url, image_post_success, image_post_duplicate = single_post_image(image_post_url,
                                                                              each_image_path,
                                                                              post_kwargs)
        
        # If we're posting to a bad url, bail on everything!
        if bad_url:
            bad_url_error_message = "({}) Image posting to bad url:\n@ {}".format(image_filename, image_post_url)
            error_message_list.append(bad_url_error_message)
            break
        
        # Add up total counts
        total_success += int(image_post_success)
        total_duplicate += int(image_post_duplicate)
        
        # If we get here, we've reached the db and posted what we could, so now we're done with this file
        remove_if_possible(each_image_path)
    
    # End timing
    t2 = perf_counter()
    total_time_ms = int(round(1000 * (t2 - t1)))
    
    return total_success, total_duplicate, total_time_ms, error_message_list

# .....................................................................................................................

def post_data_to_server(server_url, cameras_folder_path, camera_select, log_to_file = True):
    
    # Start timing
    t1 = perf_counter()
    
    # Bundle pathing args for convenience
    hard_coded_user_select = "live"
    camera_pathing_args = (cameras_folder_path, camera_select, hard_coded_user_select)
    
    # Post each data set
    caminfo_log, caminfo_err = post_all_camera_info(server_url, *camera_pathing_args)
    bg_img_log, bg_md_log, bg_err = post_all_background_data(server_url, *camera_pathing_args)
    obj_log, obj_err = post_all_object_data(server_url, *camera_pathing_args)
    snap_img_log, snap_md_log, snap_err = post_all_snapshot_data(server_url, *camera_pathing_args)
    
    # Finish timing
    t2 = perf_counter()
    total_time_taken_ms = int(round(1000 * (t2 - t1)))
    timing_response_str = "Took {:.0f} ms total (w/ protect)".format(total_time_taken_ms)
    
    # Build complete response string for feedback/logging
    full_error_msg_list = [caminfo_err, bg_err, obj_err, snap_err]
    reduced_error_msg_list = [each_msg for each_msg in full_error_msg_list if each_msg != ""]
    response_list = build_response_string_list(server_url,
                                               snap_img_log, bg_img_log,
                                               caminfo_log, bg_md_log, obj_log, snap_md_log,
                                               timing_response_str,
                                               *reduced_error_msg_list)
    
    return response_list

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Automation functions

# .....................................................................................................................

def delay_for_newest_file(newest_file_path, maximum_delay_time_sec = 1.0):
    
    ''' Helper function used to introduce delays before posting 'new' files, in case they haven't finished writing '''
    
    # Compare the current time to the newest file time
    current_timestamp = get_local_datetime().timestamp()
    file_timestamp = os.path.getmtime(newest_file_path)
    time_delta_sec = (current_timestamp - file_timestamp)
    
    # If the newest file time is very recent, delay a bit to give it time to finish saving (in case it is in-progress)
    delay_time_sec = (maximum_delay_time_sec - time_delta_sec)
    if delay_time_sec > 0:
        sleep(delay_time_sec)
    
    return

# .....................................................................................................................

def calculate_sleep_delay_sec(minimum_sleep_sec = 20.0):
    
    '''
    Helper function used to calculate a sleep time (in seconds), used to delay posting
    Note that the sleep timing can be (partly) controlled through an environment variable,
    so the timing can be modified while the script is still active!
    '''
    
    # Get delay values
    post_period_mins = get_autopost_period_mins()
    post_period_sec = (60.0 * post_period_mins)
    random_period_sec = max(0.2 * post_period_sec, minimum_sleep_sec)
    
    # Generate randomized sleep time
    random_sleep_sec = (unit_random() * random_period_sec)
    sleep_time_sec = post_period_sec + random_sleep_sec
    
    return sleep_time_sec

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
    logger = Daily_Logger(logging_folder_path, log_files_to_keep = 10, enabled = enabled, include_timestamp = False)
    
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

def scheduled_post(server_url, cameras_folder_path, camera_select, log_to_file = True):
    
    # Bail if we don't get a valid server url
    invalid_url = (server_url in {"", "None", "none", None})
    if invalid_url:
        return
    
    # Register signal handler to catch termination events & exit gracefully
    signal.signal(signal.SIGTERM, sigterm_quit)
    
    # Create logger to handle saving feedback (or printing to terminal)
    logger = create_logger(cameras_folder_path, camera_select, enabled = log_to_file)
    
    # If we aren't posting on startup, we need to have an initial sleep period before posting!
    post_on_startup = get_autopost_on_startup()
    if not post_on_startup:
        sleep_time_sec = calculate_sleep_delay_sec()
        sleep(sleep_time_sec)
    
    try:
        # Post & sleep & post & sleep & ...
        while True:
            
            # Post all available data
            response_list = single_post(server_url, cameras_folder_path, camera_select)
            
            # Print or log response
            logger.log_list(response_list)
            
            # Delay posting regardless of server status
            sleep_time_sec = calculate_sleep_delay_sec()
            sleep(sleep_time_sec)
        
    except SystemExit:
        
        # Catch SIGTERM signals, in case this is running as parallel process that may be terminated
        response_list = build_response_string_list(server_url, "Kill signal received. Posting has been halted!!")
        logger.log_list(response_list)
        
    except KeyboardInterrupt:
        
        # Catch keyboard cancels, in case this is running as parallel process that may be terminated
        response_list = build_response_string_list(server_url, "Keyboard cancel! Posting has been halted!!")
        logger.log_list(response_list)
        
    except Exception as err:
        
        # Handle any unexpected errors, so that we 'gracefully' get out of this function
        response_list = build_response_string_list(server_url, "Unknown error! Closing...", str(err))
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
                                   log_to_file = True,
                                   start_on_call = True):
    
    # Build configuration input for parallel process setup
    config_dict = {"server_url": server_url,
                   "cameras_folder_path": cameras_folder_path,
                   "camera_select": camera_select,
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
    
    # Some feedback when running manually
    print("", "Manually posting data for {}...".format(camera_select), sep = "\n")
    
    # Only post once when running directly from this script!
    response_list = single_post(arg_server_url, cameras_folder_path, camera_select)
    
    # Pretend we're logging so we can make use of the same functionality
    logger = create_logger(cameras_folder_path, camera_select, enabled = False)
    logger.log_list(response_list, prepend_empty_line = True)


# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap


