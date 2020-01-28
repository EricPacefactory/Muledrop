#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Dec 19 13:15:44 2019

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

from local.lib.ui_utils.local_ui.windows_base import Simple_Window
from local.lib.ui_utils.local_ui.drawing import Entity_Drawer, waitKey_ex, keycode_quit

from local.offline_database.file_database import launch_file_db, user_input_datetime_range, close_dbs_if_missing_data
from local.offline_database.object_reconstruction import Smooth_Hover_Object_Reconstruction, Hover_Mapping
from local.offline_database.object_reconstruction import create_trail_frame_from_object_reconstruction
from local.offline_database.snapshot_reconstruction import median_background_from_snapshots
from local.offline_database.classification_reconstruction import set_object_classification_and_colors
from local.offline_database.classification_reconstruction import create_object_class_dict

from eolib.video.text_rendering import simple_text, relative_text, position_frame_relative, font_config

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
                 smoothing_factor = 0.015):
        
        # Inherit from parent class
        super().__init__(object_metadata, frame_wh, global_start_datetime_isoformat, global_end_datetime_isoformat, 
                         smoothing_factor)
     
        # Allocate storage for in/out calculation results
        self._in_pct = None
        self._out_pct = None
        self._in_time_sec = None
        self._out_time_sec = None
        
    # .................................................................................................................
    
    def in_out_strings(self):
        
        if self._in_pct is None or self._out_pct is None:
            return None, None
        
        str_format = "{}: {:.0f}% ({:.1f} sec)"
        in_zone_str = str_format.format("in", self._in_pct, self._in_time_sec)
        out_zone_str = str_format.format("out", self._out_pct, self._out_time_sec)
        
        return in_zone_str, out_zone_str
    
    # .................................................................................................................
    
    def in_out_percents(self):
        return self._in_pct, self._out_pct
    
    # .................................................................................................................
    
    def in_out_times(self):
        return self._in_time_sec, self._out_time_sec
    
    # .................................................................................................................
    
    def calculate_in_out_value(self, zones_array_norm):
        
        ''' Function which calculates how many xy points of an object's trail, land inside the given zones '''
        
        # Count all the trail x/y points inside the zone
        in_zone_count = 0
        for each_xy in self.trail_xy:
            for each_zone_array in  zones_array_norm:
                in_zone = (cv2.pointPolygonTest(each_zone_array, tuple(each_xy), True) > 0)
                if in_zone:
                    in_zone_count += 1
                    break
        
        # Calculate in/out zone times & percentages
        in_zone_fraction = in_zone_count / len(self.trail_xy)
        out_zone_fraction = 1.0 - in_zone_fraction
        
        # Store in/out zone calculations
        self._in_pct = int(round(100 * in_zone_fraction))
        self._out_pct = int(round(100 * out_zone_fraction))
        self._in_time_sec = (self.lifetime_ms * in_zone_fraction / 1000.0)
        self._out_time_sec = (self.lifetime_ms * out_zone_fraction / 1000.0)
        
        return self._in_pct, self._out_pct
        
    # .................................................................................................................
    
    def draw_zone_info(self, zones_list_norm, 
                       frame_index = None, frame_width = 640, frame_height = 360, bg_color = (40,40,40)):
        
        # Create a frame to draw in, which matches the 'empty' frame size
        info_frame = np.full((frame_height, frame_width, 3), bg_color, dtype = np.uint8)
        half_height = int(frame_height / 2)
        half_width = int(frame_width / 2)
        
        # Don't do anything if no zones are drawn!
        no_zones = (len(zones_list_norm) == 0)
        if no_zones:
            missing_zone_text = "No zone data! Draw a zone to run analysis"
            simple_text(info_frame, missing_zone_text, (half_width, half_height), center_text = True)
            return info_frame
        
        # Handle animation
        rel_frame_idx = None
        is_animating = (frame_index is not None)
        if is_animating:
            rel_frame_idx = self._rel_index(frame_index)
            rel_frame_idx = min(self.num_samples - 1, rel_frame_idx)
            rel_frame_idx = max(0, rel_frame_idx)
        
        # Generate a time basis
        lifetime_sec = self.lifetime_ms / 1000
        time_samples = np.linspace(0, lifetime_sec, self.num_samples)
        
        # Build a list of points that are in/out of the zone
        in_zone_list = []
        in_zone_count = 0
        for each_xy in self.trail_xy:
            for each_zone_list in  zones_list_norm:
                zone_array = np.float32(each_zone_list)
                in_zone = (cv2.pointPolygonTest(zone_array, tuple(each_xy), True) > 0)
                if in_zone:
                    in_zone_count += 1
                    break
            in_zone_list.append(int(in_zone))
        
        # Calculate in/out zone times & percentages
        in_zone_fraction = in_zone_count / len(in_zone_list)
        out_zone_fraction = 1.0 - in_zone_fraction
        in_zone_time_sec = lifetime_sec * in_zone_fraction
        out_zone_time_sec = lifetime_sec * out_zone_fraction
            
        # Set plot parameters
        x1 = 20
        x2 = (frame_width - x1 - 1)
        y1 = 40 
        y2 = (frame_height - y1 - 1)
        plot_width = (x2 - x1)
        plot_height = (y2 - y1)
        
        
        # Draw graph title & x axis label
        object_title = "Object: {}".format(self.nice_id)
        in_zone_title = "IN: {:.0f}% ({:.1f} sec)".format(100 * in_zone_fraction, in_zone_time_sec)
        out_zone_title = "OUT: {:.0f}% ({:.1f} sec)".format(100 * out_zone_fraction, out_zone_time_sec)
        frame_title_str = "{}  |  {}  |  {}".format(object_title, in_zone_title, out_zone_title)
        simple_text(info_frame, frame_title_str, (half_width, 21), scale = 0.5, center_text = True)
        simple_text(info_frame, "Time", (half_width, y2 + 16), center_text = True)
        
        # Draw graph showing in/out status
        y_max = 1.15
        time_max = np.max(time_samples)
        x_plot = x1 + plot_width * (time_samples / time_max)
        y_plot = y2 - plot_height * (np.int32(in_zone_list) / y_max) - 20
        
        plot_xy = np.int32(np.round(np.vstack((x_plot, y_plot)).T))
        
        cv2.polylines(info_frame, [plot_xy], False, self._outline_color, 1, cv2.LINE_AA)
        cv2.rectangle(info_frame, (x1,y1), (x2,y2), (255, 255, 255), 1)
        relative_text(info_frame, "{:.1f} sec".format(lifetime_sec), (-x1, -y1), scale = 0.35)
        
        # Draw point on curve, if animating
        if is_animating:
            plot_idx = tuple(plot_xy[rel_frame_idx])
            cv2.circle(info_frame, plot_idx, 5, (0, 0, 200), -1, cv2.LINE_AA)
        
        return info_frame
    
    # .................................................................................................................
    # .................................................................................................................


# =====================================================================================================================
# =====================================================================================================================


class Histogram_Plot:
    
    # .................................................................................................................
    
    def __init__(self, objects_in_pct_list, num_bins = 10,
                 frame_width = 640, frame_height = 360, bg_color = (40,40,40)):
        
        # Store histogram parameters
        self.num_bins = num_bins
        self.bin_edges_list, self.bin_centers_list = self._create_bin_lists(num_bins)
        self.histo_counts = np.zeros(num_bins, dtype=np.int64)
        self.total_obj_count = len(objects_in_pct_list)
        self._objects_in_pct_list = objects_in_pct_list
        
        # Store aesthetics
        self._frame_width = frame_width
        self._frame_height = frame_height
        self._bg_color = bg_color
        self._plot_x1 = 20
        self._plot_x2 = (frame_width - self._plot_x1 - 1)
        self._plot_y1 = 35
        self._plot_y2 = (frame_height - self._plot_y1 - 15)
        self._plot_width = (self._plot_x2 - self._plot_x1)
        self._plot_height = (self._plot_y2 - self._plot_y1)
        
        # Draw bg frame for re-use
        self._bg_frame = self._draw_histogram_background_frame()
        self._histogram_frame = self._bg_frame.copy()
        
        # Store callback variables
        self._mouse_moved = False
        self._mouse_clicked = False
        self._mouse_xy = np.array((-10000,-10000))
        self._norm_by_global_max = True

    # .................................................................................................................

    def __call__(self, *args, **kwargs):        
        self._mouse_callback(*args, **kwargs)
    
    # .................................................................................................................
    
    def _mouse_callback(self, event, mx, my, flags, param):
        self._mouse_xy = np.int32((mx, my))
        self._mouse_moved = (event == cv2.EVENT_MOUSEMOVE)
        self._mouse_clicked = (event == cv2.EVENT_LBUTTONDOWN)
        
        # Toggle normalization style with mouse click
        if self._mouse_clicked:
            self._norm_by_global_max = (not self._norm_by_global_max)
            self._update_histogram_frame()

        if (event == cv2.EVENT_RBUTTONDOWN):
            self.num_bins = (10 + self.num_bins) if self.num_bins < 30 else 10
            self.bin_edges_list, self.bin_centers_list = self._create_bin_lists(self.num_bins)
            self.histo_counts = np.zeros(self.num_bins, dtype=np.int64)
            self.update_histogram()
                        

    # .................................................................................................................
    
    @staticmethod
    def _create_bin_lists(num_bins):
        
        # Calculate width of histogram bins
        bin_width = 100.0 / num_bins
        
        # Find the left/right edges and centers of each histogram bin
        bin_edges_list = [0]
        bin_centers_list = [bin_width / 2.0]
        for k in range(num_bins - 1):
            
            next_edge = bin_width + bin_edges_list[-1]
            next_center = bin_width + bin_centers_list[-1]
            
            bin_edges_list.append(next_edge)
            bin_centers_list.append(next_center)            
        
        # Append final edge 
        bin_edges_list.append(100.0)
        
        return bin_edges_list, bin_centers_list
    
    # .................................................................................................................
    
    def store_objects_in_pct_results(self, objects_in_percent_list):
        self._objects_in_pct_list = objects_in_percent_list
    
    # .................................................................................................................
    
    def update_histogram(self):
        
        # Update histogram calculations
        self.histo_counts, _ = np.histogram(self._objects_in_pct_list, bins = self.bin_edges_list)
        
        # Update histogram drawing
        self._update_histogram_frame()
    
    # .................................................................................................................
    
    def get_histogram_frame(self):
        
        mx, my = self._mouse_xy
        if self._plot_x1 < mx < self._plot_x2:            
            histo_frame = self._histogram_frame.copy()
            return self._draw_bar_count(histo_frame, mx)
        
        return self._histogram_frame
    
    # .................................................................................................................
    
    def draw_no_zone_frame(self):
        
        # Create empty background frame for drawing
        draw_frame = self._draw_blank_frame()
        half_width = int(self._frame_width / 2)
        half_height = int(self._frame_height / 2)
        
        missing_zone_text = "No zone data! Draw a zone to run analysis"
        simple_text(draw_frame, missing_zone_text, (half_width, half_height), center_text = True)
        
        return draw_frame
    
    # .................................................................................................................
    
    def _update_histogram_frame(self):
        
        ''' Helper function for updating histogram plot graphics '''
        
        draw_frame = self._bg_frame.copy()
        draw_frame = self._draw_histogram_bars(draw_frame)
        draw_frame = self._draw_bounding_rectangle(draw_frame)
        self._histogram_frame = draw_frame
    
    # .................................................................................................................
    
    def _draw_histogram_background_frame(self):
        
        # Create empty background frame for drawing
        draw_frame = self._draw_blank_frame()
        half_width = int(self._frame_width / 2)
        
        # Draw title & x-axis label
        title_str = "Zone Occupation Histogram ({} objects)".format(self.total_obj_count)
        x_label_str = "Occupation (%)"
        simple_text(draw_frame, title_str, (half_width, 21), center_text = True)
        simple_text(draw_frame, x_label_str, (half_width, self._frame_height - 15), center_text = True)
        
        # Draw x-axis ticks
        for each_edge in self.bin_edges_list:
            
            # Figure out the positioning of each tick label
            x_pos_relative_norm = each_edge / 100.0
            x_pos_relative_px = self._plot_width * x_pos_relative_norm
            x_pos_absolute_px = int(round(self._plot_x1 + x_pos_relative_px))
            
            # Draw tick label (i.e. bin-edge values)
            tick_label = "{:.0f}".format(each_edge)
            simple_text(draw_frame, tick_label, (x_pos_absolute_px, self._plot_y2 + 10),
                        scale = 0.35, center_text = True, color = (160,160,160))
            
        return self._draw_bounding_rectangle(draw_frame)
        
    # .................................................................................................................
    
    def _draw_blank_frame(self):
        ''' Helper function for drawing empty backgorund frames used in other drawing functions (for consistency) '''
        return np.full((self._frame_height, self._frame_width, 3), self._bg_color, dtype = np.uint8)   
    
    # .................................................................................................................
    
    def _draw_histogram_bars(self, plot_frame):
        
        ''' Helper function used to draw histogram bar plot '''
        
        # Figure out histogram bar (width) sizing
        bar_spacing = int(round(80 / self.num_bins))
        bar_width = (self._plot_width / self.num_bins) - 2 * (bar_spacing)
        bar_width = max(3, bar_width)
        bar_half_width = (bar_width / 2)
        
        # Figure out bar (height) sizing
        max_bar_height = (0.95 * self._plot_height)
        max_count = max(self.histo_counts) if self._norm_by_global_max else max(self.histo_counts[1:-1])
        max_count = max(1, max_count)
        
        # For convenience
        y2_px = self._plot_y2        
        bar_color = (128, 95, 11)
        
        for each_count, each_bar_center in zip(self.histo_counts, self.bin_centers_list):
            
            # Locate each bar
            x_center_norm = each_bar_center / 100
            x_center_px = x_center_norm * self._plot_width
            x1_px = self._plot_x1 + int(round(x_center_px - bar_half_width))
            x2_px = self._plot_x1 + int(round(x_center_px + bar_half_width))
            
            # Figure out bar heights
            y1_norm = min((each_count / max_count), 1.0)
            y1_px = int(round(y2_px - y1_norm * max_bar_height))
            
            # Draw bars!
            cv2.rectangle(plot_frame, (x1_px, y1_px), (x2_px, y2_px), bar_color, -1)
        
        return plot_frame
    
    # .................................................................................................................
    
    def _draw_bounding_rectangle(self, plot_frame):
        rect_tl = (self._plot_x1, self._plot_y1)
        rect_br = (self._plot_x2, self._plot_y2)
        return cv2.rectangle(plot_frame, rect_tl, rect_br, (255, 255, 255), 1)
    
    # .................................................................................................................
    
    def _draw_bar_count(self, display_frame, mouse_x):
        
        # Figure out which bar the mouse is hovering over
        mouse_x_norm = (mouse_x - self._plot_x1) / self._plot_width
        mouse_x_int = int(self.num_bins * mouse_x_norm)
        x_idx = min(mouse_x_int, self.num_bins - 1)
        
        # Figure out bar (height) sizing
        max_bar_height = (0.95 * self._plot_height)
        max_count = max(self.histo_counts) if self._norm_by_global_max else max(self.histo_counts[1:-1])
        max_count = max(1, max_count)
        bar_count = self.histo_counts[x_idx]
        
        # Figure out bar heights
        y1_norm = min((bar_count / max_count), 1.0)
        y1_px = int(round(self._plot_y2 - y1_norm * max_bar_height))
            
        # Locate bar text 
        x_center_norm = self.bin_centers_list[x_idx] / 100
        x_center_px = x_center_norm * self._plot_width
        
        # Draw count
        text_x = self._plot_x1 + int(round(x_center_px))
        text_y = (y1_px - 6)
        text_color = (61, 131, 166) if (bar_count <= max_count) else (50, 50, 180)
        simple_text(display_frame, "{}".format(bar_count), (text_x, text_y), scale = 0.35, color = text_color,
                    center_text = True)        
        
        return display_frame
    
    # .................................................................................................................
    # .................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

# .....................................................................................................................

def show_looping_animation(snapshot_database, object_database, object_to_animate, zones_list_norm,
                           window_x = 50, window_y = 50,
                           start_buffer_time_sec = 3.0, end_buffer_time_sec = 5.5):
    
    # Figure out the time range to animate over
    start_time_ems = np.min(object_to_animate.start_ems)
    end_time_ems = np.max(object_to_animate.end_ems)
    
    # Set up buffer times (used to extend animation range to include time before/after object existence)
    start_buffer_time_ms = int(start_buffer_time_sec * 1000.0)
    end_buffer_time_ms = int(end_buffer_time_sec * 1000.0)
    
    # Make sure we don't reach for snapshots out of the snapshot time range
    earliest_snap, latest_snap = snapshot_database.get_bounding_epoch_ms()
    earliest_time = max(earliest_snap, start_time_ems - start_buffer_time_ms)
    latest_time = min(latest_snap, end_time_ems + end_buffer_time_ms)
    
    # Get all the snapshot times we'll need for animation
    anim_snapshot_times = snapshot_database.get_all_snapshot_times_by_time_range(earliest_time, latest_time)
    
    # Set up the display window
    window_title = "Object {}".format(object_to_animate.nice_id)
    anim_window = Simple_Window(window_title)
    anim_window.move_corner_pixels(window_x, window_y)
    
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
        
        # Get each snapshot and draw all zones & outlines/trails for all objects in the frame
        snap_image, snap_frame_idx = snapshot_database.load_snapshot_image(each_snap_time)
        snap_image = draw_zone_indicator(snap_image, zones_list_px)
        object_to_animate.draw_trail(snap_image, snap_frame_idx, each_snap_time)
        object_to_animate.draw_outline(snap_image, snap_frame_idx, each_snap_time)
        
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

def update_object_inout_calculations(object_list, new_zones_list_norm):
    
    # Pre-convert zone definitions from lists to arrays, to avoid repeating conversion inside of objects
    zones_array_norm = [np.float32(each_zone_list) for each_zone_list in new_zones_list_norm]
    
    obj_in_pct_list = []
    obj_out_pct_list = []
    for each_obj in object_list:
        obj_in_pct, obj_out_pct = each_obj.calculate_in_out_value(zones_array_norm)
        obj_in_pct_list.append(obj_in_pct)
        obj_out_pct_list.append(obj_out_pct)
        
    return obj_in_pct_list, obj_out_pct_list

# .....................................................................................................................

def draw_zone_indicator(display_frame, new_zones_list_px,  
                        zone_line_color = (255, 255, 255), zone_line_thickness = 2, line_type = cv2.LINE_AA):
    
    # For clarity
    is_closed = True
    bg_thickness = (2 * zone_line_thickness)
    bg_color = (0, 0, 0)
    
    # Draw zones, with foreground/background colors
    indicator_frame = display_frame.copy()
    for each_zone_px in new_zones_list_px:
        zone_array = np.int32(each_zone_px)
        cv2.polylines(indicator_frame, [zone_array], is_closed, bg_color, bg_thickness, line_type)
        cv2.polylines(indicator_frame, [zone_array], is_closed, zone_line_color, zone_line_thickness, line_type)
    
    return indicator_frame

# .....................................................................................................................

def draw_inout_indicators(display_frame, in_string, out_string,
                          text_scale = 0.35, bg_color = (0, 0, 0), bg_thickness = 3):
    
    # If no in-zone string is provided, don't bother drawing anything
    if in_string is None:
        return display_frame
    
    # Draw text onto frame to indicate in/out information
    fg_str_kwargs = font_config(scale = text_scale)
    bg_str_kwargs = font_config(scale = text_scale, thickness = bg_thickness, color = bg_color)
    in_pos_rel = (-5, -20)
    out_pos_rel = (-5, -5)
    in_pos = position_frame_relative(display_frame.shape, in_string, in_pos_rel, **fg_str_kwargs)
    out_pos = position_frame_relative(display_frame.shape, out_string, out_pos_rel, **fg_str_kwargs)
    simple_text(display_frame, in_string, in_pos, **bg_str_kwargs)
    simple_text(display_frame, in_string, in_pos, **fg_str_kwargs)
    simple_text(display_frame, out_string, out_pos, **bg_str_kwargs)
    simple_text(display_frame, out_string, out_pos, **fg_str_kwargs)
    
    return display_frame

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


# ---------------------------------------------------------------------------------------------------------------------
#%% Create drawing object

zone_drawer = Entity_Drawer(frame_wh,
                            minimum_entities=0,
                            maximum_entities=None,
                            minimum_points=3,
                            maximum_points=None)
zone_drawer.initialize_entities([[(0.25, 0.25), (0.25, 0.75), (0.75, 0.75), (0.75, 0.25)]])
zone_drawer.aesthetics(finished_color = (255, 0, 255), finished_thickness = 2)

# ---------------------------------------------------------------------------------------------------------------------
#%% Load object data

# Get object metadata from the server
obj_metadata_generator = obj_db.load_metadata_by_time_range(start_dt, end_dt)

# Create list of 'reconstructed' objects based on object metadata, so we can work/interact with the object data
obj_list = Hover_Object.create_reconstruction_list(obj_metadata_generator,
                                                   frame_wh,
                                                   start_dt, 
                                                   end_dt)

# Organize objects by class label -> then by object id (nested dictionaries)
objclass_dict = create_object_class_dict(class_db, obj_list)

# Generate trail hover mapping, for quicker mouse-to-trail lookup
hover_map = Hover_Mapping(objclass_dict)


# ---------------------------------------------------------------------------------------------------------------------
#%% Create initial datasets

# Generate the background display frame, containing all object trails
trails_background = create_trail_frame_from_object_reconstruction(bg_frame, obj_list)

# Create background with 'faded' trails, for drawing zone image
zone_bg_frame = cv2.addWeighted(bg_frame, 0.5, trails_background, 0.5, 0.0)

# Get initial zone point co-ords
zones_list_norm = zone_drawer.get_entities_list(normalize = True)
zones_list_px = zone_drawer.get_entities_list(normalize = False)

# Calculate initial zone in/out values (and display image)
in_pct_list, out_pct_list = update_object_inout_calculations(obj_list, zones_list_norm)
trails_frame = draw_zone_indicator(trails_background, zones_list_px)


# ---------------------------------------------------------------------------------------------------------------------
#%% Create histogram object

histo = Histogram_Plot(in_pct_list, 10)
histo.update_histogram()

# ---------------------------------------------------------------------------------------------------------------------
#%% Interaction loop

# Close any previously open windows
cv2.destroyAllWindows()

# Set up mouse interaction callbacks
trail_hover_callback = Hover_Callback(frame_wh)
cb_sequencer = Callback_Sequencer("trails", trail_hover_callback, frame_wh)

# Set up window positioning
x_spacing = 50
y_spacing = 50
x1 = x_spacing
x2 = 2 * (x_spacing + zone_drawer.border_size_px) + frame_width
y1 = y_spacing
y2 = 2 * (y_spacing) + frame_height
x1_inset = x1 + zone_drawer.border_size_px
y1_inset = y1 + zone_drawer.border_size_px

# Set up feedback window
blank_info_image = np.full((360, 640, 3), (40,40,40), dtype = np.uint8)
simple_text(blank_info_image, "Hover over a trail to see zone occupation info...", (320, 180), center_text = True)
histo_window = Simple_Window("Zone Info")
histo_window.attach_callback(histo)
histo_window.imshow(blank_info_image)
histo_window.move_corner_pixels(x2, y2)

# Set up drawing window
draw_window = Simple_Window("Draw Zone(s)")
draw_window.attach_callback(zone_drawer)
draw_window.move_corner_pixels(x1, y1)

# Set up main display window
disp_window = Simple_Window("Select Trail")
disp_window.attach_callback(cb_sequencer)
disp_window.move_corner_pixels(x2, y1)

# Some histogram control feedback
print("",
      "Histogram controls:",
      "  Hover over bars to see the object count of the corresponding bar",
      "  Right click plot to adjust bar plot density",
      "  Left click plot to toggle normalization style",
      "    - by default, plot is normalized by global maximum",
      "    - click to normalize by 'inner' maximum (i.e. ignore end counts)",
      sep="\n")

# ... And some drawing control feedback (hacky/hard-coded for now)
print("",
      "Drawing controls:",
      "  Use shift + left click to create a new zone/add points",
      "  Use double left click to complete a new zone",
      "  Use left click to drag points on an existing zone",
      "  Use ctrl + left click to insert points into an existing zone",
      "  Use right click to delete points or cancel a new zone",
      "  Use ctrl + right click to delete an entire zone",
      "",
      "Press Esc to close", "", sep="\n")

while True:
    
    # Make clean copies of the frames to display, so we don't muddy up the originals
    display_frame = trails_frame.copy()
    zone_frame = zone_bg_frame.copy()
    
    # Update trails frame every time the zone changes
    if zone_drawer.on_change():
        
        # Get updated zone point co-ords
        zones_list_norm = zone_drawer.get_entities_list(normalize = True)
        zones_list_px = zone_drawer.get_entities_list(normalize = False)
        
        # Update in/out calculations
        in_pct_list, out_pct_list = update_object_inout_calculations(obj_list, zones_list_norm)        
        trails_frame = draw_zone_indicator(trails_background, zones_list_px)
        
        # Update histogram
        histo.store_objects_in_pct_results(in_pct_list)
        histo.update_histogram()
    
    # Respond to trail hovering, if active
    if cb_sequencer.is_active("trails"):
        
        # Get relative mouse co-ords
        mouse_xy = trail_hover_callback.mouse_xy()
        closest_trail_dist, closest_obj_id, closest_obj_class = hover_map.closest_point(mouse_xy)
        
        # Highlight the closest trail/timebar segment if the mouse is close enough
        if closest_trail_dist < 0.05:
            obj_ref = objclass_dict[closest_obj_class][closest_obj_id]
            display_frame = obj_ref.highlight_trail(display_frame)
            
            # Show hovered trail in/out info
            in_str, out_str = obj_ref.in_out_strings()
            display_frame = draw_inout_indicators(display_frame, in_str, out_str)
            
            # Play an animation if the user clicks on the highlighted trail
            if trail_hover_callback.clicked():
                obj_to_animate = obj_ref
                zones_list_px = zone_drawer.get_entities_list(normalize = False)
                show_looping_animation(snap_db, obj_db, obj_to_animate, zones_list_px,
                                       window_x = x1_inset, window_y = y1_inset)
    
    # Display zone drawing
    draw_window.imshow(zone_drawer.annotate(zone_frame))
    
    # Draw zone occupation info
    histo_window.imshow(histo.get_histogram_frame())
    
    # Show final display
    disp_win_exists = disp_window.imshow(display_frame)
    
    # Close if all windows are closed
    if not disp_win_exists:
        break
    
    # Get keypresses
    keycode, modifier = waitKey_ex(40)
    if keycode_quit(keycode):
        break
    
    zone_drawer.keypress_callback(keycode, modifier)


# Some clean up
cv2.destroyAllWindows()

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap

# TODO
# - clean up hacky implementation
# - Draw separate histograms for each class (in separate windows?)

