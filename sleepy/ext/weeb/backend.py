"""
Copyright (c) 2018-present HitchedSyringe

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""


__all__ = (
    "detect_anime_faces",
    "do_awooify",
    "make_baguette_meme",
    "make_bodypillow_meme",
    "make_hifumi_fact_meme",
    "make_kanna_fact_meme",
    "make_lolice_meme",
    "make_nichijou_gif_meme",
    "make_ritsu_dirt_meme",
    "make_ritsu_fact_meme",
    "make_trash_waifu_meme",
)


# isort: off

# This interfaces with some aspects of the image extension.
from ..images import FONTS
from ..images.helpers import get_accurate_text_size, wrap_text

# isort: on


import io
from typing import Tuple

import cv2
import numpy as np
from jishaku.functools import executor_function
from PIL import Image, ImageDraw, ImageFont, ImageSequence

from sleepy.utils import measure_performance

from .cascades import CASCADES
from .templates import TEMPLATES

LBP_ANIMEFACE: cv2.CascadeClassifier = cv2.CascadeClassifier(
    str(CASCADES / "lbpcascade_animeface.xml")
)


@executor_function
@measure_performance
def detect_anime_faces(image_buffer: io.BytesIO) -> Tuple[int, io.BytesIO]:
    # We're using PIL here since it has built-in decompression
    # bomb protection. This is just a temporary workaround until
    # OpenCV decides to implement its own protection sometime
    # in the next century (I genuinely don't know how there is
    # almost no discussion on this topic).
    with Image.open(image_buffer) as image:
        image = np.asarray(image.convert("RGBA"))

    faces = LBP_ANIMEFACE.detectMultiScale(
        cv2.equalizeHist(cv2.cvtColor(image, cv2.COLOR_RGBA2GRAY)),
        1.1,
        5,
        minSize=(24, 24),
    )

    if (count := len(faces)) == 0:
        raise RuntimeError("No anime faces were detected.")

    # Have to flip around the colours so this way the
    # output image will look correct (red is the ending
    # band in the case of OpenCV. Shouts out to OpenCV
    # for being different and using BGR instead of RGB).
    cv2.cvtColor(image, cv2.COLOR_RGBA2BGRA, image)

    for x, y, w, h in faces:
        image = cv2.rectangle(image, (x, y), (x + w, y + h), (0, 0, 255, 255), 2)

    return count, io.BytesIO(cv2.imencode(".png", image)[1])


@executor_function
@measure_performance
def do_awooify(image_buffer: io.BytesIO) -> io.BytesIO:
    with Image.open(TEMPLATES / "awooify.png") as template:
        with Image.open(image_buffer) as image:
            binder = Image.new("RGB", template.size)
            binder.paste(image.convert("RGB").resize((302, 308)), (121, 159))

        binder.paste(template, None, template)

    buffer = io.BytesIO()

    binder.save(buffer, "png")

    buffer.seek(0)

    return buffer


@executor_function
@measure_performance
def make_baguette_meme(image_buffer: io.BytesIO) -> io.BytesIO:
    with Image.open(TEMPLATES / "baguette.png") as template:
        with Image.open(image_buffer) as image:
            mask = Image.new("1", (250, 250))
            ImageDraw.Draw(mask).ellipse((0, 0, *mask.size), 255)

            template.paste(image.convert("RGB").resize(mask.size), (223, 63), mask)

        buffer = io.BytesIO()

        template.save(buffer, "png")

    buffer.seek(0)

    return buffer


@executor_function
@measure_performance
def make_bodypillow_meme(image_buffer: io.BytesIO) -> io.BytesIO:
    with Image.open(TEMPLATES / "bodypillow.png") as template:
        with Image.open(image_buffer) as image:
            mask = Image.new("1", (140, 140))
            ImageDraw.Draw(mask).ellipse((0, 0, *mask.size), 255)

            template.paste(image.convert("RGB").resize(mask.size), (548, 107), mask)

        buffer = io.BytesIO()

        template.save(buffer, "png")

    buffer.seek(0)

    return buffer


@executor_function
@measure_performance
def make_hifumi_fact_meme(text: str) -> io.BytesIO:
    with Image.open(TEMPLATES / "hifumi_fact.png") as template:
        font = ImageFont.truetype(str(FONTS / "Arimo-Regular.ttf"), 28)
        text = wrap_text(text, font, width=290)
        text_w, text_h = font.getsize_multiline(text)

        # Draw the text centered on the poster.
        ImageDraw.Draw(template).text(
            ((template.width - text_w - 55) / 2, 430 - text_h / 2),
            text,
            "black",
            font,
            align="center",
        )

        buffer = io.BytesIO()

        template.save(buffer, "png")

    buffer.seek(0)

    return buffer


@executor_function
@measure_performance
def make_kanna_fact_meme(text: str) -> io.BytesIO:
    with Image.open(TEMPLATES / "kanna_fact.png") as template:
        font = ImageFont.truetype(str(FONTS / "Arimo-Regular.ttf"), 18)

        text = wrap_text(text, font, width=160)
        text_layer = Image.new("LA", get_accurate_text_size(font, text))

        ImageDraw.Draw(text_layer).text((0, 0), text, "black", font, align="center")

        text_layer = text_layer.rotate(-13, expand=True)

        # For reference, the desired point to center the text around is (155, 151).
        template.paste(
            text_layer,
            (155 - text_layer.width // 2, 151 - text_layer.height // 2),
            text_layer,
        )

        buffer = io.BytesIO()

        template.save(buffer, "png")

    buffer.seek(0)

    return buffer


@executor_function
@measure_performance
def make_lolice_meme(image_buffer: io.BytesIO) -> io.BytesIO:
    with Image.open(TEMPLATES / "lolice.png") as template:
        with Image.open(image_buffer) as image:
            binder = Image.new("RGB", template.size)
            binder.paste(image.convert("RGB").resize((128, 156)), (329, 133))

        binder.paste(template, None, template)

    buffer = io.BytesIO()

    binder.save(buffer, "png")

    buffer.seek(0)

    return buffer


@executor_function
@measure_performance
def make_nichijou_gif_meme(text: str) -> io.BytesIO:
    with Image.open(TEMPLATES / "nichijou.gif") as template:
        font = ImageFont.truetype(str(FONTS / "Arimo-Bold.ttf"), 45)

        frames = []
        for index, frame in enumerate(ImageSequence.Iterator(template)):
            # Essentially, the humour behind this meme is the text
            # that appears near the end, i.e. the last 5 frames.
            if index > 21:
                ImageDraw.Draw(frame).text(
                    (320, 310),
                    wrap_text(text.upper(), font, width=530),
                    "white",
                    font,
                    "mm",
                    align="center",
                    stroke_fill=0,
                    stroke_width=2,
                )

            # NOTE: Due to Pillow 9.x's changes in GIF loading, the loading
            # strategy needs to be set to `RGB_AFTER_DIFFERENT_PALETTE_ONLY`
            # for this to work properly. This is automatically set when the
            # cog loads in the interest of preserving performance. If doing
            # the above isn't desired (or you're a Pillow 9.0 user), this
            # line can alternatively be changed to the following:
            # frames.append(frame.convert("RGBA"))
            frames.append(frame.convert("P"))

    buffer = io.BytesIO()

    frames[0].save(buffer, "gif", save_all=True, append_images=frames[1:])

    buffer.seek(0)

    return buffer


@executor_function
@measure_performance
def make_ritsu_dirt_meme(image_buffer: io.BytesIO) -> io.BytesIO:
    with Image.open(TEMPLATES / "ritsu_dirt.png") as template:
        with Image.open(image_buffer) as image:
            binder = Image.new("RGB", template.size)
            binder.paste(image.convert("RGB").resize((440, 576)), (415, 47))

        binder.paste(template, None, template)

    buffer = io.BytesIO()

    binder.save(buffer, "png")

    buffer.seek(0)

    return buffer


@executor_function
@measure_performance
def make_ritsu_fact_meme(text: str) -> io.BytesIO:
    with Image.open(TEMPLATES / "ritsu_fact.png") as template:
        font = ImageFont.truetype(str(FONTS / "Arimo-Regular.ttf"), 50)

        text = wrap_text(text, font, width=270)
        text_layer = Image.new("LA", get_accurate_text_size(font, text))

        ImageDraw.Draw(text_layer).text((0, 0), text, "black", font, align="center")

        text_layer = text_layer.rotate(-2, expand=True)

        # For reference, the desired point to center the text around is (727, 428).
        template.paste(
            text_layer,
            (727 - text_layer.width // 2, 428 - text_layer.height // 2),
            text_layer,
        )

        buffer = io.BytesIO()

        template.save(buffer, "png")

    buffer.seek(0)

    return buffer


@executor_function
@measure_performance
def make_trash_waifu_meme(image_buffer: io.BytesIO) -> io.BytesIO:
    with Image.open(TEMPLATES / "trash_waifu.png") as template:
        with Image.open(image_buffer) as image:
            template.paste(image.convert("RGB").resize((384, 255)), (383, 704))

        buffer = io.BytesIO()

        template.save(buffer, "png")

    buffer.seek(0)

    return buffer
