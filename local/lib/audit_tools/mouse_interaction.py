#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Aug  1 16:59:44 2020

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
#%% Callback classes

# .....................................................................................................................

class Hover_Callback:
    
    # .................................................................................................................
    
    def __init__(self, frame_wh):
        
        # Allocate storage for mouse movement variables
        self._mouse_moved = False
        self._mouse_xy = np.array((-10000,-10000))
        
        # Allocate storage for mouse click state variables
        self._l_clicked = False
        self._m_clicked = False
        self._r_clicked = False
        
        # Allocate storage for mouse release state variables
        self._l_released = False
        self._m_released = False
        self._r_released = False
        
        # Allocate storage for frame sizing variables
        self.frame_scaling = None
        self.frame_wh = None
        
        # Set initial frame size
        self.update_frame_size(frame_wh)
    
    # .................................................................................................................
    
    def __call__(self, *args, **kwargs):
        self.mouse_callback(*args, **kwargs)
    
    # .................................................................................................................
    
    def update_frame_size(self, new_frame_wh):
        
        frame_width, frame_height = new_frame_wh
        self.frame_scaling = np.float32((frame_width - 1, frame_height - 1))
        self.frame_wh = new_frame_wh
    
    # .................................................................................................................
    
    def mouse_callback(self, event, mx, my, flags, param):
        
        # Get mouse movement & positioning
        self._mouse_xy = np.int32((mx, my))
        self._mouse_moved = (event == cv2.EVENT_MOUSEMOVE)
        
        # Get mouse down/clicked events
        self._l_clicked = (event == cv2.EVENT_LBUTTONDOWN)
        self._m_clicked = (event == cv2.EVENT_MBUTTONDOWN)
        self._r_clicked = (event == cv2.EVENT_RBUTTONDOWN)
        
        # Get mouse up/release events
        self._l_released = (event == cv2.EVENT_LBUTTONUP)
        self._m_released = (event == cv2.EVENT_MBUTTONUP)
        self._r_released = (event == cv2.EVENT_RBUTTONUP)
    
    # .................................................................................................................
    
    def mouse_xy(self, normalized = True):
        
        if normalized:
            return self._mouse_xy / self.frame_scaling
        
        return self._mouse_xy
    
    # .................................................................................................................
    
    def mouse_moved(self):
        return self._mouse_moved
    
    # .................................................................................................................
    
    def left_clicked(self):
        return self._l_clicked
    
    # .................................................................................................................
    
    def middle_clicked(self):
        return self._m_clicked
    
    # .................................................................................................................
    
    def right_clicked(self):
        return self._r_clicked
    
    # .................................................................................................................
    
    def left_released(self):
        return self._l_released
    
    # .................................................................................................................
    
    def middle_released(self):
        return self._m_released
    
    # .................................................................................................................
    
    def right_released(self):
        return self._r_released
    
    # .................................................................................................................
    # .................................................................................................................


# =====================================================================================================================
# =====================================================================================================================


class Drag_Callback(Hover_Callback):
    
    # .................................................................................................................
    
    def __init__(self, frame_wh):
        
        # Inherit from parent
        super().__init__(frame_wh)
        
        # Allocate storage for drag state variables
        self._l_dragged = False
        self._m_dragged = False
        self._r_dragged = False
        
        # Allocate storage for keeping track of drag start/end mouse co-ordinates 
        self._l_drag_pt1 = None
        self._l_drag_pt2 = None
        self._m_drag_pt1 = None
        self._m_drag_pt2 = None
        self._r_drag_pt1 = None
        self._r_drag_pt2 = None
    
    # .................................................................................................................
    
    def mouse_callback(self, event, mx, my, flags, param):
        
        # Get mouse movement & positioning
        self._mouse_xy = np.int32((mx, my))
        self._mouse_moved = (event == cv2.EVENT_MOUSEMOVE)
        
        # Get mouse down/clicked events
        self._l_clicked = (event == cv2.EVENT_LBUTTONDOWN)
        self._m_clicked = (event == cv2.EVENT_MBUTTONDOWN)
        self._r_clicked = (event == cv2.EVENT_RBUTTONDOWN)
        
        # Get mouse up/release events
        self._l_released = (event == cv2.EVENT_LBUTTONUP)
        self._m_released = (event == cv2.EVENT_MBUTTONUP)
        self._r_released = (event == cv2.EVENT_RBUTTONUP)
        
        # Handle left-dragging
        if self._l_clicked:
            self._l_dragged = True
            self._l_drag_pt1 = self._mouse_xy
        if self._l_dragged:
            self._l_drag_pt2 = self._mouse_xy
        if self._l_released:
            self._l_dragged = False
        
        # Handle middle-dragging
        if self._m_clicked:
            self._m_dragged = True
            self._m_drag_pt1 = self._mouse_xy
        if self._m_dragged:
            self._m_drag_pt2 = self._mouse_xy
        if self._m_released:
            self._m_dragged = False
        
        # Handle right-dragging
        if self._r_clicked:
            self._r_dragged = True
            self._r_drag_pt1 = self._mouse_xy
        if self._r_dragged:
            self._r_drag_pt2 = self._mouse_xy
        if self._r_released:
            self._r_dragged = False
        
        return
    
    # .................................................................................................................
    
    def left_dragged(self):
        return self._l_dragged
    
    # .................................................................................................................
    
    def middle_dragged(self):
        return self._m_dragged
    
    # .................................................................................................................
    
    def right_dragged(self):
        return self._r_dragged
    
    # .................................................................................................................
    
    def left_down(self):
        return self._l_dragged or self._l_clicked
    
    # .................................................................................................................
    
    def middle_down(self):
        return self._m_dragged or self._m_clicked
    
    # .................................................................................................................
    
    def right_down(self):
        return self._r_dragged or self._r_clicked
    
    # .................................................................................................................
    
    def get_left_drag_points(self, normalized = True):
        
        if normalized:
            return (self._l_drag_pt1 / self.frame_scaling), (self._l_drag_pt2 / self.frame_scaling)
        
        return self._l_drag_pt1, self._l_drag_pt2
    
    # .................................................................................................................
    
    def get_middle_drag_points(self, normalized = True):
        
        if normalized:
            return (self._m_drag_pt1 / self.frame_scaling), (self._m_drag_pt2 / self.frame_scaling)
        
        return self._m_drag_pt1, self._m_drag_pt2
    
    # .................................................................................................................
    
    def get_right_drag_points(self, normalized = True):
        
        if normalized:
            return (self._r_drag_pt1 / self.frame_scaling), (self._r_drag_pt2 / self.frame_scaling)
        
        return self._r_drag_pt1, self._r_drag_pt2
    
    # .................................................................................................................
    # .................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Polling classes

class Row_Based_Footer_Interactions:
    
    '''
    Class used to streamline basic mouse interactions involving displays that consist of a 'main' image
    (typically a snapshot) with a 'footer' image beneath which is assumed to be organized into rows
    '''
    
    # .................................................................................................................
    
    def __init__(self, main_image_height_px, footer_image_height_px, num_footer_rows = 1):
        
        # Store inputs
        self.main_height_px = main_image_height_px
        self.footer_height_px = footer_image_height_px
        self.total_frame_height = (main_image_height_px + footer_image_height_px)
        self.num_footer_rows = num_footer_rows
        
        # Pre-calculate the location of the boundary between the main & footer images
        self.interface_y_norm = (main_image_height_px / self.total_frame_height)
        self._footer_relative_height_norm = (1.0 - self.interface_y_norm)
    
    # .................................................................................................................
    
    def update_number_of_rows(self, number_of_rows_in_footer):
        
        ''' Function used to update/modify the number of rows in the footer (which is otherwise set on init) '''
        
        self.num_footer_rows = number_of_rows_in_footer
        
        return self.num_footer_rows
    
    # .................................................................................................................
    
    def mouse_over_footer(self, mouse_y, is_normalized = True):
        
        ''' Function used to check if the mouse is hovering over the footer image '''
        
        if is_normalized:
            return (mouse_y > self.interface_y_norm)
        
        return mouse_y > self.main_height_px
    
    # .................................................................................................................
    
    def y_relative_to_footer(self, mouse_y, is_normalized = True):
        
        '''
        Function used to convert the mouse y position from the full-frame co-ordinate system
        into a footer-only co-ordinate system
        For example, if the mouse is hovering at the very top of the footer, this function will
        return a 'relative' y co-ordinate of 0.0 (normalized) or 0px (not normalized)
        '''
        
        if is_normalized:
            return (mouse_y - self.interface_y_norm) / self._footer_relative_height_norm
        
        return mouse_y - self.main_height_px
    
    # .................................................................................................................
    
    def get_footer_row_index(self, mouse_y, is_normalized = True):
        
        '''
        Function used to convert the y co-ordinate of the mouse (in the full-frame co-ordinate system)
        into a row-index of the footer, assuming all rows are equal heights
        '''
        
        # First convert to the footer y co-ordinate system
        mouse_footer_y = self.y_relative_to_footer(mouse_y, is_normalized)
        
        # Force the footer y co-ordinate to be normalized, if needed
        if not is_normalized:
            mouse_footer_y = mouse_footer_y / (self.footer_height_px - 1)
        
        # Calculate the row index
        # For example: for y = 0.0 -> row_index = 0, for y = 0.999 -> row_index = (num_rows - 1)
        row_index = int(self.num_footer_rows * mouse_footer_y)
        
        # To avoid boundary/numerical rounding issues, constrain the index to be between 0 and (num_rows - 1)
        constrained_row_index = max(0, min(row_index, self.num_footer_rows - 1))
        
        return constrained_row_index

    # .................................................................................................................
    # .................................................................................................................


# =====================================================================================================================
# =====================================================================================================================


class Reference_Image_Mouse_Interactions:
    
    '''
    Class used to bundle logic/state associated with mouse interactions involving a
    (assumed to be 'large') reference image which is used to set playback looping start/end points
    
    Most likely individual audit tools will want to inherit from this class and add additional re-draw logic
    '''
    
    # .................................................................................................................
    
    def __init__(self, drag_callback_reference, minimum_drag_length_norm = 0.002):
        
        # Store inputs
        self.callback_ref = drag_callback_reference
        self.minimum_drag_length_norm = minimum_drag_length_norm
        
        # Store some aesthetic settings
        self._subset_fg_line_color = (255, 255, 255)
        self._subset_bg_line_color = (0, 0, 0)
    
    # .................................................................................................................
    
    def _left_drag_event(self):
        
        # Get the clicked/current drag points
        (drag_x_pt1, _), (drag_x_pt2, _) = self.callback_ref.get_left_drag_points()
        
        # Order the dragging co-ords, so we can think of it as a start-to-end (left-to-right)
        start_mx, end_mx = sorted((drag_x_pt1, drag_x_pt2))
        
        # Only update if the start/end points are 'far enough' to be meaningful
        need_to_update_images = (abs(end_mx - start_mx) > self.minimum_drag_length_norm)
        
        return need_to_update_images, start_mx, end_mx
    
    # .................................................................................................................
    
    def _right_clear_event(self):
        
        # Force subset image update on clearing
        need_to_update_images = True
        
        # Reset the start/end subset values
        start_pt_norm = 0
        end_pt_norm = 1
        
        return need_to_update_images, start_pt_norm, end_pt_norm
    
    # .................................................................................................................
    
    def set_subset_line_colors(self, *, fg_line_color = None, bg_line_color = None):
        
        if fg_line_color is not None:
            self._subset_fg_line_color = fg_line_color
        
        if bg_line_color is not None:
            self._subset_bg_line_color = bg_line_color
        
        return self._subset_fg_line_color, self._subset_bg_line_color
    
    # .................................................................................................................
    
    def subset_update(self, force_normalized_range = True):
        
        # Initialize outputs
        need_to_update_images = False
        need_to_draw_subset_indicator_lines = False
        start_pt_norm = None
        end_pt_norm = None
        
        # Handle dragging events, which are used to select a subset of the data for animation display
        if self.callback_ref.left_dragged():            
            need_to_update_images, start_pt_norm, end_pt_norm = self._left_drag_event()
            need_to_draw_subset_indicator_lines = True
        
        # Handle clearing on right click
        if self.callback_ref.right_clicked():
            need_to_update_images, start_pt_norm, end_pt_norm = self._right_clear_event()
            need_to_draw_subset_indicator_lines = False
        
        # Force start/end values to 0.0<->1.0 range if needed
        if force_normalized_range:
            start_pt_norm = max(0, start_pt_norm) if start_pt_norm is not None else None
            end_pt_norm = min(1, end_pt_norm) if end_pt_norm is not None else None
        
        return need_to_update_images, need_to_draw_subset_indicator_lines, start_pt_norm, end_pt_norm
    
    # .................................................................................................................
    
    def draw_reference_subset_lines(self, display_frame, subset_start_norm, subset_end_norm):
        
        # Get frame sizing
        frame_height, frame_width = display_frame.shape[0:2]
        width_scale = (frame_width - 1)
        
        # Convert to pixels so we can position lines
        start_x_px = int(round(subset_start_norm * width_scale))
        end_x_px = int(round(subset_end_norm * width_scale))
        
        # Figure out y start/end positions so the lines draw fully vertical
        y_top = -5
        y_bot = frame_height + 5
        
        # Set up line xy drawing points
        start_line_pts = ((start_x_px, y_top), (start_x_px, y_bot))
        end_line_pts = ((end_x_px, y_top), (end_x_px, y_bot))
        
        # Draw start/end vertical lines with backgrounds
        cv2.line(display_frame, *start_line_pts, self._subset_bg_line_color, 2)
        cv2.line(display_frame, *end_line_pts, self._subset_bg_line_color, 2)
        cv2.line(display_frame, *start_line_pts, self._subset_fg_line_color, 1)
        cv2.line(display_frame, *end_line_pts, self._subset_fg_line_color, 1)
        
        return display_frame
    
    # .................................................................................................................
    # .................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Demo

if __name__ == "__main__":
    pass


# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap


