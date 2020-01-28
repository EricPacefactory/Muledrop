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

from local.lib.common.timekeeper_utils import get_isoformat_string

from local.lib.file_access_utils.reporting import Image_Report_Saver, Image_Metadata_Report_Saver


# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes

class Reference_Snapshot_Capture(Externals_Configurable_Base):
    
    # .................................................................................................................
    
    def __init__(self, cameras_folder_path, camera_select, user_select, video_select, video_wh, *, file_dunder):
        
        # Inherit from base class
        super().__init__(cameras_folder_path, camera_select, user_select, video_select, video_wh, 
                         file_dunder = file_dunder)
        
        # Store snapshotting config
        self.image_saving_enabled = None
        self.metadata_saving_enabled = None
        self.threading_enabled = None
        self._snapshot_jpg_quality = None
        
        # Allocate storage for reference info
        self.current_day = None
        self.snapshot_counter = None
        
        # Allocate storage for most recent snapshot info
        self.latest_snapshot_metadata = None
        
        # Create objects to handle saving data
        saver_args = (cameras_folder_path, camera_select, user_select, "snapshots")
        self.image_saver = Image_Report_Saver(*saver_args)        
        self.image_metadata_saver = Image_Metadata_Report_Saver(*saver_args)
        
        # Set default behaviour states
        self.toggle_image_saving(True)
        self.toggle_metadata_saving(True)
        self.toggle_threaded_saving(True)
        self.set_snapshot_quality(25)
        
    # .................................................................................................................
    
    def __repr__(self):
        
        # Figure out how many snapshots we've already taken
        num_snapshots = self.snapshot_counter
        if not num_snapshots:
            num_snapshots = "no"
        
        repr_strs = ["Snapshot Capture ({})".format(self.script_name),
                     "  Metadata folder: {}".format(self.image_metadata_saver.relative_data_path()),
                     "     Image folder: {}".format(self.image_saver.relative_data_path()),
                     "  ({} snapshots so far)".format(num_snapshots)]
        
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
        print("Closing snapshot capture...", end="")
        self.image_saver.close()
        self.image_metadata_saver.close()
        print(" Done!")
    
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE
    def toggle_image_saving(self, enable_image_saving):
        
        ''' Function used to disable image saving. Useful during testing/configuration '''
        
        self.image_saving_enabled = enable_image_saving        
        self.image_saver.toggle_saving(self.image_saving_enabled)
        
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE
    def toggle_metadata_saving(self, enable_metadata_saving):
        
        ''' Function used to disable metadata saving. Useful during testing/configuration '''
        
        self.metadata_saving_enabled = enable_metadata_saving
        self.image_metadata_saver.toggle_saving(self.metadata_saving_enabled)
        
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE
    def toggle_threaded_saving(self, enable_threaded_saving):
        
        ''' 
        Function used to enable or disable threading of image/metadata saving. 
        Mostly useful for testing out functionality (and avoiding complications from threading),
        or otherwise used during file evaluation, to force deterministic save timing
        '''
        
        self.threading_enabled = enable_threaded_saving
        self.image_saver.toggle_threading(self.threading_enabled)
        self.image_metadata_saver.toggle_threading(self.threading_enabled)
    
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
        
        # Update snapshot metadata, based on timing info
        latest_snapshot_metadata = self._create_snapshot_metadata(current_frame_index,
                                                                  current_epoch_ms,
                                                                  current_datetime)
        
        # Retrieve latest snapshot data
        snapshot_frame_data = self.create_snapshot_image(input_frame)
        
        # Trigger (threaded) saving of data
        self._save_report_data(snapshot_frame_data, latest_snapshot_metadata)
        
        # Clean up any finished saving threads & save newest metadata internally
        self.latest_snapshot_metadata = latest_snapshot_metadata
        return snapshot_frame_data, latest_snapshot_metadata
    
    # .................................................................................................................
    
    #SHOULDN'T OVERRIDE
    def set_snapshot_quality(self, snapshot_jpg_quality_0_to_100):        
        self._snapshot_jpg_quality = snapshot_jpg_quality_0_to_100
    
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
    
    # SHOULDN'T OVERRIDE!
    def _create_snapshot_name(self, ms_since_epoch):
        
        '''
        Function for generating snapshot file names. Needs to follow a standard format so other scripts
        can properly interpret the name. Do not change unless absolutely sure!!!
        '''
                
        return "snap-{}".format(ms_since_epoch)
    
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE
    def _create_snapshot_metadata(self, current_frame_index, current_epoch_ms, current_datetime):
        
        '''
        Function for generate snapshot metadata. Needs to follow a standard format so other scripts
        can properly interpret the data. Do not change unless absolutely sure!!!
        '''
        
        # Roll over snapshot counter & frame index each day, to avoid giant counter numbers
        if current_datetime.day != self.current_day:
            self.current_day = current_datetime.day
            self._reset_counters()
        
        # Get info saved into snapshot metadata
        snapshot_time_isoformat = get_isoformat_string(current_datetime)
        snapshot_count = self.snapshot_counter
        
        # Build reporting file name
        snapshot_name = self._create_snapshot_name(current_epoch_ms)
            
        # Build metadata
        snapshot_metadata = {"name": snapshot_name,
                             "datetime_isoformat": snapshot_time_isoformat,
                             "count": snapshot_count,
                             "frame_index": current_frame_index,
                             "epoch_ms": current_epoch_ms,
                             "video_select": self.video_select,
                             "video_wh": self.video_wh}
        
        # Update snapshot counter
        self.snapshot_counter += 1
        
        return snapshot_metadata
    
    # .................................................................................................................
    
    # MAY OVERRIDE, but be careful to keep track of snapshot counter
    def _reset_counters(self):
        
        ''' Function used to reset counters if needed (e.g. rewinding video files and/or changing real-time dates) '''
        
        # Snapshot counter starts at 1 not 0!
        self.snapshot_counter = 1
    
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE
    def _save_report_data(self, snapshot_image_data, snapshot_metadata):
        
        ''' Function which handles saving of image & metadata '''
        
        # Get snapshot name from metadata
        snapshot_name = snapshot_metadata["name"]
        
        # Get snapshot sizing, so we can save it with the metadata
        snap_height, snap_width = snapshot_image_data.shape[0:2]
        snap_wh = (snap_width, snap_height)
        
        # Bundle active object id data into metadata before saving
        full_metadata = snapshot_metadata.copy()
        full_metadata.update({"snap_wh": snap_wh})
        
        # Have reporting object handle image saving
        self.image_saver.save_jpg(file_save_name_no_ext = snapshot_name,
                                  image_data = snapshot_image_data,
                                  save_quality_0_to_100 = self._snapshot_jpg_quality)
        
        self.image_metadata_saver.save_json_gz(file_save_name_no_ext = snapshot_name,
                                               json_data = full_metadata)
    
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE
    def _clean_up(self):
        
        ''' Function used to clean up saving threads '''
        
        # Remove any saving threads that have finished
        self.image_saver.clean_up()
        self.image_metadata_saver.clean_up()
    
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


