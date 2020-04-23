#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Mar 31 16:22:47 2020

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

import pickle
import numpy as np

from collections import Counter
from time import perf_counter

from sklearn.tree import DecisionTreeClassifier
from sklearn.tree import export_text

from local.lib.common.timekeeper_utils import get_filesafe_date
from local.lib.common.feedback import print_time_taken_ms

from local.lib.file_access_utils.classifier import build_model_resources_path
from local.lib.file_access_utils.read_write import save_config_json, load_config_json

from local.offline_database.object_reconstruction import Smoothed_Object_Reconstruction as Obj_Recon

from local.configurables.after_database.classifier.reference_classifier import Reference_Classifier

from local.eolib.utils.files import get_folder_list

# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes

class Classifier_Stage(Reference_Classifier):
    
    # .................................................................................................................
    
    def __init__(self, cameras_folder_path, camera_select, user_select):
        
        # Inherit from base class
        super().__init__(cameras_folder_path, camera_select, user_select, file_dunder = __file__)
        
        # Storage for the decision tree & id-to-label mapping
        self._column_names_list = None
        self._dtree = None
        self._id_to_label_dict = None
        
        # .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  . Control Group 1 .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .
        
        self.ctrl_spec.new_control_group("Classification Controls")
        
        self.max_tree_depth = \
        self.ctrl_spec.attach_slider(
                "max_tree_depth",
                label = "Max tree depth",
                default_value = 5,
                min_value = 1, max_value = 15,
                return_type = int,
                zero_referenced = True,
                units = "levels",
                tooltip = ["The maximum number of 'decisions' that can be made to determine each objects class.",
                           "A larger depth will lead to a more granular ability to distinguish between different",
                           "objects/classes, however an overly deep tree risks over-fitting to the data!"])
        
        self.min_samples_per_node = \
        self.ctrl_spec.attach_slider(
                "min_samples_per_node",
                label = "Min samples per node",
                default_value = 5,
                min_value = 1, max_value = 100,
                return_type = int,
                zero_referenced = True,
                units = "samples",
                tooltip = [""])
        
        self.min_samples_per_leaf = \
        self.ctrl_spec.attach_slider(
                "min_samples_per_leaf",
                label = "Min samples per leaf",
                default_value = 5,
                min_value = 1, max_value = 100,
                return_type = int,
                zero_referenced = True,
                units = "samples",
                tooltip = [""])
    
    # .................................................................................................................
    
    def setup(self, variables_changed_dict):
        
        
        try:
            tree_classifier, id_to_label_dict = \
            load_classifier_resources(self.cameras_folder_path, self.camera_select)
            self._dtree = tree_classifier
            self._id_to_label_dict = id_to_label_dict
        except FileNotFoundError:
            pass
        # Check for existing resources
        # ...        
        
        # Warning if more than one date folder exists (will load the newest, can 'hide' unwanted folder with . prefix)
        # ...
        
        # Try to load existing resources
        # ...
        
        return
        
    # .................................................................................................................

    def request_object_data(self, object_id, object_database):
        
        # Get object metadata
        object_md = object_database.load_metadata_by_id(object_id)
        
        # Reference does nothing!
        fake_frame_wh = (100, 100)
        fake_global_start_time = 1
        fake_global_end_time = 2
        
        # Reconstruct object from saved metadata
        object_reconstruction = Obj_Recon(object_md,
                                          fake_frame_wh,
                                          fake_global_start_time,
                                          fake_global_end_time)
        
        return object_reconstruction
    
    # .................................................................................................................
    
    def classify_one_object(self, object_data, snapshot_database):
        
        # Initialize outputs
        topclass_dict = {}
        subclass_dict = {}
        attributes_dict = {}
        
        # Get data used to classify object
        data_order, obj_data_list = sample_data_from_object(object_data)
        object_data_array = np.float32(obj_data_list)
        
        # Apply classifier to sample data, and count output ids
        predicted_class_ids = self._dtree.predict(object_data_array)
        id_counts_dict = Counter(predicted_class_ids)
        total_count = len(predicted_class_ids)
        
        # Build topclass output
        for each_id, each_count in id_counts_dict.items():
            predicted_label = self._id_to_label_dict[each_id]
            normalized_score = each_count / total_count
            topclass_dict[predicted_label] = normalized_score
            
        return topclass_dict, subclass_dict, attributes_dict
    
    # .................................................................................................................
    
    def train(self, column_names_list, label_to_id_dict, input_data_array, target_output_array,
              print_feedback = True):
        
        # Store column names
        self._column_names_list = column_names_list
        
        # Generate & store the reverse id-to-label mapping
        id_to_label_dict = {each_id: each_label for each_label, each_id in label_to_id_dict.items()}
        self._id_to_label_dict = id_to_label_dict
        
        # Start timing
        t_start = perf_counter()
        if print_feedback:
            num_data_rows, num_data_cols = input_data_array.shape
            print("", 
                  "Training classifier",
                  "Using {} rows, {} columns of data".format(num_data_rows, num_data_cols),
                  sep = "\n")
        
        # Train the classifier!
        self._dtree = DecisionTreeClassifier(max_depth = self.max_tree_depth, 
                                             min_samples_split = self.min_samples_per_node,
                                             min_samples_leaf = self.min_samples_per_leaf)
        self._dtree.fit(input_data_array, target_output_array)
        
        # End timing and provide finished feedback if needed
        t_end = perf_counter()
        if print_feedback:
            print_time_taken_ms(t_start, t_end, prepend_newline = False, inset_spaces = 2)
        
        return
    
    # .................................................................................................................
    
    def export_tree_as_text(self):
        
        # Get decision tree output in text-format
        feature_name_list = self._column_names_list
        tree_as_text = export_text(self._dtree, feature_name_list, max_depth = 15, spacing = 3)
        
        # Replace instances of class outputs with actual labels
        # Note: Class outputs show up as "class: #", where # indicates the class ID associated with the decision
        edited_tree_as_text_lines = []
        for each_line in tree_as_text.splitlines():
            
            # Replace class index values with actual labels
            edit_line = each_line
            if "class:" in each_line:
                structure_text, class_id_str = each_line.split(":")
                class_id_int = int(class_id_str.strip())
                class_label = self._id_to_label_dict.get(class_id_int, str(class_id_int))
                edit_line = ": ".join([structure_text, class_label])
            edited_tree_as_text_lines.append(edit_line)
            
        # Finally, re-bundle the text into a single string with newlines
        output_text = "\n".join(edited_tree_as_text_lines)
        
        return output_text

    # .................................................................................................................
    # .................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Define pathing functions

# .....................................................................................................................

def build_dtree_folder_path(cameras_folder_path, camera_select, *path_joins):
    
    ''' Helper function which provides a consistent base folder path for storing/retrieving decision tree data '''
    
    return build_model_resources_path(cameras_folder_path, camera_select, "decision_tree", *path_joins)

# .....................................................................................................................

def build_dtree_date_folder(cameras_folder_path, camera_select, date_str, *path_joins):
    
    ''' Helper function which provides consistent pathing to the date folder where files are saved together '''
    
    return build_dtree_folder_path(cameras_folder_path, camera_select, date_str, *path_joins)

# .....................................................................................................................

def build_model_path(cameras_folder_path, camera_select, date_str):
    
    ''' Helper function which provides consistent pathing to the saved decision tree model file '''
    
    return build_dtree_date_folder(cameras_folder_path, camera_select, date_str, "dtree.pkl")

# .....................................................................................................................

def build_lut_path(cameras_folder_path, camera_select, date_str):
    
    ''' Helper function which provides consistent pathing to the id-to-label lookup file '''
    
    return build_dtree_date_folder(cameras_folder_path, camera_select, date_str, "id_to_label.json")

# .....................................................................................................................

def build_explain_path(cameras_folder_path, camera_select, date_str):
    
    ''' Helper function which provides consistent pathing to the text-based model explanation file '''
    
    return build_dtree_date_folder(cameras_folder_path, camera_select, date_str, "tree_as_text.txt")

# .....................................................................................................................

def build_all_file_paths(cameras_folder_path, camera_select, date_str):
    
    ''' Helper function which bundles all save paths into a single call, since they'll usually be shared! '''
    
    # Bundle shared args for convenience
    path_args = (cameras_folder_path, camera_select, date_str)
    
    # Get all the save paths
    model_path = build_model_path(*path_args)
    lut_path = build_lut_path(*path_args)
    explain_path = build_explain_path(*path_args)
    
    return model_path, lut_path, explain_path

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Define i/o functions

# .....................................................................................................................

def _save_model_data(save_path, tree_classifier):
    
    # Save classifier model data
    with open(save_path, "wb") as out_file:
        pickle.dump(tree_classifier, out_file)
    
    return

# .....................................................................................................................

def _save_lut_data(save_path, id_to_label_dict):
    
    # Save label lookup
    save_config_json(save_path, id_to_label_dict, create_missing_folder_path = True)
    
    return

# .....................................................................................................................

def _save_explain_data(save_path, model_as_text):
    
    # Save model explanation
    with open(save_path, "w") as out_file:
        out_file.write(model_as_text)
    
    return

# .....................................................................................................................

def _load_model_data(load_path):
    
    # Load decision tree model
    tree_classifier = None
    with open(load_path, "rb") as in_file:
        tree_classifier = pickle.load(in_file)
    
    return tree_classifier

# .....................................................................................................................

def _load_lut_data(load_path):
    
    # Load id-to-label lookup table as a config file, then make sure IDs are actually ints!
    id_to_label_dict = load_config_json(load_path)
    id_to_label_dict = {int(each_id): each_label for each_id, each_label in id_to_label_dict.items()}
    
    return id_to_label_dict

# .....................................................................................................................

def save_classifier_resources(configurable_ref):
    
    # Get camera selection pathing info from the configurable
    cameras_folder_path = configurable_ref.cameras_folder_path
    camera_select = configurable_ref.camera_select
    
    # Get data to save from the configurable
    tree_classifier = configurable_ref._dtree
    id_to_label_dict = configurable_ref._id_to_label_dict
    model_as_text = configurable_ref.export_tree_as_text()
    
    # Get current date, which we'll use to help make saves unique
    save_date_str = get_filesafe_date()
    
    # Get save pathing
    model_save_path, lut_save_path, explain_save_path = \
    build_all_file_paths(cameras_folder_path, camera_select, save_date_str)
    
    # Save everything
    _save_lut_data(lut_save_path, id_to_label_dict)
    _save_model_data(model_save_path, tree_classifier)
    _save_explain_data(explain_save_path, model_as_text)
    
    return save_date_str

# .....................................................................................................................

def load_classifier_resources(cameras_folder_path, camera_select):
    
    # Check that the folder pathing is valid
    dtree_folder_path = build_dtree_folder_path(cameras_folder_path, camera_select)
    if not os.path.exists(dtree_folder_path):
        print("", "Error! No classifier folder:", "@ {}".format(dtree_folder_path), "", sep = "\n")
        raise FileNotFoundError("Couldn't find decision tree model folder!")
        
    # Get listing of all date folders
    date_folders_list = get_folder_list(dtree_folder_path,
                                        show_hidden_folders = False,
                                        return_full_path = True,
                                        sort_list = True)
    
    # Error if there are no date folders
    no_date_folders = (len(date_folders_list) < 1)
    if no_date_folders:
        print("", "Error! No model resources:", "@ {}".format(dtree_folder_path), "", sep = "\n")
        raise FileNotFoundError("Couldn't find decision tree model resources!")
    
    # Warning if more than one date folder exists, since we're only loading the newest
    newest_date_folder = date_folders_list[-1]
    multiple_date_folders = (len(date_folders_list) > 1)
    if multiple_date_folders:
        print("", 
              "WARNING:", 
              "  Multiple decision tree models detected!",
              ""
              "Only the newest model ({}) will be loaded.".format(newest_date_folder),
              "To prevent this warning deleted unused model folders.",
              "  -> Alternatively, if you would like to keep old model data",
              "     unused folders can be prefixed with '.' to hide them from loading detection.",
              sep = "\n")
    
    # Get pathing to the saved resources
    model_load_path, lut_load_path, _ = \
    build_all_file_paths(cameras_folder_path, camera_select, newest_date_folder)
    
    # Load resources
    tree_classifier = _load_model_data(model_load_path)
    id_to_label_dict = _load_lut_data(lut_load_path)
    
    return tree_classifier, id_to_label_dict

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Define sampling functions

# .....................................................................................................................

def sample_data_from_object(object_reconstruction, num_subsamples = 10, start_inset = 0.02, end_inset = 0.02):
    
    # Initialize outputs
    data_order = []
    data_list = []
    
    # Get the start/end frame index of each object
    start_idx = object_reconstruction.start_idx
    end_idx = object_reconstruction.end_idx
    num_idx = (end_idx - start_idx)
    
    # Calculate a reduced set of samples to select training data from
    inset_start_idx = int(round(start_idx + start_inset * num_idx))
    inset_end_idx = int(round(end_idx - end_inset * num_idx))
    num_inset_idx = (inset_end_idx - inset_start_idx)
    
    # If we don't have enough data for sampling, return nothing
    if num_inset_idx < num_subsamples:
        return data_order, data_list
    
    # Grab some subset of samples to use for training
    subsample_indices = np.int32(np.round(np.linspace(inset_start_idx, inset_end_idx, num_subsamples)))
    data_order, data_list = get_data_list(object_reconstruction, subsample_indices)
    
    return data_order, data_list

# .....................................................................................................................

def get_data_list(object_reconstruction, frame_idx_list, use_raw_trail_data = True):
    
    # For clarity, should match bundled output!
    data_order = ["x", "y", 
                  "dx", "dy", "vv", 
                  "width", "height", 
                  "area", "aspectratio",
                  "x_width", "y_width", "xy_width",
                  "x_height", "y_height", "xy_height",
                  "x_area", "y_area", "xy_area"]
    
    data_order = ["dx", "dy", "vv", 
                  "width", "height", 
                  "area", "aspectratio",
                  "x_width", "y_width", "xy_width",
                  "x_height", "y_height", "xy_height",
                  "x_area", "y_area", "xy_area"]
    
    # Get object data for all provided frame indices
    output_data_list = []
    for each_frame_idx in frame_idx_list:
        
        # Get object sample index for the given frame index
        sample_idx = object_reconstruction.frame_index_to_sample_index(each_frame_idx)
        
        # Decide which trail data to use
        trail_xy = object_reconstruction._real_trail_xy if use_raw_trail_data else object_reconstruction.trail_xy
        
        # Get x/y position info
        x_cen, y_cen = trail_xy[sample_idx]
        
        # Try to calculate the x/y velocity
        try:
            x_futr, y_futr = trail_xy[sample_idx + 1]
            x_prev, y_prev = trail_xy[sample_idx - 1]
            dx_norm = 100.0 * (x_futr - x_prev) / 2.0
            dy_norm = 100.0 * (y_futr - y_prev) / 2.0
            vv_norm = 100.0 * np.sqrt(np.square(dx_norm) + np.square(dy_norm))
        except IndexError:
            dx_norm = 0.0
            dy_norm = 0.0
            vv_norm = 0.0
        
        # Get width/height info
        (x1, y1), (x2, y2) = object_reconstruction.get_box_tlbr(each_frame_idx)
        width_norm = 100.0 * (x2 - x1)
        height_norm = 100.0 * (y2 - y1)
        
        # Get area/aspect ratio
        area_norm = (width_norm * height_norm)
        aspect_ratio = width_norm / height_norm    
        
        # Get xy mixed values
        xy_min = x_cen * y_cen
        x_width = x_cen * width_norm
        y_width = y_cen * width_norm
        xy_width = xy_min * width_norm
        x_height = x_cen * height_norm
        y_height = y_cen * height_norm
        xy_height = xy_min * height_norm
        x_area = x_cen * area_norm
        y_area = y_cen * area_norm
        xy_area = xy_min * area_norm
        
        # Bundle for clarity
        '''
        output_entries = (x_cen, y_cen, 
                          dx_norm, dy_norm, vv_norm,
                          width_norm, height_norm,
                          area_norm, aspect_ratio,
                          x_width, y_width, xy_width,
                          x_height, y_height, xy_height,
                          x_area, y_area, xy_area)
        '''
        output_entries = (dx_norm, dy_norm, vv_norm,
                          width_norm, height_norm,
                          area_norm, aspect_ratio,
                          x_width, y_width, xy_width,
                          x_height, y_height, xy_height,
                          x_area, y_area, xy_area)
        output_data_list.append(output_entries)
    
    return data_order, output_data_list

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Demo

if __name__ == "__main__":
    pass

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap


