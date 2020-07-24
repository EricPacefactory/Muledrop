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

from local.lib.common.timekeeper_utils import get_human_readable_timestamp
from local.lib.common.timekeeper_utils import get_local_datetime, datetime_to_isoformat_string, datetime_to_epoch_ms
from local.lib.common.exceptions import OS_Close, register_signal_quit

from local.lib.ui_utils.cli_selections import Resource_Selector
from local.lib.ui_utils.script_arguments import script_arg_builder, get_selections_from_script_args
from local.lib.ui_utils.screen_info import Screen_Info

from local.lib.launcher_utils.video_setup import File_Video_Reader, Threaded_File_Video_Reader, RTSP_Video_Reader
from local.lib.launcher_utils.core_bundle_loader import Core_Bundle
from local.lib.launcher_utils.station_bundle_loader import Station_Bundle
from local.lib.launcher_utils.resource_initialization import initialize_background_and_framerate_from_file
from local.lib.launcher_utils.resource_initialization import initialize_background_and_framerate_from_rtsp

from local.lib.file_access_utils.shared import url_safe_name_from_path
from local.lib.file_access_utils.configurables import unpack_config_data, unpack_access_info, dynamic_import_externals
from local.lib.file_access_utils.externals import build_externals_folder_path
from local.lib.file_access_utils.reporting import build_camera_info_metadata_report_path
from local.lib.file_access_utils.reporting import build_config_info_metadata_report_path
from local.lib.file_access_utils.resources import reset_capture_folder, reset_generate_folder
from local.lib.file_access_utils.video import Playback_Access, load_rtsp_config
from local.lib.file_access_utils.stations import build_station_config_file_path
from local.lib.file_access_utils.state_files import shutdown_running_camera, save_state_file, delete_state_file
from local.lib.file_access_utils.json_read_write import load_config_json, save_config_json
from local.lib.file_access_utils.json_read_write import dict_to_human_readable_output
from local.lib.file_access_utils.metadata_read_write import save_jsongz_metadata

from local.eolib.utils.files import create_missing_folder_path
from local.eolib.utils.cli_tools import cli_confirm, cli_prompt_with_defaults
from local.eolib.utils.quitters import ide_quit


# ---------------------------------------------------------------------------------------------------------------------
#%% Define base classes

class File_Configuration_Loader:
    
    # .................................................................................................................
    
    def __init__(self):
        
        # Allocate storage for selections
        self.project_root_path = None
        self.location_select_folder_path = None
        self.location_select = None
        self.camera_select = None
        self.video_select = None
        
        # Allocate storage for video data
        self.threaded_video_enabled = False
        self.vreader = None
        self.video_wh = None
        self.video_fps = None
        self.video_type = None
        self.estimated_video_fps = None
        self.playback_settings = None
        
        # Allocate storage for core & station processing bundles
        self.core_bundle = None
        self.station_bundle = None
        
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
        self.screen_info = None
        
        # Set up special error handling
        register_signal_quit()
    
    # .................................................................................................................
    
    def __repr__(self):
        
        repr_strs = [self.__class__.__name__]
        repr_strs += ["     Camera: {}".format(self.camera_select),
                      "      Video: {}".format(self.video_select),
                      "  Threading: {}".format(self.threading_enabled),
                      "     Saving: {}".format(self.saving_enabled)]
        
        return "\n".join(repr_strs)
    
    # .................................................................................................................
    
    def selections(self,
                   arg_location_select = None,
                   arg_camera_select = None,
                   arg_video_select = None):
        
        # Create selector so we can make camera/video selections
        selector = Resource_Selector()
        
        # Get important pathing
        self.project_root_path, self.all_locations_folder_path = selector.get_shared_pathing()
        
        # Select data to run
        self.location_select, self.location_select_folder_path = selector.location(arg_location_select)
        self.camera_select, _ = selector.camera(self.location_select, arg_camera_select)
        self.video_select, _ = selector.video(self.location_select, self.camera_select, arg_video_select)
        
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
    
    def toggle_threaded_capture(self, enable_threaded_video_capture):        
        self.threaded_video_enabled = enable_threaded_video_capture
        
        # Warning if toggling after having run setup (toggle won't apply)
        if (self.vreader is not None):
            print("", "WARNING:", "  Threading should be enabled/disabled before running .setup_all()!", sep = "\n")
    
    # .................................................................................................................
    
    def save_camera_info(self, start_epoch_ms, start_datetime_isoformat):
        
        # Get camera launch info
        rtsp_config, _ = load_rtsp_config(self.location_select_folder_path, self.camera_select)
        
        # Split snapshot sizing info for reporting
        video_width, video_height = self.video_wh
        snap_width, snap_height = self.snapcap.get_snapshot_wh()
        
        # Bundle info for saving
        caminfo_id = start_epoch_ms
        camera_info_dict = {"_id": caminfo_id,
                            "ip_address": rtsp_config.get("ip_address", "unknown"),
                            "start_datetime_isoformat": start_datetime_isoformat,
                            "start_epoch_ms": start_epoch_ms,
                            "video_select": self.video_select,
                            "reported_video_fps": self.video_fps,
                            "estimated_video_fps": self.estimated_video_fps,
                            "video_width": video_width,
                            "video_height": video_height,
                            "snapshot_width": snap_width,
                            "snapshot_height": snap_height}
        
        # Build pathing to the camera reporting folder & save
        if self.saving_enabled:
            camera_info_folder_path = build_camera_info_metadata_report_path(self.location_select_folder_path,
                                                                             self.camera_select)
            create_missing_folder_path(camera_info_folder_path)
            save_jsongz_metadata(camera_info_folder_path, camera_info_dict)
        
        return
    
    # .................................................................................................................
    
    def save_config_info(self, start_epoch_ms, start_datetime_isoformat):
        
        ''' Function used to save all configuration data as a post-able output, so that it can end up in a db '''
        
        # Load all core & station config data for reporting
        core_configs_dict = self.core_bundle.get_configs_for_reporting()
        station_configs_dict = self.station_bundle.get_configs_for_reporting()
        
        # Load all externals config data for reporting
        externals_configs_dict = {"snapshots": self.snapcap.get_save_data_dict(),
                                  "backgrounds": self.bgcap.get_save_data_dict(),
                                  "objects": self.objcap.get_save_data_dict()}
        
        # Create final output dictionary
        configinfo_id = start_epoch_ms
        config_info_dict = {"_id": configinfo_id,
                            "start_datetime_isoformat": start_datetime_isoformat,
                            "start_epoch_ms": start_epoch_ms,
                            "config": {"core": core_configs_dict,
                                       "stations": station_configs_dict,
                                       "externals": externals_configs_dict}}
        
        # Build pathing to the config reporting folder & save
        if self.saving_enabled:
            config_folder_path = build_config_info_metadata_report_path(self.location_select_folder_path,
                                                                        self.camera_select)
            create_missing_folder_path(config_folder_path)
            save_jsongz_metadata(config_folder_path, config_info_dict)
        
        return
    
    # .................................................................................................................
    
    def get_screen_info(self):
        self.screen_info = Screen_Info(self.project_root_path)
    
    # .................................................................................................................
    
    def get_camera_pathing(self):
        
        '''
        Helper function used to get variables commonly needed for pathing
        
        Returns:
            location_select_folder_path, camera_select
        '''
        
        return self.location_select_folder_path, self.camera_select
    
    # .................................................................................................................
    
    def get_start_timing(self):
        
        '''
        Function used to get the start timing of the configuration, mean to be provided to saved metadata outputs
        to indicate when a new data collection run was started
        
        Inputs:
            Nothing!
        
        Outputs:
            start_epoch_ms, start_datetime_isoformat
        '''
        
        start_datetime = get_local_datetime()
        start_epoch_ms = datetime_to_epoch_ms(start_datetime)
        start_datetime_isoformat = datetime_to_isoformat_string(start_datetime)
        
        return start_epoch_ms, start_datetime_isoformat
    
    # .................................................................................................................
    
    def setup_video_reader(self):
        
        # Select video reader
        Video_Reader = File_Video_Reader
        if self.threaded_video_enabled:
            Video_Reader = Threaded_File_Video_Reader
            print("", "Threaded video capture enabled!", sep = "\n")

        # Set up the video source
        self.vreader = Video_Reader(self.location_select_folder_path, self.camera_select, self.video_select)
        self.video_wh = self.vreader.video_wh
        self.video_fps = self.vreader.video_fps
        self.video_type = self.vreader.video_type
        
        return self.vreader
    
    # .................................................................................................................
    
    def setup_core_bundle(self):
            
        # Set up full core bundle (i.e. all core stages configured)
        shared_config = self._get_shared_config()
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
    
    def setup_station_bundle(self):
        
        # Set up all station bundle (i.e. all stations configured)
        shared_config = self._get_shared_config()
        new_station_bundle = Station_Bundle(**shared_config)
        new_station_bundle.setup_all()
        
        # Enable/disable saving behaviors
        new_station_bundle.toggle_report_saving(self.saving_enabled)
        new_station_bundle.toggle_threaded_saving(self.threading_enabled)
        
        # Store bundle for re-use
        self.station_bundle = new_station_bundle
        
        return self.station_bundle
        
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
        new_snapcap.toggle_report_saving(self.saving_enabled)
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
        new_objcap.toggle_report_saving(self.saving_enabled)
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
    
    def setup_resources(self):
        
        # Make sure we always have a background image before doing anything else
        framerate_estimate = initialize_background_and_framerate_from_file(self.location_select_folder_path,
                                                                           self.camera_select,
                                                                           self.vreader,
                                                                           force_capture_reset = self.saving_enabled)
        
        # Store framerate estimate, which can report with camera info
        self.estimated_video_fps = framerate_estimate
        
        return
    
    # .................................................................................................................
    
    def setup_all(self):
        
        # Wrap in try/catch, since setup can take a while and may be interrupted
        try:
            
            # Set up access to video & make sure we have all resource before loading any other configs
            self.setup_video_reader()
            self.setup_resources()
            
        except KeyboardInterrupt:
            print("", "Keyboard cancelled! Quitting...", sep = "\n")
            self.close_video_reader()
            ide_quit()
        
        except OS_Close:
            print("", "System terminated during setup! Quitting...", sep = "\n")
            self.close_video_reader()
            ide_quit()
        
        # Get human readable timestamp for feedback
        human_start_timestamp = get_human_readable_timestamp()
        
        # Setup all main processing components
        self.setup_core_bundle()
        self.setup_station_bundle()
        self.setup_externals()
        self.get_screen_info()
        
        # Save camera & config info on start-up
        start_epoch_ms, start_datetime_isoformat = self.get_start_timing()
        self.save_camera_info(start_epoch_ms, start_datetime_isoformat)
        self.save_config_info(start_epoch_ms, start_datetime_isoformat)
    
        return human_start_timestamp
    
    # .................................................................................................................
    
    def clean_up(self, last_frame_index, last_epoch_ms, last_datetime):
        
        # For convenience
        fed_time_args = (last_frame_index, last_epoch_ms, last_datetime)
        
        # Clean up video capture
        self.close_video_reader()
        
        # Close externals
        self.snapcap.close(*fed_time_args)
        self.bgcap.close(*fed_time_args)
        
        # Close running core process & save any remaining objects
        final_stage_outputs = self.core_bundle.close_all(*fed_time_args)
        self.objcap.close(final_stage_outputs, *fed_time_args)
        
        # Close running stations & save any data in-progress
        self.station_bundle.close_all(*fed_time_args)
        
        return
    
    # .................................................................................................................
    
    def close_video_reader(self):
        
        ''' Helper function which will try to close the video reader, with very basic error handling '''
        
        try:
            self.vreader.close()
            
        except AttributeError:
            pass
            
        return
    
    # .................................................................................................................
    
    def _import_externals_class(self, externals_type):
        
        # Check configuration file to see which script/class to load from & get configuration data
        _, access_info_dict, setup_data_dict = self._load_externals_config_data(externals_type)
        script_name, _ = unpack_access_info(access_info_dict)
        
        # Programmatically import the target class
        Imported_Externals_Class = dynamic_import_externals(externals_type, script_name)
        
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
        path_to_config = build_externals_folder_path(self.location_select_folder_path,
                                                     self.camera_select,
                                                     load_file_with_ext)
        
        # Load json data and split into file access info & setup configuration data
        config_data_dict = load_config_json(path_to_config)
        access_info_dict, setup_data_dict = unpack_config_data(config_data_dict)
        
        return path_to_config, access_info_dict, setup_data_dict
    
    # .................................................................................................................
    
    def _get_shared_config(self):
        
        return {"location_select_folder_path": self.location_select_folder_path,
                "camera_select": self.camera_select,
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
    
    def selections(self,
                   arg_location_select = None,
                   arg_camera_select = None,
                   arg_video_select = "rtsp"):
        
        # Create selector so we can make camera/video selections
        # (Disable selection history save/load access, since RTSP may be called quickly by automated systems)
        selector = Resource_Selector(load_selection_history = False, save_selection_history = False)
        
        # Get important pathing
        self.project_root_path, self.all_locations_folder_path = selector.get_shared_pathing()
        
        # Select data to run
        self.location_select, self.location_select_folder_path = selector.location(arg_location_select)
        self.camera_select, _ = selector.camera(self.location_select, arg_camera_select, must_have_rtsp = True)
        self.video_select = arg_video_select
        
        return self
    
    # .................................................................................................................
    
    def setup_video_reader(self):
        
        # Select video reader
        Video_Reader = RTSP_Video_Reader
        if self.threaded_video_enabled:
            print("", "Threaded video capture is not yet implemented for RTSP!", sep = "\n")

        # Set up the video source
        self.vreader = Video_Reader(self.location_select_folder_path, self.camera_select)
        self.video_wh = self.vreader.video_wh
        self.video_fps = self.vreader.video_fps
        self.video_type = self.vreader.video_type
        
        return self.vreader
    
    # .................................................................................................................
    
    def setup_resources(self):
        
        # Make sure we always have a background image before doing anything else
        framerate_estimate = initialize_background_and_framerate_from_rtsp(self.location_select_folder_path,
                                                                           self.camera_select,
                                                                           self.vreader)
        
        # Store framerate estimate, which can report with camera info
        self.estimated_video_fps = framerate_estimate
        
        return
    
    # .................................................................................................................
    
    def shutdown_existing_camera_process(self, max_wait_sec = 300, force_kill_on_timeout = True):
        
        ''' Helper function to handle cleaning up existing camera process & state files '''
        
        return shutdown_running_camera(self.location_select_folder_path, self.camera_select,
                                       max_wait_sec, force_kill_on_timeout)
    
    # .................................................................................................................
    
    def update_state_file(self, state_description, *, in_standby = True):
        
        ''' Helper function used to update the camera state file descript and standby settings '''
        
        return save_state_file(self.location_select_folder_path, self.camera_select,
                               script_name = self.calling_script_name,
                               pid_value = self.pid,
                               in_standby = in_standby,
                               state_description_str = state_description)
    
    # .................................................................................................................
    
    def clear_state_file(self):
        
        ''' Helper function used to remove the camera state file (intended for use on shutdown only) '''
        
        return delete_state_file(self.location_select_folder_path, self.camera_select)    
    
    # .................................................................................................................
    # .................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Reconfigurable Implementations


class Reconfigurable_Loader(File_Configuration_Loader):
    
    # .................................................................................................................
    
    def __init__(self, override_stage, override_script_name):
        
        # Inherit from parent class
        super().__init__()
        
        # Allocate storage for accessing re-configurable object
        self.configurable_ref = None
        self.config_file_path = None
        self.loaded_access_info_dict = None
        self.loaded_setup_data_dict = None
        
        # Store overriding settings
        self.override_stage = override_stage
        self.override_script = override_script_name
        
        # Allocate storage for a playback settings access
        self.playback_access = None
        
        # Assume we want to turn off saving when working in a re-configuration mode
        self.saving_enabled = False
        self.threading_enabled = False
        
    # .................................................................................................................
        
    def parse_standard_args(self, debug_print = False):
        
        # Set script arguments for reconfigurable scripts
        args_list = ["location", "camera",  "video"]
        
        # Provide some extra information when accessing help text
        script_description_list = ["System configuration utility",
                                   "Can provide camera & video selection arguments to avoid menu prompts"]
        script_description_str = "\n".join(script_description_list)
        
        # Build & evaluate script arguments!
        ap_result = script_arg_builder(args_list,
                                       description = script_description_str,
                                       parse_on_call = True,
                                       debug_print = debug_print)
        
        # Split into location-select, camera_select, video_select on return to match selectons input args
        location_select, camera_select, video_select = get_selections_from_script_args(ap_result)
        
        return location_select, camera_select, video_select
    
    # .................................................................................................................
    
    def selections(self,
                   arg_location_select = None,
                   arg_camera_select = None,
                   arg_video_select = None):
        
        # Create selector so we can make camera/video selections
        selector = Resource_Selector()
        
        # Get important pathing
        self.project_root_path, self.all_locations_folder_path = selector.get_shared_pathing()
        
        # Select data to run
        self.location_select, self.location_select_folder_path = selector.location(arg_location_select)
        self.camera_select, _ = selector.camera(self.location_select, arg_camera_select)
        self.video_select, _ = selector.video(self.location_select, self.camera_select, arg_video_select)
        
        return self
    
    # .................................................................................................................
    
    def setup_all(self, file_dunder):
        
        # Set up access to video & make sure we have all resource before loading any other configs
        self.setup_video_reader()
        self.setup_resources()
        
        # Setup all main processing components
        self.setup_playback_access()
        self.setup_core_bundle()
        self.setup_station_bundle()
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
        self.station_bundle.reset_all()
    
    # .................................................................................................................
    
    def setup_playback_access(self):
        
        # Create object that can handle file i/o needed to access stored playback settings
        self.playback_access = Playback_Access(self.location_select_folder_path, self.camera_select, self.video_select)
        
        return self.playback_access
    
    # .................................................................................................................
    
    def get_save_path(self):
        
        ''' Function used to allow overrides when deciding how to construct save pathing '''
        
        # By default, use the internal storage path if it's available
        save_path = self.config_file_path
        if save_path is None:
            raise NameError("Error: Can't save because 'config_file_path' is missing!")
        
        return self.config_file_path

    # .................................................................................................................
    
    def ask_to_save_configurable_cli(self, configuration_utility_file_dunder, configurable_ref):
        
        # Get save data from configurable & add configuration utility info
        save_data_dict = configurable_ref.get_save_data_dict(configuration_utility_file_dunder)
        access_info_dict, setup_data_dict = unpack_config_data(save_data_dict)
        curr_script_name, _ = unpack_access_info(access_info_dict)
        
        # Only save if the saved data has changed
        is_passthrough = ("passthrough" in curr_script_name)
        access_info_changed = (self.loaded_access_info_dict != access_info_dict)
        setup_data_changed = (self.loaded_setup_data_dict != setup_data_dict)
        need_to_save = (access_info_changed or setup_data_changed or is_passthrough)
        
        # Handle feedback for saving or not
        if need_to_save:
            self._ask_to_save_data(save_data_dict)
        else:
            print("", "Settings unchanged!", "Skipping save prompt...", "", sep="\n")
        
        # Delay slightly before closing, may help with strange out-of-order errors on Windows 10?
        sleep(0.25)

    # .................................................................................................................
    
    def _ask_to_save_data(self, save_data_dict, print_feedback = True):
        
        # Provide prompt to user for saving
        user_confirm_save = cli_confirm("Save settings?", default_response = False)
        
        # Get pathing to save
        save_path = None
        if user_confirm_save:
            save_path = self.get_save_path()
        
        # Don't save
        if not user_confirm_save or not save_path:
            
            # Give feedback
            if print_feedback:
                print("",
                      "Here are the config settings, in case that cancel was an accident!",
                      "",
                      "Save data:",
                      dict_to_human_readable_output(save_data_dict),
                      "", sep = "\n")
            
            return
        
        # If we get here, we're saving!
        save_config_json(save_path, save_data_dict)
        relative_save_path = os.path.relpath(save_path, self.location_select_folder_path)
        if print_feedback:
            print("", "Saved configuration:", "@ {}".format(relative_save_path), "", sep = "\n")
        
        return
    
    # .................................................................................................................
    
    def _import_externals_class_with_override(self):
        
        # Check configuration file to see which script/class to load from & get configuration data
        path_to_config, access_info_dict, setup_data_dict = self._load_externals_config_data(self.override_stage)
        existing_script_name, _ = unpack_access_info(access_info_dict)
        
        # If we're loading a different script from what was saved, wipe out the loaded data
        matching_script = (existing_script_name == self.override_script)
        if not matching_script:
            access_info_dict = {}
            setup_data_dict = {}
        
        # Programmatically import the target class
        Imported_Externals_Class = dynamic_import_externals(self.override_stage, self.override_script)
        
        # Save data to re-access the override script
        self.config_file_path = path_to_config
        self.loaded_access_info_dict = access_info_dict
        self.loaded_setup_data_dict = setup_data_dict
        
        return Imported_Externals_Class, setup_data_dict
        
    # .................................................................................................................
    # .................................................................................................................


# =====================================================================================================================
# =====================================================================================================================


class Reconfigurable_Core_Stage_Loader(Reconfigurable_Loader):
    
    # .................................................................................................................
    
    def __init__(self, core_stage, script_name):
        
        # Inherit from parent class
        super().__init__(core_stage, script_name)
        
        # We want to turn off saving when working in a re-configuration mode
        self.toggle_saving(False)
        self.toggle_threaded_saving(False)
    
    # .................................................................................................................
    
    def setup_core_bundle(self):
            
        # Set up full core bundle (i.e. all core stages configured)
        shared_config = self._get_shared_config()
        new_core_bundle = Core_Bundle(**shared_config)
        new_core_bundle.setup_all(self.override_stage, self.override_script)
        
        # Grab final core stage as a reconfigurable component
        configurable_stage_name, configurable_ref = new_core_bundle.last_item()
        config_file_path = new_core_bundle.final_stage_config_file_paths[configurable_stage_name]
        config_data_dict = new_core_bundle.final_stage_config_dict[configurable_stage_name]
        
        # Store configurable reference info
        access_info_dict, setup_data_dict = unpack_config_data(config_data_dict)
        self.configurable_ref = configurable_ref
        self.config_file_path = config_file_path
        self.loaded_access_info_dict = access_info_dict
        self.loaded_setup_data_dict = setup_data_dict
        
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


class Reconfigurable_Single_Station_Loader(Reconfigurable_Loader):
    
    # .................................................................................................................
    
    def __init__(self, script_name):
        
        # The station to override is chosen by the user, after selecting a camera. So cannot be given on init!
        override_stage = None
        
        # Inherit from parent class
        super().__init__(override_stage, script_name)
        
        # Add entry for holding station selection when loading
        self.station_select = None
        
        # We want to turn off saving when working in a re-configuration mode
        self.toggle_saving(False)
        self.toggle_threaded_saving(False)
    
    # .................................................................................................................
    
    def select_station(self):
        
        # Create selector so we can make station selection
        selector = Resource_Selector()
        
        # Select shared components
        self.station_select, _ = selector.station(self.location_select, self.camera_select, self.override_script)
        
        return self
    
    # .................................................................................................................
    
    def setup_station_bundle(self):
        
        # Set up only the target station for re-configuring
        shared_config = self._get_shared_config()
        new_station_bundle = Station_Bundle(**shared_config)
        station_ref = new_station_bundle.setup_one(self.station_select,
                                                   self.override_script,
                                                   reset_on_startup = True)
        
        # Enable/disable saving behaviors
        new_station_bundle.toggle_report_saving(self.saving_enabled)
        new_station_bundle.toggle_threaded_saving(self.threading_enabled)
        
        # Store bundle for re-use
        self.station_bundle = new_station_bundle
        
        # Associate single station with re-configurable object
        self.configurable_ref = station_ref
        
        return self.station_bundle
    
    # .................................................................................................................
    
    def get_save_path(self):
        
        # OVERRIDE: Allows for station name entry before saving (if needed)
        
        # Check if we already have a name, if not, we need to ask for one
        need_station_name = (self.station_select is None)
        
        # Provide prompt to user for saving
        if need_station_name:
            user_station_name = cli_prompt_with_defaults("Enter station name: ")
            if not user_station_name:
                return None
            self.station_select = user_station_name
        
        # Build the save path
        safe_station_name = url_safe_name_from_path(self.station_select)
        save_path = build_station_config_file_path(self.location_select_folder_path,
                                                   self.camera_select,
                                                   safe_station_name)
        
        return save_path
    
    # .................................................................................................................
    # .................................................................................................................


# =====================================================================================================================
# =====================================================================================================================


class Reconfigurable_Snapshot_Capture_Loader(Reconfigurable_Loader):
    
    # .................................................................................................................
    
    def __init__(self, script_name):
        
        # Inherit from parent class
        super().__init__("snapshot_capture", script_name)
        
        # We want to turn off saving when working in a re-configuration mode
        self.toggle_saving(False)
        self.toggle_threaded_saving(False)
    
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
        new_snapcap.toggle_report_saving(self.saving_enabled)
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
    
    def __init__(self, script_name):
        
        # Inherit from parent class
        super().__init__("background_capture", script_name)
        
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
        new_bgcap.toggle_report_saving(False)
        new_bgcap.toggle_resource_saving(self.saving_enabled)
        new_bgcap.toggle_threaded_saving(self.threading_enabled)
        
        # Give user warning about file i/o usage
        print("", 
              "",
              "WARNING:",
              "  Data saving (background capture & generated images) will be enabled for configuration purposes!",
              sep = "\n")
        
        # Finally, store background capture for re-use
        self.bgcap = new_bgcap
        
        # Associate background capture with re-configurable object
        self.configurable_ref = self.bgcap
        
        return self.bgcap
    
    # .................................................................................................................
    
    def ask_to_reset_resources(self):
        
        '''
        Helper function intended to help ensure a 'clean' starting point when running background configs
        This is especially useful in cases where existing background data is used to generate future backgrounds
        '''
        
        # Always reset captures
        reset_capture_folder(self.location_select_folder_path, self.camera_select)
        
        # Make sure user confirms resource reset
        user_confirm_reset = cli_confirm("Reset existing background resources?")
        if user_confirm_reset:
            reset_generate_folder(self.location_select_folder_path, self.camera_select)
        
        return user_confirm_reset
    
    # .................................................................................................................
    # .................................................................................................................


# =====================================================================================================================
# =====================================================================================================================


class Reconfigurable_Object_Capture_Loader(Reconfigurable_Loader):
    
    # .................................................................................................................
    
    def __init__(self, script_name):
        
        # Inherit from parent class
        super().__init__("object_capture", script_name)
        
        # We want to turn off saving when working in a re-configuration mode
        self.toggle_saving(False)
        self.toggle_threaded_saving(False)
    
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
        new_objcap.toggle_report_saving(self.saving_enabled)
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


