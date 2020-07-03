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


from time import sleep

from local.lib.file_access_utils.configurables import unpack_config_data, unpack_access_info

# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes


class Reference_Station(Stations_Configurable_Base):
    
    # .................................................................................................................
    
    def __init__(self, station_name, cameras_folder_path, camera_select, video_wh, *, file_dunder):
        
        # Handle missing station names (i.e. when creating new station entries)
        station_name = "Unnamed Station" if station_name is None else station_name
        
        # Inherit from base class
        super().__init__(station_name, cameras_folder_path, camera_select, video_wh, file_dunder = file_dunder)
        
        # Allocate storage for holding a copy of the background image
        self._current_background_image = None
    
    # .................................................................................................................
    
    # MUST OVERRIDE
    def close(self, final_frame_index, final_epoch_ms, final_datetime):
        
        ''' Function called after video processing completes or is cancelled early '''
        
        raise NotImplementedError("Must implement a close() function for {}".format(self.class_name))
    
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
        
        # Reference does no post-processing, so just acts as a passthru
        return current_dataset_list
    
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
    def ask_to_save(self, configuration_utility_file_dunder):
        
        # Get save data from configurable & add configuration utility info
        save_data_dict = self.get_save_data_dict(configuration_utility_file_dunder)
        access_info_dict, setup_data_dict = unpack_config_data(save_data_dict)
        curr_script_name, _, _ = unpack_access_info(access_info_dict)
        
        # Only save if the saved data has changed
        is_passthrough = ("passthrough" in curr_script_name)
        access_info_changed = (self.loaded_access_info_dict != access_info_dict)
        setup_data_changed = (self.loaded_setup_data_dict != setup_data_dict)
        need_to_save = (access_info_changed or setup_data_changed or is_passthrough)
        
        # Handle feedback for saving or not
        if need_to_save:
            #station_name = self._ask_for_station_name()
            self._ask_to_save_data(save_data_dict)
        else:
            print("", "Settings unchanged!", "Skipping save prompt...", "", sep="\n")
        
        # Delay slightly before closing, may help with strange out-of-order errors on Windows 10?
        sleep(0.25)
        
        pass
    
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

'''
STOPPED HERE
- NEED TO DECIDE ON BASIC STATION CAPTURE IMPLEMENTATION, WHICH NEEDS TO SUPPORT (RE-)CONFIGURATION!
    -> Done? Try implementing counters, avg brightness, avg rgb
'''
