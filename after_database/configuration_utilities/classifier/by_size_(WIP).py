#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Mar 31 15:32:47 2020

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

from local.offline_database.file_database import launch_file_db, close_dbs_if_missing_data
from local.offline_database.object_reconstruction import Smooth_Hover_Object_Reconstruction as Obj_Recon
from local.offline_database.object_reconstruction import Hover_Mapping
from local.offline_database.object_reconstruction import create_trail_frame_from_object_reconstruction
from local.offline_database.snapshot_reconstruction import median_background_from_snapshots
from local.offline_database.classification_reconstruction import create_objects_by_class_dict, get_ordered_object_list

from local.lib.ui_utils.local_ui.windows_base import Simple_Window

from local.eolib.utils.cli_tools import Datetime_Input_Parser as DTIP

from local.lib.file_access_utils.supervised_labels import load_all_supervised_labels, get_svlabel_topclass_label


# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes


# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

# .....................................................................................................................

def width_height_pair_func(obj_recon_ref, frame_idx):
    
    (x1, y1), (x2, y2) = obj_recon_ref.get_box_tlbr(frame_idx)
    width_norm = (x2 - x1)
    height_norm = (y2 - y1)
    
    return (width_norm, height_norm)

# .....................................................................................................................

def get_data_pair_list(obj_by_class_dict, data_pair_func, print_feedback = True):
    
    # Initialize output. Should contain keys for each object id, storing all width/height samples in a list
    obj_datapair_lists_dict = {}
    
    # Start timing and provide feedback
    t1 = perf_counter()
    if print_feedback:
        print("", "Generating data pair lists...", sep = "\n")
    
    # Loop over every object (of every class) and get all data pair samples
    for each_class_label, each_obj_dict in obj_by_class_dict.items():
        
        # Loop over all object ids
        for each_obj_id, each_obj_recon in each_obj_dict.items():
            
            # Get the start/end frame index of each object
            start_idx = each_obj_recon.start_idx
            end_idx = each_obj_recon.end_idx
            
            # Grab every data pair for each object id
            new_datapair_list = [data_pair_func(each_obj_recon, each_idx) for each_idx in range(start_idx, end_idx)]
            obj_datapair_lists_dict[each_obj_id] = new_datapair_list
    
    # End timing and provide final feedback
    t2 = perf_counter()
    if print_feedback:
        print("  Done! Took {:.0f} ms".format(1000 * (t2 - t1)))
    
    return obj_datapair_lists_dict

# .....................................................................................................................

def draw_one_wh_list(display_frame, wh_list, line_color = (0, 100, 100), line_thickness = 1):
    
    # Get frame scaling so we can draw width/height maps back onto the frame
    frame_height, frame_width = display_frame.shape[0:2]
    frame_scale = np.float32((frame_width - 1, frame_height - 1))
    
    # For clarity
    is_closed = False
    
    # Convert the width/height listings to an array and scale to pixels, so we can draw it into the frame
    wh_array = np.float32(wh_list)
    wh_as_px = np.int32(np.round(wh_array * frame_scale))
    cv2.polylines(display_frame, [wh_as_px], is_closed, line_color, line_thickness, cv2.LINE_AA)
    
    return display_frame

# .....................................................................................................................

def draw_all_wh_list(obj_wh_lists_dict, frame_side_length = 300, line_color = (0, 100, 100), line_thickness = 1):
    
    # Create a blank frame to draw in to
    display_frame = np.zeros((frame_side_length, frame_side_length, 3), dtype=np.uint8)
    
    # Draw every width/height list into the frame
    for each_obj_id, each_wh_list in obj_wh_lists_dict.items():
        
        sv_label = get_svlabel_topclass_label(sv_labels_dict, each_obj_id)
        
        # Skip over the ignores
        if sv_label == "ignore":
            continue
        
        # Hard-code line colors
        line_color = (0, 255, 255)
        if sv_label == "pedestrian":
            line_color = (0, 255, 0)
        if sv_label == "vehicle":
            line_color = (255, 255, 0)
        
        draw_one_wh_list(display_frame, each_wh_list, line_color, line_thickness)
    
    return display_frame

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Make selections

enable_debug_mode = True

# Create selector so we can access existing report data
selector = Resource_Selector()
project_root_path, cameras_folder_path = selector.get_cameras_root_pathing()

# Select the camera to show data for (needs to have saved report data already!)
camera_select, camera_path = selector.camera(debug_mode=enable_debug_mode)

# Bundle pathing args for convenience
pathing_args = (cameras_folder_path, camera_select)


# ---------------------------------------------------------------------------------------------------------------------
#%% Catalog existing data

cinfo_db, snap_db, obj_db, class_db, summary_db = \
launch_file_db(*pathing_args,
               launch_snapshot_db = True,
               launch_object_db = True,
               launch_classification_db = True,
               launch_summary_db = False)

# Catch missing data
cinfo_db.close()
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

# Generate trail hover mapping, for quicker mouse-to-trail lookup
hover_map = Hover_Mapping(obj_by_class_dict)


# ---------------------------------------------------------------------------------------------------------------------
#%% Create initial images

# Generate the background display frame, containing all object trails
trails_background = create_trail_frame_from_object_reconstruction(bg_frame, ordered_obj_list)


#%%

sv_labels_dict = load_all_supervised_labels(*pathing_args, obj_id_list)

# ---------------------------------------------------------------------------------------------------------------------
#%% Interaction loop

# Close any previously open windows
cv2.destroyAllWindows()

# Set up parameter comparison windows
width_height_lists_dict = get_data_pair_list(obj_by_class_dict, width_height_pair_func)
parameter_frame = draw_all_wh_list(width_height_lists_dict)
param_window = Simple_Window("Width vs Height")
param_window.move_corner_pixels(800, 50)
param_window.imshow(parameter_frame)

# Set up main display window
disp_window = Simple_Window("Display")
disp_window.move_corner_pixels(50, 50)
print("", "Press Esc to close", "", sep="\n")

while True:
    
    # Make clean copies of the frames to display, so we don't muddy up the originals
    display_frame = trails_background.copy()
    
    # Show final display
    winexist = disp_window.imshow(display_frame)
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


