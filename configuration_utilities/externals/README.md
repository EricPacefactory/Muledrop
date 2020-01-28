# External Configuration

These folders hold configuration utilities for each of the external processing stages. Unlike the core processing stages, the externals do not have a strictly enforced order (at least for configuration purposes). Below is a simple overview of the purpose of each of the stages.

## External Processing Stages

##### Background Capture/Generation

Repeatedly stores frames from the input video source and occasionally tries to generate an image representing the background of the scene. Important for some types of foreground extraction as well as implementing ghosting.

##### Snapshot Capture

Repeatedly saves individual frames of the input video source so that events from the video can be reconstructed after-the-fact. These snapshots could also be used to evaluate certain rules (such as looking for idle objects or clutter, for example).

##### Object Metadata Capture

Saves object metadata output from the (core) tracker stage. This data can then be evaluated (after-the-fact) to determine if the object broke any rules. Additionally, with the snapshot images it is possible to visualize the object pathing/behavior.
