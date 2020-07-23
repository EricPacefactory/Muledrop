#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Oct 31 14:53:44 2019

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

class Reference_Classifier(After_Database_Configurable_Base):
    
    # .................................................................................................................
    
    def __init__(self, location_select_folder_path, camera_select, *, file_dunder):
        
        # Inherit from base class
        super().__init__("classifier", location_select_folder_path, camera_select, file_dunder = file_dunder)
        
    # .................................................................................................................
    
    def __repr__(self):
        
        repr_strs = ["{} ({})".format(self.class_name, self.script_name)]
        
        return "\n".join(repr_strs)
    
    # .................................................................................................................
    
    # MAY OVERRIDE
    def close(self):
        
        ''' Function called after classification is completed. Use to clean up any opened resources '''
        
        # Reference version doesn't need any clean-up, so do nothing
        return None
    
    # .................................................................................................................
        
    # MAY OVERRIDE, BUT BETTER TO OVERRIDE request_object_data() & classifiy_one_object()!
    def run(self, object_id, object_database, snapshot_database):
        
        ''' 
        Main function of the classifier. Gets called on every object, independently
        '''
        
        # First get object data (in a customizable format) then classify that object!
        object_data = self.request_object_data(object_id, object_database)
        topclass_dict, subclass_dict, attributes_dict = self.classify_one_object(object_data, snapshot_database)
            
        return topclass_dict, subclass_dict, attributes_dict
    
    # .................................................................................................................

    # SHOULD OVERRIDE TO PROVIDE APPROPRIATE DATA FORMAT (E.G. NOT ALL METADATA NEEDS TO BE LOADED/RETURNED)
    def request_object_data(self, object_id, object_database):
        
        ''' 
        Function used to get the data needed to perform classification
        The result of this function will be passed as an input to the classify_one_object() function
        It is likely to be a dictionary, but could be override to provide something more specific, 
        depending on the needs of the classifier!
        '''
        
        # Reference does nothing!
        object_data = {}
        
        return object_data
    
    # .................................................................................................................
    
    # SHOULD OVERRIDE
    def classify_one_object(self, object_data, snapshot_database):
        
        '''
        Function which performs actual classification given some 'object_data' 
        and access to the snapshot database, if needed.
        Note that the object data can be in any format, 
        depending on how it is output from the request_object_data() function.
        Though for most use cases, it's likely to be a reconstruction of some kind.
        
        Must return:
            topclass_dict, subclass_dict, attributes_dict (all dictionaries)
            
        Notes:
        - The topclass_dict and subclass_dict are expected to have keys corresponding to class labels,
          and values corresponding to the score or probability of the object being each class.
        - The topclass is meant to be the main classification, whereas the subclass represents a more granular
          classification (for example, topclass = 'vehicle', subclass = 'forklift').
        - The attributes_dict is meant to contain additional identifying info, such as whether a person
          was wearing a safety vest or eye protection. Mostly just a placeholder for now...
        '''
        
        # Reference implementation just hard-codes meaningless outputs
        topclass_dict = {}
        subclass_dict = {}
        attributes_dict = {}
        
        return topclass_dict, subclass_dict, attributes_dict

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


