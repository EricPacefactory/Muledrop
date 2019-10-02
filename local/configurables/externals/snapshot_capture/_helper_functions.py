#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Oct  1 15:11:15 2019

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

import numpy as np

from local.lib.configuration_utils.display_specification import Display_Window_Specification

from eolib.video.text_rendering import simple_text

# ---------------------------------------------------------------------------------------------------------------------
#%% Define shared displays

class Snap_Display(Display_Window_Specification):
    
    # .................................................................................................................
    
    def __init__(self, layout_index, num_rows, num_columns, initial_display = False):
        
        # Inherit from parent class
        super().__init__("Snapshots", layout_index, num_rows, num_columns, 
                         initial_display = initial_display, 
                         max_wh = None)
        
    # .................................................................................................................
        
    def display(self, stage_outputs, configurable_ref, current_frame_index, current_time_sec, current_datetime):
        
        # Display snapshot data, if available
        new_snap_available = stage_outputs.get("snapshot_capture").get("new_snapshot")
        if new_snap_available:
            return stage_outputs.get("snapshot_capture").get("snapshot_image")
        
    # .................................................................................................................
    # .................................................................................................................


class Snap_Stats_Display(Display_Window_Specification):
    
    # .................................................................................................................
    
    def __init__(self, layout_index, num_rows, num_columns, initial_display = False,
                 window_name = "Statistics"):
        
        # Inherit from parent class
        super().__init__(window_name, layout_index, num_rows, num_columns,
                         initial_display = initial_display, 
                         max_wh = (500, 500))
        
        # Pre-calculate some useful quantities
        self._seconds_per_day = (60 * 60 * 24)
        self._kb_multiplier = (1000 ** 1)
        self._mb_multiplier = (1000 ** 2)
        self._gb_multiplier = (1000 ** 3)
        self._tb_multiplier = (1000 ** 4)
        
        # Pre-calculate some scaling values
        self._bitrate_to_gb_per_day = (self._seconds_per_day / self._gb_multiplier)
        self._days_to_tb_multipler = (self._tb_multiplier / self._seconds_per_day)
        
        # Create blank frame for display
        self._display_frame = np.full((250, 400, 3), (40, 40, 40), dtype=np.uint8)
        
    # .................................................................................................................
        
    def display(self, stage_outputs, configurable_ref, current_frame_index, current_time_sec, current_datetime):
        
        # Display snapshot data, if available
        new_snap_available = stage_outputs.get("snapshot_capture").get("new_snapshot")
        if new_snap_available:
            
            # Update statistics
            snap_period_sec = self._get_snapshot_period_sec(configurable_ref)
            jpg_image_size_bytes = self._get_snap_size_bytes(configurable_ref)
            jpg_comp_time_sec = self._get_compression_time_sec(configurable_ref)
            
            # Crunch some numbers for useful stats printout
            byte_rate = (jpg_image_size_bytes / snap_period_sec)
            bit_rate = (8 * byte_rate)
            gb_per_day = (byte_rate * self._bitrate_to_gb_per_day)
            days_to_terabyte = (self._days_to_tb_multipler / byte_rate)
            ms_to_compress = (1000 * jpg_comp_time_sec)
            jpg_image_size_kb = (jpg_image_size_bytes / self._kb_multiplier)
            
            # Write useful stats into an image for display
            stats_frame = self._display_frame.copy()
            simple_text(stats_frame, "--- Snapshot Image Statistics ---", (200, 15), center_text = True)
            simple_text(stats_frame, "Snapshot size (kB): {:.1f}".format(jpg_image_size_kb), (5, 60))
            simple_text(stats_frame, "Time to compress (ms): {:.1f}".format(ms_to_compress), (5, 100))
            simple_text(stats_frame, "Bit rate: {:.0f}".format(bit_rate).format(bit_rate), (5, 140))
            simple_text(stats_frame, "Daily usage (GB): {:.1f}".format(gb_per_day), (5, 180))
            simple_text(stats_frame, "Days per 1TB: {:.1f}".format(days_to_terabyte), (5, 220))
            
            return stats_frame
        
    # .................................................................................................................
    
    def _get_snapshot_period_sec(self, configurable_ref):
        
        raise NotImplementedError("Override this function with snapshot period information!")
        
        # Example return
        snapshot_period_seconds = configurable_ref._some_variable_storing_period_info
        return snapshot_period_seconds
        
    # .................................................................................................................
    
    def _get_snap_size_bytes(self, configurable_ref):
        return configurable_ref._config_image_size_bytes
    
    # .................................................................................................................
    
    def _get_compression_time_sec(self, configurable_ref):
        return configurable_ref._config_proc_time_sec
    
    # .................................................................................................................
    # .................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

# .....................................................................................................................

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Demo
    
if __name__ == "__main__":
    pass
    

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap


