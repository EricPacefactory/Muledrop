#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Jan 30 14:22:34 2020

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

from time import perf_counter

from local.lib.ui_utils.cli_selections import Resource_Selector

from local.lib.ui_utils.local_ui.windows_base import Simple_Window
from local.lib.ui_utils.local_ui.drawing import Entity_Drawer, waitKey_ex, keycode_quit

from local.lib.file_access_utils.rules import select_rule_to_load, cli_save_rule

from local.offline_database.file_database import launch_dbs, close_dbs_if_missing_data
from local.offline_database.object_reconstruction import create_trail_frame_from_object_reconstruction
from local.offline_database.snapshot_reconstruction import median_background_from_snapshots
from local.offline_database.classification_reconstruction import create_objects_by_class_dict, get_ordered_object_list

from local.configurables.after_database.rules.zoneoccupation_rule import Zoneoccupation_Rule

from local.eolib.video.text_rendering import simple_text
from local.eolib.utils.cli_tools import Datetime_Input_Parser as DTIP


# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes

class Histogram_Plot:
    
    # .................................................................................................................
    
    def __init__(self, class_label, x, y, bar_color, num_bins, frame_width, frame_height, bg_color = (40,40,40)):
        
        # Store important config info
        self.class_label = class_label
        self.num_bins = num_bins
        
        # Calculate the initial histogram bin locations
        self.bin_edges_list, self.bin_centers_list = self._create_bin_lists(num_bins)
        
        # Store aesthetics
        self._frame_width = frame_width
        self._frame_height = frame_height
        self._bg_color = bg_color
        self._plot_x1 = 20
        self._plot_x2 = (frame_width - self._plot_x1 - 1)
        self._plot_y1 = 15
        self._plot_y2 = (frame_height - self._plot_y1 - 22)
        self._plot_width = (self._plot_x2 - self._plot_x1)
        self._plot_height = (self._plot_y2 - self._plot_y1)
        self._bar_color = bar_color
        
        # Generate the plotting window & initial graphics
        self._bg_frame = self._draw_background_frame(frame_width, frame_height, bg_color)
        self.window_ref = Simple_Window("{} Histogram".format(class_label.capitalize()))
        self.window_ref.move_corner_pixels(x, y)
        self.window_ref.imshow(self._bg_frame)
    
    # .................................................................................................................
    
    @classmethod
    def generate_histogram_plots(cls, object_class_labels, bar_colors_lut, x_offset, y_offset, num_bins = 10):
        
        # Hard-code some aesthetics
        frame_width = 400
        frame_height = 225
        x_spacing = 50 + frame_width
        y_spacing = 50 + frame_height
        bg_color = (40, 40, 40)
        
        # Generate histogram objects, with plot positioning, for each class label
        histo_list = {}
        for each_idx, each_class_label in enumerate(object_class_labels):
            x_pos = int(x_offset + np.remainder(each_idx, 2) * x_spacing)
            y_pos = int(y_offset + np.floor(each_idx / 2) * y_spacing)
            bar_color = bar_colors_lut[each_class_label]
            new_histo = cls(each_class_label, x_pos, y_pos, bar_color, num_bins, frame_width, frame_height, bg_color)
            histo_list[each_class_label] = new_histo
        
        return histo_list
    
    # .................................................................................................................
    
    def update_display(self, object_results_dict):
        
        # First create a copy of the background frame, so we don't mess up the original
        display_frame = self._bg_frame.copy()
        
        # First get a listing of all the in_percent rule result values for the provided object dictionary
        in_zone_pct_list = [each_result_dict["in_percent"] for each_result_dict, _ in object_results_dict.values()]
        
        # Update histogram result for the new distribution of in_percent values
        histo_counts, _ = np.histogram(in_zone_pct_list, bins = self.bin_edges_list)
        
        # Now draw updated bars, using new histogram counts
        self._draw_histogram_bars(display_frame, histo_counts, self.bin_centers_list)
        
        self.window_ref.imshow(display_frame)
        
        return display_frame

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
    
    def _draw_background_frame(self, frame_width, frame_height, bg_color):
        
        # Create empty background frame for drawing
        draw_frame = np.full((frame_height, frame_width, 3), bg_color, dtype = np.uint8)
        half_width = int(frame_width / 2)
        
        # Draw x-axis label
        x_label_str = "Occupation (%)"
        simple_text(draw_frame, x_label_str, (half_width, frame_height - 10), scale = 0.4, center_text = True)
        
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
            
        return draw_frame
    
    # .................................................................................................................
    
    def _draw_histogram_bars(self, display_frame, histogram_counts, bin_centers_list):
        
        ''' Helper function used to draw histogram bar plot '''
        
        # Figure out histogram bar (width) sizing
        bar_spacing = int(round(80 / self.num_bins))
        bar_width = (self._plot_width / self.num_bins) - 2 * (bar_spacing)
        bar_width = max(3, bar_width)
        bar_half_width = (bar_width / 2)
        
        # Figure out bar (height) sizing
        max_bar_height = (0.95 * self._plot_height)
        max_count = max(histogram_counts[1:-1]) #max(histogram_counts) #if self._norm_by_global_max else max(self.histo_counts[1:-1])
        max_count = max(1, max_count)
        
        # For convenience
        y2_px = self._plot_y2
        
        for each_count, each_bar_center in zip(histogram_counts, bin_centers_list):
            
            # Locate each bar
            x_center_norm = each_bar_center / 100
            x_center_px = x_center_norm * self._plot_width
            x1_px = self._plot_x1 + int(round(x_center_px - bar_half_width))
            x2_px = self._plot_x1 + int(round(x_center_px + bar_half_width))
            
            # Figure out bar heights
            y1_norm = min((each_count / max_count), 1.0)
            y1_px = int(round(y2_px - y1_norm * max_bar_height))
            
            # Draw bars!
            cv2.rectangle(display_frame, (x1_px, y1_px), (x2_px, y2_px), self._bar_color, -1)
            
            # Draw bar count
            text_x = self._plot_x1 + int(round(x_center_px))
            text_y = (y1_px - 8)
            text_color = (61, 131, 166) if (each_count <= max_count) else (50, 50, 180)
            text_str = str(each_count)
            simple_text(display_frame, text_str, (text_x, text_y), scale = 0.35, color = text_color, center_text = True)        
        
        return display_frame
    
    # .................................................................................................................
    
    def _draw_bounding_rectangle(self, plot_frame):
        rect_tl = (self._plot_x1, self._plot_y1)
        rect_br = (self._plot_x2, self._plot_y2)
        return cv2.rectangle(plot_frame, rect_tl, rect_br, (160, 160, 160), 1)

    # .................................................................................................................
    # .................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

# .....................................................................................................................

def process_all_object_data(rule_ref, object_database, frame_wh, start_time, end_time):
    
    ''' Helper function which has the rule pre-process all the object data, so we can continually re-use it '''
    
    obj_id_list = object_database.get_object_ids_by_time_range(start_time, end_time)
    obj_metadata_list = [object_database.load_metadata_by_id(each_id) for each_id in obj_id_list]
    obj_data_dict = rule_ref.process_all_object_metadata(obj_id_list, obj_metadata_list, frame_wh)
    
    return obj_data_dict

# .....................................................................................................................

def update_rule_results(rule_ref, obj_by_class_dict, snap_db, frame_wh):
    
    # Start timing, so we have an idea of how fast the rule is + avoid overly fast updates if slow!
    t_start = perf_counter()
    
    # Evaluate rule for each class separately, for easier results management
    rule_results_per_class_dict = {each_class_label: {} for each_class_label in obj_by_class_dict.keys()}
    for each_class_label, each_obj_dict in obj_by_class_dict.items():
        rule_results_per_class_dict[each_class_label] = rule_ref.evaluate_all_objects(each_obj_dict, snap_db, frame_wh)
    
    # Get time required to evaluate the rule
    t_end = perf_counter()
    update_time_ms = int(1000 * (t_end - t_start))
    #print("Rule update took {:.0f} ms".format(update_time_ms))

    return rule_results_per_class_dict, update_time_ms

# .....................................................................................................................

def update_histogram_displays(histogram_dict, rule_results_per_class):
    
    for each_class_label, each_obj_dict in rule_results_per_class.items():
        histo_ref = histogram_dict[each_class_label]
        histo_ref.update_display(each_obj_dict)
    
    return

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Make selections

enable_debug_mode = False

# Create selector so we can access existing report data
selector = Resource_Selector()
project_root_path, cameras_folder_path = selector.get_cameras_root_pathing()

# Select the camera to show data for (needs to have saved report data already!)
camera_select, camera_path = selector.camera(debug_mode=enable_debug_mode)


# ---------------------------------------------------------------------------------------------------------------------
#%% Catalog existing data

caminfo_db, snap_db, obj_db, class_db = launch_dbs(cameras_folder_path, camera_select,
                                                   "camera_info", "snapshots", "objects", "classifications")

# Catch missing data
close_dbs_if_missing_data(snap_db, error_message_if_missing = "No snapshot data in the database!")

# Get frame sizing, for rule sizing/drawing
frame_wh = caminfo_db.get_snap_frame_wh()


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
frame_scaling = np.float32((frame_width - 1, frame_height - 1))


# ---------------------------------------------------------------------------------------------------------------------
#%% Select rule to load

# Load configurable class for this config utility
rule_ref = Zoneoccupation_Rule(cameras_folder_path, camera_select, frame_wh)

# Ask user to load an existing rule config, or create a new one & configure the rule accordingly
load_from_existing_config, loaded_rule_name, initial_setup_data_dict = select_rule_to_load(rule_ref)
rule_ref.reconfigure(initial_setup_data_dict)


# ---------------------------------------------------------------------------------------------------------------------
#%% Load object data

# Load all object data, as needed by the rule
obj_dict = process_all_object_data(rule_ref, obj_db, frame_wh, user_start_dt, user_end_dt)

# Load in classification data, if any
obj_id_list, obj_by_class_dict, obj_id_to_class_dict = create_objects_by_class_dict(class_db, obj_dict)
_, _, all_label_colors_dict = class_db.get_label_color_luts()

# Get an ordered list of the objects for drawing
ordered_obj_list = get_ordered_object_list(obj_id_list, obj_by_class_dict, obj_id_to_class_dict)


# ---------------------------------------------------------------------------------------------------------------------
#%% Set up drawing

# Create a zone drawer
zone_drawer = Entity_Drawer(frame_wh,
                            minimum_entities = 0,
                            maximum_entities = None,
                            minimum_points = 3,
                            maximum_points = None)

# Initialize the drawing with the rule zone(s) definition & change the drawing colors (just for aesthetics)
zone_drawer.initialize_entities(rule_ref.zone_entity_list)
zone_drawer.aesthetics(finished_color = (255, 0, 255), finished_thickness = 2)


# ---------------------------------------------------------------------------------------------------------------------
#%% Set up displays

cv2.destroyAllWindows()

# Set up main display/drawing window
draw_window = Simple_Window("Draw Zone")
draw_window.attach_callback(zone_drawer)

# Create plots for histograms
x_offset = (frame_width + 2 * (50 + zone_drawer.border_size_px))
y_offset = 50
histogram_dict = Histogram_Plot.generate_histogram_plots(obj_by_class_dict.keys(),
                                                         all_label_colors_dict,
                                                         x_offset, y_offset)


# ---------------------------------------------------------------------------------------------------------------------
#%% Create background frames

# Draw all object trails onto the background frame
trail_frame = create_trail_frame_from_object_reconstruction(bg_frame, ordered_obj_list)

# Create initial display frames (which may be modified by user interactions)
draw_frame = trail_frame.copy()


# ---------------------------------------------------------------------------------------------------------------------
#%% *** DRAW LOOP ***

# Create variables to control whether the rule results run continuously or wait for the user to mouse-up
wait_for_mouse_up = False
max_update_delay_ms = 200

while True:
    
    # Handle drawing updates
    if zone_drawer.on_change(wait_for_mouse_up):
        
        # Update the rule with the new zone drawing
        new_zone_entity_list = zone_drawer.get_entities_list(normalize = True)
        rule_ref.reconfigure({"zone_entity_list": new_zone_entity_list})
        
        # Get new results for all objects (with timing info!)
        rule_results_per_class, update_time_ms = update_rule_results(rule_ref, obj_by_class_dict, snap_db, frame_wh)
        
        # Use update timing to decide if we should try to update the rule UI constantly ('heavy' cpu usage)
        # or if we should wait for the user to let go of the mouse before updating (much lighter!)
        wait_for_mouse_up = (update_time_ms > max_update_delay_ms)
        
        # Update the histogram(s)
        update_histogram_displays(histogram_dict, rule_results_per_class)
    
    # Draw rule zone indicator onto the frame & update the display
    draw_frame = zone_drawer.annotate(trail_frame)
    draw_window.imshow(draw_frame)
    
    # Get keypresses
    keycode, modifier = waitKey_ex(10)
    if keycode_quit(keycode):
        break
    
    # Handle arrow key nudging
    zone_drawer.keypress_callback(keycode, modifier)

# Clean up
cv2.destroyAllWindows()


# ---------------------------------------------------------------------------------------------------------------------
#%% Save rule configuration

saved_rule_name = cli_save_rule(rule_ref, load_from_existing_config, loaded_rule_name, file_dunder = __file__)


# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap

'''
# View rule results, per class
print("", "DEBUG: zone occupation output", sep = "\n")
for each_class_label, each_obj_results_dict in rule_results_per_class.items():
    print("", "Class: {}".format(each_class_label), sep = "\n")
    for each_obj_id, (each_rule_dict, each_rule_list) in each_obj_results_dict.items():
        print("  Obj", each_obj_id, "results:")
        print("   ", each_rule_dict)
        print("   ", each_rule_list)
pass
'''


'''
TODO
- Consider adding 'representating snapshot epoch_ms' value to saved rule data, to act as quick 'thumbnail' ref
'''

