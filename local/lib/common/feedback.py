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

import datetime as dt

# ---------------------------------------------------------------------------------------------------------------------
#%% Classes

# .....................................................................................................................

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% General functions

# .....................................................................................................................

def print_time_taken(t_start_sec, t_end_sec = None,
                     prepend_newline = True, inset_spaces = 0, suppress_print = False):
    
    '''
    Generalized function for printing an amount of time taken
    Handles unit conversion so that a reasonable set of units are printed
    Prints out times in format:
        "Finished! Took # days, # hours, # minutes, # seconds, # ms"
    
    Inputs:
        t_start_sec -> (Integer or float) The starting time of the period being timed. Must be in units of seconds
        
        t_end_sec -> (Integer, float or None) The ending time of the period being timed. Must be in units of seconds.
                     If left as None, the start time will be interpretted as the end time, relative to '0' start time
        
        prepend_newline -> (Boolean) If True, a new line will be printed before the actual timing info
        
        inset_spaces -> (Integer) Number of spaces to prefix the printed message (to help indent if needed)
        
        suppress_print -> (Boolean) If True, the function won't actually print, but still returns timing info
    
    Outputs:
        num_days, num_hours, num_minutes, num_seconds, num_milliseconds
        (+ message printed to terminal if not suppressed)
    '''
    
    # If no end time is given, assume the start time is actually a total
    t_end_sec = 0 if t_end_sec is None else t_end_sec
    
    # Calculate the time taken
    total_time_sec = abs(t_end_sec - t_start_sec)
    total_time_ms = int(round(1000 * total_time_sec))
    time_elapsed_delta = dt.timedelta(milliseconds = total_time_ms)
    
    # For clarity
    no_sec = (total_time_sec > (60 * 60))
    no_millis = (total_time_sec > 5)
    
    # Get the days, hours, minutes, seconds and milliseconds from the time delta object
    print_days = time_elapsed_delta.days
    print_micros = time_elapsed_delta.microseconds
    delta_str = str(time_elapsed_delta)
    if print_days > 0:
        delta_str = delta_str.split(",")[1]
    if print_micros > 0:
        delta_str = delta_str.split(".")[0]
    hours_str, mins_str, sec_str = delta_str.split(":")
    
    # Figure out the actual numbers we'll want to print
    print_hours = int(hours_str)
    print_mins = int(mins_str)
    print_sec = 0 if no_sec else int(sec_str)
    print_ms = 0 if no_millis else int(round(print_micros / 1000))
    
    # Construct & print the time string with appropriate units
    enable_print = (not suppress_print)
    if enable_print:
        
        # Figure out which units to include in string
        time_str_list = []
        if print_days > 0:
            time_str_list.append("{} days".format(print_days))
        if print_hours > 0:
            time_str_list.append("{} hours".format(print_hours))
        if print_mins > 0:
            time_str_list.append("{} minutes".format(print_mins))
        if print_sec > 0:
            time_str_list.append("{} seconds".format(print_sec))
        if print_ms > 0:
            time_str_list.append("{} ms".format(print_ms))
        time_str = ", ".join(time_str_list)
        
        # Finally, build the full print out string
        spacing_str = " " * inset_spaces
        time_taken_str = "{}Finished! Took {}".format(spacing_str, time_str)
        
        # Add prepended empty line if needed before printing
        print_str_list = [""] if prepend_newline else []
        print_str_list.append(time_taken_str)
        print(*print_str_list, sep = "\n")
    
    return print_days, print_hours, print_mins, print_sec, print_ms

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
    
    # Example of non-unit print out
    for k in range(12):
        total_time_sec = 10 ** (k - 3)
        print("", "Time: {} sec".format(total_time_sec), sep = "\n")
        print_time_taken(0, total_time_sec, prepend_newline=False, inset_spaces=2)
        print("  ->", *print_time_taken(0, total_time_sec, prepend_newline=False, inset_spaces=2, suppress_print=True))
    
    pass

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap


