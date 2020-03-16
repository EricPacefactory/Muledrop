#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Mar 25 16:17:21 2019

@author: eo
"""


# ---------------------------------------------------------------------------------------------------------------------
#%% Imports



# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

# .....................................................................................................................
        
def get_function_arg_dict(locals_var, remove_self = True, remove_keys = []):
    
    '''
    To use this function, call it at the top of a function and pass locals() as the first argument
    It will return a dictionary whose keys are the function input variable names,
    and values that equal the variable values
    '''
    
    # Copy locals() dictionary and remove 'self' variable (if needed)
    func_args = locals_var.copy()
    if "self" in func_args and remove_self:
        del func_args["self"]
        
    # Delete any other desired keys
    for each_key in remove_keys:
        if each_key in func_args:
            del func_args[each_key]
        
    return func_args

# .....................................................................................................................
    
def get_func_arg_list(function_ref):
    
    '''
    Function which returns a list of the keyword arguments of a function
    '''
    
    try:
        return list(function_ref.__func__.__kwdefaults__.keys())
    except AttributeError:
        return []

# .....................................................................................................................
    
def get_object_properties_from_list(object_ref, key_list, error_if_missing_key = True, fill_missing = None):
    
    '''
    Function which takes an object and list of object properties (key_list) 
    and returns the current value of each property as a dictionary.
    
    Example: Assume we have an object 'some_obj', with properties
      some_obj.x = 5
      some_obj.y = -3
      some_obj.width = 223.7
      some_obj.name = None
    
    Calling
        get_object_properties_from_list(some_obj, ["x", "name"])
        = {"x": 5, "name": None}
        
    If a key is provided which isn't a property of the object (e.g. some_obj.z), 
    an AttributeError will be raised by default. 
    In the case that the error is disable (error_if_missing_key = False), the value of the missing property
    will be set to the value of fill_missing (None by default)    
    '''
    
    # Allocate space for output
    property_dict = {}
    
    # Pull each object property out of the object and store in a dictionary
    for each_key in key_list:
        
        try:
            each_value = getattr(object_ref, each_key, fill_missing)
        except AttributeError:
            if error_if_missing_key:
                raise AttributeError
        
        # Store key/value pairs in output
        property_dict[each_key] = each_value
        
    return property_dict

# .....................................................................................................................
    
def set_object_properties_from_dict(object_ref, property_dict, 
                                    only_set_existing_properties = True,
                                    ignore_self_entries = True, 
                                    ignore_none_entries = False,
                                    provide_feedback = True):
    
    '''
    Function which takes an object and sets/updates object properties based on a provided dictionary
    
    Inputs:
        object_ref -> Object. The object instance to be updated
        
        property_dict -> Dictionary. Keys represent object properties to set, 
                         values represent the new property value (e.g. obj.key = value)
        
        only_set_existing_properties -> Bool. If true, will not set the object properties 
                                              unless the property has already been defined/initialized
                                              
        ignore_self_entries -> Bool. If true, ignore {"self": ...} entries from property_dict
        
        ignore_none_entries -> Bool. If true, ignore {...: None} entries from property_dict
        
        provide_feedback -> Bool. If true, print messages whenever ignoring/skipping entries from property_dict
    
    Example: Assume we have an object 'some_obj', with properties
      some_obj.x = 5
      some_obj.y = -3
      some_obj.width = 223.7
      some_obj.name = None
      
     After calling
         set_object_properties_from_dict(some_obj, {"x": 22, "name": "Batman"})
         
     We have:
        some_obj.x == 22
        some_obj.y == -3
        some_obj.width == 223.7
        some_obj.name == "Batman"
    '''
    
    # Get the class name in case we're providing feedback
    class_name = object_ref.__class__.__name__
    
    updated_properties = []
    for each_key, each_value in property_dict.items():
        
        # Skip self entries, if needed
        if ignore_self_entries and each_key == "self":
            print("", 
                  "Ignoring self entry (setting {} properties)".format(class_name), 
                  sep = "\n")
            continue
        
        # Skip None entries, if needed
        if ignore_none_entries and each_value == None:
            print("", 
                  "Ignoring {}:None entry (setting {} properties)".format(each_key, class_name),
                  sep = "\n")
            continue
        
        # Skip properties that aren't already part of the object, if needed
        if only_set_existing_properties:
            try:
                getattr(object_ref, each_key)
            except AttributeError:
                print("", 
                      "Skipping {}, unrecognized property! (setting {}) properties".format(each_key, class_name),
                      sep = "\n")
                continue
        
        # If we get this far, we should be good to update the object!
        setattr(object_ref, each_key, each_value)
        updated_properties.append(each_key)
        
    return updated_properties

# .....................................................................................................................
    
def remove_target_value_from_dict(input_dict, target_value = None):
    
    '''
    Removes entries from a dictionary based on a value match (independent of keys)
    By default, removes all entries that have None values.
    '''
    
    return {each_key: each_value for each_key, each_value in input_dict.items() if each_value != target_value}

# .....................................................................................................................
    
def dynamic_import_from_module(dot_path, item_name, remove_dotpy_ext = True, replace_forward_slashes = True):
    
    '''
    Function for programmatically performing targeted import statements. 
    Mimics the (in python script) following behaviour:
        
        from dot_path import item_name
    
    Inputs:
        dot_path -> String. Can be a python-like import statement, e.g. "some.module.path"
                    Can also be a file path, e.g. "some/module/path.py"
        
        item_name -> String. The function/class to import (and also the return value of the function call!)
        
        remove_dotpy_ext -> Bool. If true, removes any .py extensions from the provided dot_path input
        
        replace_forward_slashes -> Bool. If true, replaces "//" or "/" with "." in dot_path input        
    '''
    
    # Fairly obscure import, so keep it local to this function. Not likely to be called repeatedly
    from importlib import import_module
    
    # Replace forward slashes, if needed
    if replace_forward_slashes:
        dot_path = dot_path.replace("//", ".").replace("/", ".")
        dot_path = dot_path if dot_path[0] != "." else dot_path[1:]
        dot_path = dot_path if dot_path[-1] != "." else dot_path[:-1]
    
    # Remove .py extensions from the provided dot path if needed
    if remove_dotpy_ext:
        has_pyext = (dot_path[-3:].lower() == ".py")
        dot_path = dot_path[:-3] if has_pyext else dot_path
    
    # The following code is equivalent to: 
    # from dot_path import item_name as import_item
    try:
        lib_import = import_module(dot_path)
    except ModuleNotFoundError as err:
        print("", "Error:", "  Possibly bad dynamic import path: {}".format(dot_path), "", sep = "\n" )
        raise err
        
    try:
        import_item = getattr(lib_import, item_name)
    except AttributeError:        
        raise NameError("Bad import name: {} (@ {})".format(item_name, dot_path))

    return import_item

# .....................................................................................................................

# .....................................................................................................................
    
# .....................................................................................................................
    

# ---------------------------------------------------------------------------------------------------------------------
#%% Demo
    
if __name__ == "__main__":
    
    pass

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap



