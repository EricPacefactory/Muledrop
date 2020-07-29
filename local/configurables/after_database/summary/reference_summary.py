#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Jan 22 14:53:50 2020

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


# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes

class Reference_Summary(After_Database_Configurable_Base):
    
    # .................................................................................................................
    
    def __init__(self, location_select_folder_path, camera_select, *, file_dunder):
        
        # Inherit from base class
        super().__init__("summary", location_select_folder_path, camera_select, file_dunder = file_dunder)
        
    # .................................................................................................................
    
    def __repr__(self):
        
        repr_strs = ["{} ({})".format(self.class_name, self.script_name)]
        
        return "\n".join(repr_strs)
    
    # .................................................................................................................
    
    # MAY OVERRIDE
    def close(self):
        
        ''' Function called after summary run is completed. Use to clean up any opened resources '''
        
        # Reference version doesn't need any clean-up, so do nothing
        return None
    
    # .................................................................................................................
        
    # MAY OVERRIDE, BUT BETTER TO OVERRIDE request_object_data(...) and summarize_one_object(...)
    def run(self, object_id, object_database, snapshot_database):
        
        ''' 
        Main function of the summary stage. Gets called on every object, independently
        '''
        
        # First get object data (in a customizable format) then classify that object!
        object_data = self.request_object_data(object_id, object_database)
        summary_data_dict = self.summarize_one_object(object_data, snapshot_database)
            
        return summary_data_dict
    
    # .................................................................................................................

    # MAY OVERRIDE IF DIFFERENT DATA IS NEEDED (E.G. NOT ALL METADATA NEEDS TO BE LOADED)
    def request_object_data(self, object_id, object_database):
        
        ''' 
        Function used to get the data needed to calculate summary info
        The result of this function will be passed as an input to the summarize_one_object() function
        It is likely to be a dictionary, but could be override to provide something more specific, if needed.
        '''
        
        # Reference does nothing!
        object_data = {}
        
        return object_data
    
    # .................................................................................................................
    
    # SHOULD OVERRIDE
    def summarize_one_object(self, object_data, snapshot_database):
        
        '''
        Function which performs actual summary operation, given some 'object_data' 
        and access to the snapshot database, if needed.
        Note that the object data can be in any format,
        depending on how it is output from the request_object_data() function.
        
        Must return:
            summary_data_dict (dictionary)
        '''
        
        # Reference implementation just hard-codes an empty output
        summary_data_dict = {}
        
        return summary_data_dict

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


