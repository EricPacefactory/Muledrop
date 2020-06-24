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

import argparse
import cv2
import numpy as np

from local.lib.ui_utils.cli_selections import Resource_Selector

from local.lib.ui_utils.local_ui.windows_base import Simple_Window

from local.lib.common.timekeeper_utils import isoformat_to_datetime, fake_datetime_like

from local.offline_database.file_database import launch_file_db, close_dbs_if_missing_data
from local.offline_database.object_reconstruction import Smoothed_Object_Reconstruction as Obj_Recon
from local.offline_database.classification_reconstruction import create_objects_by_class_dict, get_ordered_object_list

from local.eolib.utils.cli_tools import Datetime_Input_Parser as DTIP
from local.eolib.utils.colormaps import create_interpolated_colormap
from local.eolib.video.imaging import image_1d_to_3d, color_list_to_image, vstack_padded
from local.eolib.video.text_rendering import position_frame_relative, font_config, simple_text


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

def parse_replay_args():
    
    # Set defaults
    default_timestamp_pos = "br"
    default_relative_timestamp = False
    
    # Set up argument parsing
    ap = argparse.ArgumentParser(formatter_class = argparse.RawTextHelpFormatter)
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
    arg_timestamp_position = args["timestamp_position"]
    arg_relative_timestamp = args["relative_timestamp"]
    
    return arg_timestamp_position, arg_relative_timestamp

# .....................................................................................................................

def get_class_count_lists(snap_db, obj_by_class_dict):

    # Get counts for each class separately
    objclass_count_lists_dict = {each_class_label: [] for each_class_label in obj_by_class_dict.keys()}
    for each_snap_time_ms in snap_times_ms_list:
        
        # Get snapshot timing info
        snap_md = snap_db.load_snapshot_metadata_by_ems(each_snap_time_ms)
        snap_epoch_ms = snap_md["epoch_ms"]
        
        # Count up all the objects on each frame, for each class label
        for each_class_label, each_obj_dict in obj_by_class_dict.items():
            objclass_count = 0
            for each_obj_id, each_obj_ref in each_obj_dict.items():
                is_on_snap = each_obj_ref.exists_at_target_time(snap_epoch_ms)
                if is_on_snap:
                    objclass_count += 1
            
            # Record the total count for each class label separately
            objclass_count_lists_dict[each_class_label].append(objclass_count)
    
    return objclass_count_lists_dict

# .....................................................................................................................

def create_density_images(class_db, objclass_count_lists_dict, snap_width, 
                          density_bar_height = 16, bar_bg_color = (40, 40, 40)):
    
    # Return a blank image if no class data is available
    density_images_dict = {each_class_label: None for each_class_label in obj_by_class_dict.keys()}
    if not objclass_count_lists_dict:
        blank_bar = np.full((density_bar_height, snap_width, 3), bar_bg_color, dtype = np.uint8)
        density_images_dict["unclassified"] = blank_bar

    # Create images to be appended to display, per class label
    _, _, all_label_colors_dict = class_db.get_label_color_luts()
    
    # Create a single row density image, for each class label separately
    for each_class_label, each_count_list in objclass_count_lists_dict.items():
        
        # Create scaled color map for each class label, with max count corresponding to full class color
        max_count = max(each_count_list)
        max_count = max(1, max_count)
        count_bgr_dict = {0: bar_bg_color, max_count: all_label_colors_dict[each_class_label]}
        count_cmap = create_interpolated_colormap(count_bgr_dict)
        
        # Convert count list to an image
        count_gray_img = image_1d_to_3d(color_list_to_image(each_count_list))
        count_image_bar = cv2.LUT(count_gray_img, count_cmap)
        
        # Resize the count image to match the snapshots (for stacking) and apply color map
        resized_density_image_bar = cv2.resize(count_image_bar, dsize = (snap_width, density_bar_height))
        density_images_dict[each_class_label] = resized_density_image_bar

    return density_images_dict

# .....................................................................................................................

def create_combined_density_image(density_images_dict):
    
    # Create combined image with all density plots
    image_list = [each_img for each_img in density_images_dict.values()]
    combined_density_bars = vstack_padded(*image_list, 
                                          pad_height = 3, 
                                          prepend_separator = True, 
                                          append_separator = True)
    
    # Figure out combined bar height, for use with playback indicator
    combined_bar_height = combined_density_bars.shape[0]
    
    return combined_density_bars, combined_bar_height

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Playback helper functions

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

def get_playback_pixel_location(start_time, end_time, current_time, frame_width, total_time = None):
    
    ''' Helper function for converting time into horizontal pixel location (for drawing timing onto playback bar) '''
    
    if total_time is None:
        total_time = end_time - start_time
    playback_progress = (current_time - start_time) / total_time
    
    playback_position_px = int(round(playback_progress * (frame_width - 1)))
    
    return playback_position_px

# .....................................................................................................................

def get_playback_line_coords(playback_position_px, playback_bar_height):
    
    ''' Helper function for generating the two points needed to indicate the playback position '''
    
    pt1 = (playback_position_px, -5)
    pt2 = (playback_position_px, playback_bar_height + 5)
    
    return pt1, pt2

# .....................................................................................................................

def redraw_density_base(original_density_image, start_idx, end_idx, max_idx, knock_out_color = (20,20,20)):
    
    ''' Helper function for blanking out regions of the playback back, when looping over shorter sections '''
    
    # Don't do anything if a subset of the timeline hasn't been selected
    if start_idx == 0 and end_idx == max_idx:
        return original_density_image
    
    # Create a copy so we don't ruin the original
    return_image = original_density_image.copy()
    
    # Get frame sizing so we know where to draw everything
    frame_height, frame_width = original_density_image.shape[0:2]
    width_scale = frame_width - 1
    
    # Calculate starting/ending points of the highlighted playback region
    x_start_px = int(round(width_scale * start_idx / max_idx))
    x_end_px = int(round(width_scale * end_idx / max_idx))
    
    # Draw starting knockout (if needed)
    if start_idx > 0:
        pt_s1 = (0, 0)
        pt_s2 = (x_start_px, frame_height + 10)
        cv2.rectangle(return_image, pt_s1, pt_s2, knock_out_color, -1)
    
    # Draw ending knockout (if needed)
    if end_idx < max_idx:
        pt_e1 = (x_end_px, 0)
        pt_e2 = (frame_width, frame_height + 10)
        cv2.rectangle(return_image, pt_e1, pt_e2, knock_out_color, -1)
    
    return return_image

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Get script arguments

timestamp_pos_arg, enable_relative_timestamp = parse_replay_args()

# ---------------------------------------------------------------------------------------------------------------------
#%% Make selections

enable_debug_mode = False

# Create selector so we can access existing report data
selector = Resource_Selector()
project_root_path, cameras_folder_path = selector.get_cameras_root_pathing()

# Select the camera to show data for (needs to have saved report data already!)
camera_select, camera_path = selector.camera(debug_mode = enable_debug_mode)


# ---------------------------------------------------------------------------------------------------------------------
#%% Catalog existing data

cinfo_db, snap_db, obj_db, class_db, summary_db = \
launch_file_db(cameras_folder_path, camera_select,
               launch_snapshot_db = True,
               launch_object_db = True,
               launch_classification_db = True,
               launch_summary_db = False)

# Catch missing data
close_dbs_if_missing_data(snap_db, error_message_if_missing = "No snapshot data in the database!")

# Get the maximum range of the data (based on the snapshots, because that's the most we could show)
earliest_datetime, latest_datetime = snap_db.get_bounding_datetimes()
snap_wh = cinfo_db.get_snap_frame_wh()
snap_width, snap_height = snap_wh


# ---------------------------------------------------------------------------------------------------------------------
#%% Ask user for time window

# Ask the user for the range of datetimes to use for selecting data
user_start_dt, user_end_dt = DTIP.cli_prompt_start_end_datetimes(earliest_datetime, latest_datetime,
                                                                 print_help_before_prompt = False,
                                                                 debug_mode = enable_debug_mode)

# Provide feedback about the selected time range
DTIP.print_start_end_time_range(user_start_dt, user_end_dt)

# Get all the snapshot times we'll need for animation
snap_times_ms_list = snap_db.get_all_snapshot_times_by_time_range(user_start_dt, user_end_dt)
num_snaps = len(snap_times_ms_list)

# Get playback timing information
start_snap_time_ms = snap_times_ms_list[0]
end_snap_time_ms = snap_times_ms_list[-1]
total_ms_duration = end_snap_time_ms - start_snap_time_ms


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
#%% Generate density data

# Get counts of each class label over time and generate an image representing the count by color intensity
objclass_count_lists_dict = get_class_count_lists(snap_db, obj_by_class_dict)
density_images_dict = create_density_images(class_db, objclass_count_lists_dict, snap_width)

# Create a combined image from all the class density images
combined_density_bars, combined_bar_height = create_combined_density_image(density_images_dict)


# ---------------------------------------------------------------------------------------------------------------------
#%% Data playback

# Set up timestamp text config, in case it's needed
snap_shape = (snap_height, snap_width, 3)
fg_font_config = font_config(scale = 0.35, color = (255, 255, 255))
bg_font_config = font_config(scale = 0.35, color = (0, 0, 0), thickness = 2)
timestamp_xy = get_timestamp_location(timestamp_pos_arg, snap_shape, fg_font_config)

# Get full frame sizing
full_frame_height = snap_height + combined_bar_height
full_frame_wh = (snap_width, full_frame_height)

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
      "  (can alternatively use 'WASD' keys)",
      "",
      "  While playing, click on the timebar to change playback position",
      "",
      "Press Esc to close", "", sep="\n")

# Label keycodes for convenience
esc_key = 27
spacebar = 32
up_arrow_keys = {82, 119}    # Up or 'w' key
left_arrow_keys = {81, 97}   # Left or 'a' key
down_arrow_keys = {84, 115}  # Down or 's' key
right_arrow_keys = {83, 100} # Right or "d' key
zero_key, one_key, two_key = 48, 49, 50

# Set up simple playback controls
pause_mode = False
pause_frame_delay = 150
play_frame_delay = 50
use_frame_delay_ms = lambda pause_frame_delay, pause_mode: pause_frame_delay if pause_mode else play_frame_delay
start_idx = 0
end_idx = num_snaps

# Create initial density base image, which may be re-drawn for reduced subset playback
density_base = redraw_density_base(combined_density_bars, start_idx, end_idx, num_snaps)

# Loop over snapshot times to generate the playback video
snap_idx = 0
while True:
    
    # Get the next snap time
    current_snap_time_ms = snap_times_ms_list[snap_idx]
    
    # Check for mouse clicks to update timebar position
    if hover_callback.clicked():
        mouse_x, mouse_y = hover_callback.mouse_xy(normalized=True)
        clicked_in_timebar = (mouse_y > (snap_height / full_frame_height))
        if clicked_in_timebar:
            snap_idx = int(round(mouse_x * num_snaps))
    
    # Load each snapshot image & draw object annoations over top
    snap_md = snap_db.load_snapshot_metadata_by_ems(current_snap_time_ms)
    snap_image, snap_frame_idx = snap_db.load_snapshot_image(current_snap_time_ms)    
    for each_obj in ordered_obj_list:
        each_obj.draw_trail(snap_image, snap_frame_idx, current_snap_time_ms)
        each_obj.draw_outline(snap_image, snap_frame_idx, current_snap_time_ms)
        
    # Draw the timebar image with playback indicator
    playback_px = get_playback_pixel_location(start_snap_time_ms, end_snap_time_ms, current_snap_time_ms,
                                              snap_width, total_time = total_ms_duration)
    play_pt1, play_pt2 = get_playback_line_coords(playback_px, combined_bar_height)
    density_image = density_base.copy()
    density_image = cv2.line(density_image, play_pt1, play_pt2, (255, 255, 255), 1)
    
    # Draw timestamp over replay image, if needed
    timestamp_image = draw_timestamp(snap_image, snap_md, fg_font_config, bg_font_config, 
                                     user_start_dt, enable_relative_timestamp, timestamp_xy)
    
    # Display the snapshot image, but stop if the window is closed
    combined_image = np.vstack((snap_image, density_image))
    winexists = disp_window.imshow(combined_image)
    if not winexists:
        break
    
    # Awkwardly handle keypresses
    keypress = cv2.waitKey(use_frame_delay_ms(play_frame_delay, pause_mode))
    if keypress == esc_key:
        break
    
    elif keypress == spacebar:
        pause_mode = not pause_mode
        
    elif keypress in left_arrow_keys:
        pause_mode = True
        snap_idx = snap_idx - 1
    elif keypress in right_arrow_keys:
        pause_mode = True
        snap_idx = snap_idx + 1
        
    elif keypress in up_arrow_keys:
        play_frame_delay = max(1, play_frame_delay - 5)
        snap_idx = snap_idx - 1
    elif keypress in down_arrow_keys:
        play_frame_delay = min(1000, play_frame_delay + 5)
        snap_idx = snap_idx - 1
        
    elif keypress == one_key:
        start_idx = snap_idx
        density_base = redraw_density_base(combined_density_bars, start_idx, end_idx, num_snaps)
    elif keypress == two_key:
        end_idx = snap_idx
        density_base = redraw_density_base(combined_density_bars, start_idx, end_idx, num_snaps)
    elif keypress == zero_key:
        start_idx = 0
        end_idx = num_snaps
        density_base = redraw_density_base(combined_density_bars, start_idx, end_idx, num_snaps)
    
    # Update the snapshot index with looping
    if not pause_mode:
        snap_idx += 1
    if snap_idx >= end_idx:
        snap_idx = start_idx
    elif snap_idx < start_idx:
        snap_idx = end_idx - 1

# Clean up
cv2.destroyAllWindows()


# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap

# TODO:
# - add smoothing controls (at least enabled/disable)
