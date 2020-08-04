#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Aug  3 09:11:30 2020

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

from local.eolib.utils.colormaps import create_interpolated_colormap
from local.eolib.video.imaging import image_1ch_to_3ch, color_list_to_image, vstack_padded
from local.eolib.video.text_rendering import position_frame_relative, position_center, font_config, simple_text


# ---------------------------------------------------------------------------------------------------------------------
#%% Bar imaging functions

# .....................................................................................................................

def create_single_bar_image(data_list, bar_width, bar_fg_color,
                            bar_bg_color = (40, 40, 40), bar_height = 21, interpolation_type = cv2.INTER_AREA):
    
    '''
    Function used to draw a 'bar image' based off of a list of data
    '''
    
    # For clarity
    bar_wh = (bar_width, bar_height)
    
    # Return a blank image if no data is available
    no_data = (len(data_list) == 0)
    if no_data:
        bar_shape = (bar_height, bar_width, 3)
        blank_bar = np.full(bar_shape, bar_bg_color, dtype = np.uint8)
        return blank_bar
    
    # Convert to array for convenience, and figure out if we're dealing with multichannel data or not
    data_array = np.int32(data_list)
    data_shape = data_array.shape
    num_channels = 1 if (len(data_shape) == 1) else data_shape[1]
    
    # Generate a bar image based on the number of channels we got
    shared_args = (data_array, bar_wh)
    color_args = (bar_fg_color, bar_bg_color)
    if num_channels == 1:
        resized_data_img = create_1_channel_bar_image(*shared_args, *color_args, interpolation_type)
    elif num_channels == 3:
        resized_data_img = create_3_channel_bar_image(*shared_args, interpolation_type)
    else:
        resized_data_img = create_n_channel_bar_image(*shared_args, *color_args, interpolation_type)
    
    return resized_data_img

# .....................................................................................................................

def create_single_bar_subset_image(data_list, start_pt_norm, end_pt_norm,
                                   bar_width, bar_fg_color, bar_bg_color = (40, 40, 40), 
                                   bar_height = 21, interpolation_type = None):
    
    # Use start/end indices to truncate the data list, then create a 'normal' bar image from the reduced data set
    num_samples = len(data_list)
    first_idx = max(0, int(round(start_pt_norm * num_samples)))
    final_idx = min(num_samples, int(round(end_pt_norm * num_samples)))
    data_subset_list = data_list[first_idx:final_idx]
    
    # Determine what kind of interpolation to use, based on whether we have enough pixels to distinguish data points
    if interpolation_type is None:
        num_subset_samples = len(data_subset_list)
        too_few_pixels = (num_subset_samples > bar_width)
        interpolation_type = cv2.INTER_AREA if too_few_pixels else cv2.INTER_NEAREST
    
    return create_single_bar_image(data_subset_list, bar_width, bar_fg_color, bar_bg_color,
                                   bar_height, interpolation_type)

# .....................................................................................................................

def draw_bar_label(bar_image, label_string, align_to_left_edge = True,
                   font_scale = 0.35, font_fg_color = (255, 255, 255), font_bg_color = (0, 0, 0)):
    
    '''
    Function used to render a label onto onto a bar image
    Renders name with a foreground & background element to help distinguish from underlying data
    Assumes text is to be rendered on the left of the bar
    '''
    
    # Get image sizing
    frame_shape = bar_image.shape
    bar_height = frame_shape[0]
    
    # Set up font configuration
    spaced_label = label_string.replace("_", " ")
    bg_font_config_dict = font_config(scale = font_scale, color = font_bg_color, thickness = 2)
    fg_font_config_dict = font_config(scale = font_scale, color = font_fg_color)
    
    # Figure out where to place the text vertically
    bar_y_center = ((bar_height - 1) / 2)
    _, text_y = position_center(spaced_label, (0, bar_y_center), **fg_font_config_dict)
    
    # Figure out how to align the text (i.e. horizontal placement)
    relative_xy = (5, 0) if align_to_left_edge else (-5, 0)
    text_x, _ = position_frame_relative(frame_shape, spaced_label, relative_xy, **fg_font_config_dict)
    
    # Draw label on to the bar (with background outline)
    text_xy = (text_x, text_y)
    bar_image = simple_text(bar_image, spaced_label, text_xy, **bg_font_config_dict)
    bar_image = simple_text(bar_image, spaced_label, text_xy, **fg_font_config_dict)
    
    return bar_image

# .....................................................................................................................

def create_1_channel_bar_image(data_array, bar_wh, bar_fg_color, bar_bg_color,
                               interpolation_type = cv2.INTER_NEAREST):
    
    ''' Helper function used to create bar images when the data is single-channeled (i.e. 1D) '''
    
    # Get min/max data value, to use for determining bar scale
    data_min = np.min(data_array)
    data_max = np.max(data_array)
    
    # Handle case where we don't have a scale to work with
    if data_max == data_min:
        if data_min > 0:
            data_min = data_max - 1
        else:
            data_max = data_min + 1
    
    # Normalize data to 0-255 range for display & create color scale
    norm_data = np.uint8(np.round(255 * ((data_array - data_min) / (data_max - data_min))))
    bgr_dict = {0: bar_bg_color, 255: bar_fg_color}
    cmap = create_interpolated_colormap(bgr_dict)
    
    # Convert normalized data array to an image
    data_gray_img = image_1ch_to_3ch(color_list_to_image(norm_data))
    data_bar_img = cv2.LUT(data_gray_img, cmap)
    resized_data_img = cv2.resize(data_bar_img, dsize = bar_wh, interpolation = interpolation_type)
    
    return resized_data_img

# .....................................................................................................................

def create_3_channel_bar_image(data_array, bar_wh,
                               interpolation_type = cv2.INTER_NEAREST):
    
    ''' Helper function used to create bar images where data is 3D, which is assumed to be RGB '''
    
    # Flip data to be BGR for OpenCV display
    data_bgr = np.uint8(np.flip(data_array, axis = 1))
    
    # Convert the data to an image format, with the desired target sizing for display
    data_as_1px_img = np.expand_dims(data_bgr, axis = 0)
    resized_data_img = cv2.resize(data_as_1px_img, dsize = bar_wh, interpolation = interpolation_type)
    
    return resized_data_img

# .....................................................................................................................

def create_n_channel_bar_image(data_array, bar_wh, bar_fg_color, bar_bg_color,
                               interpolation_type = cv2.INTER_NEAREST):
    
    '''
    Helper function used to create bar images when the number of channels is not 1 or 3
    in these cases, the display is somewhat ambiguous,
    so the channel data is shown vertically stacked within a single bar
    '''
    
    # Figure out the separate bar sizing so we get a correctly size 'single' bar as an output
    num_channels = data_array.shape[1]
    spacer_height_px = 2
    num_1px_spacers = (num_channels - 1)
    bar_width, bar_height = bar_wh
    single_height = int(np.floor((bar_height - spacer_height_px * num_1px_spacers) / num_channels))
    single_wh = (bar_width, single_height)
    
    # Create images for each data channel
    channel_image_list = []
    for each_data_channel in np.rollaxis(data_array, 1):
        new_channel_bar = create_1_channel_bar_image(each_data_channel, single_wh,
                                                      bar_fg_color, bar_bg_color,
                                                      interpolation_type)
        channel_image_list.append(new_channel_bar)
    
    # Create a single bar out of each of the channels for display
    combined_channel_bars = vstack_padded(*channel_image_list,
                                          pad_height = spacer_height_px,
                                          prepend_separator = False,
                                          append_separator = False)
    
    # Finally, resize the combined bars to be the correct target size
    resized_data_img = cv2.resize(combined_channel_bars, dsize = bar_wh, interpolation = cv2.INTER_NEAREST)
    
    return resized_data_img

# .....................................................................................................................

def create_combined_bars_image(bar_images_list,
                               bar_spacing_px = 2, spacing_bg_color = (15, 15, 15),
                               prepend_separator = True, append_separator = True):
    
    '''
    Helper function used to combine a list of separate bar images into a single larger combined image
    
    Inputs:
        bar_images_list -> (List of images) List of bar images to combine, in order
        
        bar_spacing_px -> (Integer) Number of pixels separating each bar when they are stacked
        
        spacing_bg_color -> (Tuple) Color used to fill in spacing between bars
        
        prepend_separator -> (Boolean) If True, a separator will be added to the top of the combined image.
                             The height/color of this separator will be the same as the bar spacing/color
        
        append_separator -> (Boolean) If True, a separator will be added to the bottom of the combined image
    
    Outputs:
        combined_bars_image, total_combined_height
    '''
    
    # Create combined image with all bar images stacked vertically
    combined_bars_image = vstack_padded(*bar_images_list,
                                        pad_height = bar_spacing_px,
                                        padding_color = spacing_bg_color,
                                        prepend_separator = prepend_separator,
                                        append_separator = append_separator)
    
    # Figure out combined bar height, for use with drawing overlays
    total_combined_height = combined_bars_image.shape[0]
    
    return combined_bars_image, total_combined_height

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Color functions

# .....................................................................................................................

def repeat_color_sequence_to_target_length(color_sequence_list, target_list_length):
    
    # Repeat colors if needed to get the target number of color entries in the sequence
    num_colors = len(color_sequence_list)
    num_repeats = 1 + int(target_list_length / num_colors)
    repeated_color_list = color_sequence_list * num_repeats
    output_color_sequence_list = repeated_color_list[0:target_list_length]
    
    return output_color_sequence_list

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Demo

if __name__ == "__main__":
    pass


# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap


