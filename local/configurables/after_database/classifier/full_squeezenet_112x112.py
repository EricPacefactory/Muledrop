#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Oct 31 16:48:00 2019

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

from local.configurables.after_database.classifier.reference_classifier import Reference_Classifier
from local.lib.file_access_utils.classifier import build_model_resources_path

from local.lib.classifier_models.squeezenet_variants import Full_SqueezeNet_112x112


# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes

class Image_Based_Classifier_Stage(Reference_Classifier):
    
    # .................................................................................................................
    
    def __init__(self, location_select_folder_path, camera_select):
        
        # Inherit from base class
        super().__init__(location_select_folder_path, camera_select, file_dunder = __file__)
        
        # Allocate storage for the classifier
        self.classifier_model = None
        
        # Build pathing to a saved model file, if present
        self.path_to_model_folder = build_model_resources_path(location_select_folder_path, camera_select)
        self._path_to_model_file = None
        
        # If no model files exist, raise an error (config utility should be responsible for creating base model file!)
        existing_model_files = os.listdir(self.path_to_model_folder)
        no_existing_model_files = (len(existing_model_files) == 0)
        if no_existing_model_files:
            print("",
                  "ERROR LOADING MODEL DATA ({})".format(self.class_name),
                  "",
                  "Model files shoudl be located at:",
                  "  {}".format(self.path_to_model_folder),
                  "",
                  "A default file should be copied here by the configuration utility for this classifier!",
                  sep = "\n")            
            raise FileNotFoundError("No model files found!")
        else:
            print("")
            print("FOUND EXISITING MODELS!")
            print(existing_model_files)
            
        # Figure out model naming
        model_base_name = Full_SqueezeNet_112x112.base_save_name
        self._model_save_name = "{}-({})".format(model_base_name, self.camera_select)
        
        # Set up 'control' parameters
        default_control_value = existing_model_files[0]
        if self._model_save_name in existing_model_files:
            default_control_value = self._model_save_name
        control_label_value_list = list(zip(existing_model_files, existing_model_files))
        
        
        # .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  . Control Group 1 .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .
        
        self.ctrl_spec.new_control_group("Classification Settings")
        
        self.number_frames_to_classify = \
        self.ctrl_spec.attach_slider(
                "number_frames_to_classify", 
                label = "Frames for classification", 
                default_value = 3,
                min_value = 1,
                max_value = 9,
                return_type = int,
                zero_referenced = True,
                tooltip = "Number of frames to check before finalizing the classification.")
            
        # .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  . Control Group 2 .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .
        
        self.ctrl_spec.new_control_group("Model Selection")
        
        self.model_file_name_no_ext = \
        self.ctrl_spec.attach_menu(
                "model_file_name_no_ext", 
                label = "Model File Name", 
                default_value = default_control_value,
                option_label_value_list = control_label_value_list,
                tooltip = "Set the model file name to load in (with no extension)",
                visible = False)
    
    # .................................................................................................................
    
    def close(self):
        return
    
    # .................................................................................................................
    
    def set_to_full_train_mode(self, enable = True):
        raise NotImplementedError("Full training mode not setup yet!")
        
    # .................................................................................................................
    
    def set_to_fine_tune_mode(self, enable = True):
        raise NotImplementedError("Fine tuning mode not setup yet!")
    
    # .................................................................................................................
    
    def set_to_inference_mode(self):
        self.classifier_model.set_to_inference_mode()
    
    # .................................................................................................................
    
    def setup(self, variables_changed_dict):
        
        # Load model using the (configured) model file
        self.classifier_model = Full_SqueezeNet_112x112.load_model_from_path(self.path_to_model_folder, 
                                                                             self.model_file_name_no_ext)
        
    # .................................................................................................................
    
    def classify_one_object(self, object_ref, snapshot_database):
        
        # Get bounding times so we can request snapshots for classification
        start_epoch_ms, end_epoch_ms = object_ref.get_bounding_epoch_ms()
        
        # Get snap times to used for grabbing image data to classify the object
        num_snaps_to_classify = self.number_frames_to_classify
        snap_times = snapshot_database.get_n_snapshot_times(start_epoch_ms, end_epoch_ms, num_snaps_to_classify)
        
        # Loop over several snapshots to get a 'best guess' at the classification
        num_snap_times = 0
        prediction_dict = {}
        for each_snap_time in snap_times:
            
            # Try to get a cropped image of the object for classification purposes
            snap_image, snap_frame_idx = snapshot_database.load_snapshot_image(each_snap_time)
            cropped_image = object_ref.crop_image(snap_image, snap_frame_idx, 75, 75)
            if cropped_image is None:
                continue
            
            # Assuming we got a cropped image, ask the classifier for a prediction & accumulat scoring per label
            pred_label, pred_score = self.classifier_model.predict(cropped_image)
            prediction_dict[pred_label] = prediction_dict.get(pred_label, 0.0) + pred_score
            num_snap_times += 1
            
        # Loop over all predictions and take the class label that accumulated the highest score
        highest_score = -1.0
        best_pred_label = "unknown"
        for each_label, each_score in prediction_dict.items():
            if each_score > highest_score:
                best_pred_label = each_label
                highest_score = each_score
        best_score_pct = int(round(100*(highest_score / num_snap_times)))
        
        # This model doesn't generate any subclass or attribute data...
        subclass = ""
        attributes = {}
        
        return best_pred_label, best_score_pct, subclass, attributes

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


