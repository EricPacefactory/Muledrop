#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri May 31 14:40:31 2019

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

from local.lib.ui_utils.display_specification import Display_Window_Specification


# ---------------------------------------------------------------------------------------------------------------------
#%% Define configuration displays

class Outlined_Input(Display_Window_Specification):
    
    # .................................................................................................................
    
    def __init__(self, layout_index, num_rows, num_columns, initial_display = False, drawing_json = None):
        
        # Inherit from parent class
        super().__init__("Preprocessed", layout_index, num_rows, num_columns, 
                         initial_display = initial_display, drawing_json = drawing_json,
                         limit_wh = True)
        
    # .................................................................................................................
        
    def display(self, stage_outputs, configurable_ref, mouse_xy, 
                current_frame_index, current_epoch_ms, current_datetime):
        
        # Get frame for display
        display_frame = stage_outputs["preprocessor"]["preprocessed_frame"]
        
        return draw_outlines(display_frame, stage_outputs, configurable_ref)
    
    # .................................................................................................................
    # .................................................................................................................


class Masked_Differences(Display_Window_Specification):
    
    # .................................................................................................................
    
    def __init__(self, layout_index, num_rows, num_columns, initial_display = False, drawing_json = None):
        
        # Inherit from parent class
        super().__init__("Masked Display", layout_index, num_rows, num_columns, 
                         initial_display = initial_display, drawing_json = drawing_json,
                         limit_wh = True)
        
    # .................................................................................................................
        
    def display(self, stage_outputs, configurable_ref, mouse_xy, 
                current_frame_index, current_epoch_ms, current_datetime):
        
        # Get frame for display
        display_frame = stage_outputs["preprocessor"]["preprocessed_frame"]
        binary_frame_1ch = stage_outputs["foreground_extractor"]["binary_frame_1ch"]
        
        # Scale the binary frame up to match the display
        display_height, display_width = display_frame.shape[0:2]
        display_wh = (display_width, display_height)
        scaled_binary_frame = cv2.resize(binary_frame_1ch, dsize = (display_wh), interpolation = cv2.INTER_NEAREST)
        
        # Use mask to scale in portions of the display frame
        mask_1d = np.float32(scaled_binary_frame) * np.float32(1.0 / 255.0)
        mask_3d = np.repeat(np.expand_dims(mask_1d, 2), 3, axis = 2)
        masked_display = np.uint8(display_frame * mask_3d)
        
        return masked_display
    
    # .................................................................................................................
    # .................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Define drawing functions

# .....................................................................................................................

def draw_outlines(display_frame, stage_outputs, configurable_ref):
    
    # Grab a copy of the color image that we can draw on and the binary image for finding outlines
    binary_frame_1ch = stage_outputs["foreground_extractor"]["binary_frame_1ch"]
    
    # Get display controls
    show_outlines = configurable_ref._show_outlines
    zero_threshold = (configurable_ref.threshold == 0)
    if not show_outlines or zero_threshold:
        return display_frame
    
    # Make copies so we don't alter the original frames
    outline_frame = display_frame.copy()
    detect_frame = binary_frame_1ch.copy()
    
    # Record frame sizing so we can draw normalized co-ordinate locations
    bin_h, bin_w = detect_frame.shape[0:2]
    disp_h, disp_w = outline_frame.shape[0:2]
    binary_wh = np.array((bin_w - 1, bin_h - 1))
    disp_wh = np.array((disp_w - 1, disp_h - 1))
    norm_scaling = 1 / binary_wh
    
    # Find contours using opencv 3/4 friendly syntax
    contour_list, _ = cv2.findContours(detect_frame, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[-2:]
    
    for each_outline in contour_list:
        
        # Scale the outline so we can draw it into the display frame properly
        norm_outline = each_outline * norm_scaling
        disp_outline = np.int32(norm_outline * disp_wh)        
        cv2.polylines(outline_frame, [disp_outline], True, (255, 255, 0), 1, cv2.LINE_AA)
    
    return outline_frame

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Demo
    
if __name__ == "__main__":
    pass
    

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap


