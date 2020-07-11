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
    (Those details are handled by UI provider)
    
    This object is instead responsible for bundling all data needed to represent each display,
    as well as the function used to create the display image (given the stage outputs/configurable as inputs)
    '''
    
    # .................................................................................................................
    
    def __init__(self, name, layout_index, num_rows = 2, num_columns = 2, 
                 *, initial_display = False, provide_mouse_xy = False, drawing_json = None, limit_wh = True):
        
        # Store display specification, so we can use it to build displays as needed
        self.name = name
        self.initial_display = initial_display
        self.provide_mouse_xy = provide_mouse_xy
        self.drawing_json = drawing_json
        self.limit_wh = limit_wh
        
        # Store layout information
        self.num_rows = num_rows
        self.num_cols = num_columns
        self.layout_index = layout_index
        
    # .................................................................................................................
    
    def __repr__(self):
        
        # Figure out if this is the initial display
        is_initial = (self.initial_display)
        initial_indicator = " (initial display)" if is_initial else ""
        
        # Build base repr strings
        repr_strs = ["Display Specification",
                     "  Window name: {}{}".format(self.name, initial_indicator)]
        
        # Add more info if there is a drawing variable name
        has_drawing_json = (self.drawing_json is not None)
        if has_drawing_json:
            drawing_variable_name = self.drawing_json.get("variable_name", "unknown variable name")
            repr_strs += ["  Drawing variable: {}".format(drawing_variable_name)]
        
        # Add indication that this display has mouse tracking enabled
        has_mouse_tracking = (self.provide_mouse_xy is not None)
        if has_mouse_tracking:
            repr_strs += ["  Mouse xy enabled!"]
        
        return "\n".join(repr_strs)
    
    # .................................................................................................................
    
    def display(self, stage_outputs, configurable_ref, mouse_xy, 
                current_frame_index, current_epoch_ms, current_datetime):
        return stage_outputs["video_capture_input"]["video_frame"]
    
    # .................................................................................................................
    
    def to_json(self):        
        return {"name": self.name,
                "initial_display": self.initial_display,
                "provide_mouse_xy": self.provide_mouse_xy,
                "drawing_json": self.drawing_json,
                "limit_wh": self.limit_wh,
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
                 layout_index, num_rows, num_columns, 
                 initial_display = False, 
                 provide_mouse_xy = False,
                 drawing_json = None,
                 limit_wh = False,
                 interpolation_type = cv2.INTER_NEAREST):
        
        # Inherit from parent class
        super().__init__(window_name, layout_index, num_rows, num_columns, 
                         initial_display = initial_display, provide_mouse_xy = provide_mouse_xy,
                         drawing_json = drawing_json, limit_wh = limit_wh)
        
        # Store reference & display lookups
        self.display_stage = display_stage
        self.display_name = display_name
        self.reference_stage = reference_stage
        self.reference_name = reference_name
        self.interpolation_type = interpolation_type
        
    # .................................................................................................................
        
    def display(self, stage_outputs, configurable_ref, mouse_xy, 
                current_frame_index, current_epoch_ms, current_datetime):
        
        # Get display & reference frames
        reference_sized_frame = stage_outputs[self.reference_stage][self.reference_name]
        display_frame = stage_outputs[self.display_stage][self.display_name]
        
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
    
    def __init__(self, layout_index, num_rows, num_columns, 
                 initial_display = False, provide_mouse_xy = False, drawing_json = None, limit_wh = False,
                 window_name = "Input"):
        
        # Inherit from parent class
        super().__init__(window_name, layout_index, num_rows, num_columns, 
                         initial_display = initial_display, 
                         provide_mouse_xy = provide_mouse_xy,
                         drawing_json = drawing_json,
                         limit_wh = limit_wh)
        
    # .................................................................................................................
        
    def display(self, stage_outputs, configurable_ref, mouse_xy, 
                current_frame_index, current_epoch_ms, current_datetime):
        return stage_outputs["video_capture_input"]["video_frame"]
        
    # .................................................................................................................
    # .................................................................................................................
    
    
class Background_Display(Display_Window_Specification):
    
    ''' Standard implementation for displaying the background image '''
    
    # .................................................................................................................
    
    def __init__(self, layout_index, num_rows, num_columns, 
                 initial_display = False, provide_mouse_xy = False, drawing_json = None, limit_wh = True,
                 window_name = "Background"):
        
        # Inherit from parent class
        super().__init__(window_name, layout_index, num_rows, num_columns, 
                         initial_display = initial_display, 
                         provide_mouse_xy = provide_mouse_xy,
                         drawing_json = drawing_json,
                         limit_wh = limit_wh)
        
    # .................................................................................................................
        
    def display(self, stage_outputs, configurable_ref, mouse_xy, 
                current_frame_index, current_epoch_ms, current_datetime):
        return stage_outputs["video_capture_input"]["bg_frame"]
        
    # .................................................................................................................
    # .................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Preprocessor displays

class Preprocessed_Display(Display_Window_Specification):
    
    ''' Standard implementation for displaying preprocessed frames '''
    
    # .................................................................................................................
    
    def __init__(self, layout_index, num_rows, num_columns, 
                 initial_display = False, provide_mouse_xy = False, drawing_json = None, limit_wh = True,
                 window_name = "Preprocessed"):
        
        # Inherit from parent class
        super().__init__(window_name, layout_index, num_rows, num_columns, 
                         initial_display = initial_display, 
                         provide_mouse_xy = provide_mouse_xy,
                         drawing_json = drawing_json,
                         limit_wh = limit_wh)
        
    # .................................................................................................................
        
    def display(self, stage_outputs, configurable_ref, mouse_xy, 
                current_frame_index, current_epoch_ms, current_datetime):
        return stage_outputs["preprocessor"]["preprocessed_frame"]
        
    # .................................................................................................................
    # .................................................................................................................


class Preprocessed_BG_Display(Display_Window_Specification):
    
    ''' Standard implementation for displaying the preprocessed background '''
    
    # .................................................................................................................
    
    def __init__(self, layout_index, num_rows, num_columns, 
                 initial_display = False, provide_mouse_xy = False, drawing_json = None, limit_wh = True,
                 window_name = "Preprocessed Background"):
        
        # Inherit from parent class
        super().__init__(window_name, layout_index, num_rows, num_columns, 
                         initial_display = initial_display, 
                         provide_mouse_xy = provide_mouse_xy,
                         drawing_json = drawing_json,
                         limit_wh = limit_wh)
        
    # .................................................................................................................
        
    def display(self, stage_outputs, configurable_ref, mouse_xy, 
                current_frame_index, current_epoch_ms, current_datetime):
        return stage_outputs["preprocessor"]["preprocessed_bg_frame"]
        
    # .................................................................................................................
    # .................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Foreground extractor displays

class Binary_Display(Matched_Size_Display):
    
    ''' Standard implementation for displaying the binary output image, after foreground extraction '''
    
    # .................................................................................................................
    
    def __init__(self, layout_index, num_rows, num_columns, 
                 initial_display = False, provide_mouse_xy = False, drawing_json = None, limit_wh = True):
        
        # Inherit from parent class
        super().__init__("Binary Output", 
                         "foreground_extractor", "binary_frame_1ch", 
                         "preprocessor", "preprocessed_frame",
                         layout_index, num_rows, num_columns, 
                         initial_display = initial_display,
                         provide_mouse_xy = provide_mouse_xy,
                         drawing_json = drawing_json,
                         limit_wh = limit_wh)
        
    # .................................................................................................................
    # .................................................................................................................


class Filtered_Binary_Display(Matched_Size_Display):
    
    ''' Standard implementation for displaying the filtered binary image, after pixel filtering '''
    
    # .................................................................................................................
    
    def __init__(self, layout_index, num_rows, num_columns, 
                 initial_display = False, provide_mouse_xy = False, drawing_json = None, limit_wh = True):
        
        # Inherit from parent class
        super().__init__("Filtered Binary Output", 
                         "pixel_filter", "filtered_binary_frame_1ch", 
                         "preprocessor", "preprocessed_frame",
                         layout_index, num_rows, num_columns, 
                         initial_display = initial_display,
                         provide_mouse_xy = provide_mouse_xy,
                         drawing_json = drawing_json,
                         limit_wh = limit_wh)
        
    # .................................................................................................................
    # .................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Detection displays

class Detection_Display(Display_Window_Specification):
    
    ''' Standard implementation for displaying detection objects '''
    
    # .................................................................................................................
    
    def __init__(self, layout_index, num_rows, num_columns, 
                 initial_display = False, provide_mouse_xy = False, drawing_json = None, limit_wh = True,
                 window_name = "Detection",
                 show_outlines = True,
                 show_bounding_boxes = False,
                 line_color = (255, 255, 0)):
        
        # Inherit from parent class
        super().__init__(window_name, layout_index, num_rows, num_columns, 
                         initial_display = initial_display, 
                         provide_mouse_xy = provide_mouse_xy,
                         drawing_json = drawing_json,
                         limit_wh = limit_wh)
        
        # Store display configuration details
        self._show_outlines = show_outlines
        self._show_bounding_boxes = show_bounding_boxes
        self._line_color = line_color
        
    # .................................................................................................................
        
    def display(self, stage_outputs, configurable_ref, mouse_xy, 
                current_frame_index, current_epoch_ms, current_datetime):
        
        # Grab a copy of the color image that we can draw on
        detection_ref_dict = stage_outputs["detector"]["detection_ref_dict"]
        display_frame = stage_outputs["preprocessor"]["preprocessed_frame"]  
        detection_frame = display_frame.copy()
        
        # Record frame sizing so we can draw normalized co-ordinate locations
        frame_h, frame_w = detection_frame.shape[0:2]
        frame_wh = np.array((frame_w - 1, frame_h - 1))
        
        for each_det in detection_ref_dict.values():
            
            # Draw the blob outline
            if self._show_outlines:
                det_hull = np.int32(np.round(each_det.hull_array * frame_wh))
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
    
    def __init__(self, layout_index, num_rows, num_columns, 
                 initial_display = False, provide_mouse_xy = False, drawing_json = None, limit_wh = True,
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
                         provide_mouse_xy = provide_mouse_xy,
                         drawing_json = drawing_json, 
                         limit_wh = limit_wh)
        
        # Store display configuration details
        self._show_ids = show_ids
        self._show_outlines = show_outlines
        self._show_bounding_boxes = show_bounding_boxes
        self._show_trails = show_trails
        self._show_decay = show_decay
        self._line_color = line_color
        
    # .................................................................................................................
        
    def display(self, stage_outputs, configurable_ref, mouse_xy, 
                current_frame_index, current_epoch_ms, current_datetime):
        
        # Grab a of the preprocessed image that we can draw on it
        display_frame = stage_outputs["preprocessor"]["preprocessed_frame"]
        tracked_frame = display_frame.copy()
        
        # Grab dictionary of tracked objects so we can draw them
        tracked_object_dict = stage_outputs["tracker"]["tracked_object_dict"]
        
        return draw_objects_on_frame(tracked_frame, tracked_object_dict, 
                                     self._show_ids, 
                                     self._show_outlines, 
                                     self._show_bounding_boxes,
                                     self._show_trails,
                                     self._show_decay,
                                     current_epoch_ms,
                                     outline_color = self._line_color, 
                                     box_color = self._line_color)
        
    # .................................................................................................................
    # .................................................................................................................


# =====================================================================================================================
# =====================================================================================================================


class Validation_Display(Display_Window_Specification):
    
    ''' Standard implementation for displaying validation objects during tracking '''
    
    # .................................................................................................................
    
    def __init__(self, layout_index, num_rows, num_columns, 
                 initial_display = False, provide_mouse_xy = False, drawing_json = None, limit_wh = True,
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
                         provide_mouse_xy = provide_mouse_xy,
                         drawing_json = drawing_json, 
                         limit_wh = limit_wh)
        
        # Store display configuration details
        self._show_ids = show_ids
        self._show_outlines = show_outlines
        self._show_bounding_boxes = show_bounding_boxes
        self._show_trails = show_trails
        self._show_decay = show_decay
        self._line_color = line_color
    
    # .................................................................................................................
    
    def display(self, stage_outputs, configurable_ref, mouse_xy, 
                current_frame_index, current_epoch_ms, current_datetime):
        
        # Grab a of the preprocessed image that we can draw on it
        display_frame = stage_outputs["preprocessor"]["preprocessed_frame"]
        validations_frame = display_frame.copy()
        
        # Grab dictionary of validation objects so we can draw them
        validation_object_dict = stage_outputs["tracker"]["validation_object_dict"]
        
        return draw_objects_on_frame(validations_frame, validation_object_dict, 
                                     self._show_ids, 
                                     self._show_outlines, 
                                     self._show_bounding_boxes,
                                     self._show_trails,
                                     self._show_decay,
                                     current_epoch_ms,
                                     outline_color = self._line_color, 
                                     box_color = self._line_color)
        
    # .................................................................................................................
    # ................................................................................................................. 


# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

# .....................................................................................................................
    
def draw_objects_on_frame(display_frame, object_dict, 
                          show_ids, show_outlines, show_bounding_boxes, show_trails, show_decay,
                          current_epoch_ms, outline_color, box_color):
    
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
            match_delta = each_obj.get_match_decay_time_ms(current_epoch_ms)            
            if match_delta > 1:
                draw_ol_color = dim_ol_color 
                draw_bx_color = dim_bx_color
                draw_tr_color = dim_tr_color
                
                # Show decay time
                cv2.putText(display_frame, "{:.3f}s".format(match_delta/1000), tr,
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2, cv2.LINE_AA)
        
        # Show object outlines (i.e. blobs) if needed
        if show_outlines:
            obj_hull = np.int32(np.round(each_obj.hull_array * frame_wh))
            cv2.polylines(display_frame, [obj_hull], True, draw_ol_color, 1, cv2.LINE_AA)
        
        # Draw bounding boxes if needed
        if show_bounding_boxes:
            cv2.rectangle(display_frame, tuple(tl), tuple(br), draw_bx_color, 2, cv2.LINE_4)
        
        # Draw object trails
        if show_trails:
            xy_trail = np.int32(np.round(each_obj.xy_center_history * frame_wh))
            if len(xy_trail) > 1:
                cv2.polylines(display_frame, [xy_trail], False, draw_tr_color, 1, cv2.LINE_AA)
            
        # Draw object ids
        if show_ids:   
            nice_id = each_obj.nice_id # Remove day-of-year offset from object id for nicer display
            cv2.putText(display_frame, "{}".format(nice_id), tuple(tl),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
            
    return display_frame

# .....................................................................................................................

def draw_mouse_centered_rectangle(display_frame, mouse_xy_array, rectangle_wh_px,
                                  line_color, line_thickness = 1):
    
    # Get rectangle half-sizing in both dimensions to computer centering offset
    rect_half_wh_px = np.int32(np.round(rectangle_wh_px / 2))
    
    # Compute top-left/bot-right co-ords, then draw the rectangle!
    rect_tl = tuple(mouse_xy_array - rect_half_wh_px)
    rect_br = tuple(mouse_xy_array + rect_half_wh_px)
    cv2.rectangle(display_frame, rect_tl, rect_br, line_color, line_thickness)
    
    return display_frame

# .....................................................................................................................

def draw_mouse_centered_ellipse(display_frame, mouse_xy_array, ellipse_wh_px,
                                line_color, line_thickness = 1, line_type = cv2.LINE_AA):
    
    # Hard-code some variables for clarity
    angle_deg = 0
    start_angle_deg = 0
    end_angle_deg = 360
    
    # Get ellipse half-sizing in both dimensions to draw sizing properly
    elip_half_wh_px = np.int32(np.round(ellipse_wh_px / 2))
    cv2.ellipse(display_frame, tuple(mouse_xy_array), tuple(elip_half_wh_px), 
                angle_deg, start_angle_deg, end_angle_deg, 
                line_color, line_thickness, line_type)
    
    return display_frame

# .....................................................................................................................

def draw_mouse_centered_circle(display_frame, mouse_xy_array, circle_radius_px,
                               line_color, line_thickness = 1, line_type = cv2.LINE_AA):
    
    # Draw circle. That's it!
    cv2.circle(display_frame, tuple(mouse_xy_array), circle_radius_px, line_color, line_thickness, line_type)
    
    return display_frame

# .....................................................................................................................

def mouse_follower_spec(shape, 
                        width_variable_name,
                        height_variable_name,
                        show_hide_variable_name = None,
                        line_color = (255, 255, 0), 
                        line_thickness = 1):
    
    ''' 
    Function for generation mouse follower specification json data. 
    Should be passed into a display specification, so that it can be used to construct displays during configuration
    '''
    
    # Hard-code the recognized shapes for now
    valid_shapes = ["circle", "rectangle"]
    
    # Error if the visualization shape is not recognized
    lowercase_shape = shape.lower().strip()
    invalid_shape = (lowercase_shape not in valid_shapes)
    if invalid_shape:
        raise TypeError("Unrecognized mouse follower shape ({}). Must be one of: {}".format(shape, valid_shapes))
    
    # Assume everything else is good and creat eoutput json data
    follower_json = {"shape": lowercase_shape,
                     "width_variable_name": width_variable_name,
                     "height_variable_name": height_variable_name,
                     "show_hide_variable_name": show_hide_variable_name,
                     "line_color": line_color,
                     "line_thickness": line_thickness}
    
    return follower_json

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Demo 
    
if __name__ == "__main__":
    pass


# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap


