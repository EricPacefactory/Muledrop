# Project Muledrop

(Only tested on: Linux Mint 19.1 Tessa, Python 3.5+)

## Requirements

Small parts of this project rely on a command line tool called [ranger](https://github.com/ranger/ranger), which provides a command-line menu selection screen. On Ubuntu, this can be installed as follows:

`sudo apt install ranger`

Simlarly, [tkinter](https://wiki.python.org/moin/TkInter) is used for providing a GUI selection screen. On Ubuntu, this can be installed as follows:

`sudo apt install python3-tk`

Additionally, these scripts rely on OpenCV. A pip install of OpenCV is included in the requirements file, though a compiled installation is recommended. Version 3.3+ should work fine.

**Important Note:**

These scripts rely on a set of library functions (eolib) which are not included in this repo (yet). As the scripts are finalized, thse will be included, but for now it must be added externally!

## Getting started

All new cameras/users/tasks/videos etc. are added using the editior utilties. For now, these must be accessed individually from the editior utilities folder.

To create a new camera, use the create.py script and follow the prompts. Also remember to add a video for the new camera (also using the create.py script). Video file selection is handled by either **ranger** or **tkinter** (see requirements section), so it is best to have one of these installed to simplify setup.

## Configuration

Once a camera (and video file) entry is available, it can be configured! By default, all cameras are initialized with a pre-determined configuration stored in the defaults folder. The simplest default configuration does nothing, but the defaults can be updated if an effective general-purpose configuration is found.

Camera analysis is split into two major components: core processing stages & external processing. The core processing stages take in raw video frames and sequentially process them to obtain tracking object metadata. External processing performs functions that occur before & after the core processing stages. These include background capture & generation, snapshot capturing and object metadata saving.

To configure core processing stages, the reconfigure_core.py script can be launched, which acts as a command-line hub interface for all core configuration utilities.

There is currently no hub interface for configuring external processing stages. So these must be launched manually by launching the appropriate scripts inside the configuration_utilites folder.

## Analysis

After configuring a camera, the configuration can be run to collect data that would be used for reporting/rule evaluations. Currently only files are supported.

To run analysis on a camera, use the run_file_collect.py script and follow the prompts.

## Core Process Stages

##### Frame Capture

Used to alter the rate at which frames are read into the core processing sequence

##### Preprocessor

Used to warp the incoming image data. The primary benefit is to minimize size differences of objects throughout a given scene (due to perspective effects for example), which helps the later processing stages.

##### Frame Processor

Assumes the incoming video can be split into foreground and background elements, then attempts to convert the incomnig color image data into a binary image where all foreground elements are white and all background elements are black.

##### Pixel Filter

Experimental. Further modifies the binary image from the frame processor using color pixel information. Intended to provide an arbitrary way of altering the binary image, independent of the foreground/background assumption.

##### Detector

Takes a binary image and attempts to outline all unique foreground elements.

##### Tracker

Tries to interpret detections as belonging to persistent objects (which are being repeatedly detected on every frame), and builds a history of positional information of each object.

## External Processing

##### Background Capture/Generation

Repeatedly stores frames from the input video source and occasionally tries to generate an image representing the background of the scene. Import for some types of frame processing as well as implementing ghosting.

##### Snapshot Capture

Repeatedly saves individual frames of the input video source so that events from the video can be reconstructed after-the-fact. These snapshots can also be used to evaluate certain rules (such as looking for idle objects or clutter, for example).

##### Object Metadata Capture

Saves object metadata output from the (core) tracker stage. This data can then be evaluated (after-the-fact) to determine if the object broke any rules. Additionally, with the snapshot images it is possible to visualize the object pathing/behavior.

## MAJOR TODOs

- Set up drawing functionality across all config utilties
- Add preprocessor unwarping to object metadata capturing
- Create example after-the-fact rule evaluation
- Standardize data saving formats
- Standardize database access so that 
- Set up classification functionality
- Re-implement support for web UI
