#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Jul 18 13:13:54 2019

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

import cv2
import numpy as np

from local.lib.web_communication import Websocket_Server

# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

# .....................................................................................................................

def web_core_config_video_loop(video_reader_ref,
                               background_capture_ref,
                               core_bundle_ref,
                               core_ref,
                               controls_json,
                               initial_settings,
                               display_manager_ref,
                               config_helper):
    
    # Read the socket info from script args
    socket_ip = config_helper.socket_ip
    socket_port = config_helper.socket_port
    
    # Launch the websocket server to talk with the configuration page!
    display_config, display_callbacks = display_manager_ref.get_config_info()
    socket_server = Websocket_Server(display_config, controls_json, initial_settings,
                                     host = socket_ip, port = socket_port)
    
    # Set the video processing frame delay since playback controls aren't available
    frame_delay_ms = max(1, int(round(1000 / video_reader_ref.video_fps)))
    
    # Set up initial display, so we provide the correct frame data
    #initial_display = display_config.get("initial_display")
    
    # Wait for the client to connect
    socket_server.wait_for_connection()
    
    # Run video loop
    while True:
        
        # Grab frames from the video source (with timing information for each frame!)
        req_break, input_frame, current_time_elapsed, current_datetime = video_reader_ref.read()
        if req_break:
            # Loop the video back at the end if we miss a frame
            video_reader_ref.set_current_frame(0)
            core_bundle_ref.reset_all()
            continue
        
        # Read web control updates & use it to update the configurable if anything changes
        values_changed_dict = socket_server.read_all_controls(debug_messages = True)
        if values_changed_dict:
            core_ref.reconfigure(values_changed_dict)
        
        # Read save triggers
        save_config_data = socket_server.save_trigger()
        if save_config_data:
            core_bundle_ref.force_save_core_config(core_ref)
        
        # Handle background capture stage
        bg_outputs = background_capture_ref.run(input_frame, current_time_elapsed, current_datetime)
        
        # .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .
        # --- THE FOLLOWING RUNS FOR EACH TASK ---
        
        skip_frame, stage_outputs, stage_timing = \
        core_bundle_ref.run_all(bg_outputs, current_time_elapsed, current_datetime)
        
        # .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .
        # Display
        
        if not skip_frame:
            
            # Figure out which display we're showing
            display_select = socket_server.read_current_display()
            display_frame = display_callbacks.get(display_select)(stage_outputs, core_ref)
            
            # Send frame data and stage timing info the client over the socket connection
            socket_server.upload_frame_data(display_frame, stage_timing)
        
        # .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .
        # Playback control
        
        # Delay a bit so we don't blast through the video
        cv2.waitKey(frame_delay_ms)
        
        # Shutdown if the client disconnects
        client_connected = socket_server.has_connection()
        if not client_connected:
            print("Client disconnected! Closing ({})".format(os.path.basename(__file__)))
            break
    
    # Shutdown the server
    socket_server.close()
    
    # Deal with video clean-up
    video_reader_ref.release()
    
    # For debugging
    return stage_outputs, stage_timing

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Demo

if __name__ == "__main__":
    pass

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap


