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

import json

from time import sleep

from local.lib.configuration_utils.script_arguments import script_arg_builder

from local.lib.selection_utils import Resource_Selector
from local.lib.configuration_utils.video_setup import File_Video_Reader, Threaded_File_Video_Reader, RTSP_Video_Reader

from local.lib.configuration_utils.core_bundle_loader import Core_Bundle
from local.lib.file_access_utils.video import Playback_Access
from local.lib.file_access_utils.screen_info import Screen_Info
from local.lib.file_access_utils.shared import configurable_dot_path, full_replace_save

from eolib.utils.cli_tools import cli_confirm
from eolib.utils.function_helpers import dynamic_import_from_module
from eolib.utils.read_write import load_json

# ---------------------------------------------------------------------------------------------------------------------
#%% Define base classes

class File_Configuration_Loader:
    
    # .................................................................................................................
    
    def __init__(self):
        
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
        self.threaded_video_enabled = False
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
        self.display_enabled = False
        self.screen_info = None
            
    # .................................................................................................................
    
    def __repr__(self):
        
        repr_strs = [self.__class__.__name__]
        repr_strs += ["     Camera: {}".format(self.camera_select),
                      "       User: {}".format(self.user_select),
                      "      Video: {}".format(self.video_select),
                      "  Threading: {}".format(self.threading_enabled),
                      "     Saving: {}".format(self.saving_enabled)]
        
        return "\n".join(repr_strs)
    
    # .................................................................................................................
    
    def selections(self, script_args_dict):
        
        # Store script arguments
        self.script_arg_inputs = script_args_dict
        
        # Pull out input script argument values
        arg_camera_select = self.script_arg_inputs.get("camera")
        arg_user_select = self.script_arg_inputs.get("user")
        arg_video_select = self.script_arg_inputs.get("video")
        
        # Create selector so we can make camera/user/video selections
        selector = Resource_Selector()
        self.project_root_path, self.cameras_folder_path = selector.get_project_pathing()
        
        # Select shared components
        self.camera_select, _ = selector.camera(arg_camera_select)
        self.user_select, _ = selector.user(self.camera_select, arg_user_select)
        self.video_select, _ = selector.video(self.camera_select, arg_video_select)
        
        # Find list of all tasks
        self.task_name_list = selector.get_task_list(self.camera_select, self.user_select)
        
        # Get additional information
        self.display_enabled = self.script_arg_inputs.get("display", False)
        self.threaded_video_enabled = self.script_arg_inputs.get("threaded_video", False)
        
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
        
        # Select video reader
        Video_Reader = File_Video_Reader
        if self.threaded_video_enabled:
            Video_Reader = Threaded_File_Video_Reader
            print("", "Threaded video capture enabled!", sep = "\n")

        # Set up the video source
        self.vreader = Video_Reader(self.cameras_folder_path, self.camera_select, self.video_select)
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


# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////


class RTSP_Configuration_Loader(File_Configuration_Loader):
    
    # .................................................................................................................
    
    def __init__(self):
    
        # Inherit from parent class
        super().__init__()
        
    # .................................................................................................................
    
    def selections(self, script_args_dict = {}):
        
        # Store script arguments
        self.script_arg_inputs = script_args_dict
        
        # Pull out input script argument values
        arg_camera_select = self.script_arg_inputs.get("camera")
        arg_user_select = self.script_arg_inputs.get("user")
        
        # Create selector so we can make camera/user/video selections
        selector = Resource_Selector()
        self.project_root_path, self.cameras_folder_path = selector.get_project_pathing()
        
        # Select shared components
        self.camera_select, _ = selector.camera(arg_camera_select, must_have_rtsp = True)
        self.user_select, _ = selector.user(self.camera_select, arg_user_select)
        self.video_select = "rtsp"
        
        # Find list of all tasks
        self.task_name_list = selector.get_task_list(self.camera_select, self.user_select)
        
        # Get additional information
        self.display_enabled = self.script_arg_inputs.get("display", False)
        self.threaded_video_enabled = self.script_arg_inputs.get("threaded_video", False)
        
        return self
    
    # .................................................................................................................
    
    def setup_video_reader(self):
        
        # Select video reader
        Video_Reader = RTSP_Video_Reader
        if self.threaded_video_enabled:
            #Video_Reader = Threaded_RTSP_Video_Reader
            print("", "Threaded video capture is not yet implemented for RTSP!", sep = "\n")

        # Set up the video source
        self.vreader = Video_Reader(self.cameras_folder_path, self.camera_select)
        self.video_wh = self.vreader.video_wh
        self.video_fps = self.vreader.video_fps
        self.video_type = self.vreader.video_type
        
        return self.vreader
    
    # .................................................................................................................
    # .................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Reconfigurable Implementations


class Reconfigurable_Loader(File_Configuration_Loader):
    
    # .................................................................................................................
    
    def __init__(self, override_stage, override_script_name, override_class_name = None,
                 selections_on_launch = True):
        
        # Inherit from parent class
        super().__init__()
        
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
            script_args_dict = self.parse_standard_args()
            self.selections(script_args_dict)
        
    # .................................................................................................................
        
    def parse_standard_args(self, debug_print = True):
        
        # Set script arguments for reconfigurable scripts
        args_list = ["camera", "user",  "task", "video"]
        
        # Provide some extra information when accessing help text
        script_description = "Reconfigure settings for {} stage".format(self.override_stage.replace("_", " "))
        
        # Build & evaluate script arguments!
        ap_result = script_arg_builder(args_list,
                                       description = script_description,
                                       parse_on_call = True,
                                       debug_print = debug_print)        
        return ap_result
    
    # .................................................................................................................
    
    def selections(self, script_args_dict):
        
        # Store script arguments
        self.script_arg_inputs = script_args_dict
        
        # Pull out input script argument values
        arg_camera_select = self.script_arg_inputs.get("camera")
        arg_user_select = self.script_arg_inputs.get("user")
        arg_task_select = self.script_arg_inputs.get("task")
        arg_video_select = self.script_arg_inputs.get("video")
        
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
        
        # Hard-code out options intended for run-time
        self.display_enabled = True
        self.threaded_video_enabled = False
        
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
        
        # Delay slightly before closing, may help with strange out-of-order errors on Windows 10?
        sleep(0.25)

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

# .....................................................................................................................

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Demo 
    
if __name__ == "__main__":
    pass


# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap


