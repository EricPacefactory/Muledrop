#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Jul 10 14:56:55 2020

@author: eo
"""


# ---------------------------------------------------------------------------------------------------------------------
#%% Imports

import cv2
import numpy as np

from collections import deque


# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes


class Frame_Deck:
    
    # .................................................................................................................
    
    def __init__(self, max_deck_length):
        
        ''' Used for rolling storage of frame data. Mainly intended for use with frame differencing or summing '''
        
        # Initialize the deck and store max length for reference
        self.deck = deque([], maxlen = max_deck_length)
        self.max_length = max_deck_length
    
    # .................................................................................................................
    
    def __repr__(self):        
        return "Frame Deck ({} / {} entries)".format(self.length, self.max_length)
    
    # .................................................................................................................
    
    def __len__(self):
        return self.length
    
    # .................................................................................................................
    
    @property
    def length(self):
        return len(self.deck)
    
    # .................................................................................................................
    
    @property
    def last_index(self):
        return self.length - 1
    
    # .................................................................................................................
    
    def update_max_length(self, new_max_length, *, clear_on_resize = True):
        
        '''
        Function used to update the max length setting of the frame deck, after initialization
        Mostly intended for optimizing RAM usage by reducing the deck to a minimum required length,
        which may not be known until after initialization
        
        Inputs:
            new_max_length -> (Integer) New max length to use for the frame deck
            
            clear_on_resize -> (Boolean) If true, the contents of the existing deck will be cleared after
                               resizing the deck. Otherwise, the old data will be kept, but there may be
                               missing data or empty entries in the deck due to change in max size!
        
        Outputs:
            Nothing!
        '''
        
        # First create an empty deque with the new max length
        new_deck = deque([], maxlen = new_max_length)
        
        # If we're not clearing, we need to take frames from the old deck and move them into the new one
        if not clear_on_resize:
            old_deck_length = self.length
            for k in range(old_deck_length):
                frame_from_old_deck = self.read_from_oldest(k)
                new_deck.append(frame_from_old_deck)
        
        # Update internal record of max length & deck
        self.new_max_length = new_max_length
        self.deck = new_deck
        
        return
    
    # .................................................................................................................
    
    def fill_with_frame(self, frame, fill_with_copys = True):
        
        '''
        Function used to initialize the entire deck with the given frame data
        
        Inputs:
            frame -> (Image data) The frame to fill the deck with
            
            fill_width_copys -> (Boolean) If True, the provided frame will be copied for each entry into the
                                deck. If the frame data will not be modified,
                                this can be set to False for improved performance
        
        Outputs:
            Nothing!
        '''
        
        self.clear_deck()
        if fill_with_copys:
            for k in range(self.max_length):
                self.deck.appendleft(frame.copy())
        else:
            for k in range(self.max_length):
                self.deck.appendleft(frame)
        
        return
    
    # .................................................................................................................
    
    def fill_with_blanks_like_frame(self, frame, fill_with_copys = False):
        
        '''
        Function used to initialize the deck with blank frames that have the same shape/type as the given frame
        
        Inputs:
            frame -> (Image data) A frame which will be used as a reference for creating
                     blank frames (i.e. all zeros) with the same shape/type that will be used to fill the deck
            
            fill_with_copys -> (Boolean) If True, the blanks will be copied for each entry into the
                               deck. If the blank frame data will not be modified,
                               this can be set to False for improved performance
        
        Outputs:
            Nothing!
        '''
        
        blank_frame = np.zeros_like(frame)
        self.fill_with_frame(blank_frame, fill_with_copys)
        
        return
    
    # .................................................................................................................
    
    def fill_with_blank_shape(self, frame_shape, data_type = np.uint8, fill_with_copys = False):
        
        '''
        Function used to initialize the deck with blank frames based on a given shape and data type
        
        Inputs:
            frame_shape -> (Tuple) A tuple representing the desired frame shape to fill the deck with
                           Normally, this tuple would either be (height, width, channel) or in the case of
                           single channel frames (e.g. binary or grayscale), it would just be (height, width)
            
            fill_with_copys -> (Boolean) If True, the blanks will be copied for each entry into the
                               deck. If the blank frame data will not be modified,
                               this can be set to False for improved performance
        
        Outputs:
            Nothing!
        '''
        
        blank_frame = np.zeros(frame_shape, dtype = data_type)
        self.fill_with_frame(blank_frame, fill_with_copys)
        
        return
    
    # .................................................................................................................
    
    def clear_deck(self):
        
        ''' Function used to empty all contents of the frame deck '''
        
        self.deck.clear()
    
    # .................................................................................................................
    
    def add_to_deck(self, frame):
        
        ''' Function used to add new frame data to the deck '''
        
        self.deck.appendleft(frame)
    
    # .................................................................................................................
    
    def read_from_newest(self, relative_index = 0):
        
        '''
        Function used to read frames from the deck, relative to the 'newest' data
        
        Inputs:
            relative_index -> (Integer) Index of frame data to read,
                              intepretted as being relative to the newest frame data
                              For example, an index of 0 will read the newest frame,
                              while an index of 1 would read the 'previous' frame
        
        Outputs:
            frame_data
        '''
        
        new_idx = relative_index
        return self.deck[new_idx]
    
    # .................................................................................................................
    
    def read_from_oldest(self, relative_index = 0):
        
        '''
        Function used to read frames from the deck, relative to the 'oldest' data
        
        Inputs:
            relative_index -> (Integer) Index of frame data to read,
                              intepretted as being relative to the oldest frame data
                              For example, an index of 0 will read the oldest frame,
                              while an index of 1 would read the second oldest frame etc.
        
        Outputs:
            frame_data
        '''
        
        old_idx = self.last_index - relative_index
        return self.deck[old_idx]
    
    # .................................................................................................................
    
    def absdiff_from_deck(self, difference_depth = 1):
        
        '''
        Function used to calculate the absolute difference between the newest frame in the deck and
        some older frame in the deck. Note that if the older frame isn't in the deck already,
        a blank (all zeros) frame will be returned instead, with the same shape as the newest frame
        
        Inputs:
            difference_depth -> (Integer) The index of the frame to use for differencing with the first frame
        
        Outputs:
            absolute_frame_difference
        '''
        
        # Take difference with some simple error handling
        newest_frame = self.read_from_newest(0)
        try:
            previous_frame = self.read_from_newest(difference_depth)
            absolute_frame_difference = cv2.absdiff(newest_frame, previous_frame)
            
        except (IndexError, cv2.error):
            absolute_frame_difference = np.zeros_like(newest_frame)
        
        return absolute_frame_difference
    
    # .................................................................................................................
    
    def sum_from_deck_float32(self, num_frames_to_sum):
        
        '''
        Function used to add up all pixel values from a number of frames in the deck
        
        Inputs:
            num_frames_to_sum -> (Integer) The number of frames to sum together,
                                 starting from the newest frame in the deck
        
        Outputs:
            summed_frame (float32 image data)
        '''
        
        # Gather all the frames needed for summing
        frame_list = [self.read_from_newest(each_idx) for each_idx in range(num_frames_to_sum)]
        
        # Sum up all frames in float format so we avoid overflow
        summed_frame = np.sum(frame_list, axis = 0, dtype = np.float32)
        
        return summed_frame
    
    # .................................................................................................................
    
    def sum_from_deck_uint8(self, num_frames_to_sum):
        
        '''
        Function used to add up all pixel values from a number of frames in the deck
        Note that the returned result will be forced to have values between 0 and 255, and be of type uint8!
        
        Inputs:
            num_frames_to_sum -> (Integer) The number of frames to sum together, 
                                 starting from the newest frame in the deck
        
        Outputs:
            summed_frame (uint8 image data)
        '''
        
        # Force returned result to be a 'proper' uint8 image
        return np.uint8(np.clip(self.sum_from_deck_float32(num_frames_to_sum), 0, 255))
    
    # .................................................................................................................
    
    def modify_all(self, frame_modifier_callback):
        
        ''' Function used to apply a callback to all frames in the deck '''
        
        for each_idx, each_frame in enumerate(self.deck):
            self.deck[each_idx] = frame_modifier_callback(each_frame)
        
        return
    
    # .................................................................................................................
    
    def modify_one(self, deck_index, new_frame):
        
        '''
        Helper function which allows overwriting a specific frame in the deck
        Intended for use with 'iterate_all() function
        
        Inputs:
            deck_index -> (Integer) The deck index of the frame to modify
            
            new_frame -> (Image data) The new frame data to store in the target deck index
        
        Outputs:
            Nothing!
        '''
        
        self.deck[deck_index] = new_frame
    
    # .................................................................................................................
    
    def iterate_all(self):
        
        '''
        Function which returns an iterator over all frames along with the frame indices, starting with the newest
        Can be used to make modifications to all frames in the deck using the 'modify_one()' function
        or otherwise 'examine' all frames
        Example usage:
            for each_idx, each_frame in frame_deck.iterate_all():
                new_frame = each_frame + 1
                frame_deck.modify_one(each_idx, new_frame)
        '''
        
        for each_idx, each_frame in enumerate(self.deck):
            yield each_idx, each_frame
        
        return
    
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


