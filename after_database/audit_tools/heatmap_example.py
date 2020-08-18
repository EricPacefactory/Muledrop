#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Dec  6 15:17:14 2019

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

from local.lib.ui_utils.cli_selections import Resource_Selector
from local.lib.ui_utils.screen_info import Screen_Info

from local.offline_database.file_database import launch_dbs, close_dbs_if_missing_data
from local.offline_database.object_reconstruction import Smoothed_Object_Reconstruction as Obj_Recon
from local.offline_database.object_reconstruction import create_trail_frame_from_object_reconstruction
from local.offline_database.snapshot_reconstruction import median_background_from_snapshots
from local.offline_database.classification_reconstruction import create_objects_by_class_dict, get_ordered_object_list

from local.lib.ui_utils.local_ui.windows_base import Simple_Window

from local.eolib.utils.colormaps import apply_colormap, inferno_colormap
from local.eolib.utils.cli_tools import Datetime_Input_Parser as DTIP


# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes

class Hover_Callback:
    
    # .................................................................................................................
    
    def __init__(self):
        
        self._mouse_xy = np.int32((0, 0))
    
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

def build_trail_heatmaps(obj_by_class_dict, final_frame_wh, downscale_factor = 2, trail_thickness = 5):
    
    # Hard-code scaling
    frame_width, frame_height = final_frame_wh
    trailscale_width = int(round(frame_width / downscale_factor))
    trailscale_height = int(round(frame_height / downscale_factor))
    frame_scaling = np.float32((trailscale_width - 1, trailscale_height - 1))
    
    # Create empty frame to use as a starting point for the heatmap of each class label
    blank_frame = np.zeros((trailscale_height, trailscale_width), dtype = np.float32)

    # Create heatmaps for each class separately
    class_heat_frame_dict = {}    
    for each_class_label, each_obj_dict in obj_by_class_dict.items():
        
        # Create a new blank frame to store heatmap, per class
        class_heat_frame = blank_frame.copy()
        
        # Draw trail data of each object into the class frame
        for each_obj_id, each_obj_ref in each_obj_dict.items():
            
            # Get object trail in pixel co-ords so we can 'paint' it onto the heatmap
            trail_xy_px = np.int32(np.round(frame_scaling * each_obj_ref.trail_xy))
            
            # 'Add' object trail to existing trail heatmap data, so overlapping trails accumulate heat
            new_blank_trail = blank_frame.copy()
            new_blank_trail = cv2.polylines(new_blank_trail, [trail_xy_px], False, 1, trail_thickness, cv2.LINE_AA)
            class_heat_frame += new_blank_trail
        
        # Store finished heat map, per class
        class_heat_frame_dict[each_class_label] = class_heat_frame
    
    return class_heat_frame_dict

# .....................................................................................................................

def create_colored_heatmaps_dict(class_heat_frame_dict, final_frame_wh, minimum_heat_scale = 15):
    
    colored_heat_frame_dict = {}
    for each_class_label, trail_heat in class_heat_frame_dict.items():
    
        # Scale to get a valid uint8 image (grayscale)
        max_trail_heat = np.max(trail_heat)
        max_trail_heat = max(max_trail_heat, minimum_heat_scale)    # Avoid silly results when little data is present
        scaled_heat_frame = np.uint8(255 * trail_heat / max_trail_heat)
        
        # Apply a colormap to the heatmap for visualization
        cmap = inferno_colormap()
        colored_heat = apply_colormap(scaled_heat_frame, cmap)
        resized_heat = cv2.resize(colored_heat, dsize = final_frame_wh, interpolation = cv2.INTER_NEAREST)
        
        colored_heat_frame_dict[each_class_label] = resized_heat
        
    return colored_heat_frame_dict

# .....................................................................................................................

def create_heatmap_windows_dict(screen_wh, final_frame_wh, obj_by_class_dict, mouse_callback,
                                x_spacing = 50, y_spacing = 50):
    
    # Get screen & frame dimensions for convenience
    screen_width, screen_height = screen_wh
    frame_width, frame_height = final_frame_wh
    
    # Figure out where to place the 'column' of heatmaps
    screen_x_offset = (screen_width / 2) + (x_spacing * 2)
    frame_x_offset = frame_width + (x_spacing * 2)
    x_offset = min(screen_x_offset, frame_x_offset)
    
    # Create heatmap windows
    heatmap_window_dict = {}
    for each_idx, each_class_label in enumerate(obj_by_class_dict.keys()):
        
        # Calculate y position of each heatmap, so they 'stack' on each other
        y_offset = y_spacing + (2 * y_spacing * each_idx)
        
        # Create windows
        window_name = "{} Heatmap".format(each_class_label.capitalize())
        heat_window = Simple_Window(window_name, frame_wh = final_frame_wh).move_corner_pixels(x_offset, y_offset)
        heat_window.attach_callback(mouse_hover)
        
        # Store windows in dictionary based on class labels, so we can recall them later
        heatmap_window_dict[each_class_label] = heat_window
        
    return heatmap_window_dict

# .....................................................................................................................

def draw_mouse_location(frame, mouse_xy, line_color = (0, 255, 0), line_thickness = 1,
                        radius = 15, line_type = cv2.LINE_AA):
    
    display_frame = frame.copy()
    cv2.circle(display_frame, tuple(mouse_xy), radius, line_color, line_thickness, line_type)
    
    return display_frame

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Make selections

enable_debug_mode = False

# Create selector so we can access existing report data
selector = Resource_Selector()
project_root_path = selector.get_project_root_pathing()

# Select data to run
location_select, location_select_folder_path = selector.location(debug_mode = enable_debug_mode)
camera_select, _ = selector.camera(location_select, debug_mode = enable_debug_mode)

# Get screen size so we know where to place windows
screen_info = Screen_Info(project_root_path)
screen_width, screen_height = screen_info.screen("width", "height")
screen_wh = (screen_width, screen_height)


# ---------------------------------------------------------------------------------------------------------------------
#%% Catalog existing data

snap_db, obj_db, class_db = launch_dbs(location_select_folder_path, camera_select,
                                       "snapshots", "objects", "classifications")

# Catch missing data
close_dbs_if_missing_data(snap_db, error_message_if_missing = "No snapshot data in the database!")
close_dbs_if_missing_data(obj_db, error_message_if_missing = "No object trail data in the database!")


# ---------------------------------------------------------------------------------------------------------------------
#%% Ask user for time window

# Get the maximum range of the data (based on the snapshots, because all we can show)
earliest_datetime, latest_datetime = snap_db.get_bounding_datetimes()

# Ask the user for the range of datetimes to use for selecting data
user_start_dt, user_end_dt = DTIP.cli_prompt_start_end_datetimes(earliest_datetime, latest_datetime,
                                                                 print_help_before_prompt = False,
                                                                 debug_mode = enable_debug_mode)

# Provide feedback about the selected time range
DTIP.print_start_end_time_range(user_start_dt, user_end_dt)


# ---------------------------------------------------------------------------------------------------------------------
#%% Create background frame

# Ask database for several snapshot images, so we can 'average' them to make a background frame for display
bg_frame = median_background_from_snapshots(snap_db, user_start_dt, user_end_dt, 10)
frame_height, frame_width = bg_frame.shape[0:2]
frame_wh = (frame_width, frame_height)


# ---------------------------------------------------------------------------------------------------------------------
#%% Load object data

# Get object metadata from the server
obj_metadata_generator = obj_db.load_metadata_by_time_range(user_start_dt, user_end_dt)

# Create dictionary of 'reconstructed' objects based on object metadata
obj_dict = Obj_Recon.create_reconstruction_dict(obj_metadata_generator,
                                                frame_wh,
                                                user_start_dt,
                                                user_end_dt)

# Organize objects by class label -> then by object id (nested dictionaries)
obj_id_list, obj_by_class_dict, obj_id_to_class_dict = create_objects_by_class_dict(class_db, obj_dict)

# Get an ordered list of the objects for drawing
ordered_obj_list = get_ordered_object_list(obj_id_list, obj_by_class_dict, obj_id_to_class_dict)


# ---------------------------------------------------------------------------------------------------------------------
#%% Create initial images

# Generate the background display frame, containing all object trails
trails_background = create_trail_frame_from_object_reconstruction(bg_frame, ordered_obj_list)

# Generate heatmaps
class_heat_frame_dict = build_trail_heatmaps(obj_by_class_dict, frame_wh)
colored_heat_frame_dict = create_colored_heatmaps_dict(class_heat_frame_dict, frame_wh)


# ---------------------------------------------------------------------------------------------------------------------
#%% Display
    
# Create mouse positioning callback
mouse_hover = Hover_Callback()

# Create displays
bg_window = Simple_Window("Background").move_corner_pixels(50, 50)
bg_window.attach_callback(mouse_hover)
heatmap_window_dict = create_heatmap_windows_dict(screen_wh, frame_wh, obj_by_class_dict, mouse_hover)

# Some control feedback (hacky/hard-coded for now)
print("", "Press Esc to close", "", sep="\n", flush = True)

# For convenience
frame_delay_ms = 60
esc_key = 27

try:
    while True:
        
        # Get the mouse positioning for displaying mouse location
        mouse_xy = mouse_hover.mouse_xy(normalized = False)
        
        # Display the background with the mouse hover indicator
        bg_winexists = bg_window.imshow(draw_mouse_location(bg_frame, mouse_xy))
        
        # Display each class-specific heatmap, with mouse positioning indicator
        heat_winexists = False
        for each_class_label, each_heatmap in colored_heat_frame_dict.items():
            heat_window = heatmap_window_dict[each_class_label]            
            display_frame = draw_mouse_location(each_heatmap, mouse_xy)
            display_frame = cv2.addWeighted(display_frame, 1.15, bg_frame, 0.35, 0.0)
            winexists = heat_window.imshow(display_frame)
            if winexists:
                heat_winexists = True
                
        # Close if all windows are closed
        if not (bg_winexists or heat_winexists):
            break
        
        # Read keypress to cancel
        keypress = cv2.waitKey(frame_delay_ms)
        if keypress == esc_key:
            break

except KeyboardInterrupt:
    print("Keyboard interrupt! Closing...")


# Clean up
cv2.destroyAllWindows()


# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap

# TODO:
# - Add masking, so overly active areas can be ignored!
# - Provide control over heatmap generation
# - Need to improve visualization of dwell time vs. overlapping trails
# - Better window placement/sizing, especially when there are lots of classes or large snapshot images
# - Add a way to save images?

