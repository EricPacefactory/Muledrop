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

import cv2
import json
import gzip
import threading

from shutil import copyfile


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

def find_cameras_folder(target_file=".pathing_info"):
    
    # First find the root folder path, which stores the pathing info file
    project_root_path = find_root_path()
    
    # Load camera folder path from the pathing info file (or use a default, if the file isn't available)
    cameras_folder_path = load_pathing_info(project_root_path, target_file)
    
    # Quick warning to hopefully avoid accidently syncing outputs to dropbox
    dropbox_in_path = "dropbox" in cameras_folder_path.lower()
    if dropbox_in_path:
        print("")
        print("!" * 36)
        print("WARNING:")
        print("  Dropbox found in camera folder path!")
        print("  {}".format(cameras_folder_path))
        print("!" * 36)
        
    # Create the folder if it doesn't exist yet (and give feedback about it)
    if not os.path.exists(cameras_folder_path):
        os.makedirs(cameras_folder_path)
        print("")
        print("*" * 36)
        print("Camera folder not found. folder will be created:")
        print("  {}".format(cameras_folder_path))
        print("*" * 36)
    
    return cameras_folder_path

# .....................................................................................................................

def load_pathing_info(project_root_path, target_file=".pathing_info"):
    
    # Set the default path (empty) and the fallback (used if a loaded path is not valid), in case we need it
    fallback_camera_path = os.path.join(project_root_path, "cameras")
    default_camera_path = ""
    
    # Get path to the pathing info file and computer name (since pathing is saved on a per-computer name basis)
    pathing_info_file = os.path.join(project_root_path, target_file)
    computer_name = os.uname().nodename
    pathing_info_dict = {computer_name: default_camera_path}
    
    # Check if pathing info file exists so we can load the camera path
    need_to_save = True
    if os.path.exists(pathing_info_file):
        
        # Load whatever data is in the file, so we can re-save it if the computer name isn't stored in it yet
        with open(pathing_info_file, "r") as in_file:
            loaded_info = json.load(in_file)            
            need_to_save = (computer_name not in loaded_info)
            pathing_info_dict.update(loaded_info)
        
    # Create/update the pathing info file if the computer name wasn't found
    if need_to_save:
        with open(pathing_info_file, "w") as out_file:
            json.dump(pathing_info_dict, out_file, indent = 2)
            
    # Return the project root pathing, if the loaded path is empty or not valid
    pathing_info = os.path.expanduser(pathing_info_dict.get(computer_name))
    if pathing_info == "":
        pathing_info = fallback_camera_path
    elif not os.path.exists(pathing_info):
        print("",
              "Bad pathing info for computer: {}".format(computer_name),
              "  {}".format(pathing_info),
              "Using:",
              "  {}".format(fallback_camera_path),
              "", sep="\n")
        pathing_info = fallback_camera_path
    
    return pathing_info

# .....................................................................................................................
    
def auto_project_root_path(project_root_path):    
    return find_root_path() if project_root_path is None else project_root_path

# .....................................................................................................................
    
def auto_cameras_folder_path(cameras_folder_path):    
    return find_cameras_folder() if cameras_folder_path is None else cameras_folder_path

# .....................................................................................................................

def configurable_dot_path(*module_pathing):
    
    '''
    Takes in any number of strings and generates the corresponding configurable 'dot-path',
    assuming the base pathing is local/configurables/...
    Intended to be used for programmatically importing functions/classes
    
    For example, with inputs ("core", "tracker", "example_tracker.py"), the output would be:
        "local.configurables.core.tracker.example_tracker"
        
    Also accepts paths with slashes. For example ("core", "tracker/example_tracker.py") is also a valid input
    '''
    
    # Remove file extensions and swap slashes ("/") for dots (".")
    clean_names_list = [os.path.splitext(each_module)[0].replace("/", ".") for each_module in module_pathing]
    
    return ".".join(["local", "configurables", *clean_names_list])

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Folder pathing

# .....................................................................................................................

def build_camera_folder_path(cameras_folder, camera_select, *path_joins):
    return os.path.join(cameras_folder, camera_select, *path_joins)

# .....................................................................................................................

def build_user_folder_path(cameras_folder, camera_select, user_select, *path_joins):
    if user_select is None:
        return build_camera_folder_path(cameras_folder, camera_select, "users")    
    return build_camera_folder_path(cameras_folder, camera_select, "users", user_select, *path_joins)

# .....................................................................................................................

def build_task_folder_path(cameras_folder, camera_select, user_select, task_select, *path_joins):
    if task_select is None:
        return build_user_folder_path(cameras_folder, camera_select, user_select, "tasks")    
    return build_user_folder_path(cameras_folder, camera_select, user_select, "tasks", task_select, *path_joins)

# .....................................................................................................................
    
def build_defaults_folder_path(project_root_path, *path_joins):
    return os.path.join(project_root_path, "defaults", *path_joins)

# .....................................................................................................................
    
def build_resources_folder_path(cameras_folder, camera_select, *path_joins):
    return build_camera_folder_path(cameras_folder, camera_select, "resources", *path_joins)

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% File i/o

# .....................................................................................................................
    
def create_json(file_path, json_data, creation_printout = "Creating JSON:", overwrite_existing = False):
    
    # If the file doesn't exist, create it
    file_doesnt_exist = (not os.path.exists(file_path))
    if file_doesnt_exist or overwrite_existing:
        
        if creation_printout:
            print("")
            print(creation_printout)
            print(" ", file_path)
        
        # Write the default to file
        with open(file_path, "w") as out_file:
            json.dump(json_data, out_file, indent = 2, sort_keys = True)
            
# .....................................................................................................................
            
def load_with_error_if_missing(file_path):
    
    # Check that the file path exists
    if not os.path.exists(file_path):
        print("", "",
              "!" * 42,
              "Error reading data:",
              "@ {}".format(file_path),
              "!" * 42,
              "", "", sep="\n")
        raise FileNotFoundError("Couldn't find file for loading!")
    
    # Assuming the file does exist, load it's contents
    with open(file_path, "r") as in_file:
        load_content = json.load(in_file)
        
    return load_content

# .....................................................................................................................
    
def load_or_create_json(file_path, default_content, creation_printout = "Creating JSON:"):
    
    # If the file doesn't exist, create it, then load
    create_json(file_path, default_content, creation_printout, overwrite_existing = False)
    return load_with_error_if_missing(file_path)

# .....................................................................................................................

def load_replace_save(file_path, new_dict_data, indent_data = True, create_if_missing = True):
    
    '''
    Loads an existing file, assumed to hold a dictionary of data,
    then updates the dictionary with the newly provided data,
    and re-saves the file
    '''
    
    # Check if the file exists. If it doesn't and we're not allowed to create it if missing, give an error
    file_exists = os.path.exists(file_path)
    if (not file_exists) and (not create_if_missing):
        raise FileNotFoundError("Couldn't replace file, it doesn't exists: {}".format(file_path))
    
    # Load the target data set or assume it's blank if the path isn't valid
    load_data = load_with_error_if_missing(file_path) if file_exists else {}
            
    # Update with any new data
    load_data.update(new_dict_data)
    
    # Now re-save the (updated) data
    full_replace_save(file_path, load_data, indent_data)
    
    return load_data

# .....................................................................................................................

def full_replace_save(file_path, save_data, indent_data = True):
    
    # Save the data
    indent_amount = 2 if indent_data else None
    with open(file_path, "w") as out_file:
        json.dump(save_data, out_file, indent = indent_amount)
    
    return save_data

# .....................................................................................................................
    
def copy_from_defaults(project_root_path, target_defaults_folder, copy_to_path):
    
    '''
    Function which takes all files in the folder specified from:
        project_root_path/defaults/target_defaults_folder
        
    And copies them to the given 'copy_to_path' folder path.
    This function will not overwrite existing files with the same name!
    '''
    
    # Build pathing to the defaults file and make sure it exists
    target_folder_path = build_defaults_folder_path(project_root_path, target_defaults_folder)
    if not os.path.exists(target_folder_path):
        raise FileNotFoundError("Defaults folder path not found: {}".format(target_folder_path))
        
    # Get all file paths in the target folder so we can copy them to the target copy path
    is_json = lambda file_name: (os.path.splitext(file_name)[1] == ".json")
    file_list = [each_file for each_file in os.listdir(target_folder_path) if is_json(each_file)]
    file_path_list = [os.path.join(target_folder_path, each_file) for each_file in file_list]
    
    for each_file_path in file_path_list:
        
        # Build destination path, and copy the default file over if the file doesn't already exist
        destination_path = os.path.join(copy_to_path, os.path.basename(each_file_path))
        file_doesnt_exist = (not os.path.exists(destination_path))
        if file_doesnt_exist:
            copyfile(each_file_path, destination_path, follow_symlinks = False)
            print("")
            print("DEBUG - calling copy_from_defaults()")
            print("COPY FILES:")
            print("From:", each_file_path)
            print("  To:", destination_path)
            

# .....................................................................................................................

def load_from_defaults(project_root_path, target_defaults_folder, target_file_select):
    
    # Build pathing to the defaults file and make sure it exists
    defaults_file_path = build_defaults_folder_path(project_root_path, target_defaults_folder, target_file_select)
    if not os.path.exists(defaults_file_path):
        raise FileNotFoundError("Defaults file path not found: {}".format(defaults_file_path))
    
    # Load the data from the defaults file
    try:
        default_data = load_with_error_if_missing(defaults_file_path)
            
    except json.JSONDecodeError:
        
        # Handle decoding errors (which occur if the file isn't properly json formatted)
        relative_defaults_path = os.path.relpath(defaults_file_path, project_root_path)
        print("", "",
              "!" * 42,
              "Error reading default JSON data:",
              "@ {}".format(relative_defaults_path),
              "!" * 42,
              "", "", sep="\n")
        
        raise Exception("Formatting error loading default JSON data! ({})".format(target_file_select))
        
    return default_data

# ---------------------------------------------------------------------------------------------------------------------
#%% Threaded i/o

# .....................................................................................................................
    
def threaded_image_save(save_folder_path, save_name, frame_data, save_quality = 20):
    
    # Build save path
    clean_save_name, _ = os.path.splitext(save_name)
    save_path = os.path.join(save_folder_path, "{}.jpg".format(clean_save_name))
    
    # Then save the image data
    successful_save, new_save_thread = False, None
    try:        
        
        # Build weird image quality parameter
        jpg_quality_arg = (cv2.IMWRITE_JPEG_QUALITY, save_quality)
        
        # Create saving thread
        new_save_thread = threading.Thread(target = cv2.imwrite,
                                           args = (save_path,
                                                   frame_data,
                                                   jpg_quality_arg),
                                           daemon = True)
        
        # Start the saving process!
        new_save_thread.start()
        
        # Assume things worked out if we got this far
        successful_save = True
    
    except Exception as err:
        print("", 
              "Error saving image:",
              "@ {}".format(save_path), 
              err,
              "", sep = "\n")

    return successful_save, new_save_thread

# .....................................................................................................................

def threaded_metadata_save(save_folder_path, save_name, metadata, use_gzip = True):
    
    # Build save path
    clean_save_name, _ = os.path.splitext(save_name)
    file_ext = "json.gz" if use_gzip else "json"
    save_path = os.path.join(save_folder_path, "{}.{}".format(clean_save_name, file_ext))
    save_func = save_metadata_gzip if use_gzip else save_metadata_json
    
    # Then save the image data
    successful_save, new_save_thread = False, None
    try:        
        
        # Create saving thread
        new_save_thread = threading.Thread(target = save_func,
                                           args = (save_path,
                                                   metadata),
                                           daemon = True)
        
        # Start the saving process!
        new_save_thread.start()
        
        # Assume things worked out if we got this far
        successful_save = True
    
    except Exception as err:
        print("", 
              "Error saving metadata:",
              "@ {}".format(save_path), 
              err,
              "", sep = "\n")

    return successful_save, new_save_thread

# .....................................................................................................................
    
def save_metadata_json(save_path, json_data):
    with open(save_path, "w") as out_file:
        json.dump(json_data, out_file)
        
# .....................................................................................................................
        
def save_metadata_gzip(save_path, json_data):
    with gzip.open(save_path, "wt", encoding = "ascii") as out_file:
        json.dump(json_data, out_file, separators = (",", ":"))
        
# .....................................................................................................................

def clean_thread_list(thread_list):
    
    # Figure out which threads are safe to remove
    rem_threads_idx = []
    for each_idx, each_thread in enumerate(thread_list):
        if not each_thread.is_alive():
            each_thread.join()
            rem_threads_idx.append(each_idx)
    
    # Remove the threads from our list so we can stop tracking them
    for each_idx in reversed(rem_threads_idx):
        del thread_list[each_idx]
        
    return thread_list

# .....................................................................................................................
# .....................................................................................................................
    
# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap


