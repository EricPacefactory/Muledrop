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

from local.lib.common.timekeeper_utils import Periodic_Polled_Integer_Counter
from local.lib.common.images import max_dimension_downscale

from local.configurables.externals.snapshot_capture.reference_snapcapture import Reference_Snapshot_Capture


# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes

class Configurable(Reference_Snapshot_Capture):
    
    # .................................................................................................................
    
    def __init__(self, location_select_folder_path, camera_select, video_wh):
        
        # Inherit from reference snapshot implementation
        super().__init__(location_select_folder_path, camera_select, video_wh, file_dunder = __file__)
        
        # Allocate storage for frame counter used to determine when to save snapshots
        self._frame_counter = Periodic_Polled_Integer_Counter()
        
        # Allocate storage for pre-calculated settings
        self._enable_downscale = None
        self._downscale_wh = None
        
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
        
        self.max_dimension_px = \
        self.ctrl_spec.attach_slider(
                "max_dimension_px",
                label = "Max Dimension",
                default_value = 640,
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
                           "Lower values create smaller file sizes at the cost of poorer image quality."])
    
        self.downscale_interpolation = \
        self.ctrl_spec.attach_menu(
                "downscale_interpolation",
                label = "Downscaling Interpolation",
                default_value = "Area",
                option_label_value_list = [("Nearest", cv2.INTER_NEAREST),
                                           ("Bilinear", cv2.INTER_LINEAR),
                                           ("Area", cv2.INTER_AREA)],
                visible = True,
                tooltip = "Set the interpolation style for pixels sampled at fractional indices")
    
    # .................................................................................................................
    
    def reset(self):
        
        # Reset counter, so snapshots can continue to run   
        self._frame_counter.reset_counter()
        
        return
    
    # .................................................................................................................
    
    def get_snapshot_wh(self):
        return self._downscale_wh
        
    # .................................................................................................................
    
    def setup(self, variables_changed_dict):
        
        # Pre-calculate the downscaled frame size (if we need it)
        self._enable_downscale, self._downscale_wh = max_dimension_downscale(self.video_wh, self.max_dimension_px)
        
        # Update jpg quality settings
        self.set_snapshot_quality(self.jpg_quality)
        
        # Update counter trigger
        self._frame_counter.set_count_reset_value(self.skip_frames)
        
        # Force reset, just to ensure consistency while re-configuring
        self.reset()
    
    # .................................................................................................................
    
    def trigger_snapshot(self, input_frame, current_frame_index, current_epoch_ms, current_datetime):
        
        # Use counter logic to decide when to get snapshots!
        need_new_snapshot = self._frame_counter.update_count()
        
        return need_new_snapshot
    
    # .................................................................................................................
    
    def create_snapshot_image(self, snapshot_frame):
        
        # Only apply resizing if needed
        if self._enable_downscale:
            return cv2.resize(snapshot_frame, dsize=self._downscale_wh, interpolation = self.downscale_interpolation)
        
        return snapshot_frame
    
    # .................................................................................................................
    # .................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Demo

if __name__ == "__main__":
    pass

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap


