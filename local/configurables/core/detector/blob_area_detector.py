#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Jul 10 17:03:17 2020

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

from local.configurables.core.detector.reference_detector import Reference_Detector, Unclassified_Detection_Object


# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes


class Configurable(Reference_Detector):
    
    # .................................................................................................................
    
    def __init__(self, location_select_folder_path, camera_select, input_wh):
        
        # Inherit reference functionality
        super().__init__(location_select_folder_path, camera_select, input_wh, file_dunder = __file__)
        
        # Set up blob detection sizing (parent class should have already done this, but just in case...)
        Unclassified_Detection_Object.set_frame_scaling(*input_wh)
        
        # Pre-calculate the frame area, to use for normalizing blob areas
        self._frame_area_px = np.float32(np.product(input_wh))
        
        # Allocate storage for 'real' min/max area values (after undoing config scaling)
        self._min_area_norm = None
        self._max_area_norm = None
        
        # Allocate storage for detections on each frame
        self._detection_ref_dict = {}
        self._rejection_ref_dict = {}
        
        # Allocate storage for configuration visualization variables
        self._x_follower_size_px = 0
        self._y_follower_size_px = 0
        
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
                default_value = False,
                tooltip = "Toggle the display of detection outlines.",
                save_with_config = False)
        
        self._show_bounding_circles = \
        self.ctrl_spec.attach_toggle(
                "_show_bounding_circles",
                label = "Show Bounding Circles",
                default_value = True,
                tooltip = "Toggle the display of detection area as a circle.",
                save_with_config = False)
        
        self._show_rejections = \
        self.ctrl_spec.attach_toggle(
                "_show_rejections",
                label = "Show Rejections",
                default_value = True,
                tooltip = "Toggle the display of rejected detections (too small or too big).",
                save_with_config = False)
        
        self._show_minimum_follower = \
        self.ctrl_spec.attach_toggle(
                "_show_minimum_follower",
                label = "Show Minimum Detection Size",
                default_value = True,
                tooltip = "Toggle the display of minimum detection size indicator.",
                save_with_config = False)
        
        self._show_maximum_follower = \
        self.ctrl_spec.attach_toggle(
                "_show_maximum_follower",
                label = "Show Maximum Detection Size",
                default_value = True,
                tooltip = "Toggle the display of maximum detection size indicator.",
                save_with_config = False)
        
        # .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  . Control Group 2 .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .
        
        self.ctrl_spec.new_control_group("Size Controls")
        
        self.min_area_norm_sqrt = \
        self.ctrl_spec.attach_slider(
                "min_area_norm_sqrt",
                label = "Minimum Area",
                default_value = 0.10,
                min_value = 0.00, max_value = 1.00, step_size = 1/1000,
                return_type = float,
                units = "normalized",
                tooltip = ["Minimum area required for a detection to be considered valid",
                           "Note that this value is scaled (via sqrt) to provide more a more intuitive range",
                           "and is interpretted relative to the frame area."])
        
        self.max_area_norm_sqrt = \
        self.ctrl_spec.attach_slider(
                "max_area_norm_sqrt",
                label = "Maximum Area",
                default_value = 0.750,
                min_value = 0.00, max_value = 2.00, step_size = 1/1000,
                return_type = float,
                units = "normalized",
                tooltip = ["Maximum area allowed for a detection to be considered valid",
                           "Note that this value is scaled (via sqrt) to provide more a more intuitive range",
                           "and is interpretted relative to the frame area"])
    
    # .................................................................................................................
    
    def reset(self):
        # Clear out all stored detections, since a reset may cause jumps in time/break detection continuity
        self._detection_ref_dict = {}
        self._rejection_ref_dict = {}
        
    # .................................................................................................................
    
    def setup(self, variables_changed_dict):
        
        # Undo square root scaling (used to give more intuitive config controls) to get 'real' min/max areas
        self._min_area_norm = np.square(self.min_area_norm_sqrt)
        self._max_area_norm = np.square(self.max_area_norm_sqrt)
        
    # .................................................................................................................
    
    def detections_from_frames(self, binary_frame_1ch, preprocessed_frame):
        
        # Use binary frame data to get blobs indicating where objects are in the scene
        contour_list = get_contour_list_ocv_3_or_4(binary_frame_1ch)
        
        # Fill out bounding box list
        new_detection_ref_dict = {}
        reject_ref_dict = {}
        for each_idx, each_contour in enumerate(contour_list):
            
            # Create a blob object for each contour found
            new_detection = Unclassified_Detection_Object(each_contour, preprocessed_frame)
            
            # Get the normalized detection area
            new_detection_area_norm = new_detection.hull_area_px / self._frame_area_px
            
            # Check that the bounding box is correctly sized before adding to list
            no_ignore = (not new_detection.in_zones(self.ignore_zones_list))
            goldi_area = (self._min_area_norm < new_detection_area_norm < self._max_area_norm)
            if no_ignore and goldi_area:
                new_detection_ref_dict[each_idx] = new_detection
            else:
                reject_ref_dict[each_idx] = new_detection
                
        # Store the detections (mostly for analysis/debugging)
        self._detection_ref_dict = new_detection_ref_dict
        self._rejection_ref_dict = reject_ref_dict
        
        return new_detection_ref_dict
    
    # .................................................................................................................
    # .................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions
    
# .....................................................................................................................

def draw_detections(stage_outputs, configurable_ref,
                    detection_color = (255, 255, 0), reject_color = (0, 0, 255)):
    
    # Grab a copy of the color image that we can draw on
    display_frame = stage_outputs["preprocessor"]["preprocessed_frame"]
    detection_frame = display_frame.copy()
    
    # Get display controls
    show_bounding_circles = configurable_ref._show_bounding_circles
    show_outlines = configurable_ref._show_outlines
    show_rejections = configurable_ref._show_rejections
    
    # Grab the detection dictionaries so we can draw with it!
    detections_list = configurable_ref._detection_ref_dict.values()
    rejections_list = configurable_ref._rejection_ref_dict.values() if show_rejections else []
    
    # Record frame sizing so we can draw normalized co-ordinate locations
    frame_h, frame_w = detection_frame.shape[0:2]
    frame_scaling = np.array((frame_w - 1, frame_h - 1))
    frame_area = (frame_w * frame_h)
    
    for list_idx, each_list in enumerate((rejections_list, detections_list)):
        
        is_reject = (list_idx == 0)
        for each_blob in each_list:
            
            # Change color based on validity of detection
            blob_color = reject_color if is_reject else detection_color
            circle_color = reject_color if is_reject else detection_color
            
            # Draw the blob bounding boxes (for detections only)
            if show_outlines:
                # Draw the blob outline
                blob_hull = np.int32(np.round(each_blob.hull_array * frame_scaling))
                cv2.polylines(detection_frame, [blob_hull], True, blob_color, 1, cv2.LINE_AA)
            
            if show_bounding_circles:
                # Draw the detection area as a circle
                blob_area_norm = (each_blob.hull_area_px / configurable_ref._frame_area_px)
                area_scaled_px = frame_area * blob_area_norm
                circle_radius = np.int32(np.round(np.sqrt(area_scaled_px / np.pi)))
                xy_center_px = tuple(np.int32(np.round(each_blob.xy_center_array * frame_scaling)))
                cv2.circle(detection_frame, xy_center_px, circle_radius, circle_color, 1, cv2.LINE_AA)
    
    return detection_frame

# .....................................................................................................................

def get_contour_list_ocv_3_or_4(binary_frame):
    
    # In OpenCV 3:
    # image, contour_list, hierarchy = cv2.findContours(...)
    # 
    # In OpenCV 4
    # contour_list, hierarchy = cv2.findContours(...)
    
    contour_list, _ = cv2.findContours(binary_frame, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[-2:]
    
    return contour_list

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Demo
    
if __name__ == "__main__":
    pass
    

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap



