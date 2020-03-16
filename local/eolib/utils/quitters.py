#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Jan  7 10:57:49 2020

@author: eo
"""



# ---------------------------------------------------------------------------------------------------------------------
#%% Imports

import os

# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes



# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

# .....................................................................................................................

def ide_catcher(catch_error_message = "IDE Catcher quit"):
    
    ''' Helper function which quits only if we're inside of certain (Spyder) IDEs. Otherwise does NOT quit '''
    
    # Check for spyder IDE
    if any([("spyder" in envkey.lower()) for envkey in os.environ.keys()]): 
        raise SystemExit(catch_error_message)
    
    return

# .....................................................................................................................
        
def ide_quit(ide_error_message = "IDE Quit", prepend_empty_newlines = 1):
    
    ''' Helper function which safely handles quitting in terminals or certain (Spyder) IDEs '''
    
    # Print some newlines before quitting, for aesthetic reasons
    print(*[""] * prepend_empty_newlines, sep = "\n")
    
    # Try to quit from IDE catcher first (otherwise use python quit, which is cleaner)
    ide_catcher(ide_error_message)
    quit()

# .....................................................................................................................

def debug_quit(quit_message = "DEBUG QUIT", prepend_empty_newlines = 1):
    
    ''' Helper function (meant to be used only while debugging) to prematurely end a script '''
    
    print(*[""] * prepend_empty_newlines, sep = "\n")
    raise SystemExit(quit_message)
    
# .....................................................................................................................
# .....................................................................................................................
    

# ---------------------------------------------------------------------------------------------------------------------
#%% Demo

if __name__ == "__main__":
    
    ide_quit("Quit from spyder IDE")    
    #debug_quit()

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap

