#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Jun 29 10:37:51 2020

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

from time import perf_counter

from local.lib.common.timekeeper_utils import Periodic_Polled_Timer, datetime_to_isoformat_string

from local.lib.file_access_utils.reporting import Station_Report_Data_Saver
from local.lib.file_access_utils.configurables import configurable_dot_path, unpack_config_data, unpack_access_info
from local.lib.file_access_utils.configurables import create_blank_configurable_data_dict, check_matching_access_info
from local.lib.file_access_utils.stations import build_station_config_folder_path, load_all_station_config_data

from local.eolib.utils.function_helpers import dynamic_import_from_module


# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes

class Station_Bundle:
    
    # .................................................................................................................
    
    def __init__(self, cameras_folder_path, camera_select, video_wh):
        
        '''
        Object which is responsible for loading, setting up, running and closing all 'station' configurations
        This object is also responsible for saving station data
        '''
        
        # Save selection info
        self.cameras_folder_path = cameras_folder_path
        self.camera_select = camera_select
        self.video_wh = video_wh
        
        # First make sure we have pathing to the station configs folder
        self.station_configs_folder_path = build_station_config_folder_path(cameras_folder_path, camera_select)
        
        # Allocate storage for configured data
        self.all_stations_config_paths_dict = None
        self.all_stations_config_dict = None
        self.all_stations_ref_dict = None
        
        # Set up periodic trigger used for saving station data
        self._save_timer = Periodic_Polled_Timer(trigger_on_first_check = False)
        
        # Allocate storage for saving the 'first' times of each data block that gets saved
        self._need_to_update_block_start_times = True
        self._first_frame_index = None
        self._first_epoch_ms = None
        self._first_datetime_isoformat = None
        
        # Store saving configs
        self.report_saving_enabled = None
        self.threaded_saving_enabled = None
        self._save_period_ms = None
        self._no_stations_for_saving = None
        
        # Set default behaviour states
        self.toggle_threaded_saving(False)
        self.toggle_report_saving(False)
        self.set_saving_period(minutes = 1, seconds = 0)
    
    # .................................................................................................................
    
    def __repr__(self):
        
        # Warning if no configuration data yet
        if self.all_stations_config_dict is None:
            return "Station Bundle not setup yet! Call .setup_all()"
        
        # Create list of strings to print
        repr_strs = ["Station Bundle",
                     "  camera: {}".format(self.camera_select)]
        
        # List all configured data
        for each_station_name, each_config_data_dict in self.all_stations_config_dict.items():
            
            access_info_dict, setup_data_dict = unpack_config_data(each_config_data_dict)
            script_name, class_name, _ = unpack_access_info(access_info_dict)
            num_properties = len(setup_data_dict)
            
            repr_strs += ["",
                          "--> {}".format(each_station_name),
                          "  Script: {}".format(script_name),
                          "   Class: {}".format(class_name),
                          "  ({} configured properties)".format(num_properties)]
        
        # Special output if nothing is loaded/configured
        no_stations = (len(self.all_stations_config_dict) == 0)
        if no_stations:
            repr_strs += ["", "--> No station data was found during setup!"]
        
        return "\n".join(repr_strs)
    
    # .................................................................................................................
    
    def close_all(self, current_frame_index, current_epoch_ms, current_datetime):
        
        ''' 
        Function which is called once the video ends (or is stopped/cancelled by user) 
        Each station must be called and is responsible for closing any opened resources
        
        Note that the bundler is also responsible for saving the (probably unfinished) blocks of data at this point
        '''
        
        # Some initial feedback
        print("Closing stations...", end = "")
        
        # Check if we could save the current dataset
        allow_save = False
        try:
            total_frames_in_block = (current_frame_index - self._first_frame_index)
            allow_save = (total_frames_in_block > 1)
        except TypeError:
            # Would occur if one of the frame index values (most like the internal storage) is 'None'
            # -> This implies we don't have 'good' data to save
            pass
        
        # Save all data at this point
        if allow_save:
            self._save_station_data(current_frame_index, current_epoch_ms, current_datetime)
        
        # Tell all stations to close
        for each_station_name, each_station_ref in self.all_stations_ref_dict.items():
            each_station_ref.close(current_frame_index, current_epoch_ms, current_datetime)
        
        # Final feedback
        print("Done!")
        
        return
    
    # .................................................................................................................
    
    def reset_all(self):
        
        ''' Function used to reset the state of the station bundle & all internal stations '''
        
        # If no stations have been loaded, we don't need to do anything
        if self.all_stations_ref_dict is None:
            return
        
        # Reset all station objects. Mostly for use in configuration, when the video may jump around
        for each_station_ref in self.all_stations_ref_dict.values():
            each_station_ref.reset()
        
        return
    
    # .................................................................................................................
    
    def toggle_report_saving(self, enable_data_saving):
        
        ''' Function used to disable saving. Useful during testing/configuration '''
        
        # Re-initialize the saver with new settings
        self.report_saving_enabled = enable_data_saving
        self._report_data_saver = self._initialize_report_data_saver()
        
    # .................................................................................................................
    
    def toggle_threaded_saving(self, enable_threaded_saving):
        
        ''' 
        Function used to enable or disable threading of data saving. 
        Mostly useful for testing out functionality (and avoiding complications from threading),
        or otherwise used during file evaluation, to force deterministic save timing
        '''
        
        # Re-initialize the saver with new settings
        self.threaded_saving_enabled = enable_threaded_saving
        self._report_data_saver = self._initialize_report_data_saver()
    
    # .................................................................................................................
    
    def set_saving_period(self, minutes = 0, seconds = 0, milliseconds = 0):
        
        ''' Function used to change rate at which the bundler saves station data '''
        
        self._save_timer.set_trigger_period(0, minutes, seconds, milliseconds)
        
    # .................................................................................................................
    
    def get_configs_for_reporting(self):
        
        '''
        Function called when running data collection. Used to save a reporting copy of station config data,
        so that configuration is accessible from a database
        '''
        
        return self.all_stations_config_dict
    
    # .................................................................................................................
    
    def setup_all(self, reset_on_startup = True):
        
        '''
        Function which loads all available station configs and instantiates all station objects
        
        Stores the configuration file pathing in 'all_stations_config_paths_dict'
        Stores the configuration data dictionaries in 'all_stations_config_dict'
        Stores the configured objects in 'all_stations_ref_dict'
        '''
        
        # For clarity
        set_configure_mode = False
        
        # Load all known data
        all_config_file_paths, all_config_data_dict = load_all_station_config_data(self.station_configs_folder_path)
        
        # Loop over all config data and load/configure all stations & store resulting objects
        all_stations_ref_dict = {}
        for each_station_name, each_config_dict in all_config_data_dict.items():
            station_ref = self._initialize_one_station_object(each_station_name, each_config_dict, set_configure_mode)
            all_stations_ref_dict.update({each_station_name: station_ref})
            
        # Store everything for re-use/debugging
        self.all_stations_config_paths_dict = all_config_file_paths
        self.all_stations_config_dict = all_config_data_dict
        self.all_stations_ref_dict = all_stations_ref_dict
        
        # Pre-check special case where we have no data to save
        self._no_stations_for_saving = (len(all_stations_ref_dict) == 0)
        
        # Reset everything to start
        if reset_on_startup:
            self.reset_all()
        
        return
    
    # .................................................................................................................
    
    def setup_one(self, station_name, script_name, class_name, reset_on_startup = True):
        
        '''
        Function which loads a single (target) station object. Intended for re-configuration
        If a station name is given which doesn't match an existing configuration file, this
        function will still instantiate the target script/class, but with no configuration data
        
        Otherwise behaves like the 'setup_all' function
        '''
        
        # For clarity
        set_configure_mode = True
        
        # Load all known data
        all_config_paths_dict, all_config_data_dict = load_all_station_config_data(self.station_configs_folder_path)
        
        # Create a blank configuration, which we'll use if we can't find an existing config to load
        single_config_data_dict = create_blank_configurable_data_dict(script_name, class_name)
        
        # Check if the station name is something we already know about, in which case use the existing config data
        station_already_exists = (station_name in all_config_data_dict.keys())
        if station_already_exists:
            existing_config_data_dict = all_config_data_dict[station_name]
            matches_target = check_matching_access_info(single_config_data_dict, existing_config_data_dict)
            single_config_data_dict = existing_config_data_dict if matches_target else single_config_data_dict
        
        # Load the single station object and store it as if we're loading many stations, for consistency
        station_ref = self._initialize_one_station_object(station_name, single_config_data_dict, set_configure_mode)
        all_stations_ref_dict = {station_name: station_ref}
        
        # Store everything for debugging
        self.all_stations_config_paths_dict = all_config_paths_dict
        self.all_stations_config_dict = all_config_data_dict
        self.all_stations_ref_dict = all_stations_ref_dict
        
        # Pre-check special case where we have no data to save
        self._no_stations_for_saving = (len(all_stations_ref_dict) == 0)
        
        # Reset everything to start
        if reset_on_startup:
            self.reset_all()
        
        return station_ref
    
    # .................................................................................................................
    
    def run_all(self, video_frame, background_image, background_was_updated,
                current_frame_index, current_epoch_ms, current_datetime):
        
        '''
        Function for running all station processing
        Takes in raw video frames and timing information
        Outputs:
            Nothing!
        '''
        
        # Update record of 'first' timing (which resets after each save block)
        if self._need_to_update_block_start_times:
            self._first_frame_index = current_frame_index
            self._first_epoch_ms = current_epoch_ms
            self._first_datetime_isoformat = datetime_to_isoformat_string(current_datetime)
            self._need_to_update_block_start_times = False
        
        # Loop through every run function and pass the current frame + background data
        station_timing_dict = {}
        for each_station_name, each_station_ref in self.all_stations_ref_dict.items():
            t1 = perf_counter()
            each_station_ref.run(video_frame,
                                 background_image, background_was_updated,
                                 current_frame_index, current_epoch_ms, current_datetime)
            t2 = perf_counter()
            station_timing_dict[each_station_name] = (t2 - t1)
        
        # Check timer to see if we need to save data
        need_to_save = self._save_timer.check_trigger(current_epoch_ms)
        if need_to_save:
            self._save_station_data(current_frame_index, current_epoch_ms, current_datetime)
            self._need_to_update_block_start_times = True
        
        return station_timing_dict
    
    # .................................................................................................................
    
    def _save_station_data(self, current_frame_index, current_epoch_ms, current_datetime):
        
        # Bail if we won't have any data to save
        if self._no_stations_for_saving:
            return {}
        
        # Build full metadata for saving
        metadata_dict = self._build_save_metadata(current_frame_index, current_epoch_ms, current_datetime)
        
        # Pass data to report saver for saving
        save_file_name = metadata_dict["_id"]
        self._report_data_saver.save_data(file_save_name_no_ext = save_file_name,
                                          metadata_dict = metadata_dict,
                                          json_double_precision = 3)
        
        return metadata_dict
    
    # .................................................................................................................
    
    def _build_save_metadata(self, current_frame_index, current_epoch_ms, current_datetime):
        
        ''' Helper function used to ensure consistent formatting of metadata being saved '''
        
        # Get data to save from each station object
        station_save_data_dict = {}
        for each_station_name, each_station_ref in self.all_stations_ref_dict.items():
            station_save_data_dict[each_station_name] = each_station_ref.output_data_list()
        
        # Save all stations with timing info into a single block
        save_id = self._first_epoch_ms
        metadata_dict = {"_id": save_id,
                         "first_frame_index": self._first_frame_index,
                         "first_epoch_ms": self._first_epoch_ms,
                         "first_datetime_isoformat": self._first_datetime_isoformat,
                         "final_frame_index": current_frame_index,
                         "final_epoch_ms": current_epoch_ms,
                         "final_datetime_isoformat": datetime_to_isoformat_string(current_datetime),
                         "stations": station_save_data_dict}
        
        return metadata_dict
    
    # .................................................................................................................
    
    def _initialize_one_station_object(self, station_name, station_config_data_dict, configure_mode = False):
        
        # For convenience
        input_wh = self.video_wh
        
        # Separate the raw data contained in the config file
        access_info_dict, setup_data_dict = unpack_config_data(station_config_data_dict)
        script_name, class_name, _ = unpack_access_info(access_info_dict)
        
        # Load the given station object
        import_dot_path = configurable_dot_path("stations", script_name)
        Imported_Station_Class = dynamic_import_from_module(import_dot_path, class_name)
        station_ref = Imported_Station_Class(station_name, self.cameras_folder_path, self.camera_select, input_wh)
        
        # Load initial configuration
        station_ref.set_configure_mode(configure_mode)
        station_ref.reconfigure(setup_data_dict)
        
        return station_ref
    
    # .................................................................................................................
    
    def _initialize_report_data_saver(self):
        
        ''' Helper function used to set/reset the report data saving object with new settings '''
        
        return Station_Report_Data_Saver(self.cameras_folder_path,
                                         self.camera_select,
                                         self.report_saving_enabled,
                                         self.threaded_saving_enabled)
    
    # .................................................................................................................
    # .................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Demo

if __name__ == "__main__":
    
    # Make selections for testing station bundle setup
    from local.lib.ui_utils.cli_selections import Resource_Selector
    selector = Resource_Selector(save_selection_history = False, create_folder_structure_on_select = False)
    camera_select, camera_path = selector.camera()
    video_select, _ = selector.video(camera_select)
    project_root_path, cameras_folder_path = selector.get_cameras_root_pathing()
    fake_video_wh = (100,100)
    
    sb = Station_Bundle(cameras_folder_path, camera_select, fake_video_wh)
    print("", "", "--- BEFORE SETUP ---", sep = "\n")
    print(sb)
    sb.setup_all()
    print("", "", "--- AFTER SETUP ---", sep = "\n")
    print(sb)


# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap


