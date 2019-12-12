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

from local.configurables.configurable_template import Externals_Configurable_Base

from local.lib.file_access_utils.reporting import Object_Metadata_Report_Saver

from collections import deque


# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes

class Reference_Object_Capture(Externals_Configurable_Base):
    
    # .................................................................................................................
    
    def __init__(self, cameras_folder_path, camera_select, user_select, task_select, 
                 video_select, video_wh, *, file_dunder):
        
        # Inherit from base class
        super().__init__(cameras_folder_path, camera_select, user_select, task_select, 
                         video_select, video_wh, file_dunder = file_dunder)
        
        # Store state config
        self.metadata_saving_enabled = None
        self.threading_enabled = None
        
        # Allocate storage for configuration data sets (used only to inspect behavior during config)
        self._config_dead_ids = deque([], maxlen = 10)
        
        # Create object to handle saving data
        self.metadata_saver = Object_Metadata_Report_Saver(cameras_folder_path, camera_select, user_select, task_select)
        
        # Set default behaviour states
        self.toggle_metadata_saving(True)
        self.toggle_threading(True)
        
    # .................................................................................................................
    
    def __repr__(self):
        
        repr_strs = ["Object Capture ({})".format(self.script_name),
                     "  Metadata folder: {}".format(self.metadata_saver.relative_data_path())]
        
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
        print("Closing object capture ({})...".format(self.task_select), end="")
        self.run(final_stage_outputs, final_frame_index, final_epoch_ms, final_datetime)
        self.metadata_saver.close()
        print(" Done!")
    
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE
    def toggle_metadata_saving(self, enable_metadata_saving):
        
        ''' Function used to disable metadata saving. Useful during testing/configuration '''
        
        self.metadata_saving_enabled = enable_metadata_saving
        self.metadata_saver.toggle_saving(self.metadata_saving_enabled)
        
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE
    def toggle_threading(self, enable_threaded_saving):
        
        ''' 
        Function used to enable or disable threading of image/metadata saving. 
        Mostly useful for testing out functionality (and avoiding complications from threading),
        or otherwise used during file evaluation, to force deterministic save timing
        '''
        
        self.threading_enabled = enable_threaded_saving
        self.metadata_saver.toggle_threading(self.threading_enabled)
        
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE. Instead override modify_metadata(), dying_save_condition()
    def run(self, stage_outputs, current_frame_index, current_epoch_ms, current_datetime):
        
        ''' 
        Main use function!
        Purpose is to take in the tracking results (on a per-task basis) and save object data as needed.
        Also outputs a boolean indicating the existance of on-screen objects
        
        Inputs:
            stage_outputs -> Dictionary. Should be provided from a single task! Each key represents
                             a core-processing stage name (e.g. preprocessor). The values are themselves
                             dictionaries, which labels/data based on the outputs of each stage
                             
            current_frame_index -> Integer. Current frame of the video
            
            current_epoch_ms -> Integer. Current epoch time in milliseconds
            
            current_datetime -> Datetime obj. Current datetime as of each frame. 
                                Interpretation varies based on video source type (running off files vs live-streams)
                                
        Outputs:
            objects_are_in_frame -> Boolean. True if there are any tracked objects on screen
        '''
        
        # Put stage output data in more convenient variables
        tracked_object_dict, dead_id_list = self._get_run_data(stage_outputs)
        
        # Save all objects that are about to lose tracking (dead_ids)
        self._save_dying(tracked_object_dict, dead_id_list, current_frame_index, current_epoch_ms, current_datetime)

        # Clean up any finished saving threads
        self._clean_up()
        
        # Get simple indicator of whether there are currently objects on screen
        objects_are_in_frame = (len(tracked_object_dict) > 0)
        
        return objects_are_in_frame
    
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
        
        ''' Function which splits stage outputs into more convenient variables for use in the run function '''
        
        # Get object dictionary and dead id list so we can grab objects that are disappearing
        tracked_object_dict = stage_outputs.get("tracker", {}).get("tracked_object_dict", {})
        dead_id_list = stage_outputs.get("tracker", {}).get("dead_id_list", [])
        
        return tracked_object_dict, dead_id_list
    
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE. Instead override dying_save_condition()
    def _save_dying(self, tracked_object_dict, dead_id_list,
                     current_frame_index, current_epoch_ms, current_datetime):
        
        ''' Function which handles the triggering of metadata-saving for dying objects '''
        
        # Save any object that is about to be removed from tracking
        for each_id in dead_id_list:
            
            # Grab object reference so we can access it's data
            obj_ref = tracked_object_dict.get(each_id)
            obj_metadata = self._get_object_metadata(obj_ref)
            
            # Check if we need to save this object
            need_to_save_object = self.dying_save_condition(obj_metadata,
                                                            current_frame_index, current_epoch_ms, current_datetime)
            
            # If we get here, generate the save name & save the data!
            if need_to_save_object:
                save_name = self._create_save_name(each_id)
                self._save_object_metadata(save_name, obj_metadata,
                                           current_frame_index, current_epoch_ms, current_datetime)
                
            # Store data in configuration mode, if needed
            if self.configure_mode:
                new_dead_entry = (each_id, need_to_save_object)
                self._config_dead_ids.append(new_dead_entry)
                
        pass
    
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE
    def _unwarp_metadata(self, obj_metadata):
        
        ''' 
        Function which maps object metadata back into the original frame orientation.
        This is important to ensure object data matches up with snapshot data, which is itself not-warped!
        '''
        
        # Haven't figured out a good way to handle this yet... So do nothing
        
        return obj_metadata
    
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE
    def _save_object_metadata(self, save_name, object_metadata,
                              current_frame_index, current_epoch_ms, current_datetime):
        
        ''' Function which handles the actual saving of object metadata '''
        
        # Make any final modifications to the object metadata before saving
        final_object_metadata = self._unwarp_metadata(object_metadata)
        final_object_metadata = self.modify_metadata(final_object_metadata,
                                                     current_frame_index, current_epoch_ms, current_datetime)
        
        # Have the metadata saver handle the actual (possibly threaded) file i/o
        self.metadata_saver.save_json_gz(save_name, final_object_metadata)
        
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE
    def _get_object_metadata(self, object_ref):
        
        ''' Function which grabs object metadata for convenience '''
        
        return object_ref.get_save_data()
    
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE
    def _create_save_name(self, object_id):
        
        '''
        Function for generating object metadata file names. Needs to follow a standard format so other scripts
        can properly interpret the name. Do not change unless absolutely sure!!!
        '''
        
        # Build the final save name (with no file ext)
        save_name = "obj-{}".format(object_id)
        
        return save_name
    
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE
    def _clean_up(self):
        
        ''' Function used to clean up saving threads '''
        
        # Remove any saving threads that have finished
        self.metadata_saver.clean_up()
    
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


