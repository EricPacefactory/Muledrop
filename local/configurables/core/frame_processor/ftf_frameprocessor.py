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
from local.configurables.core.frame_processor._helper_functions import partial_grayscale, partial_norm_grayscale
from local.configurables.core.frame_processor._helper_functions import partial_fast_blur
from local.configurables.core.frame_processor._helper_functions import partial_morphology, partial_resize_by_dimensions
from local.configurables.core.frame_processor._helper_functions import partial_self_sum, partial_threshold
from local.configurables.core.frame_processor._helper_functions import partial_mask_image
from local.configurables.core.frame_processor._helper_functions import Frame_Deck_LIFO, calculate_scaled_wh


# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes

class Frame_Processor_Stage(Reference_Frame_Processor):
    
    # .................................................................................................................
    
    def __init__(self, input_wh):
        
        # Inherit reference functionality
        super().__init__(input_wh, file_dunder = __file__)
        
        # Allocate space for altered frame sizing
        self.output_w = None
        self.output_h = None
        
        # Allocate space for frame decks
        self._diff_deck = None
        self._sum_deck = None
        self._max_deck_length = 30
        self._max_kernel_size = 15
        
        # Allocate space for dervied variables
        self._proc_func_list = None
        self._scaled_mask_image = None
        self.mask_zone_list = []
        
        # llocate storage for variables used to remove processing functions (to improve performance)
        self._enable_downscale = False
        self._enable_blur = False
        self._enable_difference = False
        self._enable_pre_morph = False
        self._enable_summation = False
        self._enable_threshold = False
        self._enable_post_morph = False
        
        # .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  . Control Group 1 .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .
        
        mg = self.controls_manager.new_control_group("General Controls")
        
        self._show_outlines = \
        mg.attach_toggle("_show_outlines",
                         label = "Show Outlines",
                         default_value = True,
                         tooltip = "Overlay outlines of binary shapes on the input color image. Requires thresholding!")
        
        self.downscale_factor = \
        mg.attach_slider("downscale_factor", 
                         label = "Downscaling", 
                         default_value = 0.50,
                         min_value = 0.1,
                         max_value = 1.0,
                         step_size = 1/100,
                         return_type = float,
                         zero_referenced = True,
                         tooltip = "Perform frame processing on a reduced frame size")
        
        self.downscale_interpolation = \
        mg.attach_menu("downscale_interpolation", 
                       label = "Downscaling Interpolation", 
                       default_value = "Nearest",
                       option_label_value_list = [("Nearest", cv2.INTER_NEAREST),
                                                  ("Bilinear", cv2.INTER_LINEAR),
                                                  ("Cubic", cv2.INTER_CUBIC)],
                       tooltip = "Set the interpolation style for pixels sampled at fractional indices")
        
        self.threshold = \
        mg.attach_slider("threshold", 
                         label = "Threshold", 
                         default_value = 0,
                         min_value = 0,
                         max_value = 255,
                         return_type = int,
                         tooltip = ["Thresholding converts (grayscale) frame differences to black and white images.",
                                    "Differences that are above the threshold are converted to white pixels,",
                                    "differences below the threshold will be shown as black pixels.",
                                    "Thresholding is applied after:",
                                    "downscaling, blurring, frame-differencing, (gray) gap fill and summation."])
        
        self.use_norm_diff = \
        mg.attach_toggle("use_norm_diff", 
                         label = "Use Maximum Difference", 
                         default_value = False,
                         tooltip = ["Enabling this setting means that the output of the frame difference ",
                                    "calculation will be the maximum difference among the RGB channels. When",
                                    "disabled, the output will be a grayscale average of the RGB channels.",
                                    "Using the maximum will result in a more sensitive output, but",
                                    "it runs significantly slower!"])
        
        self.enable_masking = \
        mg.attach_toggle("enable_masking", 
                         label = "Enable Masking", 
                         default_value = True,
                         tooltip = "Enable or disable masking")
        
        # .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  . Control Group 2 .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .
        
        ag = self.controls_manager.new_control_group("Pre-Threshold Controls")
        
        self.blur_size = \
        ag.attach_slider("blur_size", 
                         label = "Blurriness", 
                         default_value = 0,
                         min_value = 0,
                         max_value = self._max_kernel_size,
                         return_type = int,
                         tooltip = ["Amount of blurring to apply to a frame before calculating frame differences.",
                                    "Helps to reduce errors due to video noise/artifacting.",
                                    "For more information, try searching for 'box blur'."])
        
        self.difference_depth = \
        ag.attach_slider("difference_depth", 
                         label = "Difference Depth", 
                         default_value = 0,
                         min_value = 0,
                         max_value = self._max_deck_length,
                         return_type = int,
                         tooltip = ["When performing frame differences, this number determines how far back",
                                    "to go when selecting a frame for differencing. For example,",
                                    "a depth of 1 means to take the difference between the current frame",
                                    "and 1 frame ago (i.e. the previous frame). A depth of 5 means",
                                    "to take the difference of the current frame and 5 frames ago."])
        
        self.pre_morph_size = \
        ag.attach_slider("pre_morph_size", 
                         label = "(Gray) Shapeshift Region Size", 
                         default_value = 0,
                         min_value = 0,
                         max_value = self._max_kernel_size,
                         return_type = int,
                         tooltip = ["Determines how large a region to look in when applying shapeshifting operations",
                                    "For more detailed information about how shapeshifting works,",
                                    "try searching for 'grayscale morphology'."])
        
        self.pre_morph_op = \
        ag.attach_menu("pre_morph_op", 
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
                                  "   Exapnd Dark -> Expand the darkest regions."])
        
        self.pre_morph_shape = \
        ag.attach_menu("pre_morph_shape", 
                       label = "(Gray) Shapeshift Region Shape",
                       default_value = "Square",
                       option_label_value_list = [("Square", cv2.MORPH_RECT),
                                                  ("Circle", cv2.MORPH_ELLIPSE),
                                                  ("Cross", cv2.MORPH_CROSS)],
                       visible = True,
                       tooltip = "Determines the shape of the region used in shapeshifting")
        
        self.summation_depth = \
        ag.attach_slider("summation_depth", 
                         label = "Summation Depth", 
                         default_value = 0,
                         min_value = 0,
                         max_value = self._max_deck_length,
                         return_type = int,
                         tooltip = ["Number of additional previous frames to add up before applying thresholding.",
                                    "Can be used to help 'drown out' noise, since noise doesn't tend to add up",
                                    "as consistently (as real frame differences) over time. Can also be used to",
                                    "fill out shapes that tend to break apart or have holes in them. Note, when",
                                    "summing up many frames, thresholding will need to be increased accordingly."])
        
        # .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  . Control Group 3 .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .
        
        pg = self.controls_manager.new_control_group("Post-Threshold Controls")
        
        self.post_morph_size = \
        pg.attach_slider("post_morph_size", 
                         label = "(Binary) Shapeshift Region Size", 
                         default_value = 0,
                         min_value = 0,
                         max_value = self._max_kernel_size,
                         return_type = int,
                         tooltip = "See (Gray) Shapeshift Region Size. Operates on purely black or white pixels.")
        
        self.post_morph_op = \
        pg.attach_menu("post_morph_op", 
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
        pg.attach_menu("post_morph_shape", 
                       label = "(Binary) Shapeshift Region Shape", 
                       default_value = "Square",
                       option_label_value_list = [("Square", cv2.MORPH_RECT),
                                                  ("Circle", cv2.MORPH_ELLIPSE),
                                                  ("Cross", cv2.MORPH_CROSS)],
                       visible = True,
                       tooltip = "See (Gray) Shapeshift Region Shape. Operates on purely black or white pixels.")
        
    # .................................................................................................................
    
    def set_output_wh(self):
        # OVERRIDING FROM PARENT CLASS
        self.output_wh = (self.output_w, self.output_h)
        
    # .................................................................................................................
    
    def reset(self):
        
        # Clear out frame decks, since we don't want to sum up frames across a reset
        self._diff_deck, self._sum_deck = self._setup_decks(reset_all = True)
        
    # .................................................................................................................
    
    def setup(self, variables_changed_dict):
        
        # Set up enablers
        self._enable_downscale = (self.downscale_factor < 1.0)
        self._enable_blur = (self.blur_size > 0)
        self._enable_difference = (self.difference_depth > 0)
        self._enable_pre_morph = (self.pre_morph_size > 0)
        self._enable_summation = (self.summation_depth > 0)
        self._enable_threshold = (self.threshold > 0)
        self._enable_post_morph = (self.post_morph_size > 0)        
        
        # Re-draw the masking image
        self._scaled_mask_image = self._create_mask_image()
        
        # Set up frame decks if needed
        self._diff_deck, self._sum_deck = self._setup_decks()
        
        # Build the processing function list and update the output sizing!
        self._proc_func_list, (self.output_w, self.output_h) = self._build_frame_processor()
        
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
    
    def _setup_decks(self, reset_all = False):
        
        # Get the input frame size, so we can initialize decks with the right sizing
        _, (scaled_width, scaled_height) = calculate_scaled_wh(self.input_wh, self.downscale_factor)
        input_shape = (scaled_height, scaled_width, 3)
        gray_shape = input_shape[0:2]
        deck_length = 1 + self._max_deck_length 
        
        # Set up the difference deck if needed
        difference_deck = self._diff_deck
        if self._diff_deck is None or reset_all:
            difference_deck = Frame_Deck_LIFO(deck_length)
            difference_deck.initialize_missing_from_shape(input_shape)
        
        # Initialize the summation deck if needed
        summation_deck = self._sum_deck
        if self._sum_deck is None or reset_all:
            summation_deck = Frame_Deck_LIFO(deck_length)
            summation_deck.initialize_missing_from_shape(gray_shape)
        
        # Resize the deck contents if the scaling factor changes
        resize_func = partial_resize_by_dimensions(scaled_width, scaled_height, cv2.INTER_NEAREST)
        difference_deck.modify_all(resize_func)
        summation_deck.modify_all(resize_func)
        
        return difference_deck, summation_deck
    
    # .................................................................................................................
    
    def _build_frame_processor(self):
        
        # For disabling processing steps
        passthru = lambda frame: frame
        
        # Downscale/upscale the image
        _, downscale_wh = calculate_scaled_wh(self.input_wh, self.downscale_factor)
        downscale_func = partial_resize_by_dimensions(*downscale_wh, self.downscale_interpolation)
        
        # Blur the image
        blur_func = partial_fast_blur(self.blur_size)
        
        # Self diff
        self_diff_func = partial_self_diff(self._diff_deck, 
                                           self.difference_depth)
            
        # Grayscale 
        gray_func = partial_norm_grayscale() if self.use_norm_diff else partial_grayscale()
        
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
        func_list = [downscale_func if self._enable_downscale else passthru,
                     blur_func if self._enable_blur else passthru,
                     self_diff_func if self._enable_difference else passthru,
                     gray_func,
                     pre_morph_func if self._enable_pre_morph else passthru,
                     sum_func if self._enable_summation else passthru,
                     thresh_func if self._enable_threshold else passthru,
                     post_morph_func if self._enable_post_morph else passthru,
                     mask_func if self.enable_masking else passthru]
        
        return func_list, downscale_wh
        
    # .................................................................................................................
    
    def _create_mask_image(self):
        
        # Get the input frame size, so we can create a mask with the right size
        _, (scaled_width, scaled_height) = calculate_scaled_wh(self.input_wh, self.downscale_factor)
        frame_shape = (scaled_height, scaled_width)
        
        # Calculate the scaling factor needed to pixelize mask point locations
        frame_scaling = np.float32(((scaled_width - 1), (scaled_height - 1)))
        
        # Create an empty mask image (i.e. fully passes everything through)
        mask_image = np.full(frame_shape, 255, dtype=np.uint8)
        mask_fill = 0
        mask_line_type = cv2.LINE_8
        
        # Draw masked zones to black-out regions
        for each_zone in self.mask_zone_list:
            
            each_zone_array = np.float32(each_zone)
            mask_list_px = np.int32(np.round(each_zone_array * frame_scaling))
            cv2.fillPoly(mask_image, [mask_list_px], mask_fill, mask_line_type)
        
        return mask_image
    
    # .................................................................................................................
    # .................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

# .....................................................................................................................
    
def partial_self_diff(deck_ref, backward_index):
    
    # Create function which loads up the frame deck then reads a previous frame from it to apply absdiff
    def _update_deck_absdiff(frame, difference_index, frame_deck):
        
        # Update frame deck, then grab a previous frame for absdiff
        prev_frame = frame_deck.add_and_read_newest(frame, difference_index)  
        
        return cv2.absdiff(frame, prev_frame)
    
    # Set up partial function ahead of time for convenience
    self_diff_func = partial(_update_deck_absdiff, 
                             difference_index = backward_index,
                             frame_deck = deck_ref)
    
    return self_diff_func

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Demo
    
if __name__ == "__main__":
    
    example = Frame_Processor_Stage((500,500))
    print("", "Initial configuration:", example, sep="\n")
    example.reconfigure(setup_data_dict = {"threshold": 90, "blur_size": 77})
    print("", "After reconfiguration:", example, sep="\n")
    

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap

