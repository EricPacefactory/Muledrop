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
import numpy as np

from random import random as unit_random

# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes

class Timekeeper:
    
    # .................................................................................................................
    
    def __init__(self, start_datetime_isoformat = None, timelapse_factor = None):
        
        # Set up file-specific timing variables
        self._timelapse_factor = 1 if (timelapse_factor is None) else timelapse_factor
        self._file_tzinfo = get_utc_tzinfo()
        
        # Use an arbitrary start time by default (only affects file-based reporting) 
        # --> Guarantees helps ensure file-reported data is clearly distinguished from other results
        arbitrary_start_dt = dt.datetime(2000, 1, 1)
        self._start_dt_local = arbitrary_start_dt
        
        # Modify start times if an explicit start time is given (for files only)
        provided_start_dt = (start_datetime_isoformat is not None)
        if provided_start_dt:
            self._start_dt_local = isoformat_to_datetime(start_datetime_isoformat)
            self._file_tzinfo = self._start_dt_local.tzinfo
        
        # Set up frame counting, which rolls over every day
        self._current_dt_year = None
        self._frame_index = None
    
    # .................................................................................................................
    
    def get_file_timing(self, video_ms_elapsed, video_frame_index):
        
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
        real_time_elapsed = (video_ms_elapsed * self._timelapse_factor)
        video_timedelta = dt.timedelta(milliseconds = real_time_elapsed)
        
        # Create file-based timing info
        current_datetime = (self._start_dt_local + video_timedelta).replace(tzinfo = self._file_tzinfo)
        current_epoch_ms = datetime_to_epoch_ms(current_datetime)
        
        # Don't do anything to the video frame index... (for now?)
        current_frame_index = video_frame_index
        
        return current_frame_index, current_epoch_ms, current_datetime
    
    # .................................................................................................................
    
    def get_rtsp_time(self):
        
        '''
        Returns:
            current_frame_index, current_epoch_ms, current_datetime_utc
        '''
        
        # Create rtsp-based timing info
        current_datetime = get_local_datetime()
        current_epoch_ms = datetime_to_epoch_ms(current_datetime)
        current_frame_index = self.update_frame_index(current_datetime)
        
        return current_frame_index, current_epoch_ms, current_datetime
    
    # .................................................................................................................
    
    def get_frame_index(self):
        
        ''' Returns the timekeeper's current frame index counter '''
        
        return self._frame_index
    
    # .................................................................................................................
    
    def update_frame_index(self, current_datetime):
        
        ''' 
        Function which both updates the current frame index counter and returns the updated value.
        Note that this is intended for RTSP video streams, where a frame index isn't readily available.

        Also note that the frame index is forced to reset at the end of every year! 
        For typical framerates, this should ensure that the frame index never exceeds 1 billion or so
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


# =====================================================================================================================
# =====================================================================================================================


class Periodic_Polled_Timer:
    
    '''
    Class which instantiates a polled timer which goes off based on some specified period of time
    '''
    
    # .................................................................................................................
    
    def __init__(self, trigger_on_first_check = True):
        
        ''' 
        Initialize a new timer. 
        Note that the trigger timing for this timer must still be set using the set_trigger_period(...) function!
        
        Use the check_trigger(...) function to check for timer updates
        
        Use the enable_randomness(...) or disable_randomness() functions to add a random amount to each cycle
        
        Use the get_next_trigger_time_ms() function to manually inspect the next trigger time
        '''
        
        # Store bookkeeping variables
        self._trigger_on_first_check = trigger_on_first_check
        self._trigger_period_ms = 1
        self._next_trigger_time_ms = None
        
        # Store randomness variables
        self._enable_randomness = False
        self._max_random_offset_ms = None
    
    # .................................................................................................................
    
    def __repr__(self):
        
        repr_str_list = ["Periodic Trigger Object",
                         "  Trigger on first check: {}".format(self._trigger_on_first_check),
                         "     Trigger period (ms): {}".format(self._trigger_period_ms),
                         "  Next trigger time (ms): {}".format(self.get_next_trigger_time_ms())]
        
        return "\n".join(repr_str_list)
    
    # .................................................................................................................
    
    def reset_timer(self, trigger_on_first_check = None):
        
        '''
        Function used to forcefully reset the trigger
        
        Inputs:
            trigger_on_first_check -> Boolean or None. 
                                      If None, behavior reverts to setting provided during object init
                                      Otherwise if True, trigger will go off on next trigger check
        
        Outputs:
            None!
        '''
        
        # Re-use the trigger on first check setting (from init) if we aren't explicitly provided with a new setting
        if trigger_on_first_check is None:
            trigger_on_first_check = self._trigger_on_first_check
        
        self._next_trigger_time_ms = None
    
    # .................................................................................................................
    
    def set_trigger_period(self, hours = 0, minutes = 0, seconds = 0, milliseconds = 0):
        
        ''' Function used to update the trigger period after already initializing the object '''
        
        # Sanity check
        total_millis = convert_to_milliseconds(hours, minutes, seconds, milliseconds)
        if total_millis < 1:
            raise ValueError("Can't set trigger period to be less than 1 millisecond! Got {} ms".format(total_millis))
        
        self._trigger_period_ms = total_millis
        
        return self
    
    # .................................................................................................................
    
    def enable_randomness(self, hours = 0, minutes = 0, seconds = 0, milliseconds = 0):
        
        '''
        Function used to include a random offset to the trigger timing 
        The random offset will be a positive value between zero and the total time given as input to this function.
        '''
        
        # Sanity check
        total_millis = convert_to_milliseconds(hours, minutes, seconds, milliseconds)
        if total_millis < 1:
            raise ValueError("Can't set random period to be less than 1 millisecond! Got {} ms".format(total_millis))
            
        # If we get here, we can safely enable randomness
        self._enable_randomness = True
        self._max_random_offset_ms = total_millis
        
        return self
    
    # .................................................................................................................
    
    def disable_randomness(self):
        
        ''' Function to turn off any existing randomness settings (i.e. reset to default deterministic behavior)'''
        
        self._enable_randomness = False
    
    # .................................................................................................................
    
    def get_next_trigger_time_ms(self):        
        return self._next_trigger_time_ms
    
    # .................................................................................................................
    
    def check_trigger(self, current_epoch_ms):
        
        '''
        Function used to check if the periodic trigger has gone off (given a current epoch_ms timing)
        Handles initial call scenario, where a 'next trigger time' may not have been set yet
        Behaviour depends on 'trigger_on_first_check' setting when initializing the object!
        
        Inputs:
            current_epoch_ms --> (Integer) The current time as an epoch value in milliseconds
        
        Outputs:
            new_trigger --> (Boolean) Returns true based on a periodic timer, otherwise false
        '''
        
        # Wrap in try/except, since first evaluation will fail
        try:
            new_trigger = (current_epoch_ms > self._next_trigger_time_ms)
            
        except TypeError:
            # Exception thrown on first eval, since we don't have a _next_trigger_time_ms to evaluate
            if self._trigger_on_first_check:
                new_trigger = True
            else:
                new_trigger = False
                self._update_next_trigger_time_ms(current_epoch_ms)
        
        # If the trigger goes off, we'll need to update our next trigger time to avoid repeat triggers!
        if new_trigger:
            self._update_next_trigger_time_ms(current_epoch_ms)
        
        return new_trigger
    
    # .................................................................................................................

    def _update_next_trigger_time_ms(self, current_epoch_ms):
    
        '''
        Function which calculates a new value for the next trigger time.
        Handles initial call scenario, where a 'previous' trigger time may not exist
        '''
        
        # When this function is called, we can assume the existing 'next trigger time' is in the past
        previous_trigger_time_ms = self._next_trigger_time_ms
        
        # Figure out what the trigger period should be, with randomness if needed
        trigger_period_ms = self._trigger_period_ms
        if self._enable_randomness:
            random_offset_ms = int(round(self._max_random_offset_ms * unit_random()))
            trigger_period_ms += random_offset_ms
            
        try:
            # Update next time using previous time instead of current epoch timing, to avoid drifting errors
            new_next_trigger_time_ms = previous_trigger_time_ms + trigger_period_ms
            
        except TypeError:        
            # May get an error if the previous trigger time doesn't exist yet (i.e. on first-run)
            new_next_trigger_time_ms = current_epoch_ms + trigger_period_ms
        
        # Check that the newly calculated time isn't already in the past
        # (may happen if the camera disconnects or hangs for a while)
        if new_next_trigger_time_ms < current_epoch_ms:
            new_next_trigger_time_ms = current_epoch_ms + trigger_period_ms
        
        self._next_trigger_time_ms = new_next_trigger_time_ms
    
    # .................................................................................................................
    # .................................................................................................................


# =====================================================================================================================
# =====================================================================================================================


class Periodic_Polled_Integer_Counter:
    
    '''
    Class which instantiates a polled counter which repeatedly goes off after a set number of counts
    '''
    
    # .................................................................................................................
    
    def __init__(self, reset_after_n_counts = 5, reset_on_first_check = True):
        
        # Allocate storage for bookkeeping variables
        self._counter = None
        self._reset_after_n_counts = None
        self._reset_on_first_check = reset_on_first_check
        
        # Set the initial count reset value, so we can make consistent use of setting logic
        self.set_count_reset_value(reset_after_n_counts)
    
    # .................................................................................................................
    
    def __repr__(self):
        
        repr_str_list = ["Periodic Interger Counter",
                         "  Reset on first check: {}".format(self._reset_on_first_check),
                         "         Current count: {}".format(self.get_current_count())]
        
        return "\n".join(repr_str_list)
    
    # .................................................................................................................
    
    def reset_counter(self, reset_on_first_check = None):
        
        '''
        Function used to forcefully reset the counter
        
        Inputs:
            trigger_on_first_check -> Boolean or None. 
                                      If None, behavior reverts to setting provided during object init
                                      Otherwise if True, trigger will go off on next update_count check
        
        Outputs:
            None!
        '''
        
        # Re-use the trigger on first check setting (from init) if we aren't explicitly provided with a new setting
        if reset_on_first_check is None:
            reset_on_first_check = self._reset_on_first_check
        
        self._counter = None
    
    # .................................................................................................................
    
    def set_count_reset_value(self, new_reset_value):
        
        '''
        Function used to update the reset count after already initializing the object
        Note that this value will be the number of counts between reset events
        For example, using a value of 3 and triggering on the first check would give the following sequence:
            0 (Trigger), 1, 2, 3
            4 (Trigger), 5, 6, 7
            8 (Trigger), 9, 10, 11
            12 (Trigger), ...
        
        As a result of this behavior, a value of 0 or 1 will cause the trigger to go off on every update!
        A value of 2 will cause an update every-other count etc...
        '''
        
        # Sanity check
        if new_reset_value < 0:
            raise ValueError("Can't have negative count reset values!")
        
        self._reset_after_n_counts = new_reset_value
    
    # .................................................................................................................
    
    def get_current_count(self):
        return self._counter
    
    # .................................................................................................................
    
    def update_count(self):
        
        '''
        Function used to increment the counter and check if the trigger has gone off
        Handles initial call scenario, where a 'next trigger' may not have been set yet
        Behaviour depends on 'reset_on_first_check' setting when initializing the object!
        
        Outputs:
            count_reset --> (Boolean) Returns true based on reaching a periodic count, otherwise false
        '''
        
        # Wrap in try/except, since first evaluation will fail
        try:            
            self._counter += 1
            count_reset = (self._counter >= self._reset_after_n_counts)
            
        except TypeError:
            # Exception thrown on first eval, since we don't have a counter value to evaluate
            if self._reset_on_first_check:
                count_reset = True
            else:
                count_reset = False
                self._counter = 1
        
        # Reset everytime we reach the count trigger
        if count_reset:
            self._counter = 0
        
        return count_reset
    
    # .................................................................................................................
    # .................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

# .....................................................................................................................
    
def get_utc_datetime():

    ''' Returns a datetime object based on UTC time, with timezone information included '''

    return dt.datetime.utcnow().replace(tzinfo = get_utc_tzinfo())
    
# .....................................................................................................................
    
def get_local_datetime():

    ''' Returns a datetime object based on the local time, with timezone information included '''

    return dt.datetime.now(tz = get_local_tzinfo())

# .....................................................................................................................

def get_utc_epoch_ms():
    
    return datetime_to_epoch_ms(get_utc_datetime())

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
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% String conversion functions

# .....................................................................................................................

def get_human_readable_timestamp(input_datetime = None):
    
    '''
    Converts a datetime object into a human readable string
    Example:
        "2019/01/30 11:22:33AM"
        
    Notes:
        - This function assumes the datetime object has timezone information (tzinfo)
        - If an input datetime isn't provided, the local datetime will be used
    
    '''
    
    # Use the local datetime if nothing is provided
    if input_datetime is None:
        input_datetime = get_local_datetime()
    
    # Format timestamp in a more human readable way, without leaving out info
    human_readable_str = input_datetime.strftime("%Y/%m/%d %I:%M:%S%p (%Z)")
    # --> Note: '%P' (which writes am/pm) is not supported on Windows! Must use '%p" (which writes AM/PM)
        
    return human_readable_str

# .....................................................................................................................

def get_human_readable_timezone():
    
    ''' Convenience function for printing timezones by name instead of time offset. Ex: -05:00 -> EST '''
    
    return time.strftime("%Z")

# .....................................................................................................................

def get_filesafe_date(input_datetime = None):
    
    '''
    Converts a datetime object into a file system & human friendly date string
    Example:
        "2019-01-30"
    Note: If an input datetime isn't provided, the local datetime will be used
    '''
    
    # Use the local datetime if nothing is provided
    if input_datetime is None:
        input_datetime = get_local_datetime()
    
    # Format date in a way that is safe on all file systems (i.e. don't use / character!)
    file_safe_date_str = input_datetime.strftime("%Y-%m-%d")
    
    return file_safe_date_str

# .....................................................................................................................

def get_filesafe_time(input_datetime = None):
    
    '''
    Converts a datetime object into a file system & human friendly time string
    Example:
        "15h35m57s" (from 15:35:57)
    Note: If an input datetime isn't provided, the local datetime will be used
    '''
    
    # Use the local datetime if nothing is provided
    if input_datetime is None:
        input_datetime = get_local_datetime()
    
    # Format date in a way that is safe on all file systems (i.e. don't use : character!)
    file_safe_time_str = input_datetime.strftime("%Hh%Mm%Ss")
    
    return file_safe_time_str

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Isoformat conversion functions

# .....................................................................................................................

def isoformat_to_datetime(isoformat_datetime_str):
    
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

def isoformat_to_epoch_ms(datetime_isoformat_string):
    
    '''
    Helper function which first converts an isoformat datetime string into a python datetime object
    then converts the datetime object into an epoch_ms value
    '''
    
    return datetime_to_epoch_ms(isoformat_to_datetime(datetime_isoformat_string))

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Datetime conversion functions

# .....................................................................................................................

def datetime_to_isoformat_string(input_datetime):
    
    '''
    Converts a datetime object into an isoformat string
    Example:
        "2019-01-30T11:22:33+00:00.000000"
        
    Note: This function assumes the datetime object has timezone information (tzinfo)
    '''
    
    return input_datetime.isoformat()

# .....................................................................................................................

def datetime_to_epoch_ms(input_datetime):
    
    ''' Function which converts a datetime to the number of milliseconds since the 'epoch' (~ Jan 1970) '''
    
    return int(round(1000 * input_datetime.timestamp()))

# .....................................................................................................................

def local_datetime_to_utc_datetime(local_datetime):
    
    ''' Convenience function for converting datetime objects from local timezones to utc '''
    
    return (local_datetime - local_datetime.utcoffset()).replace(tzinfo = get_utc_tzinfo())

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Epoch conversion functions

# .....................................................................................................................

def epoch_ms_to_utc_datetime(epoch_ms):
    
    ''' Function which converts a millisecond epoch value into a utc datetime object '''
    
    epoch_sec = epoch_ms / 1000.0
    return dt.datetime.utcfromtimestamp(epoch_sec).replace(tzinfo = get_utc_tzinfo())

# .....................................................................................................................

def epoch_ms_to_local_datetime(epoch_ms):
    
    ''' Function which converts a millisecond epoch value into a datetime object with the local timezone '''
    
    epoch_sec = epoch_ms / 1000.0
    return dt.datetime.fromtimestamp(epoch_sec).replace(tzinfo = get_local_tzinfo())

# .....................................................................................................................

def epoch_ms_to_utc_isoformat(epoch_ms):
    
    '''
    Helper function which first converts an epoch_ms value into a python datetime object
    then converts the datetime object into an isoformat string
    The result will use a UTC timezone
    '''
    
    return datetime_to_isoformat_string(epoch_ms_to_utc_datetime(epoch_ms))

# .....................................................................................................................

def epoch_ms_to_local_isoformat(epoch_ms):
    
    '''
    Helper function which first converts an epoch_ms value into a python datetime object
    then converts the datetime object into an isoformat string
    The result will use the local timezone
    '''
    
    return datetime_to_isoformat_string(epoch_ms_to_local_datetime(epoch_ms))

# .................................................................................................................

def any_time_type_to_epoch_ms(time_value):
    
    # Decide how to handle the input time value based on it's type
    value_type = type(time_value)
    
    # If an integer is provided, assume it is already an epoch_ms value
    if value_type in {int, np.int64}:
        return time_value
    
    # If a float is provided, assume it is an epoch_ms value, so return integer version
    elif value_type is float:
        return int(round(time_value))
    
    # If a datetime vlaue is provided, use timekeeper library to convert
    elif value_type is dt.datetime:
        return datetime_to_epoch_ms(time_value)
    
    # If a string is provided, assume it is an isoformat datetime string
    elif value_type is str:
        return isoformat_to_epoch_ms(time_value)
    
    # If we get here, we couldn't parse the time!
    raise TypeError("Unable to parse input time value: {}, type: {}".format(time_value, value_type))

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Misc functions

# .....................................................................................................................

def convert_to_milliseconds(hours = 0, minutes = 0, seconds = 0, milliseconds = 0):
    
    ''' Function used to convert time amounts given in hours/minutes/seconds/milliseconds to just milliseconds '''
    
    # Convert units down to milliseconds
    hours_as_minutes = (hours * 60.0)
    minutes_as_seconds = ((minutes + hours_as_minutes) * 60.0)
    seconds_as_millis = ((seconds + minutes_as_seconds) * 1000.0)
    total_millis = int(round(milliseconds + seconds_as_millis))
    
    return total_millis

# .....................................................................................................................

def fake_datetime_like(reference_datetime,
                       fake_year = None, fake_month = None, fake_day = None,
                       fake_hour = 0, fake_minute = 0, fake_second = 0, fake_tzinfo = None):
    
    ''' 
    Creates a 'fake' datetime, based on an input datetime. 
    Inputs that are set to None will copy from the input datetime
    Likely used to generate 'zeroed' time components from an existing datetime (i.e. start of day datetime)
    '''
    
    set_from_ref = lambda ref_value, fake_value: ref_value if fake_value is None else fake_value
    return dt.datetime(set_from_ref(reference_datetime.year, fake_year),
                       set_from_ref(reference_datetime.month, fake_month),
                       set_from_ref(reference_datetime.day, fake_day),
                       set_from_ref(reference_datetime.hour, fake_hour),
                       set_from_ref(reference_datetime.minute, fake_minute),
                       set_from_ref(reference_datetime.second, fake_second),
                       tzinfo = set_from_ref(reference_datetime.tzinfo, fake_tzinfo))

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Demo

if __name__ == "__main__":
    
    ll = get_local_datetime()
    print("Local datetime:", get_human_readable_timestamp(ll))
    
    uu = get_utc_datetime()
    print("UTC Datetime:", get_human_readable_timestamp(uu))
    
    # Example counter behaviour
    print("", "Counter example:", sep = "\n")
    example_counter = Periodic_Polled_Integer_Counter(reset_after_n_counts = 2, reset_on_first_check = True)
    for k in range(15):
        trigger_event = example_counter.update_count()
        print(k, trigger_event)


# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap



