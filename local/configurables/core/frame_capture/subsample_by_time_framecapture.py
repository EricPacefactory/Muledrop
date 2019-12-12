#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Sep  5 10:27:25 2019

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

from local.configurables.core.frame_capture.reference_framecapture import Reference_Frame_Capture


# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes

class Frame_Capture_Stage(Reference_Frame_Capture):
    
    # .................................................................................................................
    
    def __init__(self, input_wh):
        
        # Inherit reference functionality
        super().__init__(input_wh, file_dunder = __file__)
        
        # Internal bookkeeping variables
        self._total_sample_period_ms = None
        self._next_sample_time_ms = -1
        
        # .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  . Control Group 1 .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .
        
        self.ctrl_spec.new_control_group("Sampling Controls")
        
        self.sample_period_hrs = \
        self.ctrl_spec.attach_slider(
                "sample_period_hrs", 
                label = "Sample period (hours)", 
                default_value = 0,
                min_value = 0,
                max_value = 24,
                zero_referenced = True,
                return_type = int,
                tooltip = "Number of hours to wait before grabbing a new frame.")
        
        self.sample_period_mins = \
        self.ctrl_spec.attach_slider(
                "sample_period_mins", 
                label = "Sample period (minutes)", 
                default_value = 0,
                min_value = 0,
                max_value = 60,
                zero_referenced = True,
                return_type = int,
                tooltip = "Number of minutes to wait before grabbing a new frame.")
        
        self.sample_period_sec = \
        self.ctrl_spec.attach_slider(
                "sample_period_sec", 
                label = "Sample period (seconds)", 
                default_value = 5,
                min_value = 0,
                max_value = 60,
                zero_referenced = True,
                return_type = int,
                tooltip = "Number of seconds to wait before grabbing a new frame.")
        
    # .................................................................................................................
    
    def reset(self):
        self._next_sample_time_ms = -1
        
    # .................................................................................................................
    
    def setup(self, variables_changed_dict):
        
        # Reset the sampling period if the controls change, 
        # so we're not locked in really long sample periods during configuration
        self.reset()
        
        # Calculate the actual sampling period (in seconds) based on user controls
        hours_to_mins = 60 * self.sample_period_hrs
        minutes_to_sec = 60 * (self.sample_period_mins + hours_to_mins)
        total_sample_period_sec = (self.sample_period_sec + minutes_to_sec)
        self._total_sample_period_ms = int(round(1000 * total_sample_period_sec))
        
    # .................................................................................................................
        
    def skip_conditions(self, current_frame_index, current_epoch_ms, current_datetime):      
        
        # Skip as long as we haven't passed our next sample time, if we have, update it!
        skip_frame = (current_epoch_ms < self._next_sample_time_ms)
        if not skip_frame:
            self._next_sample_time_ms = current_epoch_ms + self._total_sample_period_ms
        
            # For debugging
            #print("Next skip: {:.0f}ms - (Now: {:.0f}ms)".format(self._next_sample_time_ms, current_epoch_ms))  
        
        return skip_frame
    
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



