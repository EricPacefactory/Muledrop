#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Dec 28 12:10:24 2019

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

import cv2

from itertools import cycle
from time import sleep

from local.lib.common.timekeeper_utils import get_local_datetime, datetime_to_epoch_ms, datetime_to_isoformat_string
from local.lib.ui_utils.cli_selections import Resource_Selector
from local.lib.ui_utils.script_arguments import script_arg_builder

from local.offline_database.file_database import launch_file_db, close_dbs_if_missing_data

from flask import Flask, jsonify, Response
from flask_cors import CORS

from local.eolib.utils.quitters import ide_catcher


# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

# .....................................................................................................................

def parse_server_args(debug_print = False):
    
    # Set script arguments for running the file server
    args_list = ["camera",
                 {"user": {"default": "live"}}]
    
    # Provide some extra information when accessing help text
    script_description = "Launches an in-RAM database holding real-time data collection results, for experimenting."
    
    # Build & evaluate script arguments!
    ap_result = script_arg_builder(args_list,
                                   description = script_description,
                                   parse_on_call = True,
                                   debug_print = debug_print)
    
    return ap_result

# .....................................................................................................................

def image_to_jpg_bytearray(image):
    
    # Convert raw data to a jpg, then to a byte array which can be sent to a browser for display
    _, encoded_image = cv2.imencode(".jpg", image)
    
    return bytearray(encoded_image)

# .....................................................................................................................

def initialize_databases(selector_ref, cameras_folder_path, camera_name_list, user_select,
                         raise_error_message = False):
    
    # Initialize outputs
    cinfo_dbs_dict = {}
    rinfo_dbs_dict = {}
    snap_dbs_dict = {}
    obj_dbs_dict = {}
    class_dbs_dict = {}
    summary_dbs_dict = {}
    rule_dbs_dict = {}

    for each_camera in camera_name_list:
        
        # Launch all the dbs
        try:
            cinfo_db, rinfo_db, snap_db, obj_db, class_db, summary_db, rule_db = \
            launch_file_db(cameras_folder_path, each_camera, user_select,
                           check_same_thread = False,
                           launch_snapshot_db = True,
                           launch_object_db = True,
                           launch_classification_db = True,
                           launch_summary_db = True,
                           launch_rule_db = True)
        except Exception as err:
            print("",  "", 
                  "Error loading data for camera: {}".format(each_camera),
                  "  Dataset is likely out of date?",
                  "  Search for this error message and raise error for further debugging!",
                  "", sep = "\n")
            
            # For debugging
            if raise_error_message:
                raise err
            
            sleep(2.0)
            continue
        
        # Skip any cameras that don't contain snapshot/object data
        missing_snap_data = close_dbs_if_missing_data(snap_db, error_message_if_missing = None)
        missing_obj_data = close_dbs_if_missing_data(obj_db, error_message_if_missing = None)
        if missing_snap_data or missing_obj_data:
            msg_spacer = 3
            close_msg = "Closed due to missing snapshot/object data!"
            spaced_msg = "{}{}{}".format(" " * msg_spacer, close_msg, " " * msg_spacer)
            spaced_msg_length = len(spaced_msg)
            print("^" * spaced_msg_length, spaced_msg, "-" * spaced_msg_length, "", sep = "\n")
            sleep(2.0)
            continue
        
        # Add dbs to the dictionaries
        cinfo_dbs_dict[each_camera] = cinfo_db
        rinfo_dbs_dict[each_camera] = rinfo_db
        snap_dbs_dict[each_camera] = snap_db
        obj_dbs_dict[each_camera] = obj_db
        class_dbs_dict[each_camera] = class_db
        summary_dbs_dict[each_camera] = summary_db
        rule_dbs_dict[each_camera] = rule_db
        
    return cinfo_dbs_dict, rinfo_dbs_dict, snap_dbs_dict, obj_dbs_dict, class_dbs_dict, summary_dbs_dict, rule_dbs_dict

# .....................................................................................................................

def replay_generator(camera_select, snap_db_ref):
    
    first_epoch, last_epoch = snap_db_ref.get_bounding_epoch_ms()
    epoch_list = snap_db_ref.get_all_snapshot_times_by_time_range(first_epoch, last_epoch)
    
    inf_epoch_list = cycle(epoch_list)
    for each_snap_epoch in inf_epoch_list:
        
        # Convert to data that the browser can render
        snap_image, _ = snap_db_ref.load_snapshot_image(each_snap_epoch)
        image_bytes = image_to_jpg_bytearray(snap_image)
        full_byte_str = b"".join((b"--frame\r\n",
                                  b"Content-Type: image/jpeg\r\n\r\n", 
                                  image_bytes,
                                  b"\r\n"))
        
        yield full_byte_str
        sleep(0.25)

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Parse input args

