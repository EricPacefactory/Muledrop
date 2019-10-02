#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Sep 19 12:39:16 2019

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

from local.lib.selection_utils import Resource_Selector
from local.lib.configuration_utils.local_ui.local_windows_base import Simple_Window
from local.lib.configuration_utils.video_setup import Dummy_vreader

#from local.configurables.externals.snapshot_capture.passthrough_snapcapture import Snapshot_Capture
from local.configurables.externals.snapshot_capture.fixed_sample_snapcapture import Snapshot_Capture
#from local.configurables.externals.snapshot_capture.fixed_period_snapcapture import Snapshot_Capture

from eolib.utils.cli_tools import cli_confirm

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

# Find list of all tasks
task_name_list = selector.get_task_list(camera_select, user_select)


# ---------------------------------------------------------------------------------------------------------------------
#%% Load video

# Set up the video source
vreader = Dummy_vreader(cameras_folder_path, camera_select, video_select)
video_wh = vreader.video_wh
video_fps = vreader.video_fps
video_type = vreader.video_type


# ---------------------------------------------------------------------------------------------------------------------
#%% Load background capture

# Set saving behavior parameters
saving_enabled = cli_confirm("Save data?", default_response = False)
threading_enabled = True

externals_config = {"cameras_folder_path": cameras_folder_path,
                    "camera_select": camera_select,
                    "user_select": user_select,
                    "video_select": video_select,
                    "video_wh": video_wh}


# Load & configure snapshots
snapcap = Snapshot_Capture(**externals_config)
snapcap.reconfigure()
snapcap.toggle_image_saving(saving_enabled)
snapcap.toggle_metadata_saving(saving_enabled)
snapcap.toggle_threading(threading_enabled)

# Create empty object ids for testing saving
snap_objids_dict = {each_task_name: [] for each_task_name in task_name_list}

# ---------------------------------------------------------------------------------------------------------------------
#%% Set up displays

# Try to close any previously opened windows
try: cv2.destroyAllWindows()
except: pass

snap_window = Simple_Window("Latest Snapshot", *video_wh).move_corner_pixels(20, 20)
input_window = Simple_Window("Input", *video_wh).move_corner_pixels(600, 80)


# ---------------------------------------------------------------------------------------------------------------------
#%% *** RUN LOOP ***

# Run video loop
while True:
    
    # .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .
    # Frame reading
    
    # Grab frames from the video source (with timing information for each frame!)
    req_break, input_frame, current_frame_index, current_time_elapsed, current_datetime = vreader.read()
    if req_break:
        break
    
    # .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .
    # Get snapshot data
    
    # Get snapshot if needed and return most recent snapshot data for object metadata capture
    need_new_snapshot, current_snapshot_metadata = snapcap.metadata(input_frame, 
                                                                    current_frame_index,
                                                                    current_time_elapsed, 
                                                                    current_datetime)
    
    # .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .
    # Save snapshot data, with active object ids
    
    snapshot_frame = snapcap.save_snapshots(need_new_snapshot, input_frame, snap_objids_dict)
    
    # .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .
    # Display
    
    input_window.imshow(input_frame)    
    if snapshot_frame is not None:
        snap_window.imshow(snapshot_frame)
        
    keypress = cv2.waitKey(10)
    if keypress == 27:
        break


# Deal with video clean-up
vreader.release()
cv2.destroyAllWindows()


# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap
