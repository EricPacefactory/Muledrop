#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Apr 11 11:54:27 2019

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

from functools import partial

from local.configurables.core.frame_processor.reference_frameprocessor import Reference_Frame_Processor
from local.configurables.core.frame_processor._helper_functions import blank_binary_frame_from_input_wh
from local.configurables.core.frame_processor._helper_functions import partial_fast_blur, partial_grayscale
from local.configurables.core.frame_processor._helper_functions import partial_resize_by_dimensions, partial_threshold
from local.configurables.core.frame_processor._helper_functions import Frame_Deck_LIFO, calculate_scaled_wh

# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes

class Frame_Processor_Stage(Reference_Frame_Processor):
    
    # .................................................................................................................
    
    def __init__(self, input_wh):
        
        # Inherit reference functionality
        super().__init__(input_wh, file_dunder = __file__)
        
        # Allocate space for frame decks
        self._flow_deck = None
        self._max_deck_length = 10
        self._max_kernel_size = 15
        
        # Allocate space for dervied variables
        self._proc_func_list = None
        
        # llocate storage for variables used to remove processing functions (to improve performance)
        self._enable_downscale = False
        self._enable_blur = False
        self._enable_threshold = False
        
        # .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  . Control Group 1 .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .
        
        mg = self.controls_manager.new_control_group("Pre-Flow Controls")
        
        self.downscale_factor = \
        mg.attach_slider("downscale_factor", 
                         label = "Downscaling", 
                         default_value = 0.15,
                         min_value = 0.1,
                         max_value = 1.0,
                         step_size = 1/100,
                         return_type = float,
                         zero_referenced = True)
        
        self.threshold = \
        mg.attach_slider("threshold", 
                         label = "Threshold", 
                         default_value = 0,
                         min_value = 0,
                         max_value = 255,
                         return_type = int)
        
        self.blur_size = \
        mg.attach_slider("blur_size", 
                         label = "Blurriness", 
                         default_value = 1,
                         min_value = 0,
                         max_value = self._max_kernel_size,
                         return_type = int)
        
        self.flow_depth = \
        mg.attach_slider("flow_depth", 
                         label = "Flow Depth", 
                         default_value = 1,
                         min_value = 0,
                         max_value = self._max_deck_length,
                         return_type = int)
    
        # .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  . Control Group 3 .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .
        
        og = self.controls_manager.new_control_group("Optical Flow Controls")
        
        self.of_pyr_scale = \
        og.attach_slider("of_pyr_scale", 
                         label = "Pyramid Scaling", 
                         default_value = 0.5,
                         min_value = 0.01,
                         max_value = 0.95,
                         step_size = 1/100,
                         zero_referenced = True,
                         return_type = float)
        
        self.of_levels = \
        og.attach_slider("of_levels", 
                         label = "Pyramid Layers", 
                         default_value = 3,
                         min_value = 1,
                         max_value = 10,
                         zero_referenced = True,
                         return_type = int)
        
        self.of_winsize = \
        og.attach_slider("of_winsize", 
                         label = "Window Size", 
                         default_value = 5,
                         min_value = 1,
                         max_value = 50,
                         zero_referenced = True,
                         return_type = int)
        
        self.of_iterations = \
        og.attach_slider("of_iterations", 
                         label = "Iterations", 
                         default_value = 8,
                         min_value = 1,
                         max_value = 25,
                         zero_referenced = True,
                         return_type = int)
        
        self.of_poly_n = \
        og.attach_slider("of_poly_n", 
                         label = "Pixel Neighborhood", 
                         default_value = 5,
                         min_value = 1,
                         max_value = 25,
                         zero_referenced = True,
                         return_type = int)

        self.of_poly_sigma = \
        og.attach_slider("of_poly_sigma", 
                         label = "Gaussian StDev", 
                         default_value = 1.2,
                         min_value = 0.5,
                         max_value = 1.5,
                         step_size = 1/100,
                         zero_referenced = True,
                         return_type = float)
    
        self.of_flags = \
        og.attach_menu("of_flags",
                       label = "Flags",
                       default_value = "None", 
                       option_label_value_list = [("None", 0),
                                                  ("Gaussian Window", cv2.OPTFLOW_FARNEBACK_GAUSSIAN)],
                       tooltip = "")
        
        self.of_output_scale = \
        og.attach_slider("of_output_scale",
                         label = "Output Scale", 
                         default_value = 500,
                         min_value = 0, max_value = 50000, step_size = 1,
                         zero_referenced = True,
                         return_type = int)
        
    # .................................................................................................................
    
    def reset(self):
        
        # Clear out frame decks, since we don't want to include frames across a reset
        self._flow_deck = None
        self._setup_decks(self.downscale_factor)
        
    # .................................................................................................................
    
    def setup(self, variables_changed_dict):
        
        # Set up enablers
        self._enable_downscale = (self.downscale_factor < 1.0)
        self._enable_blur = (self.blur_size > 0)
        self._enable_flow = (self.flow_depth > 0)
        self._enable_threshold = (self.threshold > 0)     
        
        # Set up frame decks if needed
        self._setup_decks(self.downscale_factor)
        
        # Build the processing function list
        self._proc_func_list = self._build_frame_processor()
        
    # .................................................................................................................
    
    def _setup_decks(self, scaling_factor = 1.0):
        
        # Get the input frame size, so we can initialize decks with the right sizing
        _, (scaled_width, scaled_height) = calculate_scaled_wh(self.input_wh, scaling_factor)
        gray_shape = (scaled_width, scaled_height)
        deck_length = 1 + self._max_deck_length 
        
        # Se tup the flow deck if needed
        if self._flow_deck is None:
            flow_deck = Frame_Deck_LIFO(deck_length)
            flow_deck.initialize_missing_from_shape(gray_shape)
            self._flow_deck = flow_deck
        
        # Resize the deck contents if the scaling factor changes
        resize_func = partial_resize_by_dimensions(scaled_width, scaled_height, cv2.INTER_NEAREST)
        
        self._flow_deck.modify_all(resize_func)
        
    # .................................................................................................................
    
    def apply_frame_processing(self, frame):
        try:
            
            # Run through all the frame processing functions in the list!
            new_frame = frame.copy()
            for each_func in self._proc_func_list:
                new_frame = each_func(new_frame)            
                
            return new_frame
        
        except Exception as err:
            print("{}: FRAME ERROR".format(self.script_name))
            print(err)
            return blank_binary_frame_from_input_wh(self.input_wh)
        
    # .................................................................................................................
    
    def update_background(self, preprocessed_background_frame, bg_update):
        # No background processing        
        return None
        
    # .................................................................................................................
    
    def _build_frame_processor(self):
        
        # For disabling processing steps
        passthru = lambda frame: frame
        
        # Downscale if needed
        _, downscale_wh = calculate_scaled_wh(self.input_wh, self.downscale_factor)
        downscale_func = partial_resize_by_dimensions(*downscale_wh, cv2.INTER_NEAREST)
        
        # Blur the image
        blur_func = partial_fast_blur(self.blur_size)
        
        # Grayscale 
        gray_func = partial_grayscale()
        
        # Apply optical flow
        flow_func = partial_self_flow(self._flow_deck, self.flow_depth,
                                      self.of_pyr_scale, 
                                      self.of_levels, 
                                      self.of_winsize, 
                                      self.of_iterations, 
                                      self.of_poly_n, 
                                      self.of_poly_sigma, 
                                      self.of_flags,
                                      self.of_output_scale)
        
        # Threshold
        thresh_func = partial_threshold(self.threshold)
        
        # Create function call list
        func_list = [downscale_func if self._enable_downscale else passthru,
                     blur_func if self._enable_blur else passthru, 
                     gray_func, 
                     flow_func if self._enable_flow else passthru,
                     thresh_func if self._enable_threshold else passthru]
        
        return func_list
        
    # .................................................................................................................
    # .................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

# .....................................................................................................................

def partial_self_flow(deck_ref, backward_index,
                      pyr_scale, levels, winsize, iterations, poly_n, poly_sigma, flags,
                      output_scale):
    
    # Gather all the settings for cleanliness
    optflow_config = {"pyr_scale": pyr_scale,
                      "levels": levels,
                      "winsize": winsize,
                      "iterations": iterations,
                      "poly_n": poly_n,
                      "poly_sigma": poly_sigma,
                      "flags": flags}
    
    # Create function which loads up the frame deck then reads a previous frame from it to apply absdiff
    def _update_deck_oflow(frame, difference_index, frame_deck, optical_flow_config):
        
        # Update frame deck, then grab a previous frame for absdiff
        prev_frame = frame_deck.add_and_read_newest(frame, difference_index)  

        flow_uv = cv2.calcOpticalFlowFarneback(prev_frame, frame, None, **optical_flow_config)
        #cv2.calcOpticalFlowFarneback(prev, next, flow, pyr_scale, levels, 
        #                             winsize, iterations, poly_n, poly_sigma, flags)
        
        # Convert optical flow u/v values to magnitude and angle
        mag, ang = cv2.cartToPolar(flow_uv[:, :, 0], flow_uv[:, :, 1])
        
        frame_height, frame_width = frame.shape
        hsv_frame = np.full((frame_height, frame_width, 3), 255, dtype=np.uint8)
        
        hsv_frame[:, :, 0] = ang * (180 / np.pi) * (1/2)
        hsv_frame[:, :, 2] = np.clip(mag * output_scale, 0, 255) #cv2.normalize(mag, None, 0, 255, cv2.NORM_MINMAX)
        bgr_frame = cv2.cvtColor(hsv_frame, cv2.COLOR_HSV2BGR)
        
        return bgr_frame
    
    # Set up partial function ahead of time for convenience
    self_flow_func = partial(_update_deck_oflow, 
                             difference_index = backward_index,
                             frame_deck = deck_ref,
                             optical_flow_config = optflow_config)
    
    return self_flow_func

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
