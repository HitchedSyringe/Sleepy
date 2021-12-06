"""
Copyright (c) 2018-present HitchedSyringe

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""


__all__ = (
    "Images",
    "RGBColourConverter",
)


import io
from typing import Optional

import discord
from discord import Embed, File
from discord.ext import commands, flags
from PIL import UnidentifiedImageError
from PIL.Image import DecompressionBombError
from sleepy import checks
from sleepy.converters import (
    _pseudo_bool_flag,
    ImageAssetConverter,
    ImageAssetConversionFailure,
    ImageAssetTooLarge,
)
from sleepy.http import HTTPRequestFailed
from sleepy.menus import EmbedSource
from sleepy.utils import progress_bar, randint as s_randint

from . import backend
from .fonts import FONTS


# This serves a shortcut to have the input colours
# converted to 3 item tuple RGB values without having
# to manually do the conversions within commands.
class RGBColourConverter(commands.ColourConverter):

    async def convert(self, ctx, argument):
        colour = await super().convert(ctx, argument)
        return colour.to_rgb()


class Images(
    commands.Cog,
    command_attrs={
        "cooldown": commands.CooldownMapping.from_cooldown(1, 10, commands.BucketType.member),
    }
):
    """Commands having to do with images and/or their manipulation."""

    async def cog_command_error(self, ctx, error):
        error = getattr(error, "original", error)

        if isinstance(error, (ImageAssetConversionFailure, UnidentifiedImageError)):
            await ctx.send("The user, custom emoji, image attachment, or image link was invalid.")
            error.handled__ = True
        elif isinstance(error, ImageAssetTooLarge):
            await ctx.send(f"Image must not exceed {error.max_filesize / 1e6:.0f} MB in size.")
            error.handled__ = True
        elif isinstance(error, DecompressionBombError):
            await ctx.send("Go be Ted Kaczynski somewhere else.")
            error.handled__ = True
        elif isinstance(error, commands.MaxConcurrencyReached):
            await ctx.send(error)
            error.handled__ = True

    @commands.command(aliases=("asskeyify",), usage="[--invert] <image>")
    @commands.max_concurrency(5, commands.BucketType.guild)
    async def asciify(
        self,
        ctx,
        inverted: Optional[_pseudo_bool_flag("--invert")] = False,
        *,
        image: ImageAssetConverter(max_filesize=40_000_000)
    ):
        """Converts an image into ASCII art.

        This is best viewed on desktop.

        By default, this generates the dark mode friendly
        version. To generate the light mode version, pass
        `--invert` before the image argument.

        Image can either be a user, custom emoji, link, or
        attachment. Links and attachments must be under 40
        MB.
        """
        async with ctx.typing():
            try:
                art, delta = await backend.do_asciify(
                    io.BytesIO(await image.read()),
                    inverted=inverted
                )
            except discord.HTTPException:
                await ctx.send("Downloading the image failed. Try again later?")
                return

        await ctx.send(f"Requested by: {ctx.author} \N{BULLET} Took {delta:.2f} ms\n```\n{art}```")

    @commands.command(aliases=("axios", "axiosinterview", "trumpinterview"))
    @commands.bot_has_permissions(attach_files=True)
    @commands.max_concurrency(5, commands.BucketType.guild)
    async def axiostrumpinterview(
        self,
        ctx,
        *,
        text: commands.clean_content(fix_channel_mentions=True)
    ):
        """Generates an Axios interview with Trump meme.

        (Bot Needs: Attach Files)
        """
        async with ctx.typing():
            buffer, delta = await backend.make_axios_interview_meme(text)

        await ctx.send(
            f"Requested by: {ctx.author} \N{BULLET} Took {delta:.2f} ms.",
            file=File(buffer, "axios_trump_interview.png")
        )

    # No, this wasn't made because of Project Blurple.
    @commands.command(
        aliases=("blurpify", "bpify", "discordify"),
        usage="[--rebranded] <image>"
    )
    @commands.bot_has_permissions(attach_files=True)
    @commands.max_concurrency(5, commands.BucketType.guild)
    async def blurplefy(
        self,
        ctx,
        use_rebrand: Optional[_pseudo_bool_flag("--rebranded")] = False,
        *,
        image: ImageAssetConverter(max_filesize=40_000_000)
    ):
        """Blurplefies an image.

        By default, this uses the blurple colour prior to
        Discord's rebranding. To use the new colour, pass
        `--rebrand` before the image argument.

        Image can either be a user, custom emoji, link, or
        attachment. Links and attachments must be under 40
        MB.

        (Bot Needs: Attach Files)
        """
        async with ctx.typing():
            try:
                buffer, delta = await backend.do_blurpify(
                    io.BytesIO(await image.read()),
                    use_rebrand=use_rebrand
                )
            except discord.HTTPException:
                await ctx.send("Downloading the image failed. Try again later?")
                return

        await ctx.send(
            f"Requested by: {ctx.author} \N{BULLET} Took {delta:.2f} ms.",
            file=File(buffer)
        )

    @commands.command(aliases=("captionthis",))
    @commands.bot_has_permissions(embed_links=True)
    @commands.cooldown(1, 5, commands.BucketType.member)
    async def caption(
        self,
        ctx,
        *,
        image: ImageAssetConverter(max_filesize=40_000_000)
    ):
        """Captions an image.

        Image can either be a user, custom emoji, link, or
        attachment. Links and attachments must be under 40
        MB.

        (Bot Needs: Embed Links)
        """
        url = str(image)

        await ctx.trigger_typing()

        try:
            caption = await ctx.post(
                "https://captionbot2.azurewebsites.net/api/messages",
                headers__={"Content-Type": "application/json; charset=utf-8"},
                json__={"Content": url, "Type": "CaptionRequest"}
            )
        except HTTPRequestFailed:
            await ctx.send("Captioning the image failed.")
            return

        embed = Embed(title=f'"{caption}"', colour=0x2F3136)
        embed.set_image(url=url)
        embed.set_footer(
            text=f"Requested by: {ctx.author} "
                 "\N{BULLET} Powered by Microsoft CaptionBot"
        )

        await ctx.send(embed=embed)

    @commands.command(aliases=("meow",))
    @checks.can_start_menu(check_embed=True)
    @commands.cooldown(1, 5, commands.BucketType.member)
    async def cats(self, ctx):
        """Sends a random series of images of cats.

        (Bot Needs: Embed Links, Add Reactions, and Read Message History)
        """
        cats = await ctx.get("https://api.thecatapi.com/v1/images/search?limit=50")

        embeds = [
            Embed(title="\N{CAT FACE}", colour=0x2F3136)
            .set_footer(text="Powered by thecatapi.com")
            .set_image(url=c["url"])
            for c in cats
        ]

        await ctx.paginate(EmbedSource(embeds))

    @commands.command()
    @commands.bot_has_permissions(attach_files=True)
    @commands.max_concurrency(5, commands.BucketType.guild)
    async def captcha(
        self,
        ctx,
        image: ImageAssetConverter(max_filesize=40_000_000),
        *,
        text: commands.clean_content(fix_channel_mentions=True)
    ):
        """Generates a fake Google image captcha.

        (Bot Needs: Attach Files)
        """
        async with ctx.typing():
            try:
                buffer, delta = await backend.make_captcha(
                    io.BytesIO(await image.read()),
                    text
                )
            except discord.HTTPException:
                await ctx.send("Downloading the image failed. Try again later?")
                return

        await ctx.send(
            f"Requested by: {ctx.author} \N{BULLET} Took {delta:.2f} ms.",
            file=File(buffer, "captcha.png")
        )

    @commands.command(aliases=("cmm",))
    @commands.bot_has_permissions(attach_files=True)
    @commands.max_concurrency(5, commands.BucketType.guild)
    async def changemymind(
        self,
        ctx,
        *,
        text: commands.clean_content(fix_channel_mentions=True)
    ):
        """Generates a "change my mind" meme.

        (Bot Needs: Attach Files)
        """
        async with ctx.typing():
            buffer, delta = await backend.make_change_my_mind_meme(text)

        await ctx.send(
            f"Requested by: {ctx.author} \N{BULLET} Took {delta:.2f} ms.",
            file=File(buffer, "change_my_mind.png")
        )

    @commands.command(usage="[--rebranded] <text>")
    @commands.bot_has_permissions(attach_files=True)
    @commands.max_concurrency(5, commands.BucketType.guild)
    async def clyde(
        self,
        ctx,
        use_rebrand: Optional[_pseudo_bool_flag("--rebranded")] = False,
        *,
        text: commands.clean_content(fix_channel_mentions=True)
    ):
        """Generates a fake Clyde bot message.

        By default, this uses the message design prior to
        Discord's rebranding. To use the new design, pass
        `--rebranded` before the image argument.

        (Bot Needs: Attach Files)
        """
        async with ctx.typing():
            buffer, delta = await backend.make_clyde_message(text, use_rebrand=use_rebrand)

        await ctx.send(
            f"Requested by: {ctx.author} \N{BULLET} Took {delta:.2f} ms.",
            file=File(buffer, "clyde.png")
        )

    @commands.command(aliases=("cupofjoe",))
    async def coffee(self, ctx):
        """Sends a random image of coffee."""
        coffee = await ctx.get("https://coffee.alexflipnote.dev/random.json")

        embed = Embed(title="\N{HOT BEVERAGE}", colour=0x2F3136)
        embed.set_image(url=coffee["file"])
        embed.set_footer(text="Powered by alexflipnote.dev")

        await ctx.send(embed=embed)

    @commands.command(aliases=("df",))
    @commands.bot_has_permissions(attach_files=True)
    @commands.max_concurrency(5, commands.BucketType.guild)
    async def deepfry(
        self,
        ctx,
        *,
        image: ImageAssetConverter(max_filesize=40_000_000)
    ):
        """Deep fries an image.

        Image can either be a user, custom emoji, link, or
        attachment. Links and attachments must be under 40
        MB.

        (Bot Needs: Attach Files)
        """
        async with ctx.typing():
            try:
                buffer, delta = await backend.do_deepfry(
                    io.BytesIO(await image.read())
                )
            except discord.HTTPException:
                await ctx.send("Downloading the image failed. Try again later?")
                return

        await ctx.send(
            f"Requested by: {ctx.author} \N{BULLET} Took {delta:.2f} ms.",
            file=File(buffer)
        )

    @commands.command(aliases=("doggos", "woof"))
    @checks.can_start_menu(check_embed=True)
    @commands.cooldown(1, 5, commands.BucketType.member)
    async def dogs(self, ctx):
        """Sends a random series of images of dogs.

        (Bot Needs: Embed Links, Add Reactions, and Read Message History)
        """
        dogs = await ctx.get("https://dog.ceo/api/breeds/image/random/50")

        embeds = [
            Embed(title="\N{DOG FACE}", colour=0x2F3136)
            .set_footer(text="Powered by dog.ceo")
            .set_image(url=d)
            for d in dogs["message"]
        ]

        await ctx.paginate(EmbedSource(embeds))

    @commands.command(aliases=("quack",))
    @commands.bot_has_permissions(embed_links=True)
    @commands.cooldown(2, 5, commands.BucketType.member)
    async def duck(self, ctx):
        """Sends a random image of a duck.

        (Bot Needs: Embed Links)
        """
        duck = await ctx.get("https://random-d.uk/api/random")

        embed = Embed(title="\N{DUCK}", colour=0x2F3136)
        embed.set_image(url=duck["url"])
        embed.set_footer(text="Powered by random-d.uk")

        await ctx.send(embed=embed)

    @commands.command(aliases=("floof",))
    @commands.bot_has_permissions(embed_links=True)
    @commands.cooldown(2, 5, commands.BucketType.member)
    async def fox(self, ctx):
        """Sends a random image of a fox.

        (Bot Needs: Embed Links)
        """
        fox = await ctx.get("https://randomfox.ca/floof/")

        embed = Embed(title="\N{FOX FACE}", colour=0x2F3136)
        embed.set_image(url=fox["image"])
        embed.set_footer(text="Powered by randomfox.ca")

        await ctx.send(embed=embed)

    @commands.command()
    @commands.bot_has_permissions(attach_files=True)
    @commands.max_concurrency(5, commands.BucketType.guild)
    async def invert(
        self,
        ctx,
        *,
        image: ImageAssetConverter(max_filesize=40_000_000)
    ):
        """Inverts an image's colours.

        Image can either be a user, custom emoji, link, or
        attachment. Links and attachments must be under 40
        MB.

        (Bot Needs: Attach Files)
        """
        async with ctx.typing():
            try:
                buffer, delta = await backend.do_invert(io.BytesIO(await image.read()))
            except discord.HTTPException:
                await ctx.send("Downloading the image failed. Try again later?")
                return

        await ctx.send(
            f"Requested by: {ctx.author} \N{BULLET} Took {delta:.2f} ms.",
            file=File(buffer, "inverted.png")
        )

    @commands.command(aliases=("iphone10",))
    @commands.bot_has_permissions(attach_files=True)
    @commands.max_concurrency(5, commands.BucketType.guild)
    async def iphonex(
        self,
        ctx,
        *,
        image: ImageAssetConverter(max_filesize=40_000_000)
    ):
        """Fits an image into an iPhone X screen.

        Image can either be a user, custom emoji, link, or
        attachment. Links and attachments must be under 40
        MB.

        (Bot Needs: Attach Files)
        """
        async with ctx.typing():
            try:
                buffer, delta = await backend.make_iphone_x(
                    io.BytesIO(await image.read())
                )
            except discord.HTTPException:
                await ctx.send("Downloading the image failed. Try again later?")
                return

        await ctx.send(
            f"Requested by: {ctx.author} \N{BULLET} Took {delta:.2f} ms.",
            file=File(buffer, "iphone_x.png")
        )

    @commands.command(aliases=("needsmorejpeg", "jpegify"))
    @commands.bot_has_permissions(attach_files=True)
    @commands.max_concurrency(5, commands.BucketType.guild)
    async def jpeg(
        self,
        ctx,
        intensity: Optional[int] = 5,
        *,
        image: ImageAssetConverter(max_filesize=40_000_000)
    ):
        """JPEGifies an image to an optional intensity.

        Intensity value must be between 1 and 10, inclusive.
        The higher the intensity, the more JPEG the image
        result becomes.

        Image can either be a user, custom emoji, link, or
        attachment. Links and attachments must be under 40
        MB.

        (Bot Needs: Attach Files)
        """
        if not 0 < intensity <= 10:
            await ctx.send("Intensity value must be between 1 and 10, inclusive.")
            return

        async with ctx.typing():
            try:
                buffer, delta = await backend.do_jpegify(
                    io.BytesIO(await image.read()),
                    quality=11 - intensity
                )
            except discord.HTTPException:
                await ctx.send("Downloading the image failed. Try again later?")
                return

        await ctx.send(
            f"Requested by: {ctx.author} \N{BULLET} Took {delta:.2f} ms.",
            file=File(buffer, "jpegified.jpg")
        )

    @commands.command(aliases=("magic",))
    @commands.bot_has_permissions(attach_files=True)
    @commands.max_concurrency(5, commands.BucketType.guild)
    async def magik(
        self,
        ctx,
        intensity: Optional[int] = 1,
        *,
        image: ImageAssetConverter(max_filesize=40_000_000)
    ):
        """Heavily warps an image to an optional intensity.

        Intensity value must be between 1 and 25, inclusive.
        The higher the intensity, the more warped the image
        result becomes.

        Image can either be a user, custom emoji, link, or
        attachment. Links and attachments must be under 40
        MB.

        (Bot Needs: Attach Files)
        """
        # NOTE: Technically, NekoBot doesn't actually specify an
        # upper limit themselves, I'm simply just adding one in
        # for the sake of not overloading the service.
        if not 0 < intensity <= 25:
            await ctx.send("Intensity value must be between 1 and 25, inclusive.")
            return

        async with ctx.typing():
            try:
                resp = await ctx.get(
                    "https://nekobot.xyz/api/imagegen?type=magik&raw=1",
                    image=str(image),
                    intensity=intensity
                )
            except HTTPRequestFailed as exc:
                # For whatever reason, NekoBot doesn't actually
                # support converting WEBP files in this instance
                # and internally errors if one is sent.
                if exc.status == 500:
                    await ctx.send(
                        "Something went wrong internally on NekoBot's end."
                        " This is probably because you sent a WEBP file, which"
                        " currently isn't supported."
                    )
                    return

                if exc.status == 504:
                    await ctx.send("Nekobot took too long to respond.")
                    return

                raise

        await ctx.send(
            f"Requested by: {ctx.author} \N{BULLET} Powered by nekobot.xyz",
            file=File(io.BytesIO(resp), "magik.png")
        )

    @commands.command(aliases=("phcomment", "phc"))
    @commands.guild_only()
    @commands.bot_has_permissions(attach_files=True)
    @commands.max_concurrency(5, commands.BucketType.guild)
    async def pornhubcomment(
        self,
        ctx,
        user: Optional[discord.Member],
        *,
        text: commands.clean_content(fix_channel_mentions=True)
    ):
        """Generates a fake Pr0nhub comment from the specified user.

        User can either be a name, ID, or mention.

        (Bot Needs: Attach Files)

        **EXAMPLE:**
        ```
        pornhubcomment @HitchedSyringe#0598 This isn't free Discord Nitro.
        ```
        """
        if user is None:
            user = ctx.author

        async with ctx.typing():
            try:
                buffer, delta = await backend.make_pornhub_comment(
                    user.display_name,
                    io.BytesIO(await user.display_avatar.with_format("png").read()),
                    text
                )
            except discord.NotFound:
                await ctx.send("Could not resolve the user's avatar. Try again later?")
                return
            except discord.HTTPException:
                await ctx.send("Downloading the user's avatar failed. Try again later?")
                return

        await ctx.send(
            f"Requested by: {ctx.author} \N{BULLET} Took {delta:.2f} ms.",
            file=File(buffer, "pornhub_comment.png")
        )

    # This remixes an image posted by a member of a server
    # I co-own, which made by someone else encouraging others
    # to cancel said member. I figure this one will be an Easter
    # Egg since most people will probably be confused as to what
    # the funny reference is.
    @commands.command(hidden=True)
    @commands.guild_only()
    @commands.bot_has_permissions(attach_files=True)
    @commands.max_concurrency(5, commands.BucketType.guild)
    async def robloxcancel(self, ctx, *, user: discord.Member):
        """Cancels someone for being poor on bloxburg.

        User can either be a name, ID, or mention.

        (Bot Needs: Attach Files)

        **EXAMPLE:**
        ```
        robloxcancel @HitchedSyringe#0598
        ```
        """
        async with ctx.typing():
            try:
                buffer, delta = await backend.make_roblox_cancel_meme(
                    io.BytesIO(await user.display_avatar.with_format("png").read()),
                    user.name,
                    user.discriminator
                )
            except discord.NotFound:
                await ctx.send("Could not resolve the user's avatar. Try again later?")
                return
            except discord.HTTPException:
                await ctx.send("Downloading the user's avatar failed. Try again later?")
                return

        await ctx.send(
            f"Requested by: {ctx.author} \N{BULLET} Took {delta:.2f} ms.",
            file=File(buffer, "roblox_cancel.png")
        )

    @commands.command()
    @commands.guild_only()
    @commands.bot_has_permissions(embed_links=True, attach_files=True)
    @commands.max_concurrency(5, commands.BucketType.guild)
    async def ship(
        self,
        ctx,
        first_user: discord.Member,
        second_user: discord.Member = None
    ):
        """Ships two users.

        Users can either be a name, ID, or mention.

        If no second user is specified, then the second
        user will default to you.

        (Bot Needs: Embed Links and Attach Files)

        **EXAMPLES:**
        ```bnf
        <1> ship HitchedSyringe#0598
        <2> ship HitchedSyringe#0598 @Sleepy#5396
        ```
        """
        if second_user is None:
            second_user = ctx.author

        if first_user == second_user:
            await ctx.send("You cannot ship the same user.")
            return

        async with ctx.typing():
            try:
                buffer, delta = await backend.make_ship(
                    io.BytesIO(await first_user.display_avatar.with_format("png").read()),
                    io.BytesIO(await second_user.display_avatar.with_format("png").read()),
                )
            except discord.NotFound:
                await ctx.send("Could not resolve the avatars. Try again later?")
                return
            except discord.HTTPException:
                await ctx.send("Downloading the avatars failed. Try again later?")
                return

        first_name = first_user.name
        second_name = second_user.name
        score = s_randint(0, 100, seed=first_user.id ^ second_user.id)

        embed = Embed(
            title=f"{first_name} \N{HEAVY BLACK HEART} {second_name}",
            colour=0x2F3136
        )
        embed.set_author(
            name=first_name[:len(first_name) // 2] + second_name[len(second_name) // 2:]
        )
        embed.set_image(url="attachment://ship.png")
        embed.set_footer(text=f"Requested by: {ctx.author} \N{BULLET} Took {delta:.2f} ms.")

        embed.add_field(
            name=f"Confidence \N{BULLET} **{score}%**",
            value=f"0 {progress_bar(progress=score, maximum=100, per=10)} 100"
        )

        await ctx.send(embed=embed, file=File(buffer, "ship.png"))

    @commands.command(aliases=("soyjacks", "soyjak", "soyjack"))
    @commands.bot_has_permissions(attach_files=True)
    @commands.max_concurrency(5, commands.BucketType.guild)
    async def soyjaks(
        self,
        ctx,
        *,
        image: ImageAssetConverter(max_filesize=40_000_000)
    ):
        """Generates a consoomer soyjaks pointing meme.

        Image can either be a user, custom emoji, link, or
        attachment. Links and attachments must be under 40
        MB.

        (Bot Needs: Attach Files)
        """
        async with ctx.typing():
            try:
                buffer, delta = await backend.make_pointing_soyjaks_meme(
                    io.BytesIO(await image.read())
                )
            except discord.HTTPException:
                await ctx.send("Downloading the image failed. Try again later?")
                return

        await ctx.send(
            f"Requested by: {ctx.author} \N{BULLET} Took {delta:.2f} ms.",
            file=File(buffer, "soyjak.png")
        )

    # Long and strict RL due to Nekobot processing.
    @commands.command()
    @commands.bot_has_permissions(attach_files=True)
    @commands.max_concurrency(2, commands.BucketType.guild)
    @commands.cooldown(1, 40, commands.BucketType.member)
    async def stickbug(
        self,
        ctx,
        *,
        image: ImageAssetConverter(max_filesize=40_000_000)
    ):
        """Generates a stickbug meme.

        Image can either be a user, custom emoji, link, or
        attachment. Links and attachments must be under 40
        MB.

        (Bot Needs: Attach Files)
        """
        async with ctx.typing():
            try:
                resp = await ctx.get(
                    "https://nekobot.xyz/api/imagegen?type=stickbug",
                    url=str(image)
                )
            except HTTPRequestFailed as exc:
                # I'm not sure if this is filetype-specific or not,
                # but this sometimes gets returned so I might as
                # well handle it.
                if exc.status == 400:
                    await ctx.send("Nekobot thinks the image you sent was invalid.")
                    return

                if exc.status == 504:
                    await ctx.send("Nekobot took too long to respond.")
                    return

                raise

        await ctx.send(
            f"Requested by: {ctx.author} \N{BULLET} Powered by nekobot.xyz",
            file=File(io.BytesIO(await ctx.get(resp["message"])), "stickbug.mp4")
        )

    @commands.command()
    @commands.bot_has_permissions(attach_files=True)
    @commands.max_concurrency(5, commands.BucketType.guild)
    async def swirl(
        self,
        ctx,
        intensity: Optional[int] = 5,
        *,
        image: ImageAssetConverter(max_filesize=40_000_000)
    ):
        """Swirls an image to an optional intensity.

        Intensity value must be between 1 and 15, inclusive.
        The higher the intensity, the more swirly the image
        result becomes.

        Image can either be a user, custom emoji, link, or
        attachment. Links and attachments must be under 40
        MB.

        (Bot Needs: Attach Files)
        """
        if not 0 < intensity <= 15:
            await ctx.send("Intensity value must be between 1 and 15, inclusive.")
            return

        async with ctx.typing():
            try:
                buffer, delta = await backend.do_swirl(
                    io.BytesIO(await image.read()),
                    intensity=intensity * 2.5
                )
            except discord.HTTPException:
                await ctx.send("Downloading the image failed. Try again later?")
                return

        await ctx.send(
            f"Requested by: {ctx.author} \N{BULLET} Took {delta:.2f} ms.",
            file=File(buffer, "swirl.png")
        )

    @flags.add_flag("--text", required=True)
    @flags.add_flag("--font", dest="font_path", default="Arimo-Regular")
    @flags.add_flag("--textcolour", "--textcolor", dest="text_colour", type=RGBColourConverter)
    @flags.add_flag("--bgcolour", "--bgcolor", dest="bg_colour", type=RGBColourConverter)
    @flags.add_flag("--size", type=int, default=35)
    @flags.command(aliases=("tti",), usage="<--text> [options...]")
    @commands.bot_has_permissions(attach_files=True)
    async def texttoimage(self, ctx, **flags):
        """Converts text into an image.

        This uses a powerful "command-line" interface.
        Values with spaces must be surrounded by quotation marks.
        **All options except `--text` are optional.**

        __**The following options are valid:**__

        `--text`
        > The text to convert into an image. **Required**
        `--font`
        > The font to use.
        > This is case-sensitive.
        > Valid fonts: `Arimo-Bold`, `Arimo-Regular`, `Catamaran-Regular`,
        > `Lustria-Regular`, `Roboto-Bold`, `Roboto-Medium`, `Roboto-Regular`,
        > `SourceSerifPro-SemiBold`
        > Defaults to `Arimo-Bold` if omitted.
        `--textcolour` or `--textcolor`
        > The colour of the text.
        > Colour can either be a name, 6 digit hex value prefixed with either a
        > `0x`, `#`, or `0x#`; or CSS RGB function (e.g. `rgb(103, 173, 242)`).
        > Defaults to `#99AAB5` if omitted.
        `--bgcolour` or `--bgcolor`
        > The colour of the background.
        > Colour can either be a name, 6 digit hex value prefixed with either a
        > `0x`, `#`, or `0x#`; or CSS RGB function (e.g. `rgb(103, 173, 242)`).
        > If omitted, the background will be transparent.
        `--size`
        > The size of the text.
        > Must be between 5 and 35, inclusive.
        > Defaults to `35` if omitted.

        (Bot Needs: Attach Files)
        """
        if not 5 <= flags["size"] <= 35:
            await ctx.send("Text size must be between 5 and 35, inclusive.")
            return

        # flags doesn't properly handle converter instances so we have to do this.
        flags["text"] = await commands.clean_content(fix_channel_mentions=True).convert(ctx, flags["text"])

        flags["font_path"] = font = FONTS.joinpath(flags["font_path"] + ".ttf").resolve()

        if not font.is_relative_to(FONTS):
            await ctx.send("Nice try with the path traversal, buddy.")
            return

        async with ctx.typing():
            try:
                buffer, delta = await backend.make_text_image(**flags)
            except OSError:
                # TBH ImageFont.truetype should throw FileNotFoundError instead.
                await ctx.send("The given font was invalid.")
                return

        await ctx.send(
            f"Requested by: {ctx.author} \N{BULLET} Took {delta:.2f} ms.",
            file=File(buffer, "tti.png")
        )

    @texttoimage.error
    async def on_texttoimage_error(self, ctx, error):
        if isinstance(error, flags.ArgumentParsingError):
            await ctx.send(
                "An error occurred while processing your flag arguments."
                "\nPlease double-check your input arguments and try again."
            )
            error.handled__ = True

    @commands.command()
    @commands.bot_has_permissions(attach_files=True)
    @commands.max_concurrency(5, commands.BucketType.guild)
    async def threats(
        self,
        ctx,
        *,
        image: ImageAssetConverter(max_filesize=40_000_000)
    ):
        """Generates a "three threats to society" meme.

        Image can either be a user, custom emoji, link, or
        attachment. Links and attachments must be under 40
        MB.

        (Bot Needs: Attach Files)
        """
        async with ctx.typing():
            try:
                buffer, delta = await backend.make_threats_meme(
                    io.BytesIO(await image.read())
                )
            except discord.HTTPException:
                await ctx.send("Downloading the image failed. Try again later?")
                return

        await ctx.send(
            f"Requested by: {ctx.author} \N{BULLET} Took {delta:.2f} ms.",
            file=File(buffer, "threats.png")
        )

    @commands.command()
    @commands.bot_has_permissions(attach_files=True)
    @commands.max_concurrency(5, commands.BucketType.guild)
    async def trapcard(
        self,
        ctx,
        title: commands.clean_content(fix_channel_mentions=True),
        image: ImageAssetConverter(max_filesize=40_000_000),
        *,
        flavour_text: commands.clean_content(fix_channel_mentions=True)
    ):
        """Generates a fake Yu-Gi-Oh! trap card.

        Image can either be a user, custom emoji, link, or
        attachment. Links and attachments must be under 40
        MB.

        (Bot Needs: Attach Files)
        """
        async with ctx.typing():
            try:
                buffer, delta = await backend.make_trapcard(
                    title,
                    flavour_text,
                    io.BytesIO(await image.read())
                )
            except discord.HTTPException:
                await ctx.send("Downloading the image failed. Try again later?")
                return

        await ctx.send(
            f"Requested by: {ctx.author} \N{BULLET} Took {delta:.2f} ms.",
            file=File(buffer, "trapcard.png")
        )

    @commands.command()
    @commands.bot_has_permissions(attach_files=True)
    async def tucker(
        self,
        ctx,
        image: ImageAssetConverter(max_filesize=40_000_000)
    ):
        """Generates a live Tucker reaction meme.

        Image can either be a user, custom emoji, link, or
        attachment. Links and attachments must be under 40
        MB.

        (Bot Needs: Attach Files)
        """
        async with ctx.typing():
            try:
                buffer, delta = await backend.make_live_tucker_reaction_meme(
                    io.BytesIO(await image.read())
                )
            except discord.HTTPException:
                await ctx.send("Downloading the image failed. Try again later?")
                return

        await ctx.send(
            f"Requested by: {ctx.author} \N{BULLET} Took {delta:.2f} ms.",
            file=File(buffer, "live_tucker_reaction.png")
        )

    @commands.command()
    @commands.guild_only()
    @commands.bot_has_permissions(attach_files=True)
    async def tweet(
        self,
        ctx,
        user: Optional[discord.Member],
        *,
        text: commands.clean_content(fix_channel_mentions=True)
    ):
        """Generates a fake Tweet from the specified user.

        User can either be a name, ID, or mention.

        (Bot Needs: Attach Files)

        **EXAMPLE:**
        ```
        tweet @HitchedSyringe#0598 Twitter for Sleepy
        ```
        """
        if user is None:
            user = ctx.author

        async with ctx.typing():
            try:
                buffer, delta = await backend.make_tweet(
                    user.name,
                    user.display_name,
                    io.BytesIO(await user.display_avatar.with_format("png").read()),
                    text
                )
            except discord.NotFound:
                await ctx.send("Could not resolve the user's avatar. Try again later?")
                return
            except discord.HTTPException:
                await ctx.send("Downloading the user's avatar failed. Try again later?")
                return

        await ctx.send(
            f"Requested by: {ctx.author} \N{BULLET} Took {delta:.2f} ms.",
            file=File(buffer, "tweet.png")
        )

    @commands.command(aliases=("www",))
    @commands.guild_only()
    @commands.bot_has_permissions(attach_files=True)
    @commands.max_concurrency(5, commands.BucketType.guild)
    async def whowouldwin(
        self,
        ctx,
        first_user: discord.Member,
        second_user: discord.Member = None
    ):
        """Generates a "who would win" meme.

        User can either be a name, ID, or mention.

        If no second user is specified, then the second
        user will default to you.

        (Bot Needs: Attach Files)

        **EXAMPLES:**
        ```bnf
        <1> whowouldwin HitchedSyringe#0598
        <2> whowouldwin HitchedSyringe#0598 someotherperson#0194
        ```
        """
        if second_user is None:
            second_user = ctx.author

        if first_user == second_user:
            await ctx.send("You cannot compare the same user.")
            return

        async with ctx.typing():
            try:
                buffer, delta = await backend.make_who_would_win_meme(
                    io.BytesIO(await first_user.display_avatar.with_format("png").read()),
                    io.BytesIO(await second_user.display_avatar.with_format("png").read()),
                )
            except discord.NotFound:
                await ctx.send("Could not resolve the avatars. Try again later?")
                return
            except discord.HTTPException:
                await ctx.send("Downloading the avatars failed. Try again later?")
                return

        await ctx.send(
            f"Requested by: {ctx.author} \N{BULLET} Took {delta:.2f} ms.",
            file=File(buffer, "who_would_win.png")
        )

    @commands.command(aliases=("ytcomment", "ytc"))
    @commands.guild_only()
    @commands.bot_has_permissions(attach_files=True)
    @commands.max_concurrency(5, commands.BucketType.guild)
    async def youtubecomment(
        self,
        ctx,
        user: Optional[discord.Member],
        *,
        text: commands.clean_content(fix_channel_mentions=True)
    ):
        """Generates a fake YouTube comment from the specified user.

        User can either be a name, ID, or mention.

        (Bot Needs: Attach Files)

        **EXAMPLE:**
        ```
        youtubecomment @HitchedSyringe#0598 Epic video.
        ```
        """
        if user is None:
            user = ctx.author

        async with ctx.typing():
            try:
                buffer, delta = await backend.make_youtube_comment(
                    user.display_name,
                    io.BytesIO(await user.display_avatar.with_format("png").read()),
                    text
                )
            except discord.NotFound:
                await ctx.send("Could not resolve the user's avatar. Try again later?")
                return
            except discord.HTTPException:
                await ctx.send("Downloading the user's avatar failed. Try again later?")
                return

        await ctx.send(
            f"Requested by: {ctx.author} \N{BULLET} Took {delta:.2f} ms.",
            file=File(buffer, "youtube_comment.png")
        )
