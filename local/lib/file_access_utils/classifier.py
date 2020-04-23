#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Oct 14 11:39:51 2019

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

from local.lib.file_access_utils.after_database import build_after_database_configs_folder_path
from local.lib.file_access_utils.reporting import build_after_database_report_path
from local.lib.file_access_utils.resources import build_base_resources_path
from local.lib.file_access_utils.read_write import save_config_json, load_config_json, save_jgz, load_jgz

# ---------------------------------------------------------------------------------------------------------------------
#%% General Pathing functions

# .....................................................................................................................

def build_classifier_config_path(cameras_folder_path, camera_select, user_select, *path_joins):
    return build_after_database_configs_folder_path(cameras_folder_path, camera_select, user_select, "classifier.json")

# .....................................................................................................................

def build_classifier_adb_metadata_report_path(cameras_folder_path, camera_select, user_select, *path_joins):
    return build_after_database_report_path(cameras_folder_path, camera_select, user_select, "classifier")

# .....................................................................................................................

def build_classifier_resources_path(cameras_folder_path, camera_select, *path_joins):
    return build_base_resources_path(cameras_folder_path, camera_select, "classifier", *path_joins)
    
# .....................................................................................................................

def build_model_resources_path(cameras_folder_path, camera_select, *path_joins):
    classifier_folder_path = build_classifier_resources_path(cameras_folder_path, camera_select)
    return os.path.join(classifier_folder_path, "models", *path_joins)

# .....................................................................................................................

def build_reserved_labels_lut_path(cameras_folder_path, camera_select):
    return build_classifier_resources_path(cameras_folder_path, camera_select, "reserved_labels_lut.json")

# .....................................................................................................................

def build_topclass_labels_lut_path(cameras_folder_path, camera_select):
    return build_classifier_resources_path(cameras_folder_path, camera_select, "topclass_label_lut.json")

# .....................................................................................................................

def build_subclass_labels_lut_path(cameras_folder_path, camera_select):
    return build_classifier_resources_path(cameras_folder_path, camera_select, "subclass_label_lut.json")

# .....................................................................................................................

def build_attributes_dict_path(cameras_folder_path, camera_select):
    return build_classifier_resources_path(cameras_folder_path, camera_select, "attributes_dict.json")

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Reserved labels

# .....................................................................................................................

def reserved_unclassified_label():
    
    '''
    Helper function used to specify the label & default color for objects that are not yet classified 
    Returns:
        class_label (string), default_color_bgr (tuple)
    '''
    
    label = "unclassified"
    default_color_bgr = (0, 255, 255)
    
    return label, default_color_bgr

# .....................................................................................................................

def reserved_notrain_label():
    
    '''
    Helper function used to specify the label & default color for objects that should not be
    included in datasets used for training. Most likely because they represent ambiguous detections.
    Returns:
        class_label (string), default_color_bgr (tuple)
    '''
    
    label = "no train"
    default_color_bgr = (0, 0, 0)
    
    return label, default_color_bgr

# .....................................................................................................................

def reserved_background_label():
    
    '''
    Helper function used to specify the label & default color for objects that are actually
    representing the background. Mostly likely applied to errors common when using background-subtraction.
    Returns:
        class_label (string), default_color_bgr (tuple)
    '''
    
    label = "background"
    default_color_bgr = (255, 255, 255)
    
    return label, default_color_bgr

# .....................................................................................................................

def reserved_incomplete_label():
    
    '''
    Helper function used to specify the label & default color for objects that were bad detections
    or otherwise incomplete for one reason or another. Most likely applied to errors common to frame-to-frame detection
    Returns:
        class_label (string), default_color_bgr (tuple)
    '''
    
    label = "incomplete"
    default_color_bgr = (0, 100, 255)
    
    return label, default_color_bgr

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% File naming functions

# .....................................................................................................................

def create_classifier_report_file_name(object_full_id):
    return "class-{}.json.gz".format(object_full_id)

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Define config helpers

# .....................................................................................................................

def path_to_configuration_file(configurable_ref):
    
    # Get major pathing info from the configurable
    cameras_folder_path = configurable_ref.cameras_folder_path
    camera_select = configurable_ref.camera_select
    user_select = configurable_ref.user_select
    
    return build_classifier_config_path(cameras_folder_path, camera_select, user_select)

# .....................................................................................................................

def load_matching_config(configurable_ref):
    
    ''' 
    Function which takes in a configurable and tries to load an existing config file which matches the configurable.
    Intended for use in configuration utilities, where a specific configurable is hard-coded to load,
    while this function provides existing configuration data (if present), instead of always loading defaults.
    '''
    
    # Build pathing to existing configuration file
    load_path = path_to_configuration_file(configurable_ref)
    
    # Load existing config
    config_data = load_config_json(load_path)
    file_access_dict = config_data["access_info"]
    setup_data_dict = config_data["setup_data"]
    
    # Get target script/class from the configurable, to see if the saved config matches
    target_script_name = configurable_ref.script_name
    target_class_name = configurable_ref.class_name
    
    # Check if file access matches
    script_match = (target_script_name == file_access_dict["script_name"])
    class_match = (target_class_name == file_access_dict["class_name"])
    if script_match and class_match:
        return setup_data_dict
    
    # If file acces doesn't match, return an empty setup dictionary
    no_match_setup_data_dict = {}
    return no_match_setup_data_dict

# .....................................................................................................................

def save_classifier_config(configurable_ref, file_dunder = __file__):
    
    # Figure out the name of this configuration script
    config_utility_script_name, _ = os.path.splitext(os.path.basename(file_dunder))
    
    # Get file access info & current configuration data for saving
    file_access_dict, setup_data_dict = configurable_ref.get_data_to_save()
    file_access_dict.update({"configuration_utility": config_utility_script_name})
    save_data = {"access_info": file_access_dict, "setup_data": setup_data_dict}
    
    # Build pathing to existing configuration file
    save_path = path_to_configuration_file(configurable_ref)    
    save_config_json(save_path, save_data)

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Data access functions

# .....................................................................................................................

def save_classifier_report_data(cameras_folder_path, camera_select, user_select, report_data_dict):
    
    # Get object id from the report data
    object_full_id = report_data_dict["full_id"]
    
    # Build pathing to save
    save_file_name = create_classifier_report_file_name(object_full_id)
    save_folder_path = build_classifier_adb_metadata_report_path(cameras_folder_path, camera_select, user_select)
    save_file_path = os.path.join(save_folder_path, save_file_name)
    
    # Save!
    save_jgz(save_file_path, report_data_dict, create_missing_folder_path = True)

# .....................................................................................................................
    
def new_classifier_report_entry(object_full_id, 
                                topclass_dict = None,
                                subclass_dict = None,
                                attributes_dict = None):
    
    ''' 
    Helper function for creating consistently formatted classification entries 
    Inputs:
        object_full_id -> Integer. Object ID, used to associate classification data with some object metadata
        
        topclass_dict -> Dict or None. Dictionary containing keys representing class labels and corresponding
                         values representing the 'score' or probability that the object was the given class.
                         If 'None' is provided, an empty dictionary will be substituted
                         
        subclass_dict -> Dict or None. Same as the topclass_dict, but intended to provide a more granular
                         assignment of classification data, given the topclass data. For example, the topclass
                         may be 'vehicle', in which case subclass may specify the kind of vehicle 
                         (e.g. forklift vs golf cart vs. tugger vs. autonomous etc.)
                         
        attributes_dict -> Dict or None. A final dictionary (currently here only as a placeholder?!) used to
                           provide additional data about possible attributes of an object. For example, if the
                           object is identified as a pedestrian, the attributes_dict can be used to indicate
                           whether they were wearing a hard-hat, safety-vest, eye protection etc.
                           
    Outputs:
        classification entry (dict)
        (contains keys: 'full_id', 'topclass_label', 'subclass_label', 
                        'topclass_dict', 'subclass_dict', 'attributes_dict')
        
    Note: The '..._label' entries are automatically derived from the inputs
    '''
    
    # Avoid funny mutability stuff
    topclass_dict = {} if topclass_dict is None else topclass_dict
    subclass_dict = {} if subclass_dict is None else subclass_dict
    attributes_dict = {} if attributes_dict is None else attributes_dict
    
    # Figure out the 'best estimate' for the object topclass label
    default_label, _ = reserved_unclassified_label()
    topclass_label, _ = get_highest_score_label(topclass_dict, default_label)
            
    # Figure out the 'best estimate' for the subclass label, defaulting to whatever the topclass is...
    subclass_label, _ = get_highest_score_label(subclass_dict, "")
    
    return {"full_id": object_full_id,
            "topclass_label": topclass_label,
            "subclass_label": subclass_label,
            "topclass_dict": topclass_dict,
            "subclass_dict": subclass_dict,
            "attributes_dict": attributes_dict}

# .....................................................................................................................

def get_highest_score_label(label_score_dict, default_label = None):
    
    ''' 
    Helper function for determining the 'best' label given a label:score dictionary 
    
    Inputs:
        label_score_dict --> (dictionary) Dictionary to be checked for 'highest scoring' label. Should
                             have keys representing classification labels and values corresponding to scores.
        
        default_label --> (string) Label to use by default (i.e. if no label is determined from the input dictionary)
        
    Outputs:
        best_label (string), best_score
    '''
    
    # Deal with missing default label
    if default_label is None:
        default_label, _ = reserved_unclassified_label()
    
    # Find the label with the highest score, assuming dictionary of {label:score} entries
    best_label = default_label
    best_score = -1
    for each_label, each_score in label_score_dict.items():
        if each_score > best_score:
            best_score = each_score
            best_label = each_label
            
    return best_label, best_score

# .....................................................................................................................
    
def load_classifier_config(cameras_folder_path, camera_select, user_select):
    
    ''' 
    Function which loads configuration files for a classifier
    '''
    
    # Get path to the config file
    config_file_path = build_classifier_config_path(cameras_folder_path, camera_select, user_select)
    
    # Load json data and split into file access info & setup configuration data
    config_dict = load_config_json(config_file_path)
    access_info_dict = config_dict["access_info"]
    setup_data_dict = config_dict["setup_data"]
    
    return config_file_path, access_info_dict, setup_data_dict

# .....................................................................................................................

def load_reserved_labels_lut(cameras_folder_path, camera_select):
    
    ''' Function which loads a dictionary of label:color pairs corresponding to the reserved labels '''
    
    # Get built-in defaults
    unclassified_label, unclassified_color = reserved_unclassified_label()
    notrain_label, notrain_color = reserved_notrain_label()
    background_label, background_color = reserved_background_label()
    incomplete_label, incomplete_color = reserved_incomplete_label()
    
    # Build up default output
    reserved_labels_dict = {}
    reserved_labels_dict[unclassified_label] = unclassified_color
    reserved_labels_dict[notrain_label] = notrain_color
    reserved_labels_dict[background_label] = background_color
    reserved_labels_dict[incomplete_label] = incomplete_color
    
    # Load stored reserved file, in case the user has modified default values
    reserved_labels_file_path = build_reserved_labels_lut_path(cameras_folder_path, camera_select)
    loaded_reserved_labels_dict = load_config_json(reserved_labels_file_path)
    
    # Update the built-in defaults with the loaded data
    reserved_labels_dict.update(**loaded_reserved_labels_dict)
    
    return reserved_labels_dict

# .....................................................................................................................

def load_topclass_labels_lut(cameras_folder_path, camera_select):
    
    ''' Function which loads a dictionary of label:color pairs corresponding to topclass labels '''
    
    # Initialize default output
    topclass_labels_dict = {}
    
    # Load stored labels file
    topclass_labels_file_path = build_topclass_labels_lut_path(cameras_folder_path, camera_select)
    loaded_topclass_labels_dict = load_config_json(topclass_labels_file_path)
    
    # Update the built-in defaults with the loaded data
    topclass_labels_dict.update(**loaded_topclass_labels_dict)
    
    return topclass_labels_dict 

# .....................................................................................................................

def load_subclass_labels_lut(cameras_folder_path, camera_select):
    
    ''' 
    Function which loads a dictionary of lists,
    structured as:
      {
        topclass_label_1: [subclass_label_1, subclass_label_2, ...],
        topclass_label_2: [...]
      }
    for each sublcass (nested by corresponding topclass) 
    '''
    
    # Initialize default output
    subclass_labels_dict = {}
    
    # Load stored labels file
    subclass_labels_file_path = build_subclass_labels_lut_path(cameras_folder_path, camera_select)
    loaded_subclass_labels_dict = load_config_json(subclass_labels_file_path)
    
    # Update the built-in defaults with the loaded data
    subclass_labels_dict.update(**loaded_subclass_labels_dict)
    
    return subclass_labels_dict

# .....................................................................................................................

def load_attributes_dict(cameras_folder_path, camera_select):
    
    '''
    Function which loads a dictionary of dictionaries of lists
    structures as:
        {
          topclass_label_1: {subclass_label_1: [attribute_1, attribute_2, etc.],
                             subclass_label_2: [...]},
          topclass_label_2: ...
        }
    '''
    
    raise NotImplementedError("Attributes are not yet implemented!")

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap