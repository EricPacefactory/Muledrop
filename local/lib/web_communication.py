#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Apr  4 16:09:19 2019

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
import socketio
import eventlet
import json
import base64

from multiprocessing import Process, Queue, Event

#from threading import Thread, Event
#from queue import Queue


# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes

class Websocket_Server:
    
    # .................................................................................................................
    
    def __init__(self, display_config, controls_json, initial_settings,
                 host = "0.0.0.0", port = 6123, start_immediately = True):
        
        # Store socket ip/port info
        self.host = host
        self.port = int(port)
        
        # Store data used to communicate with the socketio input/outputs
        self._display_queue = Queue()
        self._control_queue = Queue()
        self._save_queue = Queue()
        self._upload_queue = Queue()
        self._client_connected = Event()
        
        # Set up current display
        self._current_display = display_config["initial_display"]
        
        # Build initialization dictionary
        initial_web_config = {"display": display_config,
                              "control": controls_json,
                              "initial": initial_settings}
        
        # Create all the resources needed to set up socket connection
        self._root_namespace = Root_Namespace(initial_web_config,
                                              self._display_queue,
                                              self._control_queue,
                                              self._save_queue,
                                              self._upload_queue,
                                              self._client_connected)        
        self._sio = socketio.Server(async_mode='eventlet')
        self._sio.register_namespace(self._root_namespace)
        self._server_proc = Process(target = self._launch, args = (self.host, self.port, self._sio))
        
        # Launch background process on startup if desired
        if start_immediately:
            self.start()
            
    # .................................................................................................................
    
    def start(self):
        
        # Prevent this from running inside Spyder IDE, since we'll get nothing but problems!
        spyder_slayer()
        self._server_proc.start()
        
    # .................................................................................................................
        
    def close(self):
        self._display_queue.close()
        self._control_queue.close()
        self._upload_queue.close()
        self._server_proc.terminate()
        
    # .................................................................................................................
    
    def has_connection(self):
        is_conn = self._client_connected.is_set()
        ##print("CONNECTED:", is_conn)
        return is_conn
        
    # .................................................................................................................
    
    def wait_for_connection(self, time_to_wait_sec = 60.0):
        return self._client_connected.wait(timeout=time_to_wait_sec)
    
    # .................................................................................................................
        
    def read_all_controls(self, debug_messages = False):
        
        # Look for any json data (i.e. dictionary) over the socket connection
        values_changed_dict = self._read_full_control_queue()
        if values_changed_dict and debug_messages:
            print("CONTROL UPDATE:", values_changed_dict)
        return values_changed_dict
    
    # .................................................................................................................
    
    def read_current_display(self, debug_messages = False):
        
        # Look for any new display selection data over the socket connection
        while not self._display_queue.empty():
            self._current_display = self._display_queue.get()
            if debug_messages:
                print("DISPLAY UPDATE:", self._current_display)
        
        return self._current_display
    
    # .................................................................................................................
    
    def save_trigger(self, debug_messages = False):
        
        # Look for any save trigger data over the socket connection
        confirm_saving = False
        while not self._save_queue.empty():
            confirm_saving = self._save_queue.get()
            if debug_messages:
                print("SAVE CONFIG:", confirm_saving)
        
        return confirm_saving
    
    # .................................................................................................................
    
    def upload_frame_data(self, frame, stage_timing = {}):
        
        # Only upload new data if we aren't currently trying to upload data
        if self._upload_queue.empty():
            
            # Compress frame data, then convert data to base64 encoded string
            _, jpg_frame = cv2.imencode(".jpg", frame)
            jpg_frame_b64 = base64.b64encode(jpg_frame).decode()
            jpg_frame_b64_str = "".join(["data:image/jpg;base64,", jpg_frame_b64])
            
            # Bundle data in a standard format that the client page is expecting
            data = {"frame_b64_str": jpg_frame_b64_str, 
                    "stage_timing": stage_timing}
            self._upload_queue.put(data)
    
    # .................................................................................................................
        
    def _read_full_control_queue(self):
        
        # If data is in the queue, try to empty it all in a single read
        # (otherwise, the loop calling this function might not be able to keep up with sender data rate!)
        data_dict = {}
        while not self._control_queue.empty():
            new_data_dict = self._control_queue.get()
            data_dict.update(new_data_dict)
            
        return data_dict
    
    # .................................................................................................................

    def _launch(self, host, port, sio_ref):
        app = socketio.WSGIApp(sio_ref)
        eventlet.wsgi.server(eventlet.listen((host, port)), app)
        
    # .................................................................................................................
    # .................................................................................................................


# /////////////////////////////////////////////////////////////////////////////////////////////////////////////////////


class Root_Namespace(socketio.Namespace):
    
    # .................................................................................................................
    
    def __init__(self, 
                 initial_config_dict, 
                 display_queue, control_queue, save_queue, upload_queue, 
                 connect_event, debug_messages = True):
        
        # Register namespace at root level
        super().__init__("/")
        
        self._initial_config_dict = initial_config_dict
        self._display_queue = display_queue
        self._control_queue = control_queue
        self._save_queue = save_queue
        self._upload_queue = upload_queue
        self._connect_event = connect_event
        self._debug_mode = debug_messages
        
    # .................................................................................................................
        
    def on_connect(self, sid, environ):
        if self._debug_mode:
            print("(pyws server) CONNECTED", environ.get("REMOTE_PORT"))
        self._connect_event.set()
        
    # .................................................................................................................

    def on_disconnect(self, sid):
        if self._debug_mode:
            print("(pyws server) DISCONNECTED", sid)
        self._connect_event.clear()
        
    # .................................................................................................................
    
    def on_config_request(self, sid, data):
        
        if self._debug_mode:
            print("")
            print("(pyws server) CONFIG REQUEST", data)
            
        self.emit('config_response', self._initial_config_dict)
        
    # .................................................................................................................
    
    def on_control_update(self, sid, data):
        
        print("")
        print("(pyws server) CONTROL UPDATE:")
        data_dict = json.loads(data)
        for each_key, each_value in data_dict.items():
            print(each_key, ":", each_value)
            
        self._control_queue.put(data_dict)
        
    # .................................................................................................................
    
    def on_display_request(self, sid, data):
        
        display_data_dict = json.loads(data)
        display_select = display_data_dict.get("display_select")
        if self._debug_mode:
            print("",
                  "(pyws server) CHANGE DISPLAY UPDATE:",
                  data, sep="\n")
        
        if display_select == "Grid View":
            print("", "Can't handle grid view yet!!!", "", sep="\n")
            return
        
        self._display_queue.put(display_select)
        
    # .................................................................................................................
    
    def on_save_request(self, sid, data):
        
        save_trigger_dict = json.loads(data)
        confirm_save = save_trigger_dict.get("save_config")
        if self._debug_mode:
            print("")
            print("(pyws server) SAVE CONFIG")
            print(data)
        
        self._save_queue.put(confirm_save)
            
    # .................................................................................................................
    
    def on_frame_request(self, sid, data):
        
        while True:
            #print("")
            #print("FRAME REQUESTED!")
            eventlet.sleep(0.125)

            if self._upload_queue.empty():
                continue
            frame_data = self._upload_queue.get()
            self.emit("frame_response", frame_data)
    
    # .................................................................................................................
    # .................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

# .....................................................................................................................

def spyder_slayer():
    import os
    if any(["spyder" in env_var.lower() for env_var in os.environ]):
        raise SystemExit("SPYDER STOPPED - Can't run a socketio server within Spyder. Use a terminal!")

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Demo

if __name__ == "__main__":
    
    import time
    
    print("Starting server as background process...")
    
    demo_display = {}
    
    socket_server = Websocket_Server(start_immediately=False)
    socket_server.start()

    print("", "*** Start control update loop ***", sep="\n")
    try:
        while True:
            socket_server.read_all_controls(debug = True)
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    
    socket_server.close()
        
    '''
    # JAVASCRIPT EXAMPLE:
    # (Don't forget to import client socketio)
    # <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/2.2.0/socket.io.js"></script>
    
    const sio = io("http://localhost:(PORT_NUMBER)");

    sio.on('connect', function(socket){
        console.log("CLIENT CONNECT");
        sio.emit("config_request", JSON.stringify({"CONFIG_REQUEST": true}));
    });
    
    sio.on("config_response", function(data) {
        console.log("CLIENT CONFIG RESPONSE:", data);
    });
    
    sio.on("connect_error", function(err) {
        console.log("SOCKET ERROR - Server not ready?");
    });
    
    function send_data(key_name, value){
        var json_to_send = {key_name: value};
        console.log("SENDING", json_to_send);
        sio.emit("control_update", JSON.stringify(json_to_send));
    }
    '''

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap



        