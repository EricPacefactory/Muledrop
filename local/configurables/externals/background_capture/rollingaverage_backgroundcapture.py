#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat May 23 11:16:07 2020

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

from local.configurables.externals.background_capture.reference_backgroundcapture import Reference_Background_Capture

from local.configurables.externals.background_capture._helper_functions import load_newest_image_from_iter


# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes

class Background_Capture(Reference_Background_Capture):
    
    # .................................................................................................................
    
    def __init__(self, location_select_folder_path, camera_select, video_wh):
        
        # Inherit from base class
        super().__init__(location_select_folder_path, camera_select, video_wh, file_dunder = __file__)
        
        # Update parent class settings with hard-coded values, specific to rolling average
        self.set_max_capture_count(3)
        self.set_max_generate_count(3)
        self.set_generate_trigger(1)
        
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
                default_value = 10,
                min_value = 0, max_value = 60,
                return_type = int,
                zero_referenced = True,
                units = "minutes",
                tooltip = "Number of minutes to wait between saving captures")
        
        # .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  . Control Group 2 .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .
        
        self.ctrl_spec.new_control_group("Generation Controls")
        
        self.update_weighting = \
        self.ctrl_spec.attach_slider(
                "update_weighting",
                label = "Weighting for Newest Capture",
                default_value = 0.15,
                min_value = 0.01, max_value = 1.0, step_size = 1/100,
                zero_referenced = True,
                return_type = float,
                units = "weighting",
                tooltip = ["Weighting applied to the newest capture image when calculating the rolling average.",
                           "The inverse of this weight (i.e. 1.0 - weight) will be the weighting applied to",
                           "the previously generated image to form the rolling average result."])
    
    # .................................................................................................................
    
    def setup(self, variables_changed_dict):
        
        # Update parent class settings
        capture_period_sec = 0
        self.set_capture_period(self.capture_period_hr, self.capture_period_min, capture_period_sec)
        
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
        not_enough_captures = (number_of_captures < 1)
        if not_enough_captures:
            return new_background_image
        
        # Load the newest capture
        loaded_capture, newest_capture = load_newest_image_from_iter(capture_image_iter)
        if not loaded_capture:
            print("Error loading newest capture image for rolling average background!")
            return new_background_image
        
        # Load the newest generated background
        loaded_generate, newest_generate = load_newest_image_from_iter(generate_image_iter)
        if not loaded_generate:
            print("Error loading newest generated image for rolling average background!")
            return new_background_image
        
        # Finally, try to average the newest capture and generated image together
        try:
            previous_weighting = 1.0 - self.update_weighting
            new_background_image = cv2.addWeighted(newest_capture, self.update_weighting,
                                                   newest_generate, previous_weighting, 0.0)
            
        except cv2.error as err:
            print("Error generating rolling average background!")
            print(err)
        
        return new_background_image
    
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


