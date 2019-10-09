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

from eolib.video.text_rendering import cv2_font_config, getTextSize_wrapper

# ---------------------------------------------------------------------------------------------------------------------
#%% Define Classes


class Local_Timing_Window(Simple_Window):
    
    # .................................................................................................................
    
    def __init__(self, window_name = "Timing"):
        
        # Inherit parent class
        super().__init__(window_name)
        
        # Attach a trackbar for controlling the amount of averaging
        self._trackbar_label = "Averaging"
        self._trackbar_max = 100
        self.add_trackbar(self._trackbar_label, 80, self._trackbar_max)
        
        # Set up display colors
        self.colors = {"bg": (69, 66, 56),
                       "bar": (74, 139, 184),
                       "title_text": (219, 219, 219),
                       "total_text": (255, 255, 255)}
        
        # Set up sizing
        self.sizes = {"screen_wborder": 20,
                      "screen_hborder": 120, 
                      "frame_width": 300,
                      "plot_wborder": 20,
                      "plot_hborder": 20,
                      "bar_height": 30,
                      "entry_spacing": 15,
                      "time_text_inset": 3}
        self.sizes.update({"plot_width": (self.sizes.get("frame_width") - 2 * self.sizes.get("plot_wborder") - 1)})
        self.sizes.update({"minimum_height": 2*self.sizes.get("plot_hborder") + self.sizes.get("bar_height")})
        
        # Set up text rendering
        self.title_text_config = cv2_font_config(color = self.colors.get("title_text"))
        self.total_text_config = cv2_font_config(color = self.colors.get("total_text"))
        (self.text_width, self.text_height), self.text_baseline = \
        getTextSize_wrapper("TOTAL:", **self.total_text_config)
        
        # Storage for re-usable data
        self._no_data_image = self._draw_no_data_image()
        self._background_frame = None
        self._text_position_lut = None
        self._bar_position_tuple_lut = None
        self._prev_stage_timing = {}
        
        # Position window (initially)
        initial_height, initial_width, _ = self._no_data_image.shape
        self._position_window(initial_width, initial_height)
    
    # .................................................................................................................
    
    def display(self, stage_timing = {}):
        
        '''
        Function called to update the timing window display! 
        Timing data is derived from the contents of the stage_timing input. 
        To ensure a consistent timing order the timing input should be an OrderedDict. 
        If the contents changes during runtime, the image will update accordingly (with a potential performance hit)
        
        Inputs:
            stage_timing (ordered dictionary)
            
        Outputs:
            None, but displays an image!
        '''
        
        # Skip all the calculations if the window was closed, to help speed things up!
        if not self.exists():
            return
        
        # Read averaging value
        trackbar_value = self.read_trackbar(self._trackbar_label)
        avg_weight = np.square(1 - (trackbar_value / self._trackbar_max))
        inv_weight = 1 - avg_weight
        
        # Show timing info. May fail if we don't know the stage names (or they change?) in which case, re-draw the bg
        try:
            display_frame = self._update_all_visuals(stage_timing, avg_weight, inv_weight)
            
        except Exception:
            display_frame = self._draw_new_background(stage_timing)
        
        # Show whatever timing image we have available
        self.imshow(display_frame)
        
    # .................................................................................................................
    
    def _draw_no_data_image(self):
        
        ''' Helper init function for drawing an 'empty' image to display when no data is available '''
        
        minimum_width = self.sizes.get("frame_width")
        minimum_height = self.sizes.get("minimum_height")
        empty_shape = (minimum_height, minimum_width, 3)
        empty_frame = np.full(empty_shape, self.colors.get("bg"), dtype = np.uint8)
        
        text_pos = (self.sizes.get("plot_wborder"), 2*self.sizes.get("plot_hborder"))
        cv2.putText(empty_frame, "No timing data available...", text_pos, **self.total_text_config)
        
        return empty_frame
        
    # .................................................................................................................
    
    def _draw_new_background(self, stage_timing):
        
        '''
        Function used to re-draw the background image. Should only be called if there is a mismatch
        between the timing data coming in and what was previously known
        '''
        
        # Reset lookups
        self._text_position_lut = {}
        self._bar_position_tuple_lut = {}
        self._prev_stage_timing = {}
        
        # If not stage timing is available, draw a blank frame
        if len(stage_timing) == 0:
            return self._no_data_image
        
        # Figure out spacing per entry
        full_entry_spacing = self.text_height + self.sizes.get("entry_spacing") + self.sizes.get("bar_height")
        num_entries = len(stage_timing) + 1
        total_entries_height = num_entries * full_entry_spacing
        total_border_height = 2 * self.sizes.get("plot_hborder")
        
        # Set frame sizing based on the number of entries we have
        frame_width = self.sizes.get("frame_width")
        frame_height = total_entries_height + total_border_height
        
        # Draw blank background frame
        frame_shape = (frame_height, frame_width, 3)
        new_background_frame = np.full(frame_shape, self.colors.get("bg"), dtype = np.uint8)
        
        # Draw static elements into the background frame
        border_offset = self.sizes.get("plot_hborder")
        for each_idx, (each_key, each_time) in enumerate(stage_timing.items()):
            
            # Draw static components for each entry
            y_offset = border_offset + (each_idx * full_entry_spacing)
            bar_text_position, bar_tl, bar_y2 = self._draw_new_entry(new_background_frame, each_key, y_offset)
            
            # Store dynamic component positioning
            new_bar_tuple = (bar_tl, bar_y2)
            self._text_position_lut.update({each_key: bar_text_position})
            self._bar_position_tuple_lut.update({each_key: new_bar_tuple})
            
        # Draw total time & store dynamic component positioning
        y_offset += full_entry_spacing
        total_text_position = self._draw_new_total(new_background_frame, y_offset)
        self._text_position_lut.update({"TOTAL": total_text_position})
    
        # Store finished background image
        self._background_frame = new_background_frame
        
        # Re-position the window to account for new background size
        frame_height, frame_width, _ = new_background_frame.shape
        self._position_window(frame_width, frame_height)
        
        return new_background_frame
    
    # .................................................................................................................
    
    def _draw_new_entry(self, draw_frame, stage_name, y_offset):
        
        ''' 
        Function for drawing the static components of each stage entry on the timing window 
        This function also returns the positioning information for the updating components 
        (though updating components are drawn elsewhere)
        '''
        
        # Get positioning info for dynamic components       
        bar_text_pos, bar_tl, bar_y2 = self._get_bar_positioning(y_offset)
        
        # Draw the static components of each entry
        nice_stage_name = stage_name.replace("_", " ").title()
        title_position = self._get_title_positioning(y_offset)
        cv2.putText(draw_frame, nice_stage_name, title_position, **self.title_text_config)
        
        return bar_text_pos, bar_tl, bar_y2    
    
    # .................................................................................................................
    
    def _draw_new_total(self, draw_frame, y_offset):
        
        ''' Function for drawing the (static) title text for the total time in the timing window '''
        
        # Get title text positoning
        bar_text_pos, bar_tl, _ = self._get_bar_positioning(y_offset)
        title_x_pos, _ = bar_tl
        _, shared_y_pos = bar_text_pos
        
        # Draw the static (title) component into the frame
        title_text = "TOTAL: "
        title_pos = (title_x_pos, shared_y_pos)
        cv2.putText(draw_frame, title_text, title_pos, **self.total_text_config)
        
        # Figure out the sizing of the static text so we can figure out the positioning of the dynamic text
        (title_width, title_height), title_base = getTextSize_wrapper(title_text, **self.total_text_config)
        total_time_text_pos = (title_x_pos + title_width, shared_y_pos)
        
        return total_time_text_pos
    
    # .................................................................................................................
    
    def _update_all_visuals(self, stage_timing, new_weight, old_weight):
        
        ''' Function for drawing the dynamic elements on the timing window '''
        
        # If no timing data is available, return an empty image
        if len(stage_timing) == 0:
            return self._no_data_image
        
        # Get base image for drawing
        draw_frame = self._background_frame.copy()
        
        # Get averaged timing data
        averaged_timing = self._calculate_average_timing(stage_timing, new_weight, old_weight)
        
        # Update each stage time text & bar followed by the total timing info
        total_time_sec = sum(averaged_timing.values())
        for each_stage_name in stage_timing.keys():          
            each_stage_time_sec = averaged_timing.get(each_stage_name)
            self._update_entry_visuals(draw_frame, each_stage_name, each_stage_time_sec, total_time_sec)
        self._update_total_visuals(draw_frame, total_time_sec)
            
        return draw_frame
    
    # .................................................................................................................
    
    def _update_entry_visuals(self, draw_frame, stage_name, stage_time_sec, total_time_sec):
        
        ''' 
        Function for drawing the updating components of each stage entry in the timing window 
        This includes both the bar indicating relative timing contribution 
        as well as the time overlayed on top the bar
        '''
        
        # Get pre-calculated positioning info
        text_pos = self._text_position_lut.get(stage_name)
        bar_tl, bar_y2 = self._bar_position_tuple_lut.get(stage_name)
        
        # Calculate some updated timing info for this stage
        time_text = self._format_time_text(stage_time_sec)
        time_fraction = stage_time_sec / total_time_sec
        time_width =  int(round(time_fraction * self.sizes.get("plot_width")))
        
        # Figure out how big the time bar should be
        bar_x2 = bar_tl[0] + time_width
        bar_br = (bar_x2, bar_y2)
        #full_x2 = self.sizes.get("plot_width") + self.sizes.get("plot_wborder")
        
        # Draw the time bar with text over top
        cv2.rectangle(draw_frame, bar_tl, bar_br, self.colors.get("bar"), -1, cv2.LINE_AA)
        cv2.putText(draw_frame, time_text, text_pos, **self.title_text_config)
        #cv2.rectangle(draw_frame, bar_tl, (full_x2, bar_y2), self.colors.get("total_text"), 1, cv2.LINE_AA)
        
    # .................................................................................................................
    
    def _update_total_visuals(self, draw_frame, total_time_sec):
        
        '''
        Function for drawing the updating components of the total time indicator in the timing window
        Unlike the stage timing display, the total time has no bar component. So only text is rendered!
        '''
        
        # Only need to draw the total time text, since there is no bar!
        time_text = self._format_time_text(total_time_sec)
        time_text_pos = self._text_position_lut.get("TOTAL")
        cv2.putText(draw_frame, time_text, time_text_pos, **self.total_text_config)
    
    # .................................................................................................................
    
    def _format_time_text(self, time_sec):
        ''' Function for applying standard string formating to time values (given in seconds) '''
        return "{:.3f} ms".format(1000 * time_sec)
    
    # .................................................................................................................
    
    def _get_bar_positioning(self, y_offset):
        
        ''' Function for figuring out the positioning of stage timing bars & the overlayed text '''
        
        # Get title positioning for the given y-offset, since we'll positoning the bar/text relative to this
        x_pos, y_pos = self._get_title_positioning(y_offset)
        
        # Get bar co-ordinates
        bar_x1, bar_y1 = (x_pos, y_pos + self.text_baseline)
        bar_y2 = bar_y1 + self.sizes.get("bar_height")
        
        # Draw time text over top of the time bar
        bar_mid = int(round((bar_y1 + bar_y2)/2))
        text_y_pos = bar_mid + self.text_baseline
        
        # Bundle useful positioning info for output
        bar_tl_pos = (bar_x1, bar_y1)
        bar_text_pos = (x_pos + self.sizes.get("time_text_inset"), text_y_pos)
        
        return bar_text_pos, bar_tl_pos, bar_y2
    
    # .................................................................................................................
    
    def _get_title_positioning(self, y_offset):
        
        ''' Function for figuring out the positioning of the title text representing each stage '''
        
        x_pos = self.sizes.get("plot_wborder")
        y_pos = self.sizes.get("plot_wborder") + y_offset
        title_pos = (x_pos, y_pos)
        
        return title_pos
    
    # .................................................................................................................
    
    def _calculate_average_timing(self, stage_timing, new_weight, old_weight):
        
        ''' Function for calculating average stage timing'''
        
        try:
            # Try to averaging new values with old. This can fail if we don't have old values though!
            average_timing = {}
            for each_key, each_new_time_sec in stage_timing.items():    
                old_time_sec = self._prev_stage_timing.get(each_key)
                new_average_value = (each_new_time_sec * new_weight) + (old_time_sec * old_weight)
                average_timing.update({each_key: new_average_value})
                
        except TypeError:
            # Copy existing times (as normal dict, not ordered) if averaging fails
            average_timing = {each_key: each_value for each_key, each_value in stage_timing.items()}
            #print("AVERAGING FAILED! (TIMING WINDOW)")
        
        # Store current times as new previous times
        self._prev_stage_timing = average_timing
            
        return average_timing
    
    # .................................................................................................................
    
    def _position_window(self, frame_width, frame_height):
        
        ''' Helper function for placing the timing window on screen with some consistency '''
        
        x_position = self.screen_width - frame_width - self.sizes.get("screen_wborder")
        y_position = self.screen_height - frame_height - self.sizes.get("screen_hborder")
        self.move_corner_pixels(x_position, y_position)
    
    # .................................................................................................................
    # .................................................................................................................
    
    
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
    
    from collections import OrderedDict
    from time import perf_counter
    
    cv2.destroyAllWindows()
    
    # Create a new timing window with no data and hang to show 'no data' display
    new_window = Local_Timing_Window()
    new_window.display({})
    cv2.waitKey(1500)
    
    # Make up a fake timing dictionary
    fake_timing = OrderedDict()
    fake_timing.update({"Stage 1": 0.001})
    fake_timing.update({"Stage 2": 0.0006})
    fake_timing.update({"Stage 3": 0.013})
    fake_timing.update({"Stage 4": 0.007})
    fake_timing.update({"Stage 5": 0.067})
    fake_timing.update({"Stage 6": 0.077})
    fake_timing.update({"Stage 7": 0.087})
    fake_timing.update({"Stage 8": 0.097})
    fake_timing.update({"Stage 9": 0.027})
    
    # Run a bunch of fake 'frames' with random timing data for testing things out
    num_iter = 150
    total_display_cost_sec = 0.0
    for k in range(num_iter):
        
        # Make new fake timing input for each 'frame'
        new_fake_timing = OrderedDict()
        for each_idx, each_key in enumerate(fake_timing):
            new_fake_timing[each_key] = np.random.rand() * (0.5 + (each_idx % 3))
        
        # Update timing display & keep track of how slow the timing itself runs!
        t1 = perf_counter()
        new_window.display(new_fake_timing)
        t2 = perf_counter()
        total_display_cost_sec += (t2 - t1)
        
        # Wait for animation effect
        cv2.waitKey(50)
        
    # Clean up
    cv2.destroyAllWindows()
    print("Average timing window cost (ms/update): {:.3f}".format(1000 * total_display_cost_sec / num_iter))

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap


