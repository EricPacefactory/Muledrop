#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Sep 18 11:01:44 2019

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

from local.configurables.externals.background_capture.reference_backgroundcapture import Reference_Background_Capture


# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes

class Background_Capture(Reference_Background_Capture):
    
    # .................................................................................................................
    
    def __init__(self, cameras_folder_path, camera_select, user_select, video_select, video_wh):
        
        # Inherit from base class
        super().__init__(cameras_folder_path, camera_select, user_select, video_select, video_wh, 
                         file_dunder = __file__)
        
        # Passthrough has no controls!
        
        # Update parent class settings
        self.set_max_capture_count(3)
        self.set_max_generate_count(3)
        self.set_capture_period(hours = 24)
        self.set_generate_trigger(every_n_captures = 1000)
    
    # .................................................................................................................
    
    def setup(self, variables_changed_dict):
        
        # No setup since there are no controls!
        
        return
    
    # .................................................................................................................
    
    def generate_background_from_resources(self,
                                           num_captures, capture_image_iter,
                                           num_generates, generate_image_iter,
                                           target_width, target_height):
        
        # Passthrough does not generate it's own images, which will force re-use of initial background forever!
        
        return None
    
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


