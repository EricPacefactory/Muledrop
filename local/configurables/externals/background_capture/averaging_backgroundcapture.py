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

import cv2
import numpy as np

from local.configurables.externals.background_capture.reference_backgroundcapture import \
Reference_Background_Capture, Reference_Frame_Capture, Reference_Background_Creator


# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes

class Background_Capture(Reference_Background_Capture):
    
    # .................................................................................................................
    
    def __init__(self, cameras_folder_path, camera_select, user_select, video_select, video_wh):
        
        # Inherit from base class
        super().__init__(cameras_folder_path, camera_select, user_select, video_select, video_wh, 
                         file_dunder = __file__,
                         frame_capture_class = Averaging_Frame_Capture,
                         background_creator_class = Averaging_Background_Creator)
        
        # Allocate storage for total capture time
        self._total_capture_period_sec = None
        
        # .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  . Control Group 1 .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .
        
        self.ctrl_spec.new_control_group("Capture Controls")
        
        self.capture_period_hr = \
        self.ctrl_spec.attach_slider(
                "capture_period_hr", 
                label = "Capture Period (H)", 
                default_value = 0,
                min_value = 0,
                max_value = 24,
                return_type = int,
                zero_referenced = True,
                units = "hours",
                tooltip = "Number of hours to wait between saving captures")
        
        self.capture_period_min = \
        self.ctrl_spec.attach_slider(
                "capture_period_min", 
                label = "Capture Period (M)", 
                default_value = 5,
                min_value = 0,
                max_value = 60,
                return_type = int,
                zero_referenced = True,
                units = "minutes",
                tooltip = "Number of minutes to wait between saving captures")
        
        self.capture_period_sec = \
        self.ctrl_spec.attach_slider(
                "capture_period_sec", 
                label = "Capture Period (S)", 
                default_value = 0,
                min_value = 0,
                max_value = 60,
                return_type = int,
                zero_referenced = True,
                units = "seconds",
                tooltip = "Number of seconds to wait between saving captures")
        
        # .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  . Control Group 2 .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .
        
        self.ctrl_spec.new_control_group("Generation Controls")
        
        self.update_weighting = \
        self.ctrl_spec.attach_slider(
                "update_weighting",
                label = "Update weighting",
                default_value = 0.5,
                min_value = 0.01, max_value = 1.0, step_size = 1/100,
                zero_referenced = True,
                return_type = float,
                units = "weighting",
                tooltip = "Amount of weighting given to newest capture versus previous generated background")
        
        
        # Limit the number of captures used by this background generation style, since it doesn't need much storage
        self.set_max_capture_count(5)
        self.set_max_generated_count(5)
    
    # .................................................................................................................
    
    def setup(self, variables_changed_dict):
        
        # Pre-calculate the total number of seconds to wait between captures & pass it to the capture object
        cap_min_from_hours = self.capture_period_hr * 60
        cap_sec_from_mins = (self.capture_period_min + cap_min_from_hours) * 60
        self._total_capture_period_sec = max(1.0, self.capture_period_sec + cap_sec_from_mins)
        self.frame_capturer.set_capture_period(self._total_capture_period_sec)
        
        # Pass background creator object the appropriate control value
        self.background_creator.set_update_weighting(self.update_weighting)
        
        # Force reset any time parameters are changed, since this will force new captures!
        self.reset()
    
    # .................................................................................................................
    # .................................................................................................................


# =====================================================================================================================
# =====================================================================================================================


class Averaging_Frame_Capture(Reference_Frame_Capture):
    
    # .................................................................................................................
    
    def __init__(self, cameras_folder_path, camera_select, user_select, video_select, video_wh, 
                 *, lock = None):
        
        # Inherit from base
        super().__init__(cameras_folder_path, camera_select, user_select, video_select, video_wh, lock = lock)
        
        # Allocate storage control variables
        self.capture_period_sec = None
        self._next_capture_time_sec = -1
        
    # .................................................................................................................
    
    def reset(self):
        self._next_capture_time_sec = -1
        
    # .................................................................................................................
    
    def set_capture_period(self, capture_period_sec):        
        self.capture_period_sec = capture_period_sec
        
    # .................................................................................................................
    
    def capture_condition(self, input_frame, current_frame_index, current_time_sec, current_datetime):
        
        ''' Function which returns a boolean value to indicate whether the current frame should be captured '''
        
        # Capture every time we pass the next capture time!
        if current_time_sec >= self._next_capture_time_sec:
            self._next_capture_time_sec = current_time_sec + self.capture_period_sec
            return True
        
        return False
    
    # .................................................................................................................
    # .................................................................................................................


# =====================================================================================================================
# =====================================================================================================================


class Averaging_Background_Creator(Reference_Background_Creator):
    
    # .................................................................................................................
    
    def __init__(self, cameras_folder_path, camera_select, user_select, video_select, video_wh,
                 *, lock = None):
        
        # Inherit from base
        super().__init__(cameras_folder_path, camera_select, user_select, video_select, video_wh, lock = lock)
        
        # Allocate storage for control variables
        self.update_weighting = None
        self._inv_weight = None
        self._latest_averaged_frame = None
        
        # Allocate variables to keep track of next generation time
        self._wait_for_new_generation = False
        self._next_generation_time_sec = None
        self._generation_lag_sec = 5.0
        
    # .................................................................................................................
    
    def reset(self):
        self._next_generation_time_sec = -1.0
        
    # .................................................................................................................
    
    def set_update_weighting(self, update_weighting):
        self.update_weighting = update_weighting
        self._inv_weight = 1 - update_weighting
    
    # .................................................................................................................
    
    def generation_condition(self, currently_generating, frame_was_captured, 
                             current_frame_index, current_time_sec, current_datetime):
        
        ''' Function which returns a boolean value to indicate whether a new background image should be generated '''
        
        # Don't start to generate a new background if we're already generating one
        if currently_generating:
            return False
        
        # Don't do anything if saving isn't enabled, since captures won't be available
        if not self.resource_saving_enabled:
            return False
        
        # Record latest capture time, since we'll use this (with a lag) to trigger background generation
        if frame_was_captured:
            self._wait_for_new_generation = True
            self._next_generation_time_sec = current_time_sec + self._generation_lag_sec
        
        # Generate a new background whenever we pass the next time trigger
        if self._wait_for_new_generation:
            
            # Check if we've waited long enough for the capture lag (make sure newest capture is finished saving)
            # If so, make sure to reset the wait flag, so we don't check on the next iteration!
            waited_long_enough = (current_time_sec > self._next_generation_time_sec)
            if waited_long_enough:
                self._wait_for_new_generation = False      
            return waited_long_enough
        
        return False
    
    # .................................................................................................................    
    
    def generation_function(self, number_of_captures, capture_data_generator):
        
        ''' Function which generates new background images. Must return the new background image! '''
        
        # If we have no image to start with, generate a random noise image
        no_existing_image = (self._latest_generated_frame is None)
        not_enough_captures = (number_of_captures < 1)
        if no_existing_image and not_enough_captures:
            video_width, video_height = self.video_wh
            new_background_image = np.random.randint(0, 255, (video_height, video_width, 3), dtype=np.uint8)
            return new_background_image
        
        # Passthrough copies the existing frame data until enough frames are available for a reasonable average
        if not_enough_captures:
            new_background_image = self._latest_generated_frame
            return new_background_image
        
        # If we get here, we either need to grab our first averaged frame, by rolling over all captures
        # or otherwise, simply average the newest capture with our existing averaged frame
        have_existing_average = (self._latest_averaged_frame is not None)
        newest_capture = next(capture_data_generator)
        if have_existing_average:
            new_background_image = self._rolling_average_image(newest_capture, self._latest_averaged_frame)
        else:
            # Create rolling average from all available capture frames (in case there is more than one available)
            new_background_image = newest_capture
            for each_capture in capture_data_generator:
                new_background_image = self._rolling_average_image(each_capture, new_background_image)
        
        # Store separate internal copy of average background to keep track of what we're doing
        self._latest_averaged_frame = new_background_image.copy()

        return new_background_image
    
    # .................................................................................................................
    
    def _rolling_average_image(self, newest_image, previous_image):
        return cv2.addWeighted(newest_image, self.update_weighting, 
                               previous_image, self._inv_weight, 0.0)
    
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

