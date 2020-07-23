#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Mar 29 12:15:03 2019

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

from local.configurables.configurable_template import Core_Configurable_Base


# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes

class Reference_Preprocessor(Core_Configurable_Base):
    
    # .................................................................................................................
    
    def __init__(self, location_select_folder_path, camera_select, input_wh, *, file_dunder):
        
        # Inherit from parent class
        super().__init__("preprocessor", location_select_folder_path, camera_select, input_wh,
                         file_dunder = file_dunder)
        
        # Allocate storage for holding on to the newest background image
        self.current_background = None
        
        # !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
        
        # For inherited classes, first call:
        # super().__init__(location_select_folder_path, camera_select, input_wh, file_dunder = __file__)
        
        # Then do any class-specific set up
        # ...
        # ...
        # ...
    
    # .................................................................................................................
    
    # MUST OVERRIDE
    def reset(self):
        ''' 
        Function which gets called everytime the system is reset, typically during configuration.
        For example, due to rewinding/looping the video playback
        '''
        raise NotImplementedError("Must implement a preprocessor reset()")
    
    # .................................................................................................................
    
    # MAY OVERRIDE. Only if some resources have been opened while running...
    def close(self, final_frame_index, final_epoch_ms, final_datetime):
        # Nothing opened, nothing to close!
        return None
    
    # .................................................................................................................
    
    # MAY OVERRIDE (BUT NOT NECESSARY, BETTER TO INSTEAD OVERRIDE: apply_transformation())
    def run(self, video_frame, bg_frame, bg_update):
        # This function must maintain this input/output structure!
        #   - Used to ensure live video data + background image getting to foreground extractor are matched
        #   - Any modifications applied by the preprocessor should be applied to the background frame before return
        
        # Apply preprocessing transformation to background images (when available) and all live video frames
        preprocessed_bg_frame = self.preprocess_background(bg_frame, bg_update)
        preprocessed_frame = self.apply_transformation(video_frame)
        
        return {"preprocessed_frame": preprocessed_frame, 
                "preprocessed_bg_frame": preprocessed_bg_frame,
                "bg_update": bg_update}
    
    # .................................................................................................................
    
    # MAY OVERRIDE (BUT NOT NECESSARY, IF POSSIBLE, BETTER TO INSTEAD OVERRIDE: apply_transformation())
    def preprocess_background(self, background_frame, bg_update):
        # This function must maintain this input/output structure
        #   - Used to ensure live video data + background image getting to foreground extractor are matched
        #   - background image is not necessarily updated every frame (depends how often bg capture outputs)
        
        # Apply preprocessing transformation to the background image to match live video frames
        if bg_update or (self.current_background is None):
            modified_background = self.apply_transformation(background_frame)
            self.current_background = modified_background.copy()
        else:
            modified_background = self.current_background
        
        return modified_background
    
    # .................................................................................................................
    
    # SHOULD OVERRIDE
    def apply_transformation(self, frame):
        
        try:
            return frame.copy()
        
        except cv2.error as err:
            self.log("ERROR TRANSFORMING ({})".format(self.script_name))
            if self.configure_mode:
                raise err
        
        return frame
    
    # .................................................................................................................
    
    # SHOULD OVERRIDE
    def unwarp_required(self):
        
        '''
        Function which will be used by the object capture stage to decide whether 
        object positioning data needs to be 'unwarped' prior to saving.
        
        The function should return True if the preprocessor alters the input image
        in such a way that the output is anything other than a scaled copy of the input
        If no warping is performed (or the preprocessor is disabled), then it can output False
        '''
        
        # Raise error to make sure preprocessors deal with this properly
        err_msg = "Must implement unwarp_required() function on preprocessor! ({})".format(self.script_name)
        raise NotImplementedError(err_msg)
        
        # Should return True or False, depending on whether the preprocessor warps the original image at all
        return True
    
    # .................................................................................................................
    
    # MUST OVERRIDE
    def unwarp_xy(self, warped_normalized_xy_npfloat32):
        
        '''
        Function which handles unwarping of x/y co-ordinate data for the object metadata saving stage.
        
        If the preprocessor warped the frame data in some way (aside from simple scaling), this function needs
        to provide the inverse warping, so that co-ordinate data from a preprocessed frame can be mapped back
        into the original frame data. The output should still be a normalized xy float32 array!
        
        If the preprocessor does not warp the frame data (or simply scales it), then this function
        can return 'None' to indicate that no warping is needed
        (this may be more efficient than copying the input to the output!)
        '''
        
        # Raise error to make sure preprocessors deal with this properly
        err_msg = "Must implement an 'unwarp_xy(...)' function on preprocessor! ({})".format(self.script_name)
        raise NotImplementedError(err_msg)
        
        # Should return the unwarped x/y array data as a float32 array
        # -> However, 'None' can be returned if the preprocessor does not require unwarping!
        return None
    
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



    