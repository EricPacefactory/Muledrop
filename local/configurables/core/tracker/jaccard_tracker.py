#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Dec 31 10:38:42 2019

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

from local.configurables.core.tracker.reference_tracker import Reference_Tracker, Reference_Trackable_Object


# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes


class Tracker_Stage(Reference_Tracker):
    
    # .................................................................................................................
    
    def __init__(self, cameras_folder_path, camera_select, input_wh):
        
        # Inherit reference functionality
        super().__init__(cameras_folder_path, camera_select, input_wh, file_dunder = __file__)
        
        # Allocate storage for helper variables/functions
        self._approximate_zero = 1 / 1000
        
        # .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  . Drawing Controls  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .
        
        self.edge_zones_list = \
        self.ctrl_spec.attach_drawing(
                "edge_zones_list",
                default_value = [[]],
                min_max_entities = None,
                min_max_points = (3, None),
                entity_type = "polygon",
                drawing_style = "zone")
        
        # .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  . Control Group 1 .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .
        
        self.ctrl_spec.new_control_group("Tracking Controls")
        
        self.validation_min_jaccard_index = \
        self.ctrl_spec.attach_slider(
                "validation_min_jaccard_index", 
                label = "Minimum Validation IoU", 
                default_value = 0.25,
                min_value = 0.0, max_value = 1.0, step_size = 0.01,
                zero_referenced = True,
                return_type = float,
                units = "percent",
                tooltip = "")
        
        self.track_min_jaccard_index = \
        self.ctrl_spec.attach_slider(
                "track_min_jaccard_index", 
                label = "Minimum Tracking IoU", 
                default_value = 0.15,
                min_value = 0.0, max_value = 1.0, step_size = 0.01,
                zero_referenced = True,
                return_type = float,
                units = "percent",
                tooltip = "")
        
        self.track_history_samples = \
        self.ctrl_spec.attach_slider(
                "track_history_samples", 
                label = "Track History", 
                default_value = 55000,
                min_value = 3, max_value = Reference_Trackable_Object.max_allowable_samples,
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
        
        # .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  . Control Group 2 .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .
        
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
                default_value = False,
                tooltip = "Hide/display object outlines (blobs)",
                save_with_config = False)
        
        self._show_bounding_boxes = \
        self.ctrl_spec.attach_toggle(
                "_show_bounding_boxes",
                label = "Show Bounding Boxes",
                default_value = True,
                tooltip = "Hide/display object bounding boxes",
                save_with_config = False)
        
        self._show_trails = \
        self.ctrl_spec.attach_toggle(
                "_show_trails",
                label = "Show Tracked Trails",
                default_value = True,
                tooltip = "Hide/display object trails",
                save_with_config = False)
    
    # .................................................................................................................
    
    def setup(self, variables_changed_dict):
        
        # Update the (smoothed) tracking class with new shared settings
        Reference_Trackable_Object.set_matching_style(match_with_speed = False)
        Reference_Trackable_Object.set_max_samples(self.track_history_samples)
    
    # .................................................................................................................
    
    def update_tracked_object_tracking(self, 
                                       tracked_object_dict, unmatched_tobj_ids, 
                                       detection_ref_dict, unmatched_detection_ids,
                                       current_frame_index, current_epoch_ms, current_datetime):
        
        # Match tracked objects using detections
        return self._update_obj_tracking(tracked_object_dict, unmatched_tobj_ids, 
                                         detection_ref_dict, unmatched_detection_ids,
                                         self.track_min_jaccard_index,
                                         current_frame_index, current_epoch_ms, current_datetime)
    
    # .................................................................................................................
    
    def update_validation_object_tracking(self,
                                          validation_object_dict, unmatched_vobj_ids, 
                                          detection_ref_dict, unmatched_detection_ids,
                                          current_frame_index, current_epoch_ms, current_datetime):
        
        # Match validation objects to remaining unmatched detections
        return self._update_obj_tracking(validation_object_dict, unmatched_vobj_ids,
                                         detection_ref_dict, unmatched_detection_ids, 
                                         self.validation_min_jaccard_index,
                                         current_frame_index, current_epoch_ms, current_datetime)
    
    # .................................................................................................................
    
    def _update_obj_tracking(self, object_dict, unmatched_object_ids_list,
                             detection_ref_dict, unmatched_detection_ids_list,
                             min_jaccard_index,
                             current_frame_index, current_epoch_ms, current_datetime):
        
        # Find the pairing between object IDs and detection indices
        objid_detid_match_list, still_unmatched_obj_ids, still_unmatched_det_ids = \
        pair_objects_to_detections(object_dict, unmatched_object_ids_list,
                                   detection_ref_dict, unmatched_detection_ids_list,
                                   min_jaccard_index)
        
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
            new_validation_obj = Reference_Trackable_Object(new_nice_id, new_full_id,
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

def calculate_jaccard_index(tlbr_a, tlbr_b):
    
    # Separate box co-ords for convenience
    (x1_a, y1_a), (x2_a, y2_a) = tlbr_a
    (x1_b, y1_b), (x2_b, y2_b) = tlbr_b
    
    # Get intersection box co-ords
    x1_i = max(x1_a, x1_b)
    y1_i = max(y1_a, y1_b)
    x2_i = min(x2_a, x2_b)
    y2_i = min(y2_a, y2_b)
    
    # If the box is reversed, we're done (no intersection)
    if x1_i > x2_i or y1_i > y2_i:
        return 0.0
    
    # If there's no intersection, we're done
    intersection_area = (x2_i - x1_i) * (y2_i - y1_i)
    if intersection_area < 0:
        return 0.0
    
    # Get the box widths/heights
    box_w_a = (x2_a - x1_a)
    box_h_a = (y2_a - y1_a)
    box_w_b = (x2_b - x1_b)
    box_h_b = (y2_b - y1_b)
    
    # Calculate the union area (i.e. the common area, but don't double count overlapping region)
    a_area = box_w_a * box_h_a
    b_area = box_w_b * box_h_b
    union_area = (a_area + b_area - intersection_area)
    
    # Avoid division by zero for boxes that don't overlap
    if union_area < 0.00001:
        return 0.0
    
    intersection_over_union = intersection_area / union_area
    
    return intersection_over_union

# .....................................................................................................................

def pair_objects_to_detections(object_ref_dict, pairable_obj_ids_list, 
                               detection_ref_dict, pairable_det_ids_list,
                               minimum_jaccard_index = 0.05):
    
    # Create lists of pairable objects & detections, so that we can rely on a fixed ordering!
    pobj_ref_list = [object_ref_dict[each_obj_id] for each_obj_id in pairable_obj_ids_list]
    pdet_ref_list = [detection_ref_dict[each_det_id] for each_det_id in pairable_det_ids_list]
    objid_detid_match_list = []
    
    # Bail if we have zero of either set since we won't be able to match anything
    num_objs = len(pobj_ref_list)
    num_dets = len(pdet_ref_list)
    if num_objs == 0 or num_dets == 0:
        return objid_detid_match_list, pairable_obj_ids_list, pairable_det_ids_list
    
    # First get all object & detection bounding boxes
    object_tlbrs = [each_obj.tl_br for each_obj in pobj_ref_list]
    detection_tlbrs = [each_detection.tl_br for each_detection in pdet_ref_list]
    
    # For each detection bounding box, get list of overlapping objects
    unmatched_obj_ids_set = set(pairable_obj_ids_list)
    unmatched_det_ids_set = set(pairable_det_ids_list)
    for each_det_idx, each_det_tlbr in enumerate(detection_tlbrs):
        jaccard_indices = [calculate_jaccard_index(each_det_tlbr, each_obj_tlbr) for each_obj_tlbr in object_tlbrs]
        
        # Find the best match (i.e. largest jaccard index), if present, otherwise add detection to unmatched listing
        best_match_obj_idx = np.argmax(jaccard_indices)
        best_match_jaccard = jaccard_indices[best_match_obj_idx]
        if best_match_jaccard > minimum_jaccard_index:
            
            # Convert list indexing into pairable object/detection ids values
            best_match_obj_id = pairable_obj_ids_list[best_match_obj_idx]
            best_match_det_id = pairable_det_ids_list[each_det_idx]
            
            # Store object/detection matching pairs and remove corresponding entries from the unmatched sets
            objid_detid_match_list.append((best_match_obj_id, best_match_det_id))
            unmatched_obj_ids_set.discard(best_match_obj_id)
            unmatched_det_ids_set.discard(best_match_det_id)
    
    # Convert unique sets of object/detection indices to lists for output
    unmatched_obj_ids_list = list(unmatched_obj_ids_set)
    unmatched_det_ids_list = list(unmatched_det_ids_set)    
    
    return objid_detid_match_list, unmatched_obj_ids_list, unmatched_det_ids_list

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Demo
    
if __name__ == "__main__":    
    
    pass

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap

# TODO
# - implement kalman filter for updating x/y position and assigning matches (instead of matching purely by IoU)
# - implement better pairing -> get rid of greedy matching approach!

