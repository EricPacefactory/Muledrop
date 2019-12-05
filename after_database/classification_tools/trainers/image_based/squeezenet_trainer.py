#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Oct 25 15:11:20 2019

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

from time import perf_counter

from local.lib.selection_utils import Resource_Selector

from local.lib.file_access_utils.classifier import select_classification_dataset
from local.lib.file_access_utils.classifier import build_curation_folder_path

from local.lib.file_access_utils.classifier import load_label_lut_tuple
from local.lib.file_access_utils.classifier import build_snapshot_image_dataset_path

from local.offline_database.object_reconstruction import minimum_crop_box

from eolib.utils.files import get_file_list
from eolib.utils.read_write import load_json
from eolib.utils.cli_tools import cli_confirm

from local.lib.classifier_models.squeezenet_variants import Truncated_SqueezeNet_112x112
from local.lib.classifier_models.squeezenet_variants import Full_SqueezeNet_112x112
from local.lib.classifier_models.squeezenet_variants import load_state_dict_no_classifier

import torch
import torch.nn as nn
import torch.optim as optim
from torch.optim import lr_scheduler
#import torchvision
from torchvision import models
import copy

# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes

from torch.utils.data import Dataset


class Curated_Data(Dataset):
    
    # Shared class parameters
    snapshot_image_folder_path = None
    label_to_idx_dict = None
    target_wh = None
    model_input_conversion_func = None
    
    # .................................................................................................................
    
    def __init__(self, data_list, is_training_data = False):
        
        # Store configuration inputs
        self.data_list = data_list
        self.is_training_data = is_training_data
        
        # Pre-generate standard transforms
        #self._pytorch_to_tensor = pytorch_transforms.ToTensor()
        #self._pytorch_normalize = pytorch_transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
    
    # .................................................................................................................
    
    def __repr__(self):
        
        repr_strs = ["Curated Dataset",
                     "  Training data: {}".format(self.is_training_data),
                     "   Dataset size: {}".format(len(self)),
                     "     Image size: {} x {}".format(*self.target_wh),
                     "   Image folder: {}".format(self.snapshot_image_folder_path)]
        
        return "\n".join(repr_strs)
        
    # .................................................................................................................
    
    @classmethod
    def set_snapshot_image_path(cls, snapshot_image_folder_path):
        cls.snapshot_image_folder_path = snapshot_image_folder_path
    
    # .................................................................................................................
    
    @classmethod
    def set_label_to_idx_dict(cls, label_to_idx_dict):
        cls.label_to_idx_dict = label_to_idx_dict
    
    # .................................................................................................................
    
    @classmethod
    def set_target_wh(cls, target_width, target_height):
        cls.target_wh = (target_width, target_height)
        
    # .................................................................................................................
    
    @classmethod
    def set_model_input_function(cls, model_input_function):
        cls.model_input_conversion_func = model_input_function
    
    # .................................................................................................................
    
    def __len__(self):
        return len(self.data_list)
    
    # .................................................................................................................
    
    def __getitem__(self, item_idx):
        
        # Convert item index to python-friendly variable, if needed
        if torch.is_tensor(item_idx):
            item_idx = item_idx.tolist()
        
        # Get the correct entry, based on the given index
        data_info_dict = self.data_list[item_idx]
        snap_name = data_info_dict["snap_name"]
        box_tlbr = data_info_dict["box_tlbr"]
        target_label = data_info_dict["class_label"]
        target_class_index = self.label_to_idx_dict[target_label]
        
        # Load the corresponding snapshot image
        snap_image_name = "".join([snap_name, ".jpg"])
        snap_image_path = os.path.join(self.snapshot_image_folder_path, snap_image_name)
        snap_image = cv2.imread(snap_image_path)
        
        # Crop out the target area of the snapshot image
        snap_height, snap_width = snap_image.shape[0:2]
        frame_scaling = np.float32((snap_width - 1, snap_height - 1))
        box_tlbr_px = np.int32(np.round(box_tlbr * frame_scaling))
        (x1, y1), (x2, y2) = box_tlbr_px
        
        # Bump up the cropping co-ords if they're too small, so we don't end up with super tiny images        
        x1, x2 = minimum_crop_box(x1, x2, 75, snap_width)
        y1, y2 = minimum_crop_box(y1, y2, 75, snap_height)
        
        # Perform transforms
        crop_image = snap_image[y1:y2, x1:x2]
        output_image = self.transform(crop_image)
        model_image = self.model_input_conversion_func(output_image)
        
        return model_image, target_class_index
    
    # .................................................................................................................
    
    def _tiny_upscale(self, image, target_width, target_height, 
                      minimum_width_scale = 0.8, minimum_height_scale = 0.8):
        
        # Decide if the image is small enough that we need to upscale
        image_height, image_width = image.shape[0:2]
        minimum_width = int(round(target_width * minimum_width_scale))
        minimum_height = int(round(target_height * minimum_height_scale))
        
        # Only upscale small images
        needs_width_upscale = (image_width < minimum_width)
        needs_height_upscale = (image_height < minimum_height)
        needs_upscale = (needs_width_upscale or needs_height_upscale)
        if needs_upscale:
            return cv2.resize(image, dsize = (minimum_width, minimum_height))
        
        return image
    
    # .................................................................................................................
    
    def _random_resize(self, image, probability = 1.0, max_fx = 0.15, max_fy = 0.15):
        
        # Apply a random amount of resizing, randomly
        random_sample = np.random.rand()
        if random_sample < probability:
            random_fx = 1.0 + (self._centered_rand() * max_fx)
            random_fy = 1.0 + (self._centered_rand() * max_fy)
            return cv2.resize(image, dsize=None, fx = random_fx, fy = random_fy)
        
        return image
    
    # .................................................................................................................
    
    def _random_horizontal_flip(self, image, probability = 0.5):
        
        # Apply a horizontal flip, randomly
        random_sample = np.random.rand()
        if random_sample < probability:
            return np.fliplr(image)
        return image
    
    # .................................................................................................................
    
    def _random_channel_swap(self, image, probability = 1.0):
        
        # Occasionally Swap color channels randomly
        random_sample = np.random.rand()
        if random_sample < probability:
            random_channels = np.random.permutation([0,1,2])
            return image[:, :, random_channels]
        
        return image
    
    # .................................................................................................................
    
    def _centered_rand(self, num_samples = None):
        ''' Function which returns uniform random samples between -1.0 and 1.0 '''
        return 2.0 * (np.random.random_sample(num_samples) - 0.5)
    
    # .................................................................................................................
    
    def _random_reflected_border(self, image, target_width, target_height):
        
        # Decide if we need to add a border
        image_height, image_width = image.shape[0:2]
        needs_width_border = (image_width < target_width)
        needs_height_border = (image_height < target_height)
        needs_border = (needs_width_border or needs_height_border)
        
        # Just return the image as-is if we don't need a border
        if not needs_border:
            return image
        
        # Calculate width border sizing
        width_diff = max(0, target_width - image_width)
        random_fraction = 0.25 + np.random.rand()/2
        left_border = int(round(random_fraction * width_diff))
        right_border = width_diff - left_border
        
        # Calculate height border sizing
        height_diff = max(0, target_height - image_height)
        random_fraction = 0.25 + np.random.rand()/2
        top_border = int(round(random_fraction * height_diff))
        bot_border = height_diff - top_border
        
        # Add a reflected border to the input image
        return cv2.copyMakeBorder(image, 
                                  top = top_border, 
                                  bottom = bot_border,
                                  left = left_border, 
                                  right = right_border,
                                  borderType = cv2.BORDER_REFLECT_101)
        
    # .................................................................................................................
    
    def _scale_to(self, image, target_width, target_height):
        
        # Decide if we need to resize
        image_height, image_width = image.shape[0:2]
        needs_width_resize = (image_width != target_width)
        needs_height_resize = (image_height != target_height)
        needs_resize = (needs_width_resize or needs_height_resize)
        
        # Only resize if the image isn't already properly sized
        if needs_resize:
            return cv2.resize(image, dsize = (target_width, target_height))
        
        return image
    
    # .................................................................................................................
    
    def transform(self, image):
        
        # Don't do any transformations while running out of training mode
        if not self.is_training_data:
            return image
        
        # Apply training-only transforms, which are purely data augmentation steps
        target_width, target_height = self.target_wh
        output_image = self._tiny_upscale(image, target_width, target_height)
        output_image = self._random_resize(output_image, probability = 0.40)
        output_image = self._random_horizontal_flip(output_image, probability = 0.25)
        output_image = self._random_channel_swap(output_image, probability = 0.10)
        output_image = self._random_reflected_border(output_image, target_width, target_height)
        
        return output_image

    # .................................................................................................................
    # .................................................................................................................
    

class Curated_Data_Splitter:
    
    # .................................................................................................................
    
    def __init__(self, cameras_folder_path, camera_select, dataset_select,
                 minimum_examples_per_class = 100, maximum_examples_per_class = 1000):
        
        # Store pathing inputs
        self.cameras_folder_path = cameras_folder_path
        self.camera_select = camera_select
        self.dataset_select = dataset_select
        
        # Build pathing to curated files
        dataset_path_args = (cameras_folder_path, camera_select, dataset_select)
        self.curation_folder_path = build_curation_folder_path(*dataset_path_args)
        self.snapshot_image_folder_path = build_snapshot_image_dataset_path(*dataset_path_args)
        
        # Load labelling lookup so we can convert to label indices for training
        self.label_lut_dict, self.label_to_idx_dict = load_label_lut_tuple(cameras_folder_path, camera_select)
        self.num_classes, self.valid_labels_dict, self.ignoreable_labels_list = self.get_labels()
        self.num_ignored = len(self.ignoreable_labels_list)
        
        # Before we go too far, make sure the data is ok
        self._check_class_index_validity()
        
        # Get all cropping data, organized by object class
        self.crop_by_class_dict = self._filter_empty_snapshots()
        self.unique_class_counts = {c_label: len(c_list) for c_label, c_list in self.crop_by_class_dict.items()}
    
    # .................................................................................................................
    
    def __repr__(self):
        
        repr_strs = ["Curated Data ({} classes)".format(len(self.crop_by_class_dict.keys()))]
        for each_label, each_data_list in self.crop_by_class_dict.items():
            repr_strs += ["  {}: {}".format(each_label, len(each_data_list))]

        return "\n".join(repr_strs)            
    
    # .................................................................................................................
    
    def _check_class_index_validity(self):
        
        # Sanity check
        min_class_index = min(self.valid_labels_dict.values())
        highest_class_index = max(self.valid_labels_dict.values()) 
        expected_num_classes = highest_class_index + (1 if min_class_index == 0 else 0)
        if expected_num_classes != self.num_classes:
            print("",
                  "Class indexing error!",
                  "  Expected num classes: {}".format(expected_num_classes),
                  "           Num classes: {}".format(self.num_classes),
                  "            Ignoreable: {}".format(", ".join(self.ignoreable_labels_list)),
                  "    Valid class labels: {}".format(self.valid_labels_dict),
                  sep = "\n")
            
            raise AttributeError("Something wrong with class indexing... Unexpected number of classes?")
        
        return None
    
    # .................................................................................................................
    
    def _filter_empty_snapshots(self):
        
        ''' 
        Function which uses the curated snapshot/class label data, 
        and outputs a dictionary organized by class label, 
        containing cropping data for all snapshots that have objects in them (in a list)
        
        Snapshots that had no objects in them, 
        or had ignorable object labels (e.g. unclassified or ignore)
        will not show up in the output from this function!
        '''
        
        # Load curated file paths
        curated_file_paths = get_file_list(self.curation_folder_path, return_full_path = True)
        
        # Allocate storage for cropping info
        crop_by_class_dict = {}
        
        # Loop through each file, ignore anything without any entries and group all others by class label
        for each_path in curated_file_paths:
            
            # Pull out some relevant data from the curation file
            curate_dict = load_json(each_path, convert_integer_keys = True)
            snap_md = curate_dict["snapshot_metadata"]
            snap_name = snap_md["name"]
            tasks_dict = curate_dict["tasks"]
            
            # Loop over all curated object data, and store cropping info, per task, per class label
            for each_task, each_obj_entry in tasks_dict.items():
                
                # Loop over all the objects recorded for the given task & snapshot, and see if we need to store them
                for each_obj_id, each_obj_dict in each_obj_entry.items():
                    
                    # Get the object label, and skip if it's ignorable
                    obj_class_label = each_obj_dict["class_label"]
                    if obj_class_label in self.ignoreable_labels_list:
                        continue
                    
                    # Add object class label to the data storage, if we don't already have it
                    if obj_class_label not in crop_by_class_dict:
                        crop_by_class_dict[obj_class_label] = []
                    
                    # If we get here, store the data we'll need to load & crop the object
                    box_tlbr = each_obj_dict["box_tlbr"]
                    new_crop_entry = {"snap_name": snap_name, 
                                      "box_tlbr": box_tlbr, 
                                      "max_box_tlbr": None,
                                      "class_label": obj_class_label,
                                      "task": each_task}
                    
                    # Add new entry to output data
                    crop_by_class_dict[obj_class_label].append(new_crop_entry)
        
        return crop_by_class_dict
    
    # .................................................................................................................
    
    def _split_datasets(self, data_list, train_split = 0.75, valid_split = 0.20, test_split = 0.05):
        
        ''' 
        Function which takes in an unshuffled list of training data and splits it into
        training, validation and testing lists, based on input split amounts.
        Note, this function shuffles the data before splitting, but does not create any duplicate entries
        '''
        
        # Make sure to normalize splitting amounts, just to avoid any funniness
        split_total = (train_split + valid_split + test_split)
        split_semi_total = (valid_split + test_split)
        
        # Calculate the number of samples for each dataset
        numsamp = lambda sample_count, sample_split: int(round(sample_count * sample_split))
        total_samples = len(data_list)
        train_samples = numsamp(total_samples, train_split / split_total)
        valid_samples = numsamp(total_samples - train_samples, valid_split / split_semi_total)
        test_samples = total_samples - train_samples - valid_samples
        
        # First shuffle the indexs of the incoming data, so the splits don't contain obvious correlations
        shuffled_idxs = np.random.permutation(total_samples).tolist()
        train_idxs = shuffled_idxs[0:train_samples]
        valid_idxs = shuffled_idxs[train_samples:(train_samples + valid_samples)]
        test_idxs = shuffled_idxs[(train_samples + valid_samples):(train_samples + valid_samples + test_samples)]
        
        # Now split the shuffled data as needed
        train_data_list = [data_list[each_idx] for each_idx in train_idxs]
        valid_data_list = [data_list[each_idx] for each_idx in valid_idxs]
        test_data_list = [data_list[each_idx] for each_idx in test_idxs]
        
        return train_data_list, valid_data_list, test_data_list
    
    # .................................................................................................................
    
    def _duplicate_data(self, data_list, num_to_duplicate, enable = True):
        
        # Bail if the input data list is empty or already long enough
        num_original_elements = len(data_list)
        no_data_in_data_list = (num_original_elements == 0)
        data_already_long_enough = (num_original_elements >= num_to_duplicate)
        if no_data_in_data_list or data_already_long_enough or (not enable):
            return data_list
        
        # Figure out how many times we'll need to pass over the original set of elements to get the desired output count
        num_passes_ceil = int(np.ceil(num_to_duplicate / num_original_elements))
        
        # Generate one or more sets of randomly arranged data indices which we'll use to get duplicate entries
        dupe_idx_list = []
        for k in range(num_passes_ceil):
            dupe_idx_list += np.random.permutation(num_original_elements).tolist()
        
        # Truncate the index list to exactly match the target number of entries
        idx_list_length = len(dupe_idx_list)
        if idx_list_length > num_to_duplicate:
            dupe_idx_list = dupe_idx_list[0:num_to_duplicate]
        
        # Finally, use the randomized indices to grab duplicate copies of the input dataset
        duplicated_data_list = [data_list[each_idx] for each_idx in dupe_idx_list]
        
        return duplicated_data_list
    
    # .................................................................................................................
    
    def _shuffle_data(self, data_list, enable = True):
        
        # Don't do anything if shuffled is not enabled
        if not enable:
            return data_list
        
        # Shuffle data by using a permutation of the original list indexing (kind of inefficient?)
        num_data_points = len(data_list)
        shuffle_idx = np.random.permutation(num_data_points)
        shuffled_data_list = [data_list[each_idx] for each_idx in shuffle_idx]
            
        return shuffled_data_list
    
    # .................................................................................................................
    
    def datasets(self, training_split = 0.75, validiation_split = 0.20, testing_split = 0.05,
                 duplicate_underrepresented_classes = True, shuffle_results = True):
        
        split_lists_by_class = {}
        max_class_count = {}
        for each_class, each_crop_list in self.crop_by_class_dict.items():
            
            # Split each list of data (per class) into training/validation/testing lists
            train_list, valid_list, test_list = self._split_datasets(each_crop_list,
                                                                     training_split, 
                                                                     validiation_split, 
                                                                     testing_split)
            
            # Store each data list by dataset type
            split_lists_by_class[each_class] = {"train": train_list, "valid": valid_list, "test": test_list}
            
            # Keep track of the maximum class count, per dataset
            max_class_count["train"] = max(max_class_count.get("train", 0), len(train_list))
            max_class_count["valid"] = max(max_class_count.get("valid", 0), len(valid_list))
            max_class_count["test"] = max(max_class_count.get("test", 0), len(test_list))        
        
        # Now duplicate data entries for classes that are underrepresented in the dataset
        dataset_lists = {"train": [], "valid": [], "test": []}
        for each_dataset, each_max_class_count in max_class_count.items():
            
            for each_class, each_dataset_dict in split_lists_by_class.items():
                data_list = each_dataset_dict.get(each_dataset)
                dataset_lists[each_dataset] += self._duplicate_data(data_list, each_max_class_count,
                                                                    duplicate_underrepresented_classes)
        
        # Shuffle the data, so that class examples are not all clustered together
        train_data_list = self._shuffle_data(dataset_lists.get("train"), shuffle_results)
        valid_data_list = self._shuffle_data(dataset_lists.get("valid"), shuffle_results)
        test_data_list = self._shuffle_data(dataset_lists.get("test"), shuffle_results)
        
        # Tell curated dataset objects about important pathing & labelling info
        Curated_Data.set_snapshot_image_path(self.snapshot_image_folder_path)
        Curated_Data.set_label_to_idx_dict(self.label_to_idx_dict)
        
        # Finally, create pytorch-friendly datasets
        train_dataset = Curated_Data(train_data_list, is_training_data = True)
        valid_dataset = Curated_Data(valid_data_list, is_training_data = False)
        test_dataset = Curated_Data(test_data_list, is_training_data = False)
        
        return train_dataset, valid_dataset, test_dataset
    
    # .................................................................................................................
    
    def get_labels(self):
        
        # Go through all labelling info and split into valid labels and ignoreables (based on class indices)
        valid_labels_dict = {}
        ignoreable_labels_list = [] 
        for each_label, each_idx in self.label_to_idx_dict.items():
            valid_idx = (each_idx >= 0)
            
            if valid_idx:
                valid_labels_dict.update({each_label: each_idx})
            else:
                ignoreable_labels_list.append(each_label)
        
        # Count the number of valid classes, since we'll need to make our one-hot vector at least this long!
        num_valid_classes = len(valid_labels_dict)
        
        return num_valid_classes, valid_labels_dict, ignoreable_labels_list
    
    # .................................................................................................................
    
    def ordered_class_labels(self):
        
        ''' Helper function to get class labels in sorted (by index) order '''
        
        idx_label_list = [(each_idx, each_label) for each_label, each_idx in self.valid_labels_dict.items()]
        sorted_idxs, sorted_labels = zip(*sorted(idx_label_list))
        
        return sorted_labels
        
    # .................................................................................................................
    # .................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

# .....................................................................................................................

def convert_pytorch_image_to_ocv(pytorch_image):
    
    image = pytorch_image.numpy().transpose((1, 2, 0)) # Convert (ch, h, w) -> (h, w, ch)
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


def imshow_results(model, dataset, num_images = 6):
    
    # Make sure model isn't in training mode
    model.eval()
    
    num_images = min(len(dataset), num_images)
    
    # Run prediction on a set of input images, with timing!
    results_list = []
    t_start = perf_counter()
    with torch.no_grad():
        for k in range(num_images):
            each_image, each_target_index = dataset[k]     
            pred_label, pred_score = model.predict_from_tensor(each_image, add_batch_dimension = True)
            results_list.append((pred_label, pred_score))
            
    # Complete timing
    t_end = perf_counter()
    proc_time_ms = 1000 * (t_end - t_start)
    per_image_ms = proc_time_ms / num_images
    print("Prediction took {:.3f} ms  ({:.3f} per input)".format(proc_time_ms, per_image_ms))
    
    # Create output images with predictions
    for k in range(num_images):
        
        each_image, each_target_label = dataset[k]
        pred_label, pred_score = results_list[k]
        window_title = "{} ({:.0f}%)".format(pred_label, 100*pred_score)
        disp_image = convert_pytorch_image_to_ocv(each_image)
    
        cv2.imshow(window_title, disp_image)
        cv2.waitKey(0)
        cv2.destroyAllWindows()
    
# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Select dataset

enable_debug_mode = False

# Create selector to handle camera selection & project pathing
selector = Resource_Selector()
project_root_path, cameras_folder_path = selector.get_project_pathing()
camera_select, camera_path = selector.camera(debug_mode=enable_debug_mode)
user_select, _ = selector.user(camera_select, debug_mode=enable_debug_mode)

# Select dataset
dataset_folder_path, dataset_select = select_classification_dataset(cameras_folder_path, camera_select, 
                                                                    enable_debug_mode)

# Bundle dataset pathing for convenience
dataset_path_args = (cameras_folder_path, camera_select, dataset_select)


# ---------------------------------------------------------------------------------------------------------------------
#%% Load existing model

# Error if a model does not exist for this camera
base_model_name = Full_SqueezeNet_112x112.base_save_name
base_model_path = os.path.join(cameras_folder_path, camera_select, "resources", "classifier", "models")


# ---------------------------------------------------------------------------------------------------------------------
#%% Setup train/test data

model_wh = Full_SqueezeNet_112x112.expected_input_wh
model_input_function = Full_SqueezeNet_112x112.prepare_numpy_inputs

# Set up dataset config, using model settings
Curated_Data.set_model_input_function(model_input_function)
Curated_Data.set_target_wh(*model_wh)

# Get datasets for training/validation/testings
data_splitter = Curated_Data_Splitter(cameras_folder_path, camera_select, dataset_select)
train_dataset, valid_dataset, test_dataset = \
data_splitter.datasets(training_split = 0.8, validiation_split = 0.15, testing_split = 0.05)

# Set up pytorch dataloaders
dataloader_config = {"batch_size": 16, "shuffle": True, "num_workers": 4}
train_dataloader = torch.utils.data.DataLoader(train_dataset, **dataloader_config)
valid_dataloader = torch.utils.data.DataLoader(valid_dataset, **dataloader_config)
test_dataloader = torch.utils.data.DataLoader(test_dataset, **dataloader_config)

# Get sizing info
ordered_class_labels = data_splitter.ordered_class_labels()
num_classes = len(ordered_class_labels)
num_train = len(train_dataset)
num_valid = len(valid_dataset)
num_test = len(test_dataset)

# Show examples
enable_examples = False
imshow_examples(train_dataloader, enable_examples)


#%%

pp = "/home/wrk/Desktop/pytorch_saved_models/full_sn_112x112.pt"

new_model = Full_SqueezeNet_112x112(ordered_class_labels)
new_model = load_state_dict_no_classifier(new_model)

#raise SystemExit("DEBUG")
'''
new_model = Truncated_SqueezeNet(ordered_class_labels)
#imshow_results(new_model, test_dataloader, ordered_class_labels, 16, True)

load_path = "/home/wrk/Desktop/pytorch_saved_models/truncated_squeezenet_112x112_state_dict_wip.pt"
new_model.load_state_dict(torch.load(load_path))
new_model.eval()
imshow_results(new_model, test_dataset, 10)

#raise SystemExit("DEBUG")
'''
train_model = new_model

'''
STOPPED HERE
- GOT LOADING WORKING, SEEMS REASONABLE?!
- NEED TO COME UP WITH A WAY TO RUN CLASSIFIER ON SAVED DATA & HAVE IT UPDATE CLASSIFICATION DB/FILE
    - THIS CAN BE RUN MANUALLY FOR NOW
    - SHOULD EVENTUALLY BE PART OF AN AUTOMATED SYSTEM? PROBABLY ACTING AS AN EXTERNAL (WHICH RUNS AFTER DB POSTING)
    - WOULD BE NICE TO HAVE OTHER OPTIONS TOO (PASSTHROUGH + METADATA BASED CLASSIFIER + SIMPLE BY-SIZE CLASSIFIER)
- NEED TO THINK ABOUT HOW MANY PARAMETERS ARE STORED/LOADED
- ALSO THINK OF HOW TO IMPROVE TRAINING (I.E. WIDER INPUT DATASET, SO SYSTEM MIGHT WORK BY DEFAULT IN MORE SITUATIONS)
'''


# ---------------------------------------------------------------------------------------------------------------------
#%% Set up model

# Set up loss function for multi-class classification
criterion = nn.CrossEntropyLoss()

# Observe that all parameters are being optimized
optimizer_ft = optim.SGD(train_model.parameters(), lr=0.001, momentum=0.9)

# Decay LR by a factor of 0.1 every 7 epochs
exp_lr_scheduler = lr_scheduler.StepLR(optimizer_ft, step_size=7, gamma=0.1)


# ---------------------------------------------------------------------------------------------------------------------
#%% Run training/validation

final_model = epoch_loop(train_dataloader, num_train, 
                         valid_dataloader, num_valid,
                         model = train_model, 
                         criterion = criterion,
                         optimizer = optimizer_ft, 
                         scheduler = exp_lr_scheduler, 
                         num_epochs = 10)
'''

STOPPED HERE
- WANT TO TRY USING SQUEEZENET... WOULD HAVE TO FIGURE OUT HOW TO RE-WRITE
- NEED TO COME UP WITH A WAY TO SAVE TRAINING/MODEL RESULTS...
- NEED TO COME UP WITH A WAY TO RUN CLASSIFIER ON SAVED DATA & HAVE IT UPDATE CLASSIFICATION DB/FILE
    - THIS CAN BE RUN MANUALLY FOR NOW
    - SHOULD EVENTUALLY BE PART OF AN AUTOMATED SYSTEM? PROBABLY ACTING AS AN EXTERNAL (WHICH RUNS AFTER DB POSTING)
    - WOULD BE NICE TO HAVE OTHER OPTIONS TOO (PASSTHROUGH + METADATA BASED CLASSIFIER + SIMPLE BY-SIZE CLASSIFIER)
'''

#%%

device = torch.device("cpu")
final_model = final_model.to(device)
final_model.eval()

imshow_results(final_model, test_dataset, 10)

#%% 

user_confirm_save = cli_confirm("Save?", default_response = False)
if user_confirm_save:
    save_path = "/home/wrk/Desktop/pytorch_saved_models/truncated_squeezenet_112x112_state_dict_wip.pt"
    torch.save(final_model.state_dict(), save_path)
    print("Saved!")
    print("@ {}".format(save_path))

#%%


#squeezenet_model = models.squeezenet1_1(pretrained = True)
#test_model = SqueezeNet_1_1(1000)
#test_model.load_state_dict(squeezenet_model.state_dict())
#trunc_model = Truncated_SqueezeNet()
#trunc_model.load_state_dict(squeezenet_model.state_dict(), strict = False)


#imshow_results(test_model, test_dataloader, class_names, 5, True)
#imshow_results(trunc_model, test_dataloader, class_names, 15, True)


#imshow_results(squeezenet_model, test_dataloader, class_names, 15, True)


#%% Try loading data...

'''
new_model = Truncated_SqueezeNet(num_classes)
imshow_results(new_model, test_dataloader, class_names, 16, True)

new_model.load_state_dict(torch.load("/home/wrk/Desktop/New Folder/truncated_squeezenet_112x112_state_dict.pt"))
imshow_results(new_model, test_dataloader, class_names, 16, True)
'''