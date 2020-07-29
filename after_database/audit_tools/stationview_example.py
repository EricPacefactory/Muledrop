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

from collections import defaultdict

from local.lib.ui_utils.cli_selections import Resource_Selector

from local.lib.ui_utils.local_ui.windows_base import Simple_Window

from local.lib.common.timekeeper_utils import isoformat_to_datetime, fake_datetime_like

from local.lib.file_access_utils.configurables import unpack_config_data

from local.offline_database.file_database import launch_dbs, close_dbs_if_missing_data

from local.eolib.utils.cli_tools import Datetime_Input_Parser as DTIP
from local.eolib.utils.colormaps import create_interpolated_colormap
from local.eolib.video.imaging import image_1ch_to_3ch, color_list_to_image, vstack_padded
from local.eolib.video.text_rendering import position_frame_relative, position_center, font_config, simple_text


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

def create_single_station_bar_image(snap_width, station_name, station_data_list, bar_fg_color,
                                    bar_height = 21, font_scale = 0.35, bar_bg_color = (40, 40, 40)):
    
    # Return a blank image if no data is available
    no_data = (len(station_data_list) == 0)
    if no_data:
        blank_bar = np.full((bar_height, snap_width, 3), bar_bg_color, dtype = np.uint8)
        return blank_bar
    
    # For clarity
    bar_wh = (snap_width, bar_height)
    
    # Convert to array for convenience, and figure out if we're dealing with multichannel data or not
    data_array = np.int32(station_data_list)
    data_shape = data_array.shape
    num_channels = 1 if (len(data_shape) == 1) else data_shape[1]
    
    # Assume 3-channel data is RGB, so reverse it to BGR for display
    if num_channels == 1:
        resized_data_img = _create_1_channel_bar_image(data_array, bar_wh, bar_fg_color, bar_bg_color)
    elif num_channels == 3:
        resized_data_img = _create_3_channel_bar_image(data_array, bar_wh)
    else:
        resized_data_img = _create_n_channel_bar_image(data_array, bar_wh, bar_fg_color, bar_bg_color)
    
    # Figure out where to place the text
    spaced_station_name = station_name.replace("_", " ")
    bg_font_config_dict = font_config(scale = font_scale, color = bar_bg_color, thickness = 2)
    fg_font_config_dict = font_config(scale = font_scale)
    bar_y_center = (bar_height / 2)
    _, text_y = position_center(spaced_station_name, (0, bar_y_center), **fg_font_config_dict)
    
    # Draw station name on to the bar (with background outline)
    resized_data_img = simple_text(resized_data_img, spaced_station_name, (5, text_y), **bg_font_config_dict)
    resized_data_img = simple_text(resized_data_img, spaced_station_name, (5, text_y), **fg_font_config_dict)

    return resized_data_img

# .....................................................................................................................

def _create_1_channel_bar_image(data_array, bar_wh, bar_fg_color, bar_bg_color,
                                interpolation_type = cv2.INTER_NEAREST):
    
    ''' Helper function used to create station bar images when the data is single-channeled (i.e. 1D) '''
    
    # Get min/max data value, to use for determining bar scale
    data_min = np.min(data_array)
    data_max = np.max(data_array)
    if data_max == data_min:
        data_max = data_min + 1
    
    # Normalize data to 0-255 range for display & create color scale
    norm_data = np.uint8(np.round(255 * ((data_array - data_min) / (data_max - data_min))))
    bgr_dict = {0: bar_bg_color, 255: bar_fg_color}
    cmap = create_interpolated_colormap(bgr_dict)
    
    # Convert normalized data array to an image
    data_gray_img = image_1ch_to_3ch(color_list_to_image(norm_data))
    data_bar_img = cv2.LUT(data_gray_img, cmap)
    resized_data_img = cv2.resize(data_bar_img, dsize = bar_wh, interpolation = interpolation_type)
    
    return resized_data_img

# .....................................................................................................................

def _create_3_channel_bar_image(data_array, bar_wh, interpolation_type = cv2.INTER_NEAREST):
    
    ''' Helper function used to create station bar images where data is 3D, which is assumed to be RGB '''
    
    # Flip data to be BGR for OpenCV display
    data_bgr = np.uint8(np.flip(data_array, axis = 1))
    
    # Convert the data to an image format, with the desired target sizing for display
    data_as_1px_img = np.expand_dims(data_bgr, axis = 0)
    resized_data_img = cv2.resize(data_as_1px_img, dsize = bar_wh, interpolation = interpolation_type)
    
    return resized_data_img

# .....................................................................................................................

def _create_n_channel_bar_image(data_array, bar_wh, bar_fg_color, bar_bg_color, interpolation_type = cv2.INTER_NEAREST):
    
    '''
    Helper function used to create station bar images when the number of channels is not 1 or 3
    in these cases, the display is somewhat ambiguous, so the channel data is just shown stacked separately,
    within a single bar
    '''
    
    # Figure out the separate bar sizing so we get a correctly size 'single' bar as an output
    num_channels = data_array.shape[1]
    spacer_height_px = 2
    num_1px_spacers = (num_channels - 1)
    bar_width, bar_height = bar_wh
    single_height = int(np.floor((bar_height - spacer_height_px * num_1px_spacers) / num_channels))
    single_wh = (bar_width, single_height)
    
    # Create images for each data channel
    channel_image_list = []
    for each_data_channel in np.rollaxis(data_array, 1):
        new_channel_bar = _create_1_channel_bar_image(each_data_channel, single_wh,
                                                      bar_fg_color, bar_bg_color,
                                                      interpolation_type)
        channel_image_list.append(new_channel_bar)
    
    # Create a single bar out of each of the channels for display
    combined_channel_bars = vstack_padded(*channel_image_list,
                                          pad_height = spacer_height_px,
                                          prepend_separator = False,
                                          append_separator = False)
    
    # Finally, resize the combined bars to be the correct target size
    resized_data_img = cv2.resize(combined_channel_bars, dsize = bar_wh, interpolation = cv2.INTER_NEAREST)
    
    return resized_data_img

# .....................................................................................................................

def create_combined_station_bars_image(station_name_order_list, stations_images_dict):
    
    # Create combined image with all station plots
    image_list = [stations_images_dict[each_name] for each_name in station_name_order_list]
    combined_station_bars = vstack_padded(*image_list,
                                          pad_height = 3,
                                          prepend_separator = True,
                                          append_separator = True)
    
    # Figure out combined bar height, for use with playback indicator
    combined_bar_height = combined_station_bars.shape[0]
    
    return combined_station_bars, combined_bar_height

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

def redraw_station_base(original_stations_image, start_idx, end_idx, max_idx, knock_out_color = (20,20,20)):
    
    ''' Helper function for blanking out regions of the playback bars, when looping over shorter sections '''
    
    # Don't do anything if a subset of the timeline hasn't been selected
    if start_idx == 0 and end_idx == max_idx:
        return original_stations_image
    
    # Create a copy so we don't ruin the original
    return_image = original_stations_image.copy()
    
    # Get frame sizing so we know where to draw everything
    frame_height, frame_width = original_stations_image.shape[0:2]
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

def draw_station_zone(display_frame, station_zone_px,
                      line_color = (255, 0, 255), thickness = 2, line_type = cv2.LINE_8):
    
    is_closed = True
    cv2.polylines(display_frame, [station_zone_px], is_closed, line_color, thickness, line_type)
    
    return display_frame

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

# Select data to run
location_select, location_select_folder_path = selector.location(debug_mode = enable_debug_mode)
camera_select, _ = selector.camera(location_select, debug_mode = enable_debug_mode)


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

# Get all camera start/stop windows. We only want to show station data for one of these periods at a time
camera_start_ems_list = caminfo_db.get_all_start_ems()
print("DEBUG - NEED TO IMPLEMENT CAMERA START/STOP SEGMENT CHECK")
# -> NEED TO FIX FILE START TIMES SO THAT THEY MATCH SNAPSHOT/DATA TIMINGS

# If more than one camera on/off period exists in the data, prompt user to select one of these times for display
more_than_one_data_sequence = (len(camera_start_ems_list) > 1)
if more_than_one_data_sequence:
    # NEED TO DO SOMETHING THAT WILL ALTER THE SNAPSHOT TIMES THAT GET LOADED, SO ONLY A SEGMENT IS AVAILABLE!
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

# Get playback timing information
start_snap_time_ms = snap_times_ms_list[0]
end_snap_time_ms = snap_times_ms_list[-1]
total_duration_ms = end_snap_time_ms - start_snap_time_ms

# Get frame index bounds
first_snap_md = snap_db.load_snapshot_metadata_by_ems(start_snap_time_ms)
final_snap_md = snap_db.load_snapshot_metadata_by_ems(end_snap_time_ms)
global_first_frame_index = first_snap_md["frame_index"]
global_final_frame_index = final_snap_md["frame_index"]


# ---------------------------------------------------------------------------------------------------------------------
#%% Load station data

all_station_metadata_gen = stn_db.load_metadata_by_time_range(start_snap_time_ms, end_snap_time_ms)

# Join all data in the provided range together in a single continuous list (for each station)
first_frame_index = 1E20
final_frame_index = -1
all_station_data_dict = defaultdict(list)
for each_data_segment_dict in all_station_metadata_gen:
    
    # Decide if we need to trim the start of the loaded station data (based on snapshot time range)
    segment_first_index = each_data_segment_dict["first_frame_index"]
    trim_first = (segment_first_index < global_first_frame_index)
    first_offset = 0
    if trim_first:
        first_offset = (global_first_frame_index - segment_first_index - 1)
    
    # Decide if we need to trim the end of the loaded station data (based on snapshot time range)
    segment_final_index = each_data_segment_dict["final_frame_index"]
    trim_final = (segment_final_index > global_final_frame_index)
    final_offset = segment_final_index
    if trim_final:
        final_offset = (global_final_frame_index - segment_final_index)
    
    # Accumulate data from all stations, with trimming if needed
    station_data_dict = each_data_segment_dict["stations"]
    for each_station_name, each_station_data_list in station_data_dict.items():
        all_station_data_dict[each_station_name] += (each_station_data_list[first_offset: final_offset])


# ---------------------------------------------------------------------------------------------------------------------
#%% Generate plot data

# Hard-code a set of colors to use for station bars 
station_colors_list = [(65, 95, 185), (209, 225, 114), (255, 204, 255), (28, 22, 168),
                       (164, 255, 150), (0, 105, 208), (173, 170, 23), (127, 216, 251)]
num_colors = len(station_colors_list)

# Get station names in alphabetical order, for display/lookup consistency
station_name_order_list = sorted(all_station_data_dict.keys())

station_bar_imgs_dict = {}
for each_stn_idx, each_station_name in enumerate(station_name_order_list):
    
    # Figure out each station color
    color_idx_select = (1 + each_stn_idx) % num_colors
    station_color_select = station_colors_list[color_idx_select]
    
    # Generate a bar image based on station data & add to storage
    each_data_list = all_station_data_dict[each_station_name]
    station_bar_img = create_single_station_bar_image(snap_width, each_station_name, each_data_list,
                                                      station_color_select)
    station_bar_imgs_dict[each_station_name] = station_bar_img

# Combine all station images together
combined_station_bars, combined_bar_height = \
create_combined_station_bars_image(station_name_order_list, station_bar_imgs_dict)


# ---------------------------------------------------------------------------------------------------------------------
#%% Load station zone data

# Load the appropriate configuration data (HACK FOR NOW, LOAD ALL AND PICK 'NEWEST')
all_config_dict = cfginfo_db.get_all_config_info()
newest_config_dict = all_config_dict[-1]
all_stations_config_dict = newest_config_dict.get("config", {}).get("stations", {})

# Get frame scaling so we can draw (normalized) zone co-ords onto the displayed image data
zone_px_scaling = np.float32((snap_width - 1, snap_height - 1))

