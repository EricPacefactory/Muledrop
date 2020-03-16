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

#from local.configurables.externals.background_capture.passthrough_backgroundcapture import Background_Capture
#from local.configurables.externals.background_capture.averaging_backgroundcapture import Background_Capture
from local.configurables.externals.background_capture.median_backgroundcapture import Background_Capture

from local.eolib.utils.cli_tools import cli_confirm

# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes

# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

# ---------------------------------------------------------------------------------------------------------------------
#%% Ask user for base selections

# Create selector so we can make camera/user/video selections
selector = Resource_Selector()
project_root_path = selector.project_root_path
cameras_folder_path = selector.cameras_folder_path

# Select shared components
camera_select, camera_path = selector.camera()
user_select, user_path = selector.user(camera_select)
video_select, video_path = selector.video(camera_select)


# ---------------------------------------------------------------------------------------------------------------------
#%% Load video

# Set up the video source
vreader = File_Video_Reader(cameras_folder_path, camera_select, video_select)
video_wh = vreader.video_wh
video_fps = vreader.video_fps
video_type = vreader.video_type


# ---------------------------------------------------------------------------------------------------------------------
#%% Load background capture

saving_enabled = cli_confirm("Save background data?", default_response = False)
threading_enabled = False

externals_config = {"cameras_folder_path": cameras_folder_path,
                    "camera_select": camera_select,
                    "user_select": user_select,
                    "video_select": video_select,
                    "video_wh": video_wh}

bgcap = Background_Capture(**externals_config)
bgcap.reconfigure({"capture_period_mins": 0.1, "update_weighting": 0.5})
bgcap.toggle_report_saving(saving_enabled)
bgcap.toggle_resource_saving(saving_enabled)
bgcap.toggle_threaded_saving(threading_enabled)

bgcap.set_max_capture_count(50)
bgcap.set_max_generated_count(10)
bgcap.set_png_compression(0)
bgcap.set_jpg_quality(25)

bgcap.generate_on_startup(vreader)

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
    req_break, input_frame, read_time_sec, current_frame_index, current_epoch_ms, current_datetime = vreader.read()
    if req_break:
        break
    
    # .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .
    # Get background image
    
    # Handle background capture stage
    background_image, background_was_updated = bgcap.run(input_frame, 
                                                         current_frame_index, current_epoch_ms, current_datetime)
    
    # .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .
    # Display
    
    input_window.imshow(input_frame)
    bg_window.imshow(background_image)
    keypress = cv2.waitKey(10)
    if keypress == 27:
        break


# Deal with video clean-up
vreader.release()
cv2.destroyAllWindows()


# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap
