#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Jul  9 10:04:01 2020

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
from local.configurables.stations._helper_functions import build_cropping_dataset

from local.eolib.video.persistence import Frame_Deck
from local.eolib.video.imaging import get_2d_kernel, crop_pixels_in_place

from local.eolib.utils.colormaps import create_interpolated_colormap


# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes


class Normalized_FTF_Station(Reference_Station):
    
    # .................................................................................................................
    
    def __init__(self, station_name, cameras_folder_path, camera_select, video_wh):
        
        # Inherit from base class
        super().__init__(station_name, cameras_folder_path, camera_select, video_wh, file_dunder = __file__)
        
        # Allocate space for control variables
        self._max_diff_depth = 30
        self._max_blur = 15
        
        # Allocate space for derived variables
        self._crop_y1y2x1x2 = None
        self._cropmask_2d3ch = None
        self._logical_cropmask_1ch = None
        self._ftf_max_count = None
        
        # Allocate space for pre-calculated values
        self._enable_blur = None
        self._blur_kernel = None
        
        # Allocate storage for previous frame data
        max_frames_to_store = (1 + self._max_diff_depth)
        self._frame_deck = Frame_Deck(max_frames_to_store)
        
        # Allocate space for variables to help with visualization during re-configuring
        self._latest_frame_difference_for_config = None
        self._difference_colormap_for_config = None
        
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
        
        self.ctrl_spec.new_control_group("Difference Controls")
        
        self._show_colormap_threshold = \
        self.ctrl_spec.attach_toggle(
                "_show_colormap_threshold",
                label = "Show colored threshold",
                default_value = True,
                tooltip = "Toggle the color mapped display of the thresholded frame data",
                save_with_config = False)
        
        self.difference_depth = \
        self.ctrl_spec.attach_slider(
                "difference_depth",
                label = "Difference depth",
                default_value = 1,
                min_value = 1,
                max_value = self._max_diff_depth,
                return_type = int,
                zero_referenced = True,
                units = "frames",
                tooltip = ["When performing frame differences between the current frame and previous frames,"
                           "this setting allows for selecting a frame 'further back in time'. For example,",
                           "if set to 1, the difference will occur between the current frame and 1 frame backwards",
                           "(i.e the previous frame). A setting of 2 will take the frame prior to the previous",
                           "frame and so on."])
        
        self.blur_size = \
        self.ctrl_spec.attach_slider(
                "blur_size",
                label = "Blurriness",
                default_value = 0,
                min_value = 0,
                max_value = self._max_blur,
                return_type = int,
                tooltip = ["Amount to blur the frame data before taking the frame difference",
                           "Blurring can help avoid errors due to noise and compression artifacts"])
        
        self.difference_threshold = \
        self.ctrl_spec.attach_slider(
                "difference_threshold",
                label = "Difference threshold",
                default_value = 0,
                min_value = 0,
                max_value = 255,
                return_type = int,
                tooltip = ["After taking the frame difference, each value is set to either a 0 or 1,",
                           "depending on whether the value of the difference is below or above",
                           "this threshold (respectively). The output of this station is then the",
                           "(normalized) proportion of pixels that have a value of 1"])
    
    # .................................................................................................................
    
    def close(self, final_frame_index, final_epoch_ms, final_datetime):
        # Nothing open/in-use, so do nothing on close
        return
    
    # .................................................................................................................
    
    def setup(self, variables_changed_dict):
        
        # Resize the frame deck to 'fit' the data storage requirements, if we're not in configuration mode
        if not self.configure_mode:
            max_frames_to_store = (1 + self.difference_depth)
            self._frame_deck.update_max_length(max_frames_to_store, clear_on_resize = True)
        
        # Re-generate crop co-ordinates & logical cropmasks in case the zone was re-drawn
        blur_pad_wh = [1 + self.blur_size] * 2
        zone_crop_coords_list, cropmask_2d3ch_list, logical_cropmasks_1ch_list = \
        build_cropping_dataset(self.video_wh, self.station_zones_list, blur_pad_wh)
        
        # Store crop & masking data for a single zone, since the configuration forces 1 zone only
        self._crop_y1y2x1x2 = zone_crop_coords_list[0]
        self._cropmask_2d3ch = cropmask_2d3ch_list[0]
        self._logical_cropmask_1ch = logical_cropmasks_1ch_list[0]
        
        # Get a single channel mask for applying to grayscale/thresholded values
        self._cropmask_2d1ch = self._cropmask_2d3ch[:,:,0]
        
        # Store the maximum FTF thresholded count, so we can normalize our output
        self._ftf_max_count = np.float32(np.count_nonzero(self._logical_cropmask_1ch))
        
        # Erase frame history if the zones are re-drawn (since different sized zones can't be compared on time)
        keys_that_change_frame_size = ["station_zones_list", "blur_size"]
        frame_size_changed = any([each_key in variables_changed_dict for each_key in keys_that_change_frame_size])
        if frame_size_changed:
            self._frame_deck.clear_deck()
        
        # Pre-calculate blurring kernel for efficiency
        self._enable_blur = (self.blur_size > 0)
        self._blur_kernel = get_2d_kernel(self.blur_size)
        
        # Generate a colormap in case we're re-configuring
        self._difference_colormap_for_config = self._create_config_colormap(self.difference_threshold)
        
        return
    
    # .................................................................................................................
    
    def process_one_frame(self, frame, current_frame_index, current_epoch_ms, current_datetime):
        
        # Crop out the region needed for difference calculations
        cropped_frame = crop_pixels_in_place(frame, self._crop_y1y2x1x2)
        
        # Blur if needed
        if self._enable_blur:
            cropped_frame = cv2.blur(cropped_frame, (self._blur_kernel))
        
        # Update the frame deck with the new frame data & get the backward frame difference
        self._frame_deck.add_to_deck(cropped_frame)
        frame_difference = self._frame_deck.absdiff_from_deck(self.difference_depth)
        
        # Convert to grayscale and apply masking
        frame_difference = cv2.cvtColor(frame_difference, cv2.COLOR_BGR2GRAY)
        frame_difference = cv2.bitwise_and(frame_difference, self._cropmask_2d1ch)
        
        # Store the masked difference frame for visualization during config
        self._latest_frame_difference_for_config = frame_difference
        
        # Apply thresholding and count the number of thresholded pixels
        _, thresh_difference = cv2.threshold(frame_difference, self.difference_threshold, 255, cv2.THRESH_BINARY)
        thresh_count = np.count_nonzero(thresh_difference)
        
        # Normalize the total difference (based on maximum possible difference)
        norm_count = thresh_count / self._ftf_max_count
        norm_count_int = int(round(1000.0 * norm_count))
        
        # Output the normalized thresholded pixel count
        one_frame_result = norm_count_int
        
        return one_frame_result
    
    # .................................................................................................................
    
    def _create_config_colormap(self, thresh_val):
        
        ''' Helper function which generates a colormap for visualizing thresholded data during config '''
        
        # For clarity
        enable_colormap = self._show_colormap_threshold
        off_color = (0, 0, 0)
        thresh_color = (255, 255, 255)
        low_color = (160, 0, 140) if enable_colormap else (0, 0, 0)
        high_color = (25, 70, 255) if enable_colormap else (0, 0, 0)
        
        # If the threshold value is set to 0, the color map shouldn't show thresholded regions
        disabled_colormap_dict = {0: off_color, 1: low_color, 255: high_color}
        
        # At a threshold of 1, the color map should just be binary
        binary_colormap_dict = {0: off_color, 1: thresh_color}
        
        # At all other thresholds, show thresholded regions in white and use color scale everywhere else
        middle_val = int(thresh_val / 2)
        prethresh_val = (thresh_val - 1)
        regular_colormap_dict = {0: off_color,
                                 middle_val: low_color,
                                 prethresh_val: high_color,
                                 thresh_val: thresh_color}
        
        # Decide on which colormap to use (default to 'regular' map)
        colormap_lookup_dict = {0: disabled_colormap_dict, 1: binary_colormap_dict}
        output_colormap_dict = colormap_lookup_dict.get(thresh_val, regular_colormap_dict)
        
        return create_interpolated_colormap(output_colormap_dict)
    
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

# TODO:
# - add downscaling

