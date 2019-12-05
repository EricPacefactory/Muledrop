#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Apr  4 16:39:41 2019

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

import subprocess
import argparse
import json
import numpy as np
from flask import Flask, render_template
from flask import request as flask_request

from eolib.utils.network import get_own_ip
from eolib.utils.files import get_folder_list, get_file_list

from local.lib.file_access_utils.shared import find_root_path
from local.lib.file_access_utils.history import load_history, save_history
from local.lib.file_access_utils.structures import build_cameras_tree, build_core_config_utils_tree

# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes



# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

# .....................................................................................................................

def spyder_catcher():
    if any(["spyder" in env_var.lower() for env_var in os.environ]):
        raise SystemExit("SPYDER STOPPED - Can't run a Flask server within Spyder. Use a terminal!")

# .....................................................................................................................

def parse_args():
    
    ap = argparse.ArgumentParser()    
    
    ap.add_argument("-d", "--debug",
                    default=False, 
                    action="store_true",
                    help="Enable debug mode")
    
    ap.add_argument("-b", "--browser",
                    default=False, 
                    action="store_true",
                    help="Launch browser on call")
    
    ap.add_argument("-wh", "--web_host",
                    default = "127.0.0.1",
                    type = str,
                    help = "Webserver IP.")
    
    ap.add_argument("-wp", "--web_port",
                    default = 5000,
                    type = int,
                    help = "Webserver port.")
    
    # Get arguments in a dictionary
    return vars(ap.parse_args())

# .....................................................................................................................
    
def get_list_of_utilities(web_resources_folder = "web_resources",
                          utilities_folder = "configuration_utilities", 
                          core_folder = "core"):
        
    # Build pathing to the core folder
    file_directory = os.path.dirname(os.path.abspath(__file__))
    core_path = os.path.join(file_directory, web_resources_folder, utilities_folder, core_folder)
    
    # Get pathing to all the component folders
    core_component_folders = get_folder_list(core_path, return_full_path = True)
    
    # Get a list of all the core component web configurables, organized in a dict by component keys
    core_files_dict = {}
    for each_component in core_component_folders:
        core_filepath_list = get_file_list(each_component, return_full_path = True)
        
        # Add each file by it's name only + it's full file path for easier lookup
        component_name_only = os.path.basename(each_component)
        core_files_dict[component_name_only] = {}
        for each_filepath in core_filepath_list:
            
            full_filename = os.path.basename(each_filepath)
            name_only, file_ext = os.path.splitext(full_filename)
            
            # Skip any non-python files
            if file_ext != ".py":
                print("(Skipping file):", full_filename)
                continue
            
            # Store data in handy format
            core_files_dict[component_name_only][name_only] = each_filepath
    
    return {"core": core_files_dict}

# .....................................................................................................................

def build_run_command_list(python_filepath, camera_select, video_select, task_select, user_select,
                           python_call = "python3"):
    
    # Create base python call (i.e. "python3 filename.py")
    base_args = [python_call, python_filepath]
    
    # Build selection arguments
    camera_args = ["-c", camera_select]
    video_args = ["-v", video_select]
    task_args = ["-t", task_select]
    user_args = ["-u", user_select]
    
    return base_args + camera_args + video_args + task_args + user_args

# .....................................................................................................................

# Hacky function for closing 'zombie' python processes
def daemon_hunter(python_proc_list):
    print("")
    print("!" * 50)
    print("PROC LENGTH:", len(python_proc_list))
    for each_proc in python_proc_list:
        if each_proc.poll() is not None:
            print("SERVER WAITING FOR CONFIGURABLE TO CLOSE...")
            popen_returncode = each_proc.wait(2)
            feedback_msg = "CONFIGURABLE CLOSED! SERVER RESUMING OPERATIONS"
            if not popen_returncode:
                feedback_msg = "BAD RETURN CODE: CONFIGURABLE NOT CLOSED! Will try to terminate..."
                each_proc.terminate()
            print("    {}".format(feedback_msg))

# .....................................................................................................................

def get_page_title(component_select, python_file_path, 
                   web_resources_folder = "web_resources", 
                   lookup_folder = "lookups", 
                   lookup_file = "page_titles.json"):
    
    # Build pathing to the page title lookup file
    project_root_path = find_root_path()
    page_lookup_path = os.path.join(project_root_path, web_resources_folder, lookup_folder, lookup_file)
    
    # Clean up the python file name
    python_full_file_name = os.path.basename(python_file_path)
    python_name_only = os.path.splitext(python_full_file_name)[0]
    
    # Generate a cleaned up name, in case we can't find a replacement
    clean_name = python_name_only.replace("_", " ").title()
    
    # If the lookup file isn't found, just return the file name with a bit of cleanup
    if not os.path.exists(page_lookup_path):
        return clean_name
    
    # Load the lookup file to see if we have a replacement title
    with open(page_lookup_path, "r") as in_file:
        page_title_lut = json.load(in_file)
    
    return page_title_lut.get(component_select, {}).get(python_name_only, clean_name)

# .....................................................................................................................

def get_core_config_display_list(core_config_utils_tree, 
                                 web_resources_folder = "web_resources", 
                                 lookup_folder = "lookups", 
                                 lookup_file = "core_config_display.json"):
    
    # Build pathing to the core config display lookup file
    project_root_path = find_root_path()
    display_lookup_path = os.path.join(project_root_path, web_resources_folder, lookup_folder, lookup_file)
    
    # If the lookup file isn't found, raise an error, since we need it to build the display!
    if not os.path.exists(display_lookup_path):
        raise FileNotFoundError("Couldn't find display list lookup! Can't build core config web page...")
    
    # Load the lookup file to see how we should display things
    with open(display_lookup_path, "r") as in_file:
        display_list = json.load(in_file)
    
    # Build the options list using the display lookup
    display_options_list = []
    for each_display_entry in display_list:
        
        page_display_name = each_display_entry["display_name"]
        component_select = each_display_entry["component_select"]
        option_names_list = core_config_utils_tree.get(component_select, {}).get("names", [])
        
        # Bundle data needed to render the core config options display
        new_options = {"display_name": page_display_name,
                       "component_select": component_select,
                       "option_names_list": option_names_list}
        
        display_options_list.append(new_options)
    
    return display_options_list

# .....................................................................................................................

def invalid_selections(check_keys = ["camera_select", "user_select", "task_select", "video_select"]):
    
    # Get a subset of the selections to check
    check_selections = [selections[each_key] for each_key in check_keys]
    print("CHECK", check_selections)
    
    # If any of the selections are None, redirect to home
    none_selections = any([(each_sel is None) for each_sel in check_selections])
    if none_selections:
        return True
    
    # If any of the selections don't exist, redirect to home for re-selection
    # ...
    
    return False

# .....................................................................................................................

def check_core_pathing(core_path, core_config_utils_tree):
    
    # Pre-allocate outputs for convenience
    is_valid = False
    valid_component_select = ""
    python_file_path = ""
    
    # First try to split the core path, which should have the format:
    #   core_path = "component_name/python_script_name"
    split_path = core_path.split("/")
    
    # Bail if splitting the path gives us a weird number of pieces
    right_number_of_parameters = (len(split_path) == 2)
    if not right_number_of_parameters:
        return is_valid, valid_component_select, python_file_path
    
    # Unpack the split path for further inspection and get the core-config tree dictionary
    component_select, python_select = split_path
    
    # Bail if the selected component isn't in the tree
    component_list = core_config_utils_tree.keys()
    if component_select not in component_list:
        return is_valid, valid_component_select, python_file_path
    
    # Get the available python script options and bail if the desired python script isn't there
    component_options_list = core_config_utils_tree[component_select]["names"]
    if python_select not in component_options_list:
        return is_valid, component_select, python_file_path
    
    # Got this far, so return the actual python path!
    file_idx = component_options_list.index(python_select)
    python_file_path = core_config_utils_tree[component_select]["paths"][file_idx]
    is_valid = os.path.exists(python_file_path)
    
    # Debugging feedback
    if debug_mode:
        print("", 
              "Selected: {}".format(component_select),
              "  Script: {}".format(python_file_path),
              "   Valid: {}".format(is_valid),
              "", sep="\n")
    
    return is_valid, component_select, python_file_path

# .....................................................................................................................

def launch_config_utility(python_file_path, 
                          camera_select, 
                          video_select, 
                          task_select, 
                          user_select, 
                          socket_host,
                          socket_port,
                          python_call = "python3"):
    
    # Create base python call (i.e. "python3 scriptname.py")
    base_args = [python_call, python_file_path]
    
    # Build selection arguments
    camera_args = ["-c", camera_select]
    user_args = ["-u", user_select]
    task_args = ["-t", task_select]
    video_args = ["-v", video_select]
    socket_args = ["-sip", str(socket_host), "-sport", str(socket_port)]
    run_command_list = base_args + camera_args + user_args + task_args + video_args + socket_args
    
    # Clear out existing python processes, start the new config utility and keep track of the process
    # (VERY AWKWARD IMPLEMENTATION!)
    daemon_hunter(global_python_procs)
    new_pyproc = subprocess.Popen(run_command_list)     # Non-blocking
    global_python_procs.append(new_pyproc)

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Load demo setup data

# Get arguments for this script call
script_args = parse_args()
launch_browser = script_args["browser"]
debug_mode = script_args["debug"]
web_host = script_args["web_host"]
web_port = script_args["web_port"]

# Hard-code these for now
socket_host = get_own_ip()
socket_port = 6123

# Hacky way to keep track of background python processes launched by the server
global_python_procs = []

# ---------------------------------------------------------------------------------------------------------------------
#%% Define routes

'''
STOPPED HERE
- NEED TO LOOK INTO STOPPING/STARTING SOCKETS, SINCE CLICKING ON OPTIONS IS GETTING REALLY ANNOYING!
- THEN THINK ABOUT DRAWING SPEC?!
'''

# Set up selection variables (and use history in debug mode for convenience)
selections = {"camera": None, "user": None, "task": None, "video": None}
selections = load_history(None, enable = True) #debug_mode)

# Crash spyder IDE before launching the server, since it doesn't work!
spyder_catcher()

# Create server
server = Flask(__name__, root_path = "web_resources")

# .....................................................................................................................

@server.route("/core/")
@server.route("/core/<path:core_path>")
def core_config_route(core_path = ""):
    
    # Go back home if there's something wrong with the selections
    if invalid_selections():
        if debug_mode:
            print("", "DEBUG: Bad selection redirect!", selections, sep="\n")
        return home_route(redirected = True)
    
    # Get all of the configuration utilities (components + options) so we can check if the selections are valid
    core_config_utils_tree = build_core_config_utils_tree(None)
    core_options_display_list = get_core_config_display_list(core_config_utils_tree)
    
    # Figure out the component/python file
    is_valid, component_select, python_file_path = check_core_pathing(core_path, core_config_utils_tree)
    
    # Render a blank configuration page if the pathing isn't pointing to a real configuration utility
    if not is_valid:
        return render_template("core_config.html", 
                               page_title = "Select a component to configure", 
                               socket_url = "",
                               left_menu_list = core_options_display_list)
    
    # Launch the python config utility script, set up the socket connection and page title and we're done!
    new_socket_host = socket_host
    new_socket_port = socket_port + np.random.randint(0, 100)
    launch_config_utility(python_file_path, **selections, socket_host=new_socket_host, socket_port=new_socket_port)
    socket_url = "http://{}:{}".format(new_socket_host, new_socket_port)#socket_port)
    page_title = get_page_title(component_select, python_file_path)
    print("REF LAUNCH:", python_file_path)
    
    return render_template("core_config.html", 
                           page_title = page_title, 
                           socket_url = socket_url,
                           left_menu_list = core_options_display_list)

# .....................................................................................................................

@server.route("/external/<python_file>")
def externals_config_route(python_file):
    return "<h1>EXTERNAL: {}\n</h1><p>But externals don't work now, sorry...</p>".format(python_file)

# .....................................................................................................................

@server.route("/")
def home_route(redirected = False):
    
    project_tree = build_cameras_tree(None, show_hidden = False, show_rtsp = False)
    
    return render_template("home.html",
                           selections = selections,
                           project_tree = project_tree, 
                           redirected = redirected)

# .....................................................................................................................

@server.route("/update_selections", methods=["POST"])
def update_selections_json():
    
    # Get selections from the webpage
    new_selections = flask_request.get_json()
    
    # Assuming the selection is good, update the corresponding selection entry
    try:
        selections.update(new_selections)
        save_history(None, selections, enable = debug_mode)
    except Exception as err:
        print("Error updating selections from web...")
        print(err)
        return ("", 404)
    
    # Some debugging feedback
    print("", "Updated selections:", selections, "", sep="\n")
    
    return ("", 204) # No content response

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% *** Launch server ***

if __name__ == "__main__":
    
    # Open the web browser if we're not in debug mode
    if launch_browser:
        import webbrowser
        web_server_url = "http://{}:{}".format(web_host, web_port)
        webbrowser.open(url = web_server_url)
        
    # Unleash the flask!
    server.run(host = web_host, port = web_port, debug=debug_mode)  # BLOCKING
    print("SHUTTING DOWN REFERENCE SERVER!")


# ---------------------------------------------------------------------------------------------------------------------
#%% Clean-up

# Clean up python subprocesses, if needed
for each_proc in global_python_procs:
    each_proc.wait(6.5)
    each_proc.terminate()
    

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap

