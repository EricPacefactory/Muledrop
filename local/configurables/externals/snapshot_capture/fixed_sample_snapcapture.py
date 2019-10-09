#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Sep 12 13:04:45 2019

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
        
        # Allocate storage for pre-calculated settings
        self._enable_downscale = None
        self._skip_frames_remainder = None
        
        # Allocate storage for keeping track of (approximate) snapshot period
        self._last_snap_time_sec = 0.0
        self._approx_snap_period_sec = -1.0        
        
        # .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  . Control Group 1 .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .
        
        self.ctrl_spec.new_control_group("Snapshot Controls")
        
        self.skip_frames = \
        self.ctrl_spec.attach_slider(
                "skip_frames", 
                label = "Skip Frames", 
                default_value = 30,
                min_value = 0, max_value = 1000,
                return_type = int,
                zero_referenced = True,
                units = "frames",
                tooltip = "Amount of frames to skip between saving snapshots")
        
        self.downscale_factor = \
        self.ctrl_spec.attach_slider(
                "downscale_factor", 
                label = "Downscaling", 
                default_value = 1.0,
                min_value = 0.1, max_value = 1.0, step_size = 1/100,
                return_type = float,
                zero_referenced = True,
                tooltip = "Save snapshots at a lowered resolution")
    
        self.jpg_quality = \
        self.ctrl_spec.attach_slider(
                "jpg_quality", 
                label = "Image Quality", 
                default_value = 25,
                min_value = 0, max_value = 100,
                return_type = int,
                zero_referenced = True,
                tooltip = ["Quality of jpg compresion when saving snapshots.",
                           "Lower values create smaller file sizes at the cost of poorer image quality."])
    
    # .................................................................................................................
    
    def reset(self):
        # No storage, so nothing to reset!
        pass
        
    # .................................................................................................................
    
    def setup(self, variables_changed_dict):
        
        # Pre-calculate the value used in frame skip remainder checks
        self._skip_frames_remainder = 1 + self.skip_frames
        
        # Pre-calculate whether we need to downscale or not
        self._enable_downscale = (self.downscale_factor <= 0.995)   
        
        # Update jpg quality settings
        self.set_snapshot_quality(self.jpg_quality)
    
    # .................................................................................................................
    
    def trigger_snapshot(self, input_frame, current_frame_index, current_time_sec, current_datetime):
        
        # Simple remainder check to subsample frames
        frame_index_remainder = ((current_frame_index - 1) % self._skip_frames_remainder)
        need_new_snapshot = (frame_index_remainder == 0)
        
        # Try to keep track of how long it takes to get a snapshot
        if need_new_snapshot:
            self._approx_snap_period_sec = current_time_sec - self._last_snap_time_sec
            self._last_snap_time_sec = current_time_sec            
        
        return need_new_snapshot
    
    # .................................................................................................................
    
    def create_snapshot_image(self, snapshot_frame):
        
        # Only apply resizing if needed
        if self._enable_downscale:
            return cv2.resize(snapshot_frame, dsize=None, fx = self.downscale_factor, fy = self.downscale_factor)
        
        return snapshot_frame
    
    # .................................................................................................................
    # .................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Demo

if __name__ == "__main__":    
    pass

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap


