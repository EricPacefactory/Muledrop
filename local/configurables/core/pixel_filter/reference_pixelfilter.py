#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed May 29 11:36:36 2019

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

from local.configurables.configurable_template import Core_Configurable_Base

# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes

class Reference_Pixel_Filter(Core_Configurable_Base):
    
    # .................................................................................................................
    
    def __init__(self, cameras_folder_path, camera_select, user_select, input_wh, *, file_dunder):
        
        # Inherit from parent class
        super().__init__("pixel_filter", 
                         cameras_folder_path, camera_select, user_select, input_wh, file_dunder = file_dunder)
        
        # !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
        
        # For inherited classes, first call:
        # super().__init__(cameras_folder_path, camera_select, user_select, input_wh, file_dunder = __file__)
        
        # Then do any class-specific set up
        # ...
        # ...
        # ...
    
    # .................................................................................................................
    
    def reset(self):
        raise NotImplementedError("Must implement a pixel processor reset()")
    
    # .................................................................................................................
    
    # MAY OVERRIDE. Only if some resources have been opened while running...
    def close(self, final_frame_index, final_epoch_ms, final_datetime):
        # Nothing opened, nothing to close!
        return None
    
    # .................................................................................................................
    
    # MAY OVERRIDE (BUT NOT NECESSARY, BETTER TO INSTEAD OVERRIDE: apply_pixel_filtering())
    def run(self, binary_frame_1ch, preprocessed_frame, preprocessed_bg_frame, bg_update):
        # This function must maintain this input/output structure!
        #   - Need to pass the preprocessed frame through (for the following detector stage)
        #   - Need to return a new binary frame (i.e. only a single 'color' channel)
        
        # Update stored background before trying to process frame data
        self.update_background(preprocessed_bg_frame, bg_update)
        
        # Make sure binary frame data is returned (i.e. only has a single channel)
        filtered_binary_frame_1ch = self.apply_pixel_filtering(binary_frame_1ch, preprocessed_frame)
        
        return {"filtered_binary_frame_1ch": filtered_binary_frame_1ch, 
                "preprocessed_frame": preprocessed_frame}
            
    # .................................................................................................................
    
    # SHOULD OVERRIDE
    def apply_pixel_filtering(self, binary_frame_1ch, color_frame):
        
        try:
            return binary_frame_1ch
        
        except cv2.error as err:
            self.log("ERROR FILTERING ({})".format(self.script_name))
            if self.configure_mode:
                raise err
        
        return binary_frame_1ch
    
    # .................................................................................................................
    
    # SHOULD OVERRIDE IF USING THE BACKGROUND IMAGE (can be used to store it, for example)
    def update_background(self, preprocessed_background_frame, bg_update):
        
        # Don't do anything if there is no background frame
        if not bg_update:
            return
            
        # Place background processing here (also need to handle storage)
        print("Background updated! Calling update_background() @ {}".format(self.script_name))
    
    # .................................................................................................................
    # .................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions



# ---------------------------------------------------------------------------------------------------------------------
#%% Demo
    
if __name__ == "__main__":
    pass
    

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap



    