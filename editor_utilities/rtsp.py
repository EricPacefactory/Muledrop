#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon May  6 16:32:00 2019

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

from functools import partial

from local.lib.editor_lib import Edit_Selector, safe_quit, parse_selection_args

from local.lib.selection_utils import Resource_Selector

from local.lib.file_access_utils.video import load_rtsp_config, save_rtsp_config

from eolib.utils.cli_tools import cli_select_from_list, cli_prompt_with_defaults
from eolib.utils.network import build_rtsp_string, parse_rtsp_string

# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes
    
class Edit_Rtsp:
    
    def __init__(self, editor_ref, camera_select):
        
        # Select a camera right away, since we'll need the path to the rtsp file regardless
        self.camera_select, _ = editor_ref.camera(camera_select)
        
        # Store some paths for convenience
        self.project_root_path, self.cameras_folder_path = editor_ref.select.get_project_pathing()
        
    # .................................................................................................................
    
    def _rtsp_feedback(self, new_rtsp_config):
        
        print_keys = ["ip_address", "username", "password", "port", "route"]
        longest_key = max([len(each_key) for each_key in print_keys])
        rtsp_print_out = []
        for each_key in print_keys:
            rtsp_print_out.append("  {}: {}".format(each_key.rjust(longest_key), new_rtsp_config[each_key]))
        rtsp_string = build_rtsp_string(**new_rtsp_config, when_ip_is_bad_return = "(invalid)")
        
        print("", 
              "RTSP info: {}".format(self.camera_select),
              "",
              "RTSP Components:",
              "\n".join(rtsp_print_out),
              "",
              "RTSP String:",
              "  {}".format(rtsp_string),
              "",
              "Quitting...", 
              "", sep="\n")
        
        # Quit immediately, since we've altered some of the file system data
        safe_quit()
        
    # .................................................................................................................
    
    def rtspstring(self, new_rtsp_string = None):
        
        # Load existing configuration so we can show the current string
        curr_rtsp_dict, curr_rtsp_string = load_rtsp_config(self.cameras_folder_path, self.camera_select)
        
        # Set up reference message if a current string isn't available
        if not curr_rtsp_string and new_rtsp_string is None:
            print("")
            print("Example RTSP format:")
            print(" ", "rtsp://username:password@ip_address:port/route")
            curr_rtsp_string = None
        
        # Only provide user prompt if an argument wasn't given
        if new_rtsp_string is None:
            new_rtsp_string = cli_prompt_with_defaults("Enter rtsp string: ", 
                                                       default_value = curr_rtsp_string, 
                                                       return_type = str)        
        
        self._update_rtsp_info_from_string(new_rtsp_string)
    
    # .................................................................................................................
    
    def components(self, ip_address = None, username = None, password = None, port = None, route = None):
        
        # Load existing data, since we'll use this to update the values
        curr_rtsp_dict, curr_rtsp_string = load_rtsp_config(self.cameras_folder_path, self.camera_select)
        
        # If no input arguments are given, provide a user prompt
        all_arg_inputs = [ip_address, username, password, port, route]
        provide_user_prompt = all([each_arg is None for each_arg in all_arg_inputs])
        
        # If needed, provide a user prompt to set the components
        if provide_user_prompt:
            
            # Set up defaults for user input convenience
            set_null_default = lambda key: curr_rtsp_dict[key] if curr_rtsp_dict[key] else None
            default_ip = set_null_default("ip_address")
            default_user = set_null_default("username")
            default_pass = set_null_default("password")
            default_port = curr_rtsp_dict["port"]
            default_route = set_null_default("route")
            
            # For convenience
            cli_prompt = partial(cli_prompt_with_defaults, response_on_newline = False, prepend_newline = False)
            prompt_str = partial(cli_prompt, return_type = str)
            prompt_int = partial(cli_prompt, return_type = int)
            none_to_blank_str = lambda result: "" if result is None else result
        
            # Ask for each of the rtsp access entries
            none_to_blank_str = lambda result: "" if result is None else result
            ip_address = none_to_blank_str(prompt_str("Enter ip address: ", default_ip))
            username = none_to_blank_str(prompt_str("  Enter username: ", default_user))
            password = none_to_blank_str(prompt_str("  Enter password: ", default_pass))
            port = prompt_int("      Enter port: ", default_port)
            route = none_to_blank_str(prompt_str("     Enter route: ", default_route))
            
        else:
            
            # Set new values based on input arguments instead of asking for user input
            update_if_not_none = lambda key, new_value: curr_rtsp_dict[key] if new_value is None else new_value
            ip_address = update_if_not_none("ip_address", ip_address)
            username = update_if_not_none("username", username)
            password = update_if_not_none("password", password)
            port = update_if_not_none("port", port)
            route = update_if_not_none("route", route)
        
        # Fix extra slashes on route entry
        if len(route) > 0:
            if route[0] == "/":
                route = route[1:]
        
        # Construct the new rtsp dictionary
        new_rtsp_dict = {"ip_address": ip_address,
                         "username": username,
                         "password": password,
                         "port": port,
                         "route": route}
        
        # Update the rtsp info, but only validate is we used user input 
        # (skip validation from script args. since they may not be finished)
        self._update_rtsp_info_from_dict(new_rtsp_dict, validate_config = provide_user_prompt)
        
    # .................................................................................................................
    
    def individual_components(self, ip_address = None, username = None, password = None, port = None, route = None):
        
        # If no input arguments are given, provide a user prompt
        all_arg_inputs = [ip_address, username, password, port, route]
        all_arg_inputs_none = all([each_arg is None for each_arg in all_arg_inputs])
        if all_arg_inputs_none:
            pass
        
        # Load existing data, since we'll use this to update the values
        curr_rtsp_dict, curr_rtsp_string = load_rtsp_config(self.cameras_folder_path, self.camera_select)
        
        # Set up defaults for user input convenience
        update_if_not_none = lambda key, new_value: curr_rtsp_dict[key] if new_value is None else new_value
        new_ip_address = update_if_not_none("ip_address", ip_address)
        new_username = update_if_not_none("username", username)
        new_password = update_if_not_none("password", password)
        new_port = update_if_not_none("port", port)
        new_route = update_if_not_none("route", route)
        
        # Construct the new rtsp dictionary
        new_rtsp_config = {"ip_address": new_ip_address,
                           "username": new_username,
                           "password": new_password,
                           "port": new_port,
                           "route": new_route}
        
        # Update the config
        save_rtsp_config(self.cameras_folder_path, self.camera_select, new_rtsp_config)
        
        # Provide feedback and quit
        self._rtsp_feedback(new_rtsp_config)
        
    # .................................................................................................................
    
    def info(self):
        rtsp_config, rtsp_string = load_rtsp_config(self.cameras_folder_path, self.camera_select)
        self._rtsp_feedback(rtsp_config)
        
    # .................................................................................................................
    
    def ping(self):
        
        # Load rtsp connection info
        rtsp_config, rtsp_string = load_rtsp_config(self.cameras_folder_path, self.camera_select)
        
        # Bail if the rtsp string is no good
        if rtsp_string == "":
            print("",
                  "Invalid rtsp info! Cannot connect...",
                  "", "Quitting...", sep="\n")
        
        # Provide feedback about connection progress
        print("",
              "Connecting...",
              "{}".format(rtsp_string),
              "", sep="\n")
        
        import cv2
        try:
            vcap = cv2.VideoCapture(rtsp_string)
            (get_frame, frame) = vcap.read()
            vcap.release()
        except Exception:
            print("",
                  "RTSP Connection error!",
                  "", "Quitting...", sep="\n")
        safe_quit()
    
    # .................................................................................................................
    
    def _update_rtsp_info_from_string(self, new_rtsp_string):
        
        # Check string is valid
        is_valid = _rtsp_string_is_valid(new_rtsp_string)
        if not is_valid:
            print("",
                  "Something is wrong with the rtsp string:",
                  new_rtsp_string,
                  "",
                  "Quitting...", sep="\n")
            safe_quit()
        
        # Update the config
        new_rtsp_config = parse_rtsp_string(new_rtsp_string)
        save_rtsp_config(self.cameras_folder_path, self.camera_select, new_rtsp_config)
        
        # Provide feedback and quit
        self._rtsp_feedback(new_rtsp_config)
    
    # .................................................................................................................
    
    def _update_rtsp_info_from_dict(self, new_rtsp_dict, validate_config = True):
        
        # Check that the config is valid if needed
        if validate_config:
            is_valid = _rtsp_config_is_valid(new_rtsp_dict)
            if not is_valid:
                print("",
                      "Something is wrong with the rtsp config:",
                      new_rtsp_dict,
                      "",
                      "Quitting...", sep="\n")
                safe_quit()
        
        # Update the config
        save_rtsp_config(self.cameras_folder_path, self.camera_select, new_rtsp_dict)
        
        # Provide feedback and quit
        self._rtsp_feedback(new_rtsp_dict)
    
    # .................................................................................................................
    # .................................................................................................................
        
# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

# .....................................................................................................................
    
def _rtsp_input_select():
    
    # Offer the following actions to the user
    rtspstring_option = "Enter RTSP string"
    components_option = "Enter RTSP components"
    info_option = "View RTSP info"
    ping_option = "Test RTSP connection"
    input_options_prompt = [rtspstring_option, components_option, info_option, ping_option]
    
    # Ask for user input (or quit if no selection is made)
    try:
        select_idx, entry_select = cli_select_from_list(input_options_prompt, 
                                                        prompt_heading = "Select input option:",
                                                        default_selection = None)
    except ValueError:
        Edit_Selector.no_selection_quit()
    
    # Create a simple lookup table as an output
    lut_out = {"rtspstring": (entry_select == rtspstring_option),
               "components": (entry_select == components_option),
               "info": (entry_select == info_option),
               "ping": (entry_select == ping_option)}
    
    return lut_out

# .....................................................................................................................

def _update_rtsp_prompt(current_rtsp_dict):
    
    # Set up defaults for user input convenience
    set_null_default = lambda key: current_rtsp_dict[key] if current_rtsp_dict[key] else None
    default_ip = set_null_default("ip_address")
    default_user = set_null_default("username")
    default_pass = set_null_default("password")
    default_port = current_rtsp_dict["port"]
    default_route = current_rtsp_dict["route"]
    
    # For convenience
    cli_prompt = partial(cli_prompt_with_defaults, response_on_newline = False, prepend_newline = False)
    prompt_str = partial(cli_prompt, return_type = str)
    prompt_int = partial(cli_prompt, return_type = int)
    
    # Ask for each of the rtsp access entries
    ip_address = prompt_str("Enter ip address: ", default_ip)
    username = prompt_str("  Enter username: ", default_user)
    password = prompt_str("  Enter password: ", default_pass)
    port = prompt_int("      Enter port: ", default_port)
    route = prompt_str("     Enter route: ", default_route)
    
    # Construct the new rtsp dictionary
    new_rtsp_dict = {"ip_address": ip_address,
                     "username": username,
                     "password": password,
                     "port": port,
                     "route": route}
    
    return new_rtsp_dict

# .....................................................................................................................

def _rtsp_string_from_data(rtsp_data):
        
    # If the video_path variable is a dictionary, assume it is an rtsp-specification
    if type(rtsp_data) is dict:
        try:
            rtsp_string = build_rtsp_string(**rtsp_data)
        except Exception as err:
            raise err("ERROR: Couldn't interpret rtsp data: {}".format(rtsp_string))
            
    elif type(rtsp_data) is str:
        # If the data is a string, interpret it as an rtsp string directly
        rtsp_string = rtsp_data            
        
    else:
        raise TypeError("Unrecognized RTSP data: {}".format(rtsp_data))
    
    return rtsp_string

# .................................................................................................................

def _rtsp_config_is_valid(rtsp_config):
    
    # Check that the required keys are present
    req_keys = ["ip_address", "username", "password", "port", "route"]
    for each_req_key, each_config_key in zip(sorted(req_keys), sorted(rtsp_config.keys())):
        if each_req_key != each_config_key:
            raise AttributeError("Bad rtsp. Key mismatch: {}".format(rtsp_config))
    
    # Check that the right number of keys are present        
    if len(req_keys) != len(rtsp_config.keys()):
        raise AttributeError("Bad rtsp config, wrong number of keys: {}".format(rtsp_config))
    
    # Check that an ip address is given
    try:
        ip_not_empty = (rtsp_config["ip_address"].strip() != "")
    except AttributeError:
        return False
    if not ip_not_empty:
        print("",
              "Bad rtsp config!",
              "  No ip address",
              "", "Quitting...", sep="\n")
        safe_quit()
    
    # Check that the given ip address has 4 number entries
    try:
        ip_has_4_numbers = len([int(each_entry) for each_entry in rtsp_config["ip_address"].split(".")]) == 4
    except ValueError:
        return False
    if not ip_has_4_numbers:
        print("",
              "Bad rtsp config!",
              "  IP doesn't have 4 numbers: {}".format(rtsp_config["ip_address"]),
              "", "Quitting...", sep="\n")
        safe_quit()
    
    # Check that the ip numbers are between 0 and 255
    ip_valid_number_ranges = all([0 <= int(each_number) < 256 for each_number in rtsp_config["ip_address"].split(".")])
    if not ip_valid_number_ranges:
        print("",
              "Bad rtsp config!",
              "  IP numbers in the wrong range (0-255): {}".format(rtsp_config["ip_address"]),
              "", "Quitting...", sep="\n")
        safe_quit()
    
    # Check that the port number is actually a number in the right range
    try:
        valid_port = (0 < rtsp_config["port"] < 2**16)
    except TypeError:
        return False
    if not valid_port:
        print("",
              "Bad rtsp config!",
              "  Port is in the wrong range: {}".format(rtsp_config["port"]),
              "", "Quitting...", sep="\n")
        safe_quit()
    
    # Combine checks for final output
    valid_ip = (ip_not_empty and ip_has_4_numbers and ip_valid_number_ranges)
    valid_rtsp_config = (valid_ip and valid_port)
    
    return valid_rtsp_config

# .................................................................................................................

def _rtsp_string_is_valid(rtsp_string):
    rtsp_config = parse_rtsp_string(rtsp_string)
    is_valid = _rtsp_config_is_valid(rtsp_config)    
    return is_valid

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Custom arguments
    
# .....................................................................................................................
    
def custom_arguments(argparser):
    
    argparser.add_argument("-ps", "--rtspstring",
                           default = None,
                           type = str,
                           help = "Update info using rtsp-string")
    
    argparser.add_argument("-pa", "--ip_address",
                           default = None,
                           type = str,
                           help = "Update rtsp ip address")
    
    argparser.add_argument("-pu", "--username",
                           default = None,
                           type = str,
                           help = "Update rtsp username")
    
    argparser.add_argument("-pp", "--password",
                           default = None,
                           type = str,
                           help = "Update rtsp password")
    
    argparser.add_argument("-po", "--port",
                           default = None,
                           type = int,
                           help = "Update rtsp port")
    
    argparser.add_argument("-pr", "--route",
                           default = None,
                           type = str,
                           help = "Update rtsp route")
    
    argparser.add_argument("-p", "--ping",
                           default = False,
                           action = "store_true",
                           help = "Test the rtsp connection")
    
    argparser.add_argument("-i", "--info",
                           default = False,
                           action = "store_true",
                           help = "Display rtsp info")
    
    argparser.add_argument("-x", "--example",
                           default = False,
                           action = "store_true",
                           help = "Print example usage and close")
    
    return argparser

# .....................................................................................................................
    
def parse_rtsp_selection(script_arguments):
    
    # Check if any components were given
    target_args = ["ip_address", "username", "password", "port", "route"]
    component_args = {each_key: script_arguments[each_key] for each_key in target_args}
    components_present = any([each_value is not None for each_value in component_args.values()])
    
    # Check if rtsp string was present
    rtsp_string = script_arguments["rtspstring"]
    rtsp_string_present = (rtsp_string is not None)
    
    # Decide if the rtsp string entry, component entry or info was selected by script arguments
    arg_entity_select = {"info": script_arguments["info"],
                         "ping": script_arguments["ping"],
                         "rtspstring": rtsp_string_present,
                         "components": components_present}
    
    # Return different things depending on whether 0, 1 or >1 new entity creation flags were provided
    total_true = sum([int(each_flag) for each_flag in arg_entity_select.values()])
    if total_true < 1:
        # Skip using args, will instead provide interactive prompt
        arg_entity_select = None
    elif total_true > 1:
        # Raise an error if more than one thing is being created
        raise AttributeError("Cannot specify info/rtspstring/components at the same time! Pick one.")
        
    return arg_entity_select, rtsp_string, component_args

# .....................................................................................................................
    
def example_message(script_arguments):
    
    # If the example trigger isn't provided, don't do anything
    if not script_arguments["example"]:
        return
    
    # Print out example argument usage
    print("",
          "OVERVIEW: RTSP settings can be viewed or altered with this script.",
          "All options require a camera selection!",
          "View rtsp settings using the info (-i) option (which then quits).",
          "Test rtsp settings using the ping (-p) option.",
          "A new rtsp string can be set directly using the (-ps) argument.",
          "Individual rtsp components can be altered using the appropriate arguments:",
          " -pa ip_address",
          " -pu username", 
          " -pp password",
          " -po port", 
          " -pr route",
          "One or many components can be specified if calling with script arguments.",
          "",
          "*Note1: No validation is done to rtsp components when called through script arguments!",
          "*Note2: RTSP string must have format: 'rtsp://username:password@ip_address:port/route'",
          "",
          "",
          "***** EXAMPLE USAGE *****",
          "",
          "View rtsp info:",
          "python3 rtsp.py -c 'InterestingCam' -i",
          "",
          "Update rtsp string directly:",
          "python3 rtsp.py -c 'demoCamera' -ps 'rtsp://aUser:aPass@1.2.3.4:554/Stream1000'",
          "",
          "Update only the route component:",
          "python3 rtsp.py -c 'theCamera' -pr 'stream/channel/to/some/place/h264",
          "",
          "Update username and password:",
          "python3 rtsp.py -c 'realCam' -pu 'newUser' -pp 'oldpazzword'",
          "", sep="\n")
    
    # Quit, since the user probably doesn't want to launch into interactive mode from here!
    safe_quit()

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Parse arguments

# Get arguments for this script call
script_args = parse_selection_args(custom_arguments, 
                                   show_user = False, show_task = False, show_video = False, show_rule = False)
camera_select = script_args["camera"]

# Get the entity selection from input arguments (if provided)
script_input_select, rtsp_string, rtsp_components = parse_rtsp_selection(script_args)

# Handle example printout
example_message(script_args)

# ---------------------------------------------------------------------------------------------------------------------
#%% Setup

# Set up resource selector
res_selector = Resource_Selector(load_selection_history = False, 
                                 save_selection_history = False)

# Set up nicer selector wrapper for editing entities, as well as the creator object for handling entity creation
edit_selector = Edit_Selector(res_selector)

# Set up rtsp editor
rtsp = Edit_Rtsp(edit_selector, camera_select)


# ---------------------------------------------------------------------------------------------------------------------
#%% RTSP

# Have user select an input option for updating the rtsp
input_select = script_input_select
if script_input_select is None:
    input_select = _rtsp_input_select()

if input_select["rtspstring"]:
    rtsp.rtspstring(rtsp_string)
    
if input_select["components"]:
    rtsp.components(**rtsp_components)
    
if input_select["info"]:
    rtsp.info()
    
if input_select["ping"]:
    rtsp.ping()

    
# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap


'''
TODO:
    - Need to test it out...
    - May consider hiding user/password storage (use hex + base64 or something? just to make it hard to read directly)
    - Script arg implementation is much messier than other editor scripts, may need to clean it up at some point...
    - Add logging
'''
