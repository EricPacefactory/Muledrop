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




#%% Pathing functions

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
#%% Data creation functions

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
    
    # Force the given script/config utility names to have more consistent formatting
    script_name_no_ext = clean_name(script_name)
    config_util_name_no_ext = None
    if configuration_utility_file_dunder is not None:
        config_util_name_no_ext = clean_name(configuration_utility_file_dunder)
    
    # Bundle access info
    access_info_dict = {"script_name": script_name_no_ext,
                        "class_name": class_name,
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
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Unpacking functions

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
#%% Formatting functions

# .....................................................................................................................

def clean_name(input_name):
    
    ''' Helper function used to ensure consistently formatted naming '''
    
    # Remove pathing in case it was provided so we're always dealing with file names only
    file_name_only = os.path.basename(input_name)
    
    # Remove common naming patterns that may cause problems
    cleaned_name = file_name_only.strip().replace(" ", "_").lower()
    
    # Remove file extension
    name_no_ext, _ = os.path.splitext(cleaned_name.strip().lower())
    
    return name_no_ext

# .....................................................................................................................

def check_matching_access_info(loaded_config_or_access_info_dict, target_script_name, target_class_name):
    
    '''
    Helperf function used to check if some loaded access info matches a target script/class name
    Intended for use in cases where loaded data may be overridden by a target script/class,
    mostly likely for re-configuration purposes
    
    Inputs:
        loaded_config_or_access_info_dict -> (Dictionary) Existing configuration data or access info to check against
        
        target_script_name -> (String) The script name to check against the loaded configuration data
        
        target_class_name -> (String) The class name to check against the loaded configuration data
    
    Outputs:
        matching_access_info
    '''
    
    # Determine if we got the full configuration data or the nested access info as an input
    got_full_config_data = ("access_info" in loaded_config_or_access_info_dict.keys())
    if got_full_config_data:
        loaded_access_info_dict, _ = unpack_config_data(loaded_config_or_access_info_dict)
    else:
        loaded_access_info_dict = loaded_config_or_access_info_dict
    
    # Break apart the loaded access info
    loaded_script_name, loaded_class_name, _ = unpack_access_info(loaded_access_info_dict)
    
    # Make sure we 'clean' the target script name for consistent comparisons
    cleaned_target_script_name = clean_name(target_script_name)
    
    # Check for matches
    matching_script_name = (loaded_script_name == cleaned_target_script_name)
    matching_class_name = (loaded_class_name == target_class_name)
    matching_access_info = (matching_script_name and matching_class_name)
    
    return matching_access_info

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap
