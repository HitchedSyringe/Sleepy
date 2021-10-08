"""
Copyright (c) 2018-present HitchedSyringe

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""


__all__ = (
    "get_accurate_text_size",
    "get_cascade_detections",
    "wrap_text",
)


import textwrap

import cv2


def get_accurate_text_size(font, text, /):
    # The normal getsize doesn't account for newline characters.
    width, height = font.getsize_multiline(text)
    return width, height + font.getmetrics()[1]


def get_cascade_detections(cascade, grayscale_image_array, /):
    # NOTE: Detections can either be an empty tuple
    # if nothing was detected or a non-empty numpy
    # array if something was detected.
    detections = cascade.detectMultiScale(
        cv2.equalizeHist(grayscale_image_array),
        1.2,
        5,
        minSize=(24, 24)
    )

    return len(detections), detections


def wrap_text(text, font, /, *, width):
    text_width = font.getsize(text)[0]
    adjusted_width = len(text) * width // text_width

    if text_width < adjusted_width:
        return text

    return textwrap.fill(text, adjusted_width, replace_whitespace=False)
