#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Jun 25 15:33:01 2020

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

from local.configurables.configurable_template import Stations_Configurable_Base


# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes


class Reference_Station(Stations_Configurable_Base):
    
    # .................................................................................................................
    
    def __init__(self, station_name, location_select_folder_path, camera_select, video_wh, *, file_dunder):
        
        # Handle missing station names (i.e. when creating new station entries)
        station_name = "Unnamed Station" if station_name is None else station_name
        
        # Inherit from base class
        super().__init__(station_name, location_select_folder_path, camera_select, video_wh, file_dunder = file_dunder)
        
        # Allocate storage for storing current dataset
        self._latest_one_frame_result_for_config = None
        self._station_dataset = []
        
        # Allocate storage for holding a copy of the background image
        self._current_background_image = None
    
    # .................................................................................................................
    
    # MUST OVERRIDE
    def close(self, final_frame_index, final_epoch_ms, final_datetime):
        
        ''' Function called after video processing completes or is cancelled early '''
        
        raise NotImplementedError("Must implement a close() function for {}".format(self.class_name))
    
    # .................................................................................................................
    
    # MAY OVERRIDE. Be sure to clear the existing dataset!
    def reset(self):
        
        ''' Function called every time video processing rewinds or jumps around in time. Mostly for configuration '''
        
        # Wipe out actual dataset
        self._clear_dataset_in_place()
        
        return
    
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE. Instead override the process_one_frame() function
    def run(self, video_frame, background_image, background_was_updated,
            current_frame_index, current_epoch_ms, current_datetime):
        
        '''
        Main function called during run-time
        Gets called for every video frame.
        Main job is to process pixel/timing data in one or more stations.
        
        Input:
            video_frame -> (Color frame data) A raw frame direct from the video capture
            
            background_image -> (Image data) Current background image data
            
            background_was_updated -> (Boolean) If true, the provided background_image was just updated
            
            current_frame_index -> (Integer) Timing data
            
            current_epoch_ms -> (Integer) Timing data
            
            current_datetime -> (Datetime object) Timing data
        
        Returns:
            Nothing
        '''
        
        # Update stored background data, if needed
        if background_was_updated:
            self._current_background_image = background_image
            self.process_new_background_image(background_image)
        
        # Process the current frame with timing info if needed
        one_frame_result = self.process_one_frame(video_frame, current_frame_index, current_epoch_ms, current_datetime)
        
        # Store the processed result
        self._latest_one_frame_result_for_config = one_frame_result
        self._store_one_frame_result(one_frame_result)
        
        return
    
    # .................................................................................................................
    
    # SHOULD OVERRIDE
    def process_one_frame(self, frame, current_frame_index, current_epoch_ms, current_datetime):
            
        '''
        Function used to process a single frame of data (along with timing information if needed)
        Note that the output can be any format (single integer, float, tuple, list etc.)
        as long as it is json-serializable (can't use numpy arrays directly!)
        
        Also note that each output will be appended to a list,
        which will eventually be output as a block representing results over a period of time.
        
        Inputs:
            frame -> (Color frame data) A raw frame direct from the video capture
            
            current_frame_index -> (Integer) Timing data
            
            current_epoch_ms -> (Integer) Timing data
            
            current_datetime -> (Datetime object) Timing data
        
        Outputs:
            one_frame_result
        '''    
        
        # Reference just returns a counting sequence
        one_frame_result = current_frame_index % 10
        
        return one_frame_result
    
    # .................................................................................................................
    
    # MAY OVERRIDE
    def post_process_output_data(self, current_dataset_list):
        
        '''
        Function used to perform any post-processing on a block of data before saving
        Can be used to apply smoothing/filter out noise for example
        Intended for use on processing that can't be done sample-by-sample in real-time
        
        Inputs:
            current_dataset_list -> (List) The current data about to be saved
        
        Outputs:
            post_processed_data_list -> (List) The post-processed data to be saved
        '''
        
        # By default, does no post-processing, so just acts as a passthru
        return current_dataset_list
    
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE
    def output_data_list(self):
        
        '''
        Function which is responsible for outputting the dataset when requested (for saving) 
        These requests are trigger by the station bundler
        
        Note that the internal dataset storage is cleared after every output!
        
        Inputs:
            Nothing!
        
        Outputs:
            post_processed_data_list
        '''
        
        # Get current dataset (list of 'one frame results')
        current_dataset_list = self._get_dataset()
        
        # Apply any post-processing, if needed
        post_processed_data_list = self.post_process_output_data(current_dataset_list)
        
        # Clear internal data storage so we can collecting new data for the next output update
        self._clear_dataset()
        
        return post_processed_data_list
    
    # .................................................................................................................
    
    # MAY OVERRIDE
    def process_new_background_image(self, new_background_image):
        
        '''
        Function used to apply any required processing to newly generated background images.
        For example, resizing/blurring.
        This function is only called once, when a background updates.
        
        Note: Any results must be saved internally! Processed background data is not managed automatically
        
        Inputs:
            new_background_image -> (Image data) A new background image to be processed
        
        Outputs:
            Nothing!
        '''
        
        # Reference does nothing with new background image data...
        
        return
    
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE
    def get_current_background(self):
        
        '''
        Simple function used to access internal background image data, without targeting variable directly
        Note this function isn't used anywhere by default, it is only made available in case station implementations
        need access to the current background image!
        
        Inputs:
            Nothing!
        
        Outputs:
            current_background_image
        '''
        
        return self._current_background_image
    
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE
    def _store_one_frame_result(self, one_frame_result):
        
        '''
        Generic function used to accumulate single-frame results
        If the dataset type is changed (from the default list type)
        this function can be overriden to maintain consistent behavior
        '''
        
        self._station_dataset.append(one_frame_result)
        
        return
    
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE
    def _get_dataset(self):
        
        '''
        Generic function used to get the current dataset.
        If the dataset type is changed (from the default list type)
        this function can be override to maintain consistent behavior
        '''
        
        return self._station_dataset
    
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE
    def _update_dataset(self, new_station_data):
        
        '''
        Generic function used to add new single-frame entries to the current dataset.
        If the dataset type is changed (from the default list type)
        this function can be override to maintain consistent behavior
        '''
        
        self._station_dataset.append(new_station_data)
        
        return
    
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE
    def _clear_dataset(self):
        
        '''
        Generic function used to clear the dataset, but not in-place
        (in case something else has a reference to the original data)
        '''
        
        self._station_dataset = []
        
        return
    
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE
    def _clear_dataset_in_place(self):
        
        ''' Function used to delete the current dataset in-place, so that all references are also cleared '''
        
        self._station_dataset *= 0
        
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


