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

from local.lib.configuration_utils.controls_specification import Controls_Specification

# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes



class Configurable_Base:
    
    # .................................................................................................................
    
    def __init__(self, *, file_dunder, target_parent_folder = None, target_grandparent_folder = None):
        
        # Extract info about the configurable based on it's file pathing
        self.script_name = os.path.basename(file_dunder)
        self.parent_folder = os.path.basename(os.path.dirname(file_dunder))
        self.grandparent_folder = os.path.basename(os.path.dirname(os.path.dirname(file_dunder)))
        
        # Raise an error if we weren't passed the right parent folder pathing
        if (target_parent_folder is not None) and (target_parent_folder != self.parent_folder):
            print("", "Mismatched parent folders!",
                  "        Got: {}".format(self.parent_folder),
                  "  Expecting: {}".format(target_parent_folder), 
                  "", "", sep="\n")
            raise AttributeError("Error in configurable parent folder! ({})".format(self.script_name))  
            
        # Raise an error if we weren't passed the right grandparent (parent-of-parent) folder pathing
        if (target_grandparent_folder is not None) and (target_grandparent_folder != self.grandparent_folder):
            print("", "Mismatched grandparent folders!",
                  "        Got: {}".format(self.grandparent_folder),
                  "  Expecting: {}".format(target_grandparent_folder), 
                  "", "", sep="\n")
            raise AttributeError("Error in configurable grandparent folder! ({})".format(self.script_name))
        
        # Storage for timing info
        self.current_frame_index = None
        self.current_time_sec = None
        self.current_datetime = None
        self.current_snapshot_metadata = None
        
        # Variables for controls/configuration functionality
        self.configure_mode = False
        self.ctrl_spec = Controls_Specification()
    
    # .................................................................................................................

    # MAY OVERRIDE
    def __repr__(self):
        
        # Blind repr, just list the setup function arguments and values
        try:
            
            # List out each (reconfigurable) variable and it's current value
            settings_dict = self.current_settings()            
            repr_strings = ["  {}: {}".format(each_key, each_value) for each_key, each_value in settings_dict.items()]
            
            # Return a special message in the case of having no settings (e.g. a passthrough)
            if len(settings_dict) < 1:
                repr_strings = ["  No configurable settings!"]
            
        except Exception:
            repr_strings = ["No repr"]
        
        return "\n".join(["{} ({}):".format(self.__class__.__name__, self.script_name)] + repr_strings)
    
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE
    @property
    def class_name(self):
        
        '''
        Return the name of the class of this object
        '''
        
        return self.__class__.__name__
    
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE
    def set_configure_mode(self, configure_enabled = True):
        
        '''
        This function should only be called during configuration. It can be used to enable the special
        configuring flag, so that special (config-only) behavior can run
        '''
        
        self.configure_mode = configure_enabled
    
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE
    def reconfigure(self, setup_data_dict = {}):
        
        '''
        Function called when adjusting controls for a given configurable
        This function calls the setup() function after updating the controllable parameters.
        The setup function is a good place to put any number-crunching that needs to be (re-) done
        after updating the controls
        '''
        
        # Loop through all variable names in the setup dictionary
        # and update those values for this object, though only if we have matching variables!
        for each_variable_name, each_value in setup_data_dict.items():
            
            # Make sure we're not setting non-existent variables
            missing_attribute = (not hasattr(self, each_variable_name))
            if missing_attribute:
                print("", 
                      "{} ({})".format(self.component_name.capitalize(), self.script_name),
                      "  Skipping unrecognized variable name: {}".format(each_variable_name), sep="\n")
                continue
            
            # If we get here, we have the attribute, so update it
            setattr(self, each_variable_name, each_value)
        
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
        setup_msg = ["Setup for {} @ {} ".format(self.class_name, self.script_name)]
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
    def current_settings(self, show_only_saveable = False):
        
        '''
        Function which returns a json-friendly output describing the current
        configuration settings (i.e. settings that can be controlled) of this object
        '''
        
        current_variable_values_dict = {}
        variable_name_list = self.ctrl_spec.get_full_variable_name_list(show_only_saveable)
        for each_variable_name in variable_name_list:
            
            # Make sure this object has the given variable name before trying to access it
            missing_attribute = (not hasattr(self, each_variable_name))
            if missing_attribute:
                print("", 
                  "!" * 42,
                  "Error reading configurable settings! ({} - {})".format(self.class_name, self.script_name),
                  "Couldn't find variable name: {}".format(each_variable_name),
                  "!" * 42,
                  "", sep="\n")
                continue
            
            # If we get here, get the current value of the variable and place it in the output dictionary
            current_variable_values_dict.update({each_variable_name: getattr(self, each_variable_name)})
            
        # Convert data types to json-friendly format (mainly dealing with numpy arrays)
        json_property_dict = jsonify_numpy_data(current_variable_values_dict)
        
        return json_property_dict
        
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
    def get_data_to_save(self):
        
        '''
        Function used to get the data/info needed to save this configurable.
        Not responsible for providing file pathing or actually performing the save however!
        
        No inputs
        Returns: access_info_dict, setup_data_dict
        '''
        
        # Grab relevant data for saving
        clean_script_name, _ = os.path.splitext(self.script_name)
        file_access_dict = {"script_name": clean_script_name, "class_name": self.class_name}
        setup_data_dict = self.current_settings(show_only_saveable = True)
        
        return file_access_dict, setup_data_dict
    
    # .................................................................................................................
    # .................................................................................................................


# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////


class Core_Configurable_Base(Configurable_Base):
    
    # .................................................................................................................
    
    def __init__(self, input_wh, *, file_dunder):
        
        # Inherit from base class
        super().__init__(file_dunder = file_dunder,
                         target_parent_folder = None,
                         target_grandparent_folder = "core")
        
        # Store the component name (e.g. preprocessor, detector, ... etc.) & use it as a save name
        self.component_name = self.parent_folder
        self.save_filename = self.component_name + ".json"
        
        # Store in/out sizing info
        self.input_wh = tuple(input_wh)
        self.output_wh = tuple(input_wh)
        
    # .................................................................................................................
    
    # MAY OVERRIDE. Don't override the i/o
    def set_output_wh(self):
        '''        
        By default, objects use the same output size as the input
        Some objects (preprocessor + frame processor) may need to override this function
        Gets called during setup, after initializing the object
        '''
        try:
            self.output_wh = self.input_wh.copy()
        except AttributeError:
            self.output_wh = self.input_wh
    
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
    def update_time(self, current_frame_index, current_time_elapsed_sec, current_datetime):
        
        '''
        Function for telling each stage the current frame timing/datetime
        '''
        
        self.current_frame_index = current_frame_index
        self.current_time_sec = current_time_elapsed_sec
        self.current_datetime = current_datetime
    
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE
    def update_snapshot_record(self, current_snapshot_metadata):
        
        '''
        Function for passing the most recent snapshot metadata into each stage
        '''
        
        self.current_snapshot_metadata = current_snapshot_metadata
        
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE
    def get_time_info(self):
        
        '''
        Returns the current time elapsed (seconds) and current datetime
        '''
        
        return self.current_frame_index, self.current_time_sec, self.current_datetime
    
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE
    def get_snapshot_info(self):
        
        '''
        Returns the current snapshot metadata. 
        Should only be needed when storing data that references snapshot images (ex. object metadata)
        '''
        
        return self.current_snapshot_metadata
    
    # .................................................................................................................
    # .................................................................................................................


# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////

class Externals_Configurable_Base(Configurable_Base):
    
    # .................................................................................................................
    
    def __init__(self, cameras_folder_path, camera_select, user_select, task_select, video_select, video_wh,
                 *, file_dunder):
        
        # Inherit from base class
        super().__init__(file_dunder = file_dunder,
                         target_parent_folder = None,
                         target_grandparent_folder = "externals")
        
        # Save selection info
        self.cameras_folder_path = cameras_folder_path
        self.camera_select = camera_select
        self.user_select = user_select
        self.task_select = task_select
        self.video_select = video_select
        self.video_wh = video_wh
        
        # Store the component name (e.g. preprocessor, detector, ... etc.) & use it as a save name
        self.component_name = self.parent_folder
        self.save_filename = self.component_name + ".json"
        
    # .................................................................................................................
    # .................................................................................................................


# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////

class Classifier_Configurable_Base(Configurable_Base):
    
    # .................................................................................................................
    
    def __init__(self, cameras_folder_path, camera_select, user_select, task_select, *, file_dunder):
        
        # Inherit from base class
        super().__init__(file_dunder = file_dunder,
                         target_parent_folder = "classifier",
                         target_grandparent_folder = None)
        
        # Save selection info
        self.cameras_folder_path = cameras_folder_path
        self.camera_select = camera_select
        self.user_select = user_select
        self.task_select = task_select
        
        # Store the component name & use it as a save name
        self.component_name = self.parent_folder
        self.save_filename = self.component_name + ".json"
        
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

    if type(data) in [list, tuple]:
        json_friendly_data = [jsonify_numpy_data(each_value) for each_value in data]
        
    elif type(data) is dict:
        json_friendly_data = {each_key: jsonify_numpy_data(each_value) for each_key, each_value in data.items()}
    
    elif type(data) is np.ndarray:
        json_friendly_data = data.tolist()
        
    elif type(data) in [np.int, np.int32, np.int64]:
        json_friendly_data = int(data)
        
    elif type(data) in [np.float, np.float16, np.float32, np.float64]:
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



    