# Try to find the 'zones' for each station
station_zones_px_dict = {}
for each_station_name in station_name_order_list:
    
    # Try to load the config data for each individual station
    each_station_config_dict = all_stations_config_dict.get(each_station_name, None)
    no_config_data = (each_station_config_dict is None)
    if no_config_data:
        continue
    
    # Break apart the configuration to get the setup data, so we can look for zone definitions
    _, setup_data_dict = unpack_config_data(each_station_config_dict)
    each_station_zone_list = setup_data_dict.get("station_zones_list", None)
    no_zone_data = (each_station_zone_list is None)
    if no_zone_data:
        continue
    
    # If we got zone data, convert it to pixel co-ordindates for drawing and save it
    each_zone_norm_array = np.float32(each_station_zone_list)
    each_zone_px_array = np.int32(np.round(each_zone_norm_array * zone_px_scaling))
    station_zones_px_dict[each_station_name] = each_zone_px_array


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

# Set up function for checking if we're in the bars display
num_stations = len(station_name_order_list)
bar_y_level = (snap_height / full_frame_height)
check_mouse_over_bars = lambda mouse_y: (mouse_y > bar_y_level)
get_bar_hover_y_norm = lambda mouse_y: (mouse_y - bar_y_level) / (1.0 - bar_y_level)

# Create window for display
hover_callback = Hover_Callback(full_frame_wh)
window_title = "Stations"
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

# Create initial station base image, which may be re-drawn for reduced subset playback
stations_base = redraw_station_base(combined_station_bars, start_idx, end_idx, num_snaps)

# Loop over snapshot times to generate the playback video
snap_idx = 0
while True:
    
    # Get the next snap time
    current_snap_time_ms = snap_times_ms_list[snap_idx]
    
    # Check for mouse clicks to update timebar position
    mouse_x, mouse_y = hover_callback.mouse_xy(normalized=True)
    mouse_is_over_bars = check_mouse_over_bars(mouse_y)
    if hover_callback.clicked():
        if mouse_is_over_bars:
            snap_idx = int(round(mouse_x * num_snaps))
    
    # Load each snapshot image & draw object annoations over top
    snap_md = snap_db.load_snapshot_metadata_by_ems(current_snap_time_ms)
    snap_image, snap_frame_idx = snap_db.load_snapshot_image(current_snap_time_ms)
    
    # If a mouse hovers a station's bar, draw the corresponding station zone 
    if mouse_is_over_bars:
        bar_y_norm = get_bar_hover_y_norm(mouse_y)
        bar_idx = np.clip(int(num_stations * bar_y_norm), 0, num_stations - 1)
        hover_station_name = station_name_order_list[bar_idx]
        hover_station_zone_px = station_zones_px_dict[hover_station_name]
        draw_station_zone(snap_image, hover_station_zone_px)
    
    # Draw the timebar image with playback indicator
    playback_px = get_playback_pixel_location(start_snap_time_ms, end_snap_time_ms, current_snap_time_ms,
                                              snap_width, total_time = total_duration_ms)
    play_pt1, play_pt2 = get_playback_line_coords(playback_px, combined_bar_height)
    stations_image = stations_base.copy()
    stations_image = cv2.line(stations_image, play_pt1, play_pt2, (255, 255, 255), 1)
    
    # Draw timestamp over replay image, if needed
    timestamp_image = draw_timestamp(snap_image, snap_md, fg_font_config, bg_font_config,
                                     user_start_dt, enable_relative_timestamp, timestamp_xy)
    
    # Display the snapshot image, but stop if the window is closed
    combined_image = np.vstack((snap_image, stations_image))
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
        stations_base = redraw_station_base(combined_station_bars, start_idx, end_idx, num_snaps)
    elif keypress == two_key:
        end_idx = snap_idx
        stations_base = redraw_station_base(combined_station_bars, start_idx, end_idx, num_snaps)
    elif keypress == zero_key:
        start_idx = 0
        end_idx = num_snaps
        stations_base = redraw_station_base(combined_station_bars, start_idx, end_idx, num_snaps)
    
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
# - redraw station names after using 1/2 segment looping which may cut off the original text
#   -> would be nice to draw names on left/right depending on where 1/2 chop occurs!
# - add ability to switch between full-scale color mapping vs. relative (i.e. min/max) mapping?
# - add ability to see zoomed/masked stations??? Hard to do, better for another tool (e.g. detailed station analysis)
# - provide graph of zone data over time? (again maybe better to do in another tool)

