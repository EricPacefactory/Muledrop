#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri May 31 15:24:07 2019

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

from local.configurables.core.detector.reference_detector import Reference_Detector, Reference_Detection_Object

# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes

class Detector_Stage(Reference_Detector):
    
    # .................................................................................................................
    
    def __init__(self, input_wh):
        
        # Inherit reference functionality
        super().__init__(input_wh, file_dunder = __file__)
        
        # Set up blob detection sizing (parent class should have already done this, but just in case...)
        Reference_Detection_Object.set_frame_scaling(*input_wh)
        
        # Allocate storage to look at the detections on each frame
        self._detection_ref_list = []
        self._rejection_ref_list = []
        
        # Allocate storage for configuration visualization variables
        self._x_follower_size_px = 0
        self._y_follower_size_px = 0
        
        # .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  . Control Group 1 .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .
        
        self.ctrl_spec.new_control_group("Display Controls")
        
        self._show_outlines = \
        self.ctrl_spec.attach_toggle(
                "_show_outlines",
                label = "Show Outlines",
                default_value = True,
                tooltip = "Toggle the display of detection outlines.",
                save_with_config = False)
        
        self._show_bounding_boxes = \
        self.ctrl_spec.attach_toggle(
                "_show_bounding_boxes",
                label = "Show Bounding Boxes",
                default_value = False,
                tooltip = "Toggle the display of detection bounding boxes.",
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
        
        self.ctrl_spec.new_control_group("Minimum Size Controls")
        
        self.min_width_norm = \
        self.ctrl_spec.attach_slider(
                "min_width_norm", 
                label = "Minimum Width", 
                default_value = 0.10,
                min_value = 0.0, max_value = 1.0, step_size = 1/100,
                return_type = float,
                units = "normalized",
                tooltip = "Minimum width required for a detection to be considered valid.")
        
        self.min_height_norm = \
        self.ctrl_spec.attach_slider(
                "min_height_norm", 
                label = "Minimum Height", 
                default_value = 0.10,
                min_value = 0.0, max_value = 1.0, step_size = 1/100,
                return_type = float,
                units = "normalized",
                tooltip = "Minimum height required for a detection to be considered valid.")
        
        # .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  . Control Group 3 .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .
        
        self.ctrl_spec.new_control_group("Maximum Size Controls")
        
        self.max_width_norm = \
        self.ctrl_spec.attach_slider(
                "max_width_norm", 
                label = "Maximum Width", 
                default_value = 0.95,
                min_value = 0.0, max_value = 1.5, step_size = 1/100,
                return_type = float,
                units = "normalized",
                tooltip = "Maximum width allowed for a detection to be considered valid.")
        
        self.max_height_norm = \
        self.ctrl_spec.attach_slider(
                "max_height_norm", 
                label = "Maximum Height", 
                default_value = 0.95,
                min_value = 0.0, max_value = 1.5, step_size = 1/100,
                return_type = float,
                units = "normalized",
                tooltip = "Maximum height allowed for a detection to be considered valid.")
    
    # .................................................................................................................
    
    def reset(self):
        # Clear out all stored detections, since a reset may cause jumps in time/break detection continuity
        self._detection_ref_list = []
        self._rejection_ref_list = []
        
    # .................................................................................................................
    
    def setup(self, variables_changed_dict):
        # Controls directly alter detection behaviour, so nothing to do here!
        pass
        
    # .................................................................................................................
    
    def detections_from_frames(self, binary_frame_1ch, preprocessed_frame):
        
        # Use binary (and color if needed) frame data to determine where objects are in the current scene
        contour_list = get_contour_list_ocv_3_or_4(binary_frame_1ch)
        
        # Fill out bounding box list
        new_detection_ref_list = []
        reject_ref_list = []
        for each_contour in contour_list:
            
            # Create a blob object for each contour found
            new_blob = Reference_Detection_Object(each_contour)
            
            # Check that the bounding box is correctly sized before adding to list
            goldi_width = (self.min_width_norm < new_blob.width < self.max_width_norm)
            goldi_height = (self.min_height_norm < new_blob.height < self.max_height_norm)
            if goldi_width and goldi_height:
                new_detection_ref_list.append(new_blob)
            else:
                reject_ref_list.append(new_blob)
                
        # Store the detections (mostly for analysis/debugging)
        self._detection_ref_list = new_detection_ref_list
        self._rejection_ref_list = reject_ref_list
        
        return new_detection_ref_list
    
    # .................................................................................................................
    # .................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions
    
# .....................................................................................................................

def draw_detections(stage_outputs, configurable_ref):
    
    # Grab a copy of the color image that we can draw on
    display_frame = stage_outputs.get("preprocessor").get("preprocessed_frame")
    detection_frame = display_frame.copy()
    
    # Get display controls
    show_bounding_boxes = configurable_ref._show_bounding_boxes
    show_outlines = configurable_ref._show_outlines
    show_rejections = configurable_ref._show_rejections
    
    # Grab the detection list out so we can draw with it!
    detection_ref_list = configurable_ref._detection_ref_list
    rejection_ref_list = configurable_ref._rejection_ref_list if show_rejections else []
    
    # Record frame sizing so we can draw normalized co-ordinate locations
    frame_h, frame_w = detection_frame.shape[0:2]
    frame_wh = np.array((frame_w, frame_h))
    
    for list_idx, each_list in enumerate((rejection_ref_list, detection_ref_list)):
        for each_blob in each_list:
            
            is_detect = (list_idx > 0)
            blob_color = (255, 255, 0) if is_detect else (0, 0, 255)
            box_color = (255, 255, 0) if is_detect else (0, 0, 255)
            
            # Draw the blob bounding boxes (for detections only)
            if show_outlines:
                # Draw the blob outline
                blob_hull = np.int32(np.round(each_blob.hull * frame_wh))
                cv2.polylines(detection_frame, [blob_hull], True, blob_color, 1, cv2.LINE_AA)
            
            if show_bounding_boxes:
                # Draw the bounding box
                tl, br = np.int32(np.round(each_blob.tl_br * frame_wh))
                cv2.rectangle(detection_frame, tuple(tl), tuple(br), box_color, 2, cv2.LINE_4)
    
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



