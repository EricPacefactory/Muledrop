# -----------------------------------------------------------------------------
#%% Base setup

# Start ubuntu-python base
FROM pybase_image


# -----------------------------------------------------------------------------
#%% Install system dependencies

# Update repo records
RUN apt-get update --quiet

# Install helpful utilities
RUN apt-get install --quiet --assume-yes \
ranger unzip zip

# Install open-cv compatibility libraries
RUN apt-get install --quiet --assume-yes \
libsm6 libxext6 libxrender-dev


# -----------------------------------------------------------------------------
#%% Set environment variables

# Create a 'home' folder path to avoid storing everything in the root fs
ENV HOME                        /home/scv2

# Set pathing to the camera configuration folder
ENV CAMERAS_FOLDER_PATH         $HOME/cameras

# Set variables for accessing the database server
ENV DBSERVER_HOST               localhost
ENV DBSERVER_PORT               8050

# Set variables for launching the config server
ENV UPSERVER_HOST               0.0.0.0
ENV UPSERVER_PORT               8181


# -----------------------------------------------------------------------------
#%% Setup python 

# Work with files outside of the root fs
WORKDIR $HOME/realtime

# Install python requirements
COPY requirements.txt $HOME/realtime
RUN pip3 install -r requirements.txt


# -----------------------------------------------------------------------------
#%% Launch!

# Move system files into the image
COPY . .

# Run the upload server! This is a blocking call...
CMD ["python3", "configuration_utilities/uploader/upload_server.py"]


# -----------------------------------------------------------------------------
# To use manually:

# From outside realtime project directory:
# sudo docker build -t realtime_image -f ./realtime/build/docker/Dockerfile ./realtime
# sudo docker run -d --network="host" -v /tmp/realtime:/home/scv2/cameras --name realtime_container realtime_image

