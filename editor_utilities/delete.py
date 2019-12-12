#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed May  8 16:00:59 2019

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

from shutil import rmtree

from local.lib.editor_lib import Edit_Selector, safe_quit, parse_editor_args

from local.lib.selection_utils import Resource_Selector

from local.lib.file_access_utils.video import load_video_file_lists, update_video_file_list

from eolib.utils.cli_tools import cli_confirm

# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes
    
class Edit_Deleter:
    
    # .................................................................................................................
    
    def __init__(self, editor_ref):
        
        # Store editor, since we'll need it when selecting nested entities
        self.edit = editor_ref
        
        # Store some paths for convenience
        self.project_root_path, self.cameras_folder_path = self.edit.select.get_project_pathing()

    # .................................................................................................................

    def _deletion_feedback(self, deletion_name, deletion_path):
        relative_deletion_path = os.path.relpath(deletion_path, self.project_root_path)
        print("", 
              "Deleted: {}".format(deletion_name),
              "@ {}".format(relative_deletion_path),
              "",
              "Quitting...", 
              "", sep="\n")
        safe_quit()
        
    # .................................................................................................................
    
    def _deletion_feedback_reference_only(self, deletion_name, deletion_path):
        relative_deletion_path = os.path.relpath(deletion_path, self.project_root_path)
        print("", 
              "Deleted reference to: {}".format(deletion_name),
              "@ {}".format(relative_deletion_path),
              "(the original video file still exists)",
              "",
              "Quitting...", 
              "", sep="\n")
        safe_quit()
        
    # .................................................................................................................
    
    def _delete_file_or_folder(self, file_or_folder_path, confirm_delete = False,
                               feedback_and_quit = True):
        
        # Store old name/path
        old_name, old_path, old_dir = _split_name_path_dir(file_or_folder_path)
        
        # Get user input for confirmation
        interactive_prompt = (not confirm_delete)
        if interactive_prompt:
            _delete_prompt(old_name)
        
        # Delete the file or folder (and all contents)
        if os.path.isdir(file_or_folder_path):
            rmtree(file_or_folder_path)
        elif os.path.isfile(file_or_folder_path):
            os.remove(file_or_folder_path)
        else:
            print("", 
                  "Unrecognized target for deletion (folder or file?)", 
                  "Delete cancelled!", 
                  ""
                  "Quitting...", "", sep="\n")
            safe_quit()
            
        # Provide feedback about deletion and quit
        if feedback_and_quit:
            self._deletion_feedback(old_name, old_path)
            safe_quit()

    # .................................................................................................................

    def _delete_video(self, camera_select, video_path, confirm_delete = False):
        # Need a special function for videos, as they are stored in a list...
        # ... which need to be updated based on deletion (the actual file shouldn't be deleted unless local)
        
        # Get the video name
        video_name = os.path.basename(video_path)
        
        # Get user input for confirmation
        interactive_prompt = (not confirm_delete)
        if interactive_prompt:
            _delete_prompt(video_name)
        
        # Update video file listing by removing the target file
        is_local = _prune_video_file_listing(self.cameras_folder_path, camera_select, video_path)
        
        # If the file is local, ask the user if they want to delete it as well (assuming interactive prompt active)
        if is_local:
            
            # Ask the user for confirmation (again) when deleting actual (local) video files
            delete_local = _delete_local_prompt() if interactive_prompt else True
                
            # Delete the local video file if confirmed
            if delete_local:
                self._delete_file_or_folder(video_path, True)
                
        # Give specialized feedback for video reference deletions
        self._deletion_feedback_reference_only(video_name, video_path)
        safe_quit()

    # .................................................................................................................
    
    def camera(self, camera_select = None, confirm_delete = False):
        
        # First need to select the camera 
        camera_select, camera_path = self.edit.camera(camera_select)
        
        # Delete camera at the given path!
        self._delete_file_or_folder(camera_path, confirm_delete)
    
    # .................................................................................................................
        
    def user(self, camera_select = None, user_select = None, confirm_delete = False):
        
        # First need to select the camera and the user to delete
        camera_select, _ = self.edit.camera(camera_select)
        user_select, user_path = self.edit.user(camera_select, user_select)
        
        # Bail if the user tries to delete the "live" user option
        if user_select.lower() == "live":
            print("", "Not allowed to delete the 'live' user!", "Quitting...", "", sep="\n")
            safe_quit()
        
        # If all goes well, ask the user to delete the selected entry
        self._delete_file_or_folder(user_path, confirm_delete)
        
    # .................................................................................................................
        
    def task(self, camera_select = None, user_select = None, task_select = None, confirm_delete = False):
        
        # First need to select the camera & the user, then the task to delete
        camera_select, _ = self.edit.camera(camera_select)
        user_select, _ = self.edit.user(camera_select, user_select)
        task_select, task_path = self.edit.task(camera_select, user_select, task_select)
        
        # Ask the user to delete the selected entry
        self._delete_file_or_folder(task_path, confirm_delete)
    
    # .................................................................................................................
    
    def video(self, camera_select = None, video_select = None, confirm_delete = False):
        
        # First need to select the camera, then the video to delete
        camera_select, _ = self.edit.camera(camera_select)
        video_select, video_path = self.edit.video(camera_select, video_select)
            
        # If all goes well, ask the user to delete the selected entry
        self._delete_video(camera_select, video_path, confirm_delete)
    
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
    
def _delete_prompt(entity_name, quit_if_no = True):
    
    # Ask to delete
    delete_msg = "Deleting: {}\nAre you sure you want to delete?".format(entity_name)
    confirm_delete = cli_confirm(delete_msg, default_response = False)
    
    # Automatically quit if the user doesn't confirm the deletion
    if quit_if_no:
        if not confirm_delete:
            print("", "Delete cancelled!", "Quitting...", "", sep="\n")
            safe_quit()
    
    return confirm_delete

# .....................................................................................................................
    
def _delete_local_prompt():
    # Ask to delete
    confirm_delete = cli_confirm("Video is stored locally! Delete this too?", default_response = True)
    return confirm_delete

# .....................................................................................................................
 
def _prune_video_file_listing(cameras_folder, camera_select, video_path):
    
    # Load the video file listing data (contains file lists under visible & hidden dictionary entries)
    file_listing = load_video_file_lists(cameras_folder, camera_select)
    vis_list = file_listing["visible"]
    hid_list = file_listing["hidden"]
    
    # Check if the path (or filename, if local) is in the visible or hidden listing    
    check_listing = [video_path, os.path.basename(video_path)]  # First check the path, then try the name only
    local_status = [False, True]
    for vid_ref, is_local in zip(check_listing, local_status):
        is_visible = vid_ref in vis_list
        is_hidden = vid_ref in hid_list
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
        
    # Remove the entry from whichever listing it was found in
    change_list = hid_list if is_hidden else vis_list 
    list_idx = change_list.index(vid_ref)
    del change_list[list_idx]
    
    # Update the video file listing with pruned list data
    update_video_file_list(cameras_folder, camera_select, change_list, is_hidden_list = is_hidden)
    
    return is_local

# .....................................................................................................................

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Custom arguments
    
# .....................................................................................................................
    
def custom_arguments(argparser):
    
    argparser.add_argument("-dc", "--delete_camera",
                           default = False,
                           action = "store_true",
                           help = "Delete camera entry")
    
    argparser.add_argument("-du", "--delete_user",
                           default = False,
                           action = "store_true",
                           help = "Delete user entry")
    
    argparser.add_argument("-dt", "--delete_task",
                           default = False,
                           action = "store_true",
                           help = "Delete task entry")
    
    argparser.add_argument("-dv", "--delete_video",
                           default = False,
                           action = "store_true",
                           help = "Delete video entry")
    
    argparser.add_argument("-x", "--example",
                           default = False,
                           action = "store_true",
                           help = "Print example usage and close")
    
    return argparser

# .....................................................................................................................
    
def parse_delete_selection(script_arguments):
    
    # Return an argument-based entity selection to override (if not None) the interactive prompt
    arg_entity_select = {"camera": script_arguments["delete_camera"],
                         "user": script_arguments["delete_user"],
                         "task": script_arguments["delete_task"],
                         "video": script_arguments["delete_video"]}
    
    # Return different things depending on whether 0, 1 or >1 new entity deletion flags were provided
    total_true = sum([int(each_flag) for each_flag in arg_entity_select.values()])
    if total_true < 1:
        # Skip using args, will instead provide interactive prompt
        arg_entity_select = None
    elif total_true > 1:
        # Raise an error if more than one thing is being deleted
        raise AttributeError("Must specify only a single 'delete *' entry for deletion!")
    
    return arg_entity_select

# .....................................................................................................................
    
def example_message(script_arguments):
    
    # If the example trigger isn't provided, don't do anything
    if not script_arguments["example"]:
        return
    
    # Print out example argument usage
    print("",
          "OVERVIEW: To delete an entry, use the appropriate -d* argument (boolean flag)",
          "For example, use -dc to delete a camera, use -dv to delete a video.",
          "The name of the target entry is provided by the corresponding selection flag.",
          "For example, use -dc -c 'CameraName' to delete the camera named 'CameraName'.",
          "Only one entry may be deleted per script-call!",
          "",
          "*Note1: Cannot delete the live user from any camera",
          "*Note2: When deleting videos, remote files will not be deleted (only the reference to them)",
          "",
          "NESTING: With the exception of cameras, all other entries are nested.",
          "Therefore, you'll need to provide the parent selections as follows:",
          "  delete user: requires camera selection (-c)",
          "  delete task: requires camera (-c) and user selection (-u)",
          "  delete video: requires camera selection (-c)",
          "",
          "***** EXAMPLE USAGE *****",
          "",
          "Camera deletion:",
          "python3 delete.py -dc -c 'AccidentalCameraName'",
          "",
          "User deletion:",
          "python3 delete.py -du -c 'SomeCam' -u 'CyaUser'",
          "",
          "Task deletion:",
          "python3 delete.py -dt -c 'ExistingCamera' -u 'ExistingUser' -t 'ByeTask'",
          "",
          "Video deletion:",
          "python3 delete.py -dv -c 'A_Cam' -v 'unneeded_video_file.avi'",
          "", sep="\n")
    
    # Quit, since the user probably doesn't want to launch into interactive mode from here!
    safe_quit()

# .....................................................................................................................
# .....................................................................................................................
        
# ---------------------------------------------------------------------------------------------------------------------
#%% Parse arguments

# Get arguments for this script call
script_args = parse_editor_args(custom_arguments)
camera_select = script_args["camera"]
user_select = script_args["user"]
task_select = script_args["task"]
video_select = script_args["video"]

# Get the entity selection from input arguments (if provided)
script_entity_select = parse_delete_selection(script_args)
confirm_delete = (script_entity_select is not None)

# Handle example printout
example_message(script_args)


# ---------------------------------------------------------------------------------------------------------------------
#%% Setup

# Set up resource selector
res_selector = Resource_Selector(load_selection_history = False, 
                                 save_selection_history = False,
                                 show_hidden_resources = True,
                                 create_folder_structure_on_select = False)

# Set up nicer selector wrapper for editing entities, as well as the creator object for handling entity creation
edit_selector = Edit_Selector(res_selector)
deleter = Edit_Deleter(edit_selector)


# ---------------------------------------------------------------------------------------------------------------------
#%% Creation

# Have user select an entity to create
entity_select = script_entity_select
if script_entity_select is None:
    entity_select = edit_selector.entity("delete")

if entity_select["camera"]:
    deleter.camera(camera_select, confirm_delete)
    
if entity_select["user"]:
    deleter.user(camera_select, user_select, confirm_delete)
    
if entity_select["task"]:
    deleter.task(camera_select, user_select, task_select, confirm_delete)
    
if entity_select["video"]:
    deleter.video(camera_select, video_select, confirm_delete)
    

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap

'''
TODO:
    - Add logging
'''
