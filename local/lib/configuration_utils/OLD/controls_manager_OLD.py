#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu May 23 17:49:30 2019

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


from eolib.utils.function_helpers import get_function_arg_dict


# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes

class Control_Manager:
    
    # .................................................................................................................
    
    def __init__(self):        
        self.group_list = []
        
    # .................................................................................................................
        
    def __repr__(self):
        
        repr_strs = ["/// Controls Manager ///"]        
        for each_group in self.group_list:
            label_var_zip = zip(each_group.get_value_list("label"), each_group.get_value_list("variable_name"))
            repr_strs += ["", "{}:".format(each_group.group_name)]
            repr_strs += ["  {} ({})".format(*each_zip) for each_zip in label_var_zip]
        
        return "\n".join(repr_strs)
        
    # .................................................................................................................
    
    def new_control_group(self, group_name):
        
        # Create new entry in the group 
        new_group_ref = Control_Group(group_name)
        self.group_list.append(new_group_ref)
        
        return new_group_ref
    
    # .................................................................................................................
    
    def get_default_config(self):
        
        variable_name_list = []
        default_value_list = []
        for each_group in self.group_list:            
            variable_name_list += each_group.get_value_list("variable_name")
            default_value_list += each_group.get_value_list("default_value")
            
        return {each_var: each_val for each_var, each_val in zip(variable_name_list, default_value_list)}
    
    # .................................................................................................................
    
    def reset_to_defaults(self, obj_ref):
        
        # Get the default configuration from the control group info
        default_config = self.get_default_config()
            
        # Set all of the given variable names in the object reference to the given default values
        for each_variable_name, each_default_value in default_config.items():
            setattr(obj_ref, each_variable_name, each_default_value)
    
    # .................................................................................................................
    
    def get_full_variable_name_list(self):
        
        # Ask each control group for a list of variable names
        variable_name_list = []
        for each_group in self.group_list:            
            variable_name_list += each_group.get_value_list("variable_name")
                    
        return variable_name_list
    
    # .................................................................................................................
    
    def get_saveable_list(self):
        
        save_list = []
        for each_group in self.group_list:
            
            # Get a (zipped) set of variable names and do-not-save settings
            name_list = each_group.get_value_list("variable_name")
            saveable = each_group.get_value_list("save_with_config")
            name_save_ziplist = zip(name_list, saveable)
            
            # Keep only the saveable variable names
            group_save_list = [each_name for each_name, is_saveable in name_save_ziplist if is_saveable]
            
            # Add filtered name list to the overall save list
            save_list += group_save_list
        
        return save_list
    
    # .................................................................................................................
    
    def update_object(self, object_reference, variable_updates):   
        
        # Get an updated list of all known variables, so we can make sure we're only updating things we know about!
        variable_name_list = self.get_full_variable_name_list()
        
        # Update every (known) variable
        for each_key, each_value in variable_updates.items():
            if each_key not in variable_name_list:
                print("", 
                      "{} ({})".format(object_reference.component_name.capitalize(), object_reference.script_name),
                      "  Skipping unrecognized variable name: {}".format(each_key), sep="\n")
                continue
            setattr(object_reference, each_key, each_value)
            
    # .................................................................................................................
    
    def to_json(self):        
        return [each_ctrl_group.to_json() for each_ctrl_group in self.group_list]
    
    # .................................................................................................................
    # .................................................................................................................


# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////


class Control_Group:
    
    # .................................................................................................................
    
    def __init__(self, group_name):
        
        self.group_name = group_name
        self.control_list = []
        
    # .................................................................................................................
    
    def get_value_list(self, key_name, missing_value = None):
        
        value_list = []
        for each_control in self.control_list:
            read_value = each_control.get(key_name, missing_value)
            value_list.append(read_value)
        
        return value_list
    
    # .................................................................................................................
    
    def attach_toggle(self, variable_name, *, label, default_value, tooltip = "", visible = True, 
                      save_with_config = True):
        
        input_values = get_function_arg_dict(locals())
        self._add_new_control("toggle", **input_values)
        
        return default_value
    
    # .................................................................................................................
    
    def attach_slider(self, variable_name, *, label, default_value, min_value, max_value, 
                      step_size = 1, units = None, return_type = float, zero_referenced = False, 
                      tooltip = "", visible = True, save_with_config = True):
        
        input_values = get_function_arg_dict(locals())
        self._add_new_control("slider", **input_values)
        
        return default_value

    # .................................................................................................................

    def attach_numentry(self, variable_name, *, label, default_value, min_value, max_value, 
                        step_size = 1, units = None, return_type = float, zero_referenced = False,
                        force_min = True, force_max = True, force_step = True, tooltip = "", 
                        visible = True, save_with_config = True):
        
        input_values = get_function_arg_dict(locals())
        self._add_new_control("numentry", **input_values)
        
        return default_value
    
    # .................................................................................................................
    
    def attach_menu(self, variable_name, *, label, default_value, option_label_value_list,
                    tooltip = "", visible = True, save_with_config = True):
        
        input_values = get_function_arg_dict(locals())
        
        # Split the labels and values so we can pick the default properly
        label_list, value_list = list(zip(*option_label_value_list))
        
        # Use option lookup to set proper default value
        default_label_idx = label_list.index(default_value)
        real_default = value_list[default_label_idx]
        input_values["default_value"] = real_default
        
        self._add_new_control("menu", **input_values)
        
        return real_default
        
    # .................................................................................................................
    
    def attach_button(self, variable_name, *, label, default_value, return_type = bool, tooltip = "", 
                      visible = True, save_with_config = False):
        
        input_values = get_function_arg_dict(locals())
        self._add_new_control("button", **input_values)
        
        return default_value
    
    # .................................................................................................................

    def _add_new_control(self, control_type, **kwargs):
        
        # Build dictionary to store all the control info
        control_info = {each_key: each_value for each_key, each_value in kwargs.items()}
        control_info["control_type"] = control_type
        
        # Add dictionary data to the control list
        self.control_list.append(control_info)
    
    # .................................................................................................................
    
    def to_json(self):
        
        # First get the group name, which can be used as a title for the set of controls
        save_group_name = self.group_name
        
        ret_type_lut = {bool: "boolean",
                        int: "integer",
                        float: "float",
                        str: "string",
                        list: "list",
                        tuple: "tuple",
                        None: None}
        
        # Next get the control listing
        control_list = self.control_list
        
        # Clean up control list entries that have python-specific data types (namely return-types & numpy arrays)
        save_control_list = []
        for each_control_dict in control_list:
            
            save_entry_dict = each_control_dict.copy()
            control_return_type = save_entry_dict.get("return_type")
            if control_return_type:
                
                safe_return_type = ret_type_lut.get(control_return_type)
                save_entry_dict.update({"return_type": safe_return_type})
                
                pass
            
            save_control_list.append(save_entry_dict)
        
        return {"group_name": save_group_name, "control_list": save_control_list}
    
    # .................................................................................................................
    # .................................................................................................................
    
# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
    
# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

# .....................................................................................................................

def convert_return_types(control_list):
    
    ''' Function which replaces python-only return types (int, float, bool, etc.) to json-friendly values '''
        
    # Create a handy lookup for converting python types
    return_type_lut = {bool: "boolean",
                       int: "integer",
                       float: "float",
                       str: "string",
                       list: "list",
                       tuple: "tuple",
                       None: None}
    
    # For convenience
    return_type_key = "return_type"
    
    # Loop through every control specification and convert the return type to a json-friendly value (if present)
    converted_control_list = []
    for each_control_spec_dict in control_list:
        
        # Skip entries that have no return type
        has_no_return_type = (return_type_key not in each_control_spec_dict)
        if has_no_return_type:
            new_control_group_dict = each_control_spec_dict.copy()
            converted_control_list.append(new_control_group_dict)
            continue
        
        # Get the current return type, which is only valid within python
        return_type = each_control_spec_dict.get(return_type_key)
        
        # Sanity check
        unrecognized_return_type = (return_type not in return_type_lut)
        if unrecognized_return_type:
            variable_name = each_control_spec_dict.get("variable_name", "unknown variable name")
            raise AttributeError("Unrecognized return type: {} ({})".format(return_type, variable_name))
        
        # Convert the python-only return type to a valid json entry
        converted_return_type = return_type_lut.get(return_type)
        new_control_group_dict = each_control_spec_dict.copy()
        new_control_group_dict.update({return_type_key: converted_return_type})
        converted_control_list.append(new_control_group_dict)
    
    return converted_control_list

# .....................................................................................................................

def safeify_drawing_default_values(default_entity_value):
    
    ''' 
    Function which converts bad/error-prone drawing default values to safe values
    Safe values should have the form of a 'list-of-lists-of-tuples'
    
    For example:
    The simplest default (no entity) is [[]]
    For a single entity, the default should be [[(x1, y1), (x2, y2), ...]]
    In general: [[(xa1, ya1), (xa2, ya2), (xa3, ya3)], [(xb1, yb1), (xb2, yb2)], [...]]
    '''
    
    # If the default is one of the empty entires, return the 'safe' empty format
    default_is_none = (default_entity_value is None)
    default_is_empty_wrong = (default_entity_value == [])
    default_is_empty_right = (default_entity_value == [[]])
    if default_is_none or default_is_empty_wrong or default_is_empty_right:
        return [[]]
    
    # If we get here, the default probably contains meaningful data. So loop over the entries to check validity
    needs_list_wrap = False
    first_entity = default_entity_value[0]
    try:
            
        # Check that the entity type is valid
        first_entity_point_type = type(first_entity[0])
        needs_list_wrap = (first_entity_point_type not in (list, tuple))
        
    except Exception:
        err_msgs = ["Error interpretting default entity value: {}".format(default_entity_value)]
        err_msgs += ["Must be in the format [[(xa1, ya1), (xa2, ya2), ...], [(xb1, yb1), (xb2, yb2), ...]]"]
        raise TypeError("\n".join(err_msgs))
    
    # Wrap default value in another list if needed
    if needs_list_wrap:
        return [default_entity_value]
    
    return default_entity_value

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Demo

if __name__ == "__main__":
    
    
    # EXAMPLE DECLARATION OF CONTROLS. SHOULD BE PLACED IN CONFIGURABLE __INIT__ FUNCTIONS!
    ctrls_manager = Control_Manager()
    
    
    blur_group = ctrls_manager.new_control_group("Blur Controls")
    
    blur_size = blur_group.attach_slider("blur_size", 
                                         label = "Bluriness", 
                                         default_value = 0,
                                         min_value = 0,
                                         max_value = 15,
                                         return_type = int)
    
    fast_blur = blur_group.attach_toggle("fast_blur", 
                                         label = "Bluriness", 
                                         default_value = False)
    
    
    
    thresh_group = ctrls_manager.new_control_group("Thresholding Controls")
    
    threshold = thresh_group.attach_slider("threshold", 
                                           label = "Threshold", 
                                           default_value = 50,
                                           min_value = 1,
                                           max_value = 255,
                                           return_type = int,
                                           zero_referenced = True)
    
    sum_depth = thresh_group.attach_slider("sum_depth", 
                                           label = "Summation Depth", 
                                           default_value = 1,
                                           min_value = 0,
                                           max_value = 15,
                                           return_type = int)
    
    interp = thresh_group.attach_menu("interp", 
                                      label = "Interpolation", 
                                      default_value = "Bilinear",
                                      option_label_value_list = [("Nearest Neighbour", 0),
                                                                 ("Bilinear", 5),
                                                                 ("Cubic", 10),
                                                                 ("Other", None)])
    
    # Expected to pass the ctrl_manager into the reconfigure() function for a configurable!
    
    # Example of json output:
    example_json = ctrls_manager.to_json()
    print(example_json)
    
    
# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap


