#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Jun 27 16:43:51 2019

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

from local.configurables.configurable_template import Rule_Configurable_Base

from eolib.math.geometry import Fixed_Line_Cross, box_intersection

# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes

class Linecross_Rule(Rule_Configurable_Base):
    
    # .................................................................................................................
    
    def __init__(self, rule_name):
        
        super().__init__(rule_name = rule_name, file_dunder = __file__)
        
        # Allocate space for variables after setup
        self.line_box_tlbr = None
        self.line_obj = None
        
        # .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  . Control Group 2 .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .
        
        ag = self.controls_manager.new_control_group("General Controls")
        
        self.show_direction = \
        ag.attach_toggle("show_direction", 
                         label = "Show Direction", 
                         default_value = True,
                         tooltip = "")
        
        self.trigger_on_forward = \
        ag.attach_toggle("trigger_on_forward", 
                         label = "Forward Trigger Only", 
                         default_value = False,
                         tooltip = "")
        
        self.flip_orientation = \
        ag.attach_toggle("flip_orientation", 
                         label = "Flip Orientation", 
                         default_value = False,
                         tooltip = "")
        
        self.enter_thickness = \
        ag.attach_slider("enter_thickness", 
                         label = "Enter Thickness", 
                         default_value = 0.0,
                         min_value = 0.0,
                         max_value = 1.0,
                         step_size = 1/100,
                         return_type = float,
                         zero_referenced = True,
                         tooltip = "")
        
        self.exit_thickness = \
        ag.attach_slider("exit_thickness", 
                         label = "Exit Thickness", 
                         default_value = 0.0,
                         min_value = 0.0,
                         max_value = 1.0,
                         step_size = 1/100,
                         return_type = float,
                         zero_referenced = True,
                         tooltip = "")
        
        # .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  . Control Group 2 .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .
        
        bg = self.controls_manager.new_control_group("First Point Controls")
        
        self._pt1x = \
        bg.attach_slider("_pt1x", 
                         label = "Point 1 X", 
                         default_value = 0.42,
                         min_value = 0.0,
                         max_value = 1.0,
                         step_size = 1/100,
                         return_type = float,
                         zero_referenced = True,
                         tooltip = "")
        
        self._pt1y = \
        bg.attach_slider("_pt1y", 
                         label = "Point 1 Y", 
                         default_value = 0.76,
                         min_value = 0.0,
                         max_value = 1.0,
                         step_size = 1/100,
                         return_type = float,
                         zero_referenced = True,
                         tooltip = "")
        
        # .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  . Control Group 3 .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .
        
        cg = self.controls_manager.new_control_group("Second Point Controls")
        
        self._pt2x = \
        cg.attach_slider("_pt2x", 
                         label = "Point 2 X", 
                         default_value = 0.66,
                         min_value = 0.0,
                         max_value = 1.0,
                         step_size = 1/100,
                         return_type = float,
                         zero_referenced = True,
                         tooltip = "")
        
        self._pt2y = \
        cg.attach_slider("_pt2y", 
                         label = "Point 2 Y", 
                         default_value = 0.70,
                         min_value = 0.0,
                         max_value = 1.0,
                         step_size = 1/100,
                         return_type = float,
                         zero_referenced = True,
                         tooltip = "")

    # .................................................................................................................
    
    def reset(self):
        pass
    
    # .................................................................................................................
    
    def setup(self, values_changed_dict):
        
        # Bundle line points into convenient format
        line_pt1 = (self._pt1x, self._pt1y)
        line_pt2 = (self._pt2x, self._pt2y)
        line_def = np.float32((line_pt1, line_pt2))
        
        # Pre-calculate the bounding box of the line, which we'll use to help avoid unneccesary intersection checks
        self.line_box_tlbr = np.float32((np.min(line_def, axis = 0), np.max(line_def, axis = 0)))
        
        # Create the fast line check object, which is used to evaluate line cross events
        self.line_obj = Fixed_Line_Cross(line_pt1, line_pt2, self.flip_orientation)
        
    # .................................................................................................................

    def run(self, tracked_object_dict, dead_id_list,
            latest_snapshot_name, frames_since_snapshot):
        
        # Grab time reference for convenience
        current_frame_index, current_time_sec, current_datetime = self.get_time_info()
        
        # Figure out which objects we need to evaluate
        check_obj_id_list = self.which_objects_to_evaluate(tracked_object_dict, dead_id_list,
                                                           current_time_sec, current_datetime)
        
        # For each object (that we've deemed 'checkable'), evaluate the rule logic and record any violation metadata
        violation_list = []
        for each_obj_id in check_obj_id_list:
            obj_ref = tracked_object_dict[each_obj_id]
            new_violation_metadata, drawing_instructions = self.evaluate_rule(obj_ref, 
                                                                              current_time_sec, 
                                                                              current_datetime)
            
            # If violation data was generated, record it for further processing
            if new_violation_metadata:
                violation_list.append((each_obj_id, obj_ref.sample_count, new_violation_metadata, drawing_instructions))
        
        # Create full rule metadata, by combining event metadata with (standard) rule metadata
        rule_metadata_list = self.generate_rule_metadata_list(violation_list, current_time_sec, current_datetime,
                                                              latest_snapshot_name, frames_since_snapshot)
        
        # Figure out which objects we can stop checking
        self.clear_objects_for_evaluation(violation_list, dead_id_list,
                                          current_time_sec, current_datetime)
        
        return rule_metadata_list
    
    # .................................................................................................................
    
    def which_objects_to_evaluate(self, tracked_object_dict, dead_id_list,
                                  current_time_sec, current_datetime):
        
        '''
        Function for 'gating' objects that will be evaluated by the rule
        Can be used to disable checks on objects that have already violated the rule for example
        Or used to prevent checks on objects that haven't passed some initial checks (ex: minimum object lifetime)
        '''
        
        # By default, allow all objects
        all_ids = list(tracked_object_dict.keys())
        
        return all_ids
    
    # .................................................................................................................
    
    def clear_objects_for_evaluation(self, violation_list, dead_id_list,
                                     current_time_sec, current_datetime):
        
        '''
        Function for removing objects that were listed for evaluation
        '''
        
        pass
    
    # .................................................................................................................
    
    def evaluate_rule(self, object_ref, current_time_sec, current_datetime):
        
        '''
        Function for evaluating rule events
        For single-object rules, this function must output a dictionary whose keys are object ids which have violated
        the rule (on the current frame!), with values corresponding to event metadata
        '''
        
        # Initialize default outputs
        new_violation = {}
        drawing_instructions = None
        
        # First check if there is an overlap between object boxes and the line, otherwise there is no intersection
        obj_tlbr = object_ref.tl_br
        box_overlap = box_intersection(obj_tlbr, self.line_box_tlbr)
        if not box_overlap:
            return new_violation, drawing_instructions
        
        # If bounding boxes overlap, check for line intersection
        obj_xy_dash = object_ref.xy_dash()
        is_intersected, cross_direction, intersection_point = self.line_obj.intersection(*obj_xy_dash)
        
        # Record event data if an intersection occurs
        if is_intersected:
            
            # Handle directional trigger conditions (if needed)
            if self.trigger_on_forward and (cross_direction != "forward"):
                return new_violation, drawing_instructions
            
            # Get metadata for the rule cross event
            new_violation = self.build_instance_metadata(cross_direction, intersection_point)
            drawing_instructions = self.drawing_instructions_per_object(object_ref)
            
            #print(object_ref.nice_id, line_segment_intersection(obj_xy_dash, self.line_def), object_ref.sample_count)
            #print("({:.3f}, {:.3f})  /  ({:.3f}, {:.3f})".format(*obj_xy_dash[0], *obj_xy_dash[1]))
        
        return new_violation, drawing_instructions
    
    # .................................................................................................................
    
    def build_instance_metadata(self, cross_direction, intersection_point):
        
        instance_metadata = {"cross_direction": cross_direction,
                             "intersection_point": intersection_point.tolist()}
        
        return instance_metadata
    
    # .................................................................................................................
    
    def drawing_instructions_per_object(self, object_ref):
        # Nothing special is done for any objects breaking the rule, so just return the general drawing instructions
        return self.drawing_instructions()
    
    # .................................................................................................................
    
    def drawing_instructions(self):
        
        # Specify shared variables
        draw_color = (255, 0, 255)
        
        # Specify basic line
        line_spec = {"start_pt": tuple(self.line_obj.pt1),
                     "end_pt": tuple(self.line_obj.pt2),
                     "color": draw_color,
                     "thickness": 2,
                     "anchors": True,
                     "directional": self.show_direction}
        
        draw_spec = [("line", line_spec)]
        
        return draw_spec
    
    # .................................................................................................................
    
    # .................................................................................................................
    # .................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

# .................................................................................................................

# .................................................................................................................
# .................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Demo

if __name__ == "__main__":
    
    pass

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap



