#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Mar  1 15:35:05 2020

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

from enum import IntEnum

from local.configurables.core.tracker.reference_tracker import Reference_Tracker, Reference_Trackable_Object

from local.configurables.core.tracker.euclidean_tracker import calculate_squared_distance_pairing_matrix
from local.configurables.core.tracker.euclidean_tracker import pair_objects_to_detections

from local.configurables.core.tracker._helper_functions import naive_object_detection_match
from local.configurables.core.tracker._helper_functions import greedy_object_detection_match
from local.configurables.core.tracker._helper_functions import minsum_object_detection_match

# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes


class Tracker_Stage(Reference_Tracker):
    
    # .................................................................................................................
    
    def __init__(self, input_wh):
        
        # Inherit reference functionality
        super().__init__(input_wh, file_dunder = __file__)
        
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
                min_value = 3, max_value = 100000,
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
        
        self.ctrl_spec.new_control_group("Smoothing Controls")
        
        self.smoothing_exponent = \
        self.ctrl_spec.attach_slider(
                "smoothing_exponent", 
                label = "Detection Smoothing Factor", 
                default_value = 2,
                min_value = -4, max_value = 4, step_size = 1,
                zero_referenced = False,
                return_type = int,
                units = "factor",
                tooltip = ["Smoothing factor. The larger this value, the more heavily detection data will",
                           "be smoothed. Large values are best suited for scenes with slow moving objects."])
        
        self.speed_x_decay = \
        self.ctrl_spec.attach_slider(
                "speed_x_decay", 
                label = "X Velocity Decay", 
                default_value = 0.65,
                min_value = 0.0, max_value = 1.00, step_size = 0.01,
                zero_referenced = True,
                return_type = float,
                units = "weighting",
                tooltip = ["When tracking is lost on an object, the existing speed of the tracked object",
                           "can be used to propagate the expected position of the object forward in time,",
                           "to hopefully better match up with the object position when tracking returns.",
                           "This parameter controls how quickly the propagation velocity",
                           "(in the x direction) is decayed over time."])
        
        self.speed_y_decay = \
        self.ctrl_spec.attach_slider(
                "speed_y_decay", 
                label = "Y Velocity Decay", 
                default_value = 0.65,
                min_value = 0.0, max_value = 1.00, step_size = 0.01,
                zero_referenced = True,
                return_type = float,
                units = "weighting",
                tooltip = ["When tracking is lost on an object, the existing speed of the tracked object",
                           "can be used to propagate the expected position of the object forward in time,",
                           "to hopefully better match up with the object position when tracking returns.",
                           "This parameter controls how quickly the propagation velocity",
                           "(in the y direction) is decayed over time."])
        
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
        
        return
    
    # .................................................................................................................
    
    def setup(self, variables_changed_dict):
        
        # Square decay parameters to create more inituitive scaling of the controls
        cubed_x_decay = (self.speed_x_decay ** 3)
        cubed_y_decay = (self.speed_y_decay ** 3)
        
        # Update the tracking class with new shared settings
        Kalman_Trackable_Object.set_smoothing_exponent(self.smoothing_exponent)
        Kalman_Trackable_Object.set_velocity_decay(cubed_x_decay, cubed_y_decay)
    
    # .................................................................................................................
    
    def update_tracked_object_tracking(self, 
                                       tracked_object_dict, unmatched_tobj_ids, 
                                       detection_ref_dict, unmatched_detection_ids,
                                       current_frame_index, current_epoch_ms, current_datetime):
        
        # Match existing tracked objects using detections
        tracked_object_dict, still_unmatched_tobj_ids, still_unmatched_det_ids = \
        self._update_obj_tracking(tracked_object_dict, unmatched_tobj_ids,
                                  detection_ref_dict, unmatched_detection_ids,
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
            if self.enabled_edge_decay_zones and each_obj.in_zones_list(self.edge_zones_list):
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
            new_validation_obj = Kalman_Trackable_Object(new_nice_id, new_full_id,
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
#%% Define Kalman resources


# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////


class Kalman_State_Order(IntEnum):
    x_L = 0
    x_R = 1
    y_T = 2
    y_B = 3
    vx = 4
    vy = 5


# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////


class Kalman_Position_Tracker:
    
    # .................................................................................................................
    
    def __init__(self, initial_x_left, initial_x_right, initial_y_top, initial_y_bottom,
                 smoothing_exponent = 0, vx_decay_factor = 0.5, vy_decay_factor = 0.5):
        
        # Set up the number of state & measurement variables used in the Kalman filter
        self._num_state_vars = len(Kalman_State_Order)
        self._num_measurement_vars = (self._num_state_vars - 2)     # state excluding vx/vy
        self._num_control_vars = 2                                  # vx & vy decay
        
        # Initialize a new kalman filter
        newk = cv2.KalmanFilter(self._num_state_vars, self._num_measurement_vars, self._num_control_vars)
        
        # Set update matrices
        newk = self._define_update_model(newk)
        newk = self._define_measurement_model(newk)
        newk = self._define_control_model(newk, vx_decay_factor, vy_decay_factor)
        newk = self._define_process_noise_covariance(newk)
        newk = self._define_measurement_noise_covariance(newk, smoothing_exponent)
        
        # Set initial state
        newk = self._set_initial_state(newk, initial_x_left, initial_x_right, initial_y_top, initial_y_bottom)
        
        # Store defined kalman filter for re-use!
        self._kfilter = newk
    
    # .................................................................................................................
    
    def _set_initial_state(self, kalman_ref, x_left, x_right, y_top, y_bottom, vx = 0, vy = 0):
        
        # Slightly awkward but flexible way of setting the initial state vector
        kalman_ref.statePost = np.empty((self._num_state_vars, 1), dtype = np.float32)
        kalman_ref.statePost[Kalman_State_Order.x_L] = x_left
        kalman_ref.statePost[Kalman_State_Order.x_R] = x_right
        kalman_ref.statePost[Kalman_State_Order.y_T] = y_top
        kalman_ref.statePost[Kalman_State_Order.y_B] = y_bottom
        kalman_ref.statePost[Kalman_State_Order.vx] = vx
        kalman_ref.statePost[Kalman_State_Order.vy] = vy
        
        # More efficient, but hard-coded
        #kalman_ref.statePost = np.float32((x_left, x_right, y_top, y_bottom, vx, vy))[:, np.newaxis]
        
        return kalman_ref
    
    # .................................................................................................................
    
    def update_from_measurements(self, x_left, x_right, y_top, y_bottom):
        
        # Convert to 'vector' for use in kalman equations
        measurement_array = np.empty((self._num_measurement_vars, 1), dtype = np.float32)
        measurement_array[Kalman_State_Order.x_L] = x_left
        measurement_array[Kalman_State_Order.x_R] = x_right
        measurement_array[Kalman_State_Order.y_T] = y_top
        measurement_array[Kalman_State_Order.y_B] = y_bottom
        
        # Predict newest state based on previous state and use newest measurements for correction
        self._kfilter.predict()
        self._kfilter.correct(measurement_array)
        
        return self.get_position_estimate()
    
    # .................................................................................................................
    
    def update_from_self(self):
        
        # Get current velocity to use as controls for applying velocity decay
        vx_decay = self._kfilter.statePost[Kalman_State_Order.vx]
        vy_decay = self._kfilter.statePost[Kalman_State_Order.vy]
        velo_decay_control_input = np.float32((vx_decay, vy_decay))
        
        # No measurement data, so perform prediction from previous state, with velocity decay control inputs
        self._kfilter.predict(velo_decay_control_input)
        
        return self.get_position_estimate()
        
    # .................................................................................................................
    
    def get_position_estimate(self):
        
        # For clarity
        curr_state = self._kfilter.statePost.squeeze()
        
        # Pull out x/y bounding box co-ordinates
        x_l = curr_state[Kalman_State_Order.x_L]
        x_r = curr_state[Kalman_State_Order.x_R]
        y_t = curr_state[Kalman_State_Order.y_T]
        y_b = curr_state[Kalman_State_Order.y_B]
        
        # Calculate x/y center point
        x_cen = (x_r + x_l) * 0.5
        y_cen = (y_t + y_b) * 0.5
        
        return x_cen, y_cen
    
    # .................................................................................................................
    
    def get_tlbr_estimate(self):
        
        # For clarity
        curr_state = self._kfilter.statePost.squeeze()
        
        # Pull out x/y bounding box co-ordinates
        x_l = curr_state[Kalman_State_Order.x_L]
        x_r = curr_state[Kalman_State_Order.x_R]
        y_t = curr_state[Kalman_State_Order.y_T]
        y_b = curr_state[Kalman_State_Order.y_B]
        
        return (x_l, y_t), (x_r, y_b)
    
    # .................................................................................................................

    def _define_update_model(self, kalman_ref):
        
        # For clarity
        kso = Kalman_State_Order        
        
        # Kalman model equations:
        # xl_1 = xl_0 + vx0 + proc noise
        # xr_1 = xr_0 + vx0 + proc noise
        # yt_1 = yt_0 + vy0 + proc noise
        # yb_1 = yb_0 + vy0 + proc noise
        # vx1 = vx0         + proc noise
        # vy1 = vy0         + proc noise
        
        # Create model matrix based on model update equations, starting with unity diagonal entries
        #   where state_new = A * state_old (A -> trans. matrix)
        transistion_matrix = np.eye(self._num_state_vars, dtype = np.float32)
        
        # Set x equations:
        transistion_matrix[kso.x_L, kso.vx] = 1.0
        transistion_matrix[kso.x_R, kso.vx] = 1.0
        
        # Set y equations:
        transistion_matrix[kso.y_T, kso.vy] = 1.0
        transistion_matrix[kso.y_B, kso.vy] = 1.0
        
        # Store final result
        kalman_ref.transitionMatrix = transistion_matrix
        
        return kalman_ref
    
    # .................................................................................................................

    def _define_measurement_model(self, kalman_ref):
        
        # Kalman measurement equations:
        # x_L = x_L_m
        # x_R = x_R_m
        # y_T = y_T_m
        # y_B = y_B_m
        
        # Create measurement matrix based on equations,
        #  where measure_new = H * state (H -> meas. matrix)
        #  (note: measurement should be 4 x 1 matrix, state is 6 x 1 matrix, so H is 4 x 6!)
        kalman_ref.measurementMatrix = np.eye(self._num_measurement_vars, self._num_state_vars, dtype = np.float32)
        
        return kalman_ref
    
    # .................................................................................................................
    
    def _define_control_model(self, kalman_ref, vx_decay, vy_decay):
        
        # For clarity
        kso = Kalman_State_Order
        
        # Kalman control model:
        # dx_L = 0
        # dx_R = 0
        # dy_T = 0
        # dy_B = 0
        # dvx = -decay_x * vx0
        # dvy = -decay_y * vy0        
        
        # Slightly hacky way to implement velocity decay when missing detections!
        # Will use control 'inputs' equal to the current velocities (vx0 & vy0)
        # So control matrix entries will simply be (negative) decay coefficients for vx/vy
        
        # Create empty control matrix
        #  where state_update_new = B * control_input (B -> control matrix)
        #  (note: state_update_new should be 6 x 1 matrix, control input is 2 x 1, so B is 6 x 2!)
        control_matrix = np.zeros((self._num_state_vars, self._num_control_vars), dtype = np.float32)
        
        # Enter vx/vy decay coefficients (0.0 = no decay, 1.0 = immediate decay)
        control_matrix[kso.vx, 0] = (-1.0 * vx_decay)
        control_matrix[kso.vy, 1] = (-1.0 * vy_decay)
        
        # Store final result
        kalman_ref.controlMatrix = control_matrix
        
        return kalman_ref
    
    # .................................................................................................................
    
    def _define_process_noise_covariance(self, kalman_ref):
        
        # For clarity
        kso = Kalman_State_Order
        
        # Start with unity covariance entries
        process_noise_cov = np.eye(self._num_state_vars, dtype = np.float32)
        
        # Set x left/right covariance
        process_noise_cov[kso.x_L, kso.x_R] = 0.55
        process_noise_cov[kso.x_R, kso.x_L] = 0.55
        
        # Set y top/bottom covariance
        process_noise_cov[kso.y_T, kso.y_B] = 0.55
        process_noise_cov[kso.y_B, kso.y_T] = 0.55
        
        # Store final result
        kalman_ref.processNoiseCov = process_noise_cov
        
        return kalman_ref
    
    # .................................................................................................................
    
    def _define_measurement_noise_covariance(self, kalman_ref, smoothing_exponent):
        
        # For clarity
        kso = Kalman_State_Order
        
        # Start with unity covariance entries
        scale_factor = np.float32(10 ** smoothing_exponent)
        measurement_noise_cov = scale_factor * np.eye(self._num_measurement_vars, dtype = np.float32)
        
        # Set x left/right covariance
        measurement_noise_cov[kso.x_L, kso.x_R] = scale_factor * 0.25
        measurement_noise_cov[kso.x_R, kso.x_L] = scale_factor * 0.25
        
        # Set y top/bottom covariance
        measurement_noise_cov[kso.y_T, kso.y_B] = scale_factor * 0.25
        measurement_noise_cov[kso.y_B, kso.y_T] = scale_factor * 0.25
        
        # Store final result
        kalman_ref.measurementNoiseCov = measurement_noise_cov
        
        return kalman_ref
    
    # .................................................................................................................
    # .................................................................................................................


# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////


class Kalman_Trackable_Object(Reference_Trackable_Object):
    
    # Set global parameters
    smoothing_exponent = 0
    vx_decay_factor = 0.5
    vy_decay_factor = 0.5
    
    # .................................................................................................................
    
    def __init__(self, nice_id, full_id, detection_object, current_frame_index, current_epoch_ms, current_datetime):
        
        # Get detection measurements for initial tracking state
        _, det_x_center, det_y_center, det_width, det_height = self.get_detection_parameters(detection_object)
        
        # Set up kalman filter for tracking        
        self._kalman_tracker = \
        Kalman_Position_Tracker(det_x_center, det_y_center, det_width, det_height, 
                                self.smoothing_exponent, self.vx_decay_factor, self.vy_decay_factor)
        
        # Inherit from reference object
        super().__init__(nice_id, full_id, detection_object, current_frame_index, current_epoch_ms, current_datetime)
    
    # .................................................................................................................
    
    @classmethod
    def set_smoothing_exponent(cls, smoothing_exponent):
        cls.smoothing_exponent = smoothing_exponent
    
    # .................................................................................................................
    
    @classmethod
    def set_velocity_decay(cls, vx_decay_factor, vy_decay_factor):
        cls.vx_decay_factor = vx_decay_factor
        cls.vy_decay_factor = vy_decay_factor
    
    # .................................................................................................................
        
    def update_from_detection(self, detection_object, current_frame_index, current_epoch_ms, current_datetime):
        
        '''
        Overrides reference implementation!
        Update using detection data through a kalman filter
        '''
        
        # Record match timing data, in case this is the last time we match up with something
        self._update_final_match_data(current_frame_index, current_epoch_ms, current_datetime)
        
        # Get detection data
        new_track_status = 1
        new_hull, new_xL, new_xR, new_yT, new_yB = self.get_detection_parameters(detection_object)
        
        # Run kalman filter & get state estimate
        est_x_cen, est_y_cen = self._kalman_tracker.update_from_measurements(new_xL, new_xR, new_yT, new_yB)
        
        # Directly add new data into object
        self.verbatim_update(new_hull, est_x_cen, est_y_cen, new_track_status)
        
    # .................................................................................................................
        
    def update_from_self(self):
        
        ''' 
        Overrides reference implementation!
        Update using kalman predictions only
        '''
        
        # Use kalman filter to propagate state forward without measurement data
        est_x_cen, est_y_cen = self._kalman_tracker.update_from_self()
        
        # Hard-code non-tracked properties
        new_hull = self.hull
        new_track_status = 0
        
        # Directly add 'new' predicted results into object
        self.verbatim_update(new_hull, est_x_cen, est_y_cen, new_track_status)
    
    # .................................................................................................................
    
    def get_detection_parameters(self, detection_object):
        
        '''
        Override from parent!
        See the reference_detector.py for the reference detection object and it's available properties
        '''
        
        # Grab parameters out of the detection object
        new_hull = detection_object.hull
        (x_L, y_T), (x_R, y_B) = detection_object.tl_br
        
        return new_hull, x_L, x_R, y_T, y_B
    
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


