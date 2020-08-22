#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Oct 16 16:55:07 2019

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

import sqlite3
import numpy as np

from time import perf_counter

from local.lib.common.timekeeper_utils import any_time_type_to_epoch_ms, isoformat_to_datetime

from local.lib.file_access_utils.reporting import build_camera_info_metadata_report_path
from local.lib.file_access_utils.reporting import build_config_info_metadata_report_path
from local.lib.file_access_utils.reporting import build_snapshot_image_report_path
from local.lib.file_access_utils.reporting import build_snapshot_metadata_report_path
from local.lib.file_access_utils.reporting import build_object_metadata_report_path
from local.lib.file_access_utils.reporting import build_station_metadata_report_path

from local.lib.file_access_utils.classifier import load_reserved_labels_lut, load_topclass_labels_lut
from local.lib.file_access_utils.classifier import reserved_notrain_label
from local.lib.file_access_utils.classifier import new_classifier_report_entry
from local.lib.file_access_utils.classifier import build_classifier_adb_metadata_report_path

from local.lib.file_access_utils.summary import build_summary_adb_metadata_report_path

from local.lib.file_access_utils.rules import save_rule_report_data
from local.lib.file_access_utils.rules import build_rule_adb_metadata_report_path
from local.lib.file_access_utils.rules import build_rule_adb_info_report_path
from local.lib.file_access_utils.rules import new_rule_report_entry

from local.lib.file_access_utils.metadata_read_write import fast_dict_to_json, fast_json_to_dict, load_metadata
from local.lib.file_access_utils.image_read_write import read_encoded_jpg, decode_image_data

from local.eolib.utils.files import get_file_list, get_folder_list, get_total_folder_size


# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes

class File_DB:
    
    # Create lookup table for mapping python data types to sqlite3 types
    _table_data_type_lut = {str: "TEXT", int: "INTEGER", bool: "INTEGER", float: "REAL"}
    
    # .................................................................................................................
    
    def __init__(self, location_select_folder_path, camera_select,
                 primary_key, required_keys_set,
                 db_path = ":memory:", check_same_thread = True, debug_connect = False):
        
        # Store camera selections
        self.location_select_folder_path = location_select_folder_path
        self.camera_select = camera_select
        
        # Store key info
        self._primary_key = primary_key
        self._required_keys_set = required_keys_set
        self._metadata_key = "metadata_json"
        self._ordered_key_list = [primary_key, *sorted(list(required_keys_set))]
        
        # Build (internal) table name
        self._table_name = "[{}-{}]".format(self.camera_select, self._class_name)
        self._table_created = False
        
        # Allocate storage for db info
        self.db_path = db_path
        self._connection = None
        
        # Start up the database!
        self._connection = self.connect(check_same_thread, debug_connect)
    
    # .................................................................................................................
    
    def __repr__(self):
        return "File DB: {}".format(self._table_name)
    
    # .................................................................................................................
    
    @property
    def _class_name(self):
        return self.__class__.__name__
    
    # .................................................................................................................
    
    @classmethod
    def _get_table_data_type(cls, python_data_type):
        return cls._table_data_type_lut[python_data_type]
    
    # .................................................................................................................
    
    def _cursor(self):
        return self._connection.cursor()
    
    # .................................................................................................................
    
    def _fetchall(self, cursor_command, *, return_if_missing):
        
        ''' Helper function used to handle fetchall cases, with error handling '''
        
        try:
            cursor = self._cursor()
            cursor.execute(cursor_command)
            fetchall_data = cursor.fetchall()
        except sqlite3.OperationalError:
            fetchall_data = return_if_missing
        
        return fetchall_data
    
    # .................................................................................................................
    
    def _fetch_1d_list(self, cursor_command, *, return_if_missing = None, return_index = 0, sort_results = True):
        
        ''' Helper function used to handle fetchall cases when expecting a 1d list, with error handling '''
        
        try:
            cursor = self._cursor()
            cursor.execute(cursor_command)
            fetchall_data = cursor.fetchall()
        except sqlite3.OperationalError:
            missing_data = [] if return_if_missing is None else return_if_missing
            return missing_data
        
        return fetchall_to_1d_list(fetchall_data, return_index, sort_results)
    
    # .................................................................................................................
    
    def _fetchone_item(self, cursor_command, *, return_if_missing = None, return_index = 0):
        
        try:
            cursor = self._cursor()
            cursor.execute(cursor_command)
            fetchone_result = cursor.fetchone()
        except sqlite3.OperationalError:
            return return_if_missing
        
        return fetchone_result[return_index]
    
    # .................................................................................................................
    
    def _fetchone_tuple(self, cursor_command, *, return_if_missing = None):
        
        try:
            cursor = self._cursor()
            cursor.execute(cursor_command)
            fetchone_result = cursor.fetchone()
        except sqlite3.OperationalError:
            fetchone_result = return_if_missing
        
        return fetchone_result
    
    # .................................................................................................................
    
    def list_table_columns(self):
        
        if not self._table_created:
            return ["Table not yet created!"]
        
        cursor_command = "PRAGMA TABLE_INFO({})".format(self._table_name)
        column_names_list = self._fetch_1d_list(cursor_command, return_index = 1, sort_results = False)
        
        return column_names_list

    # .................................................................................................................
    
    def head(self, number_to_return = 5):
        
        ''' Function used to inspect the top few elements of the database '''
        
        # Build database commands
        get_top_entries_cmd = "SELECT * FROM {} LIMIT {}".format(self._table_name, number_to_return)
        
        # Get few top rows
        top_entries = self._fetchall(get_top_entries_cmd, return_if_missing = None)
        if top_entries is None:
            print("", self._table_name, "No data!", sep = "\n")
            return
        
        # Print column names followed by example entries
        column_names_list = self.list_table_columns()
        print("",
              self._table_name,
              "COLUMNS: {}".format(", ".join(column_names_list)), "",
              *top_entries,
              sep = "\n")
        
        return
        
    # .................................................................................................................
    
    def connect(self, check_same_thread = True, debug_connect = False):
        
        connection = None
        try:
            connection = sqlite3.connect(self.db_path, check_same_thread = check_same_thread)
            if debug_connect:
                print("", "Starting {}. SQLITE Version: {}".format(self._class_name, sqlite3.version), sep = "\n")
        except Exception as err:
            print("Error connecting to file DB! ({})".format(self.db_path))
            raise err
        
        return connection
    
    # .................................................................................................................
    
    def add_entry(self, metadata_dict):
        
        # Build list of values to insert for each key, with typecasting for dictionaries
        insert_keys_list = []
        insert_values_list = []
        for each_key in self._ordered_key_list:
            
            # Type-case python data types to sqlite data types
            value_to_insert = metadata_dict[each_key]
            value_type = type(value_to_insert)
            if value_type is dict:
                value_to_insert = fast_dict_to_json(value_to_insert)
            elif value_type is list:
                value_to_insert = fast_dict_to_json(value_to_insert)
            
            # Build outputs
            insert_keys_list.append(each_key)
            insert_values_list.append(value_to_insert)
        
        # Add final entry which holds the entire metadata as a single json value
        metadata_as_json = fast_dict_to_json(metadata_dict)
        insert_keys_list.append(self._metadata_key)
        insert_values_list.append(metadata_as_json)
        
        # Insert the data into the table
        self._create_table_if_missing(insert_keys_list, insert_values_list)
        self._insert_into_table(insert_keys_list, insert_values_list)
    
    # .................................................................................................................
    
    def no_data(self):
        
        ''' Helper function which returns true if there is no data in the database '''
        
        # Build command to find at least one data entry
        select_cmd = "SELECT * FROM {} LIMIT 1".format(self._table_name)
        
        # Query the db and check if anything comes back
        single_data_entry = self._fetchone_item(select_cmd, return_if_missing = None)
        if single_data_entry is None:
            return True
    
        return False
    
    # .................................................................................................................
    
    def close(self):
        
        if self._connection is not None:
            self._connection.close()
        
        return
    
    # .................................................................................................................
    
    def _create_table_if_missing(self, insert_keys_list, insert_values_list):
        
        # Create the first table, if needed. Assumes all data will have the same formatting!
        if not self._table_created:
            self._create_initial_table(insert_keys_list, insert_values_list)
            self._table_created = True
        
        return self._table_name
    
    # .................................................................................................................
    
    def _create_initial_table(self, insert_keys_list, insert_values_list):
        
        # Make sure the insertion keys are valid before we create a table with them
        self._check_keys_are_valid(insert_keys_list)
        
        # Build primary key suffix for tagging one of the keys so the table builds correctly
        no_primary_key_suffix = ""
        is_primary_key_suffix = "PRIMARY KEY"
        
        # If we haven't created the table yet, we'll need to figure it out now, based on the incoming keys/data types
        table_columns_str_list = []
        for each_key, each_value in zip(insert_keys_list, insert_values_list):
            
            # Determine what kind of value we're going to try to insert
            key_is_primary = (each_key == self._primary_key)
            python_data_type = type(each_value)
            table_data_type = self._get_table_data_type(python_data_type)
            
            # Build list of column entries
            # Example entry: "epoch_ms INTEGER"
            key_suffix = is_primary_key_suffix if key_is_primary else no_primary_key_suffix
            new_col_str = "{} {}{}".format(each_key, table_data_type, key_suffix)
            table_columns_str_list.append(new_col_str)
        
        # Create table in db
        table_columns_full_str = ", ".join(table_columns_str_list)
        create_table_cmd = "CREATE TABLE {}({})".format(self._table_name, table_columns_full_str)
        self._cursor().execute(create_table_cmd)
        self._connection.commit()
        
        '''
        # DEBUG
        print("Created table ({})".format(self._table_name))
        print("Columns:")
        print("", table_columns_full_str)
        '''
        
        return
    
    # .................................................................................................................
    
    def _check_keys_are_valid(self, insert_keys_list):
        
        '''
        Helper function used to check if insert keys are valid
        Raises an error if not valid
        Returns nothing
        '''
        
        # For convenience
        table_name = self._table_name
        
        # First check that data includes the required values
        insert_keys_set = set(insert_keys_list)
        has_primary_key = (self._primary_key in insert_keys_list)
        has_required_keys = insert_keys_set.issuperset(self._required_keys_set)
        
        # Raise errors if needed
        if not has_primary_key:
            print("", "","Got keys:", insert_keys_set, "", sep = "\n")
            raise AttributeError("Missing primary key ({}) for table: {}".format(self._primary_key, table_name))
        if not has_required_keys:
            print("", "","Got keys:", insert_keys_set, "", sep = "\n")
            req_keys_str = ", ".join(self._required_keys_set)
            raise AttributeError("Missing required keys ({}) for table: {}".format(req_keys_str, table_name))
        
        return
    
    # .................................................................................................................
    
    def _insert_into_table(self, insert_keys_list, insert_values_list):
        
        # Build insert command
        insert_qs_list = "?" * len(insert_keys_list)
        insert_keys_str = ", ".join(insert_keys_list)
        insert_qs_str = ",".join(insert_qs_list)
        insert_cmd = "INSERT INTO {}({}) VALUES({})".format(self._table_name, insert_keys_str, insert_qs_str)
        
        # Update the database!
        cursor = self._cursor()
        cursor.execute(insert_cmd, insert_values_list)
        self._connection.commit()
    
    # .................................................................................................................
    # .................................................................................................................


# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////


class Camera_Info_DB(File_DB):
    
    # .................................................................................................................
    
    def __init__(self, location_select_folder_path, camera_select,
                 db_path = ":memory:", check_same_thread = True, debug_connect = False):
        
        # Build key info
        primary_key = "start_epoch_ms"
        required_keys_set = {"ip_address",
                             "snapshot_width", "snapshot_height",
                             "video_width", "video_height"}
        
        # Inherit from parent
        super().__init__(location_select_folder_path, camera_select, primary_key, required_keys_set,
                         db_path, check_same_thread, debug_connect)
    
    # .................................................................................................................
    
    def get_all_start_ems(self):
        
        # Build string to get all camera start times
        select_cmd = "SELECT start_epoch_ms FROM {}".format(self._table_name)
        
        # Get data from database!
        start_ems_list = self._fetch_1d_list(select_cmd)
        
        return start_ems_list
    
    # .................................................................................................................
    
    def get_all_camera_info(self):
        
        # Build string to get all camera info
        select_cmd = "SELECT {} FROM {}".format(self._metadata_key, self._table_name)
        
        # Get data from database!
        camera_info_json_list = self._fetch_1d_list(select_cmd, return_if_missing = ["{}"])
        
        # Convert json to python dictionary so we can wield it
        camera_info_dict_list = [fast_json_to_dict(each_entry) for each_entry in camera_info_json_list]
        
        return camera_info_dict_list
    
    # .................................................................................................................
    
    def get_video_frame_wh(self):
        
        # Build selection commands
        select_cmd = "SELECT video_width, video_height FROM {} LIMIT 1".format(self._table_name)
        
        # Get data from database!
        video_wh = self._fetchone_tuple(select_cmd, return_if_missing = (0, 0))
        
        return video_wh
    
    # .................................................................................................................
    
    def get_snap_frame_wh(self):
        
        # Build selection commands
        select_cmd = "SELECT snapshot_width, snapshot_height FROM {} LIMIT 1".format(self._table_name)
        
        # Get data from database!
        snap_wh = self._fetchone_tuple(select_cmd, return_if_missing = (0, 0))
        
        return snap_wh
    
    # .................................................................................................................
    
    def load_metadata_by_ems(self, target_start_epoch_ms):
        
        '''
        Function which returns camera metadata for a given (start) epoch timing
        
        Inputs:
            target start epoch_ms time (must be a valid time!)
        
        Outputs:
            metadata_dictionary
        '''
        
        
        # Build selection commands
        select_cmd = "SELECT {} FROM {} WHERE start_epoch_ms = {}".format(self._metadata_key,
                                                                          self._table_name,
                                                                          target_start_epoch_ms)
        
        # Get data from database!
        metadata_json = self._fetchone_item(select_cmd, return_if_missing = None)
        if metadata_json is None:
            metadata_json = "{}"
        
        # Convert to python dictionary so we can actually interact with it!
        metadata_dict = fast_json_to_dict(metadata_json)
        
        return metadata_dict
    
    # .................................................................................................................
    # .................................................................................................................


# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////


class Config_Info_DB(File_DB):
    
    # .................................................................................................................
    
    def __init__(self, location_select_folder_path, camera_select,
                 db_path = ":memory:", check_same_thread = True, debug_connect = False):
        
        # Build key info
        primary_key = "start_epoch_ms"
        required_keys_set = {"start_datetime_isoformat", "config"}
        
        # Inherit from parent
        super().__init__(location_select_folder_path, camera_select, primary_key, required_keys_set,
                         db_path, check_same_thread, debug_connect)
    
    # .................................................................................................................
    
    def get_all_start_ems(self):
        
        # Build string to get all start times
        select_cmd = "SELECT start_epoch_ms FROM {}".format(self._table_name)
        
        # Get data from database!
        start_ems_list = self._fetch_1d_list(select_cmd)
        
        return start_ems_list
    
    # .................................................................................................................
    
    def get_all_config_info(self):
        
        # Build string to get all configuration info
        select_cmd = "SELECT {} FROM {}".format(self._metadata_key, self._table_name)
        
        # Get data from database!
        config_info_json_list = self._fetch_1d_list(select_cmd, return_if_missing = ["{}"])
        
        # Convert json to python dictionary so we can wield it
        config_info_dict_list = [fast_json_to_dict(each_entry) for each_entry in config_info_json_list]
        
        return config_info_dict_list
    
    # .................................................................................................................
    
    def load_metadata_by_ems(self, target_start_epoch_ms):
        
        '''
        Function which returns configuration metadata for a given (start) epoch timing
        
        Inputs:
            target start epoch_ms time (must be a valid time!)
        
        Outputs:
            metadata_dictionary
        '''
        
        
        # Build selection commands
        select_cmd = "SELECT {} FROM {} WHERE start_epoch_ms = {}".format(self._metadata_key,
                                                                          self._table_name,
                                                                          target_start_epoch_ms)
        
        # Get data from database!
        metadata_json = self._fetchone_item(select_cmd, return_if_missing = None)
        if metadata_json is None:
            metadata_json = "{}"
        
        # Convert to python dictionary so we can actually interact with it!
        metadata_dict = fast_json_to_dict(metadata_json)
        
        return metadata_dict
    
    # .................................................................................................................
    # .................................................................................................................


# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////


class Rule_Info_DB(File_DB):
    
    # .................................................................................................................
    
    def __init__(self, location_select_folder_path, camera_select,
                 db_path = ":memory:", check_same_thread = True, debug_connect = False):
        
        # Build key info
        primary_key = "rule_name"
        required_keys_set = {"rule_type"}
        
        # Inherit from parent
        super().__init__(location_select_folder_path, camera_select, primary_key, required_keys_set,
                         db_path, check_same_thread, debug_connect)
        
    # .................................................................................................................
    
    def get_all_rule_names(self):
        
        # Build string to get all rule info
        select_cmd = "SELECT rule_name FROM {}".format(self._table_name)
        
        # Get data from database!
        rule_name_list = self._fetch_1d_list(select_cmd)
        if rule_name_list is None:
            rule_name_list = []
        
        return rule_name_list
    
    # .................................................................................................................
    
    def get_rule_info(self):
        
        # Build string to get all rule info
        select_cmd = "SELECT * FROM {}".format(self._table_name)
        
        # Get data from database!
        rule_info_list = self._fetchall(select_cmd, return_if_missing = None)
        if rule_info_list is None:
            rule_info_list = []
        
        # Bundle each rule info entry into a dictionary, separated by rule names (keys)
        rule_info_result_dict = {}
        for each_rule_name, each_rule_type, each_configuration_json in rule_info_list:
            configuration_dict = fast_json_to_dict(each_configuration_json)            
            rule_info_result_dict[each_rule_name] = {"rule_type": each_rule_type,
                                                     "configuration": configuration_dict}
        
        return rule_info_result_dict
    
    # .................................................................................................................
    # .................................................................................................................


# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////


class Background_DB(File_DB):
    
    # .................................................................................................................
    
    def __init__(self, location_select_folder_path, camera_select,
                 db_path = ":memory:", check_same_thread = True, debug_connect = False):
        
        # Build key info
        primary_key = "epoch_ms"
        required_keys_set = {"frame_index"}
        
        # Inherit from parent
        super().__init__(location_select_folder_path, camera_select, primary_key, required_keys_set,
                         db_path, check_same_thread, debug_connect)
        
    # .................................................................................................................
    # .................................................................................................................


# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////


class Snap_DB(File_DB):
    
    # .................................................................................................................
    
    def __init__(self, location_select_folder_path, camera_select,
                 db_path = ":memory:", check_same_thread = True, debug_connect = False):
        
        # Build key info
        primary_key = "epoch_ms"
        required_keys_set = {"frame_index", "datetime_isoformat"}
        
        # Inherit from parent
        super().__init__(location_select_folder_path, camera_select, primary_key, required_keys_set,
                         db_path, check_same_thread, debug_connect)
        
        # Set up pathing to load image data
        self.snap_images_folder_path = build_snapshot_image_report_path(location_select_folder_path,
                                                                        camera_select)
            
        # Check that the snapshot path is valid before continuing
        snapshot_image_folder_exists = os.path.exists(self.snap_images_folder_path)
        if not snapshot_image_folder_exists:
            raise FileNotFoundError("Couldn't find snapshot image folder:\n{}".format(self.snap_images_folder_path))
        
        # Check how big the image folder is, to see if it makes sense to try to cache jpg data
        _, _, snap_image_folder_size_mb, _ = get_total_folder_size(self.snap_images_folder_path)
        self._enable_jpg_cache = (snap_image_folder_size_mb < 800)
        self._snap_jpg_cache = {}
    
    # .................................................................................................................
    
    def get_total_snapshot_count(self):
        
        # Build string to total snapshot count
        select_cmd = "SELECT count(epoch_ms) FROM {}".format(self._table_name)
        
        # Get data from database!
        snapshot_count = self._fetchone_item(select_cmd, return_if_missing = -1)
        
        return snapshot_count
    
    # .................................................................................................................
    
    def get_bounding_epoch_ms(self):
        
        # Build string to get min/max datetimes from snapshots
        select_cmd = "SELECT min(epoch_ms), max(epoch_ms) FROM {}".format(self._table_name)
        
        # Get data from database!
        min_epoch_ms, max_epoch_ms = self._fetchone_tuple(select_cmd, return_if_missing = (-1, 1))
        
        return min_epoch_ms, max_epoch_ms
    
    # .................................................................................................................
    
    def get_bounding_datetimes(self):
        
        # First get bounding epoch times of bounding snapshots
        min_epoch_ms, max_epoch_ms = self.get_bounding_epoch_ms()
        
        # Build string to get the corresponding datetime strings for the bounding epoch values
        select_min_cmd = "SELECT datetime_isoformat FROM {} WHERE epoch_ms = {}".format(self._table_name,
                                                                                        min_epoch_ms)
        select_max_cmd = "SELECT datetime_isoformat FROM {} WHERE epoch_ms = {}".format(self._table_name,
                                                                                        max_epoch_ms)
        
        # Get data from database!
        min_dt_isoformat = self._fetchone_item(select_min_cmd, return_if_missing = -1)
        max_dt_isoformat = self._fetchone_item(select_max_cmd, return_if_missing = -1)
        
        # Finally, convert datetime isoformat strings back to datetime objects
        min_dt = isoformat_to_datetime(min_dt_isoformat)
        max_dt = isoformat_to_datetime(max_dt_isoformat)
        
        return min_dt, max_dt
    
    # .................................................................................................................
    
    def get_all_snapshot_times_by_time_range(self, start_time, end_time):
        
        # Convert input times to epoch values
        start_epoch_ms = any_time_type_to_epoch_ms(start_time)
        end_epoch_ms = any_time_type_to_epoch_ms(end_time)
        
        # Build command string for getting all snapshot times between start/end
        select_cmd = "SELECT epoch_ms FROM {} WHERE epoch_ms BETWEEN {} and {}".format(self._table_name,
                                                                                       start_epoch_ms,
                                                                                       end_epoch_ms)
        
        # Get data from database!
        all_snapshot_epoch_ms_times_list = self._fetch_1d_list(select_cmd)
        
        return all_snapshot_epoch_ms_times_list
    
    # .................................................................................................................
    
    def get_datetime_by_ems(self, target_ems, return_as_string = False, string_format = "%H:%M:%S"):
        
        # Build command string for getting snapshot datetime based on ems value
        select_cmd = "SELECT datetime_isoformat FROM {} WHERE epoch_ms = {}".format(self._table_name,
                                                                                    target_ems)
        
        # Get data from database!
        target_dt_isoformat = self._fetchone_item(select_cmd, return_if_missing = None)
        if target_dt_isoformat is None:
            return None
        
        # Convert to a datetime object or a string if needed
        target_dt = isoformat_to_datetime(target_dt_isoformat)
        if return_as_string:
            return target_dt.strftime(string_format)
        
        return target_dt
    
    # .................................................................................................................
    
    def get_n_snapshot_times(self, start_time, end_time, n = 10):
        
        # Get all snapshot data first
        all_snapshot_epoch_ms_times = self.get_all_snapshot_times_by_time_range(start_time, end_time)
        
        # Sub-sample the snapshot entries to get 'n' outputs
        num_snapshots = len(all_snapshot_epoch_ms_times)
        final_n = min(num_snapshots, max(2, n))
        subsample_indices = np.int32(np.round(np.linspace(0, num_snapshots - 1, final_n)))
        n_snapshot_epochs = [all_snapshot_epoch_ms_times[each_idx] for each_idx in subsample_indices]
        
        return n_snapshot_epochs
    
    # .................................................................................................................
    
    def get_closest_snapshot_epoch(self, target_time):
        
        ''' 
        Function which takes an input time and returns snapshot epochs that are closest to the input 
        Inputs:
            target_time --> Can be of type: epoch value, datetime object, isoformat datetime string,
        
        Outputs:
            floor_closest_epoch_ms, closest_epoch_ms, ceil_closest_epoch_ms
            
        *** Note, the floor/ceil outputs are the bounding times around the given target time.
            The middle output (closest_epoch_ms) is whichever bounding time is closest to the target
            (favors the floor time if the bounds are equidistant from the target!)
        '''
        
        # Convert time input into an epoch_ms value to search database
        target_epoch_ms = any_time_type_to_epoch_ms(target_time)
        
        # Build selection commands
        ceil_select_cmd = """
                          SELECT min(epoch_ms) 
                          FROM {} 
                          WHERE epoch_ms >= {} 
                          LIMIT 1
                          """.format(self._table_name, target_epoch_ms)
                          
        floor_select_cmd = """
                           SELECT max(epoch_ms) 
                           FROM {} 
                           WHERE epoch_ms <= {} 
                           LIMIT 1
                           """.format(self._table_name, target_epoch_ms)
        
        
        # Get lower bound snapshot
        floor_snapshot_epoch_ms = self._fetchone_item(floor_select_cmd, return_if_missing = None)
        no_floor = (floor_snapshot_epoch_ms is None)
        
        # Get upper bound snapshot
        ceil_snapshot_epoch_ms = self._fetchone_item(ceil_select_cmd, return_if_missing = None)
        no_ceil = (ceil_snapshot_epoch_ms is None)
        
        # Deal with missing return values
        if no_floor and no_ceil:
            raise FileNotFoundError("Couldn't find close snapshots in database! ({})".format(target_time))
        if no_ceil:
            ceil_snapshot_epoch_ms = floor_snapshot_epoch_ms
        if no_floor:
            floor_snapshot_epoch_ms = ceil_snapshot_epoch_ms
        
        # Finally, grab the resulting values and figure out which is actually closest to the input time
        upper_is_closer = ((ceil_snapshot_epoch_ms - target_epoch_ms) > (target_epoch_ms - floor_snapshot_epoch_ms))
        closest_snapshot_epoch_ms = ceil_snapshot_epoch_ms if upper_is_closer else floor_snapshot_epoch_ms
        
        # Bundle as a dictionary for more explicit usage
        return_dict = {"lower_epoch_ms": floor_snapshot_epoch_ms,
                       "closest_epoch_ms": closest_snapshot_epoch_ms,
                       "upper_epoch_ms": ceil_snapshot_epoch_ms}
        
        return return_dict
    
    # .................................................................................................................
    
    def load_snapshot_metadata_by_frame_index(self, target_frame_index):
        
        '''
        Function which returns snapshot metadata for a given epoch timing
        
        Inputs:
            target snapshot epoch_ms time (must be a valid time!)
        
        Outputs:
            metadata_dictionary
        '''
        
        # Build selection commands
        select_cmd = "SELECT {} FROM {} WHERE frame_index = {}".format(self._metadata_key,
                                                                       self._table_name,
                                                                       target_frame_index)
        
        # Get data from database!
        metadata_json = self._fetchone_item(select_cmd, return_if_missing = None)
        if metadata_json is None:
            metadata_json = "{}"
        
        # Convert to python dictionary so we can actually interact with it!
        metadata_dict = fast_json_to_dict(metadata_json)
        
        return metadata_dict
    
    # .................................................................................................................
    
    def load_snapshot_metadata_by_ems(self, target_epoch_ms):
        
        '''
        Function which returns snapshot metadata for a given epoch timing
        
        Inputs:
            target snapshot epoch_ms time (must be a valid time!)
        
        Outputs:
            metadata_dictionary
        '''
        
        
        # Build selection commands
        select_cmd = "SELECT {} FROM {} WHERE epoch_ms = {}".format(self._metadata_key,
                                                                    self._table_name,
                                                                    target_epoch_ms)
        
        # Get data from database!
        metadata_json = self._fetchone_item(select_cmd, return_if_missing = None)
        if metadata_json is None:
            metadata_json = "{}"
        
        # Convert to python dictionary so we can actually interact with it!
        metadata_dict = fast_json_to_dict(metadata_json)
        
        return metadata_dict
    
    # .................................................................................................................
    
    def load_snapshot_image(self, target_epoch_ms):
        
        '''
        Function which loads image data for a snapshot at the given target epoch_ms time
        
        Inputs:
            target snapshot epoch_ms time (must be a valid time!)
        
        Outputs:
            snapshot_image, snapshot_frame_index
        '''
        
        # First get snapshot metadata, so we can look up the correct image by name
        snap_md = self.load_snapshot_metadata_by_ems(target_epoch_ms)
        snap_epoch_ms = snap_md["epoch_ms"]
        snap_frame_index = snap_md["frame_index"]
        
        # If caching is enabled, first check if we already have the image data
        have_target_jpg = (target_epoch_ms in self._snap_jpg_cache)
        if self._enable_jpg_cache and have_target_jpg:
            jpg_data_array = self._snap_jpg_cache[target_epoch_ms]
            image_data = decode_image_data(jpg_data_array)
            return image_data, snap_frame_index
        
        # Read the jpg data and store it if we're caching jpgs
        jpg_data_array = read_encoded_jpg(self.snap_images_folder_path, snap_epoch_ms)
        image_data = decode_image_data(jpg_data_array)
        if self._enable_jpg_cache:
            self._snap_jpg_cache[target_epoch_ms] = jpg_data_array
        
        return image_data, snap_frame_index
    
    # .................................................................................................................
    # .................................................................................................................


# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////


class Object_DB(File_DB):
    
    # .................................................................................................................
    
    def __init__(self, location_select_folder_path, camera_select,
                 db_path = ":memory:", check_same_thread = True, debug_connect = False):
        
        # Build key info
        primary_key = "full_id"
        required_keys_set = {"first_epoch_ms", "final_epoch_ms",
                             "first_frame_index", "final_frame_index",
                             "tracking"}
        
        # Inherit from parent
        super().__init__(location_select_folder_path, camera_select, primary_key, required_keys_set,
                         db_path, check_same_thread, debug_connect)
    
    # .................................................................................................................
    
    def get_total_object_count(self):
        
        # Build string to get total object count
        select_cmd = "SELECT count(full_id) FROM {}".format(self._table_name)
        
        # Get data from database!
        total_object_count = self._fetchone_item(select_cmd, return_if_missing = -1)
        
        return total_object_count
    
    # .................................................................................................................
    
    def get_object_ids_by_time_range(self, start_time, end_time):
        
        # Convert time values into epoch_ms values for searching
        start_epoch_ms = any_time_type_to_epoch_ms(start_time)
        end_epoch_ms = any_time_type_to_epoch_ms(end_time)
        
        # Build selection commands
        select_cmd = """
                     SELECT full_id
                     FROM {}
                     WHERE 
                     final_epoch_ms >= {} 
                     AND 
                     first_epoch_ms <= {}
                     """.format(self._table_name, start_epoch_ms, end_epoch_ms)
                     
        # Get data from database!
        object_ids_list = self._fetch_1d_list(select_cmd)
        
        return object_ids_list
    
    # .................................................................................................................
    
    def get_ids_at_target_time(self, target_time):
        
        # Convert time value into epoch_ms value to search database
        target_epoch_ms = any_time_type_to_epoch_ms(target_time)
        
        # Build selection commands
        select_cmd = """
                     SELECT full_id
                     FROM {}
                     WHERE {} 
                     BETWEEN 
                     first_epoch_ms AND final_epoch_ms
                     """.format(self._table_name, target_epoch_ms)
                     
        # Get data from database!
        object_ids_list = self._fetch_1d_list(select_cmd)
        
        return object_ids_list
    
    # .................................................................................................................
    
    def load_metadata_by_id(self, object_id):
        
        # Build selection commands
        select_cmd = "SELECT {} FROM {} WHERE full_id = {}".format(self._metadata_key, self._table_name, object_id)
        
        # Get data from database!
        metadata_json = self._fetchone_item(select_cmd, return_if_missing = None)
        if metadata_json is None:
            metadata_json = "{}"
        
        # Convert to python dictionary so we can actually interact with it!
        metadata_dict = fast_json_to_dict(metadata_json)
        
        return metadata_dict
    
    # .................................................................................................................
    
    def load_metadata_by_time_range(self, start_time, end_time):
        
        ''' Acts as a generator! '''
        
        # First get all object IDs for the given time range
        object_id_list = self.get_object_ids_by_time_range(start_time, end_time)
        
        # Return all object metadata, using a generator
        for each_obj_id in object_id_list:
            yield self.load_metadata_by_id(each_obj_id)
        
        return
    
    # .................................................................................................................
    # .................................................................................................................
    

# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////


class Classification_DB(File_DB):
    
    # .................................................................................................................
    
    def __init__(self, location_select_folder_path, camera_select,
                 db_path = ":memory:", check_same_thread = True, debug_connect = False):
        
        # Load classification labels & colors
        self.reserved_labels_lut = load_reserved_labels_lut(location_select_folder_path, camera_select)
        self.topclass_labels_lut = load_topclass_labels_lut(location_select_folder_path, camera_select)
        self.all_label_colors_lut = {**self.reserved_labels_lut, **self.topclass_labels_lut}
        
        # Load reference to special label that is meant as a training directive only
        self.no_train_label, _ = reserved_notrain_label()
        
        # Get pathing to 'local' classification results
        self.local_classification_folder = build_classifier_adb_metadata_report_path(location_select_folder_path,
                                                                                     camera_select)
        
        # Build key info
        primary_key = "full_id"
        required_keys_set = {"topclass_label", "topclass_dict"}
        
        # Inherit from parent
        super().__init__(location_select_folder_path, camera_select, primary_key, required_keys_set,
                         db_path, check_same_thread, debug_connect)
    
    # .................................................................................................................
    
    def get_label_color(self, classification_label, missing_label_color = (0, 255, 255)):
        
        # Look up coloring from class label lookup tables
        outline_color = self.all_label_colors_lut[classification_label]
        
        return outline_color
    
    # .................................................................................................................
    
    def get_label_color_luts(self):
        
        '''
        Function which just returns the color mapping for all class labels
        
        Outputs:
            reserved_colors_dict, topclass_colors_dict, all_colors_dict
        '''
        
        return self.reserved_labels_lut, self.topclass_labels_lut, self.all_label_colors_lut
    
    # .................................................................................................................
    
    def get_all_object_ids(self):
        
        # Build selection commands
        select_cmd = "SELECT full_id FROM {}".format(self._table_name)
        
        # Get data from database!
        object_id_list = self._fetch_1d_list(select_cmd)
        
        return object_id_list
    
    # .................................................................................................................
    
    def load_classification_data(self, object_id):
        
        # Build selection commands
        select_cmd = """SELECT topclass_label, topclass_dict
                        FROM {} 
                        WHERE full_id = {}""".format(self._table_name, object_id)
        
        # Get data from database!
        topclass_label, topclass_dict_as_json = self._fetchone_tuple(select_cmd, return_if_missing = (None, None))
        
        # Convert json data to python dictionary
        if topclass_dict_as_json is not None:
            topclass_dict = fast_json_to_dict(topclass_dict_as_json)
        
        # Handle missing data
        if topclass_label is None:
            default_class_data = new_classifier_report_entry(object_id)
            topclass_label = default_class_data["topclass_label"]
            topclass_dict = default_class_data["topclass_dict"]
        
        return topclass_label, topclass_dict
    
    # .................................................................................................................
    
    def ordered_class_names(self):
        
        ''' Helper function to get class labels in sorted order '''
        
        # Order by reserved than topclass
        sorted_reserved_labels = sorted(list(self.reserved_labels_lut.keys()))
        sorted_topclass_labels = sorted(list(self.topclass_labels_lut.keys()))
        sorted_all_labels = sorted_reserved_labels + sorted_topclass_labels
        
        return sorted_all_labels
    
    # .................................................................................................................
    # .................................................................................................................

# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////


class Summary_DB(File_DB):
    
    # .................................................................................................................
    
    def __init__(self, location_select_folder_path, camera_select,
                 db_path = ":memory:", check_same_thread = True, debug_connect = False):
        
        # Build key info
        primary_key = "full_id"
        required_keys_set = {}
        
        # Inherit from parent
        super().__init__(location_select_folder_path, camera_select, primary_key, required_keys_set,
                         db_path, check_same_thread, debug_connect)
    
    # .................................................................................................................
    
    def load_summary_data(self, object_id):
        
        # Build selection commands
        select_cmd = """SELECT metadata_json FROM {} WHERE full_id = {}""".format(self._table_name, object_id)
        
        # Get data from database!
        summary_data_json = self._fetchone_item(select_cmd, return_if_missing = None)
        if summary_data_json is None:
            summary_data_json = "{}"
        
        # Convert to a dictionary for python usage
        summary_data_dict = fast_json_to_dict(summary_data_json)
        
        return summary_data_dict
    
    # .................................................................................................................
    # .................................................................................................................


# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////

class Stations_DB(File_DB):
    
    # .................................................................................................................
    
    def __init__(self, location_select_folder_path, camera_select,
                 db_path = ":memory:", check_same_thread = True, debug_connect = False):
        
        # Build key info
        primary_key = "first_epoch_ms"
        required_keys_set = {"final_epoch_ms",
                             "first_frame_index", "final_frame_index",
                             "first_datetime_isoformat", "final_datetime_isoformat",
                             "stations"}
        
        # Inherit from parent
        super().__init__(location_select_folder_path, camera_select, primary_key, required_keys_set,
                         db_path, check_same_thread, debug_connect)
    
    # .................................................................................................................
    
    def get_bounding_epoch_ms(self):
        
        # Build string to get min/max datetimes from snapshots
        select_cmd = "SELECT min(first_epoch_ms), max(final_epoch_ms) FROM {}".format(self._table_name)
        
        # Get data from database!
        min_epoch_ms, max_epoch_ms = self._fetchone_tuple(select_cmd, return_if_missing = (-1, 1))
        
        return min_epoch_ms, max_epoch_ms
    
    # .................................................................................................................
    
    def get_bounding_datetimes(self):
        
        # First get bounding epoch times of bounding snapshots
        min_epoch_ms, max_epoch_ms = self.get_bounding_epoch_ms()
        
        # Build string to get the corresponding datetime strings for the bounding epoch values
        select_min_cmd = "SELECT first_datetime_isoformat FROM {} WHERE epoch_ms = {}".format(self._table_name,
                                                                                              min_epoch_ms)
        select_max_cmd = "SELECT final_datetime_isoformat FROM {} WHERE epoch_ms = {}".format(self._table_name,
                                                                                              max_epoch_ms)
        
        # Get data from database!
        min_dt_isoformat = self._fetchone_item(select_min_cmd, return_if_missing = -1)
        max_dt_isoformat = self._fetchone_item(select_max_cmd, return_if_missing = -1)
        
        # Finally, convert datetime isoformat strings back to datetime objects
        min_dt = isoformat_to_datetime(min_dt_isoformat)
        max_dt = isoformat_to_datetime(max_dt_isoformat)
        
        return min_dt, max_dt
    
    # .................................................................................................................
    
    def get_all_station_start_times_by_time_range(self, start_time, end_time):
        
        # Convert input times to epoch values
        start_epoch_ms = any_time_type_to_epoch_ms(start_time)
        end_epoch_ms = any_time_type_to_epoch_ms(end_time)
        
        # Build selection commands
        select_cmd = """
                     SELECT first_epoch_ms
                     FROM {}
                     WHERE
                     final_epoch_ms >= {}
                     AND
                     first_epoch_ms <= {}
                     """.format(self._table_name, start_epoch_ms, end_epoch_ms)
        
        # Get data from database!
        all_snapshot_epoch_ms_times_list = self._fetch_1d_list(select_cmd)
        
        return all_snapshot_epoch_ms_times_list
    
    # .................................................................................................................
    
    def load_metadata_by_ems(self, target_epoch_ms):
        
        '''
        Function which returns station metadata for a given epoch timing
        
        Inputs:
            target station epoch_ms time (must be a valid time!)
        
        Outputs:
            metadata_dictionary
        '''
        
        # Build selection commands
        select_cmd = "SELECT {} FROM {} WHERE first_epoch_ms = {}".format(self._metadata_key,
                                                                          self._table_name,
                                                                          target_epoch_ms)
        
        # Get data from database!
        metadata_json = self._fetchone_item(select_cmd, return_if_missing = None)
        if metadata_json is None:
            metadata_json = "{}"
        
        # Convert to python dictionary so we can actually interact with it!
        metadata_dict = fast_json_to_dict(metadata_json)
        
        return metadata_dict
    
    # .................................................................................................................
    
    def load_metadata_by_time_range(self, start_time, end_time):
        
        ''' Acts as a generator! '''
        
        # First get all station times for the given time range
        station_ems_list = self.get_all_station_start_times_by_time_range(start_time, end_time)
        
        # Return all station metadata, using a generator
        for each_ems in station_ems_list:
            yield self.load_metadata_by_ems(each_ems)
        
        return
    
    # .................................................................................................................
    # .................................................................................................................
    

# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////


class Rule_DB(File_DB):
    
    # .................................................................................................................
    
    def __init__(self, location_select_folder_path, camera_select, rule_name,
                 db_path = ":memory:", check_same_thread = True, debug_connect = False):
        
        # Store rule name
        self._rule_name = rule_name
        
        # Build key info
        primary_key = "full_id"
        required_keys_set = {"rule_type", "rule_results_dict", "rule_results_list"}
        
        # Inherit from parent
        super().__init__(location_select_folder_path, camera_select, primary_key, required_keys_set,
                         db_path, check_same_thread, debug_connect)
        
        # Override the built-in table name to account for separate rules
        self._table_name = "[{}-{}-{}]".format(self.camera_select, rule_name, self._class_name)
    
    # .................................................................................................................
    
    def save_entry(self, rule_name, rule_type, object_full_id, new_rule_results_dict, new_rule_results_list):
        
        # Save a file to represent the rule evalation data
        save_rule_report_data(self.location_select_folder_path, self.camera_select,
                              rule_name, rule_type, object_full_id, new_rule_results_dict, new_rule_results_list)
    
    # .................................................................................................................
    
    def load_rule_data(self, rule_name, object_id):
        
        # Build selection commands
        table_name = self._table_name(rule_name)
        select_cmd = """SELECT * FROM {} WHERE full_id = {}""".format(table_name, object_id)
        
        # Get data from database!
        rule_data = self._fetchone_item(select_cmd, return_if_missing = None)
        if rule_data is None:
            rule_data = []
        
        # Unbundle for clarity
        try:
            _, rule_type, num_violations, rule_results_dict_json, rule_results_list_json = rule_data[0]
            
        except IndexError:
            # If we don't find the object/entry, return a default entry
            new_rule_dict = new_rule_report_entry(object_id, "missing", {}, [])
            rule_type = new_rule_dict["rule_type"]
            num_violations = new_rule_dict["num_violations"]
            rule_results_dict = new_rule_dict["rule_results_dict"]
            rule_results_list = new_rule_dict["rule_results_list"]
            
            # Convert to valid json data to mimic 'normal' database return
            rule_results_dict_json = fast_dict_to_json(rule_results_dict)
            rule_results_list_json = fast_dict_to_json(rule_results_list)
        
        # Convert json entries back to python data type for convenience
        rule_results_dict = fast_json_to_dict(rule_results_dict_json)
        rule_results_list = fast_json_to_dict(rule_results_list_json)
        
        return rule_type, num_violations, rule_results_dict, rule_results_list
    
    # .................................................................................................................
    
    def _get_existing_rule_report_names(self, location_select_folder_path, camera_select):
        
        # Check reporting folder for rule results
        rule_report_folder_path = build_rule_adb_metadata_report_path(location_select_folder_path, camera_select)
        
        # Get all reporting folders
        rule_report_folders_list = get_folder_list(rule_report_folder_path,
                                                   show_hidden_folders = False,
                                                   create_missing_folder = False,
                                                   return_full_path = False,
                                                   sort_list = False)
        
        # Build a set containing all rule names (based on folder names)
        rule_name_set = set(rule_report_folders_list)
        
        return rule_name_set
    
    # .................................................................................................................
    # .................................................................................................................


# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////


# ---------------------------------------------------------------------------------------------------------------------
#%% Shared functions

# .....................................................................................................................

def fetchall_to_1d_list(fetchall_result, return_index = 0, sort_results = True):
    
    ''' Helper function which flattens a list of tuples, which may be returned from sqlite fetchall commands '''
    
    if fetchall_result is None:
        return []
    
    if not fetchall_result:
        return []
    
    try:
        if sort_results:
            return sorted([each_entry[return_index] for each_entry in fetchall_result])
        else:
            return [each_entry[return_index] for each_entry in fetchall_result]
    except IndexError:
        return []

# .....................................................................................................................

def post_from_folder_path(folder_path, database):
    
    # Start timing
    t_start = perf_counter()
    
    # Loop over every file path in the given folder and send the data to the database
    metdata_path_list = get_file_list(folder_path, return_full_path = True, sort_list = True)
    for each_file_path in metdata_path_list:
        metadata_dict = load_metadata(each_file_path)
        database.add_entry(metadata_dict)
    
    # End timing
    t_end = perf_counter()
    time_taken_sec = (t_end - t_start)
    
    return time_taken_sec

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Posting functions

# .....................................................................................................................

def post_camera_info_report_metadata(location_select_folder_path, camera_select, database):
    
    # Build pathing to camera info report data
    camera_info_metadata_folder_path = build_camera_info_metadata_report_path(location_select_folder_path,
                                                                              camera_select)
    
    time_taken_sec = post_from_folder_path(camera_info_metadata_folder_path, database)
    
    return time_taken_sec

# .....................................................................................................................

def post_config_info_report_metadata(location_select_folder_path, camera_select, database):
    
    # Build pathing to configuration info report data
    config_info_metadata_folder_path = build_config_info_metadata_report_path(location_select_folder_path,
                                                                              camera_select)
    
    time_taken_sec = post_from_folder_path(config_info_metadata_folder_path, database)
    
    return time_taken_sec

# .....................................................................................................................

def post_snapshot_report_metadata(location_select_folder_path, camera_select, database):
    
    # Build pathing to snapshot report data
    snapshot_metadata_folder_path = build_snapshot_metadata_report_path(location_select_folder_path,
                                                                        camera_select)
    
    time_taken_sec = post_from_folder_path(snapshot_metadata_folder_path, database)
    
    return time_taken_sec
    
# .....................................................................................................................

def post_object_report_metadata(location_select_folder_path, camera_select, database):
    
    # Build pathing to object report data
    object_metadata_folder_path = build_object_metadata_report_path(location_select_folder_path,
                                                                    camera_select)
    
    time_taken_sec = post_from_folder_path(object_metadata_folder_path, database)
    
    return time_taken_sec

# .....................................................................................................................

def post_stations_report_data(location_select_folder_path, camera_select, database):
    
    # Build pathing to stations report data
    stations_metadata_folder_path = build_station_metadata_report_path(location_select_folder_path,
                                                                       camera_select)
    
    time_taken_sec = post_from_folder_path(stations_metadata_folder_path, database)
    
    return time_taken_sec

# .....................................................................................................................

def post_classifier_report_data(location_select_folder_path, camera_select, database):
    
    # Build pathing to object classification report data
    classifier_adb_metadata_folder_path = build_classifier_adb_metadata_report_path(location_select_folder_path,
                                                                                    camera_select)
    
    time_taken_sec = post_from_folder_path(classifier_adb_metadata_folder_path, database)
    
    return time_taken_sec


# .....................................................................................................................

def post_summary_report_data(location_select_folder_path, camera_select, database):
    
    # Build pathing to object summary report data
    summary_adb_metadata_folder_path = build_summary_adb_metadata_report_path(location_select_folder_path,
                                                                              camera_select)
    
    time_taken_sec = post_from_folder_path(summary_adb_metadata_folder_path, database)
    
    return time_taken_sec

# .....................................................................................................................

def post_rule_report_data(location_select_folder_path, camera_select, rule_name, database):
    
    # Build pathing to rule report data
    rule_adb_metadata_folder_path = build_rule_adb_metadata_report_path(location_select_folder_path,
                                                                        camera_select,
                                                                        rule_name)
    
    time_taken_sec = post_from_folder_path(rule_adb_metadata_folder_path, database)
    
    return time_taken_sec

# .....................................................................................................................

def post_rule_info_report_metadata(location_select_folder_path, camera_select, database):
    
    # Build pathing to object report data
    rule_info_metadata_folder_path = build_rule_adb_info_report_path(location_select_folder_path,
                                                                     camera_select)
    
    time_taken_sec = post_from_folder_path(rule_info_metadata_folder_path, database)
    
    return time_taken_sec

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Launch functions

# .....................................................................................................................

def _print_launch(launch_name):
    print("  --> {}".format(launch_name).ljust(24), end = "")

# .....................................................................................................................

def _print_done(time_taken_sec):
    print("... Done! ({:.0f} ms)".format(1000 * time_taken_sec))

# .....................................................................................................................

def _print_missing(error_message):
    print("... Missing! {}".format(error_message))

# .....................................................................................................................

def launch_dbs(location_select_folder_path, camera_select, *dbs_to_launch,
               check_same_thread = True, debug_connect = False, db_path = ":memory:"):
    
    # Specify all the different launch settings for each database type
    launch_lut = {"camera_info": {"print_name": "Camera info",
                                  "class_to_init": Camera_Info_DB,
                                  "post_function": post_camera_info_report_metadata},
                  "config_info": {"print_name": "Config info",
                                  "class_to_init": Config_Info_DB,
                                  "post_function": post_config_info_report_metadata},
                  "snapshots": {"print_name": "Snapshots",
                                "class_to_init": Snap_DB,
                                "post_function": post_snapshot_report_metadata},
                  "objects": {"print_name": "Objects",
                              "class_to_init": Object_DB,
                              "post_function": post_object_report_metadata},
                  "classifications": {"print_name": "Classifications",
                                      "class_to_init": Classification_DB,
                                      "post_function": post_classifier_report_data},
                  "summary": {"print_name": "Summary",
                              "class_to_init": Summary_DB,
                              "post_function": post_summary_report_data},
                  "stations": {"print_name": "Stations",
                               "class_to_init": Stations_DB,
                               "post_function": post_stations_report_data}}
    
    # Bundle args for clarity
    init_args = {"location_select_folder_path": location_select_folder_path,
                 "camera_select": camera_select,
                 "check_same_thread": check_same_thread,
                 "debug_connect": debug_connect,
                 "db_path": db_path}
    
    # Some feedback
    print("", "Launching FILE DB for {}".format(camera_select), sep = "\n")
    
    # Load all of the target dbs
    loaded_dbs_list = []
    for each_db_name in dbs_to_launch:
        
        # Convert each name to lowercase + remove spaces to ensure consistency
        safe_db_name = each_db_name.lower().replace(" ", "_")
        if safe_db_name not in launch_lut.keys():
            valid_db_names_list = list(launch_lut.keyss())
            err_msg_list = ["Can't load db: {}".format(each_db_name),
                            "Name not recognized! Should be one of:",
                            "{}".format(*valid_db_names_list)]
            err_msg_str = "\n".join(err_msg_list)
            raise NameError(err_msg_str)
        
        # Load the target db and store them for output
        launch_args_dict = launch_lut[safe_db_name]
        load_db = launch_one_db(**init_args, **launch_args_dict)
        loaded_dbs_list.append(load_db)
    
    return loaded_dbs_list

# .....................................................................................................................

def launch_one_db(location_select_folder_path, camera_select, check_same_thread, debug_connect, db_path,
                  print_name, class_to_init, post_function):
    
    # Bundle init args as a dictionary to make it easier to setup each class
    init_args_dict = {"location_select_folder_path": location_select_folder_path,
                      "camera_select": camera_select,
                      "check_same_thread": check_same_thread,
                      "debug_connect": debug_connect,
                      "db_path": db_path}
    
    # Print some feedback about launching the target db + the time taken for reference
    _print_launch(print_name)
    loaded_db = class_to_init(**init_args_dict)
    load_time_sec = post_function(location_select_folder_path, camera_select, loaded_db)
    _print_done(load_time_sec)
    
    return loaded_db

# .....................................................................................................................

def launch_rule_dbs(location_select_folder_path, camera_select,
                    check_same_thread = True):
    
    # Initialize outputs
    rinfo_db = None
    rule_dbs_dict = {}
    
    # Bundle args for clarity
    selection_args = (location_select_folder_path, camera_select)
    check_thread_arg = {"check_same_thread": check_same_thread}
    
    # Some feedback
    print("", "Launching RULE DBs for {}".format(camera_select), sep = "\n")
    
    # Always launch rule info db
    _print_launch("Rule info")
    rinfo_db = Rule_Info_DB(*selection_args, **check_thread_arg)
    rule_info_time = post_rule_info_report_metadata(*selection_args, rinfo_db)
    _print_done(rule_info_time)
    
    # Load all of the rules
    rule_names_list = rinfo_db.get_all_rule_names()
    for each_rule_name in rule_names_list:
        _print_launch(each_rule_name)
        rule_select_args = (*selection_args, each_rule_name)
        rule_db = Rule_DB(*rule_select_args, **check_thread_arg)
        rule_time = post_rule_report_data(*rule_select_args, rule_db)
        _print_done(rule_time)
        
        # Store all rules in a dictionary
        rule_dbs_dict[each_rule_name] = rule_db
    
    return rinfo_db, rule_dbs_dict

# .....................................................................................................................

def close_dbs_if_missing_data(*database_refs,
                              error_message_if_missing = "Missing data in database"):
    
    ''' 
    Helper function which closes all provided databases if any are missing data
    
    Inputs: 
        *database_refs: (one or many fileDB objects).
    
        error_message_if_missing: (String or None). If a string is provided and there is no data 
                                  in one or more of the database_refs, a 'RunTimeError' will be
                                  raised with the given error message.
                                  If this input is set to None (or an empty string), no error will be raised
                                      
    Outputs:
        missing_data (boolean)                                        
    '''
    
    # Check if any of the databases are missing data
    try:
        dbs_no_data = [each_db.no_data() for each_db in database_refs]
    except AttributeError:
        err_msg_list = ["Error checking missing data in dbs!",
                        "Likely forgot to pass 'error_message_if_missing' as a keyword argument"]
        raise TypeError("\n".join(err_msg_list))
    
    # Close all databases if any are missing data
    missing_data = any(dbs_no_data)
    if missing_data:
        
        # Shutdown all the dbs safely
        for each_db_ref in database_refs:
            each_db_ref.close()
            
        # Raise an error to stop execution when missing data, if needed
        if error_message_if_missing:
            raise RuntimeError(error_message_if_missing)
            
    return missing_data

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Demo

if __name__ == "__main__":
    pass


# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap


