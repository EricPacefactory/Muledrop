#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Apr 27 11:57:02 2018

@author: eo
"""


# ---------------------------------------------------------------------------------------------------------------------
#%% Imports

import os


# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes


# ---------------------------------------------------------------------------------------------------------------------
#%% String functions

# .....................................................................................................................

def blank_str_to_none(input_string, replace_blank_with = None):
    
    ''' Helper function which replaces "" values with None (replacement can be altered with arguments) '''
    
    input_is_blank = (input_string == "")
    
    return replace_blank_with if input_is_blank else input_string

# .....................................................................................................................

def none_to_blank_str(input_value, replace_none_with = ""):
    
    ''' Helper function which replaces 'None' values with empty strings (replacement can be altered with arguments) '''
    
    input_is_none = (input_value is None)
    
    return replace_none_with if input_is_none else input_value

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% List functions

# .....................................................................................................................

def reorder_list(entry_list, ordered_hints_list, add_nonmatch_to_end = True):
    
    '''
    Function which allows for re-ordering of a list of string based on a list of 'hints'
    Non-matched entries can be added to the beginning or end of the ordered component of the list
    Note that ordering by hints uses a 'starts with' check. So hints are intended to be the first few
    (unique) characters of the desired entry order
    
    Inputs:
        entry_list --> (List) List of entries to be re-ordered. Assumed to be a list of strings
        
        ordered_hints_list --> (List) List of 'hints' used to re-order the list of entries. Ordering works
                             using a 'starts with' check. So the first few (unique) characters of each
                             target entry should be provided as hints
        
        add_nonmatch_to_end --> (Boolean) If true, entries that are not matched to hints will be added
                                to the end of the output list. Otherwise they will be at the start
    
    Outputs:
        reordered_list
    
    Example:
        reorder_list(["Japan", "Moncton", "Montreal", "Australia", "Ottawa", "Brazil", "Toronto", "Vancouver"],
                     ["tor", "van", "monc", "ot", "mont"],
                     True)
        => ["Toronto", "Vancouver", "Moncton", "Ottawa", "Montreal", "Japan", "Australia", "Brazil"]
    '''
    
    # Try to enfore an ordering of the input list entries
    reordered_list = []
    for each_hint in ordered_hints_list:
        lowered_hint = str(each_hint).lower()
        for each_entry in entry_list:
            lowered_entry = str(each_entry).lower()
            matches_hint = (lowered_entry.startswith(lowered_hint))
            if matches_hint:
                reordered_list.append(each_entry)
                break
    
    # Add any entries that didn't match the target ordering to the listing
    nonmatch_list = []
    for each_entry in entry_list:
        if each_entry not in reordered_list:
            nonmatch_list.append(each_entry)
    
    # Figure out ordering of the final output, which contains matches/unmatch entries
    output_list = (reordered_list + nonmatch_list) if add_nonmatch_to_end else (nonmatch_list + reordered_list)
    
    return output_list

# .....................................................................................................................

def split_to_sublists(input_list, maximum_sublist_size = 10):
    
    '''
    Helper function which simply breaks the input list into smaller chunks
    For example:
        input_list = [1,2,3,4,5,6,7,8,9,10,11,12,13]
        split_to_sublists(input_list, 3) -> [[1,2,3], [4,5,6], [7,8,9], [10,11,12], [13]]
    
    Note: This function returns a generator, but each generated item will be a list (given a list input)
    '''
    
    num_items = len(input_list)
    for idx1 in range(0, num_items, maximum_sublist_size):
        idx2 = (idx1 + maximum_sublist_size)
        yield input_list[idx1:idx2]
    
    return

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Environment functions

# .....................................................................................................................

def in_spyder_ide():
    
    ''' Function used to check if python is running inside of the spyder ide '''
    
    return any("spyder" in each_key.lower() for each_key in os.environ)

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Demo

if __name__ == "__main__":
    pass


# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap


