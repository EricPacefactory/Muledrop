#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Oct 11 14:58:54 2019

@author: pacefactory
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

from local.lib.selection_utils import Resource_Selector

from local.lib.configuration_utils.local_ui.windows_base import Simple_Window

from local.offline_database.file_database import Snap_DB, Object_DB, Classification_DB
from local.offline_database.file_database import post_snapshot_report_metadata, post_object_report_metadata
from local.offline_database.file_database import post_object_classification_data
from local.offline_database.file_database import user_input_datetime_range
from local.offline_database.object_reconstruction import Smoothed_Object_Reconstruction as Obj_Recon
from local.offline_database.object_reconstruction import create_trail_frame_from_object_reconstruction
from local.offline_database.snapshot_reconstruction import median_background_from_snapshots
from local.offline_database.classification_reconstruction import set_object_classification_and_colors


# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes


# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

# .....................................................................................................................

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Select camera/user/task

enable_debug_mode = False

# Create selector so we can access existing report data
selector = Resource_Selector()
project_root_path, cameras_folder_path = selector.get_project_pathing()

# Select the camera/user/task to show data for (needs to have saved report data already!)
camera_select, camera_path = selector.camera(debug_mode=enable_debug_mode)
user_select, _ = selector.user(camera_select, debug_mode=enable_debug_mode)
task_select, _ = selector.task(camera_select, user_select, debug_mode=enable_debug_mode)


# ---------------------------------------------------------------------------------------------------------------------
#%% Catalog existing snapshot data

# Start 'fake' database for accessing snapshot/object data
snap_db = Snap_DB(cameras_folder_path, camera_select, user_select)
obj_db = Object_DB(cameras_folder_path, camera_select, user_select, task_select)
class_db = Classification_DB(cameras_folder_path, camera_select, user_select, task_select)

# Post snapshot data to the database on start-up
post_snapshot_report_metadata(cameras_folder_path, camera_select, user_select, snap_db)
post_object_report_metadata(cameras_folder_path, camera_select, user_select, task_select, obj_db)
post_object_classification_data(cameras_folder_path, camera_select, user_select, task_select, class_db)

# ---------------------------------------------------------------------------------------------------------------------
#%% Ask user for time window

# Get the maximum range of the data (based on the snapshots, because all we can show)
earliest_datetime, latest_datetime = snap_db.get_bounding_datetimes()

# Ask the user for the range of datetimes to use for selecting data
start_dt, end_dt, start_dt_isoformat, end_dt_isoformat = user_input_datetime_range(earliest_datetime, 
                                                                                   latest_datetime, 
                                                                                   enable_debug_mode)


# ---------------------------------------------------------------------------------------------------------------------
#%% Create background frame

# Ask databse for several snapshot images, so we can 'average' them to make a background frame for display
bg_frame = median_background_from_snapshots(snap_db, start_dt, end_dt, 10)
frame_height, frame_width = bg_frame.shape[0:2]
frame_wh = (frame_width, frame_height)


# ---------------------------------------------------------------------------------------------------------------------
#%% Load object data

# Get object metadata from the server
obj_metadata_generator = obj_db.load_metadata_by_time_range(task_select, start_dt_isoformat, end_dt_isoformat)

# Create list of 'reconstructed' objects based on object metadata, so we can work/interact with the object data
obj_list = Obj_Recon.create_reconstruction_list(obj_metadata_generator,
                                                frame_wh,
                                                start_dt_isoformat, 
                                                end_dt_isoformat,
                                                smoothing_factor = 0.005)

# Load in classification data, if any
set_object_classification_and_colors(class_db, task_select, obj_list)

# ---------------------------------------------------------------------------------------------------------------------
#%% Draw trails


# Draw all object trails onto the background frame 
trail_frame = create_trail_frame_from_object_reconstruction(bg_frame, obj_list)


# ---------------------------------------------------------------------------------------------------------------------
#%% Provide drawing UI

class In_Out_Zone_Rule:
    
    # .................................................................................................................
    
    def __init__(self):
        
        
        self.zones_list = [[]]
        self._zones_array_list = []
        pass
    
    # .................................................................................................................
    
    def reconfigure(self, zones_list):
        
        self.zones_list = zones_list
        self._zones_array_list = [np.float32(each_zone) for each_zone in zones_list]
    
    # .................................................................................................................
    
    def run(self, object_reconstruction):
        
        # Get trail data for convenience
        trail_xy = object_reconstruction.trail_xy
        
        in_zone_count = 0
        out_zone_count = 0
        for each_xy in trail_xy:
            in_zone = self._check_in_zone(each_xy)
            
            if in_zone:
                in_zone_count += 1
            else:
                out_zone_count += 1
                
        total_count = in_zone_count + out_zone_count
        in_pct = 100* in_zone_count / total_count
        out_pct = 100 * out_zone_count / total_count
        print(object_reconstruction.full_id, "In/Out%: {:.1f} / {:.1f}".format(in_pct, out_pct))
    
    # .................................................................................................................
    
    def draw_alarm_image(self, background_frame, object_reconstruction):
        
        # Create a copy of the background frame, so we don't ruin the original
        display_frame = background_frame.copy()
        
        # Get trail data for convenience
        trail_xy = object_reconstruction.trail_xy    
        end_idx = object_reconstruction.end_idx
        
        # Figure out the start/end of the time(s) spent in the in/out zone(s)
        in_zone_segments = []
        start_seg_idx = None
        for each_idx, each_xy in enumerate(trail_xy):
            
            in_zone = self._check_in_zone(each_xy)            
            if in_zone:                
                if start_seg_idx is None:
                    start_seg_idx = each_idx
            else:
                if start_seg_idx is not None:
                    in_zone_segments.append((start_seg_idx, each_idx))
                    start_seg_idx = None
            
        # End-of-trail check
        if start_seg_idx is not None:
            in_zone_segments.append((start_seg_idx, each_idx))
        
        # Overlay each 'in-zone' segment with a differently colored trail!
        for each_in_zone_segment in in_zone_segments:
            
            # Get the start & end frame indices so we can draw the line segment in a different color
            start_frame_idx = end_idx - each_in_zone_segment[1]  #each_in_zone_segment[-1] - 1
            end_frame_idx = end_idx - each_in_zone_segment[0]  # each_in_zone_segment[0] + 1
        
            # Overlay a different color when the object is in the zone(s)
            object_reconstruction.draw_trail_segment(display_frame, start_frame_idx, end_frame_idx, 
                                                     line_color = (0, 0, 255), line_thickness = 4)
        
        # Draw original trail onto the frame
        object_reconstruction.draw_trail(display_frame)
        
        return display_frame
    
    # .................................................................................................................
    
    def _check_in_zone(self, point_xy_norm):
        point_tuple = tuple(point_xy_norm)
        return any((cv2.pointPolygonTest(each_zone, point_tuple, False) > 0 for each_zone in self._zones_array_list))
    
    # .................................................................................................................
    # .................................................................................................................

cv2.destroyAllWindows()

from local.lib.configuration_utils.local_ui.drawing import Entity_Drawer

drawer = Entity_Drawer(frame_wh,
                       minimum_entities=0,
                       maximum_entities=None,
                       minimum_points=3,
                       maximum_points=None)
drawer.aesthetics(finished_color = (255, 0, 255), finished_thickness = 2)

draw_window = Simple_Window("Draw Zone")
draw_window.attach_callback(drawer)




'''
STOPPED HERE
- NEED TO CONTINUE WORK ON RULE EVAL
- GET BETTER VISUALS
- BUILD FULL BLOWN CONFIG UTIL + CONFIGURABLE FILE?!
- NEED TO START THINKING ABOUT HOW RULE IS EVALUATED FOR REAL
    - WHERE DOES DATA GO
    - HOW IS IT FORMATTED
    - HOW IS EVAL TRIGGERED?
    - HOW DOES CLASSIFICATION RUN WITH THIS?!
    
- Config interaction should probably have 2 windows
    - one for drawing zone
    - another for hovering objects
        - clicking on hovered objects should display an example of the alarm image for that object (assuming its breaking the rule)
'''



rule_obj = In_Out_Zone_Rule()

while True:
    
    if drawer.on_change(True):
        print("CHANGED")        
        
        rule_obj.reconfigure(drawer.entity_list)
        
        t_start = perf_counter()
        for each_obj in obj_list:
            rule_obj.run(each_obj)
        t_end = perf_counter()
        
        print("Done! Took {:.0f} ms".format(1000 * (t_end-t_start)))
        print("")
        
    draw_window.imshow(drawer.annotate(trail_frame))
    
    keypress = cv2.waitKey(50)
    if keypress == 27:
        break

#cv2.destroyAllWindows()


draw_frame = bg_frame.copy()
for each_obj in obj_list:
    draw_frame = rule_obj.draw_alarm_image(draw_frame, each_obj)
    

cv2.imshow("HUH", draw_frame); cv2.waitKey(0)

cv2.destroyAllWindows()

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap

