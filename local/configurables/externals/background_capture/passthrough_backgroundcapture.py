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
                         frame_capture_class = Passthrough_Frame_Capture,
                         background_creator_class = Passthrough_Background_Creator)
        
        # Passthrough has no controls!
    
    # .................................................................................................................
    
    def reset(self):
        # No storage to reset!
        pass
   
    # .................................................................................................................
    
    def setup(self, variables_changed_dict):
        # No setup. Overriding to get rid of built-in debugging warning
        pass
    
    # .................................................................................................................
    # .................................................................................................................


# =====================================================================================================================
# =====================================================================================================================


class Passthrough_Frame_Capture(Reference_Frame_Capture):
    
    # .................................................................................................................
    
    def __init__(self, cameras_folder_path, camera_select, user_select, video_select, video_wh,
                 *, lock = None):
        
        # Inherit from base
        super().__init__(cameras_folder_path, camera_select, user_select, video_select, video_wh, 
                         lock = lock)
        
        # Allocate storage for keeping track of the current hour
        self._current_hour = -1
        
    # .................................................................................................................
    
    
    def capture_condition(self, input_frame, current_frame_index, current_time_sec, current_datetime):
        
        ''' Function which returns a boolean value to indicate whether the current frame should be captured '''
        
        # Get a new capture every hour
        current_hour = current_datetime.hour
        is_new_hour = (current_hour != self._current_hour)
        if is_new_hour:
            self._current_hour = current_hour
            return True
        
        # Get capture if we don't already have one
        no_existing_data = (self._latest_capture_time_sec is None)
        if no_existing_data:
            return True
        
        return False
    
    # .................................................................................................................
    # .................................................................................................................


# =====================================================================================================================
# =====================================================================================================================


class Passthrough_Background_Creator(Reference_Background_Creator):
    
    # .................................................................................................................
    
    def __init__(self, cameras_folder_path, camera_select, user_select, video_select, video_wh,
                 *, lock = None):
        
        # Inherit from base
        super().__init__(cameras_folder_path, camera_select, user_select, video_select, video_wh, lock = lock)
        
        # Allocate storage for keeping tracking over the current day (for updating background occasionally)
        self._current_day = -1
        
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
        
        # Generate a new background if we've moved on to a new day. Also make sure to update our record of the day!
        current_day = current_datetime.day
        is_new_day = (current_day != self._current_day)
        if is_new_day:
            self._current_day = current_day
            return True
        
        return False
    
    # .................................................................................................................    
    
    def generation_function(self, number_of_captures, capture_data_generator):
        
        ''' Function which generates new background images. Must return the new background image! '''
        
        # If we have no image to start with, generate a random noise image
        no_existing_image = (self._latest_generated_frame is None)
        not_enough_captures = (number_of_captures < 5)
        if no_existing_image and not_enough_captures:
            video_width, video_height = self.video_wh
            new_background_image = np.random.randint(0, 255, (video_height, video_width, 3), dtype=np.uint8)            
            return new_background_image
        
        # Passthrough copies the existing frame data until enough frames are available for a reasonable average
        if not_enough_captures:
            
            # Some feedback about this somewhat weird behavior
            print("", 
                  "Passthrough BG Generator:",
                  "  Not enough captures (need 5 or more) to create averaged frame...",
                  "  Using existing background instead!", sep = "\n")
            
            new_background_image = self._latest_generated_frame
            return new_background_image
        
        # If we get here, generate a frame by using the average of the captured frame data
        frame_list = list(capture_data_generator)
        new_background_image = np.uint8(np.round(np.mean(frame_list, axis=0)))

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


