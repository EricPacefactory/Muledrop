#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Jul  4 09:43:48 2019

@author: eo
"""

# ---------------------------------------------------------------------------------------------------------------------
#%% Imports

import os
import gzip
import json
import shutil

# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

def unzip_gz_to_json(folder_path, file_name):
    
    # Ignore files that don't have a .gz file extension
    file_name_only, file_ext = os.path.splitext(file_name)
    if file_ext != ".gz":
        return
    
    # Some feedback if we get here
    print("Unzipping:", os.path.basename(folder_path), "/", file_name_only)
    
    # First build the full file path & json save path
    full_file_path = os.path.join(folder_path, file_name)
    json_file_path, _ = os.path.splitext(full_file_path)
    
    # Unzip (json) data into a dictionary, then re-save as .json file
    with gzip.open(full_file_path, 'rt') as in_file:
        with open(json_file_path, "w") as out_file:
            json_data = json.load(in_file)
            json.dump(json_data, out_file, indent = 2, sort_keys = True)

    # Make sure the json file exists, then delete the original gz file
    if os.path.exists(json_file_path):
        os.remove(full_file_path)

# ---------------------------------------------------------------------------------------------------------------------
#%% Initial setup

# Set the target reporting folder
target_folder = "report"
copy_folder_name = "{}_unzipped".format(target_folder)

# Make sure the target folder is in the same directory as this script
if target_folder not in os.listdir():
    print("",
          "Couldn't find target folder! ({})".format(target_folder),
          "  Make sure this script is placed in the same folder as the target folder.")
    quit()
    
# Make a copy of the target folder, so we can create unzipped copies
try:
    shutil.copytree(target_folder, copy_folder_name)
except FileExistsError:
    print("",
          "Warning: Copied target folder already exists! ({})".format(copy_folder_name),
          "  Will still try to unzip gzip files...",
          sep="\n")

# ---------------------------------------------------------------------------------------------------------------------
#%% Unzip files

for parent_path, dir_list, file_list in os.walk(copy_folder_name):
    for each_file in file_list:
        unzip_gz_to_json(parent_path, each_file)
