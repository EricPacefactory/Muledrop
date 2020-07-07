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
        self._zone_crop_coords_list = None
        self._cropmask_2d3ch_list = None
        self._logical_cropmasks_1ch_list = None
        
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
                tooltip = [""])
        
        self.low_value = \
        self.ctrl_spec.attach_slider(
                "low_value",
                label = "Low brightness value",
                default_value = 10,
                min_value = 0,
                max_value = 255,
                return_type = int,
                tooltip = [""])
        
        self.invert_output = \
        self.ctrl_spec.attach_toggle(
                "invert_output",
                label = "Invert output",
                default_value = False,
                tooltip = [""])
    
    # .................................................................................................................
    
    def close(self, final_frame_index, final_epoch_ms, final_datetime):
        # Nothing open/in-use, so do nothing on close
        return
    
    # .................................................................................................................
    
    def setup(self, variables_changed_dict):
        
        # Re-generate crop co-ordinates & logical cropmasks in case the zone(s) were re-drawn
        self._zone_crop_coords_list, self._cropmask_2d3ch_list, self._logical_cropmasks_1ch_list = \
        build_cropping_dataset(self.video_wh, self.station_zones_list)
    
    # .................................................................................................................
    
    def process_one_frame(self, frame, current_frame_index, current_epoch_ms, current_datetime):
        
        # Apply cropping + masking for each of the defined zone to get all
        all_pixel_brightness_arrays_list = []
        for each_zone_idx, each_zone in enumerate(self.station_zones_list):
            
            # Get pre-calculate zone resources
            zone_crop_coordinates = self._zone_crop_coords_list[each_zone_idx]
            zone_cropmask_1d_logical = self._logical_cropmasks_1ch_list[each_zone_idx]
            
            # Crop each zone
            cropped_frame = crop_pixels_in_place(frame, zone_crop_coordinates)
            
            # Convert to brightness (grayscale) values
            cropped_gray_frame = cv2.cvtColor(cropped_frame, cv2.COLOR_BGR2GRAY)
            
            # Apply cropped mask to each cropped piece
            cropmask_values_1d_array = inmask_pixels_1ch(cropped_gray_frame, zone_cropmask_1d_logical)
            
            # Add brightness values to total list
            all_pixel_brightness_arrays_list.append(cropmask_values_1d_array)
        
        # Now average brightness values
        single_brightness_array = np.vstack(all_pixel_brightness_arrays_list)
        average_brightness = np.int32(np.round(np.mean(single_brightness_array)))
        
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


