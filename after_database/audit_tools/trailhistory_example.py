#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Sep 19 16:48:43 2019

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

from itertools import cycle

from local.lib.ui_utils.cli_selections import Resource_Selector

from local.offline_database.file_database import user_input_datetime_range, launch_file_db, close_dbs_if_missing_data
from local.offline_database.object_reconstruction import Smooth_Hover_Object_Reconstruction, Hover_Mapping
from local.offline_database.object_reconstruction import create_trail_frame_from_object_reconstruction
from local.offline_database.snapshot_reconstruction import median_background_from_snapshots
from local.offline_database.classification_reconstruction import set_object_classification_and_colors
from local.offline_database.classification_reconstruction import create_object_class_dict

from local.lib.ui_utils.local_ui.windows_base import Simple_Window

# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes

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


# =====================================================================================================================
# =====================================================================================================================

class Callback_Sequencer:
    
    # .................................................................................................................
    
    def __init__(self, base_callback_label, base_callback_object, frame_wh):
        
        # Create storage for callback objects (by label) so we can retrieve data as needed
        self._callback_lut = {}
        self._active_cb_lut = {}
        
        # Keep track of total frame size so we can determine which region each callback covers
        self._total_frame_width = 0
        self._total_frame_height = 0
        
        # Add base callback object
        self._add_callback(base_callback_label, base_callback_object, *frame_wh)
    
    # .................................................................................................................
    
    def __call__(self, *args, **kwargs):
        self.mouse_callbacks(*args, **kwargs)
    
    # .................................................................................................................
    
    @property
    def _total_frame_size(self):
        return (self._total_frame_width, self._total_frame_height)
    
    # .................................................................................................................
    
    def _add_callback(self, callback_label, callback_object, add_width = 0, add_height = 0):
        
        # Infer starting co-ordinates, based on what is being added
        hstacking = (add_width > 0)
        vstacking = (add_height > 0)
        start_x = self._total_frame_width if hstacking else 0
        start_y = self._total_frame_height if vstacking else 0
        
        # Build up total frame size as needed
        self._total_frame_width += add_width
        self._total_frame_height += add_height
        
        # Determine frame bounds where this callback will be active
        new_x_bounds = (start_x, self._total_frame_width)
        new_y_bounds = (start_y, self._total_frame_height)
        
        # Add callback to lut so we can access it later as needed
        new_lut_entry = {"obj": callback_object, "x_bounds": new_x_bounds, "y_bounds": new_y_bounds}
        self._callback_lut.update({callback_label: new_lut_entry})
        
        # Add entry to active lut
        self._active_cb_lut.update({callback_label: False})
        
    # .................................................................................................................
    
    def add_callback_vstack(self, callback_label, callback_object, frame_wh):
        frame_height = frame_wh[1]        
        self._add_callback(callback_label, callback_object, add_height = frame_height)
        
    # .................................................................................................................
    
    def add_callback_hstack(self, callback_label, callback_object, frame_wh):
        frame_width = frame_wh[0]        
        self._add_callback(callback_label, callback_object, add_width = frame_width)
        
    # .................................................................................................................
    
    def mouse_callbacks(self, event, mx, my, flags, param):
        
        # Reset active state on all callbacks
        for each_label in self._active_cb_lut.keys():
            self._active_cb_lut[each_label] = False
        
        # Loop over each callback region to figure out which one should be called
        for each_label, each_entry in self._callback_lut.items():
            
            x1, x2 = each_entry["x_bounds"]
            y1, y2 = each_entry["y_bounds"]
            if (x1 <= mx < x2) and (y1 <= my < y2):
                self._active_cb_lut[each_label] = True
                mx_offset, my_offset = (mx - x1,  my - y1)
                each_entry["obj"](event, mx_offset, my_offset, flags, param)
                break
            
    # .................................................................................................................
    
    def is_active(self, callback_label):
        return self._active_cb_lut[callback_label]
    
    # .................................................................................................................
    # .................................................................................................................


# =====================================================================================================================
# =====================================================================================================================
    

class Hover_Object(Smooth_Hover_Object_Reconstruction):
    
    # .................................................................................................................
    
    def __init__(self, object_metadata, frame_wh, global_start_datetime_isoformat, global_end_datetime_isoformat,
                 smoothing_factor = 0.015, timebar_row_height = 30):
        
        # Inherit from parent class
        super().__init__(object_metadata, frame_wh, global_start_datetime_isoformat, global_end_datetime_isoformat, 
                         smoothing_factor)
        
        # Store addition timebar drawing sizes & scalings
        self._timebar_row_height = timebar_row_height
        tbar_width_scaling = frame_wh[0] - 1
        
        # Pre-calculate timebar pixel co-ordinates
        self._tbar_x1 = int(np.ceil(self.relative_start * tbar_width_scaling))
        self._tbar_x2 = int(np.floor(self.relative_end * tbar_width_scaling))
        self._tbar_y1 = None
        self._tbar_y2 = None
        self._timebar_tl = None
        self._timebar_br = None
        
    # .................................................................................................................
    
    def set_timebar_row_index(self, class_label_list):
        
        # Store row index, so we can use it later to check if we're hovered
        row_index = class_label_list.index(self._classification_label)
        self._tbar_row_index = row_index
        
        # Calculate timebar y co-ords
        tbar_h = self._timebar_row_height
        self._tbar_y1 = (row_index * tbar_h) + 5
        self._tbar_y2 = ((row_index + 1) * (tbar_h - 1)) - 5
        
        # Calculate timebar rectangle co-ords for drawing
        self._timebar_tl = (self._tbar_x1, self._tbar_y1)
        self._timebar_br = (self._tbar_x2, self._tbar_y2)
    
    # .................................................................................................................
    
    def hover_highlight(self, trails_frame, timebar_frame):
        
        ''' Helper function for applying both trail & timebar highlights '''
        
        return self.highlight_trail(trails_frame), self.highlight_trail_timebar(timebar_frame)
    
    # .................................................................................................................
    
    def is_hovering_timebar(self, x_point_normalized, row_index):
        
        ''' Helper function to check if mouse is hovering over the object timebar '''
        
        # If we're not on the correct row, we aren't being hovered!
        if row_index != self._tbar_row_index:
            return False
        
        return self.relative_start < x_point_normalized <= self.relative_end
    
    # .................................................................................................................
    
    def draw_trail_timebar(self, output_frame, bar_color = None):
        
        if bar_color is None:
            bar_color = self._outline_color
        
        cv2.rectangle(output_frame, 
                      pt1 = self._timebar_tl,
                      pt2 = self._timebar_br, 
                      color = bar_color,
                      thickness = -1,
                      lineType = cv2.LINE_4)
        
        return output_frame
    
    # .................................................................................................................
    
    def highlight_trail_timebar(self, output_frame):
        self.draw_trail_timebar(output_frame, bar_color = (255, 0, 255))
    
    # .................................................................................................................
    # .................................................................................................................
    

# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

# .....................................................................................................................

def create_timebar_frame_object_reconstruction(example_frame, timebar_row_height, object_list, class_count_dict, 
                                               bg_color = (40, 40, 40)):
    
    # Figure out image sizing from example frame and number of classes (rows) needed
    num_classes = len(class_count_dict)
    bar_width = example_frame.shape[1]
    bar_height = num_classes * timebar_row_height
    
    # Set up blank background timebar to draw in to
    bar_background = np.full((bar_height, bar_width, 3), bg_color, dtype=np.uint8)
    
    # Draw separator lines between class rows
    for k in range(num_classes):
        y_line = k * (timebar_row_height) - 1
        cv2.line(bar_background, (-10, y_line), (bar_width + 10, y_line), (25, 25, 25), 1)
    
    # Draw all object timebars (likely overlapping)
    for each_obj in object_list:
        each_obj.draw_trail_timebar(bar_background)
        
    return bar_background

# .....................................................................................................................

def get_hovered_timebars(mouse_x, timebar_row_index_hover, object_reconstructions_list):
    
    # Check which object time bars are being hovered
    obj_indices_hovered_list = []
    for each_idx, each_recon in enumerate(object_reconstructions_list):
        if each_recon.is_hovering_timebar(mouse_x, timebar_row_index_hover):
            obj_indices_hovered_list.append(each_idx)
            
    return obj_indices_hovered_list

# .....................................................................................................................

def show_looping_animation(snapshot_database, object_database, object_list, 
                           start_buffer_time_sec = 3.0, end_buffer_time_sec = 5.5):

    # Don't do anything if there are no objects to animate! (i.e. a blank area was clicked)
    if len(object_list) == 0:
        return
    
    # Figure out the time range to animate over
    earliest_time = np.min([each_obj.start_ems for each_obj in object_list])
    latest_time = np.max([each_obj.end_ems for each_obj in object_list])
    
    # Set up buffer times (used to extend animation range to include time before/after object existence)
    start_buffer_time_ms = int(start_buffer_time_sec * 1000.0)
    end_buffer_time_ms = int(end_buffer_time_sec * 1000.0)
    
    # Make sure we don't reach for snapshots out of the snapshot time range
    earliest_snap, latest_snap = snapshot_database.get_bounding_epoch_ms()
    earliest_time = max(earliest_snap, earliest_time - start_buffer_time_ms)
    latest_time = min(latest_snap, latest_time + end_buffer_time_ms)
    
    # Get all the snapshot times we'll need for animation
    anim_snapshot_times = snapshot_database.get_all_snapshot_times_by_time_range(earliest_time, latest_time)
    
    # Set up the display window
    object_ids_string = ", ".join([str(each_obj.nice_id) for each_obj in object_list])
    obj_prefix = "Object" if len(object_list) < 2 else "Objects:"
    window_title = "{} {}".format(obj_prefix, object_ids_string)
    anim_window = Simple_Window(window_title)
    anim_window.move_corner_pixels(x_pixels = 400, y_pixels = 200)
    
    # Hard-code key code for clarity
    esc_key = 27
    spacebar = 32
    
    # Set up frame delay settings
    playback_frame_delay_ms = 150
    pause_frame_delay_ms = 0
    pause_mode = False    
    
    # Loop over snapshots to animate infinitely
    snap_times_inf_list = cycle(anim_snapshot_times)
    for each_snap_time in snap_times_inf_list:
        
        # Get each snapshot and draw all outlines/trails for all objects in the frame
        snap_image, snap_frame_idx = snapshot_database.load_snapshot_image(each_snap_time)
        for each_obj in object_list:
            each_obj.draw_trail(snap_image, snap_frame_idx, each_snap_time)
            each_obj.draw_outline(snap_image, snap_frame_idx, each_snap_time)
        
        # Display the snapshot image, but stop if the window is closed
        winexists = anim_window.imshow(snap_image)
        if not winexists:
            break
        
        # Wait a bit, and stop if esc key is pressed
        frame_delay_ms = (pause_frame_delay_ms if pause_mode else playback_frame_delay_ms)
        keypress = cv2.waitKey(frame_delay_ms)
        if keypress == esc_key:
            break
        
        # Toggle pausing/unpausing with spacebar
        if keypress == spacebar:
            pause_mode = not pause_mode
    
    # Get rid of animation widow before leaving
    anim_window.close()

# .....................................................................................................................
# .....................................................................................................................

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

cam_db, snap_db, obj_db, class_db, _, _ = \
launch_file_db(cameras_folder_path, camera_select, user_select,
               launch_snapshot_db = True,
               launch_object_db = True,
               launch_classification_db = True,
               launch_summary_db = False,
               launch_rule_db = False)

# Catch missing data
cam_db.close()
close_dbs_if_missing_data(snap_db, obj_db)


# ---------------------------------------------------------------------------------------------------------------------
#%% Ask user for time window

# Get the maximum range of the data (based on the snapshots, because all we can show)
earliest_datetime, latest_datetime = snap_db.get_bounding_datetimes()

# Ask the user for the range of datetimes to use for selecting data
start_dt, end_dt, _, _ = user_input_datetime_range(earliest_datetime, 
                                                   latest_datetime, 
                                                   enable_debug_mode)


# ---------------------------------------------------------------------------------------------------------------------
#%% Create background frame

# Ask database for several snapshot images, so we can 'average' them to make a background frame for display
bg_frame = median_background_from_snapshots(snap_db, start_dt, end_dt, 10)
frame_height, frame_width = bg_frame.shape[0:2]
frame_wh = (frame_width, frame_height)

# Set timebar size
timebar_row_height = 30


# ---------------------------------------------------------------------------------------------------------------------
#%% Load object data

# Get object metadata from the server
obj_metadata_generator = obj_db.load_metadata_by_time_range(start_dt, end_dt)

# Create list of 'reconstructed' objects based on object metadata, so we can work/interact with the object data
obj_list = Hover_Object.create_reconstruction_list(obj_metadata_generator,
                                                   frame_wh,
                                                   start_dt, 
                                                   end_dt,
                                                   timebar_row_height = timebar_row_height)

# Organize objects by class label -> then by object id (nested dictionaries)
objclass_dict = create_object_class_dict(class_db, obj_list)

# Generate trail hover mapping, for quicker mouse-to-trail lookup
hover_map = Hover_Mapping(objclass_dict)


# Load in classification data, if any
class_count_dict = set_object_classification_and_colors(class_db, obj_list)

# Tell each object which class row index it is (for timebar)
class_label_list = list(class_count_dict.keys())
for each_obj in obj_list:
    each_obj.set_timebar_row_index(class_label_list)
num_classes = len(class_label_list)


# ---------------------------------------------------------------------------------------------------------------------
#%% Create initial images

# Generate the background display frame, containing all object trails
trails_background = create_trail_frame_from_object_reconstruction(bg_frame, obj_list)
bar_background = create_timebar_frame_object_reconstruction(bg_frame, timebar_row_height, obj_list, class_count_dict)

# Get timebar final sizing
timebar_image_height = bar_background.shape[0]
timebar_image_wh = (frame_width, timebar_image_height)


# ---------------------------------------------------------------------------------------------------------------------
#%% Interaction loop

# Close any previously open windows
cv2.destroyAllWindows()

# Set up mouse interaction callbacks
trail_hover_callback = Hover_Callback(frame_wh)
bar_hover_callback =  Hover_Callback(timebar_image_wh)
cb_sequencer = Callback_Sequencer("trails", trail_hover_callback, frame_wh)
cb_sequencer.add_callback_vstack("timebar", bar_hover_callback, timebar_image_wh)

# Set up main display window
disp_window = Simple_Window("Display")
disp_window.attach_callback(cb_sequencer)
disp_window.move_corner_pixels(50, 50)
print("", "Press Esc to close", "", sep="\n")

while True:
    
    # Make clean copies of the frames to display, so we don't muddy up the originals
    display_frame = trails_background.copy()
    timebar_frame = bar_background.copy()
    
    # Respond to trail hovering, if active
    if cb_sequencer.is_active("trails"):
        
        # Get relative mouse co-ords
        mouse_xy = trail_hover_callback.mouse_xy()
        closest_trail_dist, closest_obj_id, closest_obj_class = hover_map.closest_point(mouse_xy)
        
        # Highlight the closest trail/timebar segment if the mouse is close enough
        if closest_trail_dist < 0.05:
            obj_ref = objclass_dict[closest_obj_class][closest_obj_id]
            obj_ref.hover_highlight(display_frame, timebar_frame)
            
            # Play an animation if the user clicks on the highlighted trail
            if trail_hover_callback.clicked():
                objs_to_animate_list = [obj_ref]
                show_looping_animation(snap_db, obj_db, objs_to_animate_list)
    
    # Respond to timebar hover, if active
    if cb_sequencer.is_active("timebar"):
        
        # Get relative mouse co-ords
        mouse_x, mouse_y = bar_hover_callback.mouse_xy()
        timebar_row_index_hover = int(np.floor(mouse_y * num_classes))
        hovered_obj_idxs = get_hovered_timebars(mouse_x, timebar_row_index_hover, obj_list)
        
        # Highlight all the timebars being hovered & the corresponding trails
        for each_idx in hovered_obj_idxs:
            obj_list[each_idx].hover_highlight(display_frame, timebar_frame)
    
        # Play an animation if the user clicks on the highlighted timebar section
        if bar_hover_callback.clicked():            
            objs_to_animate_list = [obj_list[each_idx] for each_idx in hovered_obj_idxs]
            show_looping_animation(snap_db, obj_db, objs_to_animate_list)
    
    # Show final display
    combined_frame = np.vstack((display_frame, timebar_frame))
    winexist = disp_window.imshow(combined_frame)
    if not winexist:
        break
    
    # Break on esc key
    keypress = cv2.waitKey(50)
    if keypress == 27:
        break


# Some clean up
cv2.destroyAllWindows()

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap

# TODO/IDEAs
# - add fading to trails that don't start or end near the mouses current location
# - add better control over smoothing
# - add mouse scroll wheel control (on trail hover) that selects between second,third,fourth etc. closest trails
# - add lasso drawing capability to trail hover (i.e. exclude trails outside of lasso region)
# - add input for controling the time bar scale (zooming in/out over time)
# - add playback on spacebar keypress
# - add 1/2 playback boundary controls. Should also adjust to only show trails in boundary! Reset bounds with 0 key
# - would be nice to show time bars separately, with each obj having it's own (thin) bar i.e. no overlapping


