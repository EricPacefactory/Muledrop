#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Jul  8 11:30:12 2020

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

from local.lib.launcher_utils.configuration_loaders import Reconfigurable_Single_Station_Loader
from local.lib.launcher_utils.video_processing_loops import Station_Processing_Video_Loop

from local.lib.ui_utils.display_specification import Input_Display

from local.configurables.stations._helper_functions import Zoomed_Station_Display
from local.configurables.stations._helper_functions import Leveled_Data_Display, Boolean_Result_Display


# ---------------------------------------------------------------------------------------------------------------------
#%% Define displays

class Count_Levels_Display(Leveled_Data_Display):
    
    # .................................................................................................................
    
    def __init__(self, layout_index, num_rows, num_columns, initial_display = False,
                 lower_level_color = (150, 150, 150),
                 upper_level_color = (125, 125, 125),
                 display_width = 500,
                 display_height = 256):
        
        # Inherit from parent class
        super().__init__(layout_index, num_rows, num_columns, initial_display,
                         window_name = "Count (Levels)",
                         ch1_color = (255, 255, 255),
                         minimum_value = 0,
                         maximum_value = 1000,
                         lower_level_color = lower_level_color,
                         upper_level_color = upper_level_color,
                         display_width = display_width,
                         display_height = display_height)
    
    # .................................................................................................................
    
    def get_levels(self, configurable_ref):
        return (configurable_ref.low_count, configurable_ref.high_count)
    
    # .................................................................................................................
    
    def get_latest_plot_data(self, configurable_ref):
        return configurable_ref._latest_norm_count_int_for_config
    
    # .................................................................................................................
    # .................................................................................................................


# =====================================================================================================================
# =====================================================================================================================


class Station_Display(Zoomed_Station_Display):
    
    # .................................................................................................................
    
    def __init__(self, layout_index, num_rows, num_columns, initial_display = False):
        
        # Inherit from parent class
        super().__init__(layout_index, num_rows, num_columns, initial_display = initial_display)
    
    # .................................................................................................................
    
    def postprocess_cropmasked_frame(self, cropmasked_frame, configurable_ref):
        
        # Get each color channel separately for convenience
        red_ch_img = cropmasked_frame[:, :, 2]
        green_ch_img = cropmasked_frame[:, :, 1]
        blue_ch_img = cropmasked_frame[:, :, 0]
        
        # Get masking based on red channel settings
        low_red = configurable_ref.low_red
        high_red = configurable_ref.high_red
        invert_red = configurable_ref.invert_red
        red_ch_mask = configurable_ref._check_in_range(red_ch_img, low_red, high_red, invert_red)
        
        # Get masking based on green channel settings
        low_green = configurable_ref.low_green
        high_green = configurable_ref.high_green
        invert_green = configurable_ref.invert_green
        green_ch_mask = configurable_ref._check_in_range(green_ch_img, low_green, high_green, invert_green)
        
        # Get masking based on blue channel settings
        low_blue = configurable_ref.low_blue
        high_blue = configurable_ref.high_blue
        invert_blue = configurable_ref.invert_blue
        blue_ch_mask = configurable_ref._check_in_range(blue_ch_img, low_blue, high_blue, invert_blue)
        
        # Create a mask from the separate channels, which we'll apply to the proper color image for display
        combined_mask_1ch = np.uint8(255 * np.bitwise_and(blue_ch_mask, np.bitwise_and(green_ch_mask, red_ch_mask)))
        combined_mask_3ch = cv2.cvtColor(combined_mask_1ch, cv2.COLOR_GRAY2BGR)
        
        return cv2.bitwise_and(cropmasked_frame, combined_mask_3ch)
    
    # .................................................................................................................
    # .................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Main

# For clarity
target_script_name = "contains_target_rgb_station"
target_class_name = "Contains_Target_RGB_Station"

# Make all required selections
loader = Reconfigurable_Single_Station_Loader(target_script_name, target_class_name)
arg_selections = loader.parse_standard_args()
loader.selections(*arg_selections)
loader.select_station()

# Set up video capture, processing stages & playback control
configurable_ref = loader.setup_all(__file__)

# Get drawing specification for the given edge decay variable
zone_drawing_spec = configurable_ref.get_drawing_spec("station_zones_list")

# Set up object to handle all video processing
main_process = \
Station_Processing_Video_Loop(loader,
                              ordered_display_list = [Boolean_Result_Display(1, 1, 4),
                                                      Count_Levels_Display(0, 4, 1),
                                                      Station_Display(2, 3, 3),
                                                      Input_Display(1, 4, 1,
                                                                    window_name = "Draw Station Zones",
                                                                    drawing_json = zone_drawing_spec)])

# Most of the work is done here!
main_process.loop()

# Ask user to save config
loader.ask_to_save_configurable_cli(__file__, configurable_ref)


# ---------------------------------------------------------------------------------------------------------------------
#%% For debugging

# Access results for debugging
final_frame = main_process.debug_frame
final_fed_time_args = main_process.debug_fed_time_args
debug_dict = main_process.debug_dict


# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap

