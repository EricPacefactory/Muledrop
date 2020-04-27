#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Jun  3 10:08:46 2019

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

from collections import deque

from local.lib.common.timekeeper_utils import datetime_to_isoformat_string

from local.configurables.configurable_template import Core_Configurable_Base

# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes


class Reference_Tracker(Core_Configurable_Base):
    
    # .................................................................................................................
    
    def __init__(self, input_wh, file_dunder):
        
        super().__init__(input_wh, file_dunder = file_dunder)
        
        # Allocate storage for tracked objects
        self._tracked_object_dict = {}
        self._dead_tracked_id_list = []
        
        # Allocate storage for validation objects
        self._validation_object_dict = {}
        self._dead_validation_id_list = []
        
        # Store id assignment objects
        self.vobj_id_manager = ID_Manager()
        self.tobj_id_manager = ID_Manager()
        
        # Store frame sizing into the reference object for saving
        Reference_Trackable_Object.set_frame_wh(*input_wh)
        
        # !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
        #   Inherited classes must have __init__(input_wh) as arguments!
        # !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
        
        # For inherited classes, first call:
        # super().__init__(input_wh, file_dunder = __file__)
        
        # Then do any class-specific set up
        # ...
        # ...
        # ...
        
    # .................................................................................................................
    
    # MAY OVERRIDE
    def reset(self):
        
        # Clear out all stored tracking data, since the reset may cause jumps in time/break continuity
        self._tracked_object_dict = {}
        self._validation_object_dict = {}
        self._dead_tracked_id_list = []
        self._dead_validation_id_list = []
        
        # Reset ID assignments
        self.vobj_id_manager.reset()
        self.tobj_id_manager.reset()
        
        return
        
    # .................................................................................................................
    
    # MAY OVERRIDE. Maintain i/o structure
    def close(self, final_frame_index, final_epoch_ms, final_datetime):
        
        # List all active objects as dead, since we're closing...
        dead_id_list = list(self._tracked_object_dict.keys())
        
        return {"tracked_object_dict": self._tracked_object_dict,
                "validation_object_dict": self._validation_object_dict,
                "dead_id_list": dead_id_list}
    
    # .................................................................................................................
    
    # MAY OVERRIDE (BUT NOT NECESSARY, BETTER TO INSTEAD OVERRIDE INTERNAL FUNCTION CALLS)
    # Should override: clear_dead_ids(), update_object_tracking(), apply_object_decay(), generate_new_objects()
    def run(self, detection_ref_dict):
        
        # Grab time references for convenience
        fed_time_args = self.get_time_info()    # fed => frame_index, epoch_ms, datetime
        
        # Grab current tracking dictionaries & dead lists
        tobj_dict = self._tracked_object_dict
        vobj_dict = self._validation_object_dict
        dead_tobj_id_list = self._dead_tracked_id_list
        dead_vobj_id_list = self._dead_validation_id_list
        
        # Clear dead objects (from the previous iteration)
        tobj_dict, vobj_dict = self.clear_dead_ids(tobj_dict, vobj_dict, 
                                                   dead_tobj_id_list, dead_vobj_id_list)
        
        # Get lists of unmatched objects & detections
        unmatched_tobj_ids = list(tobj_dict.keys())
        unmatched_vobj_ids = list(vobj_dict.keys())
        unmatched_det_ids = list(detection_ref_dict.keys())
        
        # Update tracked objects first
        tobj_dict, still_unmatched_tobj_ids, still_unmatched_det_ids = \
        self.update_tracked_object_tracking(tobj_dict, unmatched_tobj_ids, 
                                            detection_ref_dict, unmatched_det_ids,
                                            *fed_time_args)
        
        # Then update validation objects with leftover detections
        vobj_dict, still_unmatched_vobj_ids, still_unmatched_det_ids = \
        self.update_validation_object_tracking(vobj_dict, unmatched_vobj_ids, 
                                               detection_ref_dict, still_unmatched_det_ids,
                                               *fed_time_args)
        
        # Apply object decay to tracked objects
        tobj_dict, dead_tobj_id_list = \
        self.apply_tracked_object_decay(tobj_dict, still_unmatched_tobj_ids, *fed_time_args)
        
        # Apply object decay to validation objects
        vobj_dict, dead_vobj_id_list = \
        self.apply_validation_object_decay(vobj_dict, still_unmatched_vobj_ids, *fed_time_args)
        
        # Add long-lived objects to dead list so that they get saved (protect RAM usage) and replace with new objects 
        tobj_dict, dead_tobj_id_list =  \
        self.generate_new_descendant_objects(tobj_dict, dead_tobj_id_list, *fed_time_args)
        
        # If needed, generate new tracked/validation objects
        tobj_dict, vobj_dict = self.generate_new_tracked_objects(tobj_dict, vobj_dict, *fed_time_args)
        vobj_dict = self.generate_new_validation_objects(vobj_dict, 
                                                         detection_ref_dict, still_unmatched_det_ids,
                                                         *fed_time_args)
        
        # Store tracking results & dying ids for the next iteration
        self._tracked_object_dict = tobj_dict
        self._validation_object_dict = vobj_dict
        self._dead_tracked_id_list = dead_tobj_id_list
        self._dead_validation_id_list = dead_vobj_id_list
        
        return {"tracked_object_dict": self._tracked_object_dict, 
                "validation_object_dict": self._validation_object_dict,
                "dead_id_list": self._dead_tracked_id_list}
    
    # .................................................................................................................
    
    # MAY OVERRIDE. Maintain i/o structure
    def clear_dead_ids(self, tracked_object_dict, validation_object_dict, 
                       dead_tracked_id_list, dead_validation_id_list):
        
        ''' 
        Function for removing dead object ids (based on previous iteration) from the object dictionaries 
            - Must return the updated tracked object dictionary
            - Must return the updated validation object dictionary
        '''
        
        # Clear out tracked objects that haven't been matched to detections for a while
        for each_tobj_id in dead_tracked_id_list:
            del tracked_object_dict[each_tobj_id]
        
        # Clear out validation objects that haven't been matched to detections for a while
        for each_vobj_id in dead_validation_id_list:
            del validation_object_dict[each_vobj_id]
        
        return tracked_object_dict, validation_object_dict
    
    # .................................................................................................................
    
    # SHOULD OVERRIDE. Maintain i/o structure
    def update_tracked_object_tracking(self, 
                                       tracked_object_dict, unmatched_tobj_ids, 
                                       detection_ref_dict, unmatched_detection_ids,
                                       current_frame_index, current_epoch_ms, current_datetime):
        
        '''
        Function which matches detections with existing tracked objects.
            - Must return the updated tracking object dictionary
            - Must return a list of remaining unmatched tracked objects (by id) 
            - Must return a list of unmatched detections (by id)
        '''
        
        # Reference implementation does not modify anything
        still_unmatched_tobj_ids = unmatched_tobj_ids
        still_unmatched_det_ids = unmatched_detection_ids
            
        return tracked_object_dict, still_unmatched_tobj_ids, still_unmatched_det_ids
    
    # .................................................................................................................
    
    # SHOULD OVERRIDE. Maintain i/o structure
    def update_validation_object_tracking(self,
                              validation_object_dict, unmatched_vobj_ids, 
                              detection_ref_dict, unmatched_detection_ids,
                              current_frame_index, current_epoch_ms, current_datetime):
        
        '''
        Function which matches detections with existing validation objects.
            - Must return the updated validation object dictionary
            - Must return a list of remaining unmatched tracked objects (by id) 
            - Must return a list of unmatched detections (by id)
        '''
        
        # Reference implementation does not modify anything
        still_unmatched_vobj_ids = unmatched_vobj_ids
        still_unmatched_det_ids = unmatched_detection_ids
        
        return validation_object_dict, still_unmatched_vobj_ids, still_unmatched_det_ids
    
    # .................................................................................................................
    
    # SHOULD OVERRIDE. Maintain i/o structure
    def apply_tracked_object_decay(self, tracked_object_dict, unmatched_tobj_id_list, 
                                   current_frame_index, current_epoch_ms, current_datetime):
        
        ''' 
        Function for applying decay to tracked objects. 
            - Must return the updated object dictionary
            - Must return a list of objects that need to be deleted on the next iteration (i.e. dead list)
        '''
        
        # Reference just kills all unmatched tracked objects immediately
        dead_tracked_id_list = unmatched_tobj_id_list
        
        return tracked_object_dict, dead_tracked_id_list
    
    # .................................................................................................................
    
    # SHOULD OVERRIDE. Maintain i/o structure
    def apply_validation_object_decay(self, validation_object_dict, unmatched_vobj_id_list, 
                                      current_frame_index, current_epoch_ms, current_datetime):
        
        ''' 
        Function for applying decay to validation objects. 
            - Must return the updated object dictionary
            - Must return a list of objects that need to be deleted on the next iteration (i.e. dead list)
        '''
        
        # Reference just kills all unmatched validation objects immediately
        dead_validation_ids_list = unmatched_vobj_id_list
        
        return validation_object_dict, dead_validation_ids_list
    
    # .................................................................................................................
    
    # MAY OVERRIDE. Maintain i/o structure
    def generate_new_descendant_objects(self, tracked_object_dict, dead_tracked_id_list, 
                                       current_frame_index, current_epoch_ms, current_datetime):
        
        '''
        Function for creating new objects from long-lived tracked objects
        Intended to force saving of objects that have accumulated lots of data
        Main concern is preventing infinite RAM usage for objects/detections that might be 'stuck'
            - Must return the updated tracked object dictionary
            - Must return the updated dead id list
        '''
        
        # Initialize output results
        ancestor_id_list = []
        descendant_object_dict = {}
        
        # Find all objects that are running out of storage and need to be decended
        for each_tobj_id, each_tobj in tracked_object_dict.items():
            
            # Get tracked object sample count, to see if we need to force it to save
            needs_descendant = each_tobj.is_out_of_storage_space()
            if not needs_descendant:
                continue
            
            # If we get here, we're creating a descendant object, so record the id
            ancestor_id_list.append(each_tobj_id)
            
            # Get new tracked id for each descendant object
            new_nice_id, new_full_id = self.tobj_id_manager.new_id(current_datetime)
            new_descendant = each_tobj.create_descendant(new_nice_id, new_full_id, 
                                                        current_frame_index, current_epoch_ms, current_datetime)
            
            # Move descendant into the tracked object dictionary
            descendant_object_dict[new_full_id] = new_descendant
        
        # Add new descendants to the tracked object dictionary
        tracked_object_dict.update(descendant_object_dict)
        
        # Add ancestor ids to the existing dead list so they are remove on the next iteration
        updated_dead_tracked_id_list = dead_tracked_id_list + ancestor_id_list
        
        return tracked_object_dict, updated_dead_tracked_id_list
    
    # .................................................................................................................
    
    # SHOULD OVERRIDE. Maintain i/o structure
    def generate_new_tracked_objects(self, tracked_object_dict, validation_object_dict, 
                                     current_frame_index, current_epoch_ms, current_datetime):
        
        '''
        Function for creating new tracked objects from validation objects
            - Must return an updated tracked object dictionary
            - Must return an updated validation object dictionary
        '''
        
        # Reference doesn't do anything
        
        return tracked_object_dict, validation_object_dict
    
    # .................................................................................................................
    
    # SHOULD OVERRIDE. Maintain i/o structure
    def generate_new_validation_objects(self, validation_object_dict, 
                                        detection_ref_dict, unmatched_detection_id_list,
                                        current_frame_index, current_epoch_ms, current_datetime):
        
        '''
        Function for creating new validation objects from unmatched detections
            - Must return an updated validation object dictionary
        '''
        
        # Reference doesn't do anything
        
        return validation_object_dict
    
    # .................................................................................................................
    
    # MAY OVERRIDE. Maintain i/o structure
    def promote_to_tracked_object(self, tracked_object_dict, validation_object_dict, validation_ids_to_promote_list,
                                  current_frame_index, current_epoch_ms, current_datetime):
        
        ''' 
        Function which moves validation objects to the tracked object dictionary
            - Must return the updated tracked object dictionary
            - Must return the updated validation object dictionary
        '''
        
        # Promote all validation objects, by id
        for each_vobj_id in validation_ids_to_promote_list:
        
            # Generate a new tracking id for the promoted validation object
            new_nice_id, new_full_id = self.tobj_id_manager.new_id(current_datetime)
            
            # Move object from validation dictionary to tracking ditionary and update it with the new tracking id
            tracked_object_dict[new_full_id] = validation_object_dict.pop(each_vobj_id)
            tracked_object_dict[new_full_id].update_id(new_nice_id, new_full_id)
        
        return tracked_object_dict, validation_object_dict
    
    # .................................................................................................................
    # .................................................................................................................


# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////


class Reference_Trackable_Object:
    
    frame_width = 1
    frame_height = 1
    match_with_speed = False
    max_samples = 55000
    
    # .................................................................................................................
    
    def __init__(self, nice_id, full_id, detection_object,
                 current_frame_index, current_epoch_ms, current_datetime):
        
        # Assign id to this new object
        self.nice_id = None
        self.full_id = None
        
        # Store start timing info
        self.first_frame_index = current_frame_index
        self.first_epoch_ms = current_epoch_ms
        self.first_datetime = current_datetime
        
        # Allotcate storage for timing info as of the last detection match
        self.final_match_frame_index = current_frame_index
        self.final_match_epoch_ms = current_epoch_ms
        self.final_match_datetime = current_datetime
        
        # Allocate storage for ancestry tracking (i.e. RAM protection for objects that last 'too long')
        self.ancestor_id = 0
        self.descendant_id = 0
        
        # Allocate storage for single-value variables (i.e. no history
        self.num_samples = 0
        self.num_validation_samples = 0
        
        # Allocate storage for real-time classification results (i.e. classification 'before the database')
        self.before_db_classification = {}
        
        # Allocate storage for historical variables
        self.hull_history = deque([], maxlen = self.max_samples)
        self.xy_center_history = deque([], maxlen = self.max_samples)
        self.track_status_history = deque([], maxlen = self.max_samples)
        
        # Initialize history data
        self.update_id(nice_id, full_id)
        self.update_from_detection(detection_object, current_frame_index, current_epoch_ms, current_datetime)
        
    # .................................................................................................................
    
    def __repr__(self):        
        return "{:.0f} samples @ ({:.3f}, {:.3f})".format(self.num_samples, *self.xy_center_tuple)
    
    # .................................................................................................................
    #%% Class functions
    
    @classmethod
    def set_max_samples(cls, max_samples):
        cls.max_samples = max_samples
        
    # .................................................................................................................
    
    @classmethod
    def set_matching_style(cls, match_with_speed):
        cls.match_with_speed = match_with_speed
    
    # .................................................................................................................
    
    @classmethod
    def set_frame_wh(cls, width, height):
        cls.frame_width = int(round(width))
        cls.frame_height = int(round(height))
    
    # .................................................................................................................
    #%% Updating functions
    
    def get_lifetime_ms(self, current_epoch_ms):
        ''' Function which returns the object's lifetime (in milliseconds) given the current epoch time '''
        return current_epoch_ms - self.first_epoch_ms
    
    # .................................................................................................................
    
    def get_match_decay_time_ms(self, current_epoch_ms):
        ''' Function which returns the object's match decay time (in milliseconds) given the current epoch time '''
        return current_epoch_ms - self.final_match_epoch_ms
    
    # .................................................................................................................
    
    def is_out_of_storage_space(self):
        ''' Function for checking if we've run out of storage space (i.e. about to overwrite old data) '''
        return (self.num_samples >= self.max_samples)
    
    # .................................................................................................................
    
    def create_descendant(self, new_nice_id, new_full_id, 
                         current_frame_index, current_epoch_ms, current_datetime):
        
        ''' 
        Function for creating new objects to carry on existing objects 
        which have lasted too long and need to be saved to protect RAM usage
        '''
        
        # Create new object of the same class
        new_descendant = self.__class__(new_nice_id, new_full_id, self,
                                        current_frame_index, current_epoch_ms, current_datetime)
        
        # Assign the existing object id as the ancestor to the new object and vice versa as a descendant
        new_descendant.set_ancestor_id(self.full_id)
        self.set_descendant_id(new_full_id)
        
        return new_descendant
        
    # .................................................................................................................
    
    def update_id(self, short_id, full_id):
        
        '''
        Function for altering an existing object ID. 
        Intended for use when converting an unvalidated object to validated status
        '''
        
        self.nice_id = short_id
        self.full_id = full_id
        
        self.num_validation_samples = self.num_samples
    
    # .................................................................................................................
    
    def set_ancestor_id(self, ancestor_id):
        
        ''' 
        Function for recording ids of objects that have lasted long enough to create new 
        (separately recorded) objects to protect RAM usage. This ID allows for potential historical lookup of objects
        '''
        
        self.ancestor_id = ancestor_id
        
    # .................................................................................................................
    
    def set_descendant_id(self, descendant_id):
        
        ''' 
        Sister function to the ancestor id assignment. 
        This function is used to record the id of a new object created from 'this' object
        '''
        
        self.descendant_id = descendant_id
    
    # .................................................................................................................
    
    def update_from_detection(self, detection_object, current_frame_index, current_epoch_ms, current_datetime):
        
        '''
        Reference implementation does a one-to-one update using detection data directly. 
        Override this for fancier update procedures
        '''
        
        # Record match timing data, in case this is the last time we match up with something
        self._update_final_match_data(current_frame_index, current_epoch_ms, current_datetime)
        
        # Get detection data
        new_track_status = 1
        new_hull_array, new_xy_cen_array = self.get_detection_parameters(detection_object)
        
        # Copy new data into object
        self.verbatim_update(new_hull_array, new_xy_cen_array, new_track_status)
        
    # .................................................................................................................
        
    def update_from_self(self, propagation_weight = -1.0):
        
        ''' Function which specifies how to update an object from it's own data (i.e. no detection available) '''
        
        use_propagation = (propagation_weight > 0.0)
        self.propagate_from_self(propagation_weight) if use_propagation else self.duplicate_from_self()
        
    # .................................................................................................................
    
    def get_detection_parameters(self, detection_object):
        
        '''
        Pull data from a detection object. 
        See the reference_detector.py for the reference detection object and it's available properties
        '''
        
        return detection_object.hull_array, detection_object.xy_center_array
       
    # .................................................................................................................

    def verbatim_update(self, new_hull_array, new_xy_center_array, new_track_status = 1):
        
        '''
        Update object properties verbatim (i.e. take input data as final, no other processing)
        '''
        
        # Update sample count
        self.num_samples += 1
        
        # Update object outline
        self.hull_history.append(new_hull_array)
        
        # Update centering position
        self.xy_center_history.append(new_xy_center_array)
        
        # Update tracking status (should be True/1 if we're matched to something, otherwise False/0)
        self.track_status_history.append(new_track_status)
        
    # .................................................................................................................
    
    def duplicate_from_self(self):
        
        # Generate 'new' update values, which are just copies of existing data, since we have no other data source
        new_hull_array = self.hull_array
        new_xy_cen_array = self.xy_center_array
        new_track_status = 0
        
        # Use existing update function to avoid duplicating tracking logic...
        self.verbatim_update(new_hull_array, new_xy_cen_array, new_track_status)
        
    # .................................................................................................................
        
    def propagate_from_self(self, weighting = 0.9, new_track_status = 0):
        
        ''' Function which propagates an objects trajectory, using it's own history '''
        
        # Get simple 'velocity' using previous two positions (better to look over a longer period...)
        vxy_array = self.xy_delta_array(weighting)
        
        # Generate 'new' update values, which are just copies of existing data, since we have no other data source
        new_hull_array = self.hull_array + vxy_array
        new_xy_cen_array = self.xy_center_array + vxy_array
        
        # Use existing update function to avoid duplicating tracking logic...
        self.verbatim_update(new_hull_array, new_xy_cen_array, new_track_status)
    
    # .................................................................................................................
    
    def get_object_save_data(self):
        
        # Calculate helpful additional metadata
        lifetime_ms = self.get_lifetime_ms(self.final_match_epoch_ms)
        is_final = (self.descendant_id == 0)
        
        # Bundle tracking data together for clarity
        tracking_data_dict, final_num_samples = self._get_tracking_data(is_final)
        
        # Hard-code an empty entry for 'after-database classification', which is meant to be filled in later
        # (after data has already entered the database)
        after_database_classification = {}
        
        # Generate json-friendly data to save
        save_data_dict = {"_id": self.full_id,
                          "full_id": self.full_id,
                          "nice_id": self.nice_id,
                          "ancestor_id": self.ancestor_id,
                          "descendant_id": self.descendant_id,
                          "is_final": is_final,
                          "num_samples": final_num_samples,
                          "max_samples": self.max_samples,
                          "first_frame_index": self.first_frame_index,
                          "first_epoch_ms": self.first_epoch_ms,
                          "first_datetime_isoformat": datetime_to_isoformat_string(self.first_datetime),
                          "final_frame_index": self.final_match_frame_index,
                          "final_epoch_ms": self.final_match_epoch_ms,
                          "final_datetime_isoformat": datetime_to_isoformat_string(self.final_match_datetime),
                          "lifetime_ms": lifetime_ms,
                          "bdb_classifier": self.before_db_classification,
                          "adb_classifier": after_database_classification,
                          "tracking": tracking_data_dict}
        
        return save_data_dict
    
    # .................................................................................................................
    
    def _get_tracking_data(self, is_final = True):
        
        # If we're getting final data to save, back track to find out where the data was last 'good' (i.e. tracked)
        last_good_rel_idx = -1
        if is_final:
            try:
                while self.track_status_history[last_good_rel_idx] == 0:
                    last_good_rel_idx -= 1
            except IndexError:
                # Should be a rare event to not find a last good index (implies all tracking data is bad)
                # This normally won't happen, since only tracked objects should be saved!
                # However, it is possible that a descendant object could have tracking lost during/after splitting,
                # which would cause the descendant to contain only 'bad' data, causing this error!
                # In this case, just accept all bad data...
                last_good_rel_idx = -1
        
        # Calculate the actual number of samples (ignoring bad data)
        final_num_samples = self.num_samples + last_good_rel_idx + 1
        num_decay_samples_removed = abs(last_good_rel_idx) - 1
        
        # Bundle tracking data together for clarity
        tracking_data_dict = {"num_validation_samples": self.num_validation_samples,
                              "num_decay_samples_removed": num_decay_samples_removed,
                              "frame_width": self.frame_width,
                              "frame_height": self.frame_height,
                              "track_status": list(self.track_status_history)[:final_num_samples],
                              "xy_center": self._deque_of_arrays_to_list(self.xy_center_history, final_num_samples),
                              "hull": self._deque_of_arrays_to_list(self.hull_history, final_num_samples)}
        
        return tracking_data_dict, final_num_samples
        
    # .................................................................................................................
        
    def _update_final_match_data(self, current_frame_index, current_epoch_ms, current_datetime):
        
        # Update the last match timing, since we've matched with a new detection
        self.final_match_frame_index = current_frame_index
        self.final_match_epoch_ms = current_epoch_ms
        self.final_match_datetime = current_datetime
    
    # .................................................................................................................
    
    @staticmethod
    def _deque_of_arrays_to_list(deque_of_arrays, final_sample_index):
        return [each_array.tolist() for each_array in deque_of_arrays][:final_sample_index]
        
    # .................................................................................................................
    #%% Postioning functions
    
    def xy_delta_array(self, delta_weight = 1.0):
        
        ''' Calculate the change in x/y using the 2 most recent xy-positions '''
        
        try:
            prev_xy_array = self.xy_center_history[-2]
            curr_xy_array = self.xy_center_history[-1]
            return curr_xy_array - prev_xy_array
        
        except IndexError:
            # Occurs on first run, when there is no 'previous' sample to use
            pass
        
        return np.float32((0.0, 0.0))
    
    # .................................................................................................................
    
    def xy_match_array(self):
        
        ''' 
        Function for generating a x/y co-ordinates used to match objects to detections 
        Position will either be the object center point 
        or the center point plus the change in position from the previous frame to the current one,
        depending on whether match_with_speed is enabled
        '''
        
        if self.match_with_speed:
            return self.xy_center_array + self.xy_delta_array()
        
        return self.xy_center_array 
    
    # .................................................................................................................
    
    def in_zones(self, zones_list):
        
        ''' Function which checks if this object is within a list of zones '''
        
        xy_center_tuple = self.xy_center_tuple
        for each_zone in zones_list:
            
            # If no zone data is present, then we aren't in the zone!
            if each_zone == []:
                return False
            
            # Otherwise, check if the x/y tracking location is inside any of the zones
            zone_array = np.float32(each_zone)
            in_zone = (cv2.pointPolygonTest(zone_array, xy_center_tuple, measureDist = False) > 0)
            if in_zone:
                return True
            
        return False
    
    # .................................................................................................................
    #%% Properties
    
    # .................................................................................................................
    
    @property
    def hull_array(self):
        return self.hull_history[-1]
    
    # .................................................................................................................
    
    @property
    def xy_center_tuple(self):
        return tuple(self.xy_center_history[-1].tolist())
    
    # .................................................................................................................
    
    @property
    def xy_center_array(self):
        return self.xy_center_history[-1]
    
    # .................................................................................................................
    
    @property
    def track_status(self):
        return self.track_status_history[-1]
    
    # .................................................................................................................
    
    @property
    def tl_br(self):
        
        hull_array = self.hull_array
        tl = np.min(hull_array, axis = 0)
        br = np.max(hull_array, axis = 0)
        
        return np.float32((tl, br))
    
    # .................................................................................................................
    # .................................................................................................................


# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////


class Smoothed_Trackable_Object(Reference_Trackable_Object):
    
    # Create shared smoothing variables
    _oldsmooth_xy = np.float32((0.0, 0.0))
    _newsmooth_xy = np.float32((1.0, 1.0))
    _speed_weight = 0.0
    
    # .................................................................................................................
    
    def __init__(self, nice_id, full_id, detection_object, current_frame_index, current_epoch_ms, current_datetime):
        
        # Inherit from reference object
        super().__init__(nice_id, full_id, detection_object, current_frame_index, current_epoch_ms, current_datetime)
        
    # .................................................................................................................
    
    @classmethod
    def set_smoothing_parameters(cls, x_weight, y_weight, speed_weight):
        
        # Map the maximum smoothing in x/y to 0.80, since higher values are not really practical
        max_smooth_x, max_smooth_y = 0.80, 0.80
        
        # Take the sqrt of the paremeters, which gives a slightly more intuitive feel to the scaling
        oldsmooth_x = (x_weight * max_smooth_x) ** (1/2)
        oldsmooth_y = (y_weight * max_smooth_y) ** (1/2)
        cls._oldsmooth_xy = np.float32((oldsmooth_x, oldsmooth_y))
        
        # Pre-calculate inverse smoothing values to avoid repeated calculations later
        cls._newsmooth_xy = np.float32((1.0, 1.0)) - cls._oldsmooth_xy
        
        # Update speed weighting
        cls._speed_weight = speed_weight
        
    # .................................................................................................................
        
    def update_from_detection(self, detection_object, current_frame_index, current_epoch_ms, current_datetime):
        
        '''
        Overrides reference implementation!
        Update using detection data directly, but then apply a smoothing pass after each update
        '''
        
        # Record match timing data, in case this is the last time we match up with something
        self._update_final_match_data(current_frame_index, current_epoch_ms, current_datetime)
        
        # Get detection data
        new_hull_array, new_xy_cen_array = self.get_detection_parameters(detection_object)
        
        # Apply smooth updates
        self.smooth_update(new_hull_array, new_xy_cen_array)
        
    # .................................................................................................................
    
    def smooth_update(self, new_hull_array, new_xy_cen_array):
        
        try:
            
            # Collect previous values
            old_xy_cen_array = self.xy_center_array
            
            # Calculate new (smoothed) values using new detection data and previous values
            smooth_xy_cen_array = self.smooth_xy(new_xy_cen_array, old_xy_cen_array)
        
        except IndexError:   
            # Will get an error on initial detection, since we don't have previous values needed for smoothing
            # When this happens, just perform verbatim update
            smooth_xy_cen_array = new_xy_cen_array
        
        # Update object state using smoothed values
        new_track_status = 1
        self.verbatim_update(new_hull_array, smooth_xy_cen_array, new_track_status)
    
    # .................................................................................................................
    
    def smooth_xy(self, new_xy_array, old_xy_array):
        predictive_xy = self.xy_delta_array() * self._speed_weight
        return (self._newsmooth_xy * new_xy_array) + (self._oldsmooth_xy * (old_xy_array + predictive_xy))
    
    # .................................................................................................................
    # .................................................................................................................


# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////


class ID_Manager:
    
    # .................................................................................................................
    
    def __init__(self, ids_start_at = 1):
        
        '''
        Object used to handle assignment of IDs to tracked objects
        '''
        
        self.ids_start_at = ids_start_at
        self.year = None
        self.day_of_year = None
        self.hour_of_day = None
        self.minute_of_hour = None
        self.next_id_bank = None
        self.date_id = None
        
        self.reset()
        
    # .................................................................................................................
        
    def new_id(self, current_datetime):
        
        '''
        Function for returning object IDs with a date_id component to make them unique over time!
        IDs have the format:
            yyyydddhhmm***
            
        Where *** is the ID, 
              yyyy is the current year, 
              ddd is the current day-of-the-year,
              hh is the current hour,
              mm is the current minute
        '''
        
        # Record the year & day-of-year from the given datetime
        time_data = current_datetime.timetuple()
        prev_minute_of_hour = self.minute_of_hour
        new_minute_of_hour = time_data.tm_min
        
        # Update the date id every minute
        if new_minute_of_hour != prev_minute_of_hour:
            self.reset()
            year_id = time_data.tm_year
            day_of_year_id = time_data.tm_yday
            hour_of_day_id = time_data.tm_hour
            self.date_id = self._get_date_id(year_id, day_of_year_id, hour_of_day_id, new_minute_of_hour)
        
        # Get the 'nice' id based on the current id bank setting, then update the bank
        nice_id = self.next_id_bank
        full_id = self.date_id + nice_id
        
        # Update the bank to point at the next ID
        self.next_id_bank += 1
        
        return nice_id, full_id
    
    # .................................................................................................................
    
    def reset(self):
        self.next_id_bank = self.ids_start_at
    
    # .................................................................................................................
    
    def _get_date_id(self, current_year, day_of_year, hour_of_day, minute_of_hour):
        
        '''
        Function for creating a 'date id' to append to object ids, in order to make them unique
        Takes on the format of: 
            
            yyyydddhhmm000
            
        where
          yyyy is the year (ex. 2019)
          ddd is the day-of-the-year (a number between 001 and 365)
          hh is the hour-of-the-day (a number between 00 and 23)
          mm is the minute-of-the-hour (a number between 00 and 60)
          000 is reserved space for object ids in the given year/day/hour/minute
        '''
        
        # Record new date information
        self.minute_of_hour = minute_of_hour
        self.hour_of_day = hour_of_day
        self.day_of_year = day_of_year
        self.year = current_year
        
        # Calculate offset numbers
        offset_year = current_year * 10000000000
        offset_doy =  day_of_year  * 10000000
        offset_hour = hour_of_day  * 100000
        offset_minute = minute_of_hour * 1000
        
        return offset_year + offset_doy + offset_hour + offset_minute
        
    # .................................................................................................................
    # .................................................................................................................
        
# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////

# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

# .....................................................................................................................

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Demo
    
if __name__ == "__main__":
    pass
    

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap



    