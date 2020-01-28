#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Oct 16 16:36:03 2019

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

from time import perf_counter

from scipy.interpolate import UnivariateSpline
from scipy.spatial import cKDTree

from local.offline_database.file_database import _time_to_epoch_ms

# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes

class Object_Reconstruction:
    
    # .................................................................................................................
    
    def __init__(self, object_metadata, frame_wh, global_start_time, global_end_time):
        
        # Store full copy of metadata for easy re-use
        self.metadata = object_metadata
        self.num_samples = self.metadata["num_samples"]
        self.nice_id = self.metadata["nice_id"]
        self.full_id = self.metadata["full_id"]
        self.lifetime_ms = self.metadata["lifetime_ms"]
        
        # Store object trail separately, since we'll want to use that a lot
        obj_x_array = np.float32(object_metadata["tracking"]["x_center"])
        obj_y_array = np.float32(object_metadata["tracking"]["y_center"])
        self._real_trail_xy = np.vstack((obj_x_array, obj_y_array)).T
        
        # Store smoothed trail
        self.trail_xy = self._create_trail_xy()
        
        # Store object start/end time in terms of video frame indice, used for syncing with snapshots
        self.start_idx = self.metadata["timing"]["first_frame_index"]
        self.end_idx = self.metadata["timing"]["last_frame_index"]
        self.start_ems = self.metadata["timing"]["first_epoch_ms"]
        self.end_ems = self.metadata["timing"]["last_epoch_ms"]
        
        # Store global start/end times, used for relative timing calculations
        self.global_start_ems = _time_to_epoch_ms(global_start_time)
        self.global_end_ems = _time_to_epoch_ms(global_end_time)
        self.global_length_ems = self.global_end_ems - self.global_start_ems
        
        # Store relative timing (normalized values, based on global time range)
        self.relative_start, self.relative_end = self._get_relative_start_end()
        
        # Store drawing sizes & scalings
        self.frame_wh = frame_wh
        self.frame_scaling_array = np.float32(frame_wh) - np.float32((1, 1))
        
        # Allocate storage for graphics settings
        self._trail_color = (0, 255, 255)
        self._outline_color = (0, 255, 255)
        
        # Allocate storage for classification data
        self._classification_label = "unclassified"
        self._subclass = ""
        self._classification_attributes = {}
    
    # .................................................................................................................
    
    def __repr__(self):        
        return "ID: {} - ({})".format(self.full_id, self._class_name)
    
    # .................................................................................................................
    
    @property
    def _class_name(self):
        return self.__class__.__name__
    
    # .................................................................................................................
    
    def _rel_index(self, frame_index):
        
        ''' Function for converting absolute frame indices into a index relative to the object dataset '''
        
        #return self.end_idx - frame_index
        return frame_index - self.start_idx
    
    # .................................................................................................................
    
    def _index_in_dataset(self, frame_index):
        
        ''' Function for checking if this object has data for the given frame index '''
        
        rel_index = self._rel_index(frame_index)
        is_valid = (0 <= rel_index < self.num_samples)
                
        return is_valid, rel_index
    
    # .................................................................................................................
    
    def _arrayify(self, data):
        
        ''' Helper function for converting python (normalized) values/lists into numpy arrays '''
        
        return np.float32(data)
    
    # .................................................................................................................
    
    def _pixelize(self, data_wh):
        
        ''' Function for converting normalized data to integer pixel values '''
        
        return np.int32(np.round(self._arrayify(data_wh) * self.frame_scaling_array))
    
    # .................................................................................................................
    
    def get_bounding_epoch_ms(self):
        
        ''' Function used to return the start/end timing of the object. Useful for syncing with snapshots '''
        
        return self.start_ems, self.end_ems
    
    # .................................................................................................................
    
    def get_hull_array(self, frame_index, normalized = True):
        
        ''' 
        Function for getting the original object hull data at a specified frame index
        Assuming the object had data at the given frame index, a single hull is returned (as a numpy array)
        If an index is given outside the object dataset, this function will return None
        
        Note: The frame index is interpretted as an absolute index (not index relative to object dataset)
        '''
        
        # Don't bother trying to draw anything if there aren't any samples!
        valid_index, rel_idx = self._index_in_dataset(frame_index)
        
        # Only grab target hull data if we have a valid frame index
        if valid_index:
            hull_data = self.metadata["tracking"]["hull"][rel_idx]
            return self._arrayify(hull_data) if normalized else self._pixelize(hull_data)
        
        return None
    
    # .................................................................................................................
    
    def get_box_tlbr(self, frame_index, normalized = True):
        
        '''
        Function for returning the bounding box of an object at a specified frame index 
        Assuming the object had data at the given frame index, returns a tuple containing (top_left_xy, bot_right_xy)
        If an index is given outside the object dataset, this function will return None
        
        Note: The frame index is interpretted as an absolute index (not index relative to object dataset)
        '''
        
        # Try to get the object hull data at the given frame
        obj_hull_array = self.get_hull_array(frame_index, normalized = normalized)
        
        # If no data exists, just return nothing
        if obj_hull_array is None:
            return None
        
        # Get bounding box co-ordinates
        box_top_left = np.min(obj_hull_array, axis = 0)
        box_bot_right = np.max(obj_hull_array, axis = 0)
        obj_box_tlbr = (box_top_left.tolist(), box_bot_right.tolist())
        
        return obj_box_tlbr        
    
    # .................................................................................................................
    
    def set_graphics(self, trail_color, outline_color):
        
        self._trail_color = trail_color
        self._outline_color = outline_color
    
    # .................................................................................................................
    
    def set_classification(self, class_label, subclass, attributes):
        
        self._classification_label = class_label
        self._subclass = subclass
        self._classification_attributes = attributes
    
    # .................................................................................................................
    
    def draw_outline(self, output_frame, frame_index, snapshot_epoch_ms = None,
                     line_color = None, line_thickness = 1):
        
        # If a snapshot time is provided, make sure the object existed during the given time!
        if snapshot_epoch_ms is not None:            
            in_time_range = (self.start_ems <= snapshot_epoch_ms < self.end_ems)
            if not in_time_range:
                return output_frame
        
        # Get hull data, if it exists
        hull_array = self.get_hull_array(frame_index, normalized = False)
        
        # If no hull data exists at the given frame index, don't draw anything
        if hull_array is None:
            return output_frame
        
        # If a line color isn't specified, use the built-in color
        if line_color is None:
            line_color = self._outline_color
        
        # If we get here, draw the hull
        cv2.polylines(output_frame, 
                      pts = [hull_array], 
                      isClosed = True, 
                      color = line_color,
                      thickness = line_thickness,
                      lineType = cv2.LINE_AA)       
        
        return output_frame
    
    # .................................................................................................................
    
    def draw_trail(self, output_frame, frame_index = None, snapshot_epoch_ms = None,
                   line_color = None, line_thickness = 1, 
                   use_outline_color = False):
        
        # If a snapshot time is provided, make sure the object existed during the given time!
        if snapshot_epoch_ms is not None:            
            in_time_range = (self.start_ems <= snapshot_epoch_ms < self.end_ems)
            if not in_time_range:
                return output_frame
        
        # Get reduced data set for plotting
        if frame_index:
            
            # Don't bother trying to draw anything if there aren't any samples!
            valid_index, rel_idx = self._index_in_dataset(frame_index)
            if not valid_index:
                return output_frame
            plot_trail_xy = self.trail_xy[:rel_idx]
        else:
            plot_trail_xy = self.trail_xy
        
        # If needed, override the trail color using the outline color (useful if we're not showing outlines!)
        if use_outline_color:
            line_color = self._outline_color
        
        # If a line color isn't specified, use the built-in color
        if line_color is None:
            line_color = self._trail_color
        
        # Convert trail data to pixel units and draw as an open polygon
        trail_xy_px = np.int32(np.round(plot_trail_xy * self.frame_scaling_array))
        cv2.polylines(output_frame, 
                      pts = [trail_xy_px],
                      isClosed = False, 
                      color = line_color,
                      thickness = line_thickness,
                      lineType = cv2.LINE_AA)
        
        return output_frame
    
    # .................................................................................................................
    
    def draw_trail_segment(self, output_frame, start_frame_index, end_frame_index, snapshot_epoch_ms = None,
                           line_color = None, line_thickness = 1):
        
        # If a snapshot time is provided, make sure the object existed during the given time!
        if snapshot_epoch_ms is not None:            
            in_time_range = (self.start_ems <= snapshot_epoch_ms < self.end_ems)
            if not in_time_range:
                return output_frame
        
        # Get trail segment for plotting
        start_idx = self._rel_index(start_frame_index)
        end_idx = self._rel_index(end_frame_index)
        
        # Don't draw anything if indices are out of bounds
        if start_idx is None or end_idx is None:
            return output_frame
        
        # Don't draw anything if there is no data
        not_enough_data = ((start_idx - end_idx) < 2)
        if not_enough_data:
            return output_frame
        
        # Grab trail data (which is stored in reverse order...)
        plot_trail_xy = self.trail_xy[start_idx:end_idx]
        
        # If a line color isn't specified, use the built-in color
        if line_color is None:
            line_color = self._trail_color
        
        # Convert trail data to pixel units and draw as an open polygon
        trail_xy_px = np.int32(np.round(plot_trail_xy * self.frame_scaling_array))
        cv2.polylines(output_frame, 
                      pts = [trail_xy_px],
                      isClosed = False, 
                      color = line_color,
                      thickness = line_thickness,
                      lineType = cv2.LINE_AA)
        
        return output_frame
    
    # .................................................................................................................
    
    def crop_image(self, image, frame_index, minimum_width_px = 0, minimum_height_px = 0):
        
        # First get the bounding box for the object so we know where to crop
        box_tlbr_px = self.get_box_tlbr(frame_index, normalized = False)
        
        # If no data exists, just return nothing
        if box_tlbr_px is None:
            return None
        
        # Make sure the cropping region isn't too small (based on minimums)
        (x1, y1), (x2, y2) = box_tlbr_px
        x1, x2 = minimum_crop_box(x1, x2, minimum_width_px, self.frame_wh[0])
        y1, y2 = minimum_crop_box(y1, y2, minimum_height_px, self.frame_wh[1])
        
        # Use cropping co-ords to slice out the object from the provided image
        cropped_image = image[y1:y2, x1:x2]
        
        return cropped_image
    
    # .................................................................................................................
    
    def _create_trail_xy(self):
        
        ''' 
        Function used to generate modified trails
        Base implementation returns the original (raw) trail data
        Override to provide alternate functionality (i.e. smoothing or other cleanup)
        '''
        
        return self._real_trail_xy
    
    # .................................................................................................................
    
    def _get_relative_start_end(self):
        
        # Get relative start and end times for this object (as fractional values, should be between 0 and 1)
        relative_start = (self.start_ems - self.global_start_ems) / self.global_length_ems
        relative_end = (self.end_ems - self.global_start_ems) / self.global_length_ems
        
        return relative_start, relative_end
    
    # .................................................................................................................
    
    @classmethod
    def create_reconstruction_list(cls, object_metadata_list, frame_wh, 
                                   global_start_time, global_end_time,
                                   print_feedback = True,
                                   **kwargs):
        
        ''' Helper function for generating a list of reconstructed objects based on this class '''
        
        # Some feedback before starting a potentiall heavy operation
        if print_feedback:
            print("", "Reconstructing objects...", sep = "\n")
            t_start = perf_counter()
        
        object_list = []
        for each_obj_metadata in object_metadata_list:
            new_reconstruction = cls(each_obj_metadata,
                                     frame_wh,
                                     global_start_time,
                                     global_end_time,
                                     **kwargs)
            object_list.append(new_reconstruction)
            
        # Final feedback
        if print_feedback:
            t_end = perf_counter()
            num_objects = len(object_list)
            print("  {} total objects".format(num_objects),
                  "  Finished! Took {:.0f} ms".format(1000 * (t_end - t_start)), 
                  sep = "\n")
            
        return object_list
    
    # .................................................................................................................
    # .................................................................................................................


# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////


class Smoothed_Object_Reconstruction(Object_Reconstruction):
    
    # .................................................................................................................
    
    def __init__(self, object_metadata, frame_wh, global_start_time, global_end_time,
                 smoothing_factor = 0.015):
        
        # Store smoothing parameter, since it will be needed during trail generation
        self._smoothing_factor = smoothing_factor
        
        # Inherit from parent class
        super().__init__(object_metadata, frame_wh, global_start_time, global_end_time)
        
    # .................................................................................................................
    
    def _create_trail_xy(self):
        
        ''' Overriding parent class implementation to provide additional smoothing to trail data '''
        
        # Pull out raw x/y array data
        x_array_norm = self._real_trail_xy[:, 0]
        y_array_norm = self._real_trail_xy[:, 1]
        
        # Use splines to smooth x/y data separately
        interp_idx = np.linspace(0, 1, self.num_samples)
        smooth_x = UnivariateSpline(interp_idx, x_array_norm, s = self._smoothing_factor)
        smooth_y = UnivariateSpline(interp_idx, y_array_norm, s = self._smoothing_factor)
        smoothed_trail_xy = np.vstack((smooth_x(interp_idx), smooth_y(interp_idx))).T
        
        return smoothed_trail_xy
    
    # .................................................................................................................
    # .................................................................................................................


# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////


class Smooth_Hover_Object_Reconstruction(Smoothed_Object_Reconstruction):
    
    def __init__(self, object_metadata, frame_wh, global_start_time, global_end_time, 
                 smoothing_factor = 0.015):
        
        # Inherit from parent class
        super().__init__(object_metadata, frame_wh, global_start_time, global_end_time, 
                         smoothing_factor)
    
    # .................................................................................................................
    
    def highlight_trail(self, output_frame, highlight_color = (255, 0, 255), highlight_thickness = 2):
        return self.draw_trail(output_frame, line_color = highlight_color, line_thickness = highlight_thickness)
    
    # .................................................................................................................
    # .................................................................................................................


# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////


class Hover_Mapping:
    
    # .................................................................................................................
    
    def __init__(self, object_class_dict, tree_leaf_size = 8, hover_map_name = None, print_feedback = True):
        
        # Warn user about hover map generation, since it could take a while
        if print_feedback:
            name_str = "hover map" if (hover_map_name is None) else "{} hover map".format(hover_map_name)
            feedback_msg = "Generating {}...".format(name_str)
            print("", feedback_msg, sep = "\n")
        
        # Keep track of timing for feedback
        start_time = perf_counter()
        
        # Assign numbers to represent each class (so we don't store a silly number of class label strings)
        self.index_to_class_lut, self.class_to_idx_lut = self._build_class_label_index(object_class_dict)
        
        # Construct the kd tree & data needed to lookup object associated with each point in the tree
        xy_array, self.obj_ids_array, self.class_indices_array = self._build_data_arrays(object_class_dict)
        self.kdtree = cKDTree(xy_array, tree_leaf_size)
        
        # Feedback about hover map being completed
        end_time = perf_counter()
        if print_feedback:
            print("  Finished! Took {:.0f} ms".format(1000 * (end_time - start_time)))
    
    # .................................................................................................................
    
    def _build_class_label_index(self, object_class_dict):
        
        index_to_class_lut = dict(enumerate(object_class_dict.keys()))
        class_to_index_lut = {each_value: each_key for each_key, each_value in index_to_class_lut.items()}
        
        return index_to_class_lut, class_to_index_lut
    
    # .................................................................................................................
    
    def _build_data_arrays(self, object_class_dict):
        
        # Allocate empty lists that we'll fill in a loop
        all_xy = []
        all_ids = []
        all_class_idxs = []
        
        # Gather arrays of object xy data and corresponding object ids (inefficiently!)
        # ... would be better to pre-allocate arrays, knowing the total samples from all objects
        # ... would also be nice to have some more efficient way to store repeated ids/class labels
        for each_class_label, each_obj_dict in object_class_dict.items():
            
            class_idx = self.class_to_idx_lut[each_class_label]
            for each_obj_id, each_obj in each_obj_dict.items():
                all_xy.append(each_obj.trail_xy)
                all_ids.append(np.full(each_obj.num_samples, each_obj_id))
                all_class_idxs.append(np.full(each_obj.num_samples, class_idx))
            
        # Convert list of arrays into single concatenated arrays
        xy_array = np.vstack(all_xy)
        id_array = np.hstack(all_ids)
        class_index_array = np.hstack(all_class_idxs)
        
        return xy_array, id_array, class_index_array
    
    # .................................................................................................................
    
    def closest_point(self, point_xy):
        
        # For clarity
        num_neighbours = 1
        
        # Find (only) the closest object
        closest_distance, closest_array_idx = self.kdtree.query(point_xy, num_neighbours)
        closest_object_id = self.obj_ids_array[closest_array_idx]
        closest_object_class_index = self.class_indices_array[closest_array_idx]
        
        # Get object label for easier use
        closest_object_class_label = self.index_to_class_lut[closest_object_class_index]
        
        return closest_distance, closest_object_id, closest_object_class_label
    
    # .................................................................................................................
    
    def within_radius(self, point_xy, radius):
        
        # Return all array indices within the target radius of the target point
        closest_array_indices = self.kdtree.query_ball_point(point_xy, radius, return_sorted = False)
        
        # Filter out repeated objects
        closest_object_ids_array = self.obj_ids_array[closest_array_indices]
        unique_obj_ids_array, unique_indices_array = np.unique(closest_object_ids_array, return_index = True)
        
        # Figure out the corresponding class labels for the closest (unique!) object ids
        unique_close_indices = np.array(closest_array_indices)[unique_indices_array]
        unique_obj_class_indexes_array = self.class_indices_array[unique_close_indices]
        unique_obj_class_labels = [self.index_to_class_lut[each_class_index] 
                                   for each_class_index in unique_obj_class_indexes_array]
        
        # Finally, combine object id and class labels into list of 2-tuples
        obj_id_label_tuple_list = list(zip(unique_obj_ids_array.tolist(), unique_obj_class_labels))
        
        return obj_id_label_tuple_list
    
    # .................................................................................................................
    # .................................................................................................................

    
# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

# .....................................................................................................................

def create_trail_frame_from_object_reconstruction(background_frame, object_list, use_outline_color = True):
    
    trail_frame = background_frame.copy()
    for each_obj in object_list:
        each_obj.draw_trail(trail_frame, use_outline_color = use_outline_color)
    
    return trail_frame

# .....................................................................................................................

def minimum_crop_box(pt1, pt2, minimum_distance, frame_size):
    
    # Don't do anything if the image is already big enough
    actual_distance = pt2 - pt1
    if actual_distance >= minimum_distance:
        return pt1, pt2
    
    # If we get here, we're rescaling
    scale_factor = minimum_distance / actual_distance
    mid_pt = (pt2 + pt1) / 2.0
    new_pt1 = (pt1 - mid_pt) * scale_factor + mid_pt
    new_pt2 = (pt2 - mid_pt) * scale_factor + mid_pt
    
    # Finally, make sure we prvent out-of-bounds indexing after resizing the points
    new_pt1 = int(np.clip(np.round(new_pt1), 0, frame_size - 1))
    new_pt2 = int(np.clip(np.round(new_pt2), 0, frame_size - 1))
    
    return new_pt1, new_pt2

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Demo

if __name__ == "__main__":
    pass

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap


