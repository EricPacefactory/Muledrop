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

from time import perf_counter
from tqdm import tqdm

from local.configurables.configurable_template import Classifier_Configurable_Base

from local.lib.file_access_utils.classifier import new_classification_entry

from local.offline_database.object_reconstruction import Object_Reconstruction


from local.lib.file_access_utils.classifier import build_classifier_resources_path
from local.lib.file_access_utils.resources import build_base_resource_path

# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes

class Reference_Classifier(Classifier_Configurable_Base):
    
    # .................................................................................................................
    
    def __init__(self, cameras_folder_path, camera_select, user_select, task_select, *, file_dunder):
        
        # Inherit from base class
        super().__init__(cameras_folder_path, camera_select, user_select, task_select, file_dunder = file_dunder)
        
        # Store useful pathing needed by classifiers
        self.config_folder_path = os.path.join(cameras_folder_path, 
                                               camera_select,
                                               "users",
                                               user_select,
                                               "tasks",
                                               task_select,
                                               "classifier")
        self.resources_folder_path = build_classifier_resources_path(cameras_folder_path, camera_select)
        
    # .................................................................................................................
    
    def __repr__(self):
        
        # Figure out how many snapshots we've already taken
        num_snapshots = self.snapshot_counter
        if not num_snapshots:
            num_snapshots = "no"
        
        repr_strs = ["Snapshot Capture ({})".format(self.script_name),
                     "  Metadata folder: {}".format(self.image_metadata_saver.relative_data_path()),
                     "     Image folder: {}".format(self.image_saver.relative_data_path()),
                     "  ({} snapshots so far)".format(num_snapshots)]
        
        return "\n".join(repr_strs)
    
    # .................................................................................................................
    
    # MAY OVERRIDE
    def close(self):
        
        ''' Function called after classification is completed. Use to clean up any opened resources '''
        
        # Reference version doesn't need any clean-up, so do nothing
        return
    
    # .................................................................................................................
        
    # MAY OVERRIDE, BUT BETTER TO OVERRIDE classifiy_one_object()!
    def run(self, reconstructed_object_list, snapshot_database, enable_progress_bar = False):
        
        ''' 
        Main function of the classifier. 
        This function is called after calling the create_object_list() function
        and is responsible for generating a dictionary containing keys representing object ids,
        for each id, there should be a corresponding dictionary holding classification info!
        '''
        
        # Start progres bar for feedback
        if enable_progress_bar:
            num_objs = len(reconstructed_object_list)
            cli_prog_bar = tqdm(total = num_objs, mininterval = 0.5)
        
        # Loop over every object and apply classifier
        classification_dict = {}
        for each_obj in reconstructed_object_list:
            
            # Classify each object
            class_label, score_pct, subclass, attributes = self.classify_one_object(each_obj, snapshot_database)
            
            # Add new classification results to output
            obj_id = each_obj.full_id
            new_entry = new_classification_entry(obj_id, class_label, score_pct, subclass, attributes)
            classification_dict.update(new_entry)
            
            # Update progress bar feedback, if needed
            if enable_progress_bar:
                cli_prog_bar.update()
            
        # Clean up
        if enable_progress_bar:
            cli_prog_bar.close()
            
        return classification_dict
        
    # .................................................................................................................
    
    # SHOULD OVERRIDE!
    def classify_one_object(self, object_ref, snapshot_database):
        
        '''
        Function which takes in a reconstructed object and a reference to the snapshot database,
        and is expected to output a classification for the object
        '''
        
        # Reference implementation doesn't do anything meaningful...
        class_label = "unclassified"
        score_pct = 0
        subclass = ""
        attributes = {}
        
        return class_label, score_pct, subclass, attributes
    
    # .................................................................................................................
    
    # MAY OVERRIDE IF AN ALTERNATE OBJECT RECONSTRUCTION IS NEEDED (E.G. WITH SMOOTHING)
    def create_object_list(self, object_metadata_generator, snapshot_wh, global_starting_time, global_ending_time):        
        
        ''' Function which creates the list of reconstructed objects passed into the run function '''
        
        obj_list = Object_Reconstruction.create_reconstruction_list(object_metadata_generator,
                                                                    snapshot_wh,
                                                                    global_starting_time, 
                                                                    global_ending_time)
        
        return obj_list

    # .................................................................................................................

    # MAY OVERRIDE IF DIFFERENT DATA IS NEEDED (E.G. NOT ALL METADATA NEEDS TO BE LOADED)
    def request_object_data(self, object_database, task_select, starting_time, ending_time):
        
        ''' 
        Function which creates a generator for loading object metadata off the provided object database 
        The output of this function will feed into the input of the create_object_list(...) function
        '''
        
        # Get object metadata from the server
        obj_metadata_generator = object_database.load_metadata_by_time_range(task_select, 
                                                                             starting_time, 
                                                                             ending_time)
        
        return obj_metadata_generator

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


