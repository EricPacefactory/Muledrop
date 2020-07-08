#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Jul  7 16:18:24 2020

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

from local.configurables.stations.reference_station import Reference_Station
from local.configurables.stations._helper_functions import inmask_pixels_1ch, build_cropping_dataset

from local.eolib.video.imaging import crop_pixels_in_place


# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes


class Target_Average_Brightness_Station(Reference_Station):
    
    # .................................................................................................................
    
    def __init__(self, station_name, cameras_folder_path, camera_select, video_wh):
        
        # Inherit from base class
        super().__init__(station_name, cameras_folder_path, camera_select, video_wh, file_dunder = __file__)
        
        # Allocate space for derived variables
        self._crop_y1y2x1x2 = None
        self._cropmask_2d3ch = None
        self._logical_cropmask_1ch = None
        
        # Allocate space for variables to help with visualization during re-configuring
        self._latest_average_brightness_for_config = None
        
        # .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  . Drawing Controls  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .
        
        self.station_zones_list = \
        self.ctrl_spec.attach_drawing(
                "station_zones_list",
                default_value = [[[0.48, 0.48], [0.52, 0.48], [0.52,0.52], [0.48, 0.52]]],
                min_max_entities = (1, 1),
                min_max_points = (3, None),
                entity_type = "polygon",
                drawing_style = "zone")
        
        # .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  . Control Group 1 .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .
        
        self.ctrl_spec.new_control_group("Threshold Controls")
        
        self.high_value = \
        self.ctrl_spec.attach_slider(
                "high_value",
                label = "High brightness value",
                default_value = 250,
                min_value = 0,
                max_value = 255,
                return_type = int,
                tooltip = ["Sets an upper threshold for the target brightness value. Works in combination with",
                           "the low brightness value setting.",
                           "When the average station brightness is equal to or below this upper threshold",
                           "and also equal or above than the low threshold value, this station will",
                           "output a True (1) value. When outside of this range, the output will be False (0).",
                           "More technically:",
                           "  station output = (low value <= avg. station brightness <= high value)"])
        
        self.low_value = \
        self.ctrl_spec.attach_slider(
                "low_value",
                label = "Low brightness value",
                default_value = 10,
                min_value = 0,
                max_value = 255,
                return_type = int,
                tooltip = ["Sets a lower threshold for the target brightness value. Works in combination with",
                           "the high brightness value setting.",
                           "When the average station brightness is equal to or above this lower threshold",
                           "and also equal or lower than the high threshold value, this station will",
                           "output a True (1) value. When outside of this range, the output will be False (0)."])
        
        self.invert_output = \
        self.ctrl_spec.attach_toggle(
                "invert_output",
                label = "Invert output",
                default_value = False,
                tooltip = ["If set to True, the output of the station is inverted compared to normal behavior",
                           "In other words, averaged brightness values within the low-to-high range",
                           "will generate False (0) outputs, otherwise the output will be True (1)."])
    
    # .................................................................................................................
    
    def close(self, final_frame_index, final_epoch_ms, final_datetime):
        # Nothing open/in-use, so do nothing on close
        return
    
    # .................................................................................................................
    
    def setup(self, variables_changed_dict):
        
        # Re-generate crop co-ordinates & logical cropmasks in case the zone was re-drawn
        zone_crop_coords_list, cropmask_2d3ch_list, logical_cropmasks_1ch_list = \
        build_cropping_dataset(self.video_wh, self.station_zones_list)
        
        # Store crop & masking data for a single zone, since the configuration forces 1 zone only
        self._crop_y1y2x1x2 = zone_crop_coords_list[0]
        self._cropmask_2d3ch = cropmask_2d3ch_list[0]
        self._logical_cropmask_1ch = logical_cropmasks_1ch_list[0]
    
    # .................................................................................................................
    
    def process_one_frame(self, frame, current_frame_index, current_epoch_ms, current_datetime):
        
        # Crop & mask the zone
        cropped_frame = crop_pixels_in_place(frame, self._crop_y1y2x1x2)
        cropped_gray_frame = cv2.cvtColor(cropped_frame, cv2.COLOR_BGR2GRAY)
        cropmask_values_1d_array = inmask_pixels_1ch(cropped_gray_frame, self._logical_cropmask_1ch)
        
        # Now average brightness values
        average_brightness = np.int32(np.round(np.mean(cropmask_values_1d_array)))
        
        # Store averaged brightness value for display purposes (only during config)
        self._latest_average_brightness_for_config = average_brightness
        
        # Finally check if the averaged value is in the target range, with inversion if needed
        in_range_check = (self.low_value <= average_brightness <= self.high_value)
        one_frame_result = int(self.invert_output ^ in_range_check)
        
        return one_frame_result
    
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


