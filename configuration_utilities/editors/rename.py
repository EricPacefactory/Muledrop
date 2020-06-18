#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon May  6 12:54:48 2019

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

from local.lib.ui_utils.cli_selections import Resource_Selector
from local.lib.ui_utils.editor_lib import Edit_Selector, parse_editor_args

from local.lib.file_access_utils.video import rename_video_in_files_dict

from local.eolib.utils.cli_tools import cli_prompt_with_defaults
from local.eolib.utils.quitters import ide_quit

# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes
    
class Edit_Renamer:
    
    def __init__(self, editor_ref):
        
        # Store editor, since we'll need it when selecting nested entities
        self.edit = editor_ref
        
        # Store some paths for convenience
        self.project_root_path, self.cameras_folder_path = self.edit.select.get_cameras_root_pathing()
        
    # .................................................................................................................
    
    def _rename_feedback(self, current_name, current_path, new_name, new_path):
        
        rel_cur_path = os.path.relpath(current_path, self.project_root_path)
        rel_new_path = os.path.relpath(new_path, self.project_root_path)
        print("",
              "Renamed: {}".format(current_name),
              "@ {}".format(rel_cur_path),
              "",
              "To: {}".format(new_name),
              "@ {}".format(rel_new_path),
              "", sep="\n")
        
        # Quit after feedback, since renaming can mess with file pathing (force quit/restart)
        ide_quit()
        
    # .................................................................................................................
    
    def _rename_file_or_folder(self, file_or_folder_path, 
                               new_name = None, 
                               force_same_ext = True, 
                               feedback_and_quit = True):
        
        # Store old name/path
        old_name, old_path, old_dir = _split_name_path_dir(file_or_folder_path)
        
        # Get user input for new name
        interactive_prompt = (new_name is None)
        if interactive_prompt:
            new_name = _rename_prompt(old_name)
        
        # Force file extensions (or lack-thereof) to match after renaming
        # (Note: splitext doesn't treat hidden files/folders as extensions!)
        if force_same_ext:
            old_name_only, old_ext = os.path.splitext(old_name)
            new_name_only, new_ext = os.path.splitext(new_name)
            new_name = "".join([new_name_only, old_ext])
            
        # Get rid of spaces
        new_name = new_name.replace(" ", "_")
        
        # Create the new path and rename the original file/folder
        new_path = os.path.join(old_dir, new_name)
        os.rename(old_path, new_path)
        
        # Some feedback then quit, since renaming can mess with pathing references
        if feedback_and_quit:
            self._rename_feedback(old_name, old_path, new_name, new_path)
        
        return new_path, new_name
        
    # .................................................................................................................
    
    def camera(self, camera_select = None, new_name = None):
        
        # First need to select the camera 
        camera_select, camera_path = self.edit.camera(camera_select)
        
        # Rename the camera at the given path
        self._rename_file_or_folder(camera_path, new_name)
        
    # .................................................................................................................
    
    def user(self, camera_select = None, user_select = None, new_name = None):
        
        # First need to select the camera and the user to rename
        camera_select, _ = self.edit.camera(camera_select)
        user_select, user_path = self.edit.user(camera_select, user_select)
        
        # Bail if the user tries to rename the "live" user option
        if user_select.lower() == "live":
            print("", "Not allowed to rename the 'live' user!", "Quitting...", "", sep="\n")
            ide_quit()
        
        # If all goes well, ask to rename the selected entry
        self._rename_file_or_folder(user_path, new_name)
        
    # .................................................................................................................
    
    def video(self, camera_select = None, video_select = None, new_name = None):
        
        # First need to select the camera, then the video to rename
        camera_select, _ = self.edit.camera(camera_select)
        video_select, video_path = self.edit.video(camera_select, video_select)
        
        # Ask the user to rename the selected entry
        new_video_name = _rename_prompt(video_select, quit_if_no_change = True)
        rename_video_in_files_dict(self.cameras_folder_path, camera_select, video_select, new_video_name)
        
        # Provide some feedback about the update
        self._rename_feedback(video_select, video_path, new_video_name, video_path)
        
    # .................................................................................................................
    # .................................................................................................................
    
# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

# .....................................................................................................................

def _split_name_path_dir(file_or_folder_path):
    
    full_name = os.path.basename(file_or_folder_path)
    full_path = file_or_folder_path
    full_dir = os.path.dirname(file_or_folder_path)
    
    return full_name, full_path, full_dir

# .....................................................................................................................
    
def _rename_prompt(old_name, quit_if_no_change = True):
        
    # Ask for new name
    new_name = cli_prompt_with_defaults(prompt_message = "Enter new name: ",
                                        default_value = old_name,
                                        return_type = str)
    
    # Avoid os access if there is no change to the naming
    if quit_if_no_change:
        if (old_name == new_name):
            print("", "Same name. Renaming cancelled!", "Quitting...", "", sep="\n")
            ide_quit()
    
    return new_name

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Custom arguments
    
# .....................................................................................................................
    
def custom_arguments(argparser):
    
    argparser.add_argument("-rc", "--rename_camera",
                           default = None,
                           type = str,
                           help = "Rename existing camera entry")
    
    argparser.add_argument("-ru", "--rename_user",
                           default = None,
                           type = str,
                           help = "Rename existing user entry")
    
    argparser.add_argument("-rv", "--rename_video",
                           default = None,
                           type = str,
                           help = "Rename existing video entry")
    
    argparser.add_argument("-x", "--example",
                           default = False,
                           action = "store_true",
                           help = "Print example usage and close")
    
    return argparser

# .....................................................................................................................
    
def parse_rename_selection(script_arguments):
    
    # Return an argument-based entity selection to override (if not None) the interactive prompt
    arg_entity_select = {"camera": script_arguments["rename_camera"],
                         "user": script_arguments["rename_user"],
                         "video": script_arguments["rename_video"]}
    
    # Return different things depending on whether 0, 1 or >1 new entity renaming flags were provided
    total_true = sum([int(each_name is not None) for each_name in arg_entity_select.values()])
    if total_true < 1:
        # Skip using args, will instead provide interactive prompt
        arg_entity_select = None
        new_name = None
    elif total_true > 1:
        # Raise an error if more than one thing is being renamed
        raise AttributeError("Must specify only a single 'rename *' entry for renaming!")
    else:
        # Select the non-none name from the set of values
        new_name = [each_name for each_name in arg_entity_select.values() if each_name is not None]
        new_name = new_name[0] if len(new_name) > 0 else None
    
    return arg_entity_select, new_name

# .....................................................................................................................
    
def example_message(script_arguments):
    
    # If the example trigger isn't provided, don't do anything
    if not script_arguments["example"]:
        return
    
    # Print out example argument usage
    print("",
          "OVERVIEW: To rename an existing entry, use the appropriate -r* argument,",
          "followed by the new name. Use the selection flags to pick the entity to be renamed.",
          "For example, use -u 'old_user' -ru 'new_name' to rename an existing 'old_user' to 'new_name'.",
          "Only one entry may be renamed per script-call (if more than one -r* is given, the script cancels).",
          "",
          "*Note1: the system requires the 'live' user, so it cannot be renamed!",
          "*Note2: when renaming video files, paths aren't needed, but file extensions are and can't be changed!",
          "",
          "NESTING: With the exception of cameras, all other entries are nested.",
          "Therefore, you'll need to provide the parent selections as follows:",
          "  rename user: requires camera selection (-c)",
          "  rename video: requires camera selection (-c)",
          "",
          "***** EXAMPLE USAGE *****",
          "",
          "Camera renaming:",
          "python3 rename.py -c 'OldCameraName' -rc 'NewCameraName'",
          "",
          "User renaming:",
          "python3 rename.py -c 'SomeCam' -u 'OldTestUser' -ru 'NewUserName'",
          "",
          "Video renaming:",
          "python3 rename.py -c 'A_Cam' -v 'oldfile.avi' -rv 'newfile.avi'",
          "", sep="\n")
    
    # Quit, since the user probably doesn't want to launch into interactive mode from here!
    ide_quit()

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Parse arguments

# Get arguments for this script call
script_args = parse_editor_args(custom_arguments)
camera_select = script_args["camera"]
user_select = script_args["user"]
video_select = script_args["video"]

# Get the entity selection from input arguments (if provided)
script_entity_select, new_name = parse_rename_selection(script_args)

# Handle example printout
example_message(script_args)

    
# ---------------------------------------------------------------------------------------------------------------------
#%% Setup

# Set up resource selector
res_selector = Resource_Selector(load_selection_history = False, 
                                 save_selection_history = False,
                                 show_hidden_resources = False)

# Set up nicer selector wrapper for editing entities, as well as the renaming object for handling entity renaming
edit_selector = Edit_Selector(res_selector)
renamer = Edit_Renamer(edit_selector)


# ---------------------------------------------------------------------------------------------------------------------
#%% Rename

# Have user select an entity to rename
entity_select = script_entity_select
if script_entity_select is None:
    entity_select = edit_selector.entity("rename")

if entity_select["camera"]:
    renamer.camera(camera_select, new_name)
    
if entity_select["user"]:
    renamer.user(camera_select, user_select, new_name)

if entity_select["video"]:
    renamer.video(camera_select, video_select, new_name)
    

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap

'''
TODO:
    - Add logging
'''
