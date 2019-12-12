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

from local.lib.file_access_utils.shared import build_resources_folder_path
from local.lib.file_access_utils.shared import load_or_create_json
from local.lib.file_access_utils.shared import load_replace_save
from local.lib.file_access_utils.shared import copy_from_defaults

from eolib.utils.network import build_rtsp_string, check_valid_ip



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
    
    # .................................................................................................................
    
    def load_settings(self):
        
        # Load from the playback settings file
        playback_settings_dict = load_or_create_json(self.settings_file_path,
                                                     default_content = {},
                                                     creation_printout = "Creating playback settings file:")
        
        # Initialize output results
        frame_index = start_loop_index = end_loop_index = frame_delay_ms = None
        
        # If the selected video has settings, check if they're valid
        settings_exist = (self.video_select in playback_settings_dict)
        if settings_exist:
            
            # Grab settings for the selected video
            video_settings_dict = playback_settings_dict.get(self.video_select)
            
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
        
        return load_replace_save(self.settings_file_path, new_video_settings)
    
    # .................................................................................................................
    # .................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Pathing functions

# .....................................................................................................................

def build_videos_folder_path(cameras_folder, camera_select, *path_joins):
    return build_resources_folder_path(cameras_folder, camera_select, "videos", *path_joins)

# .....................................................................................................................

def build_video_file_list_path(cameras_folder, camera_select):
    return build_videos_folder_path(cameras_folder, camera_select, "video_file_list.json")

# .....................................................................................................................

def build_rtsp_file_path(cameras_folder, camera_select):
    return build_videos_folder_path(cameras_folder, camera_select, "rtsp.json")

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Load & Save functions
    
# .....................................................................................................................

def create_default_video_configs(project_root_path, video_resources_path):
    
    # Only copy defaults if no files are present
    file_list = os.listdir(video_resources_path)
    no_configs = len(file_list) == 0
    
    # Pull default json config files out of the defaults folder, and copy in to the target task path
    if no_configs:
        copy_from_defaults(project_root_path, 
                           target_defaults_folder = "video",
                           copy_to_path = video_resources_path)

# .....................................................................................................................

def load_video_file_lists(cameras_folder, camera_select):
    
    '''
    This function loads data from the video file listing (located in the resources > videos folder).
    The returned data is a dictionary, with keys 'visible' and 'hidden', which each store a list of strings
    interpretted as references to video files. Files with full paths are considered 'remote' videos, while
    path-less names are assumed to be located with the same folder as the file listing.
    '''
    
    # Set default video file content
    default_content = {"visible": [],
                       "hidden": []}
    
    # Build pathing to the video file, then load it
    file_list_path = build_video_file_list_path(cameras_folder, camera_select)
    file_contents = load_or_create_json(file_list_path, default_content,
                                        creation_printout = "Creating video file list:")
    
    return file_contents

# .....................................................................................................................

def save_video_file_lists(cameras_folder, camera_select, new_video_path,
                          is_hidden = False,
                          file_name = "video_file_list.json"):
    '''
    This function takes in a video path and appends it to either the visible or hidden list data
    within the video file listing (depending on the 'is_hidden' flag)
    '''
    
    # Check if the video is a local file, in which case, remove the local pathing when saving it's location
    is_local_file = check_local_video_pathing(cameras_folder, camera_select, new_video_path)
    if is_local_file:
        new_video_path = os.path.basename(new_video_path)
    
    # Load the existing data, since we'll need to update it (in a nested way)
    current_data = load_video_file_lists(cameras_folder, camera_select)
    key_select = "hidden" if is_hidden else "visible"
    
    # Add the new file path to the current file list
    updated_file_list = current_data[key_select].copy()
    updated_file_list.append(new_video_path)
    
    # Overwrite the appropriate file listing
    updated_file_lists = update_video_file_list(cameras_folder, camera_select, 
                                                updated_file_list, 
                                                is_hidden_list = is_hidden)
    
    return updated_file_lists

# .....................................................................................................................
    
def update_video_file_list(cameras_folder, camera_select, updated_list, 
                           is_hidden_list = False,
                           file_name = "video_file_list.json"):
    '''
    This function takes in a list (updated_list) and replaces either the visible or hidden list data
    within the video file listing (depending on the 'is_hidden_list' flag)
    '''
    
    # Create updated dictionary to replace the existing data
    key_select = "hidden" if is_hidden_list else "visible"
    updated_key_data = {key_select: updated_list}
    
    # Build pathing to the file listing, then update it with the new list data
    file_list_path = build_video_file_list_path(cameras_folder, camera_select)
    updated_file_lists = load_replace_save(file_list_path, updated_key_data)
    
    return updated_file_lists

# .....................................................................................................................

def copy_video_file_local(cameras_folder, camera_select, remote_file_path, print_feedback = False):
    
    # Make sure the 'remote' file isn't actually local
    is_local = check_local_video_pathing(cameras_folder, camera_select, remote_file_path)
    if is_local:
        if print_feedback:
            print("",
                  "File is local",
                  "@ {}".format(remote_file_path),
                  "",
                  "Cancelling local copy...",
                  "", sep="\n")        
        return remote_file_path
    
    # Special import for copying video files
    from shutil import copy2 as copy_with_metadata
    
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

def check_local_video_pathing(cameras_folder, camera_select, video_path):
        
    # Get rid of symlinks
    videos_folder_path = build_videos_folder_path(cameras_folder, camera_select)
    real_videos_folder = os.path.realpath(videos_folder_path)
    real_video_path = os.path.realpath(video_path)
    real_video_dir = os.path.dirname(real_video_path)
    
    path_is_local = (real_video_dir == real_videos_folder)
    return path_is_local

# .....................................................................................................................

def build_video_name_path_lookup(cameras_folder, camera_select, video_select,
                                 include_hidden = False):
    
    # Build out the list of video entries to check
    video_list_contents = load_video_file_lists(cameras_folder, camera_select)
    vis_list = video_list_contents["visible"]
    hid_list = video_list_contents["hidden"]
    search_list = vis_list + hid_list if include_hidden else vis_list
    
    # Loop through all video file entries and find which ones are valid (i.e. pathing exists)
    valid_dict = {}
    for each_entry in search_list:
        
        # Get the literal path (assuming it's external) and the local version of the path
        external_path = each_entry
        local_path = build_videos_folder_path(cameras_folder, camera_select, each_entry)
        
        # Check if either path is valid
        external_exists = os.path.exists(external_path)
        local_exists = os.path.exists(local_path)
        
        # Record whichever path is valid (or skip this entry if pathing isn't valid)
        if external_exists:
            video_path = external_path
        elif local_exists:
            video_path = local_path
        else:
            continue
        
        # Store the video name/path if we get this far
        video_name = os.path.basename(video_path)
        valid_dict[video_name] = video_path
        
    return valid_dict

# .....................................................................................................................

def video_path_from_name(cameras_folder, camera_select, video_select,
                         include_hidden = False):
    
    video_name_dict = build_video_name_path_lookup(cameras_folder, camera_select, video_select, include_hidden)
    
    if video_select not in video_name_dict:
        raise FileNotFoundError("Couldn't find video {} in file listing!".format(video_select))
        
    return video_name_dict[video_select]

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
    rtsp_config = load_or_create_json(rtsp_file_path, default_rtsp_file,
                                      creation_printout = "Creating rtsp file:")
    
    # Create rtsp string for convenience
    rtsp_string = build_rtsp_string(**rtsp_config)
    
    return rtsp_config, rtsp_string

# .....................................................................................................................
    
def save_rtsp_config(cameras_folder, camera_select, new_rtsp_config, rtsp_filename = "rtsp.json"):
    
    # Replace the existing rtsp file with the new config and re-save
    rtsp_file_path = build_videos_folder_path(cameras_folder, camera_select, rtsp_filename)
    return load_replace_save(rtsp_file_path, new_rtsp_config)

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
    playback_settings_dict = load_or_create_json(load_path, default_content,
                                                 creation_printout = "Creating playback settings file:")
    
    # Check if settings exist for the target video, and if so, grab the settings in a tuple for ease of use
    settings_tuple = (None, None, None, None)
    settings_exist = (video_name in playback_settings_dict)
    if settings_exist:
        
        # Grab settings for the selected video
        video_settings_dict = playback_settings_dict.get(video_name)
        
        # Pull out settings values into more convenient tuple form for returning
        current_frame_index = video_settings_dict.get("current_frame_index")
        start_loop_index = video_settings_dict.get("start_loop_index")
        end_loop_index = video_settings_dict.get("end_loop_index")
        frame_delay_ms = video_settings_dict.get("frame_delay_ms")
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
    
    return load_replace_save(save_path, new_playback_settings)

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap


