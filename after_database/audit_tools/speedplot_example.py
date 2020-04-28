#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Dec 17 16:05:23 2019

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

from local.lib.ui_utils.cli_selections import Resource_Selector

from local.offline_database.file_database import launch_file_db, close_dbs_if_missing_data
from local.offline_database.object_reconstruction import Smooth_Hover_Object_Reconstruction, Hover_Mapping
from local.offline_database.object_reconstruction import create_trail_frame_from_object_reconstruction
from local.offline_database.snapshot_reconstruction import median_background_from_snapshots
from local.offline_database.classification_reconstruction import create_objects_by_class_dict, get_ordered_object_list

from local.lib.ui_utils.local_ui.windows_base import Simple_Window

from local.eolib.video.text_rendering import simple_text, relative_text
from local.eolib.utils.cli_tools import Datetime_Input_Parser as DTIP

# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes

class Hover_Callback:
    
    # .................................................................................................................
    
    def __init__(self, frame_wh):
        
        self._mouse_moved = False
        self._mouse_clicked = False
        self._mouse_xy = np.array((-10000,-10000))
        
        frame_width, frame_height = frame_wh
        self.frame_scaling = np.float32((frame_width - 1, frame_height - 1))
        self.frame_wh = frame_wh
    
    # .................................................................................................................
    
    def __call__(self, *args, **kwargs):        
        self.mouse_callback(*args, **kwargs)
    
    # .................................................................................................................
    
    def mouse_callback(self, event, mx, my, flags, param):
        self._mouse_xy = np.int32((mx, my))
        self._mouse_moved = (event == cv2.EVENT_MOUSEMOVE)
        self._mouse_clicked = (event == cv2.EVENT_LBUTTONDOWN)
    
    # .................................................................................................................
    
    def mouse_xy(self, normalized = True):
        
        if normalized:
            return self._mouse_xy / self.frame_scaling
        
        return self._mouse_xy
    
    # .................................................................................................................
    
    def clicked(self):
        return self._mouse_clicked
    
    # .................................................................................................................
    # .................................................................................................................


# =====================================================================================================================
# =====================================================================================================================

class Callback_Sequencer:
    
    # .................................................................................................................
    
    def __init__(self, base_callback_label, base_callback_object, frame_wh):
        
        # Create storage for callback objects (by label) so we can retrieve data as needed
        self._callback_lut = {}
        self._active_cb_lut = {}
        
        # Keep track of total frame size so we can determine which region each callback covers
        self._total_frame_width = 0
        self._total_frame_height = 0
        
        # Add base callback object
        self._add_callback(base_callback_label, base_callback_object, *frame_wh)
    
    # .................................................................................................................
    
    def __call__(self, *args, **kwargs):
        self.mouse_callbacks(*args, **kwargs)
    
    # .................................................................................................................
    
    @property
    def _total_frame_size(self):
        return (self._total_frame_width, self._total_frame_height)
    
    # .................................................................................................................
    
    def _add_callback(self, callback_label, callback_object, add_width = 0, add_height = 0):
        
        # Infer starting co-ordinates, based on what is being added
        hstacking = (add_width > 0)
        vstacking = (add_height > 0)
        start_x = self._total_frame_width if hstacking else 0
        start_y = self._total_frame_height if vstacking else 0
        
        # Build up total frame size as needed
        self._total_frame_width += add_width
        self._total_frame_height += add_height
        
        # Determine frame bounds where this callback will be active
        new_x_bounds = (start_x, self._total_frame_width)
        new_y_bounds = (start_y, self._total_frame_height)
        
        # Add callback to lut so we can access it later as needed
        new_lut_entry = {"obj": callback_object, "x_bounds": new_x_bounds, "y_bounds": new_y_bounds}
        self._callback_lut.update({callback_label: new_lut_entry})
        
        # Add entry to active lut
        self._active_cb_lut.update({callback_label: False})
        
    # .................................................................................................................
    
    def add_callback_vstack(self, callback_label, callback_object, frame_wh):
        frame_height = frame_wh[1]        
        self._add_callback(callback_label, callback_object, add_height = frame_height)
        
    # .................................................................................................................
    
    def add_callback_hstack(self, callback_label, callback_object, frame_wh):
        frame_width = frame_wh[0]        
        self._add_callback(callback_label, callback_object, add_width = frame_width)
        
    # .................................................................................................................
    
    def mouse_callbacks(self, event, mx, my, flags, param):
        
        # Reset active state on all callbacks
        for each_label in self._active_cb_lut.keys():
            self._active_cb_lut[each_label] = False
        
        # Loop over each callback region to figure out which one should be called
        for each_label, each_entry in self._callback_lut.items():
            
            x1, x2 = each_entry["x_bounds"]
            y1, y2 = each_entry["y_bounds"]
            if (x1 <= mx < x2) and (y1 <= my < y2):
                self._active_cb_lut[each_label] = True
                mx_offset, my_offset = (mx - x1,  my - y1)
                each_entry["obj"](event, mx_offset, my_offset, flags, param)
                break
            
    # .................................................................................................................
    
    def is_active(self, callback_label):
        return self._active_cb_lut[callback_label]
    
    # .................................................................................................................
    # .................................................................................................................


# =====================================================================================================================
# =====================================================================================================================


class Hover_Object(Smooth_Hover_Object_Reconstruction):
    
    # .................................................................................................................
    
    def __init__(self, object_metadata, frame_wh, global_start_datetime_isoformat, global_end_datetime_isoformat,
                 smoothing_factor = 0.015):
        
        # Inherit from parent class
        super().__init__(object_metadata, frame_wh, global_start_datetime_isoformat, global_end_datetime_isoformat, 
                         smoothing_factor)
        
        # Calculate the object velocity plot on setup, so we can easily re-use it
        self._vx = np.diff(self.trail_xy[:,0])
        self._vy = np.diff(self.trail_xy[:,1])
        self._velo = np.sqrt(np.square(self._vx) + np.square(self._vy))
        self._num_velo_samples = len(self._velo)
        self._max_velo = np.max(self._velo)
        
        # Calculate heading angle as well, in case we need to animate direction
        self._direction_angle_rad = np.arctan2(self._vy, self._vx)
        
    # .................................................................................................................
    
    def draw_speed_plot(self, median_max_velo, 
                        frame_index = None, frame_width = 640, frame_height = 360, bg_color = (40,40,40)):
        
        # Create a frame to draw in, which matches the 'empty' frame size
        speed_frame = np.full((frame_height, frame_width, 3), bg_color, dtype = np.uint8)
        half_height = int(frame_height / 2)
        half_width = int(frame_width / 2)
        
        # Handle animation
        sample_idx = None
        is_animating = (frame_index is not None)
        if is_animating:
            sample_idx = self.frame_index_to_sample_index(frame_index)
            sample_idx = min(self._num_velo_samples - 1, sample_idx)
            sample_idx = max(0, sample_idx)
        
        # Generate a time basis
        lifetime_ms = self.lifetime_ms
        time_samples = np.linspace(0, lifetime_ms, self._num_velo_samples)
        
        # Set plot parameters
        x1 = 20
        x2 = (frame_width - x1 - 1)
        y1 = 40 
        y2 = (frame_height - y1 - 1)
        plot_width = (x2 - x1)
        plot_height = (y2 - y1)   
        
        # Draw graph title & x axis label
        simple_text(speed_frame, "Object: {}".format(self.nice_id), (half_width, 21), scale = 0.6, center_text = True)
        simple_text(speed_frame, "Time", (half_width, y2 + 16), center_text = True)
        
        # Draw direction, if animating
        if is_animating:
            mid_point = (half_width, half_height)
            circle_radius = 96
            cv2.circle(speed_frame, mid_point, circle_radius, (30, 30, 30), -1, cv2.LINE_AA)
            
            curr_direction = self._direction_angle_rad[sample_idx]
            arrow_x = half_width + int(round(circle_radius * 0.9 * np.cos(curr_direction)))
            arrow_y = half_height + int(round(circle_radius * 0.9 * np.sin(curr_direction)))
            end_pt = (arrow_x, arrow_y)
            
            cv2.arrowedLine(speed_frame, mid_point, end_pt, (80,80,80), 2, cv2.LINE_AA, tipLength = 0.05)
        
        # Determine y-scale (use median max velo if higher than object max velo)
        bump_scale = 1.05
        y_max = max(median_max_velo, self._max_velo) * bump_scale
        
        # Draw median max velo
        med_color = (75, 0, 210)
        median_velo_y = int(y2 - plot_height * (median_max_velo / y_max))
        cv2.line(speed_frame, (x1, median_velo_y), (x2, median_velo_y), med_color, 1)
        simple_text(speed_frame, "(Median of max velocities)", (x1 + 2, median_velo_y - 2), 
                    scale = 0.35, color = med_color)
        
        # Draw speed plot
        time_max = np.max(time_samples)
        x_plot = x1 + plot_width * (time_samples / time_max)
        y_plot = y2 - plot_height * (self._velo / y_max) #self._max_velo)
        
        plot_xy = np.int32(np.round(np.vstack((x_plot, y_plot)).T))
        
        cv2.polylines(speed_frame, [plot_xy], False, self._outline_color, 1, cv2.LINE_AA)
        cv2.rectangle(speed_frame, (x1,y1), (x2,y2), (255, 255, 255), 1)
        relative_text(speed_frame, "{:.1f} sec".format(lifetime_ms / 1000), (-x1, -y1), scale = 0.35)
        
        # Draw point on curve, if animating
        if is_animating:
            plot_idx = tuple(plot_xy[sample_idx])
            cv2.circle(speed_frame, plot_idx, 5, (0, 0, 200), -1, cv2.LINE_AA)
        
        return speed_frame
    
    # .................................................................................................................
    # .................................................................................................................
    

# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

# .....................................................................................................................

def show_looping_animation(snapshot_database, object_database, object_to_animate, 
                           speed_plot_window_ref, median_max_velo, window_x = 50, window_y = 50,
                           start_buffer_time_sec = 3.0, end_buffer_time_sec = 5.5):
    
    # Figure out the time range to animate over
    start_time_ems = np.min(object_to_animate.start_ems)
    end_time_ems = np.max(object_to_animate.end_ems)
    
    # Set up buffer times (used to extend animation range to include time before/after object existence)
    start_buffer_time_ms = int(start_buffer_time_sec * 1000.0)
    end_buffer_time_ms = int(end_buffer_time_sec * 1000.0)
    
    # Make sure we don't reach for snapshots out of the snapshot time range
    earliest_snap, latest_snap = snapshot_database.get_bounding_epoch_ms()
    earliest_time = max(earliest_snap, start_time_ems - start_buffer_time_ms)
    latest_time = min(latest_snap, end_time_ems + end_buffer_time_ms)
    
    # Get all the snapshot times we'll need for animation
    anim_snapshot_times = snapshot_database.get_all_snapshot_times_by_time_range(earliest_time, latest_time)
    
    # Set up the display window
    window_title = "Object {}".format(object_to_animate.nice_id)
    anim_window = Simple_Window(window_title)
    anim_window.move_corner_pixels(window_x, window_y)
    
    # Hard-code key codes
    esc_key = 27
    spacebar = 32
    left_arrow_keys = {81, 97}   # Left or 'a' key
    right_arrow_keys = {83, 100} # Right or "d' key
    
    # Set up frame delay settings
    playback_frame_delay_ms = 150
    pause_frame_delay_ms = 0
    pause_mode = False    
    
    # Loop over snapshots to animate infinitely
    snap_idx = 0
    start_idx = 0
    end_idx = len(anim_snapshot_times)
    while True:
        
        # Get current snap time
        curr_snap_time = anim_snapshot_times[snap_idx]
        
        # Get each snapshot and draw all outlines/trails for all objects in the frame
        snap_image, snap_frame_idx = snapshot_database.load_snapshot_image(curr_snap_time)
        object_to_animate.draw_trail(snap_image, snap_frame_idx, curr_snap_time)
        object_to_animate.draw_outline(snap_image, snap_frame_idx, curr_snap_time)
        speed_frame = obj_to_animate.draw_speed_plot(median_max_velo, frame_index = snap_frame_idx)
        
        # Display the speed plot        
        speed_plot_window_ref.imshow(speed_frame)
        
        # Display the snapshot image, but stop if the window is closed
        winexists = anim_window.imshow(snap_image)
        if not winexists:
            break
        
        # Wait a bit, and stop if esc key is pressed
        frame_delay_ms = (pause_frame_delay_ms if pause_mode else playback_frame_delay_ms)
        keypress = cv2.waitKey(frame_delay_ms)
        if keypress == esc_key:
            break
        
        # Toggle pausing/unpausing with spacebar
        elif keypress == spacebar:
            pause_mode = not pause_mode
            
        # Step back one frame with left key
        elif keypress in left_arrow_keys:
            pause_mode = True
            snap_idx = snap_idx - 1
            
        # Step forward one frame with right key
        elif keypress in right_arrow_keys:
            pause_mode = True
            snap_idx = snap_idx + 1
            
        # Update the snapshot index with looping
        if not pause_mode:
            snap_idx += 1
        if snap_idx >= end_idx:
            snap_idx = start_idx
        elif snap_idx < start_idx:
            snap_idx = end_idx - 1
            
    # Get rid of animation widow before leaving
    anim_window.close()
    
    return
    
# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Select camera/user

enable_debug_mode = False

# Create selector so we can access existing report data
selector = Resource_Selector()
project_root_path, cameras_folder_path = selector.get_project_pathing()

# Select the camera/user to show data for (needs to have saved report data already!)
camera_select, camera_path = selector.camera(debug_mode=enable_debug_mode)
user_select, _ = selector.user(camera_select, debug_mode=enable_debug_mode)


# ---------------------------------------------------------------------------------------------------------------------
#%% Catalog existing data

cinfo_db, snap_db, obj_db, class_db, summary_db = \
launch_file_db(cameras_folder_path, camera_select, user_select,
               launch_snapshot_db = True,
               launch_object_db = True,
               launch_classification_db = True,
               launch_summary_db = False)

# Catch missing data
cinfo_db.close()
close_dbs_if_missing_data(snap_db, error_message_if_missing = "No snapshot data in the database!")
close_dbs_if_missing_data(obj_db, error_message_if_missing = "No object trail data in the database!")


# ---------------------------------------------------------------------------------------------------------------------
#%% Ask user for time window

# Get the maximum range of the data (based on the snapshots, because all we can show)
earliest_datetime, latest_datetime = snap_db.get_bounding_datetimes()

# Ask the user for the range of datetimes to use for selecting data
user_start_dt, user_end_dt = DTIP.cli_prompt_start_end_datetimes(earliest_datetime, latest_datetime,
                                                                 print_help_before_prompt = False,
                                                                 debug_mode = enable_debug_mode)

# Provide feedback about the selected time range
DTIP.print_start_end_time_range(user_start_dt, user_end_dt)


# ---------------------------------------------------------------------------------------------------------------------
#%% Create background frame

# Ask database for several snapshot images, so we can 'average' them to make a background frame for display
bg_frame = median_background_from_snapshots(snap_db, user_start_dt, user_end_dt, 10)
frame_height, frame_width = bg_frame.shape[0:2]
frame_wh = (frame_width, frame_height)


# ---------------------------------------------------------------------------------------------------------------------
#%% Load object data

# Get object metadata from the server
obj_metadata_generator = obj_db.load_metadata_by_time_range(user_start_dt, user_end_dt)

# Create dictionary of 'reconstructed' objects based on object metadata
obj_dict = Hover_Object.create_reconstruction_dict(obj_metadata_generator,
                                                   frame_wh,
                                                   user_start_dt, 
                                                   user_end_dt,
                                                   smoothing_factor = 0.015)

# Organize objects by class label -> then by object id (nested dictionaries)
obj_id_list, obj_by_class_dict, obj_id_to_class_dict = create_objects_by_class_dict(class_db, obj_dict)

# Get an ordered list of the objects for drawing
ordered_obj_list = get_ordered_object_list(obj_id_list, obj_by_class_dict, obj_id_to_class_dict)

# Generate trail hover mapping, for quicker mouse-to-trail lookup
hover_map = Hover_Mapping(obj_by_class_dict)


# ---------------------------------------------------------------------------------------------------------------------
#%% Create static datasets

# Generate the background display frame, containing all object trails
trails_background = create_trail_frame_from_object_reconstruction(bg_frame, ordered_obj_list)

# Figure out max speeds of objects
all_objs_max_velo = [each_obj._max_velo for each_obj in ordered_obj_list]
median_max_velo = np.median(all_objs_max_velo)


# ---------------------------------------------------------------------------------------------------------------------
#%% Interaction loop

# Close any previously open windows
cv2.destroyAllWindows()

# Set up mouse interaction callbacks
trail_hover_callback = Hover_Callback(frame_wh)
cb_sequencer = Callback_Sequencer("trails", trail_hover_callback, frame_wh)

# Set up window positioning
x_spacing = 50
y_spacing = 50
x1 = x_spacing
x2 = 2 * (x_spacing) + frame_width
y1 = y_spacing
y2 = 2 * (y_spacing) + frame_height


# Set up speed plot display
blank_speed_plot_image = np.full((360, 640, 3), (40,40,40), dtype = np.uint8)
simple_text(blank_speed_plot_image, "Hover over a trail to see speed plot...", (320, 180), center_text=True)
speed_window = Simple_Window("Speed Plot")
speed_window.move_corner_pixels(x2, y2)

# Set up main display window
disp_window = Simple_Window("Select Trail")
disp_window.attach_callback(cb_sequencer)
disp_window.move_corner_pixels(x1, y1)
print("", "Press Esc to close", "", sep="\n")

while True:
    
    # Make clean copies of the frames to display, so we don't muddy up the originals
    display_frame = trails_background.copy()
    speed_frame = blank_speed_plot_image
    
    # Respond to trail hovering, if active
    if cb_sequencer.is_active("trails"):
        
        # Get relative mouse co-ords
        mouse_xy = trail_hover_callback.mouse_xy()
        closest_trail_dist, closest_obj_id, closest_obj_class = hover_map.closest_point(mouse_xy)
        
        # Highlight the closest trail/timebar segment if the mouse is close enough
        if closest_trail_dist < 0.05:
            obj_ref = obj_by_class_dict[closest_obj_class][closest_obj_id]
            display_frame = obj_ref.highlight_trail(display_frame)
            speed_frame = obj_ref.draw_speed_plot(median_max_velo)
            
            # Play an animation if the user clicks on the highlighted trail
            if trail_hover_callback.clicked():
                obj_to_animate = obj_ref
                show_looping_animation(snap_db, obj_db, obj_to_animate, speed_window, median_max_velo,
                                       window_x = x2, window_y = y1)
    
    # Display speed plot
    speed_win_exists = speed_window.imshow(speed_frame)
    
    # Show final display
    disp_win_exists = disp_window.imshow(display_frame)
    
    # Close if all windows are closed
    if not (speed_win_exists or disp_win_exists):
        break
    
    # Break on esc key
    keypress = cv2.waitKey(50)
    if keypress == 27:
        break


# Some clean up
cv2.destroyAllWindows()

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap

# TODO
# - add better control over smoothing
# - clean up super hacky implementation
# - display 'median' max velocity on graphs?
# - display 'median' avg velocity on graphs?
# - display units on x/y axis
# - display total lifetime (if not displaying x axis units)
# - have hover over graph that highlights corresponding point on trail (and vice versa)

