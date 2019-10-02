#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Sep 25 15:06:37 2019

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

from time import perf_counter

from itertools import product

from local.lib.configuration_utils.local_ui.local_windows_base import Simple_Window

from local.lib.configuration_utils.local_ui.local_controls import Local_Window_Controls
from local.lib.configuration_utils.local_ui.local_timing_window import Local_Timing_Window
from local.lib.configuration_utils.local_ui.local_playback_window import Local_Playback_Controls

from local.lib.configuration_utils.display_specification import Tracked_Display

# ---------------------------------------------------------------------------------------------------------------------
#%% Define base class

    
class Video_Processing_Loop:
    
    # .................................................................................................................
    
    def __init__(self, configuration_loader_object):
        
        # Store loader object so we can access all fully configured processing objects
        self.loader = configuration_loader_object
        
        # Allocate resources for display capability
        self.enable_display = None
            
    # .................................................................................................................
    
    def loop(self, display_task_results):
        
        # Set up task display if needed
        display_window_obj_tuples_list = self.setup_task_result_display(display_task_results)
        
        # Start timer for measuring full run-time
        t_start = perf_counter()
        
        # Allocate storage for buffering time info, in case of sudden close/clean up
        prev_fsd_time_args = None
        
        try:
        
            while True:
                
                # Read video frames & get timing info
                req_break, frame, *fsd_time_args = self.read_frames()
                if req_break:
                    break
                prev_fsd_time_args = fsd_time_args
                
                # Capture frames & generate new background images
                bg_outputs = \
                self.run_background_capture(frame, *fsd_time_args)
                
                # Check if we need to save a new snapshot image
                need_new_snapshot, current_snapshot_metadata = \
                self.run_snapshot_capture(frame, *fsd_time_args)
                
                # Perform main core processing for all tasks
                all_skip_frame, all_stage_outputs, all_stage_timing, object_ids_in_frame_dict = \
                self.run_task_processing(bg_outputs, current_snapshot_metadata, *fsd_time_args)
                
                # Display results from task processing
                if display_task_results:
                    self.display_task_results(display_window_obj_tuples_list,
                                              all_skip_frame, all_stage_outputs, *fsd_time_args)
                    
                # Save snapshots if needed, along with info about object ids in the frame
                self.save_snapshots(frame, object_ids_in_frame_dict, need_new_snapshot)
                
        except KeyboardInterrupt:
            print("Keyboard interrupt! Closing...")
        
        # Clean up any open resources
        self.clean_up(*prev_fsd_time_args)
        
        # End runtime timer
        t_end = perf_counter()
        total_processing_time_sec = (t_end - t_start)
        
        return total_processing_time_sec
    
    # .................................................................................................................
    
    def setup_task_result_display(self, enable_local_display):
        
        # Store display state
        self.enable_display = enable_local_display
        
        display_window_obj_tuples_list = []
        if enable_local_display:
            
            # Figure out display positioning
            num_displays = len(self.loader.task_name_list)
            num_cols = 2
            num_rows = int(np.ceil(num_displays / num_cols))
            ordered_displays = []
            
            # Generate display windows & tracked display spec for each task
            for each_idx, each_task_name in enumerate(self.loader.task_name_list):
                new_display = Tracked_Display(each_idx, num_rows, num_cols, window_name = each_task_name)
                ordered_displays.append(new_display)
            
            display_window_obj_tuples_list = self.setup_display_windows(ordered_displays)
            
        return display_window_obj_tuples_list
    
    # .................................................................................................................
    
    def display_task_results(self, display_window_obj_tuples_list, 
                             all_skip_frame, all_stage_outputs, 
                             current_frame_index, current_time_sec, current_datetime):
        
        # Bail if display is disabled so we don't waste time here
        if not self.enable_display:
            return
        
        # Bundle time args for cleanliness
        all_windows_closed = True
        fsd_time_args = (current_frame_index, current_time_sec, current_datetime)
        for disp_obj_tuple, each_task_name in zip(display_window_obj_tuples_list, self.loader.task_name_list):
            
            # Skip frames for the given task, if needed
            if all_skip_frame.get(each_task_name):
                all_windows_closed = False
                continue
            
            # Generate the task result frames
            display_window, display_obj = disp_obj_tuple
            display_image = display_obj.display(all_stage_outputs.get(each_task_name), None, *fsd_time_args)
            
            # Keep track of whether the displays exist
            window_exists = display_window.imshow(display_image)
            if window_exists:
                all_windows_closed = False
                
        # Disable the display if all windows get closed
        if all_windows_closed:
            self.enable_display = False
            print("DISPLAY DISABLED!")
        else:
            cv2.waitKey(1)
            
    # .................................................................................................................
    
    def read_frames(self):
        
        # Grab frames from the video source (with timing information for each frame!)
        req_break, input_frame, current_frame_index, current_time_elapsed_sec, current_datetime = \
        self.loader.vreader.read()
        
        return req_break, input_frame, current_frame_index, current_time_elapsed_sec, current_datetime
    
    # .................................................................................................................
    
    def run_background_capture(self, input_frame, current_frame_index, current_time_sec, current_datetime):
        
        # Handle background capture stage
        bg_outputs = \
        self.loader.bgcap.run(input_frame, current_frame_index, current_time_sec, current_datetime)
        
        return bg_outputs
    
    # .................................................................................................................
    
    def run_snapshot_capture(self, input_frame, current_frame_index, current_time_sec, current_datetime):
        
        # Get snapshot if needed and return most recent snapshot data for object metadata capture
        need_new_snapshot, current_snapshot_metadata = \
        self.loader.snapcap.metadata(input_frame, current_frame_index, current_time_sec, current_datetime)
        
        return need_new_snapshot, current_snapshot_metadata
    
    # .................................................................................................................
    
    def run_task_processing(self, bg_outputs, current_snapshot_metadata,
                            current_frame_index, current_time_elapsed, current_datetime):
        
        # Allocate storage for task-specific outputs
        all_task_skip_frame = {}
        all_task_stage_outputs = {}
        all_task_stage_timing = {}
        object_ids_in_frame_dict = {}
        
        # Run full core-processing for each task
        for each_task_name in self.loader.task_name_list:
            
            # Get easy access to core bundles & corresponding object capturers
            core_ref = self.loader.core_bundles_dict.get(each_task_name)
            objcap_ref = self.loader.objcap_dict.get(each_task_name)
            
            # Handle core processing
            skip_frame, stage_outputs, stage_timing = \
            core_ref.run_all(bg_outputs, 
                             current_frame_index, current_time_elapsed, current_datetime,
                             current_snapshot_metadata)
            
            # Save object metadata when needed & record which object ids are in the frame, for snapshot metadata
            objids_in_frame_list = \
            objcap_ref.run(stage_outputs, current_frame_index, current_time_elapsed, current_datetime)
            
            # Store results for each task
            object_ids_in_frame_dict.update({each_task_name: objids_in_frame_list})
            all_task_skip_frame.update({each_task_name: skip_frame})
            all_task_stage_outputs.update({each_task_name: stage_outputs})
            all_task_stage_timing.update({each_task_name: stage_timing})
            
        return all_task_skip_frame, all_task_stage_outputs, all_task_stage_timing, object_ids_in_frame_dict
    
    # .................................................................................................................
    
    def save_snapshots(self, input_frame, object_ids_in_frame_dict, need_new_snapshot):
        
        # Save snapshot data, with active object ids
        snapshot_frame = \
        self.loader.snapcap.save_snapshots(input_frame, object_ids_in_frame_dict, need_new_snapshot)
        
        return snapshot_frame
    
    # .................................................................................................................
    
    def setup_display_windows(self, ordered_display_obj_list):
        
        # Get windowing area info for window placement
        min_x, max_x = 40, 1500
        min_y, max_y = 250, 1100
        
        # Build some helper functions to simplfy things
        get_row_col_idx = lambda layout_idx, nrows, ncols: list(product(range(nrows), range(ncols)))[layout_idx]
        get_x_corner = lambda col_index, num_cols: int(round(min_x + (max_x - min_x) * col_index / num_cols))
        get_y_corner = lambda row_index, num_rows: int(round(min_y + (max_y - min_y) * row_index / num_rows))
        
        window_obj_tuples = []
        for each_display_obj in ordered_display_obj_list:
            
            # Get display spec and separate into more readable components
            disp_json = each_display_obj.to_json()
            new_window_name = disp_json.get("name", "Unknown")
            is_initial = disp_json.get("initial_display", False)
            drawing_control = disp_json.get("drawing_control", None)
            max_wh = disp_json.get("max_wh", None)
            num_rows = disp_json.get("num_rows", 1)
            num_cols = disp_json.get("num_cols", 1)
            layout_index = disp_json.get("layout_index", 0)
            
            # Warning for bad layout indices
            invalid_layout = (layout_index >= (num_rows * num_cols))
            if invalid_layout:
                err_msg = "Bad layout index ({}), must be less than {} x {}".format(layout_index, num_rows, num_cols)
                raise ValueError(err_msg)
            
            # Bundle re-usable access info
            new_window_ref = Simple_Window(new_window_name)
            new_window_obj_tuple = (new_window_ref, each_display_obj)
            window_obj_tuples.append(new_window_obj_tuple)
            
            # Place window
            row_idx, col_idx = get_row_col_idx(layout_index, num_rows, num_cols)
            x_corner_px = get_x_corner(col_idx, num_cols)
            y_corner_px = get_y_corner(row_idx, num_rows)
            new_window_ref.move_corner_pixels(x_corner_px, y_corner_px)
        
        return window_obj_tuples
    
    # .................................................................................................................
    
    def clean_up(self, current_frame_index, current_time_elapsed_sec, current_datetime):
        
        # Bundle for clarity
        fsd_time_args = (current_frame_index, current_time_elapsed_sec, current_datetime)
        
        # Close externals
        self.loader.snapcap.close(*fsd_time_args)
        self.loader.bgcap.close(*fsd_time_args)
        
        '''
        # Close running core processes & any remaining objects
        for each_task_name in self.loader.task_name_list:
            final_stage_outputs = self.loader.core_bundles_dict.get(each_task_name).close(*fsd_time_args)
            self.loader.objcap_dict.get(each_task_name).close(final_stage_outputs, *fsd_time_args)
        '''
        
        # Close video capture
        self.loader.vreader.close()
    
    # .................................................................................................................
    # .................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Reconfigurable Implementations


class Reconfigurable_Video_Loop(Video_Processing_Loop):
    
    # .................................................................................................................
    
    def __init__(self, configuration_loader_object, *, ordered_display_list = []):
        
        # NEED TO HAVE THIS OBJECT PICK BETWEEN LOCAL/WEB IMPLEMENTATIONS, BASED ON LOADED VIDEO!!!
        
        # Try to close any previously opened windows
        try: cv2.destroyAllWindows()
        except: pass
        
        # Inherit from parent class
        super().__init__(configuration_loader_object)
        
        # Storage for re-configurable object
        self.configurable_ref = configuration_loader_object.configurable_ref
        
        # Storage for debugging info access
        self.debug_frame = None
        self.debug_stage_outputs = None
        self.debug_stage_timing = None
        self.debug_object_ids_in_frame_dict = None
        self.debug_current_snapshot_metadata = None
        self.debug_fsd_time_args = None
        
        # Set up local display windows
        self.controls_json, self.initial_settings, self.local_controls = self.setup_control_windows()
        self.timing_window = self.setup_timing_windows()
        self.playback_controls = self.setup_playback_window()
        self.display_window_obj_tuples = self.setup_display_windows(ordered_display_list)
        
    # .................................................................................................................
    
    def setup_control_windows(self):
        
        # Get UI setup info
        controls_json = self.configurable_ref.controls_manager.to_json()
        initial_settings = self.configurable_ref.current_settings()
        local_controls = Local_Window_Controls(controls_json, initial_settings)
        
        return controls_json, initial_settings, local_controls
    
    # .................................................................................................................
    
    def setup_timing_windows(self):
        
        timing_window = Local_Timing_Window()
        
        return timing_window
    
    # .................................................................................................................
    
    def setup_playback_window(self):
        
        playback_controls = Local_Playback_Controls(self.loader.vreader, self.loader.playback_access)
        
        return playback_controls
    
    # .................................................................................................................
    '''
    def setup_display_windows(self, ordered_display_obj_list):
        
        # Get windowing area info for window placement
        min_x, max_x = 40, 1500
        min_y, max_y = 250, 1100
        
        # Build some helper functions to simplfy things
        get_row_col_idx = lambda layout_idx, nrows, ncols: list(product(range(nrows), range(ncols)))[layout_idx]
        get_x_corner = lambda col_index, num_cols: int(round(min_x + (max_x - min_x) * col_index / num_cols))
        get_y_corner = lambda row_index, num_rows: int(round(min_y + (max_y - min_y) * row_index / num_rows))
        
        window_obj_tuples = []
        for each_display_obj in ordered_display_obj_list:
            
            # Get display spec and separate into more readable components
            disp_json = each_display_obj.to_json()
            new_window_name = disp_json.get("name", "Unknown")
            is_initial = disp_json.get("initial_display", False)
            drawing_control = disp_json.get("drawing_control", None)
            max_wh = disp_json.get("max_wh", None)
            num_rows = disp_json.get("num_rows", 1)
            num_cols = disp_json.get("num_cols", 1)
            layout_index = disp_json.get("layout_index", 0)
            
            # Warning for bad layout indices
            invalid_layout = (layout_index >= (num_rows * num_cols))
            if invalid_layout:
                err_msg = "Bad layout index ({}), must be less than {} x {}".format(layout_index, num_rows, num_cols)
                raise ValueError(err_msg)
            
            # Bundle re-usable access info
            new_window_ref = Simple_Window(new_window_name)
            new_window_obj_tuple = (new_window_ref, each_display_obj)
            window_obj_tuples.append(new_window_obj_tuple)
            
            # Place window
            row_idx, col_idx = get_row_col_idx(layout_index, num_rows, num_cols)
            x_corner_px = get_x_corner(col_idx, num_cols)
            y_corner_px = get_y_corner(row_idx, num_rows)
            new_window_ref.move_corner_pixels(x_corner_px, y_corner_px)
        
        return window_obj_tuples
    '''
    # .................................................................................................................
    
    def reset_all(self):
        self.loader.reset_all()
    
    # .................................................................................................................
    
    def loop(self):
        
        # Allocate storage for buffering time info in case of sudden close/clean up
        prev_fsd_time_args = None
        
        try:
        
            while True:
                
                # Read video frames & get timing info
                req_break, frame, *fsd_time_args = self.read_frames()
                if req_break:
                    break
                prev_fsd_time_args = fsd_time_args
                
                # Check for control updates
                self.read_controls()
                
                # Capture frames & generate new background images
                bg_outputs = \
                self.run_background_capture(frame, *fsd_time_args)
                
                # Check if we need to save a new snapshot image
                need_new_snapshot, current_snapshot_metadata = \
                self.run_snapshot_capture(frame, *fsd_time_args)
                
                # Perform main core processing for all tasks
                all_skip_frame, all_stage_outputs, all_stage_timing, object_ids_in_frame_dict = \
                self.run_task_processing(bg_outputs, current_snapshot_metadata, *fsd_time_args)
                
                # Save snapshots if needed, along with info about object ids in the frame
                self.save_snapshots(frame, object_ids_in_frame_dict, need_new_snapshot)
                
                # Pull out single-task
                skip_frame = all_skip_frame.get(self.loader.task_select)
                stage_outputs = all_stage_outputs.get(self.loader.task_select)
                stage_timing = all_stage_timing.get(self.loader.task_select)
                
                # Display results
                if not skip_frame:
                    self.display_image_data(stage_outputs, *fsd_time_args)
                    self.display_timing_data(stage_timing)
                    
                # Store info for debugging
                self._save_for_debug(frame, stage_outputs, stage_timing, 
                                     object_ids_in_frame_dict, current_snapshot_metadata, fsd_time_args)
                
                # Check for keypresses
                req_break, keypress, video_reset = self.read_keypress()
                if req_break:
                    break
                
                # Reset all stages, since the video position was changed unnaturally
                if video_reset:
                    self.reset_all()
            
        except KeyboardInterrupt:
            print("Keyboard interrupt! Closing...")
        
        # Clean up any open resources
        self.clean_up(*prev_fsd_time_args)
        cv2.destroyAllWindows()
        
        # Save configurable
        self.save_configurable()
        
    # .................................................................................................................
    
    def read_controls(self):
        
        # Read local controls & update the configurable if anything changes
        values_changed_dict = self.local_controls.read_all_controls()
        if values_changed_dict:
            self.configurable_ref.reconfigure(values_changed_dict)
    
    # .................................................................................................................
    
    def read_keypress(self):
        
        # Have playback controls manager keypresses (+ video control!)
        req_break, keypress, video_reset = self.playback_controls.update()
        
        return req_break, keypress, video_reset
    
    # .................................................................................................................
    
    def display_image_data(self, stage_outputs, current_frame_index, current_time_sec, current_datetime):
        
        for each_window_ref, each_display_obj in self.display_window_obj_tuples:
            
            if each_window_ref.exists():
                display_image = each_display_obj.display(stage_outputs, self.configurable_ref,
                                                         current_frame_index, current_time_sec, current_datetime)
                each_window_ref.imshow(display_image)
    
    # .................................................................................................................
    
    def display_timing_data(self, stage_timing):
        self.timing_window.display(stage_timing)
    
    # .................................................................................................................
    
    def save_configurable(self):
        self.loader.ask_to_save_configurable(self.configurable_ref)
    
    # .................................................................................................................
    
    def _save_for_debug(self, frame, stage_outputs, stage_timing, 
                        object_ids_in_frame_dict, current_snapshot_metadata, fsd_time_args):
        
        # Hard-coded storage for accessing helpful debugging info when running as a rec-configurable loop
        self.debug_frame = frame
        self.debug_stage_outputs = stage_outputs
        self.debug_stage_timing = stage_timing
        self.debug_object_ids_in_frame_dict = object_ids_in_frame_dict
        self.debug_current_snapshot_metadata = current_snapshot_metadata
        self.debug_fsd_time_args = fsd_time_args
    
    # .................................................................................................................
    # .................................................................................................................


# =====================================================================================================================
# =====================================================================================================================


class Snapshot_Capture_Video_Loop(Reconfigurable_Video_Loop):
    
    # .................................................................................................................
    
    def __init__(self, configuration_loader_object, ordered_display_list):
        
        # Inherit from parent
        super().__init__(configuration_loader_object, ordered_display_list = ordered_display_list)
        
        # NEED TO HAVE THIS OBJECT PICK BETWEEN LOCAL/WEB IMPLEMENTATIONS, BASED ON LOADED VIDEO!!!
    
    # .................................................................................................................
    
    def loop(self):
        
        # Allocate storage for buffering time info, in case of sudden close/clean up
        prev_fsd_time_args = None
        
        # Allocate fake results for compatibility
        object_ids_in_frame_dict = {}
        
        try:
        
            while True:
                
                # Read video frames & get timing info
                req_break, frame, *fsd_time_args = self.read_frames()
                if req_break:
                    break
                prev_fsd_time_args = fsd_time_args
                
                # Check for control updates
                self.read_controls()
                
                # Only run snapshot functions (with timing!)
                t1 = perf_counter()
                need_new_snapshot, current_snapshot_metadata = self.run_snapshot_capture(frame, *fsd_time_args)
                snapshot_image = self.save_snapshots(frame, object_ids_in_frame_dict, need_new_snapshot)
                t2 = perf_counter()
                
                # Re-use core stage outputs to make use of existing functions (somewhat hacky!)
                stage_timing = self._fake_stage_timing(t1, t2)
                stage_outputs = self._fake_stage_outputs(frame, 
                                                         need_new_snapshot,
                                                         snapshot_image, 
                                                         current_snapshot_metadata)

                
                # Display results
                self.display_image_data(stage_outputs, *fsd_time_args)
                self.display_timing_data(stage_timing)
                
                # Store info for debugging
                self._save_for_debug(frame, stage_outputs, stage_timing, 
                                     object_ids_in_frame_dict, current_snapshot_metadata, fsd_time_args)
                
                # Check for keypresses
                req_break, keypress, video_reset = self.read_keypress()
                if req_break:
                    break
                
                # Reset all stages, since the video position was changed unnaturally
                if video_reset:
                    self.reset_all()
                
        except KeyboardInterrupt:
            print("Keyboard interrupt! Closing...")
        
        # Clean up any open resources
        self.clean_up(*prev_fsd_time_args)
        cv2.destroyAllWindows()
        
        # Save configurable
        self.save_configurable()
        
    # .................................................................................................................
    
    def clean_up(self, current_frame_index, current_time_elapsed_sec, current_datetime):
        
        # Close snapshot object
        fsd_time_args = (current_frame_index, current_time_elapsed_sec, current_datetime)
        self.loader.snapcap.close(*fsd_time_args)
        
        # Close video capture
        self.loader.vreader.close()
    
    # .................................................................................................................

    def _fake_stage_outputs(self, video_frame, need_new_snapshot, snapshot_image, current_snapshot_metadata):
        
        fake_frame_capture_output = {"video_frame": video_frame}
        fake_snapshot_stage_output = {"new_snapshot": need_new_snapshot, 
                                      "snapshot_image": snapshot_image, 
                                      "snapshot_metadata": current_snapshot_metadata}
        
        return {"snapshot_capture": fake_snapshot_stage_output, "frame_capture": fake_frame_capture_output}
    
    # .................................................................................................................

    def _fake_stage_timing(self, start_time_sec, end_time_sec):        
        return {"snapshot_capture": (end_time_sec - start_time_sec)}
    
    # .................................................................................................................
    # .................................................................................................................


# =====================================================================================================================
# =====================================================================================================================

class Background_Capture_Video_Loop(Reconfigurable_Video_Loop):
    
    # .................................................................................................................
    
    def __init__(self, configuration_loader_object, ordered_display_list):
        
        # Inherit from parent
        super().__init__(configuration_loader_object, ordered_display_list = ordered_display_list)
        
        # NEED TO HAVE THIS OBJECT PICK BETWEEN LOCAL/WEB IMPLEMENTATIONS, BASED ON LOADED VIDEO!!!
        
    # .................................................................................................................
    
    def loop(self):
        
        # Allocate storage for buffering time info in case of sudden close/clean up
        prev_fsd_time_args = None
        
        # Allocate fake results for compatibility
        stage_timing = {}
        object_ids_in_frame_dict = {}
        current_snapshot_metadata = {}
        
        try:
        
            while True:
                
                # Read video frames & get timing info
                req_break, frame, *fsd_time_args = self.read_frames()
                if req_break:
                    break
                prev_fsd_time_args = fsd_time_args
                
                # Check for control updates
                self.read_controls()
                
                # Capture frames & generate new background images
                t1 = perf_counter()
                bg_outputs = \
                self.run_background_capture(frame, *fsd_time_args)
                t2 = perf_counter()
                
                # Re-use core stage outputs to make use of existing functionality (somewhat hacky!)
                stage_timing = self._fake_stage_timing(t1, t2)
                stage_outputs = self._fake_stage_outputs(bg_outputs)
                
                # Display results
                self.display_image_data(stage_outputs, *fsd_time_args)
                self.display_timing_data(stage_timing)
                    
                # Store info for debugging
                self._save_for_debug(frame, stage_outputs, stage_timing, 
                                     object_ids_in_frame_dict, current_snapshot_metadata, fsd_time_args)
                
                # Check for keypresses
                req_break, keypress, video_reset = self.read_keypress()
                if req_break:
                    break
                
                # Reset all stages, since the video position was changed unnaturally
                if video_reset:
                    self.reset_all()
            
        except KeyboardInterrupt:
            print("Keyboard interrupt! Closing...")
        
        # Clean up any open resources
        self.clean_up(*prev_fsd_time_args)
        cv2.destroyAllWindows()
        
        # Save configurable
        self.save_configurable()
    
    # .................................................................................................................
    
    def clean_up(self, current_frame_index, current_time_elapsed_sec, current_datetime):
        
        # Close background object
        fsd_time_args = (current_frame_index, current_time_elapsed_sec, current_datetime)
        self.loader.bgcap.close(*fsd_time_args)
        
        # Close video capture
        self.loader.vreader.close()

    # .................................................................................................................

    def _fake_stage_outputs(self, bg_outputs):
        return {"frame_capture": bg_outputs}
    
    # .................................................................................................................

    def _fake_stage_timing(self, start_time_sec, end_time_sec):        
        return {"background_capture": (end_time_sec - start_time_sec)}

    # .................................................................................................................
    # .................................................................................................................


class Object_Capture_Video_Loop(Reconfigurable_Video_Loop):
    
    # .................................................................................................................
    
    def __init__(self, configuration_loader_object, ordered_display_list):
        
        # Inherit from parent
        super().__init__(configuration_loader_object, ordered_display_list = ordered_display_list)
        
        # NEED TO HAVE THIS OBJECT PICK BETWEEN LOCAL/WEB IMPLEMENTATIONS, BASED ON LOADED VIDEO!!!
        
    # .................................................................................................................
    # .................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions


# ---------------------------------------------------------------------------------------------------------------------
#%% Demo 
    
if __name__ == "__main__":
    pass


# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap


