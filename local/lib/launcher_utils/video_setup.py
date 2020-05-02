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

import threading
import queue
import cv2

from time import sleep, perf_counter

from local.lib.file_access_utils.video import video_info_from_name, load_rtsp_config, check_valid_rtsp_ip
from local.lib.common.timekeeper_utils import Timekeeper, get_human_readable_timestamp

# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes

class Base_Video_Reader:
    
    # .................................................................................................................
    
    def __init__(self, video_source, video_type, 
                 start_datetime_isoformat = None, timelapse_factor = None):
        
        # Store video access info
        self.video_source = video_source
        self.video_type = video_type
        self.vcap = None
        self._start_videocapture()

        # Create object for keeping track of time
        self.timekeeper = Timekeeper(start_datetime_isoformat, timelapse_factor)

        # Get video info
        self.video_fps = self.get(cv2.CAP_PROP_FPS)
        self.video_width = int(self.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.video_height = int(self.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.video_wh = (self.video_width, self.video_height)
        self.total_frames = int(self.get(cv2.CAP_PROP_FRAME_COUNT))
    
    # .................................................................................................................
    
    def __repr__(self):
        return "Video source: {} ({}x{} @ {:.1f}Hz)".format(self.video_source, *self.video_wh, self.video_fps)
    
    # .................................................................................................................
    
    def read(self):

        # Get frames (with timing)
        t1 = perf_counter()
        (rec_frame, frame) = self.vcap.read()
        req_break = not rec_frame
        t2 = perf_counter()
        
        # Get time information for the current frame data
        curent_frame_index, current_epoch_ms, current_datetime = self._get_time()
        
        # Calculate video capture timing
        read_time_sec = (t2 - t1)
        
        return req_break, frame, read_time_sec, curent_frame_index, current_epoch_ms, current_datetime
    
    # .................................................................................................................
    
    def set(self, property_code, new_value):
        return self.vcap.set(property_code, new_value)
    
    # .................................................................................................................
    
    def get(self, property_code):
        return self.vcap.get(property_code)
    
    # .................................................................................................................
    
    def close(self):
        
        self.release()
        
        try:
            cv2.destroyAllWindows()
        except Exception:
            pass
    
    # .................................................................................................................
    
    def release(self):
        
        # Provide some feedback while closing the video capture
        print("Closing video capture...", end = " ")       
        self.vcap.release()   
        print("Done!")
    
    # .................................................................................................................
    
    def reset_videocapture(self, delay_sec = 0):
        self.vcap.release()
        sleep(delay_sec)
        self._start_videocapture()
    
    # .................................................................................................................
    
    def get_current_frame(self):
        raise NotImplementedError("Must inherit & implement a frame index retrival function!")
        
    # .................................................................................................................
    
    def set_current_frame(self, frame_index):
        raise NotImplementedError("Must inherit & implement a frame index setting function!")
    
    # .................................................................................................................
    
    def _get_time(self):
        # Must return the current frame index, the current epoch_ms value and the current datetime
        raise NotImplementedError("Must inherit & implement a time retrival function!")
        
    # .................................................................................................................
    
    def _start_videocapture(self):
        self.vcap = safe_VideoCapture(self.video_source)
    
    # .................................................................................................................
    # .................................................................................................................


# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////


class Threaded_File_Video_Reader(Base_Video_Reader):
    
    # .................................................................................................................
    
    def __init__(self, cameras_folder, camera_select, video_select):
        
        # Get pathing to the selected video & other timing information
        video_source, start_datetime_isoformat, timelapse_factor = video_info_from_name(cameras_folder, 
                                                                                        camera_select, 
                                                                                        video_select)
        
        # Set up storage for threading resources
        self._thread_lock = threading.Lock()
        self._frame_queue = queue.Queue(64)
        self._thread_on = None
        self._thread_ref = None
        
        # Inherit from parent
        super().__init__(video_source, 
                         video_type = "file",
                         start_datetime_isoformat = start_datetime_isoformat,
                         timelapse_factor = timelapse_factor)

    # .................................................................................................................
    
    def _threaded_read(self):
        
        while self._thread_on:
            
            # Lock access to video capture while we read frames & update timing
            self._thread_lock.acquire()
            
            # Get frames
            t1 = perf_counter()
            (rec_frame, frame) = self.vcap.read()
            req_break = not rec_frame
            t2 = perf_counter()
            
            # Loop the video, if we get to the end
            if req_break:
                self.vcap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            
            # Get time information for the current frame data
            curent_frame_index, current_epoch_ms, current_datetime = self._get_time()
            
            # Calculate video capture timing
            read_time_sec = (t2 - t1)
            
            # Release access to video capture
            self._thread_lock.release()
            
            # Repeatedly try to fill queue. This is needed to allow for exiting in case of a full queue!
            q_data = (req_break, frame, read_time_sec, curent_frame_index, current_epoch_ms, current_datetime)
            fill_queue = True
            while fill_queue:
                try:
                    self._frame_queue.put(q_data, block = True, timeout = 0.5)
                    fill_queue = False
                except queue.Full:
                    if not self._thread_on:
                        break
            
        # Some debugging info. Need to remove eventually
        #thread_on_str = "" if self._thread_on else " (via thread_on -> off)"
        #print("" ,"DEBUG: Ending threaded read queue{}".format(thread_on_str), "", sep = "\n")
        
        return
    
    # .................................................................................................................
    
    def read(self):
        
        # Keep trying to pull frames out of the (threaded) frame queue
        read_frames = True
        try:
            while read_frames:
                req_break, frame, read_time_sec, curent_frame_index, current_epoch_ms, current_datetime = \
                self._frame_queue.get(block = True, timeout = 0.5)
                read_frames = False
        except queue.Empty:
            pass
        
        return req_break, frame, read_time_sec, curent_frame_index, current_epoch_ms, current_datetime
    
    # .................................................................................................................
    
    def _get_time(self):
        
        try:
            # Get the current time into the video file, since we'll use this as time elapsed/time of day
            video_time_ms = self.vcap.get(cv2.CAP_PROP_POS_MSEC)
            video_frame_index = int(self.vcap.get(cv2.CAP_PROP_POS_FRAMES))
            
        except Exception:
            # Handle case where we may have a break request, so that video timing checks don't work
            video_time_ms = 0.0
            video_frame_index = -1
        
        # Figure out shared timing parameters
        current_frame_index, current_epoch_ms, current_datetime = self.timekeeper.get_file_timing(video_time_ms, 
                                                                                                  video_frame_index)

        return current_frame_index, current_epoch_ms, current_datetime
    
    # .................................................................................................................
    
    def release(self):
        
        # Provide some feedback while closing the video capture
        print("Closing threaded video capture...", end = " ")    
        self._close_threaded_capture()      
        print("Done!")
        
    # .................................................................................................................
    
    def reset_videocapture(self, delay_sec = 0):
        
        # Shutdown the existing reading thread and clear any queue data
        self._close_threaded_capture()
        self._clear_frame_queue()
        
        # Delay if needed
        sleep(delay_sec)
        
        # Re-launch the threaded reader!
        self._start_videocapture()
    
    # .................................................................................................................

    def _start_videocapture(self):
        
        # Create initial capture object
        self.vcap = safe_VideoCapture(self.video_source)
        
        # Storage for threading resources
        self._thread_on = True
        self._thread_ref = threading.Thread(target = self._threaded_read, daemon = True)
        self._thread_ref.start()
        
    # .................................................................................................................
    
    def _close_threaded_capture(self):
        
        ''' Helper function for 'safely' shutdown the threaded frame reading functionality '''
        
        # Send the 'off' signal to the threaded capture
        self._thread_on = False
        self._thread_ref.join()
        
        # Now that the thread is joined, we can shutdown the video capture safely
        self.vcap.release()
    
    # .................................................................................................................
    
    def _clear_frame_queue(self):
        
        ''' Helper function for getting rid of any frames currently in the frame queue '''
        
        with self._frame_queue.mutex:
            self._frame_queue.queue.clear()
        
    # .................................................................................................................
    # .................................................................................................................

# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////


class File_Video_Reader(Base_Video_Reader):
    
    # .................................................................................................................
    
    def __init__(self, cameras_folder, camera_select, video_select):
        
        # Get pathing to the selected video & other timing information
        video_source, start_datetime_isoformat, timelapse_factor = video_info_from_name(cameras_folder, 
                                                                                        camera_select, 
                                                                                        video_select)
        
        # Inherit from parent
        super().__init__(video_source, 
                         video_type = "file",
                         start_datetime_isoformat = start_datetime_isoformat,
                         timelapse_factor = timelapse_factor)
        
    # .................................................................................................................
    
    def _get_time(self):
        
        try:
            # Get the current time into the video file, since we'll use this as time elapsed/time of day
            video_time_ms = self.vcap.get(cv2.CAP_PROP_POS_MSEC)
            video_frame_index = self.get_current_frame()
            
        except Exception:
            # Handle case where we may have a break request, so that video timing checks don't work
            video_time_ms = 0.0
            video_frame_index = -1
        
        # Figure out shared timing parameters
        current_frame_index, current_epoch_ms, current_datetime = self.timekeeper.get_file_timing(video_time_ms, 
                                                                                                  video_frame_index)

        return current_frame_index, current_epoch_ms, current_datetime
    
    # .................................................................................................................
    
    def get_current_frame(self):
        return int(self.vcap.get(cv2.CAP_PROP_POS_FRAMES))
    
    # .................................................................................................................
    
    def set_current_frame(self, frame_index):
        return self.vcap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
    
    # .................................................................................................................
    # .................................................................................................................


# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////


class RTSP_Video_Reader(Base_Video_Reader):
    
    # .................................................................................................................
    
    def __init__(self, cameras_folder, camera_select):
        
        # Get pathing to the selected video
        rtsp_config_dict, rtsp_string = load_rtsp_config(cameras_folder, camera_select)
        
        # Catch bad rtsp configurations before launching
        is_valid_rtsp_ip = check_valid_rtsp_ip(cameras_folder, camera_select)
        if not is_valid_rtsp_ip:
            print("",
                  "Use the RTSP editor utility to specify camera configuration!",
                  "",
                  sep = "\n")
            raise AttributeError("Bad rtsp configuration! ({})".format(camera_select))
        
        # Store loaded settings
        self.rtsp_config_dict = rtsp_config_dict
        self.rtsp_string = rtsp_string
        
        # Inherit from parent
        super().__init__(rtsp_string, video_type = "rtsp")
        
    # .................................................................................................................
    
    def read(self):

        # Get frames
        t1 = t2 = 0.0
        req_break = True
        rec_frame = False
        while req_break:
            try:
                t1 = perf_counter()
                (rec_frame, frame) = self.vcap.read()
                t2 = perf_counter()
            except Exception as err:
                print("Error reading video capture...")
                print(err)
            
            # Assume we've disconnected if we don't receive a frame and try to reconnect
            req_break = (not rec_frame)
            if req_break:
                self._reconnect()
        
        # Get time information for the current frame data
        curent_frame_index, current_epoch_ms, current_datetime = self._get_time()
        
        # Calculate video capture timing
        read_time_sec = (t2 - t1)
        
        return req_break, frame, read_time_sec, curent_frame_index, current_epoch_ms, current_datetime
    
    # .................................................................................................................
    
    def get_current_frame(self):
        return self.timekeeper.get_frame_index()
    
    # .................................................................................................................
    
    def set_current_frame(self, frame_index):
        
        print("", 
              "WARNING",
              "  Trying to set the video frame index ({})".format(frame_index),
              "  But this isn't possible on RTSP video streams!",
              "", sep = "\n")
        
        return None
    
    # .................................................................................................................
    
    def _reconnect(self):
        
        # Provide some feedback
        print("", "Lost connection to RTSP stream!", sep = "\n")
        
        # Keep trying to reconnect and read frames from the video source
        rec_frame = False
        while (not rec_frame):
            
            # First, forcefully reset the connection
            print("  Trying to reconnect... {}".format(get_human_readable_timestamp()))
            self.reset_videocapture(delay_sec = 10)
        
            # Now that the capture is connected, try to get frames
            try:
                (rec_frame, frame) = self.vcap.read()
            except Exception as err:
                print("Error reconnecting... {}".format(get_human_readable_timestamp()))
                print(err)
        
        # Some feedback once we're successful
        print("  --> Reconnected! ({})".format(get_human_readable_timestamp()))
        
        return
    
    # .................................................................................................................
    
    def _get_time(self):
        
        # Get the current time info
        current_frame_index, current_epoch_ms, current_datetime = self.timekeeper.get_rtsp_time()
        
        return current_frame_index, current_epoch_ms, current_datetime
    
    # .................................................................................................................
    # .................................................................................................................


# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////

# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

# .....................................................................................................................

def create_video_reader(cameras_folder, camera_select, video_select):
    
    ''' Helper function for initializing the correct video reader object '''
    
    video_is_rtsp = (video_select.lower().strip() == "rtsp")
    if video_is_rtsp:        
        return RTSP_Video_Reader(cameras_folder, camera_select, video_select)
    
    return File_Video_Reader(cameras_folder, camera_select, video_select)

# .....................................................................................................................

def safe_VideoCapture(video_source):
    
    ''' Helper function which adds very basic error handling to cv2.VideoCapture functionality '''
    
    vcap = cv2.VideoCapture(video_source)
    if not vcap.isOpened():
        raise SystemExit("\nCouldn't open video:\n{}\n".format(video_source))
    
    return vcap

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Demo

if __name__ == "__main__":
    pass

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap


