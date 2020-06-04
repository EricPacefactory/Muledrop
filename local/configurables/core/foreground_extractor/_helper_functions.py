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

from local.lib.ui_utils.display_specification import Display_Window_Specification

from local.eolib.math.signal_processing import odd_tuplify


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
    
    def sum_from_deck(self, num_to_sum):
        
        # Gather all the frames needed for summing
        frame_list = [self.read_newest(each_idx) for each_idx in range(1 + num_to_sum)]
        
        # Sum up all frames, with extra bits to avoid overflow
        summed_frame = np.sum(frame_list, axis = 0, dtype = np.float32)
        
        # Force returned result to be a 'proper' uint8 image
        return np.uint8(np.clip(summed_frame, 0, 255))
    
    # .................................................................................................................
    
    def modify_all(self, frame_modifier_callback):
        
        ''' Function use to apply a callback to all frames in the deck '''
        
        for each_idx, each_frame in enumerate(self.deck):
            new_frame = frame_modifier_callback(each_frame)
            self.deck[each_idx] = new_frame
    
    # .................................................................................................................
    
    def modify_one(self, deck_index, new_frame):
        
        '''
        Helper function which allows overwriting a specific frame in the deck
        Intended for use with 'iterate_all() function
        '''
        
        self.deck[deck_index] = new_frame
    
    # .................................................................................................................
    
    def iterate_all(self):
        
        '''
        Function which returns an iterator, used to make modifications to all frames in the deck
        Intended to be used with the 'modify_one' function.
        Example usage:
            for each_idx, each_frame in frame_deck.iterate_all():
                new_frame = each_frame + 1
                frame_deck.modify_one(each_idx, new_frame)
        '''
        
        for each_idx, each_frame in enumerate(self.deck):
            yield each_idx, each_frame
        
        return
    
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
#%% Define setup helpers
    
# .....................................................................................................................

def get_2d_kernel(kernel_size_1d):
    
    ''' Helper function which converts an integer kernel size into a tuple of odd values for x/y '''
        
    return odd_tuplify(kernel_size_1d, one_maps_to = 3)

# .....................................................................................................................

def create_morphology_element(morphology_shape, kernel_size_1d):
    
    '''
    Helper function which builds a morphology structuring element (i.e. a kernel) based on a shape and size
    
    Inputs:
        morphology_shape --> (One of cv2.MORPH_RECT, cv2.MORPH_CROSS or cv2.MORPH_ELLIPSE) Determines the shape
                             of the morphology kernel
                             
        kernel_size_1d --> (Integer) Specifies the number of pixels (acting like a radius) that sets the total
                           size of the morphology element
    
    Outputs:
        morphology_element (for use in cv2.morphologyEx function)
    '''
    
    # Get odd sized tuple for defining the (square) morphology kernel
    kernel_size_2d = get_2d_kernel(kernel_size_1d)
    
    # Create the structure element
    return cv2.getStructuringElement(morphology_shape, kernel_size_2d)

# .....................................................................................................................

def create_mask_image(mask_wh, mask_zones_list):
    
    '''
    Helper function which creates a mask image given a target width/height and list of zones to mask
    Note that the zones are interpretted as being 'masked out' (i.e. blacked out)
    Also note that the zones themselves should be specified using normalized co-ordinates.
    '''
        
    # Get the input frame size, so we can create a mask with the right size
    mask_width, mask_height = mask_wh
    frame_scaling = np.float32(((mask_width - 1), (mask_height - 1)))
    
    # Calculate the scaling factor needed to pixelize mask point locations
    frame_scaling = np.float32(((mask_width - 1), (mask_height - 1)))
    
    # Create an empty (bright) mask image (i.e. fully passes everything through)
    mask_image = np.full((mask_height, mask_width), 255, dtype=np.uint8)
    mask_fill = 0
    mask_line_type = cv2.LINE_8
    
    # Draw masked zones to black-out regions
    for each_zone in mask_zones_list:
        
        # Don't try to draw anything when given empty entities!
        if each_zone == []:
            continue
        
        # Draw a filled (dark) polygon for each masking zone
        each_zone_array = np.float32(each_zone)
        mask_list_px = np.int32(np.round(each_zone_array * frame_scaling))
        cv2.fillPoly(mask_image, [mask_list_px], mask_fill, mask_line_type)
        cv2.polylines(mask_image, [mask_list_px], True, mask_fill, 1, mask_line_type)
    
    return mask_image

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Demo
    
if __name__ == "__main__":
    pass
    

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap


