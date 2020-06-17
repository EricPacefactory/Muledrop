#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Aug 23 15:35:29 2019

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

from local.lib.common.timekeeper_utils import Periodic_Polled_Timer
from local.lib.common.images import scale_factor_downscale

from local.configurables.core.foreground_extractor.reference_fgextractor import Reference_FG_Extractor

from local.configurables.core.foreground_extractor._helper_functions import Frame_Deck_LIFO
from local.configurables.core.foreground_extractor._helper_functions import get_2d_kernel, create_morphology_element
from local.configurables.core.foreground_extractor._helper_functions import create_mask_image


# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes

class FG_Extractor_Stage(Reference_FG_Extractor):
    
    # .................................................................................................................
    
    def __init__(self, cameras_folder_path, camera_select, user_select, input_wh):
        
        # Inherit reference functionality
        super().__init__(cameras_folder_path, camera_select, user_select, input_wh, file_dunder = __file__)
        
        # Allocate storage for timer user to update rolling background
        self._rbg_timer = Periodic_Polled_Timer()
        
        # Allocate storage for rolling-background frame data
        self.current_background = None
        self._rolling_bg_frame_float32 = None
        self._rolling_bg_frame_uint8 = None
        self._clean_rolling_bg_uint8 = None
        
        # Allocate space for altered frame sizing
        self.output_w = None
        self.output_h = None
        
        # Allocate space for frame decks
        self._sum_deck = None
        self._max_deck_length = 30
        self._max_kernel_size = 15
        
        # Allocate space for dervied variables
        self._scaled_mask_image = None
        self._downscale_wh = None
        self._pre_blur_kernel = None
        self._post_blur_kernel = None
        self._pre_morph_element = None
        self._post_morph_element = None
        
        # Allocate storage for variables used to remove processing functions (to improve performance)
        self._enable_downscale = False
        self._enable_pre_blur = False
        self._enable_post_blur = False
        self._enable_pre_morph = False
        self._enable_summation = False
        self._enable_threshold = False
        self._enable_post_morph = False
        self._enable_masking_optimized = False
        
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
                default_value = 50/100,
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
                                           ("Cubic", cv2.INTER_CUBIC)],
                tooltip = "Set the interpolation style for pixels sampled at fractional indices")
        
        self.pre_blur_size = \
        self.ctrl_spec.attach_slider(
                "pre_blur_size", 
                label = "Shared Blurriness", 
                default_value = 3,
                min_value = 0,
                max_value = self._max_kernel_size,
                return_type = int,
                tooltip = ["Amount of blurring applied to both the current frame and the",
                           "background image before calculating the difference between the two.",
                           "Helps to reduce errors due to video noise/artifacting.",
                           "For more technical information, try searching for 'box blur'."])
        
        self.threshold = \
        self.ctrl_spec.attach_slider(
                "threshold", 
                label = "Threshold", 
                default_value = 100,
                min_value = 0,
                max_value = 255,
                return_type = int,
                tooltip = ["Thresholding converts (grayscale) frame differences to black and white images.",
                           "Differences that are above the threshold are converted to white pixels,",
                           "differences below the threshold will be shown as black pixels.",
                           "Thresholding is applied after:",
                           "downscaling, blurring, frame-differencing, (gray) shapeshifting and summation."])
        
        self.use_max_diff = \
        self.ctrl_spec.attach_toggle(
                "use_max_diff", 
                label = "Use Maximum Difference", 
                default_value = False,
                tooltip = ["Enabling this setting means that the output of the background difference ",
                           "calculation will be the maximum difference among the RGB channels. When",
                           "disabled, the output will be a grayscale average of the RGB channels.",
                           "Using the maximum will result in a more sensitive output, but",
                           "it runs significantly slower!"])
        
        self.enable_masking = \
        self.ctrl_spec.attach_toggle(
                "enable_masking", 
                label = "Enable Masking", 
                default_value = True,
                tooltip = "Enable or disable masking")
        
        # .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  . Control Group 2 .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .
        
        self.ctrl_spec.new_control_group("Post-Subtraction Controls")
        
        self.post_blur_size = \
        self.ctrl_spec.attach_slider(
                "post_blur_size", 
                label = "Result Blurriness",
                default_value = 1,
                min_value = 0,
                max_value = self._max_kernel_size,
                return_type = int,
                tooltip = "Amount of blurring applied to the result of the background subtraction.")
        
        self.pre_morph_size = \
        self.ctrl_spec.attach_slider(
                "pre_morph_size", 
                label = "(Gray) Shapeshift Region Size", 
                default_value = 1,
                min_value = 0,
                max_value = self._max_kernel_size,
                return_type = int,
                tooltip = ["Determines how large a region to look in when applying shapeshifting operations",
                           "For more detailed information about how shapeshifting works,",
                           "try searching for 'grayscale morphology'."])
        
        self.pre_morph_op = \
        self.ctrl_spec.attach_menu(
                "pre_morph_op", 
                label = "(Gray) Shapeshift Operation",
                default_value = "Fill Dark",
                option_label_value_list = [("Fill Dark", cv2.MORPH_CLOSE),
                                           ("Expand Bright", cv2.MORPH_DILATE),
                                           ("Fill Bright", cv2.MORPH_OPEN),
                                           ("Expand Dark", cv2.MORPH_ERODE)],
                tooltip = ["Controls the behavior of (gray) shapeshifting.",
                           "     Fill Dark -> Fills in dark regions with the brightest surrounding values.",
                           " Expand Bright -> Expand the brightest regions.",
                           "   Fill Bright -> Fill in bright regions with the darkest surrounding values.",
                           "   Expand Dark -> Expand the darkest regions."])
        
        self.pre_morph_shape = \
        self.ctrl_spec.attach_menu(
                "pre_morph_shape", 
                label = "(Gray) Shapeshift Region Shape",
                default_value = "Square",
                option_label_value_list = [("Square", cv2.MORPH_RECT),
                                           ("Circle", cv2.MORPH_ELLIPSE),
                                           ("Cross", cv2.MORPH_CROSS)],
                visible = True,
                tooltip = "Determines the shape of the region used in shapeshifting")
        
        self.summation_depth = \
        self.ctrl_spec.attach_slider(
                "summation_depth", 
                label = "Summation Depth", 
                default_value = 3,
                min_value = 0,
                max_value = self._max_deck_length,
                return_type = int,
                tooltip = ["Number of additional previous frames to add up before applying thresholding.",
                           "Can be used to help 'drown out' noise, since noise doesn't tend to add up",
                           "as consistently (as real frame differences) over time. Can also be used to",
                           "fill out shapes that tend to break apart or have holes in them. Note, when",
                           "summing up many frames, thresholding will need to be increased accordingly."])
        
        # .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  . Control Group 3 .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .
        
        self.ctrl_spec.new_control_group("Post-Threshold Controls")
        
        self.post_morph_size = \
        self.ctrl_spec.attach_slider(
                "post_morph_size", 
                label = "(Binary) Shapeshift Region Size", 
                default_value = 3,
                min_value = 0,
                max_value = self._max_kernel_size,
                return_type = int,
                tooltip = "See (Gray) Shapeshift Region Size. Operates on purely black or white pixels.")
        
        self.post_morph_op = \
        self.ctrl_spec.attach_menu(
                "post_morph_op", 
                label = "(Binary) Shapeshift Operation", 
                default_value = "Expand Bright",
                option_label_value_list = [("Fill Dark", cv2.MORPH_CLOSE),
                                           ("Expand Bright", cv2.MORPH_DILATE),
                                           ("Fill Bright", cv2.MORPH_OPEN),
                                           ("Expand Dark", cv2.MORPH_ERODE)],
                tooltip = ["See (Gray) Shapeshift Operation. Operates on purely black or white pixels.",
                           "In binary mode, shapeshifting has a more intuitive interpretation:",
                           "     Fill Dark -> Useful for filling in holes/broken parts of shapes.",
                           " Expand Bright -> Gives nicer shapes, which can improve detection consistency.",
                           "   Fill Bright -> Useful for separating shapes that blend together too much.",
                           "   Expand Dark -> Shrinks shapes. Can be used to offset the effects of summation."])
        
        self.post_morph_shape = \
        self.ctrl_spec.attach_menu(
                "post_morph_shape", 
                label = "(Binary) Shapeshift Region Shape", 
                default_value = "Square",
                option_label_value_list = [("Square", cv2.MORPH_RECT),
                                           ("Circle", cv2.MORPH_ELLIPSE),
                                           ("Cross", cv2.MORPH_CROSS)],
                visible = True,
                tooltip = "See (Gray) Shapeshift Region Shape. Operates on purely black or white pixels.")
        
        # .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  . Control Group 4 .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .
        
        self.ctrl_spec.new_control_group("Background Controls")
        
        self.capture_period_sec = \
        self.ctrl_spec.attach_slider(
                "capture_period_sec", 
                label = "Capture Period", 
                default_value = 3,
                min_value = 1,
                max_value = 300,
                return_type = int,
                zero_referenced = True,
                units = "seconds",
                tooltip = "Number of seconds to wait between updating the rolling background image.")
        
        self.new_capture_weighting = \
        self.ctrl_spec.attach_slider(
                "new_capture_weighting", 
                label = "New Capture Weighting", 
                default_value = 15/100,
                min_value = 0.01, max_value = 1.0, step_size = 1/100,
                return_type = float,
                zero_referenced = True,
                units = "percent",
                tooltip = ["Amount of (relative) weighting given to the most recent capture image", 
                           "when updating the background image."])
    
    # .................................................................................................................
    
    def set_output_wh(self):
        # OVERRIDING FROM PARENT CLASS
        self.output_wh = (self.output_w, self.output_h)
        
    # .................................................................................................................
    
    def reset(self):
        
        # Clear out frame decks, since we don't want to sum up frames across a reset
        self._setup_decks(reset_all = True)
        
        # Reset the rolling background image & timer so we start over
        self._rolling_bg_frame_float32 = None
        self._rbg_timer.reset_timer()
        
    # .................................................................................................................
    
    def setup(self, variables_changed_dict):
        
        # Pre-calculate derived settings
        self._downscale_wh = scale_factor_downscale(self.input_wh, self.downscale_factor)
        self._pre_blur_kernel = get_2d_kernel(self.pre_blur_size)
        self._post_blur_kernel = get_2d_kernel(self.post_blur_size)
        self._pre_morph_element = create_morphology_element(self.pre_morph_shape, self.pre_morph_size)
        self._post_morph_element = create_morphology_element(self.post_morph_shape, self.post_morph_size)
        
        # Update 'output' dimensions
        self.output_w, self.output_h = self._downscale_wh
        
        # Set up enablers
        self._enable_downscale = (self.downscale_factor < 1.0)
        self._enable_pre_blur = (self.pre_blur_size > 0)
        self._enable_post_blur = (self.post_blur_size > 0)
        self._enable_pre_morph = (self.pre_morph_size > 0)
        self._enable_summation = (self.summation_depth > 0)
        self._enable_threshold = (self.threshold > 0)
        self._enable_post_morph = (self.post_morph_size > 0)
        
        # Re-draw the masking image
        self._scaled_mask_image = create_mask_image(self._downscale_wh, self.mask_zone_list)
        mask_is_meaningful = (np.min(self._scaled_mask_image) == 0)
        self._enable_masking_optimized = (self.enable_masking and mask_is_meaningful)
        
        # Set up frame decks if needed
        self._sum_deck = self._setup_decks()
        if "downscale_factor" in variables_changed_dict.keys():
            self._update_decks()
        
        # Update capture timing & force an update to the rolling-background
        self._rbg_timer.set_trigger_period(seconds = self.capture_period_sec)
        self._apply_rolling_background_processing()
        
        return
    
    # .................................................................................................................
    
    def _setup_decks(self, reset_all = False):
        
        # Get the input frame size, so we can initialize decks with the right sizing
        scaled_width, scaled_height = scale_factor_downscale(self.input_wh, self.downscale_factor)
        gray_shape = (scaled_height, scaled_width)
        deck_length = 1 + self._max_deck_length 
        
        # Initialize the summation deck if needed
        summation_deck = self._sum_deck
        if self._sum_deck is None or reset_all:
            summation_deck = Frame_Deck_LIFO(deck_length)
            summation_deck.initialize_missing_from_shape(gray_shape)
        
        return summation_deck
    
    # .................................................................................................................
    
    def _update_decks(self):
        
        # For simplicity
        resize_kwargs = {"dsize": self._downscale_wh, "interpolation": self.downscale_interpolation}
        
        # Update summation frames
        for each_idx, each_frame in self._sum_deck.iterate_all():
            new_frame = cv2.resize(each_frame, **resize_kwargs)
            self._sum_deck.modify_one(each_idx, new_frame)
        
        return
                
    # .................................................................................................................
    
    def process_current_frame(self, frame):
        
        # Update the folling background image, if needed
        self._update_rolling_background(frame)
        
        # Apply same processing used on rolling-background frame, before subtraction
        frame = self._process_rolling_background_frame(frame)
        
        # Perform rolling-background subtraction
        frame = cv2.absdiff(frame, self._rolling_bg_frame_uint8)
        
        # Convert to grayscale
        frame = np.max(frame, axis = 2) if self.use_max_diff else cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Apply post-blurring
        if self._enable_post_blur:
            frame = cv2.blur(frame, self._post_blur_kernel)
        
        # Apply pre-threshold morphology
        if self._enable_pre_morph:
            frame = cv2.morphologyEx(frame, op = self.pre_morph_op, kernel = self._pre_morph_element)
        
        # Sum up frames
        if self._enable_summation:
            self._sum_deck.add(frame)
            frame = self._sum_deck.sum_from_deck(self.summation_depth)
        
        # Apply thresholding
        if self._enable_threshold:
            _, frame = cv2.threshold(frame, self.threshold, 255, cv2.THRESH_BINARY)
        
        # Apply post-threshold morphology
        if self._enable_post_morph:
            frame = cv2.morphologyEx(frame, op = self.post_morph_op, kernel = self._post_morph_element)
        
        # Apply masking
        if self._enable_masking_optimized:
            frame = cv2.bitwise_and(frame, self._scaled_mask_image)
        
        return frame
    
    # .................................................................................................................
    
    def process_background_frame(self, frame):
        # Rolling-background frame-processor doesn't use the actual background image data!
        return 0
    
    # .................................................................................................................
    
    def _process_rolling_background_frame(self, frame):
        
        ''' Function which applies shared processing for rolling-background + current frame data '''
        
        # Downscale if needed
        if self._enable_downscale:
            frame = cv2.resize(frame, dsize = self._downscale_wh, interpolation = self.downscale_interpolation)
        
        # Apply pre-blurring
        if self._enable_pre_blur:
            frame = cv2.blur(frame, self._pre_blur_kernel)
        
        return frame
    
    # .................................................................................................................
        
    def _update_rolling_background(self, frame):
        
        # Grab time reference so we can check if we've waited long enough to update the background
        _, current_epoch_ms, _ = self.get_time_info()
        need_to_update_rbg = self._rbg_timer.check_trigger(current_epoch_ms)
        
        # Bail if we don;'t need to update the rolling background
        if not need_to_update_rbg:
            return
        
        # Set up weights for clarity
        new_weight = self.new_capture_weighting
        prev_weight = 1.0 - new_weight
        bias_term = 0.0
        
        # Convert the incoming frame to a float so we can keep track of fractional values through the weighting
        frame_float32 = np.float32(frame)
        
        # Average existing background frame data with new frame
        try:
            self._rolling_bg_frame_float32 = cv2.addWeighted(self._rolling_bg_frame_float32,
                                                             prev_weight,
                                                             frame_float32,
                                                             new_weight,
                                                             bias_term)
        except:
            # Fails on first run, since we don't have a previous frame to average with!
            self._rolling_bg_frame_float32 = frame_float32
        
        # Convert to uint8 for use in foreground processing
        new_rbg_uint8 = np.uint8(np.round(self._rolling_bg_frame_float32))
        self._clean_rolling_bg_uint8 = new_rbg_uint8.copy()
        
        # Apply processing to clean background image, to avoid re-running on every frame
        self._apply_rolling_background_processing()
    
        return
    
    # .................................................................................................................
    
    def _apply_rolling_background_processing(self):
        
        ''' Helper function, used to update any pre-processing needed on the rolling background '''
        
        if self._clean_rolling_bg_uint8 is not None:
            self._rolling_bg_frame_uint8 = self._process_rolling_background_frame(self._clean_rolling_bg_uint8.copy())
        
        return
    
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
