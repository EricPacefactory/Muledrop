#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Mar 27 13:44:54 2019

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

import numpy as np

from time import sleep

from local.lib.ui_utils.controls_specification import Controls_Specification

from local.lib.file_access_utils.configurables import create_configurable_save_data
from local.lib.file_access_utils.core import build_core_logging_folder_path
from local.lib.file_access_utils.stations import build_stations_logging_folder_path
from local.lib.file_access_utils.externals import build_externals_logging_folder_path

from local.eolib.utils.logging import Daily_Logger


# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes


class Configurable_Base:
    
    # .................................................................................................................
    
    def __init__(self, configurable_group_type, configurable_instance_type,
                 cameras_folder_path, camera_select,
                 *, file_dunder):
        
        '''
        Base class used to build all configurables! Should not be used directly, only inherited.
        
        Inputs:
            
            configurable_group_type -> (String) The name of the type of configurable. For example, whether this is
                                       a 'core' configurable or an 'external' or something else. This value should
                                       be set once in a sub-class that handles all instances belonging to the group!
            
            configurable_instance_type -> (String) The name of the specific type within a group. For example, in
                                          the 'core' group, there is a 'preprocessor' instance type. This value
                                          should be set once in a sub-class that acts as the reference implementation
                                          for all instances belonging to the given type
            
            cameras_folder_path -> (String) The pathing to the folder containing all camera folders
                                   for a given location
            
            camera_select -> (String) The name of the selected camera
            
            file_dunder -> (String) Should be entered as '__file__' from the final class implementation of the
                           configurable. That is, from a class that isn't inherited by anything else.
        '''
        
        # Store identifying info
        self.group_type = configurable_group_type
        self.instance_type = configurable_instance_type
        self.script_name = os.path.basename(file_dunder)
        
        # Store selection info
        self.cameras_folder_path = cameras_folder_path
        self.camera_select = camera_select
        
        # Allocate storage for timing info
        self.current_frame_index = None
        self.current_epoch_ms = None
        self.current_datetime = None
        
        # Variables for controls/configuration functionality
        self.configure_mode = False
        self.ctrl_spec = Controls_Specification()
        
        # Allocate storage for logger object
        self._logger = None
    
    # .................................................................................................................

    # MAY OVERRIDE
    def __repr__(self):
        
        # Blind repr, just list the setup function arguments and values
        try:
            
            # List out each (reconfigurable) variable and it's current value
            save_draw, nosave_draw, save_sliders, nosave_sliders, invis_set = self.current_settings()
            no_drawing_vars = ((len(save_draw) + len(nosave_draw)) < 1)
            no_slider_vars = ((len(save_sliders) + len(nosave_sliders)) < 1)
            no_invis_vars = (len(invis_set) < 1)
            
            # Print out names of drawing variables
            repr_strings = ["", "--- Drawing variables ---"]
            if no_drawing_vars:
                repr_strings += ["  (none)"]
            else:
                repr_strings += ["  {}: {}".format(*key_value) for key_value in save_draw.items()]
                repr_strings += ["  (not saved) {}: {}".format(*key_value) for key_value in nosave_draw.items()]
            
            # Print out names of 'slider' (i.e. non-drawing) variables
            repr_strings += ["", "--- Slider variables ---"]
            if no_slider_vars:
                repr_strings += ["  (none)"]
            else:
                repr_strings += ["  {}: {}".format(*key_value) for key_value in save_sliders.items()]
                repr_strings += ["  (not saved) {}: {}".format(*key_value) for key_value in nosave_sliders.items()]
            
            # Print out names of invisible variables (i.e. vars with hidden controls)
            repr_strings += ["", "--- Invisible variables ---"]
            if no_invis_vars:
                repr_strings += ["  (none)"]
            else:
                repr_strings += ["  " + ", ".join(list(invis_set))]
            
        except (ValueError, TypeError, AttributeError):
            repr_strings = ["No repr"]
        
        return "\n".join(["{} ({}):".format(self.__class__.__name__, self.script_name)] + repr_strings)
    
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE
    def _setup_logger(self, log_path, log_files_to_keep = 3):
        
        ''' Helper function for setting up logging on configurables '''
        
        is_enabled = (not self.configure_mode)
        self._logger = Daily_Logger(log_path,
                                    log_files_to_keep = log_files_to_keep,
                                    enabled = is_enabled,
                                    print_when_disabled = True)
        
        return
    
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE
    @property
    def class_name(self):
        
        ''' Return the name of the class of this object '''
        
        return self.__class__.__name__
    
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE
    def log(self, message, prepend_empty_line = True):
        
        # If no logger exists, just print the message
        if self._logger is None:
            if prepend_empty_line:
                print("")
            print(message)
            return
        
        self._logger.log(message, prepend_empty_line)
        
        return
    
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE
    def log_list(self, list_of_messages, prepend_empty_line = True, entry_separator = "\n"):
        
        # If no logger exists, just print the message
        if self._logger is None:
            if prepend_empty_line:
                print("")
            print(*list_of_messages, sep = entry_separator)
            return
        
        self._logger.log_list(list_of_messages, prepend_empty_line, entry_separator)
        
        return
    
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE
    def set_configure_mode(self, configure_enabled = True):
        
        '''
        This function should only be called during configuration. It can be used to enable the special
        configuring flag, so that special (config-only) behavior can run
        '''
        
        self.configure_mode = configure_enabled
        
        # If we have a logger object, disable it during config
        if self._logger is not None:
            self._logger.disable_logging()
    
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE
    def reconfigure(self, setup_data_dict = {}):
        
        '''
        Function called when adjusting controls for a given configurable
        This function calls the setup() function after updating the controllable parameters.
        The setup function is a good place to put any number-crunching that needs to be (re-) done
        after updating the controls
        '''
        
        # Set all the variable values specified by the setup_data_dict
        self._set_variable_name_values(setup_data_dict)
        
        # Call the setup function to handle any post-update setup required
        self.setup(setup_data_dict)
       
    # .................................................................................................................
    
    # SHOULD OVERRIDE. Don't override the i/o
    def setup(self, variables_changed_dictionary):
        
        ''' 
        This function is called after reconfigure() function.
        When this function is called, the configurable variables have just been updated.
        If anything needs to be done with the before the configurable calls run(), it should be placed here!
        '''
        
        # Create a simple (debug-friendly) setup function for all core configs to start with
        setup_msg = ["", "Setup for {} @ {} ".format(self.class_name, self.script_name)]
        setup_msg += ["(Override setup function to get rid of this printout)"]
        if len(variables_changed_dictionary) > 0:
            setup_msg += ["  {}: {}".format(*each_item) for each_item in variables_changed_dictionary.items()]
        else:
            setup_msg += ["  No variables changed!"]
        print("\n".join(setup_msg))
        
    # .................................................................................................................
    
    # MUST OVERRIDE. Must override the i/o for each core stage
    def run(self):
        '''
        Input/output and behaviour of this function depends on each sub-class implementation
        '''
        raise NotImplementedError("Must implement a run() function!")
        
    # .................................................................................................................
        
    # MUST OVERRIDE. No i/o. Gets called when the video jumps
    def reset(self):
        err_msg = "Must implement a reset() function! ({} - {})".format(self.script_name, self.class_name)
        raise NotImplementedError(err_msg)
        
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE
    def current_settings(self):
        
        '''
        Function which returns a json-friendly output describing the current
        configuration settings (i.e. settings that can be controlled) of this object
        
        Inputs:
            None!
        
        Outputs:
            save_draw_json, nosave_draw_json, save_slider_json, nosave_slider_json, invisible_vars_set
        '''
        
        # Grab variable name info from the control specs
        save_draw_vars, nosave_draw_vars, save_slider_vars, nosave_slider_vars, invisible_vars_set = \
        self.ctrl_spec.get_all_variable_naming()
        
        # Loop through all saveable drawing variables and retrieve values
        save_draw_json = self._get_variable_name_values(save_draw_vars, jsonify = True)
        nosave_draw_json = self._get_variable_name_values(nosave_draw_vars, jsonify = True)
        save_slider_json = self._get_variable_name_values(save_slider_vars, jsonify = True)
        nosave_slider_json = self._get_variable_name_values(nosave_slider_vars, jsonify = True)
        
        return save_draw_json, nosave_draw_json, save_slider_json, nosave_slider_json, invisible_vars_set
        
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE
    def get_drawing_spec(self, variable_name):
        
        ''' 
        Function which return a (json-friendly) drawing specification for the given variable name
        For this to work properly, the variable name must have been 
        defined as a variable that is altered through a drawing control
        (using ctrl_spec.attach_drawing(...) function)
        '''
        
        return self.ctrl_spec.get_drawing_specification(variable_name)
    
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE
    def get_save_data_dict(self, configuration_utility_file_dunder = None):
        
        '''
        Function used to get the data/info needed to save this configurable.
        Not responsible for providing file pathing or actually performing the save however!
        
        Inputs:
            configuration_utility_file_dunder -> (String or None) File dunder (__file__) from the utility
                                                 used to save the configurable data
            
        Outputs: 
            save_data_dict
        '''
        
        # Get current variable settings to save as the setup data
        save_draw_json, _, save_slider_json, _, _ = self.current_settings()
        setup_data_dict = {**save_slider_json, **save_draw_json}
        
        # Create save data using a standardized function to guarantee consistent formatting
        save_data_dict = create_configurable_save_data(self.script_name,
                                                       self.class_name,
                                                       configuration_utility_file_dunder,
                                                       setup_data_dict)
        
        return save_data_dict
    
    # .................................................................................................................
    
    def _set_variable_name_values(self, variable_name_dict):
        
        '''
        Helper function which sets the value of a set of variable names, based on an input dictionary
        The input dict should have keys corresponding to the variable names to change,
        with values corresponding to the value that should be set.
        '''
        
        # Loop through all variable names in the provided dictionary
        # and update those values for this object, though only if we have matching variables!
        for each_variable_name, each_value in variable_name_dict.items():
            
            # Make sure we're not setting non-existent variables & warn the user about it
            missing_attribute = (not hasattr(self, each_variable_name))
            if missing_attribute:
                warning_str_list = ["!" * 56,
                                    "WARNING: {} ({})".format(self.instance_type.capitalize(), self.script_name),
                                    "  Skipping unrecognized variable name: {}".format(each_variable_name),
                                    "  This configuration is likely out of date or has an error!",
                                    "!" * 56]
                self.log_list(warning_str_list)
                sleep(2.0)
                continue
            
            # If we get here, we have the attribute, so update it
            setattr(self, each_variable_name, each_value)
            
        return
    
    # .................................................................................................................
    
    def _get_variable_name_values(self, variable_name_list, jsonify = True):
        
        '''
        Helper function which reads the current value of each variable name provided as an input list
        Returns a dictionary, with keys corresponding to the variable names and their corresponding values
        Can optionally convert data to json-friendly format (i.e. convert numpy arrays to lists) for saving
        '''
        
        # Loop through each variable name and check if it exists within this object, if so, retrieve the value
        variable_values_dict = {}
        for each_variable_name in variable_name_list:
            
            # Make sure this object has the given variable name before trying to access it
            missing_attribute = (not hasattr(self, each_variable_name))
            if missing_attribute:
                warning_str_list = ["!" * 56,
                                    "WARNING: {} ({})".format(self.instance_type.capitalize(), self.script_name),
                                    "  Couldn't find variable name: {}".format(each_variable_name),
                                    "!" * 56]
                self.log_list(warning_str_list)
                sleep(2.0)
                continue
        
            # If we get here, get the current value of the variable and place it in the output dictionary
            variable_values_dict.update({each_variable_name: getattr(self, each_variable_name)})
            
        # If needed, convert data types to json-friendly format (getting rid of numpy arrays)
        if jsonify:
            return jsonify_numpy_data(variable_values_dict)
        
        return variable_values_dict
    
    # .................................................................................................................
    # .................................................................................................................


# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////


class Core_Configurable_Base(Configurable_Base):
    
    # .................................................................................................................
    
    def __init__(self, configurable_instance_type, cameras_folder_path, camera_select, 
                 input_wh, *, file_dunder):
        
        '''
        Class which serves as a base class for all core-system (i.e. detection/tracking) configurables
        All core stage implementations should inherit from this class as a starting point.
        
        Inputs:
            configurable_instance_type -> (String) The name of the specific type/stage name of the class
                                          For example: 'preprocessor', 'tracker' etc.
                                          This should be set by the reference implementation of the stage
            
            cameras_folder_path, camera_select -> (Strings) Selection args.
            
            input_wh -> (Tuple) Stores the frame dimensions of incoming image data to a given stage.
            
            file_dunder -> (String) Should be entered as '__file__' from the final class implementation of the
                           configurable. That is, from a class that isn't inherited by anything else.
        '''
        
        # Inherit from base class
        super().__init__("core", configurable_instance_type,
                         cameras_folder_path, camera_select, file_dunder = file_dunder)
        
        # Store in/out sizing info
        self.input_wh = tuple(input_wh)
        self.output_wh = tuple(input_wh)
        
        # Set up logging
        log_path = build_core_logging_folder_path(cameras_folder_path, camera_select, self.instance_type)
        self._setup_logger(log_path, log_files_to_keep = 2)
        
    # .................................................................................................................
    
    # SHOULD OVERRIDE
    def close(self, final_frame_index, final_epoch_ms, final_datetime):
        
        '''
        Function which gets called when the system is shutting down.
        Should clean up any file access or finalize data that may be saved on shutdown.
        '''
        
        print("  Closing", self.instance_type, "(should implement a close(...) function!)")
        
        return
        
    # .................................................................................................................
    
    # MAY OVERRIDE. Don't override the i/o
    def set_output_wh(self):
        
        '''
        By default, objects use the same output size as the input
        Some objects (preprocessor + foreground extractor) may need to override this function
        Gets called during setup, after initializing the object
        '''
        
        try:
            self.output_wh = self.input_wh.copy()
        except AttributeError:
            self.output_wh = self.input_wh
        
        return
    
    # .................................................................................................................
    
    # MAY OVERRIDE. Don't override the i/o
    def get_output_wh(self):
        
        '''
        Returns a tuple of the output width/height after the given processing stage
        '''
        
        if self.output_wh is None:
            raise AttributeError("Can't configure! Output width/height not set by {}".format())
        
        return self.output_wh
    
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE
    def update_time(self, current_frame_index, current_epoch_ms, current_datetime):
        
        '''
        Function for telling each stage the current frame timing/datetime
        '''
        
        self.current_frame_index = current_frame_index
        self.current_epoch_ms = current_epoch_ms
        self.current_datetime = current_datetime
        
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE
    def get_time_info(self):
        
        '''
        Returns the current frame index, the current time elapsed (epoch milliseconds) and current datetime
        '''
        
        return self.current_frame_index, self.current_epoch_ms, self.current_datetime
    
    # .................................................................................................................
    # .................................................................................................................


# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////


class Stations_Configurable_Base(Configurable_Base):
    
    # .................................................................................................................
    
    def __init__(self, station_name, cameras_folder_path, camera_select, video_wh, *, file_dunder):
        
        # Inherit from base class
        configurable_instance_type = station_name if station_name else "undefined"
        super().__init__("stations", configurable_instance_type, cameras_folder_path, camera_select,
                         file_dunder = file_dunder)
        
        # Allocate storage for storing current dataset
        self._station_dataset = []
        
        # Save video sizing info
        self.video_wh = video_wh
        
        # Set up logger
        log_path = build_stations_logging_folder_path(cameras_folder_path, camera_select, self.instance_type)
        self._setup_logger(log_path, log_files_to_keep = 2)
    
    # .................................................................................................................
    
    # SHOULD OVERRIDE
    def close(self, final_frame_index, final_epoch_ms, final_datetime):
        
        '''
        Function which gets called when the system is shutting down.
        Should clean up any file access or finalize data that may be saved on shutdown.
        '''
        
        print("  Closing", self.instance_type, "(should implement a close(...) function!)")
        
        return
    
    # .................................................................................................................
    
    # MAY OVERRIDE. Be sure to clear the existing dataset!
    def reset(self):
        
        ''' Function called every time video processing rewinds or jumps around in time. Mostly for configuration '''
        
        # Wipe out actual dataset
        self._clear_dataset_in_place()
        
        return
    
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE
    def output_data_list(self):
        
        '''
        Function which is responsible for outputting the dataset when requested (for saving) 
        These requests are trigger by the station bundler
        
        Note that the internal dataset storage is cleared after every output!
        
        Inputs:
            Nothing!
        
        Outputs:
            post_processed_data_list
        '''
        
        # Get current dataset (list of 'one frame results')
        current_dataset_list = self._get_dataset()
        
        # Apply any post-processing, if needed
        post_processed_data_list = self.post_process_output_data(current_dataset_list)
        
        # Clear internal data storage so we can collecting new data for the next output update
        self._clear_dataset()
        
        return post_processed_data_list
    
    # .................................................................................................................
    
    # MAY OVERRIDE
    def post_process_output_data(self, current_dataset_list):
        
        '''
        Function used to perform any post-processing on a block of data before saving
        Can be used to apply smoothing/filter out noise for example
        Intended for use on processing that can't be done sample-by-sample in real-time
        
        Inputs:
            current_dataset_list -> (List) The current data about to be saved
        
        Outputs:
            post_processed_data_list -> (List) The post-processed data to be saved
        '''
        
        # By default, does no post-processing, so just acts as a passthru
        return current_dataset_list
    
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE
    def _store_one_frame_result(self, one_frame_result):
        
        '''
        Generic function used to accumulate single-frame results
        If the dataset type is changed (from the default list type)
        this function can be overriden to maintain consistent behavior
        '''
        
        self._station_dataset.append(one_frame_result)
        
        return
    
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE
    def _get_dataset(self):
        
        '''
        Generic function used to get the current dataset.
        If the dataset type is changed (from the default list type)
        this function can be override to maintain consistent behavior
        '''
        
        return self._station_dataset
    
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE
    def _update_dataset(self, new_station_data):
        
        '''
        Generic function used to add new single-frame entries to the current dataset.
        If the dataset type is changed (from the default list type)
        this function can be override to maintain consistent behavior
        '''
        
        self._station_dataset.append(new_station_data)
        
        return
    
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE
    def _clear_dataset(self):
        
        '''
        Generic function used to clear the dataset, but not in-place
        (in case something else has a reference to the original data)
        '''
        
        self._station_dataset = []
        
        return
    
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE
    def _clear_dataset_in_place(self):
        
        ''' Function used to delete the current dataset in-place, so that all references are also cleared '''
        
        self._station_dataset *= 0
        
        return
    
    # .................................................................................................................
    # .................................................................................................................


# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////

class Externals_Configurable_Base(Configurable_Base):
    
    # .................................................................................................................
    
    def __init__(self, configurable_instance_type, cameras_folder_path, camera_select, video_wh, *, file_dunder):
        
        # Inherit from base class
        super().__init__("externals", configurable_instance_type, cameras_folder_path, camera_select,
                         file_dunder = file_dunder)
        
        # Save video sizing info
        self.video_wh = video_wh
        
        # Set up logger
        log_path = build_externals_logging_folder_path(cameras_folder_path, camera_select, self.instance_type)
        self._setup_logger(log_path, log_files_to_keep = 2)
        
    # .................................................................................................................
    # .................................................................................................................


# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////

class After_Database_Configurable_Base(Configurable_Base):
    
    # .................................................................................................................
    
    def __init__(self, configurable_instance_type, cameras_folder_path, camera_select, *, file_dunder):
        
        # Inherit from base class
        super().__init__("after_database", configurable_instance_type, cameras_folder_path, camera_select,
                         file_dunder = file_dunder)
        
    # .................................................................................................................
    
    def reset(self):
        # No need for a reset function for a classifier (outside of real-time loop)
        print("No reset function for classifier: {}".format(self.class_name))
        
    # .................................................................................................................
    # .................................................................................................................

# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////


# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions
    
# .....................................................................................................................
    
def jsonify_numpy_data(data):
    
    ''' 
    Function for converting data containing numpy arrays into a format that the json.dump() function can save.
    Also works on (basic) data structures that may contain numpy data. 
    For example, lists, tuples or dictionaries of np.arrays
    
    Inputs:
        data (that is meant to be saved in JSON format but may contain numpy arrays)
        
    Outputs:
        json_friendly_data
    '''

    if type(data) in {list, tuple}:
        json_friendly_data = [jsonify_numpy_data(each_value) for each_value in data]
        
    elif type(data) is dict:
        json_friendly_data = {each_key: jsonify_numpy_data(each_value) for each_key, each_value in data.items()}
    
    elif type(data) is np.ndarray:
        json_friendly_data = data.tolist()
        
    elif type(data) in {np.int, np.int32, np.int64}:
        json_friendly_data = int(data)
        
    elif type(data) in {np.float, np.float16, np.float32, np.float64}:
        json_friendly_data = float(data)
        
    else:
        try:
            json_friendly_data = data.copy()
        except AttributeError:
            json_friendly_data = data
    
    return json_friendly_data

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Demo
    
if __name__ == "__main__":
    
    pass
    

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap



    