enable_debug_mode = False

ap_result = parse_server_args()
arg_camera_select = ap_result.get("camera", None)
arg_user_select = ap_result.get("user", None)

no_camera_select = (arg_camera_select is None)


# ---------------------------------------------------------------------------------------------------------------------
#%% Get camera names for loading

# Create selector so we can access existing report data
selector = Resource_Selector()
project_root_path, cameras_folder_path = selector.get_project_pathing()
camera_name_list = list(selector.get_cameras_tree().keys())

# If a camera arg is provided, load only that camera (if it exists)
if not no_camera_select:
    camera_in_list = (arg_camera_select in camera_name_list)
    if not camera_in_list:
        err_msgs = ["Selected camera not found!".format(arg_camera_select),
                    "",
                    "Camera name ({}) must be in list:".format(arg_camera_select), 
                    *["  {}".format(each_name) for each_name in camera_name_list]]
        raise NameError("\n".join(err_msgs))
        raise NameError("Selected camera not found! ({})".format(arg_camera_select))
    camera_name_list = [arg_camera_select]

# Set other script input selections
user_select = arg_user_select


# ---------------------------------------------------------------------------------------------------------------------
#%% Catalog existing snapshot data

cinfo_dbs_dict, rinfo_dbs_dict, snap_dbs_dict, obj_dbs_dict, class_dbs_dict, summary_dbs_dict, rule_dbs_dict = \
initialize_databases(selector, cameras_folder_path, camera_name_list, user_select)

# Update camera name list to account for any missing datasets
camera_name_list = list(cinfo_dbs_dict.keys())
if len(camera_name_list) == 0:
    raise RuntimeError("No valid camera data!")

# ---------------------------------------------------------------------------------------------------------------------
#%% Create server routes

# Create server so we can start adding routes
server = Flask(__name__)
CORS(server)

# .....................................................................................................................

@server.route("/")
def home_message():
    
    html_strs = ["<title>Offline DB Server</title>", 
                 "<h1>Offline file database is running: <a href='/help'>Route listing</a></h1>"]
    
    # List every camera + the number of snapshots + number of objects total
    for each_camera in camera_name_list:
        
        # Get example data to display, for each camera
        first_epoch, _ = snap_dbs_dict[each_camera].get_bounding_epoch_ms()
        snap_count = snap_dbs_dict[each_camera].get_total_snapshot_count()
        obj_count = obj_dbs_dict[each_camera].get_total_object_count()
        
        # Get image & video links
        camera_link = "'/{}/snapshots/replay'".format(each_camera)
        first_snap_url = "'/{}/snapshots/get-image/by-epoch-ms/{}'".format(each_camera, first_epoch)
        
        # Build html
        camera_strs = ["<div style='padding: 15px'>",
                       "<p><b>{}:</b>  |  {} snapshots, {} objects</p>".format(each_camera, snap_count, obj_count),
                       "<a href={}><img src={}></a>".format(camera_link, first_snap_url),
                       "</div>"]
        
        html_strs.append("".join(camera_strs))
    
    return "\n".join(html_strs)

# .....................................................................................................................

@server.route("/help")
def server_help():
    
    # Initialize output html listing
    html_strs = ["<title>Offline DB Help</title>", "<h1>Route List:</h1>"]
    
    # Get valid methods to print
    valid_methods = ("GET", "POST")
    check_methods = lambda method: method in valid_methods
    
    url_list = []
    html_entry_list = []
    for each_route in server.url_map.iter_rules():
        
        # Ignore the static path
        if "static" in each_route.rule:
            continue
        
        # Get route urls (for sorting)
        each_url = each_route.rule
        url_list.append(each_url)
        
        # Clean up url and get GET/POST listing
        cleaned_url = each_url.replace("<", " (").replace(">", ") ")
        method_str = ", ".join(filter(check_methods, each_route.methods))
        
        html_entry = "<p><b>[{}]</b>&nbsp;&nbsp;&nbsp;{}</p>".format(method_str, cleaned_url)
        html_entry_list.append(html_entry)
    
    # Alphabetically sort url listings (so they group nicely) then add to html
    _, sorted_html_entries = zip(*sorted(zip(url_list, html_entry_list)))
    html_strs += sorted_html_entries
    
    # Add some additional info to html
    local_dt = get_local_datetime()
    example_dt_str = datetime_to_isoformat_string(local_dt)
    example_ems = datetime_to_epoch_ms(local_dt)
    html_strs += ["<br>",
                  "<p><b>Note:</b> If not specified, 'time' values can be provided in string or integer format</p>",
                  "<p>&nbsp;&nbsp;--> String format times must follow isoformat</p>",
                  "<p>&nbsp;&nbsp;--> Integer format times must be epoch millisecond values</p>",
                  "<p>Example times:</p>",
                  "<p>&nbsp;&nbsp; {} (string format)</p>".format(example_dt_str),
                  "<p>&nbsp;&nbsp; {} (integer format)</p>".format(example_ems)]
    
    return "\n".join(html_strs)

# .....................................................................................................................

@server.route("/get-camera-info")
def get_camera_info():
    
    camera_info_dict = {}
    for each_camera, each_cinfo_db in cinfo_dbs_dict.items():
        mongo_id, ip_address, time_zone, start_datetime_isoformat, start_epoch_ms, \
        video_select, video_fps, video_width, video_height, snap_width, snap_height = each_cinfo_db.get_camera_info()
        camera_info_dict[each_camera] = {"_id": mongo_id,
                                         "ip_address": ip_address,
                                         "time_zone": time_zone,
                                         "start_datetime_isoformat": start_datetime_isoformat,
                                         "start_epoch_ms": start_epoch_ms,
                                         "video_select": video_select,
                                         "video_fps": video_fps,
                                         "video_width": video_width,
                                         "video_height": video_height,
                                         "snapshot_width": snap_width,
                                         "snapshot_height": snap_height}
    
    return jsonify(camera_info_dict)

# .....................................................................................................................

@server.route("/get-rule-info")
def get_rule_info():
    
    all_rule_info_dict = {}
    for each_camera, each_rinfo_db in rinfo_dbs_dict.items():
        all_rule_info_dict[each_camera] = each_rinfo_db.get_rule_info()
    
    return jsonify(all_rule_info_dict)

# .....................................................................................................................

@server.route("/<string:camera_select>/snapshots/replay")
def snapshots_replay(camera_select):
    
    snapshot_replay = replay_generator(camera_select, snap_dbs_dict[camera_select])
    
    return Response(snapshot_replay, mimetype = "multipart/x-mixed-replace; boundary=frame")

# .....................................................................................................................

@server.route("/<string:camera_select>/snapshots/get-bounding-times")
def snapshots_get_bounding_times(camera_select):
    
    snap_db = snap_dbs_dict[camera_select]
    min_epoch_ms, max_epoch_ms = snap_db.get_bounding_epoch_ms()
    min_dt, max_dt = snap_db.get_bounding_datetimes()
    bounding_times_dict = {"min_epoch_ms": min_epoch_ms,
                           "max_epoch_ms": max_epoch_ms,
                           "min_datetime_isoformat": datetime_to_isoformat_string(min_dt),
                           "max_datetime_isoformat": datetime_to_isoformat_string(max_dt)}
    
    return jsonify(bounding_times_dict)

# .....................................................................................................................

@server.route("/<string:camera_select>/snapshots/get-epoch-ms-list/by-time-range/<start_time>/<end_time>")
def snapshots_get_epochs_by_time_range(camera_select, start_time, end_time):
    
    # Convert epoch inputs to integers, if needed
    start_time = int(start_time) if start_time.isnumeric() else start_time
    end_time = int(end_time) if end_time.isnumeric() else end_time
    
    snap_db = snap_dbs_dict[camera_select]
    snapshot_epoch_ms_list = snap_db.get_all_snapshot_times_by_time_range(start_time, end_time)
    
    return jsonify(snapshot_epoch_ms_list)

# .....................................................................................................................

@server.route("/<string:camera_select>/snapshots/get-metadata/by-epoch-ms/<int:epoch_ms>")
def snapshots_get_metadata(camera_select, epoch_ms):
    
    try:
        snap_db = snap_dbs_dict[camera_select]
        snapshot_metadata_dict = snap_db.load_snapshot_metadata(epoch_ms)
    except Exception as err:
        return ("Error: {}".format(err), 404)
    
    return jsonify(snapshot_metadata_dict)

# .....................................................................................................................

@server.route("/<string:camera_select>/snapshots/get-image/by-epoch-ms/<int:epoch_ms>")
def snapshots_get_image(camera_select, epoch_ms):
    
    snap_db = snap_dbs_dict[camera_select]
    snapshot_image, frame_index = snap_db.load_snapshot_image(epoch_ms)
    image_bytes = image_to_jpg_bytearray(snapshot_image)
    
    return Response(image_bytes, mimetype = "image/jpeg")

# .....................................................................................................................
    
@server.route("/<string:camera_select>/objects/get-ids-list/by-time-target/<target_time>")
def objects_get_ids_by_target_time(camera_select, target_time):
    
    # Convert epoch input to integers, if needed
    target_time = int(target_time) if target_time.isnumeric() else target_time
    
    obj_db = obj_dbs_dict[camera_select]
    obj_ids_list = obj_db.get_ids_at_target_time(target_time)
    
    return jsonify(obj_ids_list)

# .....................................................................................................................
    
@server.route("/<string:camera_select>/objects/get-ids-list/by-time-range/<start_time>/<end_time>")
def objects_get_ids_by_time_range(camera_select, start_time, end_time):
    
    # Convert epoch inputs to integers, if needed
    start_time = int(start_time) if start_time.isnumeric() else start_time
    end_time = int(end_time) if end_time.isnumeric() else end_time
    
    obj_db = obj_dbs_dict[camera_select]
    obj_ids_list = obj_db.get_object_ids_by_time_range(start_time, end_time)
    
    return jsonify(obj_ids_list)

# .....................................................................................................................
    
@server.route("/<string:camera_select>/objects/get-metadata/by-id/<int:object_full_id>")
def objects_get_metadata(camera_select, object_full_id):
    
    try:
        obj_db = obj_dbs_dict[camera_select]
        obj_metadata = obj_db.load_metadata_by_id(object_full_id)
    except Exception as err:
        return ("Error: {}".format(err), 404)
    
    return jsonify(obj_metadata)

# .....................................................................................................................
    
@server.route("/<string:camera_select>/objects/get-classification/by-id/<int:object_full_id>")
def objects_get_classification(camera_select, object_full_id):
    
    try:
        class_db = class_dbs_dict[camera_select]
        topclass_label, subclass_label, topclass_dict, subclass_dict, attributes_dict = \
        class_db.load_classification_data(object_full_id)
        output_dict = {"topclass_label": topclass_label,
                       "subclass_label": subclass_label,
                       "topclass_dict": topclass_dict,
                       "subclass_dict": subclass_dict,
                       "attributes_dict": attributes_dict}
    except Exception as err:
        return ("Error: {}".format(err), 404)
    
    return jsonify(output_dict)

# .....................................................................................................................

@server.route("/<string:camera_select>/objects/get-summary/by-id/<int:object_full_id>")
def objects_get_summary_results(camera_select, object_full_id):
    
    try:
        summary_db = summary_dbs_dict[camera_select]
        summary_data_dict = summary_db.load_summary_data(object_full_id)
    except Exception as err:
        return ("Error: {}".format(err), 404)
    
    return jsonify(summary_data_dict)

# .....................................................................................................................

@server.route("/<string:camera_select>/objects/get-rule-results/<string:rule_name>/by-id/<int:object_full_id>")
def objects_get_rule_results(camera_select, rule_name, object_full_id):
    
    try:
        rule_db = rule_dbs_dict[camera_select]
        rule_type, num_violations, rule_results_dict, rule_results_list = \
        rule_db.load_rule_data(rule_name, object_full_id)        
        output_dict = {"rule_type": rule_type,
                       "num_violations": num_violations,
                       "rule_results_dict": rule_results_dict,
                       "rule_results_list": rule_results_list}
        
    except Exception as err:
        return ("Error: {}".format(err), 404)
    
    return jsonify(output_dict)

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% *** Launch server ***

if __name__ == "__main__":
    
    # Crash spyder IDE if it's being used, since it doesn't play nicely with flask!
    ide_catcher("Can't run flask from IDE! Try using a terminal...")
    
    # Set server access parameters
    server_protocol = "http"
    server_host = "localhost"
    server_port = 6123
    server_url = "{}://{}:{}".format(server_protocol, server_host, server_port)
    
    # Launch server
    print("")
    server.run(server_host, port = server_port, debug=False)

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap

