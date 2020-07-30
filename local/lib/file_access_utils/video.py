#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Apr 12 12:49:38 2019

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

from shutil import copy2 as copy_with_metadata

from local.lib.common.timekeeper_utils import datetime_to_isoformat_string

from local.lib.file_access_utils.shared import build_resources_folder_path, url_safe_name
from local.lib.file_access_utils.json_read_write import load_or_create_config_json, update_config_json, save_config_json

from local.eolib.utils.network import build_rtsp_string, check_valid_ip
from local.eolib.utils.files import replace_user_home_pathing
from local.eolib.utils.quitters import ide_quit


# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes 

class Playback_Access:
    
    # .................................................................................................................
    
    def __init__(self, location_select_folder_path, camera_select, video_select,
                 playback_settings_file = "playback_settings.json"):
        
        # Store pathing info
        self.location_select_folder_path = location_select_folder_path
        self.camera_select = camera_select
        self.video_select = video_select
        self.playback_file_name = playback_settings_file
        
        # Build pathing to the playback settings file
        self.settings_file_path = build_videos_folder_path(location_select_folder_path,
                                                           camera_select,
                                                           playback_settings_file)
    
    # .................................................................................................................
    
    def load_settings(self):
        
        # Load from the playback settings file
        playback_settings_dict = load_or_create_config_json(self.settings_file_path,
                                                            default_content = {},
                                                            creation_printout = "Creating playback settings file:")
        
        # Initialize output results
        frame_index = start_loop_index = end_loop_index = frame_delay_ms = None
        
        # If the selected video has settings, check if they're valid
        settings_exist = (self.video_select in playback_settings_dict)
        if settings_exist:
            
            # Grab settings for the selected video
            video_settings_dict = playback_settings_dict[self.video_select]
            
            # Grab settings into more readable format
            frame_index = video_settings_dict.get("frame_index", 0)
            start_loop_index = video_settings_dict.get("start_loop_index", 0)
            end_loop_index = video_settings_dict.get("end_loop_index", 100)
            frame_delay_ms = video_settings_dict.get("frame_delay_ms", 1)
        
        # Bundle output settings for compactness
        settings_tuple = (frame_index, start_loop_index, end_loop_index, frame_delay_ms)
        
        return settings_exist, settings_tuple
    
    # .................................................................................................................
    
    def save_settings(self, frame_index, start_loop_index, end_loop_index, frame_delay_ms,
                      print_feedback = True):
        
        # Bundle the settings data for saving
        new_settings_dict = {"frame_index": frame_index,
                             "start_loop_index": start_loop_index,
                             "end_loop_index": end_loop_index,
                             "frame_delay_ms": frame_delay_ms}        
        new_video_settings = {self.video_select: new_settings_dict}
        
        # Let the user know what was saved
        if print_feedback:
            print("",
                  "Playback settings saved! ({})".format(self.video_select),
                  "  F: {}".format(frame_index),
                  "  S: {}".format(start_loop_index),
                  "  E: {}".format(end_loop_index),
                  "  Frame Delay (ms): {}".format(frame_delay_ms),
                  "", sep="\n")
        
        return update_config_json(self.settings_file_path, new_video_settings)
    
    # .................................................................................................................
    # .................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Pathing functions

# .....................................................................................................................

def build_videos_folder_path(location_select_folder_path, camera_select, *path_joins):
    return build_resources_folder_path(location_select_folder_path, camera_select, "videos", *path_joins)

# .....................................................................................................................

def build_video_files_dict_path(location_select_folder_path, camera_select):
    return build_videos_folder_path(location_select_folder_path, camera_select, "video_files_record.json")

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Load & save functions

# .....................................................................................................................

def get_video_names_and_paths_lists(location_select_folder_path, camera_select, error_if_no_videos = True):
    
    ''' 
    Function which returns a list of video names and corresponding loading paths based on the 
    data stored in the video files dictionary.
    Note, this function expands user pathing (e.g. ~) and also builds full pathing to local video files.
    '''
    
    # Load video file data
    video_files_dict = load_video_files_dict(location_select_folder_path, camera_select)
    videos_folder_path = build_videos_folder_path(location_select_folder_path, camera_select)
    
    # Pull out the full paths to each video file
    invalid_paths_list = []
    video_names_list = []
    video_paths_list = []
    for each_video_name, each_video_data in video_files_dict.items():
        
        # Get the video path, and expand it (if needed)
        video_path = each_video_data["path"]
        expanded_path = os.path.expanduser(video_path)
        
        # Add local directory pathing, if needed
        is_local_entry = check_entry_is_local(expanded_path)
        if is_local_entry:
            expanded_path = os.path.join(videos_folder_path, expanded_path)
            
        # If the path is not valid, save it to another list, which we'll only use if we don't find any valid paths
        invalid_path = (not os.path.exists(expanded_path))
        if invalid_path:
            invalid_paths_list.append(expanded_path)
            continue
        
        # If we get here, add the video name and pathing to the output lists!
        video_names_list.append(each_video_name)
        video_paths_list.append(expanded_path)
    
    # Raise an error if the resulting lists are empty or otherwise skip sorting if errors are disabled
    no_names = (len(video_names_list) == 0)
    no_paths = (len(video_paths_list) == 0)
    if (no_names or no_paths):
        if error_if_no_videos:
            
            # Provide error feedback
            print("", "No video files found for: {}".format(camera_select), sep = "\n")
            
            # Provide additional info about invalid video pathing if we display an error
            has_invalids = (len(invalid_paths_list) > 0)
            if has_invalids:
                print("", "Found invalid video path(s):", *invalid_paths_list, sep ="\n")
            
            # Finally, quit (safely)
            ide_quit()
            
        return video_names_list, video_paths_list
    
    # Finally, sort the video entries (by name) before returning data
    sorted_names_list, sorted_paths_list = zip(*sorted(zip(video_names_list, video_paths_list)))
    
    return sorted_names_list, sorted_paths_list

# .....................................................................................................................

def load_video_files_dict(location_select_folder_path, camera_select):
    
    '''
    This function loads data from the video listing file (located in the resources folder).
    Data is returned as a dictionary (matching the file contents)
    '''
    
    # Set the default content, in case the file doesn't exist when we try to load it
    default_files_dict = {}
    
    # Build pathing to the video file, then load it
    video_files_dict_path = build_video_files_dict_path(location_select_folder_path, camera_select)
    video_files_dict = load_or_create_config_json(video_files_dict_path, default_files_dict,
                                                  creation_printout = "Creating video file record:")    
    
    return video_files_dict

# .....................................................................................................................

def save_video_files_dict(location_select_folder_path, camera_select, new_video_files_dict):
    
    '''
    This function saves data to the video listing file (located in the resources folder).
    Note, the saving occurs by fully replacing the existing file!
    '''
    
    # Build pathing to the video file, then load it
    video_files_dict_path = build_video_files_dict_path(location_select_folder_path, camera_select)
    
    # Save the file, but make sure it's valid, so we don't mangle it if something goes wrong!
    save_path = save_config_json(video_files_dict_path, new_video_files_dict)
    
    return save_path

# .....................................................................................................................

def add_video_to_files_dict(location_select_folder_path, camera_select, new_video_path,
                            new_video_name = None,
                            new_start_datetime_isoformat = None,
                            new_timelapse_factor = 1):
    
    '''
    Function which adds new video entries to the video file dictionary
    Note, this function checks if the new video path/name are already taken.
    -> If a name is already taken, this function will raise a NameError
    -> If a path is already used, this function will raise an AttributeError
    
    Inputs:
        location_select_folder_path, camera_select -> (Strings) Pathing to a camera
        
        new_video_path -> (String) Pathing to the video file that should be added to the listing
        
        new_video_name -> (String or None) Name of video entry. If set to None,
                          the name will be taken as the file name from the provided video pathing
        
        new_start_datetime_isoformat -> (String or None) The start datetime of the video file, in isoformat.
                                        Can be set to None, which will use an default arbitrary datetime in the past
        
        new_timelapse_factor -> (Number) Can be used to indicate that a video runs faster than real-time.
                                Note that this number will scale the passage of time when running analysis on the file
    
    Outputs:
        added_video_name
    '''
    
    # If a name isn't provided, create one using the file name from the provided path
    if new_video_name is None:
        new_video_name = os.path.basename(new_video_path)
    
    # Clean name to ensure consistency. Also helps with detecting duplicates
    safe_video_name = url_safe_name(new_video_name)
    
    # Load existing video file data
    video_files_dict = load_video_files_dict(location_select_folder_path, camera_select)
    
    # Check that the video name isn't already in use
    name_in_use = (safe_video_name in video_files_dict.keys())
    if name_in_use:
        raise NameError("Error adding video: Video name already taken! ({})".format(safe_video_name))
    
    # Convert to 'local' pathing and/or remove user home pathing from the new video path, if needed
    is_local_path = check_path_is_local(location_select_folder_path, camera_select, new_video_path)
    if is_local_path:
        new_video_path = os.path.basename(new_video_path)
    new_video_path = replace_user_home_pathing(new_video_path)
    
    # Check that the video path isn't already in use
    existing_path = lambda video_name: video_files_dict.get(video_name, {}).get("path", None)
    existing_video_paths = [existing_path(each_video_name) for each_video_name in video_files_dict.keys()]
    if new_video_path in existing_video_paths:
        raise AttributeError("Error adding video: Video path already exists! ({})".format(new_video_path))
    
    # If we get here, we had no problems, so create a new video entry
    new_video_entry = {safe_video_name: {"path": new_video_path,
                                            "start_datetime_isoformat": new_start_datetime_isoformat,
                                            "video_timelapse_factor": new_timelapse_factor}}
    
    # Update the video files dictionary and save it
    video_files_dict.update(new_video_entry)
    save_video_files_dict(location_select_folder_path, camera_select, video_files_dict)
    
    return safe_video_name

# .....................................................................................................................

def rename_video_in_files_dict(location_select_folder_path, camera_select, old_video_name, new_video_name):
    
    ''' Function which renames existing entries in the video file dictionary '''
    
    # Clean name to ensure consistency. Also helps with detecting duplicates
    safe_video_name = url_safe_name(new_video_name)
    
    # Load existing video file data
    video_files_dict = load_video_files_dict(location_select_folder_path, camera_select)
    
    # Check that the video name exists (otherwise we can't rename it!)
    name_in_use = (safe_video_name in video_files_dict.keys())
    if name_in_use:
        raise NameError("Error renaming video: Video name already exists! ({})".format(safe_video_name))

    # If we get here, we had no problems, so remove the old entry and use it to create a new (renamed) entry
    old_video_data = video_files_dict.pop(old_video_name)
    new_video_entry = {safe_video_name: old_video_data}
    
    # Update the video files dictionary and save it
    video_files_dict.update(new_video_entry)
    save_video_files_dict(location_select_folder_path, camera_select, video_files_dict)

# .....................................................................................................................

def delete_video_in_files_dict(location_select_folder_path, camera_select, video_name_to_delete):
    
    ''' Function which deletes entries in the video file dictionary '''
    
    # Clean name to ensure consistency
    safe_video_name = url_safe_name(video_name_to_delete)
    
    # Load existing video file data
    video_files_dict = load_video_files_dict(location_select_folder_path, camera_select)
    
    # Check that the video name exists (otherwise we can't delete it!)
    name_in_use = (safe_video_name in video_files_dict.keys())
    if not name_in_use:
        raise NameError("Error deleting video: Video name doesn't exist! ({})".format(safe_video_name))
    
    # If we get here, we had no problems, so remove the old entry and re-save the file
    deleted_video_full_path, _, _ = video_info_from_name(location_select_folder_path, camera_select, safe_video_name)
    video_files_dict.pop(safe_video_name)
    save_video_files_dict(location_select_folder_path, camera_select, video_files_dict)
    
    # Delete local copies of videos as well
    is_local_path = check_path_is_local(location_select_folder_path, camera_select,  deleted_video_full_path)
    file_exists = os.path.exists(deleted_video_full_path)
    if is_local_path and file_exists:
        os.remove(deleted_video_full_path)
        
    return is_local_path, deleted_video_full_path

# .....................................................................................................................

def change_video_start_datetime(location_select_folder_path, camera_select, video_name, new_start_datetime):
    
    ''' Function which updates the start datetime for existing video entries in the video file dictionary '''
    
    # Convert the input datetime object to an isoformat string for saving
    new_start_dt_isoformat = datetime_to_isoformat_string(new_start_datetime)
    
    # Clean name to ensure consistency
    safe_video_name = url_safe_name(video_name)
    
    # Load existing video file data
    video_files_dict = load_video_files_dict(location_select_folder_path, camera_select)
    
    # Check that the video name exists (otherwise we can't update it!)
    name_in_use = (safe_video_name in video_files_dict.keys())
    if not name_in_use:
        raise NameError("Error updating video: Video name doesn't exist! ({})".format(safe_video_name))
    
    # If we get here we had no problems, so update the dictionary entry & save it
    old_start_dt_isoformat = str(video_files_dict[safe_video_name]["start_datetime_isoformat"])
    video_files_dict[safe_video_name]["start_datetime_isoformat"] = new_start_dt_isoformat
    save_video_files_dict(location_select_folder_path, camera_select, video_files_dict)
    
    return old_start_dt_isoformat, new_start_dt_isoformat

# .....................................................................................................................

def change_video_timelapse_factor(location_select_folder_path, camera_select, video_name, new_timelapse_factor):
    
    ''' Function which updates the timelapse factor for existing video entries in the video file dictionary '''
    
    # Force near-integers to be integers, for cleanliness
    int_leftover = abs(int(round(new_timelapse_factor)) - new_timelapse_factor)
    close_to_int = (int(round(1000.0 * int_leftover)) < 1)
    if close_to_int:
        new_timelapse_factor = int(round(new_timelapse_factor))
    
    # Clean name to ensure consistency
    safe_video_name = url_safe_name(video_name)
    
    # Load existing video file data
    video_files_dict = load_video_files_dict(location_select_folder_path, camera_select)
    
    # Check that the video name exists (otherwise we can't update it!)
    name_in_use = (safe_video_name in video_files_dict.keys())
    if not name_in_use:
        raise NameError("Error updating video: Video name doesn't exist! ({})".format(safe_video_name))
    
    # If we get here we had no problems, so update the dictionary entry & save it
    old_timelapse_factor = video_files_dict[safe_video_name]["video_timelapse_factor"]
    video_files_dict[safe_video_name]["video_timelapse_factor"] = new_timelapse_factor
    save_video_files_dict(location_select_folder_path, camera_select, video_files_dict)
    
    return old_timelapse_factor, new_timelapse_factor

# .....................................................................................................................

def copy_video_file_local(location_select_folder_path, camera_select, remote_file_path, print_feedback = False):
    
    # Make sure the 'remote' file isn't actually local
    is_local = check_path_is_local(location_select_folder_path, camera_select, remote_file_path)
    if is_local:
        if print_feedback:
            print("",
                  "File is local",
                  "@ {}".format(remote_file_path),
                  "",
                  "Cancelling local copy...",
                  "", sep="\n")        
        return remote_file_path
    
    # Print out some feedback before copying, since it can take a while
    videos_folder_path = build_videos_folder_path(location_select_folder_path, camera_select)
    if print_feedback:
        print("",
              "Copying...",
              "  {}".format(remote_file_path),
              "  to:",
              "  {}".format(videos_folder_path),
              "", sep="\n")
        
    # Perform copy, which could take a while, depending on the file size
    local_copy_path = copy_with_metadata(remote_file_path, videos_folder_path)
    
    return local_copy_path

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Lookup functions
    
# .....................................................................................................................

def check_path_is_local(location_select_folder_path, camera_select, video_path):
    
    ''' 
    Function which takes a (full) path to a video file, and determines if the file is stored locally 
    (i.e. inside the videos resources folder of the given camera)
    '''
        
    # Get rid of symlinks
    videos_folder_path = build_videos_folder_path(location_select_folder_path, camera_select)
    real_videos_folder_path = os.path.realpath(videos_folder_path)
    real_video_path = os.path.realpath(video_path)
    real_video_dir = os.path.dirname(real_video_path)
    
    path_is_local = (real_video_dir == real_videos_folder_path)
    return path_is_local

# .....................................................................................................................
    
def check_entry_is_local(video_path):
    
    ''' Helper function for checking if a provided video path is in 'local' format '''
    
    return (os.path.dirname(video_path) == "")

# .....................................................................................................................

def video_info_from_name(location_select_folder_path, camera_select, video_select):
    
    ''' 
    This function retrieves a video path given the name of the video,
    assuming the name is in the saved video listing file.
    This function does not check that the video path is valid however!
    '''
    
    # First load the video file listing data
    video_files_dict = load_video_files_dict(location_select_folder_path, camera_select)
    
    # Make sure the selected video is in the listing
    if video_select not in video_files_dict:
        raise FileNotFoundError("Couldn't find video in file listing! ({})".format(video_select))
    
    # Get selected video info
    video_info_dict = video_files_dict[video_select]
    
    # Pull out start timing and timelapse factor
    start_datetime_isoformat = video_info_dict.get("start_datetime_isoformat", None)
    timelapse_factor = video_info_dict.get("video_timelapse_factor", 1)
    
    # Expand user home pathing, if present
    video_select_path = video_info_dict["path"]
    expanded_path = os.path.expanduser(video_select_path)
    
    # Convert local paths to full paths, if needed
    is_local_entry = check_entry_is_local(expanded_path)
    if is_local_entry:
        expanded_path = build_videos_folder_path(location_select_folder_path, camera_select, expanded_path)        
    
    return expanded_path, start_datetime_isoformat, timelapse_factor
    
# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Playback Functions

# .....................................................................................................................

def load_playback_settings(location_select_folder_path, camera_select, video_select,
                           settings_filename = "playback_settings.json"):
    
    # Make sure to use only the video name, for readability (may cause collisions?!)
    video_name = os.path.basename(video_select)
    
    # Build pathing to the playback settings file
    load_path = build_videos_folder_path(location_select_folder_path, camera_select, settings_filename)
    
    # Create default file content in case it isn't there
    default_content = {}
    
    # Load the playback settings file (or create it if missing)
    playback_settings_dict = load_or_create_config_json(load_path, default_content,
                                                        creation_printout = "Creating playback settings file:")
    
    # Check if settings exist for the target video, and if so, grab the settings in a tuple for ease of use
    settings_tuple = (None, None, None, None)
    settings_exist = (video_name in playback_settings_dict)
    if settings_exist:
        
        # Grab settings for the selected video
        video_settings_dict = playback_settings_dict[video_name]
        
        # Pull out settings values into more convenient tuple form for returning
        current_frame_index = video_settings_dict["current_frame_index"]
        start_loop_index = video_settings_dict["start_loop_index"]
        end_loop_index = video_settings_dict["end_loop_index"]
        frame_delay_ms = video_settings_dict["frame_delay_ms"]
        settings_tuple = (current_frame_index, start_loop_index, end_loop_index, frame_delay_ms)
    
    return settings_exist, settings_tuple

# .....................................................................................................................

def save_playback_settings(location_select_folder_path, camera_select, video_select,
                           current_frame_index, start_loop_index, end_loop_index, frame_delay_ms,
                           settings_filename = "playback_settings.json"):
    
    # Make sure to use only the video name, for readability (may cause collisions?!)
    video_name = os.path.basename(video_select)
    
    # Build pathing to the playback settings file
    save_path = build_videos_folder_path(location_select_folder_path, camera_select, settings_filename)
    
    # Bundle the settings data for saving
    settings_dict = {"current_frame_index": current_frame_index, "frame_delay_ms": frame_delay_ms,
                     "start_loop_index": start_loop_index, "end_loop_index": end_loop_index}
    new_playback_settings = {video_name: settings_dict}
    
    return update_config_json(save_path, new_playback_settings)

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap

