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
import numpy as np
import datetime as dt

from time import sleep
from shutil import copytree
from itertools import cycle

from flask import Flask, render_template, jsonify, Response
from flask import request as flask_request

from local.lib.ui_utils.cli_selections import Resource_Selector
from local.lib.file_access_utils.reporting import build_base_report_path, build_image_report_path
from local.lib.file_access_utils.classifier import build_dataset_path, build_model_path
from local.lib.file_access_utils.classifier import build_supervised_labels_folder_path
from local.lib.file_access_utils.classifier import load_label_lut_tuple

from eolib.utils.files import get_file_list, get_folder_list, get_total_folder_size
from eolib.utils.cli_tools import cli_confirm, cli_select_from_list, clear_terminal
from eolib.utils.read_write import load_json, update_json
from eolib.utils.quitters import ide_catcher

# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes


# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

# .....................................................................................................................

def check_image_data_exists(cameras_folder, camera_select):
    
    ''' 
    Function for checking which (if any) user report folders contain image data
    Returns:
        users_with_data -> Dictionary. Keys represent valid users with report data, 
                           values hold pathing to users report data folder
    '''
    
    # Initialize output
    users_with_data = {}
    
    # Get pathing to reporting folder
    base_reporting_folder_path = build_base_report_path(cameras_folder, camera_select)
    user_report_folders = get_folder_list(base_reporting_folder_path, return_full_path = False)
    
    # No user folders means no image data!
    if len(user_report_folders) == 0:
        return users_with_data
     
    # Check which users have snapshot data (needed for classification)
    for each_user in user_report_folders:
        
        # Check how many snapshots are saved
        snapshot_image_folder_path = build_image_report_path(cameras_folder, camera_select, each_user, "snapshots")
        number_snapshots = len(os.listdir(snapshot_image_folder_path))
        
        # If there are any snapshots, we'll assume this is a valid dataset for classification
        # (Ideally, should check that there are object metadata files as well...)
        if number_snapshots > 0:
            user_report_data_path = os.path.join(base_reporting_folder_path, each_user)
            users_with_data.update({each_user: user_report_data_path})
            
    return users_with_data

# .....................................................................................................................

def prompt_to_add_dataset(cameras_folder, camera_select):
    
    # Check if datasets already exist (in which case we don't need to add anything)
    classification_dataset_folder_path = build_dataset_path(cameras_folder_path, camera_select)
    dataset_folder_paths_list = get_folder_list(classification_dataset_folder_path, return_full_path = False)
    dataset_folders_exist = (len(dataset_folder_paths_list) > 0)
    if dataset_folders_exist:
        return dataset_folder_paths_list
    
    # If we get here, no datasets exist, so we'll have to prompt the user to add one
    clear_terminal(post_delay_sec=0.25)
    
    # Some feedback to let the user known that datasets weren't found
    classification_dataset_folder_path = build_dataset_path(cameras_folder_path, camera_select)
    search_rel_path = os.path.relpath(classification_dataset_folder_path, cameras_folder)
    print("", 
          "!" * 56,
          "No classification datasets were found!",
          "  Searched: {}".format(search_rel_path),
          "",
          "Please select report data to use for classification...",
          "!" * 56,
          sep = "\n")
    sleep(0.5)
    
    # Figure out which users have valid reporting data which could be copied over to do classification
    users_with_data = check_image_data_exists(cameras_folder, camera_select)
    
    # Bail if we can't find any valid datasets
    if len(users_with_data) < 1:
        raise FileNotFoundError("Could not find any user report data to use for classification!")
    
    # Prompt user to add datasets for classification
    valid_user_list = sorted(list(users_with_data.keys()))    
    select_idx, user_select = cli_select_from_list(valid_user_list, 
                                                   prompt_heading = "Add report data for classification:")
    
    # Generate dataset folder name to store within classification folder
    time_now = dt.datetime.now()
    time_now_str = time_now.strftime("%Y%m%d")
    dataset_folder_name = "{}-({})".format(time_now_str, user_select)
    
    # Copy data over to classification folder, with user confirmation
    source_copy_folder = users_with_data[user_select]
    copy_file_count, _, copy_file_size, _ = get_total_folder_size(source_copy_folder, "M")
    print("", 
          "Data must be copied for classification",
          "     Camera: {}".format(camera_select),
          "       User: {}".format(user_select),
          "  Copied as: {}".format(dataset_folder_name),
          "",
          "({} files totaling {:.1f} MB)".format(copy_file_count, copy_file_size), 
          sep = "\n")
    
    # Ask for copy confirmation
    default_response = (copy_file_size < 100)
    user_confirm = cli_confirm("Ok to copy?", default_response)
    
    # Quit if the user doesn't want to add a dataset
    if not user_confirm:
        raise FileNotFoundError("No datasets to perform classification!")
        
    # Get pathing to copy from and where to copy to
    destination_folder = build_dataset_path(cameras_folder, camera_select, dataset_folder_name)
    
    # Copy the directory structure, with some feedback
    print("")
    print("Copying... ", end="")
    copytree(source_copy_folder, destination_folder)
    print("done!")
    
    return get_folder_list(classification_dataset_folder_path, return_full_path = False)

# .....................................................................................................................

def get_task_object_metadata_paths(dataset_folder_path):
    
    '''
    Function which checks the dataset folder for object metadata folders,
    of which there may be several, due to multiple running tasks
    ("objects-(main_task)", "objects-(motion)", "objects-(idle_objects)" etc.)
    
    Returns a dictionary where each key is a task name,
    and each value is the path to the corresponding metadata folder for that task
    '''
    
    # Get full pathing to the metadata folder and contents, which includes object metadata files (among other things)
    metadata_folder_path = os.path.join(dataset_folder_path, "metadata")
    metadata_folder_contents = get_folder_list(metadata_folder_path, return_full_path = False)
    
    # Pull out only the object metadata folder paths (and corresponding task names)
    task_path_dict = {}
    for each_folder in metadata_folder_contents:
        
        # Ignore non-object folders
        if "objects" not in each_folder:
            continue
        
        # Build the pathing to each object metadata folder and grab the task name from the folder name
        # (example name - "objects-(main_task)")
        new_object_md_folder_path = os.path.join(metadata_folder_path, each_folder)
        new_task_name = each_folder.replace("objects-", "")[1:-1]
        
        # Bundle task name and pathing to object metadata folder into a dictionary
        new_metadata_entry = {new_task_name: new_object_md_folder_path}
        task_path_dict.update(new_metadata_entry)
    
    return task_path_dict

# .....................................................................................................................

def get_object_id_metadata_paths(dataset_folder_path):
    
    '''
    Function which checks dataset folder for object metadata files
    Returns a dictionary where each key is a task name and each value is an id-path lookup
    
    The id-path lookup is itself a dictionary, where each key represents an object ID (as an integer),
    and each corresponding value represents the pathing to that object's metadata file
    '''

    # Get listing of all object id's, for all tasks
    task_objdata_path_dict = get_task_object_metadata_paths(dataset_folder_path)
    task_ids_path_luts = {}
    for each_task_name, each_folder_path in task_objdata_path_dict.items():
        
        # Get a list of all object id metadata files, as well as the
        obj_id_file_list = get_file_list(each_folder_path, return_full_path = False, sort_list = False)
        
        # Handle future error, where object data may be stored across indexed files
        object_id_index_check = any((int(each_file.split(".")[0].split("-")[1]) > 1 for each_file in obj_id_file_list))
        if object_id_index_check:
            raise ValueError("Object index > 1 found ({}). Feature not yet implemented!".format(each_folder_path))
        
        # Gather object metadata file paths and id numbers so we can form an id-path lookup dictionary
        object_id_path_list = (os.path.join(each_folder_path, each_file) for each_file in obj_id_file_list)
        object_id_number_list = [int(each_file.split("-")[0]) for each_file in obj_id_file_list]
        id_path_lut = {each_id: each_path for each_id, each_path in zip(object_id_number_list, object_id_path_list)}
        
        # Bundle id-path lookup for each task into a dictionary for output
        new_id_paths_entry = {each_task_name: id_path_lut}    
        task_ids_path_luts.update(new_id_paths_entry)
        
    return task_ids_path_luts    

# .....................................................................................................................

def load_snapshot_data(snapshot_image_folder_path, snapshot_metadata_file_path):
    
    snapshot_filename = os.path.basename(snapshot_metadata_file_path)
    snapshot_name_only = snapshot_filename.replace(".json", "").replace(".gz", "")
    
    snapshot_metadata = load_json(snapshot_metadata_file_path)
    snapshot_frame_index = snapshot_metadata["frame_index"]
    
    snapshot_image_path = os.path.join(snapshot_image_folder_path, "{}.jpg".format(snapshot_name_only))
    snapshot_image = cv2.imread(snapshot_image_path)
    
    return snapshot_frame_index, snapshot_image

# .....................................................................................................................

def get_snapshot_luts(snapshot_metadata_folder_path, snapshot_metadata_file_list):

    snap_count_luts = {}
    for each_snap_file in snapshot_metadata_file_list:
        
        # Get pathing to each snapshot metadata file, so we can load it
        snap_path = os.path.join(snapshot_metadata_folder_path, each_snap_file)
        snap_md = load_json(snap_path)
        
        # Grab handy-dandy metadata to build a database-like-dict
        snap_count = snap_md["count"]
        snap_frame_index = snap_md["frame_index"]
        snap_epoch_ms = snap_md["epoch_ms"]
    
        # Create a new entry, which we'll index by snapshot count
        new_lut_entry = {"path": snap_path,
                         "frame_index": snap_frame_index,
                         "epoch_ms": snap_epoch_ms}
        snap_count_luts.update({snap_count: new_lut_entry})
    
    return snap_count_luts

# .....................................................................................................................

def get_frame_scaling(frame):
    
    # Get frame scaling, used to convert normalized object data to pixel co-ordinates
    frame_height, frame_width = frame.shape[0:2]
    frame_scaling_array = np.float32((frame_width - 1, frame_height - 1))
    
    return frame_scaling_array

# .....................................................................................................................

def annotate_trail(frame, object_metadata, final_plot_index):
    
    # Don't bother trying to draw anything if there aren't any samples!
    num_samples = object_metadata["num_samples"]
    if num_samples <= final_plot_index:
        return
    
    # Get object metadata needed for trail drawing
    obj_x_center = object_metadata["tracking"]["x_center"]
    obj_y_center = object_metadata["tracking"]["y_center"]
    
    # Take only the data needed for plotting & convert to arrays for easier math
    obj_x_array = np.float32(obj_x_center[final_plot_index:])
    obj_y_array = np.float32(obj_y_center[final_plot_index:])
    
    # Convert trail data to pixel units and draw as an open polygon
    frame_scaling_array = get_frame_scaling(frame)
    trail_xy = np.int32(np.round(np.vstack((obj_x_array, obj_y_array)).T * frame_scaling_array))
    cv2.polylines(frame, 
                  pts = [trail_xy],
                  isClosed = False, 
                  color = (0, 255, 255),
                  thickness = 1,
                  lineType = cv2.LINE_AA)

# .....................................................................................................................

def annotate_hull(frame, object_metadata, final_plot_index):
    
    # Don't bother trying to draw anything if there aren't any samples!
    num_samples = object_metadata["num_samples"]
    if num_samples <= final_plot_index:
        return
    
    # Grab a single object outline for annotation
    hull = object_metadata["tracking"]["hull"][final_plot_index]
    
    # Convert outline to pixel units and draw it    
    frame_scaling_array = get_frame_scaling(frame)
    hull_array = np.int32(np.round(np.float32(hull) * frame_scaling_array))
    cv2.polylines(frame, 
                  pts = [hull_array], 
                  isClosed = True, 
                  color = (0, 255, 0),
                  thickness = 1,
                  lineType = cv2.LINE_AA)

# .....................................................................................................................

def downscale_large_images(image, max_width = 640, max_height = 360):
    
    # Resize the image if needed
    frame_height, frame_width, _ = image.shape
    width_rescale = (max_width / frame_width)
    height_rescale = (max_height / frame_height)
    rescale_factor = max(width_rescale, height_rescale)
    needs_rescale = (rescale_factor < 1.0)
    
    # Only downscale if the image is too large
    if needs_rescale:
        scaled_width = int(round(frame_width * rescale_factor))
        scaled_height = int(round(frame_height * rescale_factor))
        return cv2.resize(image, dsize = (scaled_width, scaled_height))
    
    return image

# .....................................................................................................................
    
def image_to_jpg_b64_str(image):
    
    # Convert to b64 for web page display
    _, jpg_frame = cv2.imencode(".jpg", image)
    jpg_frame_b64 = base64.b64encode(jpg_frame).decode()
    jpg_frame_b64_str = "".join(["data:image/jpg;base64,", jpg_frame_b64])
    
    return jpg_frame_b64_str

# .....................................................................................................................

def get_bounding_snap_counts(object_metadata):
    
    # Retrieve snapshot counts, which we'll use to find the 'mid' point snapshot count
    start_snapshot_count = max(1, object_metadata["snapshots"]["first"]["count"] - 1)
    end_snapshot_count = object_metadata["snapshots"]["last"]["count"]
    
    return start_snapshot_count, end_snapshot_count

# .....................................................................................................................

def get_example_annotated_image(task_select, object_id, relative_snapshot_index = 0.5):
    
    # Get pathing to object metadata using the lut, then load the json data
    obj_md_path = task_objids_path_luts[task_select][object_id]
    obj_md = load_json(obj_md_path)
    
    # Figure out the index of the target snapshot for the object 
    first_snap_count, last_snap_count = get_bounding_snap_counts(obj_md)
    target_snap_count = int((first_snap_count + last_snap_count + 1) * relative_snapshot_index)
    
    # Get pathing to the target snapshot and load it
    snap_path = snap_count_luts[target_snap_count]["path"]
    snap_frame_index, snap_image = load_snapshot_data(snapshot_image_folder_path, snap_path)
    scaled_snap_frame = downscale_large_images(snap_image)
    
    # Figure out data indexing
    obj_end_frame_index = obj_md["timing"]["last_frame_index"]
    final_plot_idx = max(0, obj_end_frame_index - snap_frame_index)
    
    # Draw annotated data onto the frame
    annotate_trail(scaled_snap_frame, obj_md, final_plot_idx)
    annotate_hull(scaled_snap_frame, obj_md, final_plot_idx)
    
    return scaled_snap_frame

# .....................................................................................................................

def image_to_jpg_bytearray(image):
    
    # Convert raw data to a jpg, then to a byte array which can be sent to a browser for display
    _, encoded_image = cv2.imencode(".jpg", image)
    
    return bytearray(encoded_image)

# .....................................................................................................................

def animation_generator(task_name, object_id):
    
    # Get pathing to object metadata using the lut, then load the json data
    obj_md_path = task_objids_path_luts[task_name][object_id]
    obj_md = load_json(obj_md_path)
    
    # Get start and end snapshots for this object, so we can figure out the frames for animation
    start_snap_count, end_snap_count = get_bounding_snap_counts(obj_md)
    
    # Get a minimum of 3 snaps
    min_count = min(snap_count_luts)
    max_count = max(snap_count_luts)
    num_snaps = 1 + end_snap_count - start_snap_count
    if num_snaps < 3:
        start_snap_count = max(min_count, start_snap_count - num_snaps)
        num_snaps = 1 + end_snap_count - start_snap_count
        if num_snaps < 3:
            end_snap_count = min(max_count, end_snap_count + num_snaps + 1)
    
    # Build all iterating resources
    snap_count_range = range(start_snap_count, end_snap_count + 1)
    snap_path_list = [snap_count_luts[each_count]["path"] for each_count in snap_count_range]
    snap_path_inf_list = cycle(snap_path_list)
    
    for each_snap_path in snap_path_inf_list:
        
        # Load and shrink (if needed) each snapshot
        snap_frame_index, snap_image = load_snapshot_data(snapshot_image_folder_path, each_snap_path)
        scaled_snap_frame = downscale_large_images(snap_image)
        
        # Figure out data indexing
        obj_end_frame_index = obj_md["timing"]["last_frame_index"]
        final_plot_idx = max(0, obj_end_frame_index - snap_frame_index)
        
        # Draw annotated data onto the frame
        annotate_trail(scaled_snap_frame, obj_md, final_plot_idx)
        annotate_hull(scaled_snap_frame, obj_md, final_plot_idx)
        
        # Convert to data that the browser can render
        image_bytes = image_to_jpg_bytearray(scaled_snap_frame)
        full_byte_str = b"".join((b"--frame\r\n",
                                  b"Content-Type: image/jpeg\r\n\r\n", 
                                  image_bytes,
                                  b"\r\n"))
        
        # Return the next frame in the animation sequence
        yield full_byte_str
        
        # Delay so we don't have a flood of images
        sleep(0.35)

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% User selections (cli)

enable_debug_mode = True

# Create selector to handle camera selection & project pathing
selector = Resource_Selector()
project_root_path, cameras_folder_path = selector.get_project_pathing()
camera_select, camera_path = selector.camera(debug_mode=enable_debug_mode)

# Check for existing classification data or add datasets if needed
dataset_folder_paths_list = prompt_to_add_dataset(cameras_folder_path, camera_select)
    
# Select dataset and build folder pathing to the selected dataset
select_idx, dataset_select = cli_select_from_list(dataset_folder_paths_list, prompt_heading="Select dataset", 
                                                  debug_mode = enable_debug_mode)
dataset_folder_path = build_dataset_path(cameras_folder_path, camera_select, dataset_select)


# ---------------------------------------------------------------------------------------------------------------------
#%% Get existing model data

# Get pathing to corresponding model folder, or create it if it doesn't already exist
model_folder = build_model_path(cameras_folder_path, camera_select, dataset_select)
os.makedirs(model_folder, exist_ok = True)

# Get pathing to the classification label record, or create it if it doesn't already exist
supervised_labels_folder_path = build_supervised_labels_folder_path(cameras_folder_path, camera_select, dataset_select)
os.makedirs(supervised_labels_folder_path, exist_ok = True)

# Load the label lookup table, so we know which labels can be assigned by the classifier
label_lut_dict, label_to_idx_lut = load_label_lut_tuple(cameras_folder_path, camera_select)

# ---------------------------------------------------------------------------------------------------------------------
#%% Get snapshot data

# Get pathing to classifier snapshot metadata and list of all snapshot metadata files
snapshot_image_folder_path = os.path.join(dataset_folder_path, "images", "snapshots")
snapshot_metadata_folder_path = os.path.join(dataset_folder_path, "metadata", "snapshots")
snapshot_metadata_file_list = get_file_list(snapshot_metadata_folder_path, return_full_path = False, sort_list = True)

# Bundle snapshot metadata paths into a dictionary, index with a key matching the snapshot count for each file
# (maybe not the most practical long-term, but convenient for this demo)
snap_count_luts = get_snapshot_luts(snapshot_metadata_folder_path, snapshot_metadata_file_list)

# ---------------------------------------------------------------------------------------------------------------------
#%% Get object data

# Make sure default ('unclassified') is a valid entry in the label LUT
unclassified_entry = "unclassified"
if unclassified_entry not in label_lut_dict.keys():
    raise NameError("Missing class label ({}) in class label lookup table!".format(unclassified_entry))

# Get listing of all object metadata
task_objids_path_luts = get_object_id_metadata_paths(dataset_folder_path)

# Create empty classification record for the given objects
supervised_class_labels_dict = {}
for each_task, each_obj_id_path_lut in task_objids_path_luts.items():
    empty_class_label_dict = {each_id: "unclassified" for each_id in each_obj_id_path_lut.keys()}
    supervised_class_labels_dict.update({each_task: empty_class_label_dict})

# Update/overwrite 'empty' classification labels with any existing data
for each_task, each_label_dict in supervised_class_labels_dict.items():
    
    # Load in any existing data to overwrite the default 'empty' labels
    new_label_file_path = os.path.join(supervised_labels_folder_path, each_task)
    existing_labels = load_json(new_label_file_path, convert_integer_keys = True, error_if_missing = False)
    if existing_labels is None:
        existing_labels = {}
    each_label_dict.update(existing_labels)
    
    # Overwrite the existing labels files, in case we've added any new objects that weren't in the original file
    update_json(new_label_file_path, each_label_dict, indent = 2, sort_keys = True, convert_integer_keys = True)
        

# ---------------------------------------------------------------------------------------------------------------------
#%% Define routes

# Create server so we can start adding routes
server = Flask(__name__)

# .....................................................................................................................

@server.route("/")
def overview_route():
    
    # Get the number of snapshots
    num_snapshots = len(os.listdir(snapshot_image_folder_path))
    
    # Get the task names
    task_name_list = sorted(list(task_objids_path_luts.keys()))
    
    # Get the number of objects (total across all tasks)
    total_object_count = sum([len(each_list) for each_list in task_objids_path_luts.values()])
    
    # Of classified objects, get the breakdown
    all_labels_list = list(label_lut_dict.keys())
    class_count_breakdown = {each_task: {} for each_task in task_name_list}
    for each_task in task_name_list:
        supervised_labels_list = list(supervised_class_labels_dict[each_task].values())
        label_counts_dict = {each_label: supervised_labels_list.count(each_label) for each_label in all_labels_list}
        class_count_breakdown[each_task] = label_counts_dict
    
    # Get the video source used
    example_snap_count = next(iter(snap_count_luts))
    example_snap_path = snap_count_luts[example_snap_count]["path"]
    example_snapshot_metadata = load_json(example_snap_path)
    video_source = example_snapshot_metadata["video_select"]
    
    return render_template("overview.html",
                           camera_name = camera_select,
                           dataset = dataset_select,
                           snapshot_count = num_snapshots,
                           total_object_count = total_object_count,
                           class_count_breakdown = class_count_breakdown,
                           video_source = video_source)

# .....................................................................................................................

@server.route("/label")
def label_route():
    
    # Page should only be passed a list of object ids 
    #  - Needs to request current object class label & an image, based on id & task name
    #  - Server needs to provide label as well as finding a snapshot image + annotating the object (as POST request)
    
    # Generate a dictionary of {task_name: object_id_lists} for all tasks
    get_id_list = lambda id_lut: sorted(list(id_lut.keys()))
    task_id_lists = {each_task: get_id_list(each_id_lut) for each_task, each_id_lut in task_objids_path_luts.items()}
    
    return render_template("label.html", task_id_lists = task_id_lists, label_lut_dict = label_lut_dict)

# .....................................................................................................................

@server.route("/curate")
def curate_route():
    return render_template("curate.html")

# .....................................................................................................................

@server.route("/examine")
def examine_route():    
    return render_template("examine.html")

# .....................................................................................................................

@server.route("/export")
def export_route():    
    return render_template("export.html")

# .....................................................................................................................

@server.route("/labelrequest/<string:task_name>/<int:object_id>", methods=["GET"])
def object_label_request(task_name, object_id):
    
    # Some debugging feedback
    print("", "LABEL REQUEST:", task_name, object_id, "", sep="\n")
    
    # Get the current label associate with the given object id
    object_class_label = supervised_class_labels_dict[task_name][object_id]
    object_class_index = label_to_idx_lut[object_class_label]
    label_request_data = {"label_string": object_class_label,
                          "label_index": object_class_index}
    
    print("  DATA:", label_request_data)
    
    return jsonify(label_request_data)

# .....................................................................................................................

@server.route("/imagerequest/<string:task_name>/<int:object_id>", methods=["GET"])
def object_image_request(task_name, object_id):
    
    # Some debugging feedback
    print("", "IMAGE REQUEST:", task_name, object_id, "", sep="\n")
    
    # Load appropriate snapshot image and annotate for display, then convert to base64 for web use
    scaled_image = get_example_annotated_image(task_name, object_id)
    image_bytes = image_to_jpg_bytearray(scaled_image)
    
    return Response(image_bytes, mimetype = "image/jpeg")

# .....................................................................................................................

@server.route("/animationrequest/<string:task_name>/<int:object_id>", methods=["GET"])
def object_animation_request(task_name, object_id):
    
    # - take in a task and object id and return a sequence of frames to show the object animated
    
    animation_seq = animation_generator(task_name, object_id)
    
    return Response(animation_seq, mimetype = "multipart/x-mixed-replace; boundary=frame")
    
# .....................................................................................................................

@server.route("/labelupdate", methods=["POST"])
def object_label_update():
    
    # Get data needed to update object labels
    update_json_data = flask_request.get_json()
    
    # Pull out post data
    task_name = update_json_data["task_name"]
    object_id = update_json_data["object_id"]
    new_class_label = update_json_data["new_label_string"]
    
    # Build new json entry for the labels file
    new_entry = {object_id: new_class_label}
    
    # Get path to the corresponding task label listing and update it with the new object label
    label_file_path = os.path.join(supervised_labels_folder_path, task_name)
    update_json(label_file_path, new_entry, indent = 2, sort_keys = True, convert_integer_keys = True)
    
    # Update internal record of class labels
    supervised_class_labels_dict[task_name].update(new_entry)
    
    # Some debugging feedback
    print("", 
          "LABELUPDATE POST - {} [obj_id: {}, label_str: {}]".format(task_name, object_id, new_class_label), 
          "", sep="\n")
    
    return ("", 201) # No content response

# .....................................................................................................................
# .....................................................................................................................    

# ---------------------------------------------------------------------------------------------------------------------
#%% *** Launch server ***

if __name__ == "__main__":
    
    # Crash spyder IDE if it's being used, since it doesn't play nicely with flask!
    ide_catcher("Can't run flask from IDE! Use terminal...")

    # Unleash the server
    server.run(debug=enable_debug_mode, port = 5001)

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap
    

