"""
Copyright (c) 2018-present HitchedSyringe

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""


__all__ = (
    "get_accurate_text_size",
    "wrap_text",
)


import textwrap


def get_accurate_text_size(font, text, /):
    # The normal getsize doesn't account for newline characters.
    width, height = font.getsize_multiline(text)
    return width, height + font.getmetrics()[1]


def wrap_text(text, font, /, *, width):
    text_width = font.getsize(text)[0]
    adjusted_width = len(text) * width // text_width

    if text_width < adjusted_width:
        return text

    return textwrap.fill(text, adjusted_width, replace_whitespace=False)
