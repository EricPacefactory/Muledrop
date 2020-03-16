#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Jan 24 15:01:13 2020

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

from local.configurables.configurable_template import After_Database_Configurable_Base

from local.lib.common.timekeeper_utils import get_isoformat_string, datetime_to_epoch_ms

# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes

class Reference_Rule(After_Database_Configurable_Base):
    
    # .................................................................................................................
    
    def __init__(self, cameras_folder_path, camera_select, user_select, input_wh, *, file_dunder):
        
        # Inherit from base class
        super().__init__(cameras_folder_path, camera_select, user_select, "rules", file_dunder = file_dunder)
        
        # Store rule-specific info
        self.input_wh = input_wh
        
    # .................................................................................................................
    
    def __repr__(self):
        
        repr_strs = ["{} ({})".format(self.class_name, self.script_name)]
        
        return "\n".join(repr_strs)
    
    # .................................................................................................................
    
    # MAY OVERRIDE
    def close(self):
        
        ''' Function called after rule evaluation is completed. Use to clean up any opened resources '''
        
        # Reference version doesn't need any clean-up, so do nothing
        return None
    
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE
    def get_rule_type(self):
        return os.path.splitext(self.script_name)[0]
    
    # .................................................................................................................
    
    # SHOULDN'T OVERRIDE
    def get_rule_info(self, rule_name):
        
        '''
        Function which generates data describing each configured rule, for reference on the database
        Intended to provide info about the rule configuration, which can be used for drawing/presenting the
        rule in other UIs (e.g. on the web)
        '''
        
        # Grab setup data for saving into rule info output
        access_info_dict, setup_data_dict = self.get_data_to_save()
        
        # Bundle output data, which will be saved into a json file
        output_info_dict = {"rule_type": self.get_rule_type(),
                            "rule_name": rule_name,
                            "configuration": setup_data_dict}
        
        return output_info_dict
    
    # .................................................................................................................
        
    # MAY OVERRIDE, BUT BETTER TO OVERRIDE process_object_metadata() & evaluate_one_object()!
    def run(self, object_id, object_metadata, snapshot_database):
        
        ''' 
        Main function of the rule. 
        Object metadata is loaded once, per object ID, and is passed in to each rule for evaluation.
        '''
        
        # First get object data (in a customizable format) then classify that object!
        object_data = self.process_object_metadata(object_id, object_metadata, self.input_wh)
        rule_results_dict, rule_results_list =  self.evaluate_one_object(object_data, snapshot_database, self.input_wh)
        
        return rule_results_dict, rule_results_list
    
    # .................................................................................................................

    # SHOULD OVERRIDE TO PROVIDE APPROPRIATE DATA FORMAT
    def process_object_metadata(self, object_id, object_metadata, frame_wh):
        
        ''' 
        Function used to get the data needed to perform rule evaluation
        The result of this function will be passed as an input to the evaluate_one_object() function
        '''
        
        # Reference does nothing!
        object_data = {}
        
        return object_data
    
    # .................................................................................................................
    
    # SHOULD OVERRIDE
    def evaluate_one_object(self, object_data, snapshot_database, frame_wh):
        
        '''
        Function which performs actual rule evaluation, given some 'object_data' 
        and access to the snapshot database, if needed.
        Note that the object data can be in any format, 
        depending on how it is output from the process_object_metadata() function.
        
        Must return:
            rule_results_dict, rule_results_list
            
        *** Note 1: If an object does not break/trigger a rule, it should return an empty dict/list
                    -> This helps indicate that the object WAS evaluated, and just returned no result
        *** Note 2: The rule dict can contain any shared data from evaluation. It may also be empty
        *** Note 3: The rule list should contain dictionary entries holding metadata describing rule events
        '''
        
        # Reference implementation returns empty rule results
        rule_results_dict = {}
        rule_results_list = []
        
        return rule_results_dict, rule_results_list

    # .................................................................................................................
    
    # MAY OVERRIDE. Only used during configuration
    def process_all_object_metadata(self, all_object_ids, all_object_metadata, frame_wh):
        
        '''
        Helper function meant to be used only during configuration, where the same object dataset is likely to
        be used/re-used many times.
        '''
        
        all_object_data = {}
        for each_obj_id, each_obj_metadata in zip(all_object_ids, all_object_metadata):
            all_object_data[each_obj_id] = self.process_object_metadata(each_obj_id, each_obj_metadata, frame_wh)
            
        return all_object_data
    
    # .................................................................................................................
    
    # MAY OVERRIDE. Only used during configuration
    def evaluate_all_objects(self, object_data_dict, snapshot_database, frame_wh):
        
        '''
        Helper function meant to be used only during configuration, where re-evaluating the rule across many
        (pre-processed) objects is likely to be needed.
        '''
        
        rule_results_dict = {}
        for each_obj_id, each_obj_data in object_data_dict.items():
            rule_results_dict[each_obj_id] = self.evaluate_one_object(each_obj_data, snapshot_database, frame_wh)
        
        return rule_results_dict

    # .................................................................................................................
    # .................................................................................................................


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


