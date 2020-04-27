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

from waitress import serve as wsgi_serve

from flask import Flask, jsonify, Response
from flask import request as flask_request

from local.lib.ui_utils.cli_selections import Resource_Selector

from local.offline_database.file_database import launch_file_db, close_dbs_if_missing_data
from local.offline_database.object_reconstruction import Smoothed_Object_Reconstruction as Obj_Recon

from local.lib.file_access_utils.classifier import load_reserved_labels_lut, load_topclass_labels_lut

from local.lib.file_access_utils.supervised_labels import save_single_supervised_label, load_single_supervised_label
from local.lib.file_access_utils.supervised_labels import create_supervised_label_entry
from local.lib.file_access_utils.supervised_labels import get_svlabel_topclass_label

from local.eolib.utils.quitters import ide_catcher, ide_quit

# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes


# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

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
    closest_snaps_dict = snap_db.get_closest_snapshot_epoch(middle_obj_epoch)
    closest_middle_snap_ems = closest_snaps_dict["closest_epoch_ms"]
    snap_image, snap_frame_idx = snap_db.load_snapshot_image(closest_middle_snap_ems)
    
    # Draw reconstructed object onto the snapshot
    snap_image = obj_ref.draw_outline(snap_image, snap_frame_idx, closest_middle_snap_ems)
    snap_image = obj_ref.draw_trail(snap_image, snap_frame_idx, closest_middle_snap_ems)
    
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

# Bundle pathing args for convenience
pathing_args = (cameras_folder_path, camera_select, user_select)


# ---------------------------------------------------------------------------------------------------------------------
#%% Catalog existing data

cinfo_db, snap_db, obj_db, class_db, summary_db = \
launch_file_db(cameras_folder_path, camera_select, user_select,
               check_same_thread = False,
               launch_snapshot_db = True,
               launch_object_db = True,
               launch_classification_db = False,
               launch_summary_db = False)

# Catch missing data
close_dbs_if_missing_data(snap_db, error_message_if_missing = "No snapshot data in the database!")
close_dbs_if_missing_data(obj_db, error_message_if_missing = "No object trail data in the database!")

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
reserved_colors_dict = load_reserved_labels_lut(cameras_folder_path, camera_select)
topclass_colors_dict = load_topclass_labels_lut(cameras_folder_path, camera_select)

# Get labels in sorted order so we get consistent a display
sorted_reserved_labels = sorted(list(reserved_colors_dict.keys()))
sorted_topclass_labels = sorted(list(topclass_colors_dict.keys()))


# ---------------------------------------------------------------------------------------------------------------------
#%% Define routes

# Create server so we can start adding routes
wsgi_app = Flask(__name__,
                 static_url_path = '', 
                 static_folder = "perobj_resources/static",
                 template_folder = "perobj_resources/templates")

# .....................................................................................................................

@wsgi_app.route("/")
def home_route():
    return wsgi_app.send_static_file("labeller/labeller.html")

# .....................................................................................................................

@wsgi_app.route("/setuprequest")
def setup_data_route():
    
    '''
    Route which provides all necessary setup data to display coarse labelling UI 
    (could be provided through template, but trying something different...)
    '''
    
    # Bundle all the data the UI needs to create/display a UI for (coarse) labelling
    setup_request_data = {"camera_select": camera_select,
                          "user_select": user_select,
                          "object_id_list": object_id_list,
                          "reserved_labels_list": sorted_reserved_labels,
                          "topclass_labels_list": sorted_topclass_labels}
    
    return jsonify(setup_request_data)

# .....................................................................................................................

@wsgi_app.route("/labelrequest/<int:object_id>")
def object_label_request(object_id):
    
    ''' Route which returns the current class label for a given object '''
    
    # Some debugging feedback
    print("", "LABEL REQUEST:", object_id, sep="\n")
    
    # Get the current label associated with the given object id
    object_label = "error"
    try:
        single_object_entry = load_single_supervised_label(*pathing_args, object_id, return_nested = True)
        object_label = get_svlabel_topclass_label(single_object_entry, object_id)
    except KeyError:
        print("no object {}".format(object_id))
    
    # Bundle data for return
    return_request_dict = {"full_id": object_id,
                           "object_label": object_label}
    
    # More debugging feedback
    print("--> returning:", return_request_dict)
    print("")
    
    return jsonify(return_request_dict)

# .....................................................................................................................

@wsgi_app.route("/imagerequest/<int:object_id>")
def object_image_request(object_id):
    
    ''' Route which returns a representative image of the object (taken from the 'middle' of it's time range) '''
    
    # Some debugging feedback
    print("", "IMAGE REQUEST:", object_id, "", sep="\n")
    
    # Load appropriate snapshot image and annotate for display, then convert to base64 for web use
    scaled_image = get_middle_image(object_id)
    image_bytes = image_to_jpg_bytearray(scaled_image)
    
    return Response(image_bytes, mimetype = "image/jpeg")

# .....................................................................................................................

@wsgi_app.route("/animationrequest/<int:object_id>")
def object_animation_request(object_id):
    
    ''' Route which returns a repeatingly updating image of an object, throughout it's lifetime '''
    
    # Some debugging feedback
    print("", "ANIMATION REQUEST:", object_id, "", sep="\n")
    
    # Create a generator that returns an infinite list of images to act as an animation
    obj_animation = get_animation(object_id)
    
    return Response(obj_animation, mimetype = "multipart/x-mixed-replace; boundary=frame")
    
# .....................................................................................................................

@wsgi_app.route("/labelupdate", methods=["POST"])
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
    new_class_label = update_json_data["new_label_string"]
    
    # Create save data & save it!
    new_label_data = create_supervised_label_entry(object_id, new_class_label)
    save_single_supervised_label(*pathing_args, new_label_data)
    
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
    
    # Unleash the wsgi server
    print("")
    enable_debug_mode = False
    if enable_debug_mode:
        wsgi_app.run(server_host, port = server_port, debug = True)
    else:
        wsgi_serve(wsgi_app, host = server_host, port = server_port, url_scheme = server_protocol)
    
    # Feedback in case we get here
    print("Done!")
    

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap
    
# TODOs:
# - Add script arg to control debug mode
# - Add script arg to control animation playback speed?
#   - Or should this be controllable on the web page itself???
# - update page to use radio buttons for label selection (should simplify things?)
