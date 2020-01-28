#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Oct 14 11:56:28 2019

@author: eo
"""


# ---------------------------------------------------------------------------------------------------------------------
#%% Add local path

import os
import sys

def find_path_to_local(target_folder = "local"):
    
    # Skip path finding if we successfully import the dummy file
    try:
        from local.dummy import dummy_func; dummy_func(); return
    except ImportError:
        print("", "Couldn't find local directory!", "Searching for path...", sep="\n")
    
    # Figure out where this file is located so we can work backwards to find the target folder
    file_directory = os.path.dirname(os.path.abspath(__file__))
    path_check = []
    
    # Check parent directories to see if we hit the main project directory containing the target folder
    prev_working_path = working_path = file_directory
    while True:
        
        # If we find the target folder in the given directory, add it to the python path (if it's not already there)
        if target_folder in os.listdir(working_path):
            if working_path not in sys.path:
                tilde_swarm = "~"*(4 + len(working_path))
                print("\n{}\nPython path updated:\n  {}\n{}".format(tilde_swarm, working_path, tilde_swarm))
                sys.path.append(working_path)
            break
        
        # Stop if we hit the filesystem root directory (parent directory isn't changing)
        prev_working_path, working_path = working_path, os.path.dirname(working_path)
        path_check.append(prev_working_path)
        if prev_working_path == working_path:
            print("\nTried paths:", *path_check, "", sep="\n  ")
            raise ImportError("Can't find '{}' directory!".format(target_folder))
            
find_path_to_local()

# ---------------------------------------------------------------------------------------------------------------------
#%% Imports

import cv2
import numpy as np

from local.lib.ui_utils.cli_selections import Resource_Selector

from local.lib.file_access_utils.classifier import build_dataset_path, build_labels_folder_path, build_labels_lut_path
from local.lib.file_access_utils.classifier import build_path_to_snapshot_metadata, build_path_to_snapshot_images
from local.lib.file_access_utils.classifier import build_path_object_metadata, build_crop_folder_save_paths
from local.lib.file_access_utils.classifier import get_object_id_metadata_paths, get_snapshot_count_paths

from eolib.utils.files import get_file_list
from eolib.utils.cli_tools import cli_folder_list_select
from eolib.utils.read_write import load_json

from time import perf_counter

import torch
import torch.nn as nn
import torch.optim as optim
from torch.optim import lr_scheduler
import torchvision
from torchvision import datasets, models, transforms
import copy

# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes




# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

# .....................................................................................................................

def convert_pytorch_image_to_ocv(pytorch_image):
    
    image = pytorch_image.numpy().transpose((1, 2, 0)) # Convert (c, a, b) -> (a, b, c)
    mean = np.array([0.485, 0.456, 0.406])
    std = np.array([0.229, 0.224, 0.225])
    scaled_image = std * image + mean
    clipped_image = np.uint8(np.round(np.clip(scaled_image * 255, 0, 255)))
    
    # Convert input (which is in RGB format) to bgr for openCV display
    clipped_image = cv2.cvtColor(clipped_image, cv2.COLOR_RGB2BGR)
    
    return clipped_image

# .....................................................................................................................

def imshow_examples(dataloader, enabled = True):
    
    if not enabled:
        return
    
    image_batch, class_batch = next(iter(dataloader))    
    
    for each_idx, (each_image, each_class) in enumerate(zip(image_batch, class_batch)):   
        
        disp_image = convert_pytorch_image_to_ocv(each_image)
        window_title = "Example {}: {}".format(each_idx, each_class)
        cv2.imshow(window_title, disp_image)
        cv2.waitKey(0)
        
    cv2.destroyAllWindows()

# .....................................................................................................................
    
def print_progress(phase_name, epoch_loss, epoch_accuracy):
    print(phase_name, "Loss: {:.3f}  Accuracy: {:.3f}".format(epoch_loss, epoch_accuracy))

# .....................................................................................................................
    
def epoch_loop(train_dataloader, train_dataset_size, 
               valid_dataloader, valid_dataset_size,
               model, criterion, optimizer, scheduler, num_epochs = 5):
    
    # Use a GPU if available
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    dev_model = model.to(device)
    
    # Start timing
    t_start = perf_counter()
    
    # Allocate storage for the 'best performance' weights
    best_model_weights = None
    best_valid_accuracy = -1.0
    
    # Some initialization feedback
    print("", 
          "Beginning training!",
          "  Device: {}".format(device.type),
          "  Epochs: {}".format(num_epochs),
          sep = "\n")
    
    for epoch_idx in range(num_epochs):
        
        # Some feedback
        print("", "Epoch {} / {}".format(1 + epoch_idx, num_epochs), "-" * 10,  sep = "\n")
        
        # Run train loop
        train_loss, train_corrects = train_one_epoch(device, train_dataloader, dev_model, criterion, optimizer)
        
        # Calculate performance metrics & provide feedback
        scaled_train_loss = train_loss / train_dataset_size
        train_accuracy = train_corrects / train_dataset_size
        print_progress("    Training", scaled_train_loss, train_accuracy)
        
        # Run validation loop
        valid_loss, valid_corrects = validate_one_epoch(device, valid_dataloader, dev_model, criterion, optimizer)
        
        # Calculate performance metrics & provide feedback
        scaled_valid_loss = valid_loss / valid_dataset_size
        valid_accuracy = valid_corrects / valid_dataset_size
        print_progress("  Validation", scaled_valid_loss, valid_accuracy)
        
        # Update the learning rate, as needed
        scheduler.step()
        
        # Copy model weights whenever they've improved our accuracy
        if valid_accuracy > best_valid_accuracy:
            best_valid_accuracy = valid_accuracy
            best_model_weights = copy.deepcopy(dev_model.state_dict())
    
    # End timing
    t_end = perf_counter()
    
    # Some timing feedback
    time_elapsed_sec = t_end - t_start
    print("", "",
          "Training complete in {:.0f}m {:.0f}s".format(time_elapsed_sec // 60, time_elapsed_sec % 60),
          "  Best validation accuracy: {:3f}".format(best_valid_accuracy),
          "",
          sep = "\n")

    # Finally, load the best model weights, in case we didn't end that way!
    if best_model_weights is not None:
        dev_model.load_state_dict(best_model_weights)
    
    return dev_model
    
# .....................................................................................................................

def train_one_epoch(device, dataloader, model, criterion, optimizer):
    
    # Initialzie performance statistics
    running_loss = 0.0
    running_corrects = 0
    
    # Put model into training mode
    model.train()
    
    for inputs, labels in dataloader:
        
        # Pass data to device (gpu hopefully)
        dev_inputs = inputs.to(device)
        dev_labels = labels.to(device)
        
        # zero the parameter gradients
        optimizer.zero_grad()
        
        # Forward pass
        with torch.set_grad_enabled(True):
            
            # Get model prediction
            model_pred = model(dev_inputs)
            loss = criterion(model_pred, dev_labels)
            loss.backward()
            optimizer.step()

            # Get model performance statistics
            _, best_guess_class = torch.max(model_pred, 1)
            running_loss += loss.item() * dev_inputs.size(0)
            running_corrects += torch.sum(best_guess_class == dev_labels.data)
        
    return running_loss, running_corrects.cpu().numpy()

# .....................................................................................................................

def validate_one_epoch(device, dataloader, model, criterion, optimizer):
    
    # Initialzie performance statistics
    running_loss = 0.0
    running_corrects = 0
    
    # Put model into evaluation mode
    model.eval()
    
    for inputs, labels in dataloader:
        
        # Pass data to device (gpu hopefully)
        dev_inputs = inputs.to(device)
        dev_labels = labels.to(device)
        
        # zero the parameter gradients
        optimizer.zero_grad()       # MIGHT NOT MATTER IN VALID MODE?
        
        # Forward pass
        with torch.set_grad_enabled(False):
            
            # Get model prediction
            model_pred = model(dev_inputs)
            #_, best_guess_class = torch.max(model_pred, 1)
            loss = criterion(model_pred, dev_labels)
    
            # Get model performance statistics
            _, best_guess_class = torch.max(model_pred, 1)
            running_loss += loss.item() * dev_inputs.size(0)
            running_corrects += torch.sum(best_guess_class == dev_labels.data)
        
    return running_loss, running_corrects.cpu().numpy()

# .....................................................................................................................
    
# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Select camera

enable_debug_mode = False

# Create selector to handle camera selection & project pathing
selector = Resource_Selector()
project_root_path, cameras_folder_path = selector.get_project_pathing()
camera_select, camera_path = selector.camera(debug_mode=enable_debug_mode)

# Get listing of all available datasets
all_dataset_folders_path = build_dataset_path(cameras_folder_path, camera_select)

# Select dataset and build folder pathing to the selected dataset
dataset_folder_path, dataset_select, _ = cli_folder_list_select(all_dataset_folders_path, 
                                                                prompt_heading = "Select dataset", 
                                                                debug_mode = enable_debug_mode)


# Build path to cropped images folder
cropped_images_folder_path = os.path.join(dataset_folder_path, "cropped")

# ---------------------------------------------------------------------------------------------------------------------
#%% Get cropped image data


training_transforms = transforms.Compose([transforms.Resize(224),
                                          transforms.CenterCrop(224),
                                          transforms.RandomHorizontalFlip(),
                                          transforms.ToTensor(),
                                          transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])])

# Set up training image dataset for loading into the model & get class names
image_datasets = datasets.ImageFolder(cropped_images_folder_path, transform = training_transforms)
dataloader = torch.utils.data.DataLoader(image_datasets, batch_size=4, shuffle=True, num_workers=4)
class_names = image_datasets.classes

# Get sizing info
num_classes = len(class_names)
image_dataset_size = len(image_datasets)

# Show examples
imshow_examples(dataloader, False)

# ---------------------------------------------------------------------------------------------------------------------
#%% Set up model

# Use existing model as a starting point
resnet_model = models.resnet18(pretrained=True)

# Figure out how many connections go into final (existing) layer
num_ftrs = resnet_model.fc.in_features

# Modify the number of output connections to match our number of classes
resnet_model.fc = nn.Linear(num_ftrs, num_classes)

# Set up loss function for multi-class classification
criterion = nn.CrossEntropyLoss()

# Observe that all parameters are being optimized
optimizer_ft = optim.SGD(resnet_model.parameters(), lr=0.001, momentum=0.9)

# Decay LR by a factor of 0.1 every 7 epochs
exp_lr_scheduler = lr_scheduler.StepLR(optimizer_ft, step_size=7, gamma=0.1)

# ---------------------------------------------------------------------------------------------------------------------
#%% Run training/validation

train_dataloader = dataloader
train_dataset_size = image_dataset_size

valid_dataloader = dataloader
valid_dataset_size = image_dataset_size

final_model = epoch_loop(train_dataloader, train_dataset_size, 
                         valid_dataloader, valid_dataset_size,
                         model = resnet_model, 
                         criterion = criterion,
                         optimizer = optimizer_ft, 
                         scheduler = exp_lr_scheduler, 
                         num_epochs = 5)


#%%


def imshow_results(model, dataloader, class_names, num_images=6, use_cpu = True):
    
    # Make sure model isn't in training mode
    model.eval()
    
    # Put everything on cpu for timing
    possible_device = "cuda:0" if torch.cuda.is_available() else "cpu"
    actual_device = "cpu" if use_cpu else possible_device
    device = torch.device(actual_device)
    dev_model = model.to(device)
    
    images_so_far = 0
    with torch.no_grad():
        for i, (inputs, labels) in enumerate(dataloader):
            
            # Put image + target label onto the device
            dev_inputs = inputs.to(device)
            dev_labels = labels.to(device)

            # Get model prediction
            t_start = perf_counter()
            model_pred = dev_model(dev_inputs)
            _, best_guess_class = torch.max(model_pred, 1)
            t_end = perf_counter()
            print("Running image batch, took {} ms".format(1000 * (t_end - t_start)))

            for j in range(dev_inputs.size()[0]):
                images_so_far += 1
                
                predicted_class_idx = best_guess_class[j]
                actual_class_idx = dev_labels.data[j]
                actual_class_name = class_names[actual_class_idx.cpu().numpy()]
                correct_pred = (actual_class_idx == predicted_class_idx)
                correct_text = "Correct" if correct_pred else "Wrong"
                window_title = "{} - {}".format(actual_class_name, correct_text)
                
                pytorch_image = dev_inputs.cpu().data[j]
                disp_image = convert_pytorch_image_to_ocv(pytorch_image)
                
                
                cv2.imshow(window_title, disp_image)
                cv2.waitKey(0)
                cv2.destroyAllWindows()
                
                if images_so_far >= num_images:
                    break
            
            if images_so_far >= num_images:
                break
                
imshow_results(final_model, dataloader, class_names, 15, False)
