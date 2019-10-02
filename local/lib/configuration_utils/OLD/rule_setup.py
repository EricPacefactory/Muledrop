#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Jun 19 16:36:35 2019

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
from functools import partial

from local.lib.file_access_utils.shared import configurable_dot_path, load_with_error_if_missing

from local.lib.file_access_utils.rules import build_rule_folder_path, build_rule_config_file_path, save_rule_config

from local.lib.configuration_utils.local_ui.local_video_loop import local_rule_config_video_loop
#from local.lib.configuration_utils.web_ui.web_video_loop import web_ruleconfig_video_loop

from eolib.utils.cli_tools import cli_confirm
from eolib.utils.function_helpers import dynamic_import_from_module
from eolib.utils.files import get_file_list

# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes


class Rule_Bundle:
    
    # .................................................................................................................
    
    def __init__(self, cameras_folder, camera_select, user_select, task_select):
        
        # Store pathing info
        self.cameras_folder = cameras_folder
        self.camera_select = camera_select
        self.user_select = user_select
        self.task_select = task_select
        
        # First make sure we have pathing to the rule configs folder
        self.rule_folder_path = build_rule_folder_path(cameras_folder, camera_select, user_select, task_select)
        
        # Load all rule config data
        self.rule_script_grouping_dict = None
        self.rule_configs_dict = self._load_all_configs()
        self._update_rule_script_grouping()
        
        # Set up every known rule
        self.rule_ref_dict = self._setup_all()    
    
    # .................................................................................................................
    
    def __repr__(self):
        
        repr_strs = ["Rule Bundle ({})".format(self.task_select), ""]
        for each_script, each_rule_list in self.rule_script_grouping_dict.items():
            
            script_name_only, _ = os.path.splitext(each_script)
            repr_strs += ["  --- {} ---".format(script_name_only.capitalize())]
            repr_strs += ["    {}".format(each_rule_name) for each_rule_name in each_rule_list]
        
        if len(self.rule_script_grouping_dict.keys()) < 1:
            repr_strs += ["  No rule configs!"]
            
        return "\n".join(repr_strs)
    
    # .................................................................................................................
    
    def _load_all_configs(self):
        
        # Allocate outputs
        configs_dict = {}
        
        # Get a listing of all available rule configs
        rule_config_file_list = get_file_list(self.rule_folder_path, 
                                              show_hidden_files = False, 
                                              create_missing_folder = False, 
                                              return_full_path = True)
        
        # Load every available rule configuration
        for each_file_path in rule_config_file_list:
                
            # Load the rule config data
            rule_config = load_with_error_if_missing(each_file_path)
            
            # Store rule config in a dictionary using the rule name as a key
            rule_file_name = os.path.basename(each_file_path)
            rule_name, _ = os.path.splitext(rule_file_name)
            configs_dict.update({rule_name: rule_config})
        
        return configs_dict

    # .................................................................................................................
    
    def _update_rule_script_grouping(self):
        
        # Start with empty grouping for cleanliness
        rule_script_grouping = {}
        
        # Store the rule script name, since we'll group rules by type this way
        for each_rule_name, each_config_dict in self.rule_configs_dict.items():
            
            rule_script = each_config_dict.get("access_info").get("script_name")
            script_name_only, _ = os.path.splitext(rule_script)
            if script_name_only not in rule_script_grouping:
                rule_script_grouping[script_name_only] = []
            rule_script_grouping[script_name_only].append(each_rule_name)
            
        # Finally, update internal grouping record
        self.rule_script_grouping_dict = rule_script_grouping
    
    # .................................................................................................................
    
    def _setup_single(self, rule_name, access_info_dict, setup_data_dict):
        
        # Separate the access info
        script_name = access_info_dict.get("script_name")
        class_name = access_info_dict.get("class_name")
        
        # Load the given rule object
        import_dot_path = configurable_dot_path("rules", script_name)
        imported_rule_class = dynamic_import_from_module(import_dot_path, class_name)        
        rule_ref = imported_rule_class(rule_name)
        
        # For debugging
        #print("IMPORTING:", rule_name)
        #print(import_dot_path)
        #print(imported_rule_class)
        
        # Load initial configuration
        rule_ref.reconfigure(setup_data_dict)
        
        return rule_ref
    
    # .................................................................................................................
    
    def _setup_all(self):
        
        # Initialize an empty dictionary to hold references to each configured rule object
        rule_ref_dict = {}
        
        # Loop over all config data and load/configure all rules
        for each_rule_name, each_config_dict in self.rule_configs_dict.items():
            
            # Get access info for each stage
            access_info = each_config_dict.get("access_info")
            setup_data = each_config_dict.get("setup_data")
            
            print("RULE SET UP:", each_rule_name)
            print(access_info)
            print(setup_data)
            
            # Import and configure each rule object
            rule_ref = self._setup_single(each_rule_name, access_info, setup_data)
            
            # Store configuration outputs
            rule_ref_dict.update({each_rule_name: rule_ref})
            
        return rule_ref_dict
    
    # .................................................................................................................
    
    def override_for_configuration(self, rule_name, script_name, class_name):
        
        # Check if we've already loaded this rule, in which case, just return a reference to the configured rule object
        if rule_name in self.rule_configs_dict.keys():
            rule_ref = self.rule_ref_dict.get(rule_name)
        
        # If a rule name isn't provided, load an un-configured copy of the rule
        elif rule_name is None:
            
            # Build 'fake' save data so we can load initial object
            fake_access_info_dict = {"script_name": script_name, "class_name": class_name}
            fake_setup_data_dict = {}
            
            # Make up a default name to give the (non-existing) rule
            entry_idx = 1 + len(self.rule_script_grouping_dict.get(script_name, []))
            script_name_only, _ = os.path.splitext(script_name)
            default_rule_name = "{}_{}".format(script_name_only.capitalize(), str(entry_idx).zfill(2))
            
            # Get a reference to the configured rule object
            rule_ref = self._setup_single(default_rule_name, fake_access_info_dict, fake_setup_data_dict)
            
            # Update configs & reference dictionaries
            fake_config_data = {"access_info": fake_access_info_dict, "setup_data": fake_setup_data_dict}
            self.rule_configs_dict.update({default_rule_name: fake_config_data})
            self.rule_ref_dict.update({default_rule_name: rule_ref})
            self._update_rule_script_grouping()
        
        else:
            # If we get here, a name was provided, but it's not one we recognize... so give an error
            raise NameError("Unrecognized rule name: {}".format(rule_name))
        
        # Get control/initial setting data for config
        controls_json = rule_ref.controls_manager.to_json()
        initial_settings = rule_ref.current_settings()
        
        return rule_ref, controls_json, initial_settings
    
    # .................................................................................................................
    
    def reset_all(self):
        
        # Reset all rule objects. Mostly for use in configuration, when the video may jump around
        for each_rule_ref in self.rule_ref_dict:
            each_rule_ref.reset()
    
    # .................................................................................................................
    
    def run_all(self, stage_outputs, current_time_sec, current_datetime):
        
        '''
        Outputs:
            need_to_save (boolean), rule_outputs (dict), rule_timing_sec (dict)        
        '''
        
        preprocessor_output = stage_outputs.get("preprocessor")
        tracker_output = stage_outputs.get("tracker")
        
        snapshotter.update(preprocessor_output, tracker_output, current_time_sec, current_datetime)
        
        rules_to_save, rule_outputs, rule_timing_sec = \
            each_rule_procseq.run_all(tracker_stage_outputs, current_time_sec, current_datetime)
            
        return need_to_save, rule_outputs, rule_timing_sec
    
    # .................................................................................................................
    
    def ask_to_save_rule_config(self):
        user_confirm = cli_confirm("Save configuration?", default_response = False)
        return user_confirm
    
    # .................................................................................................................
    # .................................................................................................................


# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
    
class Rule_Drawer:
    
    # .................................................................................................................
    
    def __init__(self, drawing_specification_list):
        
        self.drawing_spec = drawing_specification_list
        self.draw_func_list = self._build_drawing_functions(drawing_specification_list)
    
    # .................................................................................................................
    
    def draw_rule_spec(self, frame, in_place = False):
        
        # Draw onto the drawing frame and return result
        draw_frame = frame if in_place else frame.copy()
        for each_draw_func in self.draw_func_list:
            each_draw_func(draw_frame)
        
        return draw_frame
    
    # .................................................................................................................
    
    def draw_single_object_alarm(self, frame, rule_metadata, tracked_object_dict, in_place = False):
        
        # Record frame sizing so we can draw normalized co-ordinate locations
        frame_h, frame_w = frame.shape[0:2]
        frame_wh = np.array((frame_w - 1, frame_h - 1))
        
        # Draw onto the drawing frame and return result
        draw_frame = frame if in_place else frame.copy()
        for each_entry in rule_metadata:
            
            # Get rule drawing instructions
            rule_drawing = each_entry.get("drawing")
            rule_draw_func_list = self._build_drawing_functions(rule_drawing)
            for each_draw_func in rule_draw_func_list:
                each_draw_func(draw_frame)
            
            # Get objects breaking alarm
            object_id = each_entry.get("object_id")
            object_ref = tracked_object_dict.get(object_id)
        
            # Draw trail
            xy_trail = np.int32(np.round(object_ref.xy_track_history * frame_wh))
            if len(xy_trail) > 5:
                cv2.polylines(draw_frame, [xy_trail], False, (0, 255, 255), 1, cv2.LINE_AA)
            
            # Draw outline
            obj_hull = np.int32(np.round(object_ref.hull * frame_wh))
            cv2.polylines(draw_frame, [obj_hull], True, (0, 255, 0), 1, cv2.LINE_AA)
            
        return draw_frame
    
    # .................................................................................................................
    
    def _build_drawing_functions(self, drawing_specification_list):
        
        # Bundle drawing functions in a lookup table for ease of use
        func_lut = {"line": self._draw_line,
                    "circle": self._draw_circle,
                    "polygon": self._draw_polygon,
                    "chain": self._draw_chain,
                    "rectangle": self._draw_rectangle}
        
        func_list = []
        for each_draw_type, each_spec in drawing_specification_list:
            
            draw_func = func_lut.get(each_draw_type, None)
            
            # Skip over this drawing function, with a warning, if it isn't recognized (i.e. not in lookup table)
            if draw_func is None:
                print("", 
                      "Warning: Rule drawing style ({}) not recognized!".format(each_draw_type),
                      "Component will not be drawn!", "", sep="\n")
                continue
            
            try:
                partial_draw_func = partial(draw_func, **each_spec)
                
            except Exception:
                print("", 
                      "Error using drawing function parameters!",
                      "For type {}, got:".format(each_draw_type),
                      "  {}".format(", ".join(each_spec.keys())),
                      "Skipping...", "", sep="\n")
                continue
                
            func_list.append(partial_draw_func)
            
        return func_list
    
    # .................................................................................................................
    
    def _draw_line(self, frame, start_pt, end_pt, color, thickness, anchors, directional):
        
        # Record frame sizing so we can draw normalized co-ordinate locations
        frame_h, frame_w = frame.shape[0:2]
        frame_wh = np.array((frame_w - 1, frame_h - 1))
        
        # Scale normalized point co-ords into pixel co-ords
        start_px = tuple(np.int32(np.round(start_pt * frame_wh)))
        end_px = tuple(np.int32(np.round(end_pt * frame_wh)))
        cv2.line(frame, start_px, end_px, color, thickness, cv2.LINE_AA)
        
        # Draw direction arrow, if needed
        if directional:
            
            # Figure out the orientation of the line so we can draw the arrow in the right direction
            line_vec_px = np.array((start_px, end_px))
            mid_point_px = np.mean(line_vec_px, axis = 0)
            normal_vec = np.flip(line_vec_px - mid_point_px) * np.array((-1, 1))
            unit_normal = normal_vec * (1 / np.linalg.norm(normal_vec))
            
            # Draw arrow tip point some distance away from the line mid point and connect lines to help visualize it
            forward_pt = np.int32(np.round(mid_point_px + 20*unit_normal[1]))
            cv2.line(frame, tuple(forward_pt), tuple(start_px), color, 1, cv2.LINE_AA)
            cv2.line(frame, tuple(forward_pt), tuple(end_px), color, 1, cv2.LINE_AA)
            
        # Draw anchor points on the line, if needed
        if anchors:
            self._draw_circle(frame, start_px, 3, color, -1)
            self._draw_circle(frame, end_px, 3, color, -1)
    
    # .................................................................................................................
    
    def _draw_circle(self, frame, center, radius, color, thickness):
        cv2.circle(frame, center, radius, color, thickness, cv2.LINE_AA)
    
    # .................................................................................................................
    
    def _draw_polygon(self, frame, point_list, color, thickness):
        cv2.polylines(frame, point_list, True, color, thickness, cv2.LINE_AA)
    
    # .................................................................................................................
    
    def _draw_chain(self, frame, point_list, color, thickness):
        cv2.polylines(frame, point_list, False, color, thickness, cv2.LINE_AA)
    
    # .................................................................................................................
    
    def _draw_rectangle(self, frame, point_1, point_2, color, thickness):
        cv2.rectangle(frame, point_1, point_2, color, thickness, cv2.LINE_4)

    # .................................................................................................................
    # .................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

# .....................................................................................................................
    
def run_rule_config_video_loop(video_reader_ref, 
                               background_capture_ref,
                               core_proccess_sequence,
                               rule_ref,
                               controls_json, 
                               initial_settings,
                               display_manager_ref, 
                               config_helper):
    
    
    # Handle web vs. local configuration and video looping
    is_web_config = False
    if is_web_config:

        
        pass
    else:

        # Run main video loop
        final_stage_outputs, final_stage_timing = local_rule_config_video_loop(video_reader_ref, 
                                                                               background_capture_ref,
                                                                               core_proccess_sequence,
                                                                               rule_ref,
                                                                               controls_json,
                                                                               initial_settings,
                                                                               display_manager_ref,
                                                                               config_helper)
        
        # Use terminal to prompt user for saving config data, when running locally
        #core_proccess_sequence.ask_to_save_rule_config(rule_ref, initial_settings)
        

    # For debugging purposes
    return final_stage_outputs, final_stage_timing

# ---------------------------------------------------------------------------------------------------------------------
#%% Demo

if __name__ == "__main__":

    pass


# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap


