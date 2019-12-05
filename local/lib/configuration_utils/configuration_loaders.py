#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Sep 25 14:54:19 2019

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
import json

from local.lib.selection_utils import Resource_Selector
from local.lib.configuration_utils.video_setup import Dummy_vreader

from local.lib.configuration_utils.core_bundle_loader import Core_Bundle
from local.lib.file_access_utils.video import Playback_Access
from local.lib.file_access_utils.screen_info import Screen_Info
from local.lib.file_access_utils.shared import configurable_dot_path, full_replace_save

from eolib.utils.cli_tools import cli_confirm
from eolib.utils.function_helpers import dynamic_import_from_module
from eolib.utils.read_write import load_json

# ---------------------------------------------------------------------------------------------------------------------
#%% Define base class

class Configuration_Loader:
    
    # .................................................................................................................
    
    def __init__(self, selections_on_launch = True):
        
        # Allocate storage for selections
        self.project_root_path = None
        self.cameras_folder_path = None
        self.camera_select = None
        self.user_select = None
        self.task_select = None
        self.video_select = None
        self.task_name_list = None
        self.script_arg_inputs = {}
        
        # Allocate storage for video data
        self.vreader = None
        self.video_wh = None
        self.video_fps = None
        self.video_type = None
        self.playback_settings = None
        
        # Allocate storage for externals
        self.bgcap = None
        self.snapcap = None
        self.objcap_dict = None
        
        # Set saving behaviors
        self.saving_enabled = False
        self.threading_enabled = False
        
        # Allocate storage for display/screen information
        self.screen_info = None
        
        # Launch into selections, if needed
        if selections_on_launch:
            self.selections()
    
    # .................................................................................................................
        
    def parse_args(self):
        
        self.script_arg_inputs = parse_loader_args(enable_camera_select = True,
                                                   enable_user_select = True,
                                                   enable_task_select = False,
                                                   enable_video_select = True,
                                                   enable_socket_select = False)
        
    # .................................................................................................................
    
    def selections(self, parse_script_args = True):
        
        # Parse script input arguments, if desired
        if parse_script_args:
            self.parse_args()
        arg_camera_select = self.script_arg_inputs.get("camera_select")
        arg_user_select = self.script_arg_inputs.get("user_select")
        arg_video_select = self.script_arg_inputs.get("video_select")
        
        # Create selector so we can make camera/user/video selections
        selector = Resource_Selector()
        self.project_root_path, self.cameras_folder_path = selector.get_project_pathing()
        
        # Select shared components
        self.camera_select, _ = selector.camera(arg_camera_select)
        self.user_select, _ = selector.user(self.camera_select, arg_user_select)
        self.video_select, _ = selector.video(self.camera_select, arg_video_select)
        
        # Find list of all tasks
        self.task_name_list = selector.get_task_list(self.camera_select, self.user_select)
        
        return self
    
    # .................................................................................................................
    
    def toggle_saving(self, enable_saving):
        self.saving_enabled = enable_saving
        
        # Warning if toggling after having run setup (toggle won't apply)
        if (self.vreader is not None):
            print("", "WARNING:", "  Saving should be enabled/disabled before running .setup_all()!", sep = "\n")
        
    # .................................................................................................................
    
    def toggle_threading(self, enable_threading):
        self.threading_enabled = enable_threading
        
        # Warning if toggling after having run setup (toggle won't apply)
        if (self.vreader is not None):
            print("", "WARNING:", "  Threading should be enabled/disabled before running .setup_all()!", sep = "\n")
      
    # .................................................................................................................
    
    def get_screen_info(self):        
        self.screen_info = Screen_Info(self.project_root_path)
        
    # .................................................................................................................
    
    def setup_video_reader(self):

        # Set up the video source
        self.vreader = Dummy_vreader(self.cameras_folder_path, self.camera_select, self.video_select)
        self.video_wh = self.vreader.video_wh
        self.video_fps = self.vreader.video_fps
        self.video_type = self.vreader.video_type
        
        return self.vreader
        
    # .................................................................................................................
    
    def setup_background_capture(self):
        
        # Programmatically import the target background capture class
        Imported_Background_Capture_Class, setup_data_dict = self._import_externals_class("background_capture")
        shared_config = self._get_shared_config()
        
        # Load & configure the background capture object
        new_bgcap = Imported_Background_Capture_Class(**shared_config)
        new_bgcap.reconfigure(setup_data_dict)
        
        # Enable/disable saving behaviors
        new_bgcap.toggle_report_saving(self.saving_enabled)
        new_bgcap.toggle_resource_saving(self.saving_enabled)
        new_bgcap.toggle_threading(self.threading_enabled)
        
        # Make sure we always have a background image on startup
        new_bgcap.generate_on_startup(self.vreader)
        
        # Finally, store background capture for re-use
        self.bgcap = new_bgcap
        
        return self.bgcap
    
    # .................................................................................................................
    
    def setup_snapshot_capture(self):
        
        # Programmatically import the target snapshot capture class
        Imported_Snapshot_Capture_Class, setup_data_dict = self._import_externals_class("snapshot_capture")
        shared_config = self._get_shared_config()
        
        # Load & configure the background capture object
        new_snapcap = Imported_Snapshot_Capture_Class(**shared_config)
        new_snapcap.reconfigure(setup_data_dict)
        
        # Enable/disable saving behaviors
        new_snapcap.toggle_image_saving(self.saving_enabled)
        new_snapcap.toggle_metadata_saving(self.saving_enabled)
        new_snapcap.toggle_threading(self.threading_enabled)
        
        # Finally, store snapshot capture for re-use
        self.snapcap = new_snapcap
        
        return self.snapcap
    
    # .................................................................................................................
    
    def setup_object_capture(self):
        
        # Programmatically import the target object capture class
        Imported_Object_Capture_Class, setup_data_dict = self._import_externals_class("object_capture")
        shared_config = self._get_shared_config()
        
        # Load object capturers for each task
        new_objcap_dict = {}
        for each_task_name in self.task_name_list:
            
            # Load & configure an object capturer for each task
            new_objcap = Imported_Object_Capture_Class(**shared_config, task_select = each_task_name)
            new_objcap.reconfigure(setup_data_dict)
            
            # Enable/disable saving behaviors
            new_objcap.toggle_metadata_saving(self.saving_enabled)
            new_objcap.toggle_threading(self.threading_enabled)
            
            # Add new capture object to the dictionary
            new_objcap_dict.update({each_task_name: new_objcap})
            
        # Finally, store object capture for re-use
        self.objcap_dict = new_objcap_dict
        
        return self.objcap_dict
    
    # .................................................................................................................
    
    def setup_externals(self):
        
        self.setup_background_capture()
        self.setup_snapshot_capture()
        self.setup_object_capture()
    
    # .................................................................................................................
    
    def setup_core_bundles(self):
        
        # Load core bundles for each task
        new_core_bundles_dict = {}
        shared_config = self._get_shared_config()
        for each_task_name in self.task_name_list:
            
            # Set up full core bundle (i.e. all core stages configured)
            new_core_bundle = Core_Bundle(**shared_config, task_select = each_task_name)
            new_core_bundle.setup_all()
            
            # Add new core bundle to the dictionary
            new_core_bundles_dict.update({each_task_name: new_core_bundle})
        
        # Finally, store the bundles dictionary for re-use
        self.core_bundles_dict = new_core_bundles_dict
        
        return self.core_bundles_dict
    
    # .................................................................................................................
    
    def setup_all(self):
        
        self.setup_video_reader()
        self.setup_externals()
        self.setup_core_bundles()
        self.get_screen_info()
        
    # .................................................................................................................
    
    def _import_externals_class(self, externals_type):
        
        # Check configuration file to see which script/class to load from & get configuration data
        _, file_access_dict, setup_data_dict = self._load_externals_config_data(externals_type)
        script_name = file_access_dict.get("script_name")
        class_name = file_access_dict.get("class_name")
        
        # Programmatically import the target class
        dot_path = configurable_dot_path("externals", externals_type, script_name)
        Imported_Externals_Class = dynamic_import_from_module(dot_path, class_name)
        
        return Imported_Externals_Class, setup_data_dict
        
    # .................................................................................................................
    
    def _load_externals_config_data(self, json_file_name_no_ext):
        
        ''' 
        Function which finds and loads pre-saved configuration files for externals
        '''
        
        # Make sure there's no file extension
        load_file_name, _ = os.path.splitext(json_file_name_no_ext)
        
        # Get path to externals config file
        path_to_config = os.path.join(self.cameras_folder_path, 
                                      self.camera_select, 
                                      "users", 
                                      self.user_select,
                                      "externals",
                                      "{}.json".format(load_file_name))
        
        # Load json data and split into file access info & setup configuration data
        config_dict = load_json(path_to_config)
        access_info_dict = config_dict.get("access_info")
        setup_data_dict = config_dict.get("setup_data")
        
        return path_to_config, access_info_dict, setup_data_dict
    
    # .................................................................................................................
    
    def _load_core_stage_config_data(self, task_select, json_file_name_no_ext):
        
        ''' Function which finds & loads pre-saved configuration files for core stages '''
        
        # Make sure there's no file extension
        load_file_name, _ = os.path.splitext(json_file_name_no_ext)
        
        # Get path to externals config file
        path_to_config = os.path.join(self.cameras_folder_path, 
                                      self.camera_select, 
                                      "users", 
                                      self.user_select,
                                      "externals",
                                      "{}.json".format(load_file_name))
        
        # Load json data and split into file access info & setup configuration data
        config_dict = load_json(path_to_config)
        access_info_dict = config_dict.get("access_info")
        setup_data_dict = config_dict.get("setup_data")
        
        return access_info_dict, setup_data_dict
    
    # .................................................................................................................
    
    def _get_shared_config(self):
        
        return {"cameras_folder_path": self.cameras_folder_path,
                "camera_select": self.camera_select,
                "user_select": self.user_select,
                "video_select": self.video_select,
                "video_wh": self.video_wh}

    # .................................................................................................................
    # .................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Reconfigurable Implementations


class Reconfigurable_Loader(Configuration_Loader):
    
    # .................................................................................................................
    
    def __init__(self, override_stage, override_script_name, override_class_name = None,
                 selections_on_launch = True):
        
        # Inherit from parent class
        super().__init__(selections_on_launch = False)
        
        # Allocate storage for accessing re-configurable object
        self.configurable_ref = None
        self.configurable_config_file_path = None
        self.configurable_file_access_dict = None
        self.configurable_setup_data_dict = None
        self._config_utility_script_name = None
        
        # Store overriding settings
        self.override_stage = override_stage
        self.override_script = override_script_name
        self.override_class = override_class_name if override_class_name is not None else override_stage.title()
        
        # Allocate storage for a playback settings access
        self.playback_access = None
        
        # Assume we want to turn off saving when working in a re-configuration mode
        self.saving_enabled = False
        self.threading_enabled = False
        
        # Launch into selections, if needed
        if selections_on_launch:
            self.selections()
        
    # .................................................................................................................
        
    def parse_args(self):
        
        self.script_arg_inputs = parse_loader_args(enable_camera_select = True,
                                                   enable_user_select = True,
                                                   enable_task_select = True,
                                                   enable_video_select = True,
                                                   enable_socket_select = True)
    
    # .................................................................................................................
    
    def selections(self, parse_script_args = True):
        
        # Parse script input arguments, if desired
        if parse_script_args:
            self.parse_args()
        arg_camera_select = self.script_arg_inputs.get("camera_select")
        arg_user_select = self.script_arg_inputs.get("user_select")
        arg_task_select = self.script_arg_inputs.get("task_select")
        arg_video_select = self.script_arg_inputs.get("video_select")
        
        # Create selector so we can make camera/user/video selections
        selector = Resource_Selector()
        self.project_root_path, self.cameras_folder_path = selector.get_project_pathing()
        
        # Select shared components
        self.camera_select, _ = selector.camera(arg_camera_select)
        self.user_select, _ = selector.user(self.camera_select, arg_user_select)
        self.task_select, _ = selector.task(self.camera_select, self.user_select, arg_task_select)
        self.video_select, _ = selector.video(self.camera_select, arg_video_select)
        
        # Pretend that the list of all tasks is simply the selected task when re-configuring
        self.task_name_list = [self.task_select]
        
        return self
    
    # .................................................................................................................
    
    def setup_all(self, file_dunder):
        
        # Store configuration utility info
        self.record_configuration_utility(file_dunder)
        
        # Setup all main processing components
        self.setup_video_reader()
        self.setup_playback_access()
        self.setup_externals()
        self.setup_core_bundles()
        self.get_screen_info()
        
        return self.configurable_ref
    
    # .................................................................................................................
    
    def reset_all(self):
                
        # Reset everything, typically due to the video jumping around during configuration
        self.snapcap.reset()
        self.bgcap.reset()
        
        # Make sure to reset task-specific things separately for every task!
        for each_task_name in self.task_name_list:
            self.objcap_dict.get(each_task_name).reset()
            self.core_bundles_dict.get(each_task_name).reset_all()
            
    # .................................................................................................................
    
    def setup_playback_access(self):
        
        # Create object that can handle file i/o needed to access stored playback settings
        self.playback_access = Playback_Access(self.cameras_folder_path, self.camera_select, self.video_select)
        
        return self.playback_access

    # .................................................................................................................
    
    def record_configuration_utility(self, file_dunder):
        
        # Store configuration utility info. Helps provide lookup as to how the systme had been configured
        configuration_script_name = os.path.basename(file_dunder)
        name_only, _ = os.path.splitext(configuration_script_name)
        self._config_utility_script_name = name_only

    # .................................................................................................................
    
    def ask_to_save_configurable(self, configurable_ref):
        
        # Get save data from configurable & add configuration utility info
        file_access_dict, setup_data_dict = configurable_ref.get_data_to_save()
        file_access_dict.update({"configuration_utility": self._config_utility_script_name})
        
        # Only save if the saved data has changed
        is_passthrough = ("passthrough" in self.configurable_file_access_dict.get("script_name"))
        file_access_changed = (self.configurable_file_access_dict != file_access_dict)
        setup_data_changed = (self.configurable_setup_data_dict != setup_data_dict)
        need_to_save = (file_access_changed or setup_data_changed or is_passthrough)
        if need_to_save:
            user_confirm_save = cli_confirm("Save settings?", default_response = False)
            self._save_configurable(file_access_dict, setup_data_dict, user_confirm_save)
        else:
            print("", "Settings unchanged!", "Skipping save prompt...", "", sep="\n")

    # .................................................................................................................
    
    def _save_configurable(self, file_access_dict, setup_data_dict, confirm_save = True, print_feedback = True):
        
        # Get save data in proper format
        save_data = {"access_info": file_access_dict, "setup_data": setup_data_dict}
        
        # Get pathing
        save_path = self.configurable_config_file_path
        relative_save_path = os.path.relpath(save_path, self.cameras_folder_path)
        
        # Don't save
        if not confirm_save:
            
            # Give feedback
            if print_feedback:                
                print("",
                      "Here are the config settings, in case that cancel was an accident!",
                      "",
                      "Save path:",
                      "@ {}".format(relative_save_path),
                      "",
                      "Save data:",
                      json.dumps(save_data, indent = 2),
                      "", sep = "\n")
            
            return relative_save_path
        
        # If we get here, we're saving!
        full_replace_save(save_path, save_data, indent_data=True)
        if print_feedback:
            print("", "Saved configuration:", "@ {}".format(relative_save_path), "", sep = "\n")
        
        return relative_save_path
    
    # .................................................................................................................
    
    def _import_externals_class_with_override(self):
        
        # Check configuration file to see which script/class to load from & get configuration data
        path_to_config, file_access_dict, setup_data_dict = self._load_externals_config_data(self.override_stage)
        existing_script_name = file_access_dict.get("script_name")
        existing_class_name = file_access_dict.get("class_name")
        
        # Check if we're loading the target script/class already (in which case use the existing config)
        matching_script = (existing_script_name == self.override_script)
        matching_class = (existing_class_name == self.override_class)
        if not (matching_script and matching_class):
            file_access_dict = {"script_name": self.override_script, "class_name": self.override_class}
            setup_data_dict = {}
        
        # Programmatically import the target class
        dot_path = configurable_dot_path("externals", self.override_stage, self.override_script)
        Imported_Externals_Class = dynamic_import_from_module(dot_path, self.override_class)
        
        # Save data to re-access the override script
        self.configurable_config_file_path = path_to_config
        self.configurable_file_access_dict = file_access_dict
        self.configurable_setup_data_dict = setup_data_dict
        
        return Imported_Externals_Class, setup_data_dict
    
    # .................................................................................................................

    def _error_if_multiple_tasks(self):
        
        # Bail if something goes wrong with the task selection
        wrong_task_list = (len(self.task_name_list) != 1)
        if wrong_task_list:
            raise ValueError("Too many tasks selected! Can't set up re-configurable loader...")
        
        # Bail if the single task name doesn't match the selected task somehow
        task_select = self.task_select
        task_name = self.task_name_list[0]
        task_mismatch = (task_select != task_name)
        if task_mismatch:
            err = "Task select ({}) doesn't match task list entry ({})".format(task_select, task_name)
            raise NameError(err)
        
    # .................................................................................................................
    # .................................................................................................................


# =====================================================================================================================
# =====================================================================================================================

class Reconfigurable_Core_Stage_Loader(Reconfigurable_Loader):
    
    # .................................................................................................................
    
    def __init__(self, core_stage, script_name, class_name = None, selections_on_launch = True):
        
        # Inherit from parent class
        super().__init__(core_stage, script_name, class_name, selections_on_launch)
    
    # .................................................................................................................
    
    def setup_core_bundles(self):
        
        # Bail if something goes wrong with the task selection
        self._error_if_multiple_tasks()        
        
        # Load core bundles for each task
        new_core_bundles_dict = {}
        shared_config = self._get_shared_config()
        for each_task_name in self.task_name_list:
            
            # Set up full core bundle (i.e. all core stages configured)
            new_core_bundle = Core_Bundle(**shared_config, task_select = each_task_name)
            new_core_bundle.setup_all(self.override_stage, self.override_script, self.override_class)
            
            # Add new core bundle to the dictionary
            new_core_bundles_dict.update({each_task_name: new_core_bundle})
        
        # Finally, store the bundles dictionary for re-use
        self.core_bundles_dict = new_core_bundles_dict
        
        # Associate snapshot capture with re-configurable object
        configurable_stage_name, configurable_ref = new_core_bundles_dict.get(self.task_select).last_item()
        config_path = new_core_bundle.final_stage_config_file_paths.get(configurable_stage_name)
        config_dict = new_core_bundle.final_stage_config_dict.get(configurable_stage_name)
        
        # Store configurable reference info
        self.configurable_ref = configurable_ref
        self.configurable_config_file_path = config_path
        self.configurable_file_access_dict = config_dict.get("access_info")
        self.configurable_setup_data_dict = config_dict.get("setup_data")
        
        '''
        STOPPED HERE
        ^^^ THIS CONFIGURABLE STUFF IS A BIT UGLY, BUT NOT THE END OF THE WORLD FOR NOW...
            - WOULD BE BETTER FOR THE LOADER OBJECT TO GRAB THE FILE PATHING STUFF AND HAND TO CORE BUNDLE TO SETUP
            - NOT URGENT THOUGH...
        - THEN LOOK INTO CLEARING UP THE CORE_SETUP.PY AND/OR CORE BUNDLE SCRIPT LOCATION, ITS TOO MESSY NOW!
        '''
        
        return self.core_bundles_dict
        
    # .................................................................................................................
    # .................................................................................................................


# =====================================================================================================================
# =====================================================================================================================


class Reconfigurable_Snapshot_Capture_Loader(Reconfigurable_Loader):
    
    # .................................................................................................................
    
    def __init__(self, script_name, class_name = "Snapshot_Capture", selections_on_launch = True):
        
        # Inherit from parent class
        super().__init__("snapshot_capture", script_name, class_name, selections_on_launch)
    
    # .................................................................................................................
    
    def setup_snapshot_capture(self):
        
        # Programmatically import the target snapshot capture class
        Imported_Snapshot_Capture_Class, setup_data_dict = self._import_externals_class_with_override()
        shared_config = self._get_shared_config()
        
        # Load & configure the background capture object
        new_snapcap = Imported_Snapshot_Capture_Class(**shared_config)
        new_snapcap.set_configure_mode()
        new_snapcap.reconfigure(setup_data_dict)
        
        # Enable/disable saving behaviors
        new_snapcap.toggle_image_saving(self.saving_enabled)
        new_snapcap.toggle_metadata_saving(self.saving_enabled)
        new_snapcap.toggle_threading(self.threading_enabled)
        
        # Finally, store snapshot capture for re-use
        self.snapcap = new_snapcap
        
        # Associate snapshot capture with re-configurable object
        self.configurable_ref = self.snapcap
        
        return self.snapcap
    
    # .................................................................................................................
    # .................................................................................................................


