#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Dec 11 16:04:39 2020

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

from local.lib.audit_tools.mouse_interaction import Hover_Callback
from local.lib.audit_tools.playback import Snapshot_Playback, Corner_Timestamp

from local.offline_database.file_database import launch_dbs, close_dbs_if_missing_data
from local.offline_database.object_reconstruction import Smooth_Hover_Object_Reconstruction, Hover_Mapping
from local.offline_database.object_reconstruction import create_trail_frame_from_object_reconstruction
from local.offline_database.snapshot_reconstruction import median_background_from_snapshots
from local.offline_database.classification_reconstruction import create_objects_by_class_dict, get_ordered_object_list

from local.lib.ui_utils.local_ui.windows_base import Simple_Window

from local.eolib.utils.cli_tools import Datetime_Input_Parser as DTIP
from local.eolib.video.text_rendering import normalized_text


# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes

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
    

class Hover_Colorprop_Object(Smooth_Hover_Object_Reconstruction):
    
    # Hard-code display colors corresponding to proportion data
    proportion_bgr_colors = [(0,0,0), (255,255,255),        # Black, white
                             (0,0,255), (0,235,235),        # Red, yellow
                             (0, 235, 0), (235, 235, 0),    # Green, cyan
                             (235, 0, 0), (235, 0, 235)]    # Blue, magenta
    
    # .................................................................................................................
    
    def __init__(self, object_metadata, frame_wh, global_start_datetime_isoformat, global_end_datetime_isoformat,
                 smoothing_factor = 0.015, timebar_row_height = 30):
        
        # Inherit from parent class
        super().__init__(object_metadata, frame_wh, global_start_datetime_isoformat, global_end_datetime_isoformat,
                         smoothing_factor)
        
        # Get color proportion data from object metadata
        imaging_data = object_metadata.get("imaging", {})
        color_prop_list = imaging_data.get("color_proportions", None)
        self.has_color_data = (color_prop_list is not None)
        
        # Store color proportion data
        color_prop_array = np.int32(color_prop_list) if self.has_color_data else None
        self.color_prop_array = color_prop_array
    
    # .................................................................................................................
    
    def hover_highlight(self, trails_frame, colorbar_blank_frame):
        
        ''' Helper function for applying both trail highlighting & colorbar display'''
        
        return self.highlight_trail(trails_frame), self.draw_colorbar(colorbar_blank_frame)
    
    # .................................................................................................................
    
    def is_hovering_timebar(self, x_point_normalized, row_index):
        
        ''' Helper function to check if mouse is hovering over the object timebar '''
        
        # If we're not on the correct row, we aren't being hovered!
        if row_index != self._tbar_row_index:
            return False
        
        return self.relative_start < x_point_normalized <= self.relative_end
    
    # .................................................................................................................
    
    def draw_color_playback_indicator(self, colorbar_frame, snap_frame_index,
                                      line_fg_color = (255,255,255), line_bg_color = (0,0,0),
                                      line_type = cv2.LINE_4):
        
        ''' Function used to draw vertical playback indicator onto the colorbar display during animations '''
        
        # Don't draw anything if the object didn't exist yet!
        start_idx = self.start_idx
        end_idx = self.end_idx        
        idx_in_range = start_idx <= snap_frame_index <= end_idx
        if not idx_in_range:
            return colorbar_frame
        
        # Make copy of colorbar so we don't destroy the original
        display_frame = colorbar_frame.copy()
        frame_height, frame_width = display_frame.shape[0:2]
        
        # Figure out where to draw the playback indicator
        idx_as_fraction = (snap_frame_index - start_idx) / (end_idx - start_idx)
        x_px = int(round((frame_width - 1) * idx_as_fraction))
        pt1 = (x_px, -5)
        pt2 = (x_px, frame_height + 5)
        
        # Draw playback indicator with foreground/background coloring
        cv2.line(display_frame, pt1, pt2, line_bg_color, 2, line_type)
        cv2.line(display_frame, pt1, pt2, line_fg_color, 1, line_type)
        
        return display_frame
    
    # .................................................................................................................
    
    def draw_colorbar(self, colorbar_frame):
        
        ''' Function used to create a colorbar image (from color proportion data) '''
        
        # Get bar sizing, so we can output the proper sized image
        bar_height, bar_width = colorbar_frame.shape[0:2]
        bar_wh = (bar_width, bar_height)
        
        # Bail if there is no color data
        if not self.has_color_data:
            blank_frame = np.full((bar_height, bar_width, 3), (40, 40, 40), dtype = np.uint8)
            _, colorbar_frame = normalized_text(blank_frame, "No color data!", (0.5, 0.5), color = (10, 80, 255))
            return colorbar_frame
        
        # Draw each of the proportion values as separate 'blocks' with bars representing proportion sizing
        block_frames = []
        for each_proportion_entry in self.color_prop_array:
            new_block_frame = self._draw_one_proportion_block(each_proportion_entry)
            block_frames.append(new_block_frame)
        
        # Stack all color proporation visuals side-by-side and scale to fit displayed image
        colorbar_frame = np.hstack(block_frames)
        colorbar_frame = cv2.resize(colorbar_frame, dsize = bar_wh, interpolation = cv2.INTER_NEAREST)
        
        return colorbar_frame
    
    # .................................................................................................................
    
    def _draw_one_proportion_block(self, proportion_data, block_height = 50, interpolation_type = cv2.INTER_NEAREST):
        
        '''
        Function used to draw a single entry of color proportion data
        Many single entries can be drawn and stacked together for visualization
        '''
        
        # For clarity
        block_width = 1
        block_wh = (block_width, block_height)
        
        # Calculate the height of each (independently!) drawn segment
        segment_heights = np.int32(np.round(block_height * proportion_data / sum(proportion_data)))
        
        # Build up output block by stacking solidly colored segments on top of one another
        segments_list = []
        for each_color, each_seg_height in zip(self.proportion_bgr_colors, segment_heights):
            
            # Skip missing/overly small segments
            if each_seg_height < 1:
                continue
        
            # Create new solid color block for each color and add to list
            segment_shape = (each_seg_height, block_width, 3)
            new_segment = np.full(segment_shape, each_color, dtype = np.uint8)
            segments_list.append(new_segment)
        
        # Resize to target block sizing, in case segments are missing/rounding changes the size
        block_frame = cv2.resize(np.vstack(segments_list), dsize = block_wh, interpolation = interpolation_type)
        
        return block_frame
    
    # .................................................................................................................
    # .................................................................................................................
    

# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

# .....................................................................................................................

def show_looping_animation(snapshot_database, object_database, object_ref, colorbar_frame,
                           start_buffer_time_sec = 3.0, end_buffer_time_sec = 5.5):
    
    # Figure out the time range to animate over
    earliest_time_ems = object_ref.start_ems
    latest_time_ems = object_ref.end_ems
    
    # Set up buffer times (used to extend animation range to include time before/after object existence)
    start_buffer_time_ms = int(start_buffer_time_sec * 1000.0)
    end_buffer_time_ms = int(end_buffer_time_sec * 1000.0)
    
    # Make sure we don't reach for snapshots out of the snapshot time range
    earliest_snap_ems, latest_snap_ems = snapshot_database.get_bounding_epoch_ms()
    earliest_time_ems = max(earliest_snap_ems, earliest_time_ems - start_buffer_time_ms)
    latest_time_ems = min(latest_snap_ems, latest_time_ems + end_buffer_time_ms)
    
    # Get all the snapshot times we'll need for animation
    anim_snapshot_times_ms = snapshot_database.get_all_snapshot_times_by_time_range(earliest_time_ems, latest_time_ems)
    num_snaps = len(anim_snapshot_times_ms)
    avg_snap_period_ms = np.median(np.diff(anim_snapshot_times_ms))
    
    # Set up the display window
    window_title = "Object {}".format(object_ref.full_id)
    anim_window = Simple_Window(window_title)
    anim_window.move_corner_pixels(x_pixels = 400, y_pixels = 200)
    
    # Set up object to handle drawing playback timestamps
    example_snap, _ = snapshot_database.load_snapshot_image(earliest_snap_ems)
    cnr_timestamp = Corner_Timestamp(example_snap.shape, "br", None)
    
    # Set up object to handle playback/keypresses
    playback_ctrl = Snapshot_Playback(num_snaps, avg_snap_period_ms, default_playback_timelapse_factor = 8)
    
    # Loop over snapshots to animate infinitely
    while True:
        
        # Get snapshot indexing from playback
        snap_idx = playback_ctrl.get_snapshot_index()
        start_snap_loop_idx, end_snap_loop_idx = playback_ctrl.get_loop_indices()
        
        # Get current snap time
        current_snap_time_ms = anim_snapshot_times_ms[snap_idx]
        
        # Get each snapshot and draw all outlines/trails for all objects in the frame
        snap_md = snap_db.load_snapshot_metadata_by_ems(current_snap_time_ms)
        snap_image, snap_frame_idx = snapshot_database.load_snapshot_image(current_snap_time_ms)
        
        # Draw object trail/outline data
        object_ref.draw_trail(snap_image, snap_frame_idx, current_snap_time_ms)
        object_ref.draw_outline(snap_image, snap_frame_idx, current_snap_time_ms)
        
        # Draw timestamp to indicate help playback position
        cnr_timestamp.draw_timestamp(snap_image, snap_md)
        
        # Draw playback position indicator on to the colorbar
        color_bar_ind = object_ref.draw_color_playback_indicator(colorbar_frame, snap_frame_idx)
        
        # Display the snapshot image, but stop if the window is closed
        combined_frame = np.vstack((snap_image, color_bar_ind))
        winexists = anim_window.imshow(combined_frame)
        if not winexists:
            break
        
        # Handle keypresses
        keypress = cv2.waitKey(playback_ctrl.frame_delay_ms)
        req_break = playback_ctrl.update_playback(keypress)
        if req_break:
            break
    
    # Get rid of animation widow before leaving
    anim_window.close()
    
    return

# .....................................................................................................................
# .....................................................................................................................


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
obj_dict = Hover_Colorprop_Object.create_reconstruction_dict(obj_metadata_generator,
                                                             frame_wh,
                                                             user_start_dt,
                                                             user_end_dt)

# Organize objects by class label -> then by object id (nested dictionaries)
obj_id_list, obj_by_class_dict, obj_id_to_class_dict = create_objects_by_class_dict(class_db, obj_dict)

# Get an ordered list of the objects for drawing
ordered_obj_list = get_ordered_object_list(obj_id_list, obj_by_class_dict, obj_id_to_class_dict)

# Generate trail hover mapping, for quicker mouse-to-trail lookup
hover_map = Hover_Mapping(obj_by_class_dict)


# ---------------------------------------------------------------------------------------------------------------------
#%% Create initial images

# Generate the background display frame, containing all object trails
trails_background = create_trail_frame_from_object_reconstruction(bg_frame, ordered_obj_list)

# Create background bar frame for drawing color proportion info
bar_height = 50
bar_bg_color = (40,40,40)
bar_background = np.full((bar_height, frame_width, 3), bar_bg_color, dtype=np.uint8)


# ---------------------------------------------------------------------------------------------------------------------
#%% Interaction loop

# Close any previously open windows
cv2.destroyAllWindows()

# Set up mouse interaction callbacks
trail_hover_callback = Hover_Callback(frame_wh)
cb_sequencer = Callback_Sequencer("trails", trail_hover_callback, frame_wh)

# Set up main display window
disp_window = Simple_Window("Color Data Viewer")
disp_window.attach_callback(cb_sequencer)
disp_window.move_corner_pixels(50, 50)
print("", "Press Esc to close", "", sep= "\n", flush = True)

while True:
    
    # Make clean copies of the frames to display, so we don't muddy up the originals
    display_frame = trails_background.copy()
    colorbar_frame = bar_background.copy()
    
    # Respond to trail hovering, if active
    if cb_sequencer.is_active("trails"):
        
        # Get relative mouse co-ords
        mouse_xy = trail_hover_callback.mouse_xy()
        closest_trail_dist, closest_obj_id, closest_obj_class = hover_map.closest_point(mouse_xy)
        
        # Highlight the closest trail/timebar segment if the mouse is close enough
        if closest_trail_dist < 0.05:
            obj_ref = obj_by_class_dict[closest_obj_class][closest_obj_id]
            display_frame, colorbar_frame = obj_ref.hover_highlight(display_frame, colorbar_frame)
            
            # Play an animation if the user clicks on the highlighted trail
            if trail_hover_callback.left_clicked():
                show_looping_animation(snap_db, obj_db, obj_ref, colorbar_frame)
    
    # Show final display
    combined_frame = np.vstack((display_frame, colorbar_frame))
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

