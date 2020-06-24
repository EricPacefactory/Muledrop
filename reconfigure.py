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

from local.lib.ui_utils.cli_selections import Resource_Selector
from local.lib.ui_utils.script_arguments import script_arg_builder

from local.lib.file_access_utils.externals import build_externals_folder_path
from local.lib.file_access_utils.core import get_ordered_core_sequence, build_core_folder_path
from local.lib.file_access_utils.json_read_write import load_config_json

from local.eolib.utils.files import get_file_list, get_folder_list
from local.eolib.utils.cli_tools import cli_confirm, cli_select_from_list, clear_terminal, clean_error_quit

# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes

# .....................................................................................................................

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

# .....................................................................................................................

def parse_recon_args(debug_print = False):
    
    # Set script arguments for running files
    args_list = ["camera",
                 "video"]
    
    # Provide some extra information when accessing help text
    script_description = "Hub script for launching reconfiguration scripts"
    
    # Build & evaluate script arguments!
    ap_obj = script_arg_builder(args_list,
                                description = script_description,
                                parse_on_call = False,
                                debug_print = debug_print)
    
    
    # Add script argument for selecting externals config
    ap_obj.add_argument("-e", "--externals", default = False, action = "store_true",
                        help = "Reconfigure externals instead of core stages")
    
    # Get arg inputs into a dictionary
    ap_result = vars(ap_obj.parse_args())
    
    return ap_result

# .....................................................................................................................

def clear_with_status(camera_select, video_select, stage_select = None):
    
    ''' Function which clears the terminal, then prints the current selection status '''
    
    clear_terminal()
    
    # Build output text
    num_seperator_symbols = 48
    seperator_gfx = "=" * num_seperator_symbols
    print_strs = [seperator_gfx,
                  "Current selections:",
                  "  Camera: {}".format(camera_select),
                  "   Video: {}".format(video_select),
                  seperator_gfx]
    
    # Add stage selection info, if present
    if stage_select is not None:
        stage_display_name = clean_stage_name(stage_select)
        stage_str_length = len(stage_display_name)
        left_centering_offset = int(max(0, (num_seperator_symbols + stage_str_length) / 2))
        print_strs += [stage_display_name.rjust(left_centering_offset), seperator_gfx]
        
    # Show current selection info
    print(*print_strs, sep="\n")
    
    # Hang for a sec to prevent accidental selections
    sleep(0.5)

# .....................................................................................................................

def load_externals_info(project_root_path, cameras_folder_path):
    
    # Get pathing to the configuration utilites
    utility_parent_folder = os.path.join(project_root_path, "configuration_utilities", "externals")
    
    # Figure out stage ordering for presenting the externals stage options
    stage_ordering = get_folder_list(utility_parent_folder, sort_list = True)
    
    # Get pathing to the corresponding config files for the selected camera
    configs_folder_path = build_externals_folder_path(cameras_folder_path, camera_select)
    
    return utility_parent_folder, stage_ordering, configs_folder_path

# .....................................................................................................................

def load_core_info(project_root_path, cameras_folder_path):
    
    # Get pathing to the configuration utilites
    utility_parent_folder = os.path.join(project_root_path, "configuration_utilities", "core")
    
    # Figure out stage ordering for presenting the core stage options
    stage_ordering = get_ordered_core_sequence()
    
    # Get pathing to the corresponding config files for the selected camera
    configs_folder_path = build_core_folder_path(cameras_folder_path, camera_select)
    
    return utility_parent_folder, stage_ordering, configs_folder_path

# .....................................................................................................................

def clean_stage_name(stage_name):
    return stage_name.replace("_", " ").title()

# .....................................................................................................................

def clean_option_name(option_name):
    return option_name.replace(".py", "").replace("_", " ").title()

# .....................................................................................................................

def _select_stage(utility_parent_folder, ordered_stage_names):
    
    # Clean up list for readability
    clean_stage_list = [clean_stage_name(each_stage) for each_stage in ordered_stage_names]
    select_idx, _ = cli_select_from_list(clean_stage_list, 
                                         prompt_heading = "Select stage:")
    
    # Build the full pathing
    stage_select = ordered_stage_names[select_idx]
    stage_folder_path = os.path.join(utility_parent_folder, stage_select)
    
    return stage_folder_path, stage_select

# .....................................................................................................................

def _select_stage_option(stage_folder_path, stage_select, default_stage_option = None):
    
    # Get all options (scripts) at the given stage path
    options_list = get_file_list(stage_folder_path, return_full_path = False)
    
    # Error if there are no options to display, this is likely an interal error with pathing...
    if len(options_list) < 1:
        print("", "!"*36, "Searched path:", "@ {}".format(stage_folder_path), "!"*36, "", sep="\n")
        raise AttributeError("No options found for stage: {}".format(stage_select))
    
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
        
    # Convert stage name to display friendly format
    stage_display_name = clean_stage_name(stage_select)
    default_display_name = clean_option_name(default_stage_option)
    
    # Prompt user to select the stage option
    prompt_msg = "Select {} option:".format(stage_display_name.lower())
    select_idx, option_display_name = cli_select_from_list(clean_options_list, 
                                                           default_selection = default_display_name,
                                                           default_indicator = "(current)",
                                                           prompt_heading = prompt_msg,
                                                           zero_indexed = passthrough_in_list)
    
    
    # Build outputs
    option_select = options_list[select_idx]
    option_path = os.path.join(stage_folder_path, option_select)
    
    return option_path, option_select

# .....................................................................................................................

def get_default_option(configs_folder_path, stage_select):

    # Build pathing to existing config file (for the selected stage)
    existing_config_file_name = "{}.json".format(stage_select)
    existing_config_file_path = os.path.join(configs_folder_path, existing_config_file_name)
    
    # If an existing config file isn't found, return no default
    no_existing_config_file = (not os.path.exists(existing_config_file_path))
    if no_existing_config_file:
        return None
    
    # If a file does exist, try to extract the configuration utility used to construct it
    config_data = load_config_json(existing_config_file_path)
    file_access_dict = config_data.get("access_info", {})
    previous_config_util_used = file_access_dict.get("configuration_utility", None)
    
    return previous_config_util_used

# .....................................................................................................................

@clean_error_quit
def ui_select_stage(utility_parent_folder_path, stage_ordering):
    
    # Initialize outputs
    request_break = False
    request_continue = False
    stage_folder_path = None
    stage_display_name = None
    
    # Present stage selection menu
    try:
        stage_folder_path, stage_display_name = _select_stage(utility_parent_folder_path, stage_ordering)
    
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
        
    return request_break, request_continue, stage_folder_path, stage_display_name

# .....................................................................................................................

@clean_error_quit
def ui_select_stage_option(stage_folder_path, stage_display_name, default_stage_option):
    
    # Initialize outputs
    request_break = False
    request_continue = False
    option_path = None
    option_display_name = None
    
    # Present options menu
    try:
        option_path, option_display_name = _select_stage_option(stage_folder_path,
                                                                stage_display_name,
                                                                default_stage_option)
    
    # Cancel option select if no selection is made (return to stage select)
    except ValueError:
        # Some feedback before returning to stage select
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

def run_config_utility(camera_select, video_select, option_path):
    
    # Build arguments to pass to each config utility
    script_arg_list = ["-c", camera_select,
                       "-v", video_select]
    
    # Get python interpretter path, so we call subprocess using the same environment
    python_interpretter = sys.executable
    
    # Launch selected config util ity using direct path to option script
    run_command_list = [python_interpretter, option_path] + script_arg_list    
    subproc = subprocess.run(run_command_list)
    
    # Hang on to errors
    if subproc.returncode != 0:
        print("",
              "ERROR running configuration utility!",
              "@ {}".format(option_path),
              "", 
              "Args: {}".format(" ".join(script_arg_list)),
              "",
              "Subprocess:",
              subproc,
              "", sep="\n")
        input("Press enter to continue ")
    
    return subproc

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Setup

# Parse arguments
arg_selections = parse_recon_args()
arg_camera_select = arg_selections.get("camera", None)
arg_video_select = arg_selections.get("video", None)
arg_enable_externals = arg_selections.get("externals", None)

# ---------------------------------------------------------------------------------------------------------------------
#%% Ask for base selections

# Get shared pathing
selector = Resource_Selector()
project_root_path, cameras_folder_path = selector.get_cameras_root_pathing()

# Get camera/video selections
camera_select, camera_path = selector.camera(arg_camera_select)
video_select, video_path = selector.video(camera_select, arg_video_select)


# ---------------------------------------------------------------------------------------------------------------------
#%% Build shared pathing

utility_parent_folder, stage_ordering, configs_folder_path = load_core_info(project_root_path, cameras_folder_path)
if arg_enable_externals:
    utility_parent_folder, stage_ordering, configs_folder_path = load_externals_info(project_root_path,
                                                                                     cameras_folder_path)


# ---------------------------------------------------------------------------------------------------------------------
#%% *** MENU LOOP ***    

while True:
    
    # Have user select a stage
    clear_with_status(camera_select, video_select)
    req_break, req_continue, stage_folder_path, stage_select = ui_select_stage(utility_parent_folder, 
                                                                               stage_ordering)
    if req_continue: continue
    if req_break: break

    # Get default stage option selection (if one exists!)
    default_stage_option = get_default_option(configs_folder_path, stage_select)

    # Have user select a stage option
    clear_with_status(camera_select, video_select, stage_select)
    req_break, req_continue, option_path, option_display_name = ui_select_stage_option(stage_folder_path, 
                                                                                       stage_select, 
                                                                                       default_stage_option)
    if req_continue: continue
    if req_break: break
    
    # Hide all the selection mess before launching into the configuration utility
    clear_terminal(0, 0.25)

    # If we get this far, run whatever stage option was selected
    return_code = run_config_utility(camera_select, video_select, option_path)  # Blocking
    sleep(0.25)
    

# Some final cleanup feedback
print("", "{} closed...".format(os.path.basename(__file__)), "", sep="\n")

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap

# TODO
# - Figure out why closing scripts fails from Spyder... Seems to be due to input() function?

