#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Oct  1 15:34:06 2019

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


class Dying_Display(Display_Window_Specification):
    
    # .................................................................................................................
    
    def __init__(self, layout_index, num_rows, num_columns, initial_display = False,
                 window_name = "Dying Objects"):
        
        # Inherit from parent class
        super().__init__(window_name, layout_index, num_rows, num_columns, 
                         initial_display = initial_display, 
                         limit_wh = False)
        
        
        # Create blank frame for display
        self._display_frame = np.full((350, 400, 3), (40, 40, 40), dtype=np.uint8)
        
    # .................................................................................................................
        
    def display(self, stage_outputs, configurable_ref, mouse_xy,
                current_frame_index, current_epoch_ms, current_datetime):
        
        # Get configuration-only data out of the object
        dead_id_list = configurable_ref._config_dead_ids
        
         # Write useful stats into an image for display
        ids_frame = self._display_frame.copy()
        simple_text(ids_frame, "--- Dying Objects (IDs - Saved) ---", (200, 15), center_text = True)
        for each_idx, (each_id, each_save_status) in enumerate(dead_id_list):            
            simple_text(ids_frame, "{} - {}".format(each_id, each_save_status), (5, 70 + each_idx * 25))
            
        # Message for when no data has arrived
        if len(dead_id_list) < 1:
            simple_text(ids_frame, "None so far...", (5, 70))
            simple_text(ids_frame, "--> Requires fully configured tracking", (5, 95))
        
        return ids_frame
        
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


