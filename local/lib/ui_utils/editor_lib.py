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

from time import sleep

from local.eolib.utils.cli_tools import cli_select_from_list, cli_prompt_with_defaults, cli_confirm
from local.eolib.utils.quitters import ide_quit


# ---------------------------------------------------------------------------------------------------------------------
#%% Define cli function with error handling

# .....................................................................................................................

def select_from_list(entry_list,
                     prompt_heading = "Select from list:",
                     default_selection = None,
                     zero_indexed = False,
                     quit_on_no_selection = True):
    
    ''' Wrapper around cli_confirm(...) function, with basic error handling. Meant for editor menus '''
    
    # Initialize outputs
    select_index = None
    select_entry = None
    
    # Run a loop to handle re-trying under certain failing conditions
    keep_looping = True
    while keep_looping:
    
        try:
            select_index, select_entry = cli_select_from_list(entry_list,
                                                              prompt_heading = prompt_heading,
                                                              default_selection = default_selection,
                                                              zero_indexed = zero_indexed)
            keep_looping = False
            
        except KeyboardInterrupt:
            # Happens on ctrl + c
            print("", "", "Keyboard cancel! (ctrl + c)", "", sep="\n")
            ide_quit()
            pass
        
        except ValueError:
            # Happens if no selection is made
            print("", "", "No selection, quitting...", "", sep="\n")
            keep_looping = False
            if quit_on_no_selection:
                ide_quit()
            pass
        
        except IndexError as err_msg:
            # Happens if an index is selected which isn't part of the list
            print("", "Error!", err_msg, "", sep = "\n")
            sleep(1.5)
            pass
        
        except NameError as err_msg:
            # Tends to happen from queued up keyboard inputs
            print("", "Error!", err_msg, "", sep = "\n")
            sleep(1.5)
            pass
    
    return select_index, select_entry

# .....................................................................................................................

def prompt_with_defaults(prompt_message, default_value = None, return_type = None, quit_on_no_response = False):
    
    ''' Wrapper around cli_confirm(...) function, with basic error handling. Meant for editor menus '''
    
    # Initialize outputs
    user_response = None
    
    # Run a loop to handle re-trying under certain failing conditions
    keep_looping = True
    while keep_looping:
        
        try:
            user_response = cli_prompt_with_defaults(prompt_message,
                                                     default_value = default_value,
                                                     return_type = return_type)
            keep_looping = False
        
        except KeyboardInterrupt:
            # Happens on ctrl + c
            print("", "", "Keyboard cancel! (ctrl + c)", "", sep="\n")
            ide_quit()
            pass
    
    # Quit if needed
    no_response = (user_response is None)
    if no_response and quit_on_no_response:
        ide_quit()        
        
    return user_response

# .....................................................................................................................

def confirm(confirm_text, default_response = True):
    
    ''' Wrapper around cli_confirm(...) function, with basic error handling. Meant for editor menus '''
    
    try:
        user_confirm = cli_confirm(confirm_text, default_response = default_response)
        
    except KeyboardInterrupt:
        # Happens on ctrl + c
        print("", "", "Keyboard cancel! (ctrl + c)", "", sep="\n")
        ide_quit()
        pass
    
    return user_confirm

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

# .....................................................................................................................
    
def quit_if_none(input_value, quit_message = "No value provided"):
    
    ''' Helper function which forces a script to quit if the provided input value is None '''
    
    if input_value is None:
        print("", quit_message, "Quitting...", sep = "\n")
        ide_quit()
    
    return

# .....................................................................................................................

def build_path_to_editor_utilities(project_root_path):
    
    ''' Helper function which gets pathing to the folder containing the editor utility scripts '''
    
    return os.path.join(project_root_path, "configuration_utilities",  "editors")

# .....................................................................................................................

def check_name_is_taken(name_to_check, existing_names_list):
    
    ''' Helper function used to check if a name is already in the given list, including hidden ('.' prefixed) names '''
    
    # Update the input name list to make sure we check against hidden entries & ignore spelling/spaces etc.
    full_name_list = []
    for each_name in existing_names_list:        
        name_is_hidden = (each_name[0] == ".")
        unhidden_name = each_name[1:] if name_is_hidden else each_name
        full_name_list.append(unhidden_name)
    
    return (name_to_check in full_name_list)

# .....................................................................................................................

def warn_for_name_taken(name_to_check, existing_names_list, quit_if_name_is_taken = True):
    
    '''
    Helper function which checks if a name is already taken and prints a warning if so
    Can optionally quit as well
    '''
    
    # Check if the given name is taken and provide feedback if it is (and optionally quit)
    name_already_exists = check_name_is_taken(name_to_check, existing_names_list)
    if name_already_exists:
        print("", 
              "Can't use name: {}".format(name_to_check),
              "  It is already taken!",
              sep = "\n")
        if quit_if_name_is_taken:
            ide_quit()
    
    return name_already_exists

# .....................................................................................................................

def rename_from_path(original_name_path, new_name, perform_rename = True):
    
    '''
    Helper function which helps with renaming, takes the original full path and the new name, then
    automatically builds the new name pathing.
    
    Inputs:
        original_name_path -> (String) The path to the original file/folder that is to be renamed
        
        new_name -> (String) The new name, without a path
        
        perform_rename -> (Boolean) If true, this function will perform the actual rename operation.
                          Otherwise, the function will only construct the pathing needed, without actually renaming
    
    Outputs:
        new_name_path
    '''
    
    # Use the original parent folder pathing to build the new named pathing
    original_parent_folder = os.path.dirname(original_name_path)
    new_name_path = os.path.join(original_parent_folder, new_name)
    
    # Only execute the rename if needed
    if perform_rename:
        os.rename(original_name_path, new_name_path)
    
    return new_name_path

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap



