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

from local.lib.file_access_utils.shared import build_resources_folder_path
from local.lib.file_access_utils.json_read_write import load_or_create_config_json, update_config_json, save_config_json

from local.eolib.utils.network import build_rtsp_string, check_valid_ip
from local.eolib.utils.files import replace_user_home_pathing
from local.eolib.utils.quitters import ide_quit

# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes 

class Playback_Access:
    
    # .................................................................................................................
    
    def __init__(self, cameras_folder_path, camera_select, video_select, 
                 playback_settings_file = "playback_settings.json"):
        
        # Store pathing info
        self.cameras_folder_path = cameras_folder_path
        self.camera_select = camera_select
        self.video_select = video_select
        self.playback_file_name = playback_settings_file
        
        # Build pathing to the playback settings file
        self.settings_file_path = build_videos_folder_path(cameras_folder_path, camera_select, playback_settings_file)
    
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

def build_videos_folder_path(cameras_folder, camera_select, *path_joins):
    return build_resources_folder_path(cameras_folder, camera_select, "videos", *path_joins)

# .....................................................................................................................

def build_video_files_dict_path(cameras_folder, camera_select):
    return build_videos_folder_path(cameras_folder, camera_select, "video_files_record.json")

# .....................................................................................................................

def build_rtsp_file_path(cameras_folder, camera_select):
    return build_videos_folder_path(cameras_folder, camera_select, "rtsp.json")

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Load & Save functions

# .....................................................................................................................

def get_video_names_and_paths_lists(cameras_folder, camera_select, error_if_no_videos = True):
    
    ''' 
    Function which returns a list of video names and corresponding loading paths based on the 
    data stored in the video files dictionary.
    Note, this function expands user pathing (e.g. ~) and also builds full pathing to local video files.
    '''
    
    # Load video file data
    video_files_dict = load_video_files_dict(cameras_folder, camera_select)
    videos_folder_path = build_videos_folder_path(cameras_folder, camera_select)
    
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

def load_video_files_dict(cameras_folder, camera_select):
    
    '''
    This function loads data from the video listing file (located in the resources folder).
    Data is returned as a dictionary (matching the file contents)
    '''
    
    # Set the default content, in case the file doesn't exist when we try to load it
    default_files_dict = {}
    
    # Build pathing to the video file, then load it
    video_files_dict_path = build_video_files_dict_path(cameras_folder, camera_select)
    video_files_dict = load_or_create_config_json(video_files_dict_path, default_files_dict,
                                                  creation_printout = "Creating video file record:")    
    
    return video_files_dict

# .....................................................................................................................

def save_video_files_dict(cameras_folder, camera_select, new_video_files_dict):
    
    '''
    This function saves data to the video listing file (located in the resources folder).
    Note, the saving occurs by fully replacing the existing file!
    '''
    
    # Build pathing to the video file, then load it
    video_files_dict_path = build_video_files_dict_path(cameras_folder, camera_select)
    
    # Save the file, but make sure it's valid, so we don't mangle it if something goes wrong!
    save_path = save_config_json(video_files_dict_path, new_video_files_dict)
    
    return save_path

# .....................................................................................................................

def add_video_to_files_dict(cameras_folder, camera_select, new_video_name, new_video_path,
                            new_start_datetime_isoformat = None, new_timelapse_factor = 1):
    
    ''' Function which adds new video entries to the video file dictionary '''
    
    # Load existing video file data
    video_files_dict = load_video_files_dict(cameras_folder, camera_select)
    
    # Check that the video name isn't already in use
    name_in_use = (new_video_name in video_files_dict.keys())
    if name_in_use:
        raise NameError("Error adding video: Video name already taken! ({})".format(new_video_name))
    
    # Convert to 'local' pathing and/or remove user home pathing from the new video path, if needed
    is_local_path = check_path_is_local(cameras_folder, camera_select, new_video_path)
    if is_local_path:
        new_video_path = os.path.basename(new_video_path)
    new_video_path = replace_user_home_pathing(new_video_path)
    
    # Check that the video path isn't already in use
    existing_path = lambda video_name: video_files_dict.get(video_name, {}).get("path", None)
    existing_video_paths = [existing_path(each_video_name) for each_video_name in video_files_dict.keys()]
    if new_video_path in existing_video_paths:
        raise AttributeError("Error adding video: Video path already exists! ({})".format(new_video_path))
    
    # If we get here, we had no problems, so create a new video entry
    new_video_entry = {new_video_name: {"path": new_video_path,
                                        "start_datetime_isoformat": new_start_datetime_isoformat,
                                        "video_timelapse_factor": new_timelapse_factor}}
    
    # Update the video files dictionary and save it
    video_files_dict.update(new_video_entry)
    save_video_files_dict(cameras_folder, camera_select, video_files_dict)

# .....................................................................................................................

def rename_video_in_files_dict(cameras_folder, camera_select, old_video_name, new_video_name):
    
    ''' Function which renames existing entries in the video file dictionary '''
    
    # Load existing video file data
    video_files_dict = load_video_files_dict(cameras_folder, camera_select)
    
    # Check that the video name exists (otherwise we can't rename it!)
    name_in_use = (new_video_name in video_files_dict.keys())
    if name_in_use:
        raise NameError("Error renaming video: Video name already exists! ({})".format(new_video_name))

    # If we get here, we had no problems, so remove the old entry and use it to create a new (renamed) entry
    old_video_data = video_files_dict.pop(old_video_name)
    new_video_entry = {new_video_name: old_video_data}
    
    # Update the video files dictionary and save it
    video_files_dict.update(new_video_entry)
    save_video_files_dict(cameras_folder, camera_select, video_files_dict)

# .....................................................................................................................

def delete_video_in_files_dict(cameras_folder, camera_select, video_name_to_delete):
    
    ''' Function which deletes entries in the video file dictionary '''
    
    # Load existing video file data
    video_files_dict = load_video_files_dict(cameras_folder, camera_select)
    
    # Check that the video name exists (otherwise we can't delete it!)
    name_in_use = (video_name_to_delete in video_files_dict.keys())
    if not name_in_use:
        raise NameError("Error deleting video: Video name doesn't exist! ({})".format(video_name_to_delete))
    
    # If we get here, we had no problems, so remove the old entry and re-save the file
    deleted_video_full_path, _, _ = video_info_from_name(cameras_folder, camera_select, video_name_to_delete)
    video_files_dict.pop(video_name_to_delete)
    save_video_files_dict(cameras_folder, camera_select, video_files_dict)
    
    # Delete local copies of videos as well
    is_local_path = check_path_is_local(cameras_folder, camera_select,  deleted_video_full_path)
    file_exists = os.path.exists(deleted_video_full_path)
    if is_local_path and file_exists:
        os.remove(deleted_video_full_path)
        
    return is_local_path, deleted_video_full_path

# .....................................................................................................................

def change_video_start_datetime(cameras_folder, camera_select, video_name):
    
    ''' Function which updates the start datetime for existing video entries in the video file dictionary '''
    
    raise NotImplementedError()
    pass

# .....................................................................................................................

def change_video_timelapse_factor(cameras_folder, camera_select, video_name):
    
    ''' Function which updates the timelapse factor for existing video entries in the video file dictionary '''
    
    raise NotImplementedError()
    pass

# .....................................................................................................................

def copy_video_file_local(cameras_folder, camera_select, remote_file_path, print_feedback = False):
    
    # Make sure the 'remote' file isn't actually local
    is_local = check_path_is_local(cameras_folder, camera_select, remote_file_path)
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
    videos_folder_path = build_videos_folder_path(cameras_folder, camera_select)
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

def check_path_is_local(cameras_folder, camera_select, video_path):
    
    ''' 
    Function which takes a (full) path to a video file, and determines if the file is stored locally 
    (i.e. inside the videos resources folder of the given camera)
    '''
        
    # Get rid of symlinks
    videos_folder_path = build_videos_folder_path(cameras_folder, camera_select)
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

def video_info_from_name(cameras_folder, camera_select, video_select):
    
    ''' 
    This function retrieves a video path given the name of the video, 
    assuming the name is in the saved video listing file.
    This function does not check that the video path is valid however!
    '''
    
    # First load the video file listing data
    video_files_dict = load_video_files_dict(cameras_folder, camera_select)
    
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
        expanded_path = build_videos_folder_path(cameras_folder, camera_select, expanded_path)        
    
    return expanded_path, start_datetime_isoformat, timelapse_factor
    
# .....................................................................................................................
# .....................................................................................................................
    
# ---------------------------------------------------------------------------------------------------------------------
#%% RTSP functions

# .....................................................................................................................

def load_rtsp_config(cameras_folder, camera_select, rtsp_filename = "rtsp.json"):
    
    # Create default config entries
    default_rtsp_file = {"ip_address": "",
                         "username": "",
                         "password": "",
                         "port": 554,
                         "route": ""}
    
    # Build pathing to the rtsp file, then load it
    rtsp_file_path = build_videos_folder_path(cameras_folder, camera_select, rtsp_filename)
    rtsp_config = load_or_create_config_json(rtsp_file_path, default_rtsp_file,
                                             creation_printout = "Creating rtsp file:")
    
    # Create rtsp string for convenience
    rtsp_string = build_rtsp_string(**rtsp_config)
    
    return rtsp_config, rtsp_string

# .....................................................................................................................
    
def save_rtsp_config(cameras_folder, camera_select, new_rtsp_config, rtsp_filename = "rtsp.json"):
    
    # Replace the existing rtsp file with the new config and re-save
    rtsp_file_path = build_videos_folder_path(cameras_folder, camera_select, rtsp_filename)
    return update_config_json(rtsp_file_path, new_rtsp_config)

# .....................................................................................................................

def check_valid_rtsp_ip(cameras_folder, camera_select):
    
    ''' 
    Function for (roughly) determining if the rtsp configuration of a camera is valid 
    Only checks if the ip address is valid
    
    Returns:
        has_valid_rtsp (boolean)
    '''
    
    # Check for missing rtsp configuration
    rtsp_config_dict, _ = load_rtsp_config(cameras_folder, camera_select)
    rtsp_ip_address = rtsp_config_dict.get("ip_address", "")
    has_valid_rtsp = check_valid_ip(rtsp_ip_address, return_error = False)
    
    return has_valid_rtsp

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Playback Functions

# .....................................................................................................................

def load_playback_settings(cameras_folder, camera_select, video_select, 
                           settings_filename = "playback_settings.json"):
    
    # Make sure to use only the video name, for readability (may cause collisions?!)
    video_name = os.path.basename(video_select)
    
    # Build pathing to the playback settings file
    load_path = build_videos_folder_path(cameras_folder, camera_select, settings_filename)
    
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

def save_playback_settings(cameras_folder, camera_select, video_select, 
                           current_frame_index, start_loop_index, end_loop_index, frame_delay_ms,
                           settings_filename = "playback_settings.json"):
    
    # Make sure to use only the video name, for readability (may cause collisions?!)
    video_name = os.path.basename(video_select)
    
    # Build pathing to the playback settings file
    save_path = build_videos_folder_path(cameras_folder, camera_select, settings_filename)
    
    # Bundle the settings data for saving
    settings_dict = {"current_frame_index": current_frame_index, "frame_delay_ms": frame_delay_ms,
                     "start_loop_index": start_loop_index, "end_loop_index": end_loop_index}
    new_playback_settings = {video_name: settings_dict}
    
    return update_config_json(save_path, new_playback_settings)

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap


