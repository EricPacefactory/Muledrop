#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Apr 11 17:20:58 2019

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

from local.lib.file_access_utils.shared import find_root_path, find_cameras_folder
from local.lib.file_access_utils.structures import build_cameras_tree, build_camera_list
from local.lib.file_access_utils.settings import load_history, save_history
from local.lib.file_access_utils.video import get_video_names_and_paths_lists
from local.lib.file_access_utils.stations import get_target_station_names_and_paths_lists

from local.eolib.utils.cli_tools import cli_select_from_list, keyboard_quit, clean_error_quit


# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes

class Resource_Selector:
    
    # .................................................................................................................
    
    def __init__(self, 
                 load_selection_history = True,
                 save_selection_history = True,
                 show_hidden_resources = False,
                 create_folder_structure_on_select = True):
        
        # Store important pathing info
        self.project_root_path = find_root_path()
        self.cameras_folder_path = find_cameras_folder()
        
        # Load selection defaults
        self.selection_history = load_history(self.project_root_path, enable = load_selection_history)
        self._need_to_save_selection_history = save_selection_history
        
        # Store access settings
        self._show_hidden_resources = show_hidden_resources
        self._need_to_create_folder_structure = create_folder_structure_on_select
    
    # .................................................................................................................
    
    def __repr__(self):
        
        # Build repr output strings
        repr_strs = ["Resource selector",
                     "    Project root path: {}".format(self.project_root_path),
                     "  Cameras folder path: {}".format(self.cameras_folder_path)]
        
        # Add 'notes' depending on what features are active
        if self._need_to_save_selection_history: repr_strs += ["  *** Selection history saving is active"]        
        if self._show_hidden_resources: repr_strs += ["  *** Showing hidden resources"]        
        if self._need_to_create_folder_structure: repr_strs += ["  *** Creating folder structures on selection"]
        
        return "\n".join(repr_strs)
    
    # .................................................................................................................
    
    def get_project_root_pathing(self):
        return self.project_root_path
        
    # .................................................................................................................
        
    def get_cameras_root_pathing(self):        
        return self.project_root_path, self.cameras_folder_path
    
    # .................................................................................................................
    
    def get_cameras_tree(self):
        return build_cameras_tree(self.cameras_folder_path,
                                  show_hidden = self._show_hidden_resources)
    
    # .................................................................................................................
    
    def get_camera_names_and_paths_lists(self, must_have_rtsp = False):
        
        ''' Helper function which returns lists of camera names as well as a list of full paths '''
        
        show_hidden_cameras = self._show_hidden_resources
        camera_names_list, camera_paths_list = build_camera_list(self.cameras_folder_path, 
                                                                 show_hidden_cameras,
                                                                 must_have_rtsp)
        
        return camera_names_list, camera_paths_list
    
    # .................................................................................................................
    
    @clean_error_quit
    @keyboard_quit
    def camera(self, camera_select = None, must_have_rtsp = False, debug_mode = False):
        
        # Get list of available selection options and then (try to) select one
        camera_names_and_paths_lists = self.get_camera_names_and_paths_lists(must_have_rtsp)
        camera_select, path_select = self._make_selection("camera", camera_select, camera_names_and_paths_lists,
                                                          debug_mode = debug_mode)
        
        return camera_select, path_select
    
    # .................................................................................................................
    
    @clean_error_quit
    @keyboard_quit
    def video(self, camera_select, video_select = None, debug_mode = False):
        
        # Get list of available selection options and then (try to) select one
        video_name_path_lists = get_video_names_and_paths_lists(self.cameras_folder_path, 
                                                                camera_select,
                                                                error_if_no_videos = True)
        
        video_select, path_select = self._make_selection("video", video_select, video_name_path_lists,
                                                         zero_indexed = False,
                                                         debug_mode = debug_mode)
        
        return video_select, path_select
    
    # .................................................................................................................
    
    @clean_error_quit
    @keyboard_quit
    def station(self, camera_select, station_script_name, station_select = None, debug_mode = False):
        
        # Get list of existing stations to select
        station_names_list, station_paths_list = get_target_station_names_and_paths_lists(self.cameras_folder_path,
                                                                                          camera_select,
                                                                                          station_script_name)
        
        # Add entry for creating a new station as the first entry
        create_station_name_entry = "Create new station"
        create_station_path_entry = None
        station_names_list.insert(0, create_station_name_entry)
        station_paths_list.insert(0, create_station_path_entry)
        
        # Select a target station
        station_select, path_select = self._make_selection("station", station_select,
                                                           (station_names_list, station_paths_list),
                                                           zero_indexed = True,
                                                           debug_mode = debug_mode)
        
        # If the 'create new' entry is selected, replace the selection with None instead of the 'create' text prompt
        selected_create_new = (station_select == create_station_name_entry)
        if selected_create_new:
            station_select = None
        
        return station_select, path_select
    
    # .................................................................................................................
    
    def save_camera_select(self, camera_select):
        
        ''' Convenience function used to forcefully save a new camera select entry '''
        
        self.selection_history["camera_select"] = camera_select
        save_history(self.project_root_path, self.selection_history, enable = True)
        
        return
    
    # .................................................................................................................
    
    def save_video_select(self, video_select):
        
        ''' Convenience function used to forcefully save a new video select entry '''
        
        self.selection_history["video_select"] = video_select
        save_history(self.project_root_path, self.selection_history, enable = True)
        
        return
    
    # .................................................................................................................
    
    def save_station_select(self, station_select):
        
        ''' Convenience function used to forcefully save a new station select entry '''
        
        # Don't save 'create new' entries
        contains_create_new = ("create new" in station_select.lower())
        if contains_create_new:
            return
        
        self.selection_history["station_select"] = station_select
        save_history(self.project_root_path, self.selection_history, enable = True)
        
        return
    
    # .................................................................................................................
    
    def _make_selection(self, entry_type, default_select, entry_lists, zero_indexed = False, debug_mode = False):
        
        # For convenience
        entry_name_list, entry_path_list = entry_lists
        select_type = entry_type + "_select"
        
        # Provide cli prompt if no selection is provided
        entry_select = default_select
        need_to_prompt = (default_select is None)
        if need_to_prompt:
            _, entry_select = cli_select_from_list(entry_name_list, 
                                                   prompt_heading = "Select a {}:".format(entry_type), 
                                                   default_selection = self.selection_history[select_type],
                                                   zero_indexed = zero_indexed,
                                                   debug_mode = debug_mode)
            
        # Check that selection is valid, if not, error out!
        self._check_selection_is_valid(entry_select, entry_name_list, entry_type)
        
        # Save new selection, if needed
        self._save_selection_history(select_type, entry_select)
        
        # Get the corresponding path, in case it is needed
        entry_index = entry_name_list.index(entry_select)
        entry_path = entry_path_list[entry_index]
        
        return entry_select, entry_path
    
    # .................................................................................................................
    
    def _check_selection_is_valid(self, entry_select, valid_entry_list, entry_label = "entry"):
        if entry_select not in valid_entry_list:
            raise FileNotFoundError("Invalid {} selection: {}".format(entry_label, entry_select))
            
    # .................................................................................................................
    
    def _update_selection_history(self, selection, new_value):
        
        if selection not in self.selection_history.keys():
            raise AttributeError("Invalid history key ({}), can't update selection history!".format(selection))
        self.selection_history[selection] = new_value
        
    # .................................................................................................................
    
    def _save_selection_history(self, selection = None, new_value = None):
        
        # If saving is triggered by a new selection, update the selection history before saving
        if selection is not None and new_value is not None:
            self._update_selection_history(selection, new_value)
        
        save_history(self.project_root_path, self.selection_history,
                     enable = self._need_to_save_selection_history)
    
    # .................................................................................................................
    # .................................................................................................................

# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
    
# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

# .....................................................................................................................

# .....................................................................................................................
# .....................................................................................................................
 
# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap


