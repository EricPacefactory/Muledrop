#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Aug  1 16:59:44 2020

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

from local.lib.common.timekeeper_utils import isoformat_to_datetime, fake_datetime_like

from local.eolib.video.text_rendering import font_config, simple_text, position_frame_relative

# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes


class Key_Check:
    
    '''
    Class used to handle keypress checks
    Intended to be used on the output of cv2.waitKey(...) calls
    '''
    
    # Store keycodes for clarity
    esc_keycode = 27
    spacebar_keycode = 32
    up_keycodes = {82, 119}    # Up or 'w' or key
    left_keycodes = {81, 97}   # Left or 'a' or key
    down_keycodes = {84, 115}  # Down or 's' or key
    right_keycodes = {83, 100} # Right or 'd' or key
    zero_keycode = 48
    one_keycode = 49
    two_keycode = 50
    
    # .................................................................................................................
    
    def __init__(self):
        
        # Do nothing!
        # -> Just here to bundle functionality
        
        pass
    
    # .................................................................................................................
    
    def print_keycode(self, keypress):
        print("KEY:", keypress)
    
    # .................................................................................................................
    
    @classmethod
    def spacebar(cls, keypress):
        return (keypress == cls.spacebar_keycode)
    
    # .................................................................................................................
    
    @classmethod
    def esc(cls, keypress):
        return (keypress == cls.esc_keycode)
    
    # .................................................................................................................
    
    @classmethod
    def up(cls, keypress):
        return (keypress in cls.up_keycodes)
    
    # .................................................................................................................
    
    @classmethod
    def down(cls, keypress):
        return (keypress in cls.down_keycodes)
    
    # .................................................................................................................
    
    @classmethod
    def left(cls, keypress):
        return (keypress in cls.left_keycodes)
    
    # .................................................................................................................
    
    @classmethod
    def right(cls, keypress):
        return (keypress in cls.right_keycodes)
    
    # .................................................................................................................
    
    @classmethod
    def zero(cls, keypress):
        return (keypress == cls.zero_keycode)
    
    # .................................................................................................................
    
    @classmethod
    def one(cls, keypress):
        return (keypress == cls.one_keycode)
    
    # .................................................................................................................
    
    @classmethod
    def two(cls, keypress):
        return (keypress == cls.two_keycode)
    
    # .................................................................................................................
    # .................................................................................................................


# =====================================================================================================================
# =====================================================================================================================


class Snapshot_Playback:
    
    # .................................................................................................................
    
    def __init__(self, num_snapshots, average_snapshot_period_ms = 1000,
                 default_playback_timelapse_factor = 20.0, default_pause_delay_ms = 150):
        
        # Store inputs
        self.num_snapshots = num_snapshots
        self._avg_snapshot_period_ms = average_snapshot_period_ms
        
        # Allocate storage for current snapshot to display & range to loop over
        self._snapshot_idx = 0
        self._start_loop_idx = 0
        self._end_loop_idx = num_snapshots
        
        # Allocate storage for playback control
        self._is_paused = False
        self.playback_tl_factor = None
        self._paused_frame_delay_ms = None
        self._frame_delay_ms = None
        self._fast_frame = False
        
        # Calculate the min/max allowed playback speeds
        self._min_tl_factor = (1 / 1.5)
        self._max_tl_factor = (average_snapshot_period_ms / 1)
        
        # Set initial playback speeds
        self.set_playback_speed(default_playback_timelapse_factor)
        self.set_pause_delay_ms(default_pause_delay_ms)
        
        # Create keypress handler
        self.keycheck = Key_Check()
    
    # .................................................................................................................
    
    @property
    def frame_delay_ms(self):
        
        # Allow for special frame delay override (intended to force faster ui updates)
        if self._fast_frame:
            self._fast_frame = False
            return 1
        
        # Revert to hard-coded delay when paused
        if self._is_paused:
            return self._paused_frame_delay_ms
        
        return self._frame_delay_ms
    
    # .................................................................................................................
    
    def adjust_snapshot_index_from_mouse(self, mouse_position_normalized, force_fast_frame = True):
        
        ''' Helper function used to update playback position based on a normalized mouse co-ordinate '''
        
        # Convert the normalized mouse position to an index value
        start_end_diff = (self._end_loop_idx - self._start_loop_idx - 1)
        raw_index_from_mouse = self._start_loop_idx + (mouse_position_normalized * start_end_diff)
        
        # Make sure the index value is an integer and update our internal records
        new_snapshot_idx = int(round(raw_index_from_mouse))
        self._snapshot_idx = new_snapshot_idx
        
        # Speed up next frame delay for better responsiveness when adjusting via mouse interactions
        if force_fast_frame:
            self.force_fast_frame()
        
        return self._snapshot_idx
    
    # .................................................................................................................
    
    def set_pause_state(self, is_paused):
        self._is_paused = True
        
    # .................................................................................................................
    
    def force_fast_frame(self):
        self._fast_frame = True
    
    # .................................................................................................................
    
    def set_snapshot_index(self, new_snapshot_index):
        self._snapshot_idx = new_snapshot_index
        return self._snapshot_idx
    
    # .................................................................................................................
    
    def get_snapshot_index(self):
        return self._snapshot_idx
    
    # .................................................................................................................
    
    def set_start_loop_index(self, start_loop_index):
        self._start_loop_idx = start_loop_index
        return self._start_loop_idx
    
    # .................................................................................................................
    
    def set_end_loop_index(self, end_loop_index):
        self._end_loop_idx = end_loop_index
        return self._end_loop_idx
    
    # .................................................................................................................
    
    def set_loop_indices(self, start_loop_index, end_loop_index):
        
        ''' Helper function used to set both start/end loop indices at the same time '''
        
        self._start_loop_idx = start_loop_index
        self._end_loop_idx = end_loop_index
        
        return self._start_loop_idx, self._end_loop_idx
    
    # .................................................................................................................
    
    def get_loop_indices(self):
        return self._start_loop_idx, self._end_loop_idx
    
    # .................................................................................................................
    
    def set_pause_delay_ms(self, pause_delay_ms):
        self._paused_frame_delay_ms = int(round(pause_delay_ms))
        return self._paused_frame_delay_ms
    
    # .................................................................................................................
    
    def set_playback_speed(self, playback_timelapse_factor):
        
        # Set frame delay based on a target timelapse factor, instead of using ms timig directly
        self._frame_delay_ms = int(round(self._avg_snapshot_period_ms / playback_timelapse_factor))
        self._frame_delay_ms = max(1, self._frame_delay_ms)
        
        # Store playback factor with limits based on maximum frame delay
        constrained_playback_tl_factor = max(self._min_tl_factor, playback_timelapse_factor)
        constrained_playback_tl_factor = min(self._max_tl_factor, constrained_playback_tl_factor)
        self.playback_tl_factor = constrained_playback_tl_factor
        
        return self._frame_delay_ms
    
    # .................................................................................................................
    
    def update_playback(self, keypress):
        
        # For convenience
        snap_idx = self._snapshot_idx
        
        # Close on esc key
        req_break = self.keycheck.esc(keypress)
        
        # Pause with spacebar
        if self.keycheck.spacebar(keypress):
            self._is_paused = not self._is_paused
        
        # Go back in time with 'left' keys
        elif self.keycheck.left(keypress):
            self._is_paused = True
            snap_idx = snap_idx - 1
        
        # Go forward in time with 'right' keys
        elif self.keycheck.right(keypress):
            self._is_paused = True
            snap_idx = snap_idx + 1
        
        # Speed up playback with 'up' keys
        elif self.keycheck.up(keypress):
            
            # Speed up playback by 15%
            new_tl_factor = 1.15 * self.playback_tl_factor
            self.set_playback_speed(new_tl_factor)
            
            # Reverse playback by one frame to account for forward step due to keypress
            snap_idx = snap_idx - 1 if not self._is_paused else snap_idx
        
        # Slow down playback with 'down' keys
        elif self.keycheck.down(keypress):
            
            # Slow down playback by 15%
            new_tl_factor = self.playback_tl_factor / 1.15
            self.set_playback_speed(new_tl_factor)
            
            # Reverse playback by one frame to account for forward step due to keypress
            snap_idx = snap_idx - 1 if not self._is_paused else snap_idx
        
        # Advance one frame every time we call this function
        if not self._is_paused:
            snap_idx += 1
        
        # Handle looping
        if snap_idx >= self._end_loop_idx:
            snap_idx = self._start_loop_idx
        elif snap_idx < self._start_loop_idx:
            snap_idx = self._end_loop_idx - 1
        
        # Store snapshot index results, since we updated a copy for convenience
        self._snapshot_idx = snap_idx
        
        return req_break
    
    # .................................................................................................................
    
    def playback_as_pixel_location(self, frame_length_px,
                                   current_snapshot_index = None,
                                   start_loop_index = None,
                                   end_loop_index = None):
        
        '''
        Helper function used to convert the current playback position (in terms of snapshot index)
        into a pixel location along a (assumed to be) horizontal image
        Intended to be used for drawing a playback indicator line onto an image
        
        Inputs left as 'None' will be replaced with internal copies of the snapshot/start/end loop indices
        However, they can be overriden if needed (for example, if playback is being modified elsewhere)
        '''
        
        # Handle missing inputs
        if current_snapshot_index is None:
            current_snapshot_index = self._snapshot_idx
        if start_loop_index is None:
            start_loop_index = self._start_loop_idx
        if end_loop_index is None:
            end_loop_index = self._end_loop_idx
    
        # Handle divide-by-zero (or negative numbers?) errors
        index_diff = end_loop_index - start_loop_index - 1
        if index_diff < 1:
            return 0
        
        # Convert relative playback position to a pixel value
        playback_progress = (current_snapshot_index - start_loop_index) / index_diff
        playback_position_px = int(round(playback_progress * (frame_length_px - 1)))
        
        return playback_position_px

    # .................................................................................................................
    # .................................................................................................................


# =====================================================================================================================
# =====================================================================================================================


class Corner_Timestamp:
    
    # .................................................................................................................
    
    def __init__(self, frame_shape, text_position_str, start_datetime = None, use_relative_time = False,
                 font_scale = 0.35, font_fg_color = (255, 255, 255), font_bg_color = (0, 0, 0)):
        
        # Pre-set the font config to avoid re-defining at run time
        self.fg_font_config = font_config(scale = 0.35, color = (255, 255, 255), thickness = 1)
        self.bg_font_Config = font_config(scale = 0.35, color = (0, 0, 0), thickness = 2)
        
        # Store inputs
        self.text_position = self.get_corner_position(frame_shape, text_position_str)
        self.use_relative_time = (start_datetime is not None) and use_relative_time
        self.start_offset_dt = None
        
        # Decide if we're using relative timing or not
        if self.use_relative_time:
            self.start_offset_dt = start_datetime - fake_datetime_like(start_datetime)
        
        # Decide if we're drawing the timestamp or not
        self._enable = (self.text_position is not None)
    
    # .................................................................................................................
    
    def timestamp_from_snapshot_metadata(self, snapshot_metadata, timestamp_format = "%H:%M:%S"):
        
        # Get snapshot timing info
        datetime_isoformat = snapshot_metadata["datetime_isoformat"]
        snap_dt = isoformat_to_datetime(datetime_isoformat)
        
        # Convert timing to 'relative' time, if needed
        if self.use_relative_time:
            snap_dt = snap_dt - self.start_offset_dt
        
        # Get timestamp string based on snapshot datetime information
        timestamp_str = snap_dt.strftime(timestamp_format)
        
        return timestamp_str
    
    # .................................................................................................................
    
    def draw_timestamp(self, display_frame, snapshot_metadata):
        
        # Don't draw anything if we're not enabled
        if not self._enable:
            return display_frame
        
        # For clarity
        centered = False
        
        # Draw timestamp with background/foreground to help separate from video background
        snap_dt_str = self.timestamp_from_snapshot_metadata(snapshot_metadata)
        simple_text(display_frame, snap_dt_str, self.text_position, centered, **self.bg_font_Config)
        simple_text(display_frame, snap_dt_str, self.text_position, centered, **self.fg_font_config)
        
        return display_frame
    
    # .................................................................................................................
    
    def get_corner_position(self, frame_shape, text_position_str):
        
        '''
        Function used to get timestamp corner positioning, assuming an input of type
        'tl', 'tr', 'bl', 'br'
        '''
        
        # Use simple lookup to get the timestamp positioning
        position_lut = {"tl": (3, 3), "tr": (-3, 3),
                        "bl": (3, -1), "br": (-3, -1),
                        "None": None, "none": None}
        
        # If we can't figure out the position, return None to signal we're disabling corner timestamps
        relative_position = position_lut.get(text_position_str, None)
        if relative_position is None:
            return None
        
        return position_frame_relative(frame_shape, "00:00:00", relative_position, **self.fg_font_config)
    
    # .................................................................................................................
    # .................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Helper functions

# .....................................................................................................................

def get_playback_line_coords(playback_position_px, playback_bar_height):
    
    '''
    Helper function for generating the two line drawing co-ordinates
    needed to indicate the playback position on a vertical playback bar image
    '''
    
    pt1 = (playback_position_px, -5)
    pt2 = (playback_position_px, playback_bar_height + 5)
    
    return pt1, pt2

# .....................................................................................................................
    
def get_timestamp_location(timestamp_position_arg, snap_shape, fg_font_config):
    
    # Use simple lookup to get the timestamp positioning
    position_lut = {"tl": (3, 3), "tr": (-3, 3),
                    "bl": (3, -1), "br": (-3, -1),
                    "None": None, "none": None}
    
    # If we can't get the position (either wasn't provided, or incorrectly specified), then we won't return anything
    relative_position = position_lut.get(timestamp_position_arg, None)
    if relative_position is None:
        return None
    
    return position_frame_relative(snap_shape, "00:00:00", relative_position, **fg_font_config)

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Demo

if __name__ == "__main__":
    pass


# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap


