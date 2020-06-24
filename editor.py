#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Jun 23 16:29:44 2020

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

from time import sleep

from local.lib.ui_utils.cli_selections import Resource_Selector
from local.lib.ui_utils.editor_lib import build_path_to_editor_utilities, confirm

from local.eolib.utils.files import get_file_list
from local.eolib.utils.cli_tools import cli_select_from_list, clear_terminal


# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

# .....................................................................................................................

def run_editor_utility(script_path):
    
    # Get python interpretter path, so we call subprocess using the same environment
    python_interpretter = sys.executable
    run_command_list = [python_interpretter, script_path]
    
    # Launch the subprocess, with checks for keyboard cancels, since these seem to get re-directed here
    error_occurred = True
    try:
        subproc = subprocess.run(run_command_list)
        error_occurred = (subproc.returncode != 0 )
        
    except KeyboardInterrupt:
        error_occurred = False
    
    # Hang on to errors
    if error_occurred:
        print("",
              "ERROR running editor utility!",
              "@ {}".format(script_path),
              "",
              "Subprocess:",
              subproc,
              "", sep="\n")
    
    return error_occurred

# .....................................................................................................................

def get_ordered_editor_utilities(editor_utils_folder_path):
    
    # Sanity check that the editor folder exists!
    no_editor_folder = (not os.path.exists(editor_utils_folder_path))
    if no_editor_folder:
        err_msg_list = ["Editor utilities folder not found!",
                        "Expected:",
                        "@ {}".format(editor_utils_folder_path)]
        err_msg = "\n".join(err_msg_list)
        raise FileNotFoundError(err_msg)
    
    # Get list of all available scripts
    editor_util_script_list = get_file_list(editor_utils_folder_path, return_full_path = False, sort_list = False)
    
    # Try to enfore an ordering of the scripts
    suggested_order_list = ["loc", "cam", "vid", "rts"]
    ordered_script_list = []
    for each_suggestion in suggested_order_list:        
        for each_script in editor_util_script_list:
            lowered_script_name = each_script.lower()
            matches_suggestion = (lowered_script_name.startswith(each_suggestion.lower()))
            if matches_suggestion:
                ordered_script_list.append(each_script)
                break
    
    # Add any scripts that didn't match the target ordering to the listing
    for each_script in editor_util_script_list:
        if each_script not in ordered_script_list:
            ordered_script_list.append(each_script)
    
    # Now generate the full script paths & display-friendly names
    ordered_names_list = [os.path.splitext(each_script)[0] for each_script in ordered_script_list]
    ordered_paths_list = [os.path.join(editor_utils_folder_path, each_script) for each_script in ordered_script_list]
    
    return ordered_names_list, ordered_paths_list

# .....................................................................................................................

def ui_select_option(display_names_list, script_paths_list):
    
    # Initialize outputs
    request_break = False
    request_continue = False
    selected_script_path = None
    
    # Present stage selection menu
    try:
        select_idx, select_entry = cli_select_from_list(display_names_list,
                                                        prompt_heading = "Select editing option:",
                                                        default_selection = None,
                                                        zero_indexed = False)
        selected_script_path = script_paths_list[select_idx]
    
    # Quit with no prompt on ctrl + c
    except KeyboardInterrupt:
        print("", "", "Keyboard cancel! (ctrl + c)", "", sep="\n")
        request_break = True
    
    # Prompt to quit if no selection is made
    except ValueError:
        request_break = confirm("Quit?", default_response = True)
        request_continue = (not request_break)
    
    # Loop on index errors
    except IndexError as err_msg:
        request_continue = True
        print("", err_msg, "", sep = "\n")
        sleep(1.5)
    
    # Ignore (probably) input errors
    except NameError as err_msg:
        # Happens due to queued up inputs, should ignore
        request_continue = True
        print("", err_msg, "", sep = "\n")
    
    return request_break, request_continue, selected_script_path

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Get pathing

# Get shared pathing
selector = Resource_Selector()
project_root_path = selector.get_project_root_pathing()

# Get pathing to editor scripts
editor_utils_folder_path = build_path_to_editor_utilities(project_root_path)

# Try to order the scripts in a more preferrable order
ordered_util_names_list, ordered_util_paths_list = get_ordered_editor_utilities(editor_utils_folder_path)


# ---------------------------------------------------------------------------------------------------------------------
#%% *** MENU LOOP ***

while True:
    
    # UI to select an editor option
    req_break, req_continue, selected_script_path = ui_select_option(ordered_util_names_list, ordered_util_paths_list)
    
    # Handle program flow
    if req_continue: continue
    if req_break: break

    # If we get this far, run whatever editor option was selected
    if selected_script_path is not None:
        clear_terminal(0, 0.25)
        run_editor_utility(selected_script_path)  # Blocking
    
    # Prompt user to acknowledge whatever is on screen before we reset the menu
    print("", "", sep = "\n")
    input("Press enter to return to the editor menu...")
    clear_terminal(pre_delay_sec = 0.5, post_delay_sec = 0.25)


# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap


