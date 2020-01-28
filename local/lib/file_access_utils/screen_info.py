#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Oct  9 18:01:19 2019

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

from local.lib.file_access_utils.settings import load_screen_info

# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes

class Screen_Info:
    
    # .................................................................................................................
    
    def __init__(self, project_root_path):
        
        # Load screen info file
        self._screen_info_dict = load_screen_info(project_root_path)
        
        # Split screen info into dictionaries for each use case
        self._screen_dict = self._screen_info_dict["screen"]
        self._controls_dict = self._screen_info_dict["controls"]
        self._displays_dict = self._screen_info_dict["displays"]
        self._feedback_dict = self._screen_info_dict["feedback"]
        
    # .................................................................................................................
    
    def __repr__(self):
        
        repr_strs = ["Screen:"]
        longest_key = max((len(each_key) for each_key in self._screen_dict.keys()))
        for each_key, each_value in self._screen_dict.items():
            repr_strs += ["  {}: {}".format(each_key.rjust(longest_key), each_value)]
            
        repr_strs += ["", "Controls:"]
        longest_key = max((len(each_key) for each_key in self._controls_dict.keys()))
        for each_key, each_value in self._controls_dict.items():
            repr_strs += ["  {}: {}".format(each_key.rjust(longest_key), each_value)]
            
        repr_strs += ["", "Displays:"]
        longest_key = max((len(each_key) for each_key in self._displays_dict.keys()))
        for each_key, each_value in self._displays_dict.items():
            repr_strs += ["  {}: {}".format(each_key.rjust(longest_key), each_value)]
            
        repr_strs += ["", "Feedback:"]
        longest_key = max((len(each_key) for each_key in self._feedback_dict.keys()))
        for each_key, each_value in self._feedback_dict.items():
            repr_strs += ["  {}: {}".format(each_key.rjust(longest_key), each_value)]
    
        return "\n".join(repr_strs)
    
    # .................................................................................................................
    
    def screen(self, *return_args):
        return self._bundle_return(self._screen_dict, return_args)
    
    # .................................................................................................................
    
    def controls(self, *return_args):
        return self._bundle_return(self._controls_dict, return_args)
    
    # .................................................................................................................
    
    def displays(self, *return_args):
        return self._bundle_return(self._displays_dict, return_args)
    
    # .................................................................................................................
    
    def feedback(self, *return_args):
        return self._bundle_return(self._feedback_dict, return_args)
    
    # .................................................................................................................
    
    def _bundle_return(self, dictionary, return_args):
        
        only_1_arg = (len(return_args) == 1)
        return dictionary[return_args[0]] if only_1_arg else [dictionary[each_arg] for each_arg in return_args]
    
    # .................................................................................................................
    # .................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

# .....................................................................................................................

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap
