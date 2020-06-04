#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Sep 16 15:45:29 2019

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

import queue
import threading

from time import sleep

from local.lib.file_access_utils.metadata_read_write import encode_json_data, write_encoded_json
from local.lib.file_access_utils.metadata_read_write import encode_jsongz_data, write_encoded_jsongz
from local.lib.file_access_utils.image_read_write import encode_jpg_data, encode_png_data
from local.lib.file_access_utils.image_read_write import write_encoded_jpg, write_encoded_png


# ---------------------------------------------------------------------------------------------------------------------
#%% Background Resource savers

class Threaded_PNG_Saver:
    
    # .................................................................................................................
    
    def __init__(self, *, thread_name, png_folder_path):
        
        # Store inputs
        self.thread_name = thread_name
        self.png_folder_path = png_folder_path
        
        # For clarity
        max_queue_size = 250
        auto_kill_when_main_thread_closes = True
        
        # Set up threading resources
        self._data_queue = queue.Queue(max_queue_size)
        self._run_thread_event = threading.Event()
        thread_args = (png_folder_path, self._data_queue, self._run_thread_event)
        
        # Start saving thread
        self._thread_ref = threading.Thread(name = thread_name,
                                            target = self._wait_for_data_to_save,
                                            args = thread_args,
                                            daemon = auto_kill_when_main_thread_closes)
        
        # Start the thread
        self._run_thread_event.set()
        self._thread_ref.start()
    
    # .................................................................................................................
    
    def save_data(self, file_save_name_no_ext, image_data, png_compression_0_to_9 = 0):
        
        '''
        Function which handles 'saving' of data (at least from the callers perspective)
        Actually bundles data and passes it to the savng thread to handle actual file i/o
        '''
        
        # Encode data for saving
        encoded_png_data = encode_png_data(image_data, png_compression_0_to_9)
        
        # Bundle everything needed for saving
        bundled_data = (file_save_name_no_ext, encoded_png_data)
        
        # Now place bundled data in the queue for the thread to deal with
        # Note: we aren't actually saving (depsite the function name), we're just passing data to the thread to save!
        self._data_queue.put(bundled_data, block = True, timeout = None)
        
        return
    
    # .................................................................................................................
    
    def _wait_for_data_to_save(self, image_save_folder_path, data_queue_ref, run_thread_event_ref):
        
        # Loop until something stops us
        while True:
            
            # Save all data from the queue when it's available
            while not data_queue_ref.empty():
                
                # Get data from queue
                file_save_name_no_ext, encoded_png_data = data_queue_ref.get()
                
                # Save image data
                write_encoded_png(image_save_folder_path, file_save_name_no_ext, encoded_png_data)
            
            # Check if we need to stop
            got_shutdown_signal = (not run_thread_event_ref.is_set())
            if got_shutdown_signal and data_queue_ref.empty():
                break
            
            # Wait a bit so we aren't completely hammering this thread
            sleep(0.5)
        
        return
    
    # .................................................................................................................
    
    def close(self):
        
        # Clear event to trigger thread to close
        self._run_thread_event.clear()
        
        # Now wait for thread to close (may take a moment if still saving data)
        self._thread_ref.join(10.0)
        
        return
    
    # .................................................................................................................
    # .................................................................................................................



class Nonthreaded_PNG_Saver:
    
    # .................................................................................................................
    
    def __init__(self, *, png_folder_path):
        
        # Store inputs
        self.png_folder_path = png_folder_path
    
    # .................................................................................................................
    
    def save_data(self, file_save_name_no_ext, image_data, png_compression_0_to_9 = 0):
        
        # Encode data for saving
        encoded_png_data = encode_png_data(image_data, png_compression_0_to_9)
        
        # Save image data
        write_encoded_png(self.png_folder_path, file_save_name_no_ext, encoded_png_data)
        
        return
    
    # .................................................................................................................
    
    def close(self):
        # Nothing to close on non-threaded saver
        return
    
    # .................................................................................................................
    # .................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Object Report data Savers


class Threaded_Compressed_JSON_Saver:
    
    # .................................................................................................................
    
    def __init__(self, *, thread_name, jsongz_folder_path):
        
        # Store inputs
        self.thread_name = thread_name
        self.jsongz_folder_path = jsongz_folder_path
        
        # For clarity
        max_queue_size = 250
        auto_kill_when_main_thread_closes = True
        
        # Set up threading resources
        self._data_queue = queue.Queue(max_queue_size)
        self._run_thread_event = threading.Event()
        thread_args = (jsongz_folder_path, self._data_queue, self._run_thread_event)
        
        # Start saving thread
        self._thread_ref = threading.Thread(name = thread_name,
                                            target = self._wait_for_data_to_save,
                                            args = thread_args,
                                            daemon = auto_kill_when_main_thread_closes)
        
        # Start the thread
        self._run_thread_event.set()
        self._thread_ref.start()
    
    # .................................................................................................................
    
    def save_data(self, file_save_name_no_ext, metadata_dict, json_double_precision = 3):
        
        '''
        Function which handles 'saving' of data (at least from the callers perspective)
        Actually bundles data and passes it to the savng thread to handle actual file i/o
        '''
        
        # Encode data for saving
        encoded_json_data = encode_jsongz_data(metadata_dict, json_double_precision)
        
        # Bundle everything needed for saving
        bundled_data = (file_save_name_no_ext, encoded_json_data)
        
        # Now place bundled data in the queue for the thread to deal with
        # Note: we aren't actually saving (depsite the function name), we're just passing data to the thread to save!
        self._data_queue.put(bundled_data, block = True, timeout = None)
        
        return
    
    # .................................................................................................................
    
    def _wait_for_data_to_save(self, metadata_save_folder_path, data_queue_ref, run_thread_event_ref):
        
        # Loop until something stops us
        while True:
            
            # Save all data from the queue when it's available
            while not data_queue_ref.empty():
                
                # Get data from queue
                file_save_name_no_ext, encoded_jsongz_data = data_queue_ref.get()
                
                # Save metadata with compression
                write_encoded_jsongz(metadata_save_folder_path, file_save_name_no_ext, encoded_jsongz_data)
            
            # Check if we need to stop
            got_shutdown_signal = (not run_thread_event_ref.is_set())
            if got_shutdown_signal and data_queue_ref.empty():
                break
            
            # Wait a bit so we aren't completely hammering this thread
            sleep(0.5)     
        
        return
    
    # .................................................................................................................
    
    def close(self):
        
        # Clear event to trigger thread to close
        self._run_thread_event.clear()
        
        # Now wait for thread to close (may take a moment if still saving data)
        self._thread_ref.join(10.0)
        
        return
    
    # .................................................................................................................
    # .................................................................................................................



class Nonthreaded_Compressed_JSON_Saver:
    
    # .................................................................................................................
    
    def __init__(self, *, jsongz_folder_path):
        
        # Store inputs
        self.jsongz_folder_path = jsongz_folder_path
    
    # .................................................................................................................
    
    def save_data(self, file_save_name_no_ext, metadata_dict, json_double_precision = 3):
        
        # Encode data for saving
        encoded_jsongz_data = encode_jsongz_data(metadata_dict, json_double_precision)
        
        # Save metadata with compression
        write_encoded_jsongz(self.jsongz_folder_path, file_save_name_no_ext, encoded_jsongz_data)
        
        return
    
    # .................................................................................................................
    
    def close(self):
        
        return
    
    # .................................................................................................................
    # .................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Background/Snapshot Report Data Savers

class Threaded_JPG_and_JSON_Saver:
    
    # .................................................................................................................
    
    def __init__(self, *, thread_name, jpg_folder_path, json_folder_path):
        
        # Store inputs
        self.thread_name = thread_name
        self.jpg_folder_path = jpg_folder_path
        self.json_folder_path = json_folder_path
        
        # For clarity
        max_queue_size = 250
        auto_kill_when_main_thread_closes = True
        
        # Set up threading resources
        self._data_queue = queue.Queue(max_queue_size)
        self._run_thread_event = threading.Event()
        thread_args = (jpg_folder_path, json_folder_path, self._data_queue, self._run_thread_event)
        
        # Start saving thread
        self._thread_ref = threading.Thread(name = thread_name,
                                            target = self._wait_for_data_to_save,
                                            args = thread_args,
                                            daemon = auto_kill_when_main_thread_closes)
        
        # Start the thread
        self._run_thread_event.set()
        self._thread_ref.start()
    
    # .................................................................................................................
    
    def save_data(self, file_save_name_no_ext, image_data, metadata_dict, 
                  jpg_quality_0_to_100 = 25, json_double_precision = 3):
        
        '''
        Function which handles 'saving' of data (at least from the callers perspective)
        Actually bundles data and passes it to the saving thread to handle actual file i/o
        '''
        
        # Encode data for saving
        encoded_jpg_data = encode_jpg_data(image_data, jpg_quality_0_to_100)
        encoded_json_data = encode_json_data(metadata_dict, json_double_precision)
        
        # Bundle everything needed for saving
        bundled_data = (file_save_name_no_ext, encoded_jpg_data, encoded_json_data)
        
        # Now place bundled data in the queue for the thread to deal with
        # Note: we aren't actually saving (despite the function name), we're just passing data to the thread to save!
        self._data_queue.put(bundled_data, block = True, timeout = None)
        
        return
    
    # .................................................................................................................
    
    def _wait_for_data_to_save(self, image_save_folder_path, metadata_save_folder_path,
                               data_queue_ref, run_thread_event_ref):
        
        # Loop until something stops us
        while True:
            
            # Save all data from the queue when it's available
            while not data_queue_ref.empty():
                
                # Get data from queue
                file_save_name_no_ext, encoded_jpg_data, encoded_json_data = data_queue_ref.get()
                
                # Save image data
                write_encoded_jpg(image_save_folder_path, file_save_name_no_ext, encoded_jpg_data)
                write_encoded_json(metadata_save_folder_path, file_save_name_no_ext, encoded_json_data)
            
            # Check if we need to stop
            got_shutdown_signal = (not run_thread_event_ref.is_set())
            if got_shutdown_signal and data_queue_ref.empty():
                break
            
            # Wait a bit so we aren't completely hammering this thread
            sleep(0.5)
        
        return
    
    # .................................................................................................................
    
    def close(self):
        
        # Clear event to trigger thread to close
        self._run_thread_event.clear()
        
        # Now wait for thread to close (may take a moment if still saving data)
        self._thread_ref.join(10.0)
        
        return
    
    # .................................................................................................................
    # .................................................................................................................


# =====================================================================================================================
# =====================================================================================================================


class Nonthreaded_JPG_and_JSON_Saver:
    
    # .................................................................................................................
    
    def __init__(self, *, jpg_folder_path, json_folder_path):
        
        # Store inputs
        self.jpg_folder_path = jpg_folder_path
        self.json_folder_path = json_folder_path
    
    # .................................................................................................................
    
    def save_data(self, file_save_name_no_ext, image_data, metadata_dict,
                  jpg_quality_0_to_100 = 25, json_double_precision = 3):
        
        # Encode data for saving
        encoded_jpg_data = encode_jpg_data(image_data, jpg_quality_0_to_100)
        encoded_json_data = encode_json_data(metadata_dict, json_double_precision)
        
        # Save data
        write_encoded_jpg(self.jpg_folder_path, file_save_name_no_ext, encoded_jpg_data)
        write_encoded_json(self.json_folder_path, file_save_name_no_ext, encoded_json_data)
        
        return

    # .................................................................................................................
    
    def close(self):
        
        return
    
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
    pass


# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap

# TODO
# - unify threaded savers into a single class!
# - unify non-threaded savers as well
# - maybe unify both into a single class?

