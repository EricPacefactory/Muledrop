#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Oct 29 14:41:26 2019

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
import torch
import torch.nn as nn
import torch.nn.init as layer_init
from torchvision import transforms as pytorch_transforms
from torchvision import models as pytorch_models

# ---------------------------------------------------------------------------------------------------------------------
#%% Model components

class _Fire(nn.Module):
    
    # Based on Pytorch implementation
    # Found in ~/.cache/torch/hub/pytorch_vision_master/torchvision/models/squeezenet.py
    # (May require calling models.squeezenet1_1(pretrained = True) to download first!)
    
    # .................................................................................................................

    def __init__(self, inplanes, squeeze_planes, expand1x1_planes, expand3x3_planes):
        
        super().__init__()
        
        self.inplanes = inplanes
        self.squeeze = nn.Conv2d(inplanes, squeeze_planes, kernel_size=1)
        self.squeeze_activation = nn.ReLU(inplace=True)
        self.expand1x1 = nn.Conv2d(squeeze_planes, expand1x1_planes, kernel_size=1)
        self.expand1x1_activation = nn.ReLU(inplace=True)
        self.expand3x3 = nn.Conv2d(squeeze_planes, expand3x3_planes, kernel_size=3, padding=1)
        self.expand3x3_activation = nn.ReLU(inplace=True)

    # .................................................................................................................

    def forward(self, x):
        x = self.squeeze_activation(self.squeeze(x))
        return torch.cat([self.expand1x1_activation(self.expand1x1(x)),
                          self.expand3x3_activation(self.expand3x3(x))], 1)
    
    # .................................................................................................................
    
    def output_channels(self):        
        return self.expand1x1.out_channels + self.expand3x3.out_channels
    
    # .................................................................................................................
    # .................................................................................................................


# .....................................................................................................................
# .....................................................................................................................


class Reference_SqueezeNet_1_1(nn.Module):
    
    ''' Copy of original pytorch implementation of squeezenet version 1.1 (with minor reformatting) '''
    
    # .................................................................................................................
    
    def __init__(self, num_classes=1000, random_initialization = True):
        
        super().__init__()
        self.num_classes = num_classes
        self.features = nn.Sequential(
            nn.Conv2d(3, 64, kernel_size=3, stride=2),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(kernel_size=3, stride=2, ceil_mode=True),
            _Fire(64, 16, 64, 64),
            _Fire(128, 16, 64, 64),
            nn.MaxPool2d(kernel_size=3, stride=2, ceil_mode=True),
            _Fire(128, 32, 128, 128),
            _Fire(256, 32, 128, 128),
            nn.MaxPool2d(kernel_size=3, stride=2, ceil_mode=True),
            _Fire(256, 48, 192, 192),
            _Fire(384, 48, 192, 192),
            _Fire(384, 64, 256, 256),
            _Fire(512, 64, 256, 256),
        )
        
        # Final convolution is initialized differently from the rest
        final_conv = nn.Conv2d(512, self.num_classes, kernel_size=1)
        self.classifier = nn.Sequential(
            nn.Dropout(p=0.5),
            final_conv,
            nn.ReLU(inplace=True),
            nn.AdaptiveAvgPool2d((1, 1))
        )
        
        # Set initialization
        if random_initialization:
            for m in self.modules():
                if isinstance(m, nn.Conv2d):
                    if m is final_conv:
                        layer_init.normal_(m.weight, mean=0.0, std=0.01)
                    else:
                        layer_init.kaiming_uniform_(m.weight)
                    if m.bias is not None:
                        layer_init.constant_(m.bias, 0)

    # .................................................................................................................

    def forward(self, x):
        x = self.features(x)
        x = self.classifier(x)
        return torch.flatten(x, 1)
    
    # .................................................................................................................
    # .................................................................................................................


# =====================================================================================================================
# =====================================================================================================================


class Full_SqueezeNet_112x112(nn.Module):
    
    # Based on pytorch implementation
    # Found in ~/.cache/torch/hub/pytorch_vision_master/torchvision/models/squeezenet.py
    # (May require calling models.squeezenet1_1(pretrained = True) to download first!)
    
    # Set some globals to describe model expectations
    base_save_name = "full_squeezenet_112x112"
    save_ext = ".pt"
    input_channel_order = "rgb"
    expected_input_wh = (112, 112)
    _pytorch_to_tensor = pytorch_transforms.ToTensor()
    _pytorch_normalize = pytorch_transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
    
    # .................................................................................................................
    
    def __init__(self, ordered_class_labels_list, random_initialization = True):
        
        # Inherit from parent
        super().__init__()
        
        # Store the number of classes in the output layer
        self.ordered_class_labels_list = ordered_class_labels_list
        self.num_classes = len(ordered_class_labels_list)
        
        # Create feature layers, but truncated compared to original squeezenet  (for speed).
        self.features = nn.Sequential(
            nn.Conv2d(3, 64, kernel_size = 3, stride = 2),
            nn.ReLU(inplace = True),
            nn.MaxPool2d(kernel_size = 3, stride = 2, ceil_mode = True),
            _Fire(64, 16, 64, 64),
            _Fire(128, 16, 64, 64),
            nn.MaxPool2d(kernel_size = 3, stride = 2, ceil_mode = True),
            _Fire(128, 32, 128, 128),
            _Fire(256, 32, 128, 128),
            nn.MaxPool2d(kernel_size=3, stride=2, ceil_mode=True),
            _Fire(256, 48, 192, 192),
            _Fire(384, 48, 192, 192),
            _Fire(384, 64, 256, 256),
            _Fire(512, 64, 256, 256)
        )
        
        # Final convolution is initialized differently from the rest
        num_final_inputs = self.features[-1].output_channels()
        final_conv = nn.Conv2d(num_final_inputs, self.num_classes, kernel_size = 1)
        self.classifier = nn.Sequential(
            nn.Dropout(p = 0.5),
            final_conv,
            nn.ReLU(inplace = True),
            nn.AdaptiveAvgPool2d((1, 1))
        )
        
        # Set initialization
        initialize_weights(self, final_conv, random_initialization)
    
    # .................................................................................................................

    def forward(self, x):
        x = self.features(x)
        x = self.classifier(x)
        return torch.flatten(x, 1)
    
    # .................................................................................................................
    
    def predict_from_tensor(self, cropped_image_tensor, add_batch_dimension = True):
        
        # Add a batch dimension, if needed
        if add_batch_dimension:
            cropped_image_tensor = cropped_image_tensor.unsqueeze(0)
        
        # Run raw computation step to get model outputs
        model_outputs = self(cropped_image_tensor)
        predicted_raw_score, predicted_class_idx = torch.max(model_outputs, 1)
        
        # Convert model output to class label & score
        predicted_class_label = self.ordered_class_labels_list[predicted_class_idx]
        prediction_score = float(predicted_raw_score / torch.sum(model_outputs))
        
        return predicted_class_label, prediction_score
    
    # .................................................................................................................
    
    def predict(self, cropped_image_numpy):
        
        # Convert numpy input to tensor so we can run the model
        image_tensor = self.prepare_numpy_inputs(cropped_image_numpy)
        image_tensor.unsqueeze_(0)
        
        # Run raw computation step to get model outputs        
        model_outputs = self(image_tensor)
        predicted_raw_score, predicted_class_idx = torch.max(model_outputs, 1)
        
        # Convert model output to class label & score
        predicted_class_label = self.ordered_class_labels_list[predicted_class_idx]
        prediction_score = float(predicted_raw_score / torch.sum(model_outputs))
        
        return predicted_class_label, prediction_score
    
    # .................................................................................................................
    
    def set_to_inference_mode(self):
        
        '''
        Helper function for forcing the model into inference-only mode 
        Disabled training-only layers (dropout/batchnorm) 
        and also disables 'requires_grad' parameter for all layers 
        '''
        
        # Turn off special training layer features (e.g. dropout, batchnorm)
        self.eval()
        
        # Turn off gradient tracking wherever possible
        for each_param in self.parameters():
            try:
                each_param.requires_grad = False
            except AttributeError:
                pass
    
    # .................................................................................................................
    
    @classmethod
    def _scale_for_input(cls, image):
        
        # Decide if we need to resize
        target_width, target_height = cls.expected_input_wh
        image_height, image_width = image.shape[0:2]
        needs_width_resize = (image_width != target_width)
        needs_height_resize = (image_height != target_height)
        needs_resize = (needs_width_resize or needs_height_resize)
        
        # Only resize if the image isn't already properly sized
        if needs_resize:
            return cv2.resize(image, dsize = (target_width, target_height))
        
        return image
    
    # .................................................................................................................
    
    @classmethod
    def prepare_numpy_inputs(cls, image_numpy):
        
        # Apply remaining transforms, meant for providing consistent data formatting
        output_image = cv2.cvtColor(image_numpy, cv2.COLOR_BGR2RGB)
        output_image = cls._scale_for_input(output_image)
        output_image = cls._pytorch_to_tensor(output_image)
        output_image = cls._pytorch_normalize(output_image)
        
        return output_image
    
    # .................................................................................................................
    
    @classmethod
    def load_model_from_path(cls, folder_path, file_name_no_ext = None):
        
        # Create saving path. Use default file name, unless a name is provided
        save_name = cls.base_save_name if file_name_no_ext is None else file_name_no_ext
        save_name_no_ext, _ = os.path.splitext(save_name)
        path_to_model_data = os.path.join(folder_path, "{}{}".format(save_name_no_ext, cls.save_ext))
        
        # Load data from pytorch saved data
        loaded_data = torch.load(path_to_model_data)        
        ordered_class_labels = loaded_data["ordered_class_labels"]
        model_state_dict = loaded_data["model_state_dict"]
        
        # Initialize a new model from the loaded data
        new_model = cls(ordered_class_labels, random_initialization = False)
        new_model.load_state_dict(model_state_dict)
        
        return new_model
    
    # .................................................................................................................
    
    def save_to_path(self, folder_path, file_name_no_ext = None):
        
        # Create saving path. Use default file name, unless a name is provided
        save_name = self.base_save_name if file_name_no_ext is None else file_name_no_ext
        save_name_no_ext, _ = os.path.splitext(save_name)
        path_to_model_data = os.path.join(folder_path, "{}{}".format(save_name_no_ext, self.save_ext))
        
        # Bundle data used for saving/reloading
        save_data_dict = {"ordered_class_labels": self.ordered_class_labels_list,
                          "model_state_dict": self.state_dict()}
        
        # Save the dictionary data!
        torch.save(save_data_dict, path_to_model_data)
                
    # .................................................................................................................
    # .................................................................................................................


# =====================================================================================================================
# =====================================================================================================================


class Truncated_SqueezeNet_112x112(nn.Module):
    
    # Based on pytorch implementation
    # Found in ~/.cache/torch/hub/pytorch_vision_master/torchvision/models/squeezenet.py
    # (May require calling models.squeezenet1_1(pretrained = True) to download first!)
    
    # Set some globals to describe model expectation
    input_channel_order = "rgb"
    expected_input_wh = (112, 112)
    _pytorch_to_tensor = pytorch_transforms.ToTensor()
    _pytorch_normalize = pytorch_transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
    
    # .................................................................................................................
    
    def __init__(self, ordered_class_labels_list, random_initialization = True):
        
        # Inherit from parent
        super().__init__()
        
        # Store the number of classes in the output layer
        self.ordered_class_labels_list = ordered_class_labels_list
        self.num_classes = len(ordered_class_labels_list)
        
        # Create feature layers, but truncated compared to original squeezenet  (for speed).
        self.features = nn.Sequential(
            nn.Conv2d(3, 64, kernel_size = 3, stride = 2),
            nn.ReLU(inplace = True),
            nn.MaxPool2d(kernel_size = 3, stride = 2, ceil_mode = True),
            _Fire(64, 16, 64, 64),
            _Fire(128, 16, 64, 64),
            nn.MaxPool2d(kernel_size = 3, stride = 2, ceil_mode = True),
            _Fire(128, 32, 128, 128),
            _Fire(256, 32, 128, 128)
        )
        
        # Final convolution is initialized differently from the rest
        num_final_inputs = self.features[-1].output_channels()
        final_conv = nn.Conv2d(num_final_inputs, self.num_classes, kernel_size = 1)
        self.classifier = nn.Sequential(
            nn.Dropout(p = 0.5),
            final_conv,
            nn.ReLU(inplace = True),
            nn.AdaptiveAvgPool2d((1, 1))
        )
        
        # Set initialization
        initialize_weights(self, final_conv, random_initialization)
    
    # .................................................................................................................

    def forward(self, x):
        x = self.features(x)
        x = self.classifier(x)
        return torch.flatten(x, 1)
    
    # .................................................................................................................
    
    def predict_from_tensor(self, cropped_image_tensor, add_batch_dimension = True):
        
        # Add a batch dimension, if needed
        if add_batch_dimension:
            cropped_image_tensor = cropped_image_tensor.unsqueeze(0)
        
        # Run raw computation step to get model outputs
        model_outputs = self(cropped_image_tensor)
        predicted_raw_score, predicted_class_idx = torch.max(model_outputs, 1)
        
        # Convert model output to class label & score
        predicted_class_label = self.ordered_class_labels_list[predicted_class_idx]
        prediction_score = float(predicted_raw_score / torch.sum(model_outputs))
        
        return predicted_class_label, prediction_score
    
    # .................................................................................................................
    
    def predict(self, cropped_image_numpy):
        
        # Convert numpy input to tensor so we can run the model
        image_tensor = self.prepare_numpy_inputs(cropped_image_numpy)
        image_tensor.unsqueeze_(0)
        
        # Run raw computation step to get model outputs        
        model_outputs = self(image_tensor)
        predicted_raw_score, predicted_class_idx = torch.max(model_outputs, 1)
        
        # Convert model output to class label & score
        predicted_class_label = self.ordered_class_labels_list[predicted_class_idx]
        prediction_score = float(predicted_raw_score / torch.sum(model_outputs))
        
        return predicted_class_label, prediction_score
    
    # .................................................................................................................
    
    def set_to_inference_mode(self):
        
        '''
        Helper function for forcing the model into inference-only mode 
        Disabled training-only layers (dropout/batchnorm) 
        and also disables 'requires_grad' parameter for all layers 
        '''
        
        # Turn off special training layer features (e.g. dropout, batchnorm)
        self.eval()
        
        # Turn off gradient tracking wherever possible
        for each_param in self.parameters():
            try:
                each_param.requires_grad = False
            except AttributeError:
                pass
    
    # .................................................................................................................
    
    @classmethod
    def _scale_for_input(cls, image):
        
        # Decide if we need to resize
        target_width, target_height = cls.expected_input_wh
        image_height, image_width = image.shape[0:2]
        needs_width_resize = (image_width != target_width)
        needs_height_resize = (image_height != target_height)
        needs_resize = (needs_width_resize or needs_height_resize)
        
        # Only resize if the image isn't already properly sized
        if needs_resize:
            return cv2.resize(image, dsize = (target_width, target_height))
        
        return image
    
    # .................................................................................................................
    
    @classmethod
    def prepare_numpy_inputs(cls, image_numpy):
        
        # Apply remaining transforms, meant for providing consistent data formatting
        output_image = cv2.cvtColor(image_numpy, cv2.COLOR_BGR2RGB)
        output_image = cls._scale_for_input(output_image)
        output_image = cls._pytorch_to_tensor(output_image)
        output_image = cls._pytorch_normalize(output_image)
        
        return output_image
    
    # .................................................................................................................
    
    @classmethod
    def load_model_from_path(cls, path_to_model_data):
        
        # Load data from pytorch saved data
        loaded_data = torch.load(path_to_model_data)        
        ordered_class_labels = loaded_data["ordered_class_labels"]
        model_state_dict = loaded_data["model_state_dict"]
        
        # Initialize a new model from the loaded data
        new_model = cls(ordered_class_labels, random_initialization = False)
        new_model.load_state_dict(model_state_dict)
        
        return new_model
    
    # .................................................................................................................
    
    def save_to_path(self, path_to_model_data):
        
        save_data_dict = {"ordered_class_labels": self.ordered_class_labels_list,
                          "model_state_dict": self.state_dict}
        
        torch.save(save_data_dict, path_to_model_data)
                
    # .................................................................................................................
    # .................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

# .....................................................................................................................

def initialize_weights(model, final_conv_layer, enable = True):
        
    # Don't bother if we're not initializing
    if not enable:
        return
    
    for each_module in model.modules():
        
        # Skip non-convolutional layers
        if not isinstance(each_module, nn.Conv2d):
            continue
        
        # Initialize layer weights
        layer_init.kaiming_uniform_(each_module.weight)
        
        # Handle the final layer initialization differently
        if each_module is final_conv_layer:
            layer_init.normal_(each_module.weight, mean=0.0, std=0.01)
            
        # Initialize biases if needed
        if each_module.bias is not None:
            layer_init.constant_(each_module.bias, 0)

# .....................................................................................................................

def load_state_dict_no_classifier(new_model):
        
    # Remove original state dictionary entries containing classifier weights/biases
    # (If we don't do this, we may have a mismatch if our classifier has been modified!)
    # - Note: only intended for loading an existing squeezenet (1.1) state dict!
    
    # Load pytorch trained weights for squeeznet (v1.1)
    squeezenet_original = pytorch_models.squeezenet1_1(pretrained=True)
    full_state_dict = squeezenet_original.state_dict()
    
    # Delete existing classifier weights
    try: del full_state_dict["classifier.1.weight"]
    except KeyError: pass
    
    # Delete existing classifier biases
    try: del full_state_dict["classifier.1.bias"]
    except KeyError: pass
    
    # Load model with the modified state dictionary
    new_model.load_state_dict(full_state_dict, strict = False)
    # Setting 'strict = False' means we don't need an exact matching set of layers. 
    # However, if we've modified the layer structure (e.g. number of in/out channels)
    # without changing the layer name, we'll get an error!
    # --> Need to fully delete layers from state dict to avoid this
    
    return new_model

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Demo

if __name__ == "__main__":
    pass

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap


