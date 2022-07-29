"""
Copyright (c) 2018-present HitchedSyringe

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""


from __future__ import annotations

__all__ = (
    "get_accurate_text_size",
    "has_minimum_pillow_minor_version",
    "wrap_text",
)


import textwrap
from typing import TYPE_CHECKING, Optional, Tuple

if TYPE_CHECKING:
    from PIL.ImageFont import FreeTypeFont


__PILLOW_MINOR_VERSION: Optional[Tuple[int, int]] = None


def has_minimum_pillow_minor_version(minor_version: Tuple[int, int]) -> bool:
    from PIL import __version__ as pillow_version

    global __PILLOW_MINOR_VERSION

    if __PILLOW_MINOR_VERSION is None:
        # This is proofed against .dev[x] versions and release candidates.
        # We hopefully shouldn't have to care too much about patch levels.
        pmajor, pminor, *_ = pillow_version.split(".")

        # Cache the result so we don't have to parse every time.
        __PILLOW_MINOR_VERSION = (int(pmajor), int(pminor))

    return __PILLOW_MINOR_VERSION >= minor_version


def get_accurate_text_size(font: FreeTypeFont, text: str) -> Tuple[int, int]:
    from PIL import Image, ImageDraw

    # FreeTypeFont.getsize_multiline is deprecated as of
    # Pillow 9.2.x and is slated to be removed by 10.0.0.
    # This is the next best way to do this without having
    # to duplicate a bunch of code.
    draw = ImageDraw.Draw(Image.new("1", (0, 0)))
    return draw.multiline_textbbox((0, 0), text, font)[2:]


def wrap_text(text: str, font: FreeTypeFont, *, width: int) -> str:
    if has_minimum_pillow_minor_version((9, 2)):
        text_width = int(font.getlength(text))
    else:
        text_width = font.getsize(text)[0]

    adjusted_width = len(text) * width // text_width

    if text_width < adjusted_width:
        return text

    return textwrap.fill(text, adjusted_width, replace_whitespace=False)
