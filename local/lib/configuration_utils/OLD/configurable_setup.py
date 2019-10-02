#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Jun 14 16:51:00 2019

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

import argparse

from local.lib.selection_utils import Resource_Selector

from local.lib.configuration_utils.video_setup import Dummy_vreader
from local.lib.configuration_utils.background_capture_setup import Background_Capture_Configuration
from local.lib.configuration_utils.core_setup import Core_Bundle
#from local.lib.configuration_utils.rule_setup import Rule_Bundle

from local.lib.file_access_utils.shared import configurable_dot_path
from local.lib.file_access_utils.bgcapture import build_captures_folder_path, build_generated_folder_path
from local.lib.file_access_utils.bgcapture import load_bg_capture_config

from eolib.utils.function_helpers import dynamic_import_from_module

# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes


class Configurable_Setup_Helper:

    # .................................................................................................................

    def __init__(self):

        # Store pathing info
        self.project_root_path = None
        self.cameras_folder = None
        self.camera_select = None
        self.user_select = None
        self.task_select = None

        # Store video info
        self.video_select = None
        self.video_wh = None
        self.video_fps = None
        self.video_type = None

    # .................................................................................................................
    
    def _grab_initial_video_data(self):
        
        # Try to connect to the video source to figure out some info about it
        try:
            # Get access to video reader so we can grab useful frame sizing/timing info
            vreader_ref, _, _, _ = self.setup_video_reader()
            vreader_ref.release()
            
        except Exception:
            print("",
                  "Couldn't connect to video source: {}".format(self.video_select),
                  "  No video data available!", sep = "\n")

    # .................................................................................................................
    
    def setup_standard_core_config_util(self, stage_name, script_name, class_name, display_manager):
        
        # Select camera/user/task/video
        self.make_core_selections()

        # Set up the video source
        vreader, video_wh, video_fps, video_type = self.setup_video_reader()
        
        # Set up background capture
        bgcap = self.setup_background_capture(disable_for_configuration = True)
        
        # Set up the core sequence
        core_bundle = self.setup_core()
        
        # Override target core stage, for re-configuration
        core_ref, controls_json, initial_settings = \
        core_bundle.override_for_configuration(stage_name = stage_name,
                                               script_name = script_name,
                                               class_name = class_name)
        
        # Bundle setup data for ease of use
        video_loop_config_data_dict = {"video_reader_ref": vreader,
                                       "background_capture_ref": bgcap,
                                       "core_bundle_ref": core_bundle,
                                       "configurable_ref": core_ref,
                                       "controls_json": controls_json,
                                       "initial_settings": initial_settings,
                                       "display_manager_ref": display_manager,
                                       "config_helper": self}
        
        # Bundle some handy debugging data
        debug_data_ref = (core_ref, controls_json, initial_settings)
            
        return video_loop_config_data_dict, debug_data_ref
    
    # .................................................................................................................
    
    def setup_standard_bgcap_config_util(self, script_name, class_name, disable_threading = True):
        
        # Select camera/user/video
        self.make_external_selections()
        
        # Set up the video source
        vreader, video_wh, video_fps, video_type = self.setup_video_reader()
        
        # Override the background loader
        bgcap_ref = self.setup_background_capture(script_name = script_name,
                                                  class_name = class_name,
                                                  disable_threading = disable_threading)
        controls_json = bgcap_ref.controls_manager.to_json()
        initial_settings = bgcap_ref.current_settings()
        
        # Create the background config helper, which handles much of the background config ui/presentation
        bg_config_helper = Background_Capture_Configuration(self, vreader, bgcap_ref)
        
        # Bundle setup data for ease of use
        config_ui_data_dict = {"video_reader_ref": vreader,
                               "bg_config_helper": bg_config_helper,
                               "background_capture_ref": bgcap_ref,
                               "controls_json": controls_json,
                               "initial_settings": initial_settings,
                               "config_helper": self}
        
        # Bundle some handy debugging data
        debug_data_ref = (bgcap_ref, controls_json, initial_settings)
        
        return config_ui_data_dict, debug_data_ref

    # .................................................................................................................

    def setup_video_reader(self):

        # Setup video reader and grab important info
        vreader = Dummy_vreader(self.cameras_folder, self.camera_select, self.video_select)
        video_wh = vreader.video_wh
        video_fps = vreader.video_fps
        video_type = vreader.video_type
        
        # Store/update the internal record of video info as well, so we can re-use it if needed
        self.video_wh = video_wh
        self.video_fps = video_fps
        self.video_type = video_type

        return vreader, video_wh, video_fps, video_type
    
    # .................................................................................................................

    def split_full_config(self, full_config):        
        script_name = full_config.get("access_info").get("script_name")
        class_name = full_config.get("access_info").get("class_name")
        setup_data = full_config.get("setup_data", {})
        return script_name, class_name, setup_data
    
    # .................................................................................................................

    def check_script_class_match(self, component_name, new_script, new_class,
                                 recorded_script, recorded_class, recorded_setup_data):


        # Make sure we're comparing similar styles of names
        new_script, _ = os.path.splitext(new_script)
        recorded_script, _ = os.path.splitext(recorded_script)

        # Check matches
        script_match = (recorded_script == new_script)
        class_match = (recorded_class == new_class)
        script_and_class_match = (script_match and class_match)
        
        # If there is a mismatch, clear the setup data and provide some feedback
        output_setup_data = recorded_setup_data
        if (not script_and_class_match):

            # Erase loaded configuration data, since it won't match the new script/class
            output_setup_data = {}

            # Provide some feedback about overriding the config
            print("",
                  "Overriding {} configuration!".format(component_name),
                  "    New script: {}".format(new_script),
                  "   (previously: {})".format(recorded_script),
                  "",
                  "     New class: {}".format(new_class),
                  "   (previously: {})".format(recorded_class),
                  "", sep = "\n")

        return output_setup_data

    # .................................................................................................................

    def setup_background_capture(self, script_name = None, class_name = None, 
                                 disable_for_configuration = False,
                                 disable_threading = False):
        
        # For convenience
        component_name = "background_capture"
        
        # Get full config data & grab the recorded script/class names
        full_bgcap_config = load_bg_capture_config(self.project_root_path,
                                                   self.cameras_folder,
                                                   self.camera_select,
                                                   self.user_select)
        recorded_script, recorded_class, recorded_setup_data = self.split_full_config(full_bgcap_config)
        
        # Automatically use the recorded script & class if either wasn't provided
        script_not_provided = (script_name is None)
        class_not_provided = (class_name is None)
        use_recorded = (script_not_provided or class_not_provided)
        if use_recorded:
            script_name = recorded_script
            class_name = recorded_class
        
        # Check if the target script/class matches the saved data
        setup_data = self.check_script_class_match(component_name, script_name, class_name,
                                                   recorded_script, recorded_class, recorded_setup_data)
        
        # Get pathing to resource folders
        captures_folder_path = build_captures_folder_path(self.cameras_folder, self.camera_select)
        generated_folder_path = build_generated_folder_path(self.cameras_folder, self.camera_select)
        
        # Load the given background capture stage
        import_dot_path = configurable_dot_path("externals", component_name, script_name)
        imported_bgcap_class = dynamic_import_from_module(import_dot_path, class_name)
        bgcap_ref = imported_bgcap_class(video_select = self.video_select,
                                         video_wh = self.video_wh,
                                         captures_folder_path = captures_folder_path,
                                         generated_folder_path = generated_folder_path)
        
        # Enable configuration mode if we're not using the recorded script/class settings
        enable_configure_mode = (not use_recorded)
        bgcap_ref.set_configure_mode(enable_configure_mode)
        
        # Disable capture/generate/update conditions if needed (mainly for use during other configurations)
        if disable_for_configuration:
            bgcap_ref.disable_conditions()
            
        # Disable capture/generation on separate threads. Mostly useful if running on files
        if disable_threading:
            bgcap_ref.disable_threading()
        
        # Load initial configuration
        bgcap_ref.reconfigure(setup_data)
        
        return bgcap_ref
    
    # .................................................................................................................
    
    def setup_core(self):
        
        core_config_selections = {"cameras_folder": self.cameras_folder,
                                  "camera_select": self.camera_select,
                                  "user_select": self.user_select,
                                  "task_select": self.task_select,
                                  "video_wh": self.video_wh}
        
        core_bundle = Core_Bundle(**core_config_selections)
        core_bundle.reset_all()
        
        return core_bundle
    
    # .................................................................................................................
    '''
    def setup_rules(self):
        
        rule_config_selections = {"cameras_folder": self.cameras_folder,
                                  "camera_select": self.camera_select,
                                  "user_select": self.user_select,
                                  "task_select": self.task_select}
        
        rule_bundle = Rule_Bundle(**rule_config_selections)
        rule_bundle.reset_all()
        
        return rule_bundle
    '''
    # .................................................................................................................
    
    def make_external_selections(self):
        
        # Create a selector so we can pick what we're configuring & get important pathing
        selector = Resource_Selector()
        project_root_path, cameras_folder = selector.get_project_pathing()
        
        # Make selections
        camera_select, user_select, task_select, rule_select, video_select, socket_info = \
        selections(selector, enable_task_select = False)
        
        # Store selection results
        self.project_root_path = project_root_path
        self.cameras_folder = cameras_folder
        self.camera_select = camera_select
        self.user_select = user_select
        self.task_select = task_select
        self.rule_select = rule_select
        self.video_select = video_select
        
        # Get web info
        self.web_enabled = (socket_info is not None)
        self.socket_ip, self.socket_port = socket_info if self.web_enabled else (None, None)
        
        # Use new selection data to get video data
        self._grab_initial_video_data()
        
        # Gather outputs for convenience
        selections_dict = {"project_root_path": project_root_path,
                           "cameras_folder": cameras_folder,
                           "camera_select": camera_select,
                           "user_select": user_select,
                           "task_select": task_select,
                           "rule_select": rule_select,
                           "video_select": video_select}
        
        return selections_dict
        
    
    # .................................................................................................................
    
    def make_core_selections(self):
        
        # Create a selector so we can pick what we're configuring & get important pathing
        selector = Resource_Selector()
        project_root_path, cameras_folder = selector.get_project_pathing()
        
        # Make selections
        camera_select, user_select, task_select, rule_select, video_select, socket_info = \
        selections(selector)
        
        # Store selection results
        self.project_root_path = project_root_path
        self.cameras_folder = cameras_folder
        self.camera_select = camera_select
        self.user_select = user_select
        self.task_select = task_select
        self.rule_select = rule_select
        self.video_select = video_select
        
        # Store web info
        self.web_enabled = (socket_info is not None)
        self.socket_ip, self.socket_port = socket_info if self.web_enabled else (None, None)
        
        # Use new selection data to get video data
        self._grab_initial_video_data()
    
        # Gather outputs for convenience
        selections_dict = {"project_root_path": project_root_path,
                           "cameras_folder": cameras_folder,
                           "camera_select": camera_select,
                           "user_select": user_select,
                           "task_select": task_select,
                           "rule_select": rule_select,
                           "video_select": video_select}
    
        return selections_dict
    
    # .................................................................................................................
    
    def make_rule_selections(self):
        raise NotImplementedError("No rule selections yet...")
    
    # .................................................................................................................
    
    def make_run_selections(self):
        
        # Create a selector so we can pick what we're configuring & get important pathing
        selector = Resource_Selector()
        project_root_path, cameras_folder = selector.get_project_pathing()
        
        # Make selections
        camera_select, user_select, task_select, rule_select, video_select, socket_info = \
        selections(selector, enable_task_select = False, enable_rule_select = False)
    
        # Store selection results
        self.project_root_path = project_root_path
        self.cameras_folder = cameras_folder
        self.camera_select = camera_select
        self.user_select = user_select
        self.task_select = task_select
        self.rule_select = rule_select
        self.video_select = video_select
        
        # Store web info
        self.web_enabled = (socket_info is not None)
        self.socket_ip, self.socket_port = socket_info if self.web_enabled else (None, None)
    
        # Use new selection data to get video data
        self._grab_initial_video_data()
    
        # Gather outputs for convenience
        selections_dict = {"project_root_path": project_root_path,
                           "cameras_folder": cameras_folder,
                           "camera_select": camera_select,
                           "user_select": user_select,
                           "task_select": task_select,
                           "rule_select": rule_select,
                           "video_select": video_select}
    
        return selections_dict
    
    # .................................................................................................................
    # .................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions
    
# .....................................................................................................................
    
def parse_arguments():
    
    # Set up argparser options + positional input
    ap = argparse.ArgumentParser()
    ap.add_argument("-c", "--camera", default = None, type = str, help = "Camera select")
    ap.add_argument("-u", "--user", default = None, type = str, help = "User select")
    ap.add_argument("-t", "--task", default = None, type = str, help = "Task select")
    ap.add_argument("-r", "--rule", default = None, type = str, help = "Rule select")
    ap.add_argument("-v", "--video", default = None, type = str, help = "Video select")
    ap.add_argument("-sip", "--socketip", default = None, type = str, help = "Specify socket server IP address")
    ap.add_argument("-sport", "--socketport", default = None, type = str, help = "Specify socket server port")
    ap_result = vars(ap.parse_args())
    
    # Get script argument selections
    camera_select = ap_result.get("camera")
    user_select = ap_result.get("user")
    task_select = ap_result.get("task")
    rule_select = ap_result.get("rule")
    video_select = ap_result.get("video")
    socket_ip = ap_result.get("socketip")
    socket_port = ap_result.get("socketport")
    
    return camera_select, user_select, task_select, rule_select, video_select, socket_ip, socket_port


# .....................................................................................................................
    
def selections(selector,
               enable_user_select = True,
               enable_task_select = True,
               enable_rule_select = False,
               enable_video_select = True):
    
    # Get script argument selections
    camera_select, user_select, task_select, rule_select, video_select, socket_ip, socket_port = parse_arguments()
    socket_info = None if (socket_ip is None) or (socket_port is None) else (socket_ip, socket_port)
    
    # Always select a camera, since nothing else makes sense without one
    camera, _ = selector.camera(camera_select)
    user, task, rule, video = None, None, None, None
    
    # Select a user if needed
    if enable_user_select:
        user, _ = selector.user(camera, user_select)
    
    # Select a task if needed. Note that user select must have been enabled, or this will cause errors!
    if enable_task_select:
        task, _ = selector.task(camera, user, task_select)
    
    # Select a rule if needed. Note that rules make have blank selections (i.e. create a new rule)!
    if enable_rule_select:
        rule, _ = selector.rule(camera, user, task, rule_select)
    
    # Select a video if needed
    if enable_video_select:
        video, _ = selector.video(camera, video_select)
    
    return camera, user, task, rule, video, socket_info

# .....................................................................................................................
# .....................................................................................................................



# ---------------------------------------------------------------------------------------------------------------------
#%% Demo
    
'''
TODO:
    - Make background capture setup more similar to core processing sequence!
        - ie. move detailed functionality to separate class/function
        - config_helper just calls other class/function to do the work (and passes all relevant pathing info)
    - Maybe do similar thing to video setup? Although this isn't as important
    - Config helper should really just manage loading/making selections that require all pathing/selection info
    
    - Clean up 'make selections' code
        - Should be one function to handle all selections, with disabling used to hide unneeded selections
        - Also need to add argument parsing, so scripts can be called with command line args
'''

'''
STOPPED HERE
- TEST OUT BG CAPTURE/GEN DISABLING (MOSTLY SEEMS TO WORK?!)
- THEN GET BG CAPTURE SAVING WORKING
    - AND MAYBE CLEAN UP + MAKE INTO A RE-USABLE CONFIG UTIL?
- THEN TRY RULES?!
'''


if __name__ == "__main__":
    pass

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap


