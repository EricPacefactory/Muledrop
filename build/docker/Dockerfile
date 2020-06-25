# -----------------------------------------------------------------------------
#%% Base setup

# Start with ubuntu-python base
FROM pacefactory/scv2_ubuntupython_base:1.0.0


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

# Set variables for launching the control server
ENV CTRLSERVER_HOST             0.0.0.0
ENV CTRLSERVER_PORT             8181

# Set variables to control auto-posting
ENV AUTOPOST_ON_STARTUP         1
ENV AUTOPOST_PERIOD_MINS        2.5


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
ENTRYPOINT ["sh", "docker_entrypoint.sh"]


# -----------------------------------------------------------------------------
# To use manually:

# From the realtime root project directory:
# sudo docker build -t realtime_image -f ./build/docker/Dockerfile .
# sudo docker run -d --network="host" -v /tmp/realtime:/home/scv2/cameras --name realtime realtime_image

