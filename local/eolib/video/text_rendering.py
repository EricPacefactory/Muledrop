#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Feb 14 14:54:47 2019

@author: eo
"""


# ---------------------------------------------------------------------------------------------------------------------
#%% Imports

import cv2


# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes



# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

# .....................................................................................................................

def cv2_font_config(font = cv2.FONT_HERSHEY_SIMPLEX,
                    scale = 0.5,
                    thickness = 1,
                    color = (255, 255, 255),
                    line_type = cv2.LINE_AA):
    
    ''' Helper function for building font settings dictionary with OpenCV property naming scheme '''
    
    return {"fontFace": font, "fontScale": scale, "thickness": thickness, "color": color, "lineType": line_type}

# .....................................................................................................................

def font_config(font = cv2.FONT_HERSHEY_SIMPLEX,
                scale = 0.5,
                thickness = 1,
                color = (255, 255, 255),
                line_type = cv2.LINE_AA):
    
    ''' Helper function for building font settings dictionary '''
    
    return {"font": font, "scale": scale, "thickness": thickness, "color": color, "line_type": line_type}

# .....................................................................................................................

def getTextSize_wrapper(text, fontFace, fontScale, thickness, **kwargs):
    
    ''' 
    Wrapper function around built-in OpenCV function. 
    Accepts additional font-settings arguments without errors
    Typical usage would involve defining a single font_settings dictionary, for example:
        font_settings = {"fontFace": cv2.FONT_HERSHEY_SIMPLEX,
                         "fontScale": 0.5,
                         "thickness": 1,
                         "color": (255, 255, 255),
                         "lineType": cv2.LINE_AA}
    
    And then calling:
        text_wh, text_baseline = getTextSize_wrapper("my example text", **font_settings)
        
    Unlike the cv2.getTextSize function, the additional aesthetic arguments will not break the function call!
    
    Returns:
        text_wh, text_baseline
    '''
    
    return cv2.getTextSize(text, fontFace, fontScale, thickness)

# .....................................................................................................................

def get_text_size(text_string, font = cv2.FONT_HERSHEY_SIMPLEX, scale = 0.5, thickness = 1, **kwargs):
    
    ''' 
    Helper function for getting text sizing, with simplified input arguments,
    Returns:
        text_wh, text_baseline
    '''
    
    return cv2.getTextSize(text_string, font, scale, thickness)

# .....................................................................................................................

def position_center(text_string, center_xy, font, scale, thickness, **kwargs):
    
    '''
    Function for placing text with centering co-ordinates (instead of default top-left co-ordinates)
    Returns the top-left x/y co-ordinates that should be used for placing centered text
    
    Inputs:        
        text_string -> String. The text that is being sized
        
        center_xy -> Tuple. Represents the target centering position of the text to be drawn.
                       
        font -> Integer (from OpenCV). Use cv2.FONT_... constants to select the font
        
        scale -> Float. Specifies the overall font size
        
        thickness -> Integer. Specifies the thickness of the lines used to draw characters
        
        **kwargs -> No function. This input is provided so that cv2.putText(...) arguments can be bundled
                    and passed in to this function without errors (i.e. the kwargs catch unneccesary inputs)
                    
    Outputs:
        (text_center_x, text_center_y)
    '''
    
    # First get the size of the text, so we know how much to offset for centering
    text_wh, text_baseline = get_text_size(text_string, font, scale, thickness)
    
    # Calculate top-left co-ordinates needed to give proper center_xy positioning
    target_x, target_y = center_xy
    text_center_x = int(round(target_x - (text_wh[0] / 2)))
    text_center_y = int(round(target_y + text_baseline))
    
    return (text_center_x, text_center_y)

# .....................................................................................................................

def position_frame_relative(frame_shape, text_string, relative_xy, font, scale, thickness, **kwargs):
    
    '''
    Function for getting text placement co-ordinates (top-left) using relative positioning arguments,
    where positive numbers (x or y) are interpretted as being relative to the frame top-left, 
    while negative numbers are interpretted as being relative to the frame bottom-right
    
    Inputs:
        frame_shape -> Tuple. Obtained by passing accessing the .shape attribute on a numpy array (image)
        
        text_string -> String. The text that is being sized
        
        relative_xy -> Tuple. Relative positioning on the frame, in pixels, with a top-left origin. 
                       For example, the relative position (5, -8) 
                       would be interpretted as 5 pixels from the left, 8 pixels from the bottom
                       
        font -> Integer (from OpenCV). Use cv2.FONT_... constants to select the font
        
        scale -> Float. Specifies the overall font size
        
        thickness -> Integer. Specifies the thickness of the lines used to draw characters
        
        **kwargs -> No function. This input is provided so that cv2.putText(...) arguments can be bundled
                    and passed in to this function without errors (i.e. the kwargs catch unneccesary inputs)
                    
    Outputs:
        (absolute_x_corner_position, absolute_y_corner_position)
    '''
    
    # Get frame sizing & relative positions separated for convenience
    frame_h, frame_w = frame_shape[0:2]
    rel_x, rel_y = relative_xy
    
    # Get text size based on font settings & string
    (text_w, text_h), text_base = get_text_size(text_string, font, scale, thickness)
    
    # Get relative positioning
    text_x_pos = (rel_x + (frame_w - 1) - text_w) if rel_x < 0 else rel_x
    text_y_pos = (rel_y + (frame_h - 1) - text_base) if rel_y < 0 else (rel_y + text_h) + 1
        
    return (text_x_pos, text_y_pos)

# .....................................................................................................................

def relative_text(frame, text_string, relative_position,
                  font = cv2.FONT_HERSHEY_SIMPLEX,
                  scale = 0.5,
                  thickness = 1,
                  color = (255, 255, 255),
                  line_type = cv2.LINE_AA):
    
    ''' 
    Function for placing text relative to the frame
    Negative position values are interpretted as being relative to the bottom-right of the frame.
    Positive values behave mostly normal, though y-values take the text height into account
    '''
    
    rel_pos = position_frame_relative(frame.shape, text_string, relative_position, font, scale, thickness)
    cv2.putText(frame, text_string, rel_pos, font, scale, color, thickness, line_type)
    
    return frame

# .....................................................................................................................

def simple_text(frame, text_string, text_position, center_text = False,
                font = cv2.FONT_HERSHEY_SIMPLEX,
                scale = 0.5,
                thickness = 1,
                color = (255, 255, 255),
                line_type = cv2.LINE_AA):
    
    ''' Simplified text-rendering function, with sane defaults '''
    
    # Get text positioning, either top-left or center based on input arguments
    pos = position_center(text_string, text_position, font, scale, thickness) if center_text else text_position
    cv2.putText(frame, text_string, pos, font, scale, color, thickness, line_type)
    
    return frame

# .....................................................................................................................

def normalized_text(frame, text_string, text_xy_norm,
                    align_vertical = "center", align_horizontal = "center",
                    font = cv2.FONT_HERSHEY_SIMPLEX,
                    scale = 0.5,
                    thickness = 1,
                    color = (255, 255, 255),
                    bg_color = None,
                    line_type = cv2.LINE_AA):
    
    '''
    Function which draws text onto a frame using normalized co-ordinates
    Also supports different vertical/horizontal alignment (using strings: 'top', 'left', 'center', 'bottom', 'right')
    If a bg_color argument is provided, the function will also draw a thicker background behind the text
    Note that this function is likely 'slow' compared to alternatives, due to having to constantly calculate
    the relative positioning of text. In cases where speed is important, it is better to pre-calculate positoning!
    
    Returns:
        text_position_px, drawn_image
    '''
    
    # Get frame sizing to convert normalized co-ords to pixels
    frame_height, frame_width = frame.shape[0:2]
    
    # Scale text-xy co-ordinates to pixels
    text_x_norm, text_y_norm = text_xy_norm
    text_x_px = int(round(text_x_norm * (frame_width - 1)))
    text_y_px = int(round(text_y_norm * (frame_height - 1)))
    
    # Figure out text sizing for handling alignment
    (text_w, text_h), text_baseline = cv2.getTextSize(text_string, font, scale, thickness)
    
    # Figure out text x-location
    h_align_lut = {"left": 0, "center":  -int(text_w / 2), "right": -text_w}
    lowered_h_align = str(align_horizontal).lower()
    x_offset = h_align_lut.get(lowered_h_align, h_align_lut["left"])
    
    # Figure out text y-location
    v_align_lut = {"top": text_h, "center": text_baseline, "bottom": -text_baseline}
    lowered_v_align = str(align_vertical).lower()
    y_offset = v_align_lut.get(lowered_v_align, v_align_lut["top"])
    
    # Calculate final text postion
    text_position_px = (1 + text_x_px + x_offset, 1 + text_y_px + y_offset)
    
    # Draw background if needed
    if bg_color is not None:
        bg_thickness = (2 * thickness)
        cv2.putText(frame, text_string, text_position_px, font, scale, bg_color, bg_thickness, line_type)
    
    return text_position_px, cv2.putText(frame, text_string, text_position_px, font, scale, color, thickness, line_type)

# .....................................................................................................................

def fg_bg_text(frame, text_string, text_position, center_text = False,
               font = cv2.FONT_HERSHEY_SIMPLEX,
               scale = 0.5,
               fg_thickness = 1,
               bg_thickness = 2,
               fg_color = (255, 255, 255),
               bg_color = (0, 0, 0),
               line_type = cv2.LINE_AA):
    
    ''' 
    Text rendering with foreground/background text. Gives the appearance of the text being outlined
    Helps ensure readability against a wide variety of background imagery
    '''
    
    # Get text positioning (top-left vs. centered) for both fg/bg text
    pos = position_center(text_string, text_position, font, scale, fg_thickness) if center_text else text_position
    
    # Draw background text first, then foreground overtop to give 'outlined' appearance
    cv2.putText(frame, text_string, pos, font, scale, bg_color, bg_thickness, line_type)
    cv2.putText(frame, text_string, pos, font, scale, fg_color, fg_thickness, line_type)
    
    return frame

# .....................................................................................................................
# .....................................................................................................................
    

# ---------------------------------------------------------------------------------------------------------------------
#%% Demo
    
if __name__ == "__main__":
    
    import numpy as np
    
    frame_w = 475
    frame_h = 150
    mid_x, mid_y = frame_w / 2, frame_h / 2
    
    
    # Centering example
    black_frame = np.zeros((frame_h, frame_w, 3), np.uint8)
    simple_text(black_frame, "~~~ Centered text example ~~~", (mid_x, mid_y), center_text=True)
    
    # Foreground/background example
    rand_frame = np.random.randint(0, 255, (frame_h, frame_w, 3), dtype=np.uint8)
    fg_bg_text(rand_frame, "FG/BG Text", (5, 30), scale = 1.0, fg_thickness=2, bg_thickness=4)
    
    # Detailed custom example
    white_frame = np.full((frame_h, frame_w, 3), (255, 255, 255), dtype=np.uint8)
    color_text = "Vertically Centered & Green"
    color_font_settings = font_config(color = (0, 255, 0), scale = 0.75, font = cv2.FONT_HERSHEY_SCRIPT_COMPLEX)
    center_x, center_y = position_center(color_text, (0, mid_y), **color_font_settings)
    simple_text(white_frame, color_text, (5, center_y), **color_font_settings, center_text = False)
    
    # Normalized text example
    purple_frame = np.full((frame_h, frame_w, 3), (120, 0, 160), dtype=np.uint8)
    normalized_text(purple_frame, "(0.5, 0.5)", (0.5, 0.5), "center", "center", scale = 2, thickness = 3)
    normalized_text(purple_frame, "Top left", (0, 0), "top", "left", bg_color = (0, 0, 0))
    normalized_text(purple_frame, "Bot right", (1, 1), "bottom", "right", scale = 0.5, font = cv2.FONT_HERSHEY_COMPLEX)
    normalized_text(purple_frame, "Top mid", (0.5, 0), "top", "center", scale = 0.5, color = (0, 0, 0), bg_color = (255, 255, 255))
    
    # Relative positioning example
    red_frame = np.full((frame_h, frame_w, 3), (0, 0, 255), dtype=np.uint8)
    relative_text(red_frame, "Relative (-5, -5)", (-5,-5))
    relative_text(red_frame, "Relative (-5, +5)", (-5,5))
    relative_text(red_frame, "Relative (+5, -5)", (5,-5))
    relative_text(red_frame, "Relative (+5, +5)", (5,5))
    
    # Combine all the images into one for simpler display
    combined_frame = np.vstack((black_frame, rand_frame, white_frame, purple_frame, red_frame))
    cv2.imshow("Example", combined_frame)
    print("", "Press any key to close", sep="\n")
    cv2.waitKey(0)
    cv2.destroyAllWindows()
    

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap


