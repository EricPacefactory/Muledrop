#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Sep 12 10:40:07 2019

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

from local.configurables.externals.snapshot_capture.reference_snapcapture import Reference_Snapshot_Capture


# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes

class Snapshot_Capture(Reference_Snapshot_Capture):
    
    # .................................................................................................................
    
    def __init__(self, cameras_folder_path, camera_select, user_select, video_select, video_wh):
        
        # Inherit from reference snapshot implementation
        super().__init__(cameras_folder_path, camera_select, user_select, video_select, video_wh, 
                         file_dunder = __file__)
        
        
        # Allocate storage for fixed-frequency (over time) snapshots
        self._enable_downscale = None
        self.next_snapshot_time_sec = None
        
        # .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  . Control Group 1 .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .
        
        self.ctrl_spec.new_control_group("Snapshot Controls")
        
        self.snapshot_period_hr = \
        self.ctrl_spec.attach_slider(
                "snapshot_period_hr", 
                label = "Snapshot Period (H)", 
                default_value = 0,
                min_value = 0, max_value = 24, step_size = 1,
                return_type = int,
                zero_referenced = True,
                units = "hours",
                tooltip = "Number of hours to wait between saving snapshots (intended for idle objects)")
        
        self.snapshot_period_min = \
        self.ctrl_spec.attach_slider(
                "snapshot_period_min", 
                label = "Snapshot Period (M)", 
                default_value = 0,
                min_value = 0, max_value = 60, step_size = 1,
                return_type = int,
                zero_referenced = True,
                units = "minutes",
                tooltip = "Number of minutes to wait between saving snapshots (intended for idle objects)")
        
        self.snapshot_period_sec = \
        self.ctrl_spec.attach_slider(
                "snapshot_period_sec", 
                label = "Snapshot Period (S)", 
                default_value = 1.0,
                min_value = 0.0, max_value = 60.0, step_size = 1/1000,
                return_type = float,
                zero_referenced = True,
                units = "seconds",
                tooltip = "Number of seconds to wait between saving snapshots")
        
        self.downscale_factor = \
        self.ctrl_spec.attach_slider(
                "downscale_factor", 
                label = "Downscaling", 
                default_value = 1.0,
                min_value = 0.1, max_value = 1.0, step_size = 1/100,
                return_type = float,
                zero_referenced = True,
                tooltip = "Save snapshots at a lowered resolution relative to the input video size")
    
        self.jpg_quality = \
        self.ctrl_spec.attach_slider(
                "jpg_quality",
                label = "Image Quality",
                default_value = 25,
                min_value = 0, max_value = 100,
                return_type = int,
                zero_referenced = True,
                tooltip = ["Quality of jpg compresion when saving snapshots.",
                           "Lower values create smaller file sizes and save a bit faster,",
                           "at the cost of poorer image quality."])
    
    # .................................................................................................................
    
    def reset(self):
        
        # Reset timing, so snapshots can continue to run
        self.next_snapshot_time_sec = None
        
    # .................................................................................................................
    
    def setup(self, variables_changed_dict):
        
        # Pre-calculate the total number of seconds to wait between snapshots
        snap_min_from_hours = self.snapshot_period_hr * 60
        snap_sec_from_mins = (self.snapshot_period_min + snap_min_from_hours) * 60
        self._total_snapshot_period_sec = max(0.001, self.snapshot_period_sec + snap_sec_from_mins)
        
        # Pre-calculate whether we need to downscale or not, just to save repeated evaluations while running
        self._enable_downscale = (self.downscale_factor <= 0.995)   
        
        # Update jpg quality settings
        self.set_snapshot_quality(self.jpg_quality)
        
        # Force reset, for nicer configuration interactions
        self.reset()
    
    # .................................................................................................................
    
    def trigger_snapshot(self, input_frame, current_frame_index, current_time_sec, current_datetime):
        
        # Wrap in try/except, since first evaluation will fail
        try:
            need_new_snapshot = (current_time_sec > self.next_snapshot_time_sec)
            
        except TypeError:
            # Exception thrown on first eval, since we don't have a next_snapshot_time_sec to evaluate
            need_new_snapshot = True
        
        # Update the next snapshot time if we need a snapshot
        if need_new_snapshot:
            self._update_next_snapshot_time(current_time_sec, current_datetime)
        
        return need_new_snapshot
    
    # .................................................................................................................
    
    def create_snapshot_image(self, snapshot_frame):
        
        # Only apply resizing if needed
        if self._enable_downscale:
            return cv2.resize(snapshot_frame, dsize=None, fx = self.downscale_factor, fy = self.downscale_factor)
        
        return snapshot_frame
    
    # .................................................................................................................
    
    def _update_next_snapshot_time(self, current_time_sec, current_datetime):
        
        try:
            # Update next snapshot time based on snapshot period
            prev_snapshot_time = self.next_snapshot_time_sec
            self.next_snapshot_time_sec = prev_snapshot_time + self._total_snapshot_period_sec
            
        except TypeError:
            
            # Will get an error on first run, since previous snapshot time doesn't exist yet!
            prev_snapshot_time = float(1 + int(current_time_sec))
            self.next_snapshot_time_sec = prev_snapshot_time + self._total_snapshot_period_sec
    
    # .................................................................................................................
    # .................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Demo

if __name__ == "__main__":
    
    example_cameras_folder = "/not/a/real/path"
    example_camera_select = "No_Cam"
    example_user_select = "sudo_user"
    example_video_select = "blank_vid.wmv"
    example_video_wh = (50, 50)

    '''
    example_snapcap = Snapshot_Capture(example_cameras_folder, 
                                       example_camera_select, 
                                       example_user_select, 
                                       example_video_select, 
                                       example_video_wh)
    example_snapcap.reconfigure()
    '''

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap


