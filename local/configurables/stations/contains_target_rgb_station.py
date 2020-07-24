#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Jul  8 11:12:15 2020

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


class Configurable(Reference_Station):
    
    # .................................................................................................................
    
    def __init__(self, station_name, location_select_folder_path, camera_select, video_wh):
        
        # Inherit from base class
        super().__init__(station_name, location_select_folder_path, camera_select, video_wh, file_dunder = __file__)
        
        # Allocate space for derived variables
        self._crop_y1y2x1x2 = None
        self._cropmask_2d3ch = None
        self._logical_cropmask_1ch = None
        self._in_range_max_count = None
        self._count_gamma_power = None
        self._needs_gamma_correct = None
        
        # Allocate space for numpy-based range checks
        self._low_check_array = None
        self._high_check_array = None
        self._invert_array = None
        
        # Allocate space for variables to help with visualization during re-configuring
        self._latest_norm_count_int_for_config = None
        
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
                tooltip = ["Only pixels whose red channel is less than (or equal) to this value will be",
                           "'counted' as being in the drawn station"])
        
        self.low_red = \
        self.ctrl_spec.attach_slider(
                "low_red",
                label = "Low value (red)",
                default_value = 10,
                min_value = 0,
                max_value = 255,
                return_type = int,
                tooltip = ["Only pixels whose red channel is greater (or equal) to this value will be",
                           "'counted' as being in the drawn station"])
        
        self.invert_red = \
        self.ctrl_spec.attach_toggle(
                "invert_red",
                label = "Invert red target",
                default_value = False,
                tooltip = ["If True, the normal red channel behavior will be inverted, so that pixels",
                           "outside the upper/lower range will be counted as being in the station"])
        
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
                tooltip = ["Only pixels whose green channel is less than (or equal) to this value will be",
                           "'counted' as being in the drawn station"])
        
        self.low_green = \
        self.ctrl_spec.attach_slider(
                "low_green",
                label = "Low value (green)",
                default_value = 0,
                min_value = 0,
                max_value = 255,
                return_type = int,
                tooltip = ["Only pixels whose green channel is greater (or equal) to this value will be",
                           "'counted' as being in the drawn station"])
        
        self.invert_green = \
        self.ctrl_spec.attach_toggle(
                "invert_green",
                label = "Invert green target",
                default_value = False,
                tooltip = ["If True, the normal green channel behavior will be inverted, so that pixels",
                           "outside the upper/lower range will be counted as being in the station"])
        
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
                tooltip = ["Only pixels whose blue channel is less than (or equal) to this value will be",
                           "'counted' as being in the drawn station"])
        
        self.low_blue = \
        self.ctrl_spec.attach_slider(
                "low_blue",
                label = "Low value (blue)",
                default_value = 0,
                min_value = 0,
                max_value = 255,
                return_type = int,
                tooltip = ["Only pixels whose blue channel is greater (or equal) to this value will be",
                           "'counted' as being in the drawn station"])
        
        self.invert_blue = \
        self.ctrl_spec.attach_toggle(
                "invert_blue",
                label = "Invert blue target",
                default_value = False,
                tooltip = ["If True, the normal blue channel behavior will be inverted, so that pixels",
                           "outside the upper/lower range will be counted as being in the station"])
    
        # .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  . Control Group 4 .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .
        
        self.ctrl_spec.new_control_group("Count Controls")
        
        self.high_count = \
        self.ctrl_spec.attach_slider(
                "high_count",
                label = "High count",
                default_value = 1000,
                min_value = 0,
                max_value = 1000,
                return_type = int,
                units = "normalized",
                tooltip = ["When the (normalized) count of target RGB pixels is below this value",
                           "and above the low count threshold, the station will output a True (1) value",
                           "otherwise it will output a False (0) value"])
        
        self.low_count = \
        self.ctrl_spec.attach_slider(
                "low_count",
                label = "Low count",
                default_value = 500,
                min_value = 0,
                max_value = 1000,
                return_type = int,
                units = "normalized",
                tooltip = ["When the (normalized) count of target RGB pixels is above this value",
                           "and below the high count threshold, the station will output a True (1) value",
                           "otherwise it will output a False (0) value"])
        
        self.invert_count = \
        self.ctrl_spec.attach_toggle(
                "invert_count",
                label = "Invert count target",
                default_value = False,
                tooltip = ["If True, the count thresholding behavior is inverted, so that the station",
                           "will output True (1) when the count is outside the low-to-high count range",
                           "and False (0) when inside the range"])
        
        self.count_correction = \
        self.ctrl_spec.attach_slider(
                "count_correction",
                label = "Count scaling correction",
                default_value = 0,
                min_value = -50,
                max_value = 50,
                step_size = 1,
                return_type = int,
                tooltip = ["This value applies a gamma correction to the normalized count value before",
                           "applying the low/high thresholding. This allows scaling the count values up or down",
                           "It is intended to be used to provide better resolution on values in cases",
                           "where the counts may be consistently near the lowest or highest",
                           "end of the full scale"])
    
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
        
        # Store the maximum number of pixels we could get 'in-range', after accounting for masking
        self._in_range_max_count = np.float32(np.count_nonzero(self._logical_cropmask_1ch))
        
        # Pre-generate comparison arrays to speed up in-range checks
        self._low_check_array = np.int32((self.low_blue, self.low_green, self.low_red))
        self._high_check_array = np.int32((self.high_blue, self.high_green, self.high_red))
        self._invert_array = np.int32((self.invert_blue, self.invert_green, self.invert_red))
        
        # Pre-generate gamma correction factor and decide if we even need to use it!
        self._needs_gamma_correct = (self.count_correction != 0)
        self._count_gamma_power = np.power(1.075, self.count_correction)
    
    # .................................................................................................................
    
    def process_one_frame(self, frame, current_frame_index, current_epoch_ms, current_datetime):
        
        # Crop & mask the zone
        cropped_frame = crop_pixels_in_place(frame, self._crop_y1y2x1x2)
        cropmask_values_1d_array = inmask_pixels_3ch(cropped_frame, self._logical_cropmask_1ch)
        
        # For convenience
        red_ch = cropmask_values_1d_array[:, 2]
        green_ch = cropmask_values_1d_array[:, 1]
        blue_ch = cropmask_values_1d_array[:, 0]
        
        # Figure out which pixels are in the correct rgb target range
        in_red_range = self._check_in_range(red_ch, self.low_red, self.high_red, self.invert_red)
        in_green_range = self._check_in_range(green_ch, self.low_green, self.high_green, self.invert_green)
        in_blue_range = self._check_in_range(blue_ch, self.low_blue, self.high_blue, self.invert_blue)        
        in_rgb_range = np.bitwise_and(in_red_range, in_green_range, in_blue_range)
        
        # Count the number of pixels in range and normalize to a 0-1000 integer value
        num_pixels_in_range = np.float32(np.count_nonzero(in_rgb_range))
        norm_count = (num_pixels_in_range / self._in_range_max_count)
        if self._needs_gamma_correct:
            norm_count = np.power(norm_count, self._count_gamma_power)
        norm_count_int = int(round(1000 * norm_count))
        
        # Store integer normalized count for display purposes (only during config)
        self._latest_norm_count_int_for_config = norm_count_int
        
        # Output is determined based on pixel count being within a target range
        one_frame_result = int(self.invert_count ^ (self.low_count <= norm_count_int <= self.high_count))
        
        return one_frame_result
    
    # .................................................................................................................
    
    def _check_in_range(self, channel_values, low_value, high_value, invert_result):
        
        ''' Helper function for checking which pixels (in a given channel!) are in the target range '''
        
        return np.bitwise_xor(invert_result, np.bitwise_and(channel_values >= low_value, channel_values <= high_value))
    
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


