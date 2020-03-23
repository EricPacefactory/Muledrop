#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon May  6 11:41:17 2019

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

from local.lib.file_access_utils.structures import create_camera_folder_structure, create_user_folder_structure
from local.lib.file_access_utils.shared import build_camera_path, build_user_folder_path, list_default_types
from local.lib.file_access_utils.video import copy_video_file_local, add_video_to_files_dict

from local.eolib.utils.cli_tools import cli_confirm, cli_select_from_list, cli_prompt_with_defaults
from local.eolib.utils.ranger_tools import ranger_file_select, ranger_exists
from local.eolib.utils.gui_tools import gui_file_select
from local.eolib.utils.quitters import ide_quit

# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes
    
class Edit_Creator:
    
    # .................................................................................................................
    
    def __init__(self, editor_ref):
        
        # Store editor, since we'll need it when selecting nested entities
        self.edit = editor_ref
        
        # Store some paths for convenience
        self.project_root_path, self.cameras_folder_path = self.edit.select.get_project_pathing()

    # .................................................................................................................

    def _creation_feedback(self, creation_name, creation_path):
        relative_creation_path = os.path.relpath(creation_path, self.project_root_path)
        print("", 
              "Created {}!".format(creation_name),
              "@ {}".format(relative_creation_path),
              "",
              "Quitting...", 
              "", sep="\n")
        
    # .................................................................................................................

    def _prompt_for_new_name(self, entity_type, entity_select):
        
        # For convenience
        entity_type_lower = entity_type.lower()        
        new_entity_name = entity_select
        
        # Only provide user prompt if script arguments weren't given
        if entity_select is None:
            prompt_msg = "Enter new {} name: ".format(entity_type_lower)
            new_entity_name = cli_prompt_with_defaults(prompt_message = prompt_msg, return_type = str)
        
        # Quit if the entry is empty
        if new_entity_name is None:
            print("", 
                  "Bad {} name!".format(entity_type_lower), 
                  "", 
                  "Quitting...", 
                  sep="\n")
            ide_quit()
            
        # Convert to a 'safe' format
        safe_new_name = new_entity_name.replace(" ", "_")
        
        return safe_new_name
    
    # .................................................................................................................
    
    def _prompt_for_adding_video(self, new_camera_name):
        user_confirm = cli_confirm("Add video to the new camera ({})?".format(new_camera_name))
        return user_confirm

    # .................................................................................................................
    
    def camera(self, camera_select = None, default_from = None, entity_type = "camera"):
        
        # Get the new name for creation
        new_camera_name = self._prompt_for_new_name(entity_type, camera_select)
            
        # Build path to camera and create camera entry using camera manager
        new_camera_path = build_camera_path(self.cameras_folder_path, new_camera_name)
        
        # Prompt for default to folder structure to use
        default_select = prompt_for_default_select(self.project_root_path, default_from)
        
        # Create the initial camera folder structure
        create_camera_folder_structure(self.project_root_path, 
                                       self.cameras_folder_path, 
                                       new_camera_name,
                                       default_select)
            
        # Some feedback before quitting
        self._creation_feedback(new_camera_name, new_camera_path)
        
        # Prompt to add videos, if camera creation was not triggered from script arguments
        if camera_select is None:
            
            # Ask user if they would like to associate a video with the new camera
            user_confirm = self._prompt_for_adding_video(new_camera_name)
            if user_confirm:
                self.video(new_camera_name, None)
        
        ide_quit()
    
    # .................................................................................................................
        
    def user(self, camera_select = None, user_select = None, default_from = None, entity_type = "user"):
        
        # First need to select the camera 
        camera_select, camera_path = self.edit.camera(camera_select)
        
        # Get the new name for creation
        new_user_name = self._prompt_for_new_name(entity_type, user_select)
            
        # Build path to user folder
        new_user_path = build_user_folder_path(self.cameras_folder_path, camera_select, new_user_name)
        
        # Prompt for default to folder structure to use
        default_select = prompt_for_default_select(self.project_root_path, default_from)
        
        # Create the initial user folder structure
        create_user_folder_structure(self.project_root_path, 
                                     self.cameras_folder_path, 
                                     camera_select, 
                                     new_user_name,
                                     default_select)
        
        # Some feedback before quitting
        self._creation_feedback(new_user_name, new_user_path)
        ide_quit()
    
    # .................................................................................................................
    
    def video(self, camera_select = None, video_select = None):
        
        # For readability
        interactive_prompt = (video_select is None)
        
        # First need to select the camera
        camera_select, _ = self.edit.camera(camera_select)
        
        # Have the user select a video file (or use the provided video_select argument)
        video_path = video_select
        if interactive_prompt:
            video_path = select_video_file_prompt()
 
        # Check if user wants to create a local copy of the video file (i.e. in the camera folder)
        # (Only ask about copying if a video selection argument wasn't provided! No script arg for this...)
        if interactive_prompt:
            copied_local, video_path = copy_video_local_prompt(self.cameras_folder_path, 
                                                               camera_select, 
                                                               video_path)
        
        # Add the new video file to the file record
        video_name = os.path.basename(video_path)
        add_video_to_files_dict(self.cameras_folder_path, camera_select, video_name, video_path)
        
        # Some feedback before quitting
        self._creation_feedback(video_name, video_path)
        ide_quit()
    
    # .................................................................................................................
    # .................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions
    
# .....................................................................................................................
    
def select_video_action():
    
    # Make sure ranger exists before prompting for it...
    ranger_is_installed = ranger_exists()
    
    # Offer the following video selection actions to the user
    add_gui_option = "GUI menu (tkinter)"
    add_cli_option = "CLI menu (ranger)" if ranger_is_installed else "CLI menu (ranger - not installed!"
    add_input_option = "Enter path directly"
    video_action_options_prompt = [add_gui_option, add_cli_option, add_input_option]
        
    
    # Ask for user action (or quit if no selection is made)
    try:
        select_idx, entry_select = cli_select_from_list(video_action_options_prompt, 
                                                        prompt_heading = "Method for video selection:",
                                                        default_selection = None)
    except ValueError:
        Edit_Selector.no_selection_quit()
        
    # Create a simple lookup table as an output
    lut_out = {"add_video_tkinter": (entry_select == add_gui_option),
               "add_video_ranger": (entry_select == add_cli_option),
               "add_video_path": (entry_select == add_input_option)}
    
    return lut_out

# .....................................................................................................................

def select_video_file_prompt():

    # Ask user how to specify video path
    video_action = select_video_action()
    
    # Provide different file selection options
    if video_action["add_video_tkinter"]:
        file_select = gui_file_select(window_title = "Select a video file")
    if video_action["add_video_ranger"]:
        file_select = ranger_file_select()
    if video_action["add_video_path"]:
        file_select = cli_prompt_with_defaults("Enter path to video file: ", 
                                               default_value = "~/",
                                               return_type = str, 
                                               response_on_newline = False)
        file_select = os.path.expanduser(file_select)   # Expand user pathing (~) symbol if needed
        
    # Error if it isn't a valid file path
    if not os.path.isfile(file_select):
        print("",
              "Bad video path!",
              "@ {}".format(file_select),
              "",
              "Quitting...",
              "", sep="\n")    
        ide_quit()
        
    return file_select

# .....................................................................................................................
        
def copy_video_local_prompt(cameras_folder, camera_select, file_select):
    
    # Ask if the file should be copied to the local resources folder (or otherwise linked remotely)
    copy_local = cli_confirm("Copy file to local video folder?", default_response = False)
    
    # If we're not copying to the local folder, just return the original file path for recording path
    if not copy_local:
        return copy_local, file_select
    
    # Perform copy operation
    local_copy_path = copy_video_file_local(cameras_folder, camera_select, file_select, print_feedback = True)
    
    return copy_local, local_copy_path

# .....................................................................................................................

def prompt_for_default_select(project_root_path, default_from = None):
    
    # Get list of available default types
    default_type_list = list_default_types(project_root_path)
    
    # Error if the default type selection is missing
    type_selection_default = "blank"
    no_blank_default = (type_selection_default not in default_type_list)
    if no_blank_default:
        raise NameError("Blank default missing! Must be available in defaults folder")
    
    # Use the provided default_from script arg input, if provided
    if default_from is not None:
        if default_from in default_type_list:
            return default_from
        raise NameError("Invalid default selection! ({})".format(default_from))
    
    # Have user choose from default types
    select_idx, entry_select = cli_select_from_list(default_type_list, 
                                                    "Select default configuration:", 
                                                    default_selection = type_selection_default)
    
    return entry_select

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Custom arguments
    
# .....................................................................................................................
    
def custom_arguments(argparser):
    
    argparser.add_argument("-d", "--default",
                           default = None,
                           type = str,
                           help = "Select default configuration style")
    
    argparser.add_argument("-nc", "--new_camera",
                           default = False,
                           action = "store_true",
                           help = "Create new camera entry")
    
    argparser.add_argument("-nu", "--new_user",
                           default = False,
                           action = "store_true",
                           help = "Create new user entry")
    
    argparser.add_argument("-nv", "--new_video",
                           default = False,
                           action = "store_true",
                           help = "Create new video entry")
    
    argparser.add_argument("-x", "--example",
                           default = False,
                           action = "store_true",
                           help = "Print example usage and close")
    
    return argparser

# .....................................................................................................................
    
def parse_create_selection(script_arguments):
    
    # Return an argument-based entity selection to override (if not None) the interactive prompt
    arg_entity_select = {"camera": script_arguments["new_camera"],
                         "user": script_arguments["new_user"],
                         "video": script_arguments["new_video"]}
    
    # Return different things depending on whether 0, 1 or >1 new entity creation flags were provided
    total_true = sum([int(each_flag) for each_flag in arg_entity_select.values()])
    if total_true < 1:
        # Skip using args, will instead provide interactive prompt
        arg_entity_select = None
    elif total_true > 1:
        # Raise an error if more than one thing is being created
        raise AttributeError("Must specify only a single 'new *' entry for creation!")
    
    return arg_entity_select

# .....................................................................................................................
    
def example_message(script_arguments):
    
    # If the example trigger isn't provided, don't do anything
    if not script_arguments["example"]:
        return
    
    # Print out example argument usage
    print("",
          "OVERVIEW: To create a new entry, use the appropriate -n* argument (which is a boolean flag).",
          "For example, use -nc for a new camera or -nu for a new user.",
          "The name of a new entry is then provided by the corresponding selection flag.",
          "For example, use -nc -c 'CameraName' to specify the new camera name.",
          "Only one entry may be created per script-call (if more than one -n* is given, the script cancels).",
          "",
          "NESTING: With the exception of new cameras, all other entries are nested.",
          "Therefore, you'll need to provide the parent selections as follows:",
          "  new user: requires camera selection (-c)",
          "  new video: requires camera selection (-c)",
          "",
          "DUPLICATION: With the exception of videos, all entries can be duplicated from existing entries.",
          "To duplicate, use the duplicate flag (-d), followed by the name of the entry to duplicate.",
          "For example to make a new camera from an existing one, use -nc -c 'NewCamera' -d 'ExistingCamera'",
          "The duplication will look for a matching name based on the entity being created.",
          "If a matching entry isn't found, the script will exit without creating anything!",
          "",
          "***** EXAMPLE USAGE *****",
          "",
          "Camera creation:",
          "python3 create.py -nc -c 'NewCameraName'",
          "",
          "User creation, duplicated from existing 'live' user:",
          "python3 create.py -nu -c 'SomeCam' -u 'NewTestUser' -d 'live'",
          "",
          "Video creation:",
          "python3 create.py -nv -c 'A_Cam' -v '/path/to/video/file.avi'",
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
default_from = script_args["default"]

# Get the entity selection from input arguments (if provided)
script_entity_select = parse_create_selection(script_args)

# Handle example printout
example_message(script_args)


# ---------------------------------------------------------------------------------------------------------------------
#%% Setup

# Set up resource selector
res_selector = Resource_Selector(load_selection_history = False, 
                                 save_selection_history = False,
                                 show_hidden_resources = False)

# Set up nicer selector wrapper for editing entities, as well as the creator object for handling entity creation
edit_selector = Edit_Selector(res_selector)
creator = Edit_Creator(edit_selector)


# ---------------------------------------------------------------------------------------------------------------------
#%% Creation

# Have user select an entity to create
entity_select = script_entity_select
if script_entity_select is None:
    entity_select = edit_selector.entity("create")

if entity_select["camera"]:
    creator.camera(camera_select, default_from)
    
if entity_select["user"]:
    creator.user(camera_select, user_select, default_from)
    
if entity_select["video"]:
    creator.video(camera_select, video_select)
    

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap

'''
TODO:
    - When duplicating entire cameras, need to be careful with resources folder! 
        - Don't always want to duplicate backgrounds or video references
        - Also don't want to duplicate classification data (probably)
    - Add logging
'''
