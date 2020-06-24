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

from shutil import copyfile

from time import sleep

from local.lib.common.environment import get_env_cameras_folder

from local.lib.file_access_utils.settings import load_pathing_info


# ---------------------------------------------------------------------------------------------------------------------
#%% Pathing functions

# .....................................................................................................................

def find_root_path(dunder_file = None, target_folder = "local"):
    
    # Clean up dunder file pathing if needed
    try:
        dunder_file = __file__ if dunder_file is None else dunder_file
    except NameError:
        dunder_file = ""
    dunder_file = dunder_file if dunder_file else os.getcwd()
    
    # Set up starting path
    working_path = os.path.dirname(os.path.abspath(dunder_file))
    
    # . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .
    # Check if we're already in the root folder
    if target_folder in os.listdir(working_path):
        root_path = working_path
        return root_path
    
    # . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .
    # Check if the target folder is already part of the path
    
    if "/{}".format(target_folder) in working_path:
        root_path = working_path.split("/{}".format(target_folder))[0]
        return root_path
    
    # . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .
    # Still didn't find root folder?! Start searching towards the system root directory
    
    curr_path = working_path
    while True:
        
        # Check for the target folder in the current path
        if target_folder in os.listdir(curr_path):
            root_path = curr_path
            return root_path
        
        # Step one folder up and try again, unless we hit the root path, then stop
        old_path = curr_path
        curr_path = os.path.dirname(curr_path)
        if old_path == curr_path:
            break
    
    # . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .
    # Now we're in trouble. Try searching inside all the working directory folders
    
    print("Trying to find '{}' folder. Searching down path...".format(target_folder))
    for parent, dirs, files in os.walk(working_path):
        print(parent)
        print(dirs)
        print(files)
        if target_folder in dirs:
            root_path = parent
            return root_path
        
    raise FileNotFoundError("Couldn't find target folder: {}. Using: {}".format(target_folder, working_path))

# .....................................................................................................................

def find_cameras_folder():
    
    # Check if the camera path is available through the environment, in which case, make/use that path
    env_cameras_folder_path = get_env_cameras_folder()
    if env_cameras_folder_path is not None:
        cameras_folder_path = os.path.expanduser(env_cameras_folder_path)
        os.makedirs(cameras_folder_path, exist_ok = True)
        return cameras_folder_path
    
    # If we don't find an environment path, then find the root folder path and load from the pathing info file
    project_root_path = find_root_path()
    cameras_folder_path = load_pathing_info(project_root_path)
    
    # Quick warning to hopefully avoid accidently syncing outputs to dropbox
    dropbox_in_path = "dropbox" in cameras_folder_path.lower()
    if dropbox_in_path:
        print("")
        print("!" * 36)
        print("WARNING:")
        print("  Dropbox found in camera folder path!")
        print("  {}".format(cameras_folder_path))
        print("!" * 36)
        sleep(2.5)
        
    # Create the folder if it doesn't exist yet (and give feedback about it)
    if not os.path.exists(cameras_folder_path):
        os.makedirs(cameras_folder_path, exist_ok = True)
        print("")
        print("*" * 36)
        print("Camera folder not found. folder will be created:")
        print("  {}".format(cameras_folder_path))
        print("*" * 36)
    
    return cameras_folder_path

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Folder pathing

# .....................................................................................................................

def build_camera_path(cameras_folder, camera_select, *path_joins):
    return os.path.join(cameras_folder, camera_select, *path_joins)

# .....................................................................................................................

def build_config_folder_path(cameras_folder, camera_select, *path_joins):
    return build_camera_path(cameras_folder, camera_select, "config", *path_joins)

# .....................................................................................................................
    
def build_defaults_folder_path(project_root_path, *path_joins):
    return os.path.join(project_root_path, "defaults", *path_joins)

# .....................................................................................................................
    
def build_resources_folder_path(cameras_folder, camera_select, *path_joins):
    return build_camera_path(cameras_folder, camera_select, "resources", *path_joins)

# .....................................................................................................................

def build_logging_folder_path(cameras_folder_path, camera_select, *path_joins):
    return build_camera_path(cameras_folder_path, camera_select, "logs", *path_joins)

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Default configurations

# .....................................................................................................................

def list_default_config_options(project_root_path):
    
    '''
    Function which lists all default configurations (i.e. folder names within the defaults folder)
    Note that default configs are stored in folders that are assumed to be prefixed with an integer followed
    by an underscore. For example '0_blank'. The prefixed integer is used to enforce consistent sorting order.
    However, this function will return both the sorted original folder names, along with 'nice' versions
    of the same folder names, with prefixes removed (for display purposes)
    
    Inputs:
        project_root_path -> (String) Path to project root folder. Needed to find defaults folder
    
    Outputs:
        sorted_nice_names_tuple, sorted_original_names_tuple
    '''
    
    # Get pathing to the defaults folder & list the contents
    defaults_folder_root = build_defaults_folder_path(project_root_path)
    default_config_list = os.listdir(defaults_folder_root)
    
    # Error if defaults are missing
    no_defaults = (len(default_config_list) < 1)
    if no_defaults:
        raise FileNotFoundError("No default configurations found!\n@{}".format(defaults_folder_root))
    
    # Assume folders are named with prefixed numbers to enforce order, which we'll want to extract
    folder_index_ints_list = []
    folder_nice_names_list = []
    for each_config_name in default_config_list:
        
        # Try to parse default folder names
        try:
            folder_index_str, *remaining_names_list = each_config_name.split("_")
            folder_index_int = int(folder_index_str)
            folder_nice_name_str = " ".join(remaining_names_list)
            
        except AttributeError:
            print("", 
                  "Error splitting default config name: {}".format(each_config_name),
                  "  Expecting a string...", sep = "\n")
            continue
        
        except ValueError:
            print("",
                  "Error parsing default config index: {}".format(each_config_name),
                  "  Expecting name to start with integer + underscore",
                  "  For example, '7_example_config_name'",
                  sep = "\n")
            continue
        
        # If we get here, we must have parsed the folder name correctly, so add it to the output listing
        folder_index_ints_list.append(folder_index_int)
        folder_nice_names_list.append(folder_nice_name_str)
    
    
    # Sort by folder indexing for consistency
    sorted_default_entries = sorted(zip(folder_index_ints_list, folder_nice_names_list, default_config_list))
    _, sorted_nice_names_tuple, sorted_original_names_tuple = zip(*sorted_default_entries)
    
    return sorted_nice_names_tuple, sorted_original_names_tuple

# .....................................................................................................................

def copy_from_defaults(project_root_path, cameras_folder_path, camera_select, default_select = None,
                       debug_print = False):
    
    '''
    Function which copies all missing folders/files from the specified defaults folder into a specified camera folder
    If a default_select isn't provided, then the first default for the defaults listing will be chosen automatically
    
    Inputs:
        project_root_path -> (String) Path to root project folder
        
        cameras_folder_path, camera_select -> (Strings) Camera pathing
        
        default_select -> (String or None) The name of the defaults folder to copy from. If set to None, then
                          the first folder (after sorting) will be chosen (assumed to be the 'blank' default)
        
        debug_print -> (Boolean) If true, some debugging info will be printed out regarding creation of files
    
    Outputs:
        Nothing!
    '''
    
    # If a default selection isn't provided, pick the 'first' entry from the defaults listing
    if default_select is None:
        _, sorted_default_names_list = list_default_config_options(project_root_path)
        default_select = sorted_default_names_list[0]
    
    # Get pathing to the defaults folder
    defaults_folder_root = build_defaults_folder_path(project_root_path, default_select)
    camera_folder_root = build_camera_path(cameras_folder_path, camera_select)
    
    # Error if missing defaults folder
    no_defaults_folder = (not os.path.exists(defaults_folder_root))
    if no_defaults_folder:
        raise NameError("Default type ({}) not found!".format(default_select))
    
    # Walk thru each folder/file from the default selection and copy only the ones that are missing!
    for default_parent_path, _, each_file_list in os.walk(defaults_folder_root):
        
        # Convert the default pathing to the equivalent camera pathing
        default_rel_path = os.path.relpath(default_parent_path, defaults_folder_root)
        camera_parent_path = os.path.join(camera_folder_root, default_rel_path)
        
        # Make parent folder, if needed
        os.makedirs(camera_parent_path, exist_ok = True)
        if debug_print:
            print("MAKE DIR:", camera_parent_path)
        
        # Copy any missing files from the default folder to the camera folder
        for each_file_name in each_file_list:
            
            # Build pathing to where the equivalent camera file would be
            camera_file_path = os.path.join(camera_parent_path, each_file_name)
            
            # If the equivalent camera file is missing, copy the default file contents over to the camera file path
            camera_file_exists = os.path.exists(camera_file_path)
            if not camera_file_exists:
                default_file_path = os.path.join(default_parent_path, each_file_name)
                copyfile(default_file_path, camera_file_path, follow_symlinks = False)
                
                if debug_print:
                    print("  MAKE FILE: {}".format(camera_file_path), 
                          "      (from: {})".format(default_file_path), sep = "\n")
            else:
                if debug_print:
                    print("  NO COPY:", camera_file_path)
    
    return

# .....................................................................................................................
# .....................................................................................................................
    

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap


