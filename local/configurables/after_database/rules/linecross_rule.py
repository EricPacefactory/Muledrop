#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Jan 27 13:10:28 2020

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

from local.configurables.after_database.rules.reference_rule import Reference_Rule

from local.offline_database.object_reconstruction import Smoothed_Object_Reconstruction as Obj_Recon

from eolib.math.geometry import Fixed_Line_Cross


# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes

class Linecross_Rule(Reference_Rule):
    
    # .................................................................................................................
    
    def __init__(self, cameras_folder_path, camera_select, user_select, input_wh, rule_name):
        
        # Inherit from base class
        super().__init__(cameras_folder_path, camera_select, user_select, input_wh, rule_name,
                         file_dunder = __file__)
        
        # Allocate storage for the fixed-line object
        self.fixed_line = Fixed_Line_Cross((0,0), (1,0), flip_orientation = False, is_normalized = True)
        
        # .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  . Drawing Controls  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .
        
        self.line_entity_list = \
        self.ctrl_spec.attach_drawing(
                "line_entity_list",
                default_value = [[(0.5, 0.15), (0.5, 0.85)]],
                min_max_entities = (1, 1),
                min_max_points = (2, 2),
                entity_type = "line",
                drawing_style = "line")
        
        # .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  . Control Group 1 .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .
        
        self.ctrl_spec.new_control_group("Line Controls")
        
        self.flip_line_orientation = \
        self.ctrl_spec.attach_toggle(
                "flip_line_orientation", 
                label = "Flip Orientation", 
                default_value = False,
                tooltip = "Flips the orientation of the line. Equivalent to swapping the end points of the line.")
        
        pass
    
    # .................................................................................................................
    
    def setup(self, variables_changed_dict):
        
        # Pull out line points from drawing entity
        line_entity = self.line_entity_list[0]        
        line_pt1, line_pt2 = line_entity
        
        # Rebuild the fixed-line object, in case the start/end points of the line have changed
        self.fixed_line = Fixed_Line_Cross(line_pt1, line_pt2, 
                                           flip_orientation = self.flip_line_orientation, 
                                           is_normalized = True)
        
    
    # .................................................................................................................
    
    def process_object_metadata(self, object_id, object_metadata, frame_wh):
        
        # Create dummy data to fill out reconstruction
        global_start_time = 0.0
        global_end_time = 1.0
        
        # Reconstruct object, so we can get access to existing data manipulation functions
        object_data = Obj_Recon(object_metadata, frame_wh, global_start_time, global_end_time)
        
        return object_data
    
    # .................................................................................................................
    
    
    def evaluate_one_object(self, object_data, snapshot_database, frame_wh):
        
        # Check if the trail of the object intersects at all with the fixed line
        rule_results_list = self.fixed_line.path_intersection(object_data.trail_xy)
        
        return rule_results_list

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


