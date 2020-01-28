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

from local.lib.ui_utils.local_ui.windows_base import Control_Window

from eolib.utils.cli_tools import Color

# ---------------------------------------------------------------------------------------------------------------------
#%% Define Classes
    
class Local_Window_Controls:
    
    # .................................................................................................................
    
    def __init__(self, screen_info, controls_json, initial_settings, print_control_info = True):
        
        # Store the screen info object, which we'll use for sizing/positioning control windows
        self.screen_info = screen_info
        
        # Store the control spec in case we want to access it later (mostly for debugging?)
        self.controls_json = controls_json
        
        # Get a list of invisible controls, so we can ignore any issues with not being able to set their values
        self.invisible_variable_name_set = self._get_invisible_variable_name_set(controls_json)
        
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
            variable_is_in_controls = (each_variable_name in self.variable_window_lut)
            if variable_is_in_controls:
                self.set_control(each_variable_name, each_map_value)
                continue
            
            # If we get here, the variable wasn't found in the window lut...
            # It may just be invisible (i.e. not displayed on a window, but still active), which is fine
            # or it may be an invalid setting, which we should warn the user about
            
            # No need for any warning/feedback for invisible variables
            variable_is_invisible = (each_variable_name in self.invisible_variable_name_set)
            if variable_is_invisible:
                continue
            
            # We didn't catch the variable name for a known reason, so warn the user about it
            if provide_feedback:
                # Give some feedback
                print("",
                      "Skipped setting control variable: {}".format(each_variable_name),
                      "  (May be a drawing variable?)", 
                      each_map_value,
                      sep="\n")
        
        return
    
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
        
        # Figure out window sizing, based on screen info
        screen_width = self.screen_info.screen("width")
        feedback_width, feedback_x_pad = self.screen_info.feedback("width", "x_padding")
        max_ctrl_columns, max_ctrl_width, ctrl_x_spacing, ctrl_x_padding, ctrl_height = \
        self.screen_info.controls("max_columns", "max_width", "column_spacing", "x_padding", "empty_height")
        
        # Calculate how much area we have for the control windows
        right_edge_reserved = feedback_width + (2 * feedback_x_pad)
        column_spacing_reserved = (ctrl_x_spacing * (max_ctrl_columns - 1))
        control_area_width = screen_width - ctrl_x_padding - right_edge_reserved - column_spacing_reserved
        
        # Finally, figure out the size of hte control windows
        control_window_width = min(max_ctrl_width, int(round(control_area_width / max_ctrl_columns)))
        control_window_wh = (control_window_width, ctrl_height)
        
        window_name_list = []
        window_ref_list = []
        for each_entry in controls_json: 
            window_name = each_entry["group_name"]
            control_list = each_entry["control_list"]
            
            new_control_window = Control_Window(window_name, control_list, frame_wh = control_window_wh)
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
    
    def _get_invisible_variable_name_set(self, controls_json):
        
        # Initialize output
        invisible_set = set()
        
        # Loop through all controls, of all control groups and record any variables with a visible flag set to False
        for each_ctrl_group_dict in controls_json:
            control_list = each_ctrl_group_dict["control_list"]
            for each_ctrl_spec_dict in control_list:
                not_visible = (not each_ctrl_spec_dict["visible"])
                if not_visible:
                    invisible_variable_name = each_ctrl_spec_dict["variable_name"]
                    invisible_set.add(invisible_variable_name)
        
        return invisible_set
    
    # .................................................................................................................
    
    def position_controls(self):
        
        # Separate out the screen info
        max_ctrl_columns, ctrl_x_spacing, ctrl_y_spacing, ctrl_x_pad, ctrl_y_pad = \
        self.screen_info.controls("max_columns", "column_spacing", "row_spacing", "x_padding", "y_padding")
        screen_x_offset, screen_y_offset = self.screen_info.screen("x_offset", "y_offset")
        
        # Allocate space for variables used for locating each window
        x_offset = ctrl_x_pad + screen_x_offset
        y_offset = ctrl_y_pad + screen_y_offset
        x_pos = x_offset
        
        # Move the windows around to nice locations
        for each_idx, each_window in enumerate(self.window_ref_list):
            
            row_idx = int(each_idx / max_ctrl_columns)
            if (each_idx % max_ctrl_columns) == 0:
                x_pos = x_offset
                y_pos = y_offset + row_idx * ctrl_y_spacing
            
            each_window.move_corner_pixels(x_pixels = x_pos, y_pixels = y_pos)
            x_pos += each_window.width + ctrl_x_spacing
    
    # .................................................................................................................
    # .................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------

#%% Define functions

