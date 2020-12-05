#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Dec 17 18:54:22 2018

@author: eo
"""


# ---------------------------------------------------------------------------------------------------------------------
#%% Imports

import socket
from ipaddress import ip_address as ip_to_obj

from multiprocessing import Pool


# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes


# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

# .....................................................................................................................

def get_own_ip(default_missing_ip = "192.168.0.0"):
    
    # From:
    # https://stackoverflow.com/questions/166506/finding-local-ip-addresses-using-pythons-stdlib
        
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        try:
            sock.connect(('10.255.255.255', 1))
            ip_addr = sock.getsockname()[0]
        except:
            ip_addr = default_missing_ip
        
    return ip_addr

# .....................................................................................................................
    
def build_rtsp_string(ip_address, username, password = "", route = "", port = 554,
                      when_ip_is_bad_return = ""):
    
    ''' Function which takes in rtsp connection components and builds a full rtsp string (url) '''
    
    # Bail if the ip isn't valid
    valid_ip = check_valid_ip(ip_address, localhost_is_valid = False)
    if not valid_ip:
        return when_ip_is_bad_return
    
    # Build username/password section
    user_pass_str = username
    user_pass_str += ":{}".format(password) if password else ""
    
    # Build ip/port/route section
    ip_port_route_str = "@" if user_pass_str else ""
    ip_port_route_str += "{}:{:.0f}/{}".format(ip_address, port, route)
    
    # Remove any double slashes (//) after the rtsp:// prefix
    user_pass_str = user_pass_str.replace("//", "/")
    ip_port_route_str = ip_port_route_str.replace("//", "/")
    
    # Finally, build the full rtsp string using the pre-built sections
    rtsp_string = "".join(["rtsp://", user_pass_str, ip_port_route_str])
    
    return rtsp_string

# .....................................................................................................................
    
def parse_rtsp_string(rtsp_string):
    
    '''
    Function which attempts to break down an rtsp string into component parts. Returns a dictionary
    Note that this function may be fooled in cases where additional @ or : symbols exist within the username/password
    '''
    
    # First make sure we got a valid rtsp string!
    search_prefix = "rtsp://"
    string_prefix = rtsp_string[:len(search_prefix)]
    if string_prefix != search_prefix:
        raise TypeError("Not a valid RTSP string: {}".format(rtsp_string))
    
    # Split rtsp prefix from the rest of the info
    rtsp_prefix, info_string = rtsp_string.split(search_prefix)
    
    # Split user/pass from ip/port/route data
    user_pass, ip_port_route = info_string.split("@") if "@" in info_string else ("", info_string)
    
    # Get username/password
    username, password = user_pass.split(":") if ":" in user_pass else (user_pass, "")
    
    # Get ip, port and route
    ip_port, *route = ip_port_route.split("/") if "/" in ip_port_route else (ip_port_route, "")
    ip_address, port = ip_port.split(":") if ":" in ip_port else (ip_port, 554)
    check_valid_ip(ip_address)
    
    # Clean up the port/route values
    port = int(port)
    route = "/".join(route)
    
    # Build the rtsp dictionary for output
    output_rtsp_dict = {"ip_address": ip_address,
                        "username": username,
                        "password": password,
                        "port": port,
                        "route": route}
    
    return output_rtsp_dict
    
# .....................................................................................................................
    
def check_valid_ip(ip_address, localhost_is_valid = True):
    
    '''
    Function which tries to check if a provided IP address is valid
    Inputs:
        ip_address -> (String) The ip address to check
    
        localhost_is_valid -> (Boolean) If true the provided IP address can be the string 'localhost' and
                              this function will report the address as being valid
    
    Outputs:
        ip_is_valid (Boolean)
    '''
    
    # Special case check for localhost
    if localhost_is_valid and _ip_is_localhost(ip_address):
        return True
    
    # Try to create an ip address object, which will fail if the ip isn't valid
    try:
        ip_to_obj(ip_address)
        
    except ValueError:
        return False
    
    return True

# .....................................................................................................................

def check_connection(ip_address, port = 80, connection_timeout_sec = 3, localhost_is_valid = True):
    
    '''
    Function used to check if a connection is valid
    Works by trying to make a socket connection on a given port
    
    Inputs:
        ip_address -> (String) IP address to attempt a connection with
        
        port -> (Integer) Port used for connection attempt
        
        connection_timeout_sec -> (integer) Amount of time (in seconds) to wait for a connection attempt
        
        localhost_is_valid -> (Boolean) If true and the provided ip address is the string 'localhost', the
                              function will automatically return true
    
    Outputs:
        connection_success (Boolean)
    
    '''
    
    # Special case check for localhost
    if localhost_is_valid and _ip_is_localhost(ip_address):
        return True
    
    # Intialize output
    connection_success = False
    
    try:
        # Try to connect
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(connection_timeout_sec)
            try:
                sock.connect((ip_address, int(port)))
                connection_success = True
            except socket.error:
                connection_success = False
    
    except KeyboardInterrupt:
        connection_success = False

    return connection_success

# .....................................................................................................................

def scan_for_open_port(port,
                       connection_timeout_sec = 0.5,
                       base_ip_address = None,
                       n_workers = 32):
    
    '''
    Function used to check connections on a target port, across all ips (#.#.#.1 -to- #.#.#.254) using
    a base ip (if not provided, uses the ip of this computer). Returns a list of ips which have
    the target port open as well as the base IP address that was used
    
    Inputs:
        port -> (Integer) Port to be scanned
        
        connection_timeout_sec -> (Float) Amount of time to wait (per ip address) for a connection attempt
        
        base_ip_address -> (String) Base ip to use for scan (i.e. the first 3 ip components to use for scan)
                                    If not provided, will use the machines own ip as the base
        
        n_workers -> (Integer) Number of parallel workers to use for the scan
    
    Outputs:
        report_base_ip_address, open_ips_list (list of strings)
    
    Note:
    The combined value of timeout and number of workers can greatly alter the amount of time
    needed for this function to complete.
    Roughly, the amount of time needed for this function to complete is given by:
        time to complete (seconds) = 1 + connection_timeout_sec * (256 / n_workers)
    
    '''
    
    # Create the base ip address (using our own ip) if it isn't provided
    if base_ip_address is None:
        base_ip_address = get_own_ip()
    
    # Make sure the base ip has only 3 components, since we want to modify the final 
    try:
        ip_components = base_ip_address.split(".")
        base_ip_address = ".".join(ip_components[0:3])
        
    except (NameError, IndexError, AttributeError):
        base_ip_address = "192.160.0"
    
    # Generate the list of ip addresses to scan (by replacing final ip component with 1-254)
    ip_scan_list = ["{}.{}".format(base_ip_address, k) for k in range(1, 255)]
    
    # Generate list versions of all 'check connection' args, to be passed in to worker pool
    num_ips = len(ip_scan_list)
    port_scan_list = [port] * num_ips
    timeout_scan_list = [connection_timeout_sec] * num_ips
    localhost_valid_scan_list = [False] * num_ips
    
    # Finally, gather all the function arguments for pooling
    args_iter = zip(ip_scan_list, port_scan_list, timeout_scan_list, localhost_valid_scan_list)
    
    # Run the 'check_connection' function in parallel to scan ports
    with Pool(n_workers) as worker_pool:
        connection_success_list = worker_pool.starmap(check_connection, args_iter)
    
    # Take out only the successful connections and format as a list of ip addresses
    check_open_ips_iter = zip(ip_scan_list, connection_success_list)
    open_ips_list = [each_ip for each_ip, port_is_open in check_open_ips_iter if port_is_open]
    
    # Build an output copy of the base ip address, with wildcard to indicate variable ip values
    report_base_ip_address = "{}.*".format(base_ip_address)
    
    return report_base_ip_address, open_ips_list
    
# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Helper functions

# .....................................................................................................................

def _ip_is_localhost(ip_address):
    
    ''' Helper function used to check if the provided IP is just the localhost string '''
    
    return ("localhost" in ip_address)

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap

