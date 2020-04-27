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
    
    # MAY OVERRIDE. Only if some resources have been opened while running...
    def close(self, final_frame_index, final_epoch_ms, final_datetime):
        # Nothing opened, nothing to close!
        return None
    
    # .................................................................................................................
    
    # MAY OVERRIDE (BUT NOT NECESSARY, BETTER TO INSTEAD OVERRIDE: detections_from_frames())
    def run(self, filtered_binary_frame_1ch, preprocessed_frame):
        # This function must maintain this input/output structure!
        #   - Need to pass in binary (black or white only!) image data for (assumed) blob detection 
        #   - Also pass the color image, in case the detector wants to try something fancy with the color data
        #   - Return a list of detection objects, which should inherit from the reference detection class!
        
        # Return a dictionary of detection objects
        detection_ref_dict = self.detections_from_frames(filtered_binary_frame_1ch, preprocessed_frame)
        
        return {"detection_ref_dict": detection_ref_dict}
    
    # .................................................................................................................
    
    # SHOULD OVERRIDE
    def detections_from_frames(self, binary_frame_1ch, preprocessed_frame):
        # Use binary (and color if needed) frame data to determine where objects are in the current scene
        # Should return a dictionary, with keys to distinguish detections and values storing detection data
        return {}
    
    # .................................................................................................................
    # .................................................................................................................


# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
    

class Reference_Detection_Object:
    
    _xy_loc_scaling = None
    
    # .................................................................................................................
    
    def __init__(self, contour, realtime_classification_dict):
        
        # Get a simplified representation of the contour
        full_hull = cv2.convexHull(contour)
        num_points, _, _ = full_hull.shape
        hull_px = np.reshape(full_hull, (num_points, 2)) #full_hull.squeeze() # <-- causes errors on single pixels
        
        # Record area data. Note: cv2.contourArea is calculated without 'zero-inclusive' width/height values
        # e.g. a contour of (0,0), (100,0), (100,100), (0,100) has an area of 100*100 = 10000
        hull_area_px = cv2.contourArea(hull_px)
        
        # Handle cases where there is no hull area (single pixels, row/column contours and tight-triangles)
        no_hull_area = (hull_area_px < 1.0)
        if no_hull_area:
            
            # Make up a fake full area rather than re-calculating
            hull_area_px = 1.0
            
            # Get hull bounding box
            min_xy = np.min(hull_px, axis = 0)
            max_xy = np.max(hull_px, axis = 0)
            
            # Figure out which axes have zero separation between min/max values
            xy_diff = (max_xy - min_xy)
            null_axes = (xy_diff == 0)
            
            # Create a new hull out of the bounding box values, and add 1 to max values along zeroed axes
            hull_px = np.int32([min_xy, max_xy])
            hull_px[1, null_axes] = hull_px[1, null_axes] + 1
            
        # Scale outline into normalized co-ords
        self.hull_array = np.float32(hull_px) * self._xy_loc_scaling
                
        # Get bounding box data. Note: cv2.boundingRect width/height are calculated as 'zero-inclusive'
        # e.g. The width between points [5, 15] would be 11 (= 15 - 5 + 1)
        top_left_x_px, top_left_y_px, box_width_px, box_height_px = cv2.boundingRect(hull_px)
        bot_right_x_px = top_left_x_px + box_width_px - 1
        bot_right_y_px = top_left_y_px + box_height_px - 1
        
        # Store (normalized) location values
        self.top_left = np.float32((top_left_x_px, top_left_y_px)) * self._xy_loc_scaling
        self.bot_right = np.float32((bot_right_x_px, bot_right_y_px)) * self._xy_loc_scaling
        
        # Store width/height in format that allows reconstruction of tl/br using x/y center coords
        self.width, self.height = np.float32(self.bot_right - self.top_left)
        
        # Store x/y center points (careful to store them as python floats, not numpy floats)
        self.xy_center_array = ((self.top_left + self.bot_right) / 2.0)
        
        # Store a property for assigning classifications during detection
        # (Should be of the form: {"class_label_1": score_1, "class_label_2": score_2, etc.})
        self.realtime_classification_dict = realtime_classification_dict
        
    # .................................................................................................................
    
    def __repr__(self):
        return "Detection @ ({:.3f}, {:.3f})".format(*self.xy_center_array)
    
    # .................................................................................................................
    
    @classmethod
    def set_frame_scaling(cls, frame_width_px, frame_height_px):
        cls._xy_loc_scaling = 1.0 / np.float32((frame_width_px - 1, frame_height_px - 1))
    
    # .................................................................................................................
    #%% Properties
    
    @property
    def tl_br(self):
        return np.float32((self.top_left, self.bot_right))
    
    # .................................................................................................................
    
    @property
    def xy_center_tuple(self):
        return tuple(self.xy_center)

    # .................................................................................................................
    # .................................................................................................................


# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////


class Unclassified_Detection_Object(Reference_Detection_Object):
    
    # .................................................................................................................
    
    def __init__(self, contour):
        
        # Very simple varianet of the reference detection object. Simply hard-codes an empty classification dictionary
        # (normally, the format should be: {"class_label_1": score_1, "class_label_2": score_2, etc.})
        no_classification_dict = {}
        super().__init__(contour, no_classification_dict)
    
    # .................................................................................................................
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


