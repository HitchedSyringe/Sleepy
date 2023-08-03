"""
Copyright (c) 2018-present HitchedSyringe

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published
by the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""


from __future__ import annotations

__all__ = (
    "do_asciify",
    "do_blurpify",
    "do_deepfry",
    "do_invert",
    "do_jpegify",
    "do_lensflare_eyes",
    "do_swirl",
    "make_axios_interview_meme",
    "make_captcha",
    "make_change_my_mind_meme",
    "make_clyde_message",
    "make_dalgona",
    "make_iphone_x",
    "make_live_tucker_reaction_meme",
    "make_pointing_soyjaks_meme",
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
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Optional, Tuple, Union

import cv2
import numpy as np
from cv2.data import haarcascades as cv2_haarcascades
from jishaku.functools import executor_function
from PIL import Image, ImageDraw, ImageEnhance, ImageFont, ImageOps, ImageSequence
from skimage import transform

from sleepy.utils import measure_performance, randint

from .fonts import FONTS
from .helpers import get_accurate_text_size, wrap_text
from .templates import TEMPLATES

if TYPE_CHECKING:
    from pathlib import Path

    PILColour = Union[str, int, Tuple[int, ...]]


HAAR_EYES: cv2.CascadeClassifier = cv2.CascadeClassifier(
    f"{cv2_haarcascades}haarcascade_eye.xml"
)


@executor_function
@measure_performance
def do_asciify(image_buffer: io.BytesIO, *, inverted: bool = False) -> str:
    # Chars are ordered from dark -> light.
    chars = " .'-,_\"^*:;~=+<>!?\\/|()][}{#&$%@"

    if inverted:
        chars = chars[::-1]

    with Image.open(image_buffer) as image:
        data = np.asarray(ImageOps.contain(image.convert("L"), (61, 61)))

    return "\n".join("".join(chars[c // 8] for c in r) for r in data[::2])


@executor_function
@measure_performance
def do_blurpify(image_buffer: io.BytesIO, *, use_rebrand: bool = False) -> io.BytesIO:
    with Image.open(image_buffer) as image:
        blurple = (88, 101, 242) if use_rebrand else (114, 137, 218)

        frames = [
            ImageOps.colorize(
                ImageEnhance.Contrast(f.convert("L")).enhance(1000),
                blurple,  # type: ignore
                "white",
            )
            for f in ImageSequence.Iterator(image)
        ]

    buffer = io.BytesIO()

    if len(frames) == 1:
        frames[0].save(buffer, "png")
        buffer.name = "blurplefied.png"
    else:
        frames[0].save(
            buffer, "gif", save_all=True, optimize=True, append_images=frames[1:]
        )
        buffer.name = "blurplefied.gif"

    buffer.seek(0)

    return buffer


@executor_function
@measure_performance
def do_deepfry(image_buffer: io.BytesIO) -> io.BytesIO:
    with Image.open(image_buffer) as image:
        frames = []
        for frame in ImageSequence.Iterator(image):
            frame = frame.convert("RGB")

            red = frame.split()[0]
            red = ImageEnhance.Contrast(red).enhance(2)
            red = ImageEnhance.Brightness(red).enhance(1.5)
            red = ImageOps.colorize(red, (254, 0, 2), (255, 255, 15))  # type: ignore

            frame = Image.blend(frame, red, 0.77)
            frame = ImageEnhance.Sharpness(frame).enhance(150)
            frames.append(frame)

    buffer = io.BytesIO()

    if len(frames) == 1:
        frames[0].save(buffer, "jpeg", quality=1)
        buffer.name = "deepfried.jpeg"
    else:
        frames[0].save(
            buffer, "gif", save_all=True, optimize=True, append_images=frames[1:]
        )
        buffer.name = "deepfried.gif"

    buffer.seek(0)

    return buffer


@executor_function
@measure_performance
def do_invert(image_buffer: io.BytesIO) -> io.BytesIO:
    with Image.open(image_buffer) as image:
        img = ~np.asarray(image.convert("RGB"))

        try:
            alpha = image.getchannel("A")
        except ValueError:
            cv2.cvtColor(img, cv2.COLOR_RGB2BGR, img)
        else:
            img = np.dstack((img, alpha))  # type: ignore
            cv2.cvtColor(img, cv2.COLOR_RGBA2BGRA, img)

    return io.BytesIO(cv2.imencode(".png", img)[1].tobytes())


@executor_function
@measure_performance
def do_jpegify(image_buffer: io.BytesIO, *, quality: int = 1) -> io.BytesIO:
    with Image.open(image_buffer) as image:
        buffer = io.BytesIO()

        image.convert("RGB").save(buffer, "jpeg", quality=quality)

    buffer.seek(0)

    return buffer


@executor_function
@measure_performance
def do_lensflare_eyes(
    image_buffer: io.BytesIO, *, colour: Optional[PILColour] = None
) -> io.BytesIO:
    with Image.open(image_buffer) as image:
        image = image.convert("RGBA")

    eyes = HAAR_EYES.detectMultiScale(
        cv2.cvtColor(np.asarray(image), cv2.COLOR_RGBA2GRAY), 1.3, 5, minSize=(24, 24)
    )

    if len(eyes) == 0:
        raise RuntimeError("No eyes were detected.")

    with Image.open(TEMPLATES / "lensflare.png") as flare:
        if colour is not None:
            flare_c = ImageOps.colorize(flare.convert("L"), colour, "white", colour)  # type: ignore
            flare_c = ImageEnhance.Color(flare_c).enhance(10)
            flare_c.putalpha(flare.getchannel("A"))
            flare = flare_c

        for x, y, w, h in eyes:
            flare_s = ImageOps.contain(flare, (x + w, y + h))

            # For reference, the center of the flare is at (272, 157).
            dest_x = int(x + w / 2 - 272 * (flare_s.width / flare.width))
            dest_y = int(y + h / 2 - 157 * (flare_s.height / flare.height))

            image.alpha_composite(flare_s, (dest_x, dest_y))

    buffer = io.BytesIO()

    image.save(buffer, "png")

    buffer.seek(0)

    return buffer


@executor_function
@measure_performance
def do_swirl(image_buffer: io.BytesIO, *, intensity: float = 1) -> io.BytesIO:
    with Image.open(image_buffer) as image:
        image = transform.swirl(
            np.asarray(image.convert("RGBA")),
            strength=intensity,  # type: ignore -- documented compatible with floats
            radius=image.height / 2,  # type: ignore -- "
            preserve_range=True,
        ).astype(np.uint8)

    cv2.cvtColor(image, cv2.COLOR_RGBA2BGRA, image)

    return io.BytesIO(cv2.imencode(".png", image)[1].tobytes())


@executor_function
@measure_performance
def make_axios_interview_meme(text: str) -> io.BytesIO:
    with Image.open(TEMPLATES / "axios_interview.jpg") as template:
        font = ImageFont.truetype(str(FONTS / "Arimo-Regular.ttf"), 60)

        text = wrap_text(text, font, width=650)
        text_layer = Image.new("LA", get_accurate_text_size(font, text))

        ImageDraw.Draw(text_layer).text((0, 0), text, "black", font, align="center")

        text_layer = text_layer.rotate(-12.5, expand=True)

        # For reference, the desired point to center the
        # text around is (530, 1000).
        template.paste(
            text_layer,
            (530 - text_layer.width // 2, 1000 - text_layer.height // 2),
            text_layer,
        )

        buffer = io.BytesIO()

        template.save(buffer, "png")

    buffer.seek(0)

    return buffer


@executor_function
@measure_performance
def make_captcha(image_buffer: io.BytesIO, text: str) -> io.BytesIO:
    with Image.open(TEMPLATES / "captcha.png") as template:
        with Image.open(image_buffer) as image:
            binder = Image.new("RGB", template.size)
            binder.paste(image.convert("RGB").resize((386, 386)), (5, 127))

        ImageDraw.Draw(template).text(
            (29, 46), text, font=ImageFont.truetype(str(FONTS / "Roboto-Black.ttf"), 28)
        )

        binder.paste(template, None, template)

    buffer = io.BytesIO()

    binder.save(buffer, "png")

    buffer.seek(0)

    return buffer


@executor_function
@measure_performance
def make_change_my_mind_meme(text: str) -> io.BytesIO:
    with Image.open(TEMPLATES / "change_my_mind.png") as template:
        font = ImageFont.truetype(str(FONTS / "Arimo-Regular.ttf"), 50)

        text = wrap_text(text, font, width=620)
        text_layer = Image.new("LA", get_accurate_text_size(font, text))

        ImageDraw.Draw(text_layer).text((0, 0), text, "black", font, align="center")

        text_layer = text_layer.rotate(22.5, expand=True)

        # For reference, the desired point to center the text around is (1250, 980).
        template.paste(
            text_layer,
            (1255 - text_layer.width // 2, 980 - text_layer.height // 2),
            text_layer,
        )

        buffer = io.BytesIO()

        template.save(buffer, "png")

    buffer.seek(0)

    return buffer


@executor_function
@measure_performance
def make_clyde_message(text: str, *, use_rebrand: bool = False) -> io.BytesIO:
    clyde = "rebrand_clyde.png" if use_rebrand else "classic_clyde.png"

    with Image.open(TEMPLATES / clyde) as template:
        font = ImageFont.truetype(str(FONTS / "Catamaran-Regular.ttf"), 16)

        draw = ImageDraw.Draw(template)
        draw.text(
            (209, 4),
            datetime.now(timezone.utc).strftime("%H:%M"),
            (114, 118, 125),
            font.font_variant(size=14),
        )
        draw.text((74, 25), wrap_text(text, font, width=745), (220, 221, 222), font)

        buffer = io.BytesIO()

        template.save(buffer, "png")

    buffer.seek(0)

    return buffer


@executor_function
@measure_performance
def make_dalgona(image_buffer: io.BytesIO) -> io.BytesIO:
    with Image.open(image_buffer) as image:
        size = (245, 205)

        grey = np.asarray(image.convert("L").resize(size))

    med = np.median(grey)
    contours, _ = cv2.findContours(
        cv2.Canny(grey, int(max(0, 0.67 * med)), int(min(255, 1.33 * med))),  # type: ignore
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_NONE,
    )

    # Annoyingly, we'll have to convert the greyscale
    # image to a zeros array twice since the array is
    # modified internally by the following two draw
    # operations for whatever reason.
    edges = cv2.drawContours(np.zeros_like(grey), contours, -1, 255, 2, cv2.LINE_AA)

    # Desired coordinates and axes for the ellipses.
    mid = (size[0] // 2, size[1] // 2)
    axes = (mid[0] - 2, mid[1] - 2)

    mask = cv2.ellipse(np.zeros_like(grey), mid, axes, 0, 0, 360, 255, -1)

    outline = cv2.bitwise_and(edges, edges, mask=mask)

    # Add a border circle. This is my attempt of making
    # the result look somewhat decent since there isn't
    # really anything I can do about stray lines that
    # come up during the canny process.
    cv2.ellipse(outline, mid, axes, 0, 0, 360, 255, 2, cv2.LINE_AA)

    image = Image.new("RGB", size, (145, 129, 76))
    image.putalpha(Image.fromarray(outline))

    with Image.open(TEMPLATES / "dalgona.png") as template:
        template.paste(image, (205, 85), image)

    buffer = io.BytesIO()

    template.save(buffer, "png")

    buffer.seek(0)

    return buffer


@executor_function
@measure_performance
def make_iphone_x(image_buffer: io.BytesIO) -> io.BytesIO:
    with Image.open(TEMPLATES / "iphonex.png") as template:
        with Image.open(image_buffer) as image:
            binder = Image.new("RGBA", template.size)
            binder.paste(image.convert("RGB").resize((242, 524)), (19, 18))

        binder.alpha_composite(template)

    buffer = io.BytesIO()

    binder.save(buffer, "png")

    buffer.seek(0)

    return buffer


@executor_function
@measure_performance
def make_live_tucker_reaction_meme(image_buffer: io.BytesIO) -> io.BytesIO:
    with Image.open(TEMPLATES / "live_tucker_reaction.png") as template:
        with Image.open(image_buffer) as image:
            image.putalpha(255)

            t_size = template.size
            result = ImageOps.contain(image.convert("RGBA"), t_size)

        # If the foreground image has the same dimensions as the
        # template, then there isn't a need for whitespace to be
        # filled and we won't have to generate the blurred form.
        if result.size != t_size:
            blur = cv2.blur(np.asarray(result.resize(t_size)), (25, 25))
            blur = Image.fromarray(blur)

            center = ((t_size[0] - result.width) // 2, (t_size[1] - result.height) // 2)

            blur.alpha_composite(result, center)
            result = blur

        result.alpha_composite(template)

    buffer = io.BytesIO()

    result.save(buffer, "png")

    buffer.seek(0)

    return buffer


@executor_function
@measure_performance
def make_palette(image_buffer: io.BytesIO) -> io.BytesIO:
    with Image.open(image_buffer) as image:
        image = image.convert("RGB")
        thumb = image.copy()

        # This will somewhat ruin our accuracy, but it
        # will also make this process go a lot faster.
        thumb.thumbnail((300, 300))

    _, labels, centroids = cv2.kmeans(
        np.asarray(thumb).astype(np.float32).reshape((-1, 3)),
        5,
        None,
        (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0),
        10,
        cv2.KMEANS_RANDOM_CENTERS,
    )

    # Construct a histogram using the labels to find the
    # approximate percentage of each colour in the image.
    # This will also allow for sorting the colours (given
    # in no particular order) by prominance later on.
    hist, _ = np.histogram(labels, np.arange(len(np.unique(labels)) + 1))
    hist = hist.astype(np.float32)
    hist /= hist.sum()

    # Merge the percentages and colours and sort them.
    data = sorted(zip(hist, centroids), reverse=True, key=lambda x: x[0])

    image = ImageEnhance.Brightness(image).enhance(0.4)
    image = ImageOps.pad(image, (500, 500))

    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(str(FONTS / "Arimo-Bold.ttf"), 30)

    start = 0

    for i, (percent, colour) in enumerate(data):
        colour = tuple(map(int, colour))

        text = "#{0:02x}{1:02x}{2:02x} ({3:.2%})".format(*colour, percent)
        w, h = draw.multiline_textbbox((0, 0), text, font)[2:]

        draw.text(
            (175 + (325 - w) // 2, 100 * i + 50 - h // 2),
            text,
            font=font,
            stroke_fill=colour,
            stroke_width=1,
        )

        end = start + int(percent * 500) + 1

        draw.rectangle((0, start, 175, end), colour)
        draw.line((175, 0, 175, 500), "white", 2)

        start = end

    buffer = io.BytesIO()

    image.save(buffer, "png")

    buffer.seek(0)

    return buffer


@executor_function
@measure_performance
def make_pointing_soyjaks_meme(image_buffer: io.BytesIO) -> io.BytesIO:
    with Image.open(TEMPLATES / "pointing_soyjaks.png") as template:
        with Image.open(image_buffer) as image:
            image = image.convert("RGBA")

        # Replace any transparency with white.
        if image.getextrema()[3][0] < 255:
            image = Image.alpha_composite(Image.new("RGBA", image.size, "white"), image)

        image = ImageOps.pad(image, template.size, color="white")
        image.alpha_composite(template)

    buffer = io.BytesIO()

    image.save(buffer, "png")

    buffer.seek(0)

    return buffer


@executor_function
@measure_performance
def make_pornhub_comment(
    username: str, avatar_buffer: io.BytesIO, comment: str
) -> io.BytesIO:
    with Image.open(TEMPLATES / "pornhub_comment.png") as template:
        with Image.open(avatar_buffer) as avi:
            template.paste(avi.convert("RGB").resize((52, 52)), (24, 264))

        draw = ImageDraw.Draw(template)
        font = ImageFont.truetype(str(FONTS / "Arimo-Regular.ttf"), 25)

        draw.text((89, 275), username, (255, 163, 26), font)
        draw.text((25, 343), wrap_text(comment, font, width=950), font=font)

        buffer = io.BytesIO()

        template.save(buffer, "png")

    buffer.seek(0)

    return buffer


@executor_function
@measure_performance
def make_roblox_cancel_meme(
    avatar_buffer: io.BytesIO, username: str, discriminator: str
) -> io.BytesIO:
    with Image.open(TEMPLATES / "roblox_cancel.jpg") as template:
        with Image.open(avatar_buffer) as avi:
            mask = Image.new("1", (80, 80))
            ImageDraw.Draw(mask).ellipse((0, 0, *mask.size), 255)

            template.paste(avi.convert("RGB").resize(mask.size), (25, 130), mask)

        draw = ImageDraw.Draw(template)

        username_font = ImageFont.truetype(str(FONTS / "Catamaran-ExtraBold.ttf"), 18)
        draw.text((25, 215), username, "white", username_font)
        draw.text(
            (25 + username_font.getlength(username), 219),
            f"#{discriminator}",
            (185, 187, 190),
            ImageFont.truetype(str(FONTS / "Catamaran-Regular.ttf"), 14),
        )

        cancel_font_big = ImageFont.truetype(str(FONTS / "Roboto-Black.ttf"), 32)
        draw.text((155, -2), f"{username}!!", "white", cancel_font_big)

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


@executor_function
@measure_performance
def make_ship(
    name1: str,
    avatar1_buffer: io.BytesIO,
    name2: str,
    avatar2_buffer: io.BytesIO,
    seed: Any = None,
) -> io.BytesIO:
    with Image.open(TEMPLATES / "ship.png") as template:
        mask = Image.new("1", (80, 80))
        ImageDraw.Draw(mask).ellipse((0, 0, *mask.size), 255)

        with Image.open(avatar1_buffer) as first:
            template.paste(first.convert("RGB").resize(mask.size), (100, 45), mask)

        with Image.open(avatar2_buffer) as second:
            template.paste(second.convert("RGB").resize(mask.size), (495, 45), mask)

        draw = ImageDraw.Draw(template)

        # Show users
        font = ImageFont.truetype(str(FONTS / "Arimo-Bold.ttf"), 26)

        name1_wrap = wrap_text(name1, font, width=250)
        name2_wrap = wrap_text(name2, font, width=250)
        name1_w = max(draw.textlength(s, font) for s in name1_wrap.split("\n"))
        name2_w = max(draw.textlength(s, font) for s in name2_wrap.split("\n"))

        draw.text((140 - name1_w // 2, 129), name1_wrap, font=font, align="center")
        draw.text((535 - name2_w // 2, 129), name2_wrap, font=font, align="center")

        # Ship name
        font = font.font_variant(size=22)

        ship_name = name1[: len(name2) // 2] + name2[len(name2) // 2 :]
        ship_name_w = draw.textlength(ship_name, font)

        draw.text(((675 - ship_name_w) // 2, 201), ship_name, font=font, align="center")

        # Confidence meter
        font = font.font_variant(size=16)

        confidence = randint(0, 100, seed=seed)

        if (fill := confidence // 10) != 0:
            draw.rounded_rectangle((140, 234, 140 + 40 * fill, 264), 10, (221, 61, 72))

        draw.rounded_rectangle((140, 234, 535, 264), 10, outline="white", width=2)

        conf_text = f"{confidence}% confidence"
        conf_text_w = draw.textlength(conf_text, font)

        draw.text(((675 - conf_text_w) // 2, 241), conf_text, font=font, align="center")

        buffer = io.BytesIO()

        template.save(buffer, "png")

    buffer.seek(0)

    return buffer


@executor_function
@measure_performance
def make_text_image(
    text: str,
    font_path: Path,
    *,
    size: int,
    text_colour: Optional[PILColour] = None,
    bg_colour: Optional[PILColour] = None,
) -> io.BytesIO:
    font = ImageFont.truetype(str(font_path), size)
    text = wrap_text(text, font, width=650)
    image = Image.new("RGBA", get_accurate_text_size(font, text), bg_colour)  # type: ignore

    ImageDraw.Draw(image).text((0, 0), text, text_colour, font)

    buffer = io.BytesIO()

    image.save(buffer, "png")

    buffer.seek(0)

    return buffer


@executor_function
@measure_performance
def make_threats_meme(image_buffer: io.BytesIO) -> io.BytesIO:
    with Image.open(TEMPLATES / "threats.png") as template:
        with Image.open(image_buffer) as image:
            template.paste(image.convert("RGB").resize((330, 230)), (735, 125))

        buffer = io.BytesIO()

        template.save(buffer, "png")

    buffer.seek(0)

    return buffer


@executor_function
@measure_performance
def make_trapcard(title: str, flavour_text: str, image_buffer: io.BytesIO) -> io.BytesIO:
    with Image.open(TEMPLATES / "trapcard.png") as template:
        with Image.open(image_buffer) as image:
            template.paste(image.convert("RGB").resize((526, 526)), (107, 210))

        font = ImageFont.truetype(str(FONTS / "Lustria-Regular.ttf"), 24)

        draw = ImageDraw.Draw(template)
        draw.text((74, 786), wrap_text(flavour_text, font, width=575), "black", font)

        draw.text(
            (74, 70),
            title.upper(),
            "black",
            ImageFont.truetype(str(FONTS / "SourceSerifPro-SemiBold.ttf"), 50),
        )

        buffer = io.BytesIO()

        template.save(buffer, "png")

    buffer.seek(0)

    return buffer


@executor_function
@measure_performance
def make_tweet(
    handle: str, display_name: str, avatar_buffer: io.BytesIO, text: str
) -> io.BytesIO:
    with Image.open(TEMPLATES / "tweet.png") as template:
        with Image.open(avatar_buffer) as avi:
            mask = Image.new("1", (49, 49))
            ImageDraw.Draw(mask).ellipse((0, 0, *mask.size), 255)

            template.paste(avi.convert("RGB").resize(mask.size), (13, 8), mask)

        draw = ImageDraw.Draw(template)
        draw.text(
            (72, 14),
            display_name,
            (217, 217, 217),
            ImageFont.truetype(str(FONTS / "Arimo-Bold.ttf"), 15),
        )

        text_font = ImageFont.truetype(str(FONTS / "Arimo-Regular.ttf"), 23)
        draw.text(
            (13, 75),
            wrap_text(text, text_font, width=568),
            (217, 217, 217),
            text_font,
            spacing=8,
        )

        small_text_font = text_font.font_variant(size=15)
        draw.text(
            (13, 208),
            f"{datetime.now(timezone.utc):%I:%M %p · %b %d, %Y} \N{MIDDLE DOT} Sleepy",
            (110, 118, 125),
            small_text_font,
        )
        draw.text((72, 33), f"@{handle}", (110, 118, 125), small_text_font)

        buffer = io.BytesIO()

        template.save(buffer, "png")

    buffer.seek(0)

    return buffer


@executor_function
@measure_performance
def make_who_would_win_meme(
    left_image_buffer: io.BytesIO, right_image_buffer: io.BytesIO
) -> io.BytesIO:
    with Image.open(TEMPLATES / "who_would_win.png") as template:
        with Image.open(left_image_buffer) as left_image:
            template.paste(left_image.convert("RGB").resize((1024, 1220)), (85, 380))

        with Image.open(right_image_buffer) as right_image:
            template.paste(right_image.convert("RGB").resize((992, 1220)), (1138, 380))

        buffer = io.BytesIO()

        template.save(buffer, "png")

    buffer.seek(0)

    return buffer


@executor_function
@measure_performance
def make_youtube_comment(
    username: str, avatar_buffer: io.BytesIO, comment: str
) -> io.BytesIO:
    with Image.open(TEMPLATES / "youtube_comment.png") as template:
        with Image.open(avatar_buffer) as avi:
            mask = Image.new("1", (40, 40))
            ImageDraw.Draw(mask).ellipse((0, 0, *mask.size), 255)

            template.paste(avi.convert("RGB").resize(mask.size), (25, 25), mask)

        username_font = ImageFont.truetype(str(FONTS / "Roboto-Medium.ttf"), 15)

        draw = ImageDraw.Draw(template)
        draw.text((83, 25), username, (3, 3, 3), username_font)

        text_font = ImageFont.truetype(str(FONTS / "Roboto-Regular.ttf"), 14)
        draw.text(
            (84, 47), wrap_text(comment, text_font, width=450), (3, 3, 3), text_font
        )
        draw.text(
            # Arbitrary positioning of comment timestamp.
            (username_font.getlength(username) + 94, 25),
            "1 week ago",
            (96, 96, 96),
            text_font,
        )

        buffer = io.BytesIO()

        template.save(buffer, "png")

    buffer.seek(0)

    return buffer
