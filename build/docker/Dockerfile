# -----------------------------------------------------------------------------
#%% Base setup

# Start with Open-CV base
FROM pacefactory/scv2_opencv_base:1.0.1


# -----------------------------------------------------------------------------
#%% Install system dependencies

# Update repo records & install helpful utils
RUN apt-get update && \
    apt-get install --quiet --assume-yes \
    ranger unzip zip


# -----------------------------------------------------------------------------
#%% Setup python requirements

# Install python requirements
COPY requirements.txt /tmp/scv2/requirements.txt
RUN python3 -m pip install --upgrade pip && \
    python3 -m pip install -r /tmp/scv2/requirements.txt


# -----------------------------------------------------------------------------
#%% Set environment variables

# Create a 'home' folder path to avoid storing everything in the root fs
ENV HOME                        /home/scv2

# Set pathing to the locations folder, which holds camera configurations
ENV ALL_LOCATIONS_FOLDER_PATH   $HOME/locations
ENV LOCATION_SELECT             None

# Set variables for accessing the database server
ENV DBSERVER_HOST               localhost
ENV DBSERVER_PORT               8050

# Set variables for launching the control server
ENV CTRLSERVER_HOST             0.0.0.0
ENV CTRLSERVER_PORT             8181
ENV AUTOLAUNCH_BY_DEFAULT       True

# Set variables to control auto-posting
ENV AUTOPOST_ON_STARTUP         1
ENV AUTOPOST_PERIOD_MINS        2.5


# -----------------------------------------------------------------------------
#%% Launch!

# Work with files outside of the root fs
WORKDIR $HOME/realtime

# Move system files into the image
COPY . .

# Make sure the entrypoint script is executable
RUN chmod +x docker_entrypoint.sh

# Run the control server! This is a blocking call...
ENTRYPOINT ["./docker_entrypoint.sh"]


# -----------------------------------------------------------------------------
# To use manually:

# From the root project directory:
# docker build -t realtime_image -f ./build/docker/Dockerfile .
# docker run -d --network="host" -v /tmp/realtime:/home/scv2/locations --name realtime realtime_image

