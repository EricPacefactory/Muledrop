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

from local.lib.file_access_utils.shared import url_safe_name_from_path

from local.eolib.utils.function_helpers import dynamic_import_from_module


# ---------------------------------------------------------------------------------------------------------------------
#%% Data creation functions

# .....................................................................................................................

def create_access_info(script_name, configuration_utility_file_dunder = None):
    
    '''
    Helper function which ensures consistent access info structure for configurables
    
    Inputs:
        script_name -> (String) Name of script implementing a specific configurable
        
        configuration_utility_file_dunder -> (String or None) File dunder (__file__) of the script
                                             used to save the config data
    
    Outputs:
        access_info_dict
    '''
    
    # Force the given script/config utility names to have more consistent formatting
    script_name_no_ext = url_safe_name_from_path(script_name)
    config_util_name_no_ext = None
    if configuration_utility_file_dunder is not None:
        config_util_name_no_ext = url_safe_name_from_path(configuration_utility_file_dunder)
    
    # Bundle access info
    access_info_dict = {"script_name": script_name_no_ext,
                        "configuration_utility": config_util_name_no_ext}
    
    return access_info_dict

# .....................................................................................................................

def create_configurable_save_data(script_name, configuration_utility_file_dunder, setup_data_dict):
    
    '''
    Helper function which ensures consistent config file structure for configurables
    
    Inputs:
        script_name -> (String) Name of script implementing a specific configurable
        
        configuration_utility_file_dunder -> (String or None) File dunder (__file__) of the script
                                             used to save the config data
        
        setup_data_dict -> (Dictionary) Configuration data which will be re-loaded into the configurable on setup
    
    Outputs:
        save_data_dict
    '''
    
    # Bundle data in target format
    access_info_dict = create_access_info(script_name, configuration_utility_file_dunder)
    save_data_dict = {"access_info": access_info_dict, "setup_data": setup_data_dict}
    
    return save_data_dict

# .....................................................................................................................

def create_blank_configurable_data_dict(script_name):
    
    # For clarity
    configuration_utility_file_dunder = None
    setup_data_dict = {}
    
    # Bundle data in target format
    access_info_dict = create_access_info(script_name, configuration_utility_file_dunder)
    blank_config_data_dict = {"access_info": access_info_dict, "setup_data": setup_data_dict}
    
    return blank_config_data_dict

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
    This function will raise an KeyError if the script information is missing from the access info
    
    Inputs:
        access_info_dict -> (Dictionary) Configuration data describing how to access files needed to load a
                            given configurable. Assumed to have been already unpacked using 
                            the 'unpack_config_data' function
    
    Outputs:
        script_name_no_ext, configuration_utility_no_ext
    
    Note: The 'configuration utility' may be None if a utility was not used to generate the data
    '''
    
    configuration_utility_no_ext = access_info_dict.get("configuration_utility", None)
    
    try:
        script_name_no_ext = access_info_dict["script_name"]
    
    except KeyError:
        err_msg_list = ["",
                        "Error unpacking access info data!",
                        "Expecting key: script_name",
                        ""]
        raise KeyError("\n".join(err_msg_list))
    
    return script_name_no_ext, configuration_utility_no_ext

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Formatting functions

# .....................................................................................................................

def check_matching_access_info(config_data_dict_A, config_data_dict_B):
    
    '''
    Helper function used to check if two configurations share the same access info
    Intended for use in cases where loaded data may be overridden by a target script,
    mostly likely for re-configuration purposes
    
    Inputs:
        config_data_dict_A, config_data_dict_B -> (Dictionary) Configurations to compare
    
    Outputs:
        matching_access_info
    '''
    
    # First get the access info from each configuration
    access_info_dict_A, _ = unpack_config_data(config_data_dict_A)
    access_info_dict_B, _ = unpack_config_data(config_data_dict_B)
    
    # Now get the script name info, which we'll use for the comparison (don't care about config util!)
    script_name_A, _ = unpack_access_info(access_info_dict_A)
    script_name_B, _ = unpack_access_info(access_info_dict_B)
    
    # Check for matches
    matching_script_name = (script_name_A == script_name_B)
    
    return matching_script_name

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Dynamic importing functions

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

def dynamic_import_configurable(dot_path):
    
    '''
    Function used to dynamically import configurable classes. Note that this function returns
    a python class (!!), which will still need to be initialized. 
    -> Assumes that the class to be imported is named 'Configurable'
    
    Inputs:
        dot_path -> (String) Import path to be dynamically imported. For example,
                    "local.configurables.core.tracker.example_tracker"
                    These paths can be generated using the 'configurable_dot_path(...)' function
    
    Outputs:
        Imported_Class
    '''
    
    # Hard-coded name for initialization. May want to change this while debugging, but be careful!!!
    init_class_name = "Configurable"
    return dynamic_import_from_module(dot_path, init_class_name)

# .....................................................................................................................

def dynamic_import_core(core_stage_name, script_name):
    
    ''' Helper function used to dynamically import classes for 'core' configurables '''
    
    # Build target dot pathing
    core_dot_path = configurable_dot_path("core", core_stage_name, script_name)
    
    return dynamic_import_configurable(core_dot_path)

# .....................................................................................................................

def dynamic_import_externals(externals_type, script_name):
    
    ''' Helper function used to dynamically import classes for 'externals' configurables '''
    
    # Build target dot pathing
    externals_dot_path = configurable_dot_path("externals", externals_type, script_name)
    
    return dynamic_import_configurable(externals_dot_path)

# .....................................................................................................................

def dynamic_import_stations(script_name):
    
    ''' Helper function used to dynamically import classes for 'stations' configurables '''
    
    # Build target dot pathing
    stations_dot_path = configurable_dot_path("stations", script_name)
    
    return dynamic_import_configurable(stations_dot_path)

# .....................................................................................................................

def dynamic_import_classifier(script_name):
    
    ''' Helper function used to dynamically import classes for 'classifier' configurables '''
    
    # Build target dot pathing
    classifier_dot_path = configurable_dot_path("after_database", "classifier", script_name)
    
    return dynamic_import_configurable(classifier_dot_path)

# .....................................................................................................................

def dynamic_import_summary(script_name):
    
    ''' Helper function used to dynamically import classes for 'summary' configurables '''
    
    # Build target dot pathing
    rules_dot_path = configurable_dot_path("after_database", "summary", script_name)
    
    return dynamic_import_configurable(rules_dot_path)

# .....................................................................................................................

def dynamic_import_rules(script_name):
    
    ''' Helper function used to dynamically import classes for 'rules' configurables '''
    
    # Build target dot pathing
    rules_dot_path = configurable_dot_path("after_database", "rules", script_name)
    
    return dynamic_import_configurable(rules_dot_path)

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap

