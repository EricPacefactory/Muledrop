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

from collections import deque
from functools import partial

from local.lib.configuration_utils.display_specification import Display_Window_Specification

from eolib.math.signal_processing import odd_tuplify


# ---------------------------------------------------------------------------------------------------------------------
#%% Define configuration displays

class Outlined_Input(Display_Window_Specification):
    
    # .................................................................................................................
    
    def __init__(self, layout_index, num_rows, num_columns, initial_display = False):
        
        # Inherit from parent class
        super().__init__("Preprocessed", layout_index, num_rows, num_columns, 
                         initial_display = initial_display, 
                         max_wh = None)
        
    # .................................................................................................................
        
    def display(self, stage_outputs, configurable_ref, current_frame_index, current_time_sec, current_datetime):
        
        # Get frame for display
        display_frame = stage_outputs.get("preprocessor").get("preprocessed_frame")
        
        return draw_outlines(display_frame, stage_outputs, configurable_ref)
    
    # .................................................................................................................
    # .................................................................................................................


class Masked_Differences(Display_Window_Specification):
    
    # .................................................................................................................
    
    def __init__(self, layout_index, num_rows, num_columns, initial_display = False):
        
        # Inherit from parent class
        super().__init__("Masked Display", layout_index, num_rows, num_columns, 
                         initial_display = initial_display, 
                         max_wh = None)
        
    # .................................................................................................................
        
    def display(self, stage_outputs, configurable_ref, current_frame_index, current_time_sec, current_datetime):
        
        # Get frame for display
        display_frame = stage_outputs.get("preprocessor").get("preprocessed_frame")
        binary_frame_1ch = stage_outputs.get("frame_processor").get("binary_frame_1ch")
        
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
#%% Define classes


class Frame_Deck_LIFO:
    
    # .................................................................................................................
    
    def __init__(self, max_deck_size):
        self.deck = deque([], maxlen = max_deck_size)
        self.max_length = max_deck_size
    
    # .................................................................................................................
    
    @property
    def length(self):
        return len(self.deck)
        
    # .................................................................................................................
    
    @property
    def last_index(self):
        return self.length - 1
    
    # .................................................................................................................
    
    def initialize_missing_from_frame(self, frame):
        num_missing = self.max_length - self.length
        for k in range(num_missing):
            self.deck.append(frame)

    # .................................................................................................................
    
    def initialize_missing_from_shape(self, frame_shape, initialized_dtype = np.uint8):
        blank_frame = np.zeros(frame_shape, dtype=initialized_dtype)
        self.initialize_missing_from_frame(blank_frame)
    
    # .................................................................................................................
    
    def add(self, frame):
        self.deck.appendleft(frame)
        
    # .................................................................................................................
        
    def add_and_read_newest(self, new_frame, relative_index = 1):
        
        # Update frame deck, then return a previous frame
        self.add(new_frame)
        prev_frame = self.read_newest(relative_index)
        
        return prev_frame
    
    # .................................................................................................................
        
    def add_and_read_oldest(self, new_frame, relative_index = 1):
        
        # Update frame deck, then return a previous frame
        self.add(new_frame)
        prev_frame = self.read_oldest(relative_index)
        
        return prev_frame

    # .................................................................................................................
    
    def read_newest(self, relative_index = 0):
        new_idx = relative_index
        return self.deck[new_idx]
    
    # .................................................................................................................
    
    def read_oldest(self, relative_index = 0):        
        old_idx = self.last_index - relative_index
        return self.deck[old_idx]
    
    # .................................................................................................................
    
    def modify_all(self, frame_modifier_callback):
        for each_idx, each_frame in enumerate(self.deck):
            new_frame = frame_modifier_callback(each_frame)
            self.deck[each_idx] = new_frame
    
    # .................................................................................................................
    # .................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Define general functions

# .....................................................................................................................

def blank_binary_frame_from_input_wh(input_wh):
    return np.zeros((input_wh[1], input_wh[0]), dtype=np.uint8)

# .....................................................................................................................

def blank_binary_frame_from_frame(frame):
    frame_height, frame_width, frame_channels = frame.shape
    return np.zeros((frame_height, frame_width), dtype=np.uint8)

# .....................................................................................................................

def calculate_scaled_wh(input_wh, scaling_factor):
        
        # Get the input frame size, so we can initialize decks with the right sizing
        input_width, input_height = input_wh
        scale_width = int(round(input_width * scaling_factor))
        scale_height = int(round(input_height * scaling_factor))
        
        # Bundle the sizes for convenience
        original_wh = input_wh
        scaled_wh = (scale_width, scale_height)
        
        return original_wh, scaled_wh

# .....................................................................................................................
# .....................................................................................................................

#%% Define drawing functions

# .....................................................................................................................

def draw_outlines(display_frame, stage_outputs, configurable_ref):
    
    # Grab a copy of the color image that we can draw on and the binary image for finding outlines
    binary_frame_1ch = stage_outputs["frame_processor"]["binary_frame_1ch"]
    
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
#%% Define partialing functions
    
# .....................................................................................................................

def partial_grayscale():    
    return partial(cv2.cvtColor, code = cv2.COLOR_BGR2GRAY)

# .....................................................................................................................

def partial_norm_grayscale():
    return partial(np.max, axis = 2)

# .....................................................................................................................
    
def partial_fast_blur(kernel_size):
    
    # Get odd sized tuple for defining the (square) blur kernel
    blur_kernel_xy = odd_tuplify(kernel_size, one_maps_to = 3)
    return partial(cv2.blur, ksize = blur_kernel_xy)

# .....................................................................................................................

def partial_threshold(threshold):
    
    # Create function that pulls out the frame index (index 1) from the OCV threshold function output
    def _threshold_indexed(frame, threshold_value):
        return cv2.threshold(frame, threshold_value, 255, cv2.THRESH_BINARY)[1]
    
    # Set up partial function ahead of time for convenience
    thresh_func = partial(_threshold_indexed, threshold_value = threshold)
    
    return thresh_func

# .....................................................................................................................

def partial_mask_image(mask_image):
    return partial(cv2.bitwise_and, src2 = mask_image)

# .....................................................................................................................

def partial_morphology(kernel_size, operation, shape):
    
    # Get odd sized tuple for defining the (square) morphology kernel
    morph_kernel_xy = odd_tuplify(kernel_size, one_maps_to = 3)
    
    # Create the structure element
    morph_elem = cv2.getStructuringElement(shape, morph_kernel_xy)
    
    # Set up partial function ahead of time for convenience
    morph_func = partial(cv2.morphologyEx,
                         op = operation,
                         kernel = morph_elem)
    
    return morph_func

# .....................................................................................................................

def partial_self_sum(deck_ref, num_to_sum):
    
    # Create function which updates the frame deck then grabs a set of frames to sum up (historically)
    def _update_deck_selfsum(frame, num_to_sum, frame_deck):
        
        # Update frame deck with the new frame
        frame_deck.add(frame)
        
        # Get frames to sum
        frame_list = [frame_deck.read_newest(frame_idx) for frame_idx in range(1 + num_to_sum)]
        
        # Numpy: np.sum(a, axis, dtype)
        summed_frame = np.sum(frame_list, axis=0, dtype = np.uint16)
        return np.uint8(np.clip(summed_frame, 0, 255))
    
    # Set up partial function ahead of time for convenience
    self_sum_func = partial(_update_deck_selfsum,
                            num_to_sum = num_to_sum,
                            frame_deck = deck_ref)
    
    return self_sum_func

# .....................................................................................................................
    
def partial_resize_by_dimensions(frame_width, frame_height, interpolation = cv2.INTER_LINEAR):
    scaled_wh = (frame_width, frame_height)
    return partial(cv2.resize,
                   dsize = scaled_wh,
                   interpolation = interpolation)

# .....................................................................................................................
    
# .....................................................................................................................

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Demo
    
if __name__ == "__main__":
    pass
    

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap


