"""
© Copyright 2018-2020 HitchedSyringe, All Rights Reserved.

Redistributing, using or owning a copy of this software without explicit permissions
is against these licensing terms, your license(s) to this software can be revoked at
any time without explicit notice beforehand and at the time of revocation.
Your license is non-transferrable, the terms of this license only permit you to do the
following; Create pull requests and make modifications to this repository.

"""


import io
import random
import textwrap
import time
from functools import partial
from pathlib import Path
from typing import Optional
from urllib.parse import quote as urlquote

import discord
import numpy as np
from discord import Colour, Embed, File
from discord.ext import commands, flags
from PIL import Image, ImageDraw, ImageEnhance, ImageFont, ImageOps, ImageSequence

from SleepyBot.utils import checks, converters, formatting, reaction_menus


# The chars are ordered from Black -> White.
# The char order is reversed since this is intended for Discord dark mode users.
_ASCII_MAPPING = {
    0: " ",
    1: ".",
    2: ":",
    3: "-",
    4: "=",
    5: "+",
    6: "*",
    7: "#",
    8: "%",
    9: "@",
}


_TTI_FONTS = (
    "arial",
    "comic",
    "dyslexic",
    "georgia",
    "impact",
    "lucida",
    "simsun",
    "tahoma",
    "times",
    "trebuchet",
    "verdana",
)


class Images(commands.Cog,
             command_attrs=dict(cooldown=commands.Cooldown(rate=1, per=5, type=commands.BucketType.member))):
    """Commands having to do with images and/or their manipulation."""

    def __init__(self):
        self.image_materials = Path(__file__).parent.parent / "utils/image_manipulation"
        # Might as well make a few shorthands...
        self.image_templates = self.image_materials / "templates"
        self.image_fonts = self.image_materials / "fonts"


    async def cog_command_error(self, ctx: commands.Context, error):
        if isinstance(error, commands.BadArgument):
            # This is an attempt to make this less confusing for the end-user.
            raw_error = str(error)
            if raw_error == "Not a valid Image attachment or link.":
                await ctx.send(raw_error)
                error.handled = True


    @staticmethod
    async def _format_generic_image(ctx: commands.Context,
                                    *, url: str, provider: str, title=None, colour=None, show_requester: bool = False):
        """Sends the generic image message format.
        For internal use only.
        """
        embed = Embed(title=title, colour=colour)
        embed.set_image(url=url)
        embed.set_footer(
            text=f"Powered by {provider} | Requested by: {ctx.author}" if show_requester else f"Powered by {provider}"
        )
        await ctx.send(embed=embed)


    @staticmethod
    def do_asciify(image_buffer: io.BytesIO) -> str:
        """ASCII-ifies an image.

        Parameters
        ----------
        image_buffer: :class:`io.BytesIO`
            The image bytes.

        Returns
        -------
        :class:`str`
            The ASCII-ified result.
        """
        with Image.open(image_buffer) as image:
            array = np.asarray(image.resize((61, 61)).convert("LA"))

        return "\n".join("".join(_ASCII_MAPPING[round(np.average(c[0]) * 9 / 255)] for c in r) for r in array[::2])


    @staticmethod
    def do_blurpify(image_buffer: io.BytesIO):
        """Blurpifies an image or GIF.

        Parameters
        ----------
        image_buffer: :class:`io.BytesIO`
            The image bytes.

        Returns
        -------
        Tuple[:class:`io.BytesIO`, :class:`int`, :class:`str`]
            The resulting image bytes and buffer size, along with the intended file extension for saving.
        """
        buffer = io.BytesIO()

        with Image.open(image_buffer) as image:
            # Iterating through this on every image probably isn't the best idea,
            # but it's the least messy way I thought of that allowed support for animated images.
            frames = []
            for frame in ImageSequence.Iterator(image):
                frame = frame.convert("L")
                frame = ImageEnhance.Contrast(frame).enhance(1000)
                frame = frame.convert("RGB")

                frame.putdata(tuple(p if p == (255, 255, 255) else (114, 137, 218) for p in frame.getdata()))

                frames.append(frame)

            if getattr(image, "is_animated", False):
                frames[0].save(buffer, "gif", save_all=True, optimize=True, append_images=frames[1:])
                file_extension = "gif"
            else:
                frames[0].save(buffer, "png")
                file_extension = "png"

            # This is only actual semantic way to calculate the length of a BytesIO object.
            buffer_size = buffer.tell()

            buffer.seek(0)

            return buffer, buffer_size, file_extension


    @staticmethod
    def do_deepfry(image_buffer: io.BytesIO):
        """Deep fries an image or GIF.

        Parameters
        ----------
        image_buffer: :class:`io.BytesIO`
            The image bytes.

        Returns
        -------
        Tuple[:class:`io.BytesIO`, :class:`int`, :class:`str`]
            The resulting image bytes and buffer size, along with the intended file extension for saving.
        """
        buffer = io.BytesIO()

        with Image.open(image_buffer) as image:
            # Iterating through this on every image probably isn't the best idea,
            # but it's the least messy way I thought of that allowed support for animated images.
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

            if getattr(image, "is_animated", False):
                frames[0].save(buffer, "gif", save_all=True, optimize=True, append_images=frames[1:])
                file_extension = "gif"
            else:
                frames[0].save(buffer, "jpeg", quality=1)
                file_extension = "jpg"

            # This is only actual semantic way to calculate the length of a BytesIO object.
            buffer_size = buffer.tell()

            buffer.seek(0)

            return buffer, buffer_size, file_extension


    @staticmethod
    def do_jpegify(image_buffer: io.BytesIO, *, quality: int = 1) -> io.BytesIO:
        """JPEGifies an image.
        For internal use only.

        Parameters
        ----------
        image_buffer: :class:`io.BytesIO`
            The image bytes.
        quality: :class:`int`
            The quality the image output should be, on a scale of 1 to 10.
            The higher the quality, the less intense the JPEG.
            Defaults to ``1``.

        Returns
        -------
        :class:`io.BytesIO`
            The image after being JPEG converted.
        """
        buffer = io.BytesIO()

        with Image.open(image_buffer) as image:
            image.convert("RGB").save(buffer, "jpeg", quality=quality)

        buffer.seek(0)
        return buffer


    @staticmethod
    def wrap_text(text: str, font, *, width: int) -> str:
        """Wraps some text via pixel measurement.
        The text wrapping is approximated by calculating the average pixel
        count per character in the string.

        Parameters
        ----------
        text: :class:`str`
            The text to wrap.
        font: :class:`PIL.ImageFont.FreeTypeFont`
            The font the text is currently using.
        width: :class:`int`
            The maximum width, in pixels, before the text needs to be wrapped.

        Returns
        -------
        :class:`str`
            The newly wrapped text.
        """
        font_width, _ = font.getsize(text)
        pixels_per_char = max(font_width / len(text), 1)

        return textwrap.fill(text, width=int(width / pixels_per_char), replace_whitespace=False)


    def make_captcha(self, image_buffer: io.BytesIO, text: str) -> io.BytesIO:
        """Makes a fake Google image captcha.
        For internal use only.

        Parameters
        ----------
        image_buffer: :class:`io.BytesIO`
            The image bytes.
        text: :class:`str`
            The text for the meme.

        Returns
        -------
        :class:`io.BytesIO`
            The image result buffer.
        """
        buffer = io.BytesIO()
        font = ImageFont.truetype(str(self.image_fonts / "Roboto-Black.ttf"), size=28)

        with Image.open(self.image_templates / "captcha.png") as template:
            ImageDraw.Draw(template).text((28, 46), text, font=font)

            with Image.new("RGBA", template.size, 255) as binder:
                with Image.open(image_buffer) as image:
                    binder.paste(image.resize((386, 386)), (5, 127))

                binder.alpha_composite(template)

                binder.save(buffer, "png")

        buffer.seek(0)
        return buffer


    def make_change_my_mind_meme(self, text: str) -> io.BytesIO:
        """Makes a "change my mind" meme.
        For internal use only.

        Parameters
        ----------
        text: :class:`str`
            The text for the meme.

        Returns
        -------
        :class:`io.BytesIO`
            The image result buffer.
        """
        buffer = io.BytesIO()
        font = ImageFont.truetype(str(self.image_fonts / "Arimo-Regular.ttf"), size=50)

        with Image.open(self.image_templates / "change_my_mind.png") as template:

            with Image.new("RGBA", template.size, 255) as text_layer:
                ImageDraw.Draw(text_layer).text((755, 505), self.wrap_text(text, font, width=670), (0, 0, 0), font)
                text_layer = text_layer.rotate(22, expand=True)

                template.alpha_composite(text_layer)

            template.save(buffer, "png")

        buffer.seek(0)
        return buffer


    def make_clyde_message(self, text: str) -> io.BytesIO:
        """Makes a fake clyde message.
        For internal use only.

        Parameters
        ----------
        text: :class:`str`
            The text for the fake message.

        Returns
        -------
        :class:`io.BytesIO`
            The image result buffer.
        """
        buffer = io.BytesIO()
        font = ImageFont.truetype(str(self.image_fonts / "Catamaran-Regular.ttf"), size=16)

        with Image.open(self.image_templates / "clyde.png") as template:
            ImageDraw.Draw(template).text((74, 25), self.wrap_text(text, font, width=745), (220, 221, 222), font)
            template.save(buffer, "png")

        buffer.seek(0)
        return buffer


    def make_iphonex(self, image_buffer: io.BytesIO) -> io.BytesIO:
        """Fits an image into an iPhone X.
        For internal use only.

        Parameters
        ----------
        image_buffer: :class:`io.BytesIO`
            The image bytes.

        Returns
        -------
        :class:`io.BytesIO`
            The image result buffer.
        """
        buffer = io.BytesIO()

        with Image.open(self.image_templates / "iphonex_border.png") as border:

            # This is probably the easiest way to do it without using complex math and whatnot.
            with Image.open(self.image_templates / "iphonex_screen.png") as screen:
                with Image.open(image_buffer) as image:
                    border.paste(image.resize(screen.size), screen)

            border.save(buffer, "png")

        buffer.seek(0)
        return buffer


    def make_pornhub_comment(self, username: str, avatar: io.BytesIO, comment: str) -> io.BytesIO:
        """Makes a fake Pornhub comment.
        For internal use only.

        Parameters
        ----------
        username: :class:`str`
            The username of the account commenting.
        avatar: :class:`io.BytesIO`
            The avatar of the account commenting.
        comment: :class:`str`
            The text content for the Pornhub comment.

        Returns
        -------
        :class:`io.BytesIO`
            The image result buffer.
        """
        buffer = io.BytesIO()
        font = ImageFont.truetype(str(self.image_fonts / "Arimo-Regular.ttf"), size=25)

        with Image.open(self.image_templates / "pornhub_comment.png") as template:
            with Image.open(avatar) as avi:
                template.paste(avi.resize((52, 52)), (24, 264))

            draw = ImageDraw.Draw(template)
            draw.text((89, 275), username, (255, 163, 26), font)
            draw.text((25, 343), self.wrap_text(comment, font, width=950), font=font)

            template.save(buffer, "png")

        buffer.seek(0)
        return buffer


    def make_ship(self, first_avatar: io.BytesIO, second_avatar: io.BytesIO) -> io.BytesIO:
        """Makes a ship image. (It's just the distracted boyfriend meme)
        For internal use only.

        Parameters
        ----------
        first_avatar: :class:`io.BytesIO`
            The first avatar to use in the "ship" image.
        second_avatar: :class:`io.BytesIO`
            The second avatar to use in the "ship" image.

        Returns
        -------
        :class:`io.BytesIO`
            The image result buffer.
        """
        buffer = io.BytesIO()

        with Image.open(self.image_templates / "ship.png") as template:
            with Image.new("L", (160, 160), 0) as mask:
                ImageDraw.Draw(mask).ellipse((0, 0, 160, 160), 255)

                with Image.open(first_avatar) as first, Image.open(second_avatar) as second:
                    template.paste(first.resize(mask.size), (185, 98), mask)
                    template.paste(second.resize(mask.size), (420, 55), mask)

            template.save(buffer, "png")

        buffer.seek(0)
        return buffer


    def make_threats_meme(self, image_buffer: io.BytesIO) -> io.BytesIO:
        """Makes a "three threats to society" meme.
        For internal use only.

        Parameters
        ----------
        image_buffer: :class:`io.BytesIO`
            The image bytes.

        Returns
        -------
        :class:`io.BytesIO`
            The image result buffer.
        """
        buffer = io.BytesIO()

        with Image.open(self.image_templates / "threats.png") as template:
            with Image.open(image_buffer) as image:
                template.paste(image.resize((330, 230)), (735, 125, 1065, 355))

            template.save(buffer, "png")

        buffer.seek(0)
        return buffer


    def make_trapcard(self, title: str, flavour_text: str, image_buffer: io.BytesIO) -> io.BytesIO:
        """Makes a fake Yu-Gi-Oh! trap card.
        For internal use only.

        Parameters
        ----------
        title: :class:`str`
            The trap card's title.
        flavour_text: :class:`str`
            The trap card's flavour text.
        image_buffer: :class:`io.BytesIO`
            The image bytes.

        Returns
        -------
        :class:`io.BytesIO`
            The image result buffer.
        """
        buffer = io.BytesIO()
        font = ImageFont.truetype(str(self.image_fonts / "Lustria-Regular.ttf"), size=24)
        # Unfortunately, we won't have the small caps thing that the real cards have
        # due to the limitations of this font.
        # Although, then again, it's better that I'm not falling into a well-lit legal pitfall.
        title_font = ImageFont.truetype(str(self.image_fonts / "SourceSerifPro-SemiBold.ttf"), size=50)

        with Image.open(self.image_templates / "trapcard.png") as template:
            draw = ImageDraw.Draw(template)
            draw.text((74, 786), self.wrap_text(flavour_text, font, width=575), (0, 0, 0), font)
            draw.text((74, 70), title.upper(), (0, 0, 0), title_font)

            with Image.open(image_buffer) as image:
                template.paste(image.resize((526, 526)), (107, 210))

            template.save(buffer, "png")

        buffer.seek(0)
        return buffer


    def make_who_would_win_meme(self, left_image: io.BytesIO, right_image: io.BytesIO) -> io.BytesIO:
        """Makes a "who would win" meme.
        For internal use only.

        Parameters
        ----------
        left_image: :class:`io.BytesIO`
            The image on the left side of the meme.
        right_image: :class:`io.BytesIO`
            The image on the right side of the meme.

        Returns
        -------
        :class:`io.BytesIO`
            The image result buffer.
        """
        buffer = io.BytesIO()

        with Image.open(self.image_templates / "who_would_win.png") as template:
            with Image.open(left_image) as left, Image.open(right_image) as right:
                template.paste(left.resize((1024, 1220)), (85, 380, 1109, 1600))
                template.paste(right.resize((992, 1220)), (1138, 380, 2130, 1600))

            template.save(buffer, "png")

        buffer.seek(0)
        return buffer


    def make_youtube_comment(self, username: str, avatar: io.BytesIO, comment: str) -> io.BytesIO:
        """Makes a fake YouTube comment.
        For internal use only.

        Parameters
        ----------
        username: :class:`str`
            The username of the account commenting.
        avatar: :class:`io.BytesIO`
            The avatar of the account commenting.
        comment: :class:`str`
            The text content for the YouTube comment.

        Returns
        -------
        :class:`io.BytesIO`
            The image result buffer.
        """
        buffer = io.BytesIO()
        font = ImageFont.truetype(str(self.image_fonts / "Roboto-Regular.ttf"), size=14)
        username_font = ImageFont.truetype(str(self.image_fonts / "Roboto-Medium.ttf"), size=15)

        with Image.open(self.image_templates / "youtube_comment.png") as template:
            with Image.new("L", (40, 40), 0) as mask:
                ImageDraw.Draw(mask).ellipse((0, 0, 40, 40), 255)

                with Image.open(avatar) as avi:
                    template.paste(avi.resize(mask.size), (25, 25), mask)

            draw = ImageDraw.Draw(template)
            draw.text((83, 25), username, (3, 3, 3), username_font)
            draw.text((84, 47), self.wrap_text(comment, font, width=450), (3, 3, 3), font)

            # Arbitrary positioning of comment timestamp.
            width, _ = username_font.getsize(username)
            draw.text((width + 94, 25), "1 week ago", (96, 96, 96), font)

            template.save(buffer, "png")

        buffer.seek(0)
        return buffer


    @commands.command(aliases=["asskeyify"])
    @commands.cooldown(rate=1, per=10, type=commands.BucketType.member)
    async def asciify(self, ctx: commands.Context, image: converters.ImageAssetConverter):
        """Converts an image into ASCII art.
        Image can either be a link or attachment.
        """
        image_buffer = io.BytesIO()
        start = time.perf_counter()

        async with ctx.typing():
            await image.save(image_buffer)

            if image_buffer.__sizeof__() > 40_000_000:
                await ctx.send("Image is too big to convert.")
                return

            art = await ctx.bot.loop.run_in_executor(None, self.do_asciify, image_buffer)

        await ctx.send(f"Took {(time.perf_counter() - start) * 1000:.2f} ms\nRequested by: {ctx.author}\n```\n{art}\n```")


    # No, this wasn't made because of Project Blurple.
    @commands.command(aliases=["blurpify", "bpify", "discordify"])
    @checks.bot_has_permissions(embed_links=True, attach_files=True)
    @commands.cooldown(rate=1, per=15, type=commands.BucketType.member)
    async def blurplefy(self, ctx: commands.Context, image: converters.ImageAssetConverter):
        """Blurplefies an image.
        Image can either be a link or attachment.
        (Bot Needs: Embed Links and Attach Files)
        """
        image_buffer = io.BytesIO()
        start = time.perf_counter()

        async with ctx.typing():
            await image.save(image_buffer)

            if image_buffer.__sizeof__() > 40_000_000:
                await ctx.send("Image is too big to convert.")
                return

            buffer, buffer_size, extension = await ctx.bot.loop.run_in_executor(None, self.do_blurpify, image_buffer)

        filesize_limit = ctx.guild.filesize_limit if ctx.guild is not None else 8_388_608

        if buffer_size > filesize_limit:
            await ctx.send("Image is too big to upload.")
            return

        embed = Embed(colour=Colour.blurple())
        embed.set_image(url=f"attachment://blurpified.{extension}")
        embed.set_footer(text=f"Took {(time.perf_counter() - start) * 1000:.2f} ms | Requested by: {ctx.author}")

        await ctx.send(embed=embed, file=File(fp=buffer, filename=f"blurpified.{extension}"))


    @commands.command(aliases=["meow"])
    @checks.bot_has_permissions(embed_links=True, add_reactions=True, read_message_history=True)
    async def cats(self, ctx: commands.Context):
        """Gets a random series of images of cats.
        (Bot Needs: Embed Links, Add Reactions and Read Message History)
        """
        await ctx.trigger_typing()
        cats = await ctx.get("https://api.thecatapi.com/v1/images/search", limit=50)

        base_embed = Embed(title="\N{CAT FACE} Cats", colour=0x2F3136)
        base_embed.set_footer(text="Powered by api.thecatapi.com")

        embeds = tuple(base_embed.copy().set_image(url=cat["url"]) for cat in cats)
        await ctx.paginate(reaction_menus.EmbedSource(embeds))


    @commands.command()
    @checks.bot_has_permissions(embed_links=True, attach_files=True)
    @commands.cooldown(rate=1, per=10, type=commands.BucketType.member)
    async def captcha(self, ctx: commands.Context, image: converters.ImageAssetConverter,
                      *, text: commands.clean_content(fix_channel_mentions=True)):
        """Generates a fake Google image captcha.
        (Bot Needs: Embed Links and Attach Files)
        """
        image_buffer = io.BytesIO()
        start = time.perf_counter()

        async with ctx.typing():
            await image.save(image_buffer)

            if image_buffer.__sizeof__() > 40_000_000:
                await ctx.send("Image is too big to convert.")
                return

            buffer = await ctx.bot.loop.run_in_executor(None, self.make_captcha, image_buffer, text)

        embed = Embed(colour=0x2F3136)
        embed.set_image(url="attachment://captcha.png")
        embed.set_footer(text=f"Took {(time.perf_counter() - start) * 1000:.2f} ms | Requested by: {ctx.author}")

        await ctx.send(embed=embed, file=File(fp=buffer, filename="captcha.png"))


    @commands.command(aliases=["cmm"])
    @checks.bot_has_permissions(embed_links=True, attach_files=True)
    @commands.cooldown(rate=1, per=10, type=commands.BucketType.member)
    async def changemymind(self, ctx: commands.Context,
                           *, text: commands.clean_content(fix_channel_mentions=True)):
        """Generates a "change my mind" meme.
        (Bot Needs: Embed Links and Attach Files)
        """
        start = time.perf_counter()

        async with ctx.typing():
            buffer = await ctx.bot.loop.run_in_executor(None, self.make_change_my_mind_meme, text)

        embed = Embed(colour=0x2F3136)
        embed.set_image(url="attachment://changemymind.png")
        embed.set_footer(text=f"Took {(time.perf_counter() - start) * 1000:.2f} ms | Requested by: {ctx.author}")

        await ctx.send(embed=embed, file=File(fp=buffer, filename="changemymind.png"))


    @commands.command()
    @checks.bot_has_permissions(embed_links=True, attach_files=True)
    @commands.cooldown(rate=1, per=10, type=commands.BucketType.member)
    async def clyde(self, ctx: commands.Context,
                    *, text: commands.clean_content(fix_channel_mentions=True)):
        """Generates a fake Clyde bot message.
        (Bot Needs: Embed Links and Attach Files)
        """
        start = time.perf_counter()

        async with ctx.typing():
            buffer = await ctx.bot.loop.run_in_executor(None, self.make_clyde_message, text)

        embed = Embed(colour=Colour.blurple())
        embed.set_image(url="attachment://clyde.png")
        embed.set_footer(text=f"Took {(time.perf_counter() - start) * 1000:.2f} ms | Requested by: {ctx.author}")

        await ctx.send(embed=embed, file=File(fp=buffer, filename="clyde.png"))


    @commands.command(aliases=["df"])
    @checks.bot_has_permissions(embed_links=True, attach_files=True)
    @commands.cooldown(rate=1, per=15, type=commands.BucketType.member)
    async def deepfry(self, ctx: commands.Context, image: converters.ImageAssetConverter):
        """Deepfries an image.
        Image can either be a link or attachment.
        (Bot Needs: Embed Links and Attach Files)
        """
        image_buffer = io.BytesIO()
        start = time.perf_counter()

        async with ctx.typing():
            await image.save(image_buffer)

            if image_buffer.__sizeof__() > 40_000_000:
                await ctx.send("Image is too big to convert.")
                return

            buffer, buffer_size, extension = await ctx.bot.loop.run_in_executor(None, self.do_deepfry, image_buffer)

        filesize_limit = ctx.guild.filesize_limit if ctx.guild is not None else 8_388_608

        if buffer_size > filesize_limit:
            await ctx.send("Image is too big to upload.")
            return

        embed = Embed(colour=0x2F3136)
        embed.set_image(url=f"attachment://deepfried.{extension}")
        embed.set_footer(text=f"Took {(time.perf_counter() - start) * 1000:.2f} ms | Requested by: {ctx.author}")

        await ctx.send(embed=embed, file=File(fp=buffer, filename=f"deepfried.{extension}"))


    @commands.command(aliases=["doggos", "woof"])
    @checks.bot_has_permissions(embed_links=True, add_reactions=True, read_message_history=True)
    async def dogs(self, ctx: commands.Context):
        """Gets a random series of images of dogs.
        (Bot Needs: Embed Links, Add Reactions and Read Message History)
        """
        await ctx.trigger_typing()
        dogs = await ctx.get("https://dog.ceo/api/breeds/image/random/50")

        base_embed = Embed(title="\N{DOG FACE} Dogs", colour=0x2F3136)
        base_embed.set_footer(text="Powered by dog.ceo")

        embeds = tuple(base_embed.copy().set_image(url=dog) for dog in dogs["message"])
        await ctx.paginate(reaction_menus.EmbedSource(embeds))


    @commands.command(aliases=["quack"])
    @checks.bot_has_permissions(embed_links=True)
    @commands.cooldown(rate=2, per=5, type=commands.BucketType.member)
    async def duck(self, ctx: commands.Context):
        """Gets a random image of a duck.
        (Bot Needs: Embed Links)
        """
        await ctx.trigger_typing()
        duck = await ctx.get("https://random-d.uk/api/random")
        url = duck["url"]

        await self._format_generic_image(
            ctx, url=url, provider=duck["message"], title="Random \N{DUCK}", colour=0x2F3136
        )


    @commands.command(aliases=["floof"])
    @checks.bot_has_permissions(embed_links=True)
    @commands.cooldown(rate=2, per=5, type=commands.BucketType.member)
    async def fox(self, ctx: commands.Context):
        """Gets a random image of a fox.
        (Bot Needs: Embed Links)
        """
        await ctx.trigger_typing()
        fox = await ctx.get("https://randomfox.ca/floof/")

        await self._format_generic_image(
            ctx, url=fox["image"], provider="randomfox.ca", title="Random \N{FOX FACE}", colour=0x2F3136
        )


    @commands.command(aliases=["ipx"])
    @checks.bot_has_permissions(embed_links=True, attach_files=True)
    @commands.cooldown(rate=1, per=10, type=commands.BucketType.member)
    async def iphonex(self, ctx: commands.Context, image: converters.ImageAssetConverter):
        """Fits an image into an iPhone X screen.
        Image can either be a link or attachment.
        (Bot Needs: Embed Links and Attach Files)
        """
        image_buffer = io.BytesIO()
        start = time.perf_counter()

        async with ctx.typing():
            await image.save(image_buffer)

            if image_buffer.__sizeof__() > 40_000_000:
                await ctx.send("Image is too big to convert.")
                return

            buffer = await ctx.bot.loop.run_in_executor(None, self.make_iphonex, image_buffer)

        embed = Embed(colour=0x2F3136)
        embed.set_image(url="attachment://iphonex.png")
        embed.set_footer(text=f"Took {(time.perf_counter() - start) * 1000:.2f} ms | Requested by: {ctx.author}")

        await ctx.send(embed=embed, file=File(fp=buffer, filename="iphonex.png"))


    @commands.command(aliases=["needsmorejpeg", "jpegify"])
    @checks.bot_has_permissions(embed_links=True, attach_files=True)
    @commands.cooldown(rate=1, per=10, type=commands.BucketType.member)
    async def jpeg(self, ctx: commands.Context, quality: Optional[int], image: converters.ImageAssetConverter):
        """JPEGifies an image down to an optional quality.
        Quality value must be between 0 and 10.
        The lower the quality, the more JPEG the image result becomes.
        Image can either be a link or attachment.
        (Bot Needs: Embed Links and Attach Files)
        """
        if quality is None:
            quality = 5

        if quality > 10 or quality <= 0:
            await ctx.send("Quality must be greater than 0 and less than 10.")
            return

        image_buffer = io.BytesIO()
        start = time.perf_counter()

        async with ctx.typing():
            await image.save(image_buffer)

            if image_buffer.__sizeof__() > 40_000_000:
                await ctx.send("Image is too big to convert.")
                return

            buffer = await ctx.bot.loop.run_in_executor(None, partial(self.do_jpegify, image_buffer, quality=quality))

        embed = Embed(colour=0x2F3136)
        embed.set_image(url="attachment://jpegified.jpg")
        embed.set_footer(text=f"Took {(time.perf_counter() - start) * 1000:.2f} ms | Requested by: {ctx.author}")

        await ctx.send(embed=embed, file=File(fp=buffer, filename="jpegified.jpg"))


    @commands.command()
    @checks.bot_has_permissions(embed_links=True)
    @commands.cooldown(rate=1, per=10, type=commands.BucketType.member)
    async def magik(self, ctx: commands.Context, intensity: Optional[int], image: converters.ImageAssetConverter):
        """Heavily warps and distorts an image to an optional intensity.
        Image can either be a link or attachment.
        (Bot Needs: Embed Links)
        """
        if intensity is None:
            intensity = 1

        if intensity <= 0:
            await ctx.send("Intensity must be greater than 0.")
            return

        async with ctx.typing():
            response = await ctx.get(
                "https://nekobot.xyz/api/imagegen",
                type="magik",
                image=str(image),
                intensity=intensity
            )

        await self._format_generic_image(
            ctx, url=response["message"], provider="nekobot.xyz", colour=0x2F3136, show_requester=True
        )


    @commands.command(aliases=["phcomment", "phc"])
    @commands.guild_only()
    @checks.bot_has_permissions(embed_links=True, attach_files=True)
    @commands.cooldown(rate=1, per=10, type=commands.BucketType.member)
    async def pornhubcomment(self, ctx: commands.Context, user: Optional[discord.Member],
                             *, text: commands.clean_content(fix_channel_mentions=True)):
        """Generates a Pr0nhub comment.
        (Bot Needs: Embed Links and Attach Files)
        """
        if user is None:
            user = ctx.author

        avatar_buffer = io.BytesIO()
        start = time.perf_counter()

        async with ctx.typing():
            await user.avatar_url_as(format="png").save(avatar_buffer)

            buffer = await ctx.bot.loop.run_in_executor(
                None, self.make_pornhub_comment, user.display_name, avatar_buffer, text
            )

        embed = Embed(colour=0x2F3136)
        embed.set_image(url="attachment://pornhubcomment.png")
        embed.set_footer(text=f"Took {(time.perf_counter() - start) * 1000:.2f} ms | Requested by: {ctx.author}")

        await ctx.send(embed=embed, file=File(fp=buffer, filename="pornhubcomment.png"))


    @commands.command()
    @commands.guild_only()
    @checks.bot_has_permissions(embed_links=True, attach_files=True)
    @commands.cooldown(rate=1, per=10, type=commands.BucketType.member)
    async def ship(self, ctx: commands.Context, first_user: discord.Member, second_user: discord.Member = None):
        """Ships two users.
        If no second user is specified, then the second user will default to you.
        (Bot Needs: Embed Links and Attach Files)

        EXAMPLE:
        (Ex. 1) ship HitchedSyringe#0598
        (Ex. 2) ship HitchedSyringe#0598 someotherperson#0194
        """
        if second_user is None:
            second_user = ctx.author

        if first_user == second_user:
            await ctx.send("You cannot ship the same user.")
            return

        first_avatar_buffer = io.BytesIO()
        second_avatar_buffer = io.BytesIO()
        start = time.perf_counter()

        async with ctx.typing():
            await first_user.avatar_url_as(format="png").save(first_avatar_buffer)
            await second_user.avatar_url_as(format="png").save(second_avatar_buffer)

            buffer = await ctx.bot.loop.run_in_executor(None, self.make_ship, first_avatar_buffer, second_avatar_buffer)

        first_name = first_user.name
        second_name = second_user.name
        score = random.randint(0, 100)

        embed = Embed(title=f"{first_name} \N{HEAVY BLACK HEART} {second_name}", colour=0x2F3136)
        embed.set_author(name=first_name[:len(first_name) // 2] + second_name[len(second_name) // 2:])
        embed.set_image(url="attachment://ship.png")
        embed.set_footer(text=f"Took {(time.perf_counter() - start) * 1000:.2f} ms | Requested by: {ctx.author}")
        embed.add_field(
            name='Confidence',
            value=f"**{score}%** | 0 {formatting.progress_bar(100, 10, score)} 100",
        )


        await ctx.send(embed=embed, file=File(buffer, filename="ship.png"))


    @flags.add_flag("--font", type=str.lower, default="arial", choices=_TTI_FONTS)
    @flags.add_flag("--textcolour", "--textcolor", dest="fcolor", type=Colour, default="FFFFFF")
    @flags.add_flag("--bgcolour", "--bgcolor", dest="bcolor", type=Colour)
    @flags.add_flag("--size", type=int, default=35)
    @flags.command(aliases=["tti"])
    @checks.bot_has_permissions(embed_links=True)
    async def texttoimage(self, ctx: commands.Context,
                          text: commands.clean_content(fix_channel_mentions=True), **flags):
        """Converts text into an image.

        This uses a powerful "command-line" interface.
        The first argument is the text to convert.
        All following arguments are the option flags.
        Quotation marks must be used if a value has spaces.
        **All options are optional.**

        __The following options are valid:__

        `--font`: The text font to use.
        `--textcolour` or `--textcolor`: The colour of the text. Hexidecimal values are accepted.
        `--bgcolour` or `--bgcolor`: The colour of the background. Hexidecimal values are accepted. Omit for transparent.
        `--size`: The size of the text. (Default: 35; Min: 5; Max: 35)

        (Bot Needs: Embed Links)
        """
        size = flags["size"]
        if size > 35 or size < 5:
            await ctx.send("Text size must be greater than 5 and less than 35.")
            return

        flags["fcolor"] = str(flags["fcolor"])

        background_colour = flags["bcolor"]
        if background_colour is not None:
            flags["bcolor"] = str(background_colour)
        else:
            # Text can have transparent background, also this will cause an error if we don't remove it.
            del flags["bcolor"]

        await ctx.trigger_typing()
        url = await ctx.get("http://api.img4me.com/?type=png", text=text, cache=True, **flags)

        await self._format_generic_image(
            ctx, url=url, provider="api.img4me.com", colour=0x2F3136, show_requester=True
        )


    @texttoimage.error
    async def on_texttoimage_error(self, ctx: commands.Context, error):
        error = getattr(error, "original", error)

        if isinstance(error, flags.ArgumentParsingError):
            await ctx.send(f"Argument parsing error: {error}")
            error.handled = True


    @commands.command()
    @checks.bot_has_permissions(embed_links=True, attach_files=True)
    @commands.cooldown(rate=1, per=10, type=commands.BucketType.member)
    async def threats(self, ctx: commands.Context, image: converters.ImageAssetConverter):
        """Generates a "three threats to society" meme.
        Image can either be a link or attachment.
        (Bot Needs: Embed Links and Attach Files)
        """
        image_buffer = io.BytesIO()
        start = time.perf_counter()

        async with ctx.typing():
            await image.save(image_buffer)

            if image_buffer.__sizeof__() > 40_000_000:
                await ctx.send("Image is too big to convert.")
                return

            buffer = await ctx.bot.loop.run_in_executor(None, self.make_threats_meme, image_buffer)

        embed = Embed(colour=0x2F3136)
        embed.set_image(url="attachment://threats.png")
        embed.set_footer(text=f"Took {(time.perf_counter() - start) * 1000:.2f} ms | Requested by: {ctx.author}")

        await ctx.send(embed=embed, file=File(fp=buffer, filename="threats.png"))


    @commands.command()
    @checks.bot_has_permissions(embed_links=True, attach_files=True)
    @commands.cooldown(rate=1, per=10, type=commands.BucketType.member)
    async def trapcard(self, ctx: commands.Context,
                       title: commands.clean_content(fix_channel_mentions=True),
                       image: converters.ImageAssetConverter,
                       *, flavour_text: commands.clean_content(fix_channel_mentions=True)):
        """Generates a fake Yu-Gi-Oh! trap card.
        Image can either be a link or attachment.
        (Bot Needs: Embed Links and Attach Files)
        """
        image_buffer = io.BytesIO()
        start = time.perf_counter()

        async with ctx.typing():
            await image.save(image_buffer)

            if image_buffer.__sizeof__() > 40_000_000:
                await ctx.send("Image is too big to convert.")
                return

            buffer = await ctx.bot.loop.run_in_executor(None, self.make_trapcard, title, flavour_text, image_buffer)

        embed = Embed(colour=0x2F3136)
        embed.set_image(url="attachment://trapcard.png")
        embed.set_footer(text=f"Took {(time.perf_counter() - start) * 1000:.2f} ms | Requested by: {ctx.author}")

        await ctx.send(embed=embed, file=File(fp=buffer, filename="trapcard.png"))


    @commands.command()
    @checks.bot_has_permissions(embed_links=True)
    async def tweet(self, ctx: commands.Context, username: str,
                    *, text: commands.clean_content(fix_channel_mentions=True)):
        """Generates a tweet.
        Username is the Twitter handle without the "@".
        (Bot Needs: Embed Links)
        """
        async with ctx.typing():
            response = await ctx.get(
                "https://nekobot.xyz/api/imagegen",
                type="tweet",
                username=username,
                text=text,
                cache=True
            )

        await self._format_generic_image(
            ctx, url=response["message"], provider="nekobot.xyz", colour=0x1DA1F2, show_requester=True
        )


    @commands.command(aliases=["www"])
    @commands.guild_only()
    @checks.bot_has_permissions(embed_links=True, attach_files=True)
    @commands.cooldown(rate=1, per=10, type=commands.BucketType.member)
    async def whowouldwin(self, ctx: commands.Context, first_user: discord.Member, second_user: discord.Member = None):
        """Generates a "who would win" meme.
        If no second user is specified, then the second user will default to you.
        (Bot Needs: Embed Links and Attach Files)

        EXAMPLE:
        (Ex. 1) whowouldwin HitchedSyringe#0598
        (Ex. 2) whowouldwin HitchedSyringe#0598 someotherperson#0194
        """
        if second_user is None:
            second_user = ctx.author

        if first_user == second_user:
            await ctx.send("You cannot compare the same user.")
            return

        first_avatar_buffer = io.BytesIO()
        second_avatar_buffer = io.BytesIO()
        start = time.perf_counter()

        async with ctx.typing():
            await first_user.avatar_url_as(format="png").save(first_avatar_buffer)
            await second_user.avatar_url_as(format="png").save(second_avatar_buffer)

            buffer = await ctx.bot.loop.run_in_executor(
                None, self.make_who_would_win_meme, first_avatar_buffer, second_avatar_buffer
            )

        embed = Embed(colour=0x2F3136)
        embed.set_image(url="attachment://who_would_win.png")
        embed.set_footer(text=f"Took {(time.perf_counter() - start) * 1000:.2f} ms | Requested by: {ctx.author}")

        await ctx.send(embed=embed, file=File(fp=buffer, filename="who_would_win.png"))


    @commands.command(aliases=["ytcomment", "ytc"])
    @commands.guild_only()
    @checks.bot_has_permissions(embed_links=True, attach_files=True)
    @commands.cooldown(rate=1, per=10, type=commands.BucketType.member)
    async def youtubecomment(self, ctx: commands.Context,
                             user: Optional[discord.Member], *, text: commands.clean_content(fix_channel_mentions=True)):
        """Generates a fake YouTube comment.
        (Bot Needs: Embed Links and Attach Files)
        """
        if user is None:
            user = ctx.author

        avatar_buffer = io.BytesIO()
        start = time.perf_counter()

        async with ctx.typing():
            await user.avatar_url_as(format="png").save(avatar_buffer)

            buffer = await ctx.bot.loop.run_in_executor(
                None, self.make_youtube_comment, user.display_name, avatar_buffer, text
            )

        embed = Embed(colour=0xFF0000)
        embed.set_image(url="attachment://youtubecomment.png")
        embed.set_footer(text=f"Took {(time.perf_counter() - start) * 1000:.2f} ms | Requested by: {ctx.author}")

        await ctx.send(embed=embed, file=File(fp=buffer, filename="youtubecomment.png"))


def setup(bot):
    bot.add_cog(Images())
