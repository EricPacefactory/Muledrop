#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Mar  7 14:46:04 2020

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

import zipfile
import shutil
import subprocess
import signal
import threading
import base64

from time import sleep
from random import random as unit_random
from tempfile import TemporaryDirectory

from cv2 import VideoCapture, imencode, resize, CAP_PROP_FPS, CAP_PROP_FOURCC

from waitress import serve as wsgi_serve

from local.lib.common.timekeeper_utils import get_human_readable_timestamp, timestamped_log
from local.lib.common.environment import get_env_location_select
from local.lib.common.environment import get_ctrlserver_protocol, get_ctrlserver_host, get_ctrlserver_port

from local.lib.ui_utils.cli_selections import Resource_Selector
from local.lib.ui_utils.script_arguments import script_arg_builder

from local.lib.file_access_utils.shared import build_camera_path, build_logging_folder_path, url_safe_name
from local.lib.file_access_utils.reporting import build_base_report_path
from local.lib.file_access_utils.logging import build_stdout_log_file_path, build_stderr_log_file_path
from local.lib.file_access_utils.state_files import load_state_file, delete_state_file

from local.lib.file_access_utils.control_server import Autolaunch_Settings, get_existing_camera_names_list

from flask import Flask, jsonify, redirect, render_template
from flask import request as flask_request
from flask_cors import CORS

from local.eolib.utils.quitters import ide_catcher
from local.eolib.utils.files import create_missing_folder_path, create_missing_folders_from_file
from local.eolib.utils.network import build_rtsp_string, check_valid_ip, check_connection
from local.eolib.utils.network import scan_for_open_port, get_own_ip


# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes

class RTSP_Processes:
    
    # .................................................................................................................
    
    def __init__(self, project_root_path, location_select_folder_path, location_select):
        
        # Store inputs
        self.project_root_path = project_root_path
        self.location_select_folder_path = location_select_folder_path
        self.location_select = location_select
        
        # Set up threading lock, which prevents access errors from occuring due to background autolauncher
        self._thread_lock = threading.Lock()
        self._thread_shutdown_event = threading.Event()
        
        # Allocate storage for holding references to running camera processes
        self._proc_dict = {}
        
        # Clear out any existing camera state files
        self._clear_camera_state_files_on_startup()
        
        # Load existing autolaunch settings to start
        self._autolaunch_settings = Autolaunch_Settings(location_select_folder_path)
        self._autolaunch_on_startup()
        
        # Start background autolauncher
        self._thread_ref = self.create_autolauncher_thread()
    
    # .................................................................................................................
    
    def _clear_camera_state_files_on_startup(self):
        
        '''
        Function intended to be used to clear out camera state files
        which may be left over from previous (unclean) shutdowns
        '''
        
        all_cameras_list = get_existing_camera_names_list(self.location_select_folder_path)
        for each_camera in all_cameras_list:
            delete_state_file(self.location_select_folder_path, each_camera)
        
        return
    
    # .................................................................................................................
    
    def _autolaunch_on_startup(self):
        
        ''' Function which handles autolaunching cameras on startup, if they have autolaunch enabled '''
        
        # Clear out any missing cameras from the autolaunch settings
        self._autolaunch_settings.prune()
        
        # Get a list of all available cameras and decide if we need to launch them
        all_cameras_list = get_existing_camera_names_list(self.location_select_folder_path)
        for each_camera in all_cameras_list:
            need_to_autolaunch = self._autolaunch_settings.get_autolaunch(each_camera)
            if need_to_autolaunch:
                print("Launching: {}".format(each_camera))
                self.start_camera(each_camera, post_launch_delay_sec = 0)
        
        return
    
    # .................................................................................................................
    
    def _build_log_file_pathing(self, camera_select):
        
        ''' Function which builds paths to camera-specific log files (which capture stdout & stderr streams) '''
        
        # Build pathing to store stdout/stderr logs
        stdout_log_file_path = build_stdout_log_file_path(self.location_select_folder_path, camera_select)
        stderr_log_file_path = build_stderr_log_file_path(self.location_select_folder_path, camera_select)
        
        # Make sure the log folders exist so we can save the log files!
        create_missing_folders_from_file(stdout_log_file_path)
        create_missing_folders_from_file(stderr_log_file_path)
        
        return stdout_log_file_path, stderr_log_file_path
    
    # .................................................................................................................
    
    def _build_rtsp_launch_args(self, camera_select):
        
        ''' Function which builds a subprocess.run(...) string with arguments, for launching rtsp data collection '''
        
        # Get the python interpreter used to launch this server, which we'll use to run the scripts
        python_interpretter = sys.executable
        
        # Build script arguments
        location_arg = ["-l", self.location_select]
        camera_arg = ["-c", camera_select]
        
        # Build pathing to the launch script
        launch_script_name = "run_rtsp_collect.py"
        launch_script_path = os.path.join(self.project_root_path, launch_script_name)
        launch_args = [python_interpretter, "-u", launch_script_path] + camera_arg + location_arg
        
        return launch_args
    
    # .................................................................................................................
    
    def _start_camera_no_lock(self, camera_select, post_launch_delay_sec = 2.5):
        
        # Make sure the target camera isn't already running
        self._stop_camera_no_lock(camera_select)
        
        # Set up launch command & arguments
        launch_args = self._build_rtsp_launch_args(camera_select)
        
        # Set up log file pathing
        stdout_file_path, stderr_file_path = self._build_log_file_pathing(camera_select)
        
        # Launch script as a sub-process (with logging)
        with open(stdout_file_path, "w") as stdout_file:
            with open(stderr_file_path, "w") as stderr_file:
                
                # Launch (non-blocking) call to open a collection script
                new_process_ref = subprocess.Popen(launch_args,
                                                   stdin = None,
                                                   stdout = stdout_file,
                                                   stderr = stderr_file)
                
                # Store reference to the process, in case we want to check on it later
                self._proc_dict[camera_select] = new_process_ref
        
        # If needed, add a delay
        if post_launch_delay_sec > 0:
            sleep(post_launch_delay_sec)
        
        return
    
    # .................................................................................................................
    
    def _stop_camera_no_lock(self, camera_select, wait_for_camera_to_stop = True):
        
        # Don't do anything if the camera isn't already listed
        if camera_select not in self._proc_dict:
            return
        
        # Remove the camera entry from the process dictionary & try to stop it
        proc_ref = self._proc_dict.pop(camera_select)
        try:
            proc_ref.terminate()
            if wait_for_camera_to_stop:
                proc_ref.wait(timeout = 20)
            
        except subprocess.TimeoutExpired:
            print("",
                  "Error stopping camera: {}".format(camera_select),
                  "Will attempt forced shutdown...",
                  "",
                  "This may leave an orphaned posting process!",
                  sep = "\n")
            proc_ref.kill()
        
        return proc_ref
    
    # .................................................................................................................
    
    def _check_camera_is_running_no_lock(self, camera_select):
        
        # Initialize outputs
        camera_is_running = False
        
        # Check if the camera is in the process dictionary, and if so, check that it's running
        camera_in_process_dict = (camera_select in self._proc_dict)
        if camera_in_process_dict:
            return_code = self._proc_dict[camera_select].poll()
            camera_is_running = (return_code is None)
        
        return camera_is_running
    
    # .................................................................................................................
    
    def _clean_processes_no_lock(self):
        
        # Check on all known processes and tag the ones that have stopped for clean up
        cameras_to_delete_list = []
        cameras_to_check_list = list(self._proc_dict.keys())
        for each_camera_name in cameras_to_check_list:
            camera_is_running = self._check_camera_is_running_no_lock(each_camera_name)
            if not camera_is_running:
                cameras_to_delete_list.append(each_camera_name)
        
        # Loop over all stopped cameras for clean-up
        for each_camera_name in cameras_to_delete_list:
            self._stop_camera_no_lock(each_camera_name)
        
        return
    
    # .................................................................................................................
    
    def _set_camera_autolaunch_no_lock(self, camera_select, enable_autolaunch):
        
        # Initialize default output
        launching_camera = False
        
        # Check if the new setting is different from the old one
        old_setting = self._autolaunch_settings.get_autolaunch(camera_select)
        setting_changed = (old_setting != enable_autolaunch)
        if setting_changed:
            self._autolaunch_settings.set_autolaunch(camera_select, enable_autolaunch)
        
        # If we're enabling autolaunch and the camera isn't already running, then we should start it
        if enable_autolaunch and not self._check_camera_is_running_no_lock(camera_select):
            self._start_camera_no_lock(camera_select)
            launching_camera = True
        
        return launching_camera
    
    # .................................................................................................................
    
    def _get_camera_autolaunch_no_lock(self, camera_select):
        return self._autolaunch_settings.get_autolaunch(camera_select)
    
    # .................................................................................................................
    
    def get_running_camera_names(self):
        
        ''' Function which lists the names of all known cameras based on the internal process dictionary '''
        
        # Grab list of process keys, with a lock in case the autolaunch modifies anything!
        camera_names_list = []
        with self._thread_lock:
            camera_names_list = list(self._proc_dict.keys())
        
        return camera_names_list
    
    # .................................................................................................................
    
    def start_camera(self, camera_select, post_launch_delay_sec = 2.5):
        
        return_value = None
        with self._thread_lock:
            return_value = self._start_camera_no_lock(camera_select, post_launch_delay_sec)
            
        return return_value
    
    # .................................................................................................................
    
    def stop_camera(self, camera_select):      
        
        return_value = None
        with self._thread_lock:
            return_value = self._stop_camera_no_lock(camera_select)
        
        return return_value
    
    # .................................................................................................................
    
    def stop_all_cameras(self, wait_after_shutdown_sec = 8):
        
        # Go through all known cameras and shut them down (with a lock, so autolauncher can't interfere)
        with self._thread_lock:
            cameras_to_stop_list = list(self._proc_dict.keys())
            for each_camera_name in cameras_to_stop_list:
                self._stop_camera_no_lock(each_camera_name, wait_for_camera_to_stop = False)
        
        # Optional delay to allow all cameras to finish shutting down properly before we move on
        if wait_after_shutdown_sec > 0:
            sleep(wait_after_shutdown_sec)
        
        return
    
    # .................................................................................................................
    
    def shutdown(self):
        
        ''' Helper function which just stops autolauncher + stops all cameras '''
        
        self.kill_autolaucher_thread()
        self.stop_all_cameras()
    
    # .................................................................................................................
    
    def set_camera_autolaunch(self, camera_select, enable_autolaunch):
        
        ''' Function which enables/disables autolaunch for a given camera '''
        
        launching_camera = False
        with self._thread_lock:
            launching_camera = self._set_camera_autolaunch_no_lock(camera_select, enable_autolaunch)
        
        return launching_camera
    
    # .................................................................................................................
    
    def get_camera_autolaunch(self, camera_select):
        
        ''' Function which checks if a given camera has autolaunch enabled or not '''
        
        return_value = None
        with self._thread_lock:
            return_value = self._autolaunch_settings.get_autolaunch(camera_select)
        
        return return_value
    
    # .................................................................................................................
    
    def check_camera_is_running(self, camera_select):
        
        camera_is_running = False
        with self._thread_lock:
            camera_is_running = self._check_camera_is_running_no_lock(camera_select)
        
        return camera_is_running
    
    # .................................................................................................................
    
    def clean_processes(self):
        
        ''' Helper function which is used to clean up global record of running processes that may have stopped '''
        
        return_value = None
        with self._thread_lock:
            return_value = self._clean_processes_no_lock()
        
        return return_value
    
    # .................................................................................................................
    
    def create_autolauncher_thread(self, start_thread_on_launch = True):
        
        ''' Function which creates (and optionally starts) a separate thread  '''
        
        # For clarity
        thread_name = "autolaunch_watchdog"
        auto_kill_when_main_thread_closes = True
        
        # Create a separate thread for handling autolaunching over time
        thread_ref = threading.Thread(name = thread_name,
                                      target = self._autolaunch_watchdog,
                                      daemon = auto_kill_when_main_thread_closes)
        
        # Start the thread
        if start_thread_on_launch:
            thread_ref.start()
        
        return thread_ref
    
    # .................................................................................................................
    
    def kill_autolaucher_thread(self):
        
        ''' Function used to shutdown the autolaunch watchdog '''
        
        with self._thread_lock:
            self._thread_shutdown_event.set()
        
        return
    
    # .................................................................................................................
    
    def _autolaunch_watchdog(self):
        
        ''' Function which handle background autolaunch checks & actual autolaunching '''
        
        # Hard-coded watchdog timing
        watchdog_period_sec = 60.0
        period_random_sec = 15.0
        
        # I'm gonna live forever
        while True:
            
            # Generate slightly randomized wait time until next autolaunch check
            wait_time_sec = watchdog_period_sec + (period_random_sec * unit_random())
            shutdown_watchdog = self._thread_shutdown_event.wait(wait_time_sec)
            if shutdown_watchdog:
                print("",
                      "Autolaunch watchdog received shutdown command!",
                      "Closing...", sep = "\n")
                break
            
            # Get all available cameras
            existing_camera_names_list = get_existing_camera_names_list(self.location_select_folder_path)
            
            with self._thread_lock:
                
                # Check all cameras to see if they need to be autolaunched
                #print("DEBUG: watchdog check")
                for each_camera in existing_camera_names_list:
                    
                    # If the camera doesn't need autolaunch, skip it
                    camera_needs_autolaunch = self._get_camera_autolaunch_no_lock(each_camera)
                    if not camera_needs_autolaunch:
                        #print("DEBUG: watchdog not launching {}, not enabled".format(each_camera))
                        continue
                    
                    # If the camera is already running, skip it
                    is_running = self._check_camera_is_running_no_lock(each_camera)
                    if is_running:
                        #print("DEBUG: watchdog not launching {}, already running".format(each_camera))
                        continue
                    
                    # If we get here, the camera needs autolaunch and isn't running, so launch it!
                    #print("DEBUG: watchdog launching: {}".format(each_camera))
                    self._start_camera_no_lock(each_camera, post_launch_delay_sec = 5)
            
            pass
        
        return
    
    # .................................................................................................................
    # .................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Define control functions

# .....................................................................................................................

def parse_control_args(debug_print = False):
    
    # Set defaults
    default_protocol = get_ctrlserver_protocol()
    default_host = get_ctrlserver_host()
    default_port = get_ctrlserver_port()
    default_location = get_env_location_select()
    
    # Set arg help text
    protocol_help_text = "Specify the protocol of the control server\n(Default: {})".format(default_protocol)
    host_help_text = "Specify the host of the control server\n(Default: {})".format(default_host)
    port_help_text = "Specify the port of the control server\n(Default: {})".format(default_port)
    
    # Set script arguments for running files
    args_list = [{"location": {"default": default_location}},
                 "debug",
                 {"protocol": {"default": default_protocol, "help_text": protocol_help_text}},
                 {"host": {"default": default_host, "help_text": host_help_text}},
                 {"port": {"default": default_port, "help_text": port_help_text}}]
    
    # Provide some extra information when accessing help text
    script_description = "Launch a server for handling camera control"
    
    # Build & evaluate script arguments!
    ap_result = script_arg_builder(args_list,
                                   description = script_description,
                                   parse_on_call = True,
                                   debug_print = debug_print)
    
    return ap_result

# .....................................................................................................................

def register_waitress_shutdown_command():
    
    ''' Awkward hack to get waitress server to close on SIGTERM signals '''
    
    def convert_sigterm_to_keyboard_interrupt(signal_number, stack_frame):
        
        # Some feedback about catching kill signal
        print("", "", "*" * 48, "Kill signal received! ({})".format(signal_number), "*" * 48, "", sep = "\n")
        
        # Try to 'gracefully' close all open processes
        RTSP_PROC.shutdown()
        
        # Raise a keyboard interrupt, which waitress will respond to! (unlike SIGTERM)
        raise KeyboardInterrupt
    
    # Replaces SIGTERM signals with a Keyboard interrupt, which the server will handle properly
    signal.signal(signal.SIGTERM, convert_sigterm_to_keyboard_interrupt)
    
    return

# .....................................................................................................................

def force_server_shutdown():
    
    ''' Function used to intentionally stop the server! Useful for restarting when used with docker containers '''
    
    # Try to 'gracefully' close the server
    os.kill(os.getpid(), signal.SIGTERM)
    
    return

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Define camera status functions

# .....................................................................................................................

def create_new_camera_status(is_online, in_standby, autolaunch_enabled, state_description, timestamp_str):
    
    ''' Helper function for updating camera status (data is sent to web UI, so needs consistent formatting!) '''
    
    status_dict = {"is_online": is_online,
                   "in_standby": in_standby,
                   "autolaunch_enabled": autolaunch_enabled,
                   "description": state_description,
                   "timestamp_str": timestamp_str}
    
    return status_dict

# .....................................................................................................................

def create_new_camera_status_from_state_dict(camera_state_dict, autolaunch_enabled):
    
    ''' Helper function which fills in the camera status info using a camera state dictionary '''
    
    # Return an offline status if there is no state data
    no_state_data = (camera_state_dict == {}) or (camera_state_dict is None)
    if no_state_data:
        return _create_offline_status(autolaunch_enabled)
    
    # Try to grab the appropriate info for the web UI to present
    is_online = True
    in_standby = camera_state_dict.get("in_standby", False)
    state_description = camera_state_dict.get("state_description", "Offline")
    timestamp_str = camera_state_dict.get("timestamp_str", "unknown")
    
    return create_new_camera_status(is_online, in_standby, autolaunch_enabled, state_description, timestamp_str)

# .....................................................................................................................

def _create_offline_status(autolaunch_enabled):
    
    ''' Helper function which creates an 'offline' status entry for a camera '''
    
    # For clarity
    is_online = False
    in_standby = False
    state_description = "Reconnecting" if autolaunch_enabled else "Offline"
    timestamp_str = get_human_readable_timestamp()
    
    return create_new_camera_status(is_online, in_standby, autolaunch_enabled, state_description, timestamp_str)

# .....................................................................................................................

def unzip_cameras_file(file_path, unzip_folder_name = "unzipped"):
    
    # Determine pathing to unzip into
    dir_path = os.path.dirname(file_path)
    unzip_path = os.path.join(dir_path, unzip_folder_name)
    
    # Unzip the provided files
    with zipfile.ZipFile(file_path,"r") as zip_ref:
        zip_ref.extractall(unzip_path)
    
    # Figure out which cameras are present in data
    unzipped_camera_names_list = os.listdir(unzip_path)
    
    # Bail early if there aren't any files after unzipping... is this even possible?
    no_files_after_unzip = (len(unzipped_camera_names_list) == 0)
    if no_files_after_unzip:
        return unzip_path
    
    # Clean up camera names (remove spaces) and throw away report & logs from uploaded camera files
    for each_camera_name in unzipped_camera_names_list:
        
        # Make sure camera names don't have spaces
        clean_name = url_safe_name(each_camera_name)
        if each_camera_name is not clean_name:
            orig_path = os.path.join(unzip_path, each_camera_name)
            clean_path = os.path.join(unzip_path, clean_name)
            os.rename(orig_path, clean_path)
        
        # Remove data that shouldn't be replacing existing files
        remove_logs_and_report_data(unzip_path, clean_name)
    
    return unzip_path

# .....................................................................................................................

def remove_logs_and_report_data(LOCATION_SELECT_FOLDER_PATH, camera_select):
    
    ''' Remove run-time recording folders. Intended for cleaning up data uploaded to the server '''
    
    # Remove logs folder, if it exists
    camera_logs_path = build_logging_folder_path(LOCATION_SELECT_FOLDER_PATH, camera_select)
    if os.path.exists(camera_logs_path):
        shutil.rmtree(camera_logs_path)
        
    # Remove report folder, if it exists
    camera_report_path = build_base_report_path(LOCATION_SELECT_FOLDER_PATH, camera_select)
    if os.path.exists(camera_report_path):
        shutil.rmtree(camera_report_path)
    
    return

# .....................................................................................................................

def remove_configuration_data(LOCATION_SELECT_FOLDER_PATH, camera_select):
    
    ''' 
    Remove major configuration data. Intended for setting up new camera configs.
    In most cases, this will end up removing the 'resources' folder
    '''
    
    # Get the camera folder & pathing to folders we want to keep
    selected_camera_folder_path = build_camera_path(LOCATION_SELECT_FOLDER_PATH, camera_select)
    camera_logs_path = build_logging_folder_path(LOCATION_SELECT_FOLDER_PATH, camera_select)
    camera_report_path = build_base_report_path(LOCATION_SELECT_FOLDER_PATH, camera_select)
    paths_to_keep = {camera_logs_path, camera_report_path}
    
    # Now get a list of all files/folders in the selected camera folder and remove everything except logs & report
    camera_folder_contents = os.listdir(selected_camera_folder_path)
    for each_item_name in camera_folder_contents:
        
        # Get the pathing to each item, and skip over the paths (folders) we want to keep
        item_path = os.path.join(selected_camera_folder_path, each_item_name)
        if item_path in paths_to_keep:
            continue
        
        # If we get here, we're deleting things, which needs to be handled differently for files/folders
        if os.path.isdir(item_path):
            shutil.rmtree(item_path)
        elif os.path.isfile(item_path):
            os.remove(item_path)
    
    return

# .....................................................................................................................
    
def copy_uploaded_config_data(unzip_folder_path, camera_name):
    
    # Build path to save real camera data
    real_camera_path = build_camera_path(LOCATION_SELECT_FOLDER_PATH, camera_name)
    
    # Get a record of all files being copied from the unzipped path
    updated_file_paths_list = []
    unzipped_camera_folder = os.path.join(unzip_folder_path, camera_name)
    for each_parent_dir, each_subdir_list, each_file_list in os.walk(unzipped_camera_folder):
        
        # Create missing parent directories
        relative_parent_path = os.path.relpath(each_parent_dir, unzipped_camera_folder)
        absolute_parent_path = os.path.join(real_camera_path, relative_parent_path)
        create_missing_folder_path(absolute_parent_path)
        
        # Copy every file over from the unzipped data, and record the file pathing
        for each_file in each_file_list:
            
            # Record all of the file paths for feedback/output
            new_file_path = os.path.join(relative_parent_path, each_file)
            updated_file_paths_list.append(new_file_path)
            
            # Perform file copy!
            copy_from_path = os.path.join(each_parent_dir, each_file)
            copy_to_path = os.path.join(real_camera_path, new_file_path)
            shutil.copy2(copy_from_path, copy_to_path, follow_symlinks = False)
    
    return updated_file_paths_list

# .....................................................................................................................

def update_camera_configs(unzip_folder_path):
    
    # Figure out which cameras are present in data
    unzipped_names_list = os.listdir(unzip_folder_path)
    
    # Compare unzipped camera names to existing cameras. We'll only update existing camera files!
    existing_names_list = get_existing_camera_names_list(LOCATION_SELECT_FOLDER_PATH)
    valid_camera_names_list = [each_name for each_name in unzipped_names_list if each_name in existing_names_list]
    
    # Update all the valid cameras and store the files that were changed
    files_changes_dict = {}
    for each_camera_name in valid_camera_names_list:
        updated_file_paths_list = copy_uploaded_config_data(unzip_folder_path, each_camera_name)
        files_changes_dict[each_camera_name] = updated_file_paths_list
    
    return files_changes_dict

# .....................................................................................................................

def new_camera_configs(unzip_folder_path):
    
    # Figure out which cameras are present in data & which cameras already exist
    unzipped_names_list = os.listdir(unzip_folder_path)
    existing_names_list = get_existing_camera_names_list(LOCATION_SELECT_FOLDER_PATH)
    
    # Copy over all unzipped data, and clean out data for existing cameras
    files_changes_dict = {}
    for each_camera_name in unzipped_names_list:
        
        # Remove config data for existing cameras (but leave logs & report data)
        already_exists = (each_camera_name in existing_names_list)
        if already_exists:
            remove_configuration_data(LOCATION_SELECT_FOLDER_PATH, each_camera_name)
        
        # Copy of unzipped data
        updated_file_paths_list = copy_uploaded_config_data(unzip_folder_path, each_camera_name)
        files_changes_dict[each_camera_name] = updated_file_paths_list
    
    return files_changes_dict

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Parse input args

ap_result = parse_control_args()


# ---------------------------------------------------------------------------------------------------------------------
#%% Set up globals

# Get location selection through script arguments, in case it's being overriden
arg_location_select = ap_result.get("location", "localhost")

# Create selector so we can access existing report data
SELECTOR = Resource_Selector(load_selection_history = False, save_selection_history = False)
PROJECT_ROOT_PATH = SELECTOR.get_project_root_pathing()
LOCATION_SELECT, LOCATION_SELECT_FOLDER_PATH = SELECTOR.location(arg_location_select)

# Set up rtsp process manager for handling running cameras
RTSP_PROC = RTSP_Processes(PROJECT_ROOT_PATH, LOCATION_SELECT_FOLDER_PATH, LOCATION_SELECT)


# ---------------------------------------------------------------------------------------------------------------------
#%% Create routes

# Create wsgi app so we can start adding routes
ctrlserver_resources_folder_path = os.path.join("local", "control_server")
static_folder_path = os.path.join(ctrlserver_resources_folder_path, "static")
template_folder_path = os.path.join(ctrlserver_resources_folder_path, "templates")
wsgi_app = Flask(__name__,
                 static_url_path = '',
                 static_folder = static_folder_path,
                 template_folder = template_folder_path)
CORS(wsgi_app)

# Some feedback, mostly for docker logs
start_msg = timestamped_log("Started control server! ({})".format(LOCATION_SELECT))
print("", start_msg, sep = "\n", flush = True)

# .....................................................................................................................

@wsgi_app.route("/")
def home_route():
    return wsgi_app.send_static_file("home/home.html")

# .....................................................................................................................

@wsgi_app.route("/new")
def replace_route():
    return wsgi_app.send_static_file("new/new.html")

# .....................................................................................................................

@wsgi_app.route("/update")
def update_route():
    return wsgi_app.send_static_file("update/update.html")

# .....................................................................................................................

@wsgi_app.route("/status")
def status_route():
    return wsgi_app.send_static_file("status/status.html")

# .....................................................................................................................

@wsgi_app.route("/status/get-cameras-status")
def status_get_cameras_status_route():
    
    # Run process clean up, in case any cameras crashed unexpectedly
    RTSP_PROC.clean_processes()
    
    # Get pathing to cameras and a list of available cameras
    camera_name_list = get_existing_camera_names_list(LOCATION_SELECT_FOLDER_PATH)
    
    # Loop over all cameras and look for active state files to see if they're online
    camera_status_dict = {}
    for each_camera_name in camera_name_list:
        
        # Check each cameras state file data (if available)
        is_running = RTSP_PROC.check_camera_is_running(each_camera_name)
        if is_running:
            _, state_dict = load_state_file(LOCATION_SELECT_FOLDER_PATH, each_camera_name)
        else:
            state_dict = {}
        
        # Create some json-friendly state info for the web UI, for each camera
        autolaunch_enabled = RTSP_PROC.get_camera_autolaunch(each_camera_name)
        new_status = create_new_camera_status_from_state_dict(state_dict, autolaunch_enabled)
        camera_status_dict[each_camera_name] = new_status
    
    return jsonify(camera_status_dict)

# .....................................................................................................................

@wsgi_app.route("/control/cameras/start/<string:camera_select>")
def control_cameras_restart_route(camera_select):
    
    RTSP_PROC.start_camera(camera_select, post_launch_delay_sec = 3.0)
    
    return redirect("/status")

# .....................................................................................................................

@wsgi_app.route("/control/cameras/stop/<string:camera_select>")
def control_cameras_stop_route(camera_select):
    
    RTSP_PROC.stop_camera(camera_select)
    
    return redirect("/status")

# .....................................................................................................................

@wsgi_app.route("/control/cameras/autolaunch/<string:camera_select>/<string:enable_autolaunch>")
def control_cameras_autolaunch_route(camera_select, enable_autolaunch):
    
    # Handle enable autolaunch as a boolean
    enable_autolaunch_bool = (enable_autolaunch.lower() in {"true", "1", "on"})
    
    # Set the autolaunch status and wait for a downed camera to launch before redirect, if needed
    camera_launching = RTSP_PROC.set_camera_autolaunch(camera_select, enable_autolaunch_bool)
    if camera_launching:
        sleep(3.0)
    
    return redirect("/status")

# .....................................................................................................................

@wsgi_app.route("/control/system/shutdown")
def control_system_shutdown():
    
    '''
    Route which shuts down the server!
    Note that with docker container 'always restart' enabled, the server should immediately re-launch,
    and any changes to underlying files/scripts will take effect on the restarted system
    (i.e. this shutdown route can be used for updating the server/system code!)
    '''
    
    # Try to stop all the cameras before shutting down
    RTSP_PROC.shutdown()
    force_server_shutdown()
    
    # Shouldn't get here? Page that forced shutdown should be responsible for refresh to catch server restarting...
    return redirect("/server-shutdown")

# .....................................................................................................................

@wsgi_app.route("/control/system/load-settings")
def control_system_load_settings():
    
    # Should look to load existing control server settings file
    # - need to provide settings json data as response
    # - intended to be used to access current settings info from web page
    
    return "not implemented"

# .....................................................................................................................

@wsgi_app.route("/control/system/save-settings", methods = ["POST"])
def control_system_save_settings():
    
    # Should attempt to save settings given in post data
    # - need to handle errors/missing data or badly formatted data? (or have web ui handle this?)
    # - intended for use being accessed from web page
    
    return "not implemented"

# .....................................................................................................................

@wsgi_app.route("/new/upload", methods = ["POST"])
def upload_new_file_route():
    
    # Grab the uploaded file
    uploaded_file = flask_request.files["upload_file"]
    
    # Check that the file extension is correct
    _, file_ext = os.path.splitext(uploaded_file.filename)
    if file_ext != ".zip":
        return ("Bad file extension! Should be .zip", 404)
    
    # Make a temporary directory to handle unzipping & copying of uploaded files
    with TemporaryDirectory() as temp_dir:
        
        # Save the uploaded file data
        temp_save_path = os.path.join(temp_dir, "new_config.zip")
        uploaded_file.save(temp_save_path)
        
        # Unzip the uploaded data, and use it to create new cameras or fully replace existing camera configs
        unzipped_folder_path = unzip_cameras_file(temp_save_path, "new")
        files_changed_dict = new_camera_configs(unzipped_folder_path)
    
    return render_template("fileschanged/fileschanged.html", files_changed_dict = files_changed_dict)

# .....................................................................................................................

@wsgi_app.route("/update/upload", methods = ["POST"])
def upload_update_file_route():
    
    # Grab the uploaded file
    uploaded_file = flask_request.files["upload_file"]
    
    # Check that the file extension is correct
    _, file_ext = os.path.splitext(uploaded_file.filename)
    if file_ext != ".zip":
        return ("Bad file extension! Should be .zip", 404)
    
    # Make a temporary directory to handle unzipping & copying of uploaded files
    with TemporaryDirectory() as temp_dir:
        
        # Save the uploaded file data
        temp_save_path = os.path.join(temp_dir, "update_config.zip")
        uploaded_file.save(temp_save_path)
        
        # Unzip the uploaded data, and use it to update existing cameras
        unzipped_folder_path = unzip_cameras_file(temp_save_path, "update")
        files_changed_dict = update_camera_configs(unzipped_folder_path)
    
    return render_template("fileschanged/fileschanged.html", files_changed_dict = files_changed_dict)

# .....................................................................................................................

@wsgi_app.route("/debug/filechange")
def debug_filechange_route():
    
    files_changed_dict = {
            "Camera_1": ["/path/to/file/1/point/0.txt",
                         "/path/to/file/1/point/1.txt",
                         "/path/to/file/1/point/2.txt",
                         "/path/to/file/2/point/0.txt",
                         "/path/to/file/2/pojnt/1.txt",
                         "/path/to/file/2/point/2.txt",
                         "/path/to/file/3.txt"],
            "camera_2": ["/p/1/2",
                         "/p/1/4",
                         "/p/1/6",
                         "/p/1/7",
                         "/p/2/3",
                         "/p/2/5"]}
    
    #files_changed_dict = {}
    
    return render_template("fileschanged/fileschanged.html", files_changed_dict = files_changed_dict)

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Network routes

# .....................................................................................................................

@wsgi_app.route("/network")
def network_route():
    return wsgi_app.send_static_file("network/network.html")

# .....................................................................................................................

@wsgi_app.route("/network/scan")
def scan_rtsp_sources_route():
    return wsgi_app.send_static_file("network/scan/scan.html")

# .....................................................................................................................

@wsgi_app.route("/network/connect")
def check_rtsp_connect_route():
    return wsgi_app.send_static_file("network/connect/connect.html")

# .....................................................................................................................

@wsgi_app.route("/network/video-sample")
def video_sample_route():
    return wsgi_app.send_static_file("network/video_sample/video_sample.html")

# .....................................................................................................................

@wsgi_app.route("/network/get-server-ip")
def control_network_get_default_ip():
    
    return_result = {"server_ip": get_own_ip()}
    
    return jsonify(return_result)

# .....................................................................................................................

@wsgi_app.route("/control/network/scan-rtsp-ports", methods = ["GET", "POST"])
def control_network_search_rtsp_ports_route():
    
    ''' Route used to check for open rtsp ports '''
    
    # For clarity
    port_to_scan = 554
    base_ip_address = None
    connection_timeout_sec = 0.5
    n_workers = 32
    
    # If a post request is used, check for modifiers to the port scanner arguments
    if flask_request.method == "POST":
        post_data_dict = flask_request.get_json(force = True)
        base_ip_address = post_data_dict.get("base_ip_address", base_ip_address)
        connection_timeout_sec = post_data_dict.get("connection_timeout_sec", connection_timeout_sec)
        n_workers = post_data_dict.get("n_workers", n_workers)
    
    # Run port scan!
    reported_base_ip_address, open_ips_list = \
    scan_for_open_port(port_to_scan, connection_timeout_sec, base_ip_address, n_workers)
    
    # Bundle outputs
    return_result = {"open_ips_list": open_ips_list,
                     "base_ip_address": reported_base_ip_address,
                     "port": port_to_scan}
    
    return jsonify(return_result)

# .....................................................................................................................

@wsgi_app.route("/control/network/test-camera-connect", methods = ["POST"])
def control_network_test_camera_connect_route():
    
    ''' Route used to check if rtsp info connects to a camera. Returns a sample image on success '''
    
    # For clarity
    max_dimension = 640
    connection_timeout_sec = 3
    default_username = ""
    default_password = ""
    default_route = ""
    
    # Initialize outputs
    connect_success = False
    b64_jpg_str = None
    video_source_info = {}
    error_message = None
    
    # Setup nifty/slightly hacky lambda to handle consistent response formatting
    connect_response = lambda _ = None: jsonify({"connect_success": connect_success,
                                                 "b64_jpg": b64_jpg_str,
                                                 "video_source_info": video_source_info,
                                                 "error_msg": error_message})
    
    # Get post data
    post_data_dict = flask_request.get_json(force = True)
    
    # Bail if the ip address isn't given
    ip_not_in_post_data = ("ip_address" not in post_data_dict)
    if ip_not_in_post_data:
        error_message = "no ip address provided!"
        return connect_response()
    
    # Get settings (or defaults) from post data
    ip_address = post_data_dict["ip_address"]
    username = post_data_dict.get("username", default_username)
    password = post_data_dict.get("password", default_password)
    route = post_data_dict.get("route", default_route)
    
    # Check that the ip address is valid
    ip_is_valid = check_valid_ip(ip_address, localhost_is_valid = False)
    if not ip_is_valid:
        ip_address = ip_address if ip_address else "none given"
        error_message = "ip address is not valid ({})".format(ip_address)
        return connect_response()
    
    # Try http connection to camera, since this will fail quicker if the ip isn't a real device
    connection_is_valid = \
    check_connection(ip_address, connection_timeout_sec = connection_timeout_sec, localhost_is_valid = False)
    if not connection_is_valid:
        error_message = "cannot connect to ip ({})".format(ip_address)
        return connect_response()
    
    # Construct the rtsp string for connecting
    rtsp_string = build_rtsp_string(ip_address, username, password, route, when_ip_is_bad_return = None)
    if rtsp_string is None:
        error_message = "bad rtsp string"
        return connect_response()
    
    try:
        # Test camera connection (with error catching, to deal with internal opencv errors)
        connect_success = False
        vcap = VideoCapture(rtsp_string)
        if vcap.isOpened():
            
            # Try to read a single frame
            connect_success, sample_frame = vcap.read()
            frame_is_ok = (sample_frame is not None)
            if connect_success and frame_is_ok:
                
                # Figure out shrunken frame size (for display purposes)
                frame_height, frame_width = sample_frame.shape[0:2]
                height_scale = (max_dimension / frame_height)
                width_scale = (max_dimension / frame_width)
                scale_factor = min(height_scale, width_scale)
                shrink_wh = (int(round(frame_width * scale_factor)), int(round(frame_height * scale_factor)))
                
                # Downsize the frame and convert to base64 jpg for output
                shrunk_frame = resize(sample_frame, dsize = shrink_wh)
                _, shrunk_jpg = imencode(".jpg", shrunk_frame)
                b64_jpg_str = base64.b64encode(shrunk_jpg).decode('utf-8')
                
                # Try to get encoding
                codec = "unknown"
                try:
                    fourcc_int = int(vcap.get(CAP_PROP_FOURCC))
                    codec = fourcc_int.to_bytes(4, 'little').decode()
                except:
                    pass
                
                # Try to get frame rate
                framerate = None
                try:
                    framerate = vcap.get(CAP_PROP_FPS)
                except:
                    pass
                
                # Bundle get video source info
                video_source_info = {"width": frame_width,
                                     "height": frame_height,
                                     "framerate": framerate,
                                     "codec": codec}
                
                # Wipe out any error messages that we may have set
                error_message = None
        
        else:
            # If we get here, we couldn't open the rtsp source but the IP was probably valid
            error_message = "bad username/password or route"
        
    except Exception as err:
        error_message = str(err)
        pass
    
    # Close connection to the camera, no matter what happened
    try:
        vcap.release()
        
    except NameError:
        # Occurs if vcap was never defined (i.e. VideoCapture call fails)
        pass
    
    except AttributeError:
        # Occurs if vcap doesn't have release function (i.e. vcap is None or otherwise wasn't set properly)
        pass
    
    return connect_response()

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% *** Launch server ***

if __name__ == "__main__":
    
    # Crash spyder IDE if it's being used, since it doesn't play nicely with flask!
    ide_catcher("Can't run flask from IDE! Try using a terminal...")
    
    # Set server access parameters
    server_protocol = ap_result["protocol"]
    server_host = ap_result["host"]
    server_port = ap_result["port"]
    server_url = "{}://{}:{}".format(server_protocol, server_host, server_port)
    
    # Launch wsgi server
    print("")
    enable_debug_mode = ap_result.get("debug")
    if enable_debug_mode:
        wsgi_app.run(server_host, port = server_port, debug = True)
    else:
        register_waitress_shutdown_command()
        wsgi_serve(wsgi_app, host = server_host, port = server_port, url_scheme = server_protocol)
    
    # Feedback in case we get here
    print("Done!")


# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap

# TODO
# - set up server settings save/load route + pages that call them
#   - should have location name (for display on page only)
#   - include way to provide github token (PAT)
#   - include way to specify github repo (for eventual git-pull update system)
# - split routes for cleanliness (may be tough due to reliance on globals... esp. rtsp procs)

# More TODOs:
# - Set up page for uploading camera configs json data & have it update/write to filesystem
# - Set up routes to allow create new cameras (with rtsp info inputs)
# - May want a system for switching camera configs between pre-defined defaults

