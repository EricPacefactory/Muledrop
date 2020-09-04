#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Jun  9 15:08:28 2020

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

import signal


# ---------------------------------------------------------------------------------------------------------------------
#%% Custom exceptions

# .....................................................................................................................

class OS_Close(Exception):
    pass

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

# .....................................................................................................................

def register_signal_quit(exception_handler_function = None):
    
    # If no exception handler ios provided, use the 'custom' function
    if exception_handler_function is None:
        exception_handler_function = raise_custom_exception
    
    # Register signal handlers. This causes a exception to be raised when given a SIGTERM signal
    signal.signal(signal.SIGTERM, exception_handler_function)
    
    return

# .....................................................................................................................

def raise_custom_exception(signal_number, stack_frame):
    print("", "", "*" * 48, "Kill signal received! ({})".format(signal_number), "*" * 48, "", sep = "\n")
    raise OS_Close

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Demo

if __name__ == "__main__":    
    raise OS_Close("Example of custom exception!")


# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap


