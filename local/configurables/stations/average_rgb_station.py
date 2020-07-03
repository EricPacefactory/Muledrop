#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Jul  3 11:03:57 2020

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


class Average_RGB_Station(Reference_Station):
    
    # .................................................................................................................
    
    def __init__(self, station_name, cameras_folder_path, camera_select, video_wh):
        
        # Inherit from base class
        super().__init__(station_name, cameras_folder_path, camera_select, video_wh, file_dunder = __file__)
        
        # Allocate space for derived variables
        self._enable_processing = None
        self._zone_crop_coords_list = None
        self._cropmask_2d_list = None
        self._logical_cropmasks_1ch_list = None
        
        # .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  . Drawing Controls  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .
        
        self.station_zones_list = \
        self.ctrl_spec.attach_drawing(
                "station_zones_list",
                default_value = [[[0.48, 0.48], [0.52, 0.48], [0.52,0.52], [0.48, 0.52]]],
                min_max_entities = None,
                min_max_points = (3, None),
                entity_type = "polygon",
                drawing_style = "zone")
        
        # .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  . Control Group 1 .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .
        
        #self.ctrl_spec.new_control_group("General Controls")
    
    # .................................................................................................................
    
    def close(self, final_frame_index, final_epoch_ms, final_datetime):
        # Nothing open/in-use, so do nothing on close
        return
    
    # .................................................................................................................
    
    def setup(self, variables_changed_dict):
        
        # Handle missing zones (most likely a temporary state during configuration)
        self._enable_processing = (len(self.station_zones_list) > 0)
        
        # Re-generate crop co-ordinates & logical cropmasks in case the zone(s) were re-drawn
        self._zone_crop_coords_list, self._cropmask_2d_list, self._logical_cropmasks_1ch_list = \
        build_cropping_dataset(self.video_wh, self.station_zones_list)
    
    # .................................................................................................................
    
    def process_one_frame(self, frame, current_frame_index, current_epoch_ms, current_datetime):
        
        # Handle disable state
        if not self._enable_processing:
            return (0, 0, 0)
        
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
        
        # Now average BGR values and re-arrange as RGB for output
        single_bgr_array = np.vstack(all_pixel_bgr_arrays_list)
        average_bgr = np.round(np.uint8(np.mean(single_bgr_array, axis = 0)))
        one_frame_result = np.flip(average_bgr).tolist()
        
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


