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

from time import sleep

from local.lib.common.timekeeper_utils import get_human_readable_timestamp, get_human_readable_timezone
from local.lib.common.timekeeper_utils import get_local_datetime, datetime_to_isoformat_string, datetime_to_epoch_ms

from local.lib.ui_utils.cli_selections import Resource_Selector
from local.lib.ui_utils.script_arguments import script_arg_builder

from local.lib.launcher_utils.video_setup import File_Video_Reader, Threaded_File_Video_Reader, RTSP_Video_Reader
from local.lib.launcher_utils.core_bundle_loader import Core_Bundle

from local.configurables.configurable_template import configurable_dot_path

from local.lib.file_access_utils.pid_files import save_pid_file, clear_all_pid_files, clear_one_pid_file
from local.lib.file_access_utils.externals import build_externals_folder_path
from local.lib.file_access_utils.reporting import build_camera_info_metadata_report_path
from local.lib.file_access_utils.video import Playback_Access, load_rtsp_config
from local.lib.file_access_utils.screen_info import Screen_Info
from local.lib.file_access_utils.read_write import load_config_json, save_config_json, save_jgz
from local.lib.file_access_utils.read_write import dict_to_human_readable_output

from local.eolib.utils.cli_tools import cli_confirm
from local.eolib.utils.function_helpers import dynamic_import_from_module


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
        self.video_select = None
        self.script_arg_inputs = {}
        
        # Allocate storage for video data
        self.threaded_video_enabled = False
        self.vreader = None
        self.video_wh = None
        self.video_fps = None
        self.video_type = None
        self.playback_settings = None
        
        # Allocate storage for core processing bundle
        self.core_bundle = None
        
        # Allocate storage for preprocessor unwarping settings
        self.enable_unwarp = None
        self.unwarp_function = None
        
        # Allocate storage for externals
        self.bgcap = None
        self.snapcap = None
        self.objcap = None
        
        # Set saving behaviors
        self.saving_enabled = False
        self.threading_enabled = False
        
        # Storage for pid & script tracking
        self.calling_script_name = None
        self.pid = os.getpid()
        
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
        arg_camera_select = self.script_arg_inputs.get("camera", None)
        arg_user_select = self.script_arg_inputs.get("user", None)
        arg_video_select = self.script_arg_inputs.get("video", None)
        
        # Create selector so we can make camera/user/video selections
        selector = Resource_Selector()
        self.project_root_path, self.cameras_folder_path = selector.get_project_pathing()
        
        # Select shared components
        self.camera_select, _ = selector.camera(arg_camera_select)
        self.user_select, _ = selector.user(self.camera_select, arg_user_select)
        self.video_select, _ = selector.video(self.camera_select, arg_video_select)
        
        # Get additional information
        self.display_enabled = self.script_arg_inputs.get("display", False)
        self.threaded_video_enabled = self.script_arg_inputs.get("threaded_video", False)
        
        return self
    
    # .................................................................................................................
    
    def set_script_name(self, dunder_file):
        self.calling_script_name = os.path.basename(dunder_file)
    
    # .................................................................................................................
    
    def toggle_saving(self, enable_saving):
        self.saving_enabled = enable_saving
        
        # Warning if toggling after having run setup (toggle won't apply)
        if (self.vreader is not None):
            print("", "WARNING:", "  Saving should be enabled/disabled before running .setup_all()!", sep = "\n")
        
    # .................................................................................................................
    
    def toggle_threaded_saving(self, enable_threading):
        self.threading_enabled = enable_threading
        
        # Warning if toggling after having run setup (toggle won't apply)
        if (self.vreader is not None):
            print("", "WARNING:", "  Threading should be enabled/disabled before running .setup_all()!", sep = "\n")
      
    # .................................................................................................................
    
    def save_camera_info(self):
        
        # Get camera launch info
        rtsp_config, _ = load_rtsp_config(self.cameras_folder_path, self.camera_select)
        start_datetime = get_local_datetime()
        start_dt_str = datetime_to_isoformat_string(start_datetime)
        start_epoch_ms = datetime_to_epoch_ms(start_datetime)
        
        # Split snapshot sizing info for reporting
        video_width, video_height = self.video_wh
        snap_width, snap_height = self.snapcap.get_snapshot_wh()
        
        # Bundle info for saving
        caminfo_id = start_epoch_ms
        camera_info_dict = {"_id": caminfo_id,
                            "ip_address": rtsp_config.get("ip_address", "unknown"),
                            "time_zone": get_human_readable_timezone(),
                            "start_datetime_isoformat": start_dt_str,
                            "start_epoch_ms": start_epoch_ms,
                            "video_select": self.video_select,
                            "video_fps": self.video_fps,
                            "video_width": video_width,
                            "video_height": video_height,
                            "snapshot_width": snap_width,
                            "snapshot_height": snap_height}
        
        # Build pathing to the camera reporting folder & save
        if self.saving_enabled:
            camera_info_file_name = "caminfo-{}.json.gz".format(caminfo_id)
            camera_info_file_path = build_camera_info_metadata_report_path(self.cameras_folder_path,
                                                                           self.camera_select,
                                                                           self.user_select,
                                                                           camera_info_file_name)
            save_jgz(camera_info_file_path, camera_info_dict, create_missing_folder_path = True)
        
        return
        
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
        new_bgcap.toggle_threaded_saving(self.threading_enabled)
        
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
        new_snapcap.toggle_threaded_saving(self.threading_enabled)
        
        # Finally, store snapshot capture for re-use
        self.snapcap = new_snapcap
        
        return self.snapcap
    
    # .................................................................................................................
    
    def setup_object_capture(self):
        
        # Programmatically import the target object capture class
        Imported_Object_Capture_Class, setup_data_dict = self._import_externals_class("object_capture")
        shared_config = self._get_shared_config()
        
        # Retreive unwarping settings
        unwarp_config = {"enable_preprocessor_unwarp": self.enable_unwarp, 
                         "unwarp_function": self.unwarp_function}
        
        # Load & configure the object capturer
        new_objcap = Imported_Object_Capture_Class(**shared_config, **unwarp_config)
        new_objcap.reconfigure(setup_data_dict)
        
        # Enable/disable saving behaviors
        new_objcap.toggle_metadata_saving(self.saving_enabled)
        new_objcap.toggle_threaded_saving(self.threading_enabled)
        
        # Finally, store object capture for re-use
        self.objcap = new_objcap
        
        return self.objcap
    
    # .................................................................................................................
    
    def setup_externals(self):
        
        self.setup_background_capture()
        self.setup_snapshot_capture()
        self.setup_object_capture()
    
    # .................................................................................................................
    
    def setup_core_bundle(self):
        
        # Load core bundle
        shared_config = self._get_shared_config()
            
        # Set up full core bundle (i.e. all core stages configured)
        new_core_bundle = Core_Bundle(**shared_config)
        new_core_bundle.setup_all()
        
        # Pull out the preprocessor unwarping data and store it
        enable_preprocessor_unwarp, unwarp_function = new_core_bundle.get_preprocessor_unwarping()
        self.enable_unwarp = enable_preprocessor_unwarp
        self.unwarp_function = unwarp_function
        
        # Store the bundle for re-use
        self.core_bundle = new_core_bundle
        
        return self.core_bundle
    
    # .................................................................................................................
    
    def setup_all(self):
        
        # Get human readable timestamp for feedback
        start_timestamp = get_human_readable_timestamp()
        
        # Check/Record PID files to guarantee single file execution
        self._save_pid_file(start_timestamp)
        
        # Setup all main processing components
        self.setup_video_reader()
        self.setup_core_bundle()
        self.setup_externals()
        self.get_screen_info()
        
        # Save camera info on start-up, if needed
        self.save_camera_info()
        
        return start_timestamp
    
    # .................................................................................................................
    
    def clean_up(self):
        
        # Clean up video capture
        # ... handled by video loop for now
        
        # Clean up core system
        # ... handled by video loop for now
        
        # Clean up externals
        # ... handled by video loop for now
        
        # Clear PID tracking
        self._clear_pid_file()
        
    # .................................................................................................................
    
    def _import_externals_class(self, externals_type):
        
        # Check configuration file to see which script/class to load from & get configuration data
        _, file_access_dict, setup_data_dict = self._load_externals_config_data(externals_type)
        script_name = file_access_dict["script_name"]
        class_name = file_access_dict["class_name"]
        
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
        load_file_name_only, _ = os.path.splitext(json_file_name_no_ext)
        
        # Get path to externals config file
        load_file_with_ext = "{}.json".format(load_file_name_only)
        path_to_config = build_externals_folder_path(self.cameras_folder_path,
                                                     self.camera_select,
                                                     self.user_select,
                                                     load_file_with_ext)
        
        # Load json data and split into file access info & setup configuration data
        config_dict = load_config_json(path_to_config)
        access_info_dict = config_dict["access_info"]
        setup_data_dict = config_dict["setup_data"]
        
        return path_to_config, access_info_dict, setup_data_dict
    
    # .................................................................................................................
    
    def _get_shared_config(self):
        
        return {"cameras_folder_path": self.cameras_folder_path,
                "camera_select": self.camera_select,
                "user_select": self.user_select,
                "video_select": self.video_select,
                "video_wh": self.video_wh}
        
    # .................................................................................................................
    
    def _save_pid_file(self, start_timestamp_str):
        
        ''' Helper function for setting up initial PID file '''
        
        # Get rid of any existing PIDs, so we don't run parallel copies of the camera collection
        clear_all_pid_files(self.cameras_folder_path, self.camera_select, max_retrys = 5)
        
        # Save a new PID file to represent the system
        save_pid_file(self.cameras_folder_path, self.camera_select,
                      self.pid, self.calling_script_name, start_timestamp_str)
    
    # .................................................................................................................
    
    def _clear_pid_file(self):
        
        ''' Helper function for clearing out the PID file associated with this loader '''
        
        clear_one_pid_file(self.cameras_folder_path, self.camera_select, self.pid)

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
        arg_camera_select = self.script_arg_inputs.get("camera", None)
        arg_user_select = self.script_arg_inputs.get("user", None)
        
        # Create selector so we can make camera/user/video selections
        selector = Resource_Selector()
        self.project_root_path, self.cameras_folder_path = selector.get_project_pathing()
        
        # Select shared components
        self.camera_select, _ = selector.camera(arg_camera_select, must_have_rtsp = True)
        self.user_select, _ = selector.user(self.camera_select, arg_user_select)
        self.video_select = "rtsp"
        
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
        
    def parse_standard_args(self, debug_print = False):
        
        # Set script arguments for reconfigurable scripts
        args_list = ["camera", "user",  "video"]
        
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
        arg_camera_select = self.script_arg_inputs.get("camera", None)
        arg_user_select = self.script_arg_inputs.get("user", None)
        arg_video_select = self.script_arg_inputs.get("video", None)
        
        # Create selector so we can make camera/user/video selections
        selector = Resource_Selector()
        self.project_root_path, self.cameras_folder_path = selector.get_project_pathing()
        
        # Select shared components
        self.camera_select, _ = selector.camera(arg_camera_select)
        self.user_select, _ = selector.user(self.camera_select, arg_user_select)
        self.video_select, _ = selector.video(self.camera_select, arg_video_select)
        
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
        self.setup_core_bundle()
        self.setup_externals()
        self.get_screen_info()
        
        return self.configurable_ref
    
    # .................................................................................................................
    
    def reset_all(self):
        
        # Reset everything, typically due to the video jumping around during configuration
        self.snapcap.reset()
        self.bgcap.reset()
        self.objcap.reset()
        self.core_bundle.reset_all()
    
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
        is_passthrough = ("passthrough" in self.configurable_file_access_dict["script_name"])
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
                      dict_to_human_readable_output(save_data),
                      "", sep = "\n")
            
            return relative_save_path
        
        # If we get here, we're saving!
        save_config_json(save_path, save_data)
        if print_feedback:
            print("", "Saved configuration:", "@ {}".format(relative_save_path), "", sep = "\n")
        
        return relative_save_path
    
    # .................................................................................................................
    
    def _import_externals_class_with_override(self):
        
        # Check configuration file to see which script/class to load from & get configuration data
        path_to_config, file_access_dict, setup_data_dict = self._load_externals_config_data(self.override_stage)
        existing_script_name = file_access_dict["script_name"]
        existing_class_name = file_access_dict["class_name"]
        
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
    # .................................................................................................................


# =====================================================================================================================
# =====================================================================================================================

class Reconfigurable_Core_Stage_Loader(Reconfigurable_Loader):
    
    # .................................................................................................................
    
    def __init__(self, core_stage, script_name, class_name = None, selections_on_launch = True):
        
        # Inherit from parent class
        super().__init__(core_stage, script_name, class_name, selections_on_launch)
    
    # .................................................................................................................
    
    def setup_core_bundle(self):
        
        # Load core bundle
        shared_config = self._get_shared_config()
            
        # Set up full core bundle (i.e. all core stages configured)
        new_core_bundle = Core_Bundle(**shared_config)
        new_core_bundle.setup_all(self.override_stage, self.override_script, self.override_class)
        
        # Grab final core stage as a reconfigurable component
        configurable_stage_name, configurable_ref = new_core_bundle.last_item()
        config_path = new_core_bundle.final_stage_config_file_paths[configurable_stage_name]
        config_dict = new_core_bundle.final_stage_config_dict[configurable_stage_name]
        
        # Store configurable reference info
        self.configurable_ref = configurable_ref
        self.configurable_config_file_path = config_path
        self.configurable_file_access_dict = config_dict["access_info"]
        self.configurable_setup_data_dict = config_dict["setup_data"]
        
        '''
        ^^^ THIS CONFIGURABLE STUFF IS A BIT UGLY, BUT NOT THE END OF THE WORLD FOR NOW...
            - WOULD BE BETTER FOR THE LOADER OBJECT TO GRAB THE FILE PATHING STUFF AND HAND TO CORE BUNDLE TO SETUP
        '''
        
        # Pull out the preprocessor unwarping data and store it
        enable_preprocessor_unwarp, unwarp_function = new_core_bundle.get_preprocessor_unwarping()
        self.enable_unwarp = enable_preprocessor_unwarp
        self.unwarp_function = unwarp_function
        
        # Finally, store the bundle for re-use
        self.core_bundle = new_core_bundle
        
        return self.core_bundle
        
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
        new_snapcap.toggle_threaded_saving(self.threading_enabled)
        
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
        self.toggle_threaded_saving(False)
    
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
        new_bgcap.toggle_threaded_saving(self.threading_enabled)
        
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
        
        # Programmatically import the target object capture class
        Imported_Object_Capture_Class, setup_data_dict = self._import_externals_class_with_override()
        shared_config = self._get_shared_config()
        
        # Retreive unwarping settings
        unwarp_config = {"enable_preprocessor_unwarp": self.enable_unwarp, 
                         "unwarp_function": self.unwarp_function}
        
        # Load & configure the object capturer
        new_objcap = Imported_Object_Capture_Class(**shared_config, **unwarp_config)
        new_objcap.set_configure_mode()
        new_objcap.reconfigure(setup_data_dict)
        
        # Enable/disable saving behaviors
        new_objcap.toggle_metadata_saving(self.saving_enabled)
        new_objcap.toggle_threaded_saving(self.threading_enabled)
        
        # Finally, store the object capture
        self.objcap = new_objcap
        
        # Associate background capture with re-configurable object
        self.configurable_ref = self.objcap
        
        return self.objcap
    
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


