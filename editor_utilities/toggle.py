#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon May  6 15:29:39 2019

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

from local.lib.editor_lib import Edit_Selector, safe_quit, parse_selection_args

from local.lib.selection_utils import Resource_Selector

from local.lib.file_access_utils.video import load_video_file_lists, update_video_file_list

from eolib.utils.cli_tools import cli_select_from_list

# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes
    
class Edit_Toggler:
    
    def __init__(self, editor_ref):
        
        # Store editor, since we'll need it when selecting nested entities
        self.edit = editor_ref
        
        # Store some paths for convenience
        self.project_root_path, self.cameras_folder_path = self.edit.select.get_project_pathing()
    
    # .................................................................................................................
    
    def _toggle_feedback(self, new_state, visible_name, new_path):
        
        # Decide which state info to show, then print the state and pathing info
        state_text = "Enabled" if new_state else "Disabled"
        rel_new_path = os.path.relpath(new_path, self.project_root_path)
        print("",
              "{}: {}".format(visible_name, state_text),
              "@ {}".format(rel_new_path),
              "", sep="\n")
        
        # Quit after feedback, since toggling can mess with file pathing (force quit/restart)
        safe_quit()
    
    # .................................................................................................................
    
    def _toggle_file_or_folder(self, file_or_folder_path, flip_state = True, feedback_and_quit = True):
        
        # Store old name/path
        old_name, old_path, old_dir, old_state = _split_name_path_dir_state(file_or_folder_path)
        
        # Get user input for new state (or auto-flip it if the argument was provided)
        new_state = (not old_state) if flip_state else  _toggle_prompt(old_state)
        
        # Avoid os access if there is no change to the state
        if (old_state == new_state):
            return
        
        # Build new name, based on new state
        vis_name = old_name if old_state else old_name[1:]
        hid_name = "".join([".", old_name]) if old_state else old_name
        
        # Create the new path and rename the original file/folder to change it's visibility
        new_name = vis_name if new_state else hid_name
        new_path = os.path.join(old_dir, new_name)
        os.rename(old_path, new_path)
        
        # Some feedback then quit, since showing/hiding can mess with pathing references
        if feedback_and_quit:
            self._toggle_feedback(new_state, vis_name, new_path)
        
        return new_state, new_path, new_name
    
    # .................................................................................................................
    
    def _toggle_video(self, camera_select, video_path, flip_state = True):
        # Need a special function for videos, as they are stored in a list...
        # ... which need to be updated with new states after toggling
        
        # Check that the file exists
        if not os.path.exists(video_path):
            print("",
                  "Video file not found!",
                  "@ {}".format(video_path),
                  "",
                  "Maybe the file moved or isn't valid on this computer?",
                  "",
                  "Quitting...", sep="\n")
            safe_quit()
            
        # Get the current state of the video, based on the file listing
        _, _, old_state = _video_toggle_state(self.cameras_folder_path, camera_select, video_path)
        
        # Ask the user for the new state (or auto-flip it if the argument was provided)
        new_state = (not old_state) if flip_state else _toggle_prompt(old_state)
        
        # Avoid file access if there was no change in the state
        if (old_state == new_state):
            return
        
        # Update video file listing by flipping which list the video appears in (visible vs. hidden)
        _toggle_video_file_listing(self.cameras_folder_path, camera_select, video_path)
        
        # Give feedback and quit
        video_name = os.path.basename(video_path)
        self._toggle_feedback(new_state, video_name, video_path)
        
    # .................................................................................................................
    
    def camera(self, camera_select = None, flip_state = True):
        
        # First need to select the camera 
        camera_select, camera_path = self.edit.camera(camera_select)
        
        # Toggle the camera at the given path
        self._toggle_file_or_folder(camera_path, flip_state)
    
    # .................................................................................................................
    
    def user(self, camera_select = None, user_select = None, flip_state = True):
        
        # First need to select the camera and corresponding user to toggle
        camera_select, _ = self.edit.camera(camera_select)
        user_select, user_path = self.edit.user(camera_select, user_select)
        
        # Bail if the user tries to toggle the "live" user option
        if user_select.lower() == "live":
            print("", "Not allowed to toggle the 'live' user!", "Quitting...", "", sep="\n")
            safe_quit()
        
        # Ask the user to set the new toggle state
        self._toggle_file_or_folder(user_path, flip_state)
    
    # .................................................................................................................
        
    def task(self, camera_select = None, user_select = None, task_select = None, flip_state = True):
        
        # First need to select the camera & user, then the task to toggle
        camera_select, _ = self.edit.camera(camera_select)
        user_select, _ = self.edit.user(camera_select, user_select)
        task_select, task_path = self.edit.task(camera_select, user_select, task_select)
        
        # Ask the user to set the new toggle state
        self._toggle_file_or_folder(task_path, flip_state)
    
    # .................................................................................................................
        
    def video(self, camera_select = None, video_select = None, flip_state = True):
        
        # First need to select the camera, then the video to toggle
        camera_select, _ = self.edit.camera(camera_select)
        video_select, video_path = self.edit.video(camera_select, video_select, show_rtsp = False)
        
        # Bail if the user tries to toggle the RTSP option
        if video_select.lower() == "rtsp":
            print("", "Not allowed to toggle the RTSP option!", "Quitting...", "", sep="\n")
            safe_quit()
        
        # If all goes well, ask the user to set the new toggle state
        self._toggle_video(camera_select, video_path, flip_state)
        
    # .................................................................................................................
    # .................................................................................................................
    
# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions
    
# .................................................................................................................

def _split_name_path_dir_state(file_or_folder_path):
    
    full_name = os.path.basename(file_or_folder_path)
    full_path = file_or_folder_path
    full_dir = os.path.dirname(file_or_folder_path)
    state = (full_name[0] != ".")   # True if visible, False if hidden
    
    return full_name, full_path, full_dir, state

# .....................................................................................................................
    
def _toggle_prompt(is_visible):
    
    # Offer the following actions to the user
    visible_option = "Visible"
    hidden_option = "Hidden"
    toggle_options_prompt = [visible_option, hidden_option]
    
    # Set up current state indicator
    default_state = visible_option if is_visible else hidden_option
    
    # Ask for user input (or quit if no selection is made)
    try:
        select_idx, entry_select = cli_select_from_list(toggle_options_prompt, 
                                                        prompt_heading = "Select state:",
                                                        default_selection = default_state,
                                                        default_indicator = " >> (current)")
    except ValueError:
        Edit_Selector.no_selection_quit()
        
    # Map 'hidden' to False and 'visible' to True
    new_state = False if (entry_select == hidden_option) else True
    return new_state

# .....................................................................................................................

def _video_toggle_state(cameras_folder, camera_select, video_path):
    
    # Load the video file listing data (contains file lists under visible & hidden dictionary entries)
    file_listing = load_video_file_lists(cameras_folder, camera_select)
    vis_list = file_listing["visible"]
    hid_list = file_listing["hidden"]
    
    # Check if the path (or filename, if local) is in the visible or hidden listing
    check_old = [video_path, os.path.basename(video_path)]  # First check the path, then try the name only
    for video_ref in check_old:
        is_visible = video_ref in vis_list
        is_hidden = video_ref in hid_list
        if is_visible or is_hidden:
            break
    else:
        # Couldn't find the path or filename in either listing! So give up
        print("",
              "Can't find video file listing!",
              "@ {}".format(video_path),
              "",
              "Qutting...", sep="\n")
        safe_quit()
        
    return video_ref, file_listing, is_visible

# .....................................................................................................................
 
def _toggle_video_file_listing(cameras_folder, camera_select, video_path):
    
    # Load the video file listing data (contains file lists under visible & hidden dictionary entries)
    video_ref, file_listing, is_visible = _video_toggle_state(cameras_folder, camera_select, video_path)
    vis_list = file_listing["visible"]
    hid_list = file_listing["hidden"]
        
    # Figure out which list to add-to/remove-from
    remove_from_list = vis_list if is_visible else hid_list
    add_to_list = hid_list if is_visible else vis_list
    
    # First remove the entry from the first list
    remove_idx = remove_from_list.index(video_ref)
    del remove_from_list[remove_idx]
    update_video_file_list(cameras_folder, camera_select, remove_from_list, is_hidden_list = not is_visible)
    
    # Then add the entry to the other list
    add_to_list.append(video_ref)
    update_video_file_list(cameras_folder, camera_select, add_to_list, is_hidden_list = is_visible)
    
# .....................................................................................................................
# .....................................................................................................................
    
# ---------------------------------------------------------------------------------------------------------------------
#%% Custom arguments
    
# .....................................................................................................................
    
def custom_arguments(argparser):
    
    argparser.add_argument("-ec", "--toggle_camera",
                           default = False,
                           action = "store_true",
                           help = "Toggle camera entry")
    
    argparser.add_argument("-eu", "--toggle_user",
                           default = False,
                           action = "store_true",
                           help = "Toggle user entry")
    
    argparser.add_argument("-et", "--toggle_task",
                           default = False,
                           action = "store_true",
                           help = "Toggle task entry")
    
    argparser.add_argument("-ev", "--toggle_video",
                           default = False,
                           action = "store_true",
                           help = "Toggle video entry")
    
    argparser.add_argument("-x", "--example",
                           default = False,
                           action = "store_true",
                           help = "Print example usage and close")
    
    return argparser

# .....................................................................................................................
    
def parse_toggle_selection(script_arguments):
    
    # Return an argument-based entity selection to override (if not None) the interactive prompt
    arg_entity_select = {"camera": script_arguments["toggle_camera"],
                         "user": script_arguments["toggle_user"],
                         "task": script_arguments["toggle_task"],
                         "video": script_arguments["toggle_video"]}
    
    # Return different things depending on whether 0, 1 or >1 new entity toggling flags were provided
    total_true = sum([int(each_flag) for each_flag in arg_entity_select.values()])
    if total_true < 1:
        # Skip using args, will instead provide interactive prompt
        arg_entity_select = None
    elif total_true > 1:
        # Raise an error if more than one thing is being toggled
        raise AttributeError("Must specify only a single 'toggle *' entry for toggling!")
    
    return arg_entity_select

# .....................................................................................................................
    
def example_message(script_arguments):
    
    # If the example trigger isn't provided, don't do anything
    if not script_arguments["example"]:
        return
    
    # Print out example argument usage
    print("",
          "OVERVIEW: Toggle state using the appropriate -e* argument (boolean flag).",
          "For example, to toggle the state of a camera, use -ec. Or -eu for a user.",
          "The name of the target entity is given by the corresponding selection flag.",
          "For example, use -ec -c '.CameraName' to show a previously hidden camera.",
          "Only one entry may be toggled per script-call (if more than one -e* is given, the script cancels).",
          "",
          "*Note1: the system requires the 'live' user, so it cannot be toggled!",
          "*Note2: the rtsp video option cannot be toggled!",
          "*Note3: the hidden identifier '.' must be specified when selecting entities for toggling!",
          "",
          "NESTING: With the exception of cameras, all other entries are nested.",
          "Therefore, you'll need to provide the parent selections as follows:",
          "  toggle user: requires camera selection (-c)",
          "  toggle task: requires camera (-c) and user selection (-u)",
          "  toggle video: requires camera selection (-c)",
          "",
          "***** EXAMPLE USAGE *****",
          "",
          "Camera toggling:",
          "python3 toggle.py -ec -c '.SomeHiddenCamera'",
          "",
          "User toggling:",
          "python3 toggle.py -eu -c 'SuperCam' -u 'UglyUser'",
          "",
          "Task toggling:",
          "python3 toggle.py -et -c 'RealCamera' -u 'RealUser' -t '.SomeTask'",
          "",
          "Video toggling:",
          "python3 toggle.py -ev -c 'A_Cool_Cam' -v '.hidden_video_file.avi'",
          "", sep="\n")
    
    # Quit, since the user probably doesn't want to launch into interactive mode from here!
    safe_quit()

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Parse arguments

# Get arguments for this script call
script_args = parse_selection_args(custom_arguments)
camera_select = script_args["camera"]
user_select = script_args["user"]
task_select = script_args["task"]
video_select = script_args["video"]

# Get the entity selection from input arguments (if provided)
script_entity_select = parse_toggle_selection(script_args)
flip_state = (script_entity_select is not None)

# Handle example printout
example_message(script_args)


# ---------------------------------------------------------------------------------------------------------------------
#%% Setup

# Set up resource selector
res_selector = Resource_Selector(load_selection_history = False, 
                                 save_selection_history = False,
                                 show_hidden_resources = True)

# Set up nicer selector wrapper for editing entities
edit_selector = Edit_Selector(res_selector)
toggler = Edit_Toggler(edit_selector)


# ---------------------------------------------------------------------------------------------------------------------
#%% Toggle

# Have user select an entity to toggle
entity_select = script_entity_select
if script_entity_select is None:
    entity_select = edit_selector.entity("toggle")

if entity_select["camera"]:
    toggler.camera(camera_select)
    
if entity_select["user"]:
    toggler.user(camera_select, user_select)
    
if entity_select["task"]:
    toggler.task(camera_select, user_select, task_select)

if entity_select["video"]:
    toggler.video(camera_select, video_select)
    

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap

'''
TODO:
    - Add logging
'''
