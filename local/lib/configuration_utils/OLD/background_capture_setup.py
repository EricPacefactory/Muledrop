#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Jun 19 13:08:01 2019

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
import cv2
import numpy as np

from time import perf_counter
from collections import deque

from local.lib.file_access_utils.bgcapture import save_bg_capture_config
from local.lib.file_access_utils.shared import configurable_dot_path

from local.lib.configuration_utils.local_ui.local_windows_base import Simple_Window
from local.lib.configuration_utils.local_ui.local_controls import Local_Window_Controls


from eolib.utils.cli_tools import cli_confirm
from eolib.utils.files import get_file_list_by_age
from eolib.video.windowing import Progress_Bar
from eolib.math.plots.simple import Positive_Line_Plot


# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes

class Loadbased_Slideshow_Window(Simple_Window):
    
    # .................................................................................................................
    
    def __init__(self, window_name, file_source_list, select_last_by_default = True):
        
        # Inherit from parent class
        super().__init__(window_name)
        
        # Save input data
        self.source_list = list(file_source_list)
        self.num_source = len(file_source_list)
        self.current_select = -1
        
        # Bail if there are no files!
        if self.num_source < 1:
            return
        
        # Cheat a bit for convenience. If there is only one file, duplicate it so we don't have weird trackbar issues
        if self.num_source == 1:
            self.source_list.append(self.source_list[0])
            self.num_source = 2
        
        # Allocate variable for keeping track of the currently selected file
        num_trackbar = self.num_source - 1
        start_select = num_trackbar if select_last_by_default else 0
        
        # Add a trackbar to control access to selecting which file to display
        self.add_trackbar("File select", start_select, num_trackbar)
        
        # Load initial file and display
        self.read_file_select()
        
    # .................................................................................................................
        
    def read_file_select(self):
        
        # Don't do anything if we don't have enough sources to have a selection
        if self.num_source < 1:
            return
        
        # Check if the file selection has changed, and if so, load the newly selected file and display it
        file_select_idx = self.read_trackbar("File select")
        if file_select_idx != self.current_select:
            self.current_select = file_select_idx
            loaded_image = cv2.imread(self.source_list[file_select_idx])
            self.imshow(loaded_image)
            
            # Record the sizing of the displayed image, so we know how big our window is
            frame_height, frame_width = loaded_image.shape[0:2]
            self.width = frame_width
            self.height = frame_height
    
    # .................................................................................................................
    # .................................................................................................................
    
    
# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////


class Background_Capture_Configuration:
    
    # .................................................................................................................
    
    def __init__(self, configurable_helper, video_reader, background_capture_ref):
        
        # Store the config help, so we can use it to access the file system later
        self.config_helper = configurable_helper
        self.video_reader = video_reader
        self.bgcap_ref = background_capture_ref
        
        # Grab initial controls info
        self.controls_json = background_capture_ref.controls_manager.to_json()
        self.initial_settings = background_capture_ref.current_settings()
        
        # Grab video size for simpler access, since we'll need this for sizing
        self.video_wh = video_reader.video_wh
    
    # .................................................................................................................
    
    def read_generation_controls(self, frame_delay_ms = 50):
    
        # Store keys used to quit/cancel or continue with background generation
        cancel_keys = [27, 113]     # esc, q
        continue_keys = [32]        # spacebar
        
        # Set up controls
        local_controls = Local_Window_Controls(self.controls_json, self.initial_settings)
        
        # Bail if there aren't any controls!
        if len(self.controls_json) == 0:
            print("", "No background capture controls to display!", "", sep="\n")
            return False
        
        # Create image to display cancel/continue controls
        frame_width, frame_height = 800, 130
        text_config = {"fontFace": cv2.FONT_HERSHEY_SIMPLEX, "fontScale": 0.75, "color": (255, 255, 255),
                       "thickness": 1, "lineType": cv2.LINE_AA}
        info_window = Simple_Window("Background Generation", frame_width = frame_width, frame_height = frame_height)
        info_frame = np.zeros((frame_height, frame_width, 3), dtype=np.uint8)
        cv2.putText(info_frame, "Press spacebar to continue to background generation", (20, 40), **text_config)
        cv2.putText(info_frame, "Press q or Esc to quit", (20, 90), **text_config)    
        info_window.imshow(info_frame)
        info_window.move_center_norm(x_norm = 0.5, y_norm = 0.5)
        
        # Loop to allow user to set background capture/generation settings
        request_break = True
        while True:
            
            # Read local controls & update the configurable if anything changes
            values_changed_dict = local_controls.read_all_controls()
            if values_changed_dict:
                self.bgcap_ref.reconfigure(values_changed_dict)
            
            # Read keypresses to cancel or continue with background generation
            keypress = cv2.waitKey(frame_delay_ms) & 0xFF
            
            # Check for enter key
            if keypress in cancel_keys:
                break
            
            # Check for esc/q to cancel
            if keypress in continue_keys:
                request_break = False
                break
            
            # Quit if the info window is closed
            if not info_window.exists():
                break
            
        # Close the control windows
        cv2.destroyAllWindows()
        
        return request_break
    
    # .................................................................................................................
    
    def background_capture_loop(self):
    
        # Allocate storage for timing outputs
        frame_time_sec_list = []
        generation_timing_sec_list = []
        
        # Set up progress bar display
        total_frames = self.video_reader.total_frames
        prog_bar = Progress_Bar(total_frames, 
                                window_label = "Generating backgrounds...", 
                                update_rate = 100)
        
        # Run video loop
        cancel_early = False
        while True:
            
            # Grab frames from the video source (with timing information for each frame!)
            req_break, input_frame, current_time_elapsed, current_datetime = self.video_reader.read()
            if req_break:
                break
            
            # Handle background capture stage
            t1 = perf_counter()
            bg_outputs = self.bgcap_ref.run(input_frame, current_time_elapsed, current_datetime)
            t2 = perf_counter()
            
            # Unpack the background updates manually
            bg_update = bg_outputs.get("bg_update")
            #bg_frame = bg_outputs.get("bg_frame")
            #video_frame = bg_outputs.get("video_frame")
            
            # Get timing
            if bg_update:            
                # When generation occurs, grab the timing (and ignore frame timing, since it will be distorted)
                generation_time_sec = self.bgcap_ref.get_current_generation_time()
                generation_timing_sec_list.append(generation_time_sec)
                
            else:            
                # Get & store the frame timing (but only on non-update frames, since it messes with the interpretation)
                time_delta_sec = (t2 - t1)
                frame_time_sec_list.append(time_delta_sec)
            
            # Update progress bar
            win_exists = prog_bar.update()
            if not win_exists:
                cancel_early = True
                break
        
        # Deal with video clean-up
        self.video_reader.release()
        cv2.destroyAllWindows()
        
        return cancel_early, frame_time_sec_list, generation_timing_sec_list
        
    # .................................................................................................................
    
    def delete_existing_background_data(self):
    
        # Initialize output
        request_break = False
        
        # Get pathing to the captured/generated files to check if files already exist, and so we can load later
        capture_path = self.bgcap_ref.captures_folder_path
        generate_path = self.bgcap_ref.generated_folder_path
        
        # Check for existing background capture/generation data
        _, captured_paths = get_file_list_by_age(capture_path, newest_first = True, return_full_path = True)
        _, generated_paths = get_file_list_by_age(generate_path, newest_first = True, return_full_path = True)
        
        # Warn user about deletion, if data already exists, before deleting!
        num_captures, num_generated = len(captured_paths), len(generated_paths)
        existing_captures, existing_generated = (num_captures > 0), (num_generated > 0)
        if existing_captures or existing_generated:
            print("", 
                  "Existing background files found! ({} captures, {} generated)".format(num_captures, num_generated),
                  sep="\n")
            user_confirm = cli_confirm("These will be deleted. Ok?", default_response = False, prepend_newline = False)
            request_break = (not user_confirm)
            if request_break:
                return request_break
            
        # If we get here, delete any background files we might have
        for each_capture_image_path in captured_paths:
            os.remove(each_capture_image_path)
        for each_generated_image_path in generated_paths:
            os.remove(each_generated_image_path)
            
        return request_break
    
    # .................................................................................................................
    
    def generate_new_background_data(self):
    
        # Get pathing to the captured/generated files to check if files already exist, and so we can load later
        capture_path = self.bgcap_ref.captures_folder_path
        generate_path = self.bgcap_ref.generated_folder_path
        
        # Run background capture!
        req_break, frame_timing_list, generation_timing_list = self.background_capture_loop()
        
        # Get (age-sorted) pathing to captured/generated background files
        _, sorted_captured_paths = get_file_list_by_age(capture_path, newest_first = False, return_full_path = True)
        _, sorted_generated_paths = get_file_list_by_age(generate_path, newest_first = False, return_full_path = True)
        
        # Store the image pathing and timing data for convenient passing/access
        image_load_dict = {"captured": sorted_captured_paths, "generated": sorted_generated_paths}
        timing_data_dict = {"frame_timing": frame_timing_list, "generation_timing": generation_timing_list}
        
        return req_break, image_load_dict, timing_data_dict
    
    # .................................................................................................................
    
    def present_generated_results(self, image_load_dict, timing_data_dict):
    
        # Store keys used to quit/cancel or continue with background generation
        cancel_keys = [27, 113]     # esc, q
        continue_keys = [32]        # spacebar
        
        # Get image file list data for display
        captures_file_list = image_load_dict["captured"]
        generated_file_list = image_load_dict["generated"]
        
        # Create display windows
        frame_time_window = Simple_Window("Frame Timing")
        gener_time_window = Simple_Window("Generation Timing")
        capture_window = Loadbased_Slideshow_Window("Captures", captures_file_list)
        generate_window = Loadbased_Slideshow_Window("Backgrounds", generated_file_list)
        
        # Move the windows
        capture_window.move_corner_pixels(x_pixels = 50, y_pixels = 200)
        generate_window.move_corner_pixels(x_pixels = 800, y_pixels = 200)
        
        
        # Now get timing data for display
        frame_time_sec_list = timing_data_dict["frame_timing"]
        generation_time_ms_list = timing_data_dict["generation_timing"]
    
        # Create frame timing plot image
        frame_time_plot = Positive_Line_Plot(800, 450)
        frame_time_image = frame_time_plot.plot(frame_time_sec_list, display_units = "s")
    
        # Create generation timing plot image
        gener_time_plot = Positive_Line_Plot(800, 450)
        gener_time_plot.change_plot_line((100, 50, 170), 2)
        gener_time_image = gener_time_plot.plot(generation_time_ms_list, display_units = "s")
        
        # Create plot windows
        frame_time_window.imshow(frame_time_image)
        gener_time_window.imshow(gener_time_image)
        frame_time_window.move_corner_pixels(x_pixels = 75, y_pixels = 100)
        gener_time_window.move_corner_pixels(x_pixels = 950, y_pixels = 100)
        
        # Loop to allow the user to change which loaded files (captures/generated) they want to view
        req_break = False
        while True:
            
            # Check for changes to the selected file being viewed
            capture_window.read_file_select()
            generate_window.read_file_select()
            
            # Close if all of the windows are closed
            win_exists = [capture_window.exists(), generate_window.exists(), 
                          frame_time_window.exists(), gener_time_window.exists()]
            if not any(win_exists):
                req_break = True
                break
            
            keypress = cv2.waitKey(50) & 0xFF
            if keypress in cancel_keys:
                req_break = True
                break
            
            if keypress in continue_keys:
                break
            
        # Close the slideshow windows
        cv2.destroyAllWindows()
        
        return req_break
    
    # .................................................................................................................
    
    def generate_base_background(self, num_captures = 5):
        
        # Check the type of video
        video_type = self.video_reader.video_type
        
        # Some feedback
        print("Generating starting background image...")
        
        # If the video source is a file, generate the background by grabbing frames from throughout the video
        if video_type == "file":
            
            # Check how many frames we have to work with
            starting_frame = self.video_reader.get_current_frame()
            total_frames = self.video_reader.total_frames
            
            # Allocate storage for capture data
            capture_size = min(total_frames, num_captures)
            capture_deck = deque([], maxlen = capture_size)
            
            # Generate the frame capture indices
            frame_inds = np.int32(np.round(np.linspace(0, total_frames - 1, capture_size)))
            
            # Create a progress bar for feedback
            prog_bar = Progress_Bar(capture_size, "Generating initial background", 
                                    bg_color = (45,45,45), bar_color = (75, 7, 85), update_rate = 1)
            
            # Loop through every target frame index and grab the frame data
            for each_idx in frame_inds:
                
                # Jump to the target frame and read it
                self.video_reader.set_current_frame(each_idx)
                req_break, frame, _, _ = self.video_reader.read()
                if req_break:
                    self.video_reader.release()
                    raise Exception("Error grabbing video frame: {} / {}".format(each_idx, total_frames))
                
                # Store the target frame
                capture_deck.append(frame)
                
                # Update the progress bar for feedback
                prog_bar.update()
                
            # Now generate median image to use as the starting image
            starting_bg = np.uint8(np.median(capture_deck, axis=0))
            
            # Reset the video position before finishing up
            self.video_reader.set_current_frame(starting_frame)
            
        elif video_type == "rtsp":
            raise NotImplementedError("Can't generate base background image from rtsp, not working yet!")
        else:
            raise TypeError("Unrecognized video type: {}".format(video_type))
        
        return starting_bg
    
    # .................................................................................................................
    
    def ask_to_save_bgcapture_config(self):
        
        # Get the name of the file to save
        component_name, script_name, class_name, config_data = self.bgcap_ref.get_data_to_save()
        
        # Decide if we even need to save (i.e. has the configuration changed from the initial settings?)
        is_a_passthrough = ("passthrough" in script_name.lower())
        settings_unchanged = (config_data == self.initial_settings)
        if settings_unchanged and not is_a_passthrough:
            print("", "Settings unchanged!", "Skipping save prompt...", "", sep="\n")
            return
        
        # Prompt the user to save the file
        user_confirm = cli_confirm("Save configuration?", default_response = False)
        if not user_confirm:
            
            # User cancelled, so print out info in case they needed it!
            json.dumps(config_data)
            print("",
                  "Here are the config settings,",
                  "in case that cancel was an accident!",
                  "",
                  json.dumps(config_data, indent = 2),
                  "", sep = "\n")
            return
        
        # Get pathing info from the config helper
        cameras_folder = self.config_helper.cameras_folder
        camera_select = self.config_helper.camera_select
        user_select = self.config_helper.user_select
        
        # If we got here, we're saving! So overwrite the component config file
        save_bg_capture_config(cameras_folder, camera_select, user_select, 
                               script_name, class_name, config_data)
        
    # .................................................................................................................
    # .................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

# .....................................................................................................................
    
def run_bgcap_config_loop(video_reader_ref,
                          bg_config_helper,
                          background_capture_ref,
                          controls_json, 
                          initial_settings,
                          config_helper):

    # Read user input on setting up the background capture controls
    req_break = bg_config_helper.read_generation_controls()
    if req_break:
        print("", "Cancelled background generation!", "", sep="\n")
        return
    
    # Check for existing files, and delete if necessary
    req_break = bg_config_helper.delete_existing_background_data()
    if req_break:
        print("", "File deletion cancelled!", "No background generated!", "", sep="\n")
        return
    
    # Generate base starting background image
    starting_bg = bg_config_helper.generate_base_background()
    background_capture_ref.set_current_background(starting_bg, None, None)
    
    # Run through the video as fast as possible, getting all capture + generated data
    req_break, image_load_dict, timing_data_dict = bg_config_helper.generate_new_background_data()
    if req_break:
        print("", "Cancelled background generation!", "", sep="\n")
        return
    
    # Present generated results to the user
    req_break = bg_config_helper.present_generated_results(image_load_dict, timing_data_dict)
    
    # If we get here, save the background capture config, if needed
    bg_config_helper.ask_to_save_bgcapture_config()

# .....................................................................................................................
# .....................................................................................................................  

# ---------------------------------------------------------------------------------------------------------------------
#%% Demo

if __name__ == "__main__":

    pass


# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap

'''
TODO:
    
    - Need to clean up the background capture config implementation!
        - Need to consider use with regular 'config helper'
        - Try to streamline bgcapture config, but not clear how?
        - Ideally would allow for creation of custom displays, similar to display manager on other configs
    
    - Display captures & generated backgrounds as they occur, rather than separately afterwards
        - This would give better progress feedback
        - Plus allow for early cancel if things look bad
        - Also allow for early stop if things are 'good enough'?   
        
    - Temporarily save captures/generated backgrounds in a separate folder while configuring
        - Don't delete existing data until the user confirms they want to save the new config
        - Would then delete existing data and copy temporary files 
        - Prevents awkward situation where user doesn't agree to save, but has lost all existing capture data...
'''
