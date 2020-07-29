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

import numpy as np

from local.configurables.core.tracker.reference_tracker import Reference_Tracker, Smoothed_Trackable_Object

from local.configurables.core.tracker._helper_functions import naive_object_detection_match
from local.configurables.core.tracker._helper_functions import greedy_object_detection_match
from local.configurables.core.tracker._helper_functions import minsum_object_detection_match


# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes


class Configurable(Reference_Tracker):
    
    # .................................................................................................................
    
    def __init__(self, location_select_folder_path, camera_select, input_wh):
        
        # Inherit reference functionality
        super().__init__(location_select_folder_path, camera_select, input_wh, file_dunder = __file__)
        
        # Allocate storage for helper variables/functions
        self._approximate_zero = 1 / 1000
        
        # .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  . Drawing Controls  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .
        
        self.edge_zones_list = \
        self.ctrl_spec.attach_drawing(
                "edge_zones_list",
                default_value = [[]],
                min_max_entities = (0, None),
                min_max_points = (3, None),
                entity_type = "polygon",
                drawing_style = "zone")
        
        # .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  . Control Group 1 .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .
        
        self.ctrl_spec.new_control_group("Tracking Controls")
        
        self.match_with_speed = \
        self.ctrl_spec.attach_toggle(
                "match_with_speed",
                label = "Use Speed when Matching",
                default_value = False,
                tooltip = "Future object positions will be predicted using previous velocity before trying to match")
        
        self.use_fast_fallback_matching = \
        self.ctrl_spec.attach_toggle(
                "use_fast_fallback_matching",
                label = "Fast Fallback Algorithm",
                default_value = True,
                tooltip = ["When a simple unique object-to-detection pairing doesn't exist,",
                           "this value controls the fallback algorithm used to determine a unique pairing.",
                           "When enabled a 'greedy' algorithm is used, which (unlike the slower algorithm)",
                           "does not take into account all possible pairings.",
                           "However, it is around ~10 times faster than the slower fallback."])
        
        self.max_match_range_x = \
        self.ctrl_spec.attach_slider(
                "max_match_range_x",
                label = "Maximum Match Range X",
                default_value = 0.10,
                min_value = 0.0, max_value = 1.0, step_size = 1/100,
                return_type = float,
                units = "normalized",
                tooltip = "Maximum range at which an object can be matched to a detection")
        
        self.max_match_range_y = \
        self.ctrl_spec.attach_slider(
                "max_match_range_y",
                label = "Maximum Match Range Y",
                default_value = 0.10,
                min_value = 0.0, max_value = 1.0, step_size = 1/100,
                return_type = float,
                units = "normalized",
                tooltip = "Maximum range at which an object can be matched to a detection in the y-direction")
        
        self.track_history_samples = \
        self.ctrl_spec.attach_slider(
                "track_history_samples",
                label = "Track History",
                default_value = 55000,
                min_value = 3, max_value = Smoothed_Trackable_Object.max_allowable_samples,
                zero_referenced = True,
                return_type = int,
                units = "samples",
                tooltip = "Maximum number of tracking data samples to store",
                visible = False)
        
        self.validation_time_ms = \
        self.ctrl_spec.attach_slider(
                "validation_time_ms",
                label = "Validation Time",
                default_value = 750,
                min_value = 100, max_value = 15000,
                zero_referenced = True,
                return_type = int,
                units = "milliseconds",
                tooltip = "Amount of time to wait before validation objects are considered tracked objects")
        
        self.validation_decay_timeout_ms = \
        self.ctrl_spec.attach_slider(
                "validation_decay_timeout_ms",
                label = "Validation Decay Timeout",
                default_value = 500,
                min_value = 50, max_value = 15000,
                zero_referenced = True,
                return_type = int,
                units = "milliseconds",
                tooltip = "Time to wait before deleting a validation object that isn't matched with a detection")
        
        self.track_decay_timeout_ms = \
        self.ctrl_spec.attach_slider(
                "track_decay_timeout_ms",
                label = "Tracked Decay Timeout",
                default_value = 2500,
                min_value = 100, max_value = 15000,
                zero_referenced = True,
                return_type = int,
                units = "milliseconds",
                tooltip = "Time to wait before deleting a tracked object that isn't matched with a detection")
        
        self.enabled_edge_decay_zones = \
        self.ctrl_spec.attach_toggle(
                "enabled_edge_decay_zones",
                label = "Enable decay zones",
                default_value = True,
                tooltip = ["If enabled, objects in (user drawn) decay zones will immediately decay if they",
                           "are not matched to a detection. These zones are intended to help remove objects",
                           "near edge boundaries."])
        
        self.overlap_propagation_weight = \
        self.ctrl_spec.attach_menu(
                "overlap_propagation_weight",
                label = "Overlap Propagation",
                default_value = "Off",
                option_label_value_list = [("Off", -1),
                                           ("Light", 0.9),
                                           ("Natural", 0.99),
                                           ("Aggressive", 1.02)],
                tooltip = ["This control enables special behaviour whenever a detection overlaps two or more",
                           "previously tracked objects. If enabled, the prior trajectory of the objects will",
                           "be used to propagate all object positions forward, as long as the overlap continues.",
                           "This is intended to prevent errors when objects cross paths."])
        
        # .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  . Control Group 2 .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .
        
        self.ctrl_spec.new_control_group("Smoothing Controls")
        
        self.smooth_x = \
        self.ctrl_spec.attach_slider(
                "smooth_x",
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
        self.ctrl_spec.attach_slider(
                "smooth_y",
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
        self.ctrl_spec.attach_slider(
                "smooth_speed",
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
        
        self.ctrl_spec.new_control_group("Display Controls")
        
        self._show_obj_ids = \
        self.ctrl_spec.attach_toggle(
                "_show_obj_ids",
                label = "Show IDs",
                default_value = False,
                tooltip = "Hide/display object ID values",
                save_with_config = False)
        
        self._show_decay = \
        self.ctrl_spec.attach_toggle(
                "_show_decay",
                label = "Show Decaying Objects",
                default_value = True,
                tooltip = "Annotate objects that are not matched to detection data",
                save_with_config = False)
        
        self._show_outlines = \
        self.ctrl_spec.attach_toggle(
                "_show_outlines",
                label = "Show Outlines",
                default_value = True,
                tooltip = "Hide/display object outlines (blobs)",
                save_with_config = False)
        
        self._show_bounding_boxes = \
        self.ctrl_spec.attach_toggle(
                "_show_bounding_boxes",
                label = "Show Bounding Boxes",
                default_value = False,
                tooltip = "Hide/display object bounding boxes",
                save_with_config = False)
        
        self._show_trails = \
        self.ctrl_spec.attach_toggle(
                "_show_trails",
                label = "Show Tracked Trails",
                default_value = True,
                tooltip = "Hide/display object trails",
                save_with_config = False)
        
        self._show_max_range_indicator = \
        self.ctrl_spec.attach_toggle(
                "_show_max_range_indicator",
                label = "Show Tracking Range Indicator",
                default_value = True,
                tooltip = "Hide/display the maximum tracking range indicator (ellipse following the mouse)",
                save_with_config = False)
    
    # .................................................................................................................
    
    def setup(self, variables_changed_dict):
        
        # Update the (smoothed) tracking class with new shared settings
        Smoothed_Trackable_Object.set_matching_style(self.match_with_speed)
        Smoothed_Trackable_Object.set_max_samples(self.track_history_samples)
        Smoothed_Trackable_Object.set_smoothing_parameters(x_weight = self.smooth_x,
                                                           y_weight = self.smooth_y,
                                                           speed_weight = self.smooth_speed)
    
    # .................................................................................................................
    
    def update_tracked_object_tracking(self,
                                       tracked_object_dict, unmatched_tobj_ids,
                                       detection_ref_dict, unmatched_detection_ids,
                                       current_frame_index, current_epoch_ms, current_datetime):
        
        # Perform predictive decay whenever a detection overlaps multiple tracked objects
        tracked_object_dict, still_unmatched_tobj_ids, still_unmatched_det_ids = \
        self._tobj_overlaps(tracked_object_dict, unmatched_tobj_ids, detection_ref_dict, unmatched_detection_ids)
        
        # Match remaining tracked objects using remaining detections
        tracked_object_dict, still_unmatched_tobj_ids, still_unmatched_det_ids = \
        self._update_obj_tracking(tracked_object_dict, still_unmatched_tobj_ids,
                                  detection_ref_dict, still_unmatched_det_ids,
                                  current_frame_index, current_epoch_ms, current_datetime)
        
        return tracked_object_dict, still_unmatched_tobj_ids, still_unmatched_det_ids
    
    # .................................................................................................................
    
    def update_validation_object_tracking(self,
                                          validation_object_dict, unmatched_vobj_ids,
                                          detection_ref_dict, unmatched_detection_ids,
                                          current_frame_index, current_epoch_ms, current_datetime):
        
        # Match validation objects to remaining unmatched detections
        return self._update_obj_tracking(validation_object_dict, unmatched_vobj_ids,
                                         detection_ref_dict, unmatched_detection_ids,
                                         current_frame_index, current_epoch_ms, current_datetime)

    # .................................................................................................................
    
    def _tobj_overlaps(self,
                       tracked_object_dict, unmatched_tobj_ids,
                       detection_ref_dict, unmatched_detection_ids):
        
        ''' 
        Function which handles cases where a detection overlaps/encompasses two or more tracked objects
        Rather than assigning one object to the detection and leaving the other to decay, this function
        puts both objects into a decay state, but updates the decayed position based on the object momentum
        prior to decay. The detection is also removed from the matching pool (so it doesn't get assigned elsewhere).
        '''
        
        # Skip this step if propagation is turned off
        no_propagation = (self.overlap_propagation_weight < 0.0)
        if no_propagation:
            return tracked_object_dict, unmatched_tobj_ids, unmatched_detection_ids
        
        # Initialize variables used to track overlapping detection/objects
        unmatched_tobj_id_set = set(unmatched_tobj_ids)
        remove_tobj_ids_set = set()
        still_unmatched_det_ids = []
        
        # Check if any unmatched detection contains multiple tracked objects
        # (i.e. if the x/y tracking co-ord of multiple tracked objects fall inside the bounding box of a detection)
        for each_det_id in unmatched_detection_ids:
            
            # Get reference to detection and it's bounding box
            det_ref = detection_ref_dict[each_det_id]
            (det_x1, det_y1), (det_x2, det_y2) = det_ref.tl_br
            
            # Check if there is more than 1 object contained in the detection box
            contains_obj_ids = []
            for each_tobj_id in unmatched_tobj_id_set:
                obj_xcen, obj_ycen = tracked_object_dict[each_tobj_id].xy_center_tuple
                if (det_x1 < obj_xcen < det_x2) and (det_y1 < obj_ycen < det_y2):
                    contains_obj_ids.append(each_tobj_id)
            
            # If the detection contains one or no tracked objects, consider it 'still unmatched'
            no_obj_overlap = (len(contains_obj_ids) < 2)
            if no_obj_overlap:
                still_unmatched_det_ids.append(each_det_id)
                
            else:
                # If overlap exists, remove the objects from the unmatched list
                remove_tobj_ids_set.update(contains_obj_ids)
                unmatched_tobj_id_set = unmatched_tobj_id_set.difference(contains_obj_ids)
            
        # Propagate all removed objects forward in time (based on their momentum)
        for each_tobj_id in remove_tobj_ids_set:
            tracked_object_dict[each_tobj_id].update_from_self(self.overlap_propagation_weight)
        
        # Create 'still unmatched' tobj id list by removing the ids that were tagged for overlap
        still_unmatched_tobj_ids = list(unmatched_tobj_id_set)
        
        return tracked_object_dict, still_unmatched_tobj_ids, still_unmatched_det_ids
    
    # .................................................................................................................
    
    def _update_obj_tracking(self, object_dict, unmatched_object_ids_list,
                             detection_ref_dict, unmatched_detection_ids_list,
                             current_frame_index, current_epoch_ms, current_datetime):
        
        # Find the pairing between validation object IDs and detection indices
        objid_detid_match_list, still_unmatched_obj_ids, still_unmatched_det_ids = \
        pair_objects_to_detections(object_dict, unmatched_object_ids_list,
                                   detection_ref_dict, unmatched_detection_ids_list,
                                   self.max_match_range_x,
                                   self.max_match_range_y,
                                   self.use_fast_fallback_matching)
        
        # Update objects using detection data, based on the pairing results from above
        for each_obj_id, each_det_id in objid_detid_match_list:
            
            # Grab object references for convenience
            obj_ref = object_dict[each_obj_id]
            det_ref = detection_ref_dict[each_det_id]
            
            # Update each object using the detection object data
            obj_ref.update_from_detection(det_ref, current_frame_index, current_epoch_ms, current_datetime)
        
        # For remaining unmatched objects, also perform an empty (i.e. copy existing data) update
        for each_obj_id in still_unmatched_obj_ids:
            object_dict[each_obj_id].update_from_self()
        
        return object_dict, still_unmatched_obj_ids, still_unmatched_det_ids
    
    # .................................................................................................................
    
    def apply_tracked_object_decay(self, tracked_object_dict, unmatched_tobj_ids_list,
                                   current_frame_index, current_epoch_ms, current_datetime):
        
        return self._decay_objs(tracked_object_dict, unmatched_tobj_ids_list,
                                self.track_decay_timeout_ms, current_epoch_ms)
    
    # .................................................................................................................
    
    def apply_validation_object_decay(self, validation_object_dict, unmatched_vobj_ids_list,
                                      current_frame_index, current_epoch_ms, current_datetime):
        
        return self._decay_objs(validation_object_dict, unmatched_vobj_ids_list,
                                self.validation_decay_timeout_ms, current_epoch_ms)
    
    # .................................................................................................................
    
    def _decay_objs(self, object_dict, unmatched_obj_ids_list, decay_timeout_ms, current_epoch_ms):
        
        # Loop over all unmatched object ids and check how long they've been unmatched
        # Add them to dead list if they've been unmatched 'too long' or if they're are in a decay zone
        dead_obj_ids_list = []
        for each_obj_id in unmatched_obj_ids_list:
            
            # Get object reference for convenience
            each_obj = object_dict[each_obj_id]
            
            # Check if the object decay timer is up, in which case it's a dead object
            unmatch_time = each_obj.get_match_decay_time_ms(current_epoch_ms)
            if unmatch_time > decay_timeout_ms:
                dead_obj_ids_list.append(each_obj_id)
                continue
            
            # Any object in a decay zone is immediately dead (since it was unmatched)
            if self.enabled_edge_decay_zones and each_obj.in_zones(self.edge_zones_list):
                dead_obj_ids_list.append(each_obj_id)
        
        return object_dict, dead_obj_ids_list
    
    # .................................................................................................................
    
    def generate_new_tracked_objects(self, tracked_object_dict, validation_object_dict,
                                     current_frame_index, current_epoch_ms, current_datetime):
        
        # Figure out which (if any) validation objects should be converted to tracked objects
        promote_vobj_ids_list = []
        for each_vobj_id, each_vobj in validation_object_dict.items():
            
            # Get validation object timing variables
            match_decay_time = each_vobj.get_match_decay_time_ms(current_epoch_ms)
            lifetime_ms = each_vobj.get_lifetime_ms(current_epoch_ms)
            
            # Check if the validation object has lived long enough (and was recently matched to a detection)
            old_enough = (lifetime_ms > self.validation_time_ms)
            has_matched = (match_decay_time < self._approximate_zero)
            if old_enough and has_matched:
                promote_vobj_ids_list.append(each_vobj_id)
           
        # Now promote the validations up to tracked status
        tracked_object_dict, validation_object_dict = \
        self.promote_to_tracked_object(tracked_object_dict, validation_object_dict, promote_vobj_ids_list,
                                       current_frame_index, current_epoch_ms, current_datetime)
        
        return tracked_object_dict, validation_object_dict
    
    # .................................................................................................................
    
    def generate_new_validation_objects(self, validation_object_dict,
                                        detection_ref_dict, unmatched_detection_ids_list,
                                        current_frame_index, current_epoch_ms, current_datetime):
        
        # Generate new validation objects for all leftover detections
        for each_det_id in unmatched_detection_ids_list:
            
            # Get reference to detection object
            each_unmatched_detection = detection_ref_dict[each_det_id]
            
            # Create a new validation object using the given detection data
            new_nice_id, new_full_id = self.vobj_id_manager.new_id(current_datetime)
            new_validation_obj = Smoothed_Trackable_Object(new_nice_id, new_full_id,
                                                           each_unmatched_detection,
                                                           current_frame_index,
                                                           current_epoch_ms,
                                                           current_datetime)
            
            # Store the new validation object
            validation_object_dict[new_full_id] = new_validation_obj
            
        return validation_object_dict
    
    # .................................................................................................................
    # .................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

# .....................................................................................................................

def calculate_squared_distance_pairing_matrix(row_entry_xy_tuple_list, col_entry_xy_tuple_list,
                                              x_scale = 1.0, y_scale = 1.0):
    
    '''
    Function which calculates the squared distance between each pair of row/col objects xys
    This function assumes xy values are given with the desired tracking point already
    (i.e. will not assume center/base tracking, that should be handled beforehand)
    Note that this function doesn't assume any units! Can be used with meters/pixels/normalized etc.
    For each row/col pairing, the calculation is given by:
        
        squared_distance = (x_scale * (row_x - col_x)) ^ 2 + (y_scale * (row_y - col_y)) ^ 2
        
    This returns a matrix with a format described below...
    
    *** Given ***
    row_entries = Objects: A, B, C, D, E
    col_entries = Detections: 1, 2, 3
    
    *** Matrix Format ***
    Entries (#) are calculated using the squared_distance formula above
    
          1    2    3
    
    A     #    #    #
    
    B     #    #    #
    
    C     #    #    #
    
    D     #    #    #
    
    E     #    #    #
    
    '''
    
    # Get number of rows & columns. Bail if either is zero
    num_rows = len(row_entry_xy_tuple_list)
    num_cols = len(col_entry_xy_tuple_list)
    if num_rows == 0 or num_cols == 0:
        return np.array(())
    
    # Convert to arrays and apply x/y dimensional scaling so we can get numpy to do all the heavy lifting
    row_xy_array = np.float32(row_entry_xy_tuple_list) * np.float32((x_scale, y_scale))
    col_xy_array = np.float32(col_entry_xy_tuple_list) * np.float32((x_scale, y_scale))
    
    # Calculate the x-difference between the row and column object locations
    row_x_array = row_xy_array[:, 0]
    col_x_array = col_xy_array[:, 0]
    delta_x = np.tile(row_x_array, (num_cols, 1)).T - np.tile(col_x_array, (num_rows, 1))
    
    # Calculate the y-difference between the row and column object locations
    row_y_array = row_xy_array[:, 1]
    col_y_array = col_xy_array[:, 1]
    delta_y = np.tile(row_y_array, (num_cols, 1)).T - np.tile(col_y_array, (num_rows, 1))
    
    # Square and sum the x/y distances to get our results!
    square_distance_matrix = np.square(delta_x) + np.square(delta_y)
    
    return square_distance_matrix

# .....................................................................................................................

def pair_objects_to_detections(object_ref_dict, pairable_obj_ids_list,
                               detection_ref_dict, pairable_det_ids_list,
                               max_match_x_dist, max_match_y_dist,
                               use_fast_fallback):
    
    # Create lists of pairable objects & detections, so that we can rely on a fixed ordering!
    pobj_ref_list = [object_ref_dict[each_obj_id] for each_obj_id in pairable_obj_ids_list]
    pdet_ref_list = [detection_ref_dict[each_det_id] for each_det_id in pairable_det_ids_list]
    objid_detid_match_list = []
    
    # Bail if we have zero of either set since we won't be able to match anything
    num_objs = len(pobj_ref_list)
    num_dets = len(pdet_ref_list)
    if num_objs == 0 or num_dets == 0:
        return objid_detid_match_list, pairable_obj_ids_list, pairable_det_ids_list
    
    # Calculate x/y scaling so that the distance matrix encodes max distances
    # (By scaling this way, we can say that objects that are within 0 < x (or y) < 1.0 are in matching range)
    x_scale = 1 / max_match_x_dist if max_match_x_dist > 0 else 1E10
    y_scale = 1 / max_match_y_dist if max_match_y_dist > 0 else 1E10
    
    # Get object/detection positioning for matching
    obj_xys = [each_obj.xy_match_array() for each_obj in pobj_ref_list]
    det_xys = [each_detection.xy_center_array for each_detection in pdet_ref_list]
    obj_det_sqdist_matrix = calculate_squared_distance_pairing_matrix(obj_xys, det_xys, x_scale, y_scale)
    
    # Try to find a unique mapping from (previous) objects to (current) detections
    unique_mapping, obj_det_idx_match_list, unmatched_objref_idx_list, unmatched_detref_idx_list = \
    naive_object_detection_match(obj_det_sqdist_matrix, max_allowable_cost = 1.0)
    
    # If the unique mapping failed, then try using a (slower) method that guarantees a unique pairing
    if not unique_mapping:
        
        # Retry the object-to-detection match using a slower approach that will generate unique pairings
        if use_fast_fallback:
            obj_det_idx_match_list, unmatched_objref_idx_list, unmatched_detref_idx_list = \
            greedy_object_detection_match(obj_det_sqdist_matrix, max_allowable_cost = 1.0)
        else:
            obj_det_idx_match_list, unmatched_objref_idx_list, unmatched_detref_idx_list = \
            minsum_object_detection_match(obj_det_sqdist_matrix, max_allowable_cost = 1.0)
    
    # Finally, convert matched/unmatched reference id values (which are relative to the pobj/pdet ref lists) 
    # back into their respective pairable id values
    unmatched_obj_ids_list = [pairable_obj_ids_list[each_ref_idx] for each_ref_idx in unmatched_objref_idx_list]
    unmatched_det_ids_list = [pairable_det_ids_list[each_ref_idx] for each_ref_idx in unmatched_detref_idx_list]
    for each_obj_ref_idx, each_det_ref_idx in obj_det_idx_match_list:
        converted_pair = (pairable_obj_ids_list[each_obj_ref_idx], pairable_det_ids_list[each_det_ref_idx])
        objid_detid_match_list.append(converted_pair)
    
    return objid_detid_match_list, unmatched_obj_ids_list, unmatched_det_ids_list

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Demo
    
if __name__ == "__main__":
    
    pass

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap


