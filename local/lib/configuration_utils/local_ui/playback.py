#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Jun 18 15:49:12 2019

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

from local.lib.configuration_utils.local_ui.windows_base import Simple_Window
from local.lib.configuration_utils.local_ui.drawing import waitKey_ex

# ---------------------------------------------------------------------------------------------------------------------
#%% Define Classes

class Local_Playback_Controls(Simple_Window):
    
    # .................................................................................................................
    
    def __init__(self, video_reader_ref, playback_access_ref):
        
        # Inherit from parent class
        super().__init__("Playback Controls")
        
        # Set up keypress variables
        self.quit_keys = [113, 27]      # 113 -> q and  27 -> 'esc'
        self.start_loop_key = 49        # 49 -> 1
        self.end_loop_key = 50          # 50 -> 2
        self.start_loop_down_key = 44   # 44 -> '<'
        self.end_loop_up_key = 46       # 46 -> '>'
        self.skip_backward_key = 45     # 45 -> "-"
        self.skip_forward_key = 61      # 61 -> "="
        self.dec_delay_key = 91         # 91 -> [
        self.inc_delay_key = 93         # 93 -> ]
        self.pause_key = 32             # 32 -> spacebar
        self.save_settings_key = 112    # 112 -> p
        self.reset_settings_key = 111   # 111 -> o
        
        # Store the playback settings access object so we can load/save playback settings
        self.pback_access = playback_access_ref
        
        # Store the video reader, since we'll need to (playback) control it!
        self.vreader = video_reader_ref
        self.start_loop_index = None
        self.end_loop_index = None
        self.frame_delay_ms = None
        self.current_frame_trackbar = None
        self.paused = False
        
        # Get some info about the video playback, so we can properly set up controls
        self.video_fps = video_reader_ref.get(cv2.CAP_PROP_FPS)
        self._frame_period_ms = 1000/self.video_fps
        self.total_frames = int(video_reader_ref.get(cv2.CAP_PROP_FRAME_COUNT))
        self._max_frame = self.total_frames - 1
        self.frame_skip = max(100, int(5 * self.video_fps))
        
        # Set up basic sizing
        frame_width = 300
        x_padding, y_padding = 20, 20
        
        # Create the initial frame and record positioning needed for drawing new text updates
        self.bg_frame = self._draw_initial_frame(frame_width)
        
        # Draw and position initial frame
        self.imshow(self.bg_frame)
        self.move_corner_pixels(self.screen_width - frame_width - x_padding, y_padding)
        
        # Attach a trackbars for controlling frame position, loop start/end and frame delay time
        self.add_trackbar("F", 0, self._max_frame)
        self.add_trackbar("S", 0, self._max_frame)
        self.add_trackbar("E", 0, self._max_frame)
        self.add_trackbar("Frame Delay (ms)", 0, 1000)
        
        # Set up the initial track bar states, either by 'reseting' or by loading some playback settings
        self._set_initial_trackbar_state()
        
        # Read initial controls state, to make sure we have all our variables sorted out
        self._read_loop_controls()
    
    # .................................................................................................................
    
    def update(self):
        
        frame_delay = self._read_loop_controls()
        req_break, keycode, modifier_code = self._read_keypress(frame_delay)        
        video_reset = self._update_video_state()
        
        return req_break, video_reset, keycode, modifier_code
     
    # .................................................................................................................
    
    def _read_loop_controls(self):
        
        # Hard-code the controls to read, since there aren't too many
        self.start_loop_index = self.read_trackbar("S")
        self.end_loop_index = self.read_trackbar("E")
        self.frame_delay_ms = max(1, self.read_trackbar("Frame Delay (ms)"))            
        
        # In special pause case, return a zero frame delay to force keypress updates
        if self.paused:
            return 0
        
        return self.frame_delay_ms
    
    # .................................................................................................................
    
    def _read_frame_positioning(self):        
        return self.read_trackbar("F")
    
    # .................................................................................................................
    
    def _read_keypress(self, frame_delay_ms):
        
        # Break if the window goes down
        if not self.exists():
            return True, -1
        
        # Get keypress
        keycode, modifier = waitKey_ex(frame_delay_ms)
        req_break = (keycode in self.quit_keys)
        
        # Start loop set index key
        if keycode == self.start_loop_key:
            self.start_loop_index = self.vreader.get_current_frame()
            self.set_trackbar("S", self.start_loop_index)
            
        # End loop set index key
        elif keycode == self.end_loop_key:
            self.end_loop_index = self.vreader.get_current_frame()
            self.set_trackbar("E", self.end_loop_index)
            
        # Start loop decrement key
        elif keycode == self.start_loop_down_key:
            self.start_loop_index = max(0, self.start_loop_index - 10)
            self.set_trackbar("S", self.start_loop_index)
        
        # End loop increment key
        elif keycode == self.end_loop_up_key:
            self.end_loop_index = min(self._max_frame, self.end_loop_index + 10)
            self.set_trackbar("E", self.end_loop_index)
            
        # Skip backward key
        elif keycode == self.skip_backward_key:
            curr_frame = self.vreader.get_current_frame()
            new_frame_index = max(0, (curr_frame - self.frame_skip))
            self._update_frame_position_trackbar(new_frame_index)
            #self.vreader.set_current_frame(new_frame_index)
            
        # Skip forward key
        elif keycode == self.skip_forward_key:
            curr_frame = self.vreader.get_current_frame()
            new_frame_index = min(self._max_frame, (curr_frame + self.frame_skip))
            self._update_frame_position_trackbar(new_frame_index)
            #self.vreader.set_current_frame(new_frame_index)
        
        # Decrease frame delay key
        elif keycode == self.dec_delay_key:
            self.frame_delay_ms = max(0, self.frame_delay_ms - 10)
            self.set_trackbar("Frame Delay (ms)", self.frame_delay_ms)
        
        # Increase frame delay key
        elif keycode == self.inc_delay_key:
            self.frame_delay_ms = min(1000, self.frame_delay_ms + 10)
            self.set_trackbar("Frame Delay (ms)", self.frame_delay_ms)
            
        # Pause/unpause key
        elif keycode == self.pause_key:
            self.paused = not self.paused
            
        # Save settings key
        elif keycode == self.save_settings_key:
            self._save_settings()
            
        # Reset settings key
        elif keycode == self.reset_settings_key:
            self._reset_settings()
        
        
        # To figure out key press values....
        #print(keycode)
        
        return req_break, keycode, modifier
        
    # .................................................................................................................
    
    def _update_video_state(self):
        
        # Default output
        video_reset = False
        
        # Figure out where the video currently is, so we can decide if we need to change anything
        video_frame_pos = self.vreader.get_current_frame()
        current_frame_trackbar = self._read_frame_positioning()
        current_frame_changed = (abs(video_frame_pos - current_frame_trackbar) > 1)
        
        # Check if the user manually changed the frame position, if not, update it with the video frame position
        if current_frame_changed:
            self.vreader.set_current_frame(current_frame_trackbar)
            video_reset = True
        else:
            self._update_frame_position_trackbar(video_frame_pos)
        
        # Force looping if the video passes the end loop index
        if video_frame_pos > self.end_loop_index:
            self.vreader.set_current_frame(self.start_loop_index)
            self.set_trackbar("F", self.start_loop_index)
            video_reset = True
            
        # Force start of looping if the video is starting before the start loop index
        elif video_frame_pos < self.start_loop_index:
            self.vreader.set_current_frame(self.start_loop_index)
            self.set_trackbar("F", self.start_loop_index)
            video_reset = True
            
        return video_reset
    
    # .................................................................................................................
    
    def _update_frame_position_trackbar(self, new_position):
        self.set_trackbar("F", new_position)
    
    # .................................................................................................................
        
    def _draw_initial_frame(self, frame_width,
                            bg_even_color = (47, 42, 48), 
                            bg_odd_color = (25, 20, 27), 
                            text_color = (200, 200, 200)):
        
        # Build messages
        msg_strs = [("+ / -", "Skip forward/backward"),
                    ("1 / 2", "Set looping start/end frames"),
                    ("< / >", "Adjust start/end loop points"),
                    ("[ / ]", "Decrease/increase frame delay"),
                    ("spacebar", "Pause/unpause"),
                    ("p / o", "Save/reset playback settings")]
        
        # Set up text styling
        sub_spacing, row_spacing = 10, 20
        x_pad, y_pad = 5, 4
        sub_x_offset = 10
        text_config = {"fontFace": cv2.FONT_HERSHEY_SIMPLEX,
                       "fontScale": 0.4,
                       "color": text_color,
                       "thickness": 1,
                       "lineType": cv2.LINE_AA}
        
        # Get text sizing
        (x_size, y_size), y_baseline = \
        cv2.getTextSize("Test Text", text_config["fontFace"], text_config["fontScale"], text_config["thickness"])
        
        # Set up sizing variables
        size_per_msg = (y_size + sub_spacing + y_size + row_spacing)
        
        # Set up text postioning
        x_pos_cmd = x_pad
        y_pos_cmd = y_size + y_baseline + y_pad
        x_pos_msg = x_pos_cmd + sub_x_offset
        y_pos_msg = y_pos_cmd + y_size + sub_spacing
        
        # Create empty frame for drawing text
        blank_even_frame = np.full((size_per_msg, frame_width, 3), bg_even_color, dtype=np.uint8)
        blank_odd_frame = np.full((size_per_msg, frame_width, 3), bg_odd_color, dtype=np.uint8)
        
        frame_stack = []
        for each_idx, (each_cmd, each_msg) in enumerate(msg_strs):
            new_control_block = blank_even_frame.copy() if (each_idx % 2 == 0) else blank_odd_frame.copy()
            cv2.putText(new_control_block, "{}".format(each_cmd), (x_pos_cmd, y_pos_cmd), **text_config)
            cv2.putText(new_control_block, each_msg, (x_pos_msg, y_pos_msg), **text_config)
            frame_stack.append(new_control_block)
        
        # Vertically stack each drawn control text frame for the output
        out_frame = np.vstack(frame_stack)
        
        return out_frame
    
    # .................................................................................................................
    
    def _set_initial_trackbar_state(self):
        
        # Have the playback controller handle the file i/o
        settings_exist, settings_tuple = self.pback_access.load_settings()
        
        # For debugging
        #print("PLAYBACK SETTINGS:", settings_exist)
        #print(settings_tuple)
        
        # If settings were found, try setting the trackbars to the corresponding values
        if settings_exist:
            current_frame_index, start_loop_index, end_loop_index, frame_delay_ms = settings_tuple
            
            try:
                self.set_trackbar("F", current_frame_index)
                self.set_trackbar("S", start_loop_index)
                self.set_trackbar("E", end_loop_index)
                self.set_trackbar("Frame Delay (ms)", frame_delay_ms)
                
                # Force the video to the correct starting frame
                self.vreader.set_current_frame(current_frame_index)
                
            except TypeError:
                settings_exist = False
                print("",
                      "ERROR loading playback settings:", 
                      "  F: {}".format(current_frame_index),
                      "  S: {}".format(start_loop_index),
                      "  E: {}".format(end_loop_index),
                      "  Frame Delay (ms): {}".format(frame_delay_ms),
                      "", sep="\n")
        
        # If no settings were found, perform a 'standard' reset
        if not settings_exist:
            self._reset_settings()
    
    # .................................................................................................................
    
    def _reset_settings(self):
        
        # Attach a trackbars for controlling frame position, loop start/end and frame delay time
        self.set_trackbar("S", 0)
        self.set_trackbar("E", self._max_frame)
        self.set_trackbar("Frame Delay (ms)", int(round(self._frame_period_ms)))

    # .................................................................................................................
    
    def _save_settings(self):
        
        # Read frame index setting, which constantly changes...
        frame_index = self._read_frame_positioning()
        self._read_loop_controls()
        
        # Get non-volatile settings
        self._read_loop_controls()
        start_index = self.start_loop_index
        end_index = self.end_loop_index
        frame_delay_ms = self.frame_delay_ms
        
        # Have the playback controller manage the file i/o
        self.pback_access.save_settings(frame_index, start_index, end_index, frame_delay_ms)

    # .................................................................................................................
    # .................................................................................................................

# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
    
# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

# .....................................................................................................................

# .....................................................................................................................
# .....................................................................................................................
    
# ---------------------------------------------------------------------------------------------------------------------
#%% Demo
    
if __name__ == "__main__":
    pass
    
# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap


