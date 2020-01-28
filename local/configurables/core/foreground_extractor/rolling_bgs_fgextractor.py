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

from functools import partial

from local.configurables.core.foreground_extractor.reference_fgextractor import Reference_FG_Extractor
from local.configurables.core.foreground_extractor._helper_functions import blank_binary_frame_from_input_wh
from local.configurables.core.foreground_extractor._helper_functions import partial_grayscale, partial_norm_grayscale
from local.configurables.core.foreground_extractor._helper_functions import partial_fast_blur
from local.configurables.core.foreground_extractor._helper_functions import partial_morphology
from local.configurables.core.foreground_extractor._helper_functions import partial_resize_by_dimensions
from local.configurables.core.foreground_extractor._helper_functions import partial_self_sum, partial_threshold
from local.configurables.core.foreground_extractor._helper_functions import partial_mask_image
from local.configurables.core.foreground_extractor._helper_functions import Frame_Deck_LIFO, calculate_scaled_wh


# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes

class FG_Extractor_Stage(Reference_FG_Extractor):
    
    # .................................................................................................................
    
    def __init__(self, input_wh):
        
        # Inherit reference functionality
        super().__init__(input_wh, file_dunder = __file__)
        
        # Allocate space for altered frame sizing
        self.output_w = None
        self.output_h = None
        
        # Allocate storage for background frame data
        self.current_background = None
        self._rolling_bg_frame_float32 = None
        self._rolling_bg_frame_uint8 = None
        self._clean_rolling_bg_uint8 = None
        self._next_rbg_update_time_ms = -1
        self._capture_period_ms = None
        
        # Allocate space for frame decks
        self._sum_deck = None
        self._max_deck_length = 30
        self._max_kernel_size = 15
        
        # Allocate space for dervied variables
        self._proc_func_list = None
        self._rbg_func_list = None
        self._scaled_mask_image = None
        
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
        
        self.use_norm_diff = \
        self.ctrl_spec.attach_toggle(
                "use_norm_diff", 
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
                default_value = 5,
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
                default_value = 25/100,
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
        self._sum_deck = None
        self._setup_decks(self.downscale_factor)
        self._rolling_bg_frame_float32 = None
        self._next_rbg_update_time_ms = -1
        
    # .................................................................................................................
    
    def setup(self, variables_changed_dict):
        
        # Set up enablers
        self._enable_downscale = (self.downscale_factor < 1.0)
        self._enable_pre_blur = (self.pre_blur_size > 0)
        self._enable_post_blur = (self.post_blur_size > 0)
        self._enable_pre_morph = (self.pre_morph_size > 0)
        self._enable_summation = (self.summation_depth > 0)
        self._enable_threshold = (self.threshold > 0)
        self._enable_post_morph = (self.post_morph_size > 0)
        
        # Update capture timing
        self._capture_period_ms = int(round(1000 * self.capture_period_sec))
        
        # Re-draw the masking image
        self._scaled_mask_image = self._create_mask_image()
        mask_is_meaningful = (np.min(self._scaled_mask_image) == 0)
        self._enable_masking_optimized = (self.enable_masking and mask_is_meaningful)
        
        # Set up frame decks if needed
        self._setup_decks(self.downscale_factor)
        
        # Build the processing function list
        self._rbg_func_list, self._proc_func_list, (self.output_w, self.output_h) = self._build_foreground_extractor()
        
        # Update the background image if possible
        self._apply_rollbg_fg_extraction()
        
    # .................................................................................................................
    
    def apply_fg_extraction(self, frame):
        
        # Update the rolling background as needed
        self._update_rolling_background(frame)
        
        try:
            
            # Run through all the foreground processing functions in the list!
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
        # No (preprocessed) background processing        
        return None
    
    # .................................................................................................................
    
    def _setup_decks(self, scaling_factor = 1.0):
        
        # Get the input frame size, so we can initialize decks with the right sizing
        _, (scaled_width, scaled_height) = calculate_scaled_wh(self.input_wh, scaling_factor)
        input_shape = (scaled_height, scaled_width, 3)
        gray_shape = input_shape[0:2]
        deck_length = 1 + self._max_deck_length 
        
        # Initialize the summation deck if needed
        if self._sum_deck is None:
            summation_deck = Frame_Deck_LIFO(deck_length)
            summation_deck.initialize_missing_from_shape(gray_shape)
            self._sum_deck = summation_deck
        
        # Resize the deck contents if the scaling factor changes
        resize_func = partial_resize_by_dimensions(scaled_width, scaled_height, cv2.INTER_NEAREST)
        self._sum_deck.modify_all(resize_func)
        
    # .................................................................................................................
        
    def _update_rolling_background(self, frame):
        
        # Grab time reference so we can check if we've waited long enough to update the background
        __, current_epoch_ms, _ = self.get_time_info()
        
        # Bail if we don't need to update the background
        need_to_update_rolling_bg = (current_epoch_ms > self._next_rbg_update_time_ms)
        if not need_to_update_rolling_bg:
            return
            
        # If we get here we're updating the background so setup the next update time
        self._next_rbg_update_time_ms = current_epoch_ms + self._capture_period_ms
        
        # Set up weights for clarity
        new_weight = self.new_capture_weighting
        prev_weight = 1.0 - new_weight
        bias_term = 0.0
        
        # Convert the incoming frame to a float so we can keep track of fractional values through the weighting
        frame_float32 = np.float32(frame)
        
        # Average existing background frame data with new frame
        try:
            self._rolling_bg_frame_float32 = cv2.addWeighted(self._rolling_bg_frame_float32, prev_weight,
                                                             frame_float32, new_weight, bias_term)
        except:
            # Fails on first run, since we don't have a previous frame to average with!
            self._rolling_bg_frame_float32 = frame_float32
        
        # Convert to uint8 for use in foreground processing
        new_rbg_uint8 = np.uint8(np.round(self._rolling_bg_frame_float32))
        self._clean_rolling_bg_uint8 = new_rbg_uint8.copy()
        
        # Update the frame data used for foreground processing
        self._apply_rollbg_fg_extraction()
            
    # .................................................................................................................
    
    def _apply_rollbg_fg_extraction(self):
        
        ''' 
        Function for converting the clean rolling background to the actual frame data 
        used in background subtraction, which may include scaling/blurring
        '''
        
        # If this gets called without a clean background, just do nothing (normal to happen on start-up)
        if self._clean_rolling_bg_uint8 is None:
            return
        
        # Grab a copy of the clean image to start with
        new_rbg_uint8 = self._clean_rolling_bg_uint8.copy()
        
        # Apply pre-processing to the new rolling bg frame before storing it for use
        for each_func in self._rbg_func_list:
            new_rbg_uint8 = each_func(new_rbg_uint8)
            
        # Store the processed rolling background for actual use!
        self._rolling_bg_frame_uint8 = new_rbg_uint8
                
    # .................................................................................................................
    
    def _build_foreground_extractor(self):
        
        # For disabling processing steps
        passthru = lambda frame: frame
        
        # Downscale/upscale functions
        _, downscale_wh = calculate_scaled_wh(self.input_wh, self.downscale_factor)
        downscale_func = partial_resize_by_dimensions(*downscale_wh, self.downscale_interpolation)
        
        # Pre-blurring 
        pre_blur_func = partial_fast_blur(self.pre_blur_size)

        # Rolling background difference/subtraction
        bg_diff_func = partial_rbg_diff(self)
            
        # Grayscale
        gray_func = partial_norm_grayscale() if self.use_norm_diff else partial_grayscale()
        
        # Post-blurring
        post_blur_func = partial_fast_blur(self.post_blur_size)
        
        # Pre-morph
        pre_morph_func = partial_morphology(self.pre_morph_size, 
                                            self.pre_morph_op,
                                            self.pre_morph_shape)
        
        # Sum frames
        sum_func = partial_self_sum(self._sum_deck, self.summation_depth)        
        
        # Threshold
        thresh_func = partial_threshold(self.threshold)
        
        # Post-morph
        post_morph_func = partial_morphology(self.post_morph_size, 
                                             self.post_morph_op,
                                             self.post_morph_shape)
        
        # Masking
        mask_func = partial_mask_image(self._scaled_mask_image)
        
        # Create function call list
        bg_func_list = [downscale_func if self._enable_downscale else passthru,
                        pre_blur_func if self._enable_pre_blur else passthru]
        
        # Create function call list
        func_list = bg_func_list \
                    + [bg_diff_func,
                       gray_func,
                       post_blur_func if self._enable_post_blur else passthru,
                       pre_morph_func if self._enable_pre_morph else passthru,
                       sum_func if self._enable_summation else passthru,
                       thresh_func if self._enable_threshold else passthru,
                       post_morph_func if self._enable_post_morph else passthru,
                       mask_func if self._enable_masking_optimized else passthru]
                    
        return bg_func_list, func_list, downscale_wh
    
    # .................................................................................................................
    
    def _create_mask_image(self):
        
        # Get the input frame size, so we can create a mask with the right size
        _, (scaled_width, scaled_height) = calculate_scaled_wh(self.input_wh, self.downscale_factor)
        frame_shape = (scaled_height, scaled_width)
        
        # Calculate the scaling factor needed to pixelize mask point locations
        frame_scaling = np.float32(((scaled_width - 1), (scaled_height - 1)))
        
        # Create an empty (bright) mask image (i.e. fully passes everything through)
        mask_image = np.full(frame_shape, 255, dtype=np.uint8)
        mask_fill = 0
        mask_line_type = cv2.LINE_8
        
        # Draw masked zones to black-out regions
        for each_zone in self.mask_zone_list:
            
            # Don't try to draw anything when given empty entities!
            if each_zone == []:
                continue
            
            # Draw a filled (dark) polygon for each masking zone
            each_zone_array = np.float32(each_zone)
            mask_list_px = np.int32(np.round(each_zone_array * frame_scaling))
            cv2.fillPoly(mask_image, [mask_list_px], mask_fill, mask_line_type)
            cv2.polylines(mask_image, [mask_list_px], True, mask_fill, 1, mask_line_type)
        
        return mask_image
        
    # .................................................................................................................
    # .................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

# .....................................................................................................................
    
def partial_rbg_diff(object_ref):
    
    # Create function which takes the difference between the current frame and the rolling background frame
    def _rbg_absdiff(frame, obj_ref):
        
        # Use the rolling background frame, which updates over time
        return cv2.absdiff(frame, obj_ref._rolling_bg_frame_uint8)
    
    # Set up partial function ahead of time for convenience
    rbg_diff_func = partial(_rbg_absdiff, obj_ref = object_ref)
    
    return rbg_diff_func

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Demo
    
if __name__ == "__main__":
    pass
    

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap
