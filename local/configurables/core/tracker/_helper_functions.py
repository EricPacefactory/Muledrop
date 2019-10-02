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

from itertools import permutations, product

# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes


# ---------------------------------------------------------------------------------------------------------------------
#%% Define positioning functions

# .....................................................................................................................
    
def calculate_squared_distance_pairing_matrix(row_entry_xy_tuple_list, col_entry_xy_tuple_list,
                                              x_scale = 1.0, y_scale = 1.0):
    
    '''
    Function which calculates the squared distance between each pair of row/col objects xys
    This function assumes xy values are given with the desired tracking point already
    (i.e. will not assume center/base tracking, that should be handled beforehand)
    Note that this function doesn't assume any units! Can be used with meters/pixels/normalized etc.
    For each row/col pairing, the calculation is given by:
        
        squared_distance = (x_scale * (row_x - col_x)) ^ 2 + (y_scale * (row_y- col_y)) ^ 2
        
    This returns a matrix with a format described below...        
    
    *** Given ***
    row_entries = Objects: A, B, C, D, E
    col_entries = Detections: 1, 2, 3
    
    *** Matrix Format ***
    Entries (#) are calculated using the squared_distance formula above
    
          1    2    3
    
    A     #    #    #
    
    B     #    #    #
    
    C     #    #    #
    
    D     #    #    #
    
    E     #    #    #
    
    '''
    
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

# .....................................................................................................................
    
def build_obj_det_match_xys(object_ref_list, detection_ref_list):
    
    '''
    Get a list of xy tuples for both the objects and detections 
    Only matches by object-to-detection center points (isn't affected by center/base tracking)
    Assumes objects have an xy_match function, which can additionally use object speed to alter object xy position
    '''
    
    object_xys = [each_obj.xy_match() for each_obj in object_ref_list]
    detection_xys = [each_detection.xy_center for each_detection in detection_ref_list]
    
    return object_xys, detection_xys

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

def naive_object_detection_match(obj_by_det_sqdist_matrix, max_match_square_distance = 1.0):
    
    '''
    Function for pairing objects to detections.
    Works by assigning objects/detections their 'best' match, though this can lead to duplicate pairings
    (i.e. two objects pairing with a single detections or vice versa). 
    
    Will always make the pairing using the smaller set. For example, if there
    are 3 detections and 5 objects, then only 3 pairings will be made (the closest objects for each detection).
    This favours unmatched objects/detections (objects in the above example)
    instead of trying to resolve duplicate pairings.
    
    Example:
        D1  D2
    A     B
    
    Result:
        A -> D1
        B -> D1
    '''
    
    # Figure out how many objects/detections we have based on the distance matrix
    num_objs, num_dets = obj_by_det_sqdist_matrix.shape
    more_objs = (num_objs >= num_dets)
    
    # Match by the smaller of the two sets of inputs (objects or detections)
    if more_objs:
        best_match_rows = np.argmin(obj_by_det_sqdist_matrix, axis = 0)
        best_match_cols = np.arange(num_dets)
    else:
        best_match_rows = np.arange(num_objs)
        best_match_cols = np.argmin(obj_by_det_sqdist_matrix, axis = 1)
    
    # Filter out matches that were out of range
    within_range = obj_by_det_sqdist_matrix[best_match_rows, best_match_cols] < max_match_square_distance
    best_match_rows = best_match_rows[within_range].tolist()
    best_match_cols = best_match_cols[within_range].tolist()    # tolist() conversion speeds up list-comp later!
    
    # Check if there are any duplicate matches (i.e. not unique)
    check_len = best_match_rows if more_objs else best_match_cols
    is_unique = _fast_unique(check_len)
    
    # Bundle the object/detection pairings together
    obj_det_match_tuple = list(zip(best_match_rows, best_match_cols))
    
    # Finally, get all the all the indices (obj/det) that are not part of the best-matches (i.e. unmatched)
    unmatched_obj_list = [each_idx for each_idx in range(num_objs) if each_idx not in best_match_rows]
    unmatched_det_list = [each_idx for each_idx in range(num_dets) if each_idx not in best_match_cols]
    
    '''
    # For debugging
    print("")
    print("")
    print("***** GET NAIVE *****")
    print("Square distance matrix:")
    print(obj_by_det_sqdist_matrix)
    print("")
    print("Matches: ({})".format("Unique" if unique_mapping else "Not unique"))
    print(obj_det_match_tuple)
    print("Unmatched Obj. Index:", unmatched_obj_list)
    print("Unmatched Det. Index:", unmatched_det_list)
    print("")
    print("Press key to unpause!")
    #cv2.waitKey(0)
    '''    
    
    return is_unique, obj_det_match_tuple, unmatched_obj_list, unmatched_det_list

# .....................................................................................................................

def greedy_object_detection_match(obj_by_det_sqdist_matrix, max_match_square_distance = 1.0):
    
    '''
    Function for matching objects to detections using a greedy approach
    Works by matching  on a 'shortest-distance-first' basis.
    After matching the matched object/detection are excluded for the next round of matching
    
    This style of matching will always produce unique matched pairs, but is slower than the naive matching
    function, and may give 'poor' results in specific cases, causing objects to leapfrog each other for example.
    
    Example:
    Assume we have objects A & B from a previous frame, and detections D1 and D2 from the current frame, shown below.
    Since the B-to-D1 distance is the shortest pairing, it will be matched first, followed by A-to-D2.
    This avoids duplications (both A & B would naively match to D1), but may not be the ideal pairing.
        
        D1  D2
    A     B
    
    Result:
        B -> D1
        A -> D2
    '''
    
    # Get number of objects and detections based on the distance matrix
    num_objs, num_dets = obj_by_det_sqdist_matrix.shape
    
    # Sort all distances (smallest first)
    sorted_idxs = np.argsort(obj_by_det_sqdist_matrix.ravel())
    
    # Allocate looping resources
    max_iter = min(num_objs, num_dets)
    num_iter = 0
    matched_objs = []
    matched_dets = []
    
    # Loop over the sorted distance values and add the corresponding obj/det index to our matched list,
    # but only if we haven't already seen those indices
    for each_idx in sorted_idxs:
        
        # Convert unravelled indices back into row/col indices
        each_obj_idx = int(each_idx / num_dets)
        each_det_idx = each_idx % num_dets
        
        # Stop if the current value exceeds the maximum distance (we won't find anything smaller going forward)
        if obj_by_det_sqdist_matrix[each_obj_idx, each_det_idx] > max_match_square_distance:
            break
        
        # Add the object (row) and detection (column) index to our matched list, only if they are unique entries
        if (each_obj_idx not in matched_objs) and (each_det_idx not in matched_dets):
            matched_objs.append(each_obj_idx)
            matched_dets.append(each_det_idx)
            
            # Stop searching once we've got all unique pairs
            num_iter += 1
            if num_iter > max_iter:
                break
            
    # Bundle the object/detection pairings together
    obj_det_match_tuple = list(zip(matched_objs, matched_dets))
    
    # Finally, get all the indices (obj/det) that are not part of the best-matches (i.e. unmatched)
    unmatched_obj_list = [each_idx for each_idx in range(num_objs) if each_idx not in matched_objs]
    unmatched_det_list = [each_idx for each_idx in range(num_dets) if each_idx not in matched_dets]
    
    '''
    # For debugging
    print("")
    print("")
    print("***** GET GREEDY *****")
    print("Square distance matrix:")
    print(obj_by_det_sqdist_matrix)
    print("")
    print("Matches:")
    print(obj_det_match_tuple)
    print("Unmatched Obj. Index:", unmatched_obj_list)
    print("Unmatched Det. Index:", unmatched_det_list)
    print("")
    print("Press key to unpause!")
    cv2.waitKey(0)
    '''
        
    return obj_det_match_tuple, unmatched_obj_list, unmatched_det_list
        

# .....................................................................................................................

def pathmin_object_detection_match(obj_by_det_sqdist_matrix, max_match_square_distance = 1.0):
    
    '''
    Function which matches objects to detections by picking the (unique!) pair which minimizes
    the total squared path lengths. Inituitively, this tends to pick pairings without outliers
    (i.e. favors having consistent pairing distances over very small + very large distances)
    
    Warning: For large numbers (>6) of objects & detections, this function can run extremely slow!
             ... The scaling is so sudden, it seems like there might be something wrong?
             Also, would be worth implementing more efficient permutation checker, based on max range exclusions!
             
             Note that this function may overwrite entries in the obj/det distance matrix!
             
    Example:
        D1  D2
    A     B
    
    Result:
        A -> D1
        B -> D2
    '''
    
    # Figure out sizing
    num_objs, num_dets = obj_by_det_sqdist_matrix.shape
    more_rows = (num_objs > num_dets)
    short_matrix = obj_by_det_sqdist_matrix.T if more_rows else obj_by_det_sqdist_matrix
    
    # Overwrite any entries that exceed the max range, with a silly value to avoid matching
    bad_indices = short_matrix > max_match_square_distance
    short_matrix[bad_indices] = max_match_square_distance * 100
    
    # Determine which side dimension is smaller, since we'll minimize based on those indices
    if more_rows:
        smaller_dim = num_dets
        larger_dim = num_objs
    else:
        smaller_dim = num_objs
        larger_dim = num_dets
    
    # Set up indexing vectors
    small_index_vector = np.arange(smaller_dim)     # For 4x2 = [0,1] 
    big_index_vector = np.arange(larger_dim)        # For 4x2 = [0,1,2,3]        
    all_col_index_permutations = permutations(big_index_vector, smaller_dim)
    
    # Create indexing matrix for all unique row/column permutations
    col_perm_index_matrix = np.int64(list(all_col_index_permutations))    
    
    # Calculate the sum of every column index permutation, and find the smallest total (i.e. best match!)
    path_sums = np.sum(short_matrix[small_index_vector, col_perm_index_matrix], axis=1)
    best_match_idx = np.argmin(path_sums)
    best_match_vector = col_perm_index_matrix[best_match_idx]
    
    # Only take matches within the max matching range
    good_rows, good_cols = [], []
    for each_row_idx, each_col_idx in zip(small_index_vector, best_match_vector):
        
        # Check each matched (square) distance
        sq_dist = short_matrix[each_row_idx, each_col_idx]
        if sq_dist > max_match_square_distance:
            continue
        
        # Keep the good ones
        good_rows.append(each_row_idx)
        good_cols.append(each_col_idx)
    
    # Assign matching, based on the shape of the indexing that was used
    matched_obj_list, matched_det_list = (good_cols, good_rows) if more_rows else (good_rows, good_cols)
    obj_det_match_tuple = list(zip(matched_obj_list, matched_det_list))
    
    # Now figure out which objects/detections weren't matched
    unmatched_obj_list = [each_idx for each_idx in range(num_objs) if each_idx not in matched_obj_list]
    unmatched_det_list = [each_idx for each_idx in range(num_dets) if each_idx not in matched_det_list]
    
    return obj_det_match_tuple, unmatched_obj_list, unmatched_det_list

# .....................................................................................................................

def alt_pathmin_unfinished(obj_by_det_sqdist_matrix, max_match_square_distance = 1.0):
    
    print("WARNING UNFINISHED!")
    print("Doesn't handle certain edge cases properly...")
    print("Namely when best matches all appear on the same row")
    
    num_objs, num_dets = obj_by_det_sqdist_matrix.shape
    
    # Remove any column indices that have no 
    col_range = np.arange(num_dets)
    valid_col_idxs = col_range[np.min(obj_by_det_sqdist_matrix, axis = 0) < max_match_square_distance]
    
    row_range = np.arange(num_objs)
    valid_row_idxs = [row_range[obj_by_det_sqdist_matrix[:, each_col] < max_match_square_distance].tolist() \
                      for each_col in valid_col_idxs]
    
    row_product = product(*valid_row_idxs)
    
    smallest_sum = 1000000
    best_row_idxs = []
    for product_idx, each_row_idxs in enumerate(row_product):
        
        # Ignore checks with duplicated rows
        is_unique = _fast_unique(each_row_idxs)
        if not is_unique:
            continue
        
        dist_sum = np.sum(obj_by_det_sqdist_matrix[each_row_idxs, valid_col_idxs])
        
        if dist_sum < smallest_sum:
            smallest_sum = dist_sum
            best_row_idxs = each_row_idxs
    
    # Assign matching
    matched_obj_list, matched_det_list = best_row_idxs, valid_col_idxs
    obj_det_match_tuple = list(zip(best_row_idxs, valid_col_idxs))
    
    # Now figure out which objects/detections weren't matched
    unmatched_obj_list = [each_idx for each_idx in range(num_objs) if each_idx not in matched_obj_list]
    unmatched_det_list = [each_idx for each_idx in range(num_dets) if each_idx not in matched_det_list]
    
    return obj_det_match_tuple, unmatched_obj_list, unmatched_det_list

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Define pairing update functions

# .....................................................................................................................

def update_objects_with_detections(object_dict, detection_ref_list,
                                   fallback_function, max_match_x_dist, max_match_y_dist,
                                   current_snapshot_metadata,
                                   current_frame_index, current_time_sec, current_datetime):
        
    # Get a list of object ids, so we can force consistent dictionary lookups
    obj_ref_list = [each_obj for each_obj in object_dict.values()]
    
    # Find object-to-detection matches (and unmatched entries, by index into their respective lists)
    obj_det_match_tuple_list, unmatched_obj_idx_list, unmatched_det_idx_list = \
    pair_objects_to_detections(obj_ref_list, detection_ref_list, 
                               fallback_function, max_match_x_dist, max_match_y_dist)
    
    # Update objects using detection data
    for each_obj_idx, each_det_idx in obj_det_match_tuple_list:
        
        # Grab object references for convenience
        object_ref = obj_ref_list[each_obj_idx]
        detection_ref = detection_ref_list[each_det_idx]
        
        # Update each object using the detection object data
        object_ref.update_from_detection(detection_ref, current_snapshot_metadata,
                                         current_frame_index, current_time_sec, current_datetime)
        
    # Convert unmatched index lists to a list of object ids and a list of detection objects
    unmatched_object_id_list = [obj_ref_list[each_idx].full_id for each_idx in unmatched_obj_idx_list]
    unmatched_detection_ref_list = [detection_ref_list[each_idx] for each_idx in unmatched_det_idx_list]        
    
    return unmatched_object_id_list, unmatched_detection_ref_list

# .....................................................................................................................

def pair_objects_to_detections(object_ref_list, detection_ref_list, 
                               fallback_matching_function, max_match_x_dist, max_match_y_dist):
        
    # Bail if we have zero of either set since we won't be able to match anything
    num_objs = len(object_ref_list)
    num_dets = len(detection_ref_list)
    if num_objs == 0 or num_dets == 0:               
        obj_det_match_tuple_list = []
        unmatched_objects_list = list(range(num_objs))
        unmatched_detections_list = list(range(num_dets))
        return obj_det_match_tuple_list, unmatched_objects_list, unmatched_detections_list
    
    # Calculate x/y scaling so that the distance matrix encodes max distances
    # (By scaling this way, we can say that objects that are within 0 < x (or y) < 1.0 are in matching range)
    x_scale = 1 / max_match_x_dist if max_match_x_dist > 0 else 1E10
    y_scale = 1 / max_match_y_dist if max_match_y_dist > 0 else 1E10
    
    # Get object/detection positioning for matching
    obj_xys, det_xys = build_obj_det_match_xys(object_ref_list, detection_ref_list)
    obj_det_sqdist_matrix = calculate_squared_distance_pairing_matrix(obj_xys, det_xys, x_scale, y_scale)
    
    # Try to find a unique mapping from (previous) objects to (current) detections
    unique_mapping, obj_det_match_tuple_list, unmatched_objects_list, unmatched_detections_list = \
    naive_object_detection_match(obj_det_sqdist_matrix)
    
    # If the unique mapping failed, then try using a (slower) method that guarantees a unique pairing
    if not unique_mapping:
        
        #print("*" * 32, "NON UNIQUE MAPPING!", "*" * 32, sep="\n")
        
        # Retry the object-to-detection match using a slower approach that will generate unique pairings
        obj_det_match_tuple_list, unmatched_objects_list, unmatched_detections_list = \
        fallback_matching_function(obj_det_sqdist_matrix)
        
    return obj_det_match_tuple_list, unmatched_objects_list, unmatched_detections_list

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Demo
    
if __name__ == "__main__":    
    
    cv2.destroyAllWindows()
    
    frame_size = 400
    frame_padding = 50
    
    num_examples = 10
    match_x_dist = 0.35
    match_y_dist = 0.35
    
    match_range_color = (45, 45, 45)
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
        num_objs, num_det = 2,3
        
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
        naive_frame = blank_frame.copy()
        unique_mapping, obj_det_match_tuple, unmatched_obj_list, unmatched_det_list = \
        naive_object_detection_match(ObyD_sqdist_matrix)
        match_color = (255, 255, 0) if unique_mapping else (0, 0, 255)
        for each_obj_idx, each_det_idx in obj_det_match_tuple:
            obj_pt = ro_px[each_obj_idx]
            det_pt = rd_px[each_det_idx]
            cv2.line(naive_frame, obj_pt, det_pt, match_color, 1, cv2.LINE_AA)
        # Draw match radius circle around all unmatched objects
        for each_obj_idx in unmatched_obj_list:
            obj_pt = ro_px[each_obj_idx]
            cv2.ellipse(naive_frame, obj_pt, (match_x_px, match_y_px), 0, 0, 360, match_range_color, 1, cv2.LINE_AA)
            
        # Print info for inspection
        obj_idxs, det_idxs = zip(*obj_det_match_tuple) if len(obj_det_match_tuple) > 0 else ([], [])
        letter_obj_match = [letter_lookup[each_obj_idx] for each_obj_idx in obj_idxs]
        uniq_obj_det_match_tuple = list(zip(letter_obj_match, det_idxs))
        letter_obj_unmatch = [letter_lookup[each_obj_idx] for each_obj_idx in unmatched_obj_list]
        print("", "",
              "NAIVE Match results",
              "Unique mapping found: {}".format(unique_mapping),
              "Obj-to_det matches:",
              *uniq_obj_det_match_tuple,
              "Unmatched objs: {}".format(letter_obj_unmatch),
              "Unmatched dets: {}".format(unmatched_det_list),
              sep="\n")
        cv2.imshow("NAIVE Match", naive_frame)
        cv2.moveWindow("NAIVE Match", 450, 200)
        
        
        # Draw greedy matches
        greed_frame = blank_frame.copy()
        obj_det_match_tuple, unmatched_obj_list, unmatched_det_list = \
        greedy_object_detection_match(ObyD_sqdist_matrix)
        match_color = (255, 255, 0)
        for each_obj_idx, each_det_idx in obj_det_match_tuple:
            obj_pt = ro_px[each_obj_idx]
            det_pt = rd_px[each_det_idx]
            cv2.line(greed_frame, obj_pt, det_pt, match_color, 1, cv2.LINE_AA)
        # Draw match radius circle around all unmatched objects
        for each_obj_idx in unmatched_obj_list:
            obj_pt = ro_px[each_obj_idx]
            cv2.ellipse(greed_frame, obj_pt, (match_x_px, match_y_px), 0, 0, 360, match_range_color, 1, cv2.LINE_AA)
        
        # Print info for inspection
        obj_idxs, det_idxs = zip(*obj_det_match_tuple) if len(obj_det_match_tuple) > 0 else ([], [])
        letter_obj_match = [letter_lookup[each_obj_idx] for each_obj_idx in obj_idxs]
        greed_obj_det_match_tuple = list(zip(letter_obj_match, det_idxs))
        letter_obj_unmatch = [letter_lookup[each_obj_idx] for each_obj_idx in unmatched_obj_list]
        print("", 
              "GREEDY Match results",
              "Obj-to_det matches:",
              *greed_obj_det_match_tuple,
              "Unmatched objs: {}".format(letter_obj_unmatch),
              "Unmatched dets: {}".format(unmatched_det_list),
              sep="\n")
        cv2.imshow("GREED Match", greed_frame)
        cv2.moveWindow("GREED Match", 900, 200)
        
        
        # Draw pathmin matches
        exile_frame = blank_frame.copy()
        obj_det_match_tuple, unmatched_obj_list, unmatched_det_list = \
        pathmin_object_detection_match(ObyD_sqdist_matrix)
        match_color = (255, 255, 0)
        for each_obj_idx, each_det_idx in obj_det_match_tuple:
            obj_pt = ro_px[each_obj_idx]
            det_pt = rd_px[each_det_idx]
            cv2.line(exile_frame, obj_pt, det_pt, match_color, 1, cv2.LINE_AA)
        # Draw match radius circle around all unmatched objects
        for each_obj_idx in unmatched_obj_list:
            obj_pt = ro_px[each_obj_idx]
            cv2.ellipse(exile_frame, obj_pt, (match_x_px, match_y_px), 0, 0, 360, match_range_color, 1, cv2.LINE_AA)
        
        # Print info for inspection
        obj_idxs, det_idxs = zip(*obj_det_match_tuple) if len(obj_det_match_tuple) > 0 else ([], [])
        letter_obj_match = [letter_lookup[each_obj_idx] for each_obj_idx in obj_idxs]
        greed_obj_det_match_tuple = list(zip(letter_obj_match, det_idxs))
        letter_obj_unmatch = [letter_lookup[each_obj_idx] for each_obj_idx in unmatched_obj_list]
        print("", 
              "PATHMIN Match results",
              "Obj-to_det matches:",
              *greed_obj_det_match_tuple,
              "Unmatched objs: {}".format(letter_obj_unmatch),
              "Unmatched dets: {}".format(unmatched_det_list),
              sep="\n")
        
        cv2.imshow("PATHMIN Match", exile_frame)
        cv2.moveWindow("PATHMIN Match", 1350, 200)
        
        
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
        
        tp1 = perf_counter()
        for k in range(num_iter):
            obj_det_match_tuple, unmatched_obj_list, unmatched_det_list = \
            pathmin_object_detection_match(ObyD_sqdist_matrix)
        tp2 = perf_counter()
        
        print("")
        print("Length of ro, rd: {} x {}".format(len(ro), len(rd)))
        print("UNIQUE MAPPING:", unique_mapping)
        print("PER ITERATION TIMING:")
        print("  NAIVE TIME:", "{:.3f} ms".format(1000 *(tn2-tn1) / num_iter))
        print(" GREEDY TIME:", "{:.3f} ms".format(1000 *(tg2-tg1) / num_iter))
        print("PATHMIN TIME:", "{:.3f} ms".format(1000 *(tp2-tp1) / num_iter))




# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap
