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
import cv2
import numpy as np

from time import perf_counter

from local.lib.common.timekeeper_utils import time_to_epoch_ms, parse_isoformat_string

from local.lib.file_access_utils.reporting import build_camera_info_metadata_report_path
from local.lib.file_access_utils.reporting import build_snapshot_image_report_path
from local.lib.file_access_utils.reporting import build_snapshot_metadata_report_path
from local.lib.file_access_utils.reporting import build_object_metadata_report_path

from local.lib.file_access_utils.classifier import load_reserved_labels_lut, load_topclass_labels_lut
from local.lib.file_access_utils.classifier import reserved_notrain_label
from local.lib.file_access_utils.classifier import new_classifier_report_entry
from local.lib.file_access_utils.classifier import build_classifier_adb_metadata_report_path

from local.lib.file_access_utils.summary import save_summary_report_data, build_summary_adb_metadata_report_path

from local.lib.file_access_utils.rules import save_rule_report_data
from local.lib.file_access_utils.rules import build_rule_adb_metadata_report_path
from local.lib.file_access_utils.rules import build_rule_adb_info_report_path
from local.lib.file_access_utils.rules import new_rule_report_entry

from local.lib.file_access_utils.read_write import load_jgz, fast_dict_to_json, fast_json_to_dict

from local.eolib.utils.files import get_file_list, get_folder_list
from local.eolib.utils.quitters import ide_quit

# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes

class File_DB:
    
    # .................................................................................................................
    
    def __init__(self, cameras_folder_path, camera_select, user_select,
                 db_path = ":memory:", check_same_thread = True, debug_connect = False):
        
        # Store camera/user selections
        self.cameras_folder_path = cameras_folder_path
        self.camera_select = camera_select
        self.user_select = user_select
        
        # Allocate storage for db info
        self.db_path = db_path
        self.connection = None
        
        # Start up the database!
        self.connection = self.connect(check_same_thread, debug_connect)
        self._initialize_tables()
    
    # .................................................................................................................
    
    def __repr__(self):
        
        table_names_list = self._list_table_names()
        num_tables = len(table_names_list)
        
        repr_strs = ["{} ({} tables)".format(self._class_name, num_tables)]
        for each_table_name in table_names_list:
            repr_strs += ["  {}".format(each_table_name)]
        
        return "\n".join(repr_strs)
    
    # .................................................................................................................
    
    @property
    def _class_name(self):
        return self.__class__.__name__
        
    # .................................................................................................................
    
    def _cursor(self):
        return self.connection.cursor()
    
    # .................................................................................................................
    
    def _list_table_names(self):
        
        cursor = self._cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        table_name_list = cursor.fetchall()
        
        return fetchall_to_1d_list(table_name_list)
    
    # .................................................................................................................
    
    def _list_table_columns(self, table_name):
        
        cursor = self._cursor()
        cursor.execute("PRAGMA TABLE_INFO({})".format(table_name))
        column_info_list = cursor.fetchall()
        
        column_names = fetchall_to_1d_list(column_info_list, 1)
        
        return column_names
    
    # .................................................................................................................
    
    def _table_name(self):
        
        raise NotImplementedError("Need to specify a table name! ({})".format(self._class_name))
        
        return "[no_name]"
    
    # .................................................................................................................
        
    def _initialize_tables(self):
        
        raise NotImplementedError("Need to initial table(s)! ({})".format(self._class_name))
        
        return None
    
    # .................................................................................................................
    
    def add_entry(self, *args, **kwargs):
        
        raise NotImplementedError("Add entry function not implemented! ({})".format(self._class_name))
        
        return None

    # .................................................................................................................
    
    def head(self, target_table_name = None, number_to_return = 5):
        
        ''' Function used to inspect the top few elements of the database '''
        
        # Get table name in more convenient format
        table_name = self._table_name() if (target_table_name is None) else self._table_name(target_table_name)
        
        # Add bounding brackets to table name, if needed
        missing_prefix_bracket = (table_name[0] != "[")
        missing_suffix_bracket = (table_name[-1] != "]")
        table_name = "{}{}{}".format("[" if missing_prefix_bracket else "", 
                                     table_name, 
                                     "]" if missing_suffix_bracket else "")
        
        # Build database commands
        get_column_names_cmd = "PRAGMA TABLE_INFO({})".format(table_name)
        get_top_entries_cmd = "SELECT * FROM {} LIMIT {}".format(table_name, number_to_return)
        
        cursor = self._cursor()
        
        # Get column info
        cursor.execute(get_column_names_cmd)
        column_info_list = cursor.fetchall()
        
        # Get top few rows of data
        cursor.execute(get_top_entries_cmd)
        top_entries = cursor.fetchall()
        
        # Print column names followed by example entries
        column_names = fetchall_to_1d_list(column_info_list, 1)
        print("", table_name, "COLUMNS: {}".format(", ".join(column_names)), "", *top_entries, sep = "\n")
        
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
    
    def no_data(self):
        
        ''' Helper function which returns true if there is no data in the database '''
        
        # Build command to find at least one data entry
        select_cmd = """
                     SELECT *
                     FROM {}
                     LIMIT 1
                     """.format(self._table_name())
                     
        # Get data from database!
        cursor = self._cursor()
    
        # Get object ids in time range
        cursor.execute(select_cmd)
        single_data_entry = cursor.fetchone()
        
        # If no data came back, we've got no data!
        if single_data_entry is None:
            return True
    
        return False
    
    # .................................................................................................................
    
    def close(self):
        
        if self.connection is not None:
            self.connection.close()
        
        return
    
    # .................................................................................................................
    
    def add_entry_dict(self, metadata_dict):
        
        self._table_name = ""
        self._required_keys_set = {"_id"}
        self._primary_key = "full_id"
        
        # Build ordered list of keys to insert
        insert_keys_list = sorted(list(metadata_dict.keys()))
        
        # Build list of values to insert for each key, with typecasting for dictionaries
        insert_values_list = []
        for each_key in insert_keys_list:            
            value_to_insert = metadata_dict[each_key]
            if type(value_to_insert) is dict:
                value_to_insert = fast_dict_to_json(value_to_insert)
            insert_values_list.append(value_to_insert)
        
        # Insert the data into the table
        table_name = self._get_table_name(insert_keys_list, insert_values_list)
        self._insert_into_table(table_name, insert_keys_list, insert_values_list)
    
    # .................................................................................................................
    
    def _get_table_name(self, insert_keys_list, insert_values_list):
        
        # Create the first table, if needed. Assumes all data will have the same formatting!
        if not self._table_created:
            self._create_initial_table()
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
        create_table_cmd = "CREATE TABLE {}({})".format(self._table_name, table_columns_str_list)
        self._cursor().execute(create_table_cmd)
        self.connection.commit()
        
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
            raise AttributeError("Missing primary key ({}) for table: {}".format(self._primary_key, table_name))
        if not has_required_keys:
            req_keys_str = ", ".join(self._required_keys_set)
            raise AttributeError("Missing required keys ({}) for table: {}".format(req_keys_str, table_name))
        
        return
    
    # .................................................................................................................
    
    def _insert_into_table(self, table_name, insert_keys_list, insert_values_list):
        
        # Build insert command
        insert_qs_list = "?" * len(insert_keys_list)
        insert_keys_str = ", ".join(insert_keys_list)
        insert_qs_str = ",".join(insert_qs_list)
        insert_cmd = "INSERT INTO {}({}) VALUES({})".format(table_name, insert_keys_str, insert_qs_str)
        
        # Update the database!
        cursor = self._cursor()
        cursor.execute(insert_cmd, insert_values_list)
        self.connection.commit()
    
    # .................................................................................................................
    
    @staticmethod
    def _get_table_data_type(python_data_type):
        
        # Create a lookup table for convenience
        table_data_type_lut = {str: "TEXT",
                               int: "INTEGER",
                               float: "REAL"}
        
        return table_data_type_lut[python_data_type]
    
    # .................................................................................................................
    # .................................................................................................................


# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////


class Camera_Info_DB(File_DB):
    
    # .................................................................................................................
    
    def __init__(self, cameras_folder_path, camera_select, user_select,
                 db_path = ":memory:", check_same_thread = True):
        
        # Inherit from parent
        super().__init__(cameras_folder_path, camera_select, user_select, db_path, check_same_thread)
    
    # .................................................................................................................
    
    def _table_name(self):
        return "[{}-camerainfo]".format(self.camera_select)
    
    # .................................................................................................................
        
    def _initialize_tables(self):
        
        cursor = self._cursor()
        
        # Define table columns
        objs_columns = ["mongo_id INTEGER", 
                        "ip_address TEXT",
                        "time_zone TEXT",
                        "start_datetime_isoformat TEXT",
                        "start_epoch_ms INTEGER PRIMARY KEY",
                        "video_select TEXT",
                        "video_fps REAL",
                        "video_width INTEGER",
                        "video_height INTEGER",
                        "snapshot_width INTEGER",
                        "snapshot_height INTEGER"]
        objs_column_str = ", ".join(objs_columns)
        
        # Initialize the table 
        obj_table_name = self._table_name()
        objs_cursor_cmd = "CREATE TABLE {}({})".format(obj_table_name, objs_column_str)
        cursor.execute(objs_cursor_cmd)
            
        self.connection.commit()
    
    # .................................................................................................................
    
    def add_entry(self, mongo_id, ip_address, time_zone, start_datetime_isoformat, start_epoch_ms,
                  video_select, video_fps, video_width, video_height,
                  snapshot_width, snapshot_height):
        
        # Bundle data in the correct order for database entry
        new_entry_var_list = ["mongo_id", "ip_address", "time_zone", "start_datetime_isoformat", "start_epoch_ms",
                              "video_select", "video_fps", "video_width", "video_height",
                              "snapshot_width", "snapshot_height"]
        new_entry_value_list = [mongo_id, ip_address, time_zone, start_datetime_isoformat, start_epoch_ms,
                                video_select, video_fps, video_width, video_height,
                                snapshot_width, snapshot_height]
        new_entry_q_list = ["?"] * len(new_entry_var_list)
        
        # Build insert command
        insert_table = self._table_name()
        insert_vars = ", ".join(new_entry_var_list)
        insert_qs = ",".join(new_entry_q_list)
        insert_cmd = "INSERT INTO {}({}) VALUES({})".format(insert_table, insert_vars, insert_qs)
        
        # Update the database!
        cursor = self._cursor()
        cursor.execute(insert_cmd, new_entry_value_list)
        self.connection.commit()
    
    # .................................................................................................................
    
    def get_camera_info(self):
        
        # Build string to get all camera info
        select_cmd = "SELECT * FROM {}".format(self._table_name())
        
        # Get data from database!
        cursor = self._cursor()
        cursor.execute(select_cmd)
        camera_info = cursor.fetchall()
        
        # Make up fake camera info if nothing is returned, to avoid crippling errors
        if camera_info is None:
            camera_info = [None] * 11
        
        # Break apart return value for clarity
        mongo_id, ip_address, time_zone, start_datetime_isoformat, start_epoch_ms, \
        video_select, video_fps, video_width, video_height, snapshot_width, snapshot_height = camera_info[-1]
        
        return mongo_id, ip_address, time_zone, start_datetime_isoformat, start_epoch_ms, \
               video_select, video_fps, video_width, video_height, snapshot_width, snapshot_height
    
    # .................................................................................................................
    
    def get_video_frame_wh(self):
        
        # Build selection commands
        select_cmd = "SELECT video_width, video_height FROM {} LIMIT 1".format(self._table_name())
        
        # Get data from database!
        cursor = self._cursor()
        
        # Get video sizing
        cursor.execute(select_cmd)
        video_wh = cursor.fetchall()[0]
        
        return video_wh
    
    # .................................................................................................................
    
    def get_snap_frame_wh(self):
        
        # Build selection commands
        select_cmd = "SELECT snapshot_width, snapshot_height FROM {} LIMIT 1".format(self._table_name())
        
        # Get data from database!
        cursor = self._cursor()
        
        # Get snapshot sizing
        cursor.execute(select_cmd)
        snap_wh = cursor.fetchall()[0]
        
        return snap_wh
    
    # .................................................................................................................
    # .................................................................................................................


# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////


class Rule_Info_DB(File_DB):
    
    # .................................................................................................................
    
    def __init__(self, cameras_folder_path, camera_select, user_select,
                 db_path = ":memory:", check_same_thread = True):
        
        # Inherit from parent
        super().__init__(cameras_folder_path, camera_select, user_select, db_path, check_same_thread)
    
    # .................................................................................................................
    
    def _table_name(self):
        return "[{}-ruleinfo]".format(self.camera_select)
    
    # .................................................................................................................
        
    def _initialize_tables(self):
        
        cursor = self._cursor()
        
        # Define table columns
        ruleinfo_columns = ["rule_name TEXT PRIMARY KEY",
                            "rule_type TEXT",
                            "configuration_json TEXT"]
        ruleinfo_column_str = ", ".join(ruleinfo_columns)
        
        # Initialize the table 
        ruleinfo_table_name = self._table_name()
        ruleinfo_cursor_cmd = "CREATE TABLE {}({})".format(ruleinfo_table_name, ruleinfo_column_str)
        cursor.execute(ruleinfo_cursor_cmd)
            
        self.connection.commit()
    
    # .................................................................................................................
    
    def add_entry(self, rule_name, rule_type, configuration_json):
        
        # Bundle data in the correct order for database entry
        new_entry_var_list = ["rule_name", "rule_type", "configuration_json"]
        new_entry_value_list = [rule_name, rule_type, configuration_json]
        new_entry_q_list = ["?"] * len(new_entry_var_list)
        
        # Build insert command
        insert_table = self._table_name()
        insert_vars = ", ".join(new_entry_var_list)
        insert_qs = ",".join(new_entry_q_list)
        insert_cmd = "INSERT INTO {}({}) VALUES({})".format(insert_table, insert_vars, insert_qs)
        
        # Update the database!
        cursor = self._cursor()
        cursor.execute(insert_cmd, new_entry_value_list)
        self.connection.commit()
    
    # .................................................................................................................
    
    def get_rule_info(self):
        
        # Build string to get all rule info
        select_cmd = "SELECT * FROM {}".format(self._table_name())
        
        # Get data from database!
        cursor = self._cursor()
        cursor.execute(select_cmd)
        rule_info_list = cursor.fetchall()
        
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
    
    def __init__(self, cameras_folder_path, camera_select, user_select,
                 db_path = ":memory:", check_same_thread = True):
        
        # Inherit from parent
        super().__init__(cameras_folder_path, camera_select, user_select, db_path, check_same_thread)
        
    # .................................................................................................................
    # .................................................................................................................


# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////


class Snap_DB(File_DB):
    
    # .................................................................................................................
    
    def __init__(self, cameras_folder_path, camera_select, user_select,
                 db_path = ":memory:",
                 check_same_thread = True):
        
        # Inherit from parent
        super().__init__(cameras_folder_path, camera_select, user_select, db_path, check_same_thread)
        
        # Set up pathing to load image data
        self.snap_images_folder_path = build_snapshot_image_report_path(cameras_folder_path, 
                                                                        camera_select, 
                                                                        user_select)
            
        # Check that the snapshot path is valid before continuing
        snapshot_image_folder_exists = os.path.exists(self.snap_images_folder_path)
        if not snapshot_image_folder_exists:
            raise FileNotFoundError("Couldn't find snapshot image folder:\n{}".format(self.snap_images_folder_path))
        
    # .................................................................................................................
    
    def _table_name(self, table_select = None):        
        return "[{}-snapshots]".format(self.camera_select)
    
    # .................................................................................................................
        
    def _initialize_tables(self):
        
        cursor = self._cursor()
        
        # Initialize table for snapshot metadata
        snaps_columns = ["mongo_id INTEGER",
                         "frame_index INTEGER",
                         "datetime_isoformat TEXT",
                         "epoch_ms INTEGER PRIMARY KEY"]
        snaps_column_str = ", ".join(snaps_columns)
        snaps_cursor_cmd = "CREATE TABLE {}({})".format(self._table_name(), snaps_column_str)
        cursor.execute(snaps_cursor_cmd)
        
        self.connection.commit()
    
    # .................................................................................................................
    
    def add_entry(self, mongo_id, frame_index, datetime_isoformat, epoch_ms):
        
        # Bundle data in the correct order for database entry
        new_entry_var_list = ["mongo_id", "frame_index", "datetime_isoformat", "epoch_ms"]
        new_entry_value_list = [mongo_id, frame_index, datetime_isoformat,  epoch_ms]
        new_entry_q_list = ["?"] * len(new_entry_var_list)
        
        # Build insert command
        insert_table = self._table_name()
        insert_vars = ", ".join(new_entry_var_list)
        insert_qs = ",".join(new_entry_q_list)
        insert_cmd = "INSERT INTO {}({}) VALUES({})".format(insert_table, insert_vars, insert_qs)
        
        # Update the database!
        cursor = self._cursor()
        cursor.execute(insert_cmd, new_entry_value_list)
        self.connection.commit()
    
    # .................................................................................................................
    
    def get_total_snapshot_count(self):
        
        # Build string to total snapshot count
        select_cmd = "SELECT count(epoch_ms) FROM {}".format(self._table_name())
        
        # Get data from database!
        cursor = self._cursor()
        cursor.execute(select_cmd)
        snapshot_count = cursor.fetchone()
        
        return snapshot_count[0]
    
    # .................................................................................................................
    
    def get_bounding_epoch_ms(self):
        
        # Build string to get min/max datetimes from snapshots
        select_cmd = "SELECT min(epoch_ms), max(epoch_ms) FROM {}".format(self._table_name())
        
        # Get data from database!
        cursor = self._cursor()
        cursor.execute(select_cmd)
        min_epoch_ms, max_epoch_ms = cursor.fetchone()
        
        return min_epoch_ms, max_epoch_ms
    
    # .................................................................................................................
    
    def get_bounding_datetimes(self):
        
        # First get bounding epoch times of bounding snapshots
        min_epoch_ms, max_epoch_ms = self.get_bounding_epoch_ms()
        
        # Build string to get the corresponding datetime strings for the bounding epoch values
        select_min_cmd = "SELECT datetime_isoformat FROM {} WHERE epoch_ms = {}".format(self._table_name(),
                                                                                            min_epoch_ms)
        select_max_cmd = "SELECT datetime_isoformat FROM {} WHERE epoch_ms = {}".format(self._table_name(),
                                                                                            max_epoch_ms)
        
        # Get data from database!
        cursor = self._cursor()
        cursor.execute(select_min_cmd)
        min_dt_isoformat = cursor.fetchone()
        cursor.execute(select_max_cmd)
        max_dt_isoformat = cursor.fetchone()
        
        # Finally, convert datetime isoformat strings back to datetime objects
        min_dt_str = parse_isoformat_string(min_dt_isoformat[0])
        max_dt_str = parse_isoformat_string(max_dt_isoformat[0])
        
        return min_dt_str, max_dt_str
    
    # .................................................................................................................
    
    def get_all_snapshot_times_by_time_range(self, start_time, end_time):
        
        # Convert input times to epoch values
        start_epoch_ms = time_to_epoch_ms(start_time)
        end_epoch_ms = time_to_epoch_ms(end_time)
        
        # Build command string for getting all snapshot times between start/end
        select_cmd = "SELECT epoch_ms FROM {} WHERE epoch_ms BETWEEN {} and {}".format(self._table_name(), 
                                                                                       start_epoch_ms,
                                                                                       end_epoch_ms)
        
        # Get data from database!
        cursor = self._cursor()
        cursor.execute(select_cmd)
        all_snapshot_epoch_ms_times = cursor.fetchall()
        
        return fetchall_to_1d_list(all_snapshot_epoch_ms_times)
    
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
        target_epoch_ms = time_to_epoch_ms(target_time)
        
        # Build selection commands
        ceil_select_cmd = """
                          SELECT min(epoch_ms) 
                          FROM {} 
                          WHERE epoch_ms >= {} 
                          LIMIT 1
                          """.format(self._table_name(), target_epoch_ms)
                          
        floor_select_cmd = """
                           SELECT max(epoch_ms) 
                           FROM {} 
                           WHERE epoch_ms <= {} 
                           LIMIT 1
                           """.format(self._table_name(), target_epoch_ms)
        
        # Get data from database!
        cursor = self._cursor()
        
        # Get lower bound snapshot
        cursor.execute(floor_select_cmd)
        floor_snapshot_epoch_ms = cursor.fetchone()[0]
        no_floor = (floor_snapshot_epoch_ms is None)
        
        # Get upper bound snapshot
        cursor.execute(ceil_select_cmd)
        ceil_snapshot_epoch_ms = cursor.fetchone()[0]
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
        
        return floor_snapshot_epoch_ms, closest_snapshot_epoch_ms, ceil_snapshot_epoch_ms
    
    # .................................................................................................................
    
    def load_snapshot_metadata(self, target_epoch_ms):
        
        '''
        Function which returns snapshot metadata for a given epoch timing
        
        Inputs:
            target snapshot epoch_ms time (must be a valid time!)
        
        Outputs:
            metadata_dictionary
        '''
        
        # Build selection commands
        select_cmd = """
                     SELECT *
                     FROM {} 
                     WHERE epoch_ms = {}
                     """.format(self._table_name(), target_epoch_ms)
        
        # Get data from database!
        cursor = self._cursor()
        cursor.execute(select_cmd)
        target_snapshot_entry = cursor.fetchone()
        
        # Convert output into dictionary for easier use
        output_dict = {"mongo_id": target_snapshot_entry[0],
                       "frame_index": target_snapshot_entry[1],
                       "datetime_isoformat": target_snapshot_entry[2],
                       "epoch_ms": target_snapshot_entry[3]}
        
        return output_dict
    
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
        snap_md = self.load_snapshot_metadata(target_epoch_ms)
        snap_epoch_ms = snap_md["epoch_ms"]
        snap_frame_index = snap_md["frame_index"]
        
        # Build pathing to the corresponding image
        snap_image_name = "{}.jpg".format(snap_epoch_ms)
        snap_image_path = os.path.join(self.snap_images_folder_path, snap_image_name)
        
        # Crash if we can't find the image, since that shouldn't happen offline...
        image_not_found = (not os.path.exists(snap_image_path))
        if image_not_found:
            raise FileNotFoundError("Couldn't find snapshot image! ({})".format(snap_image_path))
        
        return cv2.imread(snap_image_path), snap_frame_index
    
    # .................................................................................................................
    # .................................................................................................................


# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////


class Object_DB(File_DB):
    
    # .................................................................................................................
    
    def __init__(self, cameras_folder_path, camera_select, user_select,
                 db_path = ":memory:", check_same_thread = True):
        
        # Inherit from parent
        super().__init__(cameras_folder_path, camera_select, user_select, db_path, check_same_thread)
    
    # .................................................................................................................
    
    def _table_name(self):
        return "[{}-objects]".format(self.camera_select)
    
    # .................................................................................................................
        
    def _initialize_tables(self):
        
        cursor = self._cursor()
        
        # Define table columns
        objs_columns = ["mongo_id INTEGER",
                        "full_id INTEGER PRIMARY KEY",
                        "nice_id INTEGER", 
                        "ancestor_id INTEGER", 
                        "descendant_id INTEGER",
                        "is_final INTEGER",
                        "first_epoch_ms INTEGER",
                        "final_epoch_ms INTEGER",
                        "lifetime_ms INTEGER", 
                        "start_frame_index INTEGER",
                        "end_frame_index INTEGER",
                        "num_samples INTEGER",
                        "bdb_classifier_json TEXT",
                        "adb_classifier_json TEXT",
                        "metadata_json TEXT"]
        objs_column_str = ", ".join(objs_columns)
        
        # Initialize the table 
        obj_table_name = self._table_name()
        objs_cursor_cmd = "CREATE TABLE {}({})".format(obj_table_name, objs_column_str)
        cursor.execute(objs_cursor_cmd)
        
        self.connection.commit()
        
    # .................................................................................................................
    
    def add_entry(self, mongo_id, full_id, nice_id, ancestor_id, descendant_id, is_final,
                  first_epoch_ms, final_epoch_ms, lifetime_ms,
                  start_frame_index, end_frame_index, num_samples,
                  bdb_classifier_json, adb_classifier_json,
                  metadata_json):
        
        # Bundle data in the correct order for database entry
        new_entry_var_list = ["mongo_id", "full_id", "nice_id", "ancestor_id", "descendant_id", "is_final",
                              "first_epoch_ms", "final_epoch_ms", "lifetime_ms",
                              "start_frame_index", "end_frame_index", "num_samples", 
                              "bdb_classifier_json", "adb_classifier_json",
                              "metadata_json"]
        new_entry_value_list = [mongo_id, full_id, nice_id, ancestor_id, descendant_id, is_final,
                                first_epoch_ms, final_epoch_ms, lifetime_ms,
                                start_frame_index, end_frame_index, num_samples,
                                bdb_classifier_json, adb_classifier_json,
                                metadata_json]
        new_entry_q_list = ["?"] * len(new_entry_var_list)
        
        # Build insert command
        insert_table = self._table_name()
        insert_vars = ", ".join(new_entry_var_list)
        insert_qs = ",".join(new_entry_q_list)
        insert_cmd = "INSERT INTO {}({}) VALUES({})".format(insert_table, insert_vars, insert_qs)
        
        # Update the database!
        cursor = self._cursor()
        cursor.execute(insert_cmd, new_entry_value_list)
        self.connection.commit()
    
    # .................................................................................................................
    
    def get_total_object_count(self):
        
        # Build string to get total object count
        select_cmd = "SELECT count(full_id) FROM {}".format(self._table_name())
        
        # Get data from database!
        cursor = self._cursor()
        cursor.execute(select_cmd)
        total_object_count = cursor.fetchone()
        
        return total_object_count[0]
    
    # .................................................................................................................
    
    def get_object_ids_by_time_range(self, start_time, end_time):
        
        # Convert time values into epoch_ms values for searching
        start_epoch_ms = time_to_epoch_ms(start_time)
        end_epoch_ms = time_to_epoch_ms(end_time)
        
        # Build selection commands
        table_name = self._table_name()        
        select_cmd = """
                     SELECT full_id
                     FROM {}
                     WHERE 
                     final_epoch_ms >= {} 
                     AND 
                     first_epoch_ms <= {}
                     """.format(table_name, start_epoch_ms, end_epoch_ms)
                     
        # Get data from database!
        cursor = self._cursor()
        
        # Get object ids in time range
        cursor.execute(select_cmd)
        object_ids_fetch = cursor.fetchall()
        
        # Convert the list to 1D (get rid of tuple entries per row)
        object_id_list = fetchall_to_1d_list(object_ids_fetch)
                     
        return object_id_list
    
    # .................................................................................................................
    
    def get_ids_at_target_time(self, target_time):
        
        # Convert time value into epoch_ms value to search database
        target_epoch_ms = time_to_epoch_ms(target_time)
        
        # Build selection commands
        table_name = self._table_name()
        select_cmd = """
                     SELECT full_id
                     FROM {}
                     WHERE {} 
                     BETWEEN 
                     first_epoch_ms AND final_epoch_ms
                     """.format(table_name, target_epoch_ms)
                     
        # Get data from database!
        cursor = self._cursor()
        
        # Get object ids in time range
        cursor.execute(select_cmd)
        object_ids_fetch = cursor.fetchall()
        
        # Convert the list to 1D (get rid of tuple entries per row)
        object_id_list = fetchall_to_1d_list(object_ids_fetch)
        
        return object_id_list
    
    # .................................................................................................................
    
    def load_metadata_by_id(self, object_id):
        
        # Build selection commands
        table_name = self._table_name()
        select_cmd = """
                     SELECT metadata_json
                     FROM {} 
                     WHERE full_id = {}
                     """.format(table_name, object_id)
        
        # Get data from database!
        cursor = self._cursor()
        cursor.execute(select_cmd)
        metadata_json = cursor.fetchone()[0]
        
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
    
    def __init__(self, cameras_folder_path, camera_select, user_select,
                 db_path = ":memory:", check_same_thread = True):
        
        # Load classification labels & colors
        self.reserved_labels_lut = load_reserved_labels_lut(cameras_folder_path, camera_select)
        self.topclass_labels_lut = load_topclass_labels_lut(cameras_folder_path, camera_select)
        self.all_label_colors_lut = {**self.reserved_labels_lut, **self.topclass_labels_lut}
        
        # Load reference to special label that is meant as a training directive only
        self.no_train_label, _ = reserved_notrain_label()
        
        # Get pathing to 'local' classification results
        self.local_classification_folder = build_classifier_adb_metadata_report_path(cameras_folder_path,
                                                                                     camera_select,
                                                                                     user_select)
        
        # Inherit from parent
        super().__init__(cameras_folder_path, camera_select, user_select, db_path, check_same_thread)
    
    # .................................................................................................................
    
    def _table_name(self):
        return "[{}-classification]".format(self.camera_select)
    
    # .................................................................................................................
        
    def _initialize_tables(self):
        
        cursor = self._cursor()
        
        # Define object classification table columns
        objs_columns = ["full_id INTEGER PRIMARY KEY",
                        "topclass_label TEXT",
                        "subclass_label TEXT",
                        "topclass_dict TEXT",
                        "subclass_dict TEXT",
                        "attributes_dict TEXT"]
        objs_column_str = ", ".join(objs_columns)
        
        # Initialize a table for object classifications
        table_name = self._table_name()
        objs_cursor_cmd = "CREATE TABLE {}({})".format(table_name, objs_column_str)
        cursor.execute(objs_cursor_cmd)
            
        self.connection.commit()
    
    # .................................................................................................................
    
    def add_entry(self, full_id, topclass_label, subclass_label, topclass_dict, subclass_dict, attributes_dict):
        
        # Bundle data in the correct order for database entry
        new_entry_var_list = ["full_id", "topclass_label", "subclass_label", 
                              "topclass_dict", "subclass_dict", "attributes_dict"]
        new_entry_value_list = [full_id, topclass_label, subclass_label, topclass_dict, subclass_dict, attributes_dict]
        new_entry_q_list = ["?"] * len(new_entry_var_list)
        
        # Build insert command
        insert_table = self._table_name()
        insert_vars = ", ".join(new_entry_var_list)
        insert_qs = ",".join(new_entry_q_list)
        insert_cmd = "INSERT INTO {}({}) VALUES({})".format(insert_table, insert_vars, insert_qs)
        
        # Update the database!
        cursor = self._cursor()
        cursor.execute(insert_cmd, new_entry_value_list)
        self.connection.commit()
    
    # .................................................................................................................
    
    def get_label_color(self, classification_label):
        
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
        table_name = self._table_name()
        select_cmd = """SELECT full_id FROM {}""".format(table_name)
        
        # Get data from database!
        cursor = self._cursor()
        cursor.execute(select_cmd)
        object_id_list = cursor.fetchall()
        
        return fetchall_to_1d_list(object_id_list)
    
    # .................................................................................................................
    
    def load_classification_data(self, object_id):
        
        # Build selection commands
        table_name = self._table_name()
        select_cmd = """SELECT * FROM {} WHERE full_id = {}""".format(table_name, object_id)
        
        # Get data from database!
        cursor = self._cursor()
        cursor.execute(select_cmd)
        object_classification_data = cursor.fetchall()
        
        # Unbundle for clarity
        try:
            class_data = object_classification_data[0]
            _, topclass_label, subclass_label, topclass_json, subclass_json, attributes_json = class_data
            
            # Convert json strings back to dictionaries so we can work with them in pytho
            topclass_dict = fast_json_to_dict(topclass_json)
            subclass_dict = fast_json_to_dict(subclass_json)
            attributes_dict = fast_json_to_dict(attributes_json)
            
        except IndexError:
            # If we don't find the object, return a default entry
            default_class_data = new_classifier_report_entry(object_id)
            topclass_label = default_class_data["topclass_label"]
            subclass_label = default_class_data["subclass_label"]
            topclass_dict = default_class_data["topclass_dict"]
            subclass_dict = default_class_data["subclass_dict"]            
            attributes_dict = default_class_data["attributes_dict"]
        
        return topclass_label, subclass_label, topclass_dict, subclass_dict, attributes_dict
    
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
    
    def __init__(self, cameras_folder_path, camera_select, user_select,
                 db_path = ":memory:", check_same_thread = True):
        
        # Inherit from parent
        super().__init__(cameras_folder_path, camera_select, user_select, db_path, check_same_thread)
    
    # .................................................................................................................
    
    def _table_name(self):        
        return "[{}-summary]".format(self.camera_select)
    
    # .................................................................................................................
        
    def _initialize_tables(self):
        
        cursor = self._cursor()
        
        # Define object summary table columns
        objs_columns = ["full_id INTEGER PRIMARY KEY",
                        "summary_data_json TEXT"]
        objs_column_str = ", ".join(objs_columns)
        
        # Initialize a table for object summary data
        table_name = self._table_name()
        objs_cursor_cmd = "CREATE TABLE {}({})".format(table_name, objs_column_str)
        cursor.execute(objs_cursor_cmd)
            
        self.connection.commit()
    
    # .................................................................................................................
    
    def add_entry(self, full_id, summary_data_json = "{}"):
        
        # Bundle data in the correct order for database entry
        new_entry_var_list = ["full_id", "summary_data_json"]
        new_entry_value_list = [full_id, summary_data_json]
        new_entry_q_list = ["?"] * len(new_entry_var_list)
        
        # Build insert command
        insert_table = self._table_name()
        insert_vars = ", ".join(new_entry_var_list)
        insert_qs = ",".join(new_entry_q_list)
        insert_cmd = "INSERT INTO {}({}) VALUES({})".format(insert_table, insert_vars, insert_qs)
        
        # Update the database!
        cursor = self._cursor()
        cursor.execute(insert_cmd, new_entry_value_list)
        self.connection.commit()
    
    # .................................................................................................................
    
    def save_entry(self, full_id, new_summary_data_dict):
        
        # Save a file to represent the summary data
        save_summary_report_data(self.cameras_folder_path, self.camera_select, self.user_select, 
                          full_id, new_summary_data_dict)
    
    # .................................................................................................................
    
    def load_summary_data(self, object_id):
        
        # Build selection commands
        table_name = self._table_name()
        select_cmd = """SELECT summary_data_json FROM {} WHERE full_id = {}""".format(table_name, object_id)
        
        # Get data from database!
        cursor = self._cursor()
        cursor.execute(select_cmd)
        summary_data_json = cursor.fetchone()
        
        # Handle missing data case
        if summary_data_json is None:
            summary_data_json = ("{}",)
        
        # Convert to a dictionary for python usage
        summary_data_dict = fast_json_to_dict(summary_data_json[0])
        
        return summary_data_dict
    
    # .................................................................................................................
    # .................................................................................................................


# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////


class Rule_DB(File_DB):
    
    # .................................................................................................................
    
    def __init__(self, cameras_folder_path, camera_select, user_select,
                 db_path = ":memory:", check_same_thread = True):
        
        # Allocate storage for known rule names
        self.rule_name_set = set()
        
        # Inherit from parent
        super().__init__(cameras_folder_path, camera_select, user_select, db_path, check_same_thread)
    
    # .................................................................................................................
    
    def _table_name(self, rule_name):
        return "[{}-rule-{}]".format(self.camera_select, rule_name)
    
    # .................................................................................................................
        
    def _initialize_tables(self):
        
        # Find all known rule names
        self.rule_name_set = self._get_existing_rule_report_names(self.cameras_folder_path, 
                                                                  self.camera_select, 
                                                                  self.user_select)
        
        # Create a table for all known rules
        for each_rule_name in self.rule_name_set:            
            self._create_rule_table(each_rule_name)
        
    # .................................................................................................................
    
    def _create_rule_table(self, rule_name):
        
        # Define rule table columns
        objs_columns = ["full_id INTEGER PRIMARY KEY",
                        "rule_type TEXT",
                        "num_violations INTEGER",
                        "rule_results_dict_json TEXT",
                        "rule_results_list_json TEXT"]
        objs_column_str = ", ".join(objs_columns)
        
        # Initialize a table for rule data
        cursor = self._cursor()
        table_name = self._table_name(rule_name)
        objs_cursor_cmd = "CREATE TABLE {}({})".format(table_name, objs_column_str)
        cursor.execute(objs_cursor_cmd)
        self.connection.commit()
    
    # .................................................................................................................
    
    def register_new_rule(self, rule_name):
        
        # Don't need to do anything if we already know about the given rule name
        if rule_name in self.rule_name_set:
            return
        
        # If we don't know about the rule name, create a table for it and record it's name
        self._create_rule_table(rule_name)
        self.rule_name_set.add(rule_name)
    
    # .................................................................................................................
    
    def add_entry(self, rule_name, full_id, rule_type, num_violations, 
                  rule_results_dict_json = "{}", rule_results_list_json = "[]"):
        
        # Bundle data in the correct order for database entry
        new_entry_var_list = ["full_id", "rule_type", "num_violations", 
                              "rule_results_dict_json", "rule_results_list_json"]
        new_entry_value_list = [full_id, rule_type, num_violations, rule_results_dict_json, rule_results_list_json]
        new_entry_q_list = ["?"] * len(new_entry_var_list)
        
        # Build insert command
        insert_table = self._table_name(rule_name)
        insert_vars = ", ".join(new_entry_var_list)
        insert_qs = ",".join(new_entry_q_list)
        insert_cmd = "INSERT INTO {}({}) VALUES({})".format(insert_table, insert_vars, insert_qs)
        
        try:
            # Update the database!
            cursor = self._cursor()
            cursor.execute(insert_cmd, new_entry_value_list)
            self.connection.commit()
        except sqlite3.OperationalError as err:
            
            print("", "",
                  "Error adding to table: {}".format(insert_table), 
                  "Table columns:",
                  self._list_table_columns(insert_table),
                  "",
                  sep = "\n")
            
            ide_quit(err)
        
        return
    
    # .................................................................................................................
    
    def save_entry(self, rule_name, rule_type, object_full_id, new_rule_results_dict, new_rule_results_list):
        
        # Save a file to represent the rule evalation data
        save_rule_report_data(self.cameras_folder_path, self.camera_select, self.user_select, 
                              rule_name, rule_type, object_full_id, new_rule_results_dict, new_rule_results_list)
    
    # .................................................................................................................
    
    def load_rule_data(self, rule_name, object_id):
        
        # Build selection commands
        table_name = self._table_name(rule_name)
        select_cmd = """SELECT * FROM {} WHERE full_id = {}""".format(table_name, object_id)
        
        # Get data from database!
        cursor = self._cursor()
        cursor.execute(select_cmd)
        rule_data = cursor.fetchall()
        
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
    
    def _get_existing_rule_report_names(self, cameras_folder_path, camera_select, user_select):
        
        # Check reporting folder for rule results
        rule_report_folder_path = build_rule_adb_metadata_report_path(cameras_folder_path, camera_select, user_select)
        
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
#%% Define functions

# .....................................................................................................................

def fetchall_to_1d_list(fetchall_result, return_index = 0):
    
    ''' Helper function which flattens a list of tuples, which may be returned from sqlite fetchall commands '''
    
    if fetchall_result is None:
        return []
    
    return [each_entry[return_index] for each_entry in fetchall_result]

# .....................................................................................................................

def _post_camera_info_metadata(camera_info_metadata_folder_path, database):
    
    # Start timing
    t_start = perf_counter()
    
    # Get all files, read the saved data and post appropriately to the database
    info_file_path_list = get_file_list(camera_info_metadata_folder_path, 
                                        return_full_path = True, 
                                        sort_list = False)
    
    # Add each camera entry to the database
    for each_file_path in info_file_path_list:
        
        # Pull data out of the camera info metadata file
        cam_info_md = load_jgz(each_file_path)
        mongo_id = cam_info_md["_id"]
        ip_address = cam_info_md["ip_address"]
        time_zone = cam_info_md["time_zone"]
        start_datetime_isoformat = cam_info_md["start_datetime_isoformat"]
        start_epoch_ms = cam_info_md["start_epoch_ms"]
        video_select = cam_info_md["video_select"]
        video_fps = cam_info_md["video_fps"]
        video_width = cam_info_md["video_width"]
        video_height = cam_info_md["video_height"]
        snapshot_width = cam_info_md["snapshot_width"]
        snapshot_height = cam_info_md["snapshot_height"]
        
        # 'POST' to the database
        database.add_entry(mongo_id, ip_address, time_zone, start_datetime_isoformat, start_epoch_ms,
                           video_select, video_fps, video_width, video_height,
                           snapshot_width, snapshot_height)
    
    # End timing
    t_end = perf_counter()
    time_taken_sec = (t_end - t_start)
    
    return time_taken_sec

# .....................................................................................................................

def _post_rule_info_metadata(rule_info_metadata_folder_path, database):
    
    # Start timing
    t_start = perf_counter()
    
    # Get all files, read the saved data and post appropriately to the database
    rule_info_file_path_list = get_file_list(rule_info_metadata_folder_path, 
                                             return_full_path = True, 
                                             sort_list = False)
    
    # Add each rule info entry to the database
    for each_file_path in rule_info_file_path_list:
        
        # Pull data out of the rule info metadata file
        rule_info_md = load_jgz(each_file_path)
        rule_name = rule_info_md["rule_name"]
        rule_type = rule_info_md["rule_type"]
        configuration_dict = rule_info_md["configuration"]
        
        configuration_json = fast_dict_to_json(configuration_dict)
        
        # 'POST' to the database
        database.add_entry(rule_name, rule_type, configuration_json)
    
    # End timing
    t_end = perf_counter()
    time_taken_sec = (t_end - t_start)
    
    return time_taken_sec

# .....................................................................................................................

def _post_snapshot_metadata(snapshot_metadata_folder_path, database):
    
    # Start timing
    t_start = perf_counter()
    
    # Get all files, read the saved data and post appropriately to the database
    snapshot_path_list = get_file_list(snapshot_metadata_folder_path, 
                                       return_full_path = True, 
                                       sort_list = False)
    
    # Add each snapshot entry to the database
    for each_file_path in snapshot_path_list:
        
        # Pull data out of the snapshot metadata file
        snap_md = load_jgz(each_file_path)
        mongo_id = snap_md["_id"]
        frame_index = snap_md["frame_index"]
        datetime_isoformat = snap_md["datetime_isoformat"]
        epoch_ms = snap_md["epoch_ms"]
        
        # 'POST' to the database
        database.add_entry(mongo_id, frame_index, datetime_isoformat, epoch_ms)
    
    # End timing
    t_end = perf_counter()
    time_taken_sec = (t_end - t_start)
    
    return time_taken_sec

# .....................................................................................................................

def _post_object_metadata(object_metadata_folder_path, database):
    
    # Start timing
    t_start = perf_counter()
    
    # Get all files, read the saved data and post appropriately to the database
    objmd_path_list = get_file_list(object_metadata_folder_path, 
                                    return_full_path = True,
                                    sort_list = False)
    
    # Add each object entry to the database
    for each_file_path in objmd_path_list:
        
        # Pull data out of the object metadata file
        obj_md = load_jgz(each_file_path)
        mongo_id = obj_md["_id"]
        full_id = obj_md["full_id"]
        nice_id = obj_md["nice_id"]
        ancestor_id = obj_md["ancestor_id"]
        descendant_id = obj_md["descendant_id"]
        is_final = obj_md["is_final"]
        
        first_epoch_ms = obj_md["first_epoch_ms"]
        final_epoch_ms = obj_md["final_epoch_ms"]
        lifetime_ms = obj_md["lifetime_ms"]
        
        first_frame_index = obj_md["first_frame_index"]
        final_frame_index = obj_md["final_frame_index"]
        num_samples = obj_md["num_samples"]
        
        bdb_classifier_json = fast_dict_to_json(obj_md.get("bdb_classifier", {}))
        adb_classifier_json = fast_dict_to_json(obj_md.get("adb_classifier", {}))
        
        metadata_json = fast_dict_to_json(obj_md)

        # 'POST' to the database
        database.add_entry(mongo_id, full_id, nice_id, ancestor_id, descendant_id, is_final,
                           first_epoch_ms, final_epoch_ms, lifetime_ms,
                           first_frame_index, final_frame_index, num_samples, 
                           bdb_classifier_json, adb_classifier_json,
                           metadata_json)
    
    # End timing
    t_end = perf_counter()
    time_taken_sec = (t_end - t_start)
    
    return time_taken_sec

# .....................................................................................................................

def _post_classifier_adb_metadata(classifier_adb_metadata_folder_path, database):
    
    # Start timing
    t_start = perf_counter()
    
    # Get all files, read the saved data and post appropriately to the database
    objclassmd_path_list = get_file_list(classifier_adb_metadata_folder_path, 
                                         return_full_path = True,
                                         sort_list = False)
    
    # Add each classified object entry to the database
    for each_file_path in objclassmd_path_list:
        
        # Pull data out of the classifier metadata file
        class_md = load_jgz(each_file_path)
        full_id = class_md["full_id"]
        topclass_label = class_md["topclass_label"]
        subclass_label = class_md["subclass_label"]
        topclass_dict = class_md["topclass_dict"]
        subclass_dict = class_md["subclass_dict"]
        attributes_dict = class_md["attributes_dict"]
        
        # Convert dictionarys to json string for the database
        topclass_json = fast_dict_to_json(topclass_dict)
        subclass_json = fast_dict_to_json(subclass_dict)
        attributes_json = fast_dict_to_json(attributes_dict)

        # 'POST' to the database
        database.add_entry(full_id, topclass_label, subclass_label, topclass_json, subclass_json, attributes_json)
    
    # End timing
    t_end = perf_counter()
    time_taken_sec = (t_end - t_start)
    
    return time_taken_sec

# .....................................................................................................................

def _post_summary_adb_metadata(summary_adb_metadata_folder_path, database):
    
    # Start timing
    t_start = perf_counter()
    
    # Get all files, read the saved data and post appropriately to the database
    summarymd_path_list = get_file_list(summary_adb_metadata_folder_path, 
                                        return_full_path = True,
                                        sort_list = False)
    
    # Add each summary object entry to the database
    for each_file_path in summarymd_path_list:
        
        # Pull data out of the summary file and convert to json for the database
        summary_md = load_jgz(each_file_path)
        full_id = summary_md["full_id"]
        summary_data_json = fast_dict_to_json(summary_md)

        # 'POST' to the database
        database.add_entry(full_id, summary_data_json)
    
    # End timing
    t_end = perf_counter()
    time_taken_sec = (t_end - t_start)
    
    return time_taken_sec

# .....................................................................................................................

def _post_rule_adb_metadata(rule_adb_metadata_folder_path, database):
    
    # Start timing
    t_start = perf_counter()
    
    # Loop over all rules (by folder pathing)
    rule_folder_paths = get_folder_list(rule_adb_metadata_folder_path, return_full_path = True, sort_list = False)
    for each_rule_path in rule_folder_paths:
        
        # Loop over all saved rule files for the given rule
        each_rule_name = os.path.basename(each_rule_path)
        rule_file_path_list = get_file_list(each_rule_path, return_full_path = True, sort_list = False)        
        for each_file_path in rule_file_path_list:
            
            # Pull data out of each rule file and convert to json for the database
            rule_md = load_jgz(each_file_path)
            full_id = rule_md["full_id"]
            rule_type = rule_md["rule_type"]
            num_violations = rule_md["num_violations"]
            rule_results_dict_json = fast_dict_to_json(rule_md["rule_results_dict"])
            rule_results_list_json = fast_dict_to_json(rule_md["rule_results_list"])
            
            # 'POST' to the database
            database.add_entry(each_rule_name, full_id, rule_type, num_violations, 
                               rule_results_dict_json, rule_results_list_json)
    
    # End timing
    t_end = perf_counter()
    time_taken_sec = (t_end - t_start)
    
    return time_taken_sec

# .....................................................................................................................

def post_snapshot_report_metadata(cameras_folder_path, camera_select, user_select, database):
    
    # Build pathing to snapshot report data
    snapshot_metadata_folder_path = build_snapshot_metadata_report_path(cameras_folder_path, 
                                                                        camera_select, 
                                                                        user_select)
    
    time_taken_sec = _post_snapshot_metadata(snapshot_metadata_folder_path, database)
    
    return time_taken_sec
    
# .....................................................................................................................

def post_object_report_metadata(cameras_folder_path, camera_select, user_select, database):
    
    # Build pathing to object report data
    object_metadata_folder_path = build_object_metadata_report_path(cameras_folder_path, 
                                                                    camera_select, 
                                                                    user_select)
    
    time_taken_sec = _post_object_metadata(object_metadata_folder_path, database)
    
    return time_taken_sec

# .....................................................................................................................

def post_classifier_report_data(cameras_folder_path, camera_select, user_select, database):
    
    # Build pathing to object classification report data
    classifier_adb_metadata_folder_path = build_classifier_adb_metadata_report_path(cameras_folder_path, 
                                                                                    camera_select,
                                                                                    user_select)
    
    time_taken_sec = _post_classifier_adb_metadata(classifier_adb_metadata_folder_path, database)
    
    return time_taken_sec


# .....................................................................................................................

def post_summary_report_data(cameras_folder_path, camera_select, user_select, database):
    
    # Build pathing to object summary report data
    summary_adb_metadata_folder_path = build_summary_adb_metadata_report_path(cameras_folder_path,
                                                                              camera_select,
                                                                              user_select)
    
    time_taken_sec = _post_summary_adb_metadata(summary_adb_metadata_folder_path, database)
    
    return time_taken_sec

# .....................................................................................................................

def post_rule_report_data(cameras_folder_path, camera_select, user_select, database):
    
    # Build pathing to rule report data
    rule_adb_metadata_folder_path = build_rule_adb_metadata_report_path(cameras_folder_path,
                                                                        camera_select,
                                                                        user_select)
    
    time_taken_sec = _post_rule_adb_metadata(rule_adb_metadata_folder_path, database)
    
    return time_taken_sec

# .....................................................................................................................

def post_camera_info_report_metadata(cameras_folder_path, camera_select, user_select, database):
    
    # Build pathing to object report data
    camera_info_metadata_folder_path = build_camera_info_metadata_report_path(cameras_folder_path, 
                                                                              camera_select, 
                                                                              user_select)
    
    time_taken_sec = _post_camera_info_metadata(camera_info_metadata_folder_path, database)
    
    return time_taken_sec

# .....................................................................................................................

def post_rule_info_report_metadata(cameras_folder_path, camera_select, user_select, database):
    
    # Build pathing to object report data
    rule_info_metadata_folder_path = build_rule_adb_info_report_path(cameras_folder_path, 
                                                                     camera_select, 
                                                                     user_select)
    
    time_taken_sec = _post_rule_info_metadata(rule_info_metadata_folder_path, database)
    
    return time_taken_sec

# .....................................................................................................................

def launch_file_db(cameras_folder_path, camera_select, user_select, 
                   check_same_thread = True,
                   launch_snapshot_db = True,
                   launch_object_db = True,
                   launch_classification_db = True,
                   launch_summary_db = False,
                   launch_rule_db = False):
    
    # Initialize outputs
    cinfo_db = None
    rinfo_db = None
    snap_db = None
    obj_db = None
    class_db = None
    rule_db = None
    summary_db = None
    
    # Bundle args for clarity
    selection_args = (cameras_folder_path, camera_select, user_select)
    check_thread_arg = {"check_same_thread": check_same_thread}
    
    # Some feedback
    print("", "Launching FILE DB for {}".format(camera_select), sep = "\n")
    print_launch = lambda launch_name: print("  --> {}".format(launch_name).ljust(24), end = "")
    print_done = lambda time_take_sec: print("... Done! ({:.0f} ms)".format(1000 * time_take_sec))
    #print_missing = lambda err_msg: print("... Missing! {}".format(err_msg))
    
    # Always launch camera info db
    print_launch("Camera info")
    cinfo_db = Camera_Info_DB(*selection_args, **check_thread_arg)
    cam_time = post_camera_info_report_metadata(*selection_args, cinfo_db)
    print_done(cam_time)
    
    # Always launch rule info db
    print_launch("Rule info")
    rinfo_db = Rule_Info_DB(*selection_args, **check_thread_arg)
    rule_info_time = post_rule_info_report_metadata(*selection_args, rinfo_db)
    print_done(rule_info_time)
    
    if launch_snapshot_db:
        print_launch("Snapshots")
        snap_db = Snap_DB(*selection_args, **check_thread_arg)
        snap_time = post_snapshot_report_metadata(*selection_args, snap_db)
        print_done(snap_time)
    
    if launch_object_db:
        print_launch("Objects")
        obj_db = Object_DB(*selection_args, **check_thread_arg)
        obj_time = post_object_report_metadata(*selection_args, obj_db)
        print_done(obj_time)
    
    if launch_classification_db:
        print_launch("Classifications")
        class_db = Classification_DB(*selection_args, **check_thread_arg)
        class_time = post_classifier_report_data(*selection_args, class_db)
        print_done(class_time)
    
    if launch_summary_db:
        print_launch("Summary")
        summary_db = Summary_DB(*selection_args, **check_thread_arg)
        summary_time = post_summary_report_data(*selection_args, summary_db)
        print_done(summary_time)
    
    if launch_rule_db:
        print_launch("Rules")
        rule_db = Rule_DB(*selection_args, **check_thread_arg)
        rule_time = post_rule_report_data(*selection_args, rule_db)
        print_done(rule_time)
    
    return cinfo_db, rinfo_db, snap_db, obj_db, class_db, summary_db, rule_db

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


