#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Feb  4 11:06:22 2020

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

import pymongo
import requests
import ujson
import datetime as dt

from itertools import islice
from time import perf_counter

from local.lib.file_access_utils.reporting import build_camera_info_metadata_report_path
from local.lib.file_access_utils.reporting import build_snapshot_metadata_report_path
from local.lib.file_access_utils.reporting import build_object_metadata_report_path
from local.lib.file_access_utils.reporting import build_background_metadata_report_path
from local.lib.file_access_utils.reporting import build_snapshot_image_report_path
from local.lib.file_access_utils.reporting import build_background_image_report_path

'''
from local.lib.file_access_utils.classifier import build_classifier_adb_metadata_report_path
from local.lib.file_access_utils.summary import build_summary_adb_metadata_report_path
from local.lib.file_access_utils.rules import build_rule_adb_info_report_path
from local.lib.file_access_utils.rules import build_rule_adb_metadata_report_path
'''

from local.lib.file_access_utils.read_write import load_jgz

from local.eolib.utils.files import get_file_list_by_age


# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes

class Mongo_DB:
    
    # .................................................................................................................
    
    def __init__(self, db_host = "localhost", db_port = "27017", timezone_aware = False, 
                 load_existing_data_on_startup = True):
        
        # Store database access info
        self.host = db_host
        self.port = db_port
        self.db_url = "mongodb://{}:{}/".format(db_host, db_port)
        
        # Create main connection to the database
        self.client = pymongo.MongoClient(self.db_url, tz_aware = timezone_aware, serverSelectionTimeoutMS = 4000)
        
        # Allocate storage for database entries, per-camera
        self.cam_dbs = {}
        
        # Allocate storage for collections, indexed by camera names
        self.snap_collections = {}
        self.obj_collections = {}
        self.bg_collections = {}
        self.rule_collections = {}
        self.summ_collections = {}
        self.class_collections = {}
        
        # Load up references to any existing data in the database
        if load_existing_data_on_startup:
            # ...
            pass
    
    # .................................................................................................................
    
    def __repr__(self):
        
        ''' For convenience, just list out all the databases & corresponding collections '''
        
        # Get all databases
        database_name_list = self.client.list_database_names()
        
        # Build the repr string for all collections for each database name
        repr_strs = []
        for each_database_name in database_name_list:
            
            # For convenience
            db_ref = self.client[each_database_name]
            collection_name_list = db_ref.list_collection_names()
            
            # Hard-code a special response if there are no collections in the database
            if not collection_name_list:
                repr_strs += ["  --> database is empty!"]
                continue
            
            # Add the name of each collection, along with the 'estimated document count' under each database name
            repr_strs += ["", "{} collections:".format(each_database_name)]
            for each_col_name in collection_name_list:
                each_doc_count = db_ref[each_col_name].estimated_document_count()
                repr_strs += ["  {} ({} documents)".format(each_col_name, each_doc_count)]
            
        return "\n".join(repr_strs)
    
    # .................................................................................................................
    
    def print_existing_dbs(self):
        print(self.client.list_database_names())
        
    # .................................................................................................................
    
    def print_existing_collections(self, database_name = None):
        
        # Build a list of database names to check (or use just the one provided)
        database_name_list = [database_name]
        if database_name is None:
            database_name_list = self.client.list_database_names()
        
        # Print out the listing of all collections for each database name
        for each_database_name in database_name_list:
            collection_name_list = self.client[each_database_name].list_collection_names()
            collection_name_list = collection_name_list if collection_name_list else ["--> database is empty!"]
            print("",
                  "{} collections:".format(each_database_name),
                  *["  {}".format(each_col_name) for each_col_name in collection_name_list],
                  sep = "\n")
        
        return
    
    # .................................................................................................................
    
    def reset_databases(self):
        
        # Define databases that we should NOT delete (i.e. system entries)
        keep_dbs_set = {"admin", "local", "config"}
        
        # Get list of existing databases and delete everything except system dbs
        existing_dbs_list = self.client.list_database_names()
        for each_db_name in existing_dbs_list:
            if each_db_name in keep_dbs_set:
                continue
            self.remove_database(each_db_name)
        
        return
    
    # .................................................................................................................
    
    def remove_database(self, database_name):
        self.client.drop_database(database_name)
    
    # .................................................................................................................
    
    # .................................................................................................................
    # .................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

# .....................................................................................................................

def build_metadata_post_url(server_url, camera_select, collection_name):
    return "{}/{}/bdb/metadata/{}".format(server_url, camera_select, collection_name)

# .....................................................................................................................

def build_image_post_url(server_url, camera_select, collection_name, image_epoch_ms_str):
    return "/".join([server_url, camera_select, "bdb", "image", collection_name, image_epoch_ms_str])

# .....................................................................................................................

def post_many_metadata_to_server(server_url, camera_select, collection_name, metadata_folder_path, 
                                 minimum_age_sec = 5.0):
    
    '''
    Helper function which bundles all available metadata into a single (big!) json entry for the database
    '''
    
    # First get all the metadata file paths from the target folder path
    sorted_timestamps_list, sorted_paths_list = get_file_list_by_age(metadata_folder_path, 
                                                                     newest_first = False, 
                                                                     show_hidden_files = False, 
                                                                     create_missing_folder = False,
                                                                     return_full_path = True)
    
    # Bail on this if there is no report data, since we'll have nothing to bundle!
    num_files = len(sorted_paths_list)
    no_report_data = (num_files == 0)
    if no_report_data:
        return None
    
    # Figure out which files are 'old enough' to be safe for reading/deleting (i.e. not being actively written)
    current_timestamp = dt.datetime.now().timestamp()
    oldest_allowed_timestamp = (current_timestamp - minimum_age_sec)
    for each_reversed_idx, each_timestamp in enumerate(reversed(sorted_timestamps_list)):
        if each_timestamp < oldest_allowed_timestamp:
            break
    last_valid_entry_index = (num_files - each_reversed_idx)
    
    # Now build up all data into one list for one big insert!
    load_path_list = islice(sorted_paths_list, last_valid_entry_index)
    data_insert_list = [load_jgz(each_metadata_path) for each_metadata_path in load_path_list]
    
    # For clarity
    post_kwargs = {"headers": {"Content-Type": "application/json"},
                   "auth": ("", ""),
                   "verify": False,
                   "timeout": 10.0}
    
    # Send it all to the server
    post_url = build_metadata_post_url(server_url, camera_select, collection_name)
    post_response = requests.post(post_url, data = ujson.dumps(data_insert_list), **post_kwargs)
    
    return post_response

# .....................................................................................................................

def post_many_images_to_server(server_url, camera_select, collection_name, image_folder_path, minimum_age_sec = 5.0):
    
    ''' Helper function for posting all the (new enough) images in a given folder to the server '''
    
    # First get all the image file paths the target folder path
    sorted_timestamps_list, sorted_paths_list = get_file_list_by_age(image_folder_path, 
                                                                     newest_first = False,
                                                                     show_hidden_files = False,
                                                                     create_missing_folder = False,
                                                                     return_full_path = True,
                                                                     allowable_exts_list = [".jpg"])
    
    # Bail on this if there is no image data, since we'll have nothing to bundle!
    num_files = len(sorted_paths_list)
    no_report_data = (num_files == 0)
    if no_report_data:
        return None
    
    # Figure out which images are 'old enough' to be safe for reading/deleting (i.e. not being actively written)
    current_timestamp = dt.datetime.now().timestamp()
    oldest_allowed_timestamp = (current_timestamp - minimum_age_sec)
    for each_reversed_idx, each_timestamp in enumerate(reversed(sorted_timestamps_list)):
        if each_timestamp < oldest_allowed_timestamp:
            break
    last_valid_entry_index = (num_files - each_reversed_idx)
    
    # For clarity
    post_kwargs = {"headers": {"Content-Type": "image/jpeg"},
                   "auth": ("", ""),
                   "verify": False,
                   "timeout": 10.0}
    
    # Only post the newest images
    load_path_list = islice(sorted_paths_list, last_valid_entry_index)
    for each_image_path in load_path_list:
        
        # Figure out the image post url
        image_filename = os.path.basename(each_image_path)
        image_epoch_ms_str, _ = os.path.splitext(image_filename)
        
        # Build the posting url and send the image
        image_post_url = build_image_post_url(server_url, camera_select, collection_name, image_epoch_ms_str)
        with open(each_image_path, "rb") as image_file:
            post_response = requests.post(image_post_url, data = image_file, **post_kwargs)
    
    return post_response

# .....................................................................................................................

def post_data_to_server(server_url, cameras_folder_path, camera_select, post_metadata = True, post_images = True):
    
    # Start timing
    t1 = perf_counter()
    
    # Bundle pathing args for convenience
    hard_coded_user_select = "live"
    camera_pathing_args = (cameras_folder_path, camera_select, hard_coded_user_select)
    
    # Build pathing to all report data that needs to get to the database
    caminfo_metadata_path = build_camera_info_metadata_report_path(*camera_pathing_args)
    bg_metadata_path = build_background_metadata_report_path(*camera_pathing_args)
    snap_metadata_path = build_snapshot_metadata_report_path(*camera_pathing_args)
    obj_metadata_path = build_object_metadata_report_path(*camera_pathing_args)
    
    # Post report metadata
    if post_metadata:
        post_many_metadata_to_server(server_url, camera_select, "camerainfo", caminfo_metadata_path)
        post_many_metadata_to_server(server_url, camera_select, "backgrounds", bg_metadata_path)
        post_many_metadata_to_server(server_url, camera_select, "snapshots", snap_metadata_path)
        post_many_metadata_to_server(server_url, camera_select, "objects", obj_metadata_path)
    
    # Finish metadata timing
    t2 = perf_counter()
    
    # Build pathing to all image data that needs to be sent to the database
    bg_image_path = build_background_image_report_path(*camera_pathing_args)
    snap_image_path = build_snapshot_image_report_path(*camera_pathing_args)
    
    # *** Important:
    # *** Images should be posted AFTER metadata
    # *** to ensure available metadata is always 'behind' available image data on the database
    # *** this avoids the situation where metadata is available that points to a non-existent image
    # Post image data
    if post_images:
        post_many_images_to_server(server_url, camera_select, "backgrounds", bg_image_path)
        post_many_images_to_server(server_url, camera_select, "snapshots", snap_image_path)
    
    # Finish image timing
    t3 = perf_counter()
    
    # Calculate output timing results
    metadata_time_taken_ms = 1000 * (t2 - t1)
    image_time_taken_ms = 1000 * (t3 - t2)
    
    return metadata_time_taken_ms, image_time_taken_ms

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap

tdb = Mongo_DB()

# For convenience
cameras_folder_path = "/home/wrk/Desktop/PythonData/safety-cv-2/cameras"
camera_select = "Plastcoat_Test"
user_select = "live"
server_url = "http://127.0.0.1:8000"


