#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Aug 23 16:43:38 2019

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

from local.lib.selection_utils import Resource_Selector

from local.lib.configuration_utils.local_ui.windows_base import Simple_Window

from local.offline_database.file_database import Snap_DB, Object_DB, Classification_DB
from local.offline_database.file_database import post_snapshot_report_metadata, post_object_report_metadata
from local.offline_database.file_database import post_object_classification_data
from local.offline_database.file_database import user_input_datetime_range
from local.offline_database.object_reconstruction import Smoothed_Object_Reconstruction as Obj_Recon
from local.offline_database.classification_reconstruction import set_object_classification_and_colors


# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes

# .....................................................................................................................

class Hover_Callback:
    
    # .................................................................................................................
    
    def __init__(self, frame_wh):
        
        self._mouse_moved = False
        self._mouse_clicked = False
        self._mouse_xy = np.array((-10000,-10000))
        
        frame_width, frame_height = frame_wh
        self.frame_scaling = np.float32((frame_width - 1, frame_height - 1))
        self.frame_wh = frame_wh
    
    # .................................................................................................................
    
    def __call__(self, *args, **kwargs):
        self.mouse_callback(*args, **kwargs)
    
    # .................................................................................................................
    
    def mouse_callback(self, event, mx, my, flags, param):
        self._mouse_xy = np.int32((mx, my))
        self._mouse_moved = (event == cv2.EVENT_MOUSEMOVE)
        self._mouse_clicked = (event == cv2.EVENT_LBUTTONDOWN)
    
    # .................................................................................................................
    
    def mouse_xy(self, normalized = True):
        
        if normalized:
            return self._mouse_xy / self.frame_scaling
        
        return self._mouse_xy
    
    # .................................................................................................................
    
    def clicked(self):
        return self._mouse_clicked
    
    # .................................................................................................................
    # .................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

# .....................................................................................................................

def redraw_timebar_base(blank_timebar, start_idx, end_idx, max_idx, highlight_color = (80,80,80)):
    
    # Get frame sizing so we know where to draw everything
    frame_height, frame_width = blank_timebar.shape[0:2]
    width_scale = frame_width - 1
    
    # Calculate starting/ending points of the highlighted playback region
    x_start_px = int(round(width_scale * start_idx / max_idx))
    x_end_px = int(round(width_scale * end_idx / max_idx))
    
    # Bundle x/y values for clarity
    pt1 = (x_start_px, 0 - 10)
    pt2 = (x_end_px, frame_height + 10)    
    return cv2.rectangle(blank_timebar.copy(), pt1, pt2, highlight_color, -1)

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Select camera/user/task

enable_debug_mode = False

# Create selector so we can access existing report data
selector = Resource_Selector()
project_root_path, cameras_folder_path = selector.get_project_pathing()

# Select the camera/user/task to show data for (needs to have saved report data already!)
camera_select, camera_path = selector.camera(debug_mode=enable_debug_mode)
user_select, _ = selector.user(camera_select, debug_mode=enable_debug_mode)
task_select, _ = selector.task(camera_select, user_select, debug_mode=enable_debug_mode)


# ---------------------------------------------------------------------------------------------------------------------
#%% Catalog existing snapshot data

# Start 'fake' database for accessing snapshot/object data
snap_db = Snap_DB(cameras_folder_path, camera_select, user_select)
obj_db = Object_DB(cameras_folder_path, camera_select, user_select, task_select)
class_db = Classification_DB(cameras_folder_path, camera_select, user_select, task_select)

# Post snapshot/object/classification data to the databases on start-up
post_snapshot_report_metadata(cameras_folder_path, camera_select, user_select, snap_db)
post_object_report_metadata(cameras_folder_path, camera_select, user_select, task_select, obj_db)
post_object_classification_data(cameras_folder_path, camera_select, user_select, task_select, class_db)


# ---------------------------------------------------------------------------------------------------------------------
#%% Ask user for time window

# Get the maximum range of the data (based on the snapshots, because that's the most we could show)
earliest_datetime, latest_datetime = snap_db.get_bounding_datetimes()
snap_wh = snap_db.get_snap_frame_wh()

# Ask the user for the range of datetimes to use for selecting data
start_dt, end_dt, _, _ = user_input_datetime_range(earliest_datetime, 
                                                   latest_datetime, 
                                                   enable_debug_mode)

# Get all the snapshot times we'll need for animation
snap_time_ms_list = snap_db.get_all_snapshot_times_by_time_range(start_dt, end_dt)
num_snaps = len(snap_time_ms_list)

# Get playback timing information
start_snap_time_ms = snap_time_ms_list[0]
end_snap_time_ms = snap_time_ms_list[-1]
total_ms_duration = end_snap_time_ms - start_snap_time_ms
playback_progress = lambda current_time_ms: (current_snap_time_ms - start_snap_time_ms) / total_ms_duration

# ---------------------------------------------------------------------------------------------------------------------
#%% Load object data

# Get object metadata from the server
obj_metadata_generator = obj_db.load_metadata_by_time_range(task_select, start_dt, end_dt)

# Create list of 'reconstructed' objects based on object metadata, so we can work/interact with the object data
obj_list = Obj_Recon.create_reconstruction_list(obj_metadata_generator,
                                                snap_wh,
                                                start_dt, 
                                                end_dt,
                                                smoothing_factor = 0.005)

# Load in classification data, if any
set_object_classification_and_colors(class_db, task_select, obj_list)


# ---------------------------------------------------------------------------------------------------------------------
#%% Data playback

# Create timebar to show playback location
snap_width, snap_height = snap_wh
timebar_height = 20
blank_timebar = np.full((timebar_height, snap_width, 3), (40, 40, 40), dtype=np.uint8)
tb_pt1 = lambda playback_pos: (playback_pos, -10)
tb_pt2 = lambda playback_pos: (playback_pos, timebar_height + 10)

# Get full frame sizing
full_frame_height = snap_height + timebar_height
full_frame_wh = (snap_width, full_frame_height)
timebar_normalized_y_thresh = snap_height / full_frame_height

# Create window for display
hover_callback = Hover_Callback(full_frame_wh)
window_title = "Replay"
disp_window = Simple_Window(window_title)
disp_window.attach_callback(hover_callback)

# Some control feedback (hacky/hard-coded for now)
print("",
      "Controls:",
      "  Press 1 to set video looping start point",
      "  Press 2 to set video looping end point",
      "  Press 0 to reset start/end looping points",
      "",
      "  Press spacebar to pause/unpause",
      "  Use left/right arrow keys to step forward backward",
      "  Use up/down arrow keys to change playback speed",
      "",
      "  While playing, click on the timebar to change playback position",
      "",
      "Press Esc to close", "", sep="\n")

# Label keycodes for convenience
esc_key = 27
spacebar = 32
left_arrow, up_arrow, right_arrow, down_arrow = 81, 82, 83, 84
zero_key, one_key, two_key = 48, 49, 50

# Set up simple playback controls
pause_mode = False
pause_frame_delay = 150
play_frame_delay = 50
use_frame_delay_ms = lambda pause_mode: pause_frame_delay if pause_mode else play_frame_delay
start_idx = 0
end_idx = num_snaps

# Create initial timebar base image, which includes highlights for playback region
timebar_base = redraw_timebar_base(blank_timebar, start_idx, end_idx, num_snaps)

# Loop over snapshot times to generate the playback video
snap_idx = 0
while True:
    
    # Get the next snap time
    current_snap_time_ms = snap_time_ms_list[snap_idx]
    
    # Check for mouse clicks to update timebar position
    if hover_callback.clicked():
        mouse_x, mouse_y = hover_callback.mouse_xy(normalized=True)
        clicked_in_timebar = (mouse_y > (snap_height / full_frame_height))
        if clicked_in_timebar:
            snap_idx = int(round(mouse_x * num_snaps))
    
    # Load each snapshot image & draw object annoations over top
    snap_image, snap_frame_idx = snap_db.load_snapshot_image(current_snap_time_ms)    
    for each_obj in obj_list:
        each_obj.draw_trail(snap_image, snap_frame_idx, current_snap_time_ms)
        each_obj.draw_outline(snap_image, snap_frame_idx, current_snap_time_ms)
        
    # Draw the timebar image with playback indicator
    playback_px = int(round(playback_progress(current_snap_time_ms) * (snap_width - 1)))
    timebar_image = timebar_base.copy()
    timebar_image = cv2.rectangle(timebar_image, tb_pt1(playback_px), tb_pt2(playback_px), (255, 255, 255), 1)
    
    # Display the snapshot image, but stop if the window is closed
    combined_image = np.vstack((snap_image, timebar_image))
    winexists = disp_window.imshow(combined_image)
    if not winexists:
        break
    
    # Awkwardly handle keypresses
    keypress = cv2.waitKey(use_frame_delay_ms(pause_mode))
    if keypress == esc_key:
        break
    
    elif keypress == spacebar:
        pause_mode = not pause_mode
        
    elif keypress == left_arrow:
        pause_mode = True
        snap_idx = snap_idx - 1
    elif keypress == right_arrow:
        pause_mode = True
        snap_idx = snap_idx + 1
        
    elif keypress == up_arrow:
        play_frame_delay = max(1, play_frame_delay - 5)
    elif keypress == down_arrow:
        play_frame_delay = min(1000, play_frame_delay + 5)
        
    elif keypress == one_key:
        start_idx = snap_idx
        timebar_base = redraw_timebar_base(blank_timebar, start_idx, end_idx, num_snaps)
    elif keypress == two_key:
        end_idx = snap_idx
        timebar_base = redraw_timebar_base(blank_timebar, start_idx, end_idx, num_snaps)
    elif keypress == zero_key:
        start_idx = 0
        end_idx = num_snaps
        timebar_base = redraw_timebar_base(blank_timebar, start_idx, end_idx, num_snaps)
    
    # Update the snapshot index with looping
    if not pause_mode:
        snap_idx += 1
    if snap_idx >= end_idx or snap_idx < start_idx:
        snap_idx = start_idx

# Clean up
cv2.destroyAllWindows()


# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap

# TODO:
# - add timebar indicator to show when objects are present
# - add smoothing controls (at least enabled/disable)
# - handle object timing/frame index matching better...
#       - When data is reset (i.e. multiple captures) frame index is also reset!
#       - frame index reset causes errors in replay, due to duplicate index values
#       - need to add additional check on snap timing, to filter out objects not in correct time range

