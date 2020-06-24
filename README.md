# Project Muledrop

(Only tested on: Linux Mint 19.1 Tessa, Python 3.6.7)

## Requirements

Some of the configuration tools for this project rely on a command line program called [ranger](https://github.com/ranger/ranger), which provides a command-line menu selection screen. On Ubuntu, this can be installed as follows:

`sudo apt install ranger`

Simlarly, [tkinter](https://wiki.python.org/moin/TkInter) is used for providing a GUI selection screen. On Ubuntu, this can be installed as follows:

`sudo apt install python3-tk`

Additionally, these scripts rely on OpenCV. A pip install of OpenCV is included in the requirements file, though a compiled installation is recommended. The compiled version has better support for some features (like recording) and runs faster (+30%) than the pip install. Version 3.3+ should work fine, including version 4+.

To install the python requirements, use:

`pip3 install -r requirements.txt`

This command should be called from the root project folder (where the requirements file is located). But keep in mind this will pip install OpenCV!

## Getting started

In order to generate/save reporting data, the system needs to have a camera entry which is used to organize all data coming from a single source/scene. At least one video source should also be associated with the camera entry, so that there is some data to analyze! The video can be a file or an RTSP networked source.

The `editor.py` script (found in the root folder of the project) can be used to create new camera entries, along with assigning video files or RTSP info to a given camera entry, simply launch the script and follow the prompts.

## Configuration

Once a camera (and video file) entry is available, it can be configured! All cameras are initialized with a set of configuration files based on the selection made when creating the camera (using the editor utilities). The simplest default configuration (a 'blank' configuration) does nothing, but some initialization types may do a reasonable job without any additional tweaking, depending on the scene and desired results.

Camera analysis is split into two major components: core processing stages & external processing. The core processing stages take in the raw video frames and sequentially process them to obtain tracking metadata for every object. External processing performs functions that occur before & after the core processing stages. These include background capture & generation, snapshot capturing and saving object metadata.

To configure core processing stages, the `reconfigure.py` script can be launched, which acts as a command-line hub interface for all core configuration utilities.

To configure external processing stages, call `reconfigure.py -e` which will provide options for selecting external stages, instead of core stages.

Alternatively, configuration scripts can be launched manually, they're stored under the `configuration_utilities/core` or `configuration_utilities/externals` accessible from the root project folder.

## Analysis

After configuring a camera, a provided video can be processed to generate data that would be used for reporting/rule evaluations.

To run analysis on a file for a camera, use the `run_file_collect.py` script and follow the prompts. To run analysis on a networked stream, use `run_rtsp_collect.py` but be sure to configure the RTSP access info for the camera through the editor utilities.

Note that each of these scripts can be called with a `-d` flag, which will enable a display while running (so that the tracking behavior can be directly observed as it happens). This can be useful/interesting to check, but beware that it can dramatically slow down data collection!

## Data Pathing

By default, all camera data will be placed in a folder called `cameras` located in the root project folder. This can be problematic if using file syncing software (e.g. Dropbox), since the data saved from analyzing cameras can be quite heavy. To avoid this, a settings file exists which stores the pathing to the cameras folder (per computer), which can be modified to point at some other location (outside of an auto-sync'd folder for example). The file can be found under `settings/pathing_info.json` from the root project folder. Note that the folder and file are created after first creating a camera using the editor utilities, so try that first if you can't find the file.

## Docker (manual use)

The realtime system can be (manually) launched through docker using the following instructions.

#### Build:

From inside the realtime folder:

`docker build -t realtime_image -f ./build/docker/Dockerfile .`

This command will create a docker image (called realtime_image) with all dependencies installed.

#### Run:

From anywhere:

```
docker run -d \
--network="host" \
-v /tmp/realtime:/home/scv2/cameras \
--name realtime \
realtime_image
```

This command will start up a container running the realtime system. The easiest way to confirm the system is running is by going to the control server url (default: `localhost:8181`).

Note that running the realtime system through docker (manually) is often an inconvenient way to use the system. When manually running/reconfiguring files, it is easier to install the system locally!

Also note that the run command above will map persistent data (camera configs) into a temporary folder (`/tmp/realtime`), this may be fine for testing/experimentation, but beware of data loss.

---

## Environment variables:

`AUTOPOST_ON_STARTUP` = 1

`AUTOPOST_PERIOD_MINS` = 2.5

`CAMERAS_FOLDER_PATH` = (none, defaults to the project foot folder)

`DBSERVER_PROTOCOL` = http

`DBSERVER_HOST` = localhost

`DBSERVER_PORT` = 8050

`CTRLSERVER_PROTOCOL` = http

`CTRLSERVER_HOST` = 0.0.0.0

`CTRLSERVER_PORT` = 8181

---

## MAJOR TODOs

- Standardize database access so that auditing tools & rule evaluations can be built
- Set up classification functionality
- Standardize data saving formats (mainly classification data)
- Re-implement support for web UI config utils
