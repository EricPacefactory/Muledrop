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

from time import perf_counter

from local.configurables.configurable_template import Externals_Configurable_Base

from local.lib.timekeeper_utils import utc_time_to_isoformat_string, utc_datetime_to_epoch_ms

from local.lib.file_access_utils.runtime_read_write import Parallel_Function, create_new_thread_lock
from local.lib.file_access_utils.reporting import Image_Report_Saver, Image_Metadata_Report_Saver
from local.lib.file_access_utils.resources import Image_Resources_Saver, Image_Resources_Loader


# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes

class Reference_Background_Capture(Externals_Configurable_Base):
    
    # .................................................................................................................
    
    def __init__(self, cameras_folder_path, camera_select, user_select, video_select, video_wh,
                 *, file_dunder, frame_capture_class = None, background_creator_class = None):
        
        '''
        Class which implements all background capture/generation functionality
        Should be inherited and overridden in actual use!
        
        To inherit, call:
            
            super().__init__(cameras_folder_path, camera_select, user_select, video_select, video_wh,
                             file_dunder = __file__,
                             frame_capture_class = <Frame_Capture_Class>,
                             background_creator_class = <Background_Creator_Class>)
            
        Then override functions as needed. Check reference functions for details.
        Most likely will want to override frame_capture_class and background_creator_class implementations
        '''
        
        # Inherit from base class
        task_select = None
        super().__init__(cameras_folder_path, camera_select, user_select, task_select, 
                         video_select, video_wh, file_dunder = file_dunder)
        
        # Allocate storage for shared background capture variables
        self.max_capture_count = None
        self.max_generated_count = None
        
        # Set saving compression/quality
        self._png_compression = None
        self._jpg_report_quality = None
        
        # Store state config
        self.report_saving_enabled = None
        self.resource_saving_enabled = None
        self.threading_enabled = None
        
        # Create shared lock used to prevent simulataneous data access across multiple threads
        self.thread_lock = create_new_thread_lock()
        
        # Use reference capture/generator if not provided (can't use as defaults for some reason?)
        if frame_capture_class is None:
            frame_capture_class = Reference_Background_Capture
        if background_creator_class is None:
            background_creator_class = Reference_Background_Creator
        
        # Store capture & generator objects
        resource_args = (cameras_folder_path, camera_select, user_select, video_select, video_wh)
        self.frame_capturer = frame_capture_class(*resource_args, lock = self.thread_lock)
        self.background_creator = background_creator_class(*resource_args, lock = self.thread_lock)
        
        # Set default behaviour states
        self.toggle_report_saving(True)
        self.toggle_resource_saving(True)
        self.toggle_threading(True)
        self.set_max_capture_count(10)
        self.set_max_generated_count(5)
        self.set_png_compression(0)
        self.set_jpg_quality(25)
        
    # .................................................................................................................
    
    def __repr__(self):
        
        repr_strs = ["Background capture ({})".format(self.script_name)]
        
        script_name, class_name, resource_relative_path = self.frame_capturer.ask_info()
        repr_strs += ["  Frame Capture: {} ({})".format(class_name, script_name),
                     "    Resource path: {}".format(resource_relative_path)]
        
        repr_strs += [""]
        
        script_name, class_name, resource_relative_path, report_rel_path = self.background_creator.ask_info()
        repr_strs += ["  Generator: {} ({})".format(class_name, script_name),
                     "    Resource path: {}".format(resource_relative_path),
                     "      Report path: {}".format(report_rel_path)]
        
        return "\n".join(repr_strs)
    
    # .................................................................................................................
    
    # MAY OVERRIDE
    def reset(self):
        
        ''' Function called every time video processing rewinds or jumps around in time. Mostly for configuration '''
        
        self.frame_capturer.reset()
        self.background_creator.reset()
        
    # .................................................................................................................
    
    # MAY OVERRIDE
    def close(self, final_frame_index, final_time_sec, final_datetime):
        
        ''' Function called after video processing completes or is cancelled early '''
        
        # Make sure file i/o is finished
        print("Closing background capture...", end="")
        self.frame_capturer.close()
        self.background_creator.close()
        print(" Done!")
        
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE
    def toggle_report_saving(self, enable_report_saving):
        
        ''' Function used to disable report saving. Useful during testing/configuration '''
        
        self.report_saving_enabled = enable_report_saving
        self.background_creator.toggle_report_saving(enable_report_saving)
        
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE
    def toggle_resource_saving(self, enable_resource_saving):
        
        ''' Function used to disable resources saving. Useful during testing/configuration '''
        
        self.resource_saving_enabled = enable_resource_saving
        self.frame_capturer.toggle_saving(enable_resource_saving)
        self.background_creator.toggle_resource_saving(enable_resource_saving)
        
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE
    def toggle_threading(self, enable_threaded_saving):
        
        ''' 
        Function used to enable or disable threading of image/metadata saving. 
        Mostly useful for testing out functionality (and avoiding complications from threading),
        or otherwise used during file evaluation, to force deterministic save timing
        '''
        
        self.threading_enabled = enable_threaded_saving
        self.frame_capturer.toggle_threading(enable_threaded_saving)
        self.background_creator.toggle_threading(enable_threaded_saving)
        
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE
    def set_max_capture_count(self, max_capture_count):
        
        ''' Function for modifying the maximum number of captures to save. Shared for all subclasses '''
        
        self.max_capture_count = max_capture_count
        self.frame_capturer.set_maximum_captures(max_capture_count)
        
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE
    def set_max_generated_count(self, max_generated_count):
        
        ''' Function for modifying the maximum number of generated images to save. Shared for all subclasses '''
        
        self.max_generated_count = max_generated_count
        self.background_creator.set_maximum_generated(max_generated_count)
        
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE
    def set_png_compression(self, new_png_compression_0_to_9):
        
        ''' Function for modifying the png compression used to save captures & generated background '''
        
        self._png_compression = new_png_compression_0_to_9        
        self.frame_capturer.set_capture_compression(new_png_compression_0_to_9)
        self.background_creator.set_generated_compression(new_png_compression_0_to_9)
        
    # .................................................................................................................

    # SHOULDN'T OVERRIDE
    def set_jpg_quality(self, new_jpg_quality_0_to_100):
        
        ''' Function for modifying the jpg quality of generated backgrounds that are saved as report data '''
        
        self._jpg_report_quality = new_jpg_quality_0_to_100
        self.background_creator.set_report_quality(new_jpg_quality_0_to_100)
        
    # .................................................................................................................
    
    # MAY OVERRIDE, but better to override capturer & generator classes!
    def run(self, input_frame, current_frame_index, current_time_sec, current_datetime):
        
        ''' 
        Main function! Used to capture frames from a video source and use them to generate background images 
        Most of the work is handled by frame_capturer & background_creator objects, 
        which have their own run() functions that handle their corresponding responsibilities
        
        Inputs:
            input_frame -> Image data. Current frame data from a video source
            
            current_frame_index -> Integer. Current frame index of the video source
            
            current_time_sec -> Float. Current time elapsed since the video started (in seconds)
            
            current_datetime -> Datetime obj. Interpretation of this object depends on video source (files vs. streams)
            
        Outputs:
            dictionary -> {"video_frame", "bg_frame", "bg_update"}        
        '''
        
        # Trigger capture of frames as needed
        frame_was_captured, number_of_captures, create_capture_generator = \
        self.frame_capturer.run(input_frame, current_frame_index, current_time_sec, current_datetime)
        
        # Trigger generation of new background images as needed
        background_was_updated, background_image = \
        self.background_creator.run(frame_was_captured, number_of_captures, create_capture_generator,
                                    current_frame_index, current_time_sec, current_datetime)
        
        return {"video_frame": input_frame, 
                "bg_frame": background_image,
                "bg_update": background_was_updated}
        
    # .................................................................................................................
    
    def clear_resources(self, enable = True):
        
        # Delete resource data only (ignore reporting)
        if enable:
            print("")
            print("Deleting existing background resources...", end = "")
            self.frame_capturer.clear_resources()
            self.background_creator.clear_resources()
            print(" Done!")
        
    # .................................................................................................................
    
    # MAY OVERRIDE
    def generate_on_startup(self, video_reader, force_generate = False):
        
        ''' Function for generating a starting background, when nothing else is available '''
        
        # First try to load an existing file
        t1 = perf_counter()
        generated_new_background, initial_background_image = \
        self.background_creator._generate_on_startup(video_reader, force_generate)
        t2 = perf_counter()
        
        # Print out generation time (assuming a background was actually generated and not loaded!)
        if generated_new_background:
            print("")
            print("Initial background generation took (ms): {}".format(1000 * (t2 - t1)))
        
        return initial_background_image
    
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE
    def _clean_up(self):
        
        ''' Function used to clean up saving threads '''
        
        # Remove any threads that have finished
        self.frame_capturer._clean_up()
        self.background_creator._clean_up()
   
    # .................................................................................................................
    # .................................................................................................................


# =====================================================================================================================
# =====================================================================================================================


class Reference_Frame_Capture:
    
    # .................................................................................................................
    
    def __init__(self, cameras_folder_path, camera_select, user_select, video_select, video_wh, *, lock = None):
        
        '''
        Class used for capturing frames to use in background image generation 
        Should be inherited and overridden in actual use!
        
        To inherit, call:
            
            super().__init__(cameras_folder_path, camera_select, user_select, video_select, video_wh, lock = None)
            
        Then override functions as needed. Check reference functions for details.
        Most likely need to override capture_condition() and nothing else!
        '''
        
        # Store video info
        self.video_select = video_select
        self.video_wh = video_wh
        
        # Allocate storage for saving variables
        self.maximum_captures = None
        self.capture_compression_0_to_9 = None
        
        # Allocate storage for file i/o config
        self.saving_enabled = None
        self.threading_enabled = None
        
        # Allocate storage for keeping track of the latest capture data
        self._latest_capture_frame = None
        self._latest_capture_index = None
        self._latest_capture_time_sec = None
        self._latest_capture_datetime = None
        self._capture_count = -1
        
        # Create object to handle resource saving/loading
        resource_args = (cameras_folder_path, camera_select, user_select, "backgrounds")
        self.image_saver = Image_Resources_Saver(*resource_args, "captures", lock = lock)
        self.image_loader = Image_Resources_Loader(*resource_args, "captures", lock = lock)
        
        # Set default behaviour states
        self.toggle_saving(True)
        self.toggle_threading(True)
        self.set_maximum_captures(10)
        self.set_capture_compression(0)
        
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE
    def ask_info(self):
        
        ''' Function for providing debugging info about this object '''
        
        script_name = os.path.basename(os.path.abspath(__file__))
        class_name = self.__class__.__name__
        resource_relative_path = self.image_saver.relative_data_path()
        
        return script_name, class_name, resource_relative_path
    
    # .................................................................................................................
    
    # MUST OVERRIDE
    def reset(self):
        raise NotImplementedError("Must implement a reset() for frame capturer ({})".format(self.__class__.__name__))
    
    # .................................................................................................................
    
    # MAY OVERRIDE
    def close(self):
        
        ''' Function called when video processing ends '''
        
        # Clean up file i/o
        self.image_saver.close()
        self.image_loader.close()
        
    # .................................................................................................................
        
    # SHOULDN'T OVERRIDE
    def clear_resources(self):
        self.image_loader.clear_existing_data()
        
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE
    def toggle_saving(self, enable_saving):
        self.saving_enabled = enable_saving
        self.image_saver.toggle_saving(enable_saving)
        
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE
    def toggle_threading(self, enable_threading):
        self.threading_enabled = enable_threading
        self.image_saver.toggle_threading(enable_threading)
        
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE
    def set_maximum_captures(self, maximum_captures):
        self.maximum_captures = maximum_captures
    
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE
    def set_capture_compression(self, capture_compression_0_to_9):
        self.capture_compression_0_to_9 = capture_compression_0_to_9
        
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE
    def create_capture_generator(self, sort_chronologically = True):        
        
        '''
        Function which returns a generator for providing captured images
        When generator is used, it provided images via OpenCv imread() function
        '''
        
        # Get sorted list of capture files to load
        capture_file_path_list = self.image_loader.list_file_paths(sort_chronologically = sort_chronologically,
                                                                   allowable_exts_list = [".png"])
        number_of_captures = len(capture_file_path_list)
        
        # Create generator for loading from the list of file paths
        def capture_image_generator():            
            for each_path in capture_file_path_list:
                yield self.image_loader.load_from_path(each_path)
        
        return number_of_captures, capture_image_generator
        
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE. Instead override capture_condition()
    def run(self, input_frame, current_frame_index, current_time_sec, current_datetime):
        
        ''' 
        Function which handles all logic related to capturing frames for background generation.
        Handles checking for triggers to save captured frames, as well as handling the actual capture/saving
        of those frames. 
        
        Returns a boolean indicating whether the current frame was captured, 
        also returns a function for creating a generator for loading capture image data
        '''
        
        # Check if we need to capture the current frame
        frame_needs_to_be_captured = \
        self.capture_condition(input_frame, current_frame_index, current_time_sec, current_datetime)
        
        # Save the captured frame if needed
        if frame_needs_to_be_captured:
            
            # Record capture event timing & data, so we can re-use it if needed, then save the capture data!
            self._record_capture_event(input_frame, current_frame_index, current_time_sec, current_datetime)
            self._save_capture_png(input_frame, current_frame_index, current_time_sec, current_datetime)
        
        # Provide a function for creating generators for loading capture data
        number_of_captures, create_capture_generator = self.create_capture_generator()
        
        # Get rid of dead threads
        self._clean_up()
        
        return frame_needs_to_be_captured, number_of_captures, create_capture_generator
        
    # .................................................................................................................
    
    # MUST OVERRIDE
    def capture_condition(self, input_frame, current_frame_index, current_time_sec, current_datetime):
        
        ''' Function which decides when a given frame should be captured for background generation purposes '''
    
        # Reference implementation captures a single frame on startup
        frame_needs_to_be_captured = (self._latest_capture_time_sec is None)
    
        return frame_needs_to_be_captured
    
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE
    def _record_capture_event(self, input_frame, current_frame_index, current_time_sec, current_datetime):
        
        ''' Function for keeping track of the latest captured frame data & timing '''
        
        # Store image & timing data
        self._latest_capture_frame = input_frame.copy()
        self._latest_capture_index = current_frame_index
        self._latest_capture_time_sec = current_time_sec
        self._latest_capture_datetime = current_datetime
        self._capture_count = (self._capture_count + 1) % self.maximum_captures
    
    # .................................................................................................................
    
    # MAY OVERRIDE, but shouldn't be necessary unless using some special naming lookup
    def _create_save_name(self, current_frame_index, current_time_sec, current_datetime):
        
        ''' Function for naming files saved as captures for background generation '''
        
        return "bgcap-{}".format(self._capture_count)
    
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE
    def _save_capture_png(self, input_frame, current_frame_index, current_time_sec, current_datetime):
        
        ''' Function which handles actual saving of capture frame data '''
        
        # Generate the save name
        capture_save_name = self._create_save_name(current_frame_index, current_time_sec, current_datetime)
        
        # Have resource object handle image saving
        self.image_saver.save_png(file_save_name_no_ext = capture_save_name,
                                  image_data = input_frame,
                                  save_compression_0_to_9 = self.capture_compression_0_to_9)
    
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE
    def _clean_up(self):
        
        ''' Function used to clean up saving threads '''
        
        # Remove any saving threads that have finished
        self.image_saver.clean_up()
        self.image_loader.clean_up()
        
    # .................................................................................................................
    # .................................................................................................................


# =====================================================================================================================
# =====================================================================================================================


class Reference_Background_Creator:
    
    # .................................................................................................................
    
    def __init__(self, cameras_folder_path, camera_select, user_select, video_select, video_wh,
                 *, lock = None):
        
        '''
        Class used for generating new background images 
        Should be inherited and overridden in actual use!
        
        To inherit, call:
            
            super().__init__(cameras_folder_path, camera_select, user_select, video_select, video_wh, lock = None)
            
        Then override functions as needed. Check reference functions for details.
        Most likely want to override generation_function() and generation_condition() functions
        '''
        
        # Store video info
        self.video_select = video_select
        self.video_wh = video_wh
        
        # Allocate storage for saving variables
        self.maximum_generated = None
        self.generated_compression_0_to_9 = None
        self.generated_report_quality_0_to_100 = None
        
        # Allocate storage for file i/o config
        self.resource_saving_enabled = None
        self.report_saving_enabled = None
        self.threading_enabled = None
        
        # Allocate storage for keeping track of the latest generated data
        video_width, video_height = video_wh
        self._latest_generated_frame = None
        self._latest_generated_index = None
        self._latest_generated_time_sec = None
        self._latest_generated_datetime = None
        self._generated_count = -1
        
        # Create object to manage parallel background image creation
        self.currently_generating = False
        self.parallel_generation = Parallel_Function(function_to_thread = self.generation_function,
                                                     lock = lock)
        
        # Create objects to handle saving reporting data
        report_saver_args = (cameras_folder_path, camera_select, user_select, "backgrounds")
        self.report_image_saver = Image_Report_Saver(*report_saver_args, lock = lock)
        self.report_meta_saver = Image_Metadata_Report_Saver(*report_saver_args, lock = lock)
        
        # Create object to handle resource saving/loading
        resource_args = (cameras_folder_path, camera_select, user_select, "backgrounds")
        self.resource_image_saver = Image_Resources_Saver(*resource_args, "generated", lock = lock)
        self.resource_image_loader = Image_Resources_Loader(*resource_args, "generated", lock = lock)
        
        # Set default behaviour states
        self.toggle_resource_saving(True)
        self.toggle_report_saving(True)
        self.toggle_threading(True)
        self.set_maximum_generated(10)
        self.set_generated_compression(0)
        self.set_report_quality(25)
        
        
        '''
        STOPPED HERE
        - THEN UPDATE RUN_FILE_COLLECT WITH NEW BACKGROUND GENERATOR
        - NEED TO CHECK INTERACTION WITH PREPROCESSORS/FRAMEPROCESSOR
        - THEN CAN CONSIDER FINALIZING SAVING/LOADING SYSTEMS!?!?!?!
        '''
    
    # .................................................................................................................
    
    # SHOUDLN'T OVERRIDE
    def ask_info(self):
        
        ''' Function for providing debugging info about this object '''
        
        script_name = os.path.basename(os.path.abspath(__file__))
        class_name = self.__class__.__name__
        resource_relative_path = self.resource_image_saver.relative_data_path()
        report_relative_path = self.report_image_saver.relative_data_path()
        
        return script_name, class_name, resource_relative_path, report_relative_path
    
    # .................................................................................................................
    
    # MUST OVERRIDE
    def reset(self):
        raise NotImplementedError("Must implement a reset() for frame creator ({})".format(self.__class__.__name__))
    
    # .................................................................................................................
    
    # MAY OVERRIDE
    def close(self):
        
        ''' Function called when video processing ends '''
        
        # Clean up file i/o
        self.report_image_saver.close()
        self.report_meta_saver.close()        
        self.resource_image_saver.close()
        self.resource_image_loader.close()
        
    # .................................................................................................................
        
    # SHOULDN'T OVERRIDE
    def clear_resources(self):
        self.resource_image_loader.clear_existing_data()
    
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE
    def toggle_resource_saving(self, enable_resource_saving):
        self.resource_saving_enabled = enable_resource_saving
        self.resource_image_saver.toggle_saving(enable_resource_saving)
        
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE
    def toggle_report_saving(self, enable_report_saving):
        self.report_saving_enabled = enable_report_saving
        self.report_image_saver.toggle_saving(enable_report_saving)
        self.report_meta_saver.toggle_saving(enable_report_saving)
        
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE
    def toggle_threading(self, enable_threading):
        self.threading_enabled = enable_threading
        self.parallel_generation.toggle_threading(enable_threading)
        self.resource_image_saver.toggle_threading(enable_threading)
        self.report_image_saver.toggle_threading(enable_threading)
        self.report_meta_saver.toggle_threading(enable_threading)
        
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE
    def set_maximum_generated(self, maximum_generated):
        self.maximum_generated = maximum_generated
    
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE
    def set_generated_compression(self, generated_compression_0_to_9):
        self.generated_compression_0_to_9 = generated_compression_0_to_9
    
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE 
    def set_report_quality(self, generated_report_quality_0_to_100):
        self.generated_report_quality_0_to_100 = generated_report_quality_0_to_100

    # .................................................................................................................

    # SHOULDN'T OVERRIDE. Instead override generate_condition(), generation_function()
    def run(self, frame_was_captured, number_of_captures, create_capture_generator, 
            current_frame_index, current_time_sec, current_datetime):
        
        ''' 
        Function which handles all logic related to generating new background images.
        Handles checking for triggers to start generating a new background.
        Also handles lookup of completed background processing (which it should handle in parallel)
        
        Inputs:
            frame_was_captured -> Boolean. Indicates whether the current frame was captured.
                                  Provided just in case it is used to trigger new background generation.
            
            number_of_captures -> Integer. Indicates how many captures are available in the capture data generator
            
            create_capture_data_generator -> Function. When called, must return a python generator 
                                             which loads captured images (in newest-first order)
                                  
            current_frame_index -> Integer. Indicates current frame of video source
            
            current_time_sec -> Float. Indicates amount of time elapsed since video start (in seconds)
            
            current_datetime -> Datetime object. Stores datetime information. 
                                Interpretation varies depending on video source (files vs streams)
                                
        Returns:
            background_was_generated -> Boolean. True whenever a new background is generated
            
            background_image -> HxWx3 numpy array. Most up-to-date background image. Provides newest
                                generated background whenever the background_was_generated flag is true.
                                Must always output a valid image, even if the background wasn't just updated.
        '''
        
        
        # Check if a new background has finished generating
        currently_generating, background_was_generated, background_image = self._check_for_background_updates()
        
        # Check if we need to generate a new background image
        background_needs_to_be_generated = \
        self.generation_condition(currently_generating, frame_was_captured,
                                  current_frame_index, current_time_sec, current_datetime)
        
        # Trigger background generation if needed (generation is non-blocking!)
        if background_needs_to_be_generated:
            print("New background needs to be generated!")
            capture_data_as_generator = create_capture_generator()
            self.parallel_generation(number_of_captures, capture_data_as_generator)
            
        # Record generation event & save the data
        if background_was_generated:
            print("New background generated!")
            self._record_generated_event(background_image, current_frame_index, current_time_sec, current_datetime)
            self._save_generated_png(background_image, current_frame_index, current_time_sec, current_datetime)
            self._save_generated_report_data(background_image, current_frame_index, current_time_sec, current_datetime)
            
        # Get rid of dead threads
        self._clean_up()
        
        return background_was_generated, background_image
    
    # .................................................................................................................
    
    # MUST OVERRIDE
    def generation_condition(self, currently_generating, frame_was_captured,
                             current_frame_index, current_time_sec, current_datetime):
        
        ''' Function which decides when a new background image should be generated '''
    
        # Reference implementation generates a single image on startup
        no_existing_data = (self._latest_generated_time_sec is None)
        background_needs_to_be_generated = (no_existing_data and not currently_generating)
    
        return background_needs_to_be_generated
    
    # .................................................................................................................
    
    # MUST OVERRIDE
    def generation_function(self, number_of_captures, capture_data_generator):
        
        ''' Function which implements all the logic needs to generate a new background. Returns the new image '''
        
        # Reference implementation generates a useless blank background frame
        video_width, video_height = self.video_wh
        new_background_image = np.zeros((video_height, video_width, 3), dtype=np.uint8)
        
        return new_background_image
    
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE
    def _check_for_background_updates(self):
        
        ''' 
        Function which actually looks for newly generated background, 
        potentially coming from a parallel generation thread
        Must return a boolean indicating whether a new image was found, and the latest background image available
        '''
        
        # Default to using the current background frame data
        background_image = self._latest_generated_frame
        
        # If the generator object has new data, grab it and provide that as the new background data
        new_background_available = self.parallel_generation.data_is_available()        
        if new_background_available:            
            background_image = self.parallel_generation.get_new_data(auto_clean_up = False)
        
        # Finally, check if the generator is in the middle of generating new data (used to avoid duplicate threads)
        currently_generating = self.parallel_generation.is_working()
        
        return currently_generating, new_background_available, background_image
    
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE
    def _record_generated_event(self, new_background_image, current_frame_index, current_time_sec, current_datetime):
        
        ''' Function for keeping track of the latest generated frame data & timing '''
        
        # Store image & timing data
        self._latest_generated_frame = new_background_image.copy()
        self._latest_generated_index = current_frame_index
        self._latest_generated_time_sec = current_time_sec
        self._latest_generated_datetime = current_datetime
        self._generated_count = (self._generated_count + 1) % self.maximum_generated
    
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE
    def _generate_on_startup(self, video_reader, force_generate = False):
        
        # Try to load an existing file
        existing_background_path_list = self.resource_image_loader.list_file_paths(allowable_exts_list = [".png"])
        data_exists = (len(existing_background_path_list) > 0)
        if data_exists and (not force_generate):
            
            # Some feedback about loading an existing background image
            print("", "Found existing background image! Loading...", sep = "\n")
            generated_new_background = False
            
            # Get the newest background file available, load it, and make sure to record it as a generation event
            newest_background_path = existing_background_path_list[0]
            background_image = self.resource_image_loader.load_from_path(newest_background_path)
            self._record_generated_event(background_image, None, None, None)
            
            
            
            return generated_new_background, background_image
        
        # Switch between different ways of grabbing the first frames, depending on video source type
        video_type = video_reader.video_type
        if video_type == "file":
            get_frame_set_func = self._generate_from_file_startup
        elif video_type == "rtsp":
            get_frame_set_func = self._generate_from_rtsp_startup
        else:
            error_msgs = ["Trying to generate initial background file.",
                         "Got unrecognized video type: {}".format(video_type)]
            raise TypeError(" ".join(error_msgs))
            
        # Grab initial frames for generating the background & convert to a python generator object
        frame_set_list, final_frame_index, final_time_sec, final_datetime = get_frame_set_func(video_reader)
        number_of_captures = len(frame_set_list)
        
        # Create generator out of frame set, so we can pass it in to generation functions
        def create_capture_generator():
            for each_frame in frame_set_list:
                yield each_frame
        
        # Generate a new background frame using the built-in generation function, as if we had captured frames normally
        background_image = self.generation_function(number_of_captures, create_capture_generator())
        generated_new_background = True
        
        # Record generation event
        time_args = (final_frame_index, final_time_sec, final_datetime)
        self._record_generated_event(background_image, *time_args)
        
        # Forcefully save the data, even if saving is disabled, just for startup generation!
        original_resource_save_setting = self.resource_saving_enabled
        self.toggle_resource_saving(True)
        self._save_generated_png(background_image, *time_args)
        self._save_generated_report_data(background_image, *time_args)
        self.toggle_resource_saving(original_resource_save_setting)
        
        # Debugging
        '''
        print("",
              "Start up results",
              "Latest frame index: {}".format(self._latest_generated_index),
              "Latest time (sec): {}".format(self._latest_generated_time_sec),
              "Latest datetime: {}".format(self._latest_generated_datetime), 
              sep="\n")
        '''
        
        return generated_new_background, background_image
        
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE
    def _generate_from_file_startup(self, video_reader):
        
        ''' Function used to grab a set of frames from a file, for generating backgrounds on startup '''
        
        # Configure some processing parameters
        target_file_time_sec = 5.0 * 60.0
        num_file_frames_to_use = 25
        
        # Figure out where to sample frames from
        total_frames = video_reader.total_frames
        video_fps = video_reader.video_fps            
        max_frame_idx = video_fps * target_file_time_sec
        frame_limit = min(max_frame_idx, int(total_frames * 0.9)) - 1
        frame_sample_indices = np.int32(np.round(np.linspace(0, frame_limit, num_file_frames_to_use)))
        
        # Some feedback
        print("", 
              "Generating initial background from file!",
              "  This may take some time...", sep = "\n")
        
        # Grab frames for generating the first background
        starting_frame_index = video_reader.get_current_frame_file()
        frame_set = []
        for each_frame_idx in frame_sample_indices:
            video_reader.set_current_frame(each_frame_idx)
            req_break, frame, current_frame_index, current_time_sec, current_datetime = video_reader.read()
            frame_set.append(frame)
        
        # Reset the video reader after we're done collecting frames
        video_reader.set_current_frame(starting_frame_index)
        
        return frame_set, current_frame_index, current_time_sec, current_datetime        
    
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE
    def _generate_from_rtsp_startup(self, video_reader):
        
        ''' Function used to grab a set of frames from an rtsp stream, for generating backgrounds on startup '''
            
        print("WARNING: GENERATE BG ON STARTUP NOT TESTED ON RTSP!!!")
        
        # Configure some processing parameters
        target_capture_time_sec = 5.0 * 60.0
        num_capture_frames_to_use = 25
        capture_period_sec = target_capture_time_sec / (num_capture_frames_to_use + 1)
        
        current_time_sec = None
        next_capture_time_sec = -1
        
        # Some feedback
        print("",
              "Generating initial background from rtsp!",
              "  This will take ~{:.1f} mins...".format(target_capture_time_sec / 60.0), sep = "\n")
        
        # Continuously grab frames for generating the first background
        frame_set = []
        while len(frame_set) < num_capture_frames_to_use:
            
            # Read every frame from the stream
            req_break, frame, current_frame_index, current_time_sec, current_datetime = video_reader.read()
            
            # Store a frame every capture period
            if current_time_sec >= next_capture_time_sec:
                frame_set.append(frame)
                next_capture_time_sec = current_time_sec + capture_period_sec
        
        return frame_set, current_frame_index, current_time_sec, current_datetime
    
    # .................................................................................................................
    
    # MAY OVERRIDE, but shouldn't be necessary unless using some special naming lookup
    def _create_resource_save_name(self, current_frame_index, current_time_sec, current_datetime):
        
        ''' Function for naming generated background images (within internal resources folder) '''
        
        return "bggen-{}".format(self._generated_count)
    
    # .................................................................................................................
    
    # MAY OVERRIDE, but shouldn't be necessary unless using some special naming lookup
    def _create_reporting_save_name(self, ms_since_epoch):
        
        ''' Function for naming generated background images for reporting '''
        
        return "bggen-{}".format(ms_since_epoch)
    
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE
    def _save_generated_png(self, background_image, current_frame_index, current_time_sec, current_datetime):
        
        ''' Function which handles actual saving of generated frame data '''
        
        # Create the save name
        generated_save_name = self._create_resource_save_name(current_frame_index, current_time_sec, current_datetime)
        
        # Have resource object handle image saving
        self.resource_image_saver.save_png(file_save_name_no_ext = generated_save_name,
                                           image_data = background_image,
                                           save_compression_0_to_9 = self.generated_compression_0_to_9)
    
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE
    def _save_generated_report_data(self, background_image, current_frame_index, current_time_sec, current_datetime):
        
        ''' Function which creates reporting copies of newly generated background image '''
        
        # Get time as a string for reporting
        bgcap_time_isoformat = utc_time_to_isoformat_string(current_datetime)
        ms_since_epoch = utc_datetime_to_epoch_ms(current_datetime)
        
        # Build reporting file name & metadata
        bgcap_name = self._create_reporting_save_name(ms_since_epoch)
        bgcap_metadata = {"name": bgcap_name,
                          "datetime_isoformat": bgcap_time_isoformat,
                          "frame_index": current_frame_index,
                          "time_elapsed_sec": current_time_sec,
                          "epoch_ms_utc": ms_since_epoch,
                          "video_select": self.video_select,
                          "video_wh": self.video_wh}
        
        # Have reporting object handle image saving
        self.report_image_saver.save_jpg(file_save_name_no_ext = bgcap_name,
                                         image_data = background_image,
                                         save_quality_0_to_100 = self.generated_report_quality_0_to_100)
        
        # Also have reporting object handle the metadata saving
        self.report_meta_saver.save_json_gz(file_save_name_no_ext = bgcap_name,
                                            json_data = bgcap_metadata)        
    
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE
    def _clean_up(self):
        
        ''' Function used to clean up saving threads '''
        
        # Remove any saving threads that have finished
        self.parallel_generation.clean_up()
        self.resource_image_saver.clean_up()
        self.report_image_saver.clean_up()
        self.report_meta_saver.clean_up()
        self.resource_image_loader.clean_up()
        
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


