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
    
    # Bail if the ip isn't valid
    valid_ip = check_valid_ip(ip_address, return_error = False)
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
    
def check_valid_ip(ip_address, return_error = True):
    
    try:
        # Try to create an ip address object, which will fail if the ip isn't valid
        ip_to_obj(ip_address)
        
    except ValueError as err:
        if return_error:
            raise err
        return False
    
    return True

# .....................................................................................................................
    
def check_connection(ip_address, port = 80):
    
    # Intialize output
    good_connection = False
    
    # Try to connect
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(3)
        try:
            sock.connect((ip_address, int(port)))
            good_connection = True
        except socket.error:
            good_connection = False

    return good_connection

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap

