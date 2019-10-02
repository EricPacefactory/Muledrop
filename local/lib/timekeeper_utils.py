#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Sep  9 11:03:14 2019

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

import time
import datetime as dt



# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes

class Timekeeper:
    
    _start_time_sec = time.perf_counter()
    
    # .................................................................................................................
    
    def __init__(self):
        
        # Get local start datetimes
        self._start_dt_local = get_local_datetime()
        self._start_date_dt_local = dt.datetime(year = self._start_dt_local.year, 
                                                month = self._start_dt_local.month, 
                                                day = self._start_dt_local.day)
        
        # Get UTC start datetimes
        self._start_dt_utc = get_utc_datetime()
        self._start_date_dt_utc = dt.datetime(year = self._start_dt_utc.year, 
                                              month = self._start_dt_utc.month, 
                                              day = self._start_dt_utc.day)
        
        # Set up frame counting, which rolls over every day
        self._current_day_utc = None
        self._frame_index = None
    
    # .................................................................................................................
    
    def get_video_timing(self, video_seconds_elapsed, video_frame_index):
        
        '''
        Inputs:
            video_seconds_elapsed - Amount of playback time into the video
            video_frame_index - Frame index reported by the video
        
        Returns:
            current_frame_index, current_time_sec, current_datetime
            
        Note: 
            current_datetime is relative to the video file (using the video time and current date)
        '''
        
        # Convert the elapsed video time into a time delta, so we can contruct a 'fake' datetime
        video_timedelta = dt.timedelta(seconds = video_seconds_elapsed)
        video_tzinfo = dt.timezone(dt.timedelta(0))

        # Create file-based timing info
        current_time_sec = video_seconds_elapsed
        current_datetime = (self._start_date_dt_local + video_timedelta).replace(tzinfo = video_tzinfo)
        
        # Don't do anything to the video frame index... (for now?)
        current_frame_index = video_frame_index
        
        return current_frame_index, current_time_sec, current_datetime
    
    # .................................................................................................................
    
    def get_rtsp_time(self):
        
        '''
        Returns:
            current_frame_index, current_time_sec, current_datetime_utc
            
        Note: 
            current_frame_index resets every (utc) day
        '''
        
        # Create rtsp-based timing info
        current_time_sec = time.perf_counter() - self._start_time_sec
        current_datetime_utc = get_utc_datetime()
        current_frame_index = self.get_frame_index(current_datetime_utc)
        
        return current_frame_index, current_time_sec, current_datetime_utc
    
    # .................................................................................................................
    
    def get_frame_index(self, current_datetime_utc):
        
        # Reset the frame count every day
        current_day = current_datetime_utc.day
        if current_day != self._current_day_utc:
            self._current_day_utc = current_day
            self._frame_index = 0
            
        # Increment the frame coutner every time we call this
        current_frame_index = self._frame_index
        self._frame_index += 1
        
        return current_frame_index

    # .................................................................................................................
    # .................................................................................................................
    
# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

# .....................................................................................................................
    
def get_utc_datetime():
    return add_utc_tzinfo(dt.datetime.utcnow())
    
# .....................................................................................................................
    
def get_local_datetime():
    return add_local_tzinfo(dt.datetime.now())

# .....................................................................................................................

def format_datetime_string(input_datetime):
    
    '''
    Converts a datetime object into an isoformat string, without milli/micro seconds
    Example:
        "2019-01-30T11:22:33+00:00"
        
    Note - This function assumes the datetime object has timezone information (tzinfo)
    If not, use add_local_tzinfo() or add_utc_tzinfo() functions to add tzinfo before calling this function.
    '''
    
    return input_datetime.isoformat("T", "seconds")

# .....................................................................................................................

def get_local_tzinfo():
    
    ''' Function which returns a local tzinfo object. Accounts for daylight savings '''
    
    # Figure out utc offset for local time, accounting for daylight savings
    is_daylight_savings = time.localtime().tm_isdst
    utc_offset_sec = time.altzone if is_daylight_savings else time.timezone
    utc_offset_delta = dt.timedelta(seconds = -utc_offset_sec)
    
    return dt.timezone(offset = utc_offset_delta)
    
# .....................................................................................................................

def get_utc_tzinfo():
    
    ''' Convenience function which returns a utc tzinfo object '''
    
    return dt.timezone.utc
    
# .....................................................................................................................

def add_tzinfo(datetime_obj, tzinfo_obj):
    
    ''' Helper function for adding timezone data (tzinfo) to datetime objects '''
    
    return datetime_obj.replace(tzinfo = tzinfo_obj)

# .....................................................................................................................

def add_local_tzinfo(datetime_obj):
    
    ''' Helper function for adding local timezone info to an ambiguous datetime object '''
    
    return datetime_obj.replace(tzinfo = get_local_tzinfo())

# .....................................................................................................................

def add_utc_tzinfo(datetime_obj):
    
    ''' Helper function for adding utc timezone info to an ambiguous datetime object '''
    
    return datetime_obj.replace(tzinfo = get_utc_tzinfo())

# .....................................................................................................................

def local_time_to_isoformat_string(local_datetime = None):
        
    # Get current local time, if needed
    if local_datetime is None:
        local_datetime = get_local_datetime()
    
    # Add in local timezone info before formatting as a string, so we get the +/- offset
    if local_datetime.tzinfo is None:
        local_datetime = add_local_tzinfo(local_datetime)
        
    return format_datetime_string(local_datetime)

# .....................................................................................................................
    
def utc_time_to_isoformat_string(utc_datetime = None):
        
    # Get the current utc time, if needed
    if utc_datetime is None:
        utc_datetime = get_utc_datetime()
        
    # Add in utc timezone info before formatting as a string, so we get the +/- offset
    if utc_datetime.tzinfo is None:
        utc_datetime = add_utc_tzinfo(utc_datetime)
    
    return format_datetime_string(utc_datetime)

# .....................................................................................................................

def parse_isoformat_string(isoformat_datetime_str):
    
    '''
    Function for parsing isoformat strings
    Example string:
        "2019-05-11T17:22:33+00:00"
    '''
    
    # Check if the end of the string contains timezone offset info
    includes_offset = isoformat_datetime_str[-6] in ("+", "-")
    offset_dt = dt.timedelta(0)
    if includes_offset:
        
        # Figure out the timezone offset amount
        offset_hrs = int(isoformat_datetime_str[-6:-3])
        offset_mins = int(isoformat_datetime_str[-2:])
        offset_mins = offset_mins if offset_hrs > 0 else -1 * offset_mins
        offset_dt = dt.timedelta(hours = offset_hrs, minutes = offset_mins)
        
        # Remove offset from string before trying to parse
        isoformat_datetime_str = isoformat_datetime_str[:-6]
    
    # Convert timezone information into a timezone object that we can add back into the returned result
    parsed_tzinfo = dt.timezone(offset = offset_dt)
    
    # Decide if we need to parse milli/micro seconds
    includes_subseconds = len(isoformat_datetime_str) > 19
    string_format = "%Y-%m-%dT%H:%M:%S.%f" if includes_subseconds else "%Y-%m-%dT%H:%M:%S"
    
    # Finally, create the output datetime, with timezone info
    parsed_dt = dt.datetime.strptime(isoformat_datetime_str[:], string_format).replace(tzinfo = parsed_tzinfo)
    
    return parsed_dt

# .....................................................................................................................
# .....................................................................................................................
    
# ---------------------------------------------------------------------------------------------------------------------
#%% Demo

if __name__ == "__main__":
    
    pass


# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap



