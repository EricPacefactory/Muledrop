#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri May 31 14:46:26 2019

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

from local.configurables.configurable_template import Core_Configurable_Base

# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes

class Reference_Detector(Core_Configurable_Base):
    
    # .................................................................................................................
    
    def __init__(self, input_wh, file_dunder):
        
        super().__init__(input_wh, file_dunder = file_dunder)
        
        # Set up reference detection object
        Reference_Detection_Object.set_frame_scaling(*input_wh)
        
        # !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
        #   Inherited classes must have __init__(input_wh) as arguments!
        # !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
        
        # For inherited classes, first call:
        # super().__init__(file_dunder = __file__)
        
        # Then do any class-specific set up
        # ...
        # ...
        # ...
    
    # .................................................................................................................
    
    def reset(self):
        raise NotImplementedError("Must implement a detector reset()")
    
    # .................................................................................................................
    
    # MAY OVERRIDE (BUT NOT NECESSARY, BETTER TO INSTEAD OVERRIDE: detections_from_frames())
    def run(self, filtered_binary_frame_1ch, preprocessed_frame):
        # This function must maintain this input/output structure!
        #   - Need to pass in binary (black or white only!) image data for (assumed) blob detection 
        #   - Also pass the color image, in case the detector wants to try something fancy
        #   - Return a list of detection objects, which should inherit from the reference detection class!
        
        # Return a list of objects from the detection class
        detection_ref_list = self.detections_from_frames(filtered_binary_frame_1ch, preprocessed_frame)
        
        return {"detection_ref_list": detection_ref_list}
    
    # .................................................................................................................
    
    # SHOULD OVERRIDE
    def detections_from_frames(self, binary_frame_1ch, preprocessed_frame):
        # Use binary (and color if needed) frame data to determine where objects are in the current scene
        return []
    
    # .................................................................................................................
    # .................................................................................................................


# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
    

class Reference_Detection_Object:
    
    _xy_loc_scaling = None
    
    # .................................................................................................................
    
    def __init__(self, detection_type, contour):
        
        # Store the 'type' of detection, in case new versions are made in the future which are not compatible
        self.detection_type = detection_type
        
        # First get simplified outline
        hull_px = cv2.convexHull(contour).squeeze()
        self.hull = np.float32(hull_px) * self._xy_loc_scaling
        
        # Get bounding box data. Note: cv2.boundingRect width/height are calculated as 'zero-inclusive'
        # e.g. The width between points [5, 15] would be 11 (= 15 - 5 + 1)
        top_left_x_px, top_left_y_px, box_width_px, box_height_px = cv2.boundingRect(hull_px)
        bot_right_x_px = top_left_x_px + box_width_px - 1
        bot_right_y_px = top_left_y_px + box_height_px - 1
        
        # Record area data. Note: cv2.contourArea is calculated without 'zero-inclusive' width/height values
        # e.g. a contour of (0,0), (100,0), (100,100), (0,100) has an area of 100*100 = 10000
        hull_area_px = cv2.contourArea(hull_px)
        box_area_px = (box_width_px - 1) * (box_height_px - 1)
        self.fill = hull_area_px / box_area_px
        
        # Store (normalized) location values
        self.top_left = np.float32((top_left_x_px, top_left_y_px)) * self._xy_loc_scaling
        self.bot_right = np.float32((bot_right_x_px, bot_right_y_px)) * self._xy_loc_scaling
        
        # Store width/height in format that allows reconstruction of tl/br using x/y center coords
        self.width, self.height = np.float64(self.bot_right - self.top_left)
        self.box_area = self.width * self.height
        
        # Store a property for assigning classifications during detection. Reference does not actually do this though!
        self.detection_classification = None
        
    # .................................................................................................................
    
    def __repr__(self):
        return "Detection @ ({:.3f}, {:.3f})".format(*self.xy_center)
    
    # .................................................................................................................
    
    @classmethod
    def set_frame_scaling(cls, frame_width_px, frame_height_px):
        cls._xy_loc_scaling = 1 / np.float32((frame_width_px - 1, frame_height_px - 1))
    
    # .................................................................................................................
    #%% Properties
    
    @property
    def tl_br(self):
        return np.float32((self.top_left, self.bot_right))
    
    # .................................................................................................................
    
    @property
    def x_center(self):
        
        half_width = self.width / 2
        left_x = self.top_left[0]
        x_center = left_x + half_width
        
        return x_center
    
    # .................................................................................................................
    
    @property
    def y_center(self):
        
        half_height = self.height / 2
        top_y = self.top_left[1]
        y_center = top_y + half_height
        
        return y_center
    
    # .................................................................................................................
    
    @property
    def xy_center(self):        
        return np.float32((self.x_center, self.y_center))

    # .................................................................................................................

# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////

# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions



# ---------------------------------------------------------------------------------------------------------------------
#%% Demo
    
if __name__ == "__main__":
    pass
    

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap


