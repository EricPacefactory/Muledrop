#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Jan 23 11:57:38 2020

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

from local.lib.common.timekeeper_utils import datetime_to_epoch_ms

from local.lib.ui_utils.cli_selections import Resource_Selector

from local.lib.ui_utils.local_ui.windows_base import Simple_Window
from local.lib.ui_utils.local_ui.drawing import Entity_Drawer, waitKey_ex, keycode_quit

from local.lib.file_access_utils.rules import select_rule_to_load, cli_save_rule

from local.offline_database.file_database import launch_dbs, close_dbs_if_missing_data
from local.offline_database.object_reconstruction import create_trail_frame_from_object_reconstruction
from local.offline_database.snapshot_reconstruction import median_background_from_snapshots
from local.offline_database.classification_reconstruction import create_objects_by_class_dict, get_ordered_object_list

from local.configurables.after_database.rules.linecross_rule import Linecross_Rule

from local.eolib.utils.cli_tools import Datetime_Input_Parser as DTIP


# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes



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

    return rule_results_per_class_dict, update_time_ms

# .....................................................................................................................

def update_event_frame(display_frame, rule_ref, rule_results_per_class_dict, all_label_colors_dict, 
                       start_epoch_ms, end_epoch_ms,
                       line_color = (255, 0, 255), line_thickness = 1, line_type = cv2.LINE_AA,
                       event_bar_height = 24, 
                       event_bar_dark_bg_color = (30, 30, 30), 
                       event_bar_light_bg_color = (40, 40, 40)):
    
    # Create copy of the display frame so we don't mess with the original
    new_event_frame = display_frame.copy()
    frame_height, frame_width = new_event_frame.shape[0:2]
    frame_scaling = np.float32((frame_width - 1, frame_height - 1))
    
    # Generate some positioning info for the event bar
    half_bar_height = int(event_bar_height / 2)
    start_bar_height = 2
    end_bar_height = event_bar_height - 3
    calculate_relative_timing = lambda snap_ems: (snap_ems - start_epoch_ms) / (end_epoch_ms - start_epoch_ms)
    
    # Create blank event bar for displaying timing info
    dark_event_bar = np.full((half_bar_height, frame_width, 3), event_bar_dark_bg_color, dtype = np.uint8)
    light_event_bar = np.full_like(dark_event_bar, event_bar_light_bg_color)
    blank_event_bar = np.vstack((dark_event_bar, light_event_bar))
    calculate_relative_timing = lambda snap_ems: (snap_ems - start_epoch_ms) / (end_epoch_ms - start_epoch_ms)
    
    # Get line points
    line_pt1, line_pt2 = rule_ref.line_entity_list[0]
    if rule_ref.flip_line_orientation:
        line_pt1, line_pt2 = line_pt2, line_pt1
    
    # First draw the line, for reference
    pt1_px = tuple(np.int32(np.round(line_pt1 * frame_scaling)))
    pt2_px = tuple(np.int32(np.round(line_pt2 * frame_scaling)))
    cv2.line(new_event_frame, pt1_px, pt2_px, line_color, line_thickness, line_type)
    
    # Also draw the line normal/direction for reference (MESSY!)
    line_vector = np.float32(pt2_px) - np.float32(pt1_px)
    line_unit_normal = np.float32((-1 * line_vector[1], line_vector[0])) / np.linalg.norm(line_vector)
    line_center_pt = np.float32(pt1_px) + (0.5 * line_vector)
    vec1_px = tuple(np.int32(np.round(line_center_pt - line_unit_normal * 10)))
    vec2_px = tuple(np.int32(np.round(line_center_pt + line_unit_normal * 35)))
    cv2.arrowedLine(new_event_frame, vec1_px, vec2_px, line_color, 1, line_type, tipLength = 0.1)
    
    # Draw all intersection points, colors by cross direction
    event_bar_frame_list = []
    for each_class_label, each_rule_results_per_obj in rule_results_per_class_dict.items():
        
        # Create new (blank) event bar for each class, so we can indicate event timing
        new_event_bar = blank_event_bar.copy()
        bar_color = all_label_colors_dict[each_class_label]
        
        for each_obj_id, (each_results_dict, each_results_list) in each_rule_results_per_obj.items():
            for each_intersection_result in each_results_list:
                
                # Pull out event info
                cross_direction = each_intersection_result["cross_direction"]
                intersection_point = each_intersection_result["intersection_point"]
                approximate_epoch_ms = each_intersection_result["approximate_epoch_ms"]
                crossed_forward = (cross_direction == "forward")
                
                # Draw intersection points
                fg_color = (0,0,0) if crossed_forward else (255,255,255)
                bg_color = (255,255,255) if crossed_forward else (0,0,0)
                circle_pt_px = tuple(np.int32(np.round(intersection_point * frame_scaling)))
                cv2.circle(new_event_frame, circle_pt_px, 5, bg_color, -1, cv2.LINE_AA)
                cv2.circle(new_event_frame, circle_pt_px, 4, fg_color, 1, cv2.LINE_AA)
                
                # Draw event indicators for every intersection
                event_timing_frac = calculate_relative_timing(approximate_epoch_ms)
                event_timing_px = int(round(event_timing_frac * (frame_width - 1)))
                if crossed_forward:
                    line_pos = ((event_timing_px, half_bar_height), (event_timing_px, end_bar_height))
                else:
                    line_pos = ((event_timing_px, start_bar_height), (event_timing_px, half_bar_height - 1))
                cv2.line(new_event_bar, *line_pos, bar_color, 1)
                
        # Store the 'finished' event bar image, so we can stack it onto the bottom of the displayed frame later
        event_bar_frame_list.append(new_event_bar)
    
    # Finally, combine all the frame data for output
    output_event_frame = np.vstack([new_event_frame, *event_bar_frame_list])
    
    return output_event_frame

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

# Calculate start/end times as epoch ms values for relative event timing
start_ems = datetime_to_epoch_ms(user_start_dt)
end_ems = datetime_to_epoch_ms(user_end_dt)


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
rule_ref = Linecross_Rule(cameras_folder_path, camera_select, frame_wh)

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

# Create a line drawer, by restricting drawing to 2 points only
line_drawer = Entity_Drawer(frame_wh,
                            minimum_entities = 1,
                            maximum_entities = 1,
                            minimum_points = 2,
                            maximum_points = 2)

# Initialize the drawing with the rule line definition & change the drawing colors (just for aesthetics)
line_drawer.initialize_entities(rule_ref.line_entity_list)
line_drawer.aesthetics(finished_color = (255, 0, 255), finished_thickness = 2)


# ---------------------------------------------------------------------------------------------------------------------
#%% Set up displays

cv2.destroyAllWindows()

# Set up main display/drawing window
draw_window = Simple_Window("Draw Line")
draw_window.attach_callback(line_drawer)

# Create event feedback window display
event_window_x_offset = frame_width + 2 * (50 + line_drawer.border_size_px)
event_window = Simple_Window("Linecross Events")
event_window.move_corner_pixels(event_window_x_offset, 50)


# ---------------------------------------------------------------------------------------------------------------------
#%% Create background frames

# Draw all object trails onto the background frame
trail_frame = create_trail_frame_from_object_reconstruction(bg_frame, ordered_obj_list)

# Create initial display frames (which may be modified by user interactions)
draw_frame = trail_frame.copy()
event_frame = trail_frame.copy()


# ---------------------------------------------------------------------------------------------------------------------
#%% *** DRAW LOOP ***

# Create variables to control whether the linecross results run continuously or wait for the user to mouse-up
wait_for_mouse_up = False
max_update_delay_ms = 200

while True:
    
    # Handle updates to the line drawing
    if line_drawer.on_change(wait_for_mouse_up):
        
        # Update the rule with the new line drawing
        new_line_entity_list = line_drawer.get_entities_list(normalize = True)
        rule_ref.reconfigure({"line_entity_list": new_line_entity_list})
        
        # Get new results for all objects (with timing info!)
        rule_results_per_class, update_time_ms = update_rule_results(rule_ref, obj_by_class_dict, snap_db, frame_wh)
        
        # Use update timing to decide if we should try to update the rule UI constantly ('heavy' cpu usage)
        # or if we should wait for the user to let go of the mouse before updating (much lighter!)
        wait_for_mouse_up = (update_time_ms > max_update_delay_ms)
        
        # Draw new intersection results
        event_frame = update_event_frame(trail_frame, rule_ref, rule_results_per_class,
                                         all_label_colors_dict, start_ems, end_ems)
    
    # Draw rule line indicator onto the frame
    draw_frame = line_drawer.annotate(trail_frame)
    
    # Update displays
    draw_window.imshow(draw_frame)
    event_window.imshow(event_frame)
    
    # Get keypresses
    keycode, modifier = waitKey_ex(10)
    if keycode_quit(keycode):
        break
    
    # Handle arrow key nudging
    line_drawer.keypress_callback(keycode, modifier)

# Clean up
cv2.destroyAllWindows()


# ---------------------------------------------------------------------------------------------------------------------
#%% Save rule configuration

saved_rule_name = cli_save_rule(rule_ref, load_from_existing_config, loaded_rule_name, file_dunder = __file__)


# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap

'''
# View rule results, per class
print("", "DEBUG: Line cross output", sep = "\n")
for each_class_label, each_obj_results_dict in rule_results_per_class.items():
    print("", "Class: {}".format(each_class_label), sep = "\n")
    for each_obj_id, (each_rule_dict, each_rule_list) in each_obj_results_dict.items():
        print("  Obj", each_obj_id, "results:")
        print("   ", each_rule_dict)
        print("   ", each_rule_list)
pass
'''

# TODO:
# - Add ability to hover intersection points and/or timing indicators and click for playback of intersection event
# - Clean up 'update_event_frame' implementation. Way too much re-calculating of state (could be handle by an object)