# =====================================================================================================================
# =====================================================================================================================


class Reconfigurable_Background_Capture_Loader(Reconfigurable_Loader):
    
    # .................................................................................................................
    
    def __init__(self, script_name, class_name = "Background_Capture", selections_on_launch = True):
        
        # Inherit from parent class
        super().__init__("background_capture", script_name, class_name, selections_on_launch)
        
        # Will need to turn on saving in order to properly use background capture during config!
        self.toggle_saving(True)
        self.toggle_threading(False)
    
    # .................................................................................................................
    
    def setup_background_capture(self):        
        
        # Programmatically import the target background capture class
        Imported_Background_Capture_Class, setup_data_dict = self._import_externals_class_with_override()
        shared_config = self._get_shared_config()
        
        # Load & configure the background capture object
        new_bgcap = Imported_Background_Capture_Class(**shared_config)
        new_bgcap.set_configure_mode()
        new_bgcap.reconfigure(setup_data_dict)
        
        # Enable/disable saving behaviors
        new_bgcap.toggle_report_saving(self.saving_enabled)
        new_bgcap.toggle_resource_saving(self.saving_enabled)
        new_bgcap.toggle_threading(self.threading_enabled)
        
        # Give user warning about file i/o usage
        print("", 
              "",
              "WARNING:",
              "  Data saving (background capture & generated images) will be enabled for configuration purposes!",
              sep = "\n")
        
        # Ask to delete existing background data to avoid messing up results from different bgcap implementations
        user_confirm_delete = cli_confirm("Delete existing background data?")
        new_bgcap.clear_resources(user_confirm_delete)
        
        # Make sure we always have a background image on startup
        user_confirm_generate = False
        if not user_confirm_delete:
            user_confirm_generate = cli_confirm("Generate initial background from full video source?")
        new_bgcap.generate_on_startup(self.vreader, force_generate = user_confirm_generate)
        
        # Finally, store background capture for re-use
        self.bgcap = new_bgcap
        
        # Associate background capture with re-configurable object
        self.configurable_ref = self.bgcap
        
        return self.bgcap
    
    # .................................................................................................................
    # .................................................................................................................


# =====================================================================================================================
# =====================================================================================================================


class Reconfigurable_Object_Capture_Loader(Reconfigurable_Loader):
    
    # .................................................................................................................
    
    def __init__(self, script_name, class_name = "Object_Capture", selections_on_launch = True):
        
        # Inherit from parent class
        super().__init__("object_capture", script_name, class_name, selections_on_launch)
    
    # .................................................................................................................
    
    def setup_object_capture(self):
        
        # Bail if something goes wrong with the task selection
        self._error_if_multiple_tasks()
        
        # Programmatically import the target object capture class
        Imported_Object_Capture_Class, setup_data_dict = self._import_externals_class_with_override()
        shared_config = self._get_shared_config()
        
        # Load single object capture. Handle as if many tasks exist to make use of existing system functionality
        new_objcap_dict = {}
        for each_task_name in self.task_name_list:
            
            # Load & configure the object capturer
            new_objcap = Imported_Object_Capture_Class(**shared_config, task_select = each_task_name)
            new_objcap.set_configure_mode()
            new_objcap.reconfigure(setup_data_dict)
            
            # Enable/disable saving behaviors
            new_objcap.toggle_metadata_saving(self.saving_enabled)
            new_objcap.toggle_threading(self.threading_enabled)
            
            # Add the new capture object to the dictionary
            new_objcap_dict.update({each_task_name: new_objcap})
            
        # Finally, store the object capture
        self.objcap_dict = new_objcap_dict
        
        # Associate background capture with re-configurable object
        self.configurable_ref = self.objcap_dict.get(self.task_select)
        
        return self.objcap_dict
    
    # .................................................................................................................
    # .................................................................................................................


# =====================================================================================================================
# =====================================================================================================================


# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

def parse_loader_args(enable_camera_select = True,
                      enable_user_select = True,
                      enable_task_select = False,
                      enable_video_select = True,
                      enable_socket_select = False,
                      output_key_prefix = "",
                      output_key_suffix = "_select"):
    
    ''' 
    Function for parsing standard input arguments for resource selection.
    Multiple enable flags are available as input arguments for controllnig which inputs are provided by arg parser
    This function returns a dictionary of the form:
        output_dict = {"camera_select": <camera_arg_result>,
                       "user_select":   <user_arg_result>,
                       "task_select":   <task_arg_result>,
                       "video_select":  <video_arg_result>}
        
    Note that the keys can be modified using the output_key_prefix/suffix function arguments.
    For example, with output_key_prefix = "ini_" and output_key_suffix = "", the output dictionary keys would be:
        "ini_camera", "ini_user", "ini_task", "ini_video"
    '''

    # Set up argparser options
    ap = argparse.ArgumentParser()
    if enable_camera_select: ap.add_argument("-c", "--camera", default = None, type = str, help = "Camera select")
    if enable_user_select: ap.add_argument("-u", "--user", default = None, type = str, help = "User select")
    if enable_task_select: ap.add_argument("-t", "--task", default = None, type = str, help = "Task select")
    if enable_video_select: ap.add_argument("-v", "--video", default = None, type = str, help = "Video select")
    ap_result = vars(ap.parse_args())
    
    # Set up socket args, if needed
    if enable_socket_select:
        ap.add_argument("-sip", "--socketip", default = None, type = str, help = "Specify socket server IP address")
        ap.add_argument("-sport", "--socketport", default = None, type = str, help = "Specify socket server port")
    
    # Get script argument selections
    out_key = lambda base_label: "{}{}{}".format(output_key_prefix, base_label, output_key_suffix)
    output_dict = {out_key("camera"): ap_result.get("camera"),
                   out_key("user"): ap_result.get("user"),
                   out_key("task"): ap_result.get("task"),
                   out_key("video"): ap_result.get("video"),
                   out_key("socketip"): ap_result.get("socketip"),
                   out_key("socketport"): ap_result.get("socketport")}
    
    return output_dict


# ---------------------------------------------------------------------------------------------------------------------
#%% Demo 
    
if __name__ == "__main__":
    pass


# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap


