#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Jun 23 09:11:16 2020

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

import datetime as dt

from local.lib.common.timekeeper_utils import get_local_datetime

from local.lib.ui_utils.cli_selections import Resource_Selector
from local.lib.ui_utils.editor_lib import select_from_list, prompt_with_defaults, confirm, quit_if_none

from local.lib.file_access_utils.video import add_video_to_files_dict
from local.lib.file_access_utils.video import delete_video_in_files_dict
from local.lib.file_access_utils.video import rename_video_in_files_dict
from local.lib.file_access_utils.video import change_video_start_datetime
from local.lib.file_access_utils.video import change_video_timelapse_factor

from local.eolib.utils.ranger_tools import ranger_multifile_select, ranger_exists, ranger_preprompt
from local.eolib.utils.gui_tools import gui_file_select_many, tkinter_exists
from local.eolib.utils.quitters import ide_quit


# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

# .....................................................................................................................

def prompt_for_file_selection(enable_ranger = True, enable_tkiner = True):
    
    # Initialize output
    selected_video_files_list = []
    
    # Use ranger if possible, otherwise try tkinter otherwise prompt for direct path input
    # -> This is safest approach, in case using a remote system where GUI isn't accessible (even if tkinter exists)
    if enable_ranger and ranger_exists():
        ranger_msg_list = ["Please use ranger to select one or more video files",
                           "  - Use enter to confirm selection",
                           "  - Use spacebar to select more than one file", 
                           "  - Use q to exit ranger without a selection", ""]
        ranger_preprompt("\n".join(ranger_msg_list))
        selected_video_files_list = ranger_multifile_select()
    
    elif enable_ranger and tkinter_exists():
        selected_video_files_list = gui_file_select_many(window_title = "Select one or more video files")
    
    else:
        selected_video_file = prompt_with_defaults("Enter path to video file: ",
                                                   default_value = "~/",
                                                   return_type = str,
                                                   response_on_newline = False)        
        quit_if_none(selected_video_file, "No video path provided!")
        expanded_selected_video_file = os.path.expanduser(selected_video_file)
        selected_video_files_list = [expanded_selected_video_file]
    
    return selected_video_files_list

# .....................................................................................................................

def prompt_for_video_rename(location_select_folder_path, camera_select, video_select):
    
    # Prompt for new name entry
    user_new_name = prompt_with_defaults("Enter new video name: ",
                                         default_value = video_select,
                                         return_type = str)
    
    # Check if the user just picked the default (in which case, don't both trying to rename!)
    no_change_to_name = (user_new_name == video_select)
    if no_change_to_name:
        return
    
    # If we get here, the user entered a difference name from default, so update it!
    rename_video_in_files_dict(location_select_folder_path, camera_select, video_select, user_new_name)

# .....................................................................................................................

def prompt_for_new_start_datetime(location_select_folder_path, camera_select, video_select):
    
    # Use the local time to set the default values
    current_dt = get_local_datetime()
    date_format = "%Y/%m/%d"
    time_format = "%H:%M:%S"
    tzinfo_format = "%z"
    
    # Set defaults to provide user with proper formatting
    default_start_date_str = current_dt.strftime(date_format)
    default_start_time_str = current_dt.strftime(time_format)
    default_start_tzinfo_str = current_dt.strftime(tzinfo_format)
    
    # Ask the user for timing inputs
    user_start_date = prompt_with_defaults("               Enter start date: ",
                                           default_value = default_start_date_str,
                                           return_type = str)
    check_for_dt_parsing_errors(user_start_date, date_format)
    
    user_start_time = prompt_with_defaults("               Enter start time: ",
                                           default_value = default_start_time_str,
                                           return_type = str)
    check_for_dt_parsing_errors(user_start_time, time_format)
    
    user_start_tzinfo = prompt_with_defaults("Enter start timezone UTC offset: ",
                                             default_value = default_start_tzinfo_str,
                                             return_type = str)
    check_for_dt_parsing_errors(user_start_tzinfo, tzinfo_format)
    
    # Bundle together all the user-entered time info to build full start datetime object
    full_datetime_str = "{} {} {}".format(user_start_date, user_start_time, user_start_tzinfo)
    full_format_str = "{} {} {}".format(date_format, time_format, tzinfo_format)
    full_dt = dt.datetime.strptime(full_datetime_str, full_format_str)
    
    # Update the video entry and provide some feedback
    old_value, new_value = change_video_start_datetime(location_select_folder_path, 
                                                       camera_select, 
                                                       video_select,
                                                       full_dt)
    
    # Provide some feedback
    print("",
          "Done! Updated {} ({})".format(video_select, camera_select),
          "  old: {}".format(old_value),
          "  new: {}".format(new_value),
          "",
          sep = "\n")
    
    return

# .....................................................................................................................

def prompt_for_new_timelapse_factor(location_select_folder_path, camera_select, video_select):
    
    # Ask the user for new timelapse factor
    user_timelapse_factor = prompt_with_defaults("Enter new timelapse factor: ",
                                                 default_value = 1.0,
                                                 return_type = float)
    
    # Update the video entry and provide some feedback
    old_value, new_value = change_video_timelapse_factor(*pathing_args, user_timelapse_factor)
    print("",
          "Done! Updated {} ({})".format(video_select, camera_select),
          "  {}  ->  {}".format(old_value, new_value),
          "",
          sep = "\n")
    
    return

# .....................................................................................................................

def check_for_dt_parsing_errors(input_dt_string, parse_format, quit_on_error = True):
    
    ''' Helper function used to check for date/time format parsing errors '''
    
    parse_succeed = False
    try:
        dt.datetime.strptime(input_dt_string, parse_format)
        parse_succeed = True
    
    except ValueError:
        print("",
              "Error parsing: {}".format(input_dt_string),
              "Doesn't match expected format!",
              "", sep = "\n")
        if quit_on_error:
            ide_quit()
    
    return parse_succeed

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Get pathing

# Set up resource selector
selector = Resource_Selector(load_selection_history = True,
                             save_selection_history = True,
                             show_hidden_resources = False,
                             create_folder_structure_on_select = True)

# Get important pathing & select location
project_root_path, all_locations_folder_path = selector.get_shared_pathing()
location_select, location_select_folder_path = selector.location()


# ---------------------------------------------------------------------------------------------------------------------
#%% Provide top-level options

# Prompt for options
new_option = "New"
update_option = "Update"
delete_option = "Delete"
options_menu_list = [new_option, update_option, delete_option]
select_idx, select_entry = select_from_list(options_menu_list,
                                            prompt_heading = "Select an option (videos)",
                                            default_selection = None)

# For convenience/clarity
selected_new = (select_entry == new_option)
selected_update = (select_entry == update_option)
selected_delete = (select_entry == delete_option)


# ---------------------------------------------------------------------------------------------------------------------
#%% Handle 'New' selection

if selected_new:
    
    # First ask user to select a camera
    camera_select, camera_path = selector.camera(location_select)
    
    # Prompt to select video(s)
    selected_video_paths_list = prompt_for_file_selection()
    
    # Add video file(s) to record
    success_names_list = []
    for each_video_path in selected_video_paths_list:
        
        # Check that each path points to a valid video file
        expanded_path = os.path.expanduser(each_video_path)
        is_valid_file = os.path.isfile(expanded_path)
        if not is_valid_file:
            print("", "Error adding video. Not a valid file path!", "@ {}".format(expanded_path), sep = "\n")
            continue
        
        # If we get here the path is valid so add it
        new_video_name = add_video_to_files_dict(location_select_folder_path, camera_select, expanded_path)
        success_names_list.append(new_video_name)
    
    # Provide some feedback
    num_videos_added = len(success_names_list)
    added_videos = (num_videos_added > 0)
    if added_videos:
        print("", "Done! Videos added:",
              *("  {}".format(each_name) for each_name in success_names_list),
              "", sep = "\n")
    
    # If only one video was added, save it as the default selection for convenience
    exactly_one_video_added = (num_videos_added == 1)
    if exactly_one_video_added:
        video_name = success_names_list[0]
        selector.save_video_select(video_name)
    
    # Save selected camera as default selection for convenience
    selector.save_camera_select(camera_select)


# ---------------------------------------------------------------------------------------------------------------------
#%% Handle 'Update' selection

if selected_update:
    
    # Ask user to select a camera & video to update
    camera_select, _ = selector.camera(location_select)
    video_select, _ = selector.video(location_select, camera_select)
    
    # Provide prompt to select what to update
    rename_option = "Rename"
    start_dt_option = "Video start timing"
    timelapse_option = "Timelapse factor"
    options_menu_list = [rename_option, start_dt_option, timelapse_option]
    select_idx, select_entry = select_from_list(options_menu_list,
                                                prompt_heading = "What would you like to do?",
                                                default_selection = None)
    
    # For convenience
    selected_rename = (select_entry == rename_option)
    selected_startdt = (select_entry == start_dt_option)
    selected_timelapse = (select_entry == timelapse_option)
    pathing_args = (location_select_folder_path, camera_select, video_select)
    
    # Handle different update options
    if selected_rename:
        prompt_for_video_rename(*pathing_args)
    elif selected_startdt:
        prompt_for_new_start_datetime(*pathing_args)
    elif selected_timelapse:
        prompt_for_new_timelapse_factor(*pathing_args)
    
    # Save selected camera & video as default selection for convenience
    selector.save_camera_select(camera_select)
    selector.save_video_select(video_select)


# ---------------------------------------------------------------------------------------------------------------------
#%% Handle 'Delete' selection

if selected_delete:
    
    # Ask user to select a camera & video to delete
    camera_select, _ = selector.camera(location_select)
    video_select, video_path = selector.video(location_select, camera_select)
    
    # Confirm with user that they want to delete the selected video
    user_confirm = confirm("Are you sure you want to delete {}?".format(video_select), default_response = False)
    if user_confirm:
        is_local_video, video_path = delete_video_in_files_dict(location_select_folder_path,
                                                                camera_select,
                                                                video_select)
        
        # Provide some feedback
        print("", "Done! Removed {} from video listing".format(video_select), "@ {}".format(video_path), sep = "\n")
    
    pass


# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap

