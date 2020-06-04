#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat May 11 11:28:07 2019

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

from local.lib.file_access_utils.shared import build_user_folder_path
from local.lib.file_access_utils.logging import build_configurables_log_path
from local.lib.file_access_utils.json_read_write import save_config_json

# ---------------------------------------------------------------------------------------------------------------------
#%% Pathing functions

# .....................................................................................................................

def build_core_folder_path(cameras_folder, camera_select, user_select, *path_joins):
    ''' Function which builds the path the folder containing core configuration files '''
    return build_user_folder_path(cameras_folder, camera_select, user_select, "core", *path_joins)

# .....................................................................................................................

def build_config_save_path(cameras_folder, camera_select, user_select, stage_name):
    ''' Function which builds the pathing for loading/saving a specific core config file '''    
    config_file_name = "".join([stage_name, ".json"])
    return build_core_folder_path(cameras_folder, camera_select, user_select, config_file_name)

# .....................................................................................................................

def build_core_logging_folder_path(cameras_folder_path, camera_select, stage_name):
    return build_configurables_log_path(cameras_folder_path, camera_select, "core", stage_name)

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Pathing functions

# .....................................................................................................................

def get_ordered_core_sequence():
    
    ''' Function which provides the (hard-coded) core processing sequence '''
    
    ordered_core_processing_sequence = \
    ["preprocessor",
     "foreground_extractor",
     "pixel_filter",
     "detector",
     "tracker"]
    
    return ordered_core_processing_sequence
    
# .....................................................................................................................

def get_ordered_config_paths(core_folder_path):
    
    '''
    Function for getting ordered lists of the core config files 
    located at the provided core_folder_path input argument.
    
    Inputs:
        core_folder_path -> String. Full path to folder containing core config files. 
                            (Can be built using the build_core_folder_path function)
    
    Outputs:
        ordered_config_path_list -> List of strings. Contains an ordered list of full paths 
                                    to the core config files. Ordering is hard-coded
        
        ordered_stage_name_list -> List of strings. Contains a 'clean' copy of the stage names, in order        
    '''
    
    # Get ordered sequence
    ordered_stage_name_list = get_ordered_core_sequence()
    
    # Get a listing of all available core configs
    core_config_file_list = os.listdir(core_folder_path)
    
    # Construct the pathing to each config file, in the proper order!
    ordered_config_files = []
    for each_stage in ordered_stage_name_list:
        
        # For each stage (in order), add the matching file name to the output ordered list
        for each_file in core_config_file_list:
            if each_stage in each_file.lower():
                ordered_config_files.append(each_file)
                break
        else:
            raise NameError("Missing core configuration file for stage: {}".format(each_stage))
            
    ordered_config_path_list = [os.path.join(core_folder_path, each_file) for each_file in ordered_config_files]
    
    return ordered_config_path_list, ordered_stage_name_list

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Config functions

# .....................................................................................................................
    
def save_core_config(cameras_folder, camera_select, user_select,
                     stage_name, script_name, class_name, config_data, confirm_save = True):
    
    # Build save pathing
    core_config_folder_path = build_core_folder_path(cameras_folder, camera_select, user_select)
    config_file_paths, stage_name_order = get_ordered_config_paths(core_config_folder_path)
    
    if stage_name not in stage_name_order:
        raise NameError("Stage not recognized! ({}) Expecting: {}".format(stage_name, stage_name_order))
    stage_index = stage_name_order.index(stage_name)
    save_file_path = config_file_paths[stage_index]
    
    # Build the data structure for core config data
    save_data = {"access_info": {"script_name": script_name,
                                 "class_name": class_name},
                 "setup_data": config_data}
    
    # Fully overwrite the existing config
    if confirm_save:
        save_config_json(save_file_path, save_data)
    
    return save_file_path, save_data

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Demo

if __name__ == "__main__":
    
    pass

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap

