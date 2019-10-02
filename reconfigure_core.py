#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Aug 22 16:21:43 2019

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

from local.lib.selection_utils import Resource_Selector, parse_args
from local.lib.file_access_utils.core import get_ordered_core_sequence, get_ordered_config_paths, build_core_folder_path
from local.lib.file_access_utils.shared import load_with_error_if_missing

from eolib.utils.files import get_file_list, get_folder_list
from eolib.utils.cli_tools import cli_confirm, cli_select_from_list, clear_terminal, clean_error_quit, loop_on_index_error

# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes

# .....................................................................................................................

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

# .....................................................................................................................

def spyder_catcher():
    
    # Spyder IDE seems to run a different env when using subprocess.run, which breaks this script...
    if any(["spyder" in each_key.lower() for each_key in os.environ.keys()]):
        print("", 
              "!" * 36,
              "WARNING:", 
              "  Subprocess calls do not work properly in Spyder IDE!",
              "  Use terminal if trying to launch configuration utilities.",
              "", sep = "\n")
    
# .....................................................................................................................

def clear_with_status(camera_select, user_select, task_select, video_select, component_select = None):
    
    clear_terminal()
    
    # Build output text
    num_seperator_symbols = 48
    seperator_gfx = "=" * num_seperator_symbols
    print_strs = [seperator_gfx,
                  "Current_selections:",
                  "  Camera: {}".format(camera_select),
                  "    User: {}".format(user_select),
                  "    Task: {}".format(task_select),
                  "   Video: {}".format(video_select),
                  seperator_gfx]
    
    # Add component selection info, if present
    if component_select is not None:
        component_str_length = len(component_select)
        left_centering_offset = int(max(0, (num_seperator_symbols + component_str_length) / 2))
        print_strs += [component_select.rjust(left_centering_offset), seperator_gfx]
        
    # Show current selection info
    print(*print_strs, sep="\n")
    
    # Hang for a sec to prevent accidental selections
    sleep(0.5)
    
# .....................................................................................................................

def clean_stage_name(stage_name):
    return stage_name.replace("_", " ").title()

# .....................................................................................................................

def clean_option_name(option_name):
    return option_name.replace(".py", "").replace("_", " ").title()

# .....................................................................................................................

def get_default_option(stage_name):

    # Build pathing and update config file paths
    core_folder_path = build_core_folder_path(cameras_folder_path, camera_select, user_select, task_select)
    config_paths, stage_order = get_ordered_config_paths(core_folder_path)
    
    # Get index of the target stage name
    clean_stage_order = [clean_stage_name(each_stage) for each_stage in stage_order]
    stage_index = clean_stage_order.index(stage_name)
    config_file_path = config_paths[stage_index]
    
    # Load data and check which configuration utility was used to set it up. We'll use that as the default
    config_data = load_with_error_if_missing(config_file_path)
    file_access_dict = config_data.get("access_info", {})
    previous_config_util_used = file_access_dict.get("configuration_utility", None)
        
    return previous_config_util_used

# .....................................................................................................................

def select_core_component(core_config_utils_folder_path, ordered_stage_names):
    
    # Get path to the folder holding all core config utilies
    #core_component_list = get_folder_list(core_config_utils_folder_path, return_full_path = False)
    
    # Clean up list for readability
    clean_stage_list = [clean_stage_name(each_stage) for each_stage in ordered_stage_names]
    select_idx, component_display_name = cli_select_from_list(clean_stage_list, 
                                                              prompt_heading = "Select core component:")
    
    # Build the full pathing
    component_original_name = ordered_stage_names[select_idx]
    component_folder_path = os.path.join(core_config_utils_folder_path, component_original_name)
    
    return component_folder_path, component_display_name

# .....................................................................................................................

def select_core_option(component_path, component_display_name):
    
    # Get all options (scripts) at the given component path
    options_list = get_file_list(component_path, return_full_path = False)
    
    # Error if there are no options to display, this is likely an interal error with pathing...
    if len(options_list) < 1:
        print("", "!"*36, "Searched path:", "@ {}".format(component_path), "!"*36, "", sep="\n")
        raise AttributeError("No options found for component: {}".format(component_display_name))
    
    # Clean up the list for display
    clean_options_list = [clean_option_name(each_entry) for each_entry in sorted(options_list)]
    
    # Re-order so that passthroughs appear as the first entry
    passthrough_label = "Passthrough"
    passthrough_in_list = (passthrough_label in clean_options_list)
    if passthrough_in_list:
        pass_idx = clean_options_list.index(passthrough_label)
        
        # Update clean option list
        clean_options_list.pop(pass_idx)
        clean_options_list = [passthrough_label] + clean_options_list
        
        # Update raw script paths as well, since we'll be referring to that later
        passthrough_script = options_list.pop(pass_idx)
        options_list = [passthrough_script] + options_list
        
    # Get default selection
    raw_default_option = get_default_option(component_display_name)
    default_option = clean_option_name(raw_default_option)
    
    # Prompt user to select core config option
    prompt_msg = "Select {} option:".format(component_display_name.lower())
    select_idx, option_display_name = cli_select_from_list(clean_options_list, 
                                                           default_selection = default_option,
                                                           default_indicator = "(current)",
                                                           prompt_heading = prompt_msg,
                                                           zero_indexed = passthrough_in_list)
    
    
    # Build outputs
    option_script = options_list[select_idx]
    option_path = os.path.join(component_path, option_script)
    
    return option_path, option_display_name

# .....................................................................................................................

@clean_error_quit
def user_select_component(component_folder_path, stage_ordering):
    
    # Initialize outputs
    request_break = False
    request_continue = False
    component_path = None
    component_display_name = None
    
    # Present component selection menu
    try:
        component_path, component_display_name = select_core_component(component_folder_path, stage_ordering)
    
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
        
    return request_break, request_continue, component_path, component_display_name

# .....................................................................................................................

@clean_error_quit
def user_select_option(component_path, component_display_name):
    
    # Initialize outputs
    request_break = False
    request_continue = False
    option_path = None
    option_display_name = None
    
    # Present options menu
    try:
        option_path, option_display_name = select_core_option(component_path, component_display_name)
    
    # Cancel option select if no selection is made (return to component select)
    except ValueError:
        # Some feedback before returning to component select
        print("", "", "Option select cancelled!", "", sep = "\n")  
        sleep(0.5)
        request_continue = True
    
    # Cancel option select if ctrl + c was pressed, and return to the main menu
    except KeyboardInterrupt:
        request_continue = True
        
    # Return to main menu on index errors
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

    return request_break, request_continue, option_path, option_display_name

# .....................................................................................................................

def run_config_utility(option_path, camera_select, user_select, task_select, video_select):
    
    # Build arguments to pass to each config utility
    script_arg_list = ["-c", camera_select,
                       "-u", user_select,
                       "-t", task_select,
                       "-v", video_select]
    
    # Launch selected config util ity using direct path to option script
    run_command_list = ["python3", option_path] + script_arg_list    
    subproc = subprocess.run(run_command_list)
    
    # Hang on to errors
    if subproc.returncode != 0:
        print("",
              "ERROR running configuration utility!",
              "@ {}".format(option_path),
              "", 
              "Args: {}".format(" ".join(script_arg_list)),
              "", sep="\n")
        input("Press enter to continue ")
    
    return subproc

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Setup

# Provide warning if running in Spyder IDE, where subprocess call doesn't seem to work properly
spyder_catcher()

# Parse arguments
arg_selections = parse_args()
arg_camera_select = arg_selections.get("camera_select")
arg_user_select = arg_selections.get("user_select")
arg_task_select = arg_selections.get("task_select")
arg_video_select = arg_selections.get("video_select")

# ---------------------------------------------------------------------------------------------------------------------
#%% Ask user for base selections

# Select shared components
selector = Resource_Selector()
project_root_path, cameras_folder_path = selector.get_project_pathing()

# Select shared components
camera_select, camera_path = selector.camera(arg_camera_select)
user_select, user_path = selector.user(camera_select, arg_user_select)
task_select, task_path = selector.task(camera_select, user_select, arg_task_select)
video_select, video_path = selector.video(camera_select, arg_video_select)


# ---------------------------------------------------------------------------------------------------------------------
#%% Build shared pathing

# Get pathing to the configuration utilites
config_component_folder_path = os.path.join(project_root_path, "configuration_utilities", "core")

# Figure out stage ordering for present core options
stage_ordering = get_ordered_core_sequence()


# ---------------------------------------------------------------------------------------------------------------------
#%% *** MENU LOOP ***    

while True:
    
    # Have user select a core component
    clear_with_status(camera_select, user_select, task_select, video_select)
    req_break, req_continue, component_path, component_name = \
    user_select_component(config_component_folder_path, stage_ordering)
    if req_continue: continue
    if req_break: break

    # Have user select a component option
    clear_with_status(camera_select, user_select, task_select, video_select, component_name)
    req_break, req_continue, option_path, option_display_name = user_select_option(component_path, component_name)
    if req_continue: continue
    if req_break: break

    # Hide all the selection mess before launching into the configuration utility
    clear_terminal(0, 0.25)

    # If we get this far, run whatever component option was selected
    return_code = run_config_utility(option_path, camera_select, user_select, task_select, video_select)  # Blocking
    sleep(0.25)

# Some final cleanup feedback
print("", "{} closed...".format(os.path.basename(__file__)), "", sep="\n")

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap

'''
STOPPED HERE
- FIGURE OUT WHY IMPORT CV2 FAILS FROM SPYDER... SEEMS TO BE USING THE WRONG ENV
'''



