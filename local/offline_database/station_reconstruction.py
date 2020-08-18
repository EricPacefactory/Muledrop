#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Jul 31 11:13:14 2020

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

from time import perf_counter
from collections import defaultdict

from local.lib.common.feedback import print_time_taken_ms

from local.lib.audit_tools.imaging import create_single_bar_image, create_single_bar_subset_image, draw_bar_label
from local.lib.audit_tools.imaging import create_combined_bars_image, repeat_color_sequence_to_target_length

from local.lib.file_access_utils.configurables import unpack_config_data


# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes

class Station_Raw_Bars_Display:
    
    # .................................................................................................................
    
    def __init__(self, station_data_dict):
        
        # Store inputs
        self.num_stations = len(station_data_dict)
        self.station_data_dict = station_data_dict
        self.ordered_names_list = sorted(station_data_dict.keys())
        self.color_list = None
        
        # Set up default color list
        default_color_list = create_default_station_color_list()
        self.set_color_list(default_color_list)
    
    # .................................................................................................................
    
    def set_ordered_station_names_list(self, ordered_station_name_list):
        self.ordered_names_list = ordered_station_name_list
    
    # .................................................................................................................
    
    def set_color_list(self, bgr_color_list):
        
        # Repeat colors so that we have enough to color all stations
        full_color_list = repeat_color_sequence_to_target_length(bgr_color_list, self.num_stations)
        self.color_list = full_color_list
    
    # .................................................................................................................
    
    def get_ordered_station_names_list(self, pretty_names = False):
        
        ordered_station_names_list = self.ordered_names_list
        if pretty_names:
            prettify = lambda name: str(name).replace("_", " ").title()
            ordered_station_names_list = [prettify(each_name) for each_name in ordered_station_names_list]
        
        return ordered_station_names_list
    
    # .................................................................................................................
    
    def create_combined_bar_image(self, bar_width,
                                  bar_height = 21,
                                  bar_bg_color = (40,40,40),
                                  prepend_row_image = None,
                                  append_row_image = None):
        
        # Draw a single bar image for each station. We'll eventually stack everything together vertically
        station_bar_imgs_list = [] if prepend_row_image is None else [prepend_row_image]
        for each_stn_idx, each_station_name in enumerate(self.ordered_names_list):
            
            # Get station color and data to plot
            station_color = self.color_list[each_stn_idx]
            each_data_list = self.station_data_dict[each_station_name]
            
            # Generate a bar image based on station data & add to storage
            station_bar_img = create_single_station_bar_image(each_station_name,
                                                              each_data_list,
                                                              bar_width,
                                                              station_color,
                                                              bar_bg_color,
                                                              bar_height)
            station_bar_imgs_list.append(station_bar_img)
        
        # Include additional row image if needed
        if append_row_image is not None:
            station_bar_imgs_list.append(append_row_image)
        
        # Combine all station images together
        combined_bars_image, combined_bars_height = \
        create_combined_bars_image(station_bar_imgs_list)
        
        return combined_bars_image, combined_bars_height
    
    # .................................................................................................................
    
    def create_combined_bar_subset_image(self, start_pt_norm, end_pt_norm, bar_width,
                                         bar_height = 21,
                                         bar_bg_color = (40, 40, 40),
                                         prepend_row_image = None,
                                         append_row_image = None):
        
        # Draw a single subset bar image for each station. We'll eventually stack everything together vertically
        subset_bar_imgs_list = [] if prepend_row_image is None else [prepend_row_image]
        for each_stn_idx, each_station_name in enumerate(self.ordered_names_list):
            
            # Get station color and data to plot
            station_color = self.color_list[each_stn_idx]
            each_data_list = self.station_data_dict[each_station_name]
            
            # Generate a bar image based on station data & add to storage
            subset_bar_img = create_single_station_bar_subset_image(each_station_name,
                                                                    each_data_list,
                                                                    start_pt_norm,
                                                                    end_pt_norm,
                                                                    bar_width,
                                                                    station_color,
                                                                    bar_bg_color,
                                                                    bar_height)
            subset_bar_imgs_list.append(subset_bar_img)
        
        # Include additional row image if needed
        if append_row_image is not None:
            subset_bar_imgs_list.append(append_row_image)
        
        # Combine all bar images together
        subset_combined_bars_image, subset_combined_bars_height = \
        create_combined_bars_image(subset_bar_imgs_list)
        
        return subset_combined_bars_image, subset_combined_bars_height
    
    # .................................................................................................................
    # .................................................................................................................


# =====================================================================================================================
# =====================================================================================================================


class Station_Zone_Display:
    
    # .................................................................................................................
    
    def __init__(self, ordered_station_names_list, station_configs_dict, display_wh):
        
        # Store inputs
        self.ordered_station_names_list = ordered_station_names_list
        self.station_configs_dict = station_configs_dict
        
        # Allocate storage for zone data
        self.display_wh = None
        self.zones_norm_dict = None
        self.zones_px_dict = None
        
        # Calculate initial zone data based on provided display sizing
        self.update_display_wh(display_wh)
    
    # .................................................................................................................
    
    def _get_station_zone_data(self):
        
        ''' Helper function used to grab normalized zone data & calculate pixelized co-ordinates as well '''
        
        # Get frame scaling so we can draw (normalized) zone co-ords onto the displayed image data
        display_width, display_height = self.display_wh
        zone_px_scaling = np.float32((display_width - 1, display_height - 1))
        
        # Try to find the 'zones' for each station
        zones_norm_dict = {}
        zones_px_dict = {}
        for each_station_name in self.ordered_station_names_list:
            
            # Try to load the config data for each individual station
            each_station_config_dict = self.station_configs_dict.get(each_station_name, None)
            no_config_data = (each_station_config_dict is None)
            if no_config_data:
                continue
            
            # Break apart the configuration to get the setup data, so we can look for zone definitions
            _, setup_data_dict = unpack_config_data(each_station_config_dict)
            each_station_zone_list = setup_data_dict.get("station_zones_list", None)
            no_zone_data = (each_station_zone_list is None)
            if no_zone_data:
                continue
            
            # Store normalized zone data
            zones_norm_dict[each_station_name] = each_station_zone_list
            
            # If we got zone data, convert it to pixel co-ordindates for drawing and save it
            each_zone_norm_array = np.float32(each_station_zone_list)
            each_zone_px_array = np.int32(np.round(each_zone_norm_array * zone_px_scaling))
            zones_px_dict[each_station_name] = each_zone_px_array
        
        return zones_norm_dict, zones_px_dict
    
    # .................................................................................................................
    
    def update_display_wh(self, new_display_wh):
        
        self.display_wh = new_display_wh
        
        # Get normalized & pixelized zone data for each station
        zones_norm_dict, zones_px_dict = self._get_station_zone_data()
        
        # Store zone data for re-use
        self.zones_norm_dict = zones_norm_dict
        self.zones_px_dict = zones_px_dict
        
        return

    # .................................................................................................................

    def draw_zone_by_name(self, display_frame, station_name,
                          line_color = (255, 0, 255), thickness = 2, line_type = cv2.LINE_8):
        
        # For clarity
        is_closed = True
        
        # Get station data to draw
        station_zone_px = self.zones_px_dict[station_name]
        
        # Draw zone polygon
        cv2.polylines(display_frame, [station_zone_px], is_closed, line_color, thickness, line_type)
        
        return display_frame
    
    # .................................................................................................................

    def draw_zone_by_index(self, display_frame, ordered_station_index,
                           line_color = (255, 0, 255), thickness = 2, line_type = cv2.LINE_8):
        
        # Get station name and then pass the work onto the 'draw by name' implementation
        station_name = self.ordered_station_names_list[ordered_station_index]
        
        return self.draw_zone_by_name(display_frame, station_name, line_color, thickness, line_type)
    
    # .................................................................................................................
    # .................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Bar imaging functions

# .....................................................................................................................

def create_single_station_bar_image(station_name, station_data_list, bar_width, bar_fg_color,
                                    bar_bg_color = (40, 40, 40), bar_height = 21,
                                    interpolation_type = cv2.INTER_AREA):
    
    ''' Helper function which draws a bar image with the station name added as a label '''
    
    # Create a single bar image
    station_bar_image = create_single_bar_image(station_data_list,
                                                bar_width,
                                                bar_fg_color,
                                                bar_bg_color,
                                                bar_height,
                                                interpolation_type)
    
    # Add the station name as a label to the bar image
    station_bar_image = draw_bar_label(station_bar_image, station_name)
    
    return station_bar_image

# .....................................................................................................................

def create_single_station_bar_subset_image(station_name, station_data_list, start_pt_norm, end_pt_norm,
                                           bar_width, bar_fg_color,
                                           bar_bg_color = (40, 40, 40), bar_height = 21):
    
    # Draw a reduced version of the station data bar image
    station_bar_subset_image = create_single_bar_subset_image(station_data_list,
                                                              start_pt_norm,
                                                              end_pt_norm,
                                                              bar_width, 
                                                              bar_fg_color,
                                                              bar_bg_color,
                                                              bar_height)
    
    # Add the station name as a label
    station_bar_subset_image = draw_bar_label(station_bar_subset_image, station_name)
    
    return station_bar_subset_image

# .....................................................................................................................
# .....................................................................................................................


    


# ---------------------------------------------------------------------------------------------------------------------
#%% Helper functions

# .....................................................................................................................

def create_default_station_color_list():
    
    default_colors_bgr = [(209, 225, 114), (65, 95, 185), (255, 204, 255), (28, 22, 168),
                          (164, 255, 150), (0, 105, 208), (173, 170, 23), (127, 216, 251)]
    
    return default_colors_bgr

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Data reconstruction functions

# .....................................................................................................................

def create_reconstruction_dict(station_database_ref, start_time_ems, end_time_ems,
                               snapshot_first_frame_index = None, snapshot_final_frame_index = None):
    
    # Some feedback
    print("", "Reconstructing station data...", sep = "\n")
    t_start = perf_counter()
    
    # Get all station data in the given time range, as a generator
    all_station_metadata_gen = station_database_ref.load_metadata_by_time_range(start_time_ems, end_time_ems)
    
    # Keep track of overall start/end frame indices
    total_first_index = None
    total_final_index = None
    
    # Join all data in the provided range together in a single continuous list (for each station)
    all_station_data_dict = defaultdict(list)
    for each_data_segment_dict in all_station_metadata_gen:
        
        # Get the start/end indices for each segment
        segment_first_index = each_data_segment_dict["first_frame_index"]
        segment_final_index = each_data_segment_dict["final_frame_index"]
        
        # Record first instances of index
        if total_first_index is None:
            total_first_index = segment_first_index
        
        # Record final instance of index, so we can find the 'most' final
        if total_final_index is None:
            total_final_index = segment_final_index
        
        # Get the overall first/final indices
        if segment_first_index < total_first_index:
            total_first_index = segment_first_index
        if segment_final_index > total_final_index:
            total_final_index = segment_final_index
        
        # Accumulate data from all stations
        station_data_dict = each_data_segment_dict["stations"]
        for each_station_name, each_station_data_list in station_data_dict.items():
            all_station_data_dict[each_station_name] += each_station_data_list
    
    # Finally, decide if we need to trucate the station data lists
    num_station_samples = len(all_station_data_dict[each_station_name])
    truncate_first_idx = 0
    truncate_final_idx = num_station_samples
    need_to_truncate_first = (snapshot_first_frame_index is not None)
    need_to_truncate_final = (snapshot_final_frame_index is not None)
    need_to_truncate = (need_to_truncate_first or need_to_truncate_final)
    
    # Get initial truncation offset if needed
    if need_to_truncate_first:
        first_offset = (snapshot_first_frame_index - total_first_index)
        truncate_first_idx = max(0, first_offset)
    
    # Get final truncation offset if needed
    if need_to_truncate_final:
        final_offset = (1 + snapshot_final_frame_index - total_final_index)
        truncate_final_idx = num_station_samples + min(0, final_offset)
    
    # Apply trucation if needed
    if need_to_truncate:
        for each_station_name, each_station_data_list in all_station_data_dict.items():
            all_station_data_dict[each_station_name] = each_station_data_list[truncate_first_idx:truncate_final_idx]
    
    # Feedback about timing
    t_end = perf_counter()
    num_stations = len(all_station_data_dict)
    print("  {} stations total".format(num_stations))
    print_time_taken_ms(t_start, t_end, prepend_newline = False, inset_spaces = 2)
    
    return all_station_data_dict

# .....................................................................................................................

def load_station_configs(config_info_database_ref):
    
    # Load the appropriate configuration data (HACK FOR NOW, LOAD ALL AND PICK 'NEWEST')
    all_config_dict = config_info_database_ref.get_all_config_info()
    newest_config_dict = all_config_dict[-1]
    all_stations_config_dict = newest_config_dict.get("config", {}).get("stations", {})
    
    return all_stations_config_dict

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Demo

if __name__ == "__main__":
    pass


# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap


