#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Mar 25 11:41:58 2019

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

from local.configurables.core.preprocessor.reference_preprocessor import Reference_Preprocessor

from local.configurables.core.preprocessor._helper_functions import unwarp_from_mapping

# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes
    

class Preprocessor_Stage(Reference_Preprocessor):
    
    # .................................................................................................................
    
    def __init__(self, input_wh):
        
        # Inherit reference functionality
        super().__init__(input_wh, file_dunder = __file__)
        
        # Allocate storage for calculated mapping
        self.x_mapping = None
        self.y_mapping = None
        self.output_w = None
        self.output_h = None        
        
        # .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  . Control Group 1 .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .
        
        self.ctrl_spec.new_control_group("Transformation Controls")
        
        self.enable_transform = \
        self.ctrl_spec.attach_toggle(
                "enable_transform", 
                label = "Enable Transform", 
                default_value = True,
                tooltip = "Enable or disable all of the transformation properties")
        
        
        self.rotation_deg = \
        self.ctrl_spec.attach_slider(
                "rotation_deg", 
                label = "Rotation", 
                default_value = 0.0,
                min_value = -180.0, max_value = 180.0, step_size = 1/10,
                zero_referenced = False,
                return_type = float,
                units = "degrees",
                tooltip = "Rotate the display of the image")
        
        self.fov_deg = \
        self.ctrl_spec.attach_slider(
                "fov_deg", 
                label = "FOV", 
                default_value = 0.0,
                min_value = 0.0, max_value = 180.0, step_size = 1/10,
                return_type = float,
                units = "degrees",
                tooltip = "Set the field of view of the camera")
        
        self.out_apert = \
        self.ctrl_spec.attach_slider(
                "out_apert", 
                label = "Output Aperture", 
                default_value = 1.0,
                min_value = 0.01, max_value = 1.0, step_size = 1/100,
                zero_referenced = True,
                return_type = float,
                units = "normalized",
                tooltip = "Set the amount of the input image to display in the output")
        
        self.interpolation_type = \
        self.ctrl_spec.attach_menu(
                "interpolation_type",
                label = "Interpolation",
                default_value = "Nearest Neighbor", 
                option_label_value_list = [("Nearest Neighbor", cv2.INTER_NEAREST),
                                           ("Bilinear", cv2.INTER_LINEAR),
                                           ("Cubic", cv2.INTER_CUBIC)],
                tooltip = "Set the interpolation style for pixels sampled at fractional indices")
        
        
        # .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  . Control Group 2 .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .
        
        self.ctrl_spec.new_control_group("Camera Adjustments")
        
        self.in_apert = \
        self.ctrl_spec.attach_slider(
                "in_apert", 
                label = "Input Aperture", 
                default_value = 1.0,
                min_value = 0.5, max_value = 1.5, step_size = 1/1000,
                return_type = float,
                units = "normalized",
                tooltip = "")
        
        self.in_ar_balance = \
        self.ctrl_spec.attach_slider(
                "in_ar_balance", 
                label = "Input AR Balance", 
                default_value = 1.0,
                min_value = 0.5, max_value = 1.5, step_size = 1/1000,
                return_type = float,
                units = "normalized",
                tooltip = "")
        
        self.x_recenter = \
        self.ctrl_spec.attach_slider(
                "x_recenter", 
                label = "Lens x-offset", 
                default_value = 0.0,
                min_value = -0.25, max_value = 0.25, step_size = 1/1000,
                return_type = float,
                units = "normalized",
                tooltip = "Set the x-offset of the camera lens relative to the image sensor")
        
        self.y_recenter = \
        self.ctrl_spec.attach_slider(
                "y_recenter", 
                label = "Lens y-offset", 
                default_value = 0.0,
                min_value = -0.25, max_value = 0.25, step_size = 1/1000,
                return_type = float,
                units = "normalized",
                tooltip = "Set the y-offset of the camera lens relative to the image sensor")        
        
        
        # .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  . Control Group 3 .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .
        
        self.ctrl_spec.new_control_group("Scaling Controls")
        
        self.output_w = \
        self.ctrl_spec.attach_slider(
                "output_w", 
                label = "Output Width", 
                default_value = input_wh[0],
                min_value = 50,
                max_value = 1280,
                return_type = int,
                zero_referenced = True,
                units = "pixels",
                tooltip = "Set the output image width, in pixels")
        
        self.output_h = \
        self.ctrl_spec.attach_slider(
                "output_h", 
                label = "Output Height", 
                default_value = input_wh[1],
                min_value = 50,
                max_value = 1280,
                return_type = int,
                zero_referenced = True,
                units = "pixels",
                tooltip = "Set the output image height, in pixels")
    
    # .................................................................................................................
    
    def set_output_wh(self):
        # OVERRIDING FROM PARENT CLASS
        self.output_wh = (self.output_w, self.output_h)
    
    # .................................................................................................................
    
    def reset(self):
        # No data in storage, nothing to reset
        return
    
    # .................................................................................................................
    
    def setup(self, variable_update_dictionary):

        # Rebuild the x/y transformation mappings
        self.build_mapping()
    
    # .................................................................................................................
    
    def apply_transformation(self, frame):
        
        # Short-cut transformation if it's been disabled
        if not self.enable_transform:
            return frame
        
        try:
            return cv2.remap(frame, self.x_mapping, self.y_mapping, self.interpolation_type)
        except:
            print("ERROR TRANSFORMING ({})".format(self.script_name))
            return frame
    
    # .................................................................................................................
    
    @staticmethod
    def _rect_to_polar(rect_x_norm_mesh, rect_y_norm_mesh):        
        radial_mesh = np.sqrt(np.square(rect_x_norm_mesh) + np.square(rect_y_norm_mesh))
        theta_mesh = np.arctan2(rect_y_norm_mesh, rect_x_norm_mesh)        
        return radial_mesh, theta_mesh
    
    # .................................................................................................................
    
    @staticmethod
    def _polar_to_rect(radial_mesh, theta_mesh):
        rect_mesh_x = radial_mesh * np.cos(theta_mesh)
        rect_mesh_y = radial_mesh * np.sin(theta_mesh)
        return rect_mesh_x, rect_mesh_y
    
    # .................................................................................................................
    
    @staticmethod
    def _phys_to_ang_mapping(fov_rad, phys_sample):
        
        '''
        This function returns the (normalized) angular sample point for 
        a given (normalized) physical sample point. Where an angular
        sample point is equivalent to the (normalized)  pixel index 
        from the original (distorted) image.
        This function assumes that the maximum (normalized) angular sample 
        occurs at +/- 1 and corresponds to physical samples taken 
        at angles of +/- FOV / 2
        
        Label:
            phys_sample -> h
             ang_sample -> a
             
        Then the relationship between physical samples (h)
        and angular samples (a), taken at a distance (z) is given by:
            h / z = tan(a * FOV / 2)
            
        Therefore:
            a = (2 / FOV) * arctan(h / z)
            
        To normalize, assume h = +/- 1, when a = +/- 1
        Then:
            1 / z = tan(FOV / 2)
            
        Label phys_normalizer -> (1 / z)
        
        Note, the mapping for 'a' is messy as FOV approaches 0.
        Could do some calculus to see what's supposed to happen,
        but intuitively, limit{FOV -> 0} corresponds to an
        orthogonal projection, so: a = h
        '''
        
        # Avoid numerical issues as the FOV approaches 0
        if fov_rad <= np.radians(0.25):
            return phys_sample
        
        half_angle = min(np.pi / 2, (fov_rad / 2))
        phys_normalizer = np.tan(half_angle)    
        return (1 / half_angle) * np.arctan(phys_sample * phys_normalizer)
    
    # .................................................................................................................
    
    @staticmethod
    def _ang_to_phys_mapping(fov_rad, ang_sample):
        
        '''
        The reverse of the physical-to-angle mapping function
        '''
        
        # Avoid numerical issues as the FOV approaches 180 degrees
        if fov_rad >= np.radians(179.75):
            return 1.0        
        if fov_rad <= np.radians(0.25):
            return ang_sample
        
        half_angle = min(np.pi / 2, (fov_rad / 2))
        inv_phys_normalizer = 1 / np.tan(half_angle)
        return inv_phys_normalizer * np.tan(ang_sample * half_angle)
    
    # .................................................................................................................
    
    def build_mapping(self):
        
        # Make sure the input/output dimensions are set properly
        self.check_scaling_validity()
        
        # Input scaling factors for convenience
        input_wh_scaling = np.array(self.input_wh) - 1
        in_width_scaling, in_height_scaling = input_wh_scaling
        output_width, output_height = self.output_w, self.output_h
        
        # Find input/output apertures, in normalized units
        in_apt_orig = self.in_apert
        out_apt_orig = self.out_apert
        max_corner = 1#np.sqrt(2)
        input_ar_balance = self.in_ar_balance
        
        # Find effective FOV (i.e. FOV at the output aperture)
        fov_rad = np.radians(min(self.fov_deg, 179.99))
        effective_fov_rad = max_corner * fov_rad * out_apt_orig / in_apt_orig
        
        '''
        STOPPED HERE, SOMETHING STRANGE
        - TO TEST:
            - First, set FOV to 900, set input_aperture to 0 (equiv. to 0.5). This is the same as a 180deg FOV correction (just zoomed in!)
            - Reduce output aperture until scene is visible
            - Notice that input aperture has to be increased (above 0.0) to fix extreme fisheye
            - This seems reasonable for extreme fisheye (i.e. 180 radius is slightly outside '100%' of image)
            - THIS ONLY WORKS WITH 'MAX_CORNER' EQUAL TO SQRT(2)
        - TO BREAK:
            - Set FOV to 1800, set input aperture to 500 (default, equiv. to 1.0)
            - Start reducing output aperture
            - Notice image is 'broken' for a while, until output aperture goes below ~70 (1/sqrt(2)!?)
            - This should not happen! As soon as output aperture is less than input, the image should start to 'fix'
            - PROBLEM GOES AWAY WITH 'MAX_CORNER' SET TO 1, BUT THEN THE PREVIOUS TEST DOESN'T WORK!
        - ALSO HAV PROBLEMS WITH AR SCALING (NEED TO GET ANNOTATION RINGS SCALING PROPERLY IN OUTPUT IMAGE)
        - INPUT/OUTPUT APERTURE VALUES SEEM TO BE MORE OFF WITH AR FIXES?!?!?!
        '''
        
        # Create (rectangular) output sampling meshes
        out_x_norm = np.linspace(-1, 1, output_width, dtype=np.float32)
        out_y_norm = np.linspace(-1, 1, output_height, dtype=np.float32)
        out_nx_mesh, out_ny_mesh = np.meshgrid(out_x_norm, out_y_norm)
        
        # Get output sampling maps in polar co-ordinates so we can perform (radially symmetric) transformations
        radial_mesh, theta_mesh = self._rect_to_polar(out_nx_mesh, out_ny_mesh)
        
        # Perform fov correction on the radial map and rotation on theta map
        radial_mesh_transformed = self._phys_to_ang_mapping(effective_fov_rad, radial_mesh)
        theta_mesh_rot = theta_mesh + np.radians(-self.rotation_deg)
        
        print("")
        print("EffFOV, MAX_RADIAL, MIN_RADIAL", effective_fov_rad, np.max(radial_mesh), np.min(radial_mesh))
        print("MAX_RAD_TRANS, MIN_RAD_TRANS", np.max(radial_mesh_transformed), np.min(radial_mesh_transformed))
        
        # Map back into rectangular co-ordinates for display
        mapped_nx_mesh, mapped_ny_mesh = self._polar_to_rect(radial_mesh_transformed, theta_mesh_rot)
        
        # Calculate centering values (in pixels)
        cen_x_px = (0.5 + self.x_recenter) * in_width_scaling
        cen_y_px = (0.5 + self.y_recenter) * in_height_scaling
        
        # Calculate input aspect ratio factors for x/y
        x_ar_scale = max(1.0, input_ar_balance)
        y_ar_scale = 2 - min(1.0, input_ar_balance)
        
        # Finally, generate convert the transformed mappings into pixel indices
        self.x_mapping = cen_x_px + (mapped_nx_mesh/2) * (in_width_scaling * out_apt_orig * x_ar_scale)
        self.y_mapping = cen_y_px + (mapped_ny_mesh/2) * (in_height_scaling * out_apt_orig * y_ar_scale)
    
        # . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 
        
        # Calculate values used for visualization
        ar_scaling = np.array((x_ar_scale, y_ar_scale))
        in_aperture_radius_px = in_apt_orig * ar_scaling * input_wh_scaling / 2
        out_aperture_radius_px = out_apt_orig * ar_scaling * input_wh_scaling / 2
        
        self._in_apert_xy_px = np.int32(np.round(in_aperture_radius_px))        
        self._out_apert_xy_px = np.int32(np.round(out_aperture_radius_px))
        self._cen_xy = np.int32(np.round((cen_x_px, cen_y_px)))
    
    # .................................................................................................................
    
    def check_scaling_validity(self):
        
        # Bail if input_wh hasn't been set yet
        if self.input_wh is None:
            raise ValueError("Input width/height not set!")
        
        # Warning if output dimensions weren't set properly
        if self.output_w is None or self.output_h is None:
            raise ValueError("Output width height are not set: ({} x {})".format(self.output_w, self.output_h))
    
    # .................................................................................................................
    
    def unwarp_required(self):
        # Only need to unwarp if the transform is enabled
        return self.enable_transform
    
    # .................................................................................................................

    def unwarp_xy(self, warped_normalized_xy_npfloat32):
        # Standard unwarp implementation      
        return unwarp_from_mapping(warped_normalized_xy_npfloat32, 
                                   self.input_wh, self.output_wh, 
                                   self.x_mapping, self.y_mapping)
    
    # .................................................................................................................
    # .................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions
    
# .....................................................................................................................

# .....................................................................................................................
# .....................................................................................................................

# ---------------------------------------------------------------------------------------------------------------------
#%% Demo
    
if __name__ == "__main__":
    pass
    

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap



    
