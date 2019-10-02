#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Jun  8 17:56:45 2019

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

from local.lib.file_access_utils.bgcapture import load_newest_image

# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes

# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions
# .....................................................................................................................

def create_blank_frame_from_video_wh(video_wh):    
    return np.zeros((video_wh[1], video_wh[0], 3), dtype=np.uint8)

# .....................................................................................................................
    
def trigger_on_time(current_time_sec, next_trigger_time_sec, trigger_period_sec):
    
    # Check the current time exceeds the target trigger time
    try:
        time_trigger = (current_time_sec > next_trigger_time_sec)
        
    except TypeError:
        
        # If there's an error (likely don't have a valid next trigger time yet), force a trigger
        time_trigger = True
        next_trigger_time_sec = current_time_sec
        
    # Update the next trigger time if needed
    next_trigger_time_sec = (next_trigger_time_sec + trigger_period_sec) if time_trigger else next_trigger_time_sec
    
    return time_trigger, next_trigger_time_sec

# .....................................................................................................................

def load_initial_background(generated_folder_path, video_wh):
    load_success, img_data = load_newest_image(generated_folder_path)
    return img_data if load_success else create_blank_frame_from_video_wh(video_wh)

# .....................................................................................................................
# .....................................................................................................................
    

# ---------------------------------------------------------------------------------------------------------------------
#%% Demo
    
if __name__ == "__main__":
    pass
    

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap


