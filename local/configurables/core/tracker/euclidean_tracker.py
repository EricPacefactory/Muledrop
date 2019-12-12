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

from local.configurables.core.tracker.reference_tracker import Reference_Tracker, Smoothed_Trackable_Object
   
from local.configurables.core.tracker._helper_functions import pair_objects_to_detections
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
        
        self.match_with_speed = \
        self.ctrl_spec.attach_toggle(
                "match_with_speed", 
                label = "Use Speed when Matching", 
                default_value = False,
                tooltip = "Future object positions will be predicted using previous velocity before trying to match")
        
        self.fallback_matching_algorithm = \
        self.ctrl_spec.attach_menu(
                "fallback_matching_algorithm",
                label = "Fallback Algorithm",
                default_value = "Greedy", 
                option_label_value_list = [("Greedy", "greedy"),
                                           ("Pathmin", "pathmin")],
                tooltip = ["Choose between algorithms for matching when a unique object-to-detection pairing doesn't exist",
                           "Greedy  - Chooses pairings on a shortest-distance-first basis. Fast, worse results",
                           "Pathmin - Chooses pairings which minimize the total squared-distance. Slow, better results",
                           "  (Rule-of-thumb: Only use Pathmin if there are never more than 5 objects/detections)"])
        
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
        
        self.track_point_str = \
        self.ctrl_spec.attach_menu(
                "track_point_str",
                label = "Tracking Point",
                default_value = "Center", 
                option_label_value_list = [("Center", "center"),
                                           ("Base", "base")],
                tooltip = "Set tracking point. Also affects how objects are matched to detections")
        
        self.track_history_samples = \
        self.ctrl_spec.attach_slider(
                "track_history_samples", 
                label = "Track History", 
                default_value = 10000,
                min_value = 3, max_value = 50000,
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
    
    def close(self, final_frame_index, final_epoch_ms, final_datetime):
        
        # List all active objects as dead, since we're closing...
        dead_id_list = list(self.tracked_object_dict.keys())
        
        return {"tracked_object_dict": self.tracked_object_dict,
                "validation_object_dict": self.validation_object_dict,
                "dead_id_list": dead_id_list}
        
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
        
        # Clear out tracked objects that haven't been matched to detections for a while
        for each_id in self.dead_tracked_id_list:
            del self.tracked_object_dict[each_id]
            
    # .................................................................................................................
            
    def _clear_dead_vobj(self):
        
        # Clear out validation objects that haven't been matched to detections for a while
        for each_id in self.dead_validation_id_list:
            del self.validation_object_dict[each_id]
    
    # .................................................................................................................
    
    def update_object_tracking(self, detection_ref_list, current_frame_index, current_epoch_ms, current_datetime):
        
        #print(detection_ref_list, self.tracked_object_dict)
        
        # Keep track of which IDs/indexs are available for matching
        unmatched_tobj_ids = [each_key for each_key in self.tracked_object_dict.keys()]
        unmatched_vobj_ids = [each_key for each_key in self.validation_object_dict.keys()]
        unmatched_det_idxs = [k for k, _ in enumerate(detection_ref_list)]
        
        # Perform predictive decay whenever a detection overlaps multiple tracked objects
        unmatched_tobj_ids, unmatched_det_idxs = \
        self._tobj_overlaps(unmatched_tobj_ids, unmatched_det_idxs, detection_ref_list,
                            current_frame_index, current_epoch_ms, current_datetime)
        
        # Match tracked objects first
        unmatched_tobj_ids, unmatched_det_idxs = \
        self._update_tobj_tracking(unmatched_tobj_ids, unmatched_det_idxs, detection_ref_list,
                                   current_frame_index, current_epoch_ms, current_datetime)
        
        # Use remaining detection data to try matching to validation objects
        unmatched_vobj_ids, unmatched_det_idxs = \
        self._update_vobj_tracking(unmatched_vobj_ids, unmatched_det_idxs, detection_ref_list,
                                   current_frame_index, current_epoch_ms, current_datetime)
        
        return (unmatched_tobj_ids, unmatched_vobj_ids), unmatched_det_idxs

    # .................................................................................................................
    
    def _tobj_overlaps(self, unmatched_tobj_ids, unmatched_detection_indexs, detection_ref_list,
                       current_frame_index, current_epoch_ms, current_datetime):
        
        ''' 
        Function which handles cases where a detection overlaps/encompasses two or more tracked objects
        Rather than assigning one object to the detection and leaving the other to decay, this function
        puts both objects into a decay state, but updates the decayed position based on the object momentum
        prior to decay. The detection is also removed from the matching pool (so it doesn't get assigned elsewhere).
        '''
        
        # Skip this step if propgation is turned off
        no_progatation = (self.overlap_propagation_weight < 0.0)
        if no_progatation:
            return unmatched_tobj_ids, unmatched_detection_indexs
        
        # Initialize variables used to track overlapping detection/objects
        unmatched_tobj_id_set = set(unmatched_tobj_ids)
        remove_tobj_ids_set = set()
        still_unmatched_det_idxs = []        
        
        # Check if any unmatched detection contains multiple tracked objects
        # (i.e. if the x/y tracking co-ord of multiple tracked objects fall inside the bounding box of a detection)
        for each_idx in unmatched_detection_indexs:
            
            # Get reference to detection and it's bounding box
            det_ref = detection_ref_list[each_idx]
            (det_x1, det_y1), (det_x2, det_y2) = det_ref.tl_br
            
            # Check if there is more than 1 object contained in the detection box
            contains_obj_ids = []
            for each_id in unmatched_tobj_id_set:
                obj_xcen, obj_ycen = self.tracked_object_dict[each_id].xy_center
                if (det_x1 < obj_xcen < det_x2) and (det_y1 < obj_ycen < det_y2):
                    contains_obj_ids.append(each_id)
            
            # If the detection contains one or no tracked objects, consider it 'still unmatched'
            no_obj_overlap = (len(contains_obj_ids) < 2)
            if no_obj_overlap:
                still_unmatched_det_idxs.append(each_idx)
                
            else:
                # If overlap exists, remove the objects from the unmatched list
                remove_tobj_ids_set.update(contains_obj_ids)
                unmatched_tobj_id_set = unmatched_tobj_id_set.difference(contains_obj_ids)
            
        # Propagate all removed objects forward in time (based on their momentum)
        for each_id in remove_tobj_ids_set:
            self.tracked_object_dict[each_id].update_from_self(self.overlap_propagation_weight)
        
        # Create 'still unmatched' tobj id list by removing the ids that were tagged for overlap
        still_unmatched_tobj_ids = list(unmatched_tobj_id_set)
        
        return still_unmatched_tobj_ids, still_unmatched_det_idxs

    # .................................................................................................................
    
    def _update_tobj_tracking(self, unmatched_tobj_ids, unmatched_detection_indexs, detection_ref_list,
                              current_frame_index, current_epoch_ms, current_datetime):
        
        '''
        Function which matches detections with existing tracked objects.
        - Matched detections are removed from the list for future checks
        - Unmatched objects update their tracking data based on their history
        '''        
        
        # Find the pairing between tracked object IDs and detection indices
        tobjid_detidx_match_list, still_unmatched_tobj_ids, still_unmatched_det_idxs = \
        pair_objects_to_detections(self.tracked_object_dict, unmatched_tobj_ids,
                                   detection_ref_list, unmatched_detection_indexs,
                                   self.max_match_range_x,
                                   self.max_match_range_y,
                                   self._fallback_match_function)
        
        # Update objects using detection data, based on the pairing results from above
        for each_tobj_id, each_det_idx in tobjid_detidx_match_list:
            
            # Grab object references for convenience
            tobj_ref = self.tracked_object_dict[each_tobj_id]
            det_ref = detection_ref_list[each_det_idx]
            
            # Update each object using the detection object data
            tobj_ref.update_from_detection(det_ref, current_frame_index, current_epoch_ms, current_datetime)
            
        # For remaining unmatched objects, perform an empty (i.e. copy existing data) update
        for each_id in still_unmatched_tobj_ids:
            self.tracked_object_dict[each_id].update_from_self()
            
        return still_unmatched_tobj_ids, still_unmatched_det_idxs
    
    # .................................................................................................................
    
    def _update_vobj_tracking(self, unmatched_vobj_ids, unmatched_detection_indexs, detection_ref_list,
                              current_frame_index, current_epoch_ms, current_datetime):
        
        '''
        Function which matches detections with existing validation objects.
        - Matched detections are removed from the list for future checks
        - Unmatched objects update their tracking data based on their history
        '''
    
        # Find the pairing between validation object IDs and detection indices
        vobjid_detidx_match_list, still_unmatched_vobj_ids, still_unmatched_det_idxs = \
        pair_objects_to_detections(self.validation_object_dict, unmatched_vobj_ids,
                                   detection_ref_list, unmatched_detection_indexs,
                                   self.max_match_range_x,
                                   self.max_match_range_y,
                                   self._fallback_match_function)
        
        # Update objects using detection data, based on the pairing results from above
        for each_vobj_id, each_det_idx in vobjid_detidx_match_list:
            
            # Grab object references for convenience
            vobj_ref = self.validation_object_dict[each_vobj_id]
            det_ref = detection_ref_list[each_det_idx]
            
            # Update each object using the detection object data
            vobj_ref.update_from_detection(det_ref, current_frame_index, current_epoch_ms, current_datetime)
            
        # For remaining unmatched objects, also perform an empty (i.e. copy existing data) update
        for each_id in still_unmatched_vobj_ids:
            self.validation_object_dict[each_id].update_from_self()
            
        return still_unmatched_vobj_ids, still_unmatched_det_idxs
    
    # .................................................................................................................
    
    def apply_object_decay(self, unmatched_object_id_list, 
                           current_frame_index, current_epoch_ms, current_datetime):
        
        # Result from update object tracking will be a tuple containing tobj/vobj id lists, so unpack for convenience
        unmatched_tobj_ids, unmatched_vobj_ids = unmatched_object_id_list
        
        # Apply decay to tracked & validation objects separately
        dead_tobj_id_list = self._decay_tobjs(unmatched_tobj_ids, current_epoch_ms, current_datetime)
        dead_vobj_id_list = self._decay_vobjs(unmatched_vobj_ids, current_epoch_ms, current_datetime)
        
        # Store internal copies, so we can access these on the next run() iteration
        self.dead_tracked_id_list = dead_tobj_id_list
        self.dead_validation_id_list = dead_vobj_id_list
        
        # Only return the tracked object dead list, since following stages (e.g. object metadata capture)
        # don't know about validation objects (they only exist for internal bookkeeping)
        return dead_tobj_id_list
    
    # .................................................................................................................
    
    def _decay_tobjs(self, unmatched_tobj_id_list, current_epoch_ms, current_datetime):
        
        dead_track_ids_list = []
        for each_id in unmatched_tobj_id_list:
            
            # Get object reference for convenience
            each_tobj = self.tracked_object_dict[each_id]
            
            # Check if the object decay timer is up, in which case it's a dead object
            unmatch_time = each_tobj.get_match_decay_time_ms(current_epoch_ms)
            if unmatch_time > self.track_decay_timeout_ms:
                dead_track_ids_list.append(each_id)
                continue
            
            # Any object in a decay zone is immediately dead (since it was unmatched)
            if self.enabled_edge_decay_zones and each_tobj.in_zones_list(self.edge_zones_list):
                dead_track_ids_list.append(each_id)
        
        return dead_track_ids_list
    
    # .................................................................................................................
    
    def _decay_vobjs(self, unmatched_vobj_id_list, current_epoch_ms, current_datetime):
        
        dead_validation_ids_list = []
        for each_id in unmatched_vobj_id_list:
            
            # Get object reference for convenience
            each_vobj = self.validation_object_dict[each_id]
            
            # Check if the object decay timer is up, in which case it's a dead object
            unmatch_time = each_vobj.get_match_decay_time_ms(current_epoch_ms)
            if unmatch_time > self.validation_decay_timeout_ms:
                dead_validation_ids_list.append(each_id)
                continue
            
            # Any object in a decay zone is immediately dead (since it was unmatched)
            if self.enabled_edge_decay_zones and each_vobj.in_zones_list(self.edge_zones_list):
                dead_validation_ids_list.append(each_id)
        
        return dead_validation_ids_list
    
    # .................................................................................................................
    
    def generate_new_decendent_objects(self, dead_id_list, current_frame_index, current_epoch_ms, current_datetime):
        
        '''
        Function for creating new objects from long-lived tracked objects
            - Intended to force saving of objects that have accumulated lots of data
            - Main concern is preventing infinite RAM usage for objects/detections that might be 'stuck'
            - Should return an updated copy of the dead_id_list (containing objects being removed)
            - Should also update internal tracked/validation dictionaries with new decendent objects!
        '''
        
        # Initialize output results
        decendent_id_list = []
        decendent_object_dict = {}
        
        # First figure out 
        for each_tobj_id, each_tobj in self.tracked_object_dict.items():
            
            # Get tracked object sample count, to see if we need to force it to save
            needs_decendent = each_tobj.is_out_of_storage_space()
            if not needs_decendent:
                continue
            
            # If we get here, we're creating a decendent object, so record the id
            decendent_id_list.append(each_tobj_id)
            
            # Get new tracked id for each decendent object
            new_nice_id, new_full_id = self.tobj_id_manager.new_id(current_datetime)
            new_decendent = each_tobj.create_decendent(new_nice_id, new_full_id, 
                                                       current_frame_index, current_epoch_ms, current_datetime)
            
            # Move decendent into the tracked object dictionary
            decendent_object_dict[new_full_id] = new_decendent
        
        # Update tracked object dictionary with decendents
        self.tracked_object_dict.update(decendent_object_dict)
        
        # Add decendent ids to the dead list
        updated_dead_id_list = dead_id_list + decendent_id_list
        self.dead_tracked_id_list = updated_dead_id_list
        
        return updated_dead_id_list
    
    # .................................................................................................................
    
    def generate_new_objects(self, unmatched_detection_index_list, detection_ref_list, 
                             current_frame_index, current_epoch_ms, current_datetime):
        
        # Generate new tracked objects based on time (lifetime of validation objects)
        self._generate_new_tobjs(current_frame_index, current_epoch_ms, current_datetime)
        
        # Generate new validation objects based on unmatched (leftover) detections
        self._generate_new_vobjs(unmatched_detection_index_list, detection_ref_list, 
                                 current_frame_index, current_epoch_ms, current_datetime)
        
        # Return a copy of the (final) tracked object dictionary, since this is passed as an output from run()
        return self.tracked_object_dict, self.validation_object_dict
    
    # .................................................................................................................
    
    def _generate_new_tobjs(self, current_frame_index, current_epoch_ms, current_datetime):
        
        promote_vobj_id_list = []
        for each_vobj_id, each_vobj in self.validation_object_dict.items():            
            
            # Get validation object timing variables
            match_decay_time = each_vobj.get_match_decay_time_ms(current_epoch_ms)
            lifetime_ms = each_vobj.get_lifetime_ms(current_epoch_ms)
            
            # Check if the validation object has lived long enough (and was recently matched to a detection)
            old_enough = (lifetime_ms > self.validation_time_ms)
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
    
    def _generate_new_vobjs(self, unmatched_detection_index_list, detection_ref_list,
                            current_frame_index, current_epoch_ms, current_datetime):
        
        # Generate new validation objects for all leftover detections
        for each_idx in unmatched_detection_index_list:
            
            # Get reference to detection object
            each_unmatched_detection = detection_ref_list[each_idx]
            
            # Create a new validation object using the given detection data
            new_nice_id, new_full_id = self.vobj_id_manager.new_id(current_datetime)
            new_validation_obj = Smoothed_Trackable_Object(new_nice_id, new_full_id,
                                                           each_unmatched_detection,
                                                           current_frame_index,
                                                           current_epoch_ms, 
                                                           current_datetime)
            
            # Store the new validation object
            self.validation_object_dict[new_full_id] = new_validation_obj
            
        return None
    
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
    current_epoch_ms = configurable_ref.current_epoch_ms
    
    # Grab dictionary of validation objects so we can draw them
    validation_object_dict = configurable_ref.validation_object_dict
    
    return _draw_objects_on_frame(validations_frame, validation_object_dict, 
                                  show_ids, show_outlines, show_bounding_boxes, show_trails, show_decay,
                                  current_epoch_ms,
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
    current_epoch_ms = configurable_ref.current_epoch_ms
    
    # Grab dictionary of tracked objects so we can draw them
    tracked_object_dict = configurable_ref.tracked_object_dict
    
    return _draw_objects_on_frame(tracked_frame, tracked_object_dict, 
                                  show_ids, show_outlines, show_bounding_boxes, show_trails, show_decay,
                                  current_epoch_ms,
                                  outline_color = (0, 255, 0), 
                                  box_color = (0, 255, 0))

# .....................................................................................................................
    
def _draw_objects_on_frame(display_frame, object_dict, 
                           show_ids, show_outlines, show_bounding_boxes, show_trails, show_decay,
                           current_epoch_ms, outline_color, box_color):
    
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
            match_delta = each_obj.get_match_decay_time_ms(current_epoch_ms)            
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
            xy_trail = np.int32(np.round(each_obj.xy_center_history * frame_wh))
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


