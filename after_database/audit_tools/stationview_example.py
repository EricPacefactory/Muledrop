#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jul 12 09:07:39 2020

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
from local.lib.ui_utils.screen_info import Screen_Info

from local.lib.audit_tools.playback import Snapshot_Playback, Corner_Timestamp, get_playback_line_coords
from local.lib.audit_tools.mouse_interaction import Drag_Callback, Row_Based_Footer_Interactions
from local.lib.audit_tools.mouse_interaction import Reference_Image_Mouse_Interactions

from local.offline_database.file_database import launch_dbs, close_dbs_if_missing_data
from local.offline_database.station_reconstruction import Station_Raw_Bars_Display, Station_Zone_Display
from local.offline_database.station_reconstruction import create_reconstruction_dict, load_station_configs

from local.eolib.utils.cli_tools import Datetime_Input_Parser as DTIP


# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes

class Station_Reference_Mouse_Interactions(Reference_Image_Mouse_Interactions):
    
    '''
    Custom class used to bundle logic/state associated with mouse interactions involving the
    'large' station data reference image, which itself is used to set playback looping start/end points
    '''
    
    # .................................................................................................................
    
    def __init__(self, drag_callback_reference, minimum_drag_length_norm = 0.002):
        
        # Inherit from parent
        super().__init__(drag_callback_reference, minimum_drag_length_norm)
    
    # .................................................................................................................
    
    def redraw_images(self, reference_bars_base_img, station_data_display_ref,
                      draw_subset_lines, subset_start_norm, subset_end_norm, subset_bar_wh):
        
        # Draw/clear subset indicator lines on reference image
        ref_bars_img = reference_bars_base_img.copy()
        if draw_subset_lines:
            self.draw_reference_subset_lines(ref_bars_img, subset_start_norm, subset_end_norm)
        
        # Re-draw the subset image
        subset_bars_base_img, _ = station_data_display_ref.create_combined_bar_subset_image(subset_start_norm,
                                                                                            subset_end_norm,
                                                                                            *subset_bar_wh)
        
        return ref_bars_img, subset_bars_base_img
    
    # .................................................................................................................
    # .................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

# .....................................................................................................................

def parse_stationview_args():
    
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

def get_corrected_time_range(snapshot_db, station_db, user_start_dt, user_end_dt):
    
    # Get the range of times from each db based on user input
    snap_times_ms_list = snap_db.get_all_snapshot_times_by_time_range(user_start_dt, user_end_dt)
    stn_start_times_ms_list = stn_db.get_all_station_start_times_by_time_range(user_start_dt, user_end_dt)
    
    # Figure out bounding snap & station metadata (based on user time range)
    start_snap_md = snap_db.load_snapshot_metadata_by_ems(snap_times_ms_list[0])
    end_snap_md = snap_db.load_snapshot_metadata_by_ems(snap_times_ms_list[-1])
    start_stn_md = stn_db.load_metadata_by_ems(stn_start_times_ms_list[0])
    end_stn_md = stn_db.load_metadata_by_ems(stn_start_times_ms_list[-1])
    
    # Figure out bounding times
    start_snap_time_ms = start_snap_md["epoch_ms"]
    end_snap_time_ms = end_snap_md["epoch_ms"]
    start_stn_time_ms = start_stn_md["first_epoch_ms"]
    end_stn_time_ms = end_stn_md["final_epoch_ms"]
    
    # Get the 'minimal' bounding times
    shared_start_time_ms = max(start_snap_time_ms, start_stn_time_ms)
    shared_end_time_ms = min(end_snap_time_ms, end_stn_time_ms)
    
    return shared_start_time_ms, shared_end_time_ms

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Get script arguments

timestamp_pos_arg, enable_relative_timestamp = parse_stationview_args()


# ---------------------------------------------------------------------------------------------------------------------
#%% Make selections

enable_debug_mode = False

# Create selector so we can access existing report data
selector = Resource_Selector()
project_root_path = selector.get_project_root_pathing()

# Select data to run
location_select, location_select_folder_path = selector.location(debug_mode = enable_debug_mode)
camera_select, _ = selector.camera(location_select, debug_mode = enable_debug_mode)


# ---------------------------------------------------------------------------------------------------------------------
#%% Get screen sizing

# Get screen sizing so we can set up 'big' displays
screen_width, screen_height = Screen_Info(project_root_path).screen("width", "height")

# Hard-code a padding to use for avoiding display elements being location right up against screen boundaries
screen_pad_x = 80
screen_pad_y = 100


# ---------------------------------------------------------------------------------------------------------------------
#%% Catalog existing data

# Load standard datasets
caminfo_db, cfginfo_db, snap_db, stn_db = launch_dbs(location_select_folder_path, camera_select,
                                                     "camera_info", "config_info", "snapshots", "stations")

# Catch missing data
close_dbs_if_missing_data(snap_db, error_message_if_missing = "No snapshot data in the database!")
close_dbs_if_missing_data(stn_db, error_message_if_missing = "No station data in the database!")

# Get the maximum range of the data (based on the snapshots, because that's the most we could show)
earliest_datetime, latest_datetime = snap_db.get_bounding_datetimes()
snap_wh = caminfo_db.get_snap_frame_wh()
snap_width, snap_height = snap_wh
snap_shape = (snap_height, snap_width, 3)

# Get all camera start/stop windows. We only want to show station data for one of these periods at a time
camera_start_ems_list = caminfo_db.get_all_start_ems()
print("DEBUG - NEED TO IMPLEMENT CAMERA INFO START/STOP SEGMENT CHECK")
# -> NEED TO FIX CAMERA INFO START TIMES SO THAT THEY MATCH SNAPSHOT/DATA TIMINGS

# If more than one camera on/off period exists in the data, prompt user to select one of these times for display
more_than_one_data_sequence = (len(camera_start_ems_list) > 1)
if more_than_one_data_sequence:
    # NEED TO DO SOMETHING THAT WILL ALTER THE SNAPSHOT TIMES THAT GET LOADED, SO ONLY ONE SEGMENT IS AVAILABLE!
    pass


# ---------------------------------------------------------------------------------------------------------------------
#%% Ask user for time window

# Ask the user for the range of datetimes to use for selecting data
user_start_dt, user_end_dt = DTIP.cli_prompt_start_end_datetimes(earliest_datetime, latest_datetime,
                                                                 print_help_before_prompt = False,
                                                                 debug_mode = enable_debug_mode)

# Provide feedback about the selected time range
DTIP.print_start_end_time_range(user_start_dt, user_end_dt)

# Get corrected times, based on whether we have enough snapshot/station data
shared_start_time_ms, shared_end_time_ms = get_corrected_time_range(snap_db, stn_db, user_start_dt, user_end_dt)

# Get all the snapshot times we'll need for animation
snap_times_ms_list = snap_db.get_all_snapshot_times_by_time_range(shared_start_time_ms, shared_end_time_ms)
num_snaps = len(snap_times_ms_list)
avg_snap_period_ms = np.median(np.diff(snap_times_ms_list))

# Get playback timing information
start_snap_time_ms = snap_times_ms_list[0]
end_snap_time_ms = snap_times_ms_list[-1]
total_duration_ms = end_snap_time_ms - start_snap_time_ms

# Get frame index bounds
first_snap_md = snap_db.load_snapshot_metadata_by_ems(start_snap_time_ms)
final_snap_md = snap_db.load_snapshot_metadata_by_ems(end_snap_time_ms)
global_first_frame_index = first_snap_md["frame_index"]
global_final_frame_index = final_snap_md["frame_index"]
global_total_frames = (1 + global_final_frame_index - global_first_frame_index)


# ---------------------------------------------------------------------------------------------------------------------
#%% Load station data & generate plots

# Load in all station data for display
all_station_data_dict = create_reconstruction_dict(stn_db, start_snap_time_ms, end_snap_time_ms,
                                                   global_first_frame_index, global_final_frame_index)

# Create object for handling display bar creation & get the built-in display name order
stn_data_display = Station_Raw_Bars_Display(all_station_data_dict)
ordered_station_names_list = stn_data_display.get_ordered_station_names_list()
num_stations = len(ordered_station_names_list)

# Construct large 'reference' bar image (used to show data over full time range)
ref_bar_wh = ((screen_width -  2 * screen_pad_x), 25)
ref_bars_base_img, ref_img_height = stn_data_display.create_combined_bar_image(*ref_bar_wh)
ref_frame_wh = (ref_bar_wh[0], ref_img_height)

# Create initial station base image, which may be re-drawn for reduced subset playback
subset_bar_wh = (snap_width, 21)
subset_bars_base_img, subset_img_height = stn_data_display.create_combined_bar_subset_image(0, 1, *subset_bar_wh)

# Load & setup zone data for display
all_stn_config_dict = load_station_configs(cfginfo_db)
stn_zone_display = Station_Zone_Display(ordered_station_names_list, all_stn_config_dict, snap_wh)


# ---------------------------------------------------------------------------------------------------------------------
#%% Set up displays

# Figure out sizing & location of reference display
ref_window_x = screen_pad_x
ref_window_y = screen_height - ref_img_height - screen_pad_y

# Create a window for displaying station data as a reference
ref_drag_callback = Drag_Callback(ref_frame_wh)
ref_window_title = "Reference Station Data"
ref_window = Simple_Window(ref_window_title, provide_mouse_xy = True)
ref_window.attach_callback(ref_drag_callback)
ref_window.move_corner_pixels(ref_window_x, ref_window_y)
ref_window.imshow(ref_bars_base_img)

# Get full frame sizing of the animated window
anim_total_frame_height = snap_height + subset_img_height
anim_frame_wh = (snap_width, anim_total_frame_height)

# Figure out where to place the animation display
anim_window_x = int(round((screen_width - snap_width) / 2))
anim_window_y = screen_pad_y

# Create a window for displaying animated image
anim_drag_callback = Drag_Callback(anim_frame_wh)
anim_window_title = "Stations"
disp_window = Simple_Window(anim_window_title)
disp_window.attach_callback(anim_drag_callback)
disp_window.move_corner_pixels(anim_window_x, anim_window_y)


# ---------------------------------------------------------------------------------------------------------------------
#%% Print controls

# Some control feedback
print("",
      "  Click & drag on the large reference image to set a time range",
      "  Right click the image to reset time range settings",
      "",
      "  Press spacebar to pause/unpause",
      "  Use left/right arrow keys to step forward backward",
      "  Use up/down arrow keys to change playback speed",
      "  (can alternatively use 'wasd' keys)",
      "",
      "  While playing, click on the timebar to change playback position",
      "",
      "Press Esc to close", "", sep="\n")


# ---------------------------------------------------------------------------------------------------------------------
#%% Data playback

# Set up object to handle drawing playback timestamps
cnr_timestamp = Corner_Timestamp(snap_shape, timestamp_pos_arg, user_start_dt, enable_relative_timestamp)

# Set up object to handle basic footer interactions for the animated display
anim_footer_helper = Row_Based_Footer_Interactions(snap_height, subset_img_height, num_footer_rows = num_stations)

# Set up object to handle reference image interactions, which can alter playback looping points
ref_img_interact = Station_Reference_Mouse_Interactions(ref_drag_callback)
ref_img_interact.set_subset_line_colors(fg_line_color = (0, 255, 255))

# Set up object to handle playback/keypresses
playback_ctrl = Snapshot_Playback(num_snaps, avg_snap_period_ms)

# Loop over snapshot times to generate the playback video
while True:
    
    # Get snapshot indexing from playback
    snap_idx = playback_ctrl.get_snapshot_index()
    start_snap_loop_idx, end_snap_loop_idx = playback_ctrl.get_loop_indices()
    
    # Get the next snap time
    current_snap_time_ms = snap_times_ms_list[snap_idx]
    
    # Check for mouse clicks to update timebar positioning
    anim_mx, anim_my = anim_drag_callback.mouse_xy(normalized = True)
    mouse_is_over_anim_bars = anim_footer_helper.mouse_over_footer(anim_my)
    if mouse_is_over_anim_bars:
        
        # Adjust playback position with left click/drag
        if anim_drag_callback.left_down():
            snap_idx = playback_ctrl.adjust_snapshot_index_from_mouse(anim_mx)
        
        # Reset playback to beginning with right click
        if anim_drag_callback.right_clicked():
            snap_idx = start_snap_loop_idx
    
    # Load each snapshot metadata & image 
    snap_md = snap_db.load_snapshot_metadata_by_ems(current_snap_time_ms)
    snap_image, snap_frame_idx = snap_db.load_snapshot_image(current_snap_time_ms)
    
    # If a mouse hovers a station's bar, draw the corresponding station zone 
    if mouse_is_over_anim_bars:
        anim_bar_idx = anim_footer_helper.get_footer_row_index(anim_my)
        stn_zone_display.draw_zone_by_index(snap_image, anim_bar_idx)
    
    # Draw playback line indicator onto the station bars image
    playback_px = playback_ctrl.playback_as_pixel_location(snap_width, snap_idx, start_snap_loop_idx, end_snap_loop_idx)
    play_pt1, play_pt2 = get_playback_line_coords(playback_px, subset_img_height)
    anim_bars_image = subset_bars_base_img.copy()
    anim_bars_image = cv2.line(anim_bars_image, play_pt1, play_pt2, (255, 255, 255), 1)
    
    # Draw timestamp to indicate help playback position
    cnr_timestamp.draw_timestamp(snap_image, snap_md)
    
    # Display the snapshot image, but stop if the window is closed
    combined_image = np.vstack((snap_image, anim_bars_image))
    winexists = disp_window.imshow(combined_image)
    if not winexists:
        break
    
    # Handle mouse interactions with the (larger) reference image
    need_to_update_base_images, draw_subset_lines, subset_start_norm, subset_end_norm = ref_img_interact.update()
    if need_to_update_base_images:
        
        # Update playback looping indices, based on reference image interactions
        start_snap_loop_idx = int(round(num_snaps * subset_start_norm))
        end_snap_loop_idx = int(round(num_snaps * subset_end_norm))
        snap_idx = start_snap_loop_idx
        
        # Force faster playback updates to avoid inconsistent feeling when adjusting subset changes
        playback_ctrl.force_fast_frame()
        
        # Re-draw both the reference image (with subset line indicators) and
        # the 'base' station bar subset image which is shown as part of the animated display
        ref_bars_img, subset_bars_base_img = \
        ref_img_interact.redraw_images(ref_bars_base_img, stn_data_display,
                                       draw_subset_lines, subset_start_norm, subset_end_norm, subset_bar_wh)
        
        # Force a window display update here, so we don't continuously have to do this otherwise
        ref_window.imshow(ref_bars_img)
    
    # Update playback control variables, which may have been modified elsewhere
    playback_ctrl.set_snapshot_index(snap_idx)
    playback_ctrl.set_loop_indices(start_snap_loop_idx, end_snap_loop_idx)
    
    # Handle keypresses
    keypress = cv2.waitKey(playback_ctrl.frame_delay_ms)
    req_break = playback_ctrl.update_playback(keypress)
    if req_break:
        break

# Clean up
cv2.destroyAllWindows()


# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap

# TODO:
# - get camera info segments working (i.e. don't allow data loaded over multi-reset events!)
# - clean up time range matching (snapshots with station data)
# - add ability to switch between full-scale color mapping vs. relative (i.e. min/max) mapping?
# - add ability to modify colors and/or even apply basic sig. processing??? (better for alternate tool)
