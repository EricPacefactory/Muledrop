#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Oct 25 11:40:38 2019

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


# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes



# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

# .....................................................................................................................

def create_objects_by_class_dict(class_database, object_id_dict,
                                 set_object_classification = True):
    
    '''
    Function which takes in a list of reconstructed objects and 
    returns a dictionary whose keys represent different class labels. 
    Each class label entry holds a list of objects corresponding to that class label.
    
    Returns:
        ordered_object_id_list, object_by_class_dict, object_id_to_class_dict
    '''
    
    default_subclass_label = ""
    default_attributes_dict = {}
    
    ordered_object_id_list = []
    object_id_to_class_dict = {}
    objects_by_class_dict = {}
    for each_obj_id, each_obj_ref in object_id_dict.items():
        
        # Look up the classification data for each object
        topclass_label, topclass_dict = class_database.load_classification_data(each_obj_id)
        
        # Add an empty list for any non-existant class labels, so we can append objects to it
        if topclass_label not in objects_by_class_dict:
            objects_by_class_dict[topclass_label] = {}
        
        # Update each object with classification & graphics settings, if needed
        if set_object_classification:
            outline_color = class_database.get_label_color(topclass_label)
            each_obj_ref.set_classification(topclass_label, default_subclass_label, default_attributes_dict)
            each_obj_ref.set_graphics(outline_color)
        
        # Finally, add the object to the corresponding class listing and other lookup storage
        objects_by_class_dict[topclass_label][each_obj_id] = each_obj_ref
        ordered_object_id_list.append(each_obj_id)
        object_id_to_class_dict[each_obj_id] = topclass_label
    
    # Make sure the ids are in order
    ordered_object_id_list = sorted(ordered_object_id_list)
    
    return ordered_object_id_list, objects_by_class_dict, object_id_to_class_dict

# .....................................................................................................................
    
def get_ordered_object_list(object_id_list, objects_by_class_dict, object_id_to_class_dict):
    
    ''' Helper function which creates a list of object reconstructions, ordered by id '''
    
    # Return object reconstructions in order of object ID
    sorted_object_id_list = sorted(object_id_list)
    ordered_object_list = []
    for each_obj_id in sorted_object_id_list:
        each_obj_class = object_id_to_class_dict[each_obj_id]
        each_obj_ref = objects_by_class_dict[each_obj_class][each_obj_id]
        ordered_object_list.append(each_obj_ref)
    
    return ordered_object_list

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Demo

if __name__ == "__main__":
    pass

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap

