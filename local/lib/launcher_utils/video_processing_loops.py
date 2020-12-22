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

from tqdm import tqdm
from time import perf_counter
from itertools import product
from collections import OrderedDict

from local.lib.common.exceptions import OS_Close

from local.lib.ui_utils.local_ui.windows_base import Simple_Window, Max_WH_Window, Drawing_Window
from local.lib.ui_utils.local_ui.controls import Local_Window_Controls
from local.lib.ui_utils.local_ui.timing import Local_Timing_Window
from local.lib.ui_utils.local_ui.playback import Local_Playback_Controls
from local.lib.ui_utils.display_specification import Tracked_Display


# ---------------------------------------------------------------------------------------------------------------------
#%% Define base class


class Video_Processing_Loop:
    
    # .................................................................................................................
    
    def __init__(self, configuration_loader_object, enable_display):
        
        # Store loader object so we can access all fully configured processing objects
        self.loader = configuration_loader_object
        
        # Storage for display settings
        self.enable_display = enable_display
        
    # .................................................................................................................
    
    def _loop_no_display(self, enable_progress_bar = False):
        
        # Allocate storage for buffering time info, in case of sudden close/clean up
        prev_fed_time_args = [None, None, None]
        
        # Set up progress bar
        if enable_progress_bar:
            total_frames = self.loader.vreader.total_frames
            cli_prog_bar = tqdm(total = total_frames, mininterval = 0.5)
        
        try:
            
            while True:
                
                # Read video frames & get timing info
                req_break, frame, read_time_sec, *fed_time_args = self.read_frames()
                if req_break:
                    break
                prev_fed_time_args = fed_time_args
                
                # Capture snapshots
                self.run_snapshot_capture(frame, *fed_time_args)
                
                # Capture frames & generate new background images
                background_args = self.run_background_capture(frame, *fed_time_args)
                
                # Perform main core processing
                stage_outputs, _ = \
                self.run_core_processing(frame, read_time_sec, *background_args, *fed_time_args)
                
                # Perform station processing
                self.run_station_processing(frame, *background_args, *fed_time_args)
                
                # Capture object data
                self.run_object_capture(stage_outputs, *fed_time_args)
                
                # Provide progress feedback if needed
                if enable_progress_bar:
                    cli_prog_bar.update()
            
        except KeyboardInterrupt:
            print("", "Keyboard interrupt! Closing...", sep = "\n")
        
        except SystemExit:
            print("", "Done! User ended...", sep = "\n")
        
        except OS_Close:
            print("", "System terminated! Quitting...", sep = "\n")
        
        # Clean up the progress bar, if needed
        if enable_progress_bar:
            cli_prog_bar.close()
            print("")
        
        return prev_fed_time_args
        
    # .................................................................................................................
    
    def _loop_with_display(self, enable_progress_bar = False):
        
        # Allocate storage for buffering time info, in case of sudden close/clean up
        prev_fed_time_args = [None, None, None]
        
        # Set up display windows
        window_ref, display_obj = create_simple_display_window(self.loader)
        
        # Set up progress bar
        if enable_progress_bar:
            total_frames = self.loader.vreader.total_frames
            cli_prog_bar = tqdm(total = total_frames, mininterval = 0.5)
        
        try:
        
            while True:
                
                # Read video frames & get timing info
                req_break, frame, read_time_sec, *fed_time_args = self.read_frames()
                if req_break:
                    break
                prev_fed_time_args = fed_time_args
                
                # Capture snapshots
                self.run_snapshot_capture(frame, *fed_time_args)
                
                # Capture frames & generate new background images
                background_args = self.run_background_capture(frame, *fed_time_args)
                
                # Perform main core processing
                stage_outputs, _ = \
                self.run_core_processing(frame, read_time_sec, *background_args, *fed_time_args)
                
                # Perform station processing
                self.run_station_processing(frame, *background_args, *fed_time_args)
                
                # Capture object data
                self.run_object_capture(stage_outputs, *fed_time_args)
                
                # Display tracking results
                simple_display(window_ref, display_obj, stage_outputs, *fed_time_args)
                
                # Provide progress feedback if needed
                if enable_progress_bar:
                    cli_prog_bar.update()
            
        except KeyboardInterrupt:
            print("", "Keyboard interrupt! Closing...", sep = "\n")
        
        except SystemExit:
            print("", "Done! User ended...", sep = "\n")
        
        except OS_Close:
            print("", "System terminated! Quitting...", sep = "\n")
        
        # Clean up the progress bar, if needed
        if enable_progress_bar:
            cli_prog_bar.close()
            print("")
        
        return prev_fed_time_args
        
    # .................................................................................................................
    
    def loop(self, *, enable_progress_bar):
        
        # Start timer for measuring full run-time
        t_start = perf_counter()
        
        # Run processing loop, with or without display depending on inputs
        if self.enable_display:
            final_fed_time_args = self._loop_with_display(enable_progress_bar)
        else:
            final_fed_time_args = self._loop_no_display(enable_progress_bar)
            
        # Clean up any open resources
        self.clean_up(*final_fed_time_args)
        
        # End runtime timer
        t_end = perf_counter()
        total_processing_time_sec = (t_end - t_start)
        
        return total_processing_time_sec
            
    # .................................................................................................................
    
    def read_frames(self):
        
        # Grab frames from the video source (with timing information for each frame!)
        req_break, input_frame, read_time_sec, current_frame_index, current_epoch_ms, current_datetime = \
        self.loader.vreader.read()
        
        return req_break, input_frame, read_time_sec, current_frame_index, current_epoch_ms, current_datetime
    
    # .................................................................................................................
    
    def run_background_capture(self, input_frame, current_frame_index, current_epoch_ms, current_datetime):
        
        # Handle background capture stage
        background_image, background_was_updated = \
        self.loader.bgcap.run(input_frame, current_frame_index, current_epoch_ms, current_datetime)
        
        return background_image, background_was_updated
    
    # .................................................................................................................
    
    def run_snapshot_capture(self, input_frame, current_frame_index, current_epoch_ms, current_datetime):
        
        # Handle snapshot capture stage
        snapshot_frame, current_snapshot_metadata = \
        self.loader.snapcap.run(input_frame, current_frame_index, current_epoch_ms, current_datetime)
        
        return snapshot_frame, current_snapshot_metadata
    
    # .................................................................................................................
    
    def run_object_capture(self, stage_outputs, current_frame_index, current_epoch_ms, current_datetime):
        
        # Save object metadata when needed & record which object ids are in the frame, for snapshot metadata
        self.loader.objcap.run(stage_outputs, current_frame_index, current_epoch_ms, current_datetime)
    
    # .................................................................................................................
    
    def run_core_processing(self, input_frame, read_time_sec, background_image, background_was_updated,
                            current_frame_index, current_epoch_ms, current_datetime):
        
        # Handle core processing
        stage_outputs, stage_timing = \
        self.loader.core_bundle.run_all(input_frame, read_time_sec, background_image, background_was_updated,
                                        current_frame_index, current_epoch_ms, current_datetime)
        
        return stage_outputs, stage_timing
    
    # .................................................................................................................
    
    def run_station_processing(self, input_frame, background_image, background_was_updated,
                               current_frame_index, current_epoch_ms, current_datetime):
        
        # Handle station processing
        station_timing_dict = \
        self.loader.station_bundle.run_all(input_frame, background_image, background_was_updated,
                                           current_frame_index, current_epoch_ms, current_datetime)
        
        return station_timing_dict
    
    # .................................................................................................................
    
    def clean_up(self, current_frame_index, current_epoch_ms, current_datetime):
        
        # Have loader clean up opened resources
        self.loader.clean_up(current_frame_index, current_epoch_ms, current_datetime)
    
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
        super().__init__(configuration_loader_object, enable_display = True)
        
        # Storage for re-configurable object
        self.configurable_ref = configuration_loader_object.configurable_ref
        
        # Storage for debugging info access
        self.debug_frame = None
        self.debug_stage_outputs = None
        self.debug_stage_timing = None
        self.debug_current_snapshot_metadata = None
        self.debug_fed_time_args = None
        
        # Get initial settings so we can properly configure control windows
        self.initial_drawing_settings, self.initial_slider_settings, self.invisible_vars = self.get_initial_settings()
        
        # Set up local display windows
        self.local_controls, self.controls_json = self.setup_control_windows(self.initial_slider_settings)
        self.timing_window = self.setup_timing_windows()
        self.playback_controls = self.setup_playback_window()
        self.display_resource_dict = arrange_display_resources(configuration_loader_object, ordered_display_list)
        
        # Setup drawing windows, if needed
        self.drawing_window_ref_list = self.get_drawing_windows(self.initial_drawing_settings)
    
    # .................................................................................................................
    
    def get_initial_settings(self):
        
        # Get initial values of the configurable, by variable category
        save_draw_json, nosave_draw_json, save_slider_json, nosave_slider_json, invisible_vars_set = \
        self.configurable_ref.current_settings()
        
        # Bundle initial values together for convenience
        initial_drawing_settings = {**save_draw_json, **nosave_draw_json}
        initial_slider_settings = {**save_slider_json, **nosave_slider_json}
        
        return initial_drawing_settings, initial_slider_settings, invisible_vars_set
    
    # .................................................................................................................
    
    def setup_control_windows(self, initial_slider_settings):
        
        # Get UI setup info
        controls_json = self.configurable_ref.ctrl_spec.to_json()
        local_controls = Local_Window_Controls(self.loader.screen_info, controls_json, initial_slider_settings)
        
        return local_controls, controls_json
    
    # .................................................................................................................
    
    def setup_timing_windows(self):
        
        timing_window = Local_Timing_Window(self.loader.screen_info)
        
        return timing_window
    
    # .................................................................................................................
    
    def setup_playback_window(self):
        
        playback_controls = Local_Playback_Controls(self.loader.vreader, self.loader.playback_access,
                                                    self.loader.screen_info)
        
        return playback_controls
    
    # .................................................................................................................
    
    def get_drawing_windows(self, initial_drawing_settings):
        
        # Pull out anything drawing windows (depends on configurable controls)
        drawing_window_ref_list = []
        for each_window, each_display_res in self.display_resource_dict.items():
            
            # Record all windows that containing drawing interactions
            has_drawing = each_display_res["has_drawing"]
            if has_drawing:
                new_drawing_window_ref = each_display_res["window_ref"]
                new_drawing_window_ref.initialize_drawing(initial_drawing_settings)
                drawing_window_ref_list.append(new_drawing_window_ref)
        
        # If there are drawing controls, print out drawing control info
        drawing_exists = (len(drawing_window_ref_list) > 0)
        if drawing_exists:
            new_drawing_window_ref.print_info()
        
        return drawing_window_ref_list
    
    # .................................................................................................................
    
    def reset_all(self):
        self.loader.reset_all()
    
    # .................................................................................................................
    
    def loop(self):
        
        ''' Reconfigurable video loop '''
        
        # Allocate storage for buffering time info in case of sudden close/clean up
        prev_fed_time_args = [None, None, None]
        
        try:
        
            while True:
                
                # Read video frames & get timing info
                req_break, frame, read_time_sec, *fed_time_args = self.read_frames()
                if req_break:
                    break
                
                prev_fed_time_args = fed_time_args
                
                # Check for control updates
                self.read_controls()
                
                # Capture snapshots
                self.run_snapshot_capture(frame, *fed_time_args)
                
                # Capture frames & generate new background images
                background_args = self.run_background_capture(frame, *fed_time_args)
                
                # Perform main core processing
                stage_outputs, stage_timing = \
                self.run_core_processing(frame, read_time_sec, *background_args, *fed_time_args)
                
                # Perform station processing
                self.run_station_processing(frame, *background_args, *fed_time_args)
                
                # Capture object data
                self.run_object_capture(stage_outputs, *fed_time_args)
                
                # Display results
                self.display_image_data(stage_outputs, *fed_time_args)
                self.display_timing_data(stage_timing)
                    
                # Store info for debugging
                self._save_for_debug(frame, fed_time_args,
                                     stage_outputs = stage_outputs)
                
                # Check for keypresses
                req_break, video_reset, key_code, modifier_code = self.read_keypress()
                if req_break:
                    break
                
                # Reset all stages, since the video position was changed unnaturally
                if video_reset:
                    self.reset_all()
            
        except KeyboardInterrupt:
            print("Keyboard interrupt! Closing...")
        
        # Clean up any open resources
        self.clean_up(*prev_fed_time_args)
        cv2.destroyAllWindows()
    
    # .................................................................................................................
    
    def read_frames(self):
        
        # Grab frames from the video source (with timing information for each frame!)
        req_break, input_frame, read_time_sec, current_frame_index, current_epoch_ms, current_datetime = \
        self.loader.vreader.read()
        
        # If a break is requested, try resetting the video capture
        if req_break:
            self.loader.vreader.set_current_frame(0)
            req_break, input_frame, read_time_sec, current_frame_index, current_epoch_ms, current_datetime = \
            self.loader.vreader.read()
            print("", "ERROR RESETTING RECONFIGURABLE VIDEO CAPTURE!", sep = "\n")
        
        return req_break, input_frame, read_time_sec, current_frame_index, current_epoch_ms, current_datetime
    
    # .................................................................................................................
    
    def read_controls(self):
        
        # Read any drawing windows
        drawing_values_changed_dict = self.read_all_drawings()
        if drawing_values_changed_dict:
            self.configurable_ref.reconfigure(drawing_values_changed_dict)
        
        # Read local controls & update the configurable if anything changes
        control_values_changed_dict = self.local_controls.read_all_controls()
        if control_values_changed_dict:
            self.configurable_ref.reconfigure(control_values_changed_dict)
    
    # .................................................................................................................
    
    def read_keypress(self):
        
        # Have playback controls manager keypresses (+ video control!)
        req_break, video_reset, key_code, modifier_code = self.playback_controls.update()
        
        # Pass keypress event to any drawing windows
        for each_drawing_window in self.drawing_window_ref_list:
            each_drawing_window.keypress(key_code, modifier_code)
        
        return req_break, video_reset, key_code, modifier_code
    
    # .................................................................................................................
    
    def read_all_drawings(self):
        
        # Initialize empty (no-change) output
        variables_changed_dict = {}
        
        # Check for drawing control changes on every known drawing window
        for each_drawing_window in self.drawing_window_ref_list:
            new_changes = each_drawing_window.update_control()
            variables_changed_dict.update(new_changes)
            
        return variables_changed_dict
    
    # .................................................................................................................
    
    def display_image_data(self, stage_outputs, current_frame_index, current_epoch_ms, current_datetime):
        
        # Loop over all active windows and generate the displayed image
        for each_display_res in self.display_resource_dict.values():
            
            # Pull out display resources for clarity
            window_ref = each_display_res["window_ref"]
            display_obj = each_display_res["display_obj"]
            
            # Skip any windows that have been closed
            if not window_ref.exists():
                continue
            
            # Get mouse co-ordinates, if the window supports it (may be None)
            mouse_xy = window_ref.mouse_xy
            
            # Have each display window apply it's display function to the input data before updating the display
            display_image = display_obj.display(stage_outputs,
                                                self.configurable_ref,
                                                mouse_xy,
                                                current_frame_index,
                                                current_epoch_ms,
                                                current_datetime)
            window_ref.imshow(display_image)
    
    # .................................................................................................................
    
    def display_timing_data(self, stage_timing):
        self.timing_window.display(stage_timing)
    
    # .................................................................................................................
    
    def _save_for_debug(self, frame, fed_time_args, **kwargs):
        
        # Hard-coded storage for accessing helpful debugging info when running as a rec-configurable loop
        self.debug_frame = frame
        self.debug_fed_time_args = fed_time_args
        self.debug_dict = kwargs
    
    # .................................................................................................................
    # .................................................................................................................


# =====================================================================================================================
# =====================================================================================================================


class Snapshot_Capture_Video_Loop(Reconfigurable_Video_Loop):
    
    # .................................................................................................................
    
    def __init__(self, configuration_loader_object, ordered_display_list):
        
        # Inherit from parent
        super().__init__(configuration_loader_object, ordered_display_list = ordered_display_list)
    
    # .................................................................................................................
    
    def loop(self):
        
        ''' Snapshot capture video loop '''
        
        # Allocate storage for buffering time info, in case of sudden close/clean up
        prev_fed_time_args = None
        
        try:
        
            while True:
                
                # Read video frames & get timing info
                req_break, frame, read_time_sec, *fed_time_args = self.read_frames()
                if req_break:
                    break
                prev_fed_time_args = fed_time_args
                
                # Check for control updates
                self.read_controls()
                
                # Only run snapshot functions (with timing!)
                t1 = perf_counter()
                snapshot_frame, current_snapshot_metadata = self.run_snapshot_capture(frame, *fed_time_args)
                t2 = perf_counter()
                
                # Re-use core stage outputs to make use of existing functions (somewhat hacky!)
                stage_timing = self._fake_stage_timing(read_time_sec, t1, t2)
                stage_outputs = self._fake_stage_outputs(frame,
                                                         snapshot_frame,
                                                         current_snapshot_metadata)
                
                # Display results
                self.display_image_data(stage_outputs, *fed_time_args)
                self.display_timing_data(stage_timing)
                
                # Store info for debugging
                self._save_for_debug(frame, fed_time_args,
                                     stage_outputs = stage_outputs,
                                     current_snapshot_metadata = current_snapshot_metadata)
                
                # Check for keypresses
                req_break, video_reset, key_code, modifier_code = self.read_keypress()
                if req_break:
                    break
                
                # Reset all stages, since the video position was changed unnaturally
                if video_reset:
                    self.reset_all()
                
        except KeyboardInterrupt:
            print("Keyboard interrupt! Closing...")
        
        # Clean up any open resources
        self.clean_up(*prev_fed_time_args)
        cv2.destroyAllWindows()
    
    # .................................................................................................................

    def _fake_stage_outputs(self, video_frame, snapshot_image, current_snapshot_metadata):
        
        input_stage = {"video_frame": video_frame}
        snapshot_stage = {"snapshot_image": snapshot_image, "snapshot_metadata": current_snapshot_metadata}
        
        stage_outputs = OrderedDict()
        stage_outputs.update({"video_capture_input": input_stage})
        stage_outputs.update({"snapshot_capture": snapshot_stage})
        
        return stage_outputs
    
    # .................................................................................................................

    def _fake_stage_timing(self, read_time_sec, start_time_sec, end_time_sec):
        
        stage_timing = OrderedDict()
        stage_timing.update({"video_capture_input": read_time_sec})
        stage_timing.update({"snapshot_capture": (end_time_sec - start_time_sec)})
        
        return stage_timing
    
    # .................................................................................................................
    # .................................................................................................................


# =====================================================================================================================
# =====================================================================================================================

class Background_Capture_Video_Loop(Reconfigurable_Video_Loop):
    
    # .................................................................................................................
    
    def __init__(self, configuration_loader_object, ordered_display_list):
        
        # Inherit from parent
        super().__init__(configuration_loader_object, ordered_display_list = ordered_display_list)
        
    # .................................................................................................................
    
    def loop(self):
        
        ''' Background capture video loop '''
        
        # Allocate storage for buffering time info in case of sudden close/clean up
        prev_fed_time_args = None
        
        try:
        
            while True:
                
                # Read video frames & get timing info
                req_break, frame, read_time_sec, *fed_time_args = self.read_frames()
                if req_break:
                    break
                prev_fed_time_args = fed_time_args
                
                # Check for control updates
                self.read_controls()
                
                # Capture frames & generate new background images
                t1 = perf_counter()
                background_image, background_was_updated = self.run_background_capture(frame, *fed_time_args)
                t2 = perf_counter()
                
                # Re-use core stage outputs to make use of existing functionality (somewhat hacky!)
                stage_timing = self._fake_stage_timing(read_time_sec, t1, t2)
                stage_outputs = self._fake_stage_outputs(frame, background_image, background_was_updated)
                
                # Display results
                self.display_image_data(stage_outputs, *fed_time_args)
                self.display_timing_data(stage_timing)
                    
                # Store info for debugging
                self._save_for_debug(frame, fed_time_args,
                                     stage_outputs = stage_outputs)
                
                # Check for keypresses
                req_break, video_reset, key_code, modifier_code = self.read_keypress()
                if req_break:
                    break
                
                # Reset all stages, since the video position was changed unnaturally
                if video_reset:
                    self.reset_all()
            
        except KeyboardInterrupt:
            print("Keyboard interrupt! Closing...")
        
        # Clean up any open resources
        self.clean_up(*prev_fed_time_args)
        cv2.destroyAllWindows()
    
    # .................................................................................................................

    def _fake_stage_outputs(self, video_frame, background_image, background_was_updated):
        
        input_stage = {"video_frame": video_frame, "bg_frame": background_image, "bg_update": background_was_updated}
        
        stage_outputs = OrderedDict()
        stage_outputs.update({"video_capture_input": input_stage})
        
        return stage_outputs
    
    # .................................................................................................................

    def _fake_stage_timing(self, read_time_sec, start_time_sec, end_time_sec):
        
        stage_timing = OrderedDict()
        stage_timing.update({"video_capture_input": read_time_sec})
        stage_timing.update({"background_capture": (end_time_sec - start_time_sec)})
        
        return stage_timing

    # .................................................................................................................
    # .................................................................................................................


class Object_Capture_Video_Loop(Reconfigurable_Video_Loop):
    
    # .................................................................................................................
    
    def __init__(self, configuration_loader_object, ordered_display_list):
        
        # Inherit from parent
        super().__init__(configuration_loader_object, ordered_display_list = ordered_display_list)
    
    # .................................................................................................................
    
    def loop(self):
        
        ''' Object capture video loop '''
        
        # Allocate storage for buffering time info in case of sudden close/clean up
        prev_fed_time_args = None
        
        try:
        
            while True:
                
                # Read video frames & get timing info
                req_break, frame, read_time_sec, *fed_time_args = self.read_frames()
                if req_break:
                    break
                prev_fed_time_args = fed_time_args
                
                # Check for control updates
                self.read_controls()
                
                # Capture frames & generate new background images
                background_image, background_was_updated = self.run_background_capture(frame, *fed_time_args)
                
                # Perform main core processing
                stage_outputs, stage_timing = \
                self.run_core_processing(frame, read_time_sec, background_image, background_was_updated, *fed_time_args)
                
                # Capture object data, with timing!
                t1 = perf_counter()
                self.run_object_capture(stage_outputs, *fed_time_args)
                t2 = perf_counter()
                
                # Re-write the stage timing to only show input time + object capture timing
                stage_timing = self._fake_stage_timing(stage_timing, t1, t2)
                
                # Display results
                self.display_image_data(stage_outputs, *fed_time_args)
                self.display_timing_data(stage_timing)
                    
                # Store info for debugging
                self._save_for_debug(frame, fed_time_args,
                                     stage_outputs = stage_outputs)
                
                # Check for keypresses
                req_break, video_reset, key_code, modifier_code = self.read_keypress()
                if req_break:
                    break
                
                # Reset all stages, since the video position was changed unnaturally
                if video_reset:
                    self.reset_all()
            
        except KeyboardInterrupt:
            print("Keyboard interrupt! Closing...")
        
        # Clean up any open resources
        self.clean_up(*prev_fed_time_args)
        cv2.destroyAllWindows()
    
    # .................................................................................................................

    def _fake_stage_timing(self, real_stage_timing, start_time_sec, end_time_sec):
        
        input_timing = real_stage_timing.pop("video_capture_input")
        core_timing = sum(real_stage_timing.values())
        
        stage_timing = OrderedDict()
        stage_timing.update({"video_capture_input": input_timing})
        stage_timing.update({"full_core_processing": core_timing})
        stage_timing.update({"object_capture": (end_time_sec - start_time_sec)})
        
        return stage_timing
    
    # .................................................................................................................
    # .................................................................................................................


# =====================================================================================================================
# =====================================================================================================================


class Station_Processing_Video_Loop(Reconfigurable_Video_Loop):
    
    # .................................................................................................................
    
    def __init__(self, configuration_loader_object, ordered_display_list):
        
        # Inherit from parent
        super().__init__(configuration_loader_object, ordered_display_list = ordered_display_list)
    
    # .................................................................................................................
    
    def loop(self):
        
        ''' Station capture video loop '''
        
        # Allocate storage for buffering time info, in case of sudden close/clean up
        prev_fed_time_args = None
        
        try:
        
            while True:
                
                # Read video frames & get timing info
                req_break, frame, read_time_sec, *fed_time_args = self.read_frames()
                if req_break:
                    break
                prev_fed_time_args = fed_time_args
                
                # Check for control updates
                self.read_controls()
                
                # Capture frames & generate new background images
                background_args = self.run_background_capture(frame, *fed_time_args)
                
                # Run station capture
                t1 = perf_counter()
                self.run_station_processing(frame, *background_args, *fed_time_args)
                t2 = perf_counter()
                
                # Re-use core stage outputs to make use of existing functions (somewhat hacky!)
                stage_outputs = self._fake_stage_outputs(frame)
                stage_timing = self._fake_stage_timing(read_time_sec, t1, t2)
                
                # Display results
                self.display_image_data(stage_outputs, *fed_time_args)
                self.display_timing_data(stage_timing)
                
                # Store info for debugging
                self._save_for_debug(frame, fed_time_args)
                
                # Check for keypresses
                req_break, video_reset, key_code, modifier_code = self.read_keypress()
                if req_break:
                    break
                
                # Reset all stages, since the video position was changed unnaturally
                if video_reset:
                    self.reset_all()
                
        except KeyboardInterrupt:
            print("Keyboard interrupt! Closing...")
        
        # Clean up any open resources
        self.clean_up(*prev_fed_time_args)
        cv2.destroyAllWindows()
    
    # .................................................................................................................

    def _fake_stage_outputs(self, video_frame):
        
        input_stage = {"video_frame": video_frame}
        
        stage_outputs = OrderedDict()
        stage_outputs.update({"video_capture_input": input_stage})
        
        return stage_outputs
    
    # .................................................................................................................

    def _fake_stage_timing(self, video_decode_time_sec, start_time_sec, end_time_sec):
        
        stage_timing = OrderedDict()
        stage_timing.update({"video_capture_input": video_decode_time_sec})
        stage_timing.update({"station_processing": (end_time_sec - start_time_sec)})
        
        return stage_timing
    
    # .................................................................................................................
    # .................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

# .....................................................................................................................

def arrange_display_resources(configuration_loader, ordered_display_obj_list):
    
    '''
    Function which sets up local display windows
    
    Inputs:
        ordered_display_obj_list --> List of display specification objects.
        
    Outputs:
        display_resources_dict --> Dictionary containing all display resources. 
        Indexed by keys representing the window names. 
        
        For each key, there is an associated dictionary containing keys: "window_ref" & "display_obj"
        The "window_ref" key contains a reference to the OpenCV window object (for the given window name)
        The "display_obj" key contains the display specification for the corresponding display
        The display specification also contains a .display() function which generates the image for the given window
    '''
    
    # Assume windows will have the video frame dimensions
    frame_wh = configuration_loader.video_wh
    
    # Get screen & display sizing
    feedback_width, feedback_x_padding = configuration_loader.screen_info.feedback("width", "x_padding")
    screen_width, screen_height = configuration_loader.screen_info.screen("width", "height")
    screen_x_offset, screen_y_offset = configuration_loader.screen_info.screen("x_offset", "y_offset")
    max_disp_width, max_disp_height = configuration_loader.screen_info.displays("max_width", "max_height")
    valid_max_wh = (max_disp_width is not None and max_disp_height is not None)
    max_wh = (max_disp_width, max_disp_height)
    
    # Get windowing area info for window placement
    min_x, min_y, reserved_vert = \
    configuration_loader.screen_info.displays("top_left_x", "top_left_y", "reserved_vertical")
    max_x = screen_width - feedback_width - (2 * feedback_x_padding)
    max_y = screen_height - reserved_vert
    
    # Build some helper functions to simplfy things
    get_row_col_idx = lambda layout_idx, nrows, ncols: list(product(range(nrows), range(ncols)))[layout_idx]
    get_x_corner = lambda col_index, num_cols: int(round(min_x + (max_x - min_x) * col_index / num_cols))
    get_y_corner = lambda row_index, num_rows: int(round(min_y + (max_y - min_y) * row_index / num_rows))
    
    display_resources_dict = OrderedDict()
    for each_display_obj in ordered_display_obj_list:
        
        # Get display spec and separate into more readable components
        disp_json = each_display_obj.to_json()
        new_window_name = disp_json.get("name", "Unknown")
        is_initial = disp_json.get("initial_display", False)
        drawing_json = disp_json.get("drawing_json", None)
        provide_mouse_xy = disp_json.get("provide_mouse_xy", None)
        limit_wh = disp_json.get("limit_wh", None)
        num_rows = disp_json.get("num_rows", 1)
        num_cols = disp_json.get("num_cols", 1)
        layout_index = disp_json.get("layout_index", 0)
        
        # Warning for bad layout indices
        invalid_layout = (layout_index >= (num_rows * num_cols))
        if invalid_layout:
            err_msg = "Bad layout index ({}), must be less than {} x {}".format(layout_index, num_rows, num_cols)
            raise ValueError(err_msg)
        
        # Determine the window type needed for display
        needs_drawing_window = (drawing_json is not None)
        needs_max_wh_window = (limit_wh and valid_max_wh)
        if needs_drawing_window:
            new_window_ref = Drawing_Window(new_window_name, frame_wh, drawing_json)
        elif needs_max_wh_window:
            new_window_ref = Max_WH_Window(new_window_name, frame_wh, max_wh, provide_mouse_xy = provide_mouse_xy)
        else:
            new_window_ref = Simple_Window(new_window_name, provide_mouse_xy = provide_mouse_xy)
        
        # Bundle re-usable access info
        new_display_entry = {new_window_name: {"window_ref": new_window_ref,
                                               "display_obj": each_display_obj,
                                               "has_drawing": needs_drawing_window}}
        display_resources_dict.update(new_display_entry)
        
        # Place window
        row_idx, col_idx = get_row_col_idx(layout_index, num_rows, num_cols)
        x_corner_px = get_x_corner(col_idx, num_cols) + screen_x_offset
        y_corner_px = get_y_corner(row_idx, num_rows) + screen_y_offset
        new_window_ref.move_corner_pixels(x_corner_px, y_corner_px)
    
    return display_resources_dict

# .....................................................................................................................
    
def create_simple_display_window(configuration_loader):
    
    # Create a single display, with object tracking visualizations
    window_name = "{} ({})".format(configuration_loader.camera_select, configuration_loader.video_select)
    ordered_display_list = [Tracked_Display(0, 1, 1, window_name = window_name)]
    display_resources_dict = arrange_display_resources(configuration_loader, ordered_display_list)
    window_ref = display_resources_dict[window_name]["window_ref"]
    display_obj = display_resources_dict[window_name]["display_obj"]
        
    return window_ref, display_obj

# .....................................................................................................................

def simple_display(window_ref, display_obj, stage_outputs,
                   current_frame_index, current_epoch_ms, current_datetime):
        
    # Set up some variables for cleanliness
    mouse_xy = None
    configurable_ref = None
    fed_time_args = (current_frame_index, current_epoch_ms, current_datetime)
    
    # Generate the frame for display
    display_image = display_obj.display(stage_outputs, configurable_ref, mouse_xy, *fed_time_args)
    
    # Keep track of whether the displays exist
    window_exists = window_ref.imshow(display_image)
    if not window_exists:
        raise SystemExit("All displays closed")
        
    # Add delay for display updates 
    cv2.waitKey(1)
            
# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Demo 
    
if __name__ == "__main__":
    pass


# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap


