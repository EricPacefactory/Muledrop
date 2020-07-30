#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Jul 29 15:45:07 2020

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

import json
import gzip

import cv2
import numpy as np

from local.lib.file_access_utils.shared import build_resources_folder_path

from local.eolib.utils.network import build_rtsp_string, check_valid_ip


# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes 


# ---------------------------------------------------------------------------------------------------------------------
#%% Pathing functions

# .....................................................................................................................

def build_rtsp_file_path(location_select_folder_path, camera_select):
    return build_resources_folder_path(location_select_folder_path, camera_select, "rtsp.data")

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Access functions

# .....................................................................................................................

def create_new_rtsp_config(ip_address, username, password, port = 554, route = ""):
    
    ''' Helper function which bundles rtsp info in a consistent format '''
    
    # Fix prefixed slashes on route input
    if len(route) > 0:
        if route[0] == "/":
            route = route[1:]
        
    return {"ip_address": ip_address,
            "username": username,
            "password": password,
            "port": port,
            "route": route}

# .....................................................................................................................

def create_default_rtsp_config():
    
    ''' Helper function used to enforce a 'standard' default rtsp config '''
    
    return create_new_rtsp_config(ip_address = "",
                                  username = "",
                                  password = "",
                                  port = 554,
                                  route = "")

# .....................................................................................................................

def unpack_rtsp_config(rtsp_config_dict):
    
    '''
    Helper function which retrieves rtsp configuration info in a consistent order.
    Used to avoid requiring knowledge of keyname/lookups
    
    Inputs:
        rtsp_config_dict -> (Dictionary) An RTSP configuration that should be unpacked
    
    Outputs:
        ip_address, username, password, port, route
    
    Note: The port will be an integer value, all others are strings!
    '''
    
    ip_address = rtsp_config_dict["ip_address"]
    username = rtsp_config_dict["username"]
    password = rtsp_config_dict["password"]
    port = int(rtsp_config_dict.get("port", 554))
    route = rtsp_config_dict["route"]
    
    return ip_address, username, password, port, route

# .....................................................................................................................

def check_valid_rtsp_ip(location_select_folder_path, camera_select):
    
    ''' 
    Function for (roughly) determining if the rtsp configuration of a camera is valid 
    Only checks if the ip address is valid
    
    Returns:
        has_valid_rtsp (boolean)
    '''
    
    # Check for missing rtsp configuration
    rtsp_config_dict, _ = load_rtsp_config(location_select_folder_path, camera_select)
    rtsp_ip_address = rtsp_config_dict.get("ip_address", "")
    has_valid_rtsp = check_valid_ip(rtsp_ip_address)
    
    return has_valid_rtsp

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Load & save functions

# .....................................................................................................................

def load_rtsp_config(location_select_folder_path, camera_select):
    
    # Try to load rtsp image data
    load_success, rtsp_image_1ch = load_obfuscated_rtsp_image(location_select_folder_path, camera_select)
    
    # Deobfuscate the loaded image or use a default config if loading failed
    rtsp_config_dict = deobfuscate_rtsp(rtsp_image_1ch) if load_success else create_default_rtsp_config()
    
    # Create rtsp string for convenience
    rtsp_string = build_rtsp_string(**rtsp_config_dict)
    
    return rtsp_config_dict, rtsp_string

# .....................................................................................................................
    
def save_rtsp_config(location_select_folder_path, camera_select, rtsp_config_dict):
    
    '''
    Function used to save rtsp config data. Obfuscates the data before saving
    
    Inputs:
        location_select_folder_path, camera_select -> (Strings) Camera pathing
        
        rtsp_config_dict -> (Dictionary) Configuration for rtsp connection. Should be in a format consistent
                            with the output from the 'create_new_rtsp_config' function
    
    Outputs:
        Nothing!
    '''
    
    # First obfuscate the config data, and then save the resulting 'image' data
    rtsp_image_1ch = obfuscate_rtsp(rtsp_config_dict)
    save_obfuscated_rtsp_image(location_select_folder_path, camera_select, rtsp_image_1ch)
    
    return

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Obfucation functions

# .....................................................................................................................

def obfuscate_rtsp(rtsp_config_dict):
    
    '''
    Helper function used to transform rtsp access info into a less human-readable format for safer storage
    Note: This is not using proper encryption! If for some reason the security of the 
    rtsp info is considered of utmost importance, the saved data from this function
    should probably be encypted as well!
    
    Inputs:
        rtsp_config_dict -> (Dictionary) A dictionary containing rtsp info. Should have a 
                            structure matching the result of the 'create_new_rtsp_config' function
    
    Outputs:
        rtsp_image_1ch (numpy uint8 array)
    '''
    
    # Convert the rtsp data into a binary format
    json_str = json.dumps(rtsp_config_dict, sort_keys = True)
    json_byte_str = json_str.encode("utf-32")
    gzip_byte_str = gzip.compress(json_byte_str)
    hex_gzip = gzip_byte_str.hex()
    
    # Now create an image out of the data
    uint8_array = np.frombuffer(hex_gzip.encode("utf-8"), dtype = np.uint8)    
    top_row = np.expand_dims(uint8_array, 0)
    
    # Randomize part of the image for giggles
    total_rows = 10
    num_cols = top_row.shape[1]
    num_lower_rows = (total_rows - 1)
    np.random.seed(uint8_array[0:4])
    lower_image = np.random.randint(np.min(top_row), np.max(top_row), (num_lower_rows, num_cols), dtype = np.uint8)
    rtsp_image_1ch = np.vstack((top_row, lower_image))
    
    return rtsp_image_1ch

# .....................................................................................................................

def deobfuscate_rtsp(rtsp_image_1ch):
    
    '''
    Function used to undo obfuscation of saved rtsp (image) data, returns an rtsp config dictionary
    
    Inputs:
        rtsp_image_1ch -> (numpy uint8 array) The image generated by the obfuscate function. Should contain
                          rtsp config data
    
    Outputs:
        rtsp_config_dict (dictionary)
    '''
    
    # Undo the obfuscation steps
    uint8_array = rtsp_image_1ch[0, :]
    hex_gzip = uint8_array.tobytes().decode("utf-8")
    gzip_byte_str = bytes.fromhex(hex_gzip)
    json_byte_str = gzip.decompress(gzip_byte_str)
    json_str = json_byte_str.decode("utf-32")
    rtsp_config_dict = json.loads(json_str)
    
    return rtsp_config_dict

# .....................................................................................................................

def save_obfuscated_rtsp_image(location_select_folder_path, camera_select, rtsp_image_1ch):
    
    '''
    Helper function which saves obfuscated rtsp (image) data
    
    Inputs:
        location_select_folder_path, camera_select -> (Strings) Camera pathing
        
        rtsp_image_1ch -> (numpy uint8 array) Obfuscated rtsp data, in image format for saving
    
    Outputs:
        rtsp_as_png_data (numpy array/uint8 byte png data)
    '''
    
    # Encode the image data as a png. It needs to be lossless!
    encode_success, rtsp_as_png_data = cv2.imencode(".png", rtsp_image_1ch)
    if not encode_success:
        raise AttributeError("Error encoding rtsp data... Not sure what happened")
    
    # Build the save path and manually write the (binary) data
    save_path = build_rtsp_file_path(location_select_folder_path, camera_select)
    with open(save_path, "wb") as out_file:
        out_file.write(rtsp_as_png_data)
    
    return rtsp_as_png_data

# .....................................................................................................................

def load_obfuscated_rtsp_image(location_select_folder_path, camera_select):
    
    '''
    Helper function which loads obfuscated rtsp (image) data
    
    Inputs:
        location_select_folder_path, camera_select -> (Strings) Camera pathing
    
    Outputs:
        load_success (boolean), rtsp_image_1ch (numpy uint8 array)
    '''
    
    # Initial outputs
    load_success = False
    rtsp_image_1ch = None
    
    # Build pathing to rtsp data and check that it exists before trying to load!
    load_path = build_rtsp_file_path(location_select_folder_path, camera_select)
    file_exists = (os.path.exists(load_path))
    
    # If the file does exist, try to load it in as an image
    if file_exists:
        rtsp_image_1ch = cv2.imread(load_path, cv2.IMREAD_GRAYSCALE)
        load_success = (type(rtsp_image_1ch) is np.ndarray)
    
    return load_success, rtsp_image_1ch

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap


