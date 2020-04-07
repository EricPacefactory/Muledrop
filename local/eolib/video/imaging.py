#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Nov  8 11:56:36 2019

@author: eo
"""


# ---------------------------------------------------------------------------------------------------------------------
#%% Imports

import cv2
import numpy as np

# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes



# ---------------------------------------------------------------------------------------------------------------------
#%% Shared Functions

# .....................................................................................................................

def image_1d_to_3d(image_1d):
    
    '''
    Function which takes a single channel image, and converts it to a 3-channel image
    The function checks the image dimensions, so it is not efficient if you already know the image is 1D!
    '''
    
    # Do nothing if we're already dealing with a 3d image
    image_shape = image_1d.shape
    if (len(image_shape) == 3) and (image_shape[2] == 3):   # Careful, making use of lazy evaluation to avoid error!
        return image_1d
    
    return cv2.cvtColor(image_1d, cv2.COLOR_GRAY2BGR)

# .....................................................................................................................

def diagonal_hatching_masked_area(display_image, mask_image, 
                                  invert_mask = False, line_spacing_px = 8, max_lines = 500,
                                  line_color = (0, 0, 0), line_thickness = 1, line_type = cv2.LINE_AA,
                                  auto_convert_1d_mask_to_3d = True):
    
    '''
    As an alternative to blacking out masked regions on an image,
    this function will draw a diagonal hatching pattern in masked out regions.
    
    This is a heavy-ish function to run! Only use in cases where speed isn't a major concern
    '''
    
    # Create copies of the input image so we can draw over top without messing up the original!
    hatch_image = display_image.copy()
    clean_image = display_image.copy()
    
    # Figure out the largest dimension, since we'll use this to angle the hatching
    img_height, img_width = display_image.shape[0:2]
    max_dimension = max(img_width, img_height)
    full_draw_width = 10 + 2 * max_dimension
    
    # Calculate how many lines we'll need to draw, in case it's going to be too many
    line_spacing_px = max(line_spacing_px, 1)
    num_lines = int(round(full_draw_width / line_spacing_px))
    too_many_lines = (num_lines > max_lines)
    if too_many_lines:
        line_spacing_px = int(round(full_draw_width / (max_lines + 1)))
        line_spacing_px = max(line_spacing_px, 1)
        
    # Initialize
    pt1_x = int(round(line_spacing_px / 2)) - max_dimension
    pt1_y, pt2_y = (max_dimension + 10), (0 - 10)
    
    # Loop through and draw diagonal lines until we reach the other side
    while pt1_x < img_width:
        
        # Build our line drawing co-ords & update the starting x point for the next iteration
        pt1 = (pt1_x, pt1_y)
        pt2 = (pt1_x + max_dimension, pt2_y)
        pt1_x += line_spacing_px
        
        # Draw each diagonal line
        cv2.line(hatch_image, pt1, pt2, line_color, line_thickness, line_type)
    
    # Figure out the mask/inverted mask for drawing
    # (we'll draw hatching in areas blocked by the mask while leaving other regions clean)
    mask_3d = image_1d_to_3d(mask_image) if auto_convert_1d_mask_to_3d else mask_image
    mask_reg = mask_3d if invert_mask else cv2.bitwise_not(mask_3d)
    mask_inv = cv2.bitwise_not(mask_3d) if invert_mask else mask_3d
    
    # Finally, combine the clean/hatching images using the mask to generate the final image
    masked_hatch = cv2.bitwise_and(hatch_image, mask_reg)
    masked_clean = cv2.bitwise_and(clean_image, mask_inv)
    hatching_display = cv2.add(masked_clean, masked_hatch)
    
    return hatching_display

# .....................................................................................................................
    
def hstack_padded(*frames, pad_width = 15, padding_color = (40, 40, 40)):
    
    ''' 
    Function which stacks frames horizontally, with a separator,
    Assumes all frames are the same size & 3-channels!
    '''
    
    # Create a separator image, assuming all frames have the same height as the first
    image_height = frames[0].shape[0]
    separator = np.full((image_height, pad_width, 3), padding_color, dtype=np.uint8)
    
    # Create a list of frame-separator-frame-separator-...-frame for horizontal stacking
    frame_stack = []
    for each_frame in frames:
        frame_stack.append(each_frame)
        frame_stack.append(separator)
    del frame_stack[-1]
    
    return np.hstack(frame_stack)

# .....................................................................................................................
    
def vstack_padded(*frames, pad_height = 15, padding_color = (40, 40, 40), 
                  prepend_separator = False, append_separator = False):
    
    ''' 
    Function which stacks frames vertically, with a separator,
    Assumes all frames are the same size & 3-channels!
    '''
    
    # Create a separator image, assuming all frames have the same width as the first
    image_width = frames[0].shape[1]
    separator = np.full((pad_height, image_width, 3), padding_color, dtype=np.uint8)
    
    # Create a list of frame-separator-frame-separator-...-frame for vertical stacking
    frame_stack = [separator] if prepend_separator else []
    for each_frame in frames:
        frame_stack.append(each_frame)
        frame_stack.append(separator)
    
    # Remove the last separator, if needed
    if not append_separator:
        del frame_stack[-1]
    
    return np.vstack(frame_stack)

# .....................................................................................................................
    
def center_padded_image(display_frame, padded_wh, padding_color = (40, 40, 40)):
    
    ''' 
    Function which takes an input image and centers it into a larger image with dimensions of padded_wh
    Does not perform an up/downscaling!
    '''
    
    # Get frame sizing so we can figure out padding needed
    frame_height, frame_width = display_frame.shape[0:2]
    
    # Figure out width padding
    empty_width = max(padded_wh[0] - frame_width, 0)
    left_pad = int(empty_width / 2)
    right_pad = empty_width - left_pad
    
    # Figure out height padding
    empty_height = padded_wh[1] - frame_height
    top_pad = int(empty_height / 2)
    bot_pad = empty_height - top_pad
    
    return cv2.copyMakeBorder(display_frame, 
                              top = top_pad, 
                              bottom = bot_pad, 
                              left = left_pad, 
                              right = right_pad, 
                              borderType = cv2.BORDER_CONSTANT,
                              value = padding_color)
    
# .....................................................................................................................

def make_mask(frame_wh, mask_zones_list, zones_are_normalized = True, 
              invert = False, return_1d = True, mask_line_type = cv2.LINE_4):
    
    '''
    Function which creates a mask frame, given a frame width/height, and list of zones.
    Note that zones are interpretted as being masked-off areas,
    this means that they will be filled in with black in the output frame (white everwhere else)
    
    
    Inputs:
        frame_wh -> List/tuple. Should contain the width & height of the frame the mask will be applied to.
        
        mask_zones_list -> Tuple/list. Should have the form: list of list of lists. The inner lists represent the 
                           x/y co-ords defining a points in the zone polygon. 
                           The next list up represents separate zones, while the outermost list is used
                           to bundle all zones together. Note this format must be used, even if 
                           only a single zone is defined. For example:
                               single_zone_list = [ [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]] ]
                               
        zones_are_normalized -> Boolean. If True, the function will use the provided frame width/height information
                                to scale the zone co-ordinates into pixel values
                                
        invert -> Boolean. If True, the mask image will be inverted, so that the provided zones appear
                  white in the output image, and the rest of the image is black
                  
        return_1d -> Boolean. If True, the returned image will not have any color channels. The 1D shape will
                     be (w, h) whereas the non-1D shape will be (w, h, 3), 
                     where w/h are the provided frame_wh values
                     
        mask_line_type -> Integer. Flag used to decide which line type will be used by OpenCV. 
                          (see cv2.LINE_4, cv2.LINE_8, cv2.LINE_AA). This value affects how the
                          edges of the masked zones will be drawn. The default should be fine for almost all cases!
                          
    Outputs:
        frame_mask -> Numpy array (np.uint8)
    '''
    
    # For convenience
    frame_width, frame_height = frame_wh
    frame_scaling = np.float32((frame_width - 1, frame_height - 1)) if zones_are_normalized else np.float32((1,1))
    
    # Build the initial (full) mask frame
    mask_bg_color = 255 if return_1d else (255, 255, 255)
    frame_shape = (frame_height, frame_width) if return_1d else (frame_height, frame_width, 3)
    frame_mask = np.full(frame_shape, mask_bg_color, dtype = np.uint8)
    
    # Draw masked zones onto the full frame
    mask_fg_color = 0 if return_1d else (0, 0, 0)
    for each_zone in mask_zones_list:
        zone_def_px = np.int32(np.round(each_zone * frame_scaling))
        cv2.fillPoly(frame_mask, [zone_def_px], mask_fg_color, mask_line_type)
        #cv2.polylines(frame_mask, [zone_def_px], True, mask_fg_color, 1, mask_line_type)
    
    # Invert the mask if needed
    if invert:
        frame_mask = cv2.bitwise_not(frame_mask)
    
    return frame_mask

# .....................................................................................................................

def image_to_row_vector(frame):
    
    ''' Function which converts an image (grid of values) into a row vector '''
    
    numel = np.prod(frame.shape[0:2])
    num_channels = 1 if len(frame.shape) < 3 else frame.shape[2]
    return np.reshape(frame, (numel, num_channels))

# .....................................................................................................................

def crop_y1y2x1x2_from_zones_list(frame_wh, zones_list, zones_are_normalized = True):
    
    '''
    Function which returns crop-cordinates, in y1, y2, x1, x2 format, for each zone in the provided zones_lists.
    Note that this format (y1, y2, x1, x2) is meant to be easy to use with numpy for cropping. For example:
        cropped_frame = original_frame[y1:y2, x1:x2]
    
    Inputs:
        frame_wh -> Tuple/list. Should contain width/height of the frame being cropped. These values are used
                    to scale zone points into pixel co-ordinates (assuming they're normalized) as well as to
                    prevent crop-cordinates from exceeding the frame boundary
                     
        zones_list -> Tuple/list. Should have the form: list of list of lists. The inner lists represent the 
                      x/y co-ords defining a points in the zone polygon. The next list up represents separate zones,
                      while the outermost list is used to bundle all zones together. Note this format must be 
                      used, even if only a single zone is defined. For example:
                          single_zone_list = [ [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]] ]
                          
        zones_are_normalized -> Boolean. If True, the function will use the provided frame width/height information
                                to scale the zone co-ordinates into pixel values
                                
    Outputs:
        crop_y1y2x1x2_list -> List of tuples. Contains cropping coordinates, in y1, y2, x1, x2 format, 
                              for each of the zones provided in the input zones_list value. 
                              Note that the coordinates are returned in pixels, 
                              regardless of whether the input is normalized!
                              
        bounding_y1y2x1x2 -> Tuple. Contains the outer-most crop coordinates that encompasses all of the provided
                             zones. This is likely the more convenient output if only a single zone was provided,
                             or if all zones are being cropped/processed as one.
    '''
    
    # For convenience
    frame_width, frame_height = frame_wh
    frame_scaling = np.float32((frame_width - 1, frame_height - 1)) if zones_are_normalized else np.float32((1,1))
    
    # Initialize outputs
    crop_y1y2x1x2_list = []
    bounding_y1 = frame_height
    bounding_y2 = 0
    bounding_x1 = frame_width
    bounding_x2 = 0
    
    # Loop over all zones and figure out the cropping co-ords
    for each_zone in zones_list:
        
        # Convert zone definition to pixels, if needed
        zone_def_px = np.int32(np.round(frame_scaling * each_zone))
        
        # Get cropping co-ordinates
        zone_mins = np.min(zone_def_px, axis = 0)
        zone_maxs = np.max(zone_def_px, axis = 0)
        crop_tl_br = [zone_mins, zone_maxs]
        crop_tl_br = np.clip(crop_tl_br, (0,0), (frame_width - 1, frame_height - 1))
        
        # Get the cropped frame mask  & crop co-ordinates
        y1, y2, x1, x2 = crop_tl_br[0][1], crop_tl_br[1][1] + 1, crop_tl_br[0][0], crop_tl_br[1][0] + 1
        new_crop_y1y2x1x2 = (y1, y2, x1, x2)
        crop_y1y2x1x2_list.append(new_crop_y1y2x1x2)
        
        # Update the bounding co-ords
        bounding_y1 = min(y1, bounding_y1)
        bounding_y2 = max(y2, bounding_y2)
        bounding_x1 = min(x1, bounding_x1)
        bounding_x2 = max(x2, bounding_x2)
        
    # Bundle the bounding crop-cordinates (i.e. co-ordinates that capture the full set of zones)
    bounding_y1y2x1x2 = (y1, y2, x1, x2)
    
    return crop_y1y2x1x2_list, bounding_y1y2x1x2

# .....................................................................................................................

def crop_pixels(frame, crop_y1y2x1x2, create_copy = False):
    
    ''' Function which crops an image, given a set of crop co-ordinates in the sequence y1, y2, x1, x2 '''
    
    cy1, cy2, cx1, cx2 = crop_y1y2x1x2
    return frame.copy()[cy1:cy2, cx1:cx2] if create_copy else frame[cy1:cy2, cx1:cx2]

# .....................................................................................................................

def color_list_to_image(color_list, image_height = 30):
    
    '''
    Function which converts a list of color tuples to a numpy image (single channel!). 
    Assumes the list is meant to be interpretted as the columns of the output image.
    Input color list should have the form:
        color_list = [[1, 2, 3], 
                      [55, 0, 33], 
                      [255, 255, 255], 
                      ... ]
    '''
    return np.repeat(np.expand_dims(np.uint8(color_list), 0), image_height, axis = 0)

# .....................................................................................................................

def pixelate_image(image, pixelation_factor = 4):
    
    orig_height, orig_width = image.shape[0:2]
    original_dsize = (orig_width, orig_height)
    downscale_factor = 1.0/pixelation_factor
    downscaled_image = cv2.resize(image, dsize = None, fx = downscale_factor, fy = downscale_factor,
                                  interpolation = cv2.INTER_NEAREST)
    
    return cv2.resize(downscaled_image, dsize = original_dsize, interpolation = cv2.INTER_NEAREST)

# .....................................................................................................................
# .....................................................................................................................




# ---------------------------------------------------------------------------------------------------------------------
#%% Demo

if __name__ == "__main__":
    
    frame_width = 600
    frame_height = 300
    frame_wh = (frame_width, frame_height)
    ex_frame = np.random.randint(0, 255, (frame_height, frame_width, 3), dtype=np.uint8)
    
    ex_zones = [[ [0.0, 0.0], [1.0, 0.0], [0.5, 0.5] ]]
    
    mask_frame = make_mask(frame_wh, ex_zones, return_1d = False)
    
    clist, blist = crop_y1y2x1x2_from_zones_list(frame_wh, ex_zones)
    
    cropframe = crop_pixels(ex_frame, blist)
    
    cv2.imshow("ORIG", ex_frame)
    cv2.imshow("MASK", mask_frame)
    cv2.imshow("CROP", cropframe)
    cv2.waitKey(0)
    cv2.destroyAllWindows()
    
    pass

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap

