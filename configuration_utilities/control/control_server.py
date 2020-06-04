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

from tempfile import TemporaryDirectory

import zipfile
import shutil
import subprocess

from time import sleep

from waitress import serve as wsgi_serve

from local.lib.common.timekeeper_utils import get_utc_epoch_ms, get_human_readable_timestamp
from local.lib.common.environment import get_control_server_protocol, get_control_server_host, get_control_server_port

from local.lib.ui_utils.cli_selections import Resource_Selector
from local.lib.ui_utils.script_arguments import script_arg_builder

from local.lib.file_access_utils.structures import create_missing_folder_path, create_missing_folders_from_file
from local.lib.file_access_utils.shared import build_camera_path, build_logging_folder_path
from local.lib.file_access_utils.reporting import build_base_report_path
from local.lib.file_access_utils.logging import make_log_folder
from local.lib.file_access_utils.logging import build_stdout_log_path, build_stderr_log_path
from local.lib.file_access_utils.logging import build_upload_new_log_file_path, build_upload_update_log_file_path
from local.lib.file_access_utils.pid_files import check_running_camera, clear_all_pid_files

from flask import Flask, jsonify, redirect, render_template
from flask import request as flask_request
from flask_cors import CORS

from local.eolib.utils.quitters import ide_catcher


# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

# .....................................................................................................................

def parse_control_args(debug_print = False):
    
    # Set defaults
    default_protocol = get_control_server_protocol()
    default_host = get_control_server_host()
    default_port = get_control_server_port()
    
    # Set arg help text
    protocol_help_text = "Specify the protocol of the control server\n(Default: {})".format(default_protocol)
    host_help_text = "Specify the host of the control server\n(Default: {})".format(default_host)
    port_help_text = "Specify the port of the control server\n(Default: {})".format(default_port)
    
    # Set script arguments for running files
    args_list = [{"display": {"default": False, "help_text": "Enable display during data collection"}},
                 {"debug": {"default": False}},
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

def get_existing_camera_names_list():
    return list(g_selector.get_cameras_tree().keys())

# .....................................................................................................................
    
def get_cameras_folder_path():
    _, cameras_folder_path = g_selector.get_project_pathing()
    return cameras_folder_path

# .....................................................................................................................

def save_update_log(camera_select, files_changed_list):
    
    # Get pathing to the log file
    cameras_folder_path = get_cameras_folder_path()
    update_log_file_path = build_upload_update_log_file_path(cameras_folder_path, camera_select)
    make_log_folder(update_log_file_path)
    
    # Handle 'no file' case
    no_files = (len(files_changed_list) == 0)
    if no_files:
        files_changed_list = ["  No files changed!"]
    
    # Save data to the log file
    with open(update_log_file_path, "a") as log_file:
        log_file.write("\n".join(["", "", get_human_readable_timestamp(), ""]))
        log_file.write("\n".join(files_changed_list))
    
    return

# .....................................................................................................................

def save_new_log(camera_select, files_changed_list):
    
    # Get pathing to the log file
    cameras_folder_path = get_cameras_folder_path()
    new_log_file_path = build_upload_new_log_file_path(cameras_folder_path, camera_select)
    make_log_folder(new_log_file_path)
    
    # Handle 'no file' case
    no_files = (len(files_changed_list) == 0)
    if no_files:
        files_changed_list = ["  No files changed!"]
    
    # Save data to the log file
    with open(new_log_file_path, "a") as log_file:
        log_file.write("\n".join(["", "", get_human_readable_timestamp(), ""]))
        log_file.write("\n".join(files_changed_list))
    
    return

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
    
    # Handle case where the user supplies a zipped 'cameras' folder containing the camera folders
    cameras_folder_path = get_cameras_folder_path()
    cameras_folder_name = os.path.basename(cameras_folder_path)
    contains_one_item = (len(unzipped_camera_names_list) == 1)
    contains_cameras_folder = (unzipped_camera_names_list[0] == cameras_folder_name)
    if contains_one_item and contains_cameras_folder:
        unzip_path = os.path.join(unzip_path, cameras_folder_name)
        unzipped_camera_names_list = os.listdir(unzip_path)
    
    # Clean up camera names (remove spaces) and throw away report & logs from uploaded camera files
    for each_camera_name in unzipped_camera_names_list:
        
        # Make sure camera names don't have spaces
        clean_name = each_camera_name.replace(" ", "_")
        if each_camera_name is not clean_name:
            orig_path = os.path.join(unzip_path, each_camera_name)
            clean_path = os.path.join(unzip_path, clean_name)
            os.rename(orig_path, clean_path)
        
        # Remove data that shouldn't be replacing existing files
        remove_logs_and_report_data(unzip_path, clean_name)
    
    return unzip_path

# .....................................................................................................................

def remove_logs_and_report_data(cameras_folder_path, camera_select):
    
    ''' Remove run-time recording folders. Intended for cleaning up data uploaded to the server '''
    
    # Remove logs folder, if it exists
    camera_logs_path = build_logging_folder_path(cameras_folder_path, camera_select)
    if os.path.exists(camera_logs_path):
        shutil.rmtree(camera_logs_path)
        
    # Remove report folder, if it exists
    camera_report_path = build_base_report_path(cameras_folder_path, camera_select)
    if os.path.exists(camera_report_path):
        shutil.rmtree(camera_report_path)
    
    return

# .....................................................................................................................

def remove_configuration_data(cameras_folder_path, camera_select):
    
    ''' 
    Remove major configuration data. Intended for setting up new camera configs.
    In most cases, this will end up removing the 'users' and 'resources' folders
    '''
    
    # Get the camera folder & pathing to folders we want to keep
    selected_camera_folder_path = build_camera_path(cameras_folder_path, camera_select)
    camera_logs_path = build_logging_folder_path(cameras_folder_path, camera_select)
    camera_report_path = build_base_report_path(cameras_folder_path, camera_select)
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
    real_cameras_folder_path = get_cameras_folder_path()
    real_camera_path = build_camera_path(real_cameras_folder_path, camera_name)
    
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
    existing_names_list = get_existing_camera_names_list()
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
    existing_names_list = get_existing_camera_names_list()
    
    # Copy over all unzipped data, and clean out data for existing cameras
    real_cameras_folder_path = get_cameras_folder_path()
    files_changes_dict = {}
    for each_camera_name in unzipped_names_list:
        
        # Remove config data for existing cameras (but leave logs & report data)
        already_exists = (each_camera_name in existing_names_list)
        if already_exists:
            remove_configuration_data(real_cameras_folder_path, each_camera_name)
        
        # Copy of unzipped data
        updated_file_paths_list = copy_uploaded_config_data(unzip_folder_path, each_camera_name)
        files_changes_dict[each_camera_name] = updated_file_paths_list
    
    return files_changes_dict

# .....................................................................................................................

def launch_rtsp_collect(camera_select, enable_display = False):
    
    # Get the python interpreter used to launch this server, which we'll use to run the scripts
    python_interpretter = sys.executable
    
    # Build script arguments
    save_arg = ["-ss"] if enable_display else ["-sk"]
    display_arg = ["-d"] if enable_display else []
    
    # Build pathing to the launch script
    project_root_path, cameras_folder_path = g_selector.get_project_pathing()
    launch_script_name = "run_rtsp_collect.py"
    launch_script_path = os.path.join(project_root_path, launch_script_name)
    launch_args = [python_interpretter, "-u", launch_script_path, "-c", camera_select] + display_arg + save_arg
    
    # Build pathing to store stdout/stderr logs
    current_epoch_ms = get_utc_epoch_ms()
    log_filename = "{}.log".format(current_epoch_ms)    
    camera_stdout_log = build_stdout_log_path(cameras_folder_path, camera_select, log_filename)
    camera_stderr_log = build_stderr_log_path(cameras_folder_path, camera_select, log_filename)
    create_missing_folders_from_file(camera_stdout_log)
    create_missing_folders_from_file(camera_stderr_log)
    
    # Launch script as a separate/detached process (with logging), which will run & close independent of the server
    with open(camera_stdout_log, "w") as stdout_file:
        with open(camera_stderr_log, "w") as stderr_file:
            # Launch (non-blocking) call to open a collection script
            subprocess.Popen(launch_args,
                             stdin = None,
                             stdout = stdout_file,
                             stderr = stderr_file,
                             preexec_fn = os.setpgrp)
    
    return

# .....................................................................................................................

def launch_file_collect(camera_select, user_select, video_select, 
                        save_and_keep = False, 
                        save_and_delete = False, 
                        skip_save = True,
                        enable_display = True):
    
    # Get the python interpreter used to launch this server, which we'll use to run the scripts
    python_interpretter = sys.executable
    
    # Build script arguments
    user_arg = ["-u", user_select]
    video_arg = ["-v", video_select]
    save_args = (["-sk"] if save_and_keep else []) + (["-sd"] if save_and_delete else [])
    skip_save_arg = (["-ss"] if skip_save else [])
    display_arg = ["-d"] if enable_display else []
    
    # Build pathing to the launch script
    project_root_path, cameras_folder_path = g_selector.get_project_pathing()
    launch_script_name = "run_file_collect.py"
    launch_script_path = os.path.join(project_root_path, launch_script_name)
    launch_args = [python_interpretter, "-u", launch_script_path, "-c", camera_select] \
                  + user_arg + video_arg + save_args + skip_save_arg + display_arg
    
    # Build pathing to store stdout/stderr logs
    current_epoch_ms = get_utc_epoch_ms()
    log_filename = "{}.log".format(current_epoch_ms)    
    camera_stdout_log = build_stdout_log_path(cameras_folder_path, camera_select, log_filename)
    camera_stderr_log = build_stderr_log_path(cameras_folder_path, camera_select, log_filename)
    create_missing_folders_from_file(camera_stdout_log)
    create_missing_folders_from_file(camera_stderr_log)
    
    # Launch script as a separate/detached process (with logging), which will run & close independent of the server
    with open(camera_stdout_log, "w") as stdout_file:
        with open(camera_stderr_log, "w") as stderr_file:
            # Launch (non-blocking) call to open a collection script
            subprocess.Popen(launch_args,
                             stdin = None,
                             stdout = stdout_file,
                             stderr = stderr_file,
                             preexec_fn = os.setpgrp)
    
    return

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Parse input args

ap_result = parse_control_args()


# ---------------------------------------------------------------------------------------------------------------------
#%% Set up globals

# Create selector so we can access existing report data
g_selector = Resource_Selector()

# Toggle collection displays on/off from script args
enable_displays = ap_result.get("display")


# ---------------------------------------------------------------------------------------------------------------------
#%% Create routes

# Create wsgi app so we can start adding routes
wsgi_app = Flask(__name__, static_url_path = '', static_folder = "web/static", template_folder = "web/templates")
CORS(wsgi_app)

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

@wsgi_app.route("/status/cameras")
def status_cameras_route():
    
    # Get pathing to cameras and a list of available cameras
    cameras_folder_path = get_cameras_folder_path()
    camera_name_list = get_existing_camera_names_list()
    
    # Loop over all cameras and look for active PID files to see if they're online
    camera_status_dict = {}
    for each_camera_name in camera_name_list:
        is_online, start_timestamp_str = check_running_camera(cameras_folder_path, each_camera_name)
        camera_status_dict[each_camera_name] = {"is_online": is_online, "start_timestamp_str": start_timestamp_str}
        
    return jsonify(camera_status_dict)

# .....................................................................................................................

@wsgi_app.route("/control/restart/<string:camera_select>")
def control_restart_camera_route(camera_select):
    
    launch_rtsp_collect(camera_select, enable_display = enable_displays)
    sleep(1.5)
    
    return redirect("/status")

# .....................................................................................................................

@wsgi_app.route("/control/stop/<string:camera_select>")
def control_stop_camera_route(camera_select):
    
    # Get pathing to cameras folder so we can clear PIDs for the selected camera
    cameras_folder_path = get_cameras_folder_path()    
    clear_all_pid_files(cameras_folder_path, camera_select, max_retrys = 3)
    
    return redirect("/status")

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
        
    # Log changes to each camera
    for each_camera, each_file_list in files_changed_dict.items():
        save_new_log(each_camera, each_file_list)
    
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
        
    # Log changes to each camera
    for each_camera, each_file_list in files_changed_dict.items():
        save_update_log(each_camera, each_file_list)
    
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
        wsgi_serve(wsgi_app, host = server_host, port = server_port, url_scheme = server_protocol)
    
    # Feedback in case we get here
    print("Done!")


# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap

# TODO
# - Handle Popen 'defunct' calls better (periodically clean up finished calls?)
