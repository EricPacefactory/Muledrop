#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Jul  2 09:23:38 2020

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

from local.lib.launcher_utils.configuration_loaders import Reconfigurable_Single_Station_Loader
from local.lib.launcher_utils.video_processing_loops import Station_Processing_Video_Loop
from local.lib.ui_utils.display_specification import Input_Display

from local.configurables.stations._helper_functions import Zoomed_Station_Display, Data_Display_1ch


# ---------------------------------------------------------------------------------------------------------------------
#%% Define displays

class Station_Display(Zoomed_Station_Display):
    
    # .................................................................................................................
    
    def __init__(self, layout_index, num_rows, num_columns, initial_display = False):
        
        # Inherit from parent class
        super().__init__(layout_index, num_rows, num_columns, initial_display = initial_display)
    
    # .................................................................................................................
    
    def postprocess_cropmasked_frame(self, cropmasked_frame, configurable_ref):
        return cv2.cvtColor(cropmasked_frame, cv2.COLOR_BGR2GRAY)
    
    # .................................................................................................................
    # .................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Main

# For clarity
target_script_name = "average_brightness_station"

# Make all required selections
loader = Reconfigurable_Single_Station_Loader(target_script_name)
arg_selections = loader.parse_standard_args()
loader.selections(*arg_selections)

# Set up video capture, processing stages & playback control
configurable_ref = loader.setup_all(__file__)

# Get drawing specification for the given edge decay variable
zone_drawing_spec = configurable_ref.get_drawing_spec("station_zones_list")

# Set up object to handle all video processing
main_process = \
Station_Processing_Video_Loop(loader,
                              ordered_display_list = [Data_Display_1ch(0, 3, 3),
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


