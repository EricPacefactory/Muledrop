#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Mar 18 16:35:24 2019

@author: eo
"""


# ---------------------------------------------------------------------------------------------------------------------
#%% Imports 

import numpy as np


# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions 

# .....................................................................................................................

def rotation_matrix_2D(angle, angle_in_radians = True, invert_matrix = False, dtype = np.float32):
    
    # Convert angle to radians if needed
    if not angle_in_radians:
        angle = np.radians(angle)
        
    # Reverse the angle if needed (equivalent to the inverse matrix)
    if invert_matrix:
        angle = -angle
        
    # Calculate component terms
    cos_term = np.cos(angle)
    sin_term = np.sin(angle)
    
    # Generate rotation matrix
    rot_mat = np.array(((cos_term, -sin_term), (sin_term, cos_term)), 
                       dtype = dtype)
    
    return rot_mat

# .....................................................................................................................
    
def rotate_around_center(rotation_matrix, x_points, y_points, x_center = 0.0, y_center = 0.0,
                         rotation_angle_deg = None):
    
    # Create vector out of x/y points so we can do matrix multiplication
    xy_center_array = np.array((x_center, y_center), dtype=np.float32)
    
    # Build rotation matrix, if needed
    if rotation_matrix is None:
        rotation_matrix = rotation_matrix_2D(rotation_angle_deg, angle_in_radians = False)
    
    xy_recenter = np.stack((x_points, y_points)) - xy_center_array
    rot_x, rot_y = np.matmul(rotation_matrix, xy_recenter) + xy_center_array
    
    return rot_x, rot_y

# .....................................................................................................................
    
# .....................................................................................................................
    

# ---------------------------------------------------------------------------------------------------------------------
#%% Demo
    
if __name__ == "__main__":
    
    pass


# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap 



