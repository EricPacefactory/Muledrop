#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Aug 23 15:22:40 2019

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
import base64

from itertools import cycle
from time import sleep

from flask import Flask, jsonify, Response
from flask import request as flask_request

from local.lib.ui_utils.cli_selections import Resource_Selector

from local.offline_database.file_database import launch_file_db, close_dbs_if_missing_data
from local.offline_database.object_reconstruction import Smoothed_Object_Reconstruction as Obj_Recon

from local.lib.file_access_utils.classifier import build_supervised_labels_folder_path
from local.lib.file_access_utils.classifier import load_label_lut_tuple, load_supervised_labels, save_supervised_label

from eolib.utils.quitters import ide_catcher, ide_quit

# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes


# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

# .....................................................................................................................

def create_supervised_label_data(class_label):
    
    ''' Helper function used to ensure consistent formatting of supervised label data '''
    
    return {"class_label": class_label}

# .....................................................................................................................
    
def image_to_jpg_b64_str(image):
    
    # Convert to b64 for web page display
    _, jpg_frame = cv2.imencode(".jpg", image)
    jpg_frame_b64 = base64.b64encode(jpg_frame).decode()
    jpg_frame_b64_str = "".join(["data:image/jpg;base64,", jpg_frame_b64])
    
    return jpg_frame_b64_str

# .....................................................................................................................

def image_to_jpg_bytearray(image):
    
    # Convert raw data to a jpg, then to a byte array which can be sent to a browser for display
    _, encoded_image = cv2.imencode(".jpg", image)
    
    return bytearray(encoded_image)

# .....................................................................................................................

def get_middle_image(object_full_id):
    
    # Get object metadata for reconstruction
    obj_md = obj_db.load_metadata_by_id(object_full_id)
    
    # Reconstruct object from metadata, so we can draw it's data
    snap_wh = cinfo_db.get_snap_frame_wh()
    obj_ref = Obj_Recon(obj_md, snap_wh, earliest_datetime, latest_datetime)
    
    # Find 'middle' snapshot for drawing
    first_epoch_ms, last_epoch_ms = obj_ref.get_bounding_epoch_ms()
    middle_obj_epoch = int((last_epoch_ms + first_epoch_ms) / 2)
    
    # Get middle snapshot image and frame index, so we can draw the object on it
    _, closest_middle_snap_epoch, _ = snap_db.get_closest_snapshot_epoch(middle_obj_epoch)
    snap_image, snap_frame_idx = snap_db.load_snapshot_image(closest_middle_snap_epoch)
    
    # Draw reconstructed object onto the snapshot
    snap_image = obj_ref.draw_outline(snap_image, snap_frame_idx, closest_middle_snap_epoch)
    snap_image = obj_ref.draw_trail(snap_image, snap_frame_idx, closest_middle_snap_epoch)
    
    return snap_image

# .....................................................................................................................

def get_animation(object_full_id, start_padded_time_ms = 3000, end_padded_time_ms = 5000):
    
    # Get object metadata for timing/reconstruction
    obj_md = obj_db.load_metadata_by_id(object_full_id)
    
    # Reconstruct object from metadata, so we can draw it's data
    snap_wh = cinfo_db.get_snap_frame_wh()
    obj_ref = Obj_Recon(obj_md, snap_wh, earliest_datetime, latest_datetime)
    first_epoch_ms, last_epoch_ms = obj_ref.get_bounding_epoch_ms()
    
    # Load snapshot times around object start/end times, with some padding
    padded_start_epoch_ms = int(first_epoch_ms - start_padded_time_ms)
    padded_end_epoch_ms = int(last_epoch_ms + end_padded_time_ms)
    snap_epoch_ms_list = snap_db.get_all_snapshot_times_by_time_range(padded_start_epoch_ms, padded_end_epoch_ms)
    
    # Infinitely loop over the snapshot times to create looping animation
    snap_times_inf_list = cycle(snap_epoch_ms_list)
    for each_snap_epoch_ms in snap_times_inf_list:
        
        # Get snapshot image data and draw outline/trail for the given object
        snap_image, snap_frame_idx = snap_db.load_snapshot_image(each_snap_epoch_ms)
        obj_ref.draw_trail(snap_image, snap_frame_idx, each_snap_epoch_ms)
        obj_ref.draw_outline(snap_image, snap_frame_idx, each_snap_epoch_ms)
        
        # Convert to data that the browser can render
        image_bytes = image_to_jpg_bytearray(snap_image)
        full_byte_str = b"".join((b"--frame\r\n",
                                  b"Content-Type: image/jpeg\r\n\r\n", 
                                  image_bytes,
                                  b"\r\n"))
        
        # Return the next frame in the animation sequence
        yield full_byte_str
        
        # Delay so we don't have a flood of images
        sleep(0.25)
    
    return 

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% User selections (cli)

enable_debug_mode = False

# Create selector so we can access existing report data
selector = Resource_Selector()
project_root_path, cameras_folder_path = selector.get_project_pathing()

# Select the camera/user to show data for (needs to have saved report data already!)
camera_select, camera_path = selector.camera(debug_mode=enable_debug_mode)
user_select, _ = selector.user(camera_select, debug_mode=enable_debug_mode)


# ---------------------------------------------------------------------------------------------------------------------
#%% Catalog existing data

cinfo_db, rinfo_db, snap_db, obj_db, _, _, _ = \
launch_file_db(cameras_folder_path, camera_select, user_select,
               check_same_thread = False,
               launch_snapshot_db = True,
               launch_object_db = True,
               launch_classification_db = False,
               launch_summary_db = False,
               launch_rule_db = False)

# Catch missing data
rinfo_db.close()
close_dbs_if_missing_data(snap_db, obj_db)

# Get the maximum range of the data (based on the snapshots, because that's the most we could show)
earliest_datetime, latest_datetime = snap_db.get_bounding_datetimes()
snap_wh = cinfo_db.get_snap_frame_wh()

# Get object metadata from the server
object_id_list = obj_db.get_object_ids_by_time_range(earliest_datetime, latest_datetime)

# Bail if no object data is present so we don't get silly errors
no_object_data = (len(object_id_list) == 0)
if no_object_data:
    print("", "No object data to load!", "  Quitting...", "", sep = "\n")
    ide_quit()


# ---------------------------------------------------------------------------------------------------------------------
#%% Get existing labelling results (if any)

# First get all the available labels
label_lut_dict, label_to_index_dict = load_label_lut_tuple(cameras_folder_path, camera_select)

# Generate an ordered set of labels for convenience
_, ordered_labels_list = zip(*sorted([(each_idx, each_label) for each_label, each_idx in label_to_index_dict.items()]))

# Get pathing to the supervised label data
supervised_labels_folder_path = build_supervised_labels_folder_path(cameras_folder_path, 
                                                                    camera_select,
                                                                    user_select,
                                                                    earliest_datetime)

# Load existing labelling data
default_label_if_missing = create_supervised_label_data(class_label = "unclassified")
supervised_class_labels_dict = load_supervised_labels(supervised_labels_folder_path,
                                                      object_id_list, 
                                                      default_if_missing = default_label_if_missing)


# ---------------------------------------------------------------------------------------------------------------------
#%% Define routes

# Create server so we can start adding routes
server = Flask(__name__,
               static_url_path = '', 
               static_folder = "web/static",
               template_folder = "web/templates")

# .....................................................................................................................

@server.route("/")
def home_route():
    return server.send_static_file("labeller/labeller.html")

# .....................................................................................................................

@server.route("/setuprequest")
def setup_data_route():
    
    '''
    Route which provides all necessary setup data to display coarse labelling UI 
    (could be provided through template, but trying something different...)
    '''
    
    # Bundle all the data the UI needs to create/display a UI for (coarse) labelling
    setup_request_data = {"camera_select": camera_select,
                          "user_select": user_select,
                          "object_id_list": object_id_list,
                          "ordered_labels_list": ordered_labels_list}
    
    return jsonify(setup_request_data)

# .....................................................................................................................

@server.route("/labelrequest/<int:object_id>")
def object_label_request(object_id):
    
    ''' Route which returns the current class label for a given object '''
    
    # Some debugging feedback
    print("", "LABEL REQUEST:", object_id, sep="\n")
    
    # Get the current label associate with the given object id
    try:
        label_request_data = supervised_class_labels_dict[object_id]
    except KeyError:
        return "no object {}".format(object_id), 500
    
    # More debugging feedback
    print("--> returning:", label_request_data)
    print("")
    
    return jsonify(label_request_data)

# .....................................................................................................................

@server.route("/imagerequest/<int:object_id>")
def object_image_request(object_id):
    
    ''' Route which returns a representative image of the object (taken from the 'middle' of it's time range) '''
    
    # Some debugging feedback
    print("", "IMAGE REQUEST:", object_id, "", sep="\n")
    
    # Load appropriate snapshot image and annotate for display, then convert to base64 for web use
    scaled_image = get_middle_image(object_id)
    image_bytes = image_to_jpg_bytearray(scaled_image)
    
    return Response(image_bytes, mimetype = "image/jpeg")

# .....................................................................................................................

@server.route("/animationrequest/<int:object_id>")
def object_animation_request(object_id):
    
    ''' Route which returns a repeatingly updating image of an object, throughout it's lifetime '''
    
    # Some debugging feedback
    print("", "ANIMATION REQUEST:", object_id, "", sep="\n")
    
    # Create a generator that returns an infinite list of images to act as an animation
    obj_animation = get_animation(object_id)
    
    return Response(obj_animation, mimetype = "multipart/x-mixed-replace; boundary=frame")
    
# .....................................................................................................................

@server.route("/labelupdate", methods=["POST"])
def object_label_update():
    
    ''' 
    Route used to update an object label, based on web UI 
    Expecting JSON data in the format:
        update_json_data = {"object_id": ...,
                            "new_class_label_string": ...}
    '''
    
    # Get data needed to update object labels
    update_json_data = flask_request.get_json()
    
    # Pull out post data
    object_id = update_json_data["object_id"]
    new_class_label = update_json_data["new_class_label_string"]
    
    # Create save data & save it!
    new_label_data = create_supervised_label_data(new_class_label)
    save_supervised_label(supervised_labels_folder_path, object_id, new_label_data)
    
    # Update the internal label records, so future label requests are consistent with updates!
    new_labels_dict = load_supervised_labels(supervised_labels_folder_path, [object_id])
    supervised_class_labels_dict.update(new_labels_dict)
    
    # Some debugging feedback
    print("", 
          "LABELUPDATE POST - {}: {}]".format(object_id, new_label_data), 
          "", sep="\n")
    
    return ("{}", 201) # No content response

# .....................................................................................................................
# .....................................................................................................................    

# ---------------------------------------------------------------------------------------------------------------------
#%% *** Launch server ***

if __name__ == "__main__":
    
    # Crash spyder IDE if it's being used, since it doesn't play nicely with flask!
    ide_catcher("Can't run flask from IDE! Use terminal...")
    
    # Set server access parameters
    server_protocol = "http"
    server_host = "localhost"
    server_port = 5000
    server_url = "{}://{}:{}".format(server_protocol, server_host, server_port)
    
    # Unleash the server
    print("")
    server.run(server_host, port = server_port, debug=False)

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap
    

