#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri May 31 11:38:54 2019

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

from local.configurables.core.frame_processor.reference_frameprocessor import Reference_Frame_Processor
from local.configurables.core.frame_processor._helper_functions import blank_binary_frame_from_input_wh

# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes

class Frame_Processor_Stage(Reference_Frame_Processor):
    
    # .................................................................................................................
    
    def __init__(self, input_wh):
        
        # Inherit reference functionality
        super().__init__(input_wh, file_dunder = __file__)
        
        # Allocate storage for a blank frame that will be re-used for the passthrough output
        self._blank_frame = None
        
    # .................................................................................................................
        
    def reset(self):
        # No storage, so do nothing
        return
        
    # .................................................................................................................
    
    def setup(self, variables_changed_dict):
        
        # Create the required blank (binary) frame for passthrough output
        self._blank_frame = blank_binary_frame_from_input_wh(self.input_wh)
        
    # .................................................................................................................
    
    def apply_frame_processing(self, frame):
        try:
            return self._blank_frame
        except Exception as err:
            print("{}: FRAME ERROR".format(self.script_name))
            print(err)
            return frame
    
    # .................................................................................................................
    
    def update_background(self, preprocessed_background_frame, bg_update):
        # No background processing
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



    