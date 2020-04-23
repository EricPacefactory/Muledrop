#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Aug 30 11:43:24 2019

@author: eo
"""


# ---------------------------------------------------------------------------------------------------------------------
#%% Imports

import cv2
import numpy as np

# ---------------------------------------------------------------------------------------------------------------------
#%% Define classes



# ---------------------------------------------------------------------------------------------------------------------
#%% Define functions

# .....................................................................................................................

def inferno_colormap(gamma = 1.0):
        
    ''' 
    Hard-coded inferno colormap 
    From:
        https://github.com/opencv/opencv/blob/master/modules/imgproc/src/colormap.cpp
        
    To use:
        lut = infero_colormap()
        inferno_color_image = cv2.LUT(grayscale_image, lut)
        
        (grayscale_image -> Must be BGR, uint8 image!)
    '''
    
    # Hard-coded red channel
    red = [0, 1, 1, 1, 2, 2, 2, 3, 4, 4, 
           5, 6, 7, 8, 9, 10, 11, 12, 13, 14,
           16, 17, 18, 20, 21, 22, 24, 25, 27, 28, 
           30, 31, 33, 35, 36, 38, 40, 41, 43, 45, 
           47, 49, 50, 52, 54, 56, 57, 59, 61, 62, 
           64, 66, 68, 69, 71, 73, 74, 76, 77, 79, 
           81, 82, 84, 85, 87, 89, 90, 92, 93, 95, 
           97, 98, 100, 101, 103, 105, 106, 108, 109, 111, 
           113, 114, 116, 117, 119, 120, 122, 124, 125, 127, 
           128, 130, 132, 133, 135, 136, 138, 140, 141, 143, 
           144, 146, 147, 149, 151, 152, 154, 155, 157, 159, 
           160, 162, 163, 165, 166, 168, 169, 171, 173, 174, 
           176, 177, 179, 180, 182, 183, 185, 186, 188, 189, 
           191, 192, 193, 195, 196, 198, 199, 200, 202, 203, 
           204, 206, 207, 208, 210, 211, 212, 213, 215, 216, 
           217, 218, 219, 221, 222, 223, 224, 225, 226, 227, 
           228, 229, 230, 231, 232, 233, 234, 235, 235, 236, 
           237, 238, 239, 239, 240, 241, 241, 242, 243, 243, 
           244, 245, 245, 246, 246, 247, 247, 248, 248, 248, 
           249, 249, 249, 250, 250, 250, 251, 251, 251, 251, 
           251, 252, 252, 252, 252, 252, 252, 252, 252, 252, 
           252, 252, 252, 251, 251, 251, 251, 251, 250, 250, 
           250, 250, 249, 249, 249, 248, 248, 247, 247, 246, 
           246, 245, 245, 244, 244, 244, 243, 243, 242, 242, 
           242, 241, 241, 241, 241, 242, 242, 243, 243, 244, 
           245, 246, 248, 249, 250, 252]
    
    # Hard-coded green channel
    green = [0, 0, 1, 1, 1, 2, 2, 2, 3, 3, 
             4, 4, 5, 5, 6, 7, 7, 8, 8, 9, 
             9, 10, 10, 11, 11, 11, 12, 12, 12, 12, 
             12, 12, 12, 12, 12, 12, 11, 11, 11, 11, 
             10, 10, 10, 10, 9, 9, 9, 9, 9, 9, 
             10, 10, 10, 10, 11, 11, 12, 12, 13, 13, 
             14, 14, 15, 15, 16, 16, 17, 18, 18, 19, 
             19, 20, 21, 21, 22, 22, 23, 24, 24, 25, 
             25, 26, 26, 27, 28, 28, 29, 29, 30, 30, 
             31, 32, 32, 33, 33, 34, 34, 35, 35, 36, 
             37, 37, 38, 38, 39, 39, 40, 41, 41, 42, 
             42, 43, 44, 44, 45, 46, 46, 47, 48, 48, 
             49, 50, 50, 51, 52, 53, 53, 54, 55, 56, 
             57, 58, 58, 59, 60, 61, 62, 63, 64, 65, 
             66, 67, 68, 69, 70, 71, 72, 74, 75, 76, 
             77, 78, 80, 81, 82, 83, 85, 86, 87, 89, 
             90, 92, 93, 94, 96, 97, 99, 100, 102, 103, 
             105, 106, 108, 110, 111, 113, 115, 116, 118, 
             120, 121, 123, 125, 126, 128, 130, 132, 133,
             135, 137, 139, 140, 142, 144, 146, 148, 150, 
             151, 153, 155, 157, 159, 161, 163, 165, 166, 
             168, 170, 172, 174, 176, 178, 180, 182, 184, 
             186, 188, 190, 192, 194, 196, 198, 199, 201, 
             203, 205, 207, 209, 211, 213, 215, 217, 219, 
             221, 223, 225, 227, 229, 230, 232, 234, 236, 
             237, 239, 241, 242, 244, 245, 246, 248, 249, 
             250, 251, 252, 253, 255]
    
    # Hard-coded blue channel
    blue = [4, 5, 6, 8, 10, 12, 14, 16, 18, 20, 
            23, 25, 27, 29, 31, 34, 36, 38, 41, 43, 
            45, 48, 50, 52, 55, 57, 60, 62, 65, 67, 
            69, 72, 74, 76, 79, 81, 83, 85, 87, 89, 
            91, 92, 94, 95, 97, 98, 99, 100, 101, 102, 
            103, 104, 104, 105, 106, 106, 107, 107, 108, 
            108, 108, 109, 109, 109, 110, 110, 110, 110, 
            110, 110, 110, 110, 110, 110, 110, 110, 110, 
            110, 110, 110, 110, 110, 110, 110, 109, 109, 
            109, 109, 109, 108, 108, 108, 107, 107, 107, 
            106, 106, 105, 105, 105, 104, 104, 103, 103, 
            102, 102, 101, 100, 100, 99, 99, 98, 97, 
            96, 96, 95, 94, 94, 93, 92, 91, 90, 90,
            89, 88, 87, 86, 85, 84, 83, 82, 81, 80,
            79, 78, 77, 76, 75, 74, 73, 72, 71, 70,
            69, 68, 67, 66, 65, 63, 62, 61, 60, 59,
            58, 56, 55, 54, 53, 52, 51, 49, 48, 47,
            46, 45, 43, 42, 41, 40, 38, 37, 36, 35, 
            33, 32, 31, 29, 28, 27, 25, 24, 23, 21, 
            20, 19, 18, 16, 15, 14, 12, 11, 10, 9, 
            8, 7, 7, 6, 6, 6, 6, 7, 7, 8, 
            9, 10, 12, 13, 15, 17, 18, 20, 22, 
            24, 26, 29, 31, 33, 35, 38, 40, 42, 
            45, 47, 50, 53, 55, 58, 61, 64, 67,
            70, 73, 76, 79, 83, 86, 90, 93, 97, 
            101, 105, 109, 113, 117, 121, 125, 130, 134, 138,
            142, 146, 150, 154, 157, 161, 164]
    
    # Build up the lookup table
    lut = np.zeros((1, len(red), 3), dtype=np.uint8)
    lut[0, :, 0] = blue
    lut[0, :, 1] = green
    lut[0, :, 2] = red

    # Apply gamma correction to scale (if needed)
    if gamma != 1.0:
        return gamma_correct(lut, gamma)

    return lut

# .....................................................................................................................

def cividis_colormap(gamma = 1.0):
        
    ''' 
    Hard-coded cividis colormap 
    From:
        https://github.com/opencv/opencv/blob/master/modules/imgproc/src/colormap.cpp
        
    To use:
        lut = cividis_colormap()
        cividis_color_image = cv2.LUT(grayscale_image, lut)
        
        (grayscale_image -> Must be BGR, uint8 image!)
    '''
    # Hard-coded red channel
    red = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
           0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
           0, 0, 0, 1, 5, 8, 12, 15, 18, 20,
           22, 24, 26, 28, 30, 32, 33, 35, 36, 38,
           39, 41, 42, 43, 45, 46, 47, 49, 50, 51,
           52, 53, 54, 56, 57, 58, 59, 60, 61, 62,
           63, 64, 65, 66, 67, 68, 69, 70, 71, 72,
           73, 74, 75, 76, 77, 78, 79, 80, 81, 82,
           83, 84, 85, 85, 86, 87, 88, 89, 90, 91,
           92, 93, 94, 94, 95, 96, 97, 98, 99, 100,
           101, 101, 102, 103, 104, 105, 106, 107, 108, 108,
           109, 110, 111, 112, 113, 114, 114, 115, 116, 117,
           118, 119, 119, 120, 121, 122, 123, 124, 125, 126,
           126, 127, 128, 129, 130, 131, 132, 133, 134, 135,
           136, 137, 138, 139, 140, 141, 142, 143, 144, 145,
           146, 146, 147, 148, 149, 150, 151, 152, 153, 154,
           155, 156, 157, 158, 159, 160, 161, 162, 163, 164,
           165, 166, 167, 168, 169, 170, 171, 172, 173, 174,
           175, 176, 177, 179, 180, 181, 182, 183, 184, 185,
           186, 187, 188, 189, 190, 191, 192, 193, 194, 195,
           196, 197, 198, 199, 200, 201, 203, 204, 205, 206,
           207, 208, 209, 210, 211, 212, 213, 214, 215, 217,
           218, 219, 220, 221, 222, 223, 224, 225, 226, 228,
           229, 230, 231, 232, 233, 234, 235, 237, 238, 239,
           240, 241, 242, 243, 245, 246, 247, 248, 249, 251,
           252, 253, 254, 254, 254, 254]
    
    # Hard-coded green channel
    green = [34, 35, 36, 37, 37, 38, 39, 40, 40, 41,
             42, 42, 43, 44, 44, 45, 46, 46, 47, 48,
             48, 49, 49, 50, 51, 51, 52, 53, 53, 54,
             55, 55, 56, 57, 58, 58, 59, 60, 60, 61,
             62, 63, 63, 64, 65, 65, 66, 67, 67, 68,
             69, 69, 70, 71, 72, 72, 73, 74, 74, 75,
             76, 76, 77, 78, 78, 79, 80, 81, 81, 82,
             83, 83, 84, 85, 85, 86, 87, 87, 88, 89,
             90, 90, 91, 92, 92, 93, 94, 94, 95, 96,
             97, 97, 98, 99, 99, 100, 101, 101, 102, 103,
             104, 104, 105, 106, 106, 107, 108, 109, 109, 110,
             111, 111, 112, 113, 114, 114, 115, 116, 116, 117,
             118, 119, 119, 120, 121, 122, 122, 123, 124, 124,
             125, 126, 127, 127, 128, 129, 130, 130, 131, 132,
             133, 133, 134, 135, 136, 136, 137, 138, 139, 139,
             140, 141, 142, 142, 143, 144, 145, 146, 146, 147,
             148, 149, 149, 150, 151, 152, 153, 153, 154, 155,
             156, 156, 157, 158, 159, 160, 160, 161, 162, 163,
             164, 165, 165, 166, 167, 168, 169, 169, 170, 171,
             172, 173, 174, 174, 175, 176, 177, 178, 179, 179,
             180, 181, 182, 183, 184, 185, 185, 186, 187, 188,
             189, 190, 191, 192, 192, 193, 194, 195, 196, 197,
             198, 199, 200, 200, 201, 202, 203, 204, 205, 206,
             207, 208, 209, 210, 211, 211, 212, 213, 214, 215,
             216, 217, 218, 219, 220, 221, 222, 223, 224, 225,
             226, 227, 228, 229, 230, 232]
    
    # Hard-coded blue channel
    blue = [78, 79, 81, 83, 84, 86, 88, 89, 91, 93,
            95, 97, 98, 100, 102, 104, 106, 108, 109, 111,
            112, 112, 113, 113, 113, 112, 112, 112, 112, 112,
            112, 111, 111, 111, 111, 111, 110, 110, 110, 110,
            110, 110, 109, 109, 109, 109, 109, 109, 109, 109,
            108, 108, 108, 108, 108, 108, 108, 108, 108, 108,
            108, 108, 108, 108, 108, 108, 108, 108, 108, 108,
            108, 108, 108, 108, 108, 108, 108, 108, 109, 109,
            109, 109, 109, 109, 109, 109, 109, 110, 110, 110,
            110, 110, 110, 111, 111, 111, 111, 111, 112, 112,
            112, 112, 112, 113, 113, 113, 113, 114, 114, 114,
            114, 115, 115, 115, 116, 116, 116, 117, 117, 117,
            118, 118, 119, 119, 119, 120, 120, 120, 120, 120,
            120, 120, 120, 120, 121, 121, 121, 121, 121, 120,
            120, 120, 120, 120, 120, 120, 120, 120, 120, 120,
            120, 120, 120, 119, 119, 119, 119, 119, 119, 118,
            118, 118, 118, 118, 117, 117, 117, 117, 116, 116,
            116, 116, 115, 115, 115, 115, 114, 114, 114, 113,
            113, 113, 112, 112, 111, 111, 111, 110, 110, 109,
            109, 109, 108, 108, 107, 107, 106, 106, 105, 105,
            104, 104, 103, 103, 102, 101, 101, 100, 99, 99,
            98, 98, 97, 96, 95, 95, 94, 93, 92, 92,
            91, 90, 89, 88, 88, 87, 86, 85, 84, 83,
            82, 81, 80, 79, 78, 76, 75, 74, 73, 72,
            70, 69, 68, 66, 65, 63, 62, 60, 58, 56,
            54, 52, 52, 53, 54, 56]
    
    # Build up the lookup table
    lut = np.zeros((1, len(red), 3), dtype=np.uint8)
    lut[0, :, 0] = blue
    lut[0, :, 1] = green
    lut[0, :, 2] = red

    # Apply gamma correction to scale (if needed)
    if gamma != 1.0:
        return gamma_correct(lut, gamma)

    return lut

# .....................................................................................................................

def twilight_colormap(gamma = 1.0):
        
    ''' 
    Hard-coded twilight colormap. Converted to 256 point map!
    From:
        https://github.com/opencv/opencv/blob/master/modules/imgproc/src/colormap.cpp
        
    To use:
        lut = cividis_colormap()
        cividis_color_image = cv2.LUT(grayscale_image, lut)
        
        (grayscale_image -> Must be BGR, uint8 image!)
    '''
    # Hard-coded red channel
    red = [226, 225, 225, 224, 224, 223, 222, 222, 221, 220,
           220, 219, 218, 217, 216, 215, 214, 213, 212, 211,
           210, 209, 208, 206, 205, 204, 203, 201, 200, 199,
           197, 196, 194, 193, 191, 190, 188, 187, 185, 184,
           182, 181, 179, 178, 176, 175, 173, 172, 170, 169,
           167, 166, 164, 163, 161, 160, 158, 157, 156, 154,
           153, 151, 150, 149, 147, 146, 145, 143, 142, 141,
           140, 138, 137, 136, 135, 134, 133, 132, 130, 129,
           128, 127, 126, 125, 124, 123, 122, 121, 120, 119,
           118, 118, 117, 116, 115, 114, 113, 113, 112, 111,
           110, 110, 109, 108, 108, 107, 107, 106, 105, 105,
           104, 104, 103, 103, 102, 102, 102, 101, 101, 100,
           100, 100, 99, 99, 99, 98, 98, 98, 98, 97,
           97, 97, 97, 97, 96, 96, 96, 96, 96, 96,
           96, 96, 95, 95, 95, 95, 95, 95, 95, 95,
           95, 95, 95, 95, 95, 95, 94, 94, 94, 94,
           94, 94, 94, 94, 94, 94, 94, 94, 94, 94,
           94, 93, 93, 93, 93, 93, 93, 93, 93, 92,
           92, 92, 92, 92, 91, 91, 91, 91, 90, 90,
           90, 89, 89, 89, 88, 88, 87, 87, 87, 86,
           86, 85, 85, 84, 83, 83, 82, 81, 81, 80,
           79, 79, 78, 77, 76, 76, 75, 74, 73, 72,
           71, 71, 70, 69, 68, 67, 66, 65, 65, 64,
           63, 62, 61, 61, 60, 59, 58, 58, 57, 56,
           55, 55, 54, 54, 53, 52, 52, 51, 51, 50,
           50, 49, 49, 48, 48, 47, 48, 49, 49, 50,
           51, 51, 52, 52, 53, 54, 54, 55, 56, 57,
           58, 58, 59, 60, 61, 62, 63, 64, 65, 66,
           67, 68, 70, 71, 72, 73, 74, 75, 77, 78,
           79, 80, 82, 83, 84, 86, 87, 88, 89, 91,
           92, 93, 95, 96, 97, 99, 100, 101, 103, 104,
           105, 107, 108, 109, 111, 112, 113, 114, 116, 117,
           118, 120, 121, 122, 123, 125, 126, 127, 128, 129,
           131, 132, 133, 134, 135, 136, 138, 139, 140, 141,
           142, 143, 144, 145, 146, 147, 148, 149, 150, 151,
           152, 153, 154, 155, 156, 157, 158, 159, 160, 160,
           161, 162, 163, 164, 165, 165, 166, 167, 168, 169,
           169, 170, 171, 172, 172, 173, 174, 175, 175, 176,
           177, 177, 178, 179, 179, 180, 181, 181, 182, 182,
           183, 184, 184, 185, 185, 186, 186, 187, 187, 188,
           188, 189, 189, 190, 190, 191, 191, 192, 192, 192,
           193, 193, 194, 194, 194, 195, 195, 196, 196, 196,
           197, 197, 197, 198, 198, 198, 198, 199, 199, 199,
           200, 200, 200, 200, 201, 201, 201, 202, 202, 202,
           202, 203, 203, 203, 204, 204, 204, 204, 205, 205,
           205, 206, 206, 206, 207, 207, 207, 208, 208, 208,
           209, 209, 209, 210, 210, 211, 211, 212, 212, 212,
           213, 213, 214, 214, 215, 215, 216, 216, 216, 217,
           217, 218, 218, 219, 219, 220, 220, 220, 221, 221,
           221, 222, 222, 222, 223, 223, 223, 224, 224, 224,
           224, 225, 225, 225, 225, 226, 226, 226, 226, 226]
    
    # Hard-coded green channel
    green = [217, 217, 217, 217, 217, 217, 217, 217, 217, 217,
             217, 216, 216, 216, 216, 215, 215, 214, 214, 214,
             213, 213, 212, 211, 211, 210, 210, 209, 208, 208,
             207, 206, 206, 205, 204, 204, 203, 202, 201, 201,
             200, 199, 198, 198, 197, 196, 195, 194, 194, 193,
             192, 191, 190, 190, 189, 188, 187, 186, 185, 184,
             184, 183, 182, 181, 180, 179, 178, 177, 177, 176,
             175, 174, 173, 172, 171, 170, 169, 168, 167, 166,
             165, 165, 164, 163, 162, 161, 160, 159, 158, 157,
             156, 155, 154, 153, 152, 151, 150, 149, 148, 147,
             146, 145, 144, 143, 142, 141, 140, 139, 138, 137,
             136, 135, 134, 133, 132, 131, 130, 128, 127, 126,
             125, 124, 123, 122, 121, 120, 119, 118, 117, 115,
             114, 113, 112, 111, 110, 109, 108, 106, 105, 104,
             103, 102, 101, 100, 98, 97, 96, 95, 94, 93,
             91, 90, 89, 88, 87, 85, 84, 83, 82, 81,
             79, 78, 77, 76, 75, 73, 72, 71, 70, 69,
             67, 66, 65, 64, 62, 61, 60, 59, 58, 56,
             55, 54, 53, 52, 50, 49, 48, 47, 46, 45,
             43, 42, 41, 40, 39, 38, 37, 36, 35, 34,
             33, 32, 31, 30, 30, 29, 28, 27, 26, 26,
             25, 25, 24, 23, 23, 22, 22, 21, 21, 21,
             20, 20, 20, 19, 19, 19, 18, 18, 18, 18,
             18, 17, 17, 17, 17, 17, 17, 17, 17, 17,
             17, 17, 17, 17, 17, 17, 17, 17, 17, 18,
             18, 18, 19, 19, 20, 20, 20, 19, 19, 18,
             18, 18, 18, 18, 17, 17, 17, 17, 17, 17,
             17, 17, 17, 17, 17, 17, 18, 18, 18, 18,
             18, 18, 18, 19, 19, 19, 19, 19, 20, 20,
             20, 20, 21, 21, 21, 21, 22, 22, 22, 22,
             23, 23, 23, 24, 24, 24, 25, 25, 25, 26,
             26, 27, 27, 27, 28, 28, 29, 29, 30, 30,
             31, 31, 32, 32, 33, 33, 34, 35, 35, 36,
             37, 37, 38, 39, 39, 40, 41, 42, 42, 43,
             44, 45, 46, 47, 47, 48, 49, 50, 51, 52,
             53, 54, 55, 56, 57, 58, 59, 60, 61, 62,
             63, 64, 65, 66, 67, 68, 69, 70, 71, 72,
             73, 74, 75, 76, 77, 78, 80, 81, 82, 83,
             84, 85, 86, 87, 89, 90, 91, 92, 93, 94,
             95, 97, 98, 99, 100, 101, 102, 104, 105, 106,
             107, 108, 110, 111, 112, 113, 114, 116, 117, 118,
             119, 121, 122, 123, 124, 125, 127, 128, 129, 130,
             132, 133, 134, 135, 137, 138, 139, 140, 142, 143,
             144, 145, 146, 148, 149, 150, 151, 153, 154, 155,
             156, 157, 159, 160, 161, 162, 163, 165, 166, 167,
             168, 169, 171, 172, 173, 174, 175, 176, 178, 179,
             180, 181, 182, 183, 184, 185, 186, 188, 189, 190,
             191, 192, 193, 194, 195, 196, 197, 198, 199, 200,
             201, 202, 203, 203, 204, 205, 206, 207, 208, 208,
             209, 210, 211, 211, 212, 212, 213, 214, 214, 215,
             215, 215, 216, 216, 216, 216, 217, 217, 217, 217]
    
    # Hard-coded blue channel
    blue = [226, 226, 226, 226, 226, 225, 225, 225, 224, 224,
            223, 223, 223, 222, 222, 221, 221, 220, 220, 219,
            219, 218, 217, 217, 216, 216, 215, 215, 214, 213,
            213, 212, 212, 211, 211, 210, 209, 209, 208, 208,
            207, 207, 206, 206, 205, 205, 205, 204, 204, 203,
            203, 202, 202, 202, 201, 201, 201, 200, 200, 200,
            200, 199, 199, 199, 198, 198, 198, 198, 197, 197,
            197, 197, 197, 196, 196, 196, 196, 196, 195, 195,
            195, 195, 195, 195, 194, 194, 194, 194, 194, 194,
            193, 193, 193, 193, 193, 193, 193, 192, 192, 192,
            192, 192, 192, 191, 191, 191, 191, 191, 191, 190,
            190, 190, 190, 190, 189, 189, 189, 189, 189, 188,
            188, 188, 188, 187, 187, 187, 187, 186, 186, 186,
            186, 185, 185, 185, 184, 184, 184, 183, 183, 182,
            182, 182, 181, 181, 180, 180, 180, 179, 179, 178,
            178, 177, 177, 176, 176, 175, 174, 174, 173, 173,
            172, 171, 171, 170, 169, 169, 168, 167, 166, 166,
            165, 164, 163, 162, 161, 161, 160, 159, 158, 157,
            156, 155, 154, 153, 152, 150, 149, 148, 147, 146,
            144, 143, 142, 141, 139, 138, 136, 135, 133, 132,
            130, 129, 127, 126, 124, 122, 121, 119, 117, 116,
            114, 112, 111, 109, 107, 105, 104, 102, 100, 99,
            97, 95, 94, 92, 90, 89, 87, 86, 84, 83,
            81, 80, 78, 77, 75, 74, 73, 72, 70, 69,
            68, 67, 66, 65, 64, 63, 62, 61, 60, 59,
            58, 58, 57, 56, 55, 54, 55, 55, 55, 55,
            55, 55, 56, 56, 56, 56, 57, 57, 57, 58,
            58, 58, 59, 59, 60, 60, 61, 61, 61, 62,
            62, 63, 64, 64, 65, 65, 66, 66, 67, 67,
            68, 68, 69, 69, 70, 70, 71, 71, 72, 72,
            73, 73, 74, 74, 75, 75, 75, 76, 76, 77,
            77, 77, 78, 78, 78, 78, 79, 79, 79, 79,
            79, 79, 80, 80, 80, 80, 80, 80, 80, 80,
            80, 80, 80, 80, 80, 80, 80, 80, 80, 80,
            80, 80, 80, 80, 80, 80, 80, 80, 80, 80,
            80, 80, 80, 80, 80, 80, 80, 80, 80, 80,
            80, 80, 80, 80, 80, 80, 80, 80, 80, 80,
            80, 80, 80, 80, 81, 81, 81, 81, 81, 81,
            82, 82, 82, 82, 83, 83, 83, 84, 84, 84,
            85, 85, 85, 86, 86, 87, 87, 87, 88, 88,
            89, 90, 90, 91, 91, 92, 93, 93, 94, 95,
            95, 96, 97, 98, 99, 99, 100, 101, 102, 103,
            104, 105, 106, 107, 108, 109, 110, 111, 113, 114,
            115, 116, 117, 119, 120, 121, 123, 124, 125, 127,
            128, 130, 131, 133, 134, 135, 137, 139, 140, 142,
            143, 145, 146, 148, 150, 151, 153, 155, 156, 158,
            160, 161, 163, 165, 167, 168, 170, 172, 173, 175,
            177, 179, 180, 182, 184, 185, 187, 189, 190, 192,
            194, 195, 197, 198, 200, 202, 203, 205, 206, 207,
            209, 210, 211, 212, 214, 215, 216, 217, 218, 218,
            219, 220, 221, 222, 223, 223, 224, 225, 225, 226]
    
    # Build up the lookup table
    lut = np.zeros((1, len(red), 3), dtype=np.uint8)
    lut[0, :, 0] = blue
    lut[0, :, 1] = green
    lut[0, :, 2] = red

    # Scale down to 256 values for compatibility
    resized_lut = cv2.resize(lut, dsize = (256, 1))
    
    # Apply gamma correction to scale (if needed)
    if gamma != 1.0:
        return gamma_correct(resized_lut, gamma)

    return resized_lut

# .....................................................................................................................

def create_interpolated_colormap(count_and_bgr_dict, normalized_keys = False):
    
    '''
    Helper function for generating colormaps with interpolated values.
    
    Expects an input dictionary in the form of:
        {
          0: (0, 255, 0),
          2: (0, 255, 255),
          5: (0, 0, 255),
          10: (255, 255, 255)
        }
    Note that the dictionary keys correspond to target values
    and the values correspond to the color mapped to that value.
    
    The counts do not need to be sequential, the function will interpolate the colors between values.
    Also, the function will automatically assign the same color 
    to all counts below or above the provided keys!
    
    Note that if normalized_keys is True, the keys should be given as floating point values, between 0.0 and 1.0
    '''
    
    # Get sorted counts, so we can order input bgr values properly
    sorted_counts = sorted(count_and_bgr_dict.keys())
    sorted_counts_as_ints = sorted_counts
    
    # If the input keys are normalized, scale them to uint8 range
    if normalized_keys:
        sorted_counts_as_ints = [int(round(each_value * 255)) for each_value in sorted_counts]
    
    # Find min/max counts and catch out-of-bounds errors
    min_count = min(sorted_counts_as_ints)
    max_count = max(sorted_counts_as_ints)
    if min_count < 0:
        min_allowed = 0.0 if normalized_keys else 0
        raise ValueError("Can't input counts below {} using this function!".format(min_allowed))
    if max_count > 255:
        max_allowed = 1.0 if normalized_keys else 255
        raise ValueError("Can't input counts above {} using this function!".format(max_allowed))
    
    # Build inital (empty) array to store provided colors
    input_blue_list = []
    input_green_list = []
    input_red_list = []
    
    # Build separate lists for each color, which we'll interpolate
    for row_idx, each_count in enumerate(sorted_counts):
        blue_val, green_val, red_val = count_and_bgr_dict[each_count]
        input_blue_list.append(blue_val)
        input_green_list.append(green_val)
        input_red_list.append(red_val)
    
    # Build target indices for interpolation
    low_missing_idxs = np.arange(0, min_count)
    provided_idxs = np.arange(min_count, max_count)
    high_missing_idxs = np.arange(max_count, 256)
    target_idxs = np.hstack((low_missing_idxs, provided_idxs, high_missing_idxs))
    
    # Perform interpolation to get all unspecified indices
    interp_list = lambda input_list: np.interp(target_idxs, sorted_counts_as_ints, input_list)
    interp_blue_array = interp_list(input_blue_list)
    interp_green_array = interp_list(input_green_list)
    interp_red_array = interp_list(input_red_list)
    
    # Build lookup table
    lut = np.uint8(np.round(np.vstack((interp_blue_array, interp_green_array, interp_red_array)).T))
    lut_1_by_256_by_3 = np.expand_dims(lut, 0)
    
    return lut_1_by_256_by_3

# .....................................................................................................................
    
def gamma_correct(lut, gamma):
    
    '''
    Function for apply gamma transformations to colormap LUTs.
    Input LUT must be a uint8 array with shape (1, 256, 3)
    Function returns the uint8 equivalent of:
        new_lut_value = 255 * ((old_lut_value/255) ^ gamma)
    '''
    
    # First normalize the incoming lut
    lut_norm = np.float32(lut) / 255.0
    
    # Apply gamma correction
    lut_gamma = np.power(lut_norm, gamma)
    
    # Convert back to uint8 scale
    lut_uint8 = np.uint8(np.round(255.0 * lut_gamma))
    
    return lut_uint8
    
# .....................................................................................................................
    
def apply_colormap_function(grayscale_image, colormap_function):
    
    '''
    Function for applying other colormap functions to grayscale images.
    This is not an efficient way to use colormaps, only intended for convenience
    
    Input 'colormap_function' should be one of the functions in this file (e.g. inferno_colormap),
    and should be passed in without calling (i.e. no brackets)
    '''
    
    # Decide if we need to convert to a 3 channel grayscale image
    image_shape = grayscale_image.shape
    has_3_channels = len(image_shape) > 2
    
    # Create 3 channel grayscale image for colormapping
    gray_3ch = grayscale_image if has_3_channels else cv2.cvtColor(grayscale_image, cv2.COLOR_GRAY2BGR)
    
    # Build lookup using the colormap function and apply it!
    lut = colormap_function()
    return cv2.LUT(gray_3ch, lut)

# .....................................................................................................................

def apply_colormap(image_1_channel, colormap):
    
    '''
    Helper function for applying colormaps to grayscale (single-channel) images
    '''
    
    # Create 3 channel image for colormapping
    image_3ch = cv2.cvtColor(image_1_channel, cv2.COLOR_GRAY2BGR)
    
    return cv2.LUT(image_3ch, colormap)

# .....................................................................................................................
    
def _generate_colormap_from_cpp_color_spec(color_string, print_copyable_list = True,
                                           return_int_list = False, return_print_str = False):
    
    '''
    Helper function for converting color maps from cpp files into usable colormaps in python.
    Input should be a string of normalized color values from cpp files. They should have the format of:
        
        color_string = "0.135112f, 0.138068f, 0.141013f, 0.143951f, 0.146877f, ..."
        
    See colormap file:
        https://github.com/opencv/opencv/blob/master/modules/imgproc/src/colormap.cpp
    '''
    
    # Functions to help convert color string into list of uint8 values
    split_to_list = lambda colstr: colstr.strip().split(", ")
    conv_to_float = lambda split_list: [float(each_str[:-1]) for each_str in split_list]
    conv_to_int = lambda float_list: [int(round(255*each_float)) for each_float in float_list]
    
    # Perform string parsing & uint8 conversion
    uint8_colors = conv_to_int(conv_to_float(split_to_list(color_string)))
    
    # Now build print friendly string to help copy lists into python
    print_friendly_lists = []
    for k in range(0, len(uint8_colors), 10):
        idx_1 = k
        idx_2 = idx_1 + 10
        new_sublist = uint8_colors[idx_1:idx_2]
        
        str_sublist = [str(each_element) for each_element in new_sublist]
        print_str = ", ".join(str_sublist)
        print_friendly_lists.append(print_str)
    
    # Finally, build a single string with linebreaks for copy pasting
    full_print_str = ",\n".join(["["] + print_friendly_lists + ["]"])
    
    # Print out for easy copy
    if print_copyable_list:
        print(full_print_str)
    
    # Handle possible return values
    if return_int_list and return_print_str:
        return uint8_colors, full_print_str
    elif return_int_list:
        return uint8_colors
    elif return_print_str:
        return full_print_str

# .....................................................................................................................
# .....................................................................................................................


# ---------------------------------------------------------------------------------------------------------------------
#%% Demo

if __name__ == "__main__":
    
    cv2.destroyAllWindows()
    
    # Create a horizontal grayscale bar image
    gray_1px = np.arange(0, 256, dtype=np.uint8)
    gray_img_1ch = np.repeat(np.expand_dims(gray_1px, 0), 30, axis = 0)
    gray_img_3ch = np.repeat(np.expand_dims(gray_img_1ch, 2), 3, axis = 2)
    
    '''
    # Apply colormaps
    inferno_img = apply_colormap_function(gray_img_3ch, inferno_colormap)
    cividis_img = apply_colormap_function(gray_img_3ch, cividis_colormap)
    '''
    
    # Handy function for convenience
    x_loc = 500
    y_loc = 200
    def plot(window_name, cmap_func, gamma = 1.0, y_loc_delta = 0, x_loc_delta = 0):
        cmap = cmap_func(gamma)
        cmap_image = cv2.LUT(gray_img_3ch, cmap)
        cv2.imshow(window_name, cmap_image)
        cv2.moveWindow(window_name, x = x_loc + x_loc_delta, y = y_loc + y_loc_delta)
    
    # Display images
    cv2.imshow("GRAY", gray_img_3ch); cv2.moveWindow("GRAY", x = x_loc, y = y_loc)
    
    plot("INFERNO", inferno_colormap, 1.0, 100)
    plot("INF (Gam 0.5)", inferno_colormap, 0.5, 100, -300)
    plot("INF (Gam 2.0)", inferno_colormap, 2.0, 100, 300)
    
    plot("CIVIDIS", cividis_colormap, 1.0, 200)
    plot("CIV (Gam 0.5)", cividis_colormap, 0.5, 200, -300)
    plot("CIV (Gam 2.0)", cividis_colormap, 2.0, 200, 300)
    
    plot("TWILIGHT", twilight_colormap, 1.0, 300)
    plot("TWI (Gam 0.5)", twilight_colormap, 0.5, 300, -300)
    plot("TWI (GAM 2.0)", twilight_colormap, 2.0, 300, 300)
    
    cv2.waitKey(500)
    
    pass

# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap

