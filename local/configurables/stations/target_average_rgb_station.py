#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Jul  7 14:03:49 2020

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

from local.configurables.stations.reference_station import Reference_Station
from local.configurables.stations._helper_functions import inmask_pixels_3ch, build_cropping_dataset

from local.eolib.video.imaging import crop_pixels_in_place


# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes


class Target_Average_RGB_Station(Reference_Station):
    
    # .................................................................................................................
    
    def __init__(self, station_name, cameras_folder_path, camera_select, video_wh):
        
        # Inherit from base class
        super().__init__(station_name, cameras_folder_path, camera_select, video_wh, file_dunder = __file__)
        
        # Allocate space for derived variables
        self._zone_crop_coords_list = None
        self._cropmask_2d3ch_list = None
        self._logical_cropmasks_1ch_list = None
        
        # Allocate space for numpy-based range checks
        self._low_check_array = None
        self._high_check_array = None
        self._invert_array = None
        
        # Allocate space for variables to help with visualization during re-configuring
        self._latest_average_bgr_for_config = None
        
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
        
        self.ctrl_spec.new_control_group("Red Controls")
        
        self.high_red = \
        self.ctrl_spec.attach_slider(
                "high_red",
                label = "High value (red)",
                default_value = 250,
                min_value = 0,
                max_value = 255,
                return_type = int,
                tooltip = ["Sets an upper threshold for the averaged red value of the station. Together with",
                           "the lower threshold value, the red-channel output is considered to be within",
                           "the target range if the averaged red channel value is between the",
                           "lower and upper threshold values (inclusive on both ends). This check is repeated",
                           "for the green & blue channels, with the final station output being the result",
                           "of evaluating if the averaged RGB value is within the red AND green AND blue ranges.",
                           "More technically:",
                           "  in-red-range = (low red <= avg. red channel value <= high red)",
                           "  final output = (in-red-range AND in-green-range AND in-blue-range)"])
        
        self.low_red = \
        self.ctrl_spec.attach_slider(
                "low_red",
                label = "Low value (red)",
                default_value = 10,
                min_value = 0,
                max_value = 255,
                return_type = int,
                tooltip = ["Sets the lower threshold for the average red value of the station. Works together",
                           "with the upper threshold value to determine if the red-channel is considered to be",
                           "within the target range.",
                           "See the 'High value (red)' tooltip for more details."])
        
        self.invert_red = \
        self.ctrl_spec.attach_toggle(
                "invert_red",
                label = "Invert red target",
                default_value = False,
                tooltip = ["If set to True, inverts the normal behavior of the red-channel evaluation.",
                           "In other words, the in-red-range check acts more like an out-of-red-range check,",
                           "so that averaged red values within the low/high red values evaluate to False (0)",
                           "while values outside the range evaluate to True (1).",
                           "See the 'High value (red)' tooltip for more details."])
        
        # .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  . Control Group 2 .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .
        
        self.ctrl_spec.new_control_group("Green Controls")
        
        self.high_green = \
        self.ctrl_spec.attach_slider(
                "high_green",
                label = "High value (green)",
                default_value = 255,
                min_value = 0,
                max_value = 255,
                return_type = int,
                tooltip = ["Sets the upper threshold for the average green value of the station",
                           "See the 'High value (red)' tooltip for more details."])
        
        self.low_green = \
        self.ctrl_spec.attach_slider(
                "low_green",
                label = "Low value (green)",
                default_value = 0,
                min_value = 0,
                max_value = 255,
                return_type = int,
                tooltip = ["Sets the lower threshold for the average green value of the station",
                           "See the 'High value (red)' tooltip for more details."])
        
        self.invert_green = \
        self.ctrl_spec.attach_toggle(
                "invert_green",
                label = "Invert green target",
                default_value = False,
                tooltip = ["If True, inverts the normal behavior of the green-channel evaluation.",
                           "See the 'Invert red target' and 'High value (red)' tooltips for more details."])
        
        # .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  . Control Group 3 .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .
        
        self.ctrl_spec.new_control_group("Blue Controls")
        
        self.high_blue = \
        self.ctrl_spec.attach_slider(
                "high_blue",
                label = "High value (blue)",
                default_value = 255,
                min_value = 0,
                max_value = 255,
                return_type = int,
                tooltip = ["Sets the upper threshold for the average blue value of the station",
                           "See the 'High value (red)' tooltip for more details."])
        
        self.low_blue = \
        self.ctrl_spec.attach_slider(
                "low_blue",
                label = "Low value (blue)",
                default_value = 0,
                min_value = 0,
                max_value = 255,
                return_type = int,
                tooltip = ["Sets the lower threshold for the average blue value of the station",
                           "See the 'High value (red)' tooltip for more details."])
        
        self.invert_blue = \
        self.ctrl_spec.attach_toggle(
                "invert_blue",
                label = "Invert blue target",
                default_value = False,
                tooltip = ["If True, inverts the normal behavior of the blue-channel evaluation.",
                           "See the 'Invert red target' and 'High value (red)' tooltips for more details."])
    
    # .................................................................................................................
    
    def close(self, final_frame_index, final_epoch_ms, final_datetime):
        # Nothing open/in-use, so do nothing on close
        return
    
    # .................................................................................................................
    
    def setup(self, variables_changed_dict):
        
        # Re-generate crop co-ordinates & logical cropmasks in case the zone(s) were re-drawn
        self._zone_crop_coords_list, self._cropmask_2d3ch_list, self._logical_cropmasks_1ch_list = \
        build_cropping_dataset(self.video_wh, self.station_zones_list)
        
        # Pre-generate comparison arrays to speed up in-range checks
        self._low_check_array = np.int32((self.low_blue, self.low_green, self.low_red))
        self._high_check_array = np.int32((self.high_blue, self.high_green, self.high_red))
        self._invert_array = np.int32((self.invert_blue, self.invert_green, self.invert_red))
    
    # .................................................................................................................
    
    def process_one_frame(self, frame, current_frame_index, current_epoch_ms, current_datetime):
        
        # Apply cropping + masking for each of the defined zone to get all
        all_pixel_bgr_arrays_list = []
        for each_zone_idx, each_zone in enumerate(self.station_zones_list):
            
            # Get pre-calculate zone resources
            zone_crop_coordinates = self._zone_crop_coords_list[each_zone_idx]
            zone_cropmask_1d_logical = self._logical_cropmasks_1ch_list[each_zone_idx]
            
            # Crop each zone
            cropped_frame = crop_pixels_in_place(frame, zone_crop_coordinates)
            
            # Apply cropped mask to each cropped piece
            cropmask_values_1d_array = inmask_pixels_3ch(cropped_frame, zone_cropmask_1d_logical)
            
            # Accumulate BGR values to total list
            all_pixel_bgr_arrays_list.append(cropmask_values_1d_array)
        
        # Now average BGR values
        single_bgr_array = np.vstack(all_pixel_bgr_arrays_list)
        average_bgr = np.round(np.int32(np.mean(single_bgr_array, axis = 0)))
        
        # Store averaged BGR value for display purposes (only during config)
        self._latest_average_bgr_for_config = average_bgr
        
        # Check each of the red/green/blue values to see if they are in the proper ranges
        in_range_check = np.bitwise_and(average_bgr >= self._low_check_array, average_bgr <= self._high_check_array)
        invert_check = np.bitwise_xor(in_range_check, self._invert_array)
        one_frame_result = int(np.all(invert_check))
        
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


