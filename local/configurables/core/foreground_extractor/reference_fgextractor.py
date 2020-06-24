#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Apr 11 11:21:02 2019

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

import cv2

from local.lib.common.images import blank_frame_from_frame_wh

from local.configurables.configurable_template import Core_Configurable_Base


# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes

class Reference_FG_Extractor(Core_Configurable_Base):
    
    # .................................................................................................................
    
    def __init__(self, cameras_folder_path, camera_select, input_wh, *, file_dunder):
        
        # Inherit from parent class
        super().__init__("foreground_extractor", 
                         cameras_folder_path, camera_select, input_wh, file_dunder = file_dunder)
        
        # Allocate storage for background image data
        self._clean_bg_frame = None
        self._processed_bg_frame = None
        
        # Allocate storage for blanked-out frame, if needed
        self._blank_frame = blank_frame_from_frame_wh(self.input_wh)
        
        
        # !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
        
        # For inherited classes, first call:
        # super().__init__(cameras_folder_path, camera_select, input_wh, file_dunder = __file__)
        
        # Then do any class-specific set up
        # ...
        # ...
        # ...
        
    # .................................................................................................................
    
    def reset(self):
        raise NotImplementedError("Must implement a foreground processor reset()")
    
    # .................................................................................................................
    
    # MAY OVERRIDE. Only if some resources have been opened while running...
    def close(self, final_frame_index, final_epoch_ms, final_datetime):
        # Nothing opened, nothing to close!
        return None
    
    # .................................................................................................................
    
    # MAY OVERRIDE (BUT NOT NECESSARY, BETTER TO INSTEAD OVERRIDE: apply_fg_extraction())
    def run(self, preprocessed_frame, preprocessed_bg_frame, bg_update):
        # This function must maintain this input/output structure!
        #   - Need to pass the preprocessed frame through (for the following pixel filter stage)
        #   - May need to keep track of updates to the background, depending on the processing being done
        #   - Need to return a binary frame (i.e. only a single 'color' channel)
        
        # Update stored background before trying to process frame data
        self._update_internal_background_frame(preprocessed_bg_frame, bg_update)
        
        # Make sure binary frame data is returned (i.e. only has a single channel)
        binary_frame_1ch = self._apply_fg_extraction(preprocessed_frame)
        
        return {"binary_frame_1ch": binary_frame_1ch, 
                "preprocessed_frame": preprocessed_frame,
                "preprocessed_bg_frame": preprocessed_bg_frame,
                "bg_update": bg_update}
    
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE
    def get_internal_background_frame(self):
        
        '''
        Helper function, used to accessed internal copy of the most recent background frame,
        with any processing already applied
        '''
        
        return self._processed_bg_frame
    
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE
    def apply_background_processing(self):
        
        '''
        Function used to apply any processing to the 'clean' background image
        The result is stored internally.
        Also intended for use during configuration, where settings may be updated that 
        require the background itself to be updated for proper functioning
        '''
        
        # Apply background processing to the clean frame data & store it for use in fg-extraction
        if self._clean_bg_frame is not None:
            new_bg_frame = self._clean_bg_frame.copy()
            self._processed_bg_frame = self.process_background_frame(new_bg_frame)
        
        return
    
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE. Instead override process_current_frame(...) function
    def _apply_fg_extraction(self, frame):
        
        '''
        Main fg-extractor function
        Applies processing on every frame
        Should return a single-channel binary frame
        '''
        
        try:
            # Perform all frame processing on each new frame (as a copy, so we don't mess up the original!)
            return self.process_current_frame(frame.copy())
            
        except cv2.error as err:
            self.log("ERROR APPLY FG EXTRACTION ({})".format(self.script_name))
            if self.configure_mode:
                raise err
        
        return self._blank_frame
    
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE
    def _update_internal_background_frame(self, preprocessed_background_frame, bg_update):
        
        '''
        Function used to manage the internal background image, which may/may not be needed for fg-extraction
        '''
        
        # Don't do anything if there is no background frame
        if bg_update or (self._processed_bg_frame is None):
            
            # Store the 'clean' background for reference & apply processing update
            self._clean_bg_frame = preprocessed_background_frame.copy()
            self.apply_background_processing()
        
        return
    
    # .................................................................................................................
    
    # SHOULD OVERRIDE
    def process_current_frame(self, frame):
        
        '''
        Main function to override in sub-classes
        This function should perform necessary foreground-extraction on each incoming frame
        The function should return single-channel binary frame
        '''
        
        # Place frame processing here. Should return a single-channel binary image!
        err_msg = "Must implement a 'process_current_frame() function ({})".format(self.script_name)
        raise NotImplementedError(err_msg)
        
        return self._blank_frame
    
    # .................................................................................................................
    
    # SHOULD OVERRIDE
    def process_background_frame(self, bg_frame):
        
        '''
        Main function to override in sub-classes
        This function is meant to perform any pre-processing on incoming background frames needed
        to make use of the background for performing fg-extraction.
        If a background image is not needed, then this function can be overrided and return the incoming frame
        '''
        
        # Place background processing here
        err_msg = "Must implement a 'update_internal_background_copy() function ({})".format(self.script_name)
        raise NotImplementedError(err_msg)
        
        return bg_frame
    
    # .................................................................................................................
    # .................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions



# ---------------------------------------------------------------------------------------------------------------------
#%% Demo
    
if __name__ == "__main__":
    pass
    

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap


