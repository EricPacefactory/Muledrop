#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Sep 18 10:52:48 2019

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

from local.lib.ui_utils.cli_selections import Resource_Selector
from local.lib.ui_utils.local_ui.windows_base import Simple_Window
from local.lib.launcher_utils.video_setup import File_Video_Reader
from local.lib.launcher_utils.resource_initialization import initialize_background_and_framerate_from_file

#from local.configurables.externals.background_capture.passthrough_backgroundcapture import Background_Capture
#from local.configurables.externals.background_capture.averaging_backgroundcapture import Background_Capture
from local.configurables.externals.background_capture.median_backgroundcapture import Background_Capture

from local.eolib.utils.cli_tools import cli_confirm

# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes

# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

# ---------------------------------------------------------------------------------------------------------------------
#%% Ask for base selections

# Create selector, get important pathing & select location
selector = Resource_Selector()
project_root_path, all_locations_folder_path = selector.get_shared_pathing()
location_select, location_select_folder_path = selector.location()

# Select camera & video to run
camera_select, camera_path = selector.camera(location_select)
video_select, video_path = selector.video(location_select, camera_select)


# ---------------------------------------------------------------------------------------------------------------------
#%% Load video

# Set up the video source
vreader = File_Video_Reader(location_select_folder_path, camera_select, video_select)
video_wh = vreader.video_wh
video_fps = vreader.video_fps
video_type = vreader.video_type


# ---------------------------------------------------------------------------------------------------------------------
#%% Load background capture

saving_enabled = cli_confirm("Save resource data?", default_response = True, debug_mode = True)
threading_enabled = False

# Make sure we have a starting background
framerate_estimate = initialize_background_and_framerate_from_file(location_select_folder_path,
                                                                   camera_select,
                                                                   vreader,
                                                                   force_capture_reset = saving_enabled)

# Bundle externals class init variables for convenience
externals_config = {"location_select_folder_path": location_select_folder_path,
                    "camera_select": camera_select,
                    "video_wh": video_wh}

bgcap = Background_Capture(**externals_config)
bgcap.reconfigure({"capture_period_hr": 0, "capture_period_min": 0, "capture_period_sec": 20})
bgcap.reconfigure({"generation_trigger_after_n_captures": 1, "max_ram_usage_mb": 19})
bgcap.toggle_report_saving(True)
bgcap.toggle_resource_saving(saving_enabled)
bgcap.toggle_threaded_saving(threading_enabled)

bgcap.set_max_capture_count(20)
bgcap.set_max_generate_count(5)
bgcap.set_png_compression(0)
bgcap.set_jpg_quality(50)


# ---------------------------------------------------------------------------------------------------------------------
#%% Set up displays

# Try to close any previously opened windows
try: cv2.destroyAllWindows()
except: pass

bg_window = Simple_Window("Background", video_wh).move_corner_pixels(20, 20)
input_window = Simple_Window("Input", video_wh).move_corner_pixels(600, 80)


# ---------------------------------------------------------------------------------------------------------------------
#%% *** RUN LOOP ***

# Run video loop
while True:
    
    # .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .
    # Frame reading
    
    # Grab frames from the video source (with timing information for each frame!)
    req_break, input_frame, read_time_sec, *fed_time_args = vreader.read()
    if req_break:
        break
    
    # .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .
    # Get background image
    
    # Handle background capture stage
    background_image, background_was_updated = bgcap.run(input_frame, *fed_time_args)
    
    # .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .
    # Display
    
    input_window.imshow(input_frame)
    bg_window.imshow(background_image)
    keypress = cv2.waitKey(5)
    if keypress == 27:
        break


# Deal with video clean-up
vreader.release()
cv2.destroyAllWindows()
bgcap.close(*fed_time_args)


# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap


