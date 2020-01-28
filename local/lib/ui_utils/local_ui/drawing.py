#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Oct  3 15:59:16 2019

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

from collections import namedtuple, deque

# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes


class Entity_Drawer:
    
    '''
    Class used to handle drawing UI for creating & editing drawn polygons
    Internally represents all point data in pixel units, but all input/output must be in normalized units!
    '''
    
    # .................................................................................................................
    
    def __init__(self, 
                 frame_wh,
                 minimum_entities = 0, 
                 maximum_entities = None, 
                 minimum_points = 3,
                 maximum_points = None,
                 border_size_px = 60,
                 debug_mode = False):
        
        # Safe-ify the input values
        safe_border_size_px = int(round(border_size_px))
        safe_min_entities = minimum_entities if (minimum_entities is not None) else 0
        safe_max_entities = maximum_entities if (maximum_entities is not None) else 1000
        safe_min_points = minimum_points if (minimum_points is not None) else 2
        safe_max_points = maximum_points if (maximum_points is not None) else 10000
        
        # Store defining characteristics
        self.frame_wh = frame_wh
        self.border_size_px = safe_border_size_px
        self.min_entities = safe_min_entities
        self.max_entities = safe_max_entities
        self.min_points_per_entity = max(2, safe_min_points)
        self.max_points_per_entity = safe_max_points 
        self.debug_mode = debug_mode
        
        # Set up possible states & corresponding callbacks
        self.state = "hover"
        self.mouse_state_callbacks = {"hover": self._mouse_hover_callback,
                                      "draw": self._mouse_draw_callback,
                                      "drag": self._mouse_drag_callback}
        self.keypress_state_callbacks = {"hover": self._key_hover_callback,
                                         "draw": self._key_draw_callback,
                                         "drag": self._key_drag_callback}
        
        # Set up callback state storage
        self.mouse_state = namedtuple("Mouse_State", ["click", "double_click", "drag", "release"])
        self.modifier_state = namedtuple("Modifiers", ["alt", "ctrl", "shift"])
        
        # Set up mouse event/state storage, so keypress can access them
        self.mouse_xy_history = deque([np.int32((frame_wh[0] / 2, frame_wh[1] / 2))], maxlen=100)
        
        # Set up entity managment
        self.entity_collection = None
        self.initialize_entities([])
        
        # Storage for drawing style
        self._aesthetics_dict = None
        self.aesthetics()
        
        # Set up variables used to detect and manage changes
        self._entity_change = False
    
    # .................................................................................................................
    
    def __repr__(self):
        
        repr_strs = ["Drawing object - Contains {} entites".format(len(self.entity_collection)),
                     "         Frame size (px): {} x {}".format(*self.frame_wh),
                     "        Border size (px): {}".format(self.border_size_px),
                     "  Min number of entities: {}".format(self.min_entities),
                     "  Max number of entities: {}".format(self.max_entities),
                     "   Min points per entity: {}".format(self.min_points_per_entity),
                     "   Max points per entity: {}".format(self.max_points_per_entity)]
        
        return "\n".join(repr_strs)
    
    # .................................................................................................................
    
    def __call__(self, *args, **kwargs):        
        self.mouse_callback(*args, **kwargs)
        
    # .................................................................................................................
    
    def __len__(self):
        return len(self.entity_collection)
    
    # .................................................................................................................
    
    def _normalize(self, pixelized_points_array):
        
        ''' Function for mapping a pixelized array of points (xy-tuples) into a normalized list '''
        
        # Don't do anything with empty arrays
        empty_array = (pixelized_points_array.size == 0)
        if empty_array:
            return pixelized_points_array.tolist()
        
        # Calculate some handy scaling/offset terms
        frame_w, frame_h = self.frame_wh
        frame_scaling = np.float32((frame_w - 1, frame_h - 1))
        border_offset = np.int32((self.border_size_px, self.border_size_px))
        
        # Convert the input to an array for easier manipulation
        normalized_points_array = np.float32(pixelized_points_array - border_offset) / frame_scaling
        normalized_points_list = normalized_points_array.tolist()
        
        return normalized_points_list
    
    # .................................................................................................................
    
    def _pixelize(self, normalized_points_list):
        
        ''' Function for mapping a normalized list of points (xy-tuples) into a pixelized array '''
        
        # Don't do anything with empty lists
        empty_list = (len(normalized_points_list) == 0)
        if empty_list:
            return np.int32([]).tolist()
        
        # Calculate some handy scaling/offset terms
        frame_w, frame_h = self.frame_wh
        frame_scaling = np.float32((frame_w - 1, frame_h - 1))
        border_offset = np.int32((self.border_size_px, self.border_size_px))
        
        # Convert the input to an array for easier manipulation
        points_array = np.float32(normalized_points_list)
        pixelized_points_array = np.int32(np.round(border_offset + (points_array * frame_scaling)))
        pixelized_points_list = pixelized_points_array.tolist()
        
        return pixelized_points_list
    
    # .................................................................................................................
        
    @property
    def last_mouse_xy(self):
        ''' Return the last mouse co-ordinate (in pixels) '''
        return self.mouse_xy_history[0]
    
    # .................................................................................................................
    
    def get_entities_list(self, normalize = True):
        
        ''' Return a (possibly normalized) list-of-lists-of-tuples representing point xy co-ordinates '''           
        
        if normalize:
            return [self._normalize(each_entity.points()) for each_entity in self.entity_collection]
        return [each_entity.points() - self.border_size_px for each_entity in self.entity_collection]
    
    # .................................................................................................................
    
    def aesthetics(self, finished_color = (0, 255, 255), in_progress_color = (255, 255, 0),
                   finished_thickness = 1, in_progress_thickness = 1,
                   anchor_radius = 3, line_type = cv2.LINE_AA, 
                   show_anchors = True):
        
        ''' Function for changing default color/styling '''
        
        # Update internal record of aesthetics
        self._aesthetics_dict = {"finished_color": finished_color,
                                 "in_progress_color": in_progress_color,
                                 "finished_thickness": finished_thickness,
                                 "in_progress_thickness": in_progress_thickness,
                                 "anchor_radius": anchor_radius,
                                 "line_type": line_type,
                                 "show_anchors": show_anchors}
        
        # Propagate changes to the entity collection
        self.entity_collection.aesthetics(**self._aesthetics_dict)
        
        return self._aesthetics_dict
    
    # .................................................................................................................
    
    def on_change(self, only_on_hover = False):
        
        ''' 
        Function for monitoring changes to the entities being drawn 
        To access modified entity data, use the .get_entities_list() function
        '''
        
        # Get state flags
        hover_flag = (self.state == "hover") if only_on_hover else True
        
        # Check for entity change flag, and if present, consume it!
        if self._entity_change and hover_flag:
            self._entity_change = False
            return True
        
        return False
    
    # .................................................................................................................
    
    def update_frame_wh(self, new_frame_width, new_frame_height):
        
        '''
        Function for updating the known frame size.
        Only use this if the image size is changing over time, 
            otherwise the frame size should be supplied on initialization
        '''
        
        # Figure out how much to scale entity points in x/y directions based on new vs old frame sizing
        old_frame_w, old_frame_h = self.frame_wh
        w_scale = (new_frame_width - 1) / (old_frame_w - 1)
        h_scale = (new_frame_height - 1) / (old_frame_h - 1)
        offset_px = self.border_size_px
        
        # Scale all entities, then update record of frame size
        self.entity_collection.scale_entities(w_scale, h_scale, offset_px)        
        self.frame_wh = (new_frame_width, new_frame_height)
        
        # Update boundaries now that the frame size has changed
        self._set_entity_boundaries()
        
        # Signal change to entities
        self._entity_change = True
        
    # .................................................................................................................
    
    def _set_entity_boundaries(self):
        
        # Simpler names for clarity
        frame_w, frame_h = self.frame_wh
        combined_border_size = 2 * self.border_size_px
        
        # Set boundaries for entity collection so that entities don't draw off the displayed frame
        min_xy = (0, 0)
        max_xy = (combined_border_size + frame_w, combined_border_size + frame_h)
        self.entity_collection.set_entity_boundaries(min_xy, max_xy)
        
    # .................................................................................................................
    
    def initialize_entities(self, entity_list):
        
        '''
        Function for initializing the drawn entities
        Inputs:
            entity_list -> Should be a list of lists of xy-tuples
            Each xy-tuple represents a point, in normalized co-ordinates!
            Each list of xy-tuples represents an entity (i.e. a single polygon or line)
            For example: [[(0.11, 0.40), (0.35, 0.25), (0.70, 0.55)],
                          [(0.11, 0.11), (0.22, 0.22), (0.44, 0.44)],
                          [(0.12, 0.34), (0.56, 0.78), (0.90, 0.98), (0.76, 0.54)]]
        '''
        
        # Create pixelized copies of each entity for internal representation
        pixelized_entity_list = [self._pixelize(each_entity) for each_entity in entity_list]
        
        # Create collection object to handle the group of entities
        self.entity_collection = Entity_Collection(pixelized_entity_list,
                                                   minimum_entities = self.min_entities,
                                                   maximum_entities = self.max_entities,
                                                   minimum_points_per_entity = self.min_points_per_entity,
                                                   maximum_points_per_entity = self.max_points_per_entity,
                                                   debug_mode = self.debug_mode)
        
        # Set boundaries
        self._set_entity_boundaries()
    
    # .................................................................................................................
    
    def replace_drawing_functions(self, new_completed_drawing_function = None, new_inprogress_drawing_function = None):
        
        ''' 
        Function used to override the way entitys are drawn.
        Inputs must be functions with arguments in the form:
            draw_func(frame, points_npint32_array)
        
        Where frame will be the frame data passed in to draw onto, 
        and points_npint32_array will be the entity points that need to be drawn
        
        Any styling/controls should be built into the function itself (it cannot take additional arguments)
        
        Inputs left as 'None' will keep existing drawing style.
        '''
        
        self.entity_collection.replace_drawing_functions(new_completed_drawing_function, 
                                                         new_inprogress_drawing_function)
        
    # .................................................................................................................
        
    def _debug_print(self, print_msg):
        if self.debug_mode:
            print(print_msg)        
        return
        
    # .................................................................................................................
    
    def _get_mouse_state(self, event, flags):
        
        mouse_move = (event == cv2.EVENT_MOUSEMOVE)
        
        # Get left mouse button state
        mouse_left_state = \
        self.mouse_state(click = (event == cv2.EVENT_LBUTTONDOWN),
                         double_click = (event == cv2.EVENT_LBUTTONDBLCLK),
                         drag = ((flags & cv2.EVENT_FLAG_LBUTTON) > 0),
                         release = (event == cv2.EVENT_LBUTTONUP))
        
        # Get middle mouse button (wheel) state
        mouse_mid_state = \
        self.mouse_state(click = (event == cv2.EVENT_MBUTTONDOWN),
                         double_click = (event == cv2.EVENT_MBUTTONDBLCLK),
                         drag = ((flags & cv2.EVENT_FLAG_MBUTTON) > 0),
                         release = (event == cv2.EVENT_MBUTTONUP))
        
        # Get right mouse button state
        mouse_right_state = \
        self.mouse_state(click = (event == cv2.EVENT_RBUTTONDOWN),
                         double_click = (event == cv2.EVENT_RBUTTONDBLCLK),
                         drag = ((flags & cv2.EVENT_FLAG_RBUTTON) > 0),
                         release = (event == cv2.EVENT_RBUTTONUP))
        
        return mouse_move, mouse_left_state, mouse_mid_state, mouse_right_state
    
    # .................................................................................................................
    
    def _get_modifier_state(self, event, flags):
        
        modifiers = self.modifier_state(alt = ((flags & cv2.EVENT_FLAG_ALTKEY) > 0),
                                        ctrl = ((flags & cv2.EVENT_FLAG_CTRLKEY) > 0),
                                        shift = ((flags & cv2.EVENT_FLAG_SHIFTKEY) > 0))
        
        return modifiers
    
    # .................................................................................................................
    
    def _start_hover(self, mxy_array):
        self._change_state("hover")
    
    # .................................................................................................................
    
    def _start_draw(self, mxy_array):        
        self.entity_collection.new_entity_in_progress(mxy_array)
        self._change_state("draw")
    
    # .................................................................................................................
    
    def _start_drag(self, mxy_array, record_history = True):
        
        # Enter dragging mode if the mouse was near enough to a point
        if self.entity_collection.point_in_range(mxy_array):
            self._change_state("drag")
            
            # Manually allow for recording list history, since we may not always want to store every drag start
            if record_history:
                self.entity_collection.record_list_history()
            
    # .................................................................................................................
    
    def _insert_point(self, mxy_array, record_history = True):
        
        # Insert a point into an existing entity, if the user clicked near a line segment
        if self.entity_collection.line_in_range(mxy_array):
            insert_success = self.entity_collection.insert_entity_point(mxy_array, record_history = record_history)
            self._debug_print("INSERT POINT ({})".format("success" if insert_success else "failed"))
            
            # Enter dragging mode on the newly added point because it just feels right
            if insert_success:
                self._start_drag(mxy_array, record_history = False)
                
                # Signal change to entities
                self._entity_change = True
    
    # .................................................................................................................
    
    def _remove_point(self, mxy_array, record_history = True):
        
        # Delete a point if the mouse was near enough
        if self.entity_collection.point_in_range(mxy_array):
            removal_success = self.entity_collection.remove_entity_point(record_history = record_history)
            self._debug_print("REMOVE POINT ({})".format("success" if removal_success else "failed"))
            
            if removal_success:
                
                # Signal change to entities
                self._entity_change = True
        
    # .................................................................................................................
    
    def _remove_entity(self, mxy_array, record_history = True):
        
        # Delete an entire entity if the mouse is near enough to a point or line
        if self.entity_collection.point_in_range(mxy_array):
            self.entity_collection.remove_entity(record_history = record_history)
            self._debug_print("REMOVE ENTITY (from point)")
            
            # Signal change to entities
            self._entity_change = True
            
        elif self.entity_collection.line_in_range(mxy_array):
            self.entity_collection.remove_entity(record_history = record_history)
            self._debug_print("REMOVE ENTITY (from line)")
            
            # Signal change to entities
            self._entity_change = True
            
    # .................................................................................................................
    
    def _draw_add_point(self, mxy_array):
        return self.entity_collection.build_entity_in_progress(mxy_array)
    
    # .................................................................................................................
    
    def _complete_draw(self, mxy_array):
        self.entity_collection.finish_entity_in_progress()
        self._start_hover(mxy_array)
        
        # Signal change to entities
        self._entity_change = True
    
    # .................................................................................................................
    
    def _cancel_draw(self, mxy_array):
        self.entity_collection.clear_entity_in_progress()
        self._start_hover(mxy_array)
    
    # .................................................................................................................
    
    def _drag_point(self, mxy_array):        
        self.entity_collection.move_entity_point(mxy_array)
        
        # Signal change to entities
        self._entity_change = True
        
    # .................................................................................................................
    
    def _complete_drag(self, mxy_array):
        self._start_hover(mxy_array)
        
        # Signal change to entities
        self._entity_change = True
    
    # .................................................................................................................
    
    def mouse_callback(self, event, mx, my, flags, param):
        
        '''
        This callback handles all mouse/window events. It should be passed to a window using:
            cv2.setMouseCallback(window_name, object_instance.mouse_callback)
            
        Alternatively, passing just the object instance will work as well:
            cv2.setMouseCallback(window_name, object_instance)
            
        Note that to react to keypresses, the keypress_callback must be called as well
        (this must be polled in a loop, see keypress_callback help for details)
        '''

        mxy_array = np.int32((mx, my))
        
        # Figure out what the mouse is doing as well as modifier keys
        mouse_move, *mouse_button_states = self._get_mouse_state(event, flags)
        modifier_state = self._get_modifier_state(event, flags)
        
        # Record mouse position changes over time
        self.mouse_xy_history.appendleft(mxy_array)
        
        # Call the appropriate mouse callback, based on the current state
        mouse_state_func = self.mouse_state_callbacks[self.state]
        mouse_state_func(mxy_array, mouse_move, *mouse_button_states, modifier_state)
    
    # .................................................................................................................
    
    def _mouse_hover_callback(self, mxy_array, mouse_move, mouse_left, mouse_mid, mouse_right, modifiers):
        
        ''' 
        This callback handles mouse interactions when the drawer is in the hovering/idle state 
        (i.e. no points-in-progress, not dragging)
        '''
        
        # Shift + left click enters drawing mode
        if modifiers.shift and mouse_left.click:
            self._start_draw(mxy_array)
        
        # Ctrl + left click inserts points into existing entities
        elif modifiers.ctrl and mouse_left.click:
            self._insert_point(mxy_array)
        
        # Left click (no modifiers) enters dragging state
        elif mouse_left.click:
            self._start_drag(mxy_array)
            
        # Ctrl + right click removes entities
        elif modifiers.ctrl and mouse_right.click:
            self._remove_entity(mxy_array)
        
        # Remove nearby points with a single right click
        elif mouse_right.click:
            self._remove_point(mxy_array)
    
    # .................................................................................................................
    
    def _mouse_draw_callback(self, mxy_array, mouse_move, mouse_left, mouse_mid, mouse_right, modifiers):
        
        ''' 
        This callback handles mouse interactions when the drawer is in the drawing state 
        (i.e. points-in-progress) 
        '''
        
        # Shift + left click adds more drawing points
        if modifiers.shift and mouse_left.click:
            self._draw_add_point(mxy_array)
            if self.entity_collection.check_entity_in_progress_complete():
                self._complete_draw(mxy_array)
        
        # Double left click ends drawing
        elif mouse_left.double_click:
            self._complete_draw(mxy_array)
        
        # Right click cancels drawing
        elif mouse_right.click:
            self._cancel_draw(mxy_array)
    
    # .................................................................................................................
    
    def _mouse_drag_callback(self, mxy_array, mouse_move, mouse_left, mouse_mid, mouse_right, modifiers):
        
        '''
        This callback handles mouse interactions when the drawer is in the dragging state
        (i.e. no points-in-progress, but a point was clicked & held)
        '''
        
        # Release left click to end dragging
        if mouse_left.release:
            self._complete_drag(mxy_array)
        
        # Left click & drag to drag existing points around
        elif mouse_left.drag:
            self._drag_point(mxy_array)
            
    # .................................................................................................................
    
    def keypress_callback(self, key_code, modifier_code):
        
        '''
        This callback handles keypress events which affect entities (undoing or nudging for example)
        It must be called in a loop using the keypress output from OpenCV's keypressEx result:
            
            key_code, modifier_code = waitKey_ex(frame_delay_ms)
            this_object_instance.keypress_callback(key_code, modifier_code)
            
        It's important that the keypress_ex value is used, not the normal cv2.waitKey() result, which
        does not contain information needed to catch modifier keys properly!
        '''
        
        # Only react to real keypress events (returns -1 if there is no keypress)
        if key_code != -1:
            
            # Interpret the modifier code, since we'll use these keys to implement certain functions
            mod_shift, mod_caps, mod_ctrl, mod_alt, mod_numlock, mod_super = \
            keypress_modifier_decoder(modifier_code)
            
            # Call the appropriate keypress callback, based on the drawer state
            key_state_func = self.keypress_state_callbacks[self.state]
            key_state_func(key_code, mod_shift, mod_ctrl, mod_alt, self.last_mouse_xy)
            
    # .................................................................................................................
    
    def _key_hover_callback(self, keycode, shift, ctrl, alt, mxy_array):
        
        ''' 
        This callback handles keypress interactions when in the hovering/idle state 
        (i.e. no points-in-progress, no dragging)
        '''
        
        # Nudge points with arrow keys
        self._arrow_nudge(mxy_array, keycode, shift)
        
        # Revert changes to the entity list (ctrl + z)
        self._undo_changes(mxy_array, keycode, ctrl)
            
        # Snap points to border (b key)
        self._snap_point_to_border(mxy_array, keycode)
            
    # .................................................................................................................
    
    def _arrow_nudge(self, mxy_array, keycode, mod_shift):
        
        # List out key values for convenience
        left_arrow = 65361
        up_arrow = 65362
        right_arrow = 65363
        down_arrow = 65364
        arrow_key_pressed = (keycode in [left_arrow, up_arrow, right_arrow, down_arrow])
        
        # Only check for nearby points if an arrow key is actually pressed
        if arrow_key_pressed:
            
            # If the mouse isn't in range of any points, don't do anything
            if not self.entity_collection.point_in_range(mxy_array):
                return
                    
            # Build shift amounts/direction
            amount_to_shift = 1 + 10 * mod_shift
            x_shift = amount_to_shift * (int(keycode == right_arrow) - int(keycode == left_arrow))
            y_shift = amount_to_shift * (int(keycode == down_arrow) - int(keycode == up_arrow))
            self.entity_collection.shift_entity_point(x_shift, y_shift, record_history = True)
            
            # Signal change to entities
            self._entity_change = True
    
    # .................................................................................................................
    
    def _undo_changes(self, mxy_array, keycode, mod_ctrl):
        
        # List out key values for convenience
        lower_z = 122
        upper_z = 90
        undo_pressed = (keycode in [lower_z, upper_z] and mod_ctrl)
        
        # Revert changes to the entity list if ctrl + z is pressed
        if undo_pressed:
            self.entity_collection.undo()
            self._debug_print("UNDO")
            
            # Signal change to entities
            self._entity_change = True
            
    # .................................................................................................................
    
    def _snap_point_to_border(self, mxy_array, keycode):
        
        # List out key values for convenience
        lower_b = 98
        upper_b = 66
        b_pressed = (keycode in [lower_b, upper_b])
        
        # Check if we're near enough to a point, and if that point is near enough to the frame borders to snap
        if b_pressed:        
            if self.entity_collection.point_in_range(mxy_array):            
                snap_success = self.entity_collection.snap_to(min_x = self.border_size_px,
                                                              max_x = self.frame_wh[0] + self.border_size_px,
                                                              min_y = self.border_size_px,
                                                              max_y = self.frame_wh[1] + self.border_size_px,
                                                              record_history = True)
                self._debug_print("SNAP-TO-BORDER ({})".format("success" if snap_success else "failed"))
                
                # Signal change to entities
                self._entity_change = True
    
    # .................................................................................................................
    
    def _key_draw_callback(self, keycode, shift, ctrl, alt, mxy_array):
        
        ''' 
        This callback handles keypress interactions when in the drawing state 
        (i.e. points-in-progress) 
        '''
        
        # Keypress can be used to undo last drawn point
        self._undo_changes(mxy_array, keycode, ctrl)
    
    # .................................................................................................................
    
    def _key_drag_callback(self, keycode, shift, ctrl, alt, mxy_array):
        
        '''
        This callback handles keypress interactions when in the dragging state
        (i.e. no points-in-progress, but a point was clicked & held)
        '''
        
        # Keypresses should do nothing in the dragging state
        
        pass
        
    # .................................................................................................................
    
    def _change_state(self, new_state, debug = True):

        old_state = self.state
        
        if new_state in self.mouse_state_callbacks:
            self.state = new_state
        
        self._debug_print("STATE: {} -> {}".format(old_state, new_state))

    # .................................................................................................................
    
    def add_border_to_frame(self, frame):
        
        # copyMakeBorder(src, top, bottom, left, right, borderType[, dst[, value]]) -> dst
        if self.border_size_px > 0:            
            return cv2.copyMakeBorder(frame,
                                      top = self.border_size_px,
                                      bottom = self.border_size_px,
                                      left = self.border_size_px,
                                      right = self.border_size_px,
                                      borderType = cv2.BORDER_CONSTANT,
                                      value = (40, 40, 40))
        
        return frame.copy()

    # .................................................................................................................
    
    def annotate(self, frame):
        
        '''
        Function for drawing entities onto a given frame. Note this function applies 'in-place' (i.e. no return value)
        Also draws any in-progress entities
        '''
        
        # Add border to incoming frame if needed
        bordered_frame = self.add_border_to_frame(frame)
        
        # Draw all existing entities
        return self.entity_collection.draw_all(bordered_frame, self.last_mouse_xy)
            
    # .................................................................................................................
    
    def mouse_trail(self, frame, line_color = (0, 0, 127), max_thickness = 12, max_history = 85):
        
        '''
        Function for drawing a trail of the mouse history over the frame
        '''
        
        num_history = min(len(self.mouse_xy_history), max_history)
        for each_idx in range(num_history - 1):
            pt1 = tuple(self.mouse_xy_history[each_idx])
            pt2 = tuple(self.mouse_xy_history[1 + each_idx])
            line_thickness = int(round(max_thickness*(num_history - each_idx)/num_history + 1))
            cv2.line(frame, pt1, pt2, line_color, line_thickness, cv2.LINE_AA)
            
    # .................................................................................................................
    # .................................................................................................................


# =====================================================================================================================
# =====================================================================================================================
    
    
class Entity_Collection:
    
    # .................................................................................................................
    
    def __init__(self, 
                 initial_entity_list,
                 minimum_entities = 0, 
                 maximum_entities = None,
                 minimum_points_per_entity = 2,
                 maximum_points_per_entity = None,
                 maximum_undos = 100,
                 debug_mode = False):
        
        '''
        Class used to manage groups of interactive entity objects as well as 'entity-in-progress' objects,
        which are used to show entities as they are being created/drawn
        Works entirely in pixel units!
        '''
        
        # Store defining characteristics
        self.min_entities = minimum_entities
        self.max_entities = maximum_entities
        self.min_points_per_entity = minimum_points_per_entity
        self.max_points_per_entity = maximum_points_per_entity
        self.max_undos = maximum_undos
        self.debug_mode = debug_mode
        
        # Storage for setting entity boundaries
        self.min_xy = np.array((-np.inf, -np.inf))
        self.max_xy = np.array((np.inf, np.inf))
        
        # Storage for drawing style
        self._finished_aesthetics_dict = {}
        self._inprog_aesthetics_dict = {}
        
        # Storage for possible custom drawing functions
        self._entity_draw_func = None
        self._inprog_draw_func = None
        
        # Initialize storage for undo
        self.undo_list_history = deque([], maxlen = maximum_undos)
        
        # Initialize storage for keeping track of most recent closest entities/points/lines
        self._closest_entity = None
        self._closest_point = None
        self._closest_line = None
        
        # Initialize storage for entities
        self.entity_list = self._initialize_entities(initial_entity_list)
        self.entity_in_progress = None
        
        # Set initial drawing style
        self.aesthetics()
    
    # .................................................................................................................
    
    def __repr__(self):
        return "\n\n".join([repr(each_entity) for each_entity in self.entity_list])
    
    # .................................................................................................................
    
    def __len__(self):
        return len(self.entity_list)
    
    # .................................................................................................................
    
    def __iter__(self):
        return iter(self.entity_list)
    
    # .................................................................................................................
    
    def _create_new_entity(self, initial_points = [], minimum_points = None, maximum_points = None,
                           replace_drawing_function = True):
        
        # Use the built-in minimum/maximum point counts if they aren't provided
        minimum_points = self.min_points_per_entity if minimum_points is None else minimum_points
        maximum_points = self.max_points_per_entity if maximum_points is None else maximum_points
        
        # Create the new entity and add a custom drawing function, if available
        new_entity = Interactive_Entity(minimum_points, maximum_points, self.debug_mode)
        new_entity.set_boundaries(self.min_xy, self.max_xy)
        new_entity.aesthetics(**self._finished_aesthetics_dict)
        
        # Add initial points if provided
        if len(initial_points) > 0:
            new_entity.initialize_points(initial_points)
        
        # Add custom drawing function if needed
        if self._entity_draw_func and replace_drawing_function:
            new_entity.update_drawing_function(self._entity_draw_func)
        
        return new_entity
    
    # .................................................................................................................
    
    def _initialize_entities(self, initial_entity_list):
        
        # Build list of entity objects from lists of points
        entity_list = deque([], maxlen = self.max_entities)
        for each_entity_def in initial_entity_list:
            
            # Skip empty entities
            empty_entity = (len(each_entity_def) == 0)
            if empty_entity:
                continue
            
            # Create a new interactive entity object for each set of points
            new_entity = self._create_new_entity(each_entity_def)
            entity_list.append(new_entity)
            
        return entity_list
    
    # .................................................................................................................
    
    def aesthetics(self, finished_color = (0, 255, 255), in_progress_color = (255, 255, 0), 
                   finished_thickness = 1, in_progress_thickness = 1, 
                   anchor_radius = 3, line_type = cv2.LINE_AA, 
                   show_anchors = True):
        
        # Update internal records
        self._finished_aesthetics_dict = {"color": finished_color,
                                          "thickness": finished_thickness,
                                          "anchor_radius": anchor_radius,
                                          "line_type": line_type,
                                          "show_anchors": show_anchors}
        
        # Update internal records
        self._inprog_aesthetics_dict = {"color": in_progress_color,
                                        "thickness": in_progress_thickness,
                                        "anchor_radius": anchor_radius,
                                        "line_type": line_type,
                                        "show_anchors": show_anchors}
        
        # Propagate changes to finished entities
        for each_entity in self.entity_list:
            each_entity.aesthetics(**self._finished_aesthetics_dict)
            
        # Propagate changes to in-progress entity, if available
        if self.entity_in_progress is not None:
            self.entity_in_progress.aesthetics(**self._inprog_aesthetics_dict)
        
        return self._finished_aesthetics_dict, self._inprog_aesthetics_dict
    
    # .................................................................................................................
    
    def record_list_history(self):
        
        ''' Function used to record a copy of all current entity points, so they can be restored later if needed '''
        
        record_list = [each_entity.points() for each_entity in self.entity_list]
        self.undo_list_history.append(record_list)
    
    # .................................................................................................................
    
    def clear_list_history(self):
        
        ''' Function used to forcefully remove all undo history '''
        
        self.undo_list_history.clear()
    
    # .................................................................................................................
    
    def undo(self):
        
        '''
        Function used to restore previous states 
        If an entity-in-progress exists, undo will remove the mostly recently added point
        If no entity-in-progress exists, undo will restore the last recorded copy of all entity points
        '''
        
        # Remove last point from the entity-in-progress if it exists
        if self.entity_in_progress is not None:
            
            if len(self.entity_in_progress) > 1:
                self.entity_in_progress.remove_point(-1)
        
        # Otherwise, revert entity list to previous state (assuming there is one!)
        elif len(self.undo_list_history) > 0:
            record_list = self.undo_list_history.pop()
            self.entity_list = self._initialize_entities(record_list)
    
    # .................................................................................................................
        
    def replace_drawing_functions(self, new_completed_function = None, new_inprogress_function = None):
        
        # Only replace the 'completed' drawing function if something was provided
        if new_completed_function is not None:
            self._entity_draw_func = new_completed_function
            for each_entity in self.entity_list:
                each_entity.update_drawing_function(new_completed_function)
            
        # Only replace the 'inprogress' drawing function if something was provided
        if new_inprogress_function is not None:
            self._inprog_draw_func = new_inprogress_function
            if self.entity_in_progress is not None:
                self.entity_in_progress.update_drawing_function(new_inprogress_function)
    
    # .................................................................................................................
    
    def new_entity_in_progress(self, new_point_xy):
        
        '''
        Function used to create a special entity-in-progress, intended for drawing feedback
        The entity-in-progress does not become part of the full entity list until calling: 
            finish_entity_in_progress()
        '''
        
        # Create a new entity in progress, with the ability to have no points so it can be drawn up
        new_points = np.int32(new_point_xy)
        new_in_progress = self._create_new_entity(minimum_points = 0, replace_drawing_function = False)
        new_in_progress.aesthetics(**self._inprog_aesthetics_dict)
        new_in_progress.initialize_points(new_points)
        
        # Add a custom drawing function if needed
        if self._inprog_draw_func:
            new_in_progress.update_drawing_function(self._inprog_draw_func)
        self.entity_in_progress = new_in_progress
    
    # .................................................................................................................
    
    def build_entity_in_progress(self, new_point_xy, record_history = True):
        
        ''' Function for building up the entity-in-progress, by appending new points '''
        
        return self.entity_in_progress.add_point(new_point_xy)
        
    # .................................................................................................................
    
    def clear_entity_in_progress(self):
        
        ''' Function which clears/removes the entity-in-progress '''
        
        self.entity_in_progress = None
        
    # .................................................................................................................
    
    def check_entity_in_progress_complete(self):
        
        eip_exists = (self.entity_in_progress is not None)
        max_limit_exists = (self.max_points_per_entity is not None)
        valid_to_check = (eip_exists and max_limit_exists)
        
        return (len(self.entity_in_progress) == self.max_points_per_entity) if valid_to_check else False
    
    # .................................................................................................................
    
    def finish_entity_in_progress(self, record_history = True):
        
        ''' Add entity-in-progress to the entity list '''
        
        # Grab the current set of points from the entity-in-progress
        points_in_progress_px = self.entity_in_progress.points()
        num_points = len(points_in_progress_px)
        
        # Delete the entity in progress regardless of whether it is valid or not
        self.clear_entity_in_progress()
        
        # Don't do anything if there aren't enough points in the entity in progress
        if num_points < self.min_points_per_entity:
            return False
        
        # Create a new 'completed' entity from the entity in progress, assuming it has enough (minimum) points!
        new_entity = self._create_new_entity(points_in_progress_px)
        
        # Record history for using undo, if needed
        if record_history:
            self.record_list_history()
        
        # Add new entity to the deck
        self.entity_list.append(new_entity)
    
    # .................................................................................................................
    
    def set_entity_boundaries(self, min_xy, max_xy):
        
        ''' Function for setting min/max boundaries for all entities '''
        
        # Update internal min/max settings
        self.min_xy = np.array(min_xy)
        self.max_xy = np.array(max_xy)
        
        # Update min/max of any existing entities
        for each_entity in self.entity_list:
            each_entity.set_boundaries(self.min_xy, self.max_xy)
    
    # .................................................................................................................
    
    def remove_entity(self, entity_index = None, record_history = True):
        
        ''' Function for removing an entire entity from the collection '''
        
        # Don't do anything if we would drop below the minimum allowed number of entities
        if len(self.entity_list) <= self.min_entities:
            return
        
        # Record history for using undo, if needed
        if record_history:
            self.record_list_history()
        
        # Use the last known closest entity if the index wasn't explicity provided
        entity_index = self._closest_entity if entity_index is None else entity_index
        
        del self.entity_list[entity_index]
        
    # .................................................................................................................
    
    def scale_entities(self, scale_x, scale_y, offset_px):
        
        ''' Function for applying scaling to all existing entity points. Used to account for frame size changes '''
        
        # Apply scaling to each entity individually
        scale_successes = []
        for each_entity in self.entity_list:
            scale_success = each_entity.scale_points(scale_x, scale_y, offset_px)
            scale_successes.append(scale_success)
            
        # Delete undo history, since it won't be preserved probably if scaling changes
        self.clear_list_history()
        
        return all(scale_successes)
    
    # .................................................................................................................
    
    def insert_entity_point(self, new_point_xy, entity_index = None, line_index = None, record_history = True):
        
        ''' Function used to insert a single point into a specific entity '''
        
        # Record history for using undo, if needed
        if record_history:
            self.record_list_history()
        
        # Use the last known closest entity/point if the indices weren't explicity provided
        entity_index = self._closest_entity if entity_index is None else entity_index
        line_index = self._closest_line if line_index is None else line_index
        
        return self.entity_list[entity_index].insert_point(line_index, new_point_xy)
    
    # .................................................................................................................
    
    def remove_entity_point(self, entity_index = None, point_index = None, record_history = True):
        
        ''' Function for removing a single point from an existing entity '''
        
        # Record history for using undo, if needed
        if record_history:
            self.record_list_history()
        
        # Use the last known closest entity/point if the indices weren't explicity provided
        entity_index = self._closest_entity if entity_index is None else entity_index
        point_index = self._closest_point if point_index is None else point_index
        
        return self.entity_list[entity_index].remove_point(point_index)
    
    # .................................................................................................................
    
    def move_entity_point(self, new_point_xy, entity_index = None, point_index = None, record_history = False):
        
        ''' Function for moving and single point from an existing entity '''
        
        # Record history for using undo, if needed
        if record_history:
            self.record_list_history()
        
        # Use the last known closest entity/point if the indices weren't explicity provided
        entity_index = self._closest_entity if entity_index is None else entity_index
        point_index = self._closest_point if point_index is None else point_index
        
        return self.entity_list[entity_index].move_point(point_index, new_point_xy)
            
    # .................................................................................................................
    
    def shift_entity_point(self, x_shift, y_shift, entity_index = None, point_index = None, record_history = False):
        
        ''' Function for shifting a single point from an existing entity '''
        
        # Record history for using undo, if needed
        if record_history:
            self.record_list_history()
        
        # Use the last known closest entity/point if the indices weren't explicity provided
        entity_index = self._closest_entity if entity_index is None else entity_index
        point_index = self._closest_point if point_index is None else point_index
        
        return self.entity_list[entity_index].shift_point(point_index, x_shift, y_shift)
    
    # .................................................................................................................
    
    def snap_to(self, min_x, max_x, min_y, max_y, max_snap_distance = 25, 
                entity_index = None, point_index = None, record_history = False):
        
        ''' Function for snapping to nearby x/y points '''
        
        # Use the last known closest entity/point if the indices weren't explicity provided
        entity_index = self._closest_entity if entity_index is None else entity_index
        point_index = self._closest_point if point_index is None else point_index
        
        # Get the current target point location and check if it is close enough to snap to a min/max point
        current_points = self.entity_list[entity_index].points()
        target_xy = current_points[point_index]
        new_point_xy = target_xy.copy()
        
        # Build some helpers to write this out a bit more cleanly
        bounds_array = np.int32([(min_x, min_y), (max_x, max_y)])
        absdists_array = np.abs(target_xy - bounds_array)
        
        # Get the closest x/y indices (min edge or max edge) & corresponding distances
        # We want to make sure min/max are checked against one another, so we don't try to snap to both!
        closest_x_idx = np.argmin(absdists_array[:, 0])
        closest_y_idx = np.argmin(absdists_array[:, 1])        
        closest_x_dist = absdists_array[closest_x_idx, 0]
        closest_y_dist = absdists_array[closest_y_idx, 1]
        
        # Update the new point x-location if we're close enough
        change_x = (closest_x_dist < max_snap_distance)
        if change_x:
            new_x = bounds_array[closest_x_idx, 0]
            new_point_xy[0] = new_x
            
        # Update the new point y-location if we're close enough
        change_y = (closest_y_dist < max_snap_distance)
        if change_y:
            new_y = bounds_array[closest_y_idx, 1]
            new_point_xy[1] = new_y
        
        # Only update if we changed x or y values
        if change_x or change_y:
            
            # Record history for using undo, if needed
            if record_history:
                self.record_list_history()
            
            return self.entity_list[entity_index].move_point(point_index, new_point_xy)
        
        return False
    
    # .................................................................................................................
    
    def point_in_range(self, target_xy_nparray, max_match_sq_distance = 50 ** 2):
        
        ''' Function for checking whether a point in an entity is within range of the target xy point '''
        
        # Reset record of closest entity/point/line every time we re-check this
        self._closest_entity = None
        self._closest_point = None
        self._closest_line = None
        
        # Don't try to check closest distance if no entities exist!
        if len(self.entity_list) < 1:
            return False
        
        # First find the squared distance to every point of each entity
        ent_dists = [each_entity.square_distances(target_xy_nparray) for each_entity in self.entity_list]
        
        # Now find the closest distance per entity
        closest_pt_idxs = [np.argmin(each_dists) for each_dists in ent_dists]
        closest_pt_dists = [each_edist[each_idx] for each_edist, each_idx in zip(ent_dists, closest_pt_idxs)]
        
        # Now find the closest point of all entities, and decide if it's within match range
        closest_entity_idx = np.argmin(closest_pt_dists)
        closest_pt_sq_distance = closest_pt_dists[closest_entity_idx]
        closest_pt_idx = closest_pt_idxs[closest_entity_idx]
        within_match_range = (closest_pt_sq_distance < max_match_sq_distance)
        if within_match_range:
            self._closest_entity = closest_entity_idx
            self._closest_point = closest_pt_idx
        
        return within_match_range
    
    # .................................................................................................................
    
    def line_in_range(self, target_xy_nparray, max_match_sq_distance = 50 ** 2):
        
        ''' Function for checking whether a line segment of any entity is within range of the target xy point '''
        
        # Reset record of closest entity/point/line every time we re-check this
        self._closest_entity = None
        self._closest_point = None
        self._closest_line = None
        
        # Don't try to check closest distance if no entities exist!
        if len(self.entity_list) < 1:
            return False
        
        # First find the projection distances to every line segment of each entity
        closest_entity_idx = None
        closest_proj_sq_dist = 1E12
        proj_pt_idx = None
        #proj_pt_xy = None
        for entity_idx, each_entity in enumerate(self.entity_list):
            
            proj_sq_dists, proj_pts = each_entity.line_projections(target_xy_nparray)
            
            # Record projections which are close enough, and try to get the closest among all entities
            shortest_proj_idx = np.argmin(proj_sq_dists)
            shortest_sq_dist = proj_sq_dists[shortest_proj_idx]
            if shortest_sq_dist < closest_proj_sq_dist:
                closest_proj_sq_dist = shortest_sq_dist
                closest_entity_idx = entity_idx
                #proj_pt_xy = proj_pts[shortest_proj_idx]
                proj_pt_idx = shortest_proj_idx
            
        within_match_range = (closest_proj_sq_dist < max_match_sq_distance)
        if within_match_range:
            self._closest_entity = closest_entity_idx
            self._closest_line = proj_pt_idx
            
        return within_match_range
    
    # .................................................................................................................
    
    def draw_all(self, frame, last_mouse_xy):
        
        ''' Function for drawing all entity data onto a given frame. Acts in_place (i.e. no return value!) '''
        
        # Draw all entities in the list
        for each_entity in self.entity_list:
            each_entity.draw(frame)
            
        # Draw the in-progress entity with an additional point (mouse location) to indicate where drawing will occur
        if self.entity_in_progress:
            self.entity_in_progress.draw_with_additional_point(frame, last_mouse_xy)
            
        return frame
    
    # .................................................................................................................
    # .................................................................................................................


# =====================================================================================================================
# =====================================================================================================================


class Interactive_Entity:
    
    def __init__(self, minimum_points = 0, maximum_points = None, debug_mode = False):
        
        '''
        Helper class used to represent polygons with a given min/max number of points
        Includes functions for modifying the polygon points list, as well as handling basic drawing functionality
        Works entirely in pixel units
        '''
        
        # Set up representation variables
        self.points_array = np.int32([[]])
        self.min_points = minimum_points
        self.max_points = maximum_points
        self.debug_mode = debug_mode
        
        # Set up optional out-of-bounds variables
        self.min_xy = np.array((-np.inf, -np.inf))
        self.max_xy = np.array((np.inf, np.inf))
        
        # Set up drawing variables
        self.show_anchors = None
        self.line_gfx = {}
        self.anchor_gfx = {}
        self.aesthetics()
        
        # Set default drawing function
        self._draw_func = self._default_draw
    
    # .................................................................................................................
    
    def __repr__(self):
        
        repr_strs = ["Entity",
                     "  Minimum points: {}".format(self.min_points),
                     "  Current points: {}".format(len(self.points_array)),
                     "  Maximum points: {}".format(self.max_points)]
        
        # Include additional point location, if we have points!
        if not self._have_no_points():
            repr_strs += ["          Min xy: ({}, {})".format(*np.min(self.points(), axis=0)),
                          "          Max xy: ({}, {})".format(*np.max(self.points(), axis=0))]
        
        return "\n".join(repr_strs)
    
    # .................................................................................................................
    
    def __len__(self):
        return len(self.points_array)
    
    # .................................................................................................................
    
    def _update_points_array(self, new_points_array):
        
        ''' Function used to ensure constrained update of points array '''
        
        # Check that we still have a valid number of points before saving
        number_new_points = len(new_points_array)
        min_ok = (number_new_points >= self.min_points if self.min_points is not None else True)
        max_ok = (number_new_points <= self.max_points if self.max_points is not None else True)
        update_success = (min_ok and max_ok)
        
        # Only update the points array if we have a valid number of points
        if not update_success:
            if self.debug_mode:
                print("", 
                      "Can't update entity points! Not within min/max point limits",
                      "  Minimum points: {}".format(self.min_points),
                      "  Maximum points: {}".format(self.max_points),
                      "           Tried: {}".format(number_new_points),
                      sep="\n")
            return update_success
        
        # Apply boundary restrictions
        new_points_array = np.int32(np.clip(new_points_array, self.min_xy, self.max_xy))
        
        # If we get this far, we're allowed to update the points array
        self.points_array = new_points_array
        update_success = True
        
        return update_success
    
    # .................................................................................................................
    
    def _default_draw(self, frame, points_px_npint32):
        
        cv2.polylines(frame, [points_px_npint32], **self.line_gfx)
        if self.show_anchors:
            for each_point in points_px_npint32:
                cv2.circle(frame, tuple(each_point), **self.anchor_gfx)
    
    # .................................................................................................................
    
    def aesthetics(self, color = (0, 255, 255), thickness = 1, anchor_radius = 3, line_type = cv2.LINE_AA, 
                   show_anchors = True):
        
        ''' Function used to set the visual appearance of an entity '''
        
        # Set flag for showing/hiding anchors (i.e. points joining line segments)
        self.show_anchors = show_anchors
        
        # Set up graphical appearance of line drawings
        self.line_gfx = {"isClosed": True,
                         "color": color,
                         "thickness": thickness,
                         "lineType": line_type}
        
        # Set up graphical appear of anchor drawings
        self.anchor_gfx = {"radius": anchor_radius,
                           "color": color,
                           "thickness": -1,
                           "lineType": line_type}
    
    # .................................................................................................................
    
    def set_boundaries(self, min_xy, max_xy):
        
        # Set up boundary restrictions
        self.min_xy = np.array(min_xy)
        self.max_xy = np.array(max_xy)
    
    # .................................................................................................................
    
    def points(self, as_int32_array = True):
        
        ''' Function for returning the entity points (in pixels) as either an int32 array or a list '''
        
        return self.points_array if as_int32_array else self.points_array.tolist()
    
    # .................................................................................................................
    
    def update_drawing_function(self, drawing_function, test_validty = True):
        
        ''' 
        Function used to override the default drawing functionality 
        The new drawing function must have arguments:
            drawing_function(frame, points_npint32_array)
            
        Can be used to change the styling of the drawing 
        (for example, by adding orientation markers or special coloring)
        '''
        
        self._draw_func = drawing_function
    
    # .................................................................................................................
    
    def square_distances(self, target_xy_nparray):
        
        ''' Function which returns the squared distance of every point in the entity to the given target xy point '''
        
        return np.sum(np.square(self.points_array - target_xy_nparray), axis=1)
    
    # .................................................................................................................
    
    def line_projections(self, target_xy_nparray, out_of_bounds_distance = np.inf):
        
        ''' 
        Function which returns the projection distance of the target point to each possible line segment formed
        by sequential pairing of the entity points 
        '''
        
        # Don't do any checks unless we've got at least 2 points!
        if len(self.points_array) < 2:
            return [out_of_bounds_distance], [None]
        
        # Get the entity points we'll use for calculating the projections
        check_points = self.points_array
        roll_points = np.roll(check_points, 1, axis=0)
        
        projection_sq_distances = []
        projection_points = []
        for each_start_point, each_end_point in zip(check_points, roll_points):
            
            # Calculate each line segment vector and the point-to-segment normalized projection
            each_vec = each_end_point - each_start_point
            vec_length = np.linalg.norm(each_vec)
            norm_vec = each_vec / vec_length
            shifted_target = target_xy_nparray - each_start_point
            shadow_length = np.dot(norm_vec, shifted_target)
            
            # If the projection doesn't land on the line segment, we won't bother calculating the projection distance
            norm_shadow = shadow_length / vec_length
            projects_to_line = (0.0 < norm_shadow < 1.0)
            if not projects_to_line:
                projection_sq_distances.append(out_of_bounds_distance)
                projection_points.append(None)
                continue
            
            # If we get here, the point can be projected onto the line, so find the projection distance
            proj_pt = each_start_point + (shadow_length * norm_vec)
            proj_sq_distance = np.sum(np.square(target_xy_nparray - proj_pt))
            projection_sq_distances.append(proj_sq_distance)
            projection_points.append(proj_pt)
        
        return projection_sq_distances, projection_points
    
    # .................................................................................................................
    
    def initialize_points(self, initial_points):
        
        ''' Function used to set initial points of the entity (without having to draw/add them one-by-one) '''
        
        initial_points_array = np.int32(np.atleast_2d(initial_points))
        update_success = self._update_points_array(initial_points_array)
        
        return update_success
    
    # .................................................................................................................
    
    def scale_points(self, scale_x, scale_y, offset_px = 0):
        
        ''' 
        Function used to scale all x/y points by a given amount
        Used to deal with changing window sizes 
        
        Inputs:
            scale_x, scale_y -> amount to scale x/y co-ordinates (1.0 does no scaling)
            offset_px        -> amount to subtract and re-add before and after scaling (used to account for borders)
        '''
        
        # If we have no points, we don't need to scale!
        if self._have_no_points():
            return True
        
        offset_array = np.int32((offset_px, offset_px))
        new_points_array = np.float32(self.points_array - offset_array) * np.float32((scale_x, scale_y))
        new_points_array = np.int32(np.round(new_points_array)) + offset_array
        update_success = self._update_points_array(new_points_array)
        
        return update_success
    
    # .................................................................................................................
    
    def add_point(self, new_point_xy):
        
        ''' Function used to append a point to the entity '''
        
        # Create new array by 'appending' new xy point to old array
        new_points_array = np.concatenate((self.points_array, np.expand_dims(new_point_xy, 0)))
        update_success = self._update_points_array(new_points_array)
        
        return update_success
    
    # .................................................................................................................
    
    def insert_point(self, insert_index, new_point_xy):
        
        ''' 
        Function used to insert a point between two existing points in the entity
        The insertion index will be the index of the newly added point after insertion
        '''
        
        # Create a copy of the previous points array with an additional point added at an arbitrary index
        new_points_array = np.insert(self.points_array, insert_index, new_point_xy, axis = 0)
        update_success = self._update_points_array(new_points_array)
        
        return update_success
    
    # .................................................................................................................
    
    def remove_point(self, removal_index):
        
        ''' Function for removing a specific point for the entity '''
        
        # Create a copy of the previous points array with one entry removed
        new_points_array = np.delete(self.points_array, removal_index, axis = 0)
        update_success = self._update_points_array(new_points_array)
        
        return update_success
    
    # .................................................................................................................
    
    def move_point(self, point_index, new_point_xy):
        
        ''' Function for changing the x/y location of an existing point in the entity '''
        
        # Create a copy of the previous points array with one entry being relocated
        new_points_array = self.points_array.copy()
        new_points_array[point_index] = new_point_xy
        update_success = self._update_points_array(new_points_array)
        
        return update_success
    
    # .................................................................................................................
    
    def shift_point(self, point_index, x_shift, y_shift):
        
        ''' Function used to shift an existing point the entity '''
        
        # Create a copy of the previous points array with on entry being shifted
        current_point_xy = self.points_array[point_index]
        
        # Construct the new point location
        shift_tuple = (x_shift, y_shift)
        shift_array = np.int32(shift_tuple)
        new_point_xy = current_point_xy + shift_array
        
        # Use built-in move to handle change of point location
        self.move_point(point_index, new_point_xy)
        
    # .................................................................................................................
    
    def draw(self, frame):
        
        ''' Function for drawing this entity onto a given frame '''
        
        # Don't do anything if we have no points to draw
        if self._have_no_points():
            return
        
        self._draw_func(frame, self.points_array)
    
    # .................................................................................................................
    
    def draw_with_additional_point(self, frame, new_point_xy):
        
        ''' Function for drawing this entity onto a given frame, with an additional point appended '''
        
        # Append additional point to the end of the array
        points_px_array = np.concatenate((self.points_array, np.expand_dims(new_point_xy, 0)))
        
        # Now draw just like normal
        self._draw_func(frame, points_px_array)
    
    # .................................................................................................................
    
    def _have_no_points(self):
        
        ''' Helper function to deal with case where we have no points for drawing '''
        
        # Return true if we have no points in our array
        return (self.points_array.size == 0)
    
    # .................................................................................................................
    # .................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions
    
# .....................................................................................................................

def waitKey_ex(frame_delay_ms = 1):
    
    '''
    Helper function for reading/interpretting cv2.waitKeyEx() calls 
    
    Inputs: 
        frame_delay_ms --> Integer. If zero, will wait forever for a key press. Otherwise waits X milliseconds.
        (See the regular cv2.waitKey or cv2.waitKeyEx functions for more info)
        
    Outputs:
        keycode, modifier_code
        
        keycode --> Integer, similar to the output of a regular cv2.waitKey call. 
                    Use this to determine which (normal) key was pressed. 
                    For example this value is 113 when q is pressed, 27 on esc key or 32 on spacebar
                    
        modifier_code --> Integer. Encodes modifier keys using an 8-bit (?) value. 
                          This includes shift, ctrl, alt etc.
                          Use the keypress_modifier_decoder function to interpret these values!
    '''
    
    keypress_ex = cv2.waitKeyEx(frame_delay_ms)
    keycode, modifier_code = keypress_ex_decoder(keypress_ex)  
    
    return keycode, modifier_code

# .....................................................................................................................

def keypress_ex_decoder(keypress_ex):
    
    '''
    Takes in a keypress code from cv2.waitKeyEx and splits it into separate outputs for the key pressed and 
    any modifier keys (shift, ctrl, alt etc.) that were active at the same time.
    Note that pressing a modifier key will return a unique keycode!
    
    Inputs:
        keypress_ex --> Integer. Comes from cv2.waitKeyEx function
        
    Outputs:
        keycode, modifier_code
    '''
    
    # Don't bother decoding when no keys are being pressed
    if keypress_ex == -1:
        return -1, None
    
    is_modified = (keypress_ex > 65535)
    keycode = keypress_ex & 0x0000FFFF
    modifier_code = (keypress_ex & 0xFFFF0000) >> 16 if is_modified else None
    
    return keycode, modifier_code

# .....................................................................................................................

def keypress_ex_quit(keypress_ex, quit_on_esc = True, quit_on_q = True):
    
    '''
    Helper function for handling quitting keypresses when using cv2.waitKeyEx
    
    Inputs:
        keypress_ex --> Integer. Comes from cv2.waitKeyEx
        
        quit_on_esc --> Boolean. If true, the esc-key will generate a break request
        
        quit_on_q --> Boolean. If true, the q or Q key will generate a break request
        
    Outputs:
        request_break --> Boolean. If true, the caller of this function should quit/break out of loops
    '''
    
    # Don't bother decoding when no keys are being pressed
    if keypress_ex == -1:
        return False
    
    # Get the keycode separate from any modifiers
    keycode = keypress_ex & 0x0000FFFF
    
    return keycode_quit(keycode, quit_on_esc, quit_on_q)

# .....................................................................................................................

def keycode_quit(keycode, quit_on_esc = True, quit_on_q = True):
    
    ''' Helper function for cancelling/quitting on keypress events '''
    
    # For clarity
    esc_keys = [27] if quit_on_esc else []
    q_keys = [113, 81] if quit_on_q else []
    quit_keys = esc_keys + q_keys
    
    # We'll quit if we catch one of the quit keys
    request_break = (keycode in quit_keys)
    
    return request_break

# .....................................................................................................................

def keypress_modifier_decoder(modifier_code):
    
    '''
    Takes modifier codes from the keypress_ex_decoder function and returns the state of modifier keys.
    Modifier codes appear to be 8-bit numbers with each bit representing the state of a specific modifier key.
    However, 2 states are currently unknown!
    
    Inputs:
        modifier_code --> Integer returned from keypress_ex_decoder
        
    Outputs:
        shift_is_active, capslock_is_active, ctrl_is_active, alt_is_active, numlock_is_active, super_is_active
    '''
    
    # Default to all false if no modifier code is present
    if not modifier_code:
        return False, False, False, False, False, False
    
    # Hard code key checks
    shift_is_active = modifier_code &     0b00000001
    capslock_is_active = modifier_code &  0b00000010
    ctrl_is_active = modifier_code &      0b00000100
    alt_is_active = modifier_code &       0b00001000
    numlock_is_active = modifier_code &   0b00010000
    # missing modifier key
    super_is_active = modifier_code &     0b01000000
    # missing modifier key
    
    return shift_is_active, capslock_is_active, ctrl_is_active, alt_is_active, numlock_is_active, super_is_active

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Demo

if __name__ == "__main__":
    
    # Set display parameters
    frame_width, frame_height = 600, 300
    blank_frame = np.full((frame_height, frame_width, 3), (83, 33, 166), dtype=np.uint8)
    frame_wh = (frame_width, frame_height)
    
    # Set up example drawer
    drawer = Entity_Drawer(frame_wh,
                           minimum_entities = 0,
                           maximum_entities = 100,
                           minimum_points = 0,
                           maximum_points = None)
    
    # Some example starting points
    test_points = [[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]]
    drawer.initialize_entities(test_points)
    
    # Window creation & callback assignment
    window_name = "DRAWING EXAMPLE"
    cv2.namedWindow(window_name)    
    cv2.setMouseCallback(window_name, drawer)


    while True:
        
        # Get a clean copy of the video
        display_frame = blank_frame.copy()
        
        # Get changes in zone data
        if drawer.on_change():
            print("Changed!")
            print(drawer.get_entities_list())
        
        # Draw annotations
        drawn_frame = drawer.annotate(display_frame)
        cv2.imshow(window_name, drawn_frame)
        
        # Get keypresses
        keycode, modifier = waitKey_ex(10)
        if keycode_quit(keycode):
            break
        
        drawer.keypress_callback(keycode, modifier)
        
    # Clean up windows
    cv2.destroyAllWindows()

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap

