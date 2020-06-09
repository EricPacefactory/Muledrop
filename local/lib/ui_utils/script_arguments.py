#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Dec 11 13:13:55 2019

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

# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes



# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

# .....................................................................................................................

def get_selections_from_script_args(argparse_result):
    
    '''
    Helper function used to pull out only the selection components from script arguments
    
    Inputs:
        argparse_result -> (Dictionary) Result from calling the 'script_arg_builder()' function
    
    Outputs:
        camera_select, user_select, video_select
    
    Note: If any selections are missing, they will have 'None' values
    '''
    
    camera_select = argparse_result.get("camera", None)
    user_select = argparse_result.get("user", None)
    video_select = argparse_result.get("video", None)
    
    return camera_select, user_select, video_select

# .....................................................................................................................

def script_arg_builder(args_list, description = None, epilog = None, parse_on_call = True,
                       debug_print = False):
    
    ''' 
    Function which builds a set of (standard) script arguments 
    
    Inputs:
        args_list -> List. Should contain a list of script arguments to provide.
                     List entries can be strings or a dictionaries. See example below
                     
        description -> String or None. If a string is provided, it will be printed 
                       above the list of script arguments
                              
        epilog -> String or None. If a string is provided, it will be printed
                  below the list of script arguments.
        
        parse_on_call -> Boolean. If True, the script arguments will be immediately evaluated,
                         and the results will be returned as a dictionary. 
                         If False, the argparse object will be returned (so more/custom arguments can be added)
            
        debug_print -> Boolean. If True and parse_on_call is also True, script argument results will be printed out
            
    Outputs:
        ap_obj or ap_result (depending on parse_on_call input value)        
            ap_obj -> argparse object, unevaluated
            ap_result -> Dictionary. Contains evaluated results of script argument inputs
       
        
    *******************
    Example args_list:
        
        args_list = ["camera",
                     {"user": {"default": "live"}},
                     "video",
                     "display"]
        
        --> This arg_list would provide the camera, user, video and display arguments.
        The user argument would additionally have it's default value set to 'live' (normally None)
                
    '''
    
    # Set up argparser options
    ap_obj = argparse.ArgumentParser(description = description, epilog = epilog,
                                     formatter_class = argparse.RawTextHelpFormatter)
    
    # Gather the appropriate positional/keyword arguments for each entry in the arg list
    for each_arg_entry in args_list:
        
        entry_type = type(each_arg_entry)
        if entry_type is str:
            function_call = _script_arg_function_lut(each_arg_entry)
            return_args, return_kwargs = function_call()
        elif entry_type is dict:
            key_name = iter(each_arg_entry).__next__()
            function_call = _script_arg_function_lut(key_name)
            return_args, return_kwargs = function_call(**each_arg_entry[key_name])
        else:
            raise TypeError("Unrecognized script arg builder type: {}".format(entry_type))
            
        # Add script argument
        ap_obj.add_argument(*return_args, **return_kwargs)
    
    # Parse arguments and place in dictionary
    if parse_on_call:
        ap_result = vars(ap_obj.parse_args())
        
        if debug_print:
            print("", "DEBUG: Script argument results", sep = "\n")
            for each_key, each_value in ap_result.items():
                print("  {}: {}".format(each_key, each_value))
        
        return ap_result
    
    return ap_obj

# .....................................................................................................................

def _script_arg_function_lut(key_name):
    
    ''' Helper function for selecting the appropriate key script argument generating function '''
    
    func_lut = {"debug": _debug_arg,
                "enable_prompts": _enable_prompts,
                "disable_prompts": _disable_prompts,
                "camera": _camera_arg,
                "user": _user_arg,
                "video": _video_arg,
                "display": _display_arg,
                "threaded_video": _threaded_video_arg,
                "unthreaded_video": _unthreaded_video_arg,
                "threaded_save": _threaded_save_arg,
                "unthreaded_save": _unthreaded_save_arg,
                "disable_saving": _disable_saving_arg,
                "delete_existing_data": _delete_existing_data_arg,
                "protocol": _protocol_arg,
                "host": _host_arg,
                "port": _port_arg,
                "url": _url_arg}
    
    # Handle bad key names
    if key_name not in func_lut.keys():
        valid_keys = list(func_lut.keys())
        raise NameError("Unrecognized script key name ({}). Must be one of: {}".format(key_name, valid_keys))
        
    return func_lut[key_name]

# .....................................................................................................................
    
def _debug_arg(help_text = "Enable debug mode"):
    return ("-debug", "--debug"), {"default": False, "action": "store_true", "help": help_text}

# .....................................................................................................................

def _enable_prompts(help_text = "Enable prompts"):
    return ("-prompts", "--enable_prompts"), {"default": False, "action": "store_true", "help": help_text}

# .....................................................................................................................

def _disable_prompts(help_text = "Disable prompts"):
    return ("-noprompts", "--disable_prompts"), {"default": False, "action": "store_true", "help": help_text}

# .....................................................................................................................
    
def _camera_arg(default = None, help_text = "Camera select"):
    return ("-c", "--camera"), {"default": default, "type": str, "help": help_text}

# .....................................................................................................................

def _user_arg(default = None, help_text = "User select"):
    return ("-u", "--user"), {"default": default, "type": str, "help": help_text}

# .....................................................................................................................

def _video_arg(default = None, help_text = "Video select"):
    return ("-v", "--video"), {"default": default, "type": str, "help": help_text}

# .....................................................................................................................

def _display_arg(help_text = "Enable display (slower)"):
    return ("-d", "--display"), {"default": False, "action": "store_true", "help": help_text}

# .....................................................................................................................

def _threaded_video_arg(help_text = "Enable threaded video capture (fast, but may be buggy!)"):
    return ("-etv", "--threaded_video"), {"default": False, "action": "store_true", "help": help_text}

# .....................................................................................................................

def _unthreaded_video_arg(help_text = "Disable threaded video capture (slower but more stable)"):
    return ("-utv", "--unthreaded_video"), {"default": False, "action": "store_true", "help": help_text}

# .....................................................................................................................

def _threaded_save_arg(help_text = "Enable threaded file saving (fast, but may be buggy!)"):
    return ("-ets", "--threaded_save"), {"default": False, "action": "store_true", "help": help_text}

# .....................................................................................................................

def _unthreaded_save_arg(help_text = "Disable threaded file saving (slower but more stable)"):
    return ("-uts", "--unthreaded_save"), {"default": False, "action": "store_true", "help": help_text}

# .....................................................................................................................

def _disable_saving_arg(help_text = "Turn off report data saving"):
    return ("-nosave", "--disable_saving"), {"default": False, "action": "store_true", "help": help_text}

# .....................................................................................................................

def _delete_existing_data_arg(help_text = "Delete existing report data on startup"):
    return ("-delete", "--delete_existing_data"), {"default": False, "action": "store_true", "help": help_text}

# .....................................................................................................................

def _protocol_arg(default = "http", help_text = "Specify a web protocol"):
    return ("-proto", "--protocol"), {"default": default, "type": str, "help": help_text}

# .....................................................................................................................

def _host_arg(default = "localhost", help_text = "Specify host/ip address"):
    return ("-host", "--host"), {"default": default, "type": str, "help": help_text}

# .....................................................................................................................

def _port_arg(default = None, help_text = "Specify a port"):
    return ("-port", "--port"), {"default": default, "help": help_text}

# .....................................................................................................................

def _url_arg(default = None, help_text = "Specify a url"):
    return ("-url", "--url"), {"default": default, "help": help_text}

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Demo

if __name__ == "__main__":
    
    # Typical usage, supply standard args in order as desired
    example_list = ["camera",
                    "user",
                    "video",
                    {"display": {"default": None}},
                    "threaded_video"]
    ap_obj = script_arg_builder(example_list, parse_on_call = False)
    
    # Example of how to add more arguments
    ap_obj.add_argument("-x", "--example", action = "store_true", help = "Example script arg add-on")
    ap_result = vars(ap_obj.parse_args())
    
    # Show resulting dictionary
    print("Arg Results:", ap_result, sep = "\n")

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap