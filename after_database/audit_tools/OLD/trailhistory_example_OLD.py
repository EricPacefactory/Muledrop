#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Sep 19 16:48:43 2019

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

from itertools import cycle

import cv2
import numpy as np

from scipy.interpolate import UnivariateSpline

from local.lib.selection_utils import Resource_Selector

from local.lib.configuration_utils.local_ui.windows_base import Simple_Window

from eolib.utils.read_write import load_json

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
            
            x1, x2 = each_entry.get("x_bounds")
            y1, y2 = each_entry.get("y_bounds")
            if (x1 <= mx < x2) and (y1 <= my < y2):
                self._active_cb_lut[each_label] = True
                mx_offset, my_offset = (mx - x1,  my - y1)
                each_entry.get("obj")(event, mx_offset, my_offset, flags, param)
                break
            
    # .................................................................................................................
    
    def is_active(self, callback_label):
        return self._active_cb_lut.get(callback_label)
    
    # .................................................................................................................
    # .................................................................................................................


# =====================================================================================================================
# =====================================================================================================================
    

class Object_Reconstruction:
    
    # .................................................................................................................
    
    def __init__(self, object_metadata, frame_wh, time_bar_wh, global_start_index, global_end_index, 
                 number_simplified_points = 11):
        
        # Store full copy of metadata for easy re-use
        self.metadata = obj_metadata
        self.num_samples = self.metadata.get("num_samples")
        self.nice_id = self.metadata.get("nice_id")
        self.full_id = self.metadata.get("full_id")
        
        # Store object trail separately, since we'll want to use that a lot
        obj_x_array = np.float32(object_metadata.get("tracking").get("x_track"))
        obj_y_array = np.float32(object_metadata.get("tracking").get("y_track"))
        #self.trail_xy = np.vstack((obj_x_array, obj_y_array)).T
        self._real_trail_xy = np.vstack((obj_x_array, obj_y_array)).T
        
        # Store smoothed trail
        self.smoothed_trail_xy = []        
        interp_idx = np.linspace(0, 1, self.num_samples)
        smooth_x = UnivariateSpline(interp_idx, obj_x_array, s = 0.005)
        smooth_y = UnivariateSpline(interp_idx, obj_y_array, s = 0.005)
        self.trail_xy = np.vstack((smooth_x(interp_idx), smooth_y(interp_idx))).T
        
        # Store simplified version of trail for mouse-distance checks
        full_idx = np.linspace(0.0, 1.0, self.num_samples)
        interp_idxs = np.linspace(0.0, 1.0, number_simplified_points)
        obj_x_simple = np.interp(interp_idxs, full_idx, obj_x_array)
        obj_y_simple = np.interp(interp_idxs, full_idx, obj_y_array)
        self._simple_trail_xy = np.vstack((obj_x_simple, obj_y_simple)).T
        
        # Store object start/end time
        self.start_idx = self.metadata.get("timing").get("first_frame_index")
        self.end_idx = self.metadata.get("timing").get("last_frame_index")
        
        # Store global start/end indices for relative timing calculations
        self.global_start_idx = global_start_index
        self.global_end_idx = global_end_index
        self.global_idx_length = global_end_index - global_start_index + 1
        
        # Store drawing sizes & scalings
        self.frame_wh = frame_wh
        self.bar_wh = bar_wh
        self.frame_scaling_array = np.float32(frame_wh) - np.float32((1, 1))
        self.bar_scaling_array = np.float32(bar_wh) - np.float32((1, 1))
    
    # .................................................................................................................
    
    def draw_outline(self, output_frame, plot_to_frame_index, line_color = (0, 255, 0), line_thickness = 1):
        
        # Don't bother trying to draw anything if there aren't any samples!
        plot_idx = self.end_idx - plot_to_frame_index 
        if plot_idx < 0 or plot_idx >= self.num_samples:
            return
        
        # Convert outline to pixel units and draw it
        hull = self.metadata.get("tracking").get("hull")[plot_idx]
        hull_array = np.int32(np.round(np.float32(hull) * self.frame_scaling_array))
        cv2.polylines(output_frame, 
                      pts = [hull_array], 
                      isClosed = True, 
                      color = line_color,
                      thickness = line_thickness,
                      lineType = cv2.LINE_AA)        
    
    # .................................................................................................................
    
    def draw_trail(self, output_frame, plot_to_frame_index = None,
                   line_color = (0, 255, 255), line_thickness = 1):
        
        # Get reduced data set for plotting
        if plot_to_frame_index:
            last_idx = max(0, self.end_idx - plot_to_frame_index)
            reduced_trail_xy = self.trail_xy[last_idx:]
        else:
            reduced_trail_xy = self.trail_xy
        #reduced_trail_xy = self._simple_trail_xy
        
        # Convert trail data to pixel units and draw as an open polygon
        trail_xy_px = np.int32(np.round(reduced_trail_xy * self.frame_scaling_array))
        cv2.polylines(output_frame, 
                      pts = [trail_xy_px],
                      isClosed = False, 
                      color = line_color,
                      thickness = line_thickness,
                      lineType = cv2.LINE_AA)
        
        return output_frame
        
    # .................................................................................................................
    
    def highlight_trail(self, output_frame, plot_to_frame_index = None):
        
        self.draw_trail(output_frame, plot_to_frame_index,
                        line_color = (255, 0, 255), 
                        line_thickness = 2)
        
        return output_frame
    
    # .................................................................................................................
    
    def draw_time_slice(self, output_frame, bar_color = (0, 255, 255)):
        
        # Get relative start and end times for drawing
        relative_start, relative_end = self._get_relative_start_end()
        
        # Calculate pixelized values
        start_px = int(np.ceil(relative_start * self.bar_scaling_array[0]))
        end_px = int(np.floor(relative_end * self.bar_scaling_array[0]))
        y_top_px = -10
        y_bot_px = int(self.bar_scaling_array[1] + 10 )
        
        # Generate rectangle bounding box for drawing
        rect_tl = (start_px, y_top_px)
        rect_br = (end_px - 1, y_bot_px)
        
        cv2.rectangle(output_frame, 
                      pt1 = rect_tl,
                      pt2 = rect_br, 
                      color = bar_color,
                      thickness = -1,
                      lineType = cv2.LINE_4)
        
        return output_frame
    
    # .................................................................................................................
    
    def highlight_time_slice(self, output_frame):
        self.draw_time_slice(output_frame, bar_color = (255, 0, 255))
    
    # .................................................................................................................
    
    def minimum_sq_distance(self, point_xy_normalized):
        
        # Ideally find the shortest distance to the path, which would involve finding the distance
        # to each point & line segment!
        
        # For now, just find the minimum distance to all (simplified) co-ords
        sq_distances = np.sum(np.power(self._simple_trail_xy - point_xy_normalized, 2), axis = 1)
        min_sq_distance = np.min(sq_distances)
        
        return min_sq_distance
    
    # .................................................................................................................
    
    def hovering_time_slice(self, x_point_normalized):
        
        # Get start and end times to see if the x point is contained (hovering) within
        relative_start, relative_end = self._get_relative_start_end()       
        
        return relative_start < x_point_normalized <= relative_end        
    
    # .................................................................................................................
    
    def get_bounding_snap_counts(self, padding = 3):
        
        # Access built-in snapshot metadata to figure out what the first and last snapshot counts were
        snap_metadata = self.metadata.get("snapshots")
        start_count = snap_metadata.get("first").get("count")
        end_count = snap_metadata.get("last").get("count")
        
        return max(0, start_count - padding), max(start_count +1, end_count + padding)
    
    # .................................................................................................................
    
    def _get_relative_start_end(self):
        
        # Get relative start and end times for this object (as fractional values, should be between 0 and 1)
        relative_start = (self.start_idx - self.global_start_idx) / self.global_idx_length
        relative_end = (self.end_idx - self.global_start_idx) / self.global_idx_length
        
        return relative_start, relative_end
    
    # .................................................................................................................
    # .................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

# .....................................................................................................................

def load_metadata(path):       
        
    try:
        metadata = load_json(path)        
        
    except Exception:
        # Objects alive at the end of the processed file will appear in the snapshot metadata, 
        # but will not have saved any object metadata, causing an error when trying to load them!
        metadata = None
        
    return metadata

# .....................................................................................................................

def load_snapshot_image_from_metadata(snapshot_image_folder, path_to_metadata_file):
    
    snap_metadata = load_metadata(path_to_metadata_file)
    snapshot_frame_index = snap_metadata.get("frame_index")
    snap_name = snap_metadata.get("name")
    snap_image_name = "{}.jpg".format(snap_name)
    snap_image_path = os.path.join(snapshot_image_folder, snap_image_name)
    
    return snapshot_frame_index, cv2.imread(snap_image_path)

# .....................................................................................................................

def draw_outline(frame, object_metadata, final_plot_index, frame_scaling_array):
    
    # Don't bother trying to draw anything if there aren't any samples!
    num_samples = object_metadata.get("num_samples")
    if num_samples <= final_plot_index:
        return
    
    # Convert outline to pixel units and draw it
    hull = object_metadata.get("tracking").get("hull")
    hull_array = np.int32(np.round(np.float32(hull[final_plot_index]) * frame_scaling_array))
    cv2.polylines(frame, 
                  pts = [hull_array], 
                  isClosed = True, 
                  color = (0, 255, 0),
                  thickness = 1,
                  lineType = cv2.LINE_AA)

# .....................................................................................................................
    
def get_snapshot_startend_timing(snap_data_paths_list):
    
    first_snap_path = snap_data_paths_list[0]
    first_snap_data = load_metadata(first_snap_path)
    first_frame_index = first_snap_data.get("frame_index")
    
    last_snap_path = snap_data_paths_list[-1]
    last_snap_data = load_metadata(last_snap_path)
    last_frame_index = last_snap_data.get("frame_index")
    
    return first_frame_index, last_frame_index

# .....................................................................................................................

def show_looping_animation(object_list, start_snap_count, end_snap_count, snapshot_image_folder, snap_data_paths_list):
    
    # First figure out which snapshot data we'll actually use for the animation
    safe_end_snap_count = min(len(snap_data_paths_list), end_snap_count + 1)    
    snaps_to_animate = snap_data_paths_list[start_snap_count:safe_end_snap_count]
    
    object_ids_string = ", ".join([str(each_obj.nice_id) for each_obj in object_list])
    obj_prefix = "Object" if len(object_list) < 2 else "Objects:"
    window_title = "{} {}".format(obj_prefix, object_ids_string)
    anim_window = Simple_Window(window_title)
    anim_window.move_corner_pixels(x_pixels = 400, y_pixels = 200)
    
    #print("ANIMATING", start_snap_count, safe_end_snap_count)
    
    # Loop over snapshots to animate infinitely
    snap_path_inf_list = cycle(snaps_to_animate)
    for each_snap_path in snap_path_inf_list:
        
        snapshot_idx, snapshot_image = load_snapshot_image_from_metadata(snapshot_image_folder, each_snap_path)
        
        for each_obj in object_list:
            each_obj.draw_trail(snapshot_image, snapshot_idx)
            each_obj.draw_outline(snapshot_image, snapshot_idx)
        
        winexists = anim_window.imshow(snapshot_image)
        if not winexists:
            break
        
        # Wait a bit, and stop if esc key is pressed
        keypress = cv2.waitKey(150)
        if keypress == 27:
            break
    
    # Get rid of animation widow before leaving
    anim_window.close()

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Get report data pathing

# Select the camera/user/task to show data for (needs to have saved report data already!)
selector = Resource_Selector()
project_root_path, cameras_folder_path = selector.get_project_pathing()

camera_select, camera_path = selector.camera()
user_select, _ = selector.user(camera_select)
task_select, _ = selector.task(camera_select, user_select)

# Build base report folder path
report_data_folder_path = os.path.join(cameras_folder_path, camera_select, "report", user_select)

# Folders containing reported data
object_metadata_folder = os.path.join(report_data_folder_path, "metadata", "objects-({})".format(task_select))
snapshot_metadata_folder = os.path.join(report_data_folder_path, "metadata", "snapshots")
snapshot_image_folder = os.path.join(report_data_folder_path, "images", "snapshots")

# Make sure the report data folders exist
check_paths = (object_metadata_folder, snapshot_metadata_folder, snapshot_image_folder)
if not all([os.path.exists(each_path) for each_path in check_paths]):
    raise FileNotFoundError("Couldn't find report data paths!")
    

# ---------------------------------------------------------------------------------------------------------------------
#%% Get snap/object metadata 

# Some helper functions
sorted_data_paths = lambda folder: [os.path.join(folder, each_file) for each_file in sorted(os.listdir(folder))]
remove_dir = lambda path: os.path.basename(path)
remove_idx = lambda file: file.split("-")[0]
name_path_tuples = lambda paths: [(remove_idx(remove_dir(each_path)), each_path) for each_path in paths]

# Grab list of loading paths for snapshot metadata and a LUT of object IDs and corresponding metadata loading paths
snap_data_paths_list = sorted_data_paths(snapshot_metadata_folder)
obj_data_paths_list = sorted_data_paths(object_metadata_folder)
obj_data_paths_dict = {int(each_id): each_path for each_id, each_path in name_path_tuples(obj_data_paths_list)}

# Handle possible future error (object data stored across multiple indexed files, which currently isn't supported)
find_idx_error = lambda file: (int(file.split(".")[0].split("-")[1]) > 0)
if any((find_idx_error(remove_dir(each_path)) for each_path in obj_data_paths_list)):
    raise ValueError("Found object with non-zero partition index! Trail history does not support this (yet)!")

# Find first & last frame indices for getting relative timing data
first_frame_idx, last_frame_idx = get_snapshot_startend_timing(snap_data_paths_list)


# ---------------------------------------------------------------------------------------------------------------------
#%% Load background

# Try to load a background image to use as the background for trail history
# ...

# Otherwise load the first snapshots as a background
_, trail_background = load_snapshot_image_from_metadata(snapshot_image_folder, snap_data_paths_list[0])

# Set up scaling for drawing
frame_height, frame_width = trail_background.shape[0:2]
frame_scaling = np.float32((frame_width - 1, frame_height - 1))
frame_wh = (frame_width, frame_height)

# Create time bar frame, for plotting object start/end times
bar_bg_color = (40, 40, 40)
bar_width, bar_height = frame_width, 30
bar_background = np.full((bar_height, bar_width, 3), bar_bg_color, dtype=np.uint8)
bar_scaling = np.float32((bar_width - 1, bar_height - 1))
bar_wh = (bar_width, bar_height)

# Set up variables for playback start/end points
playback_start_idx = None
playback_end_idx = None

# ---------------------------------------------------------------------------------------------------------------------
#%% Load object data

display_frame = trail_background.copy()

from time import perf_counter
t1 = perf_counter()

obj_recon_list = []
for each_obj_path in obj_data_paths_list:    
    obj_metadata = load_metadata(each_obj_path)
    new_recon = Object_Reconstruction(obj_metadata, 
                                      frame_wh = frame_wh,
                                      time_bar_wh = bar_wh,
                                      global_start_index = first_frame_idx,
                                      global_end_index = last_frame_idx)
    obj_recon_list.append(new_recon)
    
t2 = perf_counter()
print("", "Loading, decompression & storage took (ms): {:.3f}".format(1000 * (t2 - t1)), sep = "\n")


# ---------------------------------------------------------------------------------------------------------------------
#%% Interaction loop

# Close any previously open windows
cv2.destroyAllWindows()

trail_hover_callback = Hover_Callback(frame_wh)
bar_hover_callback =  Hover_Callback(bar_wh)
cb_sequencer = Callback_Sequencer("trails", trail_hover_callback, frame_wh)
cb_sequencer.add_callback_vstack("timebar", bar_hover_callback, bar_wh)

disp_window = Simple_Window("Display")
disp_window.attach_callback(cb_sequencer)
disp_window.move_corner_pixels(50, 50)


while True:
    
    # Make clean copies of the frames to display, so we don't muddy up the originals
    display_frame = trail_background.copy()
    time_bar_frame = bar_background.copy()
    
    # Draw all trails & time bar slices (ideally don't do this every time unconditionally!!!)
    for each_recon in obj_recon_list:
        each_recon.draw_trail(display_frame)
        each_recon.draw_time_slice(time_bar_frame)
    
    # Respond to trail hovering, if active
    if cb_sequencer.is_active("trails"):
        
        # Get relative mouse co-ords
        mouse_xy = trail_hover_callback.mouse_xy()
        
        # Check the distance to every trail
        mouse_sq_dists = []
        for each_recon in obj_recon_list:
            each_sq_dist = each_recon.minimum_sq_distance(mouse_xy)
            mouse_sq_dists.append(each_sq_dist)
        
        # Check if the closest distance is 'close enough' and if so, highlight it & the corresponding time bar slice
        closest_idx = None
        closest_dist = np.min(mouse_sq_dists)
        if closest_dist < 0.05:
            closest_idx = np.argmin(mouse_sq_dists)
            obj_recon_list[closest_idx].highlight_trail(display_frame)
            obj_recon_list[closest_idx].highlight_time_slice(time_bar_frame)
        
        # If the user clicks while hovering, play a looping video of the object trail they clicked on (if any)
        if closest_idx is not None:
            if trail_hover_callback.clicked():                
                obj_ref = obj_recon_list[closest_idx]
                start_snap, end_snap = obj_ref.get_bounding_snap_counts(5)
                objs_to_animate_list = [obj_ref]
                show_looping_animation(objs_to_animate_list, start_snap, end_snap, 
                                       snapshot_image_folder, snap_data_paths_list)
    
    # Respond to time bar hovering, if active
    if cb_sequencer.is_active("timebar"):
        
        # Get relative mouse co-ords
        x_norm, y_norm = bar_hover_callback.mouse_xy()
        
        # Check which object time bars are being hovered
        obj_idx_hovered_list = []
        for each_idx, each_recon in enumerate(obj_recon_list):
            if each_recon.hovering_time_slice(x_norm):
                obj_idx_hovered_list.append(each_idx)
                each_recon.highlight_trail(display_frame)
                each_recon.highlight_time_slice(time_bar_frame)

        # If the user clicks while hovering, play a looping video of the time bar slice they clicked on (if any)
        if bar_hover_callback.clicked() and len(obj_idx_hovered_list) > 0:
            
            objs_to_animate_list = [obj_recon_list[each_idx] for each_idx in obj_idx_hovered_list]
            start_snap, end_snap = 1E8, -1
            for each_obj in objs_to_animate_list:
                
                # Figure out what the largest start/end range is, based on all objects highlighted
                new_start_snap, new_end_snap = each_obj.get_bounding_snap_counts(5)
                if new_start_snap < start_snap: start_snap = new_start_snap
                if new_end_snap > end_snap: end_snap = new_end_snap
                
            # Show animation of all objects highlighted on time bar
            show_looping_animation(objs_to_animate_list, start_snap, end_snap, 
                                   snapshot_image_folder, snap_data_paths_list)
        
    # Combine the display & bar frames
    combined_frame = np.vstack((display_frame, time_bar_frame))
    
    # Show final display
    winexist = disp_window.imshow(combined_frame)
    if not winexist:
        break
    
    # Break on esc key
    keypress = cv2.waitKey(50)
    if keypress == 27:
        break


# Clean up
cv2.destroyAllWindows()




# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap

# TODO
# - add classification coloring/annotations (at least as placeholder)
# - load existing background image instead of first snapshot
# - add better control over smoothing
# - improve mouse-to-nearest-trail detection (only using points now, better to check point-to-line-segment distances)
# - add mouse scroll wheel control (on trail hover) that selects between second,third,fourth etc. closest trails
# - add lasso drawing capability to trail hover (i.e. exclude trails outside of lasso region)
# - add input for controling the time bar scale (zooming in/out over time)
# - add playback on spacebar keypress
# - add 1/2 playback boundary controls. Should also adjust to only show trails in boundary! Reset bounds with 0 key
# - would be nice to show time bars separately, with each obj having it's own (thin) bar (but super complicated...!?)
# - clean up implementation. Probably best to standardize data access, put functionality in separate library file


