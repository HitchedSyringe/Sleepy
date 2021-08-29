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


# This interfaces with some aspects of the image extension.
from ..images import FONTS
from ..images.helpers import get_accurate_text_size, wrap_text


import io
from math import radians, sin

import cv2
import numpy
from PIL import Image, ImageDraw, ImageFont, ImageSequence
from sleepy.utils import awaitable, measure_performance

from .cascades import CASCADES
from .templates import TEMPLATES


ANIME_FACE_CASCADE = cv2.CascadeClassifier(str(CASCADES / "lbpcascade_animeface.xml"))
RITSU_SINE = sin(radians(2))
KANNA_SINE = sin(radians(13))


@awaitable
@measure_performance
def detect_anime_faces(image_buffer, /):
    # We're using PIL here since it has built-in decompression
    # bomb protection. This is just a temporary workaround until
    # OpenCV decides to implement its own protection sometime
    # in the next century (I genuinely don't know how there is
    # almost no discussion on this topic).
    with Image.open(image_buffer) as image:
        image = numpy.asarray(image.convert("RGBA"))

    faces = ANIME_FACE_CASCADE.detectMultiScale(
        cv2.equalizeHist(cv2.cvtColor(image, cv2.COLOR_RGBA2GRAY)),
        1.1,
        5,
        minSize=(24, 24)
    )

    # Yes yes return both tuples and numpy arrays
    # why don't you. What matters here is that faces
    # isn't empty.
    if len(faces) == 0:
        return None

    # Have to flip around the colours so this way the
    # output image will look correct (red is the ending
    # band in the case of OpenCV. Shouts out to OpenCV
    # for being different and using BGR instead of RGB).
    image = cv2.cvtColor(image, cv2.COLOR_RGBA2BGRA)

    for x, y, w, h in faces:
        image = cv2.rectangle(
            image,
            (x, y),
            (x + w, y + h),
            (0, 0, 255, 255),
            2
        )

    return io.BytesIO(cv2.imencode(".png", image)[1])


@awaitable
@measure_performance
def do_awooify(image_buffer, /):
    with Image.open(TEMPLATES / "awooify.png") as template:
        with Image.open(image_buffer) as image:
            binder = Image.new("RGB", template.size)
            binder.paste(image.convert("RGB").resize((302, 308)), (121, 159))

        binder.paste(template, template)

    buffer = io.BytesIO()

    binder.save(buffer, "png")

    buffer.seek(0)

    return buffer


@awaitable
@measure_performance
def make_baguette_meme(image_buffer, /):
    with Image.open(TEMPLATES / "baguette.png") as template:
        with Image.open(image_buffer) as image:
            mask = Image.new("1", (250, 250))
            ImageDraw.Draw(mask).ellipse((0, 0, *mask.size), 255)

            template.paste(image.convert("RGB").resize(mask.size), (223, 63), mask)

        buffer = io.BytesIO()

        template.save(buffer, "png")

    buffer.seek(0)

    return buffer


@awaitable
@measure_performance
def make_bodypillow_meme(image_buffer, /):
    with Image.open(TEMPLATES / "bodypillow.png") as template:
        with Image.open(image_buffer) as image:
            mask = Image.new("1", (140, 140))
            ImageDraw.Draw(mask).ellipse((0, 0, *mask.size), 255)

            template.paste(image.convert("RGB").resize(mask.size), (548, 107), mask)

        buffer = io.BytesIO()

        template.save(buffer, "png")

    buffer.seek(0)

    return buffer


@awaitable
@measure_performance
def make_hifumi_fact_meme(text, /):
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
            align="center"
        )

        buffer = io.BytesIO()

        template.save(buffer, "png")

    buffer.seek(0)

    return buffer


@awaitable
@measure_performance
def make_kanna_fact_meme(text, /):
    with Image.open(TEMPLATES / "kanna_fact.png") as template:
        font = ImageFont.truetype(str(FONTS / "Arimo-Regular.ttf"), 18)

        text = wrap_text(text, font, width=160)
        text_layer = Image.new("RGBA", get_accurate_text_size(font, text))
        t_w, t_h = text_layer.size

        ImageDraw.Draw(text_layer).text(
            (0, 0),
            text,
            "black",
            font,
            align="center"
        )

        text_layer = text_layer.rotate(-13, expand=True)

        # For reference, the midpoint is at (155, 171).
        template.paste(
            text_layer,
            (
                155 - (t_w + int(t_h * KANNA_SINE)) // 2,
                151 - text_layer.height // 2
            ),
            text_layer
        )

        buffer = io.BytesIO()

        template.save(buffer, "png")

    buffer.seek(0)

    return buffer


@awaitable
@measure_performance
def make_lolice_meme(image_buffer, /):
    with Image.open(TEMPLATES / "lolice.png") as template:
        with Image.open(image_buffer) as image:
            binder = Image.new("RGB", template.size)
            binder.paste(image.convert("RGB").resize((128, 156)), (329, 133))

        binder.paste(template, template)

    buffer = io.BytesIO()

    binder.save(buffer, "png")

    buffer.seek(0)

    return buffer


@awaitable
@measure_performance
def make_nichijou_gif_meme(text, /):
    with Image.open(TEMPLATES / "nichijou.gif") as template:
        font = ImageFont.truetype(str(FONTS / "Arimo-Bold.ttf"), 36)

        frames = []
        for index, frame in enumerate(ImageSequence.Iterator(template)):
            # Essentially, the humour behind this meme is the text
            # that appears near the end, i.e. the last 21 frames.
            if index > 21:
                ImageDraw.Draw(frame).text(
                    (320, 310),
                    wrap_text(text.upper(), font, width=530),
                    251,
                    font,
                    "mm",
                    align="center",
                    stroke_fill=0,
                    stroke_width=2
                )

            frames.append(frame.convert("P"))

    buffer = io.BytesIO()

    frames[0].save(
        buffer,
        "gif",
        save_all=True,
        optimize=True,
        append_images=frames[1:]
    )

    buffer.seek(0)

    return buffer


@awaitable
@measure_performance
def make_ritsu_dirt_meme(image_buffer, /):
    with Image.open(TEMPLATES / "ritsu_dirt.png") as template:
        with Image.open(image_buffer) as image:
            binder = Image.new("RGB", template.size)
            binder.paste(image.convert("RGB").resize((440, 576)), (415, 47))

        binder.paste(template, template)

    buffer = io.BytesIO()

    binder.save(buffer, "png")

    buffer.seek(0)

    return buffer


@awaitable
@measure_performance
def make_ritsu_fact_meme(text, /):
    with Image.open(TEMPLATES / "ritsu_fact.png") as template:
        font = ImageFont.truetype(str(FONTS / "Arimo-Regular.ttf"), 50)

        text = wrap_text(text, font, width=270)
        text_layer = Image.new("RGBA", get_accurate_text_size(font, text))
        t_w, t_h = text_layer.size

        ImageDraw.Draw(text_layer).text(
            (0, 0),
            text,
            "black",
            font,
            align="center"
        )
        text_layer = text_layer.rotate(-2, expand=True)

        # For reference, the midpoint is at (727, 428).
        template.paste(
            text_layer,
            (
                727 - (t_w + int(t_h * RITSU_SINE)) // 2,
                428 - text_layer.height // 2
            ),
            text_layer
        )

        buffer = io.BytesIO()

        template.save(buffer, "png")

    buffer.seek(0)

    return buffer


@awaitable
@measure_performance
def make_trash_waifu_meme(image_buffer, /):
    with Image.open(TEMPLATES / "trash_waifu.png") as template:
        with Image.open(image_buffer) as image:
            template.paste(image.convert("RGB").resize((384, 255)), (383, 704))

        buffer = io.BytesIO()

        template.save(buffer, "png")

    buffer.seek(0)

    return buffer
