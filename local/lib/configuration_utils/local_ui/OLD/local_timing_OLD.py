#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Jun 18 15:55:17 2019

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

from local.lib.configuration_utils.local_ui.windows_base import Simple_Window

# ---------------------------------------------------------------------------------------------------------------------
#%% Define Classes
    
class Local_Core_Timing_Window_OLD(Simple_Window):
    
    def __init__(self, core_bundle_ref, window_name = "Stage Timing"):
        
        # Inherit parent class
        super().__init__(window_name)
        
        # Attach a trackbar for controlling the amount of averaging
        self._trackbar_label = "Averaging"
        self._trackbar_max = 100
        self.add_trackbar(self._trackbar_label, 75, self._trackbar_max)
        
        # Set up display colors
        self.color_bg = (69, 66, 56)
        self.color_bar = (74, 139, 184)
        self.color_stage_ms_text = (219, 219, 219)
        self.color_total_ms_text = (255, 255, 255)
        
        # Set up basic sizing
        self.gfx_frame_height = None    # Will be calculated based on how many stages are displayed!
        self.gfx_frame_width = 300      # Width of overall window
        self.gfx_plot_border = 20       # X/Y offset spacing
        self.gfx_bar_height = 30        # Relative time bar height
        self.gfx_text_height = 15       # Space allocated for component names
        self.gfx_stage_spacing = 15     # Spacing between each stage listing
        self.gfx_plot_width = self.gfx_frame_width - (2 * self.gfx_plot_border)
        
        # Set up text styling
        self.stage_text_config = {"fontFace": cv2.FONT_HERSHEY_SIMPLEX,
                                  "fontScale": 0.5,
                                  "color": self.color_stage_ms_text,
                                  "thickness": 1,
                                  "lineType": cv2.LINE_AA}
        self.total_text_config = {**self.stage_text_config, "color": self.color_total_ms_text}
        
        # Get the names + order of the stages that we'll be displaying
        self.process_order, self.prev_stage_time_ms_list = self._get_process_order(core_bundle_ref)
        
        # Set up window sizing + default appearance
        self.gfx_frame_height, self.bar_tl_pos_list, total_text_pos = self._get_window_sizing()
        
        # Create the initial frame and record positioning needed for drawing new text updates
        self.bg_frame, self.stage_ms_text_pos_list, self.total_ms_text_pos = self._draw_initial_frame(total_text_pos)
        
        # Draw and position initial frame
        self.imshow(self.bg_frame)
        self.move_corner_pixels(self.screen_width - self.gfx_frame_width - 20,
                                self.screen_height - self.gfx_frame_height - 120)
        
    # .................................................................................................................
        
    def _get_process_order(self, core_bundle_ref):
        
        # Get the actual process order (after potential pruning due to re-configuration!)
        full_processing_squence = core_bundle_ref.full_process_list
        real_processing_sequence = core_bundle_ref.real_process_names_list
        
        # Build actual processing sequence (which should include initial missing stages, e.g. frame_capture)
        actual_process_list = real_processing_sequence.copy()
        actual_process_list.insert(0, full_processing_squence[0])
            
        # Initial stage timing
        prev_stage_time_ms_list = [None for each_stage in actual_process_list]            
            
        return actual_process_list, prev_stage_time_ms_list

    # .................................................................................................................
        
    def _get_window_sizing(self):
        
        # Figure out some info needed to size the frame
        num_stages = len(self.process_order)
        height_per_stage = self.gfx_bar_height + self.gfx_text_height + self.gfx_stage_spacing
        total_ms_text_height = self.gfx_text_height + self.gfx_stage_spacing
        plot_border_total = 2 * self.gfx_plot_border
        
        # Size the height of the frame based on the number of stages being displayed
        frame_height = (num_stages * height_per_stage) + total_ms_text_height + plot_border_total
        
        # Set bar positions
        bar_x_offset = self.gfx_plot_border
        bar_y_offset = self.gfx_plot_border + self.gfx_text_height
        bar_tl_x_list = [bar_x_offset] * num_stages
        bar_tl_y_list = [bar_y_offset + height_per_stage * stage_idx for stage_idx in range(num_stages)]
        bar_plot_tl_pos_list = list(zip(bar_tl_x_list, bar_tl_y_list))
        
        # Figure out the positioning of the total time text, and draw it in to the frame
        last_bar_x, last_bar_y = bar_plot_tl_pos_list[-1]
        total_text_x = last_bar_x
        total_text_y = last_bar_y + height_per_stage
        total_text_pos = (total_text_x, total_text_y)
        
        return frame_height, bar_plot_tl_pos_list, total_text_pos
    
    # .................................................................................................................
        
    def _draw_initial_frame(self, total_text_pos):
        
        # Pull out the bar x/y data for convenience
        bar_x_list, bar_y_list = zip(*self.bar_tl_pos_list)
        
        # Set up the stage title text positioning
        stage_title_x_list = [each_bar_x for each_bar_x in bar_x_list]
        stage_title_y_list = [each_bar_y - 5 for each_bar_y in bar_y_list]
        stage_title_pos_list = list(zip(stage_title_x_list, stage_title_y_list))
        
        # Set the time text position for each bar plot
        stage_ms_x_list = [each_bar_x + 5 for each_bar_x in bar_x_list]
        stage_ms_y_list = [each_bar_y + self.gfx_bar_height - 10 for each_bar_y in bar_y_list]
        stage_ms_pos_list = list(zip(stage_ms_x_list, stage_ms_y_list))
    
        # Figure out where to draw each bit of text and bar plot and draw in the elements that won't change
        blank_frame = np.full((self.gfx_frame_height, self.gfx_frame_width, 3), self.color_bg, dtype=np.uint8)
        for each_stage_name, each_title_pos in zip(self.process_order, stage_title_pos_list):
            
            # Draw the stage names in to the image, since they don't need to be updated over time
            nice_name = each_stage_name.replace("_", " ").title()
            cv2.putText(blank_frame, nice_name, each_title_pos, **self.stage_text_config)
        
        # Draw the total text into the frame as well, since it doesn't change
        total_text_fixed = "TOTAL: "
        cv2.putText(blank_frame, total_text_fixed, total_text_pos, **self.total_text_config)
        
        # Figure out the positioning of the total time (ms) text
        sizing_config = {"fontFace": self.total_text_config["fontFace"], 
                         "fontScale": self.total_text_config["fontScale"], 
                         "thickness": self.total_text_config["thickness"]}
        total_text_size, _ = cv2.getTextSize(total_text_fixed, **sizing_config)
        total_ms_text_pos = (total_text_pos[0] + total_text_size[0], total_text_pos[1])
        
        return blank_frame, stage_ms_pos_list, total_ms_text_pos
    
    # .................................................................................................................
    
    def update_timing_display(self, stage_timing):
        
        # Get a copy of the background image, so we don't mess it up
        timing_image = self.bg_frame.copy()
        
        # Calculate updated (and averaged) times
        stage_time_ms_list, total_time_ms = self.calculate_avg_stage_times(stage_timing)
        
        # Combine all the info in a zipped list ahead of time for readability
        name_time_bar_text_ziplist = zip(self.process_order, 
                                         stage_time_ms_list, 
                                         self.bar_tl_pos_list, 
                                         self.stage_ms_text_pos_list)
        
        # Draw each bar + timing text
        for each_stage_name, each_time_ms, each_bar_tl_pos, each_text_pos in name_time_bar_text_ziplist:
            
            # Calculate the percentage of total time each stage represents
            each_time_fraction = each_time_ms / total_time_ms
            time_text = "{:.3f} ms".format(each_time_ms)
            
            # Get bar co-ordinates
            bar_x1, bar_y1 = each_bar_tl_pos
            bar_x2 = bar_x1 + int(each_time_fraction * self.gfx_plot_width)
            bar_y2 = bar_y1 + self.gfx_bar_height
            
            # Draw the time bar and then the actual time (as text) over top
            cv2.rectangle(timing_image, (bar_x1, bar_y1), (bar_x2, bar_y2), self.color_bar, -1, cv2.LINE_AA)
            cv2.putText(timing_image, time_text, each_text_pos, **self.stage_text_config)
            
        # Add total timing info
        total_text = "{:.3f} ms".format(total_time_ms)
        cv2.putText(timing_image, total_text, self.total_ms_text_pos, **self.total_text_config)
    
        # Finally, show the image!
        self.imshow(timing_image)
        
    # .................................................................................................................
        
    def calculate_avg_stage_times(self, stage_timing):
        
        # First read the trackbar to find the desired weighting
        trackbar_value = self.read_trackbar(self._trackbar_label)
        avg_weight = np.square(1 - (trackbar_value / self._trackbar_max))
        inv_weight = 1 - avg_weight
        
        # First get the stage times, in order, in units of milliseconds (from seconds originally)
        new_stage_time_ms_list = [1000 * stage_timing[each_stage_name] for each_stage_name in self.process_order]
        
        # Calculate new average (exponential smoothing) time
        times_zipped = zip(new_stage_time_ms_list, self.prev_stage_time_ms_list)
        #avg_time_list = [(new_time * avg_weight) + (old_time * inv_weight) for new_time, old_time in times_zipped]
        avg_time_list = [self._running_average(new_time, old_time, avg_weight, inv_weight) \
                         for new_time, old_time in times_zipped]
        
        # Finally calculate the total (based on the averaged value, not the instantaneous times!)
        total_time_ms = np.sum(avg_time_list)
        
        # Finally update the internal record of the stage timing
        self.prev_stage_time_ms_list = avg_time_list
        
        return avg_time_list, total_time_ms
    
    # .................................................................................................................
    
    def _running_average(self, new_time, old_time, new_weight, old_weight):
        
        try:
            avg_value = (new_time * new_weight) + (old_time * old_weight)
        except TypeError:
            avg_value = new_time
            
        return avg_value
    
    # .................................................................................................................
    # .................................................................................................................


# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////

    
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


