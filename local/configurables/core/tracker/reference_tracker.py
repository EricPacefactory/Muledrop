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

import numpy as np

from collections import deque

from local.configurables.configurable_template import Core_Configurable_Base
from local.lib.timekeeper_utils import format_datetime_string

# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes


class Reference_Tracker(Core_Configurable_Base):
    
    # .................................................................................................................
    
    def __init__(self, input_wh, file_dunder):
        
        super().__init__(input_wh, file_dunder = file_dunder)
        
        # Store id assignment objects
        self.vobj_id_manager = ID_Manager()
        self.tobj_id_manager = ID_Manager()
        
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
    
    def reset(self):
        raise NotImplementedError("Must implement a tracker reset()")
        
    # .................................................................................................................
    
    # MAY OVERRIDE (BUT NOT NECESSARY, BETTER TO INSTEAD OVERRIDE INTERNAL FUNCTION CALLS)
    # Should override: clear_dead_ids(), update_object_tracking(), apply_object_decay(), generate_new_objects()
    def run(self, detection_ref_list):
            
        # Grab time reference & snapshot data for convenience
        current_frame_index, current_time_sec, current_datetime = self.get_time_info()
        current_snapshot_metadata = self.get_snapshot_info()
        
        # Clear dead objects (from the previous iteration)
        self.clear_dead_ids()
        
        # Update object tracking data based on the new detection data
        unmatched_object_id_list, unmatched_detections_list = \
        self.update_object_tracking(detection_ref_list, 
                                    current_frame_index, current_time_sec, current_datetime,
                                    current_snapshot_metadata)
        
        # Apply object decay to determine which objects will be deleted on the next iteration
        dead_id_list = \
        self.apply_object_decay(unmatched_object_id_list, 
                                current_frame_index, current_time_sec, current_datetime,
                                current_snapshot_metadata)
        
        # Finally, generate any new objects for tracking & return the final tracked object dictionary
        tracked_object_dict, validation_object_dict = \
        self.generate_new_objects(unmatched_detections_list, 
                                  current_frame_index, current_time_sec, current_datetime,
                                  current_snapshot_metadata)
        
        # Finally, trigger the clean-up of long-lasting objects, which should be saved across multiple files
        elder_id_list = self.partition_elder_objects(tracked_object_dict, dead_id_list)
        
        '''
        STOPPED HERE
        - ALSO UPDATE OBJ METADATA TO SAVE PROPER START/END INDICES, SEPARATE FROM SNAPSHOT METADATA
        - THEN CLEAN UP ALL THE BG/OBJMD/SNAP SAVING LOAD/SAVE CONFIGS!
        '''
        
        return {"tracked_object_dict": tracked_object_dict, 
                "validation_object_dict": validation_object_dict,
                "dead_id_list": dead_id_list,
                "elder_id_list": elder_id_list}
    
    # .................................................................................................................
    
    # SHOULD OVERRIDE. Maintain i/o structure
    def clear_dead_ids(self):
        
        '''
        Function for removing dead object ids (based on previous iteration) from the object dictionaries
            - Should rely on internal variables for accessing object dictionaries
            - Should also rely on internal variables for accessing dead id lists
            - No return values!
        '''
        
        # Reference implementation does nothing
        
        return
    
    # .................................................................................................................
    
    # SHOULD OVERRIDE. Maintain i/o structure
    def update_object_tracking(self, detection_ref_list, 
                               current_frame_index, current_time_sec, current_datetime,
                               current_snapshot_metadata):
        
        '''
        Function for updating objects with detections that match up with existing data
            - Unmatched object ids should be returned for use in applying decay
            - Unmatched detections (objects in a list) should be returned for use in generating new objects
            - Neither return needs to be stored internally!
        '''
        
        # Reference performs no updates, passes all detections through
        unmatched_object_ids = []
        unmatched_detections = detection_ref_list[:]
        
        return unmatched_object_ids, unmatched_detections
    
    # .................................................................................................................
    
    # SHOULD OVERRIDE. Maintain i/o structure
    def apply_object_decay(self, unmatched_object_id_list, 
                           current_frame_index, current_time_sec, current_datetime,
                           current_snapshot_metadata):
        
        '''
        Function for getting rid of objects that didn't match up with detection data
            - Don't clear ids here!
            - Should return a list of dead ids, which can be used by following stages (e.g. object capture)
                 so that they know if objects are about to be removed and react accordingly
            - Implementation should also keep an internal copy of the dead id list, 
                 for use in clearing ids on the next run() iteration
        '''
        
        # Reference performs no tracking and therefore accumulates no objects for decay
        dead_id_list = []
        
        return dead_id_list
    
    # .................................................................................................................
    
    # SHOULD OVERRIDE. Maintain i/o structure
    def generate_new_objects(self, unmatched_detections_list, 
                             current_frame_index, current_time_sec, current_datetime,
                             current_snapshot_metadata):
        
        '''
        Function for creating new objects from unmatched detections from the current frame
            - Should return a finalized dictionary of tracked objects
            - Should also keep an internal copying of the output dictionary, since it can't be passed back to self
        '''
        
        tracked_object_dict = {}
        validation_object_dict = {}
        
        return tracked_object_dict, validation_object_dict
    
    # .................................................................................................................
    
    # MAY OVERRIDE
    def partition_elder_objects(self, tracked_object_dict, dead_id_list):
        
        '''
        Function for splitting up objects that last 'too long'
        Used to prevent infinite memory usage for objects that don't disappear. Ideally the
        results from this function should trigger object metadata saving!
        '''
        
        # Loop over all tracked objects and check for paritioning requests
        # (i.e. objects that are storing too much data and need to be split up)
        elder_id_list = []
        for each_id, each_obj in tracked_object_dict.items():
            
            # Don't count objects that are dying on this frame!
            if each_id in dead_id_list:
                continue
            
            # For living objects, check for partitioning
            needs_partition = each_obj.check_for_partition_request()
            if needs_partition:
                elder_id_list.append(each_id)
                
        return elder_id_list

    # .................................................................................................................
    # .................................................................................................................


# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////


class Reference_Trackable_Object:
    
    track_point_str = "center"
    match_with_speed = False
    max_samples = 5000
    
    # .................................................................................................................
    
    def __init__(self, nice_id, full_id, detection_object, current_snapshot_metadata,
                 current_frame_index, current_time_sec, current_datetime):
        
        # Assign id to this new object
        self.nice_id = None
        self.full_id = None
        
        # Store start timing info
        self.start_snapshot_metadata = current_snapshot_metadata.copy()
        self.start_frame_index = current_frame_index
        self.start_time_sec = current_time_sec
        self.start_datetime = current_datetime
        
        # Allotcate storage for timing info as of the last detection match
        self.last_match_snapshot_metadata = {}
        self.last_match_frame_index = current_frame_index
        self.last_match_time_sec = current_time_sec
        self.last_match_datetime = current_datetime
                
        # Allocate storage for single-value variables (i.e. no history)
        self.detection_classification = detection_object.detection_classification
        self.num_samples = 0
        self.num_validation_samples = 0
        self.partition_index = 1
        self._request_partition = False
        
        # Allocate storage for historical variables
        self.hull_history = deque([], maxlen = self.max_samples)
        self.width_history = deque([], maxlen = self.max_samples)
        self.height_history = deque([], maxlen = self.max_samples)
        self.fill_history = deque([], maxlen = self.max_samples)
        self.x_center_history = deque([], maxlen = self.max_samples)
        self.y_center_history = deque([], maxlen = self.max_samples)
        self.x_track_history = deque([], maxlen = self.max_samples)
        self.y_track_history = deque([], maxlen = self.max_samples)
        self.track_status_history = deque([], maxlen = self.max_samples)
        
        # Fill first data points
        self.update_id(nice_id, full_id)
        self.update_from_detection(detection_object, current_snapshot_metadata,
                                   current_frame_index, current_time_sec, current_datetime)
        
    # .................................................................................................................
    
    def __repr__(self):        
        return "{:.0f} samples @ ({:.3f}, {:.3f})".format(self.num_samples, self.x_track, self.y_track)
    
    # .................................................................................................................
    #%% Class functions
    
    @classmethod
    def set_max_samples(cls, max_samples):
        cls.max_samples = max_samples
        
    # .................................................................................................................
    
    @classmethod
    def set_tracking_point(cls, track_point_str):
        cls.track_point_str = track_point_str
        
    # .................................................................................................................
    
    @classmethod
    def set_matching_style(cls, match_with_speed):
        cls.match_with_speed = match_with_speed
    
    # .................................................................................................................
    #%% Updating functions
    
    def lifetime_sec(self, current_time_sec):
        return current_time_sec - self.start_time_sec
    
    # .................................................................................................................
    
    def match_decay_time_sec(self, current_time_sec):
        return current_time_sec - self.last_match_time_sec
    
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
    
    def update_from_detection(self, detection_object, current_snapshot_metadata,
                              current_frame_index, current_time_sec, current_datetime):
        
        '''
        Reference implementation does a one-to-one update using detection data directly. 
        Override this for fancier update procedures
        '''
        
        # Record match timing data, in case this is the last time we match up with something
        self._update_last_match_data(current_snapshot_metadata, 
                                     current_frame_index, current_time_sec, current_datetime)
        
        # Get detection data
        new_track_status = 1
        new_hull, new_x_cen, new_y_cen, new_w, new_h, new_fill = self.get_detection_parameters(detection_object)
        
        # Copy new data into object
        self.verbatim_update(new_hull, new_x_cen, new_y_cen, new_w, new_h, new_fill, new_track_status)
        
    # .................................................................................................................
        
    def update_from_self(self):
        self.empty_update()
        
    # .................................................................................................................
    
    def check_for_partition_request(self):
        self._request_partition = (self.num_samples >= self.max_samples)
        return self._request_partition
        
    # .................................................................................................................
    
    def get_track_coordinates(self, x_center, y_center, width, height):
        
        '''
        Function which returns different tracking co-ordinates, depending on tracking-point settings
        '''
        
        if self.track_point_str == "center":
            
            x_track = x_center
            y_track = y_center
            
        elif self.track_point_str == "base":
            
            x_track = x_center
            y_track = y_center + (height / 2)
        
        else:
            
            raise AttributeError("TRACKING ERROR: Unrecognized tracking point: {}!".format(self.track_point_str))
        
        return x_track, y_track
        
    # .................................................................................................................
    
    def get_detection_parameters(self, detection_object):
        
        '''
        Pull data from a detection object. 
        See the reference_detector.py for the reference detection object and it's available properties
        '''
        
        # Grab parameters out of the detection object
        new_hull = detection_object.hull
        new_x_cen = detection_object.x_center
        new_y_cen = detection_object.y_center
        new_w = detection_object.width
        new_h = detection_object.height
        new_fill = detection_object.fill
        
        return new_hull, new_x_cen, new_y_cen, new_w, new_h, new_fill
       
    # .................................................................................................................

    def verbatim_update(self, new_hull, new_x_cen, new_y_cen, new_w, new_h, new_fill, new_track_status = 1):
        
        '''
        Update object properties verbatim (i.e. take input data as final, no other processing)
        '''
        
        # Handle data partitioning
        if self._request_partition:
            self._partition()
            self._request_partition = False
        
        # Update sample count
        self.num_samples += 1
        
        # Update object outline
        self.hull_history.appendleft(new_hull)
        
        # Update centering position
        self.x_center_history.appendleft(new_x_cen)
        self.y_center_history.appendleft(new_y_cen)
        
        # Update positioning
        new_x_track, new_y_track = self.get_track_coordinates(new_x_cen, new_y_cen, new_w, new_h)
        self.x_track_history.appendleft(new_x_track)
        self.y_track_history.appendleft(new_y_track)
        
        # Update object sizing
        self.width_history.appendleft(new_w)
        self.height_history.appendleft(new_h)
        
        # Update secondary feature(s)
        self.fill_history.appendleft(new_fill)
        
        # Update tracking status (should be True/1 if we're matched to something, otherwise False/0)
        self.track_status_history.appendleft(new_track_status)
        
    # .................................................................................................................
    
    def empty_update(self):
        
        # Generate 'new' update values, which are just copies of existing data, since we have no other data source
        new_hull = self.hull
        new_x_cen = self.x_center
        new_y_cen = self.y_center
        new_w = self.width
        new_h = self.height
        new_fill = self.fill
        new_track_status = 0
        
        # Use existing update function to avoid duplicating tracking logic...
        self.verbatim_update(new_hull, new_x_cen, new_y_cen, new_w, new_h, new_fill, new_track_status)
    
    # .................................................................................................................
    
    def get_save_data(self, is_final = True):
        
        # Bundle tracking data together for clarity
        tracking_data_dict = self._get_tracking_data(is_final)
        timing_data_dict = self._get_timing_data(is_final)
        snapshot_data_dict = self._get_snapshot_data(is_final)
        
        # Calculate helpful additional metadata
        lifetime_sec = self.last_match_time_sec - self.start_time_sec
        
        # Generate json-friendly data to save
        save_data_dict = {"full_id": self.full_id,
                          "nice_id": self.nice_id,
                          "lifetime_sec": lifetime_sec,
                          "num_validation_samples": self.num_validation_samples,
                          "max_samples": self.max_samples,
                          "partition_index": self.partition_index,
                          "detection_class": self.detection_classification,
                          "is_final": is_final,
                          "snapshots": snapshot_data_dict,
                          "timing": timing_data_dict,
                          "tracking": tracking_data_dict}
        
        return save_data_dict
    
    # .................................................................................................................
    
    def _get_tracking_data(self, is_final = True):
        
        # If we're getting final data to save, back track to find out where the data was last 'good' (i.e. tracked)
        first_good_idx = 0
        if is_final:
            try:
                while self.track_status_history[first_good_idx] == 0:
                    first_good_idx += 1
            except IndexError:
                # Should be a rare event to not find a a first good index (implies all tracking data is bad)
                # This normally won't happen, since only tracked objects should be saved!
                # However, it is possible that a partitioned object could have tracking lost during partitioning,
                # which would cause the next partition to be all 'bad' data, causing this error!
                # In this case, just accept all bad data...
                first_good_idx = 0
        
        # Bundle tracking data together for clarity
        tracking_data_dict = {"tracking_point": self.track_point_str,
                              "sample_order": "newest_first",
                              "num_samples": self.num_samples - first_good_idx,
                              "num_decay_samples_removed": first_good_idx,
                              "warped": True,
                              "track_status": list(self.track_status_history)[first_good_idx:],
                              "x_track": list(self.x_track_history)[first_good_idx:],
                              "y_track": list(self.y_track_history)[first_good_idx:],
                              "width": list(self.width_history)[first_good_idx:],
                              "height": list(self.height_history)[first_good_idx:],
                              "fill": list(self.fill_history)[first_good_idx:],
                              "hull": [each_hull.tolist() for each_hull in self.hull_history][first_good_idx:]}
        
        return tracking_data_dict
    
    # .................................................................................................................
    
    def _get_timing_data(self, is_final = True):
        
        # Bundle timing data together, for clarity
        timing_data_dict = {"start_frame_index": self.start_frame_index,
                            "start_time_sec": self.start_time_sec,
                            "start_datetime_isoformat": format_datetime_string(self.start_datetime),
                            "last_frame_index": self.last_match_frame_index,
                            "last_time_sec": self.last_match_time_sec,
                            "last_datetime_isoformat": format_datetime_string(self.last_match_datetime)}
        
        return timing_data_dict
    
    # .................................................................................................................
    
    def _get_snapshot_data(self, is_final = True):
        
        snapshot_data_dict = {"start": self.start_snapshot_metadata,
                              "last": self.last_match_snapshot_metadata}
        
        return snapshot_data_dict
    
    # .................................................................................................................
    
    def _partition(self):
        
        ''' 
        Function for clearing out existing object data, without deleting the object
        Should be used to prevent infinite memory usage and/or loss of older data samples
        '''
        
        # Update partition indexing to indicate the data has been split
        self.partition_index += 1
        
        # Clear the history storage
        self.hull_history.clear()
        self.width_history.clear()
        self.height_history.clear()
        self.fill_history.clear()
        self.x_center_history.clear()
        self.y_center_history.clear()
        self.x_track_history.clear()
        self.y_track_history.clear()
        self.track_status_history.clear()
        
        # Reset the sample count, since we've just cleared everything!
        self.num_samples = 0
        
    # .................................................................................................................
        
    def _update_last_match_data(self, current_snapshot_metadata,
                                current_frame_index, current_time_sec, current_datetime):
        
        # Update the last match timing, since we've matched with a new detection
        self.last_match_snapshot_metadata = current_snapshot_metadata # .copy() ?
        self.last_match_frame_index = current_frame_index
        self.last_match_time_sec = current_time_sec
        self.last_match_datetime = current_datetime
        
    # .................................................................................................................
    #%% Postioning functions
    
    def x_delta(self, delta_weight = 1.0):
        
        ''' Calculate the change in x using the 2 most recent x-positions '''
        
        try:
            return (self.x_track_history[0] - self.x_track_history[1]) * delta_weight
        except IndexError:
            return 0
        
    # .................................................................................................................
    
    def y_delta(self, delta_weight = 1.0):
        
        ''' Calculate the change in y using the 2 most recent y-positions '''
        
        try:
            return (self.y_track_history[0] - self.y_track_history[1]) * delta_weight
        except IndexError:
            return 0
    
    # .................................................................................................................
    
    def x_dash(self):
        
        '''
        Function which returns the two most recent x positions as a line segment
        '''
        
        try:
            return (self.x_track_history[0], self.x_track_history[1])
        except IndexError:
            # Fails on first index, since we don't have any historical data!
            return (self.x_track_history[0], self.x_track_history[0])
    
    # .................................................................................................................
    
    def y_dash(self):
        
        '''
        Function which returns the two most recent y positions as a line segment
        '''
        
        try:
            return (self.y_track_history[0], self.y_track_history[1])
        except IndexError:
            # Fails on first index, since we don't have any historical data!
            return (self.y_track_history[0], self.y_track_history[0])
    
    # .................................................................................................................
    
    def xy_dash(self):
        return np.vstack((self.x_dash(), self.y_dash())).T
        
    # .................................................................................................................
    
    def x_match(self):
        
        ''' 
        Function for generating an x co-ordinate used to match objects to detections 
        Position will either by object x-center point or the x-center point plus the change in x-position,
        depending on whether match_with_speed is enabled
        '''
        
        return self.x_center + self.x_delta() if self.match_with_speed else self.x_center
    
    # .................................................................................................................
    
    def y_match(self):
        
        ''' 
        Function for generating a y co-ordinate used to match objects to detections 
        Position will either by object y-center point or the y-center point plus the change in y-position,
        depending on whether match_with_speed is enabled
        '''
        
        return self.y_center + self.y_delta() if self.match_with_speed else self.y_center
    
    # .................................................................................................................
    
    def xy_match(self):
        return np.float32((self.x_match(), self.y_match()))
    
    # .................................................................................................................
    #%% Properties
    
    # .................................................................................................................
    
    @property
    def hull(self):
        return self.hull_history[0]
    
    # .................................................................................................................
    
    @property
    def x_center(self):
        return self.x_center_history[0]
    
    # .................................................................................................................
    
    @property
    def y_center(self):
        return self.y_center_history[0]
    
    # .................................................................................................................
    
    @property
    def xy_center(self):
        return np.float32((self.x_center, self.y_center))
    
    # .................................................................................................................
    
    @property
    def x_track(self):
        return self.x_track_history[0]
    
    # .................................................................................................................
    
    @property
    def y_track(self):
        return self.y_track_history[0]
    
    # .................................................................................................................
    
    @property
    def xy_track(self):
        return np.float32((self.x_track, self.y_track))
    
    # .................................................................................................................
    
    @property
    def xy_track_history(self):
        return np.vstack((self.x_track_history, self.y_track_history)).T
    
    # .................................................................................................................
    
    @property
    def width(self):
        return self.width_history[0]
    
    # .................................................................................................................
    
    @property
    def height(self):
        return self.height_history[0]
    
    # .................................................................................................................
    
    @property
    def fill(self):
        return self.fill_history[0]
    
    # .................................................................................................................
    
    @property
    def track_status(self):
        return self.track_status_history[0]
    
    # .................................................................................................................
    
    @property
    def tl_br(self):
        '''
        if self.track_point_str == "center":
            
            half_width = self.width / 2
            half_height = self.height / 2
            
            tl = (self.x_center - half_width, self.y_center - half_height)
            br = (self.x_center + half_width, self.y_center + half_height)
            
        elif self.track_point_str == "base":
            
            half_width = self.width / 2
            half_height = self.height / 2
            
            tl = (self.x_center - half_width, self.y_center - half_height)
            br = (self.x_center + half_width, self.y_center)
        
        else:
            warning_msg = "TL_BR Error: Unrecognized tracking point ({})!".format(self.track_point_str)
            raise AttributeError(warning_msg)
        '''
        half_width = self.width / 2
        half_height = self.height / 2
        
        tl = (self.x_center - half_width, self.y_center - half_height)
        br = (self.x_center + half_width, self.y_center + half_height)
        
        return np.float32((tl, br))
    
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
        self.next_id_bank = None
        self.date_id = None
        
        self.reset()
        
    # .................................................................................................................
        
    def new_id(self, current_datetime):
        
        '''
        Function for returning object IDs with a date_id component to make them unique over time!
        IDs have the format:
            *yyyyddd
            
        Where * is the ID, yyyy is the current year and ddd is the current day-of-the-year
        '''
        
        # Record the year & day-of-year from the given datetime
        time_data = current_datetime.timetuple()
        prev_day_of_year = self.day_of_year
        new_day_of_year = time_data.tm_yday
        
        # If we reach a new day, reset the id bank and update the date id value for new objects
        if new_day_of_year != prev_day_of_year:
            self.reset()
            self.date_id = self._get_date_id(time_data.tm_year, new_day_of_year)
        
        # Get the 'nice' id based on the current id bank setting, then update the bank
        nice_id = self.next_id_bank
        full_id = (nice_id * 10000000) + self.date_id
        
        # Update the bank to point at the next ID
        self.next_id_bank += 1
        
        return nice_id, full_id
    
    # .................................................................................................................
    
    def reset(self):
        self.next_id_bank = self.ids_start_at
    
    # .................................................................................................................
    
    def _get_date_id(self, current_year, day_of_year):
        
        '''
        Function for creating a 'date id' to append to object ids, in order to make them unique
        Takes on the format of: 
            
            yyyyddd, 
            
        where yyyy is the year (ex. 2019) and ddd is the day-of-the-year (a number between 1 and 365)
        '''
        
        # Record new date information
        self.day_of_year = day_of_year
        self.year = current_year
        
        return (current_year * 1000) + day_of_year
        
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



    