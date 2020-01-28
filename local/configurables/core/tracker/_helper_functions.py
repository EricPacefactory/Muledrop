#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Jun  6 09:33:15 2019

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

import cv2
import numpy as np

from scipy.optimize import linear_sum_assignment

# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes


# ---------------------------------------------------------------------------------------------------------------------
#%% Define positioning functions

# .....................................................................................................................

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Define matching functions

# .....................................................................................................................

def _fast_unique(iterable):
    
    '''
    Faster than len(set(iterable)) == len(iterable) or np.unique(...),
    but only when expecting duplicates or if the iterable length is small
    
    From:
    https://stackoverflow.com/questions/
            50883576/fastest-way-to-check-if-duplicates-exist-in-a-python-list-numpy-ndarray
    '''
    
    # Loop through every value, check if we've seen it before (is so, the iterable has non-unique values so bail)
    is_unique = True
    values_seen = set()
    values_seen_add = values_seen.add
    for each_value in iterable:
        if each_value in values_seen or values_seen_add(each_value):
            is_unique = False
            break
    
    return is_unique

# .....................................................................................................................

def naive_object_detection_match(obj_by_det_cost_matrix, max_allowable_cost = 1.0):
    
    '''
    Function for pairing objects to detections.
    Works by assigning objects/detections based on the lowest cost assignement available.
    Note that this approach his can lead to duplicate pairings!
    (i.e. two objects pairing with a single detections or vice versa). 
    
    Will always make the pairing using the smaller set. For example, if there
    are 3 detections and 5 objects, then only 3 pairings will be made (the 'best' objects for each detection).
    
    Inputs:
        obj_by_det_cost_matrix --> np array. Each entry represents the 'cost' of assigning 
                                   the given object (row) to the given detection (column)
                                
        max_allowable_cost --> Float. Cost values must be below the allowable max to be consider valid matches.
        
    Outputs:
        is_unique --> Boolean. If true, the assignment is unique (i.e. no obj/detection was matched more than once)
        
        obj_det_idx_match_tuple_list --> List of tuples. Each tuple represents a pairing 
                                         of one object with one detection. The tuple itself contains
                                         the corresponding (row, column) index of the input cost matrix
                                         
        unmatched_objidx_list --> List. Represents the list of unmatched objects, where the entries themselves
                                  correspond to the rows of the cost matrix that were not matched.
                                  
        unmatched_detidx_list --> List. Represents the list of unmatched detections, where the entries themselves
                                  correspond to the columns of the cost matrix that were not matched.
    
    # ***************************
    
    Example:
        D1  D2
    A     B
    
    Result:
        A -> D1
        B -> D1
    
    # ***************************
    '''
    
    # Figure out how many objects/detections we have based on the cost matrix
    num_objs, num_dets = obj_by_det_cost_matrix.shape
    more_objs = (num_objs >= num_dets)
    
    # Match by the smaller of the two sets of inputs (objects or detections)
    if more_objs:
        best_match_rows = np.argmin(obj_by_det_cost_matrix, axis = 0)
        best_match_cols = np.arange(num_dets)
    else:
        best_match_rows = np.arange(num_objs)
        best_match_cols = np.argmin(obj_by_det_cost_matrix, axis = 1)
    
    # Filter out matches that have overly high costs
    allowable_matches = obj_by_det_cost_matrix[best_match_rows, best_match_cols] < max_allowable_cost
    best_match_rows = best_match_rows[allowable_matches].tolist()
    best_match_cols = best_match_cols[allowable_matches].tolist()   # tolist() conversion speeds up list-comp later!
    
    # Check if there are any duplicate matches (i.e. not unique)
    check_len = best_match_rows if more_objs else best_match_cols
    is_unique = _fast_unique(check_len)
    
    # Bundle the object/detection index pairings together
    obj_det_idx_match_tuple_list = list(zip(best_match_rows, best_match_cols))
    
    # Finally, get all the all the indices (obj/det) that are not part of the best-matches (i.e. unmatched)
    unmatched_objidx_list = [each_idx for each_idx in range(num_objs) if each_idx not in best_match_rows]
    unmatched_detidx_list = [each_idx for each_idx in range(num_dets) if each_idx not in best_match_cols]
    
    '''
    # For debugging
    print("")
    print("")
    print("***** GET NAIVE *****")
    print("Cost matrix:")
    print(obj_by_det_cost_matrix)
    print("")
    print("Matches: ({})".format("Unique" if unique_mapping else "Not unique"))
    print(obj_det_idx_match_tuple_list)
    print("Unmatched Obj. Index:", unmatched_objidx_list)
    print("Unmatched Det. Index:", unmatched_detidx_list)
    print("")
    print("Press key to unpause!")
    #cv2.waitKey(0)
    '''    
    
    return is_unique, obj_det_idx_match_tuple_list, unmatched_objidx_list, unmatched_detidx_list

# .....................................................................................................................

def greedy_object_detection_match(obj_by_det_cost_matrix, max_allowable_cost = 1.0):
    
    '''
    Function for matching objects to detections using a greedy approach
    Works by matching 'best-match-first' basis.
    After matching the matched pair are excluded from all assignment checks
    
    This style of matching will always produce unique matched pairs, but is typically slower (~x2) 
    than the naive matching function, and may give 'poor' results in specific cases,
    causing objects to leapfrog each other for example.
    
    Inputs:
        obj_by_det_cost_matrix --> np array. Each entry represents the 'cost' of assigning 
                                   the given object (row) to the given detection (column)
                                
        max_allowable_cost --> Float. Cost values must be below the allowable max to be consider valid matches.
        
    Outputs:        
        obj_det_idx_match_tuple_list --> List of tuples. Each tuple represents a pairing 
                                         of one object with one detection. The tuple itself contains
                                         the corresponding (row, column) index of the input cost matrix
                                         
        unmatched_objidx_list --> List. Represents the list of unmatched objects, where the entries themselves
                                  correspond to the rows of the cost matrix that were not matched.
                                  
        unmatched_detidx_list --> List. Represents the list of unmatched detections, where the entries themselves
                                  correspond to the columns of the cost matrix that were not matched.
    
    # ***************************
    
    Example:
    Assume we have objects A & B from a previous frame, and detections D1 and D2 from the current frame, shown below.
    Also assume that the cost matrix is just the distance between the object/detection.
    Since the B-to-D1 distance is the shortest pairing, it will be matched first, followed by A-to-D2.
    This avoids duplications (both A & B would naively match to D1), 
    but may not be the ideal pairing since the pairing is criss-crossed 
    (if A/B continue traveling diagonally, each iteration would tend to leapfrog them back and forth!).
    
        D1  D2
    A     B
    
    Result:
        B -> D1
        A -> D2
        
    # ***************************
    '''
    
    # Get number of objects and detections based on the cost matrix
    num_objs, num_dets = obj_by_det_cost_matrix.shape
    
    # Sort all costs (smallest first)
    sorted_idxs = np.argsort(obj_by_det_cost_matrix.ravel())
    
    # Allocate looping resources
    max_iter = min(num_objs, num_dets)
    num_iter = 0
    matched_objs = []
    matched_dets = []
    
    # Loop over the sorted cost values and add the corresponding obj/det index to our matched list,
    # but only if we haven't already seen those indices
    for each_idx in sorted_idxs:
        
        # Convert unravelled indices back into row/col indices
        each_obj_idx = int(each_idx / num_dets)
        each_det_idx = each_idx % num_dets
        
        # Stop if the current value exceeds the maximum cost (we won't find anything smaller going forward)
        if obj_by_det_cost_matrix[each_obj_idx, each_det_idx] > max_allowable_cost:
            break
        
        # Add the object (row) and detection (column) index to our matched list, only if they are unique entries
        if (each_obj_idx not in matched_objs) and (each_det_idx not in matched_dets):
            matched_objs.append(each_obj_idx)
            matched_dets.append(each_det_idx)
            
            # Stop searching once we've got all unique pairs
            num_iter += 1
            if num_iter > max_iter:
                break
            
    # Bundle the object/detection index pairings together
    obj_det_idx_match_tuple_list = list(zip(matched_objs, matched_dets))
    
    # Finally, get all the indices (obj/det) that are not part of the best-matches (i.e. unmatched)
    unmatched_objidx_list = [each_idx for each_idx in range(num_objs) if each_idx not in matched_objs]
    unmatched_detidx_list = [each_idx for each_idx in range(num_dets) if each_idx not in matched_dets]
    
    '''
    # For debugging
    print("")
    print("")
    print("***** GET GREEDY *****")
    print("Cost matrix:")
    print(obj_by_det_cost_matrix)
    print("")
    print("Matches:")
    print(obj_det_idx_match_tuple_list)
    print("Unmatched Obj. Index:", unmatched_objidx_list)
    print("Unmatched Det. Index:", unmatched_detidx_list)
    print("")
    print("Press key to unpause!")
    cv2.waitKey(0)
    '''
        
    return obj_det_idx_match_tuple_list, unmatched_objidx_list, unmatched_detidx_list

# .....................................................................................................................
    
def minsum_object_detection_match(obj_by_det_cost_matrix, max_allowable_cost = 1.0):
    
    '''
    Function for matching objects to detections by finding the pairing with the minimum total cost.
    Google 'Hungarian algorithm' for more info.
    
    This style of matching should (usually) produce better pairing than the greedy approach. For example,
    if the cost function is the square distance between objects/detections, then the result of this pairing
    willl tend avoid outliers (i.e favor consistent pairing distances over very small + very large distances).
    It will also tend to make the most 'possible' pairs.
    
    Note however that this function runs significantly slower (~x10) than the greedy or naive pairing functions.
    It also modifys the cost matrix!
    
    Inputs:
        obj_by_det_cost_matrix --> np array. Each entry represents the 'cost' of assigning 
                                   the given object (row) to the given detection (column)
                                
        max_allowable_cost --> Float. Cost values must be below the allowable max to be consider valid matches.
        
    Outputs:        
        obj_det_idx_match_tuple_list --> List of tuples. Each tuple represents a pairing 
                                         of one object with one detection. The tuple itself contains
                                         the corresponding (row, column) index of the input cost matrix
                                         
        unmatched_objidx_list --> List. Represents the list of unmatched objects, where the entries themselves
                                  correspond to the rows of the cost matrix that were not matched.
                                  
        unmatched_detidx_list --> List. Represents the list of unmatched detections, where the entries themselves
                                  correspond to the columns of the cost matrix that were not matched.
    '''
    
    # Figure out sizing
    num_objs, num_dets = obj_by_det_cost_matrix.shape
    
    # Scale up 'high cost' values, so that they don't mess with matching too much
    bad_matches = obj_by_det_cost_matrix > max_allowable_cost
    obj_by_det_cost_matrix[bad_matches] = (100.0 * max_allowable_cost)
    
    # Find obj/detection matches. Note that the function handles short matrix conversion!
    obj_match_idxs, det_match_idxs = linear_sum_assignment(obj_by_det_cost_matrix)
    
    # Allocate loop resources
    obj_det_idx_match_tuple_list = []
    matched_obj_list = []
    matched_det_list = []
    
    # Build object/detection match lists
    for each_obj_idx, each_det_idx in zip(obj_match_idxs, det_match_idxs):
        match_cost = obj_by_det_cost_matrix[each_obj_idx, each_det_idx]
        if match_cost < max_allowable_cost:
            obj_det_idx_match_tuple_list.append((each_obj_idx, each_det_idx))
            matched_obj_list.append(each_obj_idx)
            matched_det_list.append(each_det_idx)
    
    # Now figure out which objects/detections weren't matched
    unmatched_objidx_list = [each_idx for each_idx in range(num_objs) if each_idx not in matched_obj_list]
    unmatched_detidx_list = [each_idx for each_idx in range(num_dets) if each_idx not in matched_det_list]
    
    return obj_det_idx_match_tuple_list, unmatched_objidx_list, unmatched_detidx_list

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Demo
    
if __name__ == "__main__":    
    
    def calculate_squared_distance_pairing_matrix(row_entry_xy_tuple_list, col_entry_xy_tuple_list,
                                                  x_scale = 1.0, y_scale = 1.0):
        
        # Get number of rows & columns. Bail if either is zero
        num_rows = len(row_entry_xy_tuple_list)
        num_cols = len(col_entry_xy_tuple_list)
        if num_rows == 0 or num_cols == 0:
            return np.array(())
        
        # Convert to arrays and apply x/y dimensional scaling so we can get numpy to do all the heavy lifting
        row_xy_array = np.float32(row_entry_xy_tuple_list) * np.float32((x_scale, y_scale))
        col_xy_array = np.float32(col_entry_xy_tuple_list) * np.float32((x_scale, y_scale))
        
        # Calculate the x-difference between the row and column object locations
        row_x_array = row_xy_array[:, 0]
        col_x_array = col_xy_array[:, 0]
        delta_x = np.tile(row_x_array, (num_cols, 1)).T - np.tile(col_x_array, (num_rows, 1))
        
        # Calculate the y-difference between the row and column object locations
        row_y_array = row_xy_array[:, 1]
        col_y_array = col_xy_array[:, 1]
        delta_y = np.tile(row_y_array, (num_cols, 1)).T - np.tile(col_y_array, (num_rows, 1))
        
        # Square and sum the x/y distances to get our results!
        square_distance_matrix = np.square(delta_x) + np.square(delta_y)
        
        return square_distance_matrix
    
    def draw_matches(match_name, display_frame, od_match_tuple_list, unmatched_objs, unmatched_dets, 
                     window_pos = (200, 200),
                     is_unique = None,
                     letter_lookup = "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
                     match_range_color = (45, 45, 45)):
        
        draw_frame = display_frame.copy()
        match_color = (255, 255, 0)
        if is_unique is not None:
            match_color = (255, 255, 0) if is_unique else (0, 0, 255)
        
        # Draw lines connecting object/detection matches
        for each_obj_idx, each_det_idx in obj_det_match_tuple:
            obj_pt = ro_px[each_obj_idx]
            det_pt = rd_px[each_det_idx]
            cv2.line(draw_frame, obj_pt, det_pt, match_color, 1, cv2.LINE_AA)
        
        # Draw match radius circle around all unmatched objects
        for each_obj_idx in unmatched_objs:
            obj_pt = ro_px[each_obj_idx]
            cv2.ellipse(draw_frame, obj_pt, (match_x_px, match_y_px), 0, 0, 360, match_range_color, 1, cv2.LINE_AA)
            
        # Print info for inspection
        obj_idxs, det_idxs = zip(*obj_det_match_tuple) if len(obj_det_match_tuple) > 0 else ([], [])
        letter_obj_match = [letter_lookup[each_obj_idx] for each_obj_idx in obj_idxs]
        uniq_obj_det_match_tuple = list(zip(letter_obj_match, det_idxs))
        letter_obj_unmatch = [letter_lookup[each_obj_idx] for each_obj_idx in unmatched_objs]
        print("", "",
              "{} Match results".format(match_name), sep = "\n")
        if is_unique is not None:
            print("Unique mapping found:", is_unique)
        print("Obj-to_det matches:",
              *uniq_obj_det_match_tuple,
              "Unmatched objs: {}".format(letter_obj_unmatch),
              "Unmatched dets: {}".format(unmatched_dets),
              sep="\n")
        cv2.imshow("{} Match".format(match_name), draw_frame)
        cv2.moveWindow("{} Match".format(match_name), *window_pos)
    
    cv2.destroyAllWindows()
    
    frame_size = 400
    frame_padding = 50
    
    num_examples = 10
    match_x_dist = 0.35
    match_y_dist = 0.35
    
    letter_lookup = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    text_config = {"fontFace": cv2.FONT_HERSHEY_SIMPLEX,
                   "fontScale": 0.5,
                   "thickness": 1,
                   "lineType": cv2.LINE_AA}
    #for match_x_dist in reversed([1.0, 0.75, 0.5, 0.25, 0.1]):
    for k in range(num_examples):
        
        # Set match distance pixel values and scaling, in case loop is changing distances...
        match_x_px = int(round((frame_size - 1) * match_x_dist))
        match_y_px = int(round((frame_size - 1) * match_y_dist))
        x_scale = 1 / match_x_dist if match_x_dist > 0 else 1E10
        y_scale = 1 / match_y_dist if match_y_dist > 0 else 1E10
    
        # Generate some random object + detection points
        num_objs, num_dets = np.random.randint(2, 9, 2)
        
        # Generate some points and calculate their squared distance matrix
        ro = np.clip(np.random.rand(num_objs, 2), 0.05, 0.95)
        rd = np.clip(np.random.rand(num_dets, 2), 0.05, 0.95)
        ObyD_sqdist_matrix = calculate_squared_distance_pairing_matrix(ro, rd, x_scale, y_scale)
        
        '''
        # Good example of differences between matching methods (try match_x_dist = match_y_dist = 0.25)
        ro = [[0.59, 0.365], [0.7125, 0.36], [0.7475, 0.42], [0.37, 0.4975], 
              [0.715, 0.5225], [0.4225, 0.5575], [0.255, 0.3325]]
        rd = [[0.3275, 0.7175], [0.5925, 0.4725], [0.59, 0.5275], [0.3825, 0.2825], 
              [0.29, 0.2825], [0.475, 0.6475], [0.6425, 0.7]]
        ObyD_sqdist_matrix = calculate_squared_distance_pairing_matrix(ro, rd, x_scale, y_scale)
        '''
        
        '''
        # Another good example of differences (try match_x_dist = match_y_dist = 0.25)
        ro = [[0.3325, 0.4375], [0.605, 0.7075], [0.4625, 0.285], [0.5875, 0.4075], 
              [0.61, 0.6625], [0.49, 0.385], [0.3375, 0.66]]
        rd = [[0.66, 0.73], [0.62, 0.2925], [0.5275, 0.6875], [0.3075, 0.32], 
              [0.6825, 0.5875], [0.735, 0.535], [0.4425, 0.38]]
        ObyD_sqdist_matrix = calculate_squared_distance_pairing_matrix(ro, rd, x_scale, y_scale)
        '''
        
        ro_px = [tuple(np.int32(np.round(np.array(each_ro) * (frame_size - 1)))) for each_ro in ro]
        rd_px = [tuple(np.int32(np.round(np.array(each_rd) * (frame_size - 1)))) for each_rd in rd]
        
        print("")
        print(" *" * 20)
        print("Random object:")
        print(ro_px)
        print("Random detection:")
        print(rd_px)
        
        # Create blank frame to draw points in to
        blank_frame = np.zeros((frame_size, frame_size, 3), dtype=np.uint8)
        
        # Draw objects
        for each_obj_idx, each_oxy in enumerate(ro_px):
            obj_letter_str = letter_lookup[each_obj_idx]
            cv2.putText(blank_frame, obj_letter_str, each_oxy, color = (0, 255, 255), **text_config)
            
        # Draw detections
        for each_det_idx, each_dxy in enumerate(rd_px):
            cv2.putText(blank_frame, "{}".format(each_det_idx), each_dxy, color = (0, 255, 0), **text_config)
        
        # Draw naive matches
        unique_mapping, obj_det_match_tuple, unmatched_obj_list, unmatched_det_list = \
        naive_object_detection_match(ObyD_sqdist_matrix)        
        draw_matches("NAIVE", blank_frame, obj_det_match_tuple, unmatched_obj_list, unmatched_det_list,
                     window_pos = (450, 200),
                     is_unique = unique_mapping)
        
        
        # Draw greedy matches
        obj_det_match_tuple, unmatched_obj_list, unmatched_det_list = \
        greedy_object_detection_match(ObyD_sqdist_matrix)
        draw_matches("GREEDY", blank_frame, obj_det_match_tuple, unmatched_obj_list, unmatched_det_list,
                     window_pos = (900, 200))
        
        # Draw MinSUM matches
        obj_det_match_tuple, unmatched_obj_list, unmatched_det_list = \
        minsum_object_detection_match(ObyD_sqdist_matrix)
        draw_matches("MINSUM", blank_frame, obj_det_match_tuple, unmatched_obj_list, unmatched_det_list,
                     window_pos = (1350, 200))
        
        cv2.waitKey(0)
        
    cv2.destroyAllWindows()

# ---------------------------------------------------------------------------------------------------------------------
#%% Performance check 

if __name__ == "__main__":
    
    from time import perf_counter
    
    # Set match distance and calculate x/y scaling
    match_x_dist = 0.35
    match_y_dist = 0.35
    
    # Generate some random object + detection points
    num_objs, num_dets = np.random.randint(2, 9, 2)
    num_objs, num_dets = 3, 3
    
    # Generate some random points (with normalized co-ords)
    ro = np.clip(np.random.rand(num_objs, 2), 0.05, 0.95)
    rd = np.clip(np.random.rand(num_dets, 2), 0.05, 0.95)
    
    # Calculate scaled square distance matrix, needed for each matching check
    x_scale = 1 / match_x_dist if match_x_dist > 0 else 1E10
    y_scale = 1 / match_y_dist if match_y_dist > 0 else 1E10
    ObyD_sqdist_matrix = calculate_squared_distance_pairing_matrix(ro, rd, x_scale, y_scale)
    sqmat = ObyD_sqdist_matrix.copy()
    
    # Some feedback
    print("")
    print("Performance test in progress...")
    num_iter = 100
    
    if num_iter > 0:
    
        # Performance check
        tn1 = perf_counter()
        for k in range(num_iter):
            unique_mapping, obj_det_match_tuple, unmatched_obj_list, unmatched_det_list = \
            naive_object_detection_match(ObyD_sqdist_matrix)
        tn2 = perf_counter()
        
        tg1 = perf_counter()
        for k in range(num_iter):
            obj_det_match_tuple, unmatched_obj_list, unmatched_det_list = \
            greedy_object_detection_match(ObyD_sqdist_matrix)
        tg2 = perf_counter()
        
        ts1 = perf_counter()
        for k in range(num_iter):
            obj_det_match_tuple, unmatched_obj_list, unmatched_det_list = \
            minsum_object_detection_match(ObyD_sqdist_matrix)
        ts2 = perf_counter()
        
        print("")
        print("Length of ro, rd: {} x {}".format(len(ro), len(rd)))
        print("UNIQUE MAPPING:", unique_mapping)
        print("PER ITERATION TIMING:")
        print("  NAIVE TIME:", "{:.3f} ms".format(1000 *(tn2-tn1) / num_iter))
        print(" GREEDY TIME:", "{:.3f} ms".format(1000 *(tg2-tg1) / num_iter))
        print(" MINSUM TIME:", "{:.3f} ms".format(1000 *(ts2-ts1) / num_iter))




# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap
