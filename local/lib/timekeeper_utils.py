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
        self._current_dt_year = None
        self._frame_index = None
    
    # .................................................................................................................
    
    def get_video_timing(self, video_ms_elapsed, video_frame_index):
        
        '''
        Inputs:
            video_seconds_elapsed - Amount of playback time into the video
            video_frame_index - Frame index reported by the video
        
        Returns:
            current_frame_index, current_epoch_ms, current_datetime
            
        Note: 
            current_datetime is relative to the video file (using the video time and current date)
        '''
        
        # Convert the elapsed video time into a time delta, so we can contruct a 'fake' datetime
        video_timedelta = dt.timedelta(milliseconds = video_ms_elapsed)
        video_tzinfo = get_utc_tzinfo()

        # Create file-based timing info
        current_datetime = (self._start_date_dt_local + video_timedelta).replace(tzinfo = video_tzinfo)
        current_epoch_ms = datetime_to_epoch_ms_utc(current_datetime)
        
        # Don't do anything to the video frame index... (for now?)
        current_frame_index = video_frame_index
        
        return current_frame_index, current_epoch_ms, current_datetime
    
    # .................................................................................................................
    
    def get_rtsp_time(self):
        
        '''
        Returns:
            current_frame_index, current_epoch_ms, current_datetime_utc
            
        Note: 
            current_frame_index resets every day (based on datetime)
        '''
        
        # Create rtsp-based timing info
        current_datetime = get_local_datetime()
        current_epoch_ms = datetime_to_epoch_ms_utc(current_datetime)
        current_frame_index = self.update_frame_index(current_datetime)
        
        return current_frame_index, current_epoch_ms, current_datetime
    
    # .................................................................................................................
    
    def get_frame_index(self):
        ''' Function which returns the timekeeper's current frame index counter '''
        return self._frame_index
    
    # .................................................................................................................
    
    def update_frame_index(self, current_datetime):
        
        ''' 
        Function which both updates the current frame index counter and returns the updated value.
        Note that this is intended for RTSP video streams, where a frame index isn't readily available.
        Also note that the frame index resets at the end of every year!
        '''
        
        # Reset the frame count every year
        current_year = current_datetime.year
        if current_year != self._current_dt_year:
            self._current_dt_year = current_year
            self._frame_index = 0
            
        # Increment the frame counter every time we call this
        current_frame_index = self._frame_index
        self._frame_index += 1
        
        return current_frame_index

    # .................................................................................................................
    # .................................................................................................................
    
# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

# .....................................................................................................................
    
def get_utc_datetime():
    return dt.datetime.utcnow().replace(tzinfo = get_utc_tzinfo())
    
# .....................................................................................................................
    
def get_local_datetime():
    return dt.datetime.now(tz = get_local_tzinfo())

# .....................................................................................................................

def get_isoformat_string(input_datetime):
    
    '''
    Converts a datetime object into an isoformat string, without micro seconds
    Example:
        "2019-01-30T11:22:33+00:00.000"
        
    Note: This function assumes the datetime object has timezone information (tzinfo)
    '''
    
    return input_datetime.isoformat("T", "milliseconds")

# .....................................................................................................................

def get_human_readable_timestamp(input_datetime = None):
    
    '''
    Converts a datetime object into a human readable string
    Example:
        "2019/01/30 06:22:33pm"
        
    Note: This function assumes the datetime object has timezone information (tzinfo)
    '''
    
    # Use the local date time if nothing is provided
    if input_datetime is None:
        input_datetime = get_local_datetime()
    
    in_utc_timezone = (input_datetime.tzinfo == get_utc_tzinfo())
    tzinfo_str = "UTC" if in_utc_timezone else "Local"
    human_readable_str = input_datetime.strftime("%Y/%m/%d %I:%M:%S%P ({})".format(tzinfo_str))
        
    return human_readable_str

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

def parse_isoformat_string(isoformat_datetime_str):
    
    '''
    Function for parsing isoformat strings
    Example string:
        "2019-05-11T17:22:33+00:00.999"
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

def datetime_to_epoch_ms_utc(input_datetime):
    
    ''' 
    Function which converts a datetime to the number of milliseconds since the 'epoch' (~ Jan 1970) 
    Note that the result is always in utc format!
    '''
    
    return int(round(1000 * input_datetime.timestamp()))

# .....................................................................................................................

def epoch_ms_to_utc_datetime(epoch_ms):
    
    ''' 
    Function which converts an millisecond epoch value back into a utc datetime.
    Assumes epoch_ms value was generated from a utc datetime originally!
    '''
    
    epoch_sec = epoch_ms / 1000.0    
    return dt.datetime.utcfromtimestamp(epoch_sec).replace(tzinfo = dt.timezone.utc)

# .....................................................................................................................
    
def isoformat_to_epoch_ms(datetime_isoformat_string):
    
    ''' 
    Helper function which first converts an isoformat datetime string into a python datetime object
    then converts the datetime object into an epoch_ms value
    '''
    
    return datetime_to_epoch_ms_utc(parse_isoformat_string(datetime_isoformat_string))

# .....................................................................................................................
# .....................................................................................................................
    
# ---------------------------------------------------------------------------------------------------------------------
#%% Demo

if __name__ == "__main__":
    
    tt = get_local_datetime()
    print(get_human_readable_timestamp(tt))
    
    qq = get_utc_datetime()
    print(get_human_readable_timestamp(qq))


# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap



