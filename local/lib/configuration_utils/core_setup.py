#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon May 27 14:22:40 2019

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

import json
from time import perf_counter

from collections import OrderedDict
from itertools import islice

from local.lib.file_access_utils.shared import configurable_dot_path, load_with_error_if_missing

from local.lib.file_access_utils.core import build_core_folder_path, save_core_config, get_ordered_config_paths

from local.lib.configuration_utils.local_ui.local_video_loop import local_core_config_video_loop
from local.lib.configuration_utils.web_ui.web_video_loop import web_core_config_video_loop

from eolib.utils.cli_tools import cli_confirm
from eolib.utils.function_helpers import dynamic_import_from_module

# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes


class Core_Bundle:
    
    # .................................................................................................................
    
    def __init__(self, cameras_folder_path, camera_select, user_select, task_select, video_select, video_wh):
        
        # Save selection info
        self.cameras_folder_path = cameras_folder_path
        self.camera_select = camera_select
        self.user_select = user_select
        self.task_select = task_select
        self.video_select = video_select
        self.video_wh = video_wh
        
        # First make sure we have pathing to the core configs folder
        self.core_folder_path = build_core_folder_path(cameras_folder_path, camera_select, user_select, task_select)
        
        # Allocate storage for configured data
        self.final_stage_config_file_paths = None
        self.final_stage_config_dict = None
        self.core_ref_dict = None
        self.input_wh_list = None
        
        # Allocate storage for holding running results
        self._stage_outputs = None
        self._stage_timing = None
        self._skip_frame = None        
    
    # .................................................................................................................
        
    def __repr__(self):
        
        # Warning if no configuration data yet
        if self.final_stage_config_dict is None:
            return "Core Bundle ({}) - Not setup yet! Call .setup_all()".format(self.task_select)
        
        # Helper function for prettier stage names in the print out
        titleize = lambda ugly_name: ugly_name.replace("_", " ").title()
        
        # List all configured data
        repr_strs = ["Core Bundle ({})".format(self.task_select)]
        for each_stage, each_config in self.final_stage_config_dict.items():
            
            access_info = each_config.get("access_info")
            script_name = access_info.get("script_name")
            class_name = access_info.get("class_name")
            num_properties = len(each_config.get("setup_data"))
            
            repr_strs += ["",
                          "--> {}".format(titleize(each_stage)),
                          "  Script: {}".format(script_name),
                          "   Class: {}".format(class_name),
                          "  ({} configured properties)".format(num_properties)]
            
        return "\n".join(repr_strs)
    
    # .................................................................................................................
    
    @property
    def _frame_capture(self):
        return self.core_ref_dict.get("frame_capture")
    
    # .................................................................................................................
    
    def last_item(self):
        
        '''
        Function which retrieves the last core stage name & object reference
        Intended for use when overriding/reconfiguring stages (where the final stage may be altered)
        Note that this function must be called after calling .setup_all()
        
        Inputs:
            None!
            
        Outputs:
            stage_name, stage_object_reference        
        '''
        
        if self.core_ref_dict is None:
            err_msg = "Can't get last item since Core Bundle ({}) hasn't been configured yet!".format(self.task_select)
            raise IndexError(err_msg)
        
        last_key = next(reversed(self.core_ref_dict))
        return last_key, self.core_ref_dict.get(last_key)
    
    # .................................................................................................................
    
    def reset_all(self):
        
        ''' Function used to reset the state of the core bundle & all internal stages '''
        
        # Reset all core objects. Mostly for use in configuration, when the video may jump around
        if self.core_ref_dict is not None:
            for each_stage_ref in self.core_ref_dict.values():
                each_stage_ref.reset()
        
        # Reset own internal copies of output data
        self._stage_outputs = OrderedDict()
        self._stage_timing = OrderedDict()
        self._skip_frame = False

    # .................................................................................................................

    def setup_all(self, override_stage = None, override_script = None, override_class = None,
                  reset_on_startup = True):
        
        # Load all known data
        all_stage_config_file_paths, all_stage_config_dict = self._load_all_config_data()
        
        # Override target stage, if needed
        final_stage_config_dict = self._override_configuration(all_stage_config_dict,
                                                               override_stage,
                                                               override_script,
                                                               override_class)
        
        # Initialize an empty dictionary to hold references to each configured core stage object
        core_ref_dict = OrderedDict()
        input_wh_dict = OrderedDict()
        new_input_wh = self.video_wh
        
        # Loop over all config data and load/configure all stages
        final_stage_config_file_paths = OrderedDict()
        for each_stage_name, each_config_dict in final_stage_config_dict.items():
            
            # Store only the config file paths that were used
            final_stage_config_file_paths.update({each_stage_name: all_stage_config_file_paths.get(each_stage_name)})
            
            # Import and configure each core object then store the results
            core_ref, new_input_wh = self._setup_single(each_stage_name, new_input_wh, each_config_dict)
            core_ref_dict.update({each_stage_name: core_ref})
            input_wh_dict.update({each_stage_name: new_input_wh})
            
        # Store everything for debugging
        self.final_stage_config_file_paths = final_stage_config_file_paths
        self.final_stage_config_dict = final_stage_config_dict
        self.input_wh_dict = input_wh_dict
        self.core_ref_dict = core_ref_dict
        
        # Reset everything to start
        if reset_on_startup:
            self.reset_all()
        
    # .................................................................................................................
    
    def run_all(self, 
                bg_outputs, 
                current_frame_index, current_time_sec, current_datetime,
                current_snapshot_metdata):
        
        '''
        Function for running the full core processing sequence,
        Takes input from the initial video/background capture stages
        Outputs:
            skip_frame (boolean), stage_outputs (OrderedDict), stage_timing (OrderedDict)
        '''
        
        # Run the frame capture to decide if we should skip this frame
        start_time = perf_counter()
        skip_frame = self._frame_capture.run(current_frame_index, current_time_sec, current_datetime)
        end_time = perf_counter()
        
        # Bundle outputs
        stage_outputs = OrderedDict([("frame_capture", bg_outputs)])
        stage_timing = OrderedDict([("frame_capture", (end_time - start_time))])
        
        # End early if we're skipping the frames
        if skip_frame:
            
            # Update internal copies with whatever we can, and return our own internal records
            self._skip_frame = skip_frame
            self._stage_outputs.update(stage_outputs)
            self._stage_timing.update(stage_timing)
            
            return self._skip_frame, self._stage_outputs, self._stage_timing
        

        # Loop through every run function passing outputs from each stage to inputs of the next stage
        process_outputs = bg_outputs
        try:
            for each_stage_name, each_stage_ref in islice(self.core_ref_dict.items(), 1, None):
                
                # Run each stage with timing
                process_outputs, process_timing = \
                self._run_one(process_outputs, each_stage_ref, 
                              current_frame_index, current_time_sec, current_datetime,
                              current_snapshot_metdata)

                # Store results for analysis
                stage_outputs.update({each_stage_name: process_outputs})
                stage_timing.update({each_stage_name: process_timing})

        except Exception as err:
            print("", "Error on core stage: {}".format(each_stage_name), "", sep="\n")
            raise err
            
        # Keep internal copy of outputs, in case we need to repeat them (e.g. when skipping frames)
        self._skip_frame = skip_frame
        self._stage_outputs = stage_outputs
        self._stage_timing = stage_timing

        return skip_frame, stage_outputs, stage_timing
        
    # .................................................................................................................
    
    def _run_one(self, process_inputs, stage_ref, 
                 current_frame_index, current_time_sec, current_datetime,
                 current_snapshot_metadata):
        
        '''
        Function for running a single core processing stage
        '''
        
        # Provide each stage with the timing of the current video frame data
        stage_ref.update_time(current_frame_index, current_time_sec, current_datetime)
        stage_ref.update_snapshot_record(current_snapshot_metadata)
        
        # Run each stage with timing
        start_time = perf_counter()
        process_outputs = stage_ref.run(**process_inputs)
        end_time = perf_counter()
        
        # Record process timing results
        process_timing = (end_time - start_time)
        
        return process_outputs, process_timing
    
    # .................................................................................................................
    
    def _setup_single(self, stage_name, input_wh, stage_config_dict):
        
        # Separate the raw data contained in the config file
        access_info_dict = stage_config_dict.get("access_info")
        setup_data_dict = stage_config_dict.get("setup_data")
        
        # Separate the access info
        script_name = access_info_dict.get("script_name")
        class_name = access_info_dict.get("class_name")
        
        # Load the given core object
        import_dot_path = configurable_dot_path("core", stage_name, script_name)
        Imported_Core_Class = dynamic_import_from_module(import_dot_path, class_name)        
        core_ref = Imported_Core_Class(input_wh)
        
        # For debugging
        #print("IMPORTING:", stage_name)
        #print(import_dot_path)
        #print(imported_core_class)
        
        # Load initial configuration and get the output sizing for the next stage
        core_ref.reconfigure(setup_data_dict)
        core_ref.set_output_wh()
        output_wh = core_ref.get_output_wh()
        
        return core_ref, output_wh
        
    # .................................................................................................................
        
    def _override_configuration(self, all_stage_config_dict, 
                                override_stage = None, override_script = None, override_class = None):
        
        '''
        Function used alter the configuration sequence by overriding a target stage with a 
        (potentially) different script and/or class.
        This is intended to be used to create a re-configurable 
        '''
        
        # For clarity
        no_stage = (override_stage is None)
        no_script = (override_stage is None)
        no_class = (override_stage is None)
        
        # Do nothing if neither stage or script are being overriden
        if no_stage and no_script:
            return all_stage_config_dict
        
        # If one, but not both of the stage/script aren't specified, it's an error!
        if no_stage or no_script:
            error_msg = "If overriding, must specify both stage & script"
            what_i_got_msg = "Got {} (stage) and {} (script)".format(override_stage, override_script)
            raise AttributeError("{}. {}.".format(error_msg, what_i_got_msg))
        
        # Bail if the override stage isn't part of the existing configs
        stage_doesnt_exist = (override_stage not in all_stage_config_dict)
        if stage_doesnt_exist:
            actual_sequence = ", ".join(all_stage_config_dict.keys())
            error_msg = "Override stage ({}) is not part of the core processing sequence!".format(override_stage)
            seq_msg = "Expecting one of: {}".format(actual_sequence)
            raise NameError("{} {}".format(error_msg, seq_msg))
        
        # Guess at the class if it wasn't specifed
        if no_class:
            override_class = override_script.title()
            
        # Remove all stages after the overriden one
        final_stage_config_dict = OrderedDict()
        for each_key, each_value in all_stage_config_dict.items():
            final_stage_config_dict.update({each_key: each_value})
            if each_key == override_stage:
                break
        
        # Alter loading info for the overriden stage. Keep setup data if the script/class match. Otherwise blank it
        override_config = final_stage_config_dict.get(override_stage)
        access_info_dict = override_config.get("access_info")
        setup_data_dict = override_config.get("setup_data")
        mismatch_script = (access_info_dict.get("script_name") != override_script)
        mismatch_class = (access_info_dict.get("class_name") != override_class)
        if mismatch_script or mismatch_class:
            access_info_dict = {"script_name": override_script, "class_name": override_class}
            setup_data_dict = {}
            
        # Write access/setup data back into overriden stage
        override_config = {"access_info": access_info_dict, "setup_data": setup_data_dict}
        final_stage_config_dict[override_stage] = override_config
        
        return final_stage_config_dict
    
    # .................................................................................................................
    
    def _load_all_config_data(self):
        
        # Load all core config data
        core_config_path_list, core_stage_name_list = get_ordered_config_paths(self.core_folder_path)
        
        # Load every available core configuration
        configs_dict = OrderedDict()
        path_dict = OrderedDict()
        for each_config_file_path, each_stage_name in zip(core_config_path_list, core_stage_name_list):
            
            # Load the core config data
            core_config = load_with_error_if_missing(each_config_file_path)
            
            # Store core config in an ordered dictionary using the stage name as a key
            configs_dict.update({each_stage_name: core_config})
            path_dict.update({each_stage_name: each_config_file_path})
        
        return path_dict, configs_dict

    # .................................................................................................................
    # .................................................................................................................

class OLD_Core_Bundle:
    
    # .................................................................................................................
    
    def __init__(self, cameras_folder, camera_select, user_select, task_select, video_wh):
        
        # Store pathing info
        self.cameras_folder = cameras_folder
        self.camera_select = camera_select
        self.user_select = user_select
        self.task_select = task_select
        self.video_wh = video_wh
        
        # First make sure we have pathing to the core configs folder
        self.core_folder_path = build_core_folder_path(cameras_folder, camera_select, user_select, task_select)
        
        # Load all core config data
        core_config_path_list, core_stage_name_list = get_ordered_config_paths(self.core_folder_path)
        self._core_config_paths = core_config_path_list
        self._process_list = core_stage_name_list
        self.core_configs_dict = self._load_all_configs()
        
        # Set up every core stage
        self.core_ref_dict, self.input_wh_list = self._setup_all()
        
        # Update actual processing sequence lists
        self.real_process_names_list = self.real_process_tuples_list = None
        self._update_real_process_lists()
        
        # Create storage for holding running results
        self._stage_outputs = None
        self._stage_timing = None
        self._skip_frame = None
        
        # Reset everything, just in case
        self.reset_all()
        
    # .................................................................................................................
    
    def __repr__(self):
        
        repr_strs = ["Core Bundle ({})".format(self.task_select)]
        for each_stage in self.full_process_list:
            
            stage_config_data = self.core_configs_dict.get(each_stage)
            access_info = stage_config_data.get("access_info")
            script_name = access_info.get("script_name")
            class_name = access_info.get("class_name")
            num_properties = len(stage_config_data.get("setup_data"))
            
            repr_strs += ["",
                          "--- {} ---".format(each_stage.replace("_", " ").title()),
                          "  Script: {}".format(script_name),
                          "   Class: {}".format(class_name),
                          "  ({} configured properties)".format(num_properties)]
            
        
        return "\n".join(repr_strs)
    
    # .................................................................................................................
    
    @property
    def _frame_capture(self):
        return self.core_ref_dict["frame_capture"]
    
    # .................................................................................................................
    
    def _update_real_process_lists(self, last_stage = None):
        
        # If a last stage isn't provided, assume we're running the full list
        last_stage = self.full_process_list[-1] if last_stage is None else last_stage
        
        # Allocate outputs
        real_process_names_list = []
        real_process_tuples_list = []
        for each_stage_name in self.full_process_list:
            
            # Skip frame capture stage, since it is handled independently
            if each_stage_name == "frame_capture":
                if last_stage == "frame_capture":
                    break
                continue
            
            # Build up the real processing sequence & running tuple lists
            real_process_names_list.append(each_stage_name)
            real_process_tuples_list.append((each_stage_name, self.core_ref_dict[each_stage_name]))
            
            # Stop when we get to the last stage
            if each_stage_name == last_stage:
                break
        
        # Update internal records
        self.real_process_names_list = real_process_names_list
        self.real_process_tuples_list = real_process_tuples_list

    # .................................................................................................................
    
    def _load_all_configs(self):
        
        # Allocate outputs
        configs_dict = {}
        
        # Get an ordered listing of all the core configuration file paths
        core_config_path_list, core_stage_name_list = get_ordered_config_paths(self.core_folder_path)
        
        '''
        # Get a listing of all available core configs
        core_config_file_list = get_file_list(self.core_folder_path, 
                                              show_hidden_files = False, 
                                              create_missing_folder = False, 
                                              return_full_path = True)
        '''
        
        # Load every available core configuration
        for each_file_path, each_stage_name in zip(core_config_path_list, core_stage_name_list):
            
            # Load the core config data
            core_config = load_with_error_if_missing(each_file_path)
            
            # Store core config in a dictionary using the stage name as a key
            #core_file_name = os.path.basename(each_file_path)
            #stage_name, _ = os.path.splitext(core_file_name)
            configs_dict.update({each_stage_name: core_config})
            
            '''
            # Warn if an unrecognized config was loaded
            if stage_name not in self.full_process_list:
                print("", 
                      "Warning! Unrecognized core configuration loaded:",
                      "  {}".format(core_file_name),
                      "", sep="\n")
            '''
        
        return configs_dict
    
    # .................................................................................................................
    
    def _setup_single(self, stage_name, input_wh, access_info_dict, setup_data_dict):
        
        # Separate the access info
        script_name = access_info_dict.get("script_name")
        class_name = access_info_dict.get("class_name")
        
        # Load the given core object
        import_dot_path = configurable_dot_path("core", stage_name, script_name)
        imported_core_class = dynamic_import_from_module(import_dot_path, class_name)        
        core_ref = imported_core_class(input_wh)
        
        # For debugging
        #print("IMPORTING:", stage_name)
        #print(import_dot_path)
        #print(imported_core_class)
        
        # Load initial configuration and get the output sizing for the next stage
        core_ref.reconfigure(setup_data_dict)
        core_ref.set_output_wh()
        output_wh = core_ref.get_output_wh()
        
        return core_ref, output_wh
    
    # .................................................................................................................
    
    def _setup_all(self):
        
        # Initialize an empty dictionary to hold references to each configured core stage object
        core_ref_dict = {}
        input_wh_list = [self.video_wh]
        
        # Loop over all config data and load/configure all stages
        for each_stage_name in self.full_process_list:
            
            # Get the configuration data for the given stage
            config_dict = self.core_configs_dict.get(each_stage_name)
            
            # Get access info for each stage
            access_info = config_dict.get("access_info")
            setup_data = config_dict.get("setup_data")       
            
            print("CORE SET UP:", each_stage_name)
            print(access_info)
            print(setup_data)
            
            # Import and configure each core object
            input_wh = input_wh_list[-1]
            core_ref, output_wh = self._setup_single(each_stage_name, input_wh, access_info, setup_data)
            
            # Store configuration outputs
            core_ref_dict.update({each_stage_name: core_ref})
            input_wh_list.append(output_wh)
            
        return core_ref_dict, input_wh_list
    
    # .................................................................................................................
    
    def _run_one(self, process_inputs, stage_ref, 
                 current_frame_index, current_time_sec, current_datetime,
                 current_snapshot_metadata):
        
        '''
        Function for running a single core processing stage
        '''
        
        # Provide each stage with the timing of the current video frame data
        stage_ref.update_time(current_frame_index, current_time_sec, current_datetime)
        stage_ref.update_snapshot_record(current_snapshot_metadata)
        
        # Run each stage with timing
        start_time = perf_counter()
        process_outputs = stage_ref.run(**process_inputs)
        end_time = perf_counter()
        
        # Record process timing results
        process_timing = (end_time - start_time)
        
        return process_outputs, process_timing
    
    # .................................................................................................................
    
    def override_for_configuration(self, stage_name, script_name, class_name):
        
        # Make sure we're using a recognized stage
        if stage_name not in self.full_process_list:
            raise NameError("ERROR OVERRIDING: Stage ({}) not found in process list!".format(stage_name))
        
        # Figure out where the overriding stage is in the process list
        stage_idx = self.full_process_list.index(stage_name)
        new_input_wh = self.input_wh_list[stage_idx]
        
        # Build access info needed to run setup
        new_access_info = {"script_name": script_name, "class_name": class_name}
        
        # If we already have the setup data, we'll load that, otherwise use nothing
        existing_config_data = self.core_configs_dict.get(stage_name, {})
        existing_access_info = existing_config_data.get("access_info")
        existing_script_name = os.path.splitext(existing_access_info.get("script_name", "_"))[0]
        existing_class_name = existing_access_info.get("class_name", "_")
        access_matches = (existing_script_name == script_name) and (existing_class_name == class_name)        
        new_setup_data = existing_config_data.get("setup_data", {}) if access_matches else {}
        
        # Import and configure the given stage
        core_ref, output_wh = self._setup_single(stage_name, new_input_wh, new_access_info, new_setup_data)
        
        # Force configure mode, since overriding is only done when re-configuring!
        core_ref.set_configure_mode(configure_enabled = True)
        
        # Grab the control spec & initial settings
        controls_json = core_ref.controls_manager.to_json()
        initial_settings = core_ref.current_settings()

        # Provide some feedback
        '''
        print("",
              "*** Overriding for configuration ***",
              "  Component: {}".format(component_name.upper()),
              "     Script: {}".format(script_name),
              "      Class: {}".format(class_name),
              "", sep="\n")
        '''
        
        # Overwrite existing core ref and config data
        self.core_ref_dict[stage_name] = core_ref
        self.core_configs_dict[stage_name] = {"access_info": new_access_info, "setup_data": new_setup_data}
        
        # Update real processing list to remove stages after the one being overridden
        self._update_real_process_lists(last_stage = stage_name)
    
        return core_ref, controls_json, initial_settings
    
    # .................................................................................................................
    
    def reset_all(self):
        
        # Reset all core objects. Mostly for use in configuration, when the video may jump around
        for each_stage_name, each_stage_ref in self.real_process_tuples_list:
            each_stage_ref.reset()
            
        # Reset own internal copies of output data
        self._stage_outputs = {}
        self._stage_timing = {}
        self._skip_frame = False
    
    # .................................................................................................................
    
    def run_all(self, 
                bg_outputs, 
                current_frame_index, current_time_sec, current_datetime,
                current_snapshot_metdata):
        
        '''
        Function for running the full core processing sequence,
        Takes input from the initial video/background capture stages
        Outputs:
            skip_frame (boolean), stage_outputs (dict), stage_timing (dict)
        '''
        
        # Run the frame capture to decide if we should skip this frame
        start_time = perf_counter()
        skip_frame = self._frame_capture.run(current_frame_index, current_time_sec, current_datetime)
        end_time = perf_counter()
        
        # Bundle outputs
        stage_outputs = OrderedDict([("frame_capture", bg_outputs)])
        stage_timing = OrderedDict([("frame_capture", (end_time - start_time))])
        
        # End early if we're skipping the frames
        if skip_frame:
            
            # Update internal copies with whatever we can, and return our own internal records
            self._skip_frame = skip_frame
            self._stage_outputs.update(stage_outputs)
            self._stage_timing.update(stage_timing)
            
            return self._skip_frame, self._stage_outputs, self._stage_timing
        

        # Loop through every run function passing outputs from each stage to inputs of the next stage
        process_outputs = bg_outputs
        try:
            for each_stage_name, each_stage_ref in self.real_process_tuples_list:
                
                # Run each stage with timing
                process_outputs, process_timing = \
                self._run_one(process_outputs, each_stage_ref, 
                              current_frame_index, current_time_sec, current_datetime,
                              current_snapshot_metdata)

                # Store results for analysis
                stage_outputs.update({each_stage_name: process_outputs})
                stage_timing.update({each_stage_name: process_timing})

        except Exception as err:
            print("", "Error on core stage: {}".format(each_stage_name), "", sep="\n")
            raise err
            
        # Keep internal copy of outputs, in case we need to repeat them (e.g. when skipping frames)
        self._skip_frame = skip_frame
        self._stage_outputs = stage_outputs
        self._stage_timing = stage_timing

        return skip_frame, stage_outputs, stage_timing
    
    # .................................................................................................................
    
    def force_save_core_config(self, core_ref):
        
        # Get the name of the file to save
        stage_name, script_name, class_name, config_data = core_ref.get_data_to_save()
        
        # Either save the data, or at least get the saved data format for printout
        save_path, save_data = \
        save_core_config(self.cameras_folder, self.camera_select, self.user_select, self.task_select,
                         stage_name, script_name, class_name, config_data,
                         confirm_save = True)
        
        # Some feedback/debugging
        relative_save_path = os.path.relpath(save_path, self.cameras_folder)
        print("",
              "Saving Configuration:",
              "@ {}".format(relative_save_path),
              "",
              "Save data:",
              json.dumps(save_data, indent = 2), 
              sep="\n")
    
    # .................................................................................................................
    
    def ask_to_save_core_config(self, core_ref, initial_settings):
        
        # Get the name of the file to save
        stage_name, script_name, class_name, config_data = core_ref.get_data_to_save()
        
        # Decide if we even need to save (i.e. has the configuration changed from the initial settings?)
        empty_initial_settings = (self.core_configs_dict.get(stage_name).get("setup_data") == {})
        settings_unchanged = (config_data == initial_settings)
        if settings_unchanged and not empty_initial_settings:
            print("", "Settings unchanged!", "Skipping save prompt...", "", sep="\n")
            return
        
        # Prompt the user to save the file
        user_confirm = cli_confirm("Save configuration?", default_response = False)
        
        # Either save the data, or at least get the saved data format for printout
        save_path, save_data = \
        save_core_config(self.cameras_folder, self.camera_select, self.user_select, self.task_select,
                         stage_name, script_name, class_name, config_data, confirm_save = user_confirm)
        
        # If we got here, we're saving! So overwrite the component config file
        if not user_confirm:
            relative_save_path = os.path.relpath(save_path, self.cameras_folder)
            print("",
                  "Here are the config settings, in case that cancel was an accident!",
                  "",
                  "Save path:",
                  "@ {}".format(relative_save_path),
                  "",
                  "Save data:",
                  json.dumps(save_data, indent = 2),
                  "", sep = "\n")
            return
        return
    
    # .................................................................................................................
    
    @property
    def full_process_list(self):
        
        '''
        process_list = ["frame_capture",
                        "preprocessor",
                        "frame_processor",
                        "pixel_filter",
                        "detector",
                        "tracker"]
        '''
        
        return self._process_list
    
    # .................................................................................................................
    # .................................................................................................................



# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////

# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

# .....................................................................................................................
    
def run_core_config_video_loop(video_reader_ref, 
                               background_capture_ref,
                               core_bundle_ref,
                               configurable_ref,
                               controls_json, 
                               initial_settings,
                               display_manager_ref, 
                               config_helper):
    
    
    # Handle web vs. local configuration and video looping
    is_web_config = config_helper.web_enabled
    if is_web_config:

        # Run main video loop
        final_stage_outputs, final_stage_timing = web_core_config_video_loop(video_reader_ref, 
                                                                             background_capture_ref,
                                                                             core_bundle_ref,
                                                                             configurable_ref,
                                                                             controls_json,
                                                                             initial_settings,
                                                                             display_manager_ref,
                                                                             config_helper)
        
    else:

        # Run main video loop
        final_stage_outputs, final_stage_timing = local_core_config_video_loop(video_reader_ref, 
                                                                               background_capture_ref,
                                                                               core_bundle_ref,
                                                                               configurable_ref,
                                                                               controls_json,
                                                                               initial_settings,
                                                                               display_manager_ref,
                                                                               config_helper)
        
        # Use terminal to prompt user for saving config data, when running locally
        core_bundle_ref.ask_to_save_core_config(configurable_ref, initial_settings)
        

    # For debugging purposes
    return final_stage_outputs, final_stage_timing

# ---------------------------------------------------------------------------------------------------------------------
#%% Demo

if __name__ == "__main__":
    
    # Testing out ordered dictionary functionality
    od = OrderedDict()
    od["a"] = 1
    od["b"] = 2
    od["c"] = 3
    od["d"] = 4
    
    # Make selections for testing core bundle setup
    from local.lib.selection_utils import Resource_Selector
    selector = Resource_Selector(save_selection_history = False, create_folder_structure_on_select = False)
    camera_select, camera_path = selector.camera()
    user_select, _ = selector.user(camera_select)
    task_select, _ = selector.task(camera_select, user_select)
    video_select, _ = selector.video(camera_select)
    project_root_path, cameras_folder_path = selector.get_project_pathing()
    fake_video_wh = (100,100)
    
    cb = Core_Bundle(cameras_folder_path, camera_select, user_select, task_select, video_select, fake_video_wh)
    cb.setup_all()

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap


