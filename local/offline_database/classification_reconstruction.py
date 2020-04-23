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

def create_object_class_dict(class_database, object_list,
                             set_object_classification = True):
    
    '''
    Function which takes in a list of reconstructed objects and 
    returns a dictionary whose keys represent different class labels. 
    Each class label entry holds a list of objects corresponding to that class label.
    '''
    
    object_class_dict = {}
    for each_obj in object_list:
        
        # Look up the classification data for each object
        obj_id = each_obj.full_id
        topclass_label, subclass_label, _, _, attributes_dict = class_database.load_classification_data(obj_id)
        
        # Add an empty list for any non-existant class labels, so we can append objects to it
        if topclass_label not in object_class_dict:
            object_class_dict[topclass_label] = {}
        
        # Update each object with classification & graphics settings, if needed
        if set_object_classification:
            outline_color = class_database.get_label_color(topclass_label)
            each_obj.set_classification(topclass_label, subclass_label, attributes_dict)
            each_obj.set_graphics(outline_color)
        
        # Finally, add the object to the corresponding class list
        object_class_dict[topclass_label][obj_id] = each_obj
    
    return object_class_dict

# .....................................................................................................................

def set_object_classification_and_colors(class_database, object_list):
    
    # Record the number of classes
    class_count_dict = {}
    
    # Load classification for all the objects
    for each_obj in object_list:
    
        # Look up the classification data for each object
        obj_id = each_obj.full_id
        topclass_label, subclass_label, _, _, attributes_dict = class_database.load_classification_data(obj_id)
        outline_color = class_database.get_label_color(topclass_label)
        
        # Update each object with classification & graphics settings
        each_obj.set_classification(topclass_label, subclass_label, attributes_dict)
        each_obj.set_graphics(outline_color)
        
        # Update class count
        if topclass_label not in class_count_dict:
            class_count_dict[topclass_label] = 0
        class_count_dict[topclass_label] += 1
        
    return class_count_dict

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Demo

if __name__ == "__main__":
    pass

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap

