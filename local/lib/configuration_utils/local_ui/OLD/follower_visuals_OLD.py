#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Oct  8 10:24:43 2019

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

# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes

class Mouse_Follower:
    
    # .................................................................................................................
    
    def __init__(self):
        
        # Allocate storage for mouse position and whether following is enabled or not
        self.mouse_xy = np.array((0, 0), dtype=np.int32)
        self.follow_state = True
        
    # .................................................................................................................
        
    def __call__(self, *args, **kwargs):
        ''' Convenience wrapper. Allows object to be used as a callback function directly '''
        return self.callback(*args, **kwargs)
        
    # .................................................................................................................
                
    def callback(self, event, mx, my, flags, param):
        
        # Record mouse xy position
        if self.follow_state:
            self.mouse_xy = np.int32((mx, my))
        
        # Toggle following state on left click
        if event == cv2.EVENT_LBUTTONDOWN:
            self.follow_state = (not self.follow_state)
            
    # .................................................................................................................
    
    def draw_mouse_xy(self, display_frame, point_radius = 5, point_color = (255, 0, 255)):
        
        ''' Function to help with debugging. Displays a point at the mouse location, along with x/y co-ordinates '''
        
        xy_tuple = tuple(self.xy)
        text_xy = (xy_tuple[0] + point_radius + 2, xy_tuple[1] + 5)
        
        drawn_frame = display_frame.copy()
        cv2.circle(drawn_frame, xy_tuple, point_radius, point_color, -1, cv2.LINE_AA)
        cv2.putText(drawn_frame, 
                    "({:.0f}, {:.0f})".format(*xy_tuple), 
                    text_xy,
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (255, 255, 255),
                    1,
                    cv2.LINE_AA)
        
        return drawn_frame
    
    # .................................................................................................................
    
    @property
    def xy(self):
        return self.mouse_xy
    
    # .................................................................................................................
    # .................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

# .....................................................................................................................

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Demo

if __name__ == "__main__":
    
    # Set display parameters
    frame_width, frame_height = 600, 300
    blank_frame = np.full((frame_height, frame_width, 3), (33, 166, 83), dtype=np.uint8)
    frame_wh = (frame_width, frame_height)
    
    # Set up example mouse follower
    follower = Mouse_Follower()
    
    # Window creation & callback assignment
    window_name = "FOLLOWER EXAMPLE"
    cv2.namedWindow(window_name)    
    cv2.setMouseCallback(window_name, follower)
    
    while True:
        
        # Get a clean copy of the video
        display_frame = blank_frame.copy()
        
        # Draw mouse location as an example
        drawn_frame = follower.draw_mouse_xy(display_frame)
        cv2.imshow(window_name, drawn_frame)
        
        # Get keypress
        keypress = cv2.waitKey(40)
        esc_key_press = (keypress == 27)
        q_key_pressed = (keypress == 113)
        if esc_key_press or q_key_pressed:
            break
        
    # Clean up windows
    cv2.destroyAllWindows()

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap

