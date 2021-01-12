#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Jan  5 14:28:51 2021

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
from local.lib.common.timekeeper_utils import Periodic_Polled_Timer

from local.configurables.core.foreground_extractor.reference_fgextractor import Reference_FG_Extractor

from local.eolib.video.imaging import get_2d_kernel, create_morphology_element, make_mask_1ch


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
        
        # Allocate storage for periodic timer used to trigger background updates
        self._bg_update_timer = Periodic_Polled_Timer(trigger_on_first_check = False)
        
        # Allocate space for MoG background subtractor
        self._bgsubtractor = cv2.createBackgroundSubtractorMOG2()
        
        # Set all varaibles that require model resets (note, this is hard-coded! May become outdated...)
        self._bgs_reset_keys = {"downscale_factor", "downscale_interpolation", "blur_size", "use_grayscale"}
        
        # Allocate space for derived variables
        self._effective_learning_rate = None
        self._scaled_mask_image = None
        self._downscale_wh = None
        self._blur_kernel = None
        self._thresh_sq = None
        self._morph_element = None
        
        # Allocate storage for variables used to remove processing functions (to improve performance)
        self._enable_downscale = False
        self._enable_blur = False
        self._enable_morph = False
        self._enable_masking_optimized = False
        self._enable_sample_period = False
        self._enable_processing = False
        
        # .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  . Drawing Controls  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .
        
        self.mask_zone_list = \
        self.ctrl_spec.attach_drawing(
                "mask_zone_list",
                default_value = [[]],
                min_max_entities = None,
                min_max_points = (3, None),
                entity_type = "polygon",
                drawing_style = "zone")
        
        # .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  . Control Group 1 .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .
        
        self.ctrl_spec.new_control_group("General Controls")
        
        self._show_outlines = \
        self.ctrl_spec.attach_toggle(
                "_show_outlines",
                label = "Show Outlines",
                default_value = True,
                tooltip = "Overlay outlines of binary shapes on the input color image. Requires thresholding!")
        
        self.downscale_factor = \
        self.ctrl_spec.attach_slider(
                "downscale_factor",
                label = "Downscaling",
                default_value = 0.5,
                min_value = 0.1, max_value = 1.0, step_size = 1/100,
                return_type = float,
                zero_referenced = True,
                tooltip = "Perform all foreground processing on a reduced frame size")
        
        self.downscale_interpolation = \
        self.ctrl_spec.attach_menu(
                "downscale_interpolation",
                label = "Downscaling Interpolation",
                default_value = "Nearest",
                option_label_value_list = [("Nearest", cv2.INTER_NEAREST),
                                           ("Bilinear", cv2.INTER_LINEAR),
                                           ("Area", cv2.INTER_AREA)],
                tooltip = "Set the interpolation style for pixels sampled at fractional indices")
        
        self.blur_size = \
        self.ctrl_spec.attach_slider(
                "blur_size",
                label = "Blur Size",
                default_value = 2,
                min_value = 0,
                max_value = 15,
                return_type = int,
                tooltip = "Controls the amount of blurring applied, before background subtraction")
        
        self.use_grayscale = \
        self.ctrl_spec.attach_toggle(
                "use_grayscale",
                label = "Use Grayscale",
                default_value = False,
                tooltip = "If enabled, the background subtraction is performed in grayscale")
        
        self.enable_masking = \
        self.ctrl_spec.attach_toggle(
                "enable_masking",
                label = "Enable Masking",
                default_value = True,
                tooltip = "Enable or disable masking")
        
        # .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  . Control Group 2 .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .
        
        self.ctrl_spec.new_control_group("Subtraction Controls")
        
        self.sample_period_sec = \
        self.ctrl_spec.attach_slider(
                "sample_period_sec",
                label = "Background Sample Period",
                default_value = 15,
                min_value = 0,
                max_value = 60,
                return_type = int,
                zero_referenced = True,
                tooltip = ["Determines how often frames are used to update the modelled background image",
                           "If set to zero, every frame will be used!"])
        
        self.history_length = \
        self.ctrl_spec.attach_slider(
                "history_length",
                label = "History",
                default_value = 500,
                min_value = 5,
                max_value = 10000,
                return_type = int,
                zero_referenced = True,
                visible = False,
                tooltip = "Number of frames used to determine model weights")
        
        self.threshold = \
        self.ctrl_spec.attach_slider(
                "threshold",
                label = "Threshold",
                default_value = 25,
                min_value = 1,
                max_value = 255,
                return_type = int,
                zero_referenced = True,
                tooltip = ["Threshold used to decide if a pixel is 'far enough' from",
                           "the modelled background to be considered part of the foreground."])
        
        self.learning_rate = \
        self.ctrl_spec.attach_slider(
                "learning_rate",
                label = "Learning Rate",
                default_value = 0.0,
                min_value = 0.0,
                max_value = 0.2,
                step_size = 0.001,
                return_type = float,
                zero_referenced = True,
                tooltip = ["Controls how much each new frame sample contributes",
                           "to updating the background estimate. Lower values",
                           "make the background updates less sensitive to the current",
                           "frame. Using a value of zero results in an 'auto'",
                           "learning rate selection."])
        
        self.enable_shadow_removal = \
        self.ctrl_spec.attach_toggle(
                "enable_shadow_removal",
                label = "Remove Shadows",
                default_value = False,
                tooltip = "If enabled, background subtraction will also attempt to remove shadows")
        
        # .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  . Control Group 3 .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .
        
        self.ctrl_spec.new_control_group("Post-Threshold Controls")
        
        self.morph_size = \
        self.ctrl_spec.attach_slider(
                "morph_size",
                label = "Shapeshift Region Size",
                default_value = 1,
                min_value = 0,
                max_value = 15,
                return_type = int,
                tooltip = ["Determines how large a region to look in when applying shapeshifting operations",
                           "For more detailed information about how shapeshifting works,",
                           "try searching for 'grayscale morphology'."])
        
        self.morph_op = \
        self.ctrl_spec.attach_menu(
                "morph_op",
                label = "Shapeshift Operation",
                default_value = "Expand Bright",
                option_label_value_list = [("Fill Dark", cv2.MORPH_CLOSE),
                                           ("Expand Bright", cv2.MORPH_DILATE),
                                           ("Fill Bright", cv2.MORPH_OPEN),
                                           ("Expand Dark", cv2.MORPH_ERODE)],
                tooltip = ["Changes the shapeshifting operation being performed:",
                           "     Fill Dark -> Useful for filling in holes/broken parts of shapes.",
                           " Expand Bright -> Gives nicer shapes, which can improve detection consistency.",
                           "   Fill Bright -> Useful for separating shapes that blend together too much.",
                           "   Expand Dark -> Shrinks shapes. Can be used to offset the effects of summation."])
        
        self.morph_shape = \
        self.ctrl_spec.attach_menu(
                "morph_shape",
                label = "Shapeshift Region Shape",
                default_value = "Square",
                option_label_value_list = [("Square", cv2.MORPH_RECT),
                                           ("Circle", cv2.MORPH_ELLIPSE),
                                           ("Cross", cv2.MORPH_CROSS)],
                visible = True,
                tooltip = "Determines the shape of the regions used in shapeshifting")
    
    # .................................................................................................................
    
    def set_output_wh(self):
        # OVERRIDING FROM PARENT CLASS
        self.output_wh = (self.output_w, self.output_h)
        
    # .................................................................................................................
    
    def reset(self):
        
        # Reset timing, so updates can continue to run        
        self._bg_update_timer.reset_timer()
        
        return
        
    # .................................................................................................................
    
    def setup(self, variables_changed_dict):
        
        # Pre-calculate derived settings
        self._downscale_wh = scale_factor_downscale(self.input_wh, self.downscale_factor)
        self._blur_kernel = get_2d_kernel(self.blur_size)
        self._morph_element = create_morphology_element(self.morph_shape, self.morph_size)
        
        # Update 'output' dimensions
        self.output_w, self.output_h = self._downscale_wh
        
        # Set up enablers
        self._enable_downscale = (self.downscale_factor < 1.0)
        self._enable_blur = (self.blur_size > 0)
        self._enable_morph = (self.morph_size > 0)
        self._enable_sample_period = (self.sample_period_sec > 0)
        
        # Update background update trigger period
        timer_ms = 1 if (self.sample_period_sec == 0) else 0
        self._bg_update_timer.set_trigger_period(seconds = self.sample_period_sec, milliseconds = timer_ms)
        
        # Re-draw the masking image
        self._scaled_mask_image = make_mask_1ch(self._downscale_wh, self.mask_zone_list, zones_are_normalized = True)
        mask_is_meaningful = (np.min(self._scaled_mask_image) == 0)
        self._enable_masking_optimized = (self.enable_masking and mask_is_meaningful)
        
        # Figure out if we need to set the learning rate to 'auto' (i.e. negative value)
        self._effective_learning_rate = self.learning_rate if self.learning_rate > 0 else -1
        
        # Re-create the background subtractor when specific variables are changed
        reset_subtractor = (not self._bgs_reset_keys.isdisjoint(variables_changed_dict.keys()))
        if reset_subtractor:
            self._bgsubtractor = cv2.createBackgroundSubtractorMOG2()
        
        # Initialize the background subtractor with the system-level background data if needed
        self._initialize_background_estimate(reset_subtractor)
        
        # Update background subtractor parameters
        self._bgsubtractor.setHistory(self.history_length)
        self._bgsubtractor.setVarThreshold(self.threshold ** 2)
        self._bgsubtractor.setDetectShadows(self.enable_shadow_removal)
    
    # .................................................................................................................
    
    def _initialize_background_estimate(self, subtractor_was_reset):
        
        '''
        Helper function used to set up an initial background for the subtractor
        If possible, uses an existing estimate from the subtractor itself
        otherwise will use system background estimate
        '''
        
        # Initialize the background subtractor with the system-level background data if needed
        existing_bg_estimate = self._bgsubtractor.getBackgroundImage()
        use_system_estimate = ((existing_bg_estimate is None) or subtractor_was_reset)
        
        # Grab the system estimate, and apply appropriate pre-processing
        if use_system_estimate:
            self.apply_background_processing()
            existing_bg_estimate = self.get_internal_background_frame()
            if existing_bg_estimate is not None:
                
                # Apply grayscale conversion
                if self.use_grayscale:
                    existing_bg_estimate = cv2.cvtColor(existing_bg_estimate, cv2.COLOR_BGR2GRAY)
                
                # Apply blurring
                if self._enable_blur:
                    existing_bg_estimate = cv2.blur(existing_bg_estimate, self._blur_kernel)
        
        # Force a 'full' update using an existing estimate
        self._bgsubtractor.apply(existing_bg_estimate, learningRate = 1)
        
        return
    
    # .................................................................................................................
    
    def process_current_frame(self, frame):
        
        # Delay processing until we've loaded the internal background (to use as a starting point)
        if not self._enable_processing:
            
            # Force a background initialization so we can try to access the internal background
            self._initialize_background_estimate(True)
            self.setup({})
            self._enable_processing = (self.get_internal_background_frame() is not None)
            
            # Create a blank frame as output until we begin
            frame_width, frame_height = self._downscale_wh
            blank_frame = np.zeros((frame_height, frame_width), dtype = np.uint8)
            
            return blank_frame
        
        # Apply downscaling
        if self._enable_downscale:
            frame = cv2.resize(frame, dsize = self._downscale_wh, interpolation = self.downscale_interpolation)
        
        # Apply grayscale conversion
        if self.use_grayscale:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Apply blurring
        if self._enable_blur:
            frame = cv2.blur(frame, self._blur_kernel)
        
        # Decide if we should 'sample' the background on this frame
        _, current_epoch_ms, _ = self.get_time_info()
        update_bgs = self._bg_update_timer.check_trigger(current_epoch_ms)
        
        # Perform background subtraction (with thresholding to remove shadows)
        enabled_learning_rate = self._effective_learning_rate if update_bgs else 0
        frame = self._bgsubtractor.apply(frame, learningRate = enabled_learning_rate)
        
        # Threshold the image to remove shadows (which are mapped to a value of 127), if needed
        if self.enable_shadow_removal:
            _, frame = cv2.threshold(frame, 128, 255, cv2.THRESH_BINARY)
        
        # Apply post-threshold morphology
        if self._enable_morph:
            frame = cv2.morphologyEx(frame, op = self.morph_op, kernel = self._morph_element)
        
        # Apply masking
        if self._enable_masking_optimized:
            frame = cv2.bitwise_and(frame, self._scaled_mask_image)
        
        return frame
    
    # .................................................................................................................
    
    def process_background_frame(self, bg_frame):
        
        # Scale the (system) background frame to matching processing dimensions
        # Note: this only occurs on startup, since the background subtractor takes over afterwards
        bg_frame = cv2.resize(bg_frame, dsize = self._downscale_wh, interpolation = self.downscale_interpolation)        
        
        return bg_frame
    
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
