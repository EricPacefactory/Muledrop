#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Sep 19 11:38:17 2019

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

from itertools import islice as slice_generator

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
                         frame_capture_class = Median_Frame_Capture,
                         background_creator_class = Median_Background_Creator)
        
        # Allocate storage for pre-calculated values
        self._total_capture_period_sec = None
        self._total_generation_period_sec = None
        
        
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
                default_value = 15,
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
        
        self.generation_period_hr = \
        self.ctrl_spec.attach_slider(
                "generation_period_hr",
                label = "Generation Period (H)",
                default_value = 1,
                min_value = 0, max_value = 24,
                return_type = int,
                zero_referenced = True,
                units = "hours",
                tooltip = "Number of hours to wait between generating new background")
        
        self.generation_period_min = \
        self.ctrl_spec.attach_slider(
                "generation_period_min",
                label = "Generation Period (M)",
                default_value = 0,
                min_value = 0, max_value = 60,
                return_type = int,
                zero_referenced = True,
                units = "minutes",
                tooltip = "Number of minutes to wait between generating new background")
        
        self.generation_period_sec = \
        self.ctrl_spec.attach_slider(
                "generation_period_sec",
                label = "Generation Period (S)",
                default_value = 0,
                min_value = 0, max_value = 60,
                return_type = int,
                zero_referenced = True,
                units = "seconds",
                tooltip = "Number of seconds to wait between generating new background")
        
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
        
        # Limit the number of saved backgrounds, just enough to see what's going on
        self.set_max_generated_count(15)
    
    # .................................................................................................................
    
    def setup(self, variables_changed_dict):
        
        # Pre-calculate the total number of seconds to wait between captures & pass it to the capture object
        cap_min_from_hours = self.capture_period_hr * 60
        cap_sec_from_mins = (self.capture_period_min + cap_min_from_hours) * 60
        self._total_capture_period_sec = max(1.0, self.capture_period_sec + cap_sec_from_mins)
        self.frame_capturer.set_capture_period(self._total_capture_period_sec)
        
        # Pre-calculate the total number of seconds to wait between generated bgs & pass it to the generator object
        gen_min_from_hours = self.generation_period_hr * 60
        gen_sec_from_mins = (self.generation_period_min + gen_min_from_hours) * 60
        self._total_generation_period_sec = max(1.0, self.generation_period_sec + gen_sec_from_mins)
        self.background_creator.set_generation_period(self._total_generation_period_sec)
        
        # Tell the generator how many captures are needed/allowed when generating backgrounds
        self.background_creator.set_min_max_captures(self.min_captures_to_use, self.max_captures_to_use)
        
        # Don't capture any more than we need
        self.set_max_capture_count(self.max_captures_to_use)
        
        # Force reset any time parameters are changed, since this will force new captures!
        self.reset()
    
    # .................................................................................................................
    # .................................................................................................................


# =====================================================================================================================
# =====================================================================================================================


class Median_Frame_Capture(Reference_Frame_Capture):
    
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


class Median_Background_Creator(Reference_Background_Creator):
    
    # .................................................................................................................
    
    def __init__(self, cameras_folder_path, camera_select, user_select, video_select, video_wh,
                 *, lock = None):
        
        # Inherit from base
        super().__init__(cameras_folder_path, camera_select, user_select, video_select, video_wh, lock = lock)
        
        # Allocate storage for control variables
        self.generation_period_sec = None
        self.min_captures_to_use = None
        self.max_captures_to_use = None
        self._next_generation_time_sec = -1
        
    # .................................................................................................................
    
    def reset(self):
        self._next_generation_time_sec = -1.0
        
    # .................................................................................................................
    
    def set_generation_period(self, generation_period_sec):
        self.generation_period_sec = generation_period_sec
        
    # .................................................................................................................
    
    def set_min_max_captures(self, min_captures_to_use, max_captures_to_use):
        self.min_captures_to_use = min_captures_to_use
        self.max_captures_to_use = max_captures_to_use
    
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
        
        # Generate every time we pass the next generation time!
        if current_time_sec >= self._next_generation_time_sec:
            self._next_generation_time_sec = current_time_sec + self.generation_period_sec
            return True
        
        return False
    
    # .................................................................................................................    
    
    def generation_function(self, number_of_captures, capture_data_generator):
        
        ''' Function which generates new background images. Must return the new background image! '''
        
        # If we have no image to start with, generate a random noise image
        no_existing_image = (self._latest_generated_frame is None)
        not_enough_captures = (number_of_captures < self.min_captures_to_use)
        if no_existing_image and not_enough_captures:
            video_width, video_height = self.video_wh
            new_background_image = np.random.randint(0, 255, (video_height, video_width, 3), dtype=np.uint8)
            return new_background_image
        
        # Copy the existing frame data until enough frames are available to generate median background
        if not_enough_captures:
            new_background_image = self._latest_generated_frame
            return new_background_image
        
        # If we get here, there must be enough frames to generate a median background, so go for it!
        num_to_median = min(self.max_captures_to_use, number_of_captures)
        frames_to_median = list(slice_generator(capture_data_generator, num_to_median))
        new_background_image = np.uint8(np.round(np.median(frames_to_median, axis=0)))

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

