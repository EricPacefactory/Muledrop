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

from local.lib.file_access_utils.shared import build_user_folder_path, build_task_folder_path

from local.lib.file_access_utils.shared import auto_project_root_path, auto_cameras_folder_path
from local.lib.file_access_utils.video import build_videos_folder_path, load_video_file_lists

from local.lib.file_access_utils.externals import build_externals_folder_path, create_default_externals_config
from local.lib.file_access_utils.core import create_default_core_configs
from local.lib.file_access_utils.video import create_default_video_configs, check_valid_rtsp_ip
from local.lib.file_access_utils.classifier import create_default_classifier_configs

from eolib.utils.files import get_folder_list, get_file_list

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
    
    structure = {"tasks", "externals"}
    
    return structure

# .....................................................................................................................
    
def task_folder_structure():
    
    structure = {"core", "rules", "classifier", "summary_statistics"}
    
    return structure

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Folder structure functions
    
# .....................................................................................................................
    
def create_camera_folder_structure(project_root_path, camera_path):
    
    # Make sure the base camera folder is created
    os.makedirs(camera_path, exist_ok = True)
    
    # Build out the rest of the camera folder structure
    create_folder_structure_from_dictionary(camera_path, camera_folder_structure())
    
    # Make sure a 'live' user exists as well
    live_user_path = os.path.join(camera_path, "users", "live")
    create_user_folder_structure(project_root_path, live_user_path)
    
    # Make sure the resources folder is initialized
    resources_path = os.path.join(camera_path, "resources")
    video_resource_path = os.path.join(resources_path, "videos")
    classifier_resource_path = os.path.join(resources_path, "classifier")
    
    # Make sure video resource data is initialized
    video_resource_path = os.path.join(resources_path, "videos")
    create_default_video_configs(project_root_path, video_resource_path)
    create_default_classifier_configs(project_root_path, classifier_resource_path)
    
# .....................................................................................................................
    
def create_user_folder_structure(project_root_path, user_path):
    
    # Make sure the base user folder is created
    os.makedirs(user_path, exist_ok = True)
    
    # Build out the rest of the user folder structure
    create_folder_structure_from_dictionary(user_path, user_folder_structure())
    
    # Build paths to user folder structure that was created
    # Warning: This is being hard-coded! Has to match the output of user_folder_structure()
    tasks_folder_path = os.path.join(user_path, "tasks")
    externals_folder_path = os.path.join(user_path, "externals")
    
    # Create default externals configs
    create_default_externals_config(project_root_path, externals_folder_path)
    
    # If no tasks exist, make a default 'main_task' for this user
    tasks_folder_list = get_folder_list(tasks_folder_path)
    tasks_exist = (len(tasks_folder_list) > 0)
    if not tasks_exist:
        mask_task_path = os.path.join(tasks_folder_path, "main_task")
        create_task_folder_structure(project_root_path, mask_task_path)
        
# .....................................................................................................................
    
def create_task_folder_structure(project_root_path, task_path):
    
    # Make sure the base task folder is created
    os.makedirs(task_path, exist_ok = True)
    
    # Build out the rest of the task folder structure
    create_folder_structure_from_dictionary(task_path, task_folder_structure())
    
    # Create default core configs
    create_default_core_configs(project_root_path, task_path)
    
# .....................................................................................................................
    
def create_folder_structure_from_dictionary(base_path, dictionary, make_folders = True):
    # Recursive function for creating file paths from a dictionary
    
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

def build_task_list(cameras_folder, camera_select, user_select, show_hidden_tasks = False):
    
    # Build path to the selected camera, user folder and tasks folder    
    tasks_folder_path = build_task_folder_path(cameras_folder, camera_select, user_select, None)
    
    # Find all task folders
    task_path_list = get_folder_list(tasks_folder_path, 
                                     show_hidden_folders = show_hidden_tasks, 
                                     create_missing_folder = False,
                                     return_full_path = True)
    task_name_list = [os.path.basename(each_path) for each_path in task_path_list]
    
    return task_name_list, task_path_list

# .....................................................................................................................
    
def build_external_list(cameras_folder, camera_select, user_select, show_hidden_externals = False):
    
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

def build_video_list(cameras_folder, camera_select, 
                     show_hidden_videos = False,
                     error_if_no_videos = True):
    
    cameras_folder = auto_cameras_folder_path(cameras_folder)
    
    # Get video file listing
    videos_folder_path = build_videos_folder_path(cameras_folder, camera_select)
    file_listings = load_video_file_lists(cameras_folder, camera_select)
    
    # Build a list of all file paths to consider for the video load list
    full_path_list = file_listings["visible"] + (file_listings["hidden"] if show_hidden_videos else [])
    num_visible = len(file_listings["visible"])
    
    # Have the video manager handle naming/pathing for each of the loaded paths
    name_list, path_list = [], []
    for path_idx, each_path in enumerate(full_path_list):
        
        # Try using local pathing, if the given path doesn't exist
        if not os.path.exists(each_path):
            try_local_path = os.path.join(videos_folder_path, each_path)
            each_path = try_local_path if os.path.exists(try_local_path) else each_path
        
        # Skip over missing paths
        if not os.path.exists(each_path):
            continue
        
        # Add hidden identifier '.' for hidden video file names to match filesystem behavior
        each_name = os.path.basename(each_path)
        if path_idx >= num_visible:
            each_name = "".join([".", each_name]) if each_name[0] != "." else each_name            
        
        # Add file name and pathing
        name_list.append(each_name)
        path_list.append(each_path)
        
    # Sort the names (and paths) for display
    sorted_names, sorted_paths = [], []
    if len(name_list)*len(path_list) > 0:
        sorted_names, sorted_paths = zip(*sorted(zip(name_list, path_list)))
        
    # Raise an error if the resulting lists are empty
    if len(sorted_names)*len(sorted_paths) == 0:
        if error_if_no_videos:
            raise FileNotFoundError("No video files!")                    
    
    return sorted_names, sorted_paths

# .....................................................................................................................

def build_core_config_components_list(project_root_path, config_utils_folder = "configuration_utilities"):
    
    project_root_path = auto_project_root_path(project_root_path)
    
    # Build path to the configuration utilities folder
    config_utils_folder_path = os.path.join(project_root_path, config_utils_folder, "core")
    
    # Find all configuration utility folders
    util_components_path_list = get_folder_list(config_utils_folder_path, 
                                                show_hidden_folders = False, 
                                                create_missing_folder = False,
                                                return_full_path = True)
    util_components_name_list = [os.path.basename(each_path) for each_path in util_components_path_list]
    
    return util_components_name_list, util_components_path_list

# .....................................................................................................................

def build_core_config_options_list(project_root_path, component_select, show_hidden_options = False,
                                   config_utils_folder = "configuration_utilities"):
    
    # Build path to the config utils folder storing all option scripts
    configuration_utility_folder_path = os.path.join(project_root_path, config_utils_folder, "core", component_select)
    
    # Get all the files in the given components utilities folder
    util_options_path_list = get_file_list(configuration_utility_folder_path, 
                                           show_hidden_files = show_hidden_options, 
                                           create_missing_folder = False,
                                           return_full_path = True)
    
    # Remove any non-python script files
    util_options_path_list = [each_path for each_path in util_options_path_list 
                              if os.path.splitext(each_path)[1] == ".py"]
    
    # Also get just the file names (with no extensions)
    util_options_fullname_list = [os.path.basename(each_path) for each_path in util_options_path_list]
    util_options_name_list = [os.path.splitext(each_name)[0] for each_name in util_options_fullname_list]
    
    return util_options_name_list, util_options_path_list

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Tree functions

def build_cameras_tree(cameras_folder, show_hidden = False):
    
    cameras_folder = auto_cameras_folder_path(cameras_folder)

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
    
def build_core_config_utils_tree(project_root_path, show_hidden = False):
    
    project_root_path = auto_project_root_path(project_root_path)
    
    # Get a list of all the core component config utilties (preprocessor, tracker etc.)
    util_components_name_list, _ = build_core_config_components_list(project_root_path)
    
    # Build a tree structure (dictionary) to store all of the core config utility info
    util_components_tree = {}
    for each_util_name in util_components_name_list:
        util_components_tree[each_util_name] = _build_core_options_tree(project_root_path,
                                                                        each_util_name, 
                                                                        show_hidden)
    
    return util_components_tree

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
        new_user_tree = {"tasks": {}, "externals": {}}
        new_user_tree["tasks"] = _build_task_tree(cameras_folder, camera_select, each_user, show_hidden)
        new_user_tree["externals"] = build_external_list(cameras_folder, camera_select, each_user, show_hidden)[0]
        user_tree[each_user] = new_user_tree
    
    return user_tree

# .....................................................................................................................

def _build_task_tree(cameras_folder, camera_select, user_select, show_hidden):
    
    task_names_list, _ = build_task_list(cameras_folder, camera_select, user_select,
                                         show_hidden_tasks = show_hidden)
    
    task_tree = {each_task: {} for each_task in task_names_list}
    
    return task_tree

# .....................................................................................................................

def _build_video_tree(cameras_folder, camera_select, show_hidden, error_if_no_videos = False):
    
    video_names_list, video_paths_list = build_video_list(cameras_folder, camera_select, 
                                                          show_hidden_videos = show_hidden,
                                                          error_if_no_videos = error_if_no_videos)
        
    video_tree = {"names": video_names_list,
                  "paths": video_paths_list}
    
    return video_tree

# .....................................................................................................................

def _build_core_options_tree(project_root_path, component_select, show_hidden):
    
    util_options_name_list, util_options_path_list = build_core_config_options_list(project_root_path,
                                                                                    component_select,
                                                                                    show_hidden_options = show_hidden)
    
    # Move passthroughs to the top of the lists, if present
    passthrough_name = "passthrough"
    lower_case_list = [each_entry.lower() for each_entry in util_options_name_list]
    if passthrough_name in lower_case_list:
        passthru_idx = lower_case_list.index(passthrough_name)
        passthru_name_entry = util_options_name_list.pop(passthru_idx)
        passthru_path_entry = util_options_path_list.pop(passthru_idx)
        util_options_name_list.insert(0, passthru_name_entry)
        util_options_path_list.insert(0, passthru_path_entry)
        
    util_options_tree = {"names": util_options_name_list,
                         "paths": util_options_path_list}
    
    return util_options_tree
    
# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap

