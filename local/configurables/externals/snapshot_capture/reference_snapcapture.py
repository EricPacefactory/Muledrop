#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Sep 11 15:22:46 2019

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

from local.lib.file_access_utils.reporting import Snapshot_Report_Data_Saver, create_image_metadata


# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes

class Reference_Snapshot_Capture(Externals_Configurable_Base):
    
    # .................................................................................................................
    
    def __init__(self, cameras_folder_path, camera_select, user_select, video_select, video_wh, *, file_dunder):
        
        # Inherit from base class
        super().__init__(cameras_folder_path, camera_select, user_select, video_select, video_wh, 
                         file_dunder = file_dunder)
        
        # Store snapshotting config
        self.report_saving_enabled = None
        self.threaded_saving_enabled = None
        self._snapshot_jpg_quality = None
        
        # Allocate storage for reference info
        self.current_day = None
        
        # Allocate storage for most recent snapshot info
        self.latest_snapshot_metadata = None
        
        # Allocate storage for the data saver object which handles file i/o
        self._report_data_saver = None
        
        # Set default behaviour states
        self.toggle_threaded_saving(False)
        self.toggle_report_saving(False)
        self.set_snapshot_quality(25)
        
    # .................................................................................................................
    
    def __repr__(self):
        
        repr_strs = ["Snapshot Capture ({})".format(self.script_name)]
        
        return "\n".join(repr_strs)
    
    # .................................................................................................................
    
    # MUST OVERRIDE
    def reset(self):
        
        ''' Function called every time video processing rewinds or jumps around in time. Mostly for configuration '''
        
        raise NotImplementedError("Must implement a snapshot reset()")
    
    # .................................................................................................................
    
    # MAY OVERRIDE
    def close(self, final_frame_index, final_epoch_ms, final_datetime):
        
        ''' Function called after video processing completes or is cancelled early '''
        
        # Make sure file i/o is finished
        print("Closing snapshot capture...", end = "")
        
        self._logger.log("Closing: Shutting down report data saver...")
        self._report_data_saver.close()
        self._logger.log("Closing: Report saver closed!")
        
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
        Function used to enable or disable threading of data saving. 
        Mostly useful for testing out functionality (and avoiding complications from threading),
        or otherwise used during file evaluation, to force deterministic save timing
        '''
        
        # Re-initialize the saver with new settings
        self.threaded_saving_enabled = enable_threaded_saving
        self._report_data_saver = self._initialize_report_data_saver()
    
    # .................................................................................................................
    
    #SHOULDN'T OVERRIDE
    def set_snapshot_quality(self, snapshot_jpg_quality_0_to_100):
        
        ''' Function used to change the jpg compression quality for all saved snapshots '''
        
        self._snapshot_jpg_quality = snapshot_jpg_quality_0_to_100
    
    # .................................................................................................................
    
    #SHOULD OVERRIDE
    def get_snapshot_wh(self):
        
        ''' 
        Function which returns the size of snapshot frames. 
        Called on startup so that info can be stored per-camera
        '''
        
        raise NotImplementedError("Must implement get_snapshot_wh() function! ({})".format(self.script_name))
        
        # Should return tuple of width/height of the saved snapshots (integer values)
        return (0, 0)
    
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE. Instead override helper functions: trigger_snapshot(), create_snapshot_image()
    def run(self, input_frame, current_frame_index, current_epoch_ms, current_datetime):
        
        '''
        Main function called during run-time
        Gets called for every video frame.
        Main job is to determine if the current frame should be saved as a snapshot,
        and if so, save the snapshot image & metadata to disk. 
        
        Returns:
            snapshot_frame_data (nparray), latest_snapshot_metadata (dictionary)
        '''
        
        # Initialize outputs
        snapshot_frame_data = None
        latest_snapshot_metadata = self.latest_snapshot_metadata
        
        # Check if we need to save the current frame as a snapshot
        need_new_snapshot = self.trigger_snapshot(input_frame, current_frame_index, current_epoch_ms, current_datetime)
        if not need_new_snapshot:
            return snapshot_frame_data, latest_snapshot_metadata
        
        # ////////////////////////////////////////////////////
        #   *** If we get here, we're saving a snapshot! ***
        # ////////////////////////////////////////////////////
        
        # Create snapshot image from the input frame data
        snapshot_frame_data = self.create_snapshot_image(input_frame)
        
        # Trigger saving of data
        latest_snapshot_metadata = self._save_report_data(snapshot_frame_data,
                                                          current_frame_index, current_epoch_ms, current_datetime)
        
        # Clean up any finished saving threads & save newest metadata internally
        self.latest_snapshot_metadata = latest_snapshot_metadata
        
        return snapshot_frame_data, latest_snapshot_metadata
    
    # .................................................................................................................
    
    # SHOULD OVERRIDE. Use this function to set conditions for when snapshots are taken
    def trigger_snapshot(self, input_frame, current_frame_index, current_epoch_ms, current_datetime):
        
        '''
        Function used to trigger snapshots! Must return only a boolean.
        This function is not responsible for saving/capturing the actual snapshot data, 
        it is only used to signal that the current frame should be saved.
        
        Returns:
            need_new_snapshot (boolean)
        '''
        
        # Reference won't ever save a snapshot, though this shouldn't actually be used!
        return False
    
    # .................................................................................................................
    
    # MAY OVERRIDE. Can use to modify the saved image (e.g. scaling)
    def create_snapshot_image(self, snapshot_frame):
        
        ''' Function which allows for image manipulations prior to saving as a snapshot '''
        
        # For reference implementation, save the image as-is, no scaling or other modifications
        return snapshot_frame
    
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE
    def _save_report_data(self, snapshot_image_data, current_frame_index, current_epoch_ms, current_datetime):
        
        ''' Function which handles saving of image & metadata '''
        
        # Generate metadata for the given timing
        snapshot_metadata = create_image_metadata(current_frame_index, current_epoch_ms, current_datetime)
        
        # Get (unique!) file name and have the report saver handle the i/o
        snapshot_file_name = snapshot_metadata["_id"]
        self._report_data_saver.save_data(file_save_name_no_ext = snapshot_file_name,
                                          image_data = snapshot_image_data,
                                          metadata_dict = snapshot_metadata,
                                          jpg_quality_0_to_100 = self._snapshot_jpg_quality)
        
        return snapshot_metadata
    
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE
    def _initialize_report_data_saver(self):
        
        ''' Helper function used to set/reset the data saving object with new settings '''
        
        return Snapshot_Report_Data_Saver(self.cameras_folder_path, 
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


