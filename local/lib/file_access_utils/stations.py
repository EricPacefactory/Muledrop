#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Jun 26 15:07:24 2020

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

from local.lib.file_access_utils.shared import build_config_folder_path, url_safe_name_from_path
from local.lib.file_access_utils.configurables import unpack_config_data, unpack_access_info
from local.lib.file_access_utils.logging import build_configurables_log_path
from local.lib.file_access_utils.json_read_write import load_config_json

from local.eolib.utils.files import get_file_list


# ---------------------------------------------------------------------------------------------------------------------
#%% Pathing functions

# .....................................................................................................................

def build_station_config_folder_path(location_select_folder_path, camera_select, *path_joins):
    ''' Function which builds the path the folder containing station configuration files '''
    return build_config_folder_path(location_select_folder_path, camera_select, "stations", *path_joins)

# .....................................................................................................................

def build_station_config_file_path(location_select_folder_path, camera_select, station_name):
    ''' Function which builds the pathing to a config file for the given station name '''
    return build_station_config_folder_path(location_select_folder_path, camera_select, "{}.json".format(station_name))

# .....................................................................................................................

def build_stations_logging_folder_path(location_select_folder_path, camera_select, station_name):
    ''' Function which builds the pathing to a folder container logging files for station configurables'''
    return build_configurables_log_path(location_select_folder_path, camera_select, "station", station_name)

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Access functions

# .....................................................................................................................

def create_new_station_prompt_entry():
    
    '''
    Dummy function used to standardize the appearance of the 'create new'
    option when selecting stations from a menu'''
    
    return "Create new station"

# .....................................................................................................................

def get_station_config_paths(station_config_folder_path):
    
    '''
    Function for getting a list of station config files 
    located at the provided station_folder_path input argument.
    
    Inputs:
        station_config_folder_path -> String. Full path to folder containing station config files.
                                      (Can be built using the build_station_config_folder_path function)
    
    Outputs:
        station_config_paths_list -> List of strings. Contains a list of full paths to the station config files
        
        station_names_list -> List of strings. Contains a 'clean' copy of the station name
    '''
    
    # Get a listing of all available station configs
    station_config_paths_list = get_file_list(station_config_folder_path,
                                              show_hidden_files = False,
                                              create_missing_folder = True,
                                              return_full_path = True,
                                              sort_list = True)
    
    # Construct 'safe' list of names
    station_names_list = [url_safe_name_from_path(each_path) for each_path in station_config_paths_list]
    
    return station_config_paths_list, station_names_list

# .....................................................................................................................

def get_target_station_names_and_paths_lists(location_select_folder_path, camera_select, station_script_name):
    
    ''' 
    Function which returns a list of existing station names and corresponding loading paths
    Filters out stations whose script names do not match the target script name
    '''
    
    # Build pathing to station config files
    station_configs_folder_path = build_station_config_folder_path(location_select_folder_path, camera_select)
    
    # Load all config data so we can filter out only the target configs
    all_config_paths_dict, all_config_data_dict = load_all_station_config_data(station_configs_folder_path,
                                                                               load_hidden_files = False,
                                                                               create_missing_folder = True)
    
    # Get names in sorted order for output, for consistency
    all_names_sorted = sorted(list(all_config_paths_dict.keys()))
    
    # Build listing of all station names & paths that match our target script name
    sorted_names_list = []
    sorted_paths_list = []
    for each_station_name in all_names_sorted:
        
        # Pull out the script name from the config data
        each_config_data_dict = all_config_data_dict[each_station_name]
        loaded_access_info_dict, _ = unpack_config_data(each_config_data_dict)
        loaded_script_name, _ = unpack_access_info(loaded_access_info_dict)
        
        # Only store the name/path if the loaded script name info matches our target
        matches_target_script_name = (loaded_script_name == station_script_name)
        if matches_target_script_name:
            sorted_names_list.append(each_station_name)
            sorted_paths_list.append(all_config_paths_dict[each_station_name])
    
    return sorted_names_list, sorted_paths_list

# .....................................................................................................................

def load_all_station_config_data(station_configs_folder_path, load_hidden_files = False, create_missing_folder = True):
        
        '''
        Function which finds and loads all station config data & config file paths.
        Results are stored in dictionaries which are 'keyed' using the station names ('safe' file names)
        
        Inputs:
            load_hidden_file -> (Boolean) If true, hidden configs will also be loaded
            
            create_missing_folder -> (Boolean) If true, the station config folder will be created if it is missing
        
        Outputs:
            all_config_paths_dict, all_config_data_dict
        '''
        
        # Initialize outputs
        all_config_data_dict = {}
        all_config_paths_dict = {}
        
        # Get listing of all config file paths
        all_station_config_paths_list = get_file_list(station_configs_folder_path,
                                                      show_hidden_files = load_hidden_files,
                                                      create_missing_folder = create_missing_folder,
                                                      return_full_path = True,
                                                      sort_list = False)
        
        # Load all config data and store by station (file) name
        for each_config_path in all_station_config_paths_list:
            
            # Get a name for reference and the configuration data
            station_name = url_safe_name_from_path(each_config_path)
            station_config_data_dict = load_config_json(each_config_path)
            
            # Store everything in dictionaries for convenience
            all_config_paths_dict[station_name] = each_config_path
            all_config_data_dict[station_name] = station_config_data_dict
        
        return all_config_paths_dict, all_config_data_dict

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Demo

if __name__ == "__main__":
    
    pass


# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap


