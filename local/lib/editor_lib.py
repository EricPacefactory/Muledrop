#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon May  6 12:46:29 2019

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

import argparse

from eolib.utils.cli_tools import cli_select_from_list

# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes


class Edit_Selector:
    
    '''
    This class is just a wrapper for the more general resource selector (from selection_utils.py)
    It provides slightly different feedback when using the selection functions, more suited to editing
    '''
    
    # .................................................................................................................
    
    def __init__(self, selector_ref):
        
        self.select = selector_ref
    
    # .................................................................................................................
    
    def entity(self, action_text, show_camera = True, show_user = True, show_task = True, show_video = True):
        
        # Offer the following entity options to the user
        camera_option = "Camera"
        user_option = "User"
        task_option = "Task"
        video_option = "Video"
        
        # Build prompt list
        entity_options_prompt = []
        entity_options_prompt += [camera_option] if show_camera else []
        entity_options_prompt += [user_option] if show_user else []
        entity_options_prompt += [task_option] if show_task else []
        entity_options_prompt += [video_option] if show_video else []
        
        # Ask for user entity (or quit if no selection is made)
        try:
            prompt_msg = "Select entity to {}:".format(action_text)
            select_idx, entry_select = cli_select_from_list(entity_options_prompt, 
                                                            prompt_heading = prompt_msg,
                                                            default_selection = None)
        except ValueError:
            self.no_selection_quit()
            
        # Create a simple lookup table as an output
        lut_out = {"camera": (entry_select == camera_option),
                   "user": (entry_select == user_option),
                   "task": (entry_select == task_option),
                   "video": (entry_select == video_option)}
        
        return lut_out

    # .................................................................................................................
    
    def camera(self, camera_select = None):
        
        # Provide feedback about having to select the camera first
        if camera_select is None:
            print("", "/" * 32,
                  "  Must select a camera first",
                  "/" * 32, sep="\n")
        
        # Select camera
        try:
            camera_name, camera_path = self.select.camera(camera_select = camera_select)
        except ValueError:
            self.no_selection_quit()
            
        return camera_name, camera_path

    # .................................................................................................................
    
    def user(self, camera_select, user_select = None):
        
        # Provide feedback about having to select the user first
        if user_select is None:
            print("", "/" * 32,
                  "  Must select a user first",
                  "/" * 32, sep="\n")
        
        # Select user
        try:
            user_name, user_path = self.select.user(camera_select, 
                                                    user_select = user_select)
        except ValueError:
            self.no_selection_quit()
            
        return user_name, user_path

    # .................................................................................................................
    
    def task(self, camera_select, user_select, task_select = None):
        
        # Provide feedback about having to select the task first
        if task_select is None:
            print("", "/" * 32,
                  "  Must select a task first",
                  "/" * 32, sep="\n")
        
        # Select task
        try:
            task_name, task_path = self.select.task(camera_select, 
                                                    user_select, 
                                                    task_select = task_select)
        except ValueError:
            self.no_selection_quit()
            
        return task_name, task_path

    # .................................................................................................................
    
    def video(self, camera_select, video_select = None, show_rtsp = True):
        
        # Provide feedback about having to select the video first
        if video_select is None:
            print("", "/" * 32,
                  "  Must select a video first",
                  "/" * 32, sep="\n")
        
        # Select video
        try:
            video_name, video_path = self.select.video(camera_select, 
                                                       video_select = video_select,
                                                       show_rtsp_option = show_rtsp)
        except ValueError:
            self.no_selection_quit()
            
        return video_name, video_path

    # .................................................................................................................
    
    @staticmethod
    def no_selection_quit():
        print("")
        print("No selection. Quitting...")
        print("")
        safe_quit()
        
    # .................................................................................................................
    # .................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

# .....................................................................................................................

def safe_quit():
    if any([("spyder" in envkey.lower()) for envkey in os.environ.keys()]): 
        raise SystemExit("Spyder Quit")
    quit()

# .....................................................................................................................

def parse_selection_args(custom_arg_parser_function = None, *, 
                         show_camera = True,
                         show_user = True,
                         show_task = True,
                         show_video = True):
    
    # Construct the argument parser
    ap = argparse.ArgumentParser()
    
    if show_camera:
        ap.add_argument("-c", "--camera",
                        default = None,
                        type = str,
                        help="Camera selection")
    
    if show_user:
        ap.add_argument("-u", "--user",
                        default = None,
                        type = str,
                        help="User selection")
    
    if show_task:
        ap.add_argument("-t", "--task",
                        default = None,
                        type = str,
                        help="Task selection")
    
    if show_video:
        ap.add_argument("-v", "--video",
                        default = None,
                        type = str,
                        help="Video selection")
        
    # Add custom arguments if a function is provided
    if custom_arg_parser_function is not None:
        ap = custom_arg_parser_function(ap)

    # Gather arguments into a dictionary for easier use
    args = vars(ap.parse_args())
    
    return args

# .....................................................................................................................
# .....................................................................................................................
    
# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap



