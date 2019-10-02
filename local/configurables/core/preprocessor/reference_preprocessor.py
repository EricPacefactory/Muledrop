#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Mar 29 12:15:03 2019

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

from local.configurables.configurable_template import Core_Configurable_Base

# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes

class Reference_Preprocessor(Core_Configurable_Base):
    
    # .................................................................................................................
    
    def __init__(self, input_wh, file_dunder):
        
        super().__init__(input_wh, file_dunder = file_dunder)
        
        # Allocate storage for holding on to the newest background image
        self.current_background = None
        
        # !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
        #   Inherited classes must have __init__(input_wh) as arguments!
        # !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
        
        # For inherited classes, first call:
        # super().__init__(input_wh, file_dunder = __file__)
        
        # Then do any class-specific set up
        # ...
        # ...
        # ...
    
    # .................................................................................................................
    
    def reset(self):
        raise NotImplementedError("Must implement a preprocessor reset()")
    
    # .................................................................................................................
    
    # MAY OVERRIDE (BUT NOT NECESSARY, BETTER TO INSTEAD OVERRIDE: apply_transformation())
    def run(self, video_frame, bg_frame, bg_update):
        # This function must maintain this input/output structure!
        #   - Used to ensure live video data + background image getting to frame processor are matched
        #   - Any modifications applied by the preprocessor should be applied to the background frame before return
        
        # Apply preprocessing transformation to background images (when available) and all live video frames
        preprocessed_bg_frame = self.preprocess_background(bg_frame, bg_update)
        preprocessed_frame = self.apply_transformation(video_frame)
        
        return {"preprocessed_frame": preprocessed_frame, 
                "preprocessed_bg_frame": preprocessed_bg_frame,
                "bg_update": bg_update}
    
    # .................................................................................................................
    
    # MAY OVERRIDE (BUT NOT NECESSARY, IF POSSIBLE, BETTER TO INSTEAD OVERRIDE: apply_transformation())
    def preprocess_background(self, background_frame, bg_update):
        # This function must maintain this input/output structure
        #   - Used to ensure live video data + background image getting to frame processor are matched
        #   - background image is not necessarily updated every frame (depends how often bg capture outputs)
        
        # Apply preprocessing transformation to the background image to match live video frames
        if bg_update or (self.current_background is None):
            modified_background = self.apply_transformation(background_frame)
            self.current_background = modified_background.copy()
        else:
            modified_background = self.current_background
        
        return modified_background
    
    # .................................................................................................................
    
    # SHOULD OVERRIDE
    def apply_transformation(self, frame):
        try:
            return frame.copy()
        except:
            print("PREPROCESSOR: ERROR TRANSFORMING")
            return frame
    
    # .................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions



# ---------------------------------------------------------------------------------------------------------------------
#%% Demo
    
if __name__ == "__main__":
    pass
    

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap



    