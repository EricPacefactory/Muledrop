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

from local.lib.file_access_utils.shared import build_camera_path, copy_from_defaults
from local.lib.file_access_utils.externals import build_externals_folder_path
from local.lib.file_access_utils.video import get_video_names_and_paths_lists, check_valid_rtsp_ip

from local.eolib.utils.files import get_folder_list, get_file_list


# ---------------------------------------------------------------------------------------------------------------------
#%% Folder structures

# .....................................................................................................................

def camera_folder_structure():
    
    structure = {
                 "report": {"images", "metadata"},
                 "config": {"after_database", "externals", "core"},
                 "resources": {"videos": {},
                               "backgrounds": {"captures", "generated"},
                               "classifier": {"datasets", "models"}},
                 "logs": {"system", "configurables"}
                 }
    
    return structure

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Folder structure functions
    
# .....................................................................................................................
    
def create_camera_folder_structure(project_root_path, cameras_folder_path, camera_select, default_select = None):
    
    ''' Function which creates the base camera folder structure with required (default) files, if missing '''
    
    # Make sure the base camera folder is created
    camera_path = build_camera_path(cameras_folder_path, camera_select)
    os.makedirs(camera_path, exist_ok = True)
    
    # Build out the rest of the camera folder structure
    create_folder_structure_from_dictionary(camera_path, camera_folder_structure())
    
    # Make sure default files are present
    copy_from_defaults(project_root_path, cameras_folder_path, camera_select, default_select)

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
#%% File structure functions

# .....................................................................................................................

def create_access_info(script_name, class_name, configuration_utility_file_dunder = None):
    
    '''
    Helper function which ensures consistent access info structure for configurables
    
    Inputs:
        script_name -> (String) Name of script implementing a specific configurable
        
        class_name -> (String) Name of class to instantiate with given configuration data
        
        configuration_utility_file_dunder -> (String or None) File dunder (__file__) of the script
                                             used to save the config data
    
    Outputs:
        access_info_dict
    '''
    
    # Make sure the given script name doesn't include any extension
    script_name_no_ext, _ = os.path.splitext(script_name)
    
    # Also make sure to only save the config util name (with no extension) instead of the full path
    config_util_name_no_ext = None
    if configuration_utility_file_dunder is not None:
        config_util_name_only = os.path.basename(configuration_utility_file_dunder)
        config_util_name_no_ext, _ = os.path.splitext(config_util_name_only)
    
    # Bundle access info
    access_info_dict = {"script_name": script_name_no_ext, "class_name": class_name, 
                        "configuration_utility": config_util_name_no_ext}
    
    return access_info_dict

# .....................................................................................................................

def create_configurable_save_data(script_name, class_name, configuration_utility_file_dunder, setup_data_dict):
    
    '''
    Helper function which ensures consistent config file structure for configurables
    
    Inputs:
        script_name -> (String) Name of script implementing a specific configurable
        
        class_name -> (String) Name of class to instantiate with given configuration data
        
        configuration_utility_file_dunder -> (String or None) File dunder (__file__) of the script
                                             used to save the config data
        
        setup_data_dict -> (Dictionary) Configuration data which will be re-loaded into the configurable on setup
    
    Outputs:
        save_data_dict
    '''
    
    # Bundle data in target format
    access_info_dict = create_access_info(script_name, class_name, configuration_utility_file_dunder)
    save_data_dict = {"access_info": access_info_dict, "setup_data": setup_data_dict}
    
    return save_data_dict

# .....................................................................................................................

def unpack_config_data(config_data_dict):
    
    '''
    Helper function used to simplify & hide details about how to access/index configuration data
    This function will raise an IOError if the access inof or setup data is missing from the config_data_dict
    
    Inputs:
        config_data_dict -> (Dictionary) Configuration data saved for a 'configurable'. Assumed to have been
                            built using the 'create_configurable_save_data' function!
    
    Outputs:
        access_info_dict, setup_data_dict
    
    Note: Use the function 'unpack_configurable_access_info' to further unpack the access info if needed
    '''
    
    try:
        access_info_dict = config_data_dict["access_info"]
        setup_data_dict = config_data_dict["setup_data"]
        
    except KeyError:
        err_msg_list = ["", 
                        "Error unpacking configurable config data!",
                        "Expecting keys: access_info & setup_data",
                        ""]
        raise IOError("\n".join(err_msg_list))
    
    return access_info_dict, setup_data_dict

# .....................................................................................................................

def unpack_access_info(access_info_dict):
    
    '''
    Helper function used to further simplify & hide details about how to index into the access info part of 
    a configurable's config file data
    This function will raise an IOError if the script or class name information is missing from the access info
    
    Inputs:
        access_info_dict -> (Dictionary) Configuration data describing how to access files needed to load a
                            given configurable. Assumed to have been already unpacked using 
                            the 'unpack_config_data' function
    
    Outputs:
        script_name_no_ext, class_init_name, configuration_utility_no_ext
    
    Note: The 'configuration utility' may be None if nothing was saved
    '''
    
    configuration_utility_no_ext = access_info_dict.get("configuration_utility", None)
    
    try:
        script_name_no_ext = access_info_dict["script_name"]
        class_init_name = access_info_dict["class_name"]
    
    except KeyError:
        err_msg_list = ["", 
                        "Error unpacking access info data!",
                        "Expecting keys: script_name & class_name",
                        ""]
        raise IOError("\n".join(err_msg_list))
    
    return script_name_no_ext, class_init_name, configuration_utility_no_ext

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% List building functions

# .....................................................................................................................

def build_camera_list(cameras_folder_path, show_hidden_cameras = False, must_have_rtsp = False):
    
    ''' Function which returns all camera names & corresponding folder paths '''
    
    # Find all the camera folders within the 'cameras' folder
    camera_path_list = get_folder_list(cameras_folder_path, 
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
            is_valid_rtsp_ip = check_valid_rtsp_ip(cameras_folder_path, each_camera_name)
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
    
def build_external_list(cameras_folder_path, camera_select, show_hidden_externals = False):
    
    ''' Function which returns all file names & corresponding paths to externals config files (for a given camera)'''
    
    # Build path to the selected camera and externals folder    
    externals_folder_path = build_externals_folder_path(cameras_folder_path, camera_select)
    
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

def build_cameras_tree(cameras_folder_path, show_hidden = False):

    # Get a list of all the cameras
    camera_names_list, _ = build_camera_list(cameras_folder_path, 
                                             show_hidden_cameras = show_hidden)
    
    # Build up a tree structure to store all of the info for all cameras
    cameras_tree = {}
    for each_camera in camera_names_list:
        cameras_tree[each_camera] = {"videos": {}} 
        cameras_tree[each_camera]["videos"] = _build_video_tree(cameras_folder_path, each_camera, show_hidden)
    
    return cameras_tree

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Helper functions

# .....................................................................................................................

def create_missing_folder_path(folder_path):
    
    ''' Helper function which creates missing folder paths '''
    
    os.makedirs(folder_path, exist_ok = True)

# .....................................................................................................................

def create_missing_folders_from_file(file_path):
    
    ''' Helper function which creates the folder pathing needed for a given file path '''
    
    folder_path = os.path.dirname(file_path)
    os.makedirs(folder_path, exist_ok = True)
    
    return folder_path

# .....................................................................................................................

def _build_video_tree(cameras_folder_path, camera_select, show_hidden, error_if_no_videos = False):
    
    video_names_list, video_paths_list = get_video_names_and_paths_lists(cameras_folder_path,
                                                                         camera_select, 
                                                                         error_if_no_videos)
        
    video_tree = {"names": video_names_list,
                  "paths": video_paths_list}
    
    return video_tree

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap

