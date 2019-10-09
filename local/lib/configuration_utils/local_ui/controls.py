#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Jun 18 15:52:38 2019

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

from local.lib.configuration_utils.local_ui.windows_base import Control_Window

from eolib.utils.cli_tools import Color

# ---------------------------------------------------------------------------------------------------------------------
#%% Define Classes
    
class Local_Window_Controls:
    
    # .................................................................................................................
    
    def __init__(self, controls_json, initial_settings, print_control_info = True):
        
        # Store the control spec in case we want to access it later (mostly for debugging?)
        self.controls_json = controls_json
        
        # Create each control window object
        self.window_name_list, self.window_ref_list = self._create_control_windows(controls_json)
        
        # Then create a lookup table for each variable name which specifies the window index it belongs to
        self.variable_window_lut = self._get_variable_window_lookup()
        
        # Finally, set the initial values for each control, and position the windows nicely
        self.set_all_controls(initial_settings)
        self.position_controls()
        
        # Print out control info, if needed
        if print_control_info:
            self.print_info()
      
    # .................................................................................................................
    
    def set_control(self, variable_name, map_value):
        
        # Figure out which window the target variable lives in
        window_idx = self.variable_window_lut[variable_name]
        control_window_ref = self.window_ref_list[window_idx]
        
        # Have the control window handle setting the variable
        control_window_ref.set_trackbar(variable_name, map_value)

    # .................................................................................................................

    def set_all_controls(self, variable_values_dict, provide_feedback = True):
        
        # Loop through all label: value pairs in the control dictionary to set the control value
        for each_variable_name, each_map_value in variable_values_dict.items():
            
            # Only set variables that we know about.
            # Should avoid issues with invisible controls + any config loading mismatch
            if each_variable_name in self.variable_window_lut:
                self.set_control(each_variable_name, each_map_value)
                
            elif provide_feedback:
                # Give some feedback
                print("",
                      "Skipped setting control variable: {}".format(each_variable_name),
                      "  (Variable not recognized! May not be visible?)", sep="\n")
    
    # .................................................................................................................
           
    def read_all_controls(self):
        
        # Allocate space for all changes values
        values_changed_dict = {}
        
        # Ask each window for a dictionary of the values that have changed and the new values
        for each_window in self.window_ref_list:
            new_values_dict = each_window.read_trackbar_changes()
            values_changed_dict.update(new_values_dict)
        
        return values_changed_dict
    
    # .................................................................................................................
    
    def print_info(self):
        
        # Print out a block of control info for each control window. Should show control window title,
        # followed by control labels & their corresponding tooltip info
        for each_window in self.window_ref_list:
            
            # Get info for the printout, per-control window
            window_name = each_window.window_name
            window_info_str = each_window.print_info(return_string = True)
            
            # Print out info for each window
            max_len = 60
            full_spacer_len = max(0, max_len - len(window_name))
            half_spacer_len = int(full_spacer_len / 2)
            end_spacer_len = max(0, max_len - len(window_name) - 2*half_spacer_len)
            
            # Build components for printing control title blocks, then print control info!
            title_spacer = (" " * half_spacer_len)
            end_spacer = (" " * end_spacer_len)
            window_heading_str = "".join([title_spacer, window_name, title_spacer, end_spacer])
            print("", 
                  "",
                  "",
                  Color(window_heading_str.upper()).bold.invert,
                  window_info_str, 
                  "",
                  sep="\n")
           
    # .................................................................................................................
    
    def _create_control_windows(self, controls_json):
        
        window_name_list = []
        window_ref_list = []
        for each_entry in controls_json: 
            window_name = each_entry["group_name"]
            control_list = each_entry["control_list"]
            
            new_control_window = Control_Window(window_name, control_list)
            window_ref_list.append(new_control_window)
            window_name_list.append(window_name)
            
        return window_name_list, window_ref_list
    
    # .................................................................................................................
        
    def _get_variable_window_lookup(self):
        
        variable_window_lut = {}
        for each_window_idx, each_ctrl_window in enumerate(self.window_ref_list):
            
            variable_name_list = each_ctrl_window.variable_name_list            
            label_lut = {each_var_name: each_window_idx for each_var_name in variable_name_list}
            
            variable_window_lut.update(label_lut)
        
        return variable_window_lut
        
    # .................................................................................................................
    
    def position_controls(self, x_offset = 20, y_offset = 20, x_spacing = 20, y_spacing = 250, max_columns = 3):
        
        # Allocate space for accumulator variables for locating each window
        x_acc = x_offset
        y_acc = y_offset        
        
        # Move the windows around to nice locations
        for each_idx, each_window in enumerate(self.window_ref_list):
            
            row_idx = int(each_idx / max_columns)
            if (each_idx % max_columns) == 0:
                x_acc = x_offset
                y_acc = y_offset + row_idx * y_spacing
            
            each_window.move_corner_pixels(x_pixels = x_acc, y_pixels = y_acc)
            x_acc += each_window.width + x_spacing
    
    # .................................................................................................................
    # .................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------

#%% Define functions

