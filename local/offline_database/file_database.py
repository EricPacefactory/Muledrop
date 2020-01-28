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
import json
import cv2
import numpy as np
import datetime as dt

from time import perf_counter

from local.lib.common.timekeeper_utils import datetime_to_epoch_ms
from local.lib.common.timekeeper_utils import parse_isoformat_string, get_isoformat_string, isoformat_to_epoch_ms

from local.lib.file_access_utils.reporting import build_camera_info_metadata_report_path
from local.lib.file_access_utils.reporting import build_snapshot_image_report_path
from local.lib.file_access_utils.reporting import build_snapshot_metadata_report_path
from local.lib.file_access_utils.reporting import build_object_metadata_report_path

from local.lib.file_access_utils.classifier import load_label_lut_tuple, save_classifier_data
from local.lib.file_access_utils.classifier import new_classification_entry
from local.lib.file_access_utils.classifier import build_classifier_adb_metadata_report_path

from local.lib.file_access_utils.summary import save_summary_data, build_summary_adb_metadata_report_path

from eolib.utils.cli_tools import cli_prompt_with_defaults
from eolib.utils.read_write import load_json
from eolib.utils.files import get_file_list

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
    
    def head(self, number_to_return = 5):
        
        ''' Function used to inspect the top few elements of the database '''
        
        # Get table name in more convenient format
        table_name = self._table_name()
        
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
    
    # .................................................................................................................
    # .................................................................................................................


# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////


class Camera_DB(File_DB):
    
    # .................................................................................................................
    
    def __init__(self, cameras_folder_path, camera_select, user_select,
                 db_path = ":memory:", check_same_thread = True):
        
        # Inherit from parent
        super().__init__(cameras_folder_path, camera_select, user_select, db_path, check_same_thread)
    
    # .................................................................................................................
    
    def _table_name(self):
        return "[{}-info]".format(self.camera_select)
    
    # .................................................................................................................
        
    def _initialize_tables(self):
        
        cursor = self._cursor()
        
        # Define table columns
        objs_columns = ["camera_name TEXT PRIMARY KEY",
                        "ip_address TEXT",
                        "datetime_isoformat TEXT",
                        "time_zone TEXT"]
        objs_column_str = ", ".join(objs_columns)
        
        # Initialize the table 
        obj_table_name = self._table_name()
        objs_cursor_cmd = "CREATE TABLE {}({})".format(obj_table_name, objs_column_str)
        cursor.execute(objs_cursor_cmd)
            
        self.connection.commit()
    
    # .................................................................................................................
    
    def add_entry(self, ip_address, datetime_isoformat, time_zone):
        
        # Bundle data in the correct order for database entry
        new_entry_var_list = ["camera_name", "ip_address", "datetime_isoformat", "time_zone"]
        new_entry_value_list = [self.camera_select, ip_address, datetime_isoformat, time_zone]
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
        
        # Build string to get total object count
        select_cmd = "SELECT * FROM {}".format(self._table_name())
        
        # Get data from database!
        cursor = self._cursor()
        cursor.execute(select_cmd)
        camera_info = cursor.fetchone()
        
        # Make up fake camera info if nothing is returned, to avoid crippling errors
        if camera_info is None:
            camera_info = (self.camera_select, None, None, None)
        
        # Break apart return value for clarity
        camera_name, ip_address, datetime_isoformat, time_zone = camera_info
        
        return camera_name, ip_address, datetime_isoformat, time_zone
    
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
            raise FileNotFoundError("Couldn't find snapshot image folder: {}".format(self.snap_images_folder_path))
        
    # .................................................................................................................
    
    def _table_name(self, table_select = None):        
        return "[{}-snapshots]".format(self.camera_select)
    
    # .................................................................................................................
        
    def _initialize_tables(self):
        
        cursor = self._cursor()
        
        # Initialize table for snapshot metadata
        snaps_columns = ["name TEXT", 
                         "count INTEGER",
                         "frame_index INTEGER",
                         "datetime_isoformat TEXT",
                         "epoch_ms INTEGER PRIMARY KEY",
                         "snap_width INTEGER",
                         "snap_height INTEGER"]
        snaps_column_str = ", ".join(snaps_columns)
        snaps_cursor_cmd = "CREATE TABLE {}({})".format(self._table_name(), snaps_column_str)
        cursor.execute(snaps_cursor_cmd)
        
        self.connection.commit()
    
    # .................................................................................................................
    
    def add_entry(self, name, count, frame_index, datetime_isoformat, epoch_ms, snap_width, snap_height):
        
        # Bundle data in the correct order for database entry
        new_entry_var_list = ["name", "count", "frame_index", "datetime_isoformat", "epoch_ms", 
                              "snap_width", "snap_height"]
        new_entry_value_list = [name, count, frame_index, datetime_isoformat,  epoch_ms, 
                                snap_width, snap_height]
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
        start_epoch_ms = _time_to_epoch_ms(start_time)
        end_epoch_ms = _time_to_epoch_ms(end_time)
        
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
        
        # Convert time input into an epoch_ms value to search database
        target_epoch_ms = _time_to_epoch_ms(target_time)
        
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
        floor_snapshot_epoch_ms = cursor.fetchone()
        no_floor = (floor_snapshot_epoch_ms is None)
        
        # Get upper bound snapshot
        cursor.execute(ceil_select_cmd)
        ceil_snapshot_epoch_ms = cursor.fetchone()
        no_ceil = (ceil_snapshot_epoch_ms is None)
        
        # Deal with missing return values
        if no_floor and no_ceil:
            raise FileNotFoundError("Couldn't find close snapshots in database! ({})".format(target_time))
        if no_ceil:
            ceil_snapshot_epoch_ms = floor_snapshot_epoch_ms
        if no_floor:
            floor_snapshot_epoch_ms = ceil_snapshot_epoch_ms
        
        return floor_snapshot_epoch_ms[0], ceil_snapshot_epoch_ms[0]
    
    # .................................................................................................................
    
    def get_snap_frame_wh(self):
        
        # Build selection commands
        select_cmd = "SELECT snap_width, snap_height FROM {} LIMIT 1".format(self._table_name())
        
        # Get data from database!
        cursor = self._cursor()
        
        # Get lower bound snapshot
        cursor.execute(select_cmd)
        snap_wh = cursor.fetchall()[0]
        
        return snap_wh
    
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
        output_dict = {"name": target_snapshot_entry[0],
                       "count": target_snapshot_entry[1],
                       "frame_index": target_snapshot_entry[2],
                       "datetime_isoformat": target_snapshot_entry[3],
                       "epoch_ms": target_snapshot_entry[4],
                       "snap_width": target_snapshot_entry[5],
                       "snap_height": target_snapshot_entry[6]}
        
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
        snap_name = snap_md["name"]
        snap_frame_index = snap_md["frame_index"]
        
        # Build pathing to the corresponding image
        snap_image_name = "{}.jpg".format(snap_name)
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
        objs_columns = ["full_id INTEGER PRIMARY KEY",
                        "nice_id INTEGER", 
                        "ancestor_id INTEGER", 
                        "decendent_id INTEGER",
                        "is_final INTEGER",
                        "detection_class TEXT",
                        "classification_score REAL",
                        "first_epoch_ms INTEGER",
                        "last_epoch_ms INTEGER",
                        "lifetime_ms INTEGER", 
                        "start_frame_index INTEGER",
                        "end_frame_index INTEGER",
                        "num_samples INTEGER",
                        "metadata_json TEXT"]
        objs_column_str = ", ".join(objs_columns)
        
        # Initialize the table 
        obj_table_name = self._table_name()
        objs_cursor_cmd = "CREATE TABLE {}({})".format(obj_table_name, objs_column_str)
        cursor.execute(objs_cursor_cmd)
            
        self.connection.commit()
        
    # .................................................................................................................
    
    def add_entry(self, full_id, nice_id, ancestor_id, decendent_id, is_final,
                  detection_class, classification_score,
                  first_epoch_ms, last_epoch_ms, lifetime_ms,
                  start_frame_index, end_frame_index, num_samples, metadata_json):
        
        # Bundle data in the correct order for database entry
        new_entry_var_list = ["full_id", "nice_id", "ancestor_id", "decendent_id", "is_final",
                              "detection_class", "classification_score",
                              "first_epoch_ms", "last_epoch_ms", "lifetime_ms",
                              "start_frame_index", "end_frame_index", "num_samples", "metadata_json"]
        new_entry_value_list = [full_id, nice_id, ancestor_id, decendent_id, is_final,
                                detection_class, classification_score,
                                first_epoch_ms, last_epoch_ms, lifetime_ms,
                                start_frame_index, end_frame_index, num_samples,  metadata_json]
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
        start_epoch_ms = _time_to_epoch_ms(start_time)
        end_epoch_ms = _time_to_epoch_ms(end_time)
        
        # Build selection commands
        table_name = self._table_name()        
        select_cmd = """
                     SELECT full_id
                     FROM {}
                     WHERE 
                     last_epoch_ms >= {} 
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
        target_epoch_ms = _time_to_epoch_ms(target_time)
        
        # Build selection commands
        table_name = self._table_name()
        select_cmd = """
                     SELECT full_id
                     FROM {}
                     WHERE {} 
                     BETWEEN 
                     first_epoch_ms AND last_epoch_ms
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
        metadata_dict = json.loads(metadata_json)
        
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
        
        # Load the class labelling lookup table for graphic settings
        self._class_label_lut, self.label_to_idx_dict = load_label_lut_tuple(cameras_folder_path, camera_select)        
        self.num_classes, self.valid_labels_dict, self.ignoreable_labels_list = self.get_labels()
        
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
                        "class_label TEXT",
                        "score_pct INTEGER",
                        "is_classified INTEGER",
                        "subclass TEXT",
                        "attributes_json TEXT"]
        objs_column_str = ", ".join(objs_columns)
        
        # Initialize a table for object classifications
        table_name = self._table_name()
        objs_cursor_cmd = "CREATE TABLE {}({})".format(table_name, objs_column_str)
        cursor.execute(objs_cursor_cmd)
            
        self.connection.commit()
    
    # .................................................................................................................
    
    def add_entry(self, full_id, class_label, score_pct, subclass = "", attributes_json = "{}"):
        
        # Create variable to signify whether the object has been classified or not
        is_classified = int(class_label.lower() != "unclassified")
        if not is_classified:
            score_pct = 0
        
        # Bundle data in the correct order for database entry
        new_entry_var_list = ["full_id", "class_label", "is_classified", "score_pct", "subclass", "attributes_json"]
        new_entry_value_list = [full_id, class_label, is_classified, score_pct, subclass, attributes_json]
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
    
    def save_entry(self, full_id, new_class_label, new_score_pct, new_subclass = "", new_attributes_dict = None):
        
        # Create unique dictionary every time the function is called, for safety
        new_attributes_dict = {} if new_attributes_dict is None else new_attributes_dict
        
        # Save a file to represent the classifier data
        save_classifier_data(self.cameras_folder_path, self.camera_select, self.user_select, 
                             full_id, new_class_label, new_score_pct, new_subclass, new_attributes_dict)
    
    # .................................................................................................................
    
    def get_class_colors(self, class_label):
        
        # Look up coloring from class label lookup tables
        trail_color_rgb = self._class_label_lut[class_label]["trail_color"]
        outline_color_rgb = self._class_label_lut[class_label]["outline_color"]
        
        # Convert to bgr for OpenCV
        trail_color_bgr = trail_color_rgb[::-1]
        outline_color_bgr = outline_color_rgb[::-1]
        
        return trail_color_bgr, outline_color_bgr
        
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
            _, class_label, score_pct, is_classified, subclass, attributes_json = object_classification_data[0]
            
        except IndexError:
            # If we don't find the object, return a default entry
            new_class_dict =  new_classification_entry(object_id)
            class_label = new_class_dict["class_label"]
            score_pct = new_class_dict["score_pct"]
            subclass = new_class_dict["subclass"]
            attributes_dict = new_class_dict["attributes"]            
            attributes_json = json.dumps(attributes_dict)
        
        # Convert attributes back to python dictionary for convenience
        attributes_dict = json.loads(attributes_json)
        
        return class_label, score_pct, subclass, attributes_dict
    
    # .................................................................................................................
    
    def get_labels(self):
        
        # Go through all labelling info and split into valid labels and ignoreables (based on class indices)
        valid_labels_dict = {}
        ignoreable_labels_list = [] 
        for each_label, each_idx in self.label_to_idx_dict.items():
            valid_idx = (each_idx >= 0)
            
            if valid_idx:
                valid_labels_dict.update({each_label: each_idx})
            else:
                ignoreable_labels_list.append(each_label)
        
        # Count the number of valid classes, since we'll need to make our one-hot vector at least this long!
        num_valid_classes = len(valid_labels_dict)
        
        return num_valid_classes, valid_labels_dict, ignoreable_labels_list
    
    # .................................................................................................................
    
    def ordered_class_names(self):
        
        ''' Helper function to get class labels in sorted (by index) order '''
        
        idx_label_list = [(each_idx, each_label) for each_label, each_idx in self.valid_labels_dict.items()]
        sorted_idxs, sorted_labels = zip(*sorted(idx_label_list))
        
        return sorted_labels
    
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
        return "[summary-({})]".format(self.camera_select)
    
    # .................................................................................................................
        
    def _initialize_tables(self):
        
        cursor = self._cursor()
        
        # Define object classification table columns
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
        save_summary_data(self.cameras_folder_path, self.camera_select, self.user_select, 
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
        
        # Convert to a dictionary for python usage
        summary_data_dict = json.loads(summary_data_json)
        
        return summary_data_dict
    
    # .................................................................................................................
    # .................................................................................................................


# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////


class Rule_DB(File_DB):
    
    # .................................................................................................................
    
    def __init__(self, rule_name, cameras_folder_path, camera_select, user_select,
                 db_path = ":memory:", check_same_thread = True):
        
        # Store additional rule information
        self.rule_name = rule_name
        
        # Inherit from parent
        super().__init__(cameras_folder_path, camera_select, user_select, db_path, check_same_thread)
    
    # .................................................................................................................
    
    def _table_name(self):        
        return "[rule-({})]".format(self.rule_name)
    
    # .................................................................................................................
        
    def _initialize_tables(self):
        
        raise NotImplementedError("Need to initial table(s)! ({})".format(self._class_name))
        
        return None
    
    # .................................................................................................................
    
    def add_entry(self, *args, **kwargs):
        
        raise NotImplementedError("Add entry function not implemented! ({})".format(self._class_name))
        
        return None
    
    # .................................................................................................................
    # .................................................................................................................


# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////


# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

# .................................................................................................................

def _time_to_epoch_ms(time_value):
    
    value_type = type(time_value)
    
    # If an integer is provided, assume it is already an epoch_ms value
    if value_type in [int, np.int64]:
        return time_value
    
    # If a float is provided, assume it is an epoch_ms value, so return integer version
    elif value_type is float:
        return int(round(time_value))
    
    # If a datetime vlaue is provided, use timekeeper library to convert
    elif value_type is dt.datetime:
        return datetime_to_epoch_ms(time_value)
    
    # If a string is provided, assume it is an isoformat datetime string
    elif value_type is str:
        return isoformat_to_epoch_ms(time_value)
    
    # If we get here, we could've parse the time!
    raise TypeError("Unable to parse input time value: {}, type: {}".format(time_value, value_type))

# .....................................................................................................................

def fetchall_to_1d_list(fetchall_result, return_index = 0):
    
    ''' Helper function which flattens a list of tuples, which may be returned from sqlite fetchall commands '''
    
    if fetchall_result is None:
        return []
    
    return [each_entry[return_index] for each_entry in fetchall_result]

# .....................................................................................................................

def user_input_datetime_range(earliest_datetime, latest_datetime, debug_mode = False):
    
    # Error if the start/end dates are not the same (don't have UI to deal with that yet!)
    same_dates = (earliest_datetime.date() == latest_datetime.date())
    #same_hour = (earliest_datetime.hour == latest_datetime.hour)
    #same_min = (earliest_datetime.min == latest_datetime.min)
    '''
    if not same_dates:
        raise NotImplementedError("Start/end snapshot dates are not the same! Can't deal with this yet...")
    '''

    # Create default strings
    time_format_str = "%Y/%m/%d %H:%M:%S" if (not same_dates) else "%H:%M:%S"
    default_start_str = earliest_datetime.strftime(time_format_str) #"%H:%M:%S")
    default_end_str = latest_datetime.strftime(time_format_str) #"%H:%M:%S")
    replace_bundle_dict = {"tzinfo": earliest_datetime.tzinfo}
    if same_dates:
        replace_bundle_dict.update({"year": earliest_datetime.year,
                                    "month": earliest_datetime.month, 
                                    "day": earliest_datetime.day,})
    
    # Get user to enter start/end datetimes when configuring the rule
    user_start_str = cli_prompt_with_defaults("Enter start of time range:", default_start_str, debug_mode=debug_mode)
    user_end_str = cli_prompt_with_defaults("  Enter end of time range:", default_end_str, debug_mode=debug_mode)
    
    # Convert user inputs back into datetimes
    start_dt = dt.datetime.strptime(user_start_str, time_format_str).replace(**replace_bundle_dict)
    end_dt = dt.datetime.strptime(user_end_str, time_format_str).replace(**replace_bundle_dict)
    
    # Force earliest/latest boundary timing
    start_dt = max(earliest_datetime, start_dt)
    end_dt = min(latest_datetime, end_dt)
    start_dt_isoformat = get_isoformat_string(start_dt)
    end_dt_isoformat = get_isoformat_string(end_dt)
    
    return start_dt, end_dt, start_dt_isoformat, end_dt_isoformat

# .....................................................................................................................

def _post_camera_info_metadata(camera_info_metadata_folder_path, database):
    
    # Start timing
    t_start = perf_counter()
    
    # Get all files, read the saved data and post appropriately to the database
    info_file_path_list = get_file_list(camera_info_metadata_folder_path, 
                                        return_full_path = True, 
                                        sort_list = False)
    
    # Add each snapshot entry to the database
    for each_path in info_file_path_list:
        
        # Pull data out of the camera info metadata file
        obj_info_md = load_json(each_path)
        ip_address = obj_info_md["ip_address"]
        datetime_isoformat = obj_info_md["datetime_isoformat"]
        time_zone = obj_info_md["time_zone"]
        
        # 'POST' to the database
        database.add_entry(ip_address, datetime_isoformat, time_zone)
    
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
    for each_path in snapshot_path_list:
        
        # Pull data out of the snapshot metadata file
        snap_md = load_json(each_path)
        name = snap_md["name"]
        count = snap_md["count"]
        frame_index = snap_md["frame_index"]
        datetime_isoformat = snap_md["datetime_isoformat"]
        epoch_ms = snap_md["epoch_ms"]
        snap_width, snap_height = snap_md["snap_wh"]
        
        # 'POST' to the database
        database.add_entry(name, count, frame_index, datetime_isoformat, epoch_ms, snap_width, snap_height)
    
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
    for each_path in objmd_path_list:
        
        # Pull data out of the object metadata file
        obj_md = load_json(each_path)
        full_id = obj_md["full_id"]
        nice_id = obj_md["nice_id"]
        ancestor_id = obj_md["ancestor_id"]
        decendent_id = obj_md["decendent_id"]
        is_final = obj_md["is_final"]
        
        detection_class = obj_md["detection_class"]
        classification_score = obj_md["classification_score"]
        
        first_epoch_ms = obj_md["timing"]["first_epoch_ms"]
        last_epoch_ms = obj_md["timing"]["last_epoch_ms"]
        lifetime_ms = obj_md["lifetime_ms"]
        
        first_frame_index = obj_md["timing"]["first_frame_index"]
        last_frame_index = obj_md["timing"]["last_frame_index"]
        num_samples = obj_md["num_samples"]
        
        metadata_json = json.dumps(obj_md)

        # 'POST' to the database
        database.add_entry(full_id, nice_id, ancestor_id, decendent_id, is_final,
                           detection_class, classification_score,
                           first_epoch_ms, last_epoch_ms, lifetime_ms,
                           first_frame_index, last_frame_index, num_samples, metadata_json)
    
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
    for each_path in objclassmd_path_list:
        
        # Pull data out of the classifier metadata file
        class_md = load_json(each_path)
        full_id = class_md["full_id"]
        class_label = class_md["class_label"]
        score_pct = class_md["score_pct"]
        subclass = class_md["subclass"]
        attributes = class_md["attributes"]
        
        # Convert attributes dictionary to a json string for the database
        attributes_json = json.dumps(attributes)

        # 'POST' to the database
        database.add_entry(full_id, class_label, score_pct, subclass, attributes_json)
    
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
    for each_path in summarymd_path_list:
        
        # Pull data out of the summary file and convert to json for the database
        summary_md = load_json(each_path)
        full_id = summary_md["full_id"]
        summary_data_json = json.dumps(summary_md)

        # 'POST' to the database
        database.add_entry(full_id, summary_data_json)
    
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

def post_camera_info_report_metadata(cameras_folder_path, camera_select, user_select, database):
    
    # Build pathing to object report data
    camera_info_metadata_folder_path = build_camera_info_metadata_report_path(cameras_folder_path, 
                                                                              camera_select, 
                                                                              user_select)
    
    time_taken_sec = _post_camera_info_metadata(camera_info_metadata_folder_path, database)
    
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
    print_missing = lambda err_msg: print("... Missing! {}".format(err_msg))
    
    # Always launch camera db
    print_launch("Camera info")
    cam_db = Camera_DB(*selection_args, **check_thread_arg)
    cam_time = post_camera_info_report_metadata(*selection_args, cam_db)
    print_done(cam_time)
    
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
        print_missing("(not implemented yet)")    
    
    return cam_db, snap_db, obj_db, class_db, summary_db, rule_db

# .....................................................................................................................

def close_dbs_if_missing_data(*database_refs, error_if_missing_data = True):
    
    ''' Helper function which closes all provided databases if any are missing data '''
    
    # Check if any of the databases are missing data
    dbs_no_data = [each_db.no_data() for each_db in database_refs]
    
    # Close all databases if any are missing data
    missing_data = any(dbs_no_data)
    if missing_data:
        
        # Shutdown all the dbs safely
        for each_db_ref in database_refs:
            each_db_ref.close()
            
        # Raise an error to stop execution when missing data, if needed
        if error_if_missing_data:
            raise RuntimeError("Missing data in database")
            
    return missing_data

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Demo

if __name__ == "__main__":
    pass

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap


