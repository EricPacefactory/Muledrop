# Core Configuration

These folders hold configuration utilities for each of the core processing stages. Note that the stages have an order to them and in order for any of the later stages to work, the preceeding stages will need to have some kind of configuration (other than the blank defaults for example). Below is a simple overview of the purpose of each of the stages.

## Core Processing Stages

##### Preprocessor

Used to warp the incoming image data. This is primarily useful for maintaining (as best as possible) the size of an object as it moves throughout the scene (due to perspective effects for example). Consistent object sizing tends to improve detection/tracking performance.

##### Foreground Extractor

Assumes the incoming video can be split into foreground and background elements, then attempts to convert the incoming color image data into a binary image where all foreground elements are white and all background elements are black.

##### Pixel Filter

Experimental. Further modifies the binary image from the foreground extractor using pixel color information. Intended to provide a more general way of altering the binary image, independent of the foreground/background assumption used by the foreground extractor.

##### Detector

Takes a foreground/background binary image ()possibly with additional filtering from the pixel filter stage) and attempts to outline all unique foreground elements.

##### Tracker

Assumes detections belong to persistent objects (which are being repeatedly detected on every frame), and builds a history of positional information of each object over time.
