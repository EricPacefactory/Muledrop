#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu May 21 16:03:10 2020

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
import numpy as np

from time import perf_counter

from local.lib.common.timekeeper_utils import Periodic_Polled_Timer

from local.lib.file_access_utils.resources import load_newest_generated_background
from local.lib.file_access_utils.resources import reset_capture_folder, reset_generate_folder
from local.lib.file_access_utils.image_read_write import save_png_image


# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes


# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

# .....................................................................................................................

def initialize_background_and_framerate_from_file(cameras_folder_path, camera_select, video_reader_ref,
                                                  force_capture_reset = False):
    
    '''
    Function which should be called before running video processing
    Handles the creation of an initial background file (if missing) and gets a video framerate estimate
    
    Returns:
            
    '''
    
    # Get video info from the video reader
    video_width, video_height = video_reader_ref.video_wh
    
    # Get a framerate estimate (though this is not as meaningful for files as with rtsp...)
    framerate_estimate = get_file_framerate_estimate(video_reader_ref)
    
    # Delete any existing captures, in case they came from a different file/timing
    if force_capture_reset:
        reset_capture_folder(cameras_folder_path, camera_select)
    
    # Check if we already have a valid background, in which case we don't have to do anything
    background_already_exists = check_for_valid_background(cameras_folder_path,
                                                           camera_select,
                                                           video_width,
                                                           video_height)
    
    # If we got a background, we're done!
    if background_already_exists:
        return framerate_estimate
    
    # .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .
    
    # Generate the background image data
    new_background_image = _generate_initial_background_from_file(video_reader_ref,
                                                                  max_ram_usage_MB = 250,
                                                                  max_frames_to_use = 25)
    
    # Clear out existing resources and save the new background
    _save_initial_background_image(cameras_folder_path, camera_select, new_background_image)
    
    return framerate_estimate

# .....................................................................................................................

def initialize_background_and_framerate_from_rtsp(cameras_folder_path, camera_select, video_reader_ref,
                                                  force_capture_reset = True):
    
    '''
    Function which should be called before running video processing
    Handles the creation of an initial background file (if missing) and gets a video framerate estimate
    Note, this function will delay the use of the stream by at least 1 minute as it estimates the frame rate
    (the delay is also needed to avoid object ID assignment errors in the case of restarting connections!)
    
    Returns:
        framerate_estimate
    '''
    
    # Get video info from the video reader
    video_width, video_height = video_reader_ref.video_wh
    
    # Get an estimate of the 'real' framerate of the video
    framerate_estimate = get_rtsp_framerate_estimate(video_reader_ref,
                                                     minutes_to_run = 1)
    
    # Delete any existing captures, in case they came from a different time
    if force_capture_reset:
        reset_capture_folder(cameras_folder_path, camera_select)
    
    # Check if we already have a valid background, in which case we don't have to do anything else
    background_already_exists = check_for_valid_background(cameras_folder_path,
                                                           camera_select,
                                                           video_width,
                                                           video_height)
    
    # If we got a background, we're done!
    if background_already_exists:
        return framerate_estimate
    
    # .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .
    
    # Generate the background image data
    new_background_image = _generate_initial_background_from_rtsp(video_reader_ref,
                                                                  minutes_to_run = 4,
                                                                  max_ram_usage_MB = 250,
                                                                  max_frames_to_use = 25)
    
    # Clear out existing resources and save the new background
    _save_initial_background_image(cameras_folder_path, camera_select, new_background_image)
    
    return framerate_estimate

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Define helper functions

# .....................................................................................................................

def check_for_valid_background(cameras_folder_path, camera_select, video_width, video_height,
                               print_feedback_on_existing = True):
    
    ''' Helper function used to check if a valid (i.e. properly sized) background file exists '''
    
    # Initialize output
    background_exists = False
    
    # See if we can just load an existing background
    newest_background = load_newest_generated_background(cameras_folder_path, camera_select, 
                                                         error_if_no_backgrounds = False)
    if newest_background is None:
        return background_exists
    
    # Assuming loading worked, make sure the background is the right size
    loaded_height, loaded_width = newest_background.shape[0:2]
    wrong_width = (loaded_width != video_width)
    wrong_height = (loaded_height != video_height)
    if wrong_width or wrong_height:
        return background_exists
    
    # If we get here, we loaded a valid background, so it exists!
    background_exists = True
    if print_feedback_on_existing:
        print("",
              "Found existing background file!",
              sep = "\n")
    
    return background_exists

# .....................................................................................................................

def get_file_framerate_estimate(video_reader_ref):
    
    '''
    Function intended to estimate the 'real' framerate of a (file-based) video source.
    Some files do incorrectly report their framerates, though programs like VLC are somehow able
    to detect this and come up with a more accurate framerate...
    It's not clear how this works for now
    '''
    
    # For now, best guess is literally whatever the file reports... It would nice to figure out how VLC does this
    framerate_estimate = video_reader_ref.video_fps
    
    return framerate_estimate

# .....................................................................................................................

def get_rtsp_framerate_estimate(video_reader_ref, minutes_to_run = 1):
    
    '''
    Function which estimates the 'real' framerate of a network video source.
    Although network cameras do report framerate values, they're often inaccurate!
    Note that this function also helps delay immediate restarts of rtsp streams, 
    which can otherwise cause (temporary) object ID assignment errors on saved data.
    '''
    
    # Make sure we run for at least 1 minute
    minutes_to_run = max(1, minutes_to_run)
    seconds_to_run = (60.0 * minutes_to_run)
    
    # Provide some feedback, since the estimation takes some time
    reported_framerate = video_reader_ref.video_fps
    print("",
          "Video framerate reported as {:.3f}".format(reported_framerate),
          "  --> Will now estimate actual framerate from stream",
          "      this will take about {} minute(s)...".format(minutes_to_run),
          sep = "\n")
    
    # Burn the first few frames, in case frames were being buffered
    burn_time_sec = 10
    t_burn_start = perf_counter()
    t_burn_end = t_burn_start + burn_time_sec
    while True:
        video_reader_ref.no_decode_read()
        current_time = perf_counter()
        if current_time > t_burn_end:
            break
    
    # Read frames as fast as possible, with timing & counts
    frame_count = 0
    t_start = perf_counter()
    target_end_time = (t_start + seconds_to_run)
    while True:        
        video_reader_ref.no_decode_read()
        frame_count += 1        
        t_end = perf_counter()
        if t_end > target_end_time:
            break
    
    # Calculate experimental framerate
    total_time_sec = (t_end - t_start)
    framerate_estimate = (frame_count / total_time_sec)
    
    # Report results
    print("",
          "Experimentally determined framerate as {:.3f}".format(framerate_estimate),
          sep = "\n")
    
    return framerate_estimate

# .....................................................................................................................

def _generate_initial_background_from_file(video_reader_ref, max_ram_usage_MB = 250, max_frames_to_use = 25):
    
    '''
    Helper function which generates a background image given a video reader object
    Assumes the video reader is file-based (i.e. not reading off a network stream)
    
    Inputs:
        video_reader_ref --> (Object) A video reader object. Should be reading from a file!
        
        max_ram_usage_MB --> (Integer/Float) The maximum amount of RAM (in megabytes) that can be
                             used when generating the initial background image
    
    Outputs:
        file_generated_background (np.uint8 array)
    '''
    
    # Get video info
    video_width, video_height = video_reader_ref.video_wh
    total_frames = video_reader_ref.total_frames
    
    # Set up a separate video reader to handle capture 
    # (to avoid any threading or weird behavior on provided reader)
    temp_vreader = cv2.VideoCapture(video_reader_ref.video_source)
    
    # Figure out how many frames we can use given the RAM limit
    num_bytes_per_pixel = 3
    num_bytes_per_frame = (video_width * video_height * num_bytes_per_pixel)
    num_MB_per_frame = (num_bytes_per_frame / 1E6)
    num_frames_allowed_by_ram = int(max_ram_usage_MB / num_MB_per_frame)
    
    # Figure out which frame indices to use for grabbing frames for background generation
    ignore_first_frames = 10
    ignore_final_frames = 10
    first_frame_idx = ignore_first_frames
    last_frame_idx = (total_frames - 1 - ignore_final_frames)
    num_frames_allowed_by_indexing = (last_frame_idx - first_frame_idx)
    
    # Figure out how many total frames we can use and then generate the target indices
    num_frames_allowed = min(max_frames_to_use, num_frames_allowed_by_ram, num_frames_allowed_by_indexing)
    target_frame_index_array = np.linspace(first_frame_idx, last_frame_idx, num_frames_allowed, dtype = np.int32)
    
    # Provide some feedback, because the next step can be slow
    print("", 
          "No background file found! ({}x{})".format(video_width, video_height),
          "  --> Will need to generate one from the file, which may take a moment...",
          sep = "\n")
    
    # Start timing
    t_start = perf_counter()
    
    # Grab all target frames to use for generating the background
    frame_stack = []
    for each_frame_index in target_frame_index_array:
        temp_vreader.set(cv2.CAP_PROP_POS_FRAMES, each_frame_index)
        rec_frame, new_frame = temp_vreader.read()
        if not rec_frame:
            print("",
                  "WARNING:",
                  "  Video frames ended unexpectedly... Background may be poorly formed",
                  sep = "\n")
            break
        frame_stack.append(new_frame)
    
    # Close our (hacky-ish) video reader
    temp_vreader.release()
    
    # Generate background using all loaded frame data
    file_generated_background = _generate_background_from_median(frame_stack)
    
    # Some feedback about generation
    t_end = perf_counter()
    generate_time_sec = (t_end - t_start)
    print("",
          "Done generating initial background!",
          "  Took {:.1f} seconds".format(generate_time_sec),
          sep = "\n")
    
    return file_generated_background

# .....................................................................................................................

def _generate_initial_background_from_rtsp(video_reader_ref,
                                           minutes_to_run = 4,
                                           max_ram_usage_MB = 150,
                                           max_frames_to_use = 25):
    
    # Get video info
    video_width, video_height = video_reader_ref.video_wh
    
    # Figure out how many frames we can use given the RAM limit
    num_bytes_per_pixel = 3
    num_bytes_per_frame = (video_width * video_height * num_bytes_per_pixel)
    num_MB_per_frame = (num_bytes_per_frame / 1E6)
    num_frames_allowed_by_ram = int(max_ram_usage_MB / num_MB_per_frame)
    
    # Figure out how often to grab captured data
    num_frames_allowed = min(max_frames_to_use, num_frames_allowed_by_ram)
    total_seconds_to_run = (60 * minutes_to_run)
    capture_period_sec = total_seconds_to_run / num_frames_allowed
    
    # If we get here, we have no background! We'll need to generate one from the stream
    approx_ram_usage_MB = int(round(num_frames_allowed * num_MB_per_frame))
    print("", 
          "No background file found! ({}x{})".format(video_width, video_height),
          "  --> Will need to generate one. This will take about {:.0f} minutes...".format(minutes_to_run),
          "  --> Using {} frames (approx. {} MB of RAM)".format(num_frames_allowed, approx_ram_usage_MB),
          sep = "\n")
    
    # Loop until we get enough frames
    capture_timer = Periodic_Polled_Timer(trigger_on_first_check = True)
    capture_timer.set_trigger_period(seconds = capture_period_sec)
    capture_timer.disable_randomness()
    frame_stack = []
    while True:
        
        # Partially read the video (don't bother encoding, in case we don't need the frame data)
        video_reader_ref.no_decode_read()
        
        # Get the current time as an epoch value and keep checking for periodic triggering
        current_time_ms = int(perf_counter() * 1000)
        need_new_capture = capture_timer.check_trigger(current_time_ms)
        if need_new_capture:
            
            # Get the frame data if possible, otherwise crash, since we don't want to deal with disconnects...
            req_break, new_frame, read_time_sec, *fed_time_args = video_reader_ref.decode_read()
            if req_break:
                error_msg_list = ["Missed frame from rtsp stream during background initialization!",
                                  "  Cancelling..."]
                error_msg = "\n".join(error_msg_list)
                raise IOError(error_msg)
            
            # Store new frame data for processing
            if new_frame is not None:
                frame_stack.append(new_frame)
            
            # Stop once we have enough frames to generate a background
            got_enough_frames = (len(frame_stack) >= num_frames_allowed)
            if got_enough_frames:
                break
    
    # Generate background using all loaded frame data
    rtsp_generated_background = _generate_background_from_median(frame_stack)
    
    # Some feedback to make it clear that the background generation finished
    print("", "Done generating initial background!", sep = "\n")
    
    return rtsp_generated_background

# .....................................................................................................................

def _save_initial_background_image(cameras_folder_path, camera_select, new_background_image):
    
    ''' Helper function which clears out existing background resource data and save a new 'initial' image '''
    
    # Reset resource folders & get paths so we can save the generate image data
    generate_folder_path = reset_generate_folder(cameras_folder_path, camera_select)
    
    # Save the generated data as the 'first' file in the folder
    save_name_no_ext = "0"
    save_png_image(generate_folder_path, save_name_no_ext, new_background_image)
    
    return

# .....................................................................................................................

def _generate_background_from_median(list_of_frames):
    
    ''' Helper function which provides consistent median background calculation '''
    
    return np.uint8(np.round(np.median(list_of_frames, axis = 0)))

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Demo 
    
if __name__ == "__main__":
    pass


# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap


