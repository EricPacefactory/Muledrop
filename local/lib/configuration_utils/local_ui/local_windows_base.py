#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri May 24 14:30:05 2019

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

import screeninfo

from collections import deque

from eolib.utils.cli_tools import Color

# ---------------------------------------------------------------------------------------------------------------------
#%% Define Classes


class Simple_Window:
    
    # ................................................................................................................. 
    
    def __init__(self, window_name,
                 frame_wh = None,
                 max_wh = None,
                 create_on_startup = True):
        
        # Get window name so we can continue to refer to this window!
        self.window_name = window_name
        
        # Get user display sizing
        self.screen_width, self.screen_height = display_wh()
        
        # Variables for recording the window position
        self.x_px = None
        self.y_px = None
        
        
        # Variables used to record the size of the displayed image
        self.width = None
        self.height = None
        if frame_wh is not None:
            self.width, self.height = frame_wh
    
        # Variables for limiting frame size
        self.max_width = None
        self.max_height = None
        self._check_resize = False
        if max_wh is not None:
            self.max_width, self.max_height = max_wh
            self._check_resize = True
        
        # Create the display, if needed
        if display_is_available() and create_on_startup:
            self.create_window()
    
    # ................................................................................................................. 
    
    def __repr__(self):
        return "Simple_Window ({})".format(self.window_name)
    
    # ................................................................................................................. 
    
    def get_window_name(self):
        return self.window_name
    
    # .................................................................................................................
    
    def get_window_wh(self):
        return self.width, self.height
    
    # ................................................................................................................. 
        
    def imshow(self, display_frame):
        
        # Check if the window exists (by looking for window properties)
        window_exists = self.exists()
        
        # Don't do anything if a valid frame isn't supplied
        if display_frame is None:
            return self.exists()
        
        # Only update showing if the window exists
        if window_exists:
            cv2.imshow(self.window_name, display_frame)
        
        return window_exists
    
    # ................................................................................................................. 
        
    def imshow_blank(self, blank_wh = None):
        
        # Set blank size if needed
        if self.width is None and self.height is None:
            blank_wh = (500, 30) if blank_wh is None else blank_wh
        else:
            blank_wh = (self.width, self.height)
        
        # Only update showing if the window exists
        window_exists = self.exists()
        if window_exists:
            blank_image = np.zeros((blank_wh[1], blank_wh[0], 3), dtype=np.uint8)
            cv2.imshow(self.window_name, blank_image)
        
        return window_exists
    
    # ................................................................................................................. 
    
    def move_corner_norm(self, x_norm, y_norm):
        
        '''
        Move the window corner to a screen position, specified using normalized co-ords. 
        Normalized mapping: 0.0 -> Left/top-most 1.0 -> Right/bottom-most
        '''
        
        # Find pixel location based on normalized input
        screen_x_px = (self.screen_width - 1) * x_norm
        screen_y_px = (self.screen_height - 1) * y_norm
        
        return self.move_corner_pixels(screen_x_px, screen_y_px)
       
    # ................................................................................................................. 
    
    def move_center_norm(self, x_norm, y_norm, 
                         frame_width = None, frame_height = None):
        
        '''
        Move the window center to a screen position, specified using normalized co-ords.
        Normalized mapping: 0.0 -> Left/top-most 1.0 -> Right/bottom-most
        '''
        
        # Update frame width/height if needed
        self.width = frame_width if frame_width is not None else self.width
        self.height = frame_height if frame_height is not None else self.height
        
        # Get the frame half sizing for centering
        try:
            half_frame_width = self.width / 2
            half_frame_height = self.height / 2
        except TypeError:
            raise AttributeError("Can't move the window without knowing it's frame width/height!")
        
        # Find the screen location in pixels from normalized units
        screen_x_px = (self.screen_width - 1) * x_norm
        screen_y_px = (self.screen_height - 1) * y_norm
        
        # Find window corner location, so that the frame center lands at the target screen position
        window_corner_x_px = screen_x_px - half_frame_width
        window_corner_y_px = screen_y_px - half_frame_height
        
        return self.move_corner_pixels(window_corner_x_px, window_corner_y_px)
    
    # ................................................................................................................. 
    
    def move_corner_pixels(self, x_pixels, y_pixels):
        
        '''
        Move the window corner to a screen position, specified in pixels
        '''
        
        self.x_px = int(round(x_pixels))
        self.y_px = int(round(y_pixels))
        
        cv2.moveWindow(self.window_name, self.x_px, self.y_px)
        
        return self
    
    # ................................................................................................................. 
    
    def move_center_pixels(self, x_pixels, y_pixels, frame_width = None, frame_height = None):
        
        '''
        Move the window center to a screen position, specified in pixels
        '''
        
        # Update frame width/height if needed
        self.width = frame_width if frame_width is not None else self.width
        self.height = frame_height if frame_height is not None else self.height
        
        # Get the frame half sizing for centering
        try:
            half_frame_width = self.width / 2
            half_frame_height = self.height / 2
        except TypeError:
            raise AttributeError("Can't move the window without knowing it's frame width/height!")
        
        # Find window corner location, so that the frame center lands at the target screen position
        window_corner_x_px = x_pixels - half_frame_width
        window_corner_y_px = y_pixels - half_frame_height
        
        return self.move_corner_pixels(window_corner_x_px, window_corner_y_px)
    
    # .................................................................................................................
    
    def exists(self):
        return cv2.getWindowProperty(self.window_name, cv2.WND_PROP_AUTOSIZE) > 0
    
    # .................................................................................................................    
    
    def close(self):
        if self.exists(): 
            cv2.destroyWindow(self.window_name)
        
    # ................................................................................................................. 
        
    def attach_callback(self, mouse_callback, callback_data = {}):
        cv2.setMouseCallback(self.window_name, mouse_callback, callback_data)
        return self
    
    # ................................................................................................................. 
    
    def add_trackbar(self, label, initial_value, max_value):        
        cv2.createTrackbar(label, self.window_name, initial_value, max_value, lambda x: None)
        
    # ................................................................................................................. 
        
    def set_trackbar(self, label, new_value):
        cv2.setTrackbarPos(label, self.window_name, new_value)
    
    # ................................................................................................................. 
        
    def read_trackbar(self, label):
        return cv2.getTrackbarPos(label, self.window_name)
    
    # ................................................................................................................. 
    
    def create_window(self):
        
        # Create window
        cv2.namedWindow(self.window_name)
        self.imshow_blank()
        self.move_corner_pixels(x_pixels = 50, y_pixels = 50)
        
        return self
        
    # .................................................................................................................
    # .................................................................................................................

# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
    
class Control_Window(Simple_Window):
    
    # .................................................................................................................
    
    def __init__(self, window_name, control_list_json, frame_wh = (500, 30)):
        
        # Inherit from simple window
        super().__init__(window_name, frame_wh)
        
        # Set width/height of control window (which is normally just a small blackout area)
        self.width, self.height = frame_wh
        
        # Store controls for future reference if needed
        self.control_list_json = control_list_json
        
        # Draw initial blank frame
        self._blank_frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        self.imshow(self._blank_frame)        
        
        # Allocate space to store trackbar info
        self.tooltip_dict = {}
        self.units_dict = {}
        self.menu_labels_dict = {}
        self.variable_to_label_lut = []
        self.trackbar_position_dict = {}
        self.trackbar_minimums_dict = {}
        self.variable_name_list = []
        
        # Allocate space for mapping functions
        self._map_to_raw_func_dict = {}
        self._raw_to_map_func_dict = {}
        
        # Create all the trackbars and read their initial values
        self._build_trackbars(self.control_list_json)
        
    # .................................................................................................................
    
    def print_info(self, return_string = True):
        
        # Loop through every variable and construct a nice info printout
        print_str_list = []
        for each_variable in self.variable_name_list:
            
            # Pull out control info
            control_label = self.variable_to_label_lut[each_variable]
            control_units = self.units_dict[each_variable]
            control_tooltip = self.tooltip_dict[each_variable]
            control_menu_labels = self.menu_labels_dict[each_variable]
            
            # Bail if no tooltip is present. If a tooltip comes in as a list, treat it as separate lines to print out
            if control_tooltip is None:
                continue
            elif control_tooltip == "":
                tooltip_str = "  No tooltip!"
            elif type(control_tooltip) in [tuple, list]:
                tooltip_str = "\n".join(["  {}".format(each_line) for each_line in control_tooltip])
            else:
                tooltip_str = "  {}".format(control_tooltip)
            
            # Set up the heading title string for each variable print out
            heading_str = control_label
            if control_units:
                heading_str += " ({}):".format(control_units)
            elif len(control_menu_labels) > 1:
                menu_labels_str = " / ".join(control_menu_labels)
                heading_str += " ({}):".format(menu_labels_str)
            else:
                heading_str += ":"
            
            # Combine the label heading and tooltip strings
            new_print_str = ["",
                             Color(heading_str).bold.str,
                             tooltip_str]
            
            # Add to the list of variable info printouts
            print_str_list += new_print_str
            
        # Finally, return or print out all the control info
        print_out_str = "\n".join(print_str_list)
        if return_string:
            return print_out_str
        else:
            print(print_out_str)
    
    # .................................................................................................................
    
    def set_trackbar(self, variable_name, mapped_value):
        
        map_to_raw_func = self._map_to_raw_func_dict[variable_name]
        raw_value = map_to_raw_func(mapped_value)
        
        control_label  = self.variable_to_label_lut[variable_name]
        self._set_trackbar_raw(control_label, raw_value)
        
    # .................................................................................................................
    
    def read_trackbar(self, variable_name, force_minimum = True):
        
        # Get the function needed to map from raw (trackbar position) values to mapped values
        raw_to_map_func = self._raw_to_map_func_dict[variable_name]
        
        # Get trackbar position
        control_label = self.variable_to_label_lut[variable_name]
        raw_value = self._read_trackbar_raw(control_label)
        
        # Stop the user from going below some minimum trackbar position
        if force_minimum:
            tb_min = self.trackbar_minimums_dict[control_label]
            if raw_value < tb_min:
                raw_value = tb_min
                self._set_trackbar_raw(control_label, raw_value)
        
        # Check if the trackbar position changed
        value_changed = (raw_value != self.trackbar_position_dict[control_label])
        if value_changed:
            self.trackbar_position_dict[control_label] = raw_value
        
        # Finally, return the variable in it's proper representation
        map_value = raw_to_map_func(raw_value)
        
        return value_changed, map_value
    
    # .................................................................................................................
        
    def read_trackbar_changes(self):
        
        # Loop through all trackbar, reading values
        # Need to check values against some recorded value, and report them if they changed...
        # Report back using variable_name and new value
        value_changes_dict = {}
        for each_variable in self.variable_name_list:
            value_changed, map_value = self.read_trackbar(each_variable)
            if value_changed:
                value_changes_dict.update({each_variable: map_value})
        
        return value_changes_dict
    
    # .................................................................................................................
    
    def _set_trackbar_raw(self, label, raw_value):        
        if self.exists():
            cv2.setTrackbarPos(label, self.window_name, raw_value)
    
    # .................................................................................................................
    
    def _read_trackbar_raw(self, label):
        return cv2.getTrackbarPos(label, self.window_name) if self.exists() else self.trackbar_position_dict[label]
    
    # .................................................................................................................
    
    def _build_trackbars(self, control_list):
        
        # Allocate space to store trackbar info
        self.tooltip_dict = {}
        self.units_dict = {}
        self.menu_labels_dict = {}
        self.variable_to_label_lut = {}
        self.trackbar_position_dict = {}
        self.trackbar_minimums_dict = {}
        self.variable_name_list = []
        
        for each_entry in control_list:
            
            '''
            print("")
            print("({})".format(os.path.basename(__file__)))
            print("CONTROL ENTRY:", each_entry)
            print("Control_type", control_type)
            '''
            
            # Get important identifying info
            control_label = each_entry.get("label")
            variable_name = each_entry.get("variable_name")
            control_type = each_entry.get("control_type")
            visible = each_entry.get("visible", True)
            
            # Skip over any non-visible controls
            if not visible:
                continue
            
            # Configure each control and figure out the trackbar (initial) settings
            config_function = self._control_type_lookup(control_type)
            tb_minimum, tb_maximum, tb_initial = config_function(each_entry)            
            self.add_trackbar(control_label, tb_initial, tb_maximum)
            
            # Store the units and tooltip info so we can print it out later
            self.tooltip_dict[variable_name] = each_entry.get("tooltip", "")
            self.units_dict[variable_name] = each_entry.get("units", "")
            self.menu_labels_dict[variable_name], _ = zip(*each_entry.get("option_label_value_list", [("", "")]))
            
            # Store data we'll need for reading the trackbars later
            self.variable_to_label_lut[variable_name] = control_label
            self.trackbar_position_dict[control_label] = tb_initial
            self.trackbar_minimums_dict[control_label] = tb_minimum
            self.variable_name_list.append(variable_name)
            
    # .................................................................................................................
            
    def _control_type_lookup(self, control_type):

        # Use dictionary as a simple lookup for matching control types with configuration functions
        ctrl_type_lut = {"toggle": self._toggle_config,
                         "slider": self._slider_config,
                         "numentry": self._numentry_config,
                         "menu": self._menu_config,
                         "button": self._button_config}   
        
        return ctrl_type_lut[control_type]
    
    # .................................................................................................................
    
    def _toggle_config(self, config_data):
        
        # Expects
        '''
        variable_name, label
        default_value,
        tooltip, visible
        '''
        
        # Pull out some relevant data for convenience
        variable_name = config_data.get("variable_name")
        default_value = config_data.get("default_value", 0)
        
        # Get the mapping functions based on the config data
        raw_to_map_func, map_to_raw_func = bool_to_int()
        
        # Store the mapping functions so we can use them when reading/setting the trackbar
        self._map_to_raw_func_dict[variable_name] = map_to_raw_func
        self._raw_to_map_func_dict[variable_name] = raw_to_map_func
        
        # Get the default and maximum trackbar values
        trackbar_initial = map_to_raw_func(default_value)
        trackbar_minimum = 0
        trackbar_maximum = 1
        
        return trackbar_minimum, trackbar_maximum, trackbar_initial
            
    # ................................................................................................................. 
    
    def _slider_config(self, config_data):
        
        # Expects
        '''
        variable_name, label
        default_value
        min_value, max_value, step_size 
        units, return_type, zero_referenced,
        tooltip, visible
        '''
        
        # Pull out some relevant data for convenience
        variable_name = config_data.get("variable_name")
        default_value = config_data.get("default_value", 0)
        min_value = config_data.get("min_value")
        max_value = config_data.get("max_value")
        step_size = config_data.get("step_size", 1)
        return_type = return_type_strings_to_functions(config_data.get("return_type", None))
        zero_referenced = config_data.get("zero_referenced", False)
        
        # Get the mapping functions based on the config data
        if zero_referenced:
            raw_to_map_func, map_to_raw_func = minceil_affine(min_value, max_value, step_size, return_type)
        else:
            raw_to_map_func, map_to_raw_func = simple_affine(min_value, max_value, step_size, return_type)
        
        # Store the mapping functions so we can use them when reading/setting the trackbar
        self._map_to_raw_func_dict[variable_name] = map_to_raw_func
        self._raw_to_map_func_dict[variable_name] = raw_to_map_func
        
        # Get the default and maximum trackbar values
        trackbar_initial = map_to_raw_func(default_value)
        trackbar_minimum = map_to_raw_func(min_value)
        trackbar_maximum = map_to_raw_func(max_value)
        
        return trackbar_minimum, trackbar_maximum, trackbar_initial
    
    # .................................................................................................................
    
    def _numentry_config(self, config_data):
        
        # Expects
        '''
        variable_name,
        label,
        default_value, 
        min_value, 
        max_value, 
        step_size = 1, 
        units = None, 
        return_type = float, 
        zero_referenced = False,
        force_min = True, 
        force_max = True, 
        force_step = True, 
        tooltip = "", 
        visible = True
        '''
        
        # Pull outdata that allows us to createa regular slider 
        # (numerical entry doesn't behave differently from a slider when using the local ui!)
        grab_slider_keys = ["variable_name", "label", "default_value", 
                            "min_value", "max_value", "step_size", 
                            "units", "return_type", "zero_referenced", 
                            "tooltip", "visible"]
        slider_config_data = {each_key: config_data[each_key] for each_key in grab_slider_keys}
        
        return self._slider_config(slider_config_data)
    
    # .................................................................................................................
    
    def _menu_config(self, config_data):
        
        # Expects
        '''
        variable_name, 
        label,
        default_value,
        option_label_value_dict,
        tooltip = "", 
        visible = True
        '''
        
        # Pull out some relevant data for convenience
        variable_name = config_data.get("variable_name")
        default_value = config_data.get("default_value", 0)
        option_label_value_list = config_data.get("option_label_value_list")
        
        # Separate the labels and values, since we only need the values for local usage
        label_list, value_list = list(zip(*option_label_value_list))
        
        # Get the mapping functions based on the config data
        raw_to_map_func, map_to_raw_func = value_list_lookup(value_list)
        
        # Store the mapping functions so we can use them when reading/setting the trackbar
        self._map_to_raw_func_dict[variable_name] = map_to_raw_func
        self._raw_to_map_func_dict[variable_name] = raw_to_map_func
        
        # Get the default and maximum trackbar values
        trackbar_initial = map_to_raw_func(default_value)
        trackbar_minimum = 0
        trackbar_maximum = len(value_list) - 1
        
        return trackbar_minimum, trackbar_maximum, trackbar_initial
    
    # .................................................................................................................
    
    def _button_config(self, config_data):
        
        # Expects
        '''
        variable_name, 
        label, 
        default_value, 
        return_type = bool,
        tooltip = "", 
        visible = True
        '''
        
        # Pull out some relevant data for convenience
        variable_name = config_data.get("variable_name")
        default_value = config_data.get("default_value", 0)
        
        # Get the mapping functions based on the config data
        set_trackbar_func = self._set_trackbar_raw
        raw_to_map_func, map_to_raw_func = button_map(variable_name, set_trackbar_func)
        
        # Store the mapping functions so we can use them when reading/setting the trackbar
        self._map_to_raw_func_dict[variable_name] = map_to_raw_func
        self._raw_to_map_func_dict[variable_name] = raw_to_map_func
        
        # Get the default and maximum trackbar values
        trackbar_initial = map_to_raw_func(default_value)
        trackbar_minimum = 0
        trackbar_maximum = 1
        
        return trackbar_minimum, trackbar_maximum, trackbar_initial
        
    # .................................................................................................................
    
    # .................................................................................................................
    # .................................................................................................................

# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////


class Slideshow_Window(Simple_Window):
    
    # .................................................................................................................
    
    def __init__(self, window_name, 
                 frame_wh = None,
                 max_wh = None,
                 missing_image_test = "No image...",
                 max_storage = 10):
        
        # Inherit from parent class
        super().__init__(window_name, frame_wh, max_wh)
        
        # Initialize storage variables
        self.frame_deck = self._initialize_empty_frame_deck(missing_image_test, max_storage)
        self.current_select = 0
        self._update_enabled = True
        
        # Add a trackbar to control access to selecting which image to display
        self._trackbar_enable_label = "Enable Updates"
        self._trackbar_select_label = "Image select"
        self.add_trackbar(self._trackbar_enable_label, 1, 1)
        self.add_trackbar(self._trackbar_select_label, self.current_select, max_storage - 1)
        
        # Draw initial image
        self.imshow_by_index()
      
    # .................................................................................................................
    
    def _initialize_empty_frame_deck(self, missing_image_test, deque_size, default_blank_wh = (360, 240)):
        
        # Create new deque for storing 'slideshow' images
        new_deque = deque([], maxlen = deque_size)
        
        # Create blank frame
        frame_width = self.width if self.width else default_blank_wh[0]
        frame_height = self.height if self.height else default_blank_wh[1]
        
        # Draw an empty frame with some text indicating that no image is available
        blank_frame = np.zeros((frame_height, frame_width, 3), dtype=np.uint8)
        cv2.putText(blank_frame, missing_image_test, 
                    (10, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 1, cv2.LINE_AA)
        
        # Fill in frame deque with blank frames
        for k in range(deque_size):
            new_deque.append(blank_frame.copy())
        
        return new_deque
        
    # .................................................................................................................
        
    def imshow(self, display_frame):
        
        # Only update if the window exists
        window_exists = self.exists()
        if window_exists:
            
            # Only update the frame deck (and display) if the slideshow updates are still enabled
            if self._update_enabled:
                self.frame_deck.appendleft(display_frame)
                self.imshow_by_index()
        
        return window_exists
    
    # .................................................................................................................
    
    def imshow_by_index(self, index_select = None):
        
        # Automatically use the current index if one isn't provided
        if index_select is None:
            index_select = self.current_select
            
        # Only update if the window exists
        window_exists = self.exists()
        if window_exists:
            cv2.imshow(self.window_name, self.frame_deck[index_select])
            
        return window_exists
    
    # .................................................................................................................
    
    def read_trackbars(self):
        
        # Determine if updates are enabled
        self._update_enabled = self.read_trackbar(self._trackbar_enable_label)
        
        # Determine if we need to update the displayed index
        new_select = self.read_trackbar(self._trackbar_select_label)
        if new_select != self.current_select:
            self.current_select = new_select
            self.imshow_by_index(new_select)
            
    # .................................................................................................................
    # .................................................................................................................
    
# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

# .....................................................................................................................
       
def simple_affine(min_value, max_value, step_size = 1, return_type = None):
    
    # Using y = mx + b (y -> mapped value, x -> raw/trackbar value)
    # Where y = min             when x = 0
    #       y = max_value       when x = (max_value - min_value) / step_size
    # So:
    # min = 0 + b
    # max = m * (1 / step) * (max - min) + b
    
    # Therefore
    # b = min
    # m = step * (max - b) * (1 / max - min)
    #
    # b = min, m = step
    # y = step * x + min
    # x = (y - min) / step
    
    def raw_to_map_func(raw_value):
        map_value = step_size * raw_value + min_value
        return return_type(map_value) if return_type else map_value
    
    def map_to_raw_func(map_value):    
        raw_value = (map_value - min_value) / step_size
        return (int(round(raw_value)))
    
    return raw_to_map_func, map_to_raw_func

# .....................................................................................................................
    
def minceil_affine(min_value, max_value, step_size = 1, return_type = None):
    
    # Same as an affine mapping, but won't allow the value to go below the minimum value
    # Intended for cases where the trackbar is pinned to 0 for display purposes.
    
    # Pre-calculate/generate some useful variables
    simple_raw_to_map_func, simple_map_to_raw_func = simple_affine(min_value, max_value, step_size, return_type)
    min_raw_value = min_value / step_size
    min_offset = (min_value / step_size)
    
    def raw_to_map_func(raw_value):        
        ceil_raw_value = max(min_raw_value, raw_value) - min_offset
        map_value = simple_raw_to_map_func(ceil_raw_value)
        return map_value
    
    def map_to_raw_func(map_value):
        raw_value = simple_map_to_raw_func(map_value) + min_offset
        return int(round(raw_value))
    
    return raw_to_map_func, map_to_raw_func

# .....................................................................................................................
    
def value_list_lookup(value_list):
    
    def raw_to_map_func(raw_value):
        # For menus, the raw value is the trackbar location, 
        # which selects a value from the value list as a simple (list) index
        return value_list[raw_value]
    
    def map_to_raw_func(map_value):
        # For menus, the mapped value is an entry in the value list
        # The raw value is the trackbar location, which is also just the index of the value in the list
        return value_list.index(map_value)
    
    return raw_to_map_func, map_to_raw_func

# .....................................................................................................................
    
def bool_to_int():
    
    def raw_to_map_func(raw_value):
        return bool(raw_value)
    
    def map_to_raw_func(map_value):
        return int(map_value)
    
    return raw_to_map_func, map_to_raw_func

# .....................................................................................................................
    
def button_map(control_label, set_trackbar_func):
    
    raise NotImplementedError
    def raw_to_map_func(raw_value):
        button_state = bool(raw_value)
        set_trackbar_func(control_label, 0)     # Does this work?
        return button_state
    
    def map_to_raw_func(map_value):
        return int(map_value)
    
    return raw_to_map_func, map_to_raw_func

# .....................................................................................................................

def display_is_available():
    
    # Assume we're not running headless if using windows
    if "nt" in os.name:
        return True
    
    # Linux/Mac check
    return ("DISPLAY" in os.environ)

# .....................................................................................................................
    
def display_wh():
    main_screen = screeninfo.get_monitors()[0]
    return main_screen.width, main_screen.height

# .....................................................................................................................
    
def return_type_strings_to_functions(return_type_str):
    
    ret_str_lut = {None: None,
                   "string": str,
                   "integer": int,
                   "float": float,
                   "bool": bool,
                   "list": list,
                   "tuple": tuple}
    
    return ret_str_lut.get(return_type_str)

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap


