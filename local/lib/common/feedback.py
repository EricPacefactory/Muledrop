#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Apr 20 11:27:52 2020

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


# ---------------------------------------------------------------------------------------------------------------------
#%% Classes

# .....................................................................................................................

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% General functions

# .....................................................................................................................

def print_time_taken_sec(t_start_sec, t_end_sec = None, 
                         prepend_newline = True, string_format = "{:.1f}", inset_spaces = 0):
    
    # Add prepended empty line if needed
    print_str_list = []
    if prepend_newline:
        print_str_list.append("")
    
    # If no end time is given, assume the start time is actually a total
    t_end_sec = 0 if t_end_sec is None else t_end_sec
    
    # Calculate the time taken and construct the string to print
    total_time_sec = abs(t_end_sec - t_start_sec)
    time_str = string_format.format(total_time_sec)
    spacing_str = " " * inset_spaces
    time_taken_str = "{}Finished! Took {} seconds".format(spacing_str, time_str)
    
    # Print!
    print_str_list.append(time_taken_str)
    print(*print_str_list, sep = "\n")
            
    return total_time_sec

# .....................................................................................................................

def print_time_taken_ms(t_start_sec, t_end_sec = None, 
                        prepend_newline = True, string_format = "{:.0f}", inset_spaces = 0):
    
    # Add prepended empty line if needed
    print_str_list = []
    if prepend_newline:
        print_str_list.append("")
    
    # If no end time is given, assume the start time is actually a total
    t_end_sec = 0 if t_end_sec is None else t_end_sec
    
    # Calculate the time taken and construct the string to print
    total_time_sec = abs(t_end_sec - t_start_sec)
    total_time_ms = (1000 * total_time_sec)
    time_str = string_format.format(total_time_ms)
    spacing_str = " " * inset_spaces
    time_taken_str = "{}Finished! Took {} ms".format(spacing_str, time_str)
    
    # Print!
    print_str_list.append(time_taken_str)
    print(*print_str_list, sep = "\n")
            
    return total_time_ms

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Demo

if __name__ == "__main__":
    
    pass

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap


