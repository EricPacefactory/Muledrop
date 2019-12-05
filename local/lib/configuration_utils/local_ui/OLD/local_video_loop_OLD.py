#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon May 27 15:02:51 2019

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

from local.lib.configuration_utils.local_ui.windows_base import Simple_Window, display_wh
from local.lib.configuration_utils.local_ui.timing import Local_Timing_Window
from local.lib.configuration_utils.local_ui.controls import Local_Window_Controls
from local.lib.configuration_utils.local_ui.playback import Local_Playback_Controls

# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

# .....................................................................................................................


#def local_video_loop(process_info_dict, display_manager_ref):
def local_core_config_video_loop(video_reader_ref,
                                 background_capture_ref,
                                 core_bundle_ref,
                                 core_ref,
                                 controls_json,
                                 initial_settings,
                                 display_manager_ref,
                                 config_helper):
    
    # Try to close any previously opened windows
    try: cv2.destroyAllWindows()
    except: pass
    
    # Generate stage timing window
    timing_window = Local_Timing_Window()
    
    # Generate a video playback control window
    playback_controls = Local_Playback_Controls(video_reader_ref, config_helper)
    
    # Generate the local control windows
    local_controls = Local_Window_Controls(controls_json, initial_settings)
    
    # Get general display configuration and create the displays
    display_config, display_callbacks = display_manager_ref.get_config_info()
    window_ref_list = _create_display_windows(display_config)
    #local_displays = Local_Display_Windows(display_manager_ref) # <-- Ideally do something like this to bundle up behaviour
    
    # Run video loop
    while True:
        
        # Grab frames from the video source (with timing information for each frame!)
        req_break, input_frame, current_time_elapsed, current_datetime = video_reader_ref.read()
        if req_break:
            # Loop the video back at the end if we miss a frame
            video_reader_ref.set_current_frame(0)
            core_bundle_ref.reset_all()
            continue
        
        # Read local controls & update the configurable if anything changes
        values_changed_dict = local_controls.read_all_controls()
        if values_changed_dict:
            core_ref.reconfigure(values_changed_dict)
        
        # Handle background capture stage
        bg_outputs = background_capture_ref.run(input_frame, current_time_elapsed, current_datetime)
        
        # .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .
        # --- THE FOLLOWING RUNS FOR EACH TASK ---
        
        skip_frame, stage_outputs, stage_timing = \
        core_bundle_ref.run_all(bg_outputs, current_time_elapsed, current_datetime)
        
        # .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .
        # Display
        
        if not skip_frame:
            
            # Display stage timing
            timing_window.display(stage_timing)
            
            # Display images
            _display_images(window_ref_list, display_callbacks, stage_outputs, core_ref)
            #local_displays.update_displays(stage_outputs, core_ref)  # <-- Ideally do something like this
        
        # .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .
        # Playback + keypress controls
        
        # Have playback controls manager keypresses (+ video control!)
        req_break, keypress, video_reset = playback_controls.update()
        if req_break:
            break
        
        # Reset all configurables, since the video position was changed unnaturally
        if video_reset:
            core_bundle_ref.reset_all()
    
    # Deal with video clean-up
    video_reader_ref.release()
    cv2.destroyAllWindows()
    
    # For debugging
    return stage_outputs, stage_timing

# .....................................................................................................................

def _create_display_windows(display_config, x_offset = 0.02, y_offset = 0.25,
                            x_padding = 0.01, y_padding = 0.01):
    
    # Get display window config info 
    num_rows, num_cols = display_config["layout_row_col"]
    initial_display = display_config["initial_display"]
    displays = display_config["displays"]
    
    # Get the users screen size, so we know how/where to place the display windows
    screen_width, screen_height = display_wh()
    
    # Figure out how much to offset the windows from the top-left corner
    x_offset_px = int(round(screen_width * x_offset))
    y_offset_px = int(round(screen_height * y_offset))
    
    # Figure out how much display space is left, so we can determine window spacing
    display_area_width = screen_width - 2*x_offset_px
    display_area_height = screen_height - 2*y_offset_px
    x_locs = x_offset_px + np.linspace(0, display_area_width, num_cols + 1, np.int32)
    y_locs = y_offset_px + np.linspace(0, display_area_height, num_rows + 1, dtype=np.int32)
    
    # Set up each display
    display_info_list = []
    initial_display_info = None
    for each_idx, each_display in enumerate(displays):
        window_name = each_display["window_name"]
        window_wh = each_display["max_wh"]
        #drawing_control_variable_name = each_display["drawing_control"]
        #visualization_variable_name = each_display["visualization"]
        
        # Get initial display width/height if possible
        initial_wh = window_wh if None not in window_wh else (100, 100)
        
        # Get initial window position based on the layout info
        row_idx, col_idx = int(each_idx / num_cols), int(each_idx % num_cols)
        x_pos = x_locs[col_idx]#x_offset_px + col_idx * x_padding
        y_pos = y_locs[row_idx]#y_offset_px + row_idx * y_padding
        initial_position = (int(round(x_pos)),int(round(y_pos)))
        
        # Set up display info
        new_display_info = (window_name, initial_wh, initial_position)
        
        # Skip over the window set as the initial display, since we'll launch that last to force it above others
        if window_name != initial_display:            
            display_info_list.append(new_display_info)
        else:
            initial_display_info = new_display_info
            
    # Append the initial display info to the end of the list, so that it is last to be created
    # (forces it above all other displays)
    display_info_list.append(initial_display_info)
    
    print("DISP CONFIG:")
    print(display_info_list)
    
    # Now actually create and locate each window
    window_ref_list = []
    for each_name, each_wh, each_pos in display_info_list:
        
        print("CREATING", each_name, "@", each_pos, " - ", each_wh)
        
        # Create the window, set its size and position it
        window_ref = Simple_Window(each_name)
        window_ref.imshow_blank(blank_wh = each_wh)
        window_ref.move_corner_pixels(*each_pos)
        
        # Finally, store the reference to the window, since we'll need to return it
        window_ref_list.append(window_ref)
    
    return window_ref_list

# .....................................................................................................................
    
def _display_images(window_ref_list, display_callbacks, stage_outputs, configurable_ref):
    try:
        for each_window_ref in window_ref_list:
            disp_frame = display_callbacks[each_window_ref.window_name](stage_outputs, configurable_ref)
            each_window_ref.imshow(disp_frame)
            
    except KeyError as err:
        print("",
              "Key error ({}) on display window: {}".format(err, each_window_ref.window_name),
              "Probably trying to access stage_outputs that don't exists!", sep="\n")

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Demo

if __name__ == "__main__":
    pass

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap


