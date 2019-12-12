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
import cv2
import json
import gzip

from time import perf_counter

from eolib.utils.files import get_file_list, get_file_list_by_age


# ---------------------------------------------------------------------------------------------------------------------
#%% Worker classes

class Threaded_Worker:
    
    # .................................................................................................................
    
    def __init__(self, threading_enabled = True, run_as_daemon = True, lock = None):
        
        # Store behavior flags
        self.threading_enabled = threading_enabled
        self._run_as_daemon = run_as_daemon
        self._lock = lock
        self._lock_available = (lock is not None)
        
        # Allocate storage for keeping track of threads
        self._thread_list = []
    
    # .................................................................................................................
    
    def toggle_threading(self, enable_threading):
        self.threading_enabled = enable_threading
    
    # .................................................................................................................
    
    def is_working(self):
        
        ''' Function used to check if any threads are active '''
        
        # Check if any threads are active
        for each_thread in self._thread_list:
            if each_thread.is_alive(): 
                return True
            
        return False
    
    # .................................................................................................................
    
    def launch_as_thread(self, function_to_thread, *function_args, **function_kwargs):
        
        '''
        Function for launching a given function on a separate thread. The function should be passed by name
        (without calling, i.e. no parenthesis), along with any positional args or key-word args.
        This object will automatically keep track of threads, but the clean_up() function should be called
        to clear out these records over time.
        
        Inputs:
            function_to_thread -> Function. Pass in without executing (no parenthesis)
            
            *function_args -> Any type. Positional arguments for the function. 
                              Pass in each argument separate with commas
                              (do not bundle these as a list/tuple)
                              
            **function_kwargs -> Any type. Key-word arguments for the function. 
                                 Pass in using the normal style: keyword = value
                                 (do not bundle these as a dictionary)
        
        Outputs:
            None
        '''
        
        # Create thread
        func_to_run = self._lock_function(function_to_thread) if self._lock_available else function_to_thread
        new_func_thread = threading.Thread(target = func_to_run,
                                           args = function_args,
                                           kwargs = function_kwargs,
                                           daemon = self._run_as_daemon)
        
        # Start the threaded function call & add thread to the list for clean-up
        new_func_thread.start()
        self._thread_list.append(new_func_thread)
        
        # Wait for thread to finish if threading is actually disabled
        if not self.threading_enabled:
            new_func_thread.join()
    
    # .................................................................................................................
    
    def clean_up(self):
        
        ''' Function for clearing out finished threads. No inputs/outputs '''
        
        # Figure out which threads are safe to remove
        rem_threads_idx = []
        for each_idx, each_thread in enumerate(self._thread_list):
            if each_thread.is_alive(): continue
            each_thread.join()
            rem_threads_idx.append(each_idx)
        
        # Remove finished threads from our list so we can stop tracking them
        for each_idx in reversed(rem_threads_idx):
            del self._thread_list[each_idx]
            
    # .................................................................................................................
    
    def close(self):
        
        ''' Function which blocks execution while waiting for all threads to finish. No inputs/outputs '''
        
        # Wait for all threads to finish & clean up
        for each_thread in self._thread_list:
            each_thread.join()
            
        self.clean_up()
        
    # .................................................................................................................
    
    def _lock_function(self, function_to_call):
        
        def _locked_call(*function_args, **function_kwargs):
            
            # Make sure we lock out other threads if possible
            self._lock.acquire()
            
            # Call the function with whatever arguments it needs and place it's results into the queue for later access
            function_to_call(*function_args, **function_kwargs)
            
            # Unlock so other threads can continue
            self._lock.release()
                
            return
    
        return _locked_call
    
    # .................................................................................................................
    # .................................................................................................................
    
    # .................................................................................................................
    # .................................................................................................................



class Parallel_Function(Threaded_Worker):
    
    # .................................................................................................................
    
    def __init__(self, function_to_thread, queue_size = 10, threading_enabled = True, *, lock = None):
        
        '''
        Class used to launch a function call as a parallel (threaded) worker process.
        The return value of the function will be placed in a queue as it finishes
        
        Useful methods:
            
            launch_as_thread() -> Call with function args/kwargs to launch the function on a separate thread
                                  (with optional thread lock around start/end of the function)
                                
            data_is_available() -> Call to check if new function results are available
            
            get_new_data() -> Non-blocking call to retrieve new data. Note that this can fail if no data is available!
            
            get_new_data_blocking() -> Same as get_new_data(), but blocks until data is available
            
            is_working() -> Check if an unfinished function call is currently running
            
            toggle_threading() -> Use to turn threading on or off
            
            clean_up() -> If auto-clean up is not used when getting data, 
                          this must be called to get rid of finished threads!
        '''
        
        # Inherit from parent class
        super().__init__(threading_enabled, lock = lock)
        
        # Store function to thread
        self._function_to_thread = function_to_thread
        
        # Store threading data access variables
        self._queue_size = queue_size
        self._results_queue = queue.Queue(queue_size)
    
    # .................................................................................................................
    
    def __call__(self, *function_args, **function_kwargs):
        
        ''' Convenience version of launch_as_thread() '''
        
        self.launch_as_thread(*function_args, **function_kwargs)
    
    # .................................................................................................................
    
    # OVERRIDNG FROM PARENT!
    def launch_as_thread(self, *function_args, **function_kwargs):
        
        # Create saving thread
        new_func_thread = threading.Thread(target = self._locked_wrapper,
                                           args = function_args,
                                           kwargs = function_kwargs,
                                           daemon = True)
        
        # Start the threaded function call & add it to the list to keep track of it
        new_func_thread.start()
        self._thread_list.append(new_func_thread)
        
        # Wait for thread to finish if threading is actually disabled
        if not self.threading_enabled:
            new_func_thread.join()
            
    # .................................................................................................................
    
    def data_is_available(self):
        return (not self._results_queue.empty())
    
    # .................................................................................................................
    
    def get_new_data(self, error_if_missing = True, return_if_missing = None, auto_clean_up = True):
        
        ''' 
        Function for retrieving new data from the threaded background worker. Non-blocking
        Worker is not guarenteed to have data available! Check availablity with data_is_available() function
        
        Inputs:
            error_if_missing -> Boolean. If true, an IOError is raised if no data is available. Otherwise,
                                the returned data is determined by the other input argument...
            
            return_if_missing -> Any type. Data to return if the worker has nothing available
            
            auto_clean_up -> Boolean. If true, the interal clean_up() function is called after retrieving data
            
        Outputs:
            newest_data
        '''
        
        try:
            new_results = self._results_queue.get_nowait()
            if auto_clean_up:
                self.clean_up()
            
        except queue.Empty:
            if error_if_missing:
                raise IOError("No data in worker queue!")
            new_results = return_if_missing
        
        return new_results
    
    # .................................................................................................................
    
    def get_new_data_blocking(self, timeout_sec = None, error_on_timeout = True, return_on_timeout = None,
                              auto_clean_up = True):
        
        ''' 
        A blocking version of the get_new_data() function
        
        Inputs:
            timeout_sec -> Float or None. If a number is provided, function will block for at most, this
                           number of seconds before failing. If None, blocks forever
                           
            error_on_timeout -> Boolean. If true, and IOError is raised if no data is available before timeout.
                                Otherwise returns data based on the final function argument...
                                
            return_on_timeout -> Any type. Data to return if no data is available before timeout
            
            auto_clean_up -> Boolean. If true, the interal clean_up() function is called after retrieving data
        '''
        
        try:
            new_results = self._results_queue.get(block = True, timeout = timeout_sec)
            if auto_clean_up:
                self.clean_up()
            
        except queue.Empty:            
            if error_on_timeout:
                raise IOError("No data in worker queue!")
            new_results = return_on_timeout
        
        return new_results
    
    # .................................................................................................................
    
    def _locked_wrapper(self, *args, **kwargs):
        
        # Make sure we lock out other threads if possible
        if self._lock_available:
            self._lock.acquire()
        
        # Call the function with whatever arguments it needs and place it's results into the queue for later access
        new_results = self._function_to_thread(*args, **kwargs)
        self._results_queue.put(new_results)
        
        # Unlock so other threads can continue
        if self._lock_available:
            self._lock.release()
    
    # .................................................................................................................
    # .................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Saver classes

class Data_Access(Threaded_Worker):
    
    # .................................................................................................................
    
    def __init__(self, cameras_folder_path, camera_select, user_select, task_select = None,
                 create_folder_if_missing = True, threading_enabled = True,
                 *, lock = None):
        
        # Inherit from parent class. Gives access to threading functionality (if needed)
        super().__init__(threading_enabled, lock = lock)
        
        # Store all required pathing info for re-use
        self.cameras_folder_path = cameras_folder_path
        self.camera_select = camera_select
        self.user_select = user_select
        self.task_select = task_select
        
        # Create base saving path
        self._data_folder_path = self._build_data_folder_path()
        if create_folder_if_missing:
            os.makedirs(self._data_folder_path, exist_ok = True)
    
    # .................................................................................................................
    
    def _build_data_folder_path(self):
        
        class_name = self.__class__.__name__
        error_msg = "Need to override _build_data_folder_path() in sub-class! ({})".format(class_name)
        
        raise NotImplementedError(error_msg)
        
    # .................................................................................................................
    
    def relative_data_path(self, start_path = None):
        
        ''' Function for providing a string representing the relative path to this objects data folder '''
        
        if start_path is None:
            start_path = self.cameras_folder_path
        
        return os.path.relpath(self._data_folder_path, start_path)
    
    # .................................................................................................................
    
    def list_file_paths(self, sort_chronologically = True, allowable_exts_list = []):
        
        ''' 
        Function which provides a list of file paths at the data path
        Various inputs allow for different ways of sorting the resulting pathings
        
        Inputs:
            sort_chronologically -> Boolean. If true, results are sorted by file creation time. Newest first.
            
        Outputs:
            file_path_list -> List. Full file paths with optional sorting        
        '''        
        
        if sort_chronologically:
            sorted_ages, file_path_list = get_file_list_by_age(self._data_folder_path, 
                                                               newest_first = True,
                                                               show_hidden_files = False, 
                                                               create_missing_folder = False,
                                                               return_full_path = True,
                                                               allowable_exts_list = allowable_exts_list)
        else:
            file_path_list = get_file_list(self._data_folder_path, 
                                           show_hidden_files = False, 
                                           create_missing_folder = False,
                                           return_full_path = True, 
                                           sort_list = False,
                                           allowable_exts_list = allowable_exts_list)
        
        return file_path_list
    
    # .................................................................................................................
    
    def clear_existing_data(self, allowable_exts_list = []):
        
        ''' Function which deletes target files from the access path '''
        
        # Get a list of files, with possible extension filtering, then ask the os to delete them all!
        existing_file_paths = self.list_file_paths(False, allowable_exts_list)
        for each_path in existing_file_paths:
            os.remove(each_path)
    
    # .................................................................................................................
    # .................................................................................................................


class Image_Saver(Data_Access):
    
    # .................................................................................................................
    
    def __init__(self, cameras_folder_path, camera_select, user_select, task_select,
                 saving_enabled = True, create_save_folder_if_missing = True, threading_enabled = True,
                 *, lock = None):
        
        # Inherit from base class
        super().__init__(cameras_folder_path, camera_select, user_select, task_select,
                         create_folder_if_missing = create_save_folder_if_missing,
                         threading_enabled = threading_enabled,
                         lock = lock)
        
        # Store saving settings
        self.saving_enabled = saving_enabled
        
    # .................................................................................................................
    
    def toggle_saving(self, enable_saving):
        self.saving_enabled = enable_saving
    
    # .................................................................................................................
    
    def apply_jpg_quality(self, image_data, save_quality_0_to_100):
        
        '''
        Function which applies jpg compression to input image data (numpy array) and returns the result
        Also returns the time required to perform conversion & data size
        '''
        
        # Convert image data to a jpg with specified quality and time it!
        t1 = perf_counter()
        jpg_quality_arg = (cv2.IMWRITE_JPEG_QUALITY, save_quality_0_to_100)
        _, jpg_image = cv2.imencode(".jpg", image_data, jpg_quality_arg)
        t2 = perf_counter()
        
        # Get outputs
        processing_time_sec = t2 - t1
        image_size_bytes = jpg_image.nbytes
        output_image = cv2.imdecode(jpg_image, cv2.IMREAD_COLOR)
        
        return output_image, image_size_bytes, processing_time_sec
    
    # .................................................................................................................
    
    def apply_png_compression(self, image_data, save_compression_0_to_9):
        
        '''
        Function which applies png compression to input image data (numpy array) and returns the result
        Also returns the time required to perform conversion & data size
        '''
        
        # Convert image data to a jpg with specified quality and time it!
        t1 = perf_counter()
        png_compression_arg = (cv2.IMWRITE_PNG_COMPRESSION, save_compression_0_to_9)   
        _, png_image = cv2.imencode(".jpg", image_data, png_compression_arg)
        t2 = perf_counter()
        
        # Get outputs
        processing_time_sec = t2 - t1
        image_size_bytes = png_image.nbytes
        output_image = cv2.imdecode(png_image, cv2.IMREAD_COLOR)
        
        return output_image, image_size_bytes, processing_time_sec
    
    # .................................................................................................................
    
    def save_jpg(self, file_save_name_no_ext, image_data, save_quality_0_to_100 = 20):
        
        '''
        Saves jpg files to the save path created during class initialization
        
        Inputs:
            file_save_name_no_ext -> String. Name of file to save. Extension (.jpg) will be added automatically
            
            image_data -> Numpy array. Image data to save
            
            save_quality_0_to_100 -> Controls trade-off between image quality and file size. 
                                     Also affects saving time
        
        Testing results for sample image @ 1280x720:
        (Timing results vary based on image content & cpu speed. Mostly provided for relative comparison)
                            Quality 0  |    Quality 25  |   Quality 50  |   Quality 75  |   Quality 100
          File size (kb)    23              77              116             168             686
         Time taken (ms)    4.1             4.8             5.3             6.3             11
         (Note: Saving times were highly variable, even across a 1000 sample average!)
        '''
        
        # Skip saving if disabled
        if not self.saving_enabled:
            return None
        
        # Build file save pathing
        save_file_name = "".join([file_save_name_no_ext, ".jpg"])
        save_file_path = os.path.join(self._data_folder_path, save_file_name)
        
        # Build the (somewhat obscure) jpg quality argument
        jpg_quality_arg = (cv2.IMWRITE_JPEG_QUALITY, save_quality_0_to_100)
        
        # Save image, with threading (if enabled)
        threaded_func = cv2.imwrite
        self.launch_as_thread(threaded_func, save_file_path, image_data, jpg_quality_arg)
        
        return save_file_path
    
    # .................................................................................................................
    
    def save_png(self, file_save_name_no_ext, image_data, save_compression_0_to_9 = 0):
        
        '''
        Saves png files to the save path created during class initialization
        
        Inputs:
            file_save_name_no_ext -> String. Name of file to save. Extension (.png) will be added automatically
            
            image_data -> Numpy array. Image data to save
            
            compression_level_0_to_9 -> Controls trade-off between file size and saving time.
                                        Doesn't affect image quality! (png is lossless)
        
        Testing results for sample image @ 1280x720:
        (Timing results vary based on image content & cpu speed. Mostly provided for relative comparison)
                            Compression 0  |    Compression 5  |    Compression 9
          File size (MB)    2.8                 1.2                 1.1
         Time taken (ms)    45                  137                 780
        '''
        
        # Skip saving if disabled
        if not self.saving_enabled:
            return None
        
        # Build file save pathing
        save_file_name = "".join([file_save_name_no_ext, ".png"])
        save_file_path = os.path.join(self._data_folder_path, save_file_name)
        
        # Build the (somewhat obscure) png compression argument
        png_compression_arg = (cv2.IMWRITE_PNG_COMPRESSION, save_compression_0_to_9)   
        
        # Save image, with threading (if enabled)
        threaded_func = cv2.imwrite
        self.launch_as_thread(threaded_func, save_file_path, image_data, png_compression_arg)
        
        return save_file_path
    
    # .................................................................................................................
    # .................................................................................................................


# =====================================================================================================================
# =====================================================================================================================


class Metadata_Saver(Data_Access):
    
    # .................................................................................................................
    
    def __init__(self, cameras_folder_path, camera_select, user_select, task_select,
                 saving_enabled = True, create_save_folder_if_missing = True, threading_enabled = True,
                 *, lock = None):
        
        # Inherit from base class
        super().__init__(cameras_folder_path, camera_select, user_select, task_select,
                         create_folder_if_missing = create_save_folder_if_missing,
                         threading_enabled = threading_enabled, 
                         lock = lock)
        
        # Store saving settings
        self.saving_enabled = saving_enabled
    
    # .................................................................................................................
    
    def toggle_saving(self, enable_saving):
        self.saving_enabled = enable_saving
    
    # .................................................................................................................
    
    def save_json(self, file_save_name_no_ext, json_data):
        
        # Skip saving if disabled
        if not self.saving_enabled:
            return None
        
        # Build file save pathing
        save_file_name = "".join([file_save_name_no_ext, ".json"])
        save_file_path = os.path.join(self._data_folder_path, save_file_name)
        
        # Save json data
        self.launch_as_thread(self._write_json, save_file_path, json_data)
        
        return save_file_path
    
    # .................................................................................................................
    
    def save_json_gz(self, file_save_name_no_ext, json_data):
        
        # Skip saving if disabled
        if not self.saving_enabled:
            return None
        
        # Build file save pathing
        save_file_name = "".join([file_save_name_no_ext, ".json.gz"])
        save_file_path = os.path.join(self._data_folder_path, save_file_name)
        
        # Save json data with gzip compression
        self.launch_as_thread(self._write_json_gz, save_file_path, json_data)
        
        return save_file_path
    
    # .................................................................................................................
    
    @staticmethod
    def _write_json(save_file_path, json_data):
        # Save json data (with human-readable spacing)
        with open(save_file_path, "w") as out_file:
            json.dump(json_data, out_file, indent = 2)
    
    # .................................................................................................................
    
    @staticmethod
    def _write_json_gz(save_file_path, json_data):
        # Save json data with gzip compression and very human-un-readable settings for small file sizes
        with gzip.open(save_file_path, "wt", encoding = "ascii") as out_file:
            json.dump(json_data, out_file, separators = (",", ":"), indent = None)
            
    # .................................................................................................................
    # .................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Loader classes

class Data_Loader(Data_Access):
    
    # .................................................................................................................
    
    def __init__(self, cameras_folder_path, camera_select, user_select, task_select = None,
                 saving_enabled = True, create_load_folder_if_missing = True, threading_enabled = True,
                 *, lock = None):
        
        # Inherit from base class
        super().__init__(cameras_folder_path, camera_select, user_select, task_select,
                         create_folder_if_missing = create_load_folder_if_missing,
                         threading_enabled = threading_enabled,
                         lock = lock)
        
    # .................................................................................................................
    # .................................................................................................................
    

class Image_Loader(Data_Loader):
    
    # .................................................................................................................
    
    def __init__(self, cameras_folder_path, camera_select, user_select, task_select,
                 threading_enabled = True, saving_enabled = True, create_load_folder_if_missing = True,
                 *, lock = None):
        
        # Inherit from base class
        super().__init__(cameras_folder_path, camera_select, user_select, task_select,
                         threading_enabled = threading_enabled, 
                         saving_enabled = saving_enabled,
                         create_load_folder_if_missing = create_load_folder_if_missing,
                         lock = lock)
       
    # .................................................................................................................
    
    def load_from_path(self, load_path):
        
        # Load an image with error checking, though OpenCV doesn't like to raise errors while reading images...
        try:
            load_image = cv2.imread(load_path)
        except Exception:
            pass
        
        # OpenCV load image function doesn't give errors when loading non-image files or files-in-progress
        # ... instead it just returns None
        if load_image is None:
            raise FileNotFoundError("Error loading image:", load_path)
            
        return load_image
        
    # .................................................................................................................
    
    def load_image(self, file_load_name_with_ext):
        
        # Build png name & path to file for loading
        load_path = os.path.join(self._data_folder_path, file_load_name_with_ext)
        
        return self.load_from_path(load_path)
    
    # .................................................................................................................
    
    def load_jpg(self, file_load_name_no_ext):
        
        # Build png name & path to file for loading
        load_name = "{}{}".format(file_load_name_no_ext, ".jpg")
        load_path = os.path.join(self._data_folder_path, load_name)
        
        return self.load_from_path(load_path)
    
    # .................................................................................................................
    
    def load_png(self, file_load_name_no_ext):
        
        # Build png name & path to file for loading
        load_name = "{}{}".format(file_load_name_no_ext, ".png")
        load_path = os.path.join(self._data_folder_path, load_name)
        
        return self.load_from_path(load_path)
    
    # .................................................................................................................
    # .................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

def create_new_thread_lock():
    
    ''' 
    Simple helper function to avoid having to import threading library elsewhere. 
    Returns a Lock object 
    Use .acquire() & .release() around threaded code to block multiple threads from being active at the same time
    '''
    
    return threading.Lock()

# ---------------------------------------------------------------------------------------------------------------------
#%% Demo

if __name__ == "__main__":
    pass


# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap

