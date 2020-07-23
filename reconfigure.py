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
from local.lib.ui_utils.script_arguments import script_arg_builder, get_selections_from_script_args

from local.lib.file_access_utils.configurables import unpack_config_data, unpack_access_info
from local.lib.file_access_utils.core import get_ordered_core_sequence, build_core_folder_path
from local.lib.file_access_utils.externals import build_externals_folder_path
from local.lib.file_access_utils.stations import build_station_config_folder_path
from local.lib.file_access_utils.json_read_write import load_config_json

from local.eolib.utils.files import get_file_list, get_folder_list
from local.eolib.utils.cli_tools import cli_confirm, cli_select_from_list, clear_terminal


# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes

# .....................................................................................................................

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Define misc functions

# .....................................................................................................................

def parse_recon_args(debug_print = False):
    
    # Set script arguments for running files
    args_list = ["location", "camera", "video"]
    
    # Provide some extra information when accessing help text
    script_description = "Hub script for launching reconfiguration scripts"
    
    # Build & evaluate script arguments!
    ap_result = script_arg_builder(args_list,
                                   description = script_description,
                                   parse_on_call = True,
                                   debug_print = debug_print)
    
    return ap_result

# .....................................................................................................................

def clear_with_status(first_select = None):
    
    ''' Function which clears the terminal, then prints the current selection status '''
    
    clear_terminal()
    
    # Build output text
    num_seperator_symbols = 48
    seperator_gfx = "=" * num_seperator_symbols
    print_strs = [seperator_gfx,
                  "Current selections:",
                  "  Location: {}".format(LOCATION_SELECT),
                  "    Camera: {}".format(CAMERA_SELECT),
                  "     Video: {}".format(VIDEO_SELECT),
                  "  Category: {}".format(CATEGORY_SELECT),
                  seperator_gfx]
    
    # Add stage selection info, if present
    if first_select is not None:
        stage_display_name = pretty_menu_name(first_select)
        stage_str_length = len(stage_display_name)
        left_centering_offset = int(max(0, (num_seperator_symbols + stage_str_length) / 2))
        print_strs += [stage_display_name.rjust(left_centering_offset), seperator_gfx]
        
    # Show current selection info
    print(*print_strs, sep="\n")
    
    # Hang for a sec to prevent accidental selections
    sleep(0.1)
    
# .....................................................................................................................

def pretty_menu_name(menu_name):
    return menu_name.replace("_", " ").replace(".py", "").title()

# .....................................................................................................................

def set_passthru_ordering(entry_list, passthrough_label = "passthrough.py"):
    
    # Create new list for output, so we don't modify the original
    ordered_entry_list = entry_list.copy()
    
    # Re-order so that passthroughs appear as the first entry
    passthrough_in_list = (passthrough_label in entry_list)
    if passthrough_in_list:
        pass_idx = entry_list.index(passthrough_label)
        ordered_entry_list.pop(pass_idx)
        ordered_entry_list = [passthrough_label] + ordered_entry_list
    
    return ordered_entry_list

# .....................................................................................................................

def run_config_utility(config_utility_path):
    
    # Build arguments to pass to each config utility
    script_arg_list = ["-l", LOCATION_SELECT, "-c", CAMERA_SELECT, "-v", VIDEO_SELECT]
    
    # Get python interpretter path, so we call subprocess using the same environment
    python_interpretter = sys.executable
    
    # Launch selected configuration utility using direct path to the script
    run_command_list = [python_interpretter, config_utility_path] + script_arg_list    
    subproc = subprocess.run(run_command_list)
    
    # Present errors to user
    got_subprocess_error = (subproc.returncode != 0)
    if got_subprocess_error:
        print("",
              "ERROR running configuration utility!",
              "@ {}".format(config_utility_path),
              "", 
              "Args: {}".format(" ".join(script_arg_list)),
              "",
              "Subprocess:",
              subproc,
              "", sep="\n")
    
    # Pause after running the configuration utility, to give the user a chance to see terminal output
    req_break = False
    try:
        input("Press enter to return to the configuration menu\n")
        
    except KeyboardInterrupt:
        req_break = True
    
    return req_break, subproc

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Define pathing functions

# .....................................................................................................................

def build_path_to_config_utils(project_root_path, utility_type):
    ''' Helper function for building pathing to configuration utilities folders '''
    return os.path.join(project_root_path, "configuration_utilities", utility_type)

# .....................................................................................................................

def get_util_scripts_list(*path_joins):
    
    # First build the path to the location of the script options
    scripts_folder_path = os.path.join(*path_joins)
    
    script_names_list = get_file_list(scripts_folder_path,
                                      show_hidden_files = True,
                                      sort_list = True,
                                      return_full_path = False)
    
    # Re-order the script names if there is a passthrough option (so that it appears at the top)
    ordered_script_names_list = set_passthru_ordering(script_names_list)
    
    return ordered_script_names_list

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Define info loading functions

# .....................................................................................................................

def load_core_menu_info(project_root_path, location_select_folder_path):
    
    # Get pathing to the configuration utilites
    utility_parent_folder = build_path_to_config_utils(project_root_path, "core")
    
    # Figure out stage ordering for presenting the core stage options
    stage_ordering = get_ordered_core_sequence()
    
    # Get pathing to the corresponding config files for the selected camera
    configs_folder_path = build_core_folder_path(location_select_folder_path, CAMERA_SELECT)
    
    return utility_parent_folder, stage_ordering, configs_folder_path

# .....................................................................................................................

def load_stations_menu_info(project_root_path, location_select_folder_path):
    
    # Get pathing to the configuration utilites
    utility_parent_folder = build_path_to_config_utils(project_root_path, "stations")
    
    # Figure out ordering for presenting the station options
    option_ordering = get_file_list(utility_parent_folder, sort_list = True)
    
    # Get pathing to the corresponding config files for the selected camera
    configs_folder_path = build_station_config_folder_path(location_select_folder_path, CAMERA_SELECT)
    
    return utility_parent_folder, option_ordering, configs_folder_path

# .....................................................................................................................

def load_externals_menu_info(project_root_path, location_select_folder_path):
    
    # Get pathing to the configuration utilites
    utility_parent_folder = build_path_to_config_utils(project_root_path, "externals")
    
    # Figure out stage ordering for presenting the externals stage options
    stage_ordering = get_folder_list(utility_parent_folder, sort_list = True)
    
    # Get pathing to the corresponding config files for the selected camera
    configs_folder_path = build_externals_folder_path(location_select_folder_path, CAMERA_SELECT)
    
    return utility_parent_folder, stage_ordering, configs_folder_path

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Define menu functions

# .....................................................................................................................

def menu_select(prompt_msg, entry_list, default_selection = None):
    
    ''' Helper function which wraps the cli menu selection to provide better error handling '''
    
    # Initialize outputs
    selection_error = False
    selection_empty = False
    selection_cancelled = False
    selected_name = None
    
    # Convert names to 'pretty' format for display
    pretty_entry_list = [pretty_menu_name(each_entry) for each_entry in entry_list]
    pretty_default = pretty_menu_name(default_selection) if default_selection is not None else None
    
    try:
        # Get user to select entry from the menu, then convert back to original input name
        select_idx, _ = cli_select_from_list(pretty_entry_list, prompt_msg, pretty_default)
        selected_name = entry_list[select_idx]
        
    except KeyboardInterrupt:
        selection_cancelled = True
    
    # No selection is made
    except ValueError:
        selection_empty = True
    
    # Selected numeric entry that isn't in the list
    except IndexError:
        selection_error = True
    
    # Probably an input error (e.g. non-numeric input) also happens from queued up entries
    except NameError:
        selection_error = True
    
    return selection_error, selection_cancelled, selection_empty, selected_name

# .....................................................................................................................
    
def menu_select_loop_on_error(prompt_msg, entry_list, default_selection = None, clear_text = True):
    
    ''' Helper function which continues providing menu selection on input errors '''
    
    s_err = False
    keep_looping = True
    while keep_looping:
        
        # Clear if needed
        if clear_text:
            clear_with_status()
        
        # Provide some feedback about why the menu is looping!
        if s_err:
            print("", "Input error! Must enter a number matching an entry in the list", sep = "\n")
        
        # Prompt with menu selection
        s_err, s_cancel, s_empty, selected_name = menu_select(prompt_msg, entry_list, default_selection)
        keep_looping = s_err
    
    return s_cancel, s_empty, selected_name

# .....................................................................................................................

def ask_to_quit_menu(clear_terminal_if_no_quit = True):
    
    ''' Helper function which provides a quit prompt '''
    
    quit_menu = cli_confirm("Quit?")
    if not quit_menu and clear_terminal_if_no_quit:
        clear_terminal(0, 0.1)
    
    return quit_menu

# .....................................................................................................................

def get_script_name_from_config_file(configs_folder_path, parent_select):

    ''' Function used to get the default script selection '''
    
    # Build pathing to existing config file
    existing_config_file_name = "{}.json".format(parent_select)
    existing_config_file_path = os.path.join(configs_folder_path, existing_config_file_name)
    
    # If an existing config file isn't found, return no default
    no_existing_config_file = (not os.path.exists(existing_config_file_path))
    if no_existing_config_file:
        return None
    
    # If a file does exist, try to extract the configuration utility used to construct it
    config_data_dict = load_config_json(existing_config_file_path)
    access_info_dict, _ = unpack_config_data(config_data_dict)
    _, _, previous_config_util_used = unpack_access_info(access_info_dict)
    
    return previous_config_util_used

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Setup

# Parse arguments
arg_selections = parse_recon_args()
arg_location_select, arg_camera_select, arg_video_select = get_selections_from_script_args(arg_selections)


# ---------------------------------------------------------------------------------------------------------------------
#%% Ask for base selections

# Get important pathing
selector = Resource_Selector()
project_root_path = selector.get_project_root_pathing()

# Get data to run
LOCATION_SELECT, location_select_folder_path = selector.location(arg_location_select)
CAMERA_SELECT, camera_path = selector.camera(LOCATION_SELECT, arg_camera_select)
VIDEO_SELECT, video_path = selector.video(LOCATION_SELECT, CAMERA_SELECT, arg_video_select)


# ---------------------------------------------------------------------------------------------------------------------
#%% Prompt to select configurable type

# Build menu for which type of configurable we want to reconfigure
core_option = "Core"
stations_option = "Stations"
externals_option = "Externals"
category_menu_list = [core_option, stations_option, externals_option]

# Prompt user to select a configuration option
s_cancel, s_empty, CATEGORY_SELECT = \
menu_select_loop_on_error("Select category:", category_menu_list, clear_text = False)

# For convenience/clarity
selected_core = (CATEGORY_SELECT == core_option)
selected_stations = (CATEGORY_SELECT == stations_option)
selected_externals = (CATEGORY_SELECT == externals_option)


# ---------------------------------------------------------------------------------------------------------------------
#%% *** CORE MENU LOOP ***

# Handle core menus
while selected_core:

    # Load data for handling core menu options
    core_util_parent_folder, core_stage_ordering, core_configs_folder_path = \
    load_core_menu_info(project_root_path, location_select_folder_path)
    
    # Select which core stage to re-configure
    s_cancel, s_empty, select_stage_name = \
    menu_select_loop_on_error("Select core stage:", core_stage_ordering)
    
    # Handle quitting
    if s_cancel:
        break
    
    # Handle empty selection (ask to quit or reset to core stage menu)
    if s_empty:
        confirm_quit = ask_to_quit_menu()
        if confirm_quit: break
        else:            continue
    
    # Figure out which option should be default (if any)
    core_stage_default = get_script_name_from_config_file(core_configs_folder_path, select_stage_name)
    
    # Select which option from the selected stage to load
    script_options_list = get_util_scripts_list(core_util_parent_folder, select_stage_name)
    s_cancel, s_empty, select_script_name = \
    menu_select_loop_on_error("Select option:", script_options_list, core_stage_default)
    
    # Handle empty selection (reset to core stage menu)
    if s_empty or s_cancel:
        clear_terminal(0, 0.1)
        continue
    
    # If we get this far, run whatever config utility was selected
    selected_script_path = os.path.join(core_util_parent_folder, select_stage_name, select_script_name)
    req_break, return_code = run_config_utility(selected_script_path)  # Blocking
    if req_break:
        break
    sleep(0.15)


# ---------------------------------------------------------------------------------------------------------------------
#%% *** STATIONS MENU LOOP ***

# Handle stations menus
while selected_stations:
        
    # Load data for handle stations menu option
    stn_util_parent_folder, stn_option_ordering, stn_configs_folder_path = \
    load_stations_menu_info(project_root_path, location_select_folder_path)
    
    # Select which type of station to re-configure
    s_cancel, s_empty, select_script_name = \
    menu_select_loop_on_error("Select station:", stn_option_ordering)
    
    # Handle quitting
    if s_cancel:
        break
    
    # Handle empty selection (ask to quit or reset to stations menu)
    if s_empty:
        confirm_quit = ask_to_quit_menu()
        if confirm_quit: break
        else:            continue
    
    # If we get this far, run whatever config utility was selected
    selected_script_path = os.path.join(stn_util_parent_folder, select_script_name)
    req_break, return_code = run_config_utility(selected_script_path)  # Blocking
    if req_break:
        break
    sleep(0.15)


# ---------------------------------------------------------------------------------------------------------------------
#%% *** EXTERNALS MENU LOOP ***

# Handle externals menus
while selected_externals:
    
    # Load data for handling externals menu option
    ext_util_parent_folder, ext_stage_ordering, ext_configs_folder_path = \
    load_externals_menu_info(project_root_path, location_select_folder_path)
    
    # Select which external type to re-configure
    s_cancel, s_empty, select_type_name = \
    menu_select_loop_on_error("Select external type:", ext_stage_ordering)
    
    # Handle quitting
    if s_cancel:
        break
    
    # Handle empty selection (ask to quit or reset to external type menu)
    if s_empty:
        confirm_quit = ask_to_quit_menu()
        if confirm_quit: break
        else:            continue
    
    # Figure out which option should be default (if any)
    external_type_default = get_script_name_from_config_file(ext_configs_folder_path, select_type_name)
    
    # Select which option from the selected stage to load
    script_options_list = get_util_scripts_list(ext_util_parent_folder, select_type_name)
    s_cancel, s_empty, select_script_name = \
    menu_select_loop_on_error("Select option:", script_options_list, external_type_default)
    
    # Handle empty selection (reset to external type menu)
    if s_empty or s_cancel:
        clear_terminal(0, 0.1)
        continue
    
    # If we get this far, run whatever config utility was selected
    selected_script_path = os.path.join(ext_util_parent_folder, select_type_name, select_script_name)
    req_break, return_code = run_config_utility(selected_script_path)  # Blocking
    if req_break:
        break
    sleep(0.15)


# ---------------------------------------------------------------------------------------------------------------------
#%% Clean up

# Some final cleanup feedback
print("", "{} closed...".format(os.path.basename(__file__)), "", sep = "\n")


# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap

# TODO
# - re-arrange station menus, so that existing configs + 'create new' menu appears first?
#   - if existing config chosen, immediately load corresponding script
#   - if 'create new' is chosen, then prompt with another menu for station type
