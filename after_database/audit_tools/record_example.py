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

from local.offline_database.file_database import launch_file_db, close_dbs_if_missing_data
from local.offline_database.object_reconstruction import Smoothed_Object_Reconstruction as Obj_Recon
from local.offline_database.classification_reconstruction import set_object_classification_and_colors

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
    
    default_output_path = "~/Desktop"
    default_codec = "avc1"
    default_recording_ext = "mp4"
    
    # Set up argument parsing
    ap = argparse.ArgumentParser(formatter_class = argparse.RawTextHelpFormatter)
    ap.add_argument("-o", "--output", default = default_output_path, type = str,
                    help = "Base folder path for the recorded video file. \
                            \n(Default: {})".format(default_output_path))
    ap.add_argument("-x", "--extension", default = default_recording_ext, type = str,
                    help = "File extension of the recorded video (avi, mp4, mkv, etc.). \
                            \n(Default: {})".format(default_recording_ext))
    ap.add_argument("-c", "--codec", default = default_codec, type = str,
                    help = "FourCC code used for recording (avc1, X264, XVID, MJPG, mp4v, etc.). \
                            \n(Default: {})".format(default_codec))
    
    # Get arg inputs into a dictionary
    args = vars(ap.parse_args())
    
    # Get script arg values
    arg_recording_path = args["output"]
    arg_file_extension = args["extension"]
    arg_codec = args["codec"]
    
    # Replace output folder user pathing (~) with actual user path
    expanded_arg_recording_path = os.path.expanduser(arg_recording_path)
    
    # Make sure file extension has preceeding '.' (i.e. convert 'avi' to '.avi')
    safe_file_ext = "".join([".", arg_file_extension]).replace("..", ".")
    
    return expanded_arg_recording_path, safe_file_ext, arg_codec

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
    recording_folder = os.path.join(base_path, "safety-cv-recordings")
    os.makedirs(recording_folder, exist_ok = True)
    
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
#%% Get script arguments

recording_folder_path, recording_file_ext, recording_codec = parse_record_args()

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

cinfo_db, rinfo_db, snap_db, obj_db, class_db, _, _ = \
launch_file_db(cameras_folder_path, camera_select, user_select,
               launch_snapshot_db = True,
               launch_object_db = True,
               launch_classification_db = True,
               launch_summary_db = False,
               launch_rule_db = False)

# Catch missing data
rinfo_db.close()
close_dbs_if_missing_data(snap_db, error_message_if_missing = "No snapshot data in the database!")


# ---------------------------------------------------------------------------------------------------------------------
#%% Ask user for time window

# Get the maximum range of the data (based on the snapshots, because that's the most we could show)
earliest_datetime, latest_datetime = snap_db.get_bounding_datetimes()
snap_wh = cinfo_db.get_snap_frame_wh()

# Ask the user for the range of datetimes to use for selecting data
user_start_dt, user_end_dt = DTIP.cli_prompt_start_end_datetimes(earliest_datetime, latest_datetime,
                                                                 print_help_before_prompt = False,
                                                                 debug_mode = enable_debug_mode)


# ---------------------------------------------------------------------------------------------------------------------
#%% Load object data

# Get object metadata from the server
obj_metadata_generator = obj_db.load_metadata_by_time_range(user_start_dt, user_end_dt)

# Create list of 'reconstructed' objects based on object metadata, so we can work/interact with the object data
obj_list = Obj_Recon.create_reconstruction_list(obj_metadata_generator,
                                                snap_wh,
                                                user_start_dt, 
                                                user_end_dt)

# Load in classification data, if any
set_object_classification_and_colors(class_db, obj_list)


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
        snap_image, snap_frame_idx = snap_db.load_snapshot_image(each_snap_time_ms)
        for each_obj in obj_list:            
            each_obj.draw_trail(snap_image, snap_frame_idx, each_snap_time_ms)
            each_obj.draw_outline(snap_image, snap_frame_idx, each_snap_time_ms)
        
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

