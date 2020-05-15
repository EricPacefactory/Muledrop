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
from local.configurables.externals.snapshot_capture._helper_functions import max_dimension_downscale


# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes

class Snapshot_Capture(Reference_Snapshot_Capture):
    
    # .................................................................................................................
    
    def __init__(self, cameras_folder_path, camera_select, user_select, video_select, video_wh):
        
        # Inherit from reference snapshot implementation
        super().__init__(cameras_folder_path, camera_select, user_select, video_select, video_wh, 
                         file_dunder = __file__)
        
        # Allocate storage for fixed-frequency (over time) snapshots settings
        self._enable_downscale = None
        self._downscale_wh = None
        self._next_snapshot_time_ms = None
        self._total_snapshot_period_ms = None
        
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
        
        self.max_dimension_px = \
        self.ctrl_spec.attach_slider(
                "max_dimension_px", 
                label = "Max Dimension", 
                default_value = 800,
                min_value = 100, max_value = 1280,
                units = "pixels",
                return_type = int,
                zero_referenced = True,
                tooltip = "Save snapshots at a resolution where the maximum side length is no larger than this value")
    
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
    
        self.downscale_interpolation = \
        self.ctrl_spec.attach_menu(
                "downscale_interpolation", 
                label = "Downscaling Interpolation", 
                default_value = "Nearest",
                option_label_value_list = [("Nearest", cv2.INTER_NEAREST),
                                           ("Bilinear", cv2.INTER_LINEAR),
                                           ("Cubic", cv2.INTER_CUBIC)],
                visible = False,
                tooltip = "Set the interpolation style for pixels sampled at fractional indices")
    
    # .................................................................................................................
    
    def reset(self):
        
        # Reset timing, so snapshots can continue to run
        self._next_snapshot_time_ms = None
        
    # .................................................................................................................
    
    def get_snapshot_wh(self):
        return self._downscale_wh
        
    # .................................................................................................................
    
    def setup(self, variables_changed_dict):
        
        # Pre-calculate the total number of seconds to wait between snapshots
        snap_min_from_hours = self.snapshot_period_hr * 60
        snap_sec_from_mins = (self.snapshot_period_min + snap_min_from_hours) * 60
        total_snapshot_period_sec = max(0.001, self.snapshot_period_sec + snap_sec_from_mins)
        self._total_snapshot_period_ms = int(round(1000 * total_snapshot_period_sec))
        
        # Pre-calculate the downscaled frame size (if we need it)
        self._enable_downscale, self._downscale_wh = max_dimension_downscale(self.video_wh, self.max_dimension_px)
        
        # Update jpg quality settings
        self.set_snapshot_quality(self.jpg_quality)
        
        # Force reset, for nicer configuration interactions
        self.reset()
    
    # .................................................................................................................
    
    def trigger_snapshot(self, input_frame, current_frame_index, current_epoch_ms, current_datetime):
        
        # Wrap in try/except, since first evaluation will fail
        try:
            need_new_snapshot = (current_epoch_ms > self._next_snapshot_time_ms)
            
        except TypeError:
            # Exception thrown on first eval, since we don't have a next_snapshot_time_ms to evaluate
            need_new_snapshot = True
        
        # Update the next snapshot time if we need a snapshot
        if need_new_snapshot:
            self._next_snapshot_time_ms = self._calculate_next_snapshot_time_ms(current_epoch_ms, current_datetime)
        
        return need_new_snapshot
    
    # .................................................................................................................
    
    def create_snapshot_image(self, snapshot_frame):
        
        # Only apply resizing if needed
        if self._enable_downscale:
            return cv2.resize(snapshot_frame, dsize=self._downscale_wh, interpolation = self.downscale_interpolation)
        
        return snapshot_frame
    
    # .................................................................................................................
    
    def _calculate_next_snapshot_time_ms(self, current_epoch_ms, current_datetime):
        
        try:
            # Update next snapshot time based on snapshot period
            # (add to the previous 'next_time' instead of the current time, so we don't accumulate timing errors)
            next_snapshot_time_ms = self._next_snapshot_time_ms + self._total_snapshot_period_ms
            
        except TypeError:
            
            # Will get an error on first run, since the value of '_next_snapshot_time_ms' doesn't exist yet!
            next_snapshot_time_ms = current_epoch_ms + self._total_snapshot_period_ms
        
        # Check that the newly calculated time isn't already in the past
        # (may happen if the camera disconnects or hangs for a while)
        if next_snapshot_time_ms < current_epoch_ms:
            next_snapshot_time_ms = current_epoch_ms + self._total_snapshot_period_ms
        
        return next_snapshot_time_ms
    
    # .................................................................................................................
    # .................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Demo

if __name__ == "__main__":
    pass

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap


