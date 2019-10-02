#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Jun 19 16:26:12 2019

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

from time import perf_counter

from local.lib.configuration_utils.configurable_setup import Configurable_Setup_Helper

from local.lib.configuration_utils.rule_setup import Rule_Drawer

from local.configurables.external.snapshots.fixed_frequency_snapshots import Snapshots
from local.configurables.external.object_metadata.passthrough_objectmetadata import Object_Metadata
from local.configurables.external.rule_metadata.passthrough_rulemetadata import Rule_Metadata

# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes

'''
STOPPED HERE
- CONSIDER MAKING DRAW-LESS VERSION OF VANISHPOINT CORRECTION (USE FOV IDEA AND WARP PLANE BASED ON PHYSICAL MODEL)
- NEED TO DECIDE HOW TO GENERALIZE RULES
    - WHAT KIND OF DATA IS SAVED
    - DO RULES SAVE THEIR OWN IMAGES, OR REFERENCE SNAPSHOTS?
        - RECORD CURRENT TIME IN RULE METADATA
        - RECORD MOST RECENT SNAPSHOT TIME?
    - DOES RULE DRAWER HANDLE EVERY CASE? WHAT ABOUT CLUMPING (DRAWING CUSTOM OBJECT OUTLINES?)
        - MAY NEED ADDITIONAL DATA
        - DRAW ALL OBJECTS?
        - DRAW ONE OBJECT?
        - DRAW NO OBJECTS? (CLUMPING IS THEN A CUSTOM POLYGON WITH NO OBJECTS?)
        - PROBABLY NEED FUNCTIONS FOR EACH CASE?
        - SHOULD ALSO MAKE HELPER FUNCTIONS FOR GENERATING DRAWING SPECS (NO MANUAL DICTIONARY BUNDLING)
- FIGURE OUT RUN() STRUCTURE FOR RULES, IS THERE A USEFUL GENERAL CASE STRUCTURE?


Saved data/alarms:
- Save 3 independent data sets!
    - Periodic snapshots (only image source) + metadata
    - Object metadata (every object entering/leaving the scene)
    - Rule metadata (when triggered)
    
- Periodic snapshots (Only images saved?!)
    - Periodic snapshot metadata (image_name, timing, objects in frame, snapshot index, etc.)
- Object metadata (saved for every object passing through the scene. Save x,y,w,h,fill,outline, starttime, endtime, objid)
- Rule event metadata (saved when rules trigger. saves rule-specific data + object references, no image!)
'''

'''
STOPPED HERE
- GOT BASIC RULE BUNDLE WORKING
    - WILL NEED TO TEST WITH MULTIPLE RULES...
    - WILL NEED TO GET SAVING WORKING
    - ALSO FIGURE OUT LOAD/SELECTION PROCESS, SINCE IT WILL BE DIFFERENT FOR RULES (NEED A CREATE-NEW-RULE OPTION)

- NEED TO MAKE SNAPSHOT CONFIGURABLE. SHOULD BE PART (END) OF CORE PROC SEQUENCE FOR NOW
    - IDEALLY WOULD BE EXTERNAL (SHARED BY ALL TASKS)
        - NEED TO SAVE/DRAW ALL EVENTS IN UNWARPED SPACE FOR THIS TO WORK! 
        - KIND OF IDEAL ACTUALLY, BUT DIFFICULT FOR FIRST IMPLEMENTATION, SO IGNORE FOR NOW

- STILL NEED TO FIGURE OUT HOW TO HANDLE LOADING OF ALL TASKS + RULES + SAVING RULES
- SHOULD CLEAN UP CORE PROC SEQ. CLASS TO LOOK MORE LIKE THE RULE BUNDLER
- SHOULD ALSO RE-THINK CONFIG HELPER
    - SHOULD SIMPLIFY IT INTO ONLY HOLDING PATHING INFO (AND PROVIDING THAT INFO TO OTHER CLASSES)
    - MAYBE INCLUDE HELPER CLASSES FOR STANDARD SETUP AS WELL (LIKE IT HAS)
'''
# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

# .....................................................................................................................

def _draw_objects_on_frame(display_frame, object_dict, 
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
            nice_id = each_obj.nice_id #(each_id >> 9) # Remove day-of-year offset from object id for nicer display
            cv2.putText(display_frame, "{}".format(nice_id), tuple(tl),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
            
    return display_frame
    

# .....................................................................................................................

def draw_tracked_objects(stage_outputs):
    
    # Grab a copy of the color image that we can draw on
    display_frame = stage_outputs["preprocessor"]["preprocessed_frame"]
    tracked_frame = display_frame.copy()
    
    tracked_object_dict = stage_outputs.get("tracker").get("tracked_object_dict")
    
    show_ids = True
    show_outlines = True
    show_bounding_boxes = False
    show_trails = True
    show_decay = False
    current_time_sec = 0.0
    
    return _draw_objects_on_frame(tracked_frame, tracked_object_dict, 
                                  show_ids, show_outlines, show_bounding_boxes, show_trails, show_decay,
                                  current_time_sec,
                                  outline_color = (0, 255, 0), 
                                  box_color = (0, 255, 0))

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Set up displays

# Build the display manager
#dm = Core_Config_Display_Manager(layout_cols=2)
#dm.register_custom_callback("Potential Objects", draw_potential_objects)
#dm.register_custom_callback("Tracked Objects", draw_tracked_objects, initial_display = True)
#dm.register_custom_callback("Detections", draw_detections)


# ---------------------------------------------------------------------------------------------------------------------
#%% Set up custom override

# Select camera/user/task/video
config_helper = Configurable_Setup_Helper()
config_helper.make_core_selections()

# Set up the video source
vreader, video_wh, video_fps, video_type = config_helper.setup_video_reader()

# Set up background capture
bgcap = config_helper.setup_background_capture(disable_for_configuration = True)

# Set up the core sequence
core_bundle = config_helper.setup_core()

# Set up rules
rule_bundle = config_helper.setup_rules()

# Override rule for configuration
rule_ref, controls_json, initial_settings = rule_bundle.override_for_configuration(rule_name = None,
                                                                                   script_name = "linecross",
                                                                                   class_name = "Linecross_Rule")


# HARD-CODE Setup rule drawer
rule_drawer = Rule_Drawer(rule_ref.drawing_instructions())


snapshot_config_selections = {"cameras_folder": config_helper.cameras_folder,
                              "camera_select": config_helper.camera_select,
                              "user_select": config_helper.user_select,
                              "task_select": config_helper.task_select}

snapper = Snapshots(**snapshot_config_selections, saving_enabled = False)



objdata_config_selections = {"cameras_folder": config_helper.cameras_folder,
                             "camera_select": config_helper.camera_select,
                             "user_select": config_helper.user_select,
                             "task_select": config_helper.task_select}


objdata = Object_Metadata(**objdata_config_selections, saving_enabled = False)


ruledata_config_selections = {"cameras_folder": config_helper.cameras_folder,
                              "camera_select": config_helper.camera_select,
                              "user_select": config_helper.user_select,
                              "task_select": config_helper.task_select}


ruledata = Rule_Metadata(**ruledata_config_selections, saving_enabled = False)
ruledata.register_rules(rule_bundle)


'''
STOPPED HERE
- NEED TO LOOK AT 'REGISTER_RULES' RULEDATA SHOULD FUNCTION WITHOUT IT IDEALLY!
    - EITHER IT IGNORES UNRECOGNIZED RULE NAMES
    - OR GIVES A HELPFUL ERROR MESSAGE
    - OR DYNAMICALLY ADDS RULE NAMES AS IT SEES THEM (MIGHT BE DIFFICULT DUE TO LACK OF RULE TYPE INFO?)
- THEN NEED TO TRY TO GET THIS ALL WORKING WITH A REAL 'FILE_RUNNER' EXAMPLE
    - WILL NEED TO FIGURE OUT HOW TO SAVE RULE DATA!
    - ALSO NEED TO HAVE OBJDATA, RULEDATA, SNAPSHOTS CONFIG LOADING FROM SOMEWHERE (RELY ON DEFAULTS FOR NOW)
- MAYBE CONSIDER GENERATING EXAMPLE RULE IMAGES AND/OR GIFS AS A SAMPLE?!
'''


'''
STOPPED HERE
- LOOK AT CREATING OBJECT METADATA SAVER
    - Mostly done. May consider adding minimum lifetime control to prevent saving object 'blips'
- THEN LOOK AT CREATING A RULE METADATA SAVER (PUT IN RULE BUNDLE?)
- THEN LOOK AT FILE RUNNER, AND TRY TO GET A REAL WORKING SYSTEM, WITH RULE DATA SAVING
    - WILL NEED TO BUILD SYSTEM FOR SAVING RULE ALARM DATA, SEPARATE FROM THE RULES THEMSELVES? (OR USE RULE BUNDLE?!)
    - MAY CONSIDER ATTACHING SNAPSHOTS, OBJECT METADATA SAVING & RULE METADATA SAVING TO RULE BUNDLE!
- NEED TO ADD ENTER/EXIT THICKNESS TO LINE RULE (AT SOME POINT...)
    - PLUS ADD CHECK TO IGNORE OBJECTS THAT HAVE ALREADY VIOLATED THE RULE
    - WOULD BE NICE TO HAVE STANDARD WAY (OBJECT?) OF MANAGING DEBOUNCING/TAGGING OBJECTS TO IGNORE
'''

# ---------------------------------------------------------------------------------------------------------------------
#%% Launch video loop

# Run video loop and return some parameters for debugging purposes
#stage_outputs, stage_timing, rule_outputs, rule_timing = run_rule_config_video_loop(**video_loop_config_data_dict)



# ---------------------------------------------------------------------------------------------------------------------
#%% Manual video loop

from local.lib.configuration_utils.local_ui.local_windows_base import Slideshow_Window
from local.lib.configuration_utils.local_ui.local_timing_window import Local_Rule_Timing_Window
from local.lib.configuration_utils.local_ui.local_controls import Local_Window_Controls
from local.lib.configuration_utils.local_ui.local_playback_window import Local_Playback_Controls

# Try to close any previously opened windows
try: cv2.destroyAllWindows()
except: pass

# Generate stage timing window
timing_window = Local_Rule_Timing_Window()

# Generate a video playback control window
playback_controls = Local_Playback_Controls(vreader, config_helper)

# Generate the local control windows
local_controls = Local_Window_Controls(controls_json, initial_settings)

# Get general display configuration and create the displays
#display_config, display_callbacks = display_manager_ref.get_config_info()
#window_ref_list = _create_display_windows(display_config)
#local_displays = Local_Display_Windows(display_manager_ref) # <-- Ideally do something like this to bundle up behaviour

# Create alarm image display window
rule_window = Slideshow_Window("Events")

# Run video loop
while True:
    
    # .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .
    # Frame reading
    
    # Grab frames from the video source (with timing information for each frame!)
    req_break, input_frame, current_time_elapsed, current_datetime = vreader.read()
    if req_break:
        # Loop the video back at the end if we miss a frame
        vreader.set_current_frame(0)
        core_bundle.reset_all()
        rule_ref.reset()
        continue
    
    # .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .
    # Playback + keypress controls
    
    # Have playback controls manager keypresses (+ video control!)
    req_break, keypress, video_reset = playback_controls.update()
    if req_break:
        break
    
    # Reset all configurables, since the video position was changed unnaturally
    if video_reset:
        core_bundle.reset_all()
        rule_ref.reset()
    
    # .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .
    # Reconfiguration
    
    # Read local controls & update the configurable if anything changes
    values_changed_dict = local_controls.read_all_controls()
    if values_changed_dict:
        rule_ref.reconfigure(values_changed_dict)
        rule_drawer = Rule_Drawer(rule_ref.drawing_instructions())  # Hacky ugly...
        
    # Update rule image display
    rule_window.read_trackbars()
    
    # .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .
    # Main processing
    
    # Handle background capture stage
    bg_outputs = bgcap.run(input_frame, current_time_elapsed, current_datetime)
    
    # Handle core processing
    skip_frame, stage_outputs, stage_timing = \
    core_bundle.run_all(bg_outputs, current_time_elapsed, current_datetime)
    
    
    # Handle rule processing
    if not skip_frame:
        
        # Handle snapshotting
        snapshot_outputs = snapper.run(stage_outputs, current_time_elapsed, current_datetime)
        
        tracker_outputs = stage_outputs.get("tracker")
        
        objdata.run(tracker_outputs, current_time_elapsed, current_datetime)
        
        rule_ref.update_time(current_time_elapsed, current_datetime)
        
        rt1 = perf_counter()
        rule_metadata_list = rule_ref.run(**tracker_outputs, **snapshot_outputs)
        rule_timing = perf_counter() - rt1
        
        if rule_metadata_list:
            print(rule_metadata_list)
            tracked_object_dict = stage_outputs["tracker"]["tracked_object_dict"]
            
            ruledata.run(rule_metadata_list, current_time_elapsed, current_datetime)
            
            rule_frame = stage_outputs.get("preprocessor").get("preprocessed_frame").copy()
            rule_drawer.draw_single_object_alarm(rule_frame, rule_metadata_list, tracked_object_dict, in_place = True)
            rule_window.imshow(rule_frame)
    
    
    # .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .
    # Display
    
    if not skip_frame:
    
        tracked_frame = draw_tracked_objects(stage_outputs)
        
        rule_drawer.draw_rule_spec(tracked_frame, in_place=True)
        cv2.imshow("RULE", tracked_frame)
        
        # Display stage timing
        timing_window.update_timing_display(stage_timing, rule_timing)
        
        # Display images
        #_display_images(window_ref_list, display_callbacks, stage_outputs, rule_ref)
        #local_displays.update_displays(stage_outputs, core_ref)  # <-- Ideally do something like this
        pass


# Deal with video clean-up
vreader.release()
cv2.destroyAllWindows()

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap
