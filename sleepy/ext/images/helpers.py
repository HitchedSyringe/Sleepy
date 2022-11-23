"""
Copyright (c) 2018-present HitchedSyringe

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""


from __future__ import annotations

__all__ = (
    "get_accurate_text_size",
    "wrap_text",
)


import textwrap
from typing import TYPE_CHECKING, Tuple

if TYPE_CHECKING:
    from PIL.ImageFont import FreeTypeFont


def get_accurate_text_size(font: FreeTypeFont, text: str) -> Tuple[int, int]:
    from PIL import Image, ImageDraw

    # FreeTypeFont.getsize_multiline is deprecated as of
    # Pillow 9.2.x and is slated to be removed by 10.0.0.
    # This is the next best way to do this without having
    # to duplicate a bunch of code.
    draw = ImageDraw.Draw(Image.new("1", (0, 0)))
    return draw.multiline_textbbox((0, 0), text, font)[2:]


def wrap_text(text: str, font: FreeTypeFont, *, width: float) -> str:
    text_width = font.getlength(text)
    adjusted_width = int(width * len(text) / text_width)

    if text_width < adjusted_width:
        return text

    return textwrap.fill(text, adjusted_width, replace_whitespace=False)
