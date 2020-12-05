#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Aug 18 11:45:38 2020

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

from local.configurables.core.detector.reference_detector import Reference_Detector, Pedestrian_Detection_Object


# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes


class Configurable(Reference_Detector):
    
    # .................................................................................................................
    
    def __init__(self, location_select_folder_path, camera_select, input_wh):
        
        # Inherit reference functionality
        super().__init__(location_select_folder_path, camera_select, input_wh, file_dunder = __file__)
        
        # Set up (hacky) flag used to confirm the preprocessed frame sizing on initial start up
        self._need_to_check_frame_size = True
        
        # Set up blob detection sizing (parent class should have already done this, but just in case...)
        Pedestrian_Detection_Object.set_frame_scaling(*input_wh)
        
        # Initialize the HOG detector on startup
        self._hog = cv2.HOGDescriptor()
        self._hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
        
        # Allocate storage for derived values
        self._window_size_tuple = (1, 1)
        self._padding_tuple = (0, 0)
        self._blurring_tuple = (0, 0)
        self._needs_blur = False
        self._hog_frame_wh = None
        self._needs_resize = False
        self._max_input_dimension = max(input_wh)
        self._width_detection_scaling = None
        self._height_detection_scaling = None
        
        # Allocate storage for detections on each frame
        self._detection_ref_dict = {}
        self._rejection_ref_dict = {}
        
        # .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  . Drawing Controls  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .
        
        self.ignore_zones_list = \
        self.ctrl_spec.attach_drawing(
                "ignore_zones_list",
                default_value = [[]],
                min_max_entities = None,
                min_max_points = (3, None),
                entity_type = "polygon",
                drawing_style = "zone")
        
        # .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  . Control Group 1 .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .
        
        self.ctrl_spec.new_control_group("Display Controls")
        
        self._show_outlines = \
        self.ctrl_spec.attach_toggle(
                "_show_outlines",
                label = "Show Outlines",
                default_value = True,
                tooltip = "Toggle the display of detection outlines.",
                save_with_config = False)
        
        self._show_rejections = \
        self.ctrl_spec.attach_toggle(
                "_show_rejections",
                label = "Show Rejections",
                default_value = True,
                tooltip = "Toggle the display of rejected detections (too small or too big).",
                save_with_config = False)
        
        # .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  . Control Group 2 .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .
        
        self.ctrl_spec.new_control_group("HOG Controls")
        
        self.hog_pre_blur = \
        self.ctrl_spec.attach_slider(
                "hog_pre_blur",
                label = "Pre-blur",
                default_value = 0,
                min_value = 0, max_value = 12,
                zero_referenced = True,
                return_type = int,
                units = "pixels",
                tooltip = ["If non-zero, applies blurring to the image (before scaling)",
                           "May help improve accuracy in cases where",
                           "image quality/video noise is a problem."])
        
        self.max_frame_dimension = \
        self.ctrl_spec.attach_slider(
                "max_frame_dimension",
                label = "Frame max dimension",
                default_value = 640,
                min_value = 220, max_value = 1280,
                zero_referenced = True,
                return_type = int,
                units = "pixels",
                tooltip = ["Scale of image that the HOG detector will actually run on.",
                           "Lower image sizes will speed up detection, but may not have",
                           "enough detail for the detector to properly detect people.",
                           "Fails for settings below 215px for some reason..."])
        
        self.hog_win_stride = \
        self.ctrl_spec.attach_slider(
                "hog_win_stride",
                label = "Window stride",
                default_value = 2,
                min_value = 1, max_value = 12,
                zero_referenced = True,
                return_type = int,
                units = "pixels",
                tooltip = ["Number of pixels between each HOG detection attempt",
                           "Higher values will speed up detection, but with the potential",
                           "to 'skip' over objects during detection"])
        
        self.hog_scale = \
        self.ctrl_spec.attach_slider(
                "hog_scale",
                label = "HOG scale",
                default_value = 1.02,
                min_value = 1.00, max_value = 1.5, step_size = 1/1000,
                return_type = float,
                units = "normalized",
                tooltip = ["Controls 'pyramid scaling' used by HOG detector. Smaller values will",
                           "result in more image scales used during detection and potentially"
                           "better/more detection results, at the expense of slower detection speed.",
                           "At the lowest value, pyramid scaling is disabled."])
        
        self.hog_padding = \
        self.ctrl_spec.attach_slider(
                "hog_padding",
                label = "Window padding",
                default_value = 3,
                min_value = 0, max_value = 12,
                zero_referenced = True,
                return_type = int,
                units = "pixels",
                tooltip = ["Padding applied to sliding detection windows. May improve detection results",
                           "by providing more 'context' to each of the sliding windows."])
        
        self.hog_hit_threshold = \
        self.ctrl_spec.attach_slider(
                "hog_hit_threshold",
                label = "Hit threshold",
                default_value = 0,
                min_value = 0.0, max_value = 5.0, step_size = 1/10,
                zero_referenced = True,
                return_type = float,
                units = "normalized",
                tooltip = ["Poorly documented control! Helps to exclude low-confidence detections",
                           "A value of zero should be fine in many cases",
                           "Only consider increasing if there are too many (obvious) false-positives"])
    
        self.hog_weight_threshold = \
        self.ctrl_spec.attach_slider(
                "hog_weight_threshold",
                label = "Weight threshold",
                default_value = 0.35,
                min_value = 0.0, max_value = 1.0, step_size = 1/100,
                zero_referenced = True,
                return_type = float,
                units = "normalized",
                tooltip = ["Sets the minimum required detection weight/confidence.",
                           "Lower weight detections will be rejected based on this setting."])
    
    # .................................................................................................................
    
    def reset(self):
        # Clear out all stored detections, since a reset may cause jumps in time/break detection continuity
        self._detection_ref_dict = {}
        self._rejection_ref_dict = {}
        
    # .................................................................................................................
    
    def setup(self, variables_changed_dict):
        
        # Pre-calculate tuple controls
        even_blur = int(2 * self.hog_pre_blur)
        even_stride = int(2 * self.hog_win_stride)
        even_pad = int(2 * self.hog_padding)
        self._blurring_tuple = (even_blur, even_blur)
        self._window_size_tuple = (even_stride, even_stride)
        self._padding_tuple = (even_pad, even_pad)
        
        # Decide if we even need to blur
        self._needs_blur = (self.hog_pre_blur > 0)
        
        # Figure out scaling if needed
        self._needs_resize, self._hog_frame_wh = max_frame_scale(self.input_wh, self.max_frame_dimension)
        
        # Reset detection scaling so that co-ordinates are properly normalized on detection
        Pedestrian_Detection_Object.set_frame_scaling(*self._hog_frame_wh)
        self._width_detection_scaling = (self._hog_frame_wh[0] - 1)
        self._height_detection_scaling = (self._hog_frame_wh[1] - 1)
        
    # .................................................................................................................
    
    def detections_from_frames(self, binary_frame_1ch, preprocessed_frame):
        
        # Hacky check to ensure proper input sizing
        if self._need_to_check_frame_size:
            self._fix_input_wh(preprocessed_frame)
        
        # Apply blurring if needed
        frame_to_process = preprocessed_frame
        if self._needs_blur:
            frame_to_process = cv2.blur(frame_to_process, self._blurring_tuple)
        
        # Apply downscaling if needed
        if self._needs_resize:
            frame_to_process = cv2.resize(frame_to_process,
                                          dsize = self._hog_frame_wh,
                                          interpolation = cv2.INTER_NEAREST)
        
        # Apply HOG detector to the input image
        rects_list, weights_list = self._hog.detectMultiScale(frame_to_process,
                                                              hitThreshold = self.hog_hit_threshold,
                                                              winStride = self._window_size_tuple,
                                                              padding = self._padding_tuple,
                                                              scale = self.hog_scale)
        
        # Fill out bounding box list
        new_detection_ref_dict = {}
        reject_ref_dict = {}
        for each_idx, (each_weight, (x,y,w,h)) in enumerate(zip(weights_list, rects_list)):
            
            # Get bounding box corner co-ordinates
            tl_x = x
            tl_y = y
            br_x = (x + w)
            br_y = (y + h)
            
            # Create a 'fake' rectangular contour so we can report it as a detected object contour
            rect_contour = np.float32([(tl_x, tl_y), (br_x, tl_y), (br_x, br_y), (tl_x, br_y)])
            new_detection = Pedestrian_Detection_Object(rect_contour, preprocessed_frame)
            
            # Check that the weight is ok and the bounding box is not inside an ignore zone before adding to list
            below_weight_threshold = (each_weight < self.hog_weight_threshold)
            if below_weight_threshold or new_detection.in_zones(self.ignore_zones_list):
                reject_ref_dict[each_idx] = new_detection
            else:
                new_detection_ref_dict[each_idx] = new_detection
                
        # Store the detections (mostly for analysis/debugging)
        self._detection_ref_dict = new_detection_ref_dict
        self._rejection_ref_dict = reject_ref_dict
        
        return new_detection_ref_dict
    
    # .................................................................................................................
    
    def _fix_input_wh(self, preprocessed_frame):
        
        '''
        Function used to adjust the input width/height assumed by the detector
        By default, detector uses binary frame w/h values (from previous stage) as the input wh,
        by for HOG specifically, we need the preprocessed frame size, since we need color data!
        '''
        
        # Get preprocessed (i.e. target) frame sizing
        frame_height, frame_width = preprocessed_frame.shape[0:2]
        
        # Compare given input width/height to target size
        input_width, input_height = self.input_wh
        wrong_width = (frame_width != input_width)
        wrong_height = (frame_height != frame_height)
        
        # Update internal input frame sizing, and force 'setup' update again to account for changes
        if wrong_width or wrong_height:
            self.input_wh = (frame_width, frame_height)
            self.setup({})
        
        # Prevent future frame sizing checks, since it shouldn't change
        self._need_to_check_frame_size = False
        
        return
    
    # .................................................................................................................
    # .................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

# .....................................................................................................................

def max_frame_scale(frame_wh, max_dimension_px):

    # First figure out how much we would need to independently scale sides to acheive max dimension length
    frame_width, frame_height = frame_wh
    width_rescale_factor = max_dimension_px / frame_width
    height_rescale_factor = max_dimension_px / frame_height
    
    # Now pick the smaller of the two scaling factors and calculate the resulting scaled size
    shared_rescale_factor = min(width_rescale_factor, height_rescale_factor)
    rescale_width = int(round(shared_rescale_factor * frame_width))
    rescale_height = int(round(shared_rescale_factor * frame_height))
    rescale_wh = (rescale_width, rescale_height)

    # Finally, decide if scaling was actually applied!
    needs_scaling = (rescale_wh != frame_wh)
    
    return needs_scaling, rescale_wh

# .....................................................................................................................

def draw_detections(stage_outputs, configurable_ref,
                    detection_color = (255, 255, 0), reject_color = (0, 0, 255)):
    
    # Grab a copy of the color image that we can draw on
    display_frame = stage_outputs["preprocessor"]["preprocessed_frame"]
    detection_frame = display_frame.copy()
    
    # Get display controls
    show_outlines = configurable_ref._show_outlines
    show_rejections = configurable_ref._show_rejections
    
    # Grab the detection dictionaries so we can draw with it!
    detections_list = configurable_ref._detection_ref_dict.values()
    rejections_list = configurable_ref._rejection_ref_dict.values() if show_rejections else []
    
    # Record frame sizing so we can draw normalized co-ordinate locations
    frame_h, frame_w = detection_frame.shape[0:2]
    frame_wh = np.array((frame_w - 1, frame_h - 1))
    
    for list_idx, each_list in enumerate((rejections_list, detections_list)):
        
        is_reject = (list_idx == 0)
        for each_blob in each_list:
            
            # Change color based on validity of detection
            blob_color = reject_color if is_reject else detection_color
            
            # Draw the blob bounding boxes (for detections only)
            if show_outlines:
                # Draw the blob outline
                blob_hull = np.int32(np.round(each_blob.hull_array * frame_wh))
                cv2.polylines(detection_frame, [blob_hull], True, blob_color, 1, cv2.LINE_AA)
            
    return detection_frame

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Demo
    
if __name__ == "__main__":
    pass
    

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap



