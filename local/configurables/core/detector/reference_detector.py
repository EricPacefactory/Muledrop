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
    
    def __init__(self, location_select_folder_path, camera_select, input_wh, *, file_dunder):
        
        # Inherit from parent class
        super().__init__("detector", location_select_folder_path, camera_select, input_wh,
                         file_dunder = file_dunder)
        
        # Set up reference detection object
        Reference_Detection_Object.set_frame_scaling(*input_wh)
        
        # !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
        
        # For inherited classes, first call:
        # super().__init__(location_select_folder_path, camera_select, input_wh, file_dunder = __file__)
        
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
    
    def __init__(self, contour, realtime_classification_dict, display_frame):
        
        # Store a property for assigning classifications during detection
        # (Should be of the form: {"class_label_1": score_1, "class_label_2": score_2, etc.})
        self.realtime_classification_dict = realtime_classification_dict
        
        # Get a simplified representation of the contour
        full_hull = cv2.convexHull(contour)
        num_points, _, _ = full_hull.shape
        hull_px = np.reshape(full_hull, (num_points, 2)) #full_hull.squeeze() # <-- causes errors on single pixels
        
        # Record area data. Note: cv2.contourArea is calculated without 'zero-inclusive' width/height values
        # e.g. a contour of (0,0), (100,0), (100,100), (0,100) has an area of 100*100 = 10000
        hull_area_px = cv2.contourArea(hull_px)
        
        # Store x/y center points base on hull
        self.xy_center_array = np.mean(hull_px, axis = 0) * self._xy_loc_scaling
        
        # Handle cases where there is no hull area (single pixels, row/column contours and tight-triangles)
        no_hull_area = (hull_area_px < 1.0)
        if no_hull_area:
            
            # Get hull bounding box
            min_x, min_y = np.min(hull_px, axis = 0)
            max_x, max_y = np.max(hull_px, axis = 0)
            
            # Re-assign min/max values by shifting min values down 1 pixel, if needed
            min_x = max(0, min_x - 1) if min_x == max_x else min_x
            min_y = max(0, min_y - 1) if min_y == max_y else min_y
            max_x = max(1, max_x)
            max_y = max(1, max_y)
            
            # Generate new hull as a bounding box around min/max values
            hull_px = np.int32(((min_x, min_y), (max_x, min_y), (max_x, max_y), (min_x, max_y)))
            hull_area_px = cv2.contourArea(hull_px)
        
        # Store hull area
        self.hull_area_px = hull_area_px
        
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
        
        # Store imaging data
        self.imaging_data_dict = self._get_imaging_data(display_frame)
    
    # .................................................................................................................
    
    def __repr__(self):
        return "Detection @ ({:.3f}, {:.3f})".format(*self.xy_center_array)
    
    # .................................................................................................................
    
    @classmethod
    def set_frame_scaling(cls, frame_width_px, frame_height_px):
        cls._xy_loc_scaling = 1.0 / np.float32((frame_width_px - 1, frame_height_px - 1))
    
    # .................................................................................................................
    #%% Position functions
    
    def in_zones(self, zones_list):
        
        ''' Function which checks if this detection is within a list of zones '''
        
        for each_zone in zones_list:
            
            # If no zone data is present, then we aren't in the zone!
            if each_zone == []:
                return False
            
            # Otherwise, check if the x/y tracking location is inside any of the zones
            zone_array = np.float32(each_zone)
            in_zone = (cv2.pointPolygonTest(zone_array, self.xy_center_tuple, measureDist = False) > 0)
            if in_zone:
                return True
        
        return False
    
    # .................................................................................................................
    #%% Properties
    
    @property
    def tl_br(self):
        return np.float32((self.top_left, self.bot_right))
    
    # .................................................................................................................
    
    @property
    def xy_center_tuple(self):
        return tuple(self.xy_center_array)
    
    # .................................................................................................................
    #%% Image manipulations
    
    # .................................................................................................................
    
    def _get_imaging_data(self, display_frame):
        
        ''' Function used to bundle together all image-based data values to be included in metadata '''
        
        # Crop detection from display for further processing
        cropped_frame = self._get_cropped_display(display_frame)
        
        # Bin + count pixel colors
        masked_bgr_rows = self._get_row_of_masked_pixels(cropped_frame)
        color_proportions = self._get_hsv_color_proportions(masked_bgr_rows)
        
        # Build imaging data
        imaging_data_dict = {"color_proportions": color_proportions}
        
        return imaging_data_dict
    
    # .................................................................................................................
    
    def _get_cropped_display(self, display_frame, max_dimension = 50, blur_size = 3):
        
        '''
        Helper function which takes in a display image and crops down
        to the bounding box of this detection (based on the hull)
        Also downscales the result if it is too large and applies bluring
        '''
        
        # Get display scaling
        frame_height, frame_width = display_frame.shape[0:2]
        display_scaling = np.float32([(frame_width - 1), (frame_height - 1)])
        tl_display = np.int32(np.round(self.top_left * display_scaling))
        br_display = np.int32(np.round(self.bot_right * display_scaling))
        
        # Use detection bounding-box to crop out a rectangular copy of the detection from the display image
        x1, y1 = tl_display
        x2, y2 = br_display
        color_crop_px = display_frame[y1:y2, x1:x2, :]
        
        # Downscale the cropped image if needed
        crop_height, crop_width = color_crop_px.shape[0:2]
        width_factor = np.ceil(crop_width / max_dimension)
        height_factor = np.ceil(crop_height / max_dimension)
        scale_factor = max(1, width_factor, height_factor)
        needs_downscale = (scale_factor > 1)
        if needs_downscale:
            scale_width = max(1, int(crop_width / scale_factor))
            scale_height = max(1, int(crop_height / scale_factor))
            scale_wh = (scale_width, scale_height)
            color_crop_px = cv2.resize(color_crop_px, dsize = scale_wh, interpolation = cv2.INTER_NEAREST)
        
        # Apply blurring to help reduce noise
        color_crop_px = cv2.blur(color_crop_px, (3, 3), borderType = cv2.BORDER_REFLECT)
        
        return color_crop_px
    
    # .................................................................................................................
    
    def _get_row_of_masked_pixels(self, cropped_frame):
        
        '''
        Helper function which takes a cropped frame, applies masking based on the detection hull,
        then indexes out only the pixels within the hull. Outputs as a single row of bgr values,
        assuming N pixels remain after masking, the result will have shape: N x 1 x 3
        '''
        
        # Generate a mask based on the detection hull, adjusted to fit over the cropped image of the detection
        crop_height, crop_width = cropped_frame.shape[0:2]
        crop_scaling = np.float32([crop_width - 1, crop_height - 1])
        cropped_hull_norm = (self.hull_array - self.top_left) / (self.bot_right - self.top_left)
        hull_pts_px = np.int32(np.round(crop_scaling * cropped_hull_norm))
        hull_mask_1ch = np.zeros((crop_height, crop_width), dtype = np.uint8)
        hull_mask_1ch = cv2.fillConvexPoly(hull_mask_1ch, hull_pts_px, 255)
        
        # Convert the mask to a 1D logical aray and use it to index out pixels from the cropped image
        # Note: this results in a listing of pixel values, not a useable image!
        hull_mask_1ch_logical = (hull_mask_1ch > 0)
        masked_bgr_rows = cropped_frame[hull_mask_1ch_logical, :]
        
        # Convert back to an 'image' format (this way we can directly use opencv functions on the result)
        # -> Result will have dimensions of N x 1 x 3 as opposed to being N x 3
        masked_bgr_rows = np.expand_dims(masked_bgr_rows, 1)
        
        return masked_bgr_rows
    
    # .................................................................................................................
    
    def _get_hsv_color_proportions(self, bgr_rows):
        
        '''
        Helper function used to bin pixels into 8 regions which can be described (roughly) as follows: 
            - dark, light
            - red, yellow, green, cyan, blue, magenta
        
        The resulting counts of pixels-per-color bin is returned as a list of integers,
        where the total count is normalized to 1000, so that each entry in the
        returned list represents the proportion of each color bin
        
        The bins are segmented from the (cylindrical) hsv color space
        From a side-view of the cylindrical co-ord system (with the 'value' channel running vertically),
        the bins are divided approximately as follows:
             ___________
            |   |   |   |
            |   | L |   |
            | H |___| H |
            |   |   |   |
            |___| D |___|
            |___________|
        
        Where D represents the 'dark' segment,
        L represents the 'light' segment,
        and H represents different hue segments
        Note that there are 6 separate hue segments (RYGCBM) which wrap around the cylinder (not shown)
        '''
        
        # Convert to hsv (not full!) so we can more easily define meaninngful color bins
        # hsv mapping: hue -> [0, 179], sat -> [0, 255], val -> [0, 255]
        hsv_rows = cv2.cvtColor(bgr_rows, cv2.COLOR_BGR2HSV)
        
        # For clarity
        low_sat_l = 63
        low_sat_u = low_sat_l + 1
        low_val_l = 63
        low_val_u = low_val_l + 1
        
        # For convenience
        hsv_in_range = lambda l_hsv, h_hsv: np.sum(np.bool8(cv2.inRange(hsv_rows, np.uint8(l_hsv), np.uint8(h_hsv))))
        hue_in_range = lambda low_hue, high_hue: hsv_in_range([low_hue, low_sat_u, low_val_u], [high_hue, 255, 255])
        
        # Map a full short cylindrical base to dark regions
        # (convers all hues, all saturations and very low brightness values)
        dark_1_start = [0, 0, 0]
        dark_1_end = [255, 255, low_val_l]
        dark_pixels = hsv_in_range(dark_1_start, dark_1_end)
        
        # Also map a small lower-central tube to dark regions
        # (covers all hues, low saturations and low brightness values)
        dark_2_start = [0, 0, low_val_u]
        dark_2_end = [255, low_sat_l, 127]
        dark_pixels += hsv_in_range(dark_2_start, dark_2_end)
        
        # Map a small upper-central tube to light region
        # (covers all hues, low saturations and high brightness values)
        light_start = [0, 0, 128]
        light_end = [255, low_sat_l, 255]
        light_pixels = hsv_in_range(light_start, light_end)
        
        # Get red pixel counts, which wrap around hsv space and need to be counted in two sets...
        # (covers red hues, middle-to-high saturation, middle-to-high brightness values)
        red_pixels = hue_in_range(0, 14)
        red_pixels += hue_in_range(165, 179)
        
        # Get remaining color counts based on rgb (and cmy) binning
        # (covers target hue ranges, middle-to-high saturation, middle-to-high brightness values)
        yellow_pixels = hue_in_range(15, 44)
        green_pixels = hue_in_range(45, 74)
        cyan_pixels = hue_in_range(75, 104)
        blue_pixels = hue_in_range(105, 134)
        magenta_pixels = hue_in_range(135, 164)
        
        # Arrange counts in a reasonably intuitive way
        num_pixels = hsv_rows.shape[0]
        pixel_color_counts = np.float32([dark_pixels, light_pixels,
                                         red_pixels, yellow_pixels,
                                         green_pixels, cyan_pixels,
                                         blue_pixels, magenta_pixels])
        
        '''
        # Sanity check. Slower way to determine total pixel count but useful to check for double-counting
        total_count = np.sum(pixel_color_counts)
        if (num_pixels != total_count):
            print("Error! Double counting color pixels:", num_pixels, total_count)
        '''
        
        # Scale pixel counts to proportional values (integer values scaled to 1000)
        color_prop = np.int32(np.round(1000 * pixel_color_counts / num_pixels)).tolist()
        
        return color_prop

    # .................................................................................................................
    # .................................................................................................................


# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////


class Unclassified_Detection_Object(Reference_Detection_Object):
    
    # .................................................................................................................
    
    def __init__(self, contour, display_frame):
        
        # Very simple variant of the reference detection object. Simply hard-codes an empty classification dictionary
        # (normally, the format should be: {"class_label_1": score_1, "class_label_2": score_2, etc.})
        no_classification_dict = {}
        super().__init__(contour, no_classification_dict, display_frame)
    
    # .................................................................................................................
    # .................................................................................................................


# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////


class Pedestrian_Detection_Object(Reference_Detection_Object):
    
    # .................................................................................................................
    
    def __init__(self, contour, display_frame):
        
        # Very simple variant of the reference detection object. Simply hard-codes an empty classification dictionary
        # (normally, the format should be: {"class_label_1": score_1, "class_label_2": score_2, etc.})
        ped_classification_dict = {"pedestrian": 1.0}
        super().__init__(contour, ped_classification_dict, display_frame)
    
    # .................................................................................................................
    # .................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions



# ---------------------------------------------------------------------------------------------------------------------
#%% Demo
    
if __name__ == "__main__":
    pass
    

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap


