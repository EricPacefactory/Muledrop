#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Jun 14 16:54:12 2019

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

from local.lib.file_access_utils.video import video_path_from_name
from local.lib.timekeeper_utils import Timekeeper

# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes



class Dummy_vreader:

    def __init__(self, cameras_folder, camera_select, video_select):
        
        # Get pathing to the selected video
        video_source = video_path_from_name(cameras_folder, camera_select, video_select)
        
        # Store video access info
        self.video_source = video_source
        self.vcap = cv2.VideoCapture(video_source)
        self.video_type = "file" # Hard-coded for dummy usage

        # Create object for keeping track of time
        self.timekeeper = Timekeeper()
        self.frame_index = 0

        # Get total frame count (for files only) and framerate
        self.total_frames = int(self.get(cv2.CAP_PROP_FRAME_COUNT))
        self.video_fps = self.get(cv2.CAP_PROP_FPS)

        # Get sizing info
        self.video_width = int(self.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.video_height = int(self.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.video_wh = (self.video_width, self.video_height)
        
    def __repr__(self):
        return "Video source: {} ({}x{} @ {:.1f}Hz)".format(self.video_source, *self.video_wh, self.video_fps)

    def _get_time_file(self):

        # Get the current time into the video file, since we'll use this as time elapsed/time of day
        video_time_sec = self.get_current_video_time_sec()
        video_frame_index = self.get_current_frame_file()
        
        current_frame_index, current_time_sec, current_datetime = \
        self.timekeeper.get_video_timing(video_time_sec, video_frame_index)

        return current_frame_index, current_time_sec, current_datetime

    def _get_time_rtsp(self):
        
        # Get the current time info
        current_time_sec, current_datetime = self.timekeeper.get_rtsp_time()
        current_frame_index = self.timekeeper.get_frame_index(current_datetime)
        
        return current_frame_index, self.timekeeper.get_rtsp_time()

    def read(self):

        (rec_frame, frame) = self.vcap.read()
        req_break = not rec_frame

        curent_frame_index, current_time_sec, current_datetime = self._get_time_file()

        return req_break, frame, curent_frame_index, current_time_sec, current_datetime

    def set(self, property_code, new_value):
        return self.vcap.set(property_code, new_value)

    def get(self, property_code):
        return self.vcap.get(property_code)

    def get_current_video_time_sec(self):
        # File only
        return self.vcap.get(cv2.CAP_PROP_POS_MSEC)/1000
    
    def get_current_frame(self):
        
        if self.video_type == "file":
            return self.get_current_frame_file()
        return self.get_current_frame_rtsp()

    def get_current_frame_rtsp(self):        
        self.frame_index += 1
        return self.frame_index

    def get_current_frame_file(self):
        # File only
        return int(self.vcap.get(cv2.CAP_PROP_POS_FRAMES))
    
    def set_current_frame(self, frame_index):
        # File only
        return self.vcap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)

    def close(self):
        self.release()
        cv2.destroyAllWindows()

    def release(self):
        self.vcap.release()


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


