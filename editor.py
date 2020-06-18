#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Jan  6 17:14:54 2020

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

from local.eolib.utils.files import get_file_list
from local.eolib.utils.cli_tools import cli_confirm, cli_select_from_list, clear_terminal, clean_error_quit

# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes

# .....................................................................................................................

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

# .....................................................................................................................

def clean_option_name(option_name):
    return option_name.replace(".py", "").replace("_", " ").title()

# .....................................................................................................................

def _select_option(editor_parent_folder_path, script_ordering):
    
    # Clean up list for readability
    clean_option_list = [clean_option_name(each_stage) for each_stage in script_ordering]
    select_idx, _ = cli_select_from_list(clean_option_list, 
                                         prompt_heading = "Select editing option:")
    
    # Build the full pathing
    editor_select = script_ordering[select_idx]
    editor_script_path = os.path.join(editor_parent_folder_path, editor_select)
    
    return editor_script_path, editor_select

# .....................................................................................................................

@clean_error_quit
def user_select_editor_option(editor_parent_folder_path, script_ordering):
    
    # Initialize outputs
    request_break = False
    request_continue = False
    editor_script_path = None
    
    # Present stage selection menu
    try:
        editor_script_path, editor_select = _select_option(editor_parent_folder_path, script_ordering)
    
    # Prompt to quit if no selection is made
    except ValueError:
        request_break = cli_confirm("Quit?")
        request_continue = (not request_break)
        
    # Quit with no prompt on ctrl + c
    except KeyboardInterrupt:
        print("", "", "Keyboard cancel! (Ctrl + c)", sep="\n")
        request_break = True
    
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
        sleep(1.0)
        
    return request_break, request_continue, editor_script_path

# .....................................................................................................................

def run_editor_utility(option_path):
    
    # Get python interpretter path, so we call subprocess using the same environment
    python_interpretter = sys.executable
    
    # Launch selected utility using direct path to option script
    run_command_list = [python_interpretter, option_path]
    subproc = subprocess.run(run_command_list)
    
    # Hang on to errors
    if subproc.returncode != 0:
        print("",
              "ERROR running editor utility!",
              "@ {}".format(option_path),
              "",
              "Subprocess:",
              subproc,
              "", sep="\n")
        input("Press enter to continue ")
    
    return subproc

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Ask user for base selections

# Get shared pathing
selector = Resource_Selector()
project_root_path = selector.get_project_root_pathing()


# ---------------------------------------------------------------------------------------------------------------------
#%% Get pathing info

# Build path to editor utility scripts
editor_utils_folder_path = os.path.join(project_root_path, "configuration_utilities",  "editors")

# Sanity check that the editor folder exists!
no_editor_folder = (not os.path.exists(editor_utils_folder_path))
if no_editor_folder:
    raise FileNotFoundError("Editor utilities folder not found!\n  (Expecting {})".format(editor_utils_folder_path))

# Get list of all available scripts, in some order
editor_script_options = get_file_list(editor_utils_folder_path, return_full_path = False, sort_list = True)


# ---------------------------------------------------------------------------------------------------------------------
#%% *** MENU LOOP ***

while True:
    
    # Have user select an editor option
    req_break, req_continue, option_path = user_select_editor_option(editor_utils_folder_path, editor_script_options)
    
    if req_continue: continue
    if req_break: break
    
    # Hide all the selection mess before launching into the editor utility
    clear_terminal(0, 0.25)

    # If we get this far, run whatever editor option was selected
    return_code = run_editor_utility(option_path)  # Blocking
    
    # Wait a bit to show final text, then clear and repeat prompt
    clear_terminal(pre_delay_sec = 1.25, post_delay_sec = 0.25)
    

# Some final cleanup feedback
print("", "{} closed...".format(os.path.basename(__file__)), "", sep="\n")


# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap

# TODO
# - Figure out why closing scripts fails from Spyder... Seems to be due to input() function?

