#! /usr/bin/env python3
# Copyright (c) 2020, NVIDIA CORPORATION.  All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import sys
sys.path.insert(0, os.getcwd())

import argparse
import numpy as np
import shutil

from code.common import logging
import cv2
import math
from PIL import Image

def center_crop(img, output_size):
    image_width, image_height = img.size
    crop_height, crop_width = output_size
    crop_top = int(round((image_height - crop_height) / 2.))
    crop_left = int(round((image_width - crop_width) / 2.))

    def crop(img, top, left, height, width):
        return img.crop((left, top, left + width, top + height))

    return crop(img, crop_top, crop_left, crop_height, crop_width)

def resize_with_aspectratio(img, out_size, interpolation = Image.BILINEAR):
    w, h  = img.size
    size = out_size
    if (w <= h and w == size) or (h <= w and h == out_size):
        return img
    if w < h:
        ow = size
        oh = int(size * h / w)
        return img.resize((ow, oh), interpolation)
    else:
        oh = size
        ow = int(size * w / h)

    img = img.resize((ow,oh), interpolation)
    return img

class ImagePreprocessor:
    def __init__(self, loader, quantizer):
        self.loader = loader
        self.quantizer = quantizer
        self.all_formats = ["fp32", "int8_linear", "int8_chw4"]

    def run(self, src_dir, dst_dir, data_map, formats, overwrite=False):
        assert all([i in self.all_formats for i in formats]), "Unsupported formats {:}.".format(formats)
        self.src_dir = src_dir
        self.dst_dir = dst_dir
        self.run_formats = formats
        self.overwrite = overwrite
        self.make_dirs()

        image_list = []
        with open(data_map) as f:
            for line in f:
                image_list.append(line.split()[0])
        self.convert(image_list)

    def make_dirs(self):
        for format in self.run_formats:
            dir = self.get_dir(format)
            if not os.path.exists(dir):
                os.makedirs(dir)

    def convert(self, image_list):
        for idx, img_file in enumerate(image_list):
            logging.info("Processing image No.{:d}/{:d}...".format(idx, len(image_list)))
            output_files = [self.get_filename(format, img_file) for format in self.run_formats]

            if all([os.path.exists(i) for i in output_files]) and not self.overwrite:
                logging.info("Skipping {:} because it already exists.".format(img_file))
                continue

            image_fp32 = self.loader(os.path.join(self.src_dir, img_file))
            if "fp32" in self.run_formats:
                np.save(self.get_filename("fp32", img_file), image_fp32)
            image_int8_linear = self.quantizer(image_fp32)
            if "int8_linear" in self.run_formats:
                np.save(self.get_filename("int8_linear", img_file), image_int8_linear)
            image_int8_chw4 = self.linear_to_chw4(image_int8_linear)
            if "int8_chw4" in self.run_formats:
                np.save(self.get_filename("int8_chw4", img_file), image_int8_chw4)

    def get_dir(self, format):
        return os.path.join(self.dst_dir, format)

    def get_filename(self, format, img_file):
        return os.path.join(self.get_dir(format), "{:}.npy".format(img_file))

    def linear_to_chw4(self, image_int8):
        return np.moveaxis(np.pad(image_int8, ((0, 1), (0, 0),(0, 0)), "constant"), -3, -1)
