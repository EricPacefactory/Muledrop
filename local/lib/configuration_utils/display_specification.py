#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Sep 25 15:09:29 2019

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

# ---------------------------------------------------------------------------------------------------------------------
#%% Define base displays

class Display_Window_Specification:
    
    '''
    Base class for creating display specifications. 
    Note this object is not responsible for providing/updating displays! 
    (Those details are handled by UI provider -> local or web ui)
    
    This object is instead responsible for bundling all data needed to represent each display,
    as well as the function used to create the display image (given the stage outputs/configurable as inputs)
    '''
    
    # .................................................................................................................
    
    def __init__(self, name, layout_index, num_rows = 2, num_columns = 2, 
                 *, initial_display = False, drawing_control = None, max_wh = (800, 450)):
        
        # Store display specification, so we can use it to build displays as needed
        self.name = name
        self.initial_display = initial_display
        self.drawing_control = drawing_control
        self.max_wh = max_wh
        
        # Store layout information
        self.num_rows = num_rows
        self.num_cols = num_columns
        self.layout_index = layout_index
        
    # .................................................................................................................
    
    def __repr__(self):
        
        is_initial = (self.initial_display)
        has_drawing_control = (self.drawing_control is not None)
        
        repr_strs = ["Display Specification",
                     "  Window name: {}".format(self.name),
                     "  Is initial: {}".format(is_initial),
                     "  Has drawing control: {}".format(has_drawing_control)]
        
        return "\n".join(repr_strs)
    
    # .................................................................................................................
    
    def display(self, stage_outputs, configurable_ref, current_frame_index, current_time_sec, current_datetime):
        return stage_outputs.get("frame_capture").get("video_frame")
    
    # .................................................................................................................
    
    def to_json(self):        
        return {"name": self.name,
                "initial_display": self.initial_display,
                "drawing_control": self.drawing_control,
                "max_wh": self.max_wh,
                "num_rows": self.num_rows,
                "num_cols": self.num_cols,
                "layout_index": self.layout_index}
    
    # .................................................................................................................
    # .................................................................................................................


# =====================================================================================================================
# =====================================================================================================================


class Matched_Size_Display(Display_Window_Specification):
    
    '''
    Base class for creating displays that are resized to match a reference frame.
    Can be used directly or subclasses for cleanliness
    '''
    
    # .................................................................................................................
    
    def __init__(self, window_name, display_stage, display_name, reference_stage, reference_name,
                 layout_index, num_rows, num_columns, initial_display = False, 
                 interpolation_type = cv2.INTER_NEAREST):
        
        # Inherit from parent class
        super().__init__(window_name, layout_index, num_rows, num_columns, 
                         initial_display = initial_display, 
                         max_wh = None)
        
        # Store reference & display lookups
        self.display_stage = display_stage
        self.display_name = display_name
        self.reference_stage = reference_stage
        self.reference_name = reference_name
        self.interpolation_type = interpolation_type
        
    # .................................................................................................................
        
    def display(self, stage_outputs, configurable_ref, current_frame_index, current_time_sec, current_datetime):
        
        # Get display & reference frames
        reference_sized_frame = stage_outputs.get(self.reference_stage).get(self.reference_name)
        display_frame = stage_outputs.get(self.display_stage).get(self.display_name)
        
        # Get the size of the reference frame, so we can match the display frame to it
        display_height, display_width = reference_sized_frame.shape[0:2]
        
        return cv2.resize(display_frame, dsize = (display_width, display_height), 
                          interpolation = self.interpolation_type)
        
    # .................................................................................................................
    # .................................................................................................................
    

# ---------------------------------------------------------------------------------------------------------------------
#%% Input displays

class Input_Display(Display_Window_Specification):
    
    ''' Standard implementation for displaying the (raw) input video image '''
    
    # .................................................................................................................
    
    def __init__(self, layout_index, num_rows, num_columns, initial_display = False, max_wh = None,
                 window_name = "Input"):
        
        # Inherit from parent class
        super().__init__(window_name, layout_index, num_rows, num_columns, 
                         initial_display = initial_display, 
                         max_wh = max_wh)
        
    # .................................................................................................................
        
    def display(self, stage_outputs, configurable_ref, current_frame_index, current_time_sec, current_datetime):
        return stage_outputs.get("frame_capture").get("video_frame")
        
    # .................................................................................................................
    # .................................................................................................................
    
    
class Background_Display(Display_Window_Specification):
    
    ''' Standard implementation for displaying the background image '''
    
    # .................................................................................................................
    
    def __init__(self, layout_index, num_rows, num_columns, initial_display = False, max_wh = None,
                 window_name = "Background"):
        
        # Inherit from parent class
        super().__init__(window_name, layout_index, num_rows, num_columns, 
                         initial_display = initial_display, 
                         max_wh = max_wh)
        
    # .................................................................................................................
        
    def display(self, stage_outputs, configurable_ref, current_frame_index, current_time_sec, current_datetime):
        return stage_outputs.get("frame_capture").get("bg_frame")
        
    # .................................................................................................................
    # .................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Preprocessor displays

class Preprocessed_Display(Display_Window_Specification):
    
    ''' Standard implementation for displaying preprocessed frames '''
    
    # .................................................................................................................
    
    def __init__(self, layout_index, num_rows, num_columns, initial_display = False, max_wh = None,
                 window_name = "Preprocessed"):
        
        # Inherit from parent class
        super().__init__(window_name, layout_index, num_rows, num_columns, 
                         initial_display = initial_display, 
                         max_wh = max_wh)
        
    # .................................................................................................................
        
    def display(self, stage_outputs, configurable_ref, current_frame_index, current_time_sec, current_datetime):
        return stage_outputs.get("preprocessor").get("preprocessed_frame")
        
    # .................................................................................................................
    # .................................................................................................................


class Preprocessed_BG_Display(Display_Window_Specification):
    
    ''' Standard implementation for displaying the preprocessed background '''
    
    # .................................................................................................................
    
    def __init__(self, layout_index, num_rows, num_columns, initial_display = False, max_wh = None,
                 window_name = "Preprocessed Background"):
        
        # Inherit from parent class
        super().__init__(window_name, layout_index, num_rows, num_columns, 
                         initial_display = initial_display, 
                         max_wh = max_wh)
        
    # .................................................................................................................
        
    def display(self, stage_outputs, configurable_ref, current_frame_index, current_time_sec, current_datetime):
        return stage_outputs.get("preprocessor").get("preprocessed_bg_frame")
        
    # .................................................................................................................
    # .................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Frame processor displays

class Binary_Display(Matched_Size_Display):
    
    ''' Standard implementation for displaying the binary output image, after frame processing '''
    
    # .................................................................................................................
    
    def __init__(self, layout_index, num_rows, num_columns, initial_display = False):
        
        # Inherit from parent class
        super().__init__("Binary Output", 
                         "frame_processor", "binary_frame_1ch", 
                         "preprocessor", "preprocessed_frame",
                         layout_index, num_rows, num_columns, 
                         initial_display = initial_display)
        
    # .................................................................................................................
    # .................................................................................................................


class Filtered_Binary_Display(Matched_Size_Display):
    
    ''' Standard implementation for displaying the filtered binary image, after pixel filtering '''
    
    # .................................................................................................................
    
    def __init__(self, layout_index, num_rows, num_columns, initial_display = False):
        
        # Inherit from parent class
        super().__init__("Filtered Binary Output", 
                         "pixel_filter", "filtered_binary_frame_1ch", 
                         "preprocessor", "preprocessed_frame",
                         layout_index, num_rows, num_columns, 
                         initial_display = initial_display)
        
    # .................................................................................................................
    # .................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Detection displays

class Detection_Display(Display_Window_Specification):
    
    ''' Standard implementation for displaying detection objects '''
    
    # .................................................................................................................
    
    def __init__(self, layout_index, num_rows, num_columns, initial_display = False, max_wh = None,
                 window_name = "Detection",
                 show_outlines = True,
                 show_bounding_boxes = False,
                 line_color = (255, 255, 0)):
        
        # Inherit from parent class
        super().__init__(window_name, layout_index, num_rows, num_columns, 
                         initial_display = initial_display, 
                         max_wh = max_wh)
        
        # Store display configuration details
        self._show_outlines = show_outlines
        self._show_bounding_boxes = show_bounding_boxes
        self._line_color = line_color
        
    # .................................................................................................................
        
    def display(self, stage_outputs, configurable_ref, current_frame_index, current_time_sec, current_datetime):
        
        # Grab a copy of the color image that we can draw on
        detection_ref_list = stage_outputs["detector"]["detection_ref_list"]
        display_frame = stage_outputs.get("preprocessor").get("preprocessed_frame")        
        detection_frame = display_frame.copy()
        
        # Record frame sizing so we can draw normalized co-ordinate locations
        frame_h, frame_w = detection_frame.shape[0:2]
        frame_wh = np.array((frame_w - 1, frame_h - 1))
        
        for each_det in detection_ref_list:
            
            # Draw the blob outline
            if self._show_outlines:
                det_hull = np.int32(np.round(each_det.hull * frame_wh))
                cv2.polylines(detection_frame, [det_hull], True, self._line_color, 1, cv2.LINE_AA)
            
            # Draw the bounding box
            if self._show_bounding_boxes:
                tl, br = np.int32(np.round(each_det.tl_br * frame_wh))
                cv2.rectangle(detection_frame, tuple(tl), tuple(br), self._line_color, 2, cv2.LINE_4)
        
        return detection_frame
    
    # .................................................................................................................
    # .................................................................................................................


# =====================================================================================================================
# =====================================================================================================================

# ---------------------------------------------------------------------------------------------------------------------
#%% Tracking displays

class Tracked_Display(Display_Window_Specification):
    
    ''' Standard implementation for displaying tracked objects '''
    
    # .................................................................................................................
    
    def __init__(self, layout_index, num_rows, num_columns, initial_display = False, max_wh = None,
                 window_name = "Tracked",
                 show_ids = False,
                 show_outlines = True,
                 show_bounding_boxes = False,
                 show_trails = True,
                 show_decay = False,
                 line_color = (0, 255, 0)):
        
        # Inherit from parent class
        super().__init__(window_name, layout_index, num_rows, num_columns, 
                         initial_display = initial_display, 
                         max_wh = max_wh)
        
        # Store display configuration details
        self._show_ids = show_ids
        self._show_outlines = show_outlines
        self._show_bounding_boxes = show_bounding_boxes
        self._show_trails = show_trails
        self._show_decay = show_decay
        self._line_color = line_color
        
    # .................................................................................................................
        
    def display(self, stage_outputs, configurable_ref, current_frame_index, current_time_sec, current_datetime):
        
        # Grab a of the preprocessed image that we can draw on it
        display_frame = stage_outputs.get("preprocessor").get("preprocessed_frame")
        tracked_frame = display_frame.copy()
        
        # Grab dictionary of tracked objects so we can draw them
        tracked_object_dict = stage_outputs.get("tracker").get("tracked_object_dict", {})
        
        return draw_objects_on_frame(tracked_frame, tracked_object_dict, 
                                     self._show_ids, 
                                     self._show_outlines, 
                                     self._show_bounding_boxes,
                                     self._show_trails,
                                     self._show_decay,
                                     current_time_sec,
                                     outline_color = self._line_color, 
                                     box_color = self._line_color)
        
    # .................................................................................................................
    # .................................................................................................................


# =====================================================================================================================
# =====================================================================================================================


class Validation_Display(Display_Window_Specification):
    
    ''' Standard implementation for displaying validation objects during tracking '''
    
    # .................................................................................................................
    
    def __init__(self, layout_index, num_rows, num_columns, initial_display = False, max_wh = None,
                 window_name = "Validation",
                 show_ids = False,
                 show_outlines = True,
                 show_bounding_boxes = False,
                 show_trails = True,
                 show_decay = True,
                 line_color = (255, 0, 255)):
        
        # Inherit from parent class
        super().__init__(window_name, layout_index, num_rows, num_columns, 
                         initial_display = initial_display, 
                         max_wh = max_wh)
        
        # Store display configuration details
        self._show_ids = show_ids
        self._show_outlines = show_outlines
        self._show_bounding_boxes = show_bounding_boxes
        self._show_trails = show_trails
        self._show_decay = show_decay
        self._line_color = line_color
    
    # .................................................................................................................
    
    def display(self, stage_outputs, configurable_ref, current_frame_index, current_time_sec, current_datetime):
        
        # Grab a of the preprocessed image that we can draw on it
        display_frame = stage_outputs.get("preprocessor").get("preprocessed_frame")
        validations_frame = display_frame.copy()
        
        # Grab dictionary of validation objects so we can draw them
        validation_object_dict = stage_outputs.get("tracker").get("validation_object_dict")
        
        return draw_objects_on_frame(validations_frame, validation_object_dict, 
                                     self._show_ids, 
                                     self._show_outlines, 
                                     self._show_bounding_boxes,
                                     self._show_trails,
                                     self._show_decay,
                                     current_time_sec,
                                     outline_color = self._line_color, 
                                     box_color = self._line_color)
        
    # .................................................................................................................
    # ................................................................................................................. 


# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

# .....................................................................................................................
    
def draw_objects_on_frame(display_frame, object_dict, 
                          show_ids, show_outlines, show_bounding_boxes, show_trails, show_decay,
                          current_time_sec, outline_color, box_color):
    
    # Set up some dimming colors for each drawing color, in case of decaying objects
    dim_ol_color = [np.mean(outline_color)] * 3
    dim_bx_color = [np.mean(outline_color)] * 3
    dim_tr_color = [np.mean(outline_color)] * 3
    
    # Record frame sizing so we can draw normalized co-ordinate locations
    frame_h, frame_w = display_frame.shape[0:2]
    frame_wh = np.array((frame_w - 1, frame_h - 1))
    
    for each_id, each_obj in object_dict.items():
        
        # Get object bbox co-ords for re-use
        tl, br = np.int32(np.round(each_obj.tl_br * frame_wh))
        tr = (br[0], tl[1])
        #bl = (tl[0], br[1])
        
        # Re-color objects that are decaying
        draw_ol_color = outline_color
        draw_bx_color = box_color
        draw_tr_color = (0, 255, 255)
        if show_decay:
            match_delta = each_obj.match_decay_time_sec(current_time_sec)            
            if match_delta > (1/100):
                draw_ol_color = dim_ol_color 
                draw_bx_color = dim_bx_color
                draw_tr_color = dim_tr_color
                
                # Show decay time
                cv2.putText(display_frame, "{:.3f}s".format(match_delta), tr,
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2, cv2.LINE_AA)
        
        # Show object outlines (i.e. blobs) if needed
        if show_outlines:
            obj_hull = np.int32(np.round(each_obj.hull * frame_wh))
            cv2.polylines(display_frame, [obj_hull], True, draw_ol_color, 1, cv2.LINE_AA)
        
        # Draw bounding boxes if needed
        if show_bounding_boxes:
            cv2.rectangle(display_frame, tuple(tl), tuple(br), draw_bx_color, 2, cv2.LINE_4)
        
        # Draw object trails
        if show_trails:
            xy_trail = np.int32(np.round(each_obj.xy_track_history * frame_wh))
            if len(xy_trail) > 5:
                cv2.polylines(display_frame, [xy_trail], False, draw_tr_color, 1, cv2.LINE_AA)
            
        # Draw object ids
        if show_ids:   
            nice_id = each_obj.nice_id # Remove day-of-year offset from object id for nicer display
            cv2.putText(display_frame, "{}".format(nice_id), tuple(tl),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
            
    return display_frame

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Demo 
    
if __name__ == "__main__":
    pass


# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap


