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

from local.lib.timekeeper_utils import utc_datetime_to_epoch_ms, epoch_ms_to_utc_datetime
from local.lib.timekeeper_utils import parse_isoformat_string, isoformat_datetime_string, isoformat_to_epoch_ms

from local.lib.file_access_utils.structures import build_task_list

from local.lib.file_access_utils.reporting import build_snapshot_image_report_path
from local.lib.file_access_utils.reporting import build_snapshot_metadata_report_path
from local.lib.file_access_utils.reporting import build_object_metadata_report_path

from local.lib.file_access_utils.classifier import build_snapshot_image_dataset_path
from local.lib.file_access_utils.classifier import build_snapshot_metadata_dataset_path
from local.lib.file_access_utils.classifier import build_object_metadata_dataset_path

from local.lib.file_access_utils.classifier import load_label_lut_tuple, load_local_classification_file
from local.lib.file_access_utils.classifier import update_local_classification_file, new_classification_entry

from eolib.utils.cli_tools import cli_prompt_with_defaults
from eolib.utils.read_write import load_json
from eolib.utils.files import get_file_list

# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes

class File_DB:
    
    # .................................................................................................................
    
    def __init__(self, cameras_folder_path, camera_select, user_select,
                 db_path = ":memory:"):
        
        # Store camera/user selections
        self.cameras_folder_path = cameras_folder_path
        self.camera_select = camera_select
        self.user_select = user_select
        
        # Allocate storage for db info
        self.db_path = db_path
        self.connection = None
        
        # Start up the database!
        self.connection = self.connect()
        self._initialize_tables()
    
    # .................................................................................................................
    
    def __repr__(self):
        num_tables = len(self._list_table_names())
        return "{} ({} tables)".format(self._class_name, num_tables)
    
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
    
    def _table_name(self, table_select = None):
        
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
    
    def head(self, table_select = None, number_to_return = 5):
        
        ''' Function used to inspect the top few elements of the database '''
        
        # Get table name in more convenient format
        try:
            table_name = self._table_name(table_select)
        except Exception:
            print("Error with table name!",
                  "Must be one of the following:",
                  *self._list_table_names, sep = "\n")
            return
        
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
    
    def connect(self):
        
        connection = None
        try:
            connection = sqlite3.connect(self.db_path)
            print("", "Starting {}. SQLITE Version: {}".format(self._class_name, sqlite3.version), sep = "\n")
        except Exception as err:
            print("Error connecting to file DB! ({})".format(self.db_path))
            raise err
        
        return connection
        
    # .................................................................................................................
    
    def close(self):
        if self.connection is not None:
            self.connection.close()
    
    # .................................................................................................................
    # .................................................................................................................


# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////


class Background_DB(File_DB):
    
    # .................................................................................................................
    
    def __init__(self, cameras_folder_path, camera_select, user_select,
                 db_path = ":memory:"):
        
        # Inherit from parent
        super().__init__(cameras_folder_path, camera_select, user_select, db_path)
        
    # .................................................................................................................
    # .................................................................................................................


# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////


class Snap_DB(File_DB):
    
    # .................................................................................................................
    
    def __init__(self, cameras_folder_path, camera_select, user_select,
                 load_from_dataset = None,
                 db_path = ":memory:"):
        
        # Inherit from parent
        super().__init__(cameras_folder_path, camera_select, user_select, db_path)
        
        # Set up pathing to load image data
        load_from_reporting = (load_from_dataset is None)
        if load_from_reporting:
            self.snap_images_folder_path = build_snapshot_image_report_path(cameras_folder_path, 
                                                                            camera_select, 
                                                                            user_select)
        
        else:
            self.snap_images_folder_path = build_snapshot_image_dataset_path(cameras_folder_path,
                                                                             camera_select, 
                                                                             load_from_dataset)
            
        # Check that the snapshot path is valid before continuing
        snapshot_image_folder_exists = os.path.exists(self.snap_images_folder_path)
        if not snapshot_image_folder_exists:
            raise FileNotFoundError("Couldn't find snapshot image folder: {}".format(self.snap_images_folder_path))
        
    # .................................................................................................................
    
    def _table_name(self, table_select = None):        
        return "[snapshots]"
    
    # .................................................................................................................
        
    def _initialize_tables(self):
        
        cursor = self._cursor()
        
        # Initialize table for snapshot metadata
        snaps_columns = ["name TEXT", 
                         "count INTEGER",
                         "frame_index INTEGER",
                         "datetime_isoformat TEXT",
                         "epoch_ms_utc INTEGER PRIMARY KEY",
                         "snap_width INTEGER",
                         "snap_height INTEGER"]
        snaps_column_str = ", ".join(snaps_columns)
        snaps_cursor_cmd = "CREATE TABLE {}({})".format(self._table_name(), snaps_column_str)
        cursor.execute(snaps_cursor_cmd)
        
        self.connection.commit()
    
    # .................................................................................................................
    
    def add_entry(self, name, count, frame_index, datetime_isoformat, epoch_ms_utc, snap_width, snap_height):
        
        # Bundle data in the correct order for database entry
        new_entry_var_list = ["name", "count", "frame_index", "datetime_isoformat", "epoch_ms_utc", 
                              "snap_width", "snap_height"]
        new_entry_value_list = [name, count, frame_index, datetime_isoformat,  epoch_ms_utc, 
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
    
    def get_bounding_epoch_ms(self):
        
        # Build string to get min/max datetimes from snapshots
        select_cmd = "SELECT min(epoch_ms_utc), max(epoch_ms_utc) from {}".format(self._table_name())
        
        # Get data from database!
        cursor = self._cursor()
        cursor.execute(select_cmd)
        min_epoch_ms, max_epoch_ms = cursor.fetchone()
        
        return min_epoch_ms, max_epoch_ms
    
    # .................................................................................................................
    
    def get_bounding_datetimes(self):
        
        # First get bounding epoch times, then convert to datetime objects
        min_epoch_ms, max_epoch_ms = self.get_bounding_epoch_ms()
        min_dt = epoch_ms_to_utc_datetime(min_epoch_ms)
        max_dt = epoch_ms_to_utc_datetime(max_epoch_ms)
        
        return min_dt, max_dt
    
    # .................................................................................................................
    
    def get_all_snapshot_times_by_time_range(self, start_time, end_time):
        
        # Convert input times to epoch values
        start_epoch_ms = _time_to_epoch_ms_utc(start_time)
        end_epoch_ms = _time_to_epoch_ms_utc(end_time)
        
        # Build command string for getting all snapshot times between start/end
        select_cmd = "SELECT epoch_ms_utc FROM {} WHERE epoch_ms_utc BETWEEN {} and {}".format(self._table_name(), 
                                                                                               start_epoch_ms, 
                                                                                               end_epoch_ms)
        
        # Get data from database!
        cursor = self._cursor()
        cursor.execute(select_cmd)
        all_snapshot_times = cursor.fetchall()
        
        return fetchall_to_1d_list(all_snapshot_times)
    
    # .................................................................................................................
    
    def get_n_snapshot_times(self, start_time, end_time, n = 10):
        
        # Get all snapshot data first
        all_snapshot_times = self.get_all_snapshot_times_by_time_range(start_time, end_time)
        
        # Sub-sample the snapshot entries to get 'n' outputs
        num_snapshots = len(all_snapshot_times)
        final_n = min(num_snapshots, max(2, n))
        subsample_indices = np.int32(np.round(np.linspace(0, num_snapshots - 1, final_n)))
        n_snapshot_epochs = [all_snapshot_times[each_idx] for each_idx in subsample_indices]
        
        return n_snapshot_epochs
    
    # .................................................................................................................
    
    def get_closest_snapshot(self, target_time):
        
        # Convert time input into an epoch_ms_utc value to search database
        target_epoch_ms_utc = _time_to_epoch_ms_utc(target_time)
        
        # Build selection commands
        ceil_select_cmd = """
                          SELECT min(epoch_ms_utc) 
                          FROM {} 
                          WHERE epoch_ms_utc >= {} 
                          LIMIT 1
                          """.format(self._table_name(), target_epoch_ms_utc)
                          
        floor_select_cmd = """
                           SELECT max(epoch_ms_utc) 
                           FROM {} 
                           WHERE epoch_ms_utc <= {} 
                           LIMIT 1
                           """.format(self._table_name(), target_epoch_ms_utc)
        
        # Get data from database!
        cursor = self._cursor()
        
        # Get lower bound snapshot
        cursor.execute(floor_select_cmd)
        floor_snapshot = cursor.fetchone()
        no_floor = (floor_snapshot is None)
        
        # Get upper bound snapshot
        cursor.execute(ceil_select_cmd)
        ceil_snapshot = cursor.fetchone()
        no_ceil = (ceil_snapshot is None)
        
        # Deal with missing return values
        if no_floor and no_ceil:
            raise FileNotFoundError("Couldn't find close snapshots in database! ({})".format(target_time))
        if no_ceil:
            ceil_snapshot = floor_snapshot
        if no_floor:
            floor_snapshot = ceil_snapshot        
        
        return floor_snapshot, ceil_snapshot
    
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
    
    def load_snapshot_metadata(self, target_epoch_ms_utc):
        
        # Build selection commands
        select_cmd = """
                     SELECT *
                     FROM {} 
                     WHERE epoch_ms_utc = {}
                     """.format(self._table_name(), target_epoch_ms_utc)
        
        # Get data from database!
        cursor = self._cursor()
        cursor.execute(select_cmd)
        target_snapshot_entry = cursor.fetchone()
        
        # Convert output into dictionary for easier use
        output_dict = {"name": target_snapshot_entry[0],
                       "count": target_snapshot_entry[1],
                       "frame_index": target_snapshot_entry[2],
                       "datetime_isoformat": target_snapshot_entry[3],
                       "epoch_ms_utc": target_snapshot_entry[4],
                       "snap_width": target_snapshot_entry[5],
                       "snap_height": target_snapshot_entry[6]}
        
        return output_dict
    
    # .................................................................................................................
    
    def load_snapshot_image(self, target_epoch_ms_utc):
        
        # First get snapshot metadata, so we can look up the correct image by name
        snap_md = self.load_snapshot_metadata(target_epoch_ms_utc)
        snap_name = snap_md.get("name")
        snap_frame_index = snap_md.get("frame_index")
        
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
    
    def __init__(self, cameras_folder_path, camera_select, user_select, task_select = None,
                 db_path = ":memory:"):
        
        # Store additional task information
        self.task_select = task_select
        
        # Set up list of known tasks
        task_name_list, _ = build_task_list(cameras_folder_path, camera_select, user_select)
        if task_select is not None:
            task_name_list = [task_select]
        self.task_name_list = task_name_list
        
        # Inherit from parent
        super().__init__(cameras_folder_path, camera_select, user_select, db_path)
    
    # .................................................................................................................
    
    def _table_name(self, task_select = None):
        
        # Try to use selected task (if a single task was selected!) if a task name isn't provided
        if task_select is None:
            if self.task_select is None:
                raise NameError("No task selected when specifying table name! ({})".format(self._class_name))
            task_select = self.task_select
        
        return "[objects-({})]".format(task_select)
    
    # .................................................................................................................
        
    def _initialize_tables(self):
        
        cursor = self._cursor()
        
        # Define table columns
        objs_columns = ["full_id INTEGER PRIMARY KEY",
                        "nice_id INTEGER", 
                        "detection_class TEXT",
                        "start_epoch_ms_utc INTEGER",
                        "end_epoch_ms_utc INTEGER",
                        "lifetime_sec REAL", 
                        "start_frame_index INTEGER",
                        "end_frame_index INTEGER",
                        "num_samples INTEGER",
                        "partition_index INTEGER",
                        "is_final INTEGER",
                        "metadata_json TEXT"]
        objs_column_str = ", ".join(objs_columns)
        
        # Initialize a table for objects for each task
        for each_task in self.task_name_list:
            obj_table_name = self._table_name(each_task)
            objs_cursor_cmd = "CREATE TABLE {}({})".format(obj_table_name, objs_column_str)
            cursor.execute(objs_cursor_cmd)
            
        self.connection.commit()
        
    # .................................................................................................................
    
    def add_entry(self, task_select, full_id, nice_id, detection_class,
                  start_epoch_ms_utc, end_epoch_ms_utc, lifetime_sec,
                  start_frame_index, end_frame_index, num_samples, 
                  partition_index, is_final, metadata_json):
        
        # Bundle data in the correct order for database entry
        new_entry_var_list = ["full_id", "nice_id", "detection_class",
                              "start_epoch_ms_utc", "end_epoch_ms_utc", "lifetime_sec",
                              "start_frame_index", "end_frame_index", "num_samples", 
                              "partition_index", "is_final",
                              "metadata_json"]
        new_entry_value_list = [full_id, nice_id, detection_class,
                                start_epoch_ms_utc, end_epoch_ms_utc, lifetime_sec,
                                start_frame_index, end_frame_index, num_samples, 
                                partition_index, is_final, 
                                metadata_json]
        new_entry_q_list = ["?"] * len(new_entry_var_list)
        
        # Build insert command
        insert_table = self._table_name(task_select)
        insert_vars = ", ".join(new_entry_var_list)
        insert_qs = ",".join(new_entry_q_list)
        insert_cmd = "INSERT INTO {}({}) VALUES({})".format(insert_table, insert_vars, insert_qs)
        
        # Update the database!
        cursor = self._cursor()
        cursor.execute(insert_cmd, new_entry_value_list)
        self.connection.commit()
    
    # .................................................................................................................
    
    def get_object_ids_by_time_range(self, task_select, start_time, end_time):
        
        # Convert time values into epoch_ms values for searching
        start_epoch_ms_utc = _time_to_epoch_ms_utc(start_time)
        end_epoch_ms_utc = _time_to_epoch_ms_utc(end_time)
        
        # Build selection commands
        table_name = self._table_name(task_select)
        select_cmd = """
                     SELECT full_id
                     FROM {}
                     WHERE 
                     start_epoch_ms_utc >= {} 
                     AND 
                     end_epoch_ms_utc <= {}
                     """.format(table_name, start_epoch_ms_utc, end_epoch_ms_utc)
                     
        # Get data from database!
        cursor = self._cursor()
        
        # Get object ids in time range
        cursor.execute(select_cmd)
        object_id_list = cursor.fetchall()
        no_objects = (object_id_list is None)
        if no_objects:
            object_id_list = []
        
        # Convert the list to 1D (get rid of tuple entries per row)
        object_id_list = fetchall_to_1d_list(object_id_list)
                     
        return no_objects, object_id_list
    
    # .................................................................................................................
    
    def get_ids_at_target_time(self, task_select, target_time):
        
        # Convert time value into epoch_ms value to search database
        target_epoch_ms_utc = _time_to_epoch_ms_utc(target_time)
        
        # Build selection commands
        table_name = self._table_name(task_select)
        select_cmd = """
                     SELECT full_id
                     FROM {}
                     WHERE {} 
                     BETWEEN 
                     start_epoch_ms_utc AND end_epoch_ms_utc
                     """.format(table_name, target_epoch_ms_utc)
                     
        # Get data from database!
        cursor = self._cursor()
        
        # Get object ids in time range
        cursor.execute(select_cmd)
        object_id_list = cursor.fetchall()
        no_objects = (object_id_list is None or object_id_list == [])
        if no_objects:
            object_id_list = []
        
        # Convert the list to 1D (get rid of tuple entries per row)
        object_id_list = fetchall_to_1d_list(object_id_list)
        
        return no_objects, object_id_list
    
    # .................................................................................................................
    
    def load_metadata_by_id(self, task_select, object_id):
        
        # Build selection commands
        table_name = self._table_name(task_select)
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
    
    def load_metadata_by_time_range(self, task_select, start_time, end_time):
        
        ''' Acts as a generator! '''
        
        # First get all object IDs for the given time range
        no_objects, object_id_list = self.get_object_ids_by_time_range(task_select, 
                                                                       start_time, 
                                                                       end_time)
        
        # Crash if we don't have any object data
        if no_objects:
            err_msg = "No object IDs in the given time range! ({} to {})"
            err_msg = err_msg.format(start_time, end_time)
            raise FileNotFoundError(err_msg)
        
        # Return all object metadata, using a generator
        for each_obj_id in object_id_list:            
            yield self.load_metadata_by_id(task_select, each_obj_id)
        
        return
    
    # .................................................................................................................
    # .................................................................................................................
    

# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////


class Classification_DB(File_DB):
    
    # .................................................................................................................
    
    def __init__(self, cameras_folder_path, camera_select, user_select, task_select = None,
                 db_path = ":memory:"):
        
        # Store additional task information
        self.task_select = task_select
        
        # Set up list of known tasks
        task_name_list, _ = build_task_list(cameras_folder_path, camera_select, user_select)
        if task_select is not None:
            task_name_list = [task_select]
        self.task_name_list = task_name_list
        
        # Load the class labelling lookup table for graphic settings
        self._class_label_lut, self.label_to_idx_dict = load_label_lut_tuple(cameras_folder_path, camera_select)        
        self.num_classes, self.valid_labels_dict, self.ignoreable_labels_list = self.get_labels()
        
        # Inherit from parent
        super().__init__(cameras_folder_path, camera_select, user_select, db_path)
    
    # .................................................................................................................
    
    def _table_name(self, task_select = None):
        
        # Try to use selected task (if a single task was selected!) if a task name isn't provided
        if task_select is None:
            if self.task_select is None:
                raise NameError("No task selected when specifying table name! ({})".format(self._class_name))
            task_select = self.task_select
        
        return "[classification-({})]".format(task_select)
    
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
        
        # Initialize a table for objects for each task
        for each_task in self.task_name_list:
            obj_table_name = self._table_name(each_task)
            objs_cursor_cmd = "CREATE TABLE {}({})".format(obj_table_name, objs_column_str)
            cursor.execute(objs_cursor_cmd)
            
        self.connection.commit()
    
    # .................................................................................................................
    
    def add_entry(self, task_select, full_id, class_label, score_pct, subclass = "", attributes_json = "{}"):
        
        # Create variable to signify whether the object has been classified or not
        is_classified = int(class_label.lower() != "unclassified")
        if not is_classified:
            score_pct = 0
        
        # Bundle data in the correct order for database entry
        new_entry_var_list = ["full_id", "class_label", "is_classified", "score_pct", "subclass", "attributes_json"]
        new_entry_value_list = [full_id, class_label, is_classified, score_pct, subclass, attributes_json]
        new_entry_q_list = ["?"] * len(new_entry_var_list)
        
        # Build insert command
        insert_table = self._table_name(task_select)
        insert_vars = ", ".join(new_entry_var_list)
        insert_qs = ",".join(new_entry_q_list)
        insert_cmd = "INSERT INTO {}({}) VALUES({})".format(insert_table, insert_vars, insert_qs)
        
        # Update the database!
        cursor = self._cursor()
        cursor.execute(insert_cmd, new_entry_value_list)
        self.connection.commit()
        
    # .................................................................................................................
    
    def update_entry(self, task_select, full_id, new_class_label, new_score_pct, 
                     new_subclass = "", new_attributes_json = "{}"):
        
        # Create variable to signify whether the object has been classified or not
        is_classified = int(new_class_label.lower() != "unclassified")
        if not is_classified:
            new_score_pct = 0
        
        # Bundle data in the correct order for database entry
        update_entry_var_list = ["class_label", "is_classified", "score_pct", "subclass", "attributes_json"]
        update_entry_value_list = [new_class_label, is_classified, new_score_pct, new_subclass, new_attributes_json]
        update_strs_list = ["{}=?".format(each_var) for each_var in update_entry_var_list]
        update_str = ",".join(update_strs_list)
        
        # Build update command
        update_table = self._table_name(task_select)
        update_cmd = "UPDATE {} SET {} WHERE full_id={}".format(update_table, update_str, full_id)
        
        # Update the database!
        cursor = self._cursor()
        cursor.execute(update_cmd, update_entry_value_list)
        self.connection.commit()
        
    # .................................................................................................................
    
    def update_classification_file(self, task_select = None):
        
        # Get the list of tasks to update (or do all tasks if a task isn't specified)
        update_tasks = [task_select] if task_select is not None else self.task_name_list
        
        # Bundle pathing args for convenience
        pathing_args = (self.cameras_folder_path, self.camera_select, self.user_select)
        
        # Loop over all tasks for all objects to update
        for each_task in update_tasks:
            
            # For each object, retrieve the current classification data so we can write it to the local file
            new_classification_dict = {}
            for each_obj_id in self.get_all_object_ids(each_task):
                
                # Get database entries for each object
                class_label, score_pct, subclass, attributes_dict = \
                self.load_classification_data(each_task, each_obj_id)
                
                # Bundle into classification file format
                new_file_entry = new_classification_entry(each_obj_id, 
                                                          class_label, 
                                                          score_pct, 
                                                          subclass, 
                                                          attributes_dict)
                
                # Add new object classification data to the output
                new_classification_dict.update(new_file_entry)
            
            # Update the local file with all collected object data
            update_local_classification_file(*pathing_args, each_task, new_classification_dict)
    
    # .................................................................................................................
    
    def get_class_colors(self, class_label):
        
        # Look up coloring from class label lookup tables
        trail_color_rgb = self._class_label_lut.get(class_label).get("trail_color")
        outline_color_rgb = self._class_label_lut.get(class_label).get("outline_color")
        
        # Convert to bgr for OpenCV
        trail_color_bgr = trail_color_rgb[::-1]
        outline_color_bgr = outline_color_rgb[::-1]
        
        return trail_color_bgr, outline_color_bgr
        
    # .................................................................................................................
    
    def get_all_object_ids(self, task_select):
        
        # Build selection commands
        table_name = self._table_name(task_select)
        select_cmd = """SELECT full_id FROM {}""".format(table_name)
        
        # Get data from database!
        cursor = self._cursor()
        cursor.execute(select_cmd)
        object_id_list = cursor.fetchall()
        
        return fetchall_to_1d_list(object_id_list)
    
    # .................................................................................................................
    
    def load_classification_data(self, task_select, object_id):
        
        # Build selection commands
        table_name = self._table_name(task_select)
        select_cmd = """SELECT * FROM {} WHERE full_id = {}""".format(table_name, object_id)
        
        # Get data from database!
        cursor = self._cursor()
        cursor.execute(select_cmd)
        object_classification_data = cursor.fetchall()
        
        # Unbundle for clarity
        object_full_id, class_label, score_pct, is_classified, subclass, attributes_json = object_classification_data[0]
        
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


class Rule_DB(File_DB):
    
    # .................................................................................................................
    
    def __init__(self, rule_name, cameras_folder_path, camera_select, user_select, task_select,
                 db_path = ":memory:"):
        
        # Store additional task information
        self.rule_name = rule_name
        self.task_select = task_select
        
        # Inherit from parent
        super().__init__(cameras_folder_path, camera_select, user_select, db_path)
    
    # .................................................................................................................
    
    def _table_name(self, table_select = None):        
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



# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

# .................................................................................................................

def _time_to_epoch_ms_utc(time_value):
    
    value_type = type(time_value)
    
    # If an integer is provided, assume it is already an epoch_ms value
    if value_type in [int, np.int64]:
        return time_value
    
    # If a float is provided, assume it is an epoch_ms value, so return integer version
    elif value_type is float:
        return int(round(time_value))
    
    # If a datetime vlaue is provided, use timekeeper library to convert
    elif value_type is dt.datetime:
        return utc_datetime_to_epoch_ms(time_value)
    
    # If a string is provided, assume it is an isoformat datetime string
    elif value_type is str:
        return isoformat_to_epoch_ms(time_value)
    
    # If we get here, we could've parse the time!
    raise TypeError("Unable to parse input time value: {}, type: {}".format(time_value, value_type))

# .....................................................................................................................

def fetchall_to_1d_list(fetchall_result, return_index = 0):
    
    ''' Helper function which flattens a list of tuples, which may be returned from sqlite fetchall commands '''
    
    return [each_entry[return_index] for each_entry in fetchall_result]

# .....................................................................................................................

def user_input_datetime_range(earliest_datetime, latest_datetime, debug_mode = False):
    
    # Error if the start/end dates are not the same (don't have UI to deal with that yet!)
    earliest_date = earliest_datetime.date()
    latest_date = latest_datetime.date()
    not_same_dates = (earliest_date != latest_date)
    if not_same_dates:
        raise NotImplementedError("Start/end snapshot dates are not the same! Can't deal with this yet...")
    
    # Create default strings
    time_format_str = "%H:%M:%S"
    default_start_str = earliest_datetime.strftime("%H:%M:%S")
    default_end_str = latest_datetime.strftime("%H:%M:%S")
    replace_bundle_dict = {"year": earliest_datetime.year, 
                           "month": earliest_datetime.month, 
                           "day": earliest_datetime.day,
                           "tzinfo": earliest_datetime.tzinfo}
    
    # Get user to enter start/end datetimes when configuring the rule
    user_start_str = cli_prompt_with_defaults("Enter start of time range:", default_start_str, debug_mode=debug_mode)
    user_end_str = cli_prompt_with_defaults("  Enter end of time range:", default_end_str, debug_mode=debug_mode)
    
    # Convert user inputs back into datetimes
    start_dt = dt.datetime.strptime(user_start_str, time_format_str).replace(**replace_bundle_dict)
    end_dt = dt.datetime.strptime(user_end_str, time_format_str).replace(**replace_bundle_dict)
    
    # Force earliest/latest boundary timing
    start_dt = max(earliest_datetime, start_dt)
    end_dt = min(latest_datetime, end_dt)
    start_dt_isoformat = isoformat_datetime_string(start_dt)
    end_dt_isoformat = isoformat_datetime_string(end_dt)
    
    return start_dt, end_dt, start_dt_isoformat, end_dt_isoformat

# .....................................................................................................................

def _post_object_metadata(object_metadata_folder_path, task_select, database):
    
    # Start timing
    print("", "Posting object metadata to database ({})".format(task_select), sep = "\n")
    t_start = perf_counter()
    
    # Get all files, read the saved data and post appropriately to the database
    objmd_path_list = get_file_list(object_metadata_folder_path, 
                                    return_full_path = True,
                                    sort_list = False)
    
    # Add each object entry to the database
    for each_path in objmd_path_list:
        
        # Pull data out of the snapshot metadata file
        obj_md = load_json(each_path)
        full_id = obj_md["full_id"]
        nice_id = obj_md["nice_id"]
        detection_class = obj_md["detection_class"]
        
        first_datetime_str = obj_md["timing"]["first_datetime_isoformat"]
        last_datetime_str = obj_md["timing"]["last_datetime_isoformat"]
        start_epoch_ms_utc = utc_datetime_to_epoch_ms(parse_isoformat_string(first_datetime_str))
        end_epoch_ms_utc = utc_datetime_to_epoch_ms(parse_isoformat_string(last_datetime_str))
        lifetime_sec = obj_md["lifetime_sec"]
        
        first_frame_index = obj_md["timing"]["first_frame_index"]
        last_frame_index = obj_md["timing"]["last_frame_index"]
        num_samples = obj_md["num_samples"]
        
        partition_index = obj_md["partition_index"]
        is_final = obj_md["is_final"]
        
        metadata_json = json.dumps(obj_md)

        # 'POST' to the database
        database.add_entry(task_select, 
                           full_id, nice_id, detection_class,
                           start_epoch_ms_utc, end_epoch_ms_utc, lifetime_sec,
                           first_frame_index, last_frame_index, num_samples, 
                           partition_index, is_final, 
                           metadata_json)
    
    # End timing
    t_end = perf_counter()
    print("  Finished, took {:.0f} ms".format(1000 * (t_end - t_start)))

# .....................................................................................................................

def _post_snapshot_metadata(snapshot_metadata_folder_path, database):
    
    # Start timing
    print("", "Posting snapshot metadata to database...", sep = "\n")
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
        epoch_ms_utc = snap_md["epoch_ms_utc"]
        snap_width, snap_height = snap_md["snap_wh"]
        
        # 'POST' to the database
        database.add_entry(name, count, frame_index, datetime_isoformat, epoch_ms_utc, snap_width, snap_height)
    
    # End timing
    t_end = perf_counter()
    print("  Finished, took {:.0f} ms".format(1000 * (t_end - t_start)))

# .....................................................................................................................

def post_snapshot_report_metadata(cameras_folder_path, camera_select, user_select, database):
    
    # Build pathing to snapshot report data
    snapshot_metadata_folder_path = build_snapshot_metadata_report_path(cameras_folder_path, 
                                                                        camera_select, 
                                                                        user_select)
    
    _post_snapshot_metadata(snapshot_metadata_folder_path, database)
    
# .....................................................................................................................

def post_object_report_metadata(cameras_folder_path, camera_select, user_select, task_select, database):
    
    # Build pathing to object report data for the given task
    object_metadata_folder_path = build_object_metadata_report_path(cameras_folder_path, 
                                                                    camera_select, 
                                                                    user_select,
                                                                    task_select)
    
    _post_object_metadata(object_metadata_folder_path, task_select, database)
    
# .....................................................................................................................

def post_snapshot_dataset_metadata(cameras_folder_path, camera_select, dataset_select, database):
    
    # Build pathing to snapshot dataset (classifier) data
    snapshot_metadata_folder_path = build_snapshot_metadata_dataset_path(cameras_folder_path, 
                                                                         camera_select, 
                                                                         dataset_select)
    
    _post_snapshot_metadata(snapshot_metadata_folder_path, database)
    
# .....................................................................................................................

def post_object_dataset_metadata(cameras_folder_path, camera_select, task_select, dataset_select, database):
    
    # Build pathing to object report data for the given task
    object_metadata_folder_path = build_object_metadata_dataset_path(cameras_folder_path, 
                                                                     camera_select,
                                                                     task_select,
                                                                     dataset_select)
    
    _post_object_metadata(object_metadata_folder_path, task_select, database)

# .....................................................................................................................

def post_object_classification_data(cameras_folder_path, camera_select, user_select, task_select, database):    
    
    # Load all the classification labels for the given task
    class_labels_dict = load_local_classification_file(cameras_folder_path, camera_select, user_select, task_select)
    
    # Start timing
    print("", "Posting classification labels to database ({})".format(task_select), sep = "\n")
    t_start = perf_counter()
    
    # Add each object entry to the database
    for each_obj_id, each_classification_dict in class_labels_dict.items():
        
        # Pull out the data needed for the classification database
        class_label = each_classification_dict["class_label"]
        score_pct = each_classification_dict["score_pct"]
        subclass = each_classification_dict["subclass"]
        attributes = each_classification_dict["attributes"]
        
        # Convert attributes dictionary to a json string for the database
        attributes_json = json.dumps(attributes)

        # 'POST' to the database
        database.add_entry(task_select, each_obj_id, class_label, score_pct, subclass, attributes_json)
    
    # End timing
    t_end = perf_counter()
    print("  Finished, took {:.0f} ms".format(1000 * (t_end - t_start)))

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Demo

if __name__ == "__main__":
    pass

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap


