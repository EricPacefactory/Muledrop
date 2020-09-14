#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Aug 21 11:06:04 2020

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

import requests
import asyncio
import ujson

from tqdm import tqdm

import websockets as ws_requests

from local.lib.common.timekeeper_utils import any_time_type_to_epoch_ms

from local.lib.file_access_utils.reporting import build_camera_info_metadata_report_path
from local.lib.file_access_utils.reporting import build_config_info_metadata_report_path
from local.lib.file_access_utils.reporting import build_snapshot_metadata_report_path
from local.lib.file_access_utils.reporting import build_object_metadata_report_path
from local.lib.file_access_utils.reporting import build_station_metadata_report_path
from local.lib.file_access_utils.reporting import build_background_metadata_report_path
from local.lib.file_access_utils.reporting import build_snapshot_image_report_path
from local.lib.file_access_utils.reporting import build_background_image_report_path

from local.eolib.utils.files import create_missing_folder_path


# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes

# .....................................................................................................................

class Server_Access:
    
    # .................................................................................................................
    
    def __init__(self, dbserver_host = None, dbserver_port = None, is_secured = False, request_timeout_sec = 5.0):
        
        # Allocate storage for server settings
        self.protocol = None
        self.host = None
        self.port = None
        self.is_secured = None
        self.server_http_url = None
        self.server_websocket_url = None
        self.set_server_url(dbserver_host, dbserver_port, is_secured)
        
        # Store timeout settings (shared across all requests)
        self.timeout_sec = None
        self.set_request_timeout(request_timeout_sec)
        
    # .................................................................................................................
    
    def _build_http_url(self, raise_error = True):
        
        # Make sure we have all the required components
        missing_components = (None in [self.port, self.host, self.is_secured])
        if missing_components:
            if raise_error:
                raise AttributeError("\n".join(["Can't build http url, missing components:",
                                                "     Host: {}".format(self.host),
                                                "     Port: {}".format(self.port),
                                                "  Secured: {}".format(self.is_secured)]))
            return None
        
        # Set protocol component
        protocol = "https" if self.is_secured else "http"
        
        return "{}://{}:{}".format(protocol, self.host, self.port)
    
    # .................................................................................................................
    
    def _build_websocket_url(self, raise_error = True):
        
        # Make sure we have all the required components
        missing_components = (None in [self.port, self.host, self.is_secured])
        if missing_components:
            if raise_error:
                raise AttributeError("\n".join(["Can't build websocket url, missing components:",
                                                "     Host: {}".format(self.host),
                                                "     Port: {}".format(self.port),
                                                "  Secured: {}".format(self.is_secured)]))
            return None
        
        # Set protocol component
        protocol = "wss" if self.is_secured else "ws"
        
        return "{}://{}:{}".format(protocol, self.host, self.port)
    
    # .................................................................................................................
    
    def _build_http_request_url(self, *route_addons):
        
        '''
        Helper function used to build request urls of the form:
        
        "(http_base_url)/route/add/ons/.../etc"
        '''
        
        # Force all add-ons to be strings
        addon_strs = [str(each_addon) for each_addon in route_addons]
        
        # Remove any leading/trails slashes from add-ons
        clean_addons = [each_addon.strip("/") for each_addon in addon_strs]
        
        # Combine add-ons to server url
        request_url = "/".join([self.server_http_url, *clean_addons])
        
        return request_url
    
    # .................................................................................................................
    
    def _build_websocket_request_url(self, *route_addons):
        
        '''
        Helper function used to build request urls of the form:
        
        "(websocket_base_url)/route/add/ons/.../etc"
        '''
        
        # Force all add-ons to be strings
        addon_strs = [str(each_addon) for each_addon in route_addons]
        
        # Remove any leading/trails slashes from add-ons
        clean_addons = [each_addon.strip("/") for each_addon in addon_strs]
        
        # Combine add-ons to server url
        request_url = "/".join([self.server_websocket_url, *clean_addons])
        
        return request_url
    
    # .................................................................................................................
    
    def set_server_url(self, host = None, port = None, is_secured = False):
        
        # Only update if not 'None'
        if host is not None:
            self.host = host
        if port is not None:
            self.port = int(port)
        if is_secured is not None:
            self.is_secured = is_secured
        
        # Try to build the url if possible
        self.server_http_url = self._build_http_url(raise_error = False)
        self.server_websocket_url = self._build_websocket_url(raise_error = False)
        
        return
    
    # .................................................................................................................
    
    def set_request_timeout(self, timeout_sec):
        self.timeout_sec = timeout_sec
    
    # .................................................................................................................
    
    def check_server_connection(self):        
        
        ''' Helper function which checks that a server is accessible '''
    
        # Build server status check url
        status_check_url = self._build_http_request_url("is-alive")
        
        # Request status check from the server
        server_is_alive = False
        try:
            server_response = requests.get(status_check_url, timeout = 10.0)
            server_is_alive = (server_response.status_code == 200)
            
        except (requests.ConnectionError, requests.exceptions.ReadTimeout):
            server_is_alive = False
        
        return server_is_alive
    
    # .................................................................................................................
    
    def get_is_alive(self, *,
                     use_gzip = False, no_data_response = None, raise_errors = True):
        
        # Build url
        req_url = self._build_http_request_url("is-alive")
        
        return get_json(req_url, use_gzip, self.timeout_sec, no_data_response, raise_errors)
    
    # .................................................................................................................
    
    def get_all_camera_names(self, *,
                             use_gzip = False, no_data_response = None, raise_errors = True):
    
        # Build url
        req_url = self._build_http_request_url("get-all-camera-names")
        
        return get_json(req_url, use_gzip, self.timeout_sec, no_data_response, raise_errors)
    
    # .................................................................................................................
    
    def get_disk_usage(self, server_url, *,
                       use_gzip = False, no_data_response = None, raise_errors = True):
        
        # Build url
        req_url = self._build_http_request_url("get-disk-usage")
        
        return get_json(req_url, use_gzip, self.timeout_sec, no_data_response, raise_errors)
    
    # .................................................................................................................
    # .................................................................................................................


# =====================================================================================================================
# =====================================================================================================================


class Camera_Data_Retrieval:
    
    # .................................................................................................................
    
    def __init__(self, server_access_ref, location_select_folder_path, camera_select):
        
        # Store server access reference
        self.server_access = server_access_ref
        
        # Allocate storage for camera selection
        self.location_select_folder_path = None
        self.camera_select = None
        self.set_location_select_folder_path(location_select_folder_path)
        self.set_camera_select(camera_select)
    
    # .................................................................................................................
    
    def _build_camera_http_request_url(self, *route_addons):
        
        '''
        Helper function used to build camera data request urls of the form:
        
        "/(http_url)/(camera_select)/add/ons/.../etc"
        '''
        
        return self.server_access._build_http_request_url(self.camera_select, *route_addons)
    
    # .................................................................................................................
    
    def _build_camera_websocket_request_url(self, *route_addons):
        
        '''
        Helper function used to build camera data request urls of the form:
        
        "/(websocket_url)/(camera_select)/add/ons/.../etc"
        '''
        
        return self.server_access._build_websocket_request_url(self.camera_select, *route_addons)
    
    # .................................................................................................................
    
    def get_report_args(self):
        return (self.location_select_folder_path, self.camera_select)
    
    # .................................................................................................................
    
    def set_location_select_folder_path(self, location_select_folder_path):
        self.location_select_folder_path = location_select_folder_path
    
    # .................................................................................................................
    
    def set_camera_select(self, camera_select):
        self.camera_select = camera_select
    
    # .................................................................................................................
    # .................................................................................................................


# =====================================================================================================================
# =====================================================================================================================


class Camerainfo(Camera_Data_Retrieval):
    
    # .................................................................................................................
    
    def __init__(self, server_access_ref, camera_select):
        
        # Inherit from parent class
        super().__init__(server_access_ref, camera_select)
    
    # .................................................................................................................
    
    def _build_camerainfo_url(self, *route_addons):
        return self._build_camera_http_request_url("camerainfo", *route_addons)
    
    # .................................................................................................................
    
    def get_oldest_metadata(self, *,
                            use_gzip = False, no_data_response = None, raise_errors = True):
        
        # Build the request url
        req_url = self._build_camerainfo_url("get-oldest-metadata")
        
        return get_json(req_url, use_gzip, self.server_access.timeout_sec, no_data_response, raise_errors)
    
    # .................................................................................................................
    
    def build_metadata_save_path(self, create_folder_if_missing = True):
        
        ''' Helper function which returns the metadata (json) save pathing for camera info'''
        
        report_args = self.get_report_args()
        save_folder_path = build_camera_info_metadata_report_path(*report_args)
        if create_folder_if_missing:
            create_missing_folder_path(save_folder_path)
        
        return save_folder_path
    
    # .................................................................................................................
    
    def get_newest_metadata(self, *,
                            use_gzip = False, no_data_response = None, raise_errors = True):
        
        # Build the request url
        req_url = self._build_camerainfo_url("get-newest-metadata")
        
        return get_json(req_url, use_gzip, self.server_access.timeout_sec, no_data_response, raise_errors)
    
    # .................................................................................................................
    
    def get_active_metadata_by_time_target(self, target_time, *,
                                           use_gzip = False, no_data_response = None, raise_errors = True):
        
        # Convert any input time to an ems value for consistency
        target_ems = convert_to_ems(target_time)
        
        # Build the request url
        req_url = self._build_camerainfo_url("get-active-metadata", "by-time-target", target_ems)
        
        return get_json(req_url, use_gzip, self.server_access.timeout_sec, no_data_response, raise_errors)
    
    # .................................................................................................................
    
    def get_many_metadata_by_time_range(self, start_time, end_time, *,
                                        use_gzip = False, no_data_response = None, raise_errors = True):
        
        # Convert any input time to an ems value for consistency
        start_ems, end_ems = convert_to_ems(start_time, end_time)
        
        # Build the request url
        req_url = self._build_camerainfo_url("get-many-metadata", "by-time-range", start_ems, end_ems)
        
        return get_json(req_url, use_gzip, self.server_access.timeout_sec, no_data_response, raise_errors)
    
    # .................................................................................................................
    
    def get_count_by_time_range(self, start_time, end_time, *,
                                use_gzip = False, no_data_response = None, raise_errors = True):
        
        # Convert any input time to an ems value for consistency
        start_ems, end_ems = convert_to_ems(start_time, end_time)
        
        # Build the request url
        req_url = self._build_camerainfo_url("count", "by-time-range", start_ems, end_ems)
        count_dict = get_json(req_url, use_gzip, self.server_access.timeout_sec, no_data_response, raise_errors)
        
        return count_dict.get("count", 0)
    
    # .................................................................................................................
    # .................................................................................................................


# =====================================================================================================================
# =====================================================================================================================


class Configinfo(Camera_Data_Retrieval):
    
    # .................................................................................................................
    
    def __init__(self, server_access_ref, camera_select):
        
        # Inherit from parent class
        super().__init__(server_access_ref, camera_select)
    
    # .................................................................................................................
    
    def _build_configinfo_url(self, *route_addons):
        return self._build_camera_http_request_url("configinfo", *route_addons)
    
    # .................................................................................................................
    
    def get_oldest_metadata(self, *,
                            use_gzip = False, no_data_response = None, raise_errors = True):
        
        # Build the request url
        req_url = self._build_configinfo_url("get-oldest-metadata")
        
        return get_json(req_url, use_gzip, self.server_access.timeout_sec, no_data_response, raise_errors)
    
    # .................................................................................................................
    
    def build_metadata_save_path(self, create_folder_if_missing = True):
        
        ''' Helper function which returns the metadata (json) save pathing for config info data'''
        
        report_args = self.get_report_args()
        save_folder_path = build_config_info_metadata_report_path(*report_args)
        if create_folder_if_missing:
            create_missing_folder_path(save_folder_path)
        
        return save_folder_path
    
    # .................................................................................................................
    
    def get_newest_metadata(self, *,
                            use_gzip = False, no_data_response = None, raise_errors = True):
        
        # Build the request url
        req_url = self._build_configinfo_url("get-newest-metadata")
        
        return get_json(req_url, use_gzip, self.server_access.timeout_sec, no_data_response, raise_errors)
    
    # .................................................................................................................
    
    def get_active_metadata_by_time_target(self, target_time, *,
                                           use_gzip = False, no_data_response = None, raise_errors = True):
        
        # Convert any input time to an ems value for consistency
        target_ems = convert_to_ems(target_time)
        
        # Build the request url
        req_url = self._build_configinfo_url("get-active-metadata", "by-time-target", target_ems)
        
        return get_json(req_url, use_gzip, self.server_access.timeout_sec, no_data_response, raise_errors)
    
    # .................................................................................................................
    
    def get_many_metadata_by_time_range(self, start_time, end_time, *,
                                        use_gzip = False, no_data_response = None, raise_errors = True):
        
        # Convert any input time to an ems value for consistency
        start_ems, end_ems = convert_to_ems(start_time, end_time)
        
        # Build the request url
        req_url = self._build_configinfo_url("get-many-metadata", "by-time-range", start_ems, end_ems)
        
        return get_json(req_url, use_gzip, self.server_access.timeout_sec, no_data_response, raise_errors)
    
    # .................................................................................................................
    
    def get_count_by_time_range(self, start_time, end_time, *,
                                use_gzip = False, no_data_response = None, raise_errors = True):
        
        # Convert any input time to an ems value for consistency
        start_ems, end_ems = convert_to_ems(start_time, end_time)
        
        # Build the request url
        req_url = self._build_configinfo_url("count", "by-time-range", start_ems, end_ems)
        count_dict = get_json(req_url, use_gzip, self.server_access.timeout_sec, no_data_response, raise_errors)
        
        return count_dict.get("count", 0)
    
    # .................................................................................................................
    # .................................................................................................................


# =====================================================================================================================
# =====================================================================================================================


class Backgrounds(Camera_Data_Retrieval):
    
    # .................................................................................................................
    
    def __init__(self, server_access_ref, camera_select):
        
        # Inherit from parent class
        super().__init__(server_access_ref, camera_select)
    
    # .................................................................................................................
    
    def _build_backgrounds_url(self, *route_addons):
        return self._build_camera_http_request_url("backgrounds", *route_addons)
    
    # .................................................................................................................
    
    def _build_background_websocket_url(self, *route_addons):
        return self._build_camera_websocket_request_url("backgrounds", *route_addons)
    
    # .................................................................................................................
    
    def get_bounding_times(self, *,
                           use_gzip = False, no_data_response = None, raise_errors = True):
        
        # Build the request url
        req_url = self._build_backgrounds_url("get-bounding-times")
        
        return get_json(req_url, use_gzip, self.server_access.timeout_sec, no_data_response, raise_errors)
    
    # .................................................................................................................
    
    def build_metadata_save_path(self, create_folder_if_missing = True):
        
        ''' Helper function which returns the metadata (json) save pathing for backgrounds'''
        
        report_args = self.get_report_args()
        save_folder_path = build_background_metadata_report_path(*report_args)
        if create_folder_if_missing:
            create_missing_folder_path(save_folder_path)
        
        return save_folder_path
    
    # .................................................................................................................
    
    def build_image_save_path(self, create_folder_if_missing = True):
        
        ''' Helper function which returns the image (jpg) save pathing for backgrounds'''
        
        report_args = self.get_report_args()
        save_folder_path = build_background_image_report_path(*report_args)
        if create_folder_if_missing:
            create_missing_folder_path(save_folder_path)
        
        return save_folder_path
    
    # .................................................................................................................
    
    def get_ems_list_by_time_range(self, start_time, end_time, *,
                                   use_gzip = False, no_data_response = None, raise_errors = True):
        
        # Convert any input time to an ems value for consistency
        start_ems, end_ems = convert_to_ems(start_time, end_time)
        
        # Build the request url
        req_url = self._build_backgrounds_url("get-ems-list", "by-time-range", start_ems, end_ems)
        
        return get_json(req_url, use_gzip, self.server_access.timeout_sec, no_data_response, raise_errors)
    
    # .................................................................................................................
    
    def get_newest_metadata(self, *,
                            use_gzip = False, no_data_response = None, raise_errors = True):
        
        # Build the request url
        req_url = self._build_backgrounds_url("get-newest-metadata")
        
        return get_json(req_url, use_gzip, self.server_access.timeout_sec, no_data_response, raise_errors)
    
    # .................................................................................................................
    
    def get_one_metadata_by_ems(self, target_ems, *,
                                use_gzip = False, no_data_response = None, raise_errors = True):
        
        # Build the request url
        req_url = self._build_backgrounds_url("get-one-metadata", "by-ems", target_ems)
        
        return get_json(req_url, use_gzip, self.server_access.timeout_sec, no_data_response, raise_errors)
    
    # .................................................................................................................
    
    def get_active_metadata_by_ems(self, target_ems, *,
                                   use_gzip = False, no_data_response = None, raise_errors = True):
        
        # Build the request url
        req_url = self._build_backgrounds_url("get-active-metadata", "by-ems", target_ems)
        
        return get_json(req_url, use_gzip, self.server_access.timeout_sec, no_data_response, raise_errors)
    
    # .................................................................................................................
    
    def get_many_metadata_by_time_range(self, start_time, end_time, *,
                                        use_gzip = False, no_data_response = None, raise_errors = True):
        
        # Convert any input time to an ems value for consistency
        start_ems, end_ems = convert_to_ems(start_time, end_time)
        
        # Build the request url
        req_url = self._build_backgrounds_url("get-many-metadata", "by-time-range", start_ems, end_ems)
        
        return get_json(req_url, use_gzip, self.server_access.timeout_sec, no_data_response, raise_errors)
    
    # .................................................................................................................
    
    def get_newest_image(self, *,
                         no_data_response = None, raise_errors = True):
        
        # Build the request url
        req_url = self._build_backgrounds_url("get-newest-image")
        
        return get_jpg(req_url, self.server_access.timeout_sec, no_data_response, raise_errors)
    
    # .................................................................................................................
    
    def get_one_image_by_ems(self, target_ems, *,
                             no_data_response = None, raise_errors = True):
        
        # Build the request url
        req_url = self._build_backgrounds_url("get-one-image", "by-ems", target_ems)
        
        return get_jpg(req_url, self.server_access.timeout_sec, no_data_response, raise_errors)
    
    # .................................................................................................................
    
    def get_active_image_by_ems(self, target_ems, *,
                                no_data_response = None, raise_errors = True):
        
        # Build the request url
        req_url = self._build_backgrounds_url("get-active-image", "by-ems", target_ems)
        
        return get_jpg(req_url, self.server_access.timeout_sec, no_data_response, raise_errors)
    
    # .................................................................................................................
    
    def get_one_b64_jpg_by_ems(self, target_ems, *,
                               no_data_response = None, raise_errors = True):
        
        # For clarity
        use_gzip = False
        
        # Build the request url
        req_url = self._build_backgrounds_url("get-one-b64-jpg", "by-ems", target_ems)
        
        return get_str(req_url, use_gzip, self.server_access.timeout_sec, no_data_response, raise_errors)
    
    # .................................................................................................................
    
    def get_count_by_time_range(self, start_time, end_time, *,
                                use_gzip = False, no_data_response = None, raise_errors = True):
        
        # Convert any input time to an ems value for consistency
        start_ems, end_ems = convert_to_ems(start_time, end_time)
        
        # Build the request url
        req_url = self._build_backgrounds_url("count", "by-time-range", start_ems, end_ems)
        count_dict = get_json(req_url, use_gzip, self.server_access.timeout_sec, no_data_response, raise_errors)
        
        return count_dict.get("count", 0)
    
    # .................................................................................................................
    
    def save_stream_many_metadata_by_time_range(self, start_time, end_time, *,
                                                no_data_response = None, raise_errors = True):
        
        # Convert any input time to an ems value for consistency
        start_ems, end_ems = convert_to_ems(start_time, end_time)
        
        # Build the request url
        req_url = self._build_background_websocket_url("stream-many-metadata-and-images",
                                                       "by-time-range",
                                                       start_ems, end_ems)
        
        # Build save pathing
        json_save_folder_path = self.build_metadata_save_path()
        image_save_folder_path = self.build_image_save_path()
        
        # Run (async) streaming function to stream & save metadata + image data
        id_list = asyncio.get_event_loop().run_until_complete(save_stream_json_and_jpgs(req_url,
                                                                                        json_save_folder_path,
                                                                                        image_save_folder_path))
        
        return id_list
    
    # .................................................................................................................
    # .................................................................................................................


# =====================================================================================================================
# =====================================================================================================================


class Snapshots(Camera_Data_Retrieval):
    
    # .................................................................................................................
    
    def __init__(self, server_access_ref, location_select_folder_path, camera_select):
        
        # Inherit from parent class
        super().__init__(server_access_ref, location_select_folder_path, camera_select)
    
    # .................................................................................................................
    
    def _build_snapshots_url(self, *route_addons):
        return self._build_camera_http_request_url("snapshots", *route_addons)
    
    # .................................................................................................................
    
    def _build_snapshots_websocket_url(self, *route_addons):
        return self._build_camera_websocket_request_url("snapshots", *route_addons)
    
    # .................................................................................................................
    
    def build_metadata_save_path(self, create_folder_if_missing = True):
        
        ''' Helper function which returns the metadata (json) save pathing for snapshots'''
        
        report_args = self.get_report_args()
        save_folder_path = build_snapshot_metadata_report_path(*report_args)
        if create_folder_if_missing:
            create_missing_folder_path(save_folder_path)
        
        return save_folder_path
    
    # .................................................................................................................
    
    def build_image_save_path(self, create_folder_if_missing = True):
        
        ''' Helper function which returns the image (jpg) save pathing for snapshots'''
        
        report_args = self.get_report_args()
        save_folder_path = build_snapshot_image_report_path(*report_args)
        if create_folder_if_missing:
            create_missing_folder_path(save_folder_path)
        
        return save_folder_path
    
    # .................................................................................................................
    
    def get_bounding_times(self, *,
                           use_gzip = False, no_data_response = None, raise_errors = True):
        
        # Build the request url
        req_url = self._build_snapshots_url("get-bounding-times")
        
        return get_json(req_url, use_gzip, self.server_access.timeout_sec, no_data_response, raise_errors)
    
    # .................................................................................................................
    
    def get_ems_list_by_time_range(self, start_time, end_time, *,
                                   use_gzip = False, no_data_response = None, raise_errors = True):
        
        # Convert any input time to an ems value for consistency
        start_ems, end_ems = convert_to_ems(start_time, end_time)
        
        # Build the request url
        req_url = self._build_snapshots_url("get-ems-list", "by-time-range", start_ems, end_ems)
        
        return get_json(req_url, use_gzip, self.server_access.timeout_sec, no_data_response, raise_errors)
    
    # .................................................................................................................
    
    def get_closest_ems_by_time_target(self, target_time, *,
                                       use_gzip = False, no_data_response = None, raise_errors = True):
        
        # Convert any input time to an ems value for consistency
        target_ems = convert_to_ems(target_time)
        
        # Build the request url
        req_url = self._build_snapshots_url("get-closest-ems", "by-time-target", target_ems)
        
        return get_json(req_url, use_gzip, self.server_access.timeout_sec, no_data_response, raise_errors)
    
    # .................................................................................................................
    
    def get_newest_metadata(self, *,
                            use_gzip = False, no_data_response = None, raise_errors = True):
        
        # Build the request url
        req_url = self._build_snapshots_url("get-newest-metadata")
        
        return get_json(req_url, use_gzip, self.server_access.timeout_sec, no_data_response, raise_errors)
    
    # .................................................................................................................
    
    def get_one_metadata_by_ems(self, target_ems, *,
                                use_gzip = False, no_data_response = None, raise_errors = True):
        
        # Build the request url
        req_url = self._build_snapshots_url("get-one-metadata", "by-ems", target_ems)
        
        return get_json(req_url, use_gzip, self.server_access.timeout_sec, no_data_response, raise_errors)
    
    # .................................................................................................................
    
    def get_closest_metadata_by_time_target(self, target_time, *,
                                            use_gzip = False, no_data_response = None, raise_errors = True):
        
        # Convert any input time to an ems value for consistency
        target_ems = convert_to_ems(target_time)
        
        # Build the request url
        req_url = self._build_snapshots_url("get-closest-metadata", "by-time-target", target_ems)
        
        return get_json(req_url, use_gzip, self.server_access.timeout_sec, no_data_response, raise_errors)
    
    # .................................................................................................................
    
    def get_many_metadata_by_time_range(self, start_time, end_time, *,
                                        use_gzip = False, no_data_response = None, raise_errors = True):
        
        # Convert any input time to an ems value for consistency
        start_ems, end_ems = convert_to_ems(start_time, end_time)
        
        # Build the request url
        req_url = self._build_snapshots_url("get-many-metadata", "by-time-range", start_ems, end_ems)
        
        return get_json(req_url, use_gzip, self.server_access.timeout_sec, no_data_response, raise_errors)
    
    # .................................................................................................................
    
    def get_many_metadata_by_time_range_skip_n(self, start_time, end_time, skip_n, *,
                                        use_gzip = False, no_data_response = None, raise_errors = True):
        
        # Convert any input time to an ems value for consistency & make sure skip value is an integer
        start_ems, end_ems = convert_to_ems(start_time, end_time)
        skip_n_int = int(skip_n)
        
        # Build the request url
        req_url = self._build_snapshots_url("get-many-metadata", "by-time-range", "skip-n",
                                            start_ems, end_ems, skip_n_int)
        
        return get_json(req_url, use_gzip, self.server_access.timeout_sec, no_data_response, raise_errors)
    
    # .................................................................................................................
    
    def get_many_metadata_by_time_range_n_samples(self, start_time, end_time, n_samples, *,
                                                  use_gzip = False, no_data_response = None, raise_errors = True):
        
        # Convert any input time to an ems value for consistency & make sure we use an integer number of samples
        start_ems, end_ems = convert_to_ems(start_time, end_time)
        n_samples_int = int(n_samples)
        
        # Build the request url
        req_url = self._build_snapshots_url("get-many-metadata", "by-time-range", "n-samples",
                                            start_ems, end_ems, n_samples_int)
        
        return get_json(req_url, use_gzip, self.server_access.timeout_sec, no_data_response, raise_errors)
    
    # .................................................................................................................
    
    def get_newest_image(self, *,
                         no_data_response = None, raise_errors = True):
        
        # Build the request url
        req_url = self._build_snapshots_url("get-newest-image")
        
        return get_jpg(req_url, self.server_access.timeout_sec, no_data_response, raise_errors)
    
    # .................................................................................................................
    
    def get_one_image_by_ems(self, target_ems, *,
                             no_data_response = None, raise_errors = True):
        
        # Build the request url
        req_url = self._build_snapshots_url("get-one-image", "by-ems", target_ems)
        
        return get_jpg(req_url, self.server_access.timeout_sec, no_data_response, raise_errors)
    
    # .................................................................................................................
    
    def get_one_b64_jpg_by_ems(self, target_ems, *,
                               no_data_response = None, raise_errors = True):
        
        # For clarity
        use_gzip = False
        
        # Build the request url
        req_url = self._build_snapshots_url("get-one-b64-jpg", "by-ems", target_ems)
        
        return get_str(req_url, use_gzip, self.server_access.timeout_sec, no_data_response, raise_errors)
    
    # .................................................................................................................
    
    def get_count_by_time_range(self, start_time, end_time, *,
                                use_gzip = False, no_data_response = None, raise_errors = True):
        
        # Convert any input time to an ems value for consistency
        start_ems, end_ems = convert_to_ems(start_time, end_time)
        
        # Build the request url
        req_url = self._build_snapshots_url("count", "by-time-range", start_ems, end_ems)
        count_dict = get_json(req_url, use_gzip, self.server_access.timeout_sec, no_data_response, raise_errors)
        
        return count_dict.get("count", 0)
    
    # .................................................................................................................
    
    def save_stream_many_metadata_by_time_range_n_samples(self, start_time, end_time, n_samples = 0, *,
                                                          no_data_response = None, raise_errors = True):
        
        # Convert any input time to an ems value for consistency
        start_ems, end_ems = convert_to_ems(start_time, end_time)
        
        # Build the request url
        req_url = self._build_snapshots_websocket_url("stream-many-metadata-and-images",
                                                      "by-time-range",
                                                      "n-samples",
                                                      start_ems, end_ems, n_samples)
        
        # Build save pathing
        json_save_folder_path = self.build_metadata_save_path()
        image_save_folder_path = self.build_image_save_path()
        
        # Run (async) streaming function to stream & save metadata + image data
        id_list = asyncio.get_event_loop().run_until_complete(save_stream_json_and_jpgs(req_url,
                                                                                        json_save_folder_path,
                                                                                        image_save_folder_path))
        
        return id_list
    
    # .................................................................................................................
    # .................................................................................................................


# =====================================================================================================================
# =====================================================================================================================


class Objects(Camera_Data_Retrieval):
    
    # .................................................................................................................
    
    def __init__(self, server_access_ref, camera_select):
        
        # Inherit from parent class
        super().__init__(server_access_ref, camera_select)
    
    # .................................................................................................................
    
    def _build_objects_url(self, *route_addons):
        return self._build_camera_http_request_url("objects", *route_addons)
    
    # .................................................................................................................
    
    def _build_objects_websocket_url(self, *route_addons):
        return self._build_camera_websocket_request_url("objects", *route_addons)
    
    # .................................................................................................................
    
    def build_metadata_save_path(self, create_folder_if_missing = True):
        
        ''' Helper function which returns the metadata (json) save pathing for objects'''
        
        report_args = self.get_report_args()
        save_folder_path = build_object_metadata_report_path(*report_args)
        if create_folder_if_missing:
            create_missing_folder_path(save_folder_path)
        
        return save_folder_path
    
    # .................................................................................................................
    
    def get_newest_metadata(self, *,
                            use_gzip = False, no_data_response = None, raise_errors = True):
        
        # Build the request url
        req_url = self._build_objects_url("get-newest-metadata")
        
        return get_json(req_url, use_gzip, self.server_access.timeout_sec, no_data_response, raise_errors)
    
    # .................................................................................................................
    
    def get_all_ids_list(self, *,
                         use_gzip = False, no_data_response = None, raise_errors = True):
        
        # Build the request url
        req_url = self._build_objects_url("get-all-ids-list")
        
        return get_json(req_url, use_gzip, self.server_access.timeout_sec, no_data_response, raise_errors)
    
    # .................................................................................................................
    
    def get_ids_list_by_time_target(self, target_time, *,
                                    use_gzip = False, no_data_response = None, raise_errors = True):
        
        # Convert any input time to an ems value for consistency
        target_ems = convert_to_ems(target_time)
        
        # Build the request url
        req_url = self._build_objects_url("get-ids-list", "by-time-target", target_ems)
        
        return get_json(req_url, use_gzip, self.server_access.timeout_sec, no_data_response, raise_errors)
    
    # .................................................................................................................
    
    def get_ids_list_by_time_range(self, start_time, end_time, *,
                                   use_gzip = False, no_data_response = None, raise_errors = True):
        
        # Convert any input time to an ems value for consistency
        start_ems, end_ems = convert_to_ems(start_time, end_time)
        
        # Build the request url
        req_url = self._build_objects_url("get-ids-list", "by-time-range", start_ems, end_ems)
        
        return get_json(req_url, use_gzip, self.server_access.timeout_sec, no_data_response, raise_errors)
    
    # .................................................................................................................
    
    def get_one_metadata_by_id(self, target_id, *,
                               use_gzip = False, no_data_response = None, raise_errors = True):
        
        # Build the request url
        req_url = self._build_objects_url("get-one-metadata", "by-id", target_id)
        
        return get_json(req_url, use_gzip, self.server_access.timeout_sec, no_data_response, raise_errors)
    
    # .................................................................................................................
    
    def get_many_metadata_by_time_target(self, target_time, *,
                                         use_gzip = False, no_data_response = None, raise_errors = True):
        
        # Convert any input time to an ems value for consistency
        target_ems = convert_to_ems(target_time)
        
        # Build the request url
        req_url = self._build_objects_url("get-many-metadata", "by-time-target", target_ems)
        
        return get_json(req_url, use_gzip, self.server_access.timeout_sec, no_data_response, raise_errors)
    
    # .................................................................................................................
    
    def get_many_metadata_by_time_range(self, start_time, end_time, *,
                                        use_gzip = False, no_data_response = None, raise_errors = True):
        
        # Convert any input time to an ems value for consistency
        start_ems, end_ems = convert_to_ems(start_time, end_time)
        
        # Build the request url
        req_url = self._build_objects_url("get-many-metadata", "by-time-range", start_ems, end_ems)
        
        return get_json(req_url, use_gzip, self.server_access.timeout_sec, no_data_response, raise_errors)
    
    # .................................................................................................................
    
    def get_count_by_time_target(self, target_time, *,
                                 use_gzip = False, no_data_response = None, raise_errors = True):
        
        # Convert any input time to an ems value for consistency
        target_ems = convert_to_ems(target_time)
        
        # Build the request url
        req_url = self._build_objects_url("count", "by-time-target", target_ems)
        
        return get_json(req_url, use_gzip, self.server_access.timeout_sec, no_data_response, raise_errors)
    
    # .................................................................................................................
    
    def get_count_by_time_range(self, start_time, end_time, *,
                                use_gzip = False, no_data_response = None, raise_errors = True):
        
        # Convert any input time to an ems value for consistency
        start_ems, end_ems = convert_to_ems(start_time, end_time)
        
        # Build the request url
        req_url = self._build_objects_url("count", "by-time-range", start_ems, end_ems)
        count_dict = get_json(req_url, use_gzip, self.server_access.timeout_sec, no_data_response, raise_errors)
        
        return count_dict.get("count", 0)
    
    # .................................................................................................................
    
    def set_indexing(self, *,
                     use_gzip = False, no_data_response = None, raise_errors = True):
        
        # Build the request url
        req_url = self._build_objects_url("set-indexing")
        count_dict = get_json(req_url, use_gzip, self.server_access.timeout_sec, no_data_response, raise_errors)
        
        return count_dict.get("count", 0)
    
    # .................................................................................................................
    
    def save_stream_many_metadata_by_time_range(self, start_time, end_time, *,
                                                no_data_response = None, raise_errors = True):
        
        # Convert any input time to an ems value for consistency
        start_ems, end_ems = convert_to_ems(start_time, end_time)
        
        # Build the request url
        req_url = self._build_objects_websocket_url("stream-many-metadata-gz", "by-time-range", start_ems, end_ems)
        
        # Build path to save metadata
        jsongz_save_folder_path = self.build_metadata_save_path()
        
        # Run (async) streaming function to get metadata
        metadata_list = asyncio.get_event_loop().run_until_complete(save_stream_jsongz(req_url,
                                                                                       jsongz_save_folder_path))
        
        return metadata_list
    
    # .................................................................................................................
    # .................................................................................................................


# =====================================================================================================================
# =====================================================================================================================


class Stations(Camera_Data_Retrieval):
    
    # .................................................................................................................
    
    def __init__(self, server_access_ref, camera_select):
        
        # Inherit from parent class
        super().__init__(server_access_ref, camera_select)
    
    # .................................................................................................................
    
    def _build_stations_url(self, *route_addons):
        return self._build_camera_http_request_url("stations", *route_addons)
    
    # .................................................................................................................
    
    def _build_stations_websocket_url(self, *route_addons):
        return self._build_camera_websocket_request_url("stations", *route_addons)
    
    # .................................................................................................................
    
    def build_metadata_save_path(self, create_folder_if_missing = True):
        
        ''' Helper function which returns the metadata (json) save pathing for station data'''
        
        report_args = self.get_report_args()
        save_folder_path = build_station_metadata_report_path(*report_args)
        if create_folder_if_missing:
            create_missing_folder_path(save_folder_path)
        
        return save_folder_path
    
    # .................................................................................................................
    
    def get_oldest_metadata(self, *,
                            use_gzip = False, no_data_response = None, raise_errors = True):
        
        # Build the request url
        req_url = self._build_stations_url("get-oldest-metadata")
        
        return get_json(req_url, use_gzip, self.server_access.timeout_sec, no_data_response, raise_errors)
    
    # .................................................................................................................
    
    def get_newest_metadata(self, *,
                            use_gzip = False, no_data_response = None, raise_errors = True):
        
        # Build the request url
        req_url = self._build_stations_url("get-newest-metadata")
        
        return get_json(req_url, use_gzip, self.server_access.timeout_sec, no_data_response, raise_errors)
    
    # .................................................................................................................
    
    def get_all_ids_list(self, *,
                         use_gzip = False, no_data_response = None, raise_errors = True):
        
        # Build the request url
        req_url = self._build_stations_url("get-all-ids-list")
        
        return get_json(req_url, use_gzip, self.server_access.timeout_sec, no_data_response, raise_errors)
    
    # .................................................................................................................
    
    def get_ids_list_by_time_range(self, start_time, end_time, *,
                                  use_gzip = False, no_data_response = None, raise_errors = True):
        
        # Convert any input time to an ems value for consistency
        start_ems, end_ems = convert_to_ems(start_time, end_time)
        
        # Build the request url
        req_url = self._build_stations_url("get-ids-list", "by-time-range", start_ems, end_ems)
        
        return get_json(req_url, use_gzip, self.server_access.timeout_sec, no_data_response, raise_errors)
    
    # .................................................................................................................
    
    def get_one_metadata_by_id(self, target_id, *,
                               use_gzip = False, no_data_response = None, raise_errors = True):
        
        # Build the request url
        req_url = self._build_stations_url("get-one-metadata", "by-id", target_id)
        
        return get_json(req_url, use_gzip, self.server_access.timeout_sec, no_data_response, raise_errors)
    
    # .................................................................................................................
    
    def get_many_metadata_by_time_range(self, start_time, end_time, *,
                                        use_gzip = False, no_data_response = None, raise_errors = True):
        
        # Convert any input time to an ems value for consistency
        start_ems, end_ems = convert_to_ems(start_time, end_time)
        
        # Build the request url
        req_url = self._build_stations_url("get-many-metadata", "by-time-range", start_ems, end_ems)
        
        return get_json(req_url, use_gzip, self.server_access.timeout_sec, no_data_response, raise_errors)
    
    # .................................................................................................................
    
    def get_count_by_time_range(self, start_time, end_time, *,
                                use_gzip = False, no_data_response = None, raise_errors = True):
        
        # Convert any input time to an ems value for consistency
        start_ems, end_ems = convert_to_ems(start_time, end_time)
        
        # Build the request url
        req_url = self._build_stations_url("count", "by-time-range", start_ems, end_ems)
        count_dict = get_json(req_url, use_gzip, self.server_access.timeout_sec, no_data_response, raise_errors)
        
        return count_dict.get("count", 0)
    
    # .................................................................................................................
    
    def set_indexing(self, *,
                     use_gzip = False, no_data_response = None, raise_errors = True):
        
        # Build the request url
        req_url = self._build_stations_url("set-indexing")
        
        return get_json(req_url, use_gzip, self.server_access.timeout_sec, no_data_response, raise_errors)
    
    # .................................................................................................................
    
    def save_stream_many_metadata_by_time_range(self, start_time, end_time, *,
                                                no_data_response = None, raise_errors = True):
        
        # Convert any input time to an ems value for consistency
        start_ems, end_ems = convert_to_ems(start_time, end_time)
        
        # Build the request url
        req_url = self._build_stations_websocket_url("stream-many-metadata-gz", "by-time-range", start_ems, end_ems)
        
        # Build path to save metadata
        jsongz_save_folder_path = self.build_metadata_save_path()
        
        # Run (async) streaming function to get metadata
        metadata_list = asyncio.get_event_loop().run_until_complete(save_stream_jsongz(req_url,
                                                                                       jsongz_save_folder_path))
        
        return metadata_list
    
    # .................................................................................................................
    # .................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% GET Request helpers

# .....................................................................................................................

def get_json(request_url, use_gzip = False, timeout_sec = 5.0, no_data_response = None, raise_errors = True):
    
    # Build header as needed
    headers = {}
    if not use_gzip:
        headers.update({"Accept-Encoding": "identity"})
    
    # Make the actual get-request
    get_reponse = requests.get(request_url, headers = headers, timeout = timeout_sec)
    
    # Only try to raise request errors if needed
    if raise_errors:
        get_reponse.raise_for_status()
    
    # Convert json response data to python data type
    try:
        return_data = get_reponse.json()
    except ValueError:
        return_data = no_data_response
    
    return return_data

# .....................................................................................................................

def get_jpg(request_url, timeout_sec = 5.0, no_data_response = None, raise_errors = True):

    # Build request header
    headers = {"Accept-Encoding": "identity"}
    
    # Request data from the server
    get_reponse = requests.get(request_url, headers = headers, timeout = timeout_sec)
    
    # Only try to raise request errors if needed
    if raise_errors:
        get_reponse.raise_for_status()
    
    # Pull image data out of response
    return_data = get_reponse.content
    
    return return_data

# .....................................................................................................................

def get_str(request_url, use_gzip = False, timeout_sec = 5.0, no_data_response = None, raise_errors = True):
        
    # Build header as needed
    headers = {}
    if not use_gzip:
        headers.update({"Accept-Encoding": "identity"})
    
    # Make the actual get-request
    get_reponse = requests.get(request_url, headers = headers, timeout = timeout_sec)
    
    # Only try to raise request errors if needed
    if raise_errors:
        get_reponse.raise_for_status()
    
    # Return the raw content
    return_data = get_reponse.content
    
    return return_data

# .....................................................................................................................
    
def convert_to_ems(*time_values):
    
    '''
    Helper function whichs takes 1 or more 'time' values (in various formats)
    and converts them all to epoch ms values
    Converted values are returned in the order they were passed in
    '''
    
    # Convert as many inputs as needed to ems values
    output_ems_list = [any_time_type_to_epoch_ms(each_value) for each_value in time_values]
    
    # In case of a single output value, return a single (i.e. non-iterable) value
    only_one_output = (len(output_ems_list) == 1)
    if only_one_output:
        return output_ems_list[0]
    
    return output_ems_list

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Websocket request helpers

# .....................................................................................................................

async def save_stream_json(request_url, save_folder_path):
    
    '''
    Function which uses a websocket connection to stream json data
    Assumes data is sent with starting list, to indicate streamed data
    Also assumed data is sent entirely in json format
    '''
    
    async with ws_requests.connect(request_url) as ws_connection:
        
        try:
            # First capture the list of IDs which will be streamed
            ids_list_str = await ws_connection.recv()
            ids_list = ujson.loads(ids_list_str)
            
            # Then wait for each entry to be streamed
            for each_id in tqdm(ids_list):
                metadata_str = await ws_connection.recv()
                save_path = os.path.join(save_folder_path, "{}.json".format(each_id))
                with open(save_path, "w") as out_file:
                    out_file.write(metadata_str)
            
        except ws_requests.exceptions.ConnectionClosedOK:
            pass
    
    return each_id

# .....................................................................................................................

async def save_stream_jsongz(request_url, save_folder_path):
    
    '''
    Function which uses a websocket connection to stream gzipped json data, in binary format
    Assumes data is sent with a starting (json) list which indicates each id of the streamed data
    This function directly saves each entry in to a target folder
    '''
    
    async with ws_requests.connect(request_url) as ws_connection:
        
        try:
            # First capture the list of IDs which will be streamed
            ids_list_str = await ws_connection.recv()
            ids_list = ujson.loads(ids_list_str)
            
            # Then receive and save each of the streamed entries
            for each_id in tqdm(ids_list):
                encoded_jsongz_bytes = await ws_connection.recv()
                save_path = os.path.join(save_folder_path, "{}.json.gz".format(each_id))
                with open(save_path, "wb") as out_file:
                    out_file.write(encoded_jsongz_bytes)
            
        except ws_requests.exceptions.ConnectionClosedOK:
            pass
    
    return ids_list

# .....................................................................................................................

async def save_stream_json_and_jpgs(request_url, json_save_folder_path, image_save_folder_path):
    
    '''
    Function which uses a websocket connection to stream jpg data, in binary format
    Assumes data is sent with a starting (json) list which indicates each id of the streamed jpgs 
    This function directly saves each image in to a target folder
    '''
    
    async with ws_requests.connect(request_url) as ws_connection:
        
        try:
            # First capture the list of IDs which will be streamed
            ids_list_str = await ws_connection.recv()
            ids_list = ujson.loads(ids_list_str)
            
            # Then save each of the json-jpg pairs
            for each_id in tqdm(ids_list):
                
                # json (metadata) data is sent first
                metadata_str = await ws_connection.recv()
                json_save_path = os.path.join(json_save_folder_path, "{}.json".format(each_id))
                with open(json_save_path, "w") as json_out_file:
                    json_out_file.write(metadata_str)
                
                # jps (image) data is sent after
                image_bytes = await ws_connection.recv()
                save_path = os.path.join(image_save_folder_path, "{}.jpg".format(each_id))
                with open(save_path, "wb") as jpg_out_file:
                    jpg_out_file.write(image_bytes)
            
        except ws_requests.exceptions.ConnectionClosedOK:
            pass
    
    return ids_list

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Demo

if __name__ == "__main__":
    pass


# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap


