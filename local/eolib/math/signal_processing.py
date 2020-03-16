#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Sep 17 16:22:52 2018

@author: eo
"""


# ---------------------------------------------------------------------------------------------------------------------
#%% Imports

from itertools import tee

import numpy as np


# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes




# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

# .....................................................................................................................

def pairs_of(input_iterable):
    
    ''''
    Function intended as a for-loop helper.
    Takes in an iterable of elements and returns an iterable of pairs of elements, from the original inputs
    
    Example:
         input: [1,2,3,4,5]
        output: [(1, 2), (2, 3), (3, 4), (4, 5)]
    
    Taken from python itertools recipes:
        https://docs.python.org/3/library/itertools.html
    '''
    
    # Duplicate the input iterable, then advance one copy forward and combine to get sequential pairs of the input
    iter_copy1, iter_copy2 = tee(input_iterable)
    next(iter_copy2, None)
    
    return zip(iter_copy1, iter_copy2)

# .....................................................................................................................  

def create_smoothing_kernel(num_samples = 3, window = "auto"):
    
    '''
    Function which generates smoothing kernels with a given number of samples for FIR filtering
    Available window types:
        "rectangle", "triangle", "blackman", "auto"
        
    The auto window will pick from among the other window types, depending on the given number of samples    
    '''
    
    # Can't do anything to a null value
    if num_samples is None:
        return None
    
    # Make sure a valid window type is used (and print these out, since it would be mysterious otherwise)
    valid_window_types = ["auto", "rectangle", "triangle", "blackman"]
    if window not in valid_window_types:
        print("")
        print("Window supplied is not valid:", window)
        print("Must be one of the following:")
        for eachWindow in valid_window_types:
            print("  -", eachWindow)
            
            
    # Make sure number of samples is odd
    num_samples = force_to_odd(num_samples, force_downward = True, zero_maps_to = 1)
    
    if window == "auto":
        if num_samples < 7:
            window = "rectangle"
        elif num_samples < 21:
            window = "triangle"
        else:
            window = "blackman"
    
    if window == "rectangle":    
        return [1/num_samples] * num_samples
    
    if window == "triangle":
        
        # Scale factor is calculated so that the result matches a rectangle convolved with itself!
        count_seq = np.arange(0, num_samples)
        center_shift = (num_samples - 1) / 2
        scale_factor = (num_samples + 1) / 2
        triangle_seq = 1 - abs(count_seq - center_shift) / scale_factor
        norm_values = triangle_seq / sum(triangle_seq)
        
        return norm_values
    
    if window == "blackman":
    
        a0 = 0.42
        a1 = 0.5
        a2 = 0.08
        
        n = np.arange(0, num_samples)
        denom = num_samples - 1        
        
        blackman_seq = a0 - a1*np.cos(2*np.pi*n/denom) + a2*np.cos(4*np.pi*n/denom)
        norm_values = blackman_seq/sum(blackman_seq)
        
        return norm_values
        
# .....................................................................................................................    
    
def safe_smooth(data, kernel, same_size_out = True, data_type_out = np.float32, extrapolation_factor = 2,
                restore_first_value = False,
                restore_last_value = False):
    
    # If no kernel is provided, just return the data as-is
    if kernel is None:
        return data
    
    # Make sure the kernel isn't too big to use on this data
    kernel_size = len(kernel)
    data_len = len(data)
    if data_len < 2*kernel_size:
        return data
    
    # Figure out how many extrapolated values are needed (on both sides!)
    num_ext = int((kernel_size - 1)/2)
    
    # Calculate 'safe' extrapolated values to get back original data length
    smooth_data = np.convolve(data, kernel, mode = "valid")
    if same_size_out:
        smooth_out = list(smooth_data)
        for k in range(num_ext):
            new_front = smooth_out[0] + (smooth_out[0] - smooth_out[1])/extrapolation_factor
            new_back = smooth_out[-1] + (smooth_out[-1] - smooth_out[-2])/extrapolation_factor
            smooth_out = [new_front] + smooth_out + [new_back]
        
        # Restore the first/last values (with no smoothing) if desired
        if restore_first_value:
            smooth_out[0] = data[0]        
        if restore_last_value:
            smooth_out[-1] = data[-1]
            
        return data_type_out(smooth_out)
    
    return data_type_out(smooth_data)

# .....................................................................................................................
    
def safe_smooth_2d(data, kernel, same_size_out = True, data_type_out = np.float32, extrapolation_factor = 2,
                   restore_first_value = False,
                   restore_last_value = False):
    
    data_a_1d = data[:,0]
    smooth_data_a = safe_smooth(data_a_1d, kernel, same_size_out, data_type_out, extrapolation_factor, 
                                restore_first_value, restore_last_value)
    
    data_b_1d = data[:,1]
    smooth_data_b = safe_smooth(data_b_1d, kernel, same_size_out, data_type_out, extrapolation_factor, 
                                restore_first_value, restore_last_value)
    
    smooth_data = np.vstack((smooth_data_a, smooth_data_b)).T
    
    return smooth_data

# .....................................................................................................................

def central_diff(data, same_size_out = True, data_type_out = np.float32):
    
    # Special case when data is smaller than difference kernel (i.e. fewer than 3 points), return all zeros
    try: data[2]
    except IndexError: return data_type_out([0] * len(data))
    
    # Apply central difference using convolution (might be more efficient ways to do this!)
    kernel = [1/2, 0, -1/2]
    dd = np.convolve(data, kernel, mode='valid')
    
    # Add missing data end-points by using forward/backward differences
    if same_size_out:
        dd0 = data[1] - data[0]
        ddn = data[-1] - data[-2]    
        dd_out = [dd0] + list(dd) + [ddn]         
        return data_type_out(dd_out)
    
    return data_type_out(dd)

# .....................................................................................................................

# Function which takes any integer and forces it to the nearest (lower by default) odd number
def force_to_odd(input_value, force_downward = True, zero_maps_to = 0):
    
    # Can't do anything to a null value
    if input_value is None:
        return None
    
    # Special case, we don't want negative numbers...
    if input_value <= 0:
        return zero_maps_to
    
    # Determine whether if the number is even/odd, then shift it depending of force direction
    one_if_even_zero_if_odd = (1 - input_value % 2)
    if force_downward:
        return input_value - one_if_even_zero_if_odd
    else:
        return input_value + one_if_even_zero_if_odd

# .....................................................................................................................

# Function which maps all integers to odd values (not the same as forcing to an odd value!)
def map_ints_to_odds(input_value, lowest_valid_input = 0, one_maps_to = 1):
    
    # Can't do anything to a null value
    if input_value is None:
        return None
    
    # Convert to a null output if we don't pass the lowest valid input
    if input_value < lowest_valid_input:
        return None
    
    # Transformation converts:
    # 1 -> one_maps_to
    # 2 -> one_maps_to + 2
    # 3 -> one_maps_to + 4, etc.
    odd_conversion = 2*(input_value - 1)
    odd_conversion = max(0, odd_conversion)
    output_value = odd_conversion + one_maps_to
    
    # Return odd version of input
    return output_value

# .....................................................................................................................

# Function which takes in any integer and create a tuple of odd numbers
def odd_tuplify(input_value, lowest_valid_input = 0, one_maps_to = 1):
    
    odd_value = map_ints_to_odds(input_value, lowest_valid_input = lowest_valid_input, one_maps_to = one_maps_to)
    
    if odd_value is None:
        return None
    
    tuplified = (odd_value, odd_value)
    return tuplified

# .....................................................................................................................

def windowed_data(input_1d_array, window_length, return_edge_windows = True):
    
    '''
    Takes a numpy (1D) array and returns a matrix, where each row can be thought of as a subset of the original
    array, with length (i.e. number of columns) set by the 'window_length' parameter
    
    If return_edge_windows is True, a list of the incomplete windows at the edges will be provided
    
    Applying a (linear) function across all windows is equivalent to performing a convolution/correlation.
    However, the resulting windows allow for non-linear data transformations, such as median/min/max evaluations.
    
    Based on:
        https://stackoverflow.com/questions/40084931/
        taking-subarrays-from-numpy-array-with-given-stride-stepsize/40085052#40085052
    
    '''
    
    # Convert input to a numpy array if needed
    if type(input_1d_array) in {tuple, list}:
        input_1d_array = np.array(input_1d_array)
    
    # Make sure the window length is odd
    odd_window_length = force_to_odd(window_length, force_downward = True)
    
    num_full_windows = 1 + (len(input_1d_array) - odd_window_length)
    num_bytes_per_entry = input_1d_array.strides[0]    
    windowed_data = np.lib.stride_tricks.as_strided(input_1d_array, 
                                                    shape = (num_full_windows, odd_window_length), 
                                                    strides = (num_bytes_per_entry, num_bytes_per_entry))
    
    # Return no edge windows by default, otherwise, extract the appropriate edge points for return data
    left_edge_windows = []
    right_edge_windows = []
    if return_edge_windows:
        
        # We'll have as many edge (left + right) windows as there are off-center points in our window
        num_edge_windows = int((odd_window_length - 1) / 2)
        for k in range(num_edge_windows):
            
            # Extract each set of points for the left/right windows
            sub_window_length = 1 + num_edge_windows + k
            new_left_window = input_1d_array[:sub_window_length]
            new_right_window = input_1d_array[(-sub_window_length):]
            
            # Build up our list of edge windows
            left_edge_windows.append(new_left_window)
            right_edge_windows.append(new_right_window)
            
    return windowed_data, left_edge_windows, right_edge_windows

# .....................................................................................................................
    
def median_filter_1d(input_1d_array, window_length):
    
    # Make sure the window length is odd
    odd_window_length = force_to_odd(window_length, force_downward = True)
    
    # Split the data into windows for applying median filter
    window_data, left_edges, right_edges = windowed_data(input_1d_array, odd_window_length)
    
    # Perform median calculations, then combine results
    left_medians = [np.median(each_left_window) for each_left_window in left_edges]
    right_medians = [np.median(each_right_window) for each_right_window in right_edges]
    body_medians = np.median(window_data, axis = 1)
    return np.concatenate((left_medians, body_medians, right_medians))

# .....................................................................................................................
    
def minwindow_filter_1d(input_1d_array, window_length):
    
    # Make sure the window length is odd
    odd_window_length = force_to_odd(window_length, force_downward = True)
    
    # Split the data into windows
    window_data, left_edges, right_edges = windowed_data(input_1d_array, odd_window_length)
    
    # Find minimums, then combine results
    left_mins = [np.min(each_left_window) for each_left_window in left_edges]
    right_mins = [np.min(each_right_window) for each_right_window in right_edges]
    body_mins = np.min(window_data, axis = 1)
    return np.concatenate((left_mins, body_mins, right_mins))

# .....................................................................................................................
    
def maxwindow_filter_1d(input_1d_array, window_length):
    
    # Make sure the window length is odd
    odd_window_length = force_to_odd(window_length, force_downward = True)
    
    # Split the data into windows
    window_data, left_edges, right_edges = windowed_data(input_1d_array, odd_window_length)
    
    # Find maximums, then combine results
    left_maxs = [np.max(each_left_window) for each_left_window in left_edges]
    right_maxs = [np.max(each_right_window) for each_right_window in right_edges]
    body_maxs = np.max(window_data, axis = 1)
    return np.concatenate((left_maxs, body_maxs, right_maxs))

# .....................................................................................................................

def sparse_windowed_data(input_1d_array, num_windows):
    
    ''' 
    Function for returning a list of start/end indices which represent sequential windows into a given data set
    For example:
        
        sparse_windowed_data([1,2,3,4,5,6,7,8,9], 3) -> [[0, 3], [3, 6], [6, 9]]
        
    The resulting indices can be used to grab sequences of data from the original list for 'summary' processing
    (e.g. taking the mean of sequential blocks to generate a moving average estimate of a signal)
    '''
    
    num_points = len(input_1d_array)
    sample_indices = np.int32(np.round(np.linspace(0, num_points, num_windows + 1)))
    
    return np.vstack((sample_indices[:-1], sample_indices[1:])).T.tolist()

# .....................................................................................................................
    
def approx_moving_average(input_1d_array, num_approximation_regions = 12):
    
    '''
    Function which calculates an approximate moving average for a signal over a set of distinct regions
    '''
    
    # Get a set of data windows over which we'll get mean values
    data_window_indices = sparse_windowed_data(input_1d_array, num_approximation_regions)
    
    # Initialize output array
    averaged_data = np.zeros_like(input_1d_array)
    
    # Loop over all data windows and fill output array with windowed mean
    for start_idx, end_idx in data_window_indices:
        data_window = input_1d_array[start_idx:end_idx]
        averaged_data[start_idx:end_idx] = np.mean(data_window)
    
    return averaged_data

# .....................................................................................................................
    
def staircase_envelope(input_1d_array, num_approximation_regions = 12):
    
    ''' 
    Function which generates a coarse approximation of min/max envelope of a signal
    Increasing the number of approximation regions reduces the coarseness, but may overfit the data waveform
    
    Returns:
        min_envelope, max_envelope
    
    The return values are arrays with the same number of elements as the input array
    '''
    
    # Get a set of data windows over which we'll get the min/max envelopes
    data_window_indices = sparse_windowed_data(input_1d_array, num_approximation_regions)
    
    # Initialize outputs
    max_envelope = np.zeros_like(input_1d_array)
    min_envelope = np.zeros_like(input_1d_array)
    
    # Loop through each window of data and calculate the min/max values
    for start_idx, end_idx in data_window_indices:
        
        # Get each data window and record min/max values
        data_window = input_1d_array[start_idx:end_idx]
        min_envelope[start_idx:end_idx] = np.min(data_window)
        max_envelope[start_idx:end_idx] = np.max(data_window)
    
    return min_envelope, max_envelope

# .....................................................................................................................
    
def envelope_normalization(input_1d_array, num_approximation_regions = 12):
    
    '''
    Function which takes a 'bumpy' 1D input signal, splits it into multiple regions 
    and normalizes, 0.0-1.0 based on local min/max values each region separately
    Intended to help remove difting mean/scaling values from a signal to ease further processing
    Returns:
        normalized_data
    
    The output array has the same length as the input and takens on values between 0.0 and 1.0
    '''
    
    # Get a set of data windows over which we'll calculate the min/max envelopes used for normalization
    data_window_indices = sparse_windowed_data(input_1d_array, num_approximation_regions)
    
    # Initialize output array
    normalized_data = np.zeros_like(input_1d_array)
    
    # Loop through and normalize each window
    for start_idx, end_idx in data_window_indices:
        
        # Get each data window and record min/max values
        data_window = input_1d_array[start_idx:end_idx]
        min_value = np.min(data_window)
        max_value = np.max(data_window)
        mm_delta = max_value - min_value
        
        # Deal with divide by zero errors
        if mm_delta <= 0:
            mm_delta = 1
        
        # Normalize each window
        normalized_data[start_idx:end_idx] = (data_window - min_value) / mm_delta
            
    return normalized_data

# .....................................................................................................................

def value_hysteresis_filter(input_1d_array, falling_threshold, rising_threshold, initial_state = None):
    
    ''' Slow non-vectorized implementation of high/low thresholding '''
    
    # Change state after passing rising/falling threshold depending on which is higher
    rise_state = True #rising_threshold > falling_threshold
    fall_state = not rise_state
    
    # Set the initial state if needed
    if initial_state is None:
        rise_dist = np.abs(input_1d_array[0] - rising_threshold)
        fall_dist = np.abs(input_1d_array[0] - falling_threshold)
        initial_state = fall_state if fall_dist < rise_dist else rise_state
    
    output_array = np.full_like(input_1d_array, initial_state, dtype=np.bool)
    for data_idx, each_value in enumerate(input_1d_array[1:], 1):
        
        
        prev_state = output_array[data_idx - 1]
        prev_value = input_1d_array[data_idx - 1]
        
        
        # Carry previous state forward by default
        output_array[data_idx] = prev_state
        
        if prev_state == fall_state:
            is_rising = (each_value > prev_value)
            above_threshold = (each_value >= rising_threshold)
            if is_rising and above_threshold:
                output_array[data_idx] = True
        
        elif prev_state == rise_state:
            is_falling = (each_value < prev_value)
            below_threshold = (each_value <= falling_threshold)
            if is_falling and below_threshold:
                output_array[data_idx] = False
        
    return output_array

# .....................................................................................................................

def fill_boolean_signal_gaps(input_1d_boolean, sample_gap_threshold, fill_high_gaps = True,
                             fill_start_gaps = False, fill_end_gaps = False):
    
    '''
    (slow non-vectorized)
    Function which is used to remove spurious noise from boolean signals by 
    'filling in' sections where the signal may be (erroneously) on/off for a short time.
    
    Inputs:
        input_1d_boolean -> A numpy array of boolean values (or 0/1 values)
        
        sample_gap_threshold -> Any gap less than this number of samples will be filled in
        
        fill_high_gaps -> If true, the function fills in gaps between high sections of the the signal
                          if false, gaps betwen low sections are filled in.
                          Call this function multiple times in sequence toggling this flag to fill highs & lows!
                          
        fill_start_gaps -> If true, the first data points will be considered as a possible gap and can be filled in
        
        fill_end_gaps -> If true, the final data points will be considered as a possible gap and can be filled in
        
    Example:
        Let sample_gap_threshold = 3
                  fill_high_gaps = True
                 fill_start_gaps = False
                   fill_end_gaps = True
                input_1d_boolean = [0, 0, 1, 1, 1, 1, 0 , 0 , 1, 1, 0, 0, 0, 0, 1, 0 ]               
                Then the result -> [0, 0, 1, 1, 1, 1, 1*, 1*, 1, 1, 0, 0, 0, 0, 1, 1*]
                (where * indicates values filled in by the function)
    '''
    
    # For clarity
    need_to_fill = lambda start, end: (end - start) <= sample_gap_threshold
    
    # Set up some convenient variables to deal with low vs. high gaps
    gap_value = (not fill_high_gaps)
    fill_value = fill_high_gaps
    gap_value_idxs = np.where(input_1d_boolean == gap_value)[0]
    
    # If there are no gaps, we're already done!
    if len(gap_value_idxs) < 1:
        return input_1d_boolean
    
    # Initialize a copy of the output, which we'll modify (i.e. fill gaps) as needed
    output_array = input_1d_boolean.copy()
    
    # Set the first target index to check for gaps, accounting for starting gaps
    first_gap_idx = 0
    if (gap_value_idxs[0] == 0) and (not fill_start_gaps):
        first_gap_idx = np.argmax(input_1d_boolean) if fill_high_gaps else np.argmin(input_1d_boolean)
    
    # If the first gap index is outside the gap value index list, then there is no gap to fill!
    if first_gap_idx >= len(gap_value_idxs):
        return output_array
    
    # Initialize start/end indices for each gap we check
    start_idx = gap_value_idxs[first_gap_idx]
    end_idx = start_idx
    
    # Loop through the indices of every value that might need to be fill, and check for 'small' gaps
    for each_idx in gap_value_idxs[first_gap_idx:]:
        
        # If the current gap index if ahead of the target end index, we've hit a signal toggle point
        if each_idx > end_idx:
            
            # Check if there's a small enough gap betwene the start & end index that we should fill
            if need_to_fill(start_idx, end_idx):
                output_array[start_idx:end_idx] = fill_value
            
            # Reset the start index
            start_idx = each_idx
        
        # Update the target end index
        end_idx = 1 + each_idx
    
    # Handle end edge case, if we need to fill end gaps
    if fill_end_gaps and (end_idx >= (len(input_1d_boolean) - 1)):
        if need_to_fill(start_idx, end_idx):
            output_array[start_idx:end_idx] = fill_value
    
    return output_array

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Demo

if __name__ == "__main__":

    import matplotlib.pyplot as plt
    kernel_size = 27
    rr = create_smoothing_kernel(kernel_size, "rectangle")
    tt = create_smoothing_kernel(kernel_size, "triangle") 
    bb = create_smoothing_kernel(kernel_size, "blackman")
    
    # Example of kernels
    plt.figure("Kernels")
    plt.plot(rr)
    plt.plot(tt)
    plt.plot(bb)


    # Filter comparison
    t = np.linspace(0, 1, 500)
    noise_mag = 2
    clean_signal = np.sin(2*np.pi*(11)*t) + np.cos(2*np.pi*(7)*t) + np.sin(2*np.pi*(3)*t)    
    noisy_signal = clean_signal + np.random.rand(len(clean_signal))*(noise_mag) - noise_mag/2
    min_val, max_val = np.floor(min(clean_signal)), np.ceil(max(clean_signal))
    
    plt.figure("Clean Signal")
    plt.plot(t, noisy_signal)
    plt.plot(t, clean_signal)
    plt.ylim([min_val, max_val])
    
    # Run filter comparisons
    n_offset = int((kernel_size - 1)/2)
    idx = t[n_offset:-n_offset]
    
    plt.figure("Rectangle Performance")
    plt.plot(idx, np.convolve(noisy_signal, rr, mode="valid"))
    plt.plot(t, clean_signal)
    plt.ylim([min_val, max_val])    
    
    plt.figure("Triangle Performance")
    plt.plot(idx, np.convolve(noisy_signal, tt, mode="valid"))
    plt.plot(t, clean_signal)
    plt.ylim([min_val, max_val])
    
    plt.figure("Blackman Performance")
    plt.plot(idx, np.convolve(noisy_signal, bb, mode="valid"))
    plt.plot(t, clean_signal)
    plt.ylim([min_val, max_val])

    plt.figure("Blackman Safe Performance")
    plt.plot(t, safe_smooth(noisy_signal, bb, extrapolation_factor= 2))
    plt.plot(t, clean_signal)
    plt.ylim([min_val, max_val])

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap

