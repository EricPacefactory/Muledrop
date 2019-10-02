#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Jun  3 12:17:18 2019

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

from local.configurables.core.tracker.reference_tracker import Reference_Tracker, Reference_Trackable_Object
   
from local.configurables.core.tracker._helper_functions import update_objects_with_detections
from local.configurables.core.tracker._helper_functions import greedy_object_detection_match
from local.configurables.core.tracker._helper_functions import pathmin_object_detection_match

# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes


class Tracker_Stage(Reference_Tracker):
    
    # .................................................................................................................
    
    def __init__(self, input_wh):
        
        # Inherit reference functionality
        super().__init__(input_wh, file_dunder = __file__)
        
        # Allocate storage for tracked objects
        self.tracked_object_dict = {}
        self.dead_tracked_id_list = []
        
        # Allocate storage for validation objects
        self.validation_object_dict = {}
        self.dead_validation_id_list = []
        
        # Allocate storage for helper variables/functions
        self._approximate_zero = 1 / 1000
        
        # .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  . Control Group 1 .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .
        
        tg = self.controls_manager.new_control_group("Tracking Controls")
        
        self.match_with_speed = \
        tg.attach_toggle("match_with_speed", 
                         label = "Use Speed when Matching", 
                         default_value = False,
                         tooltip = "Future object positions will be predicted using previous velocity before trying to match")
        
        self.fallback_matching_algorithm = \
        tg.attach_menu("fallback_matching_algorithm",
                       label = "Fallback Algorithm",
                       default_value = "Greedy", 
                       option_label_value_list = [("Greedy", "greedy"),
                                                  ("Pathmin", "pathmin")],
                       tooltip = ["Choose between algorithms for matching when a unique object-to-detection pairing doesn't exist",
                                  "Greedy  - Chooses pairings on a shortest-distance-first basis. Fast, worse results",
                                  "Pathmin - Chooses pairings which minimize the total squared-distance. Slow, better results",
                                  "  (Rule-of-thumb: Only use Pathmin if there are never more than 5 objects/detections)"])
        
        self.max_match_range_x = \
        tg.attach_slider("max_match_range_x", 
                         label = "Maximum Match Range X", 
                         default_value = 0.10,
                         min_value = 0.0, max_value = 1.0, step_size = 1/100,
                         return_type = float,
                         units = "normalized",
                         tooltip = "Maximum range at which an object can be matched to a detection")
        
        self.max_match_range_y = \
        tg.attach_slider("max_match_range_y", 
                         label = "Maximum Match Range Y", 
                         default_value = 0.10,
                         min_value = 0.0, max_value = 1.0, step_size = 1/100,
                         return_type = float,
                         units = "normalized",
                         tooltip = "Maximum range at which an object can be matched to a detection in the y-direction")
        
        self.track_point_str = \
        tg.attach_menu("track_point_str",
                       label = "Tracking Point",
                       default_value = "Center", 
                       option_label_value_list = [("Center", "center"),
                                                  ("Base", "base")],
                       tooltip = "Set tracking point. Also affects how objects are matched to detections")
        
        self.track_history_samples = \
        tg.attach_slider("track_history_samples", 
                         label = "Track History", 
                         default_value = 9000,
                         min_value = 3, max_value = 10000,
                         zero_referenced = True,
                         return_type = int,
                         units = "samples",
                         tooltip = "Maximum number of tracking data samples to store",
                         visible = False)
        
        self.validation_time_sec = \
        tg.attach_slider("validation_time_sec", 
                         label = "Validation Time", 
                         default_value = 0.75,
                         min_value = 0.1, max_value = 15.0, step_size = 1/1000,
                         zero_referenced = True,
                         return_type = float,
                         units = "seconds",
                         tooltip = "Amount of time to wait before validation objects are considered tracked objects")
        
        self.validation_decay_timeout_sec = \
        tg.attach_slider("validation_decay_timeout_sec", 
                         label = "Validation Decay Timeout", 
                         default_value = 0.5,
                         min_value = 0.05, max_value = 15.0, step_size = 1/1000,
                         zero_referenced = True,
                         return_type = float,
                         units = "seconds",
                         tooltip = "Amount of time to wait before deleting a validation object that isn't matched with detection data")
        
        self.track_decay_timeout_sec = \
        tg.attach_slider("track_decay_timeout_sec", 
                         label = "Tracked Decay Timeout", 
                         default_value = 2.5,
                         min_value = 0.1, max_value = 15.0, step_size = 1/1000,
                         zero_referenced = True,
                         return_type = float,
                         units = "seconds",
                         tooltip = "Amount of time to wait before deleting a tracked object that isn't matched with detection data")
        
        # .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  . Control Group 2 .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .
        
        sg = self.controls_manager.new_control_group("Smoothing Controls")
        
        self.smooth_x = \
        sg.attach_slider("smooth_x", 
                         label = "X Position Smoothing", 
                         default_value = 3/5,
                         min_value = 0.0, max_value = 1.0, step_size = 1/5,
                         zero_referenced = True,
                         return_type = float,
                         units = "weighting",
                         tooltip = ["Amount of reliance on previous values of x when updating x position",
                                    "X position values (and bounding box widths) are updated using:",
                                    "    new_x = prev_x * (smooth_x) + detection_x * (1 - smooth_x)"])
        
        self.smooth_y = \
        sg.attach_slider("smooth_y", 
                         label = "Y Position Smoothing", 
                         default_value = 3/5,
                         min_value = 0.0, max_value = 1.0, step_size = 1/5,
                         zero_referenced = True,
                         return_type = float,
                         units = "weighting",
                         tooltip = ["Amount of reliance on previous values of y when updating y position.",
                                    "Y position values (and bounding box heights) are updated using:",
                                    "    new_y = prev_y * (smooth_y) + detection_y * (1 - smooth_y)"])
        self.smooth_speed = \
        sg.attach_slider("smooth_speed", 
                         label = "Predictive Smoothing", 
                         default_value = 1/10,
                         min_value = 0.0, max_value = 1.0, step_size = 1/10,
                         zero_referenced = True,
                         return_type = float,
                         units = "weighting",
                         tooltip = ["Amount of weighting given to predictive positioning updating.",
                                    "When this value is non-zero, 'previous values' are adjusted using the",
                                    "previous step (defined as the difference between previous 2 positions):",
                                    "    prev_pos = raw_prev_pos + (prev_step * predictive_smoothing)"])
        
        # .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  . Control Group 3 .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .
        
        dg = self.controls_manager.new_control_group("Drawing Controls")
        
        self._show_obj_ids = \
        dg.attach_toggle("_show_obj_ids",
                         label = "Show IDs",
                         default_value = False,
                         tooltip = "Hide/display object ID values",
                         save_with_config = False)
        
        self._show_decay = \
        dg.attach_toggle("_show_decay",
                         label = "Show Decaying Objects",
                         default_value = True,
                         tooltip = "Annotate objects that are not matched to detection data",
                         save_with_config = False)
        
        self._show_outlines = \
        dg.attach_toggle("_show_outlines",
                         label = "Show Outlines",
                         default_value = True,
                         tooltip = "Hide/display object outlines (blobs)",
                         save_with_config = False)
        
        self._show_bounding_boxes = \
        dg.attach_toggle("_show_bounding_boxes",
                         label = "Show Bounding Boxes",
                         default_value = False,
                         tooltip = "Hide/display object bounding boxes",
                         save_with_config = False)
        
        self._show_trails = \
        dg.attach_toggle("_show_trails",
                         label = "Show Tracked Trails",
                         default_value = True,
                         tooltip = "Hide/display object trails",
                         save_with_config = False)
        
    # .................................................................................................................
    
    def reset(self):
        
        # Clear out all stored tracking data, since the reset may cause jumps in time/break continuity
        self.tracked_object_dict = {}
        self.dead_tracked_id_list = []
        self.validation_object_dict = {}
        self.dead_validation_id_list = []
        
        # Reset ID assignments
        self.vobj_id_manager.reset()
        self.tobj_id_manager.reset()
        
    # .................................................................................................................
    
    def setup(self, variables_changed_dict):
        
        # Pick the appropriate fallback matching function for use when object-detection pairing isn't unique
        if self.fallback_matching_algorithm == "greedy":
            fallback_matching_func = greedy_object_detection_match
        elif self.fallback_matching_algorithm == "pathmin":
            fallback_matching_func = pathmin_object_detection_match
        else:
            raise NameError("Unrecognized fallback ({}) error with controls?".format(self.fallback_matching_algorithm))  
        self._fallback_match_function = fallback_matching_func
        
        # Update the (smoothed) tracking class with new shared settings
        Smoothed_Trackable_Object.set_tracking_point(self.track_point_str)
        Smoothed_Trackable_Object.set_matching_style(self.match_with_speed)
        Smoothed_Trackable_Object.set_max_samples(self.track_history_samples)
        Smoothed_Trackable_Object.set_smoothing_parameters(x_weight = self.smooth_x,
                                                           y_weight = self.smooth_y,
                                                           speed_weight = self.smooth_speed)
    
    # .................................................................................................................
    
    def clear_dead_ids(self):        
        self._clear_dead_tobj()
        self._clear_dead_vobj()
    
    # .................................................................................................................
    
    def _clear_dead_tobj(self):
        
        # Clear out tracked objects
        for each_id in self.dead_tracked_id_list:
            del self.tracked_object_dict[each_id]
            
    # .................................................................................................................
            
    def _clear_dead_vobj(self):
        
        # Clear out validation objects
        for each_id in self.dead_validation_id_list:
            del self.validation_object_dict[each_id]
    
    # .................................................................................................................
    
    def update_object_tracking(self, detection_ref_list, 
                               current_frame_index, current_time_sec, current_datetime,
                               current_snapshot_metadata):
        
        #print(detection_ref_list, self.tracked_object_dict)
        
        # Match already tracked objects first
        unmatched_tobj_ids, unumatched_detections = \
        self._update_tobj_tracking(detection_ref_list, current_snapshot_metadata,
                                   current_frame_index, current_time_sec, current_datetime)
        
        # Use any remaining detection data to try matching to current validation objects
        unmatched_vobj_ids, unumatched_leftovers = \
        self._update_vobj_tracking(unumatched_detections, current_snapshot_metadata,
                                   current_frame_index, current_time_sec, current_datetime)
        
        return (unmatched_tobj_ids, unmatched_vobj_ids), unumatched_leftovers

    # .................................................................................................................
    
    def _update_tobj_tracking(self, detection_ref_list, current_snapshot_metadata,
                              current_frame_index, current_time_sec, current_datetime):
        
        unmatched_tobj_ids, unmatched_detection_ref_list = \
        update_objects_with_detections(object_dict = self.tracked_object_dict, 
                                       detection_ref_list = detection_ref_list,
                                       fallback_function = self._fallback_match_function,
                                       max_match_x_dist = self.max_match_range_x,
                                       max_match_y_dist = self.max_match_range_y,
                                       current_snapshot_metadata = current_snapshot_metadata,
                                       current_frame_index = current_frame_index,
                                       current_time_sec = current_time_sec, 
                                       current_datetime = current_datetime)
        
        # For unmatched objects, also perform an empty (i.e. copy existing data) update
        for each_id in unmatched_tobj_ids:
            self.tracked_object_dict[each_id].update_from_self()
        
        return unmatched_tobj_ids, unmatched_detection_ref_list
    
    # .................................................................................................................
    
    def _update_vobj_tracking(self, unmatched_detections, current_snapshot_metadata,
                              current_frame_index, current_time_sec, current_datetime):
    
        unmatched_vobj_ids, unmatched_leftovers_ref_list = \
        update_objects_with_detections(object_dict = self.validation_object_dict, 
                                       detection_ref_list = unmatched_detections,
                                       fallback_function = self._fallback_match_function,
                                       max_match_x_dist = self.max_match_range_x,
                                       max_match_y_dist = self.max_match_range_y,
                                       current_snapshot_metadata = current_snapshot_metadata,
                                       current_frame_index = current_frame_index,
                                       current_time_sec = current_time_sec, 
                                       current_datetime = current_datetime)
        
        # For unmatched objects, also perform an empty (i.e. copy existing data) update
        for each_id in unmatched_vobj_ids:
            self.validation_object_dict[each_id].update_from_self()
        
        return unmatched_vobj_ids, unmatched_leftovers_ref_list
    
    # .................................................................................................................
    
    def apply_object_decay(self, unmatched_object_id_list, 
                           current_frame_index, current_time_sec, current_datetime,
                           current_snapshot_metadata):
        
        # Result from update object tracking will be a tuple containing tobj/vobj id lists, so unpack for convenience
        unmatched_tobj_ids, unmatched_vobj_ids = unmatched_object_id_list
        
        # Apply decay to tracked & validation objects separately
        dead_tobj_id_list = self._decay_tobjs(unmatched_tobj_ids, current_time_sec, current_datetime)
        dead_vobj_id_list = self._decay_vobjs(unmatched_vobj_ids, current_time_sec, current_datetime)
        
        # Store internal copies, so we can access these on the next run() iteration
        self.dead_tracked_id_list = dead_tobj_id_list
        self.dead_validation_id_list = dead_vobj_id_list
        
        # Only return the tracked object dead list, since following stages (e.g. rules) don't know about 
        # validation objects (they only exist for internal bookkeeping)
        return dead_tobj_id_list
    
    # .................................................................................................................
    
    def _decay_tobjs(self, unmatched_tobj_id_list, current_time_sec, current_datetime):
        
        dead_track_ids = []
        for each_id in unmatched_tobj_id_list:
            
            each_tobj = self.tracked_object_dict[each_id]
            unmatch_time = each_tobj.match_decay_time_sec(current_time_sec)
            if unmatch_time > self.track_decay_timeout_sec:
                dead_track_ids.append(each_id)
        
        return dead_track_ids
    
    # .................................................................................................................
    
    def _decay_vobjs(self, unmatched_vobj_id_list, current_time_sec, current_datetime):
        
        dead_validation_ids = []
        for each_id in unmatched_vobj_id_list:
            
            each_vobj = self.validation_object_dict[each_id]
            unmatch_time = each_vobj.match_decay_time_sec(current_time_sec)
            if unmatch_time > self.validation_decay_timeout_sec:
                dead_validation_ids.append(each_id)
        
        return dead_validation_ids
    
    # .................................................................................................................
    
    def generate_new_objects(self, unmatched_detections_list, 
                             current_frame_index, current_time_sec, current_datetime,
                             current_snapshot_metadata):
        
        # Generate new tracked objects based on time (lifetime of validation objects)
        self._generate_new_tobjs(current_frame_index, current_time_sec, current_datetime)
        
        # Generate new validation objects based on unmatched (leftover) detections
        self._generate_new_vobjs(unmatched_detections_list, 
                                 current_frame_index, current_time_sec, current_datetime,
                                 current_snapshot_metadata)
        
        # Return a copy of the (final) tracked object dictionary, since this is passed as an output from run()
        return self.tracked_object_dict, self.validation_object_dict
    
    # .................................................................................................................
    
    def _generate_new_tobjs(self, current_frame_index, current_time_sec, current_datetime):
        
        promote_vobj_id_list = []
        for each_vobj_id, each_vobj in self.validation_object_dict.items():            
            
            # Get validation object timing variables
            match_decay_time = each_vobj.match_decay_time_sec(current_time_sec)
            lifetime = each_vobj.lifetime_sec(current_time_sec)
            
            # Check if the validation object has lived long enough (and was recently matched to a detection)
            old_enough = (lifetime > self.validation_time_sec)
            has_matched = (match_decay_time < self._approximate_zero)
            if old_enough and has_matched:
                promote_vobj_id_list.append(each_vobj_id)
           
        # Now promote the validations up to tracked status by moving them into the tracked dictionary
        for each_vobj_id in promote_vobj_id_list:
            
            # Generate a new tracking id for each promoted validation object
            new_nice_id, new_full_id = self.tobj_id_manager.new_id(current_datetime)
            
            # Move object from validation dictionary to tracking ditionary and update it with the new tracking id
            self.tracked_object_dict[new_full_id] = self.validation_object_dict.pop(each_vobj_id)
            self.tracked_object_dict[new_full_id].update_id(new_nice_id, new_full_id)
            
        return None
    
    # .................................................................................................................
    
    def _generate_new_vobjs(self, unmatched_leftover_list, 
                            current_frame_index, current_time_sec, current_datetime,
                            current_snapshot_metadata):
        
        # Generate new validation objects for all leftover detections
        for each_idx, each_leftover_detection in enumerate(unmatched_leftover_list):
            
            # Create a new validation object using the given detection data
            new_nice_id, new_full_id = self.vobj_id_manager.new_id(current_datetime)
            new_pot_obj = Smoothed_Trackable_Object(new_nice_id, new_full_id,
                                                    each_leftover_detection,
                                                    current_snapshot_metadata,
                                                    current_frame_index,
                                                    current_time_sec, 
                                                    current_datetime)
            
            # Store the new validation object
            self.validation_object_dict[new_full_id] = new_pot_obj
            
        return None
    
    # .................................................................................................................
    # .................................................................................................................
    

# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////


class Smoothed_Trackable_Object(Reference_Trackable_Object):
    
    # Create shared smoothing variables
    _oldsmooth_x = 0.0
    _oldsmooth_y = 0.0
    _newsmooth_x = 1.0
    _newsmooth_y = 1.0
    _speed_weight = 0.0
    
    # .................................................................................................................
    
    def __init__(self, nice_id, full_id, detection_object, current_snapshot_metadata,
                 current_frame_index, current_time_sec, current_datetime):
        
        # Inherit from reference object
        super().__init__(nice_id, full_id, detection_object, current_snapshot_metadata,
                         current_frame_index, current_time_sec, current_datetime)
        
    # .................................................................................................................
    
    @classmethod
    def set_smoothing_parameters(cls, x_weight, y_weight, speed_weight):
        
        # Map the maximum smoothing in x/y to 0.80, since higher values are not really practical
        max_smooth_x, max_smooth_y = 0.80, 0.80
        
        # Take the sqrt of the paremeters, which gives a slightly more intuitive feel to the scaling
        cls._oldsmooth_x = (x_weight * max_smooth_x) ** (1/2)
        cls._oldsmooth_y = (y_weight * max_smooth_y) ** (1/2)
        
        # Pre-calculate inverse smoothing values to avoid repeated calculations later
        cls._newsmooth_x = 1 - cls._oldsmooth_x
        cls._newsmooth_y = 1 - cls._oldsmooth_y
        
        # Update speed weighting
        cls._speed_weight = speed_weight
        
    # .................................................................................................................
        
    def update_from_detection(self, detection_object, current_snapshot_metadata,
                              current_frame_index, current_time_sec, current_datetime):
        
        '''
        Overrides reference implementation!
        Update using detection data directly, but then apply a smoothing pass after each update
        '''
        
        # Record match timing data, in case this is the last time we match up with something
        self._update_last_match_data(current_snapshot_metadata, 
                                     current_frame_index, current_time_sec, current_datetime)
        
        # Get detection data
        new_hull, new_x_cen, new_y_cen, new_w, new_h, new_fill = self.get_detection_parameters(detection_object)
        
        # Apply smooth updates
        self.smooth_update(new_hull, new_x_cen, new_y_cen, new_w, new_h, new_fill)
        
    # .................................................................................................................
    
    def smooth_update(self, new_hull, new_x_cen, new_y_cen, new_w, new_h, new_fill):
        
        try:
            
            # Collect previous values
            old_x_cen = self.x_center
            old_y_cen = self.y_center
            old_w = self.width
            old_h = self.height
            
            # Calculate new (smoothed) values using new detection data and previous values
            smooth_x_cen = self.smooth_x(new_x_cen, old_x_cen)
            smooth_y_cen = self.smooth_y(new_y_cen, old_y_cen)
            smooth_w = self.smooth_w(new_w, old_w)
            smooth_h = self.smooth_h(new_h, old_h)
        
        except IndexError:   
            # Will get an error on initial detection, since we don't have previous values needed for smoothing
            # When this happens, just perform verbatim update
            smooth_x_cen = new_x_cen
            smooth_y_cen = new_y_cen
            smooth_w = new_w
            smooth_h = new_h
        
        # Update object state using smoothed values
        new_track_status = 1
        self.verbatim_update(new_hull, smooth_x_cen, smooth_y_cen, smooth_w, smooth_h, new_fill, new_track_status)
        
    # .................................................................................................................
    
    def smooth_x(self, new_x, old_x):
        predictive_x = self.x_delta() * self._speed_weight
        return self._newsmooth_x * new_x + self._oldsmooth_x * (old_x + predictive_x)
    
    # .................................................................................................................
    
    def smooth_y(self, new_y, old_y):
        predictive_y = self.y_delta() * self._speed_weight
        return self._newsmooth_y * new_y + self._oldsmooth_y * (old_y + predictive_y)
    
    # .................................................................................................................
    
    def smooth_w(self, new_w, old_w):
        return self._newsmooth_x * new_w + self._oldsmooth_x * old_w
    
    # .................................................................................................................
    
    def smooth_h(self, new_h, old_h):
        return self._newsmooth_y * new_h + self._oldsmooth_y * old_h
    
    # .................................................................................................................
    # .................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

# .....................................................................................................................

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Visualizations

def draw_validation_objects(stage_outputs, configurable_ref):
    
    # Grab a copy of the color image that we can draw on
    display_frame = stage_outputs["preprocessor"]["preprocessed_frame"]
    validations_frame = display_frame.copy()
    
    # Get display controls
    show_ids = configurable_ref._show_obj_ids
    show_outlines = configurable_ref._show_outlines
    show_bounding_boxes = configurable_ref._show_bounding_boxes
    show_trails = configurable_ref._show_trails
    show_decay = configurable_ref._show_decay
    current_time_sec = configurable_ref.current_time_sec
    
    # Grab dictionary of validation objects so we can draw them
    validation_object_dict = configurable_ref.validation_object_dict
    
    return _draw_objects_on_frame(validations_frame, validation_object_dict, 
                                  show_ids, show_outlines, show_bounding_boxes, show_trails, show_decay,
                                  current_time_sec,
                                  outline_color = (255, 0, 255), 
                                  box_color = (255, 0, 255))

# .....................................................................................................................

def draw_tracked_objects(stage_outputs, configurable_ref):
    
    # Grab a copy of the color image that we can draw on
    display_frame = stage_outputs["preprocessor"]["preprocessed_frame"]
    tracked_frame = display_frame.copy()
    
    # Get display controls
    show_ids = configurable_ref._show_obj_ids
    show_outlines = configurable_ref._show_outlines
    show_bounding_boxes = configurable_ref._show_bounding_boxes
    show_trails = configurable_ref._show_trails
    show_decay = configurable_ref._show_decay
    current_time_sec = configurable_ref.current_time_sec
    
    # Grab dictionary of tracked objects so we can draw them
    tracked_object_dict = configurable_ref.tracked_object_dict
    
    return _draw_objects_on_frame(tracked_frame, tracked_object_dict, 
                                  show_ids, show_outlines, show_bounding_boxes, show_trails, show_decay,
                                  current_time_sec,
                                  outline_color = (0, 255, 0), 
                                  box_color = (0, 255, 0))

# .....................................................................................................................
    
def _draw_objects_on_frame(display_frame, object_dict, 
                           show_ids, show_outlines, show_bounding_boxes, show_trails, show_decay,
                           current_time_sec, outline_color, box_color):
    
    # Set up some dimming colors for each drawing color, in case of decaying objects
    dim_ol_color = [np.mean(outline_color)] * 3
    dim_bx_color = [np.mean(outline_color)] * 3
    dim_tr_color = [np.mean(outline_color)] * 3
    
    # Record frame sizing so we can draw normalized co-ordinate locations
    frame_h, frame_w = display_frame.shape[0:2]
    frame_wh = np.array((frame_w - 1, frame_h - 1))
    
    for each_id, each_obj in object_dict.items():
        
        # Get object bbox co-ords for re-use
        tl, br = np.int32(np.round(each_obj.tl_br * frame_wh))
        tr = (br[0], tl[1])
        #bl = (tl[0], br[1])
        
        # Re-color objects that are decaying
        draw_ol_color = outline_color
        draw_bx_color = box_color
        draw_tr_color = (0, 255, 255)
        if show_decay:
            match_delta = each_obj.match_decay_time_sec(current_time_sec)            
            if match_delta > (1/100):
                draw_ol_color = dim_ol_color 
                draw_bx_color = dim_bx_color
                draw_tr_color = dim_tr_color
                
                # Show decay time
                cv2.putText(display_frame, "{:.3f}s".format(match_delta), tr,
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2, cv2.LINE_AA)
        
        # Show object outlines (i.e. blobs) if needed
        if show_outlines:
            obj_hull = np.int32(np.round(each_obj.hull * frame_wh))
            cv2.polylines(display_frame, [obj_hull], True, draw_ol_color, 1, cv2.LINE_AA)
        
        # Draw bounding boxes if needed
        if show_bounding_boxes:
            cv2.rectangle(display_frame, tuple(tl), tuple(br), draw_bx_color, 2, cv2.LINE_4)
        
        # Draw object trails
        if show_trails:
            xy_trail = np.int32(np.round(each_obj.xy_track_history * frame_wh))
            if len(xy_trail) > 5:
                cv2.polylines(display_frame, [xy_trail], False, draw_tr_color, 1, cv2.LINE_AA)
            
        # Draw object ids
        if show_ids:   
            nice_id = each_obj.nice_id # Remove day-of-year offset from object id for nicer display
            cv2.putText(display_frame, "{}".format(nice_id), tuple(tl),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
            
    return display_frame
    

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Demo
    
if __name__ == "__main__":    
    
    pass

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap


