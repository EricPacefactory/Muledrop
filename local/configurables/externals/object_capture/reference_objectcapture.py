#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Sep 16 12:29:49 2019

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

from local.configurables.configurable_template import Externals_Configurable_Base

from local.lib.file_access_utils.reporting import Object_Report_Data_Saver

from collections import deque


# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes

class Reference_Object_Capture(Externals_Configurable_Base):
    
    # .................................................................................................................
    
    def __init__(self, cameras_folder_path, camera_select, user_select, video_wh,
                 enable_preprocessor_unwarp, unwarp_function,
                 *, file_dunder):
        
        # Inherit from base class
        super().__init__("object_capture",
                         cameras_folder_path, camera_select, user_select, video_wh, file_dunder = file_dunder)
        
        # Store object saving config
        self.report_saving_enabled = None
        self.threaded_saving_enabled = None
        self._json_double_precision = None
        
        # Allocate storage for configuration data sets (used only to inspect behavior during config)
        self._config_dead_ids = deque([], maxlen = 10)
        
        # Allocate storage for the data saver object which handles file i/o
        self._report_data_saver = None
        
        # Set default behaviour states
        self.toggle_threaded_saving(False)
        self.toggle_report_saving(False)
        self.set_json_double_precision(3)
        
        # Store unwarping info
        self.enable_unwarp = enable_preprocessor_unwarp
        self.unwarp_function = unwarp_function
        
    # .................................................................................................................
    
    def __repr__(self):
        
        repr_strs = ["Object Capture ({})".format(self.script_name)]
        
        return "\n".join(repr_strs)
    
    # .................................................................................................................
    
    # MUST OVERRIDE
    def reset(self):
        
        ''' Function called every time video processing rewinds or jumps around in time. Mostly for configuration '''
        
        raise NotImplementedError("Must implement an object capture reset()")
    
    # .................................................................................................................
    
    # MAY OVERRIDE
    def close(self, final_stage_outputs, final_frame_index, final_epoch_ms, final_datetime):
        
        ''' Function called after video processing completes or is cancelled early '''
        
        # Make sure file i/o is finished
        print("Closing object capture...", end="")
        self.run(final_stage_outputs, final_frame_index, final_epoch_ms, final_datetime)
        
        self.log("Closing: Shutting down report data saver...", prepend_empty_line = False)
        self._report_data_saver.close()
        self.log("Closing: Report saver closed!", prepend_empty_line = False)
        
        print(" Done!")
    
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE
    def toggle_report_saving(self, enable_data_saving):
        
        ''' Function used to disable saving. Useful during testing/configuration '''
        
        # Re-initialize the saver with new settings
        self.report_saving_enabled = enable_data_saving
        self._report_data_saver = self._initialize_report_data_saver()
    
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE
    def toggle_threaded_saving(self, enable_threaded_saving):
        
        ''' 
        Function used to enable or disable threading of image/metadata saving. 
        Mostly useful for testing out functionality (and avoiding complications from threading),
        or otherwise used during file evaluation, to force deterministic save timing
        '''
        
        # Re-initialize the saver with new settings
        self.threaded_saving_enabled = enable_threaded_saving
        self._report_data_saver = self._initialize_report_data_saver()
    
    # .................................................................................................................
    
    #SHOULDN'T OVERRIDE
    def set_json_double_precision(self, json_double_precision):
        self._json_double_precision = json_double_precision
    
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE. Instead override modify_metadata(), dying_save_condition()
    def run(self, stage_outputs, current_frame_index, current_epoch_ms, current_datetime):
        
        ''' 
        Main use function!
        Purpose is to take in the tracking results and save object data as needed.
        Also outputs a boolean indicating the existance of on-screen objects
        
        Inputs:
            stage_outputs -> Dictionary. Each key represents a core-processing stage name (e.g. preprocessor).
                             The values are themselves dictionaries, 
                             with labels/data based on the outputs of each stage
                             
            current_frame_index -> Integer. Current frame of the video
            
            current_epoch_ms -> Integer. Current epoch time in milliseconds
            
            current_datetime -> Datetime obj. Current datetime as of each frame. 
                                Interpretation varies based on video source type (running off files vs live-streams)
                                
        Outputs:
            None!
        '''
        
        # Put stage output data in more convenient variables
        tracked_object_dict, dead_id_list = self._get_run_data(stage_outputs)
        
        # Save any object that is about to be removed from tracking (dead_ids)
        for each_id in dead_id_list:
            
            # Grab object reference so we can access it's data
            obj_ref = tracked_object_dict[each_id]
            obj_metadata = obj_ref.get_object_save_data()
            
            # Check if we need to save this object
            need_to_save_object = self.dying_save_condition(obj_metadata,
                                                            current_frame_index, current_epoch_ms, current_datetime)
            
            # If we get here, generate the save name & save the data!
            if need_to_save_object:
                self._save_report_data(obj_metadata, current_frame_index, current_epoch_ms, current_datetime)
            
            # Store data in configuration mode, if needed
            if self.configure_mode:
                new_dead_entry = (each_id, need_to_save_object)
                self._config_dead_ids.append(new_dead_entry)
        
        return
    
    # .................................................................................................................
    
    # MAY OVERRIDE
    def dying_save_condition(self, object_metadata, current_frame_index, current_epoch_ms, current_datetime):
        
        ''' Function which can decide if a dying object should be saved or not '''
        
        # Reference implementation allows all dying objects to be saved.
        
        return True
    
    # .................................................................................................................
    
    # MAY OVERRIDE
    def modify_metadata(self, object_metadata, current_frame_index, current_epoch_ms, current_datetime):
        
        ''' Function for modifying or adding to object metadata before saving '''
        
        # Reference implementation doesn't modify the data
        
        return object_metadata
    
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE
    def _get_run_data(self, stage_outputs):
        
        ''' Helper function which splits stage outputs into more convenient variables for use in the run function '''
        
        # Get object dictionary and dead id list so we can grab objects that are disappearing
        tracker_stage = stage_outputs.get("tracker", {})
        tracked_object_dict = tracker_stage.get("tracked_object_dict", {})
        dead_id_list = tracker_stage.get("dead_id_list", [])
        
        return tracked_object_dict, dead_id_list
    
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE
    def _unwarp_metadata(self, obj_metadata):
        
        ''' 
        Function which maps object metadata back into the original frame orientation.
        This is important to ensure object data matches up with snapshot data, which itself is not-warped!
        '''
        
        # Perform correction on trail data
        orig_xy_array = np.float32(obj_metadata["tracking"]["xy_center"])
        new_xy_array = self.unwarp_function(orig_xy_array)
        obj_metadata["tracking"]["xy_center"] = new_xy_array.tolist()
        
        # Perform correction on every point of every hull
        orig_hull_lists = obj_metadata["tracking"]["hull"]
        orig_hull_arrays = (np.float32(each_hull) for each_hull in orig_hull_lists)
        obj_metadata["tracking"]["hull"] = [self.unwarp_function(each_hull).tolist() for each_hull in orig_hull_arrays]
        
        return obj_metadata
    
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE
    def _save_report_data(self, object_metadata, current_frame_index, current_epoch_ms, current_datetime):
        
        ''' Function which handles the actual saving of object metadata '''
        
        # Unwarp the object metadata, if needed
        if self.enable_unwarp:
            object_metadata = self._unwarp_metadata(object_metadata)
        
        # Make any final modifications to the object metadata before saving
        final_object_metadata = self.modify_metadata(object_metadata,
                                                     current_frame_index, current_epoch_ms, current_datetime)
        
        # Get (unique!) file name and have the report saver handle the i/o
        object_file_name = object_metadata["_id"]
        self._report_data_saver.save_data(file_save_name_no_ext = object_file_name,
                                          metadata_dict = final_object_metadata,
                                          json_double_precision = self._json_double_precision)
        
        return
    
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE
    def _initialize_report_data_saver(self):
        
        ''' Helper function used to set/reset the data saving object with new settings '''
        
        return Object_Report_Data_Saver(self.cameras_folder_path, 
                                        self.camera_select, 
                                        self.user_select,
                                        self.report_saving_enabled,
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


