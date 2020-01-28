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

from collections import OrderedDict

from eolib.utils.function_helpers import get_function_arg_dict


# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes

class Controls_Specification:
    
    # .................................................................................................................
    
    def __init__(self):
        
        # Store reference to the parent object, so we can infer which variable names are associated with controls
        #self.obj_ref = object_reference
        
        # Allocate storage for keeping track of control groups & specifications
        self.drawing_control_dict = {}
        self.control_group_dict = OrderedDict()
        self._current_group = None
    
    # .................................................................................................................
    
    def __repr__(self):
        
        # Print out control group names and the list of controls
        repr_strs = ["/// Control Groups ///"]
        for each_group_name, each_group_list in self.control_group_dict.items():
            repr_strs += ["", "-" * 20, each_group_name]
            for each_control_spec in each_group_list:
                variable_name = each_control_spec.get("variable_name", "unknown variable name")
                control_type = each_control_spec.get("control_type", "unknown control type")
                repr_strs += ["  {}: {}".format(variable_name, control_type)]
            
        # Add info about drawing controls, if present
        drawing_controls_exist = (len(self.drawing_control_dict) > 0)
        if drawing_controls_exist:
            repr_strs += ["", "", "/// Drawing Controls ///"]
            for each_variable_name, each_drawing_spec in self.drawing_control_dict.items():
                entity_type = each_drawing_spec.get("entity_type", "unknown entity type")
                drawing_style = each_drawing_spec.get("drawing_style", "unknown drawing style")
                repr_strs += ["{}: {} ({})".format(each_variable_name, entity_type, drawing_style)]
        
        return "\n".join(repr_strs)
    
    # .................................................................................................................
    
    def get_all_variable_naming(self):
        
        '''
        Function which loops over all available control variables (including sliders & drawing vars)
        and splits variable names into save/nosave lists 
        as well as accumulating a set of names which are invisible (i.e. shouldn't appear on the UI)
        
        Inputs:
            None!
            
        Outputs:
            save_draw_vars (List),
            nosave_draw_vars (List),
            save_slider_vars (List), 
            nosave_slider_vars (List), 
            invisible_vars_set (Set)
        '''
        
        # Allocate storage for outputs
        save_draw_vars = []
        nosave_draw_vars = []
        save_slider_vars = []
        nosave_slider_vars = []
        invisible_vars_set = set()
        
        # Loop over all drawing controls and split into appropriate outputs
        for each_drawing_variable, each_drawing_spec in self.drawing_control_dict.items():
            
            # Determine if the drawing variable is savable and/or visible
            is_saveable = each_drawing_spec["save_with_config"]
            is_visible = each_drawing_spec["visible"]
            
            # Add variable name to appropriate lists and invis. set as needed
            (save_draw_vars if is_saveable else nosave_draw_vars).append(each_drawing_variable)
            if not is_visible:
                invisible_vars_set.add(each_drawing_variable)
                
        # Loop over all 'slider' controls and split into appropriate outputs
        for each_group_name, each_control_list in self.control_group_dict.items():
            for each_control_spec in each_control_list:
                
                # Get each variable name for this control group & check if it's saveable
                slider_variable_name = each_control_spec["variable_name"]
                is_saveable = each_control_spec["save_with_config"]
                is_visible = each_control_spec["visible"]
                
                # Add variable name to appropriate lists and invis. set as needed
                (save_slider_vars if is_saveable else nosave_slider_vars).append(slider_variable_name)
                if not is_visible:
                    invisible_vars_set.add(slider_variable_name)
        
        return save_draw_vars, nosave_draw_vars, save_slider_vars, nosave_slider_vars, invisible_vars_set
    
    # .................................................................................................................
    
    def get_drawing_specification(self, variable_name):
        
        '''
        Function which returns a dictionary that specifies how to handle/represent a given drawing variable
        The spec is subject to change over time, but as of early 2020, the following keys would be present:
            'save_with_config': (boolean)
            'out_of_bounds': (boolean)
            'drawing_style': (string)
            'entity_type': (string)
            'min_max_points': (tuple)
            'min_max_entities': (tuple)
            'default_value': (nested lists)
            'variable_name': (string)
            'visible': (boolean)
        '''
        
        # Sanity check
        unrecognized_variable_name = (variable_name not in self.drawing_control_dict)
        if unrecognized_variable_name:
            raise NameError("No drawing specification for variable: {}".format(variable_name))
        
        return self.drawing_control_dict[variable_name]
    
    # .................................................................................................................
    
    def to_json(self):
        
        '''
        Function used to generate a (json-friendly) list of control groups 
        and corresponding controls within each group
        
        The output takes on the following format:
            control_groups_list = [{"group_name": "...", 
                                    "control_list": [{<control_spec>}, {<control_spec>}, {...}]}]
            
        NOTE:
            This function does not return drawing specifications. 
            Use the get_drawing_specification(<variable_name>) function to get a json-friendly drawing spec!
        '''
        
        # Create list of control groups
        control_groups_list = []
        for each_group_name, each_control_list in self.control_group_dict.items():
            json_friendly_control_list = convert_return_types(each_control_list)
            new_group_entry = {"group_name": each_group_name, "control_list": json_friendly_control_list}
            control_groups_list.append(new_group_entry)
        
        return control_groups_list
    
    # .................................................................................................................
    
    def attach_drawing(self, variable_name, *, default_value, 
                       min_max_entities = (0, None), 
                       min_max_points = (3, None), 
                       entity_type = "polygon", 
                       drawing_style = "zone", 
                       out_of_bounds = True,
                       visible = True,
                       save_with_config = True):
        
        ''' 
        Function used to associate a polygon-drawing with a variable.
        Note that this type of control is not grouped like other (.attach) controls!
        '''
        
        input_values = get_function_arg_dict(locals())
        
        # Ensure default values are of the form of a list of lists (of tuples possibly)
        default_key = "default_value"
        safe_default = safeify_drawing_default_values(input_values[default_key])
        input_values.update({default_key: safe_default})
        
        self.drawing_control_dict[variable_name] = input_values
        
        return safe_default
    
    # .................................................................................................................
    
    def new_control_group(self, control_group_name):
        
        ''' Function used to associate all preceeding .attach_<control> calls with a single group '''
        
        # Quick sanity check
        group_name_is_taken = (control_group_name in self.control_group_dict)
        if group_name_is_taken:
            raise NameError("Control group name already exists! ({})".format(control_group_name))
        
        # Make a new group entry and update the curent grouping name
        new_group_entry = {control_group_name: []}
        self.control_group_dict.update(new_group_entry)
        self._current_group = control_group_name
    
        return self
    
    # .................................................................................................................
    
    def attach_toggle(self, variable_name, *, label, default_value, tooltip = "", visible = True, 
                      save_with_config = True):
        
        ''' Function used to associate a toggle control with a variable '''
        
        input_values = get_function_arg_dict(locals())
        self._add_new_control("toggle", **input_values)
        
        return default_value
    
    # .................................................................................................................
    
    def attach_slider(self, variable_name, *, label, default_value, min_value, max_value, 
                      step_size = 1, units = None, return_type = float, zero_referenced = False, 
                      tooltip = "", visible = True, save_with_config = True):
        
        ''' Function used to associate a slider control with a variable '''
        
        input_values = get_function_arg_dict(locals())
        self._add_new_control("slider", **input_values)
        
        return default_value
    
    # .................................................................................................................

    def attach_numentry(self, variable_name, *, label, default_value, min_value, max_value, 
                        step_size = 1, units = None, return_type = float, zero_referenced = False,
                        force_min = True, force_max = True, force_step = True, tooltip = "", 
                        visible = True, save_with_config = True):
        
        ''' Function used to associate a numerical entry (i.e. an unbounded slider) control with a variable '''
        
        input_values = get_function_arg_dict(locals())
        self._add_new_control("numentry", **input_values)
        
        return default_value
    
    # .................................................................................................................
    
    def attach_menu(self, variable_name, *, label, default_value, option_label_value_list,
                    tooltip = "", visible = True, save_with_config = True):
        
        ''' Function used to associate a drop-down style menu control with a variable '''
        
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

    def _add_new_control(self, control_type, **control_spec):
        
        # Quick sanity check
        control_type_in_spec = ("control_type" in control_spec)
        if control_type_in_spec:
            variable_name = control_spec.get("variable_name", "unknown variable name")
            err_strs = ["Error attaching control for variable: {}.".format(variable_name)]
            err_strs += ["Cannot have a control property called 'control_type' as it is reserved!"]
            raise AttributeError(" ".join(err_strs))
        
        # Warning if a group hasn't been set
        current_group = self._current_group
        group_not_set = (current_group is None)
        if group_not_set:
            variable_name = control_spec.get("variable_name", "unknown variable name")
            err_strs = ["Error attaching {} control ({}).".format(control_type, variable_name)]
            err_strs += ["A control group hasn't been defined yet!"]
            err_strs += ["Use .new_control_group() to define one before attaching controls."]
            raise AttributeError(" ".join(err_strs))
            
        # Store the control specification & control type info
        control_info = {**control_spec, "control_type": control_type}
        
        # Add dictionary data to the current control group
        group_name = self._current_group
        self.control_group_dict[group_name].append(control_info)
    
    # .................................................................................................................
    # .................................................................................................................


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
        return_type = each_control_spec_dict[return_type_key]
        
        # Sanity check
        unrecognized_return_type = (return_type not in return_type_lut)
        if unrecognized_return_type:
            variable_name = each_control_spec_dict.get("variable_name", "unknown variable name")
            raise AttributeError("Unrecognized return type: {} ({})".format(return_type, variable_name))
        
        # Convert the python-only return type to a valid json entry
        converted_return_type = return_type_lut[return_type]
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
    
    # Example declartion of controls. Should be placed in the __init__ of configurables!
    cspec = Controls_Specification()
    cspec = cspec
    
    zones_list = cspec.attach_drawing("zones_list", default_value = [])
    
    cspec.new_control_group("Blur Controls")
        
    blur_size = \
    cspec.attach_slider("blur_size", 
                        label = "Bluriness", 
                        default_value = 0,
                        min_value = 0,
                        max_value = 15,
                        return_type = int)
    
    fast_blur = \
    cspec.attach_toggle("fast_blur", 
                        label = "Bluriness", 
                        default_value = False)
    
    
    
    cspec.new_control_group("Thresholding Controls")
    
    threshold = \
    cspec.attach_slider("threshold", 
                        label = "Threshold", 
                        default_value = 50,
                        min_value = 1,
                        max_value = 255,
                        return_type = int,
                        zero_referenced = True)
    
    sum_depth = \
    cspec.attach_slider("sum_depth", 
                        label = "Summation Depth", 
                        default_value = 1,
                        min_value = 0,
                        max_value = 15,
                        return_type = int)
    
    interp = \
    cspec.attach_menu("interp", 
                      label = "Interpolation", 
                      default_value = "Bilinear",
                      option_label_value_list = [("Nearest Neighbour", 0),
                                                 ("Bilinear", 5),
                                                 ("Cubic", 10),
                                                 ("Other", None)])
    
    # Expected to pass the ctrl_manager into the reconfigure() function for a configurable!
    
    # Example of json output:
    example_json = cspec.to_json()
    print(example_json)
    
    
# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap

