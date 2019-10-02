#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue May 28 12:48:00 2019

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
import numpy as np


# ---------------------------------------------------------------------------------------------------------------------
#%% Define Classes

class Core_Config_Display_Manager:
    
    # .................................................................................................................
    
    def __init__(self, layout_cols = None, layout_rows = None):
        
        # Allocate storage for layout variables
        self.layout_cols = layout_cols
        self.layout_rows = layout_rows
        
        # Allocate storage for registered displays
        self.display_callback_dict = {}
        self.display_config_list = []
        self.initial_display = None
    
    # .................................................................................................................
    
    def __repr__(self):
        
        repr_strs = ["Display List:"]
        
        for each_entry in self.display_config_list:
            window_name = each_entry.get("window_name", "No Name?")
            repr_strs += ["  {}".format(window_name)]
        
        return "\n".join(repr_strs)
    
    # .................................................................................................................
    
    def register_display(self, window_name, stage_output_key, frame_key,
                         initial_display = False, 
                         max_wh = (None, None), 
                         drawing_control_variable = None, 
                         visualization_variable = None):
        
        # Use resizing callback if a max width/height was given, otherwise use passthrough
        display_callback_function = passthrough(stage_output_key, frame_key)
        if None not in max_wh:
            display_callback_function = limit_size(stage_output_key, frame_key, 
                                                   max_display_wh = max_wh)
        
        return self.register_custom_callback(window_name, 
                                             display_callback_function, 
                                             initial_display, max_wh, 
                                             drawing_control_variable, 
                                             visualization_variable)
    
    # .................................................................................................................
    
    def register_custom_callback(self, window_name, display_callback_function,
                                 initial_display = False,
                                 max_wh = (None, None), 
                                 drawing_control_variable = None, 
                                 visualization_variable = None):
        
        '''
        Adds a display to the configuration utility.
        Display functions should be of the form:
            display_callback_function(stage_outputs, configurable_ref)
            
        Where "all_stage_outputs" comes directly from the output of the processing sequence!
        The display callback is responsible for accessing the required frame/info out of the stage outputs.
        '''
        
        # Set this window to be the initial display, if needed
        if initial_display:
            self.initial_display = window_name
        
        # Record the display callback
        self.display_callback_dict[window_name] = display_callback_function
        
        # Record the new display configuration info
        new_config = {"window_name": window_name, 
                      "max_wh": max_wh, 
                      "drawing_control": drawing_control_variable, 
                      "visualization": visualization_variable,
                      "initial_display": initial_display}
        self.display_config_list.append(new_config)
        
    # .................................................................................................................
    
    def to_json(self):
        
        # Figure out the window layout
        self._set_layout()
        
        # Set first display as the initial one, if an initial display wasn't set
        if self.initial_display is None:
            self.initial_display = self.display_config_list[0]["window_name"]
        
        # Build the output json data
        display_config_dict = {"layout_row_col": (self.layout_rows, self.layout_cols),
                               "initial_display": self.initial_display,
                               "displays": self.display_config_list}
        
        return display_config_dict
    
    # .................................................................................................................
    
    def get_config_info(self):        
        return self.to_json(), self.display_callback_dict
        
    # .................................................................................................................
    
    def _set_layout(self):
        
        # If there are no displays, raise an error for now... May be an ok thing in the future?
        num_displays = len(self.display_config_list)
        if num_displays < 1:
            raise AttributeError("Cannot configure displays. since no displays were specified!")
        
        # Figure out the window layout
        num_cols = self.layout_cols
        num_rows = self.layout_rows
        
        # Handle case where the both rows/columns are set adaptively
        if (num_cols is None) and (num_rows is None):
            num_rows = int(max(np.floor(np.sqrt(num_displays)), 1))
            num_cols = int(np.ceil(num_displays / num_rows))
        
        # Handle case where the number of rows was specifed and num cols needs to be set adaptively
        elif num_cols is None:            
            num_cols = int(np.ceil(num_displays / num_rows))
        
        # Handle case where the number of columns was specifed and num rows needs to be set adaptively
        elif num_rows is None:            
            num_rows = int(max(1, np.floor(num_displays / num_cols)))
            
        # Set the layout values
        self.layout_cols = num_cols
        self.layout_rows = num_rows
    
    # .................................................................................................................
    # .................................................................................................................
    

# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

# .....................................................................................................................
    
def passthrough(stage_name, output_key):
    
    '''
    Function for creating display callbacks for the Core_Config_Display_Manager.
    This function simply passes an image straight through to the output
    '''
    
    def display_callback(stage_outputs, configurable_ref):
        return stage_outputs[stage_name][output_key]
    
    return display_callback

# .....................................................................................................................
    
def bordered(stage_name, output_key, border_width = 60, border_height = 60, border_color = (40,40,40)):
    
    '''
    Function for creating display callbacks for the Core_Config_Display_Manager.
    This function adds borders to a target image
    '''
    
    # Define function for display callback, which requires the inputs (stage_outputs, configurable_ref)
    def display_callback(stage_outputs, configurable_ref):
        
        # Grab the target frame from the stage outputs, then return it with borders added
        input_frame = stage_outputs[stage_name][output_key]
        return cv2.copyMakeBorder(input_frame, 
                                  top = border_height, 
                                  bottom = border_height, 
                                  left = border_width, 
                                  right = border_width,
                                  borderType = cv2.BORDER_CONSTANT,
                                  value = border_color)
    
    return display_callback

# .....................................................................................................................

def limit_size(stage_name, output_key, max_display_wh = (1280, 1280)):
    
    '''
    Function for creating display callbacks for the Core_Config_Display_Manager.
    This function is used to limit the display size of a target frame (by shrinking), 
    while maintaining the aspect ratio of the original image.
    '''
    
    # For convenience
    max_width = max_display_wh[0]
    max_height = max_display_wh[1]
    
    # Define function for display callback, which requires the inputs (stage_outputs, configurable_ref)
    def display_callback(stage_outputs, configurable_ref):
        
        # Grab the target frame from the stage outputs
        input_frame = stage_outputs[stage_name][output_key]
        
        # Check if the frame is bigger than the target sizing
        frame_height, frame_width = input_frame.shape[0:2]               
        if frame_height > max_height or frame_width > max_width:
            
            # Find the dimension that requires greater scaling and use that to shrink both dimensions equally
            scale_factor_width = max_width / frame_width
            scale_factor_height = max_height / frame_height
            scale_factor_shared = min(scale_factor_width, scale_factor_height)
            
            return cv2.resize(input_frame, dsize = None, fx = scale_factor_shared, fy = scale_factor_shared)
        
        # If resizing isn't needed, just display the frame as-is
        return input_frame.copy()

    return display_callback

# .....................................................................................................................

def pixelate(stage_name, output_key, pixelation_factor = 2):
    
    '''
    Function for creating display callbacks for the Core_Config_Display_Manager.
    Intended for testing images! Probably not worth using in real configurations!
    '''
    
    # For convenience
    scale_down_factor = 1 / pixelation_factor
    scale_up_factor = pixelation_factor
    
    # Define function for display callback, which requires the inputs (stage_outputs, configurable_ref)
    def display_callback(stage_outputs, configurable_ref):
        
        # Grab the target frame from the stage outputs
        input_frame = stage_outputs[stage_name][output_key]
        
        shrink_frame = cv2.resize(input_frame, dsize=None, fx = scale_down_factor, fy = scale_down_factor)
        pixelated_frame = cv2.resize(shrink_frame, dsize=None, fx = scale_up_factor, fy = scale_up_factor,
                                     interpolation = cv2.INTER_NEAREST)
        
        return pixelated_frame
    
    return display_callback

# .....................................................................................................................
    
def draw_matched_frame_size(target_stage, target_frame, reference_stage, reference_frame,
                            interpolation_style = cv2.INTER_NEAREST):
    
    '''
    Function which matches the frame size of one (target) frame to some other (reference) frame
    '''
    
    def draw_scaled_frame(stage_outputs, configurable_ref):
        scale_h, scale_w = stage_outputs[reference_stage][reference_frame].shape[0:2]
        output_frame = stage_outputs[target_stage][target_frame].copy()        
        return cv2.resize(output_frame, dsize = (scale_w, scale_h), interpolation=interpolation_style) 
    
    return draw_scaled_frame

# .....................................................................................................................
# .....................................................................................................................
    

# ---------------------------------------------------------------------------------------------------------------------
#%% Demo

if __name__ == "__main__":
    
    # As an example: 
    #   Set up a display output which resizes the input frame to a max size of 640 x 360px
    #   Also set up a display of the preprocessed frame with no max size
    dm = Core_Config_Display_Manager(layout_cols = 2)
    dm.register_display("Input", "frame_capture", "video_frame", max_wh = (640, 360))
    dm.register_display("Preprocessed", "preprocessor", "preprocessed_frame", initial_display = True)
    
    # Would be passed to local/web video loop function, where it is called using:
    display_config_json, display_callbacks = dm.get_config_info()
    print("", "Example display config:", display_config_json, "", sep="\n")
    # - display_callbacks are used by python to generate the frame data (based on 'register_display' above)
    # - display_config_json is used to configure the display (either local OCV windows or web UI stuff)


# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap
   

