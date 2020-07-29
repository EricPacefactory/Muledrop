#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Sep 16 09:21:36 2019

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

import numpy as np

from time import sleep, perf_counter
from multiprocessing import Process

from local.configurables.configurable_template import Externals_Configurable_Base

from local.lib.common.timekeeper_utils import Periodic_Polled_Timer, Periodic_Polled_Integer_Counter

from local.lib.file_access_utils.reporting import Background_Report_Data_Saver
from local.lib.file_access_utils.reporting import create_image_metadata

from local.lib.file_access_utils.resources import Background_Resources_Data_Saver
from local.lib.file_access_utils.resources import load_background_captures_iter, load_background_generates_iter
from local.lib.file_access_utils.resources import load_newest_generated_background, save_generated_image
from local.lib.file_access_utils.resources import build_background_capture_folder_path
from local.lib.file_access_utils.resources import build_background_generate_folder_path

from local.lib.launcher_utils.resource_initialization import check_for_valid_background

from local.eolib.utils.files import create_missing_folder_path


# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes


class Reference_Background_Capture(Externals_Configurable_Base):
    
    # .................................................................................................................
    
    def __init__(self, location_select_folder_path, camera_select, video_wh, *, file_dunder):
        
        # Inherit from base class
        super().__init__("background_capture", location_select_folder_path, camera_select, video_wh,
                         file_dunder = file_dunder)
        
        # Store state config
        self.report_saving_enabled = None
        self.resource_saving_enabled = None
        self.threaded_saving_enabled = None
        
        # Allocate storage for setting saving quality (note, png compression is hard-coded)
        self._jpg_quality_0_to_100 = None
        self._png_compression_0_to_9 = None
        
        # Allocate storage for shared background capture/generation variables & counters
        self.max_capture_count = None
        self.max_generate_count = None
        self._capture_counter = Periodic_Polled_Integer_Counter(reset_on_first_check = True)
        self._generate_counter = Periodic_Polled_Integer_Counter(reset_on_first_check = True)
        
        # Allocate storage for the parallel background generating task
        self._parallel_process_name = "bggen_{}".format(camera_select)
        self._parallel_process = None
        
        # Allocate storage for background image data
        self._current_background_image = None
        
        # Allocate storage for the data saver objects which handles file i/o
        self._report_data_saver = None
        self._capture_data_saver = None
        
        # Set up periodic triggers used for capturing frame data & generating new backgrounds
        self._capture_timer = Periodic_Polled_Timer(trigger_on_first_check = False)
        self._generate_trigger = Periodic_Polled_Integer_Counter(reset_on_first_check = False)
        
        # Set default behaviour states
        self.toggle_report_saving(False)
        self.toggle_resource_saving(False)
        self.toggle_threaded_saving(False)
        self.set_jpg_quality(50)
        self.set_png_compression(0)
        self.set_max_capture_count(25)
        self.set_max_generate_count(3)
        self.set_capture_period(minutes = 6)
        self.set_generate_trigger(every_n_captures = 5)
        
        # Make sure we a background exists on startup (another function is responsible for initial bg generation!)
        background_available = \
        check_for_valid_background(location_select_folder_path, camera_select, *video_wh,
                                   print_feedback_on_existing = False)
        if not background_available:
            error_msg = "Can't initialize background capture, no initial background image found!"
            self.log(error_msg)
            raise FileNotFoundError(error_msg)
        
        # Build pathing to captures/generation folders and make sure they exist
        self._capture_folder_path = build_background_capture_folder_path(location_select_folder_path, camera_select)
        self._generate_folder_path = build_background_generate_folder_path(location_select_folder_path, camera_select)
        create_missing_folder_path(self._capture_folder_path)
        create_missing_folder_path(self._generate_folder_path)
    
    # .................................................................................................................
    
    # MAY OVERRIDE
    def reset(self):
        
        ''' Function called every time video processing rewinds or jumps around in time. Mostly for configuration '''
        
        # Force capture/generate timers to reset, so trigger timings aren't messed up by video rewind/fastforwards
        self._capture_timer.reset_timer()
        self._generate_trigger.reset_counter()
        
        return
    
    # .................................................................................................................
    
    # MAY OVERRIDE
    def close(self, final_frame_index, final_epoch_ms, final_datetime):
        
        ''' Function called after video processing completes or is cancelled early '''
        
        # Make sure file i/o is finished
        print("Closing background capture...", end="")
        
        # Shutdown threaded savers
        self.log("Closing: Shutting down report & capture data savers...", prepend_empty_line = False)
        self._report_data_saver.close()
        self._capture_data_saver.close()
        self.log("Closing: Report & capture savers closed!", prepend_empty_line = False)
        
        # Shutdown the parallel background creator, if it exists
        if self._parallel_process is not None:
            wait_seconds = 15
            warn_msg = "Closing: Parallel generation still running. Waiting {} seconds...".format(wait_seconds)
            self.log(warn_msg, prepend_empty_line = False)
            self._parallel_process.join(wait_seconds)
            self.log("Closing: Parallel generation closed!", prepend_empty_line = False)
        
        print(" Done!")
    
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE
    def toggle_report_saving(self, enable_data_saving):
        
        ''' Function used to disable saving of report data. Useful during testing/configuration '''
        
        # Re-initialize report saver with new settings
        self.report_saving_enabled = enable_data_saving
        self._report_data_saver = self._initialize_report_data_saver()
    
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE
    def toggle_resource_saving(self, enable_data_saving):
        
        ''' Function used to disable saving of resource data. Useful during testing/configuration '''
        
        # Re-initialize resource saver with new settings
        self.resource_saving_enabled = enable_data_saving
        self._capture_data_saver = self._initialize_capture_data_saver()
        
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE
    def toggle_threaded_saving(self, enable_threaded_saving):
        
        ''' 
        Function used to enable or disable threading of data saving. 
        Mostly useful for testing out functionality (and avoiding complications from threading),
        or otherwise used during file evaluation, to force deterministic save timing
        '''
        
        # Re-initialize the savers with new settings
        self.threaded_saving_enabled = enable_threaded_saving
        self._report_data_saver = self._initialize_report_data_saver()
        self._capture_data_saver = self._initialize_capture_data_saver()
        
        # When using threaded saving, make the capture is random to help avoid synchronization across multiple cameras
        # (only expected to be enabled when running on RTSP)
        if enable_threaded_saving:
            self._capture_timer.enable_randomness(seconds = 5)
        else:
            self._capture_timer.disable_randomness()
        
        return
    
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE
    def set_jpg_quality(self, jpg_quality_0_to_100):
        
        ''' Function used to change the jpg compression quality for all reported background images '''
        
        self._jpg_quality_0_to_100 = jpg_quality_0_to_100
    
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE
    def set_png_compression(self, png_compression_0_to_9):
        
        ''' Function used to change the png compression for all background capture images '''
        
        self._png_compression_0_to_9 = png_compression_0_to_9
    
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE
    def set_max_capture_count(self, max_capture_count):
        
        ''' Function for modifying the maximum number of captures to save. Shared for all subclasses '''
        
        self.max_capture_count = max_capture_count
        self._capture_counter.set_count_reset_value(max_capture_count)
        
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE
    def set_max_generate_count(self, max_generate_count):
        
        ''' Function for modifying the maximum number of generated images to save. Shared for all subclasses '''
        
        self.max_generate_count = max_generate_count
        self._generate_counter.set_count_reset_value(max_generate_count)
    
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE
    def set_capture_period(self, hours = 0, minutes = 0, seconds = 0, milliseconds = 0):
        
        '''
        Function for modifying the frame capture period
        Captured frames are used to generate background images
        '''
        
        self._capture_timer.set_trigger_period(hours, minutes, seconds, milliseconds)
    
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE
    def set_generate_trigger(self, every_n_captures):
        
        ''' Function for modifying how often background generation occurs (occurring after repeated captures) '''
        
        self._generate_trigger.set_count_reset_value(every_n_captures)
    
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE
    def set_current_background(self, new_background_frame):
        
        '''
        Function used to update the current background in use.
        Should be called by sub-classes instead of overwriting background image variable directly!
        '''
        
        self._current_background_image = new_background_frame
    
    # .................................................................................................................
    
    # MAY OVERRIDE, but better to override generate_background_from_resources() function
    def run(self, input_frame, current_frame_index, current_epoch_ms, current_datetime):
        
        '''
        Main function! Generates backgrounds from regularly captured frames of the scene
        Note: Must output a valid background_frame regardless of whether a new frame was generated or not!)
        
        Inputs:
            input_frame -> Image data. Current frame data from a video source
            
            current_frame_index -> Integer. Current frame index of the video source
            
            current_epoch_ms -> Integer. Current epoch time, in mlliseconds
            
            current_datetime -> Datetime object. Current datetime (interpretation depends on files vs rtsp)
        
        Outputs:
            background_frame (np array), background_was_updated (boolean)
        '''
        
        # Initialize outputs
        background_image = self._current_background_image
        background_was_updated = False
        
        # Check if we need to load a new background frame (from generation)
        need_to_load_new_background = self._trigger_load_new_background()
        if need_to_load_new_background:
            
            # Load the new background data
            image_height, image_width = input_frame.shape[0:2]
            new_background_image = self._load_newest_background(image_width, image_height)
            
            # Save new background as report data
            self._save_report_data(new_background_image, current_frame_index, current_epoch_ms, current_datetime)
            
            # Update internal record & outputs
            self._current_background_image = new_background_image
            background_image = new_background_image
            background_was_updated = True
        
        # Bail if we're not saving resource files
        if not self.resource_saving_enabled:
            return background_image, background_was_updated
        
        # Check if we need to save the current frame
        need_new_capture = self._trigger_capture(input_frame, current_epoch_ms)
        if not need_new_capture:
            return background_image, background_was_updated
        
        # Check if we need to generate a new background frame
        need_new_generate = self._trigger_generate(current_epoch_ms)
        if need_new_generate:
            self.log("Update: Need to generate a new background!")
        
        return background_image, background_was_updated
    
    # .................................................................................................................
    
    # SHOULD OVERRIDE
    def generate_background_from_resources(self,
                                           num_captures, capture_image_iter,
                                           num_generates, generate_image_iter,
                                           target_width, target_height):
        
        '''
        Function which generates the actual background from captured/generated data.
        Note that this function runs in parallel with the main process
        Also note that the function must return an image or None (if an image isn't generated),
        and it must have the dimensions given by the target inputs
        '''
        
        # Reference returns a noise frame
        new_background_image = np.random.randint(0, 255, (target_height, target_width, 3), dtype = np.uint8)
        
        return new_background_image
    
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE, instead override the generate_background_from_resources
    def _generate_and_save_new_background(self,
                                          location_select_folder_path, camera_select,
                                          target_width, target_height, save_index, threading_enabled):
        
        '''
        Function directly called by parallel process launcher
        Note that this function acts as a wrapper around the 'generate' functions implemented by subclasses,
        and handles some of the bookkeeping needed to properly handle the newly generated background image.
        '''
        
        # Delay a small amount to help ensure newest capture is saved
        if threading_enabled:
            sleep(4.0)
        
        # Set up generator to grab captures that are available. Bail if there aren't any
        num_captures, capture_image_iter = load_background_captures_iter(location_select_folder_path, camera_select)
        if num_captures == 0:
            self.log("Error: Trying to generate background but no captures available")
            return
        
        # Set up generator to grab existing generated images that are available. Bail if there aren't any
        num_generates, generate_image_iter = load_background_generates_iter(location_select_folder_path, camera_select)
        if num_generates == 0:
            self.log("Error: Trying to generate background but no generates available")
            return
        
        t1 = perf_counter()
        # Call subclassed generation function and get return result to pass on to the pipe
        # (Helps hide the piping logic from the subclass implementation)
        new_background_image = self.generate_background_from_resources(num_captures,
                                                                       capture_image_iter,
                                                                       num_generates,
                                                                       generate_image_iter,
                                                                       target_width,
                                                                       target_height)
        t2 = perf_counter()
        
        # Log timing
        self.log("Update: BG Generation took {:.0f} ms".format(1000 * (t2 - t1)))
        
        # Save the newly generated image, assuming it's valid and of the right shape
        valid_image = (new_background_image is not None)
        if valid_image:
            new_height, new_width = new_background_image.shape[0:2]
            wrong_width = (new_width != target_width)
            wrong_height = (new_height != target_height)
            if not (wrong_width or wrong_height):
                save_generated_image(location_select_folder_path, camera_select, new_background_image, save_index)
        
        return
    
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE
    def _save_report_data(self, background_image_data, current_frame_index, current_epoch_ms, current_datetime):

        ''' Function which handles saving of image & metadata for reporting (resource data is saved elsewhere) '''
        
        # Generate metadata for the given timing
        background_metadata = create_image_metadata(current_frame_index, current_epoch_ms, current_datetime)
        
        # Get (unique!) file name and have the report saver handle the i/o
        background_file_name = background_metadata["_id"]
        self._report_data_saver.save_data(file_save_name_no_ext = background_file_name,
                                          image_data = background_image_data,
                                          metadata_dict = background_metadata,
                                          jpg_quality_0_to_100 = self._jpg_quality_0_to_100)
        
        return background_metadata
    
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE
    def _save_capture_data(self, capture_image_data):
        
        ''' Function which handles saving of captures images as resource data '''
        
        # Update capture counter & get index to use for naming save file
        self._capture_counter.update_count()
        next_save_index = self._capture_counter.get_current_count()
        
        # Have the resource saver handle the file i/o
        self._capture_data_saver.save_data(file_save_name_no_ext = next_save_index,
                                           image_data = capture_image_data,
                                           png_compression_0_to_9 = self._png_compression_0_to_9)
        
        return
    
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE
    def _load_newest_background(self, target_width, target_height):
        
        '''
        Helper function which loads the newest available background, with a check on the target dimensions
        '''
        
        # Load image data
        loaded_background_image = load_newest_generated_background(self.location_select_folder_path, self.camera_select)
        if loaded_background_image is None:
            error_msg = "Error loading background data!"
            self.log(error_msg)
            raise ValueError(error_msg)
        
        # Make sure the background shape is correct
        loaded_height, loaded_width = loaded_background_image.shape[0:2]
        wrong_width = (loaded_width != target_width)
        wrong_height = (loaded_height != target_height)
        if wrong_width or wrong_height:
            error_msg_list = ["Loaded background has the wrong dimensions!",
                              "  Required: {} x {}".format(loaded_width, loaded_height),
                              "    Loaded: {} x {}".format(target_width, target_height)]
            self.log_list(error_msg_list)
            error_msg = "\n".join(error_msg_list)
            raise AttributeError(error_msg)
        
        return loaded_background_image
    
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE
    def _trigger_load_new_background(self):
        
        '''
        Function used to check if we need to load a newly available background images 
        create from the parallel generating function
        
        Returns:
            need_to_load_new_background (boolean)
        '''
        
        # Initialize output
        need_to_load_new_background = False
        
        # Load if we don't have a current background
        if self._current_background_image is None:
            need_to_load_new_background = True
            return need_to_load_new_background
        
        # If the parallel process doesn't exist, we don't need to load anything
        if self._parallel_process is None:
            return need_to_load_new_background
        
        # If the parallel process exists,  we'll want to load when it's finished
        if not self._parallel_process.is_alive():
            
            # Try to give feedback in case of errors
            process_exit_code = self._parallel_process.exitcode
            process_finished_successfully = (process_exit_code == 0)
            if not process_finished_successfully:
                error_msg_list = ["ERROR:",
                                  "Parallel background generation exited with an error!",
                                  "  Got exit code: {}".format(process_exit_code)]
                self.log_list(error_msg_list)
                self._parallel_process.terminate()
            
            # Wait for the process to join, then delete the reference to it
            self._parallel_process.join(timeout = 1)
            self._parallel_process = None
            need_to_load_new_background = process_finished_successfully
        
        return need_to_load_new_background
    
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE. Instead, use 'set_capture_period(...)' function to change timing
    def _trigger_capture(self, input_frame, current_epoch_ms):
        
        '''
        Function used to trigger frame captures! Handles capture saving if needed
        
        Returns:
            need_new_capture (boolean)
        '''
        
        # Check if we should save the current frame or not
        need_new_capture = self._capture_timer.check_trigger(current_epoch_ms)
        if need_new_capture:
            self._wait_for_parallel_process()
            self._save_capture_data(input_frame)
        
        return need_new_capture
    
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE. Instead, use 'set_generate_trigger(...)' to change timing
    def _trigger_generate(self, new_capture_saved):
        
        '''
        Function used to trigger background generation! Must return only a boolean.
        This function is not responsible for generating the actual background image data,
        it is only used to signal that generation should begin.
        
        Returns:
            need_new_generate (boolean)
        '''
        
        # Only consider generating a new background after a new capture has been saved
        need_new_generate = self._generate_trigger.update_count() if new_capture_saved else False
        if need_new_generate:
            self._wait_for_parallel_process()
            self._start_new_background_generation()
        
        return need_new_generate
    
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE
    def _wait_for_parallel_process(self):
        
        '''
        Function which blocks execution until the parallel process (generating background) is finished
        --> Intended to be used to protect the state of the captures/generated file system while the
            background generation is running
        '''
        
        # Wait for any existing processes to finish
        needed_to_wait = False
        process_exists = (self._parallel_process is not None)
        if process_exists:
            needed_to_wait = (self._parallel_process.is_alive())
            if needed_to_wait:
                self.log_list(["Warning: Blocking execution until parallel process finishes....",
                               "--> This only happens if either the background generation is being",
                               "    called too often, or if it takes too long. May want to reduce",
                               "    background capture/generation frequency"])
                self._parallel_process.join()        
        
        return needed_to_wait
    
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE
    def _start_new_background_generation(self):
        
        '''
        Function used to 'set off' a parallel process that generates a new background image
        Note that the parallel process is responsible for saving the background image!
        '''
        
        # Update counter
        self._generate_counter.update_count()
        
        # For clarity
        close_when_main_process_closes = True
        video_width, video_height = self.video_wh
        threading_saving_enabled = self.threaded_saving_enabled
        next_save_index = self._generate_counter.get_current_count()
        
        # Bundle process arguments for convenience
        proc_kwargs = {"location_select_folder_path": self.location_select_folder_path,
                       "camera_select": self.camera_select,
                       "target_width": video_width,
                       "target_height": video_height,
                       "save_index": next_save_index,
                       "threading_enabled": threading_saving_enabled}
        
        # Set off the parallel background generation process
        self._parallel_process = Process(name = self._parallel_process_name,
                                         target = self._generate_and_save_new_background,
                                         kwargs = proc_kwargs,
                                         daemon = close_when_main_process_closes)
        self._parallel_process.start()
        
        # Forcefully wait for the process if we're not running threaded saving
        # (i.e. on a file) to enforce deterministic timing
        if not threading_saving_enabled:
            self._parallel_process.join()
        
        return
    
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE
    def _initialize_report_data_saver(self):
        
        ''' Helper function used to set/reset the report data saving object with new settings '''
        
        return Background_Report_Data_Saver(self.location_select_folder_path,
                                            self.camera_select,
                                            self.report_saving_enabled,
                                            self.threaded_saving_enabled)
    
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE
    def _initialize_capture_data_saver(self):
        
        ''' Helper function used to set/reset the resource data saving object with new settings '''
        
        return Background_Resources_Data_Saver(self.location_select_folder_path,
                                               self.camera_select,
                                               self.resource_saving_enabled,
                                               self.threaded_saving_enabled)
    
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


