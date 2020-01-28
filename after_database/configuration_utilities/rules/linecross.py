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

from local.lib.ui_utils.cli_selections import Resource_Selector

from local.lib.ui_utils.local_ui.windows_base import Simple_Window
from local.lib.ui_utils.local_ui.drawing import Entity_Drawer, waitKey_ex, keycode_quit

from local.lib.file_access_utils.after_database import build_after_database_configs_folder_path
from local.lib.file_access_utils.rules import load_all_rule_configs

from local.offline_database.file_database import user_input_datetime_range, launch_file_db, close_dbs_if_missing_data
from local.offline_database.object_reconstruction import Smoothed_Object_Reconstruction as Obj_Recon
from local.offline_database.object_reconstruction import create_trail_frame_from_object_reconstruction
from local.offline_database.snapshot_reconstruction import median_background_from_snapshots
from local.offline_database.classification_reconstruction import create_object_class_dict

from local.configurables.after_database.rules.linecross_rule import Linecross_Rule

from eolib.utils.cli_tools import cli_confirm, cli_select_from_list
from eolib.utils.read_write import load_json, save_json

# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes



# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

# .....................................................................................................................

def update_rule_results(rule_ref, objclass_dict, snap_db, frame_wh):
    
    # Start timing, so we have an idea of how fast the rule is + avoid overly fast updates if slow!
    t_start = perf_counter()
    
    # Evaluate rule for each class separately, for easier results management
    rule_results_per_class = {each_class_label: {} for each_class_label in objclass_dict.keys()}
    for each_class_label, each_obj_dict in objclass_dict.items():
        rule_results_per_class[each_class_label] = rule_ref.evaluate_all_objects(each_obj_dict, snap_db, frame_wh)
    
    # Get time required to evaluate the rule
    t_end = perf_counter()
    update_time_ms = int(1000 * (t_end - t_start))

    return rule_results_per_class, update_time_ms

# .....................................................................................................................

def update_event_frame(display_frame, rule_ref, rule_results_dict,
                       line_color = (255, 0, 255), line_thickness = 1, line_type = cv2.LINE_AA):
    
    # Create copy of the display frame so we don't mess with the original
    new_event_frame = display_frame.copy()
    frame_height, frame_width = new_event_frame.shape[0:2]
    frame_scaling = np.float32((frame_width - 1, frame_height - 1))
    
    # Get line points
    line_pt1, line_pt2 = rule_ref.line_entity_list[0]
    if rule_ref.flip_line_orientation:
        line_pt1, line_pt2 = line_pt2, line_pt1
    
    # First draw the line, for reference
    pt1_px = tuple(np.int32(np.round(line_pt1 * frame_scaling)))
    pt2_px = tuple(np.int32(np.round(line_pt2 * frame_scaling)))
    cv2.line(new_event_frame, pt1_px, pt2_px, line_color, line_thickness, line_type)
    
    # Draw all intersection points, colors by cross direction
    for each_class_label, each_results_dict in rule_results_dict.items():
        for each_obj_id, each_obj_results_list in each_results_dict.items():
            for each_intersection_result in each_obj_results_list:
                cross_direction = each_intersection_result["cross_direction"]
                fg_col = (0,0,0) if cross_direction == "forward" else (255,255,255)
                bg_col = (255,255,255) if cross_direction == "forward" else (0,0,0)
                intersection_point = each_intersection_result["intersection_point"]
                circle_pt_px = tuple(np.int32(np.round(intersection_point * frame_scaling)))
                cv2.circle(new_event_frame, circle_pt_px, 5, bg_col, -1, cv2.LINE_AA)
                cv2.circle(new_event_frame, circle_pt_px, 4, fg_col, 1, cv2.LINE_AA)
                
            pass
        pass
    
    return new_event_frame

# .....................................................................................................................

def path_to_configuration_file(configurable_ref):
    
    # Get major pathing info from the configurable
    cameras_folder_path = configurable_ref.cameras_folder_path
    camera_select = configurable_ref.camera_select
    user_select = configurable_ref.user_select
    
    # Get additional pathing info so we can find the config file
    component_name = configurable_ref.component_name
    save_name = configurable_ref.save_filename
    
    return build_after_database_configs_folder_path(cameras_folder_path, camera_select, user_select, 
                                                    component_name, save_name)

# .....................................................................................................................

def load_matching_config(configurable_ref):
    
    # Build pathing to existing configuration file
    load_path = path_to_configuration_file(configurable_ref)
    
    # Load existing config
    config_data = load_json(load_path)
    file_access_dict = config_data["access_info"]
    setup_data_dict = config_data["setup_data"]
    
    # Get target script/class from the configurable, to see if the saved config matches
    target_script_name = configurable_ref.script_name
    target_class_name = configurable_ref.class_name
    
    # Check if file access matches
    script_match = (target_script_name == file_access_dict["script_name"])
    class_match = (target_class_name == file_access_dict["class_name"])
    if script_match and class_match:
        return setup_data_dict
    
    # If file acces doesn't match, return an empty setup dictionary
    no_match_setup_data_dict = {}
    return no_match_setup_data_dict

# .....................................................................................................................

def save_config(configurable_ref, file_dunder = __file__):
    
    # Figure out the name of this configuration script
    config_utility_script_name, _ = os.path.splitext(os.path.basename(file_dunder))
    
    # Get file access info & current configuration data for saving
    file_access_dict, setup_data_dict = configurable_ref.get_data_to_save()
    file_access_dict.update({"configuration_utility": config_utility_script_name})
    save_data = {"access_info": file_access_dict, "setup_data": setup_data_dict}
    
    # Build pathing to existing configuration file
    save_path = path_to_configuration_file(configurable_ref)    
    save_json(save_path, save_data)

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Make user selections

enable_debug_mode = False

# Create selector so we can access existing report data
selector = Resource_Selector()
project_root_path, cameras_folder_path = selector.get_project_pathing()

# Select the camera/user to show data for (needs to have saved report data already!)
camera_select, camera_path = selector.camera(debug_mode=enable_debug_mode)
user_select, _ = selector.user(camera_select, debug_mode=enable_debug_mode)


# ---------------------------------------------------------------------------------------------------------------------
#%% Catalog existing data

cam_db, snap_db, obj_db, class_db, _, rule_db = \
launch_file_db(cameras_folder_path, camera_select, user_select,
               launch_snapshot_db = True,
               launch_object_db = True,
               launch_classification_db = True,
               launch_summary_db = False,
               launch_rule_db = True)

# Catch missing data
cam_db.close()
close_dbs_if_missing_data(snap_db, obj_db)

# Get frame sizing, for the rule
frame_wh = snap_db.get_snap_frame_wh()


# ---------------------------------------------------------------------------------------------------------------------
#%% Ask user for time window

# Get the maximum range of the data (based on the snapshots, because all we can show)
earliest_datetime, latest_datetime = snap_db.get_bounding_datetimes()

# Ask the user for the range of datetimes to use for selecting data
start_dt, end_dt, start_dt_isoformat, end_dt_isoformat = user_input_datetime_range(earliest_datetime, 
                                                                                   latest_datetime, 
                                                                                   enable_debug_mode)

'''
STOPPED HERE
- NEED TO FIGURE OUT SAVING/LOADING SYSTEM FOR ALL RULES
'''

# ---------------------------------------------------------------------------------------------------------------------
#%% Configure the rule



# ---------------------------------------------------------------------------------------------------------------------
#%% Create background frame

# Ask databse for several snapshot images, so we can 'average' them to make a background frame for display
bg_frame = median_background_from_snapshots(snap_db, start_dt, end_dt, 10)
frame_height, frame_width = bg_frame.shape[0:2]
frame_wh = (frame_width, frame_height)
frame_scaling = np.float32((frame_width - 1, frame_height - 1))


# ---------------------------------------------------------------------------------------------------------------------
#%% Load object data

# Get object metadata from the server
obj_metadata_generator = obj_db.load_metadata_by_time_range(start_dt, end_dt)

# Create list of 'reconstructed' objects based on object metadata, so we can work/interact with the object data
obj_list = Obj_Recon.create_reconstruction_list(obj_metadata_generator,
                                                frame_wh,
                                                start_dt, 
                                                end_dt,
                                                smoothing_factor = 0.005)

# Load in classification data, if any
objclass_dict = create_object_class_dict(class_db, obj_list)

# Get object count so we can calculate per-object statistics
num_objects = len(obj_list)

# ---------------------------------------------------------------------------------------------------------------------
#%% Select rule to load

# Load configurable class for this config utility
rule_ref = Linecross_Rule(cameras_folder_path, camera_select, user_select, frame_wh, "unspecified_rule_name")

# Get list of all rule configs
all_rule_configs = load_all_rule_configs(cameras_folder_path, camera_select, user_select,
                                         target_rule_type = rule_ref.rule_type)

# Provide prompt to load existing rule, or create a new one
rule_load_list = ["Create new rule", *all_rule_configs.keys()]
select_idx, select_entry = cli_select_from_list(rule_load_list, "Select rule to load:", 
                                                default_selection = rule_load_list[0],
                                                zero_indexed = True)

load_from_existing_config = (select_idx > 0)
initial_setup_data_dict = {}
loading_rule_name = None
if load_from_existing_config:
    initial_setup_data_dict = all_rule_configs[select_entry]["setup_data"]
    loading_rule_name = select_entry

# Load initial configuration
rule_ref.reconfigure(initial_setup_data_dict)
rule_ref.update_rule_name(loading_rule_name)


# ---------------------------------------------------------------------------------------------------------------------
#%% Draw trails

# Draw all object trails onto the background frame 
trail_frame = create_trail_frame_from_object_reconstruction(bg_frame, obj_list)


# ---------------------------------------------------------------------------------------------------------------------
#%% Set up drawing

line_drawer = Entity_Drawer(frame_wh,
                            minimum_entities=1,
                            maximum_entities=1,
                            minimum_points=2,
                            maximum_points=2)


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
#%% *** DRAW LOOP ***

draw_frame = trail_frame.copy()
event_frame = trail_frame.copy()
wait_for_mouse_up = False

while True:
    
    # Handle updates to the line drawing
    if line_drawer.on_change(wait_for_mouse_up):
        
        # Update the rule
        new_line_entity_list = line_drawer.get_entities_list(normalize = True)
        rule_ref.reconfigure({"line_entity_list": new_line_entity_list})
        
        # Get new results for all objects (with timing info!)
        rule_results_per_class, update_time_ms = update_rule_results(rule_ref, objclass_dict, snap_db, frame_wh)
        
        # Use update timing to decide if we should try to update the rule UI constantly (heavy cpu usage)
        # or if we should wait for the user to let go of the mouse before updating (much lighter!)
        wait_for_mouse_up = (update_time_ms > 200)
        
        # Draw intersection results
        event_frame = update_event_frame(trail_frame, rule_ref, rule_results_per_class)
    
    # Draw rule line onto the frame
    draw_frame = line_drawer.annotate(trail_frame)
    
    # Update displays
    draw_window.imshow(draw_frame)    
    event_window.imshow(event_frame)
    
    # Get keypresses
    keycode, modifier = waitKey_ex(10)
    if keycode_quit(keycode):
        break
    
    line_drawer.keypress_callback(keycode, modifier)

cv2.destroyAllWindows()


# ---------------------------------------------------------------------------------------------------------------------
#%% Save rule configuration

'''
user_confirm_save = cli_confirm("Save linecross rule config?", default_response = False)
if user_confirm_save:
    save_config(rule_ref, __file__)
'''

'''
STOPPED HERE
- NEED TO MAKE LINECROSS RULE CONFIGURABLE
- AND FIGURE OUT SAVING/LOADING
- THEN GET RUN_RULE SCRIPT WORKING!
'''

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap

print("", "DEBUG: Line cross output", sep = "\n")
for each_class_label, each_obj_results_dict in rule_results_per_class.items():
    print("", "Class: {}".format(each_class_label), sep = "\n")
    for each_obj_id, each_results_list in each_obj_results_dict.items():
        print("  Obj", each_obj_id, "results:", each_results_list)
