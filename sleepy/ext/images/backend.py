"""
Copyright (c) 2018-present HitchedSyringe

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""


__all__ = (
    "do_asciify",
    "do_blurpify",
    "do_deepfry",
    "do_jpegify",
    "do_swirl",
    "make_axios_interview_meme",
    "make_captcha",
    "make_change_my_mind_meme",
    "make_clyde_message",
    "make_iphone_x",
    "make_live_tucker_reaction_meme",
    "make_pornhub_comment",
    "make_roblox_cancel_meme",
    "make_ship",
    "make_text_image",
    "make_threats_meme",
    "make_trapcard",
    "make_tweet",
    "make_who_would_win_meme",
    "make_youtube_comment",
)


import io
from math import radians, sin
from datetime import datetime

import imageio
import numpy
from PIL import (
    Image,
    ImageDraw,
    ImageEnhance,
    ImageFilter,
    ImageFont,
    ImageOps,
    ImageSequence,
)
from skimage import transform
from sleepy.utils import awaitable, measure_performance

from .helpers import get_accurate_text_size, wrap_text
from .fonts import FONTS
from .templates import TEMPLATES


# Chars are ordered from dark -> light.
ASCII_CHARS = (
    " ",
    ".",
    "'",
    "-",
    ",",
    "_",
    '"',
    "^",
    "*",
    ":",
    ";",
    "~",
    "=",
    "+",
    "<",
    ">",
    "!",
    "?",
    "\\",
    "/",
    "|",
    "(",
    ")",
    "]",
    "[",
    "}",
    "{",
    "#",
    "&",
    "$",
    "%",
    "@",
)


AXIOS_SINE = sin(radians(12.5))
CMM_SINE = sin(radians(22.5))


@awaitable
@measure_performance
def do_asciify(image_buffer, /, *, inverted=False):
    chars = ASCII_CHARS[::-1] if inverted else ASCII_CHARS

    with Image.open(image_buffer) as image:
        data = numpy.asarray(image.convert("L").resize((61, 61)))

    return "\n".join("".join(chars[c // 8] for c in r) for r in data[::2])


@awaitable
@measure_performance
def do_blurpify(image_buffer, /, *, use_rebrand=False):
    with Image.open(image_buffer) as image:
        blurple = (88, 101, 242) if use_rebrand else (114, 137, 218)

        frames = [
            ImageOps.colorize(
                ImageEnhance.Contrast(f.convert("L")).enhance(1000),
                blurple,
                "white"
            ) for f in ImageSequence.Iterator(image)
        ]

    buffer = io.BytesIO()

    if len(frames) == 1:
        frames[0].save(buffer, "png")
        buffer.name = "blurplefied.png"
    else:
        frames[0].save(
            buffer,
            "gif",
            save_all=True,
            optimize=True,
            append_images=frames[1:]
        )
        buffer.name = "blurplefied.gif"

    buffer.seek(0)

    return buffer


@awaitable
@measure_performance
def do_deepfry(image_buffer, /):
    with Image.open(image_buffer) as image:
        frames = []
        for frame in ImageSequence.Iterator(image):
            frame = frame.convert("RGB")

            red = frame.split()[0]
            red = ImageEnhance.Contrast(red).enhance(2)
            red = ImageEnhance.Brightness(red).enhance(1.5)
            red = ImageOps.colorize(red, (254, 0, 2), (255, 255, 15))

            frame = Image.blend(frame, red, 0.77)
            frame = ImageEnhance.Sharpness(frame).enhance(150)
            frames.append(frame)

    buffer = io.BytesIO()

    if len(frames) == 1:
        frames[0].save(buffer, "jpeg", quality=1)
        buffer.name = "deepfried.jpeg"
    else:
        frames[0].save(
            buffer,
            "gif",
            save_all=True,
            optimize=True,
            append_images=frames[1:]
        )
        buffer.name = "deepfried.gif"

    buffer.seek(0)

    return buffer


@awaitable
@measure_performance
def do_jpegify(image_buffer, /, *, quality=1):
    with Image.open(image_buffer) as image:
        buffer = io.BytesIO()

        image.convert("RGB").save(buffer, "jpeg", quality=quality)

    buffer.seek(0)

    return buffer


@awaitable
@measure_performance
def do_swirl(image_buffer, /, *, intensity=1):
    with Image.open(image_buffer) as image:
        image = transform.swirl(
            numpy.asarray(image.convert("RGBA")),
            strength=intensity,
            radius=image.height / 2,
            preserve_range=True
        )

    buffer = io.BytesIO()

    imageio.imwrite(buffer, image.astype(numpy.uint8), "png", optimize=True)

    buffer.seek(0)

    return buffer


@awaitable
@measure_performance
def make_axios_interview_meme(text, /):
    with Image.open(TEMPLATES / "axios_interview.jpg") as template:
        font = ImageFont.truetype(str(FONTS / "Arimo-Regular.ttf"), 60)

        text = wrap_text(text, font, width=650)
        text_layer = Image.new("RGBA", get_accurate_text_size(font, text))
        t_w, t_h = text_layer.size

        ImageDraw.Draw(text_layer).text(
            (0, 0),
            text,
            "black",
            font,
            align="center"
        )

        text_layer = text_layer.rotate(-12.5, expand=True)

        # For reference, centering the text uses the following:
        # x = mid_x - ((text_layer_w + displacement) // 2)
        # y = mid_y - ((rotated_text_layer_h + displacement) // 2)
        # The midpoint of this image is at (502, 1002).
        # Note that the displacement bit is necessary to account for
        # the fact that the top left corner point is also translated
        # (in this case, horizontally to the right) when the text
        # layer is rotated. We need to base the paste location on the
        # correct corner point in order to properly position this text.
        template.paste(
            text_layer,
            (
                532 - ((t_w + int(t_h * AXIOS_SINE)) // 2),
                1002 - (text_layer.height // 2)
            ),
            text_layer
        )

        buffer = io.BytesIO()

        template.save(buffer, "png")

    buffer.seek(0)

    return buffer


@awaitable
@measure_performance
def make_captcha(image_buffer, text, /):
    with Image.open(TEMPLATES / "captcha.png") as template:
        with Image.open(image_buffer) as image:
            binder = Image.new("RGB", template.size)
            binder.paste(image.convert("RGB").resize((386, 386)), (5, 127))

        ImageDraw.Draw(template).text(
            (29, 46),
            text,
            font=ImageFont.truetype(str(FONTS / "Roboto-Black.ttf"), 28)
        )

        binder.paste(template, template)

    buffer = io.BytesIO()

    binder.save(buffer, "png")

    buffer.seek(0)

    return buffer


@awaitable
@measure_performance
def make_change_my_mind_meme(text, /):
    with Image.open(TEMPLATES / "change_my_mind.png") as template:
        font = ImageFont.truetype(str(FONTS / "Arimo-Regular.ttf"), 50)

        text = wrap_text(text, font, width=620)
        text_layer = Image.new("RGBA", get_accurate_text_size(font, text))
        t_w = text_layer.width

        ImageDraw.Draw(text_layer).text(
            (0, 0),
            text,
            "black",
            font,
            align="center"
        )

        text_layer = text_layer.rotate(22.5, expand=True)

        # For reference, the midpoint is at (1245, 983).
        template.alpha_composite(
            text_layer,
            (1245 - (t_w // 2), 983 - int(t_w * CMM_SINE))
        )

        buffer = io.BytesIO()

        template.save(buffer, "png")

    buffer.seek(0)

    return buffer


@awaitable
@measure_performance
def make_clyde_message(text, /, *, use_rebrand=False):
    clyde = "rebrand_clyde.png" if use_rebrand else "classic_clyde.png"

    with Image.open(TEMPLATES / clyde) as template:
        font = ImageFont.truetype(str(FONTS / "Catamaran-Regular.ttf"), 16)

        draw = ImageDraw.Draw(template)
        draw.text(
            (209, 4),
            datetime.utcnow().strftime("%H:%M"),
            (114, 118, 125),
            font.font_variant(size=14)
        )
        draw.text(
            (74, 25),
            wrap_text(text, font, width=745),
            (220, 221, 222),
            font
        )

        buffer = io.BytesIO()

        template.save(buffer, "png")

    buffer.seek(0)

    return buffer


@awaitable
@measure_performance
def make_iphone_x(image_buffer, /):
    with Image.open(TEMPLATES / "iphonex.png") as template:
        with Image.open(image_buffer) as image:
            binder = Image.new("RGBA", template.size)
            binder.paste(image.convert("RGB").resize((242, 524)), (19, 18))

        binder.alpha_composite(template)

    buffer = io.BytesIO()

    binder.save(buffer, "png")

    buffer.seek(0)

    return buffer


@awaitable
@measure_performance
def make_live_tucker_reaction_meme(image_buffer, /):
    with Image.open(TEMPLATES / "live_tucker_reaction.png") as template:
        with Image.open(image_buffer) as image:
            image = image.convert("RGB")

        w, h = template.size
        blur = image.resize((w, h)).filter(ImageFilter.GaussianBlur(10))

        # In order to actually make this look like a realistic
        # occurrance on Tucker Carlson Live, we have to keep the
        # image in its original aspect ratio and scale it with
        # the height of the template, as well as centering the
        # actual image. Also, just to make it look better, I
        # generated a stretched blurred version just to fill the
        # resulting empty space in the background.
        i_new_w = round(image.width * (h / image.height))

        blur.paste(image.resize((i_new_w, h)), ((w - i_new_w) // 2, 0))
        blur.paste(template, template)

    buffer = io.BytesIO()

    blur.save(buffer, "png")

    buffer.seek(0)

    return buffer


@awaitable
@measure_performance
def make_pornhub_comment(username, avatar, comment, /):
    with Image.open(TEMPLATES / "pornhub_comment.png") as template:
        with Image.open(avatar) as avi:
            template.paste(avi.convert("RGB").resize((52, 52)), (24, 264))

        draw = ImageDraw.Draw(template)
        font = ImageFont.truetype(str(FONTS / "Arimo-Regular.ttf"), 25)

        draw.text((89, 275), username, (255, 163, 26), font)
        draw.text((25, 343), wrap_text(comment, font, width=950), font=font)

        buffer = io.BytesIO()

        template.save(buffer, "png")

    buffer.seek(0)

    return buffer


@awaitable
@measure_performance
def make_roblox_cancel_meme(avatar, username, discriminator, /):
    with Image.open(TEMPLATES / "roblox_cancel.jpg") as template:
        with Image.open(avatar) as avi:
            mask = Image.new("1", (80, 80))
            ImageDraw.Draw(mask).ellipse((0, 0, *mask.size), 255)

            template.paste(avi.convert("RGB").resize(mask.size), (25, 130), mask)

        draw = ImageDraw.Draw(template)

        username_font = ImageFont.truetype(str(FONTS / "Catamaran-ExtraBold.ttf"), 18)
        draw.text((25, 215), username, "white", username_font)
        draw.text(
            (25 + username_font.getsize(username)[0], 219),
            f"#{discriminator}",
            (185, 187, 190),
            ImageFont.truetype(str(FONTS / "Catamaran-Regular.ttf"), 14)
        )

        cancel_font_big = ImageFont.truetype(str(FONTS / "Roboto-Black.ttf"), 32)
        draw.text(
            (155, -2),
            f"{username}!!",
            "white",
            cancel_font_big
        )

        cancel_font_small = cancel_font_big.font_variant(size=16)
        draw.text(
            (409, 103),
            username,
            "white",
            cancel_font_small,
        )
        draw.text(
            (424, 167),
            username,
            "white",
            cancel_font_small,
            "mm",
            align="center",
        )

        buffer = io.BytesIO()

        template.save(buffer, "png")

    buffer.seek(0)

    return buffer


@awaitable
@measure_performance
def make_ship(first_avatar, second_avatar, /):
    with Image.open(TEMPLATES / "ship.png") as template:
        mask = Image.new("1", (160, 160))
        ImageDraw.Draw(mask).ellipse((0, 0, *mask.size), 255)

        with Image.open(first_avatar) as first:
            template.paste(first.convert("RGB").resize(mask.size), (185, 98), mask)

        with Image.open(second_avatar) as second:
            template.paste(second.convert("RGB").resize(mask.size), (420, 55), mask)

        buffer = io.BytesIO()

        template.save(buffer, "png")

    buffer.seek(0)

    return buffer


# Not enforcing positionals here since the actual command
# just passes the flags in as kwargs, which would break
# what was an easy and simple approach to frontending this.
@awaitable
@measure_performance
def make_text_image(text, font_path, *, size, text_colour=None, bg_colour=None):
    font = ImageFont.truetype(str(font_path), size)
    text = wrap_text(text, font, width=650)
    image = Image.new("RGBA", get_accurate_text_size(font, text), bg_colour)

    # Default colour is Discord's light grey for neutrality
    # between dark mode and light mode users.
    ImageDraw.Draw(image).text((0, 0), text, text_colour or (153, 170, 181), font)

    buffer = io.BytesIO()

    image.save(buffer, "png")

    buffer.seek(0)

    return buffer


@awaitable
@measure_performance
def make_threats_meme(image_buffer, /):
    with Image.open(TEMPLATES / "threats.png") as template:
        with Image.open(image_buffer) as image:
            template.paste(image.convert("RGB").resize((330, 230)), (735, 125))

        buffer = io.BytesIO()

        template.save(buffer, "png")

    buffer.seek(0)

    return buffer


@awaitable
@measure_performance
def make_trapcard(title, flavour_text, image_buffer, /):
    with Image.open(TEMPLATES / "trapcard.png") as template:
        with Image.open(image_buffer) as image:
            template.paste(image.convert("RGB").resize((526, 526)), (107, 210))

        font = ImageFont.truetype(str(FONTS / "Lustria-Regular.ttf"), 24)

        draw = ImageDraw.Draw(template)
        draw.text(
            (74, 786),
            wrap_text(flavour_text, font, width=575),
            "black",
            font
        )

        draw.text(
            (74, 70),
            title.upper(),
            "black",
            ImageFont.truetype(str(FONTS / "SourceSerifPro-SemiBold.ttf"), 50)
        )

        buffer = io.BytesIO()

        template.save(buffer, "png")

    buffer.seek(0)

    return buffer


@awaitable
@measure_performance
def make_tweet(handle, display_name, avatar, text, /):
    with Image.open(TEMPLATES / "tweet.png") as template:
        with Image.open(avatar) as avi:
            mask = Image.new("1", (49, 49))
            ImageDraw.Draw(mask).ellipse((0, 0, *mask.size), 255)

            template.paste(avi.convert("RGB").resize(mask.size), (13, 8), mask)

        draw = ImageDraw.Draw(template)
        draw.text(
            (72, 14),
            display_name,
            (217, 217, 217),
            ImageFont.truetype(str(FONTS / "Arimo-Bold.ttf"), 15)
        )

        text_font = ImageFont.truetype(str(FONTS / "Arimo-Regular.ttf"), 23)
        draw.text(
            (13, 75),
            wrap_text(text, text_font, width=568),
            (217, 217, 217),
            text_font,
            spacing=8
        )

        small_text_font = text_font.font_variant(size=15)
        draw.text(
            (13, 208),
            f"{datetime.utcnow():%I:%M %p · %b %d, %Y} \N{MIDDLE DOT} Sleepy",
            (110, 118, 125),
            small_text_font
        )
        draw.text((72, 33), f"@{handle}", (110, 118, 125), small_text_font)

        buffer = io.BytesIO()

        template.save(buffer, "png")

    buffer.seek(0)

    return buffer


@awaitable
@measure_performance
def make_who_would_win_meme(left_image, right_image, /):
    with Image.open(TEMPLATES / "who_would_win.png") as template:
        with Image.open(left_image) as left:
            template.paste(left.convert("RGB").resize((1024, 1220)), (85, 380))

        with Image.open(right_image) as right:
            template.paste(right.convert("RGB").resize((992, 1220)), (1138, 380))

        buffer = io.BytesIO()

        template.save(buffer, "png")

    buffer.seek(0)

    return buffer


@awaitable
@measure_performance
def make_youtube_comment(username, avatar, comment, /):
    with Image.open(TEMPLATES / "youtube_comment.png") as template:
        with Image.open(avatar) as avi:
            mask = Image.new("1", (40, 40))
            ImageDraw.Draw(mask).ellipse((0, 0, *mask.size), 255)

            template.paste(avi.convert("RGB").resize(mask.size), (25, 25), mask)

        username_font = ImageFont.truetype(str(FONTS / "Roboto-Medium.ttf"), 15)

        draw = ImageDraw.Draw(template)
        draw.text((83, 25), username, (3, 3, 3), username_font)

        text_font = ImageFont.truetype(str(FONTS / "Roboto-Regular.ttf"), 14)
        draw.text(
            (84, 47),
            wrap_text(comment, text_font, width=450),
            (3, 3, 3),
            text_font
        )
        draw.text(
            # Arbitrary positioning of comment timestamp.
            (username_font.getsize(username)[0] + 94, 25),
            "1 week ago",
            (96, 96, 96),
            text_font
        )

        buffer = io.BytesIO()

        template.save(buffer, "png")

    buffer.seek(0)

    return buffer
