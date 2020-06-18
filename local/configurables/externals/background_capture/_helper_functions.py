#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Oct  1 15:11:15 2019

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

from local.lib.ui_utils.display_specification import Display_Window_Specification

from local.eolib.video.text_rendering import simple_text


# ---------------------------------------------------------------------------------------------------------------------
#%% Define shared displays


class Stats_Display(Display_Window_Specification):
    
    # .................................................................................................................
    
    def __init__(self, layout_index, num_rows, num_columns, initial_display = False, drawing_json = None):
        
        # Inherit from parent class
        super().__init__("Statistics", layout_index, num_rows, num_columns, 
                         initial_display = initial_display, drawing_json = drawing_json,
                         limit_wh = False)
        
        # Create blank frame for display
        self._display_frame = np.full((175, 400, 3), (40, 40, 40), dtype=np.uint8)
        
    # .................................................................................................................
        
    def display(self, stage_outputs, configurable_ref, mouse_xy,
                current_frame_index, current_epoch_ms, current_datetime):
        
        # Get the amount of RAM usage per capture
        video_wh = configurable_ref.video_wh
        ram_mb_per_frame = calculate_mb_per_frame(video_wh)
        max_ram_usage = self._max_ram_usage_mb(configurable_ref, ram_mb_per_frame)
        
        # Write useful stats into an image for display
        stats_frame = self._display_frame.copy()
        simple_text(stats_frame, "--- Image Statistics ---", (200, 15), center_text = True)
        simple_text(stats_frame, "Video dimensions (px): {:.0f} x {:.0f}".format(*video_wh), (5, 60))
        simple_text(stats_frame, "RAM per capture (MB): {:.1f}".format(ram_mb_per_frame), (5, 100))
        simple_text(stats_frame, "Max RAM usage (MB): {:.1f}".format(max_ram_usage), (5, 140))
        
        # Grab data out of capturer object
        return stats_frame
    
    # .................................................................................................................
    
    def _max_ram_usage_mb(self, configurable_ref, ram_mb_per_frame):
        
        '''
        Sub-class and override this function to display total RAM usage
        in cases where more than 1 capture is stored during background generation
        '''
        
        # Set to 1 as default assumption (i.e. background generation uses only 1 capture image in RAM)
        max_frame_count = 1
        
        return ram_mb_per_frame * max_frame_count
        
    # .................................................................................................................
    # .................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

# .....................................................................................................................

def load_all_valid_captures(capture_image_iter, max_captures_to_load, target_width, target_height):
    
    # Try to load in all valid sized capture images
    frame_stack = []
    for each_capture_image in capture_image_iter:
        
        try:
            # Make sure the captures are the right size before adding them to our stack
            capture_height, capture_width = each_capture_image.shape[0:2]
        except AttributeError:
            continue
        
        # Don't use captures that are incorrectly sized
        wrong_width = (capture_width != target_width)
        wrong_height = (capture_height != target_height)
        if (wrong_width or wrong_height):
            continue
        
        # If we get here, we can add to the stack
        frame_stack.append(each_capture_image)
        
        # Stop grabbing capture images if we hit our max setting
        have_enough_frames = (len(frame_stack) >= max_captures_to_load)
        if have_enough_frames:
            break
    
    return frame_stack

# .....................................................................................................................

def load_newest_image_from_iter(image_iterator):
    
    # Initialize outputs
    newest_image = None
    load_succeeded = False
    
    try:
        newest_image = next(image_iterator)
        load_succeeded = True
    
    except TypeError:
        # Fail case if iterator isn't actually an iterator!
        pass
    
    except StopIteration:
        # Fail case if iterator has been exhausted
        pass
    
    return load_succeeded, newest_image

# .....................................................................................................................

def calculate_mb_per_frame(frame_wh):
    
    '''
    Helper function which calculates the amount of RAM usage (in MB) per frame, based on the width/height
    Note: The MB value is calculated as the number of bytes per frame divided by 1E6
    
    Inputs:
        frame_wh -> Tuple/List. The width/height of a single frame
    
    Outputs:
        num_MB_per_frame (float value)
    '''
    
    # Figure out how much RAM is needed per frame
    frame_height, frame_width = frame_wh
    num_bytes_per_pixel = 3
    num_bytes_per_frame = (frame_width * frame_height * num_bytes_per_pixel)
    num_MB_per_frame = (num_bytes_per_frame / 1E6)
    
    return num_MB_per_frame

# .....................................................................................................................
    
def check_frame_loading_ram_limits(max_ram_usage_MB, frame_wh):
    
    '''
    Helper function which figure out how many frames can be stored in memory based on a given RAM usage limit
    
    Inputs:
        max_ram_usage_MB -> Integer/Float. The maximum allowed amount of RAM usage (in MB) for storing frames
        
        frame_wh -> Tuple/List. The width/height of the frames being stored
    
    Outputs:
        num_frames_allowed_by_ram (integer)
    '''
    
    num_MB_per_frame = calculate_mb_per_frame(frame_wh)
    num_frames_allowed_by_ram = int(max_ram_usage_MB / num_MB_per_frame)
    
    return num_frames_allowed_by_ram

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Demo
    
if __name__ == "__main__":
    pass
    

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap


