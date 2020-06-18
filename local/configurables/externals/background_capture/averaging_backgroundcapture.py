#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Sep 19 10:05:16 2019

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

from local.configurables.externals.background_capture.reference_backgroundcapture import Reference_Background_Capture
from local.configurables.externals.background_capture._helper_functions import load_all_valid_captures
from local.configurables.externals.background_capture._helper_functions import check_frame_loading_ram_limits


# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes

class Background_Capture(Reference_Background_Capture):
    
    # .................................................................................................................
    
    def __init__(self, cameras_folder_path, camera_select, user_select, video_wh):
        
        # Inherit from base class
        super().__init__(cameras_folder_path, camera_select, user_select, video_wh, file_dunder = __file__)
        
        # Allocate storage for pre-calculated values
        self._ram_limited_min_captures_to_use = None
        self._ram_limited_max_captures_to_use = None
        
        # .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  . Control Group 1 .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .
        
        self.ctrl_spec.new_control_group("Capture Controls")
        
        self.capture_period_hr = \
        self.ctrl_spec.attach_slider(
                "capture_period_hr", 
                label = "Capture Period (H)", 
                default_value = 0,
                min_value = 0, max_value = 24,
                return_type = int,
                zero_referenced = True,
                units = "hours",
                tooltip = "Number of hours to wait between saving captures")
        
        self.capture_period_min = \
        self.ctrl_spec.attach_slider(
                "capture_period_min", 
                label = "Capture Period (M)", 
                default_value = 5,
                min_value = 0, max_value = 60,
                return_type = int,
                zero_referenced = True,
                units = "minutes",
                tooltip = "Number of minutes to wait between saving captures")
        
        self.capture_period_sec = \
        self.ctrl_spec.attach_slider(
                "capture_period_sec", 
                label = "Capture Period (S)", 
                default_value = 0,
                min_value = 0, max_value = 60,
                return_type = int,
                zero_referenced = True,
                units = "seconds",
                tooltip = "Number of seconds to wait between saving captures")        
        
        # .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  . Control Group 2 .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .
        
        self.ctrl_spec.new_control_group("Generation Controls")
        
        self.generation_trigger_after_n_captures = \
        self.ctrl_spec.attach_slider(
                "generation_trigger_after_n_captures",
                label = "Generation Every N Captures",
                default_value = 6,
                min_value = 1, max_value = 50,
                return_type = int,
                zero_referenced = True,
                units = "count",
                tooltip = ["A new background will be generated after this many captures.",
                           "For example, if the capture period is set to be 5 minutes, and this value",
                           "is set to 3, then a new background will be generated (roughly)",
                           "every 15 minutes (5 minutes * 3 captures)."])
        
        self.min_captures_to_use = \
        self.ctrl_spec.attach_slider(
                "min_captures_to_use",
                label = "Minimum Captures Per Update",
                default_value = 7,
                min_value = 3, max_value = 50,
                zero_referenced = True,
                return_type = int,
                units = "samples",
                tooltip = "Minimum number of captures to use when generating new background images")
        
        self.max_captures_to_use = \
        self.ctrl_spec.attach_slider(
                "max_captures_to_use",
                label = "Maximum Captures Per Update",
                default_value = 25,
                min_value = 3, max_value = 50,
                zero_referenced = True,
                return_type = int,
                units = "samples",
                tooltip = "Maximum number of captures to use when generating new background images")
        
        self.max_ram_usage_mb = \
        self.ctrl_spec.attach_slider(
                "max_ram_usage_mb",
                label = "Maximum RAM Usage",
                default_value = 250,
                min_value = 50, max_value = 2000,
                zero_referenced = True,
                return_type = int,
                units = "Megabytes",
                tooltip = ["Maximum amount of RAM to use when generating a new background.",
                           "Note that this setting works by limiting the number of captures that are used.",
                           "Therefore, this setting may override the 'Min/Max Captures Per Update' settings!"])
    
    # .................................................................................................................
    
    def setup(self, variables_changed_dict):
        
        # Get RAM limited settings
        self._check_ram_limiting()
        
        # Update parent class settings
        self.set_max_capture_count(self.max_captures_to_use)
        self.set_capture_period(self.capture_period_hr, self.capture_period_min, self.capture_period_sec)
        self.set_generate_trigger(self.generation_trigger_after_n_captures)
        
        # Reset capture/generate timing, in case we're being re-configured
        self.reset()
    
    # .................................................................................................................
    
    def generate_background_from_resources(self,
                                           number_of_captures, capture_image_iter,
                                           num_generates, generate_image_iter,
                                           target_width, target_height):
        
        ''' Note this function runs as a parallel process! Need to be careful not to introduce race-conditions '''
        
        # Initialize (bad) output
        new_background_image = None
        
        # Bail if we don't have enough captures
        not_enough_captures = (number_of_captures < self._ram_limited_min_captures_to_use)
        if not_enough_captures:
            return new_background_image
        
        # Load in all valid sized capture images (if something goes wrong with loading enough captures, then bail)
        max_captures = self._ram_limited_max_captures_to_use
        frame_stack = load_all_valid_captures(capture_image_iter, max_captures, target_width, target_height)        
        not_enough_captures = (len(frame_stack) < self._ram_limited_min_captures_to_use)
        if not_enough_captures:
            return new_background_image
        
        # Finally, try to create a background image by taking the mean of corresponding pixels along all captures
        try:
            new_background_image = np.uint8(np.round(np.mean(frame_stack, axis = 0)))
            if np.isnan(new_background_image):
                new_background_image = None
            
        except TypeError as err:
            print("Error generating averaged background!")
            print(err)
        
        return new_background_image
    
    # .................................................................................................................
    
    def _check_ram_limiting(self):
        
        # Figure out how many captures we're allowed to used base on RAM usage setting        
        max_captures_allowed_by_ram = check_frame_loading_ram_limits(self.max_ram_usage_mb, self.video_wh)
        
        # Set ram limited minimum, with warning
        self._ram_limited_min_captures_to_use = min(max_captures_allowed_by_ram, self.min_captures_to_use)
        if self._ram_limited_min_captures_to_use < self.min_captures_to_use:
            print("",
                  "WARNING:",
                  "  Minimum capture limit is being limited by RAM constraints!",
                  "  Originally set to: {}".format(self.min_captures_to_use),
                  "      Overriding to: {}".format(self._ram_limited_min_captures_to_use),
                  sep = "\n")
        
        # Set ram limited maximum, with warning
        self._ram_limited_max_captures_to_use = min(max_captures_allowed_by_ram, self.max_captures_to_use)
        if self._ram_limited_max_captures_to_use < self.max_captures_to_use:
            print("",
                  "WARNING:",
                  "  Maximum capture limit is being limited by RAM constraints!",
                  "  Originally set to: {}".format(self.max_captures_to_use),
                  "      Overriding to: {}".format(self._ram_limited_max_captures_to_use),
                  sep = "\n")
        
        return
    
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


