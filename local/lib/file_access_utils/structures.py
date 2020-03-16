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

from local.lib.file_access_utils.shared import build_camera_path, build_user_folder_path, copy_from_defaults
from local.lib.file_access_utils.externals import build_externals_folder_path
from local.lib.file_access_utils.video import get_video_names_and_paths_lists, check_valid_rtsp_ip

from local.eolib.utils.files import get_folder_list, get_file_list

# ---------------------------------------------------------------------------------------------------------------------
#%% Folder structures

def camera_folder_structure():
    
    structure = {
                 "report": {},
                 "users": {},
                 "resources": {"videos": {},
                               "backgrounds": {"captures", "generated"},
                               "classifier": {"datasets", "models"}},
                 "logs": {"system", "configurables"}
                 }
    
    return structure

# .....................................................................................................................
    
def user_folder_structure():
    
    structure = {"after_database", "externals", "core"}
    
    return structure

# .....................................................................................................................
    
def afterdb_folder_structure():
    
    structure = {"classifier", "rules", "summary"}
    
    return structure

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Folder structure functions
    
# .....................................................................................................................
    
def create_camera_folder_structure(project_root_path, cameras_folder_path, camera_select,
                                   default_select = "blank"):
    
    ''' Function which creates the base camera folder structure with required (default) files, if missing '''
    
    # Make sure the base camera folder is created
    camera_path = build_camera_path(cameras_folder_path, camera_select)
    os.makedirs(camera_path, exist_ok = True)
    
    # Build out the rest of the camera folder structure
    create_folder_structure_from_dictionary(camera_path, camera_folder_structure())
    
    # Make sure default files are present, including a 'live' user
    user_select = "live"
    copy_from_defaults(project_root_path, cameras_folder_path, camera_select, user_select, default_select)
    
    # Make sure a 'live' user exists as well
    create_user_folder_structure(project_root_path, cameras_folder_path, camera_select, user_select, default_select)
    
# .....................................................................................................................
    
def create_user_folder_structure(project_root_path, cameras_folder_path, camera_select, user_select,
                                 default_select = "blank"):
    
    ''' Function which creates the base user folder structure with default files, if missing'''
    
    # Make sure the base user folder is created
    user_path = build_user_folder_path(cameras_folder_path, camera_select, user_select)
    os.makedirs(user_path, exist_ok = True)
    
    # Build out the rest of the user folder structure
    create_folder_structure_from_dictionary(user_path, user_folder_structure())
    
    # Create after-database folder structure (likely temporary, until full db is up and running!)
    after_db_path = os.path.join(user_path, "after_database")
    create_folder_structure_from_dictionary(after_db_path, afterdb_folder_structure())
    
    # Make sure the select user default files exist
    copy_from_defaults(project_root_path, cameras_folder_path, camera_select, user_select, default_select)

# .....................................................................................................................
    
def create_folder_structure_from_dictionary(base_path, dictionary, make_folders = True):
    
    '''
    Recursive function for creating folder paths from a dictionary 
    
    Inputs:
        base_path --> String. Folder path used as the 'root' of the folder structure created by this function
        
        dictionary --> Dictionary. Stores folder structure to be created. See example below
        
        make_folders --> Boolean. If true, any folders missing fom the dictionary structure will be created
        
    Outputs:
        path_list --> List. A list of all paths specified/created from the provided dictionary
    '''
    
    # If a set is given, interpret it as a dictionary, with each key having an empty dictionary
    if type(dictionary) is set:
        dictionary = {each_set_item: {} for each_set_item in dictionary}
    
    # If the dictionary is empty/not a dictionary, then we're done
    if not dictionary:
        return []
    
    # Allocate space for outputting generated paths
    path_list = []
    
    # Recursively build paths by diving through dictionary entries
    for each_key, each_value in dictionary.items():
        
        # Add the next dictionary key to the existing path
        create_path = os.path.join(base_path, each_key)
        path_list.append(create_path)
        
        new_path_list = create_folder_structure_from_dictionary(create_path, each_value, make_folders = False)
        path_list += new_path_list
        
    # Create the folders, if needed
    if make_folders:
        for each_path in path_list:
            os.makedirs(each_path, exist_ok = True)
        
    return path_list

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% List building functions

# .....................................................................................................................

def build_camera_list(cameras_folder, show_hidden_cameras = False, must_have_rtsp = False):
    
    ''' Function which returns all camera names & corresponding folder paths '''
    
    # Find all the camera folders within the 'cameras' folder
    camera_path_list = get_folder_list(cameras_folder, 
                                       show_hidden_folders = show_hidden_cameras,
                                       create_missing_folder = False, 
                                       return_full_path = True)
    camera_name_list = [os.path.basename(each_path) for each_path in camera_path_list]
    
    # Filter out cameras that don't have valid RTSP configs
    if must_have_rtsp:
        
        # Keep only the camera entries that have valid rtsp ip addresses
        filtered_name_list = []
        filtered_path_list = []
        for each_camera_name, each_camera_path in zip(camera_name_list, camera_path_list):            
            is_valid_rtsp_ip = check_valid_rtsp_ip(cameras_folder, each_camera_name)
            if is_valid_rtsp_ip:
                filtered_name_list.append(each_camera_name)
                filtered_path_list.append(each_camera_path)
        
        # Overwrite existing outputs
        camera_name_list = filtered_name_list
        camera_path_list = filtered_path_list
        
        # Warning if no cameras are left after rtsp-filter
        no_rtsp_cameras = (len(camera_name_list) == 0)
        if no_rtsp_cameras:
            raise AttributeError("No RTSP configuration found for any cameras! Use RTSP editor to configure cameras.")
    
    return camera_name_list, camera_path_list

# .....................................................................................................................

def build_user_list(cameras_folder, camera_select, show_hidden_users = False):
    
    ''' Function which returns all user names & corresponding folder paths (for a given camera) '''
        
    # Build path to the selected camera and users folder
    users_folder_path = build_user_folder_path(cameras_folder, camera_select, None)
    
    # Find all user folders
    user_path_list = get_folder_list(users_folder_path, 
                                     show_hidden_folders = show_hidden_users, 
                                     create_missing_folder = False,
                                     return_full_path = True)
    user_name_list = [os.path.basename(each_path) for each_path in user_path_list]
    
    return user_name_list, user_path_list

# .....................................................................................................................
    
def build_external_list(cameras_folder, camera_select, user_select, show_hidden_externals = False):
    
    ''' Function which returns all file names & corresponding paths to externals config files (for a given camera)'''
    
    # Build path to the selected camera, user folder and externals folder    
    externals_folder_path = build_externals_folder_path(cameras_folder, camera_select, user_select)
    
    # Find all external files
    externals_path_list = get_file_list(externals_folder_path, 
                                        show_hidden_files = show_hidden_externals,
                                        create_missing_folder = False,
                                        return_full_path = True,
                                        allowable_exts_list = [".json"])
    externals_name_list = [os.path.basename(each_path) for each_path in externals_path_list]
    
    return externals_name_list, externals_path_list

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Tree functions

def build_cameras_tree(cameras_folder, show_hidden = False):

    # Get a list of all the cameras
    camera_names_list, _ = build_camera_list(cameras_folder, 
                                             show_hidden_cameras = show_hidden)
    
    # Build up a tree structure to store all of the info for all cameras
    cameras_tree = {}
    for each_camera in camera_names_list:
        cameras_tree[each_camera] = {"users": {}, "videos": {}} 
        cameras_tree[each_camera]["users"] = _build_user_tree(cameras_folder, each_camera, show_hidden)
        cameras_tree[each_camera]["videos"] = _build_video_tree(cameras_folder, each_camera, show_hidden)
    
    return cameras_tree

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Helper functions
    
# .....................................................................................................................
    
def _build_user_tree(cameras_folder, camera_select, show_hidden):
    
    user_names_list, _ = build_user_list(cameras_folder, camera_select, 
                                         show_hidden_users = show_hidden)
    
    user_tree = {}
    for each_user in user_names_list:
        new_user_tree = {"externals": {}}
        new_user_tree["externals"] = build_external_list(cameras_folder, camera_select, each_user, show_hidden)[0]
        user_tree[each_user] = new_user_tree
    
    return user_tree

# .....................................................................................................................

def _build_video_tree(cameras_folder, camera_select, show_hidden, error_if_no_videos = False):
    
    video_names_list, video_paths_list = get_video_names_and_paths_lists(cameras_folder,
                                                                         camera_select, 
                                                                         error_if_no_videos)
        
    video_tree = {"names": video_names_list,
                  "paths": video_paths_list}
    
    return video_tree

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap

