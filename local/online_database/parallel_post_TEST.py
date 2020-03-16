#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Feb 10 12:40:41 2020

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



from time import sleep, perf_counter
from multiprocessing import Process

from local.lib.ui_utils.cli_selections import Resource_Selector

from local.online_database.auto_post import scheduled_post



#%%

def dummy(value):
    
    if value is None:
        return
    
    else:
        sleep(500)
        
    return

para = Process(target = dummy, args = (None,), daemon = True)
para.start()

sleep(1)

aa = para.join(0.5)
qq = para.terminate()

#%%

'''
# Create selector to choose a camera & get pathing info
selector = Resource_Selector()
project_root_path, cameras_folder_path = selector.get_project_pathing()
camera_select, camera_path = selector.camera()


# Config for scheduled post function
post_func_config = {"server_url": "http://localhost:8000",
                    "cameras_folder_path": cameras_folder_path,
                    "camera_select": camera_select,
                    "post_period_mins": 1.0,
                    "post_on_startup": True,
                    "log_to_file": True}


post_func = Process(target = scheduled_post, kwargs = post_func_config)
post_func.start()


total_run_time_ms = (1000 * 5 * 60)
start_time_ms = (1000 * perf_counter())
time_elapsed_ms = 0


while time_elapsed_ms < total_run_time_ms:
    
    time_elapsed_ms = int(round((1000 * perf_counter()) - start_time_ms))
    print("Alive -", time_elapsed_ms, "ms")
    sleep(10)



post_func.terminate()
'''
'''
STOPPED HERE
- NEED TO INCORPORATE MULTIPROC POST INTO RTSP RUNNER!
    - THEN TEST IT AGAIN WITH RTSP AT MAPLE
    - THINK ABOUT DELETING OLD FILES THAT FAIL TO POST AFTER SOME TIME???
    - IF THAT WORKS, ADD ROUTE DOCUMENTATION TO STARLETTE SERVER
    - THEN DOCKER-IZE THE STARLETTE SERVER
    - THEN TRY AGAIN WITH DOCKER-ED SERVER
    - THEN NEED TO THINK ABOUT DOCKER-IZING THE MAIN SYSTEM & HOW TO CO-ORDINATE/DEPLOY ALL THIS STUFF
    - THEN NEED TO CLEANUP TRAIL X/Y STORAGE!!!
    - THEN MAYBE WE HAVE A v0.1 BETA???
'''