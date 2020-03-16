#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Jun 20 13:07:12 2019

@author: eo
"""


# ---------------------------------------------------------------------------------------------------------------------
#%% Imports

import cv2
import numpy as np


# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes

class Fixed_Line_Cross:
    
    '''
    Class for implementing line segment intersection tests with a fixed line segment
    The input points (line_pt1, line_pt2) can be in pixels or normalized units,
    as long as intersections and/or orientation tests use points with the same units.
    
    If 'is_normalized' is None, the type of the points (normalized or not) will be inferred.
    This input can be set to True/False to force the type (affects drawing).
    (points are assumed to be normalized if all x/y values are less than 2)
    
    Note that the order of line_pt1 & line_pt2 determine the orientation of this line!
    To make sense of the line orientation, consider the line to be the hand of a clock.
    line_pt1 can be thought of as the center of the clock (i.e. the pivot point), 
    line_pt2 can be thought of as the tip of the clock hand.
    
    When running orientation/intersections with this line, points that are on the 'counter-clockwise' side
    of the line are considered negative, while points that are on the 'clockwise' side are positive.
    '''
    
    # .................................................................................................................
    
    def __init__(self, line_pt1, line_pt2, flip_orientation = False, is_normalized = None):
        
        '''
        Inputs:
            line_pt1: Pair of x/y points. Input can be integer (pixels) or floats (fractional pixels or normalized),
                      Represents the 'start' of the line segment, assuming the orientation isn't flipped.
            
            line_pt2: Pair of x/y points, similar to line_pt1, but representing the end of the line segment.
            
            flip_orientation: Boolean. If True, the orientation of the line is interpretted in reverse.
            
            is_normalized: Boolean or None. If None, the 'units' (normalized/pixels) of the provided end points
                           will be inferred (if either contains values >2, they are assumed to be in pixel units)
        
        *** If using this object to check a line intersection with another line segment, 
        *** see the .segment_intersection(...) function
        *** If using this object to check intersections against entire paths, 
        *** see the .path_intersection(...) function
        '''
        
        # Record whether this line is using normalized co-ordinates (if needed)
        if is_normalized is None:
            points_list = [*line_pt1, *line_pt2]
            maximum_location_less_than_2 = all([each_value < 2 for each_value in points_list])
            is_normalized = maximum_location_less_than_2
        self.normalized = is_normalized
        
        # Record raw line points
        self.pt1 = np.array(line_pt1 if not flip_orientation else line_pt2)
        self.pt2 = np.array(line_pt2 if not flip_orientation else line_pt1)
        self.pt_mid = np.mean(np.array((self.pt1, self.pt2)), axis = 0)
        
        # Get bounding box of the line, so we can enable quick box overlap checks (if needed)
        self.line_box_tlbr = self._get_line_bounding_box_tlbr()
        
        # Get line rotation matrix, used to rotate other points relative to itself, to check for line crosses
        self.vector, self.rot_matrix = self._get_line_rotation()
        self.unit_normal_vector = self._calculate_unit_normal()
        
        # Get line length
        self.length = np.linalg.norm(self.vector)
        self.half_length = self.length / 2.0
    
    # .................................................................................................................
    
    def __repr__(self):
        if self.normalized:
            return "Fast Linecross from ({:.3f}, {:.3f}) to ({:.3f}, {:.3f})".format(*self.pt1, *self.pt2)
        else:
            return "Fast Linecross from ({}, {}) to ({}, {})".format(*self.pt1, *self.pt2)
    
    # .................................................................................................................
    
    def return_flipped_orientation_copy(self):
        
        ''' Function which returns a new line with the end points flipped, so that the line orientation is flipped '''
        
        return Fixed_Line_Cross(self.pt2, self.pt1)
    
    # .................................................................................................................
    
    def return_normalized_copy(self, frame_width, frame_height):
        
        ''' Function which returns a normalized copy of this line, using the provided frame width/height values '''
        
        # Don't try to normalize an already normalized line!
        if self.normalized:
            print("", "This line is already normalized!", "Ignoring normalization...", sep="\n")
            return self
        
        # Otherwise apply scaling factor and return a new line
        frame_wh_scaling = np.array((frame_width - 1, frame_height - 1))
        normalized_pt1 = self.pt1 / frame_wh_scaling
        normalized_pt2 = self.pt2 / frame_wh_scaling
        
        return Fixed_Line_Cross(normalized_pt1, normalized_pt2)
    
    # .................................................................................................................
    
    def orient_to_self(self, points_xy):
        
        '''
        Function which rotates/shifts points so that they are mapped into a new co-ordinate system,
        where the fixed line is positioned so that point 1 is located at the origin and oriented vertically. 
        In this orientation, the distance of a point to the line is given by the x-coordinate of the point.
        
        For example, consider the affect on example points 'x' and 'q':
        
               o pt1                    o pt2
           x  /                         |
             /                     q    |
            /           ---->           |
           /                            |
          /    q                        | x
         /                              |
        o pt2                           o pt1
        
        Note that the resulting line is vertically oriented,
        with pt2 above pt1 only when drawn in image co-ordinates (i.e. y-axis is positive downward)
        '''
        
        return np.matmul(self.rot_matrix, (points_xy - self.pt1).T).T
    
    # .................................................................................................................
    
    def revert_orient_to_self(self, rot_points_xy):
        
        '''
        Function for undoing the result of the orient_to_self() function 
        (i.e. map points back into the original coordinate system)
        '''
        
        return np.matmul(self.rot_matrix.T, rot_points_xy) + self.pt1
    
    # .................................................................................................................
    
    def distance_to_single_point(self, point_xy):
        
        '''
        Function which returns the distance of a single point to the line.
        Distances can be negative or positive, depending on which side of the line the point lies on.
        '''
        
        return self.orient_to_self(point_xy)[0]
    
    # .................................................................................................................
    
    def distance_to_points(self, points_xy):
        
        '''
        Function which returns the distances of many points from the line.
        Distances can be negative or positive, depending on which side of the line the point lies on.
        
        The input, points_xy, should be a 2D numpy array, where each row is an xy tuple
        '''
        
        return self.orient_to_self(points_xy)[:, 0]
    
    # .................................................................................................................
    
    def segment_intersection(self, segment_start_xy, segment_end_xy, reverse_segment_direction = False):
        
        '''
        Function for checking for line segment intersections
        Inputs should be xy points with the same units as the fixed line points 
        (can be pixels or normalized as long as units are consistent)
        
        Function returns a tuple:
            intersected, cross_direction, intersection_point
            
            intersected (boolean):
                True if an intersection occurred, otherwise False
                
            cross_direction (String or None)
                 Will return None, 'forward' or 'backward'
                 -> None occurs when there is no intersection
                 -> 'forward' occurs on counter-clockwise to clockwise transistions
                 -> 'backward' occurs on clockwise to counter-clockwise transistions
                 (alternatively, 'forward' occurs when crossing in the same direction as the fixed line normal)
                 See the orient_to_self() docstring for more info on the line orientation!
                
            intersection_point: (floating point xy tuple or None)
                The co-ordinates of the intersection point or None if no intersection
        '''
        
        # Rotate/shift other line segment to make cross-detection simpler
        line_pt1 = segment_end_xy if reverse_segment_direction else segment_start_xy
        line_pt2 = segment_start_xy if reverse_segment_direction else segment_end_xy
        (pt1_x_rot_dist, pt1_y_rot_dist) = self.orient_to_self(line_pt1)
        (pt2_x_rot_dist, pt2_y_rot_dist) = self.orient_to_self(line_pt2)
        
        # Initialize outputs 
        intersected = False
        cross_direction = None
        intersection_point = None
        
        # Check if the line segment crosses the fixed line horizontally (after re-orientation)
        crossed_horizontally, cross_direction = \
        self._check_rotated_horizontal_intersection(pt1_x_rot_dist, pt2_x_rot_dist)
        if not crossed_horizontally:
            return intersected, cross_direction, intersection_point
        
        # Check that the line actually intersects the reference line vertically (didn't skip over it)
        crossed_vertically, intersection_point = \
        self._check_rotated_vertical_intersection(pt1_x_rot_dist, pt1_y_rot_dist, pt2_x_rot_dist, pt2_y_rot_dist)
        if not crossed_vertically:
            return intersected, cross_direction, intersection_point
        
        # If we got here, we've got an intersection
        intersected = True
        
        return intersected, cross_direction, intersection_point
    
    # .................................................................................................................
    
    def _check_rotated_horizontal_intersection(self, rotated_x1, rotated_x2):
        
        '''
        Helper function which checks for horizontal intersections, 
        assuming the inputs have already been rotated to be oriented to the line
        '''
        
        # Note: np.sign(...) & != check seems as fast or faster than np.signbit, even if using bitwise comparison!
        pt1_sign = np.sign(rotated_x1)
        pt2_sign = np.sign(rotated_x2)
        crossed_horizontally = (pt1_sign != pt2_sign)
        
        # Check the cross direction, if needed
        cross_direction = None
        if crossed_horizontally:
            cross_direction = self._cross_direction_lookup(pt1_sign, pt2_sign)
        
        return crossed_horizontally, cross_direction
    
    # .................................................................................................................
    
    def _check_rotated_vertical_intersection(self, rotated_x1, rotated_y1, rotated_x2, rotated_y2):
        
        ''' 
        Helper function which checks for vertical intersections, 
        assuming the inputs have already been rotated to be oriented to the line
        '''
        
        # Using similar triangles to find intersection height on reference line
        dy_over_dx =  (rotated_y1 - rotated_y2) / (rotated_x1 - rotated_x2)
        intersection_height = (rotated_x1 * dy_over_dx) - rotated_y1
        crossed_vertically = (0 < intersection_height < self.length)
        
        # Check the intersection point, if needed
        intersection_point = None
        if crossed_vertically:
            intersection_point = self.revert_orient_to_self((0, -intersection_height))
        
        return crossed_vertically, intersection_point
    
    # .................................................................................................................
    
    def path_intersection(self, path_xy, reverse_path_direction = False):
        
        '''
        Function for checking intersections with entire paths (i.e. many line segments)
        Input should be an array of xy points with the same units as the fixed line points 
        (can be pixels or normalized as long as units are consistent)
        
        Returns a list of intersection events
            Each 'event' is a dictionary containing keys:
                "path_index", "cross_direction", "intersection_point"
        '''
        
        # First re-orient the path to the line orientation
        oriented_path_xy = self.orient_to_self(path_xy)
        
        # Find all potential intersection points, by finding sign changes in the x co-ordinate
        x_signs = np.sign(oriented_path_xy[:, 0])
        x_sign_changes = np.where(np.diff(x_signs))[0]
        
        # Loop through all sign change indices, and check if they correspond to intersection events
        intersection_events_list = []
        for each_idx in x_sign_changes:
            
            # Graqb the line segment where we detected a horizontal sign change
            seg_x1, seg_y1 = oriented_path_xy[each_idx]
            seg_x2, seg_y2 = oriented_path_xy[1 + each_idx]
            
            # Check if the segment also crossed the line vertically (after re-orientation)
            crossed_vertically, intersection_point = \
            self._check_rotated_vertical_intersection(seg_x1, seg_y1, seg_x2, seg_y2)
            
            # Only record intersection if the x-sign changes have a corresponding vertical crossing
            if crossed_vertically:
                cross_direction = self._cross_direction_lookup(np.sign(seg_x1), np.sign(seg_x2))
                new_intersection_event = {"path_index": (1 + each_idx),
                                          "cross_direction": cross_direction,
                                          "intersection_point": intersection_point}
                intersection_events_list.append(new_intersection_event)
            
        return intersection_events_list
    
    # .................................................................................................................
    
    def _get_line_bounding_box_tlbr(self):
        return (np.min([self.pt1, self.pt2], axis = 0), np.max([self.pt1, self.pt2], axis = 0))
    
    # .................................................................................................................
    
    def _get_line_rotation(self):
        
        # Get rotation angle of line
        # (Calculated so that the line vector points up 90 degrees after applying rotation)
        line_vec = self.pt2 - self.pt1
        rot_angle = -(np.pi/2 - np.math.atan2(-line_vec[1], line_vec[0]))
        line_rot_matrix = calculate_rotation_matrix(rot_angle)
        
        return line_vec, line_rot_matrix 
    
    # .................................................................................................................
    
    def _cross_direction_lookup(self, pt1_sign, pt2_sign):
        left_to_right = (pt2_sign > pt1_sign)
        return "forward" if left_to_right else "backward"
    
    # .................................................................................................................
    
    def _calculate_unit_normal(self):
        
        oriented_unit_vector = np.float32((1.0, 0))
        unit_normal_vector = self.revert_orient_to_self(oriented_unit_vector) - self.pt1
        unit_normal_vector = unit_normal_vector / np.linalg.norm(unit_normal_vector)
        
        return unit_normal_vector
    
    # .................................................................................................................
    
    def _calculate_unit_normal_plot_points(self, normal_length_fraction = 0.25):
        
        '''
        Function which returns two xy points (with the same units as the line points) for drawing the normal.
        The length of the line will be set as a fraction of the line length itself
        '''
        
        normal_pt1 = self.pt_mid
        normal_pt2 = normal_pt1 + (normal_length_fraction * self.length * self.unit_normal_vector)
        
        return normal_pt1, normal_pt2
    
    # .................................................................................................................
    
    def draw_self(self, display_frame,
                  line_color = (255, 0, 255), line_thickness = 2, 
                  line_point_1_radius = 3, line_point_2_radius = 3,
                  draw_normal = True):
        
        ''' 
        Function for drawing the fixed line onto an existing frame.
        Note that this function is likely to be slower than a custom made one, 
        due to dealing with possible conversions to pixelized units from normalized inputs.
        
        If speed is a concern, it is better to write a custom drawing function!
        (Access line end points with .pt1, .pt2)
        '''
        
        # Figure out pixel-point conversion
        if self.normalized:
            frame_height, frame_width = display_frame.shape[0:2]
            frame_scaling = np.array((frame_width - 1, frame_height - 1))            
            to_px_func = lambda pointxy: tuple(np.int32(np.round(pointxy * frame_scaling)))            
        else:
            to_px_func = lambda pointxy: tuple(np.int32(np.round(pointxy)))
        
        # Convert line endpoints positions to pixels for drawing
        pt1_px = to_px_func(self.pt1)
        pt2_px = to_px_func(self.pt2)
        
        # Draw the line itself
        cv2.line(display_frame, pt1_px, pt2_px, line_color, line_thickness, cv2.LINE_AA)
        
        # Draw the endpoints if needed
        if line_point_1_radius > 0:
            cv2.circle(display_frame, pt1_px, line_point_1_radius, line_color, -1, cv2.LINE_AA)
        if line_point_2_radius > 0:
            cv2.circle(display_frame, pt2_px, line_point_2_radius, line_color, -1, cv2.LINE_AA)
        
        # Draw normal indicator if needed
        if draw_normal:
            
            # Convert normal co-ords to pixels for drawing
            npt1, npt2 = self._calculate_unit_normal_plot_points()
            npt1_px = to_px_func(npt1)
            npt2_px = to_px_func(npt2)
            cv2.arrowedLine(display_frame, npt1_px, npt2_px, line_color, 1, cv2.LINE_AA, tipLength = 0.2)
            
        return display_frame
            
    # .................................................................................................................
    
    def draw_other_line_segment(self, display_frame, segment_start_xy, segment_end_xy,
                                line_color = (0, 255, 255), line_thickness = 1,
                                line_point_1_radius = 7, line_point_2_radius = 3):
        
        '''
        Helper function for drawing another line segment using similar settings as with draw_self().
        Mostly intended for debugging.
        
        This function will perform the same normalization functions as draw_self(),
        therefore, the input line start/end xy values should have the same units as the ones
        used to define the fixed line segment.
        '''
        
        # Figure out pixel-point conversion
        if self.normalized:
            frame_height, frame_width = display_frame.shape[0:2]
            frame_scaling = np.array((frame_width - 1, frame_height - 1))            
            to_px_func = lambda pointxy: tuple(np.int32(np.round(pointxy * frame_scaling)))            
        else:
            to_px_func = lambda pointxy: tuple(np.int32(np.round(pointxy)))
            
        # Convert the other line endpoints positions to pixels for drawing
        other_pt1_px = to_px_func(segment_start_xy)
        other_pt2_px = to_px_func(segment_end_xy)
        
        # Draw the line itself
        cv2.arrowedLine(display_frame, other_pt1_px, other_pt2_px, line_color, line_thickness, cv2.LINE_AA,
                        tipLength = 0.1)
        
        '''
        # Draw the endpoints if needed
        if line_point_1_radius > 0:
            cv2.circle(display_frame, other_pt1_px, line_point_1_radius, line_color, -1, cv2.LINE_AA)
        if line_point_2_radius > 0:
            cv2.circle(display_frame, other_pt2_px, line_point_2_radius, line_color, -1, cv2.LINE_AA)
        '''
    
    # .................................................................................................................
    
    def draw_reoriented_points(self, points_xy, 
                               negative_points_color = (0, 0, 255), 
                               positive_points_color = (0, 255, 0), 
                               points_radius = 4,
                               line_color = (255, 0, 255), line_thickness = 2,
                               line_point_1_radius = 7, line_point_2_radius = 3,
                               draw_normal = True):
        
        '''
        Function for drawing the line (and points) in the rotated co-ordinate system used to check for intersections.
        Mostly intended for debugging!
        
        Input points_xy can be a list of xy tuples or a 2D numpy array of xy tuples (each row is a point)
        The points should be using the same units as the fixed line.
        '''
        
        # Figure out where the center of the image is, so we can properly position the line
        buffer_size = 1.25
        frame_size = 500 if self.normalized else int(round(buffer_size * self.length))
        buffer_px_size = frame_size / buffer_size
        frame_mid = (frame_size - 1) / 2
        centering_offset = np.array((frame_mid, 0.5*(frame_size + buffer_px_size)))        
        
        # Use line data to re-orient the end points, rather than hard-coding the expected result
        pt1_rot = self.orient_to_self(self.pt1)
        pt2_rot = self.orient_to_self(self.pt2)
        
        # Figure out pixel-point conversion
        if self.normalized:
            max_norm_point = np.max(np.abs([pt1_rot, pt2_rot]))
            scale_factor = buffer_px_size / max_norm_point
            to_px_func = lambda pointxy: tuple(np.int32(np.round(pointxy*scale_factor + centering_offset)))
            
        else:
            to_px_func = lambda pointxy: tuple(np.int32(np.round(pointxy + centering_offset)))
            
        # Convert line endpoints positions to pixels for drawing
        pt1_px = to_px_func(pt1_rot)
        pt2_px = to_px_func(pt2_rot)
        
        # Create a blank frame to draw in to
        display_frame = np.zeros((frame_size, frame_size, 3), dtype=np.uint8)
        
        # Draw the line itself
        cv2.line(display_frame, pt1_px, pt2_px, line_color, line_thickness, cv2.LINE_AA)
        
        # Draw the line endpoints if needed
        if line_point_1_radius > 0:
            cv2.circle(display_frame, pt1_px, line_point_1_radius, line_color, -1, cv2.LINE_AA)
        if line_point_2_radius > 0:
            cv2.circle(display_frame, pt2_px, line_point_2_radius, line_color, -1, cv2.LINE_AA)
        
        # Draw the normal if needed
        if draw_normal:            
            # Convert normal co-ords to pixels in rotated co-ord system for drawing
            npt1, npt2 = self._calculate_unit_normal_plot_points()
            npt1_px = to_px_func(self.orient_to_self(npt1))
            npt2_px = to_px_func(self.orient_to_self(npt2))
            cv2.line(display_frame, npt1_px, npt2_px, line_color, 1, cv2.LINE_AA)
        
        # Draw all the points, mapped into the correct co-ord system
        for each_point in points_xy:
            each_pt_rot = self.orient_to_self(each_point)
            each_pt_px = to_px_func(each_pt_rot)
            each_color = negative_points_color if each_pt_rot[0] < 0 else positive_points_color
            cv2.circle(display_frame, each_pt_px, points_radius, each_color, -1, cv2.LINE_AA)
        
        return display_frame
    
    # .................................................................................................................
    # .................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

# .....................................................................................................................  

def calculate_rotation_matrix(rotation_angle_rad):
    
    '''
    Function for calculation a rotation matrix 
    Apply rotation using:
        np.matmul(rotation_matrix, point - rotation_center)
        
    Rotate the opposite way using:
        np.matmul(rotation_matrix.T, point - rotation_center)
    '''
    
    # Build the rotation matrix using the rotation angle
    cos_a = np.cos(rotation_angle_rad)
    sin_a = np.sin(rotation_angle_rad)
    rot_matrix = np.array(((cos_a, -sin_a), (sin_a, cos_a)), dtype = np.float32)
    
    return rot_matrix

# .....................................................................................................................  

def box_intersection(box_1_tl_br, box_2_tl_br):
    
    '''
    Check if two boxes are overlapping. 
    Assumes boxes are provided in top-left, bot-right format! Will not work properly otherwise.
    
    If a different corner format is being used (eg. top-right, bot-left), points can be re-arranged manually
    If points are not intentionally ordered (e.g. drawing a box around a line segment), can use numpy.
        
        Assume we have two points: pt1, pt2 --> Want to generate tl_br co-ordinates
        Use:
            box_tl_br = (np.min([pt1, pt2], axis=0), np.max([pt1, pt2], axis=0))
    '''
    
    # For readability
    (left_x1, top_y1), (right_x1, bot_y1) = box_1_tl_br
    (left_x2, top_y2), (right_x2, bot_y2) = box_2_tl_br
    
    # Check if box 1 is fully above or below box 2
    box_1_above_box_2 = bot_y1 < top_y2
    box_1_below_box_2 = top_y1 > bot_y2
    if box_1_above_box_2 or box_1_below_box_2:
        return False
    
    # Check if box 1 is fully left or right of box 2
    box_1_left_of_box_2 = right_x1 < left_x2
    box_1_right_of_box_2 = left_x1 > right_x2
    if box_1_left_of_box_2 or box_1_right_of_box_2:
        return False    
    
    return True

# .....................................................................................................................  

def line_segment_intersection(line_segment_a, line_segment_b):
    
    ''' 
    Intersection test between 2 line segments. Doesn't provide intersection point however!
    Works by checking if an infinite extension of line_segment_a would intersect line_segment_b and vice versa.
    If either check fails, the line segments must not intersect!
    
    Only use this if the two line segments are always different.
    If one line is fixed, use the fixed line cross object, it's (~5x) faster!
    '''
    
    # For convenience
    a0, a1 = line_segment_a
    b0, b1 = line_segment_b
    
    # Get 'vector a' formed from line_segment_a points, and 'wing' vectors formed between a0 and b0, b1 points
    # The wing vectors need to be on opposite sides of vector a for infinite line a to intersect line segment b
    v_a0a1 = a1 - a0
    wing_a0b0 = b0 - a0
    wing_a0b1 = b1 - a0
    
    # Calculate cross product of vector a with 'wing' vectors, 
    # which is a measure of area (magnitude) & orientation (sign) between the pairs of vectors
    a_wing_area_0 = np.cross(v_a0a1, wing_a0b0)
    a_wing_area_1 = np.cross(v_a0a1, wing_a0b1)
    
    # Special case: if a and b are co-linear, check if the bounding boxes around each line are overlapping
    a_colinear_with_b = ((a_wing_area_0 == 0) and (a_wing_area_1 == 0))
    if a_colinear_with_b:        
        box_a_tlbr = (np.min(line_segment_a, axis = 0), np.max(line_segment_a, axis = 0))
        box_b_tlbr = (np.min(line_segment_b, axis = 0), np.max(line_segment_b, axis = 0))
        return box_intersection(box_a_tlbr, box_b_tlbr)
    
    # Check if an infinitely long 'line a' would intersect the line_segment_b
    inf_a_would_not_split_b = (np.sign(a_wing_area_0) == np.sign(a_wing_area_1))
    if inf_a_would_not_split_b:
        return False
    
    # Build cross-product vectors for checking if 'infinite b' intersects 'segment a'
    v_b0b1 = b1 - b0
    wing_b0a0 = - wing_a0b0
    wing_b0a1 = a1 - b0
    
    # Check if an infinitely long 'line b' would intersect the line_segment_a
    b_wing_area_0 = np.cross(v_b0b1, wing_b0a0)
    b_wing_area_1 = np.cross(v_b0b1, wing_b0a1)
    inf_b_would_not_split_a = (np.sign(b_wing_area_0) == np.sign(b_wing_area_1))
    if inf_b_would_not_split_a:
        return False
    
    return True

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Re-orientation Demo

if __name__ == "__main__" and True:
    
    cv2.destroyAllWindows()
    
    padding = 20
    frame_size = 500
    
    line_a = np.random.randint(padding, frame_size - 1 - padding, (2, 2))
    line_b = np.random.randint(padding, frame_size - 1 - padding, (2, 2))
    
    
    
    num_points = 7
    line_a_mid = np.int32(np.round(np.mean(line_a, axis=0)))
    points_test = np.random.randint(-50, 50, (num_points, 2)) + np.tile(line_a_mid, (num_points, 1))
    
    line_a = line_a / frame_size
    line_b = line_b / frame_size
    points_test = points_test / frame_size
    
    
    fixed_line = Fixed_Line_Cross(*line_a)
    
    test_frame = np.zeros((frame_size, frame_size, 3), dtype=np.uint8)
    fixed_line.draw_self(test_frame)
    for each_point in points_test:
        pt_px = np.int32(np.round( each_point * (frame_size - 1)))
        cv2.circle(test_frame, tuple(pt_px), 4, (0, 255, 255), -1, cv2.LINE_AA)
    cv2.imshow("ORIGINAL SPACE", test_frame)
    cv2.moveWindow("ORIGINAL SPACE", 10, 10)
    
    alt_frame = fixed_line.draw_reoriented_points(points_test, 
                                                  negative_points_color = (0, 0, 255), 
                                                  positive_points_color = (0, 255, 0))   
    cv2.imshow("REORIENTED", alt_frame)
    cv2.moveWindow("REORIENTED", 100 + frame_size, 10)
    
    cv2.waitKey(0)    
    cv2.destroyAllWindows()
    
# ---------------------------------------------------------------------------------------------------------------------
#%% Intersection Demo

if __name__ == "__main__" and True:
    
    cv2.destroyAllWindows()
    
    padding = 20
    frame_size = 500
    num_examples = 10
    y_pos = 200
    
    for k in range(num_examples):        
    
        # . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .
        
        line_a = np.random.randint(padding, frame_size - 1 - padding, (2, 2))
        line_b = np.random.randint(padding, frame_size - 1 - padding, (2, 2))
        box_a_tlbr = (np.min(line_a, axis=0), np.max(line_a, axis=0))      
        box_b_tlbr = (np.min(line_b, axis=0), np.max(line_b, axis=0)) 
        
        # . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .
        # Draw fixed line image
        fixed_line = Fixed_Line_Cross(*line_a)
        fixed_line_frame = np.zeros((frame_size, frame_size, 3), dtype=np.uint8)
        line_zip_lists = zip([line_a, line_b], [(0, 255, 255), (255, 255, 0)])
        fixed_line.draw_self(fixed_line_frame, line_color = (0, 255, 255), line_thickness = 1)
        fixed_line.draw_other_line_segment(fixed_line_frame, *line_b, line_color = (255, 255, 0), line_thickness = 1)
            
        # Draw fixed line intersection result into frame
        lines_intersect, cross_dir, intersection_point = fixed_line.segment_intersection(*line_b)
        disp_text = "INTERSECTION ({})".format(cross_dir) if lines_intersect else "No intersection"
        disp_color = (0, 0, 255) if lines_intersect else (0, 255, 0)
        cv2.putText(fixed_line_frame, disp_text, (5, 15), cv2.FONT_HERSHEY_SIMPLEX, 0.5, disp_color, 1, cv2.LINE_AA)
        if lines_intersect:
            int_pt_px = tuple(np.int32(np.round(intersection_point)))
            cv2.circle(fixed_line_frame, int_pt_px, 5, disp_color, -1, cv2.LINE_AA)
        
        # . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .
        # Draw line image
        line_frame = np.zeros((frame_size, frame_size, 3), dtype=np.uint8)
        line_zip_lists = zip([line_a, line_b], [(0, 255, 255), (255, 255, 0)])
        for (pt1, pt2), each_color in line_zip_lists:
            cv2.arrowedLine(line_frame, tuple(pt1), tuple(pt2), each_color, 1, cv2.LINE_AA, tipLength = 0.1)
            
        # Draw line intersection result into frame
        lines_intersect = line_segment_intersection(line_a, line_b)
        disp_text = "INTERSECTION" if lines_intersect else "No intersection"
        disp_color = (0, 0, 255) if lines_intersect else (0, 255, 0)
        cv2.putText(line_frame, disp_text, (5, 15), cv2.FONT_HERSHEY_SIMPLEX, 0.5, disp_color, 1, cv2.LINE_AA)
        
        # . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .
        # Draw box image
        box_frame = np.zeros((frame_size, frame_size, 3), dtype=np.uint8)     
        box_zip_lists = zip([box_a_tlbr, box_b_tlbr], [(0, 255, 255), (255, 255, 0)])
        for (each_tl, each_br), each_color in box_zip_lists:     
            cv2.rectangle(box_frame, tuple(each_tl), tuple(each_br), each_color, 1)
            
        # Draw box intersection result into frame
        boxes_intersect = box_intersection(box_a_tlbr, box_b_tlbr)
        disp_text = "INTERSECTION" if boxes_intersect else "No intersection"
        disp_color = (0, 0, 255) if boxes_intersect else (0, 255, 0)
        cv2.putText(box_frame, disp_text, (5, 15), cv2.FONT_HERSHEY_SIMPLEX, 0.5, disp_color, 1, cv2.LINE_AA)
        
        # . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .
        # Show images
        cv2.imshow("FIXED LINE", fixed_line_frame)
        cv2.moveWindow("FIXED LINE", 100, y_pos)
        cv2.imshow("LINE FUNCTION", line_frame)
        cv2.moveWindow("LINE FUNCTION", 150 + frame_size, y_pos)
        cv2.imshow("BOXES", box_frame)
        cv2.moveWindow("BOXES", 200 + 2 * frame_size, y_pos)
        cv2.waitKey(0)
        
    cv2.destroyAllWindows()

# ---------------------------------------------------------------------------------------------------------------------
#%% Performance Demo

if __name__ == "__main__" and False:
    
    from time import perf_counter
    
    padding = 20
    frame_size = 500
    num_examples = 10
    y_pos = 200
    
    num_iter = 10000
    ref_line = np.random.randint(2*padding, frame_size - 1 - 2*padding, (2, 2))
    check_lines = [np.random.randint(padding, frame_size - 1 - padding, (2, 2)) for k in range(num_iter)]
    
    # Pre-define fixed line
    # It isn't faster than the intersection function if it has to be re-initialized each iteration!
    fixed_line = Fixed_Line_Cross(*ref_line)
    
    # Time the fixed line class intersection test
    t1f = perf_counter()
    check_fast = [fixed_line.segment_intersection(*each_line)[0] for each_line in check_lines]
    t2f = perf_counter()
    
    # Time the line segment intersection function
    t1s = perf_counter()
    check_slow = [line_segment_intersection(ref_line, each_line) for each_line in check_lines]
    t2s = perf_counter()
    
    # Check for any mismatches in the outputs
    mismatches = 0
    mismatched_lines = []
    for each_idx, (each_fast, each_slow) in enumerate(zip(check_fast, check_slow)):
        if each_fast != each_slow:
            mismatches += 1
            mismatched_lines.append(check_lines[each_idx])
    print("Mismatched:", mismatches, "({:.0f} %)".format(100 * mismatches / num_iter))
    
    # Print final results for comparison
    print("Fast time (ms):", 1000 * (t2f - t1f), "({:.3f} ms per iter)".format(1000 * (t2f - t1f) / num_iter))
    print("Slow time (ms):", 1000 * (t2s - t1s), "({:.3f} ms per iter)".format(1000 * (t2s - t1s) / num_iter))


# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap

