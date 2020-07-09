#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Jun 30 14:40:12 2020

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

from collections import deque

from local.lib.ui_utils.display_specification import Display_Window_Specification

from local.eolib.video.imaging import crop_y1y2x1x2_from_zones_list, make_cropmask_1ch, image_to_channel_column_vector
from local.eolib.video.imaging import crop_pixels_in_place, zoom_on_frame, add_frame_border

from local.eolib.video.text_rendering import simple_text

# ---------------------------------------------------------------------------------------------------------------------
#%% Define configuration displays


class Zoomed_Station_Display(Display_Window_Specification):
    
    # .................................................................................................................
    
    def __init__(self, layout_index, num_rows, num_columns, initial_display = False,
                 min_zoom_size = 250, max_zoom_size = 600):
        
        # Inherit from parent class
        super().__init__("Station (zoomed)", layout_index, num_rows, num_columns,
                         initial_display = initial_display, drawing_json = None,
                         limit_wh = False)
        
        # Store zoom settings
        self._min_zoom_size = min_zoom_size
        self._max_zoom_size = max_zoom_size
    
    # .................................................................................................................
    
    def get_crop_info(self, configurable_ref):
        
        return configurable_ref._crop_y1y2x1x2, configurable_ref._cropmask_2d3ch
    
    # .................................................................................................................
    
    def _get_cropmasked_frame(self, full_display_frame, crop_y1y2x1x2, cropmask_2d3ch):
        
        # Apply crop/mask/grayscale conversion as is done with the configurable itself
        crop_frame = crop_pixels_in_place(full_display_frame, crop_y1y2x1x2)
        cropmasked_frame = cv2.bitwise_and(crop_frame, cropmask_2d3ch)
        
        return cropmasked_frame
    
    # .................................................................................................................
    
    def _create_zoomed_output(self, cropmasked_frame):
        
        # Zoom in on the cropped/masked segment if it is too small, and add a border to help visualize boundary
        zoomed_frame = zoom_on_frame(cropmasked_frame, self._min_zoom_size, self._max_zoom_size)
        
        return add_frame_border(zoomed_frame)
    
    # .................................................................................................................
    
    def preprocess_full_frame(self, full_frame, configurable_ref):
        
        # OVERRIDE FOR CUSTOMIZED FUNCTIONALITY
        
        return full_frame
    
    # .................................................................................................................
    
    def postprocess_cropmasked_frame(self, cropmasked_frame, configurable_ref):
        
        # OVERRIDE FOR CUSTOMIZED FUNCTIONALITY
        
        return cropmasked_frame
    
    # .................................................................................................................
        
    def display(self, stage_outputs, configurable_ref, mouse_xy, 
                current_frame_index, current_epoch_ms, current_datetime):
        
        # Get frame for display
        full_display_frame = stage_outputs["video_capture_input"]["video_frame"]
        
        # Get cropping info to pick-out the station to display
        crop_y1y2x1x2, cropmask_2d3ch = self.get_crop_info(configurable_ref)
        
        # Get cropped & masked frame, with potential pre- & post-processing
        preprocessed_full_frame = self.preprocess_full_frame(full_display_frame, configurable_ref)
        cropmasked_frame = self._get_cropmasked_frame(preprocessed_full_frame, crop_y1y2x1x2, cropmask_2d3ch)
        postprocessed_cropmasked_frame = self.postprocess_cropmasked_frame(cropmasked_frame, configurable_ref)
        
        # Zoom & add a border to the final display frame
        bordered_frame = self._create_zoomed_output(postprocessed_cropmasked_frame)
        
        return bordered_frame
    
    # .................................................................................................................
    # .................................................................................................................


# =====================================================================================================================
# =====================================================================================================================


class Data_Display_3ch(Display_Window_Specification):
    
    # .................................................................................................................
    
    def __init__(self, layout_index, num_rows, num_columns, initial_display = False,
                 window_name = "Station Data (3ch)",
                 ch1_color = (0, 0, 255),
                 ch2_color = (0, 255, 0),
                 ch3_color = (255, 80, 80),
                 minimum_value = 0,
                 maximum_value = 255,
                 display_width = 900,
                 display_height = 512):
        
        # Inherit from parent class
        super().__init__(window_name, layout_index, num_rows, num_columns,
                         initial_display = initial_display,
                         provide_mouse_xy = True,
                         drawing_json = None,
                         limit_wh = False)
        
        # Store configuration data
        self._ch1_color = tuple(ch1_color)
        self._ch2_color = tuple(ch2_color)
        self._ch3_color = tuple(ch3_color)
        self._min_value = minimum_value
        self._max_value = maximum_value
        self._display_width = display_width
        self._display_height = display_height
        
        # Allocate storage for drawing image
        self._full_x_array = np.arange(0, display_width, dtype = np.int32)
        self._scale_value = np.float32((1 + self._max_value - self._min_value) / display_height)
        self._blank_bg = np.zeros((display_height, display_width, 3), dtype=np.uint8)
        self._draw_background_grid(self._blank_bg)
        
        # Allocate
        self._data_deck = deque([], maxlen = display_width)
    
    # .................................................................................................................
    
    def _draw_background_grid(self, display_frame, num_grid = 17, grid_gray_value = 35, grid_thickness = 1):
        
        # Set up grid locations
        grid_spacing = (self._display_height / num_grid)
        grid_color = [grid_gray_value] * 3
        for k in range(1 + num_grid):
            line_y = int(round(k * grid_spacing))
            self.draw_horizontal_line(display_frame, line_y, grid_color, grid_thickness)
        
        return display_frame
    
    # .................................................................................................................
    
    def get_latest_plot_data(self, configurable_ref):
        return configurable_ref._latest_one_frame_result_for_config
    
    # .................................................................................................................
    
    def scale_to_display_height(self, input_value):
        return np.int32(np.round((1.0 + np.float32(self._max_value) - np.float32(input_value)) / self._scale_value))
    
    # .................................................................................................................
    
    def draw_horizontal_line(self, display_frame, y_pixel_value, line_color = (100, 100, 100), line_thickness = 1):
        
        line_pt1 = (-5, y_pixel_value)
        line_pt2 = (5 + self._display_width, y_pixel_value)
        cv2.line(display_frame, line_pt1, line_pt2, line_color, line_thickness, cv2.LINE_4)
        
        return display_frame
    
    # .................................................................................................................
    
    def draw_data_plot(self, display_frame):
        
        # Generate x plot co-ords
        num_data = len(self._data_deck)        
        x_data_array = self._full_x_array[-num_data:]
        
        # Generate y plot co-ords
        y_data_array = self.scale_to_display_height(self._data_deck)
        
        # Combine x/y & draw plot
        plot_data_ch1_array = np.vstack((x_data_array, y_data_array[:, 0])).T
        plot_data_ch2_array = np.vstack((x_data_array, y_data_array[:, 1])).T
        plot_data_ch3_array = np.vstack((x_data_array, y_data_array[:, 2])).T
        
        cv2.polylines(display_frame, [plot_data_ch1_array], False, self._ch1_color, 1, cv2.LINE_AA)
        cv2.polylines(display_frame, [plot_data_ch2_array], False, self._ch2_color, 1, cv2.LINE_AA)
        cv2.polylines(display_frame, [plot_data_ch3_array], False, self._ch3_color, 1, cv2.LINE_AA)
        
        return display_frame
    
    # .................................................................................................................
    
    def draw_mouse_value(self, display_frame, mouse_xy):
        
        # For clarity
        mouse_x, mouse_y = mouse_xy
        line_color = (100, 100, 100)
        
        # Convert mouse-xy to data value for display
        mouse_y_norm = (self._display_height - mouse_y) / self._display_height
        mouse_y_data = int(round(self._max_value * mouse_y_norm))
        
        # Draw horizontal line to indicate mouse y
        self.draw_horizontal_line(display_frame, mouse_y, line_color)
        
        # Draw text to indicate data value for the drawn line
        text_xy = tuple(mouse_xy + np.int32((0, -8)))
        text_xy = (int(self._display_width / 2), mouse_y)
        simple_text(display_frame, "{}".format(mouse_y_data), text_xy, center_text = True)
        
        return display_frame
    
    # .................................................................................................................
    
    def draw_overlay(self, display_frame, configurable_ref):
        # Function used to provide custom graphics in addition to standard mouse-over + plotting
        # Not used by default...
        return display_frame
    
    # .................................................................................................................
    
    def display(self, stage_outputs, configurable_ref, mouse_xy, 
                current_frame_index, current_epoch_ms, current_datetime):
        
        # Update the internal copy of the dataset
        latest_data = self.get_latest_plot_data(configurable_ref)
        self._data_deck.append(latest_data)
        
        # Get a copy of the blank background and draw annotations/plot onto it
        display_frame = self._blank_bg.copy()
        self.draw_overlay(display_frame, configurable_ref)
        self.draw_mouse_value(display_frame, mouse_xy)
        self.draw_data_plot(display_frame)
        
        return display_frame
    
    # .................................................................................................................
    # .................................................................................................................



# =====================================================================================================================
# =====================================================================================================================


class Data_Display_1ch(Data_Display_3ch):
    
    # .................................................................................................................
    
    def __init__(self, layout_index, num_rows, num_columns, initial_display = False,
                 window_name = "Station Data (1ch)",
                 ch1_color = (255, 255, 255),
                 minimum_value = 0,
                 maximum_value = 255,
                 display_width = 900,
                 display_height = 512):
        
        # Inherit from parent class
        super().__init__(layout_index, num_rows, num_columns, initial_display, window_name,
                         ch1_color = ch1_color,
                         ch2_color = (0, 0, 0),
                         ch3_color = (0, 0, 0),
                         minimum_value = minimum_value,
                         maximum_value = maximum_value,
                         display_width = display_width,
                         display_height = display_height)
    
    # .................................................................................................................
    
    # OVERRIDING
    def draw_data_plot(self, display_frame):
        
        # Generate x plot co-ords
        num_data = len(self._data_deck)        
        x_data_array = self._full_x_array[-num_data:]
        
        # Generate y plot co-ords
        y_data_array = self.scale_to_display_height(self._data_deck)
        
        # Combine x/y & draw plot
        plot_data_array = np.vstack((x_data_array, y_data_array)).T
        
        return cv2.polylines(display_frame, [plot_data_array], False, self._ch1_color, 1, cv2.LINE_AA)
    
    # .................................................................................................................
    # .................................................................................................................


# =====================================================================================================================
# =====================================================================================================================


class Boolean_Result_Display(Data_Display_1ch):
    
    # .................................................................................................................
    
    def __init__(self, layout_index, num_rows, num_columns, initial_display = False,
                 window_name = "Boolean Result",
                 ch1_color = (0, 255, 255),
                 display_width = 900,
                 display_height = 256):
        
        # Hard-code some values for display
        self._y_offset = (0.1 * display_height)        
        self._plot_height = (display_height - 2 * self._y_offset)
        
        # Inherit from parent class
        minimum_value, maximum = 0, 1
        super().__init__(layout_index, num_rows, num_columns, initial_display, window_name, ch1_color,
                         minimum_value, maximum, display_width, display_height)
    
    # .................................................................................................................
    
    # OVERRIDING
    def _draw_background_grid(self, display_frame, num_grid = 2, grid_gray_value = 65, grid_thickness = 2):
        
        # Get the true/false line positions
        false_y = self.scale_to_display_height(0)
        true_y = self.scale_to_display_height(1)
        
        # Only draw the true/false lines
        grid_color = [grid_gray_value] * 3
        self.draw_horizontal_line(display_frame, false_y, grid_color, grid_thickness)
        self.draw_horizontal_line(display_frame, true_y, grid_color, grid_thickness)
        
        return display_frame
    
    # .................................................................................................................
    
    # OVERRIDING
    def scale_to_display_height(self, input_value):
        
        float_input = np.float32(input_value)
        scaled_offset_boolean = self._y_offset + (self._plot_height * (1.0 - float_input))
        
        return np.int32(np.round(scaled_offset_boolean))
    
    # .................................................................................................................
    
    # OVERRIDING
    def draw_data_plot(self, display_frame):
        
        # Generate x plot co-ords
        num_data = len(self._data_deck)        
        x_data_array = self._full_x_array[-num_data:]
        
        # Generate y plot co-ords
        y_data_array = self.scale_to_display_height(self._data_deck)
        
        # Combine x/y & draw plot
        plot_data_array = np.vstack((x_data_array, y_data_array)).T
        
        return cv2.polylines(display_frame, [plot_data_array], False, self._ch1_color, 1, cv2.LINE_AA)
    
    # .................................................................................................................
    
    # OVERRIDING
    def draw_mouse_value(self, display_frame, mouse_xy):
        # Don't bother drawing the mouse over for boolean data
        return display_frame
    
    # .................................................................................................................
    # .................................................................................................................


# =====================================================================================================================
# =====================================================================================================================


class Leveled_Data_Display(Data_Display_1ch):
    
    # .................................................................................................................
    
    def __init__(self, layout_index, num_rows, num_columns, initial_display = False,
                 window_name = "Station Data (Levels)",
                 ch1_color = (255, 255, 255),
                 lower_level_color = (80, 180, 180),
                 upper_level_color = (0, 255, 255),
                 minimum_value = 0,
                 maximum_value = 255,
                 display_width = 500,
                 display_height = 256):
        
        # Inherit from parent class
        super().__init__(layout_index, num_rows, num_columns, initial_display, 
                         window_name, ch1_color, minimum_value, maximum_value, display_width, display_height)
        
        # Store varibles unique to this class
        self._lower_level_color = lower_level_color
        self._upper_level_color = upper_level_color
    
    # .................................................................................................................
    
    def get_levels(self, configurable_ref):
        return configurable_ref._lower_upper_levels_for_config
    
    # .................................................................................................................
    
    def draw_overlay(self, display_frame, configurable_ref):
        
        # First get level data for drawing
        lower_level, upper_level = self.get_levels(configurable_ref)
        
        # Convert levels to display locations
        lower_y = self.scale_to_display_height(lower_level)
        upper_y = self.scale_to_display_height(upper_level)
        
        # Draw horizontal lines for lower/upper levels
        self.draw_horizontal_line(display_frame, lower_y, self._lower_level_color)
        self.draw_horizontal_line(display_frame, upper_y, self._lower_level_color)
        
        return display_frame
    
    # .................................................................................................................
    # .................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Define crop helpers

# .....................................................................................................................

def inmask_pixels_1ch(frame_1ch, mask_logical_1ch):
    
    '''
    Function which applies a mask to a single-channel frame and returns only the masked-in values
    This is useful when doing stats-based calculations on the pixels,
    since it avoids including the masked off values in the calculation.
    
    Note however that because the masked-off pixels are removed, 
    the output is not suitable for any processing requiring spatial information!
    
    Inputs:
        frame_1ch -> (Image Data/Numpy array) A single-channel (e.g. grayscale) frame
        
        mask_logical_1ch -> (Numpy array) A single-channel logical mask to apply to the given frame.
                            Areas that should be kept (i.e. 'mask-in') should have values of True/1,
                            while areas to mask out should have values of False/0
    
    Outputs:
        inmask_pixels_1d_array (numpy array)
    
    Note: The shape of the output will be M x 1, where M is the number of mask-in pixels
    '''
    
    # First convert the input frame to 1d data
    frame_1d = np.ravel(frame_1ch)
    
    # Now use logical mask to index only the in-mask pixels
    inmask_pixels_1d_array = frame_1d[mask_logical_1ch]
    
    return inmask_pixels_1d_array

# .....................................................................................................................

def inmask_pixels_3ch(frame_3ch, mask_logical_1ch):
    
    '''
    Function which applies a mask to a 3-channel frame and returns only the masked-in values
    This is useful when doing stats-based calculations on the pixels,
    since it avoids including the masked off values in the calculation.
    
    Note however that because the masked-off pixels are removed, 
    the output is not suitable for any processing requiring spatial information!
    
    Inputs:
        frame_3ch -> (Image Data/Numpy array) A 3-channel (e.g. color) frame
        
        mask_logical_1ch -> (Numpy array) A single-channel logical mask to apply to the given frame.
                            Areas that should be kept (i.e. 'mask-in') should have values of True/1,
                            while areas to mask out should have values of False/0
    
    Outputs:
        inmask_pixels_1d_array (numpy array)
        
    Note: The shape of the output will be M x 3, where M is the number of mask-in pixels
    '''
    
    # First convert the input frame to 1d data
    num_pixels = np.prod(frame_3ch.shape[0:2])
    frame_1d = np.reshape(frame_3ch, (num_pixels, 3))
    
    # Now use logical mask to index only the in-mask pixels
    inmask_pixels_1d_array = frame_1d[mask_logical_1ch]
    
    return inmask_pixels_1d_array

# .....................................................................................................................

def build_cropping_dataset(frame_wh, station_zones_list, padding_wh = (0, 0)):
    
    '''
    Function used to generate standard datasets used for cropping
    
    Inputs:
        frame_wh -> (Tuple) The width and height of the frame to be cropped
        
        station_zones_list -> (List-of-lists-of-xy pairs) The list of zones to be cropped
        
        padding_wh -> (Tuple) Used to extend the outer border of the cropped regions. Useful if the region
                      needs some spatial processing (e.g. blurring) before applying crop mask
    
    Outputs:
        crop_y1y2x1x2_list, cropmask_2d3ch_list, logical_cropmask_1d_list
    '''
    
    # Get cropping co-ordinates
    crop_y1y2x1x2_list, _ = crop_y1y2x1x2_from_zones_list(frame_wh,
                                                          station_zones_list,
                                                          zones_are_normalized = True,
                                                          padding_wh = padding_wh,
                                                          error_if_no_zones = False)
    
    # Get 2D & logical 1D cropmask data
    cropmask_2d3ch_list = []
    logical_cropmask_1d_list = []
    for each_crop_y1y2x1x2, each_zone in zip(crop_y1y2x1x2_list, station_zones_list):
        
        # Generate the single-channel 2d cropmasks
        cropmask_1ch = make_cropmask_1ch(frame_wh, each_zone, each_crop_y1y2x1x2)
        cropmask_3ch = cv2.cvtColor(cropmask_1ch, cv2.COLOR_GRAY2BGR)
        cropmask_2d3ch_list.append(cropmask_3ch)
        
        # From the 2d cropmasks, generate the 1d logical cropmasks
        cropmask_1ch_as_col_vector = image_to_channel_column_vector(cropmask_1ch)
        logical_cropmask_1d = (cropmask_1ch_as_col_vector[:,0] > 127)
        logical_cropmask_1d_list.append(logical_cropmask_1d)
    
    return crop_y1y2x1x2_list, cropmask_2d3ch_list, logical_cropmask_1d_list

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Demo
    
if __name__ == "__main__":
    pass
    

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap


