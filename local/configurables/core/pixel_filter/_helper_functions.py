#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed May 29 15:48:35 2019

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

from local.lib.configuration_utils.display_specification import Display_Window_Specification


# ---------------------------------------------------------------------------------------------------------------------
#%% Define shared displays

class Color_Filtered(Display_Window_Specification):
    
    # .................................................................................................................
    
    def __init__(self, layout_index, num_rows, num_columns, initial_display = False):
        
        # Inherit from parent class
        super().__init__("Color Filtered", layout_index, num_rows, num_columns, 
                         initial_display = initial_display, 
                         max_wh = None)
        
    # .................................................................................................................
        
    def display(self, stage_outputs, configurable_ref, current_frame_index, current_time_sec, current_datetime):
        
        return color_masked(stage_outputs, configurable_ref)
        
    # .................................................................................................................
    # .................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

# .....................................................................................................................

def color_masked(stage_outputs, configurable_ref):
    
    '''
    Similar to color_filtered function, but uses an internal filter mask, which doesn't include the frame
    processing (stage prior to pixel filter) mask
    '''
    
    # Grab the preprocessed frame and internal filtering mask so we can show the combined effect
    color_frame = stage_outputs["frame_processor"]["preprocessed_frame"]
    mask_frame = configurable_ref.filter_mask
    
    # If no mask is available, just return the un-masked frame
    if mask_frame is None:
        return color_frame
    
    # Get the color frame size so we properly mask the image
    disp_h, disp_w = color_frame.shape[0:2]
    
    # Convert the mask to 3 channels so we can apply it to the color image
    mask_frame_bgr = cv2.cvtColor(mask_frame, cv2.COLOR_GRAY2BGR)
    scaled_mask = cv2.resize(mask_frame_bgr, dsize = (disp_w, disp_h), interpolation = cv2.INTER_NEAREST)
    color_masked = cv2.bitwise_and(color_frame, scaled_mask)
    
    return color_masked

# .....................................................................................................................
    
def draw_bgr_rect_region(hsv_display_frame, top_left, bot_right, invert_region, 
                         conversion_code, bg_color = (0, 0, 0), fg_color = None):
    
    '''
    Takes a rectangular colorspace image, converts it to bgr for display and 
    adds lines indicating color filtering regions
    '''
    
    # Convert hsv values to bgr for display
    bgr_display_frame = cv2.cvtColor(hsv_display_frame, conversion_code)
    
    # Draw color space sectioning lines, based on settings
    bg_rect_thickness = -1 if invert_region else 2
    cv2.rectangle(bgr_display_frame, top_left, bot_right, (0, 0, 0), bg_rect_thickness)
    if fg_color:
        cv2.rectangle(bgr_display_frame, top_left, bot_right, fg_color, 1)
    
    return bgr_display_frame

# .....................................................................................................................

def inRange_with_colorspace(bgr_color_frame, conversion_code, lower_bound_3ch, upper_bound_3ch):
    
    '''
    Function which applies the OpenCV inRange function, with an additional color-space conversion step.
    Returns a (1D) binary image based on the given lower/upper boundary values applied in the given color space.
    See help(cv2.inRange) for more information
    
    Inputs:
        bgr_color_frame -> Color image (numpy array) in BGR color-space. 
        
        conversion_code -> OpenCV color conversion code. Example: cv2.COLOR_BGR2HSV_FULL
        
        lower_bound_3ch -> Tuple with 3 numbers. Lower boundary for the cv2.inRange function (lowerb). 
                           All values below these numbers will be black in the output mask (on a per-channel basis)
                           
        upper_bound_3ch -> Tuple with 3 numbers. Upper boundary for the cv2.inRange function (upperb).
                           All values above these numbers will be black in the output mask (on a per-channel basis)
                           
    Outputs:
        binary_mask_1d -> Single channel binary image (numpy array). 
    '''
    
    # Convert incoming (bgr) color frame to the target color space before applying inRange filtering
    color_space_frame = cv2.cvtColor(bgr_color_frame, conversion_code)
    binary_mask_1d = cv2.inRange(color_space_frame, lower_bound_3ch, upper_bound_3ch)
    
    return binary_mask_1d

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Demo

if __name__ == "__main__":
    pass

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap


