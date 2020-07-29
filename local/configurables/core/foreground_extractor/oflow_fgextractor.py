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

from local.lib.common.images import scale_factor_downscale

from local.configurables.core.foreground_extractor.reference_fgextractor import Reference_FG_Extractor

from local.eolib.video.persistence import Frame_Deck
from local.eolib.video.imaging import get_2d_kernel


# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes

class Configurable(Reference_FG_Extractor):
    
    # .................................................................................................................
    
    def __init__(self, location_select_folder_path, camera_select, input_wh):
        
        # Inherit reference functionality
        super().__init__(location_select_folder_path, camera_select, input_wh, file_dunder = __file__)
        
        # Allocate space for altered frame sizing
        self.output_w = None
        self.output_h = None
        
        # Allocate space for frame decks
        self._flow_deck = None
        self._max_deck_length = 10
        self._max_kernel_size = 15
        
        # Allocate space for dervied variables
        self._scaled_mask_image = None
        self._downscale_wh = None
        self._blur_kernel = None
        
        # llocate storage for variables used to remove processing functions (to improve performance)
        self._enable_downscale = False
        self._enable_blur = False
        self._enable_threshold = False
        
        # .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  . Control Group 1 .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .
        
        self.ctrl_spec.new_control_group("Pre-Flow Controls")
        
        self.downscale_factor = \
        self.ctrl_spec.attach_slider(
                "downscale_factor",
                label = "Downscaling",
                default_value = 0.50,
                min_value = 0.1, max_value = 1.0, step_size = 1/100,
                return_type = float,
                zero_referenced = True)
        
        self.downscale_interpolation = \
        self.ctrl_spec.attach_menu(
                "downscale_interpolation",
                label = "Downscaling Interpolation",
                default_value = "Nearest",
                option_label_value_list = [("Nearest", cv2.INTER_NEAREST),
                                           ("Bilinear", cv2.INTER_LINEAR),
                                           ("Area", cv2.INTER_AREA)],
                tooltip = "Set the interpolation style for pixels sampled at fractional indices")
        
        self.threshold = \
        self.ctrl_spec.attach_slider(
                "threshold",
                label = "Threshold",
                default_value = 0,
                min_value = 0,
                max_value = 255,
                return_type = int)
        
        self.blur_size = \
        self.ctrl_spec.attach_slider(
                "blur_size",
                label = "Blurriness",
                default_value = 1,
                min_value = 0,
                max_value = self._max_kernel_size,
                return_type = int)
        
        self.flow_depth = \
        self.ctrl_spec.attach_slider(
                "flow_depth",
                label = "Flow Depth",
                default_value = 1,
                min_value = 0,
                max_value = self._max_deck_length,
                return_type = int)
    
        # .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  . Control Group 3 .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .
        
        self.ctrl_spec.new_control_group("Optical Flow Controls")
        
        self.of_pyr_scale = \
        self.ctrl_spec.attach_slider(
                "of_pyr_scale",
                label = "Pyramid Scaling",
                default_value = 0.5,
                min_value = 0.01, max_value = 0.95, step_size = 1/100,
                zero_referenced = True,
                return_type = float)
        
        self.of_levels = \
        self.ctrl_spec.attach_slider(
                "of_levels",
                label = "Pyramid Layers",
                default_value = 3,
                min_value = 1,
                max_value = 10,
                zero_referenced = True,
                return_type = int)
        
        self.of_winsize = \
        self.ctrl_spec.attach_slider(
                "of_winsize",
                label = "Window Size",
                default_value = 5,
                min_value = 1,
                max_value = 50,
                zero_referenced = True,
                return_type = int)
        
        self.of_iterations = \
        self.ctrl_spec.attach_slider(
                "of_iterations",
                label = "Iterations",
                default_value = 8,
                min_value = 1,
                max_value = 25,
                zero_referenced = True,
                return_type = int)
        
        self.of_poly_n = \
        self.ctrl_spec.attach_slider(
                "of_poly_n",
                label = "Pixel Neighborhood",
                default_value = 5,
                min_value = 1,
                max_value = 25,
                zero_referenced = True,
                return_type = int)

        self.of_poly_sigma = \
        self.ctrl_spec.attach_slider(
                "of_poly_sigma",
                label = "Gaussian StDev",
                default_value = 1.2,
                min_value = 0.5, max_value = 1.5, step_size = 1/100,
                zero_referenced = True,
                return_type = float)
    
        self.of_flags = \
        self.ctrl_spec.attach_menu(
                "of_flags",
                label = "Flags",
                default_value = "None",
                option_label_value_list = [("None", 0),
                                           ("Gaussian Window", cv2.OPTFLOW_FARNEBACK_GAUSSIAN)],
                tooltip = "")
        
        self.of_output_scale = \
        self.ctrl_spec.attach_slider(
                "of_output_scale",
                label = "Output Scale",
                default_value = 500,
                min_value = 0, max_value = 50000, step_size = 1,
                zero_referenced = True,
                return_type = int)
        
    # .................................................................................................................
    
    def reset(self):
        
        # Clear out frame decks, since we don't want to sum up frames across a reset
        self._setup_decks(reset_all = True)
        
    # .................................................................................................................
    
    def setup(self, variables_changed_dict):
        
        # Pre-calculate derived settings
        self._downscale_wh = scale_factor_downscale(self.input_wh, self.downscale_factor)
        self._blur_kernel = get_2d_kernel(self.blur_size)
        
        # Update 'output' dimensions
        self.output_w, self.output_h = self._downscale_wh
        
        # Set up enablers
        self._enable_downscale = (self.downscale_factor < 1.0)
        self._enable_blur = (self.blur_size > 0)
        self._enable_flow = (self.flow_depth > 0)
        self._enable_threshold = (self.threshold > 0)     
        
        # Set up frame decks if needed
        self._flow_deck = self._setup_decks()
        if "downscale_factor" in variables_changed_dict.keys():
            self._update_decks()
        
        return
    
    # .................................................................................................................
    
    def _setup_decks(self, reset_all = False):
        
        # Get the input frame size, so we can initialize the deck with properly sized blank frames
        scaled_width, scaled_height = scale_factor_downscale(self.input_wh, self.downscale_factor)
        gray_shape = (scaled_height, scaled_width)
        
        # Initialize the summation deck if needed
        flow_deck = self._flow_deck
        if flow_deck is None or reset_all:
            deck_length = (1 + self._max_deck_length) if self.configure_mode else (1 + self.flow_depth)
            flow_deck = Frame_Deck(deck_length)
            flow_deck.fill_with_blank_shape(gray_shape)
        
        return flow_deck
    
    # .................................................................................................................
    
    def _update_decks(self):
        
        # For simplicity
        resize_kwargs = {"dsize": self._downscale_wh, "interpolation": self.downscale_interpolation}
        
        # Update summation frames
        for each_idx, each_frame in self._flow_deck.iterate_all():
            new_frame = cv2.resize(each_frame, **resize_kwargs)
            self._flow_deck.modify_one(each_idx, new_frame)
        
        return
    
    # .................................................................................................................
    
    def process_current_frame(self, frame):
        
        # Apply downscaling
        if self._enable_downscale:
            frame = cv2.resize(frame, dsize = self._downscale_wh, interpolation = self.downscale_interpolation)
        
        # Apply blurring
        if self._enable_blur:
            frame = cv2.blur(frame, self._blur_kernel)
        
        # Convert to grayscale
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Store frame in deck
        prev_frame = self._flow_deck.read_from_newest()
        self._flow_deck.add_to_deck(frame)
        
        # Apply optical flow
        frame = apply_optical_flow(frame, prev_frame, self.of_output_scale,
                                   self.of_pyr_scale,
                                   self.of_levels,
                                   self.of_winsize,
                                   self.of_iterations,
                                   self.of_poly_n,
                                   self.of_poly_sigma,
                                   self.of_flags)
        
        # Apply thresholding
        if self._enable_threshold:
            _, frame = cv2.threshold(frame, self.threshold, 255, cv2.THRESH_BINARY)
        
        return frame
    
    # .................................................................................................................
    
    def process_background_frame(self, bg_frame):
        # Do nothing, since we don't use a background for frame-to-frame differences
        return 0
    
    # .................................................................................................................
    # .................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

# .....................................................................................................................

def apply_optical_flow(curr_frame, prev_frame, output_scale,
                       pyr_scale, levels, winsize, iterations, poly_n, poly_sigma, flags):
    
    # Generate optical flow image output
    flow_uv = cv2.calcOpticalFlowFarneback(prev_frame, curr_frame,
                                           flow = None,
                                           pyr_scale = pyr_scale,
                                           levels = levels,
                                           winsize = winsize,
                                           iterations = iterations,
                                           poly_n = poly_n,
                                           poly_sigma = poly_sigma,
                                           flags = flags)
    
    # Convert optical flow u/v values to magnitude and angle
    mag, ang = cv2.cartToPolar(flow_uv[:, :, 0], flow_uv[:, :, 1])
    
    # Create hsv image from optical flow data
    frame_height, frame_width = curr_frame.shape[0:2]
    hsv_frame = np.full((frame_height, frame_width, 3), 255, dtype=np.uint8)
    
    # Convert optical flow output into a bgr image for viewing
    hsv_frame[:, :, 0] = ang * (180 / np.pi) * (1/2)
    hsv_frame[:, :, 2] = np.clip(mag * output_scale, 0, 255) #cv2.normalize(mag, None, 0, 255, cv2.NORM_MINMAX)
    bgr_frame = cv2.cvtColor(hsv_frame, cv2.COLOR_HSV2BGR)
    
    return bgr_frame

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Demo
    
if __name__ == "__main__":
    pass
    

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap
