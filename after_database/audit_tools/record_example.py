#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Dec  6 14:49:09 2019

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

import argparse
import numpy as np

from time import perf_counter
from tqdm import tqdm

from local.lib.ui_utils.cli_selections import Resource_Selector

from local.lib.common.timekeeper_utils import isoformat_to_datetime, fake_datetime_like

from local.lib.file_access_utils.structures import create_missing_folder_path
from local.lib.file_access_utils.settings import load_recording_info

from local.offline_database.file_database import launch_file_db, close_dbs_if_missing_data
from local.offline_database.object_reconstruction import Smoothed_Object_Reconstruction as Obj_Recon
from local.offline_database.classification_reconstruction import create_objects_by_class_dict, get_ordered_object_list

from local.eolib.video.text_rendering import position_frame_relative, font_config, simple_text

from local.eolib.video.read_write import Video_Recorder

from local.eolib.utils.cli_tools import Datetime_Input_Parser as DTIP
from local.eolib.utils.cli_tools import cli_prompt_with_defaults, cli_confirm
from local.eolib.utils.quitters import ide_quit

# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes


# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

# .....................................................................................................................

def parse_record_args():
    
    # Set defaults
    default_output_path = os.path.join("~", "Desktop")
    default_timestamp_pos = "br"
    default_relative_timestamp = False
    
    # Set up argument parsing
    ap = argparse.ArgumentParser(formatter_class = argparse.RawTextHelpFormatter)
    ap.add_argument("-o", "--output", default = default_output_path, type = str,
                    help = "\n".join(["Base folder path for the recorded video file.",
                                      "(Default: {})".format(default_output_path)]))
    ap.add_argument("-t", "--timestamp_position", default = default_timestamp_pos, type = str,
                    help = "\n".join(["Set the position of a timestamp to be overlayed on the replay.",
                                      "Can be set to: none or tl, tr, bl, br",
                                      "Corresponding to (t)op, (b)ottom, (l)eft and (r)ight.",
                                      "If set to 'none', the timestamp will not be added.",
                                      "(Default: {})".format(default_timestamp_pos)]))
    ap.add_argument("-r", "--relative_timestamp", default = default_relative_timestamp, action = "store_true",
                    help = "\n".join(["If enabled, the overlayed timestamp will report relative time",
                                      "(e.g. video time) as opposed to absolute time.",
                                      "Note, a timestamp position must be set to see the timestamp!"]))
    
    # Get arg inputs into a dictionary
    args = vars(ap.parse_args())
    
    # Get script arg values
    arg_recording_path = args["output"]
    arg_timestamp_position = args["timestamp_position"]
    arg_relative_timestamp = args["relative_timestamp"]
    
    # Replace output folder user pathing (~) with actual user path
    expanded_arg_recording_path = os.path.expanduser(arg_recording_path)
    
    
    return expanded_arg_recording_path, arg_timestamp_position, arg_relative_timestamp

# .....................................................................................................................
    
def no_decimal_string_format(number_for_string):
    
    # Split number into integer and decimal parts
    int_part = int(number_for_string)
    dec_part = int(round(100 * (number_for_string - int_part)))
    
    # Build string components
    int_only_str = str(int_part)
    dec_str = str(dec_part).zfill(2)
    with_dec_str = "{}p{}".format(int_only_str, dec_str)
    
    # Decide which string format to output
    contains_decimal = (dec_part > 0)
    formatted_number_string = with_dec_str if contains_decimal else int_only_str
    
    return formatted_number_string

# .....................................................................................................................
    
def build_recording_path(base_path, camera_select, user_select, timelapse_factor, file_ext):
    
    # Check that the base pathing exists (if not, ask user if it's ok to create the folder)
    if not os.path.exists(base_path):
        
        # Warn user about the folder not existing
        print("",
              "Recording folder path does not exist!",
              "@ {}".format(base_path),
              sep = "\n")
        
        # Make sure user is ok with creating the folder for recording
        user_confirm_folder_creation = cli_confirm("Create folder for recording?")
        if not user_confirm_folder_creation:
            print("", "Recording folder not created! Cancelling recording...", "", sep = "\n")
            ide_quit()
    
    # Build full folder pathing
    recording_folder = os.path.join(base_path, "safety-cv-exports", "recordings")
    create_missing_folder_path(recording_folder)
    
    # Build timelapse str, if it isn't just 1
    tl_str = "" 
    need_tl_str = abs(timelapse_factor - 1.0) > 0.001
    if need_tl_str:
        tl_str = "-TLx{}".format(no_decimal_string_format(timelapse_factor))
    
    # Build file name & combine with recording folder path for final output
    file_name = "{}-({}){}{}".format(camera_select, user_select, tl_str, file_ext)
    return os.path.join(recording_folder, file_name)

# .....................................................................................................................

def get_recording_times(snapshot_times_ms_list, effective_timelapse_factor):
    
    # If the effective timelapse is 1 or less, then we just record all snapshot times
    low_tl_factor = (effective_timelapse_factor < 1.0)
    tl_factor_is_one = (abs(effective_timelapse_factor - 1.0) < 0.001)
    if low_tl_factor or tl_factor_is_one:
        return snapshot_times_ms_list
    
    # Convert snapshot times to relative values
    snap_times_ms_array = np.int64(snapshot_times_ms_list)
    relative_snap_times_ms = snap_times_ms_array - snap_times_ms_array[0]
    
    # Calculate all recording frame indices
    ms_per_recorded_frame = 1000.0 * effective_timelapse_factor
    timelapsed_frame_indices = np.int64(np.floor(relative_snap_times_ms / ms_per_recorded_frame))
    
    # Now pull out only the frames where the indices changed an integer amount
    frame_index_deltas = np.diff(timelapsed_frame_indices)
    frame_index_deltas[0] = 1
    recording_indices = np.nonzero(frame_index_deltas)
    
    # Finally, create a new list of snapshot times, containing only the timelapsed indices to record
    tl_snapshot_times_ms_list = snap_times_ms_array[recording_indices].tolist()
    
    return tl_snapshot_times_ms_list

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Timestamp functions

# .....................................................................................................................

def draw_timestamp(display_frame, snapshot_metadata, fg_config, bg_config, replay_start_dt, use_relative_time, 
                   text_position = None):
    
    # Don't draw the timestamp if there is no position data
    if text_position is None:
        return display_frame
    
    # For clarity
    centered = False
    
    # Get snapshot timing info
    datetime_isoformat = snapshot_metadata["datetime_isoformat"]
    snap_dt = isoformat_to_datetime(datetime_isoformat)
    
    # Convert timing to 'relative' time, if needed
    if use_relative_time:
        snap_dt = (snap_dt - replay_start_dt) + fake_datetime_like(snap_dt)
    
    # Draw timestamp with background/foreground to help separate from video background
    snap_dt_str = snap_dt.strftime("%H:%M:%S")
    simple_text(display_frame, snap_dt_str, text_position, centered, **bg_config)
    simple_text(display_frame, snap_dt_str, text_position, centered, **fg_config)
    
    return display_frame

# .....................................................................................................................
    
def get_timestamp_location(timestamp_position_arg, snap_shape, fg_font_config):
    
    # Use simple lookup to get the timestamp positioning
    position_lut = {"tl": (3, 3), "tr": (-3, 3),
                    "bl": (3, -1), "br": (-3, -1),
                    "None": None, "none": None}
    
    # If we can't get the position (either wasn't provided, or incorrectly specified), then we won't return anything
    relative_position = position_lut.get(timestamp_position_arg, None)
    if relative_position is None:
        return None
    
    return position_frame_relative(snap_shape, "00:00:00", relative_position, **fg_font_config)

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Get script arguments

recording_folder_path, timestamp_pos_arg, enable_relative_timestamp = parse_record_args()


# ---------------------------------------------------------------------------------------------------------------------
#%% Select camera/user

enable_debug_mode = False

# Create selector so we can access existing report data
selector = Resource_Selector()
project_root_path, cameras_folder_path = selector.get_project_pathing()

# Select the camera/user to show data for (needs to have saved report data already!)
camera_select, camera_path = selector.camera(debug_mode=enable_debug_mode)
user_select, _ = selector.user(camera_select, debug_mode=enable_debug_mode)


# ---------------------------------------------------------------------------------------------------------------------
#%% Catalog existing data

cinfo_db, snap_db, obj_db, class_db, summary_db = \
launch_file_db(cameras_folder_path, camera_select, user_select,
               launch_snapshot_db = True,
               launch_object_db = True,
               launch_classification_db = True,
               launch_summary_db = False)

# Catch missing data
close_dbs_if_missing_data(snap_db, error_message_if_missing = "No snapshot data in the database!")


# ---------------------------------------------------------------------------------------------------------------------
#%% Ask user for time window

# Get the maximum range of the data (based on the snapshots, because that's the most we could show)
earliest_datetime, latest_datetime = snap_db.get_bounding_datetimes()
snap_wh = cinfo_db.get_snap_frame_wh()
snap_width, snap_height = snap_wh

# Ask the user for the range of datetimes to use for selecting data
user_start_dt, user_end_dt = DTIP.cli_prompt_start_end_datetimes(earliest_datetime, latest_datetime,
                                                                 print_help_before_prompt = False,
                                                                 debug_mode = enable_debug_mode)

# Provide feedback about the selected time range
DTIP.print_start_end_time_range(user_start_dt, user_end_dt)


# ---------------------------------------------------------------------------------------------------------------------
#%% Load object data

# Get object metadata from the server
obj_metadata_generator = obj_db.load_metadata_by_time_range(user_start_dt, user_end_dt)

# Create dictionary of 'reconstructed' objects based on object metadata
obj_dict = Obj_Recon.create_reconstruction_dict(obj_metadata_generator,
                                                snap_wh,
                                                user_start_dt, 
                                                user_end_dt)

# Organize objects by class label -> then by object id (nested dictionaries)
obj_id_list, obj_by_class_dict, obj_id_to_class_dict = create_objects_by_class_dict(class_db, obj_dict)

# Get an ordered list of the objects for drawing
ordered_obj_list = get_ordered_object_list(obj_id_list, obj_by_class_dict, obj_id_to_class_dict)


# ---------------------------------------------------------------------------------------------------------------------
#%% Determine playback speed

# Get all the snapshot times we'll need for animation
snap_times_ms_list = snap_db.get_all_snapshot_times_by_time_range(user_start_dt, user_end_dt)

# Estimate the 'framerate' of the snapshots, based on the average time difference between them
average_snap_timedelta_ms = np.round(np.mean(np.diff(snap_times_ms_list)))
snapshot_fps = (1000.0 / average_snap_timedelta_ms)

# Determine a reasonble 'default' timelapse factor (so that the output video isn't horribly choppy)
maximum_fps = 30.0
target_minimum_fps = 15.0
default_tl_factor = round(target_minimum_fps / snapshot_fps)

# Have user enter a timelapse factor for the recording
user_tl_factor = cli_prompt_with_defaults("Enter timelapse factor:", 
                                          default_value = default_tl_factor, 
                                          return_type = float)

# Calculate the recording fps based on user specified timelapse factor. Try to timelapse using higher framerate
recording_fps = min(maximum_fps, (snapshot_fps * user_tl_factor))
effective_tl_factor = (snapshot_fps * user_tl_factor) / recording_fps
recording_snap_times_ms_list = get_recording_times(snap_times_ms_list, effective_tl_factor)


# ---------------------------------------------------------------------------------------------------------------------
#%% Set up recording

# Load codec/file extension settings
recording_info_dict = load_recording_info(project_root_path)
recording_file_ext = recording_info_dict["file_extension"]
recording_codec = recording_info_dict["codec"]

# Make sure we add a leading dot to the file extension
recording_file_ext = "".join([".", recording_file_ext]).replace("..", ".")

# Build pathing to recorded file
recording_file_path = build_recording_path(recording_folder_path, 
                                           camera_select, 
                                           user_select,
                                           user_tl_factor, 
                                           recording_file_ext)

# Create video writer object
vwriter = Video_Recorder(recording_file_path,
                         recording_FPS = recording_fps,
                         recording_WH = snap_wh,
                         codec = recording_codec)


# ---------------------------------------------------------------------------------------------------------------------
#%% Data playback

# Set up timestamp text config, in case it's needed
snap_shape = (snap_height, snap_width, 3)
fg_font_config = font_config(scale = 0.35, color = (255, 255, 255))
bg_font_config = font_config(scale = 0.35, color = (0, 0, 0), thickness = 2)
timestamp_xy = get_timestamp_location(timestamp_pos_arg, snap_shape, fg_font_config)

# Some feedback about recording
print("", 
      "Recording...",
      "@ {}".format(recording_file_path), 
      "",
      sep = "\n")

# Create cli progress bar for feedback
num_recording_snaps = len(recording_snap_times_ms_list)
cli_prog_bar = tqdm(total = num_recording_snaps, mininterval = 0.5)

# Start timing for final feedback
t_start = perf_counter()

try:

    # Loop over snapshot times to generate the playback video
    for each_snap_time_ms in recording_snap_times_ms_list:
        
        # Load each snapshot image & draw object annoations over top
        snap_md = snap_db.load_snapshot_metadata_by_ems(each_snap_time_ms)
        snap_image, snap_frame_idx = snap_db.load_snapshot_image(each_snap_time_ms)
        for each_obj in ordered_obj_list:
            each_obj.draw_trail(snap_image, snap_frame_idx, each_snap_time_ms)
            each_obj.draw_outline(snap_image, snap_frame_idx, each_snap_time_ms)
        
        # Draw timestamp over displayed image, if needed
        timestamp_image = draw_timestamp(snap_image, snap_md, fg_font_config, bg_font_config, 
                                         user_start_dt, enable_relative_timestamp, timestamp_xy)
        
        # Record frames
        vwriter.write(snap_image)
        cli_prog_bar.update()
        
except KeyboardInterrupt:
    print("Keyboard interrupt! Closing...")

# End timing
t_end = perf_counter()

# Clean up
vwriter.release()
cli_prog_bar.close()

# Some feedback
total_time = (t_end - t_start)
print("", "Done! Took {:.1f} seconds".format(total_time), "", sep="\n")


# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap

# TODO
# - Add ghosting option?
# - clean up recording settings file (ideally, first creation should auto-select codec/file ext!)
# - consider unifying replay + record tools?
