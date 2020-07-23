#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Apr 27 11:46:14 2018

@author: eo
"""

import os


# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes


# ---------------------------------------------------------------------------------------------------------------------
#%% Define pathing functions

# .....................................................................................................................

def get_file_pathing_info(file_path):
    
    '''
    Function which breaks down file naming/pathing
    
    Inputs:
        file_path -> (String) Path to target file
    
    Outputs:
        directory_path, file_name_no_extension, file_extension
    '''
    
    directory_path = os.path.dirname(file_path)    
    file_name = os.path.basename(file_path)
    file_name_no_ext, file_ext = os.path.splitext(file_name)
    
    return directory_path, file_name_no_ext, file_ext

# .....................................................................................................................

def replace_user_home_pathing(input_path):
    
    ''' 
    Function which 'compresses' pathing, by replacing the user home path with a ~ symbol 
    The full path can be recovered using os.path.expanduser(...)
    '''
    
    # Get the user home pathing to use as a target for replacement
    user_home_path = os.path.expanduser("~")
    return input_path.replace(user_home_path, "~")

# .....................................................................................................................

def create_folder_structure_from_dictionary(base_path, dictionary, make_folders = True):
    
    '''
    Recursive function for creating folder paths from a dictionary 
    
    Inputs:
        base_path --> String. Folder path used as the 'root' of the folder structure created by this function
        
        dictionary --> Dictionary. Stores folder structure to be created. See example below
        
        make_folders --> Boolean. If true, any folders missing fom the dictionary structure will be created
        
    Outputs:
        path_list --> List. A list of all paths specified/created from the provided dictionary
    '''
    
    # If a set is given, interpret it as a dictionary, with each key having an empty dictionary
    if type(dictionary) is set:
        dictionary = {each_set_item: {} for each_set_item in dictionary}
    
    # If the dictionary is empty/not a dictionary, then we're done
    if not dictionary:
        return []
    
    # Allocate space for outputting generated paths
    path_list = []
    
    # Recursively build paths by diving through dictionary entries
    for each_key, each_value in dictionary.items():
        
        # Add the next dictionary key to the existing path
        create_path = os.path.join(base_path, each_key)
        path_list.append(create_path)
        
        new_path_list = create_folder_structure_from_dictionary(create_path, each_value, make_folders = False)
        path_list += new_path_list
        
    # Create the folders, if needed
    if make_folders:
        for each_path in path_list:
            os.makedirs(each_path, exist_ok = True)
        
    return path_list

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Folder creation

# .....................................................................................................................

def create_missing_folder_path(folder_path):
    
    ''' Helper function which creates missing folder paths. Nothing happens if the folder path already exists '''
    
    os.makedirs(folder_path, exist_ok = True)

# .....................................................................................................................

def create_missing_folders_from_file(file_path):
    
    ''' Helper function which creates the folder pathing needed for a given file path '''
    
    folder_path = os.path.dirname(file_path)
    os.makedirs(folder_path, exist_ok = True)
    
    return folder_path

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Listing helpers

# .....................................................................................................................

def get_folder_list(search_folder_path, 
                    show_hidden_folders = False,
                    create_missing_folder = False, 
                    return_full_path = False,
                    sort_list = True):
    
    '''
    Returns a list of all folders in the specified search folder
    '''
    
    # Make sure the search folder exists before trying to list it's contents!
    if not os.path.exists(search_folder_path):
        if create_missing_folder:
            os.makedirs(search_folder_path)
        return []
    
    # Take out only the files from the list of items in the search folder
    folder_list = [each_entry for each_entry in os.listdir(search_folder_path) 
                   if os.path.isdir(os.path.join(search_folder_path, each_entry))]
    
    # Sort if needed
    if sort_list:
        folder_list.sort()    
    
    # Hide folders beginning with dots (i.e. hidden)
    if not show_hidden_folders:
        folder_list = [each_folder for each_folder in folder_list if each_folder[0] != "."]
    
    # Prepend the search folder path if desired
    if return_full_path:
        folder_list = [os.path.join(search_folder_path, each_folder) for each_folder in folder_list]

    return folder_list

# .....................................................................................................................
    
def get_file_list(search_folder_path, 
                  show_hidden_files = False, 
                  create_missing_folder = False, 
                  return_full_path = False,
                  sort_list = True,
                  allowable_exts_list = []):
    
    '''
    Returns a list of all files in the specified search folder
    '''
    
    # Make sure the search folder exists before trying to list it's contents!
    if not os.path.exists(search_folder_path):
        if create_missing_folder:
            os.makedirs(search_folder_path)
        return []
    
    # Take out only the files from the list of items in the search folder
    file_list = [each_entry for each_entry in os.listdir(search_folder_path) 
                 if os.path.isfile(os.path.join(search_folder_path, each_entry))]
    
    # Remove entries that don't have the target extensions
    if allowable_exts_list:
        
        # Clean up the allowable extensions list (add preceeding . and lowercase!), in case the user entered them funny
        safeify_ext = lambda ext: ".{}".format(ext.lower()) if ext[0] != "." else ext.lower()
        safe_exts = [safeify_ext(each_ext) for each_ext in allowable_exts_list]
        
        # Filter out files that don't have an extension from the (safe-ified) allowable ext list
        keep_file = lambda file, ext_list: (os.path.splitext(file)[1].lower() in ext_list)
        file_list = [each_file for each_file in file_list if keep_file(each_file, safe_exts)]
    
    # Sort if needed
    if sort_list:
        file_list.sort()
    
    # Hide files beginning with dots (i.e. hidden)
    if not show_hidden_files:
        file_list = [each_file for each_file in file_list if each_file[0] != "."]
    
    # Prepend the search folder path if desired
    if return_full_path:
        file_list = [os.path.join(search_folder_path, each_file) for each_file in file_list]
    
    return file_list

# .....................................................................................................................
    
def sort_path_list_by_age(path_list, newest_first, return_full_path = True):
    
    '''
    Function which takes a list of file/folder paths and returns a sorted copy of them by newest/oldest first,
    along with the corresponding file/folder age as reported by the os.
    
    Inputs:
        path_list --> (list/iterable of strings). The list of file/folder paths whose age should be sorted
        
        newest_first --> Boolean. If true, the returned listed will have the newest entry first
        
        return_full_path --> Boolean. If true, the entire file/folder path is returned
        
    Outputs:
    sorted_timestamps_list, sorted_names_or_paths_list
    
    Note: Ages are reported from os.path.mtime(...)
          The times use 'epoch' formatting stored as floats (i.e. seconds since Jan 1 1970)
          Example: 1577854801.000001 (= 2020/01/01 00:00:01.000001)
    '''
    
    # Bail if we have an empty list
    if len(path_list) == 0:
        return ((), ())
    
    # Check the modification time (as a measure of age)
    path_ages = [os.path.getmtime(each_path) for each_path in path_list]
    
    # Generate a list of basenames if we don't want to return the full paths
    if not return_full_path:
        name_list = [os.path.basename(each_path) for each_path in path_list]
    
    # Sort files by age before returning the file paths/names
    list_to_sort = path_list if return_full_path else name_list
    sorted_timestamps_list, sorted_names_or_paths_list = zip(*sorted(zip(path_ages, list_to_sort),
                                                                     reverse = newest_first))
    
    return sorted_timestamps_list, sorted_names_or_paths_list

# .....................................................................................................................
    
def get_file_list_by_age(search_folder_path,
                         newest_first = True,
                         show_hidden_files = False,
                         create_missing_folder = False,
                         return_full_path = False,
                         allowable_exts_list = []):
    
    '''
    Returns two lists:
    sorted_timestamps, sorted_names_or_paths
    '''
    
    # Get pathing to every file in the search folder
    path_list = get_file_list(search_folder_path, 
                              show_hidden_files = show_hidden_files, 
                              create_missing_folder = create_missing_folder, 
                              return_full_path = True,
                              sort_list = False,
                              allowable_exts_list = allowable_exts_list)
    
    sorted_timestamps, sorted_names_or_paths = sort_path_list_by_age(path_list, newest_first, return_full_path)
    
    return sorted_timestamps, sorted_names_or_paths

# .....................................................................................................................
    
def get_folder_list_by_age(search_folder_path, 
                           newest_first = True, 
                           show_hidden_folders = False, 
                           create_missing_folder = False,
                           return_full_path = False):
    
    '''
    Returns two lists:
    sorted_timestamps, sorted_names_or_paths
    '''
    
    # Get pathing to every file in the search folder
    path_list = get_folder_list(search_folder_path, 
                                show_hidden_folders = show_hidden_folders, 
                                create_missing_folder = create_missing_folder,
                                sort_list = False,
                                return_full_path = True)
    
    sorted_timestamps, sorted_names_or_paths = sort_path_list_by_age(path_list, newest_first, return_full_path)
    
    return sorted_timestamps, sorted_names_or_paths

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Sizing helpers

# .....................................................................................................................

def get_total_folder_size(folder_path, size_units = "M"):
    
    ''' 
    Function for calculating the total size of all contents within the given folder path
    Inputs:
        folder_path -> String. Path of parent folder whose total size is to be checked
        
        size_units -> String. One of None, "k", "M", "G", representing the unit scaling of the output
                      (None returns units in bytes, other options scale by powers of 1024)
                      
    Outputs:
        file_count, subdirectory_count, total_file_size, total_subdirectory_size
    '''
    
    # Create helper functions to deal with os.walk output pathing
    get_file_path = lambda dir_path, file: os.path.join(dir_path, file)
    get_file_size = lambda dir_path, file: os.path.getsize(get_file_path(dir_path, file))
    
    # Initialize loop counters
    file_count = 0
    subdir_count = 0
    total_file_size = 0
    total_subdir_size = 0
    
    # Don't bother searching if the folder doesn't exist!
    if not os.path.exists(folder_path):
        return file_count, subdir_count, total_file_size, total_subdir_size
    
    # Step through each directory (recursively) and sum the size of all folders & files
    for each_dir_path, each_subdir_list, each_file_list in os.walk(folder_path):
        
        file_count += len(each_file_list)
        subdir_count += len(each_subdir_list)
        total_file_size += sum((get_file_size(each_dir_path, each_file) for each_file in each_file_list))
        total_subdir_size += os.path.getsize(each_dir_path)
        
    # Scale output
    scaling_lut = {None: 1, "k": 1024, "m": 1024 ** 2, "g": 1024 ** 3, "p": 1024 ** 4}
    safe_size_units = size_units.strip().lower() if size_units is not None else None
    scaling_factor = scaling_lut.get(safe_size_units, 1)
    scaled_file_size = (total_file_size / scaling_factor)
    scaled_dir_size = (total_subdir_size / scaling_factor)
    
    return file_count, subdir_count, scaled_file_size, scaled_dir_size

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Demo

if __name__ == "__main__":    
    pass

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap


