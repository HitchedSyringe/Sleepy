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

# fmt: off
__all__ = (
    "Images",
)
# fmt: on


import io
from typing import TYPE_CHECKING, Optional

import discord
from discord import Colour, Embed, File
from discord.ext import commands
from PIL import UnidentifiedImageError
from PIL.Image import DecompressionBombError
from typing_extensions import Annotated

from sleepy.converters import (
    ImageAssetConversionFailure,
    ImageAssetConverter,
    ImageAssetTooLarge,
    _positional_bool_flag,
)
from sleepy.http import HTTPRequestFailed
from sleepy.menus import EmbedSource
from sleepy.utils import _as_argparse_dict

from . import backend
from .fonts import FONTS

if TYPE_CHECKING:
    from pathlib import Path

    from sleepy.context import Context as SleepyContext
    from sleepy.mimics import PartialAsset


def resolve_font(name: str) -> Path:
    path = FONTS.joinpath(f"{name}.ttf").resolve()

    if not path.is_file() or not path.is_relative_to(FONTS):  # type: ignore
        raise commands.BadArgument(f"Font '{name}' is invalid.")

    return path


class TTIFlags(commands.FlagConverter):
    text: Annotated[str, commands.clean_content(fix_channel_mentions=True)]
    font_path: Path = commands.flag(
        name="font", converter=resolve_font, default=FONTS / "Arimo-Regular.ttf"
    )
    text_colour: Colour = commands.flag(
        name="text-colour",
        aliases=("text-color",),  # type: ignore
        default=Colour.greyple(),
    )
    bg_colour: Colour = commands.flag(
        name="bg-colour",
        aliases=("bg-color",),  # type: ignore
        default=None,
    )
    size: commands.Range[int, 20, 50] = 35


class Images(
    commands.Cog,
    command_attrs={
        "cooldown": commands.CooldownMapping.from_cooldown(
            1, 10, commands.BucketType.member
        ),
    },
):
    """Commands that involve images and/or their manipulation."""

    ICON: str = "\N{FRAME WITH PICTURE}"

    async def cog_command_error(self, ctx: SleepyContext, error: Exception) -> None:
        error = getattr(error, "original", error)

        if isinstance(error, (ImageAssetConversionFailure, UnidentifiedImageError)):
            await ctx.send("The image was either invalid or could not be read.")
            ctx._already_handled_error = True
        elif isinstance(error, ImageAssetTooLarge):
            max_size_mb = error.max_filesize / 1e6

            await ctx.send(f"Images cannot exceed {max_size_mb:.0f} MB in size.")
            ctx._already_handled_error = True
        elif isinstance(error, DecompressionBombError):
            await ctx.send("Go be Ted Kaczynski somewhere else.")
            ctx._already_handled_error = True
        elif isinstance(error, commands.MaxConcurrencyReached):
            await ctx.send(error)  # type: ignore
            ctx._already_handled_error = True

    @commands.command(aliases=("asskeyify",), usage="[-invert] <image>")
    @commands.max_concurrency(5, commands.BucketType.guild)
    async def asciify(
        self,
        ctx: SleepyContext,
        inverted: Annotated[bool, Optional[_positional_bool_flag("-invert")]] = False,  # type: ignore
        *,
        image: Annotated["PartialAsset", ImageAssetConverter],
    ) -> None:
        """Converts an image into ASCII art.

        This is best viewed on desktop.

        By default, this generates the dark mode friendly
        version. To generate the light mode version, pass
        `-invert` before the image argument.

        Image can either be a user, custom emoji, sticker,
        link, or attachment. Links and attachments must be
        under 40 MB.
        """
        async with ctx.typing():
            try:
                image_bytes = await image.read()
            except discord.HTTPException:
                await ctx.send("Downloading the image failed. Try again later?")
                return

            art, delta = await backend.do_asciify(
                io.BytesIO(image_bytes), inverted=inverted
            )

        await ctx.send(
            f"Requested by: {ctx.author} \N{BULLET} Took {delta:.2f} ms\n```\n{art}```"
        )

    @commands.command(aliases=("axios", "axiosinterview", "trumpinterview"))
    @commands.bot_has_permissions(attach_files=True)
    @commands.max_concurrency(5, commands.BucketType.guild)
    async def axiostrumpinterview(
        self,
        ctx: SleepyContext,
        *,
        text: Annotated[str, commands.clean_content(fix_channel_mentions=True)],
    ) -> None:
        """Generates an Axios interview with Trump meme.

        (Bot Needs: Attach Files)
        """
        async with ctx.typing():
            buffer, delta = await backend.make_axios_interview_meme(text)

        await ctx.send(
            f"Requested by: {ctx.author} \N{BULLET} Took {delta:.2f} ms.",
            file=File(buffer, "axios_trump_interview.png"),
        )

    # No, this wasn't made because of Project Blurple.
    @commands.command(
        aliases=("blurpify", "bpify", "discordify"), usage="[-rebranded] <image>"
    )
    @commands.bot_has_permissions(attach_files=True)
    @commands.max_concurrency(5, commands.BucketType.guild)
    async def blurplefy(
        self,
        ctx: SleepyContext,
        use_rebrand: Annotated[
            bool, Optional[_positional_bool_flag("-rebranded")]  # type: ignore
        ] = False,
        *,
        image: Annotated["PartialAsset", ImageAssetConverter],
    ) -> None:
        """Blurplefies an image.

        By default, this uses the blurple colour prior to
        Discord's rebranding. To use the new colour, pass
        `-rebranded` before the image argument.

        Image can either be a user, custom emoji, sticker,
        link, or attachment. Links and attachments must be
        under 40 MB.

        (Bot Needs: Attach Files)
        """
        async with ctx.typing():
            try:
                image_bytes = await image.read()
            except discord.HTTPException:
                await ctx.send("Downloading the image failed. Try again later?")
                return

            buffer, delta = await backend.do_blurpify(
                io.BytesIO(image_bytes), use_rebrand=use_rebrand
            )

        await ctx.send(
            f"Requested by: {ctx.author} \N{BULLET} Took {delta:.2f} ms.",
            file=File(buffer),
        )

    @commands.command(aliases=("meow",))
    @commands.bot_has_permissions(embed_links=True)
    @commands.cooldown(1, 5, commands.BucketType.member)
    async def cats(self, ctx: SleepyContext) -> None:
        """Sends a random series of images of cats.

        (Bot Needs: Embed Links)
        """
        cats = await ctx.get("https://api.thecatapi.com/v1/images/search?limit=50")

        embeds = [
            Embed(title="\N{CAT FACE}", colour=Colour.dark_embed())
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
        ctx: SleepyContext,
        image: Annotated["PartialAsset", ImageAssetConverter],
        *,
        text: Annotated[str, commands.clean_content(fix_channel_mentions=True)],
    ) -> None:
        """Generates a fake Google image captcha.

        (Bot Needs: Attach Files)
        """
        async with ctx.typing():
            try:
                image_bytes = await image.read()
            except discord.HTTPException:
                await ctx.send("Downloading the image failed. Try again later?")
                return

            buffer, delta = await backend.make_captcha(io.BytesIO(image_bytes), text)

        await ctx.send(
            f"Requested by: {ctx.author} \N{BULLET} Took {delta:.2f} ms.",
            file=File(buffer, "captcha.png"),
        )

    @commands.command(usage="[-rebranded] <text>")
    @commands.bot_has_permissions(attach_files=True)
    @commands.max_concurrency(5, commands.BucketType.guild)
    async def clyde(
        self,
        ctx: SleepyContext,
        use_rebrand: Annotated[
            bool, Optional[_positional_bool_flag("-rebranded")]  # type: ignore
        ] = False,
        *,
        text: Annotated[str, commands.clean_content(fix_channel_mentions=True)],
    ) -> None:
        """Generates a fake Clyde bot message.

        By default, this uses the message design prior to
        Discord's rebranding. To use the new design, pass
        `-rebranded` before the image argument.

        (Bot Needs: Attach Files)
        """
        async with ctx.typing():
            buffer, delta = await backend.make_clyde_message(
                text, use_rebrand=use_rebrand
            )

        await ctx.send(
            f"Requested by: {ctx.author} \N{BULLET} Took {delta:.2f} ms.",
            file=File(buffer, "clyde.png"),
        )

    @commands.command(aliases=("cupofjoe",))
    async def coffee(self, ctx: SleepyContext) -> None:
        """Sends a random image of coffee."""
        coffee = await ctx.get("https://coffee.alexflipnote.dev/random.json")

        embed = Embed(title="\N{HOT BEVERAGE}", colour=Colour.dark_embed())
        embed.set_image(url=coffee["file"])
        embed.set_footer(text="Powered by alexflipnote.dev")

        await ctx.send(embed=embed)

    @commands.command(aliases=("honeycomb",))
    @commands.bot_has_permissions(attach_files=True)
    @commands.max_concurrency(5, commands.BucketType.guild)
    async def dalgona(
        self, ctx: SleepyContext, *, image: Annotated["PartialAsset", ImageAssetConverter]
    ) -> None:
        """\N{IDEOGRAPHIC NUMBER ZERO}\N{WHITE UP-POINTING TRIANGLE}\N{BALLOT BOX}

        Image can either be a user, custom emoji, sticker,
        link, or attachment. Links and attachments must be
        under 40 MB.

        (Bot Needs: Attach Files)
        """
        async with ctx.typing():
            try:
                image_bytes = await image.read()
            except discord.HTTPException:
                await ctx.send("Downloading the image failed. Try again later?")
                return

            buffer, delta = await backend.make_dalgona(io.BytesIO(image_bytes))

        await ctx.send(
            f"Requested by: {ctx.author} \N{BULLET} Took {delta:.2f} ms.",
            file=File(buffer, "dalgona.png"),
        )

    @commands.command(aliases=("df",))
    @commands.bot_has_permissions(attach_files=True)
    @commands.max_concurrency(5, commands.BucketType.guild)
    async def deepfry(
        self, ctx: SleepyContext, *, image: Annotated["PartialAsset", ImageAssetConverter]
    ) -> None:
        """Deep fries an image.

        Image can either be a user, custom emoji, sticker,
        link, or attachment. Links and attachments must be
        under 40 MB.

        (Bot Needs: Attach Files)
        """
        async with ctx.typing():
            try:
                image_bytes = await image.read()
            except discord.HTTPException:
                await ctx.send("Downloading the image failed. Try again later?")
                return

            buffer, delta = await backend.do_deepfry(io.BytesIO(image_bytes))

        await ctx.send(
            f"Requested by: {ctx.author} \N{BULLET} Took {delta:.2f} ms.",
            file=File(buffer),
        )

    @commands.command(aliases=("doggos", "woof"))
    @commands.bot_has_permissions(embed_links=True)
    @commands.cooldown(1, 5, commands.BucketType.member)
    async def dogs(self, ctx: SleepyContext) -> None:
        """Sends a random series of images of dogs.

        (Bot Needs: Embed Links)
        """
        dogs = await ctx.get("https://dog.ceo/api/breeds/image/random/50")

        embeds = [
            Embed(title="\N{DOG FACE}", colour=Colour.dark_embed())
            .set_footer(text="Powered by dog.ceo")
            .set_image(url=d)
            for d in dogs["message"]
        ]

        await ctx.paginate(EmbedSource(embeds))

    @commands.command(aliases=("quack",))
    @commands.bot_has_permissions(embed_links=True)
    @commands.cooldown(2, 5, commands.BucketType.member)
    async def duck(self, ctx: SleepyContext) -> None:
        """Sends a random image of a duck.

        (Bot Needs: Embed Links)
        """
        duck = await ctx.get("https://random-d.uk/api/random")

        embed = Embed(title="\N{DUCK}", colour=Colour.dark_embed())
        embed.set_image(url=duck["url"])
        embed.set_footer(text="Powered by random-d.uk")

        await ctx.send(embed=embed)

    @commands.command(aliases=("floof",))
    @commands.bot_has_permissions(embed_links=True)
    @commands.cooldown(2, 5, commands.BucketType.member)
    async def fox(self, ctx: SleepyContext) -> None:
        """Sends a random image of a fox.

        (Bot Needs: Embed Links)
        """
        fox = await ctx.get("https://randomfox.ca/floof/")

        embed = Embed(title="\N{FOX FACE}", colour=Colour.dark_embed())
        embed.set_image(url=fox["image"])
        embed.set_footer(text="Powered by randomfox.ca")

        await ctx.send(embed=embed)

    @commands.command()
    @commands.bot_has_permissions(attach_files=True)
    @commands.max_concurrency(5, commands.BucketType.guild)
    async def invert(
        self, ctx: SleepyContext, *, image: Annotated["PartialAsset", ImageAssetConverter]
    ) -> None:
        """Inverts an image's colours.

        Image can either be a user, custom emoji, sticker,
        link, or attachment. Links and attachments must be
        under 40 MB.

        (Bot Needs: Attach Files)
        """
        async with ctx.typing():
            try:
                image_bytes = await image.read()
            except discord.HTTPException:
                await ctx.send("Downloading the image failed. Try again later?")
                return

            buffer, delta = await backend.do_invert(io.BytesIO(image_bytes))

        await ctx.send(
            f"Requested by: {ctx.author} \N{BULLET} Took {delta:.2f} ms.",
            file=File(buffer, "inverted.png"),
        )

    @commands.command(aliases=("iphone10",))
    @commands.bot_has_permissions(attach_files=True)
    @commands.max_concurrency(5, commands.BucketType.guild)
    async def iphonex(
        self, ctx: SleepyContext, *, image: Annotated["PartialAsset", ImageAssetConverter]
    ) -> None:
        """Fits an image into an iPhone X screen.

        Image can either be a user, custom emoji, sticker,
        link, or attachment. Links and attachments must be
        under 40 MB.

        (Bot Needs: Attach Files)
        """
        async with ctx.typing():
            try:
                image_bytes = await image.read()
            except discord.HTTPException:
                await ctx.send("Downloading the image failed. Try again later?")
                return

            buffer, delta = await backend.make_iphone_x(io.BytesIO(image_bytes))

        await ctx.send(
            f"Requested by: {ctx.author} \N{BULLET} Took {delta:.2f} ms.",
            file=File(buffer, "iphone_x.png"),
        )

    @commands.command(aliases=("needsmorejpeg", "jpegify"))
    @commands.bot_has_permissions(attach_files=True)
    @commands.max_concurrency(5, commands.BucketType.guild)
    async def jpeg(
        self,
        ctx: SleepyContext,
        intensity: Annotated[int, Optional[commands.Range[int, 1, 10]]] = 5,
        *,
        image: Annotated["PartialAsset", ImageAssetConverter],
    ) -> None:
        """JPEGifies an image to an optional intensity.

        Intensity value must be between 1 and 10, inclusive.
        The higher the intensity, the more JPEG the image
        result becomes.

        Image can either be a user, custom emoji, sticker,
        link, or attachment. Links and attachments must be
        under 40 MB.

        (Bot Needs: Attach Files)
        """
        async with ctx.typing():
            try:
                image_bytes = await image.read()
            except discord.HTTPException:
                await ctx.send("Downloading the image failed. Try again later?")
                return

            buffer, delta = await backend.do_jpegify(
                io.BytesIO(image_bytes), quality=11 - intensity
            )

        await ctx.send(
            f"Requested by: {ctx.author} \N{BULLET} Took {delta:.2f} ms.",
            file=File(buffer, "jpegified.jpg"),
        )

    @commands.command(aliases=("eyes",))
    @commands.bot_has_permissions(attach_files=True)
    @commands.max_concurrency(5, commands.BucketType.guild)
    async def lensflareeyes(
        self,
        ctx: SleepyContext,
        colour: Annotated[Colour, Optional[Colour]] = Colour.red(),
        *,
        image: Annotated["PartialAsset", ImageAssetConverter],
    ) -> None:
        """Places lensflares of a given colour on human eyes.

        Colour can either be a name, 6 digit hex value prefixed
        with either a `0x`, `#`, or `0x#`; or CSS RGB function
        (e.g. `rgb(103, 173, 242)`).

        Image can either be a user, custom emoji, sticker,
        link, or attachment. Links and attachments must be
        under 40 MB.

        (Bot Needs: Attach Files)
        """
        async with ctx.typing():
            try:
                image_bytes = await image.read()

                buffer, delta = await backend.do_lensflare_eyes(
                    io.BytesIO(image_bytes), colour=colour.to_rgb()
                )
            except discord.HTTPException:
                await ctx.send("Downloading the image failed. Try again later?")
                return
            except RuntimeError:
                await ctx.send("I didn't detect any eyes.")
                return

        await ctx.send(
            f"Requested by: {ctx.author} \N{BULLET} Took {delta:.2f} ms.",
            file=File(buffer, "lensflareeyes.jpg"),
        )

    @commands.command(aliases=("magic",))
    @commands.bot_has_permissions(attach_files=True)
    @commands.max_concurrency(5, commands.BucketType.guild)
    async def magik(
        self,
        ctx: SleepyContext,
        intensity: Annotated[int, Optional[commands.Range[int, 1, 25]]] = 1,
        *,
        image: Annotated["PartialAsset", ImageAssetConverter],
    ) -> None:
        """Heavily warps an image to an optional intensity.

        Intensity value must be between 1 and 25, inclusive.
        The higher the intensity, the more warped the image
        result becomes.

        Image can either be a user, custom emoji, sticker,
        link, or attachment. Links and attachments must be
        under 40 MB.

        (Bot Needs: Attach Files)
        """
        async with ctx.typing():
            try:
                resp = await ctx.get(
                    "https://nekobot.xyz/api/imagegen?type=magik&raw=1",
                    image=str(image),
                    intensity=intensity,
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
            file=File(io.BytesIO(resp), "magik.png"),
        )

    @commands.command(aliases=("colours", "colors"))
    @commands.bot_has_permissions(attach_files=True)
    @commands.max_concurrency(5, commands.BucketType.guild)
    async def palette(
        self, ctx: SleepyContext, *, image: Annotated["PartialAsset", ImageAssetConverter]
    ) -> None:
        """Shows the five most prominent colours in an image.

        Image can either be a user, custom emoji, sticker,
        link, or attachment. Links and attachments must be
        under 40 MB.

        (Bot Needs: Attach Files)
        """
        async with ctx.typing():
            try:
                image_bytes = await image.read()
            except discord.HTTPException:
                await ctx.send("Downloading the image failed. Try again later?")
                return

            buffer, delta = await backend.make_palette(io.BytesIO(image_bytes))

        await ctx.send(
            f"Requested by: {ctx.author} \N{BULLET} Took {delta:.2f} ms.",
            file=File(buffer, "palette.png"),
        )

    @commands.command(aliases=("phcomment", "phc"))
    @commands.guild_only()
    @commands.bot_has_permissions(attach_files=True)
    @commands.max_concurrency(5, commands.BucketType.guild)
    async def pornhubcomment(
        self,
        ctx: SleepyContext,
        user: Annotated[discord.Member, Optional[discord.Member]] = commands.Author,
        *,
        text: Annotated[str, commands.clean_content(fix_channel_mentions=True)],
    ) -> None:
        """Generates a fake Pr0nhub comment from the specified user.

        User can either be a name, ID, or mention.

        (Bot Needs: Attach Files)

        **EXAMPLE:**
        ```
        pornhubcomment hitchedsyringe This isn't free Discord Nitro.
        ```
        """
        async with ctx.typing():
            try:
                avatar_bytes = await user.display_avatar.with_format("png").read()
            except discord.HTTPException:
                await ctx.send("Downloading the user's avatar failed. Try again later?")
                return

            buffer, delta = await backend.make_pornhub_comment(
                user.display_name, io.BytesIO(avatar_bytes), text
            )

        await ctx.send(
            f"Requested by: {ctx.author} \N{BULLET} Took {delta:.2f} ms.",
            file=File(buffer, "pornhub_comment.png"),
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
    async def robloxcancel(self, ctx: SleepyContext, *, user: discord.Member) -> None:
        """Cancels someone for being poor on bloxburg.

        User can either be a name, ID, or mention.

        (Bot Needs: Attach Files)

        **EXAMPLE:**
        ```
        robloxcancel hitchedsyringe
        ```
        """
        async with ctx.typing():
            try:
                avatar_bytes = await user.display_avatar.with_format("png").read()
            except discord.HTTPException:
                await ctx.send("Downloading the user's avatar failed. Try again later?")
                return

            buffer, delta = await backend.make_roblox_cancel_meme(
                io.BytesIO(avatar_bytes), user.name, user.discriminator
            )

        await ctx.send(
            f"Requested by: {ctx.author} \N{BULLET} Took {delta:.2f} ms.",
            file=File(buffer, "roblox_cancel.png"),
        )

    @commands.command()
    @commands.guild_only()
    @commands.bot_has_permissions(embed_links=True, attach_files=True)
    @commands.max_concurrency(5, commands.BucketType.guild)
    async def ship(
        self,
        ctx: SleepyContext,
        first_user: discord.Member,
        second_user: discord.Member = commands.Author,
    ) -> None:
        """Ships two users.

        Users can either be a name, ID, or mention.

        If no second user is specified, then the second
        user will default to you.

        (Bot Needs: Embed Links and Attach Files)

        **EXAMPLES:**
        ```bnf
        <1> ship hitchedsyringe
        <2> ship hitchedsyringe Sleepy#5396
        ```
        """
        if first_user == second_user:
            await ctx.send("You cannot ship the same user.")
            return

        async with ctx.typing():
            try:
                avatar1_bytes = await first_user.display_avatar.with_format("png").read()
                avatar2_bytes = await second_user.display_avatar.with_format("png").read()
            except discord.HTTPException:
                await ctx.send("Downloading the avatars failed. Try again later?")
                return

            buffer, delta = await backend.make_ship(
                first_user.display_name,
                io.BytesIO(avatar1_bytes),
                second_user.display_name,
                io.BytesIO(avatar2_bytes),
                first_user.id ^ second_user.id,
            )

        await ctx.send(
            f"Requested by: {ctx.author} \N{BULLET} Took {delta:.2f} ms.",
            file=File(buffer, "ship.png"),
        )

    @commands.command(aliases=("soyjacks", "soyjak", "soyjack"))
    @commands.bot_has_permissions(attach_files=True)
    @commands.max_concurrency(5, commands.BucketType.guild)
    async def soyjaks(
        self, ctx: SleepyContext, *, image: Annotated["PartialAsset", ImageAssetConverter]
    ) -> None:
        """Generates a consoomer soyjaks pointing meme.

        Image can either be a user, custom emoji, sticker,
        link, or attachment. Links and attachments must be
        under 40 MB.

        (Bot Needs: Attach Files)
        """
        async with ctx.typing():
            try:
                image_bytes = await image.read()
            except discord.HTTPException:
                await ctx.send("Downloading the image failed. Try again later?")
                return

            buffer, delta = await backend.make_pointing_soyjaks_meme(
                io.BytesIO(image_bytes)
            )

        await ctx.send(
            f"Requested by: {ctx.author} \N{BULLET} Took {delta:.2f} ms.",
            file=File(buffer, "soyjak.png"),
        )

    # Long and strict RL due to Nekobot processing.
    @commands.command()
    @commands.bot_has_permissions(attach_files=True)
    @commands.max_concurrency(2, commands.BucketType.guild)
    @commands.cooldown(1, 40, commands.BucketType.member)
    async def stickbug(
        self, ctx: SleepyContext, *, image: Annotated["PartialAsset", ImageAssetConverter]
    ) -> None:
        """Generates a stickbug meme.

        Image can either be a user, custom emoji, sticker,
        link, or attachment. Links and attachments must be
        under 40 MB.

        (Bot Needs: Attach Files)
        """
        async with ctx.typing():
            try:
                resp = await ctx.get(
                    "https://nekobot.xyz/api/imagegen?type=stickbug&raw=1", url=str(image)
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

        video_bytes = await ctx.get(resp["message"])

        await ctx.send(
            f"Requested by: {ctx.author} \N{BULLET} Powered by nekobot.xyz",
            file=File(io.BytesIO(video_bytes), "stickbug.mp4"),
        )

    @commands.command()
    @commands.bot_has_permissions(attach_files=True)
    @commands.max_concurrency(5, commands.BucketType.guild)
    async def swirl(
        self,
        ctx: SleepyContext,
        intensity: Annotated[int, Optional[commands.Range[int, 1, 15]]] = 5,
        *,
        image: Annotated["PartialAsset", ImageAssetConverter],
    ) -> None:
        """Swirls an image to an optional intensity.

        Intensity value must be between 1 and 15, inclusive.
        The higher the intensity, the more swirly the image
        result becomes.

        Image can either be a user, custom emoji, sticker,
        link, or attachment. Links and attachments must be
        under 40 MB.

        (Bot Needs: Attach Files)
        """
        async with ctx.typing():
            try:
                image_bytes = await image.read()
            except discord.HTTPException:
                await ctx.send("Downloading the image failed. Try again later?")
                return

            buffer, delta = await backend.do_swirl(
                io.BytesIO(image_bytes), intensity=intensity * 2.5
            )

        await ctx.send(
            f"Requested by: {ctx.author} \N{BULLET} Took {delta:.2f} ms.",
            file=File(buffer, "swirl.png"),
        )

    @commands.command(aliases=("tti",), usage="text: <text> [options...]")
    @commands.bot_has_permissions(attach_files=True)
    async def texttoimage(self, ctx: SleepyContext, *, options: TTIFlags) -> None:
        """Converts text into an image.

        This command's interface is similar to Discord's slash commands.
        Values with spaces must be surrounded by quotation marks.

        Options can be given in any order and, unless otherwise stated,
        are assumed to be optional.

        The following options are valid:

        `text: <text>` **Required**
        > The text to convert into an image.
        `font: <font>`
        > The font to use.
        > This is case-sensitive.
        > Valid fonts: `Arimo-Bold`, `Arimo-Regular`, `Catamaran-Regular`,
        > `Lustria-Regular`, `Roboto-Bold`, `Roboto-Medium`, `Roboto-Regular`,
        > `SourceSerifPro-SemiBold`
        > Defaults to `Arimo-Bold` if omitted.
        `[text-colour|text-color]: <colour>`
        > The text colour.
        > This can either be a name, 6 digit hex value prefixed with either a
        > `0x`, `#`, or `0x#`; or CSS RGB function (e.g. `rgb(103, 173, 242)`).
        > Defaults to `#99AAB5` if omitted.
        `[bg-colour|bg-color]: <colour>`
        > The background colour.
        > This can either be a name, 6 digit hex value prefixed with either a
        > `0x`, `#`, or `0x#`; or CSS RGB function (e.g. `rgb(103, 173, 242)`).
        > If omitted, the background will be transparent.
        `size: <integer>`
        > The size of the text.
        > Must be between 20 and 50, inclusive.
        > Defaults to `35` if omitted.

        (Bot Needs: Attach Files)
        """
        kwargs = _as_argparse_dict(options)
        kwargs["text_colour"] = kwargs["text_colour"].to_rgb()

        if kwargs["bg_colour"] is not None:
            kwargs["bg_colour"] = kwargs["bg_colour"].to_rgb()

        async with ctx.typing():
            try:
                buffer, delta = await backend.make_text_image(**kwargs)
            except OSError:
                await ctx.send("Something went wrong while reading the font.")
                return

        await ctx.send(
            f"Requested by: {ctx.author} \N{BULLET} Took {delta:.2f} ms.",
            file=File(buffer, "tti.png"),
        )

    @commands.command()
    @commands.bot_has_permissions(attach_files=True)
    @commands.max_concurrency(5, commands.BucketType.guild)
    async def threats(
        self, ctx: SleepyContext, *, image: Annotated["PartialAsset", ImageAssetConverter]
    ) -> None:
        """Generates a "three threats to society" meme.

        Image can either be a user, custom emoji, sticker,
        link, or attachment. Links and attachments must be
        under 40 MB.

        (Bot Needs: Attach Files)
        """
        async with ctx.typing():
            try:
                image_bytes = await image.read()
            except discord.HTTPException:
                await ctx.send("Downloading the image failed. Try again later?")
                return

            buffer, delta = await backend.make_threats_meme(io.BytesIO(image_bytes))

        await ctx.send(
            f"Requested by: {ctx.author} \N{BULLET} Took {delta:.2f} ms.",
            file=File(buffer, "threats.png"),
        )

    @commands.command()
    @commands.bot_has_permissions(attach_files=True)
    @commands.max_concurrency(5, commands.BucketType.guild)
    async def trapcard(
        self,
        ctx: SleepyContext,
        title: Annotated[str, commands.clean_content(fix_channel_mentions=True)],
        image: Annotated["PartialAsset", ImageAssetConverter],
        *,
        flavour_text: Annotated[str, commands.clean_content(fix_channel_mentions=True)],
    ) -> None:
        """Generates a fake Yu-Gi-Oh! trap card.

        Image can either be a user, custom emoji, sticker,
        link, or attachment. Links and attachments must be
        under 40 MB.

        If the title requires spaces, you must surround it
        in quotation marks.

        (Bot Needs: Attach Files)
        """
        async with ctx.typing():
            try:
                image_bytes = await image.read()
            except discord.HTTPException:
                await ctx.send("Downloading the image failed. Try again later?")
                return

            buffer, delta = await backend.make_trapcard(
                title, flavour_text, io.BytesIO(image_bytes)
            )

        await ctx.send(
            f"Requested by: {ctx.author} \N{BULLET} Took {delta:.2f} ms.",
            file=File(buffer, "trapcard.png"),
        )

    @commands.command()
    @commands.bot_has_permissions(attach_files=True)
    async def tucker(
        self, ctx: SleepyContext, *, image: Annotated["PartialAsset", ImageAssetConverter]
    ) -> None:
        """Generates a live Tucker reaction meme.

        Image can either be a user, custom emoji, sticker,
        link, or attachment. Links and attachments must be
        under 40 MB.

        (Bot Needs: Attach Files)
        """
        async with ctx.typing():
            try:
                image_bytes = await image.read()
            except discord.HTTPException:
                await ctx.send("Downloading the image failed. Try again later?")
                return

            buffer, delta = await backend.make_live_tucker_reaction_meme(
                io.BytesIO(image_bytes)
            )

        await ctx.send(
            f"Requested by: {ctx.author} \N{BULLET} Took {delta:.2f} ms.",
            file=File(buffer, "live_tucker_reaction.png"),
        )

    @commands.command()
    @commands.guild_only()
    @commands.bot_has_permissions(attach_files=True)
    async def tweet(
        self,
        ctx: SleepyContext,
        user: Annotated[discord.Member, Optional[discord.Member]] = commands.Author,
        *,
        text: Annotated[str, commands.clean_content(fix_channel_mentions=True)],
    ) -> None:
        """Generates a fake Tweet from the specified user.

        User can either be a name, ID, or mention.

        (Bot Needs: Attach Files)

        **EXAMPLE:**
        ```
        tweet hitchedsyringe Twitter for Sleepy
        ```
        """
        async with ctx.typing():
            try:
                avatar_bytes = await user.display_avatar.with_format("png").read()
            except discord.HTTPException:
                await ctx.send("Downloading the user's avatar failed. Try again later?")
                return

            buffer, delta = await backend.make_tweet(
                user.name, user.display_name, io.BytesIO(avatar_bytes), text
            )

        await ctx.send(
            f"Requested by: {ctx.author} \N{BULLET} Took {delta:.2f} ms.",
            file=File(buffer, "tweet.png"),
        )

    @commands.command(aliases=("www",))
    @commands.guild_only()
    @commands.bot_has_permissions(attach_files=True)
    @commands.max_concurrency(5, commands.BucketType.guild)
    async def whowouldwin(
        self,
        ctx: SleepyContext,
        left_image: Annotated["PartialAsset", ImageAssetConverter],
        right_image: Annotated["PartialAsset", ImageAssetConverter],
    ) -> None:
        """Generates a "who would win" meme.

        Images can either be a user, custom emoji, link, or
        attachment. Links and attachments must be under 40
        MB.

        (Bot Needs: Attach Files)
        """
        async with ctx.typing():
            try:
                left_bytes = await left_image.read()
                right_bytes = await right_image.read()
            except discord.HTTPException:
                await ctx.send("Downloading the images failed. Try again later?")
                return

            buffer, delta = await backend.make_who_would_win_meme(
                io.BytesIO(left_bytes), io.BytesIO(right_bytes)
            )

        await ctx.send(
            f"Requested by: {ctx.author} \N{BULLET} Took {delta:.2f} ms.",
            file=File(buffer, "who_would_win.png"),
        )

    @commands.command(aliases=("ytcomment", "ytc"))
    @commands.guild_only()
    @commands.bot_has_permissions(attach_files=True)
    @commands.max_concurrency(5, commands.BucketType.guild)
    async def youtubecomment(
        self,
        ctx: SleepyContext,
        user: Annotated[discord.Member, Optional[discord.Member]] = commands.Author,
        *,
        text: Annotated[str, commands.clean_content(fix_channel_mentions=True)],
    ) -> None:
        """Generates a fake YouTube comment from the specified user.

        User can either be a name, ID, or mention.

        (Bot Needs: Attach Files)

        **EXAMPLE:**
        ```
        youtubecomment hitchedsyringe Epic video.
        ```
        """
        async with ctx.typing():
            try:
                avatar_bytes = await user.display_avatar.with_format("png").read()
            except discord.HTTPException:
                await ctx.send("Downloading the user's avatar failed. Try again later?")
                return

            buffer, delta = await backend.make_youtube_comment(
                user.display_name, io.BytesIO(avatar_bytes), text
            )

        await ctx.send(
            f"Requested by: {ctx.author} \N{BULLET} Took {delta:.2f} ms.",
            file=File(buffer, "youtube_comment.png"),
        )
