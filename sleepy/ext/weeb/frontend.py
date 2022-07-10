"""
Copyright (c) 2018-present HitchedSyringe

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""


from __future__ import annotations

# fmt: off
__all__ = (
    "Weeb",
)
# fmt: on


import io
import textwrap
from typing import TYPE_CHECKING

import discord
from discord import Colour, Embed, File
from discord.ext import commands
from PIL import GifImagePlugin as GIP, UnidentifiedImageError
from PIL.Image import DecompressionBombError
from typing_extensions import Annotated

from sleepy.converters import (
    ImageAssetConversionFailure,
    ImageAssetConverter,
    ImageAssetTooLarge,
)
from sleepy.menus import EmbedSource
from sleepy.utils import plural

from . import backend

if TYPE_CHECKING:
    from sleepy.context import Context as SleepyContext, GuildContext
    from sleepy.mimics import PartialAsset


# ネックビアードコグ
class Weeb(
    commands.Cog,
    command_attrs={
        "cooldown": commands.CooldownMapping.from_cooldown(
            2, 5, commands.BucketType.member
        ),
    },
):
    """Commands having to do with weeaboo stuff.

    Pretty sure the name was implicit.
    """

    ICON: str = "\N{SUSHI}"

    async def cog_command_error(self, ctx: SleepyContext, error: Exception) -> None:
        error = getattr(error, "original", error)

        if isinstance(error, (ImageAssetConversionFailure, UnidentifiedImageError)):
            await ctx.send(
                "The user, custom emoji, image attachment, or image link was invalid."
            )
            ctx._already_handled_error = True
        elif isinstance(error, ImageAssetTooLarge):
            await ctx.send(
                f"Image must not exceed {error.max_filesize / 1e6:.0f} MB in size."
            )
            ctx._already_handled_error = True
        elif isinstance(error, DecompressionBombError):
            await ctx.send("Go be Ted Kaczynski somewhere else.")
            ctx._already_handled_error = True
        elif isinstance(error, (commands.BadArgument, commands.MaxConcurrencyReached)):
            await ctx.send(error)  # type: ignore
            ctx._already_handled_error = True

    def cog_load(self) -> None:
        from PIL import __version__ as pillow_version

        # This is proofed against .dev[x] versions and release candidates.
        major, minor, *_ = pillow_version.split(".")

        if int(major) >= 9 and int(minor) >= 1:
            # This modifies PIL's GIF loading strategy on the global level.
            # This needs to be done since `nichijou` breaks on Pillow 9.x.
            # Unfortunately, this can only be done on Pillow 9.1+. Pillow
            # 9.0 people are on their own on this front, since there's no
            # other way to modify the GIF loading strategy otherwise.
            self._original_gif_loading_strategy = GIP.LOADING_STRATEGY  # type: ignore
            GIP.LOADING_STRATEGY = GIP.LoadingStrategy.RGB_AFTER_DIFFERENT_PALETTE_ONLY  # type: ignore

    def cog_unload(self) -> None:
        if hasattr(self, "_original_gif_loading_strategy"):
            GIP.LOADING_STRATEGY = self._original_gif_loading_strategy  # type: ignore

    @staticmethod
    async def send_nekobot_image_embed(ctx: SleepyContext, *, image_type: str) -> None:
        resp = await ctx.get("https://nekobot.xyz/api/image", type=image_type)

        embed = Embed(colour=Colour(resp["color"]))
        embed.set_image(url=resp["message"])
        embed.set_footer(text="Powered by nekobot.xyz")

        await ctx.send(embed=embed)

    @commands.command(aliases=("animesearch",))
    @commands.bot_has_permissions(embed_links=True)
    @commands.cooldown(1, 5, commands.BucketType.member)
    async def anime(self, ctx: GuildContext, *, query: Annotated[str, str.lower]) -> None:
        """Searches for an anime on MyAnimeList and returns the top 10 results.

        The search results displayed are based on whether or not this command
        was executed in an NSFW channel.

        **EXAMPLE:**
        ```
        anime K-ON!
        ```
        """
        if len(query) < 3:
            await ctx.send("Search queries must be at least 3 characters long.")
            return

        search_url = "https://api.jikan.moe/v4/anime?limit=10"

        if ctx.guild is not None and not ctx.channel.is_nsfw():
            search_url += "&genre=9,12,49&genre_exclude=1"

        await ctx.typing()

        search = await ctx.get(search_url, cache__=True, q=query)

        results = search["data"]

        if not results:
            await ctx.send("No results found.")
            return

        embeds = []

        for item in results:
            id_ = item["mal_id"]

            embed = Embed(
                title=f"`{id_}` - {item['title']}", colour=0x2F3136, url=item["url"]
            )
            embed.set_thumbnail(url=item["images"]["webp"]["large_image_url"])
            embed.set_footer(text="Powered by jikan.moe")

            if item["airing"]:
                embed.set_author(name="Currently Ongoing")
            else:
                embed.set_author(name=f"{plural(item['episodes'] or 0, ',d'):Episode}")

            embed.description = (
                f"\U0001F1EC\U0001F1E7 English: {item['title_english'] or 'N/A'}"
                f"\n\U0001F1EF\U0001F1F5 Japanese: {item['title_japanese'] or 'N/A'}\n\n"
                + textwrap.shorten(item["synopsis"] or "No synopsis given.", 1990)
            )

            embed.add_field(name="Type", value=item["type"])
            embed.add_field(name="Status", value=item["status"])
            embed.add_field(name="Aired", value=item["aired"]["string"])
            embed.add_field(name="Duration", value=item["duration"])
            embed.add_field(name="Rating", value=item["rating"])
            embed.add_field(
                name="Genres",
                value="\n".join(g["name"] for g in item["genres"]) or "None",
            )
            embed.add_field(
                name="Studios",
                value="\n".join(s["name"] for s in item["studios"]) or "None",
            )
            embed.add_field(
                name="Producers",
                value="\n".join(p["name"] for p in item["producers"]) or "None",
            )
            embed.add_field(
                name="Licensors",
                value="\n".join(i["name"] for i in item["licensors"]) or "None",
            )
            embed.add_field(
                name=f"Score \N{BULLET} **Rank {item['rank'] or 'N/A'}**",
                value=f"{item['score'] or 0}/10 ({item['scored_by'] or 0:,} scored)",
            )
            embed.add_field(
                name=f"Members \N{BULLET} **Rank {item['popularity'] or 'N/A'}**",
                value=f"{item['members']:,} ({item['favorites']:,} favourited)",
            )

            embeds.append(embed)

        await ctx.paginate(EmbedSource(embeds))

    @commands.command()
    @commands.bot_has_permissions(embed_links=True)
    async def animecoffee(self, ctx: SleepyContext) -> None:
        """Sends a random image of an anime girl drinking coffee.

        (Bot Needs: Embed Links)
        """
        await self.send_nekobot_image_embed(ctx, image_type="coffee")

    @commands.command()
    @commands.cooldown(1, 8, commands.BucketType.member)
    async def animeface(
        self,
        ctx: SleepyContext,
        *,
        image: PartialAsset = commands.parameter(converter=ImageAssetConverter),
    ) -> None:
        """Detects and highlights anime faces in an image.

        Image can either be a user, custom emoji, link, or
        attachment. Links and attachments must be under 40
        MB.

        (Bot Needs: Attach Files)
        """
        async with ctx.typing():
            try:
                image_bytes = await image.read()

                (count, buffer), delta = await backend.detect_anime_faces(
                    io.BytesIO(image_bytes)
                )
            except discord.HTTPException:
                await ctx.send("Downloading the image failed. Try again later?")
                return
            except RuntimeError:
                await ctx.send("I didn't detect any anime faces.")
                return

        await ctx.send(
            f"I detected **{count}** anime faces in this image."
            f"\nRequested by: {ctx.author} \N{BULLET} Took {delta:.2f} ms",
            file=File(buffer, "highlighted_anime_faces.png"),
        )

    @commands.command()
    @commands.bot_has_permissions(embed_links=True)
    async def animefood(self, ctx: SleepyContext) -> None:
        """Sends a random image of anime food.

        (Bot Needs: Embed Links)
        """
        await self.send_nekobot_image_embed(ctx, image_type="food")

    @commands.command()
    @commands.bot_has_permissions(attach_files=True)
    @commands.cooldown(1, 5, commands.BucketType.member)
    async def awooify(
        self,
        ctx: SleepyContext,
        *,
        image: PartialAsset = commands.parameter(converter=ImageAssetConverter),
    ) -> None:
        """Awooifies an image.

        Image can either be a user, custom emoji, link, or
        attachment. Links and attachments must be under 40
        MB.

        (Bot Needs: Attach Files)
        """
        async with ctx.typing():
            try:
                image_bytes = await image.read()
            except discord.HTTPException:
                await ctx.send("Downloading the image failed. Try again later?")
                return

            buffer, delta = await backend.do_awooify(io.BytesIO(image_bytes))

        await ctx.send(
            f"Requested by: {ctx.author} \N{BULLET} Took {delta:.2f} ms",
            file=File(buffer, "awooify.png"),
        )

    @commands.command(aliases=("france",))
    @commands.bot_has_permissions(attach_files=True)
    @commands.cooldown(1, 5, commands.BucketType.member)
    async def baguette(
        self,
        ctx: SleepyContext,
        *,
        image: PartialAsset = commands.parameter(converter=ImageAssetConverter),
    ) -> None:
        """Turns an image into an anime girl eating a baguette.

        Image can either be a user, custom emoji, link, or
        attachment. Links and attachments must be under 40
        MB.

        (Bot Needs: Attach Files)
        """
        async with ctx.typing():
            try:
                image_bytes = await image.read()
            except discord.HTTPException:
                await ctx.send("Downloading the image failed. Try again later?")
                return

            buffer, delta = await backend.make_baguette_meme(io.BytesIO(image_bytes))

        await ctx.send(
            f"Requested by: {ctx.author} \N{BULLET} Took {delta:.2f} ms",
            file=File(buffer, "baguette.png"),
        )

    @commands.command(aliases=("bp",))
    @commands.bot_has_permissions(attach_files=True)
    @commands.cooldown(1, 5, commands.BucketType.member)
    async def bodypillow(
        self,
        ctx: SleepyContext,
        *,
        image: PartialAsset = commands.parameter(converter=ImageAssetConverter),
    ) -> None:
        """Turns an image into an anime body pillow.

        Image can either be a user, custom emoji, link, or
        attachment. Links and attachments must be under 40
        MB.

        (Bot Needs: Attach Files)
        """
        async with ctx.typing():
            try:
                image_bytes = await image.read()
            except discord.HTTPException:
                await ctx.send("Downloading the image failed. Try again later?")
                return

            buffer, delta = await backend.make_bodypillow_meme(io.BytesIO(image_bytes))

        await ctx.send(
            f"Requested by: {ctx.author} \N{BULLET} Took {delta:.2f} ms",
            file=File(buffer, "bodypillow.png"),
        )

    # Commented out because the API this is powered by is
    # currently on hiatus until v3 is completed, in an
    # effort to respect content creators and their work,
    # since the API provided these images uncredited.
    # This will be uncommented when the API comes back,
    # and I'll make sure to include the credits the API
    # provides in the resulting embed.
    # @commands.command(aliases=("hatsunemiku",))
    # @commands.bot_has_permissions(embed_links=True)
    # async def miku(self, ctx: SleepyContext) -> None:
    #     """Shows a random image of Hatsune Miku.

    #     (Bot Needs: Embed Links)
    #     """
    #     resp = await ctx.get("https://miku-for.us/api/v2/random")

    #     embed = Embed(colour=0x2F3136)
    #     embed.set_image(url=resp["url"])
    #     embed.set_footer(text="Powered by miku-for.us")

    #     await ctx.send(embed=embed)

    @commands.command()
    @commands.bot_has_permissions(attach_files=True)
    @commands.cooldown(1, 5, commands.BucketType.member)
    async def hifumifact(
        self,
        ctx: SleepyContext,
        *,
        text: Annotated[str, commands.clean_content(fix_channel_mentions=True)],
    ) -> None:
        """Generates an image of Hifumi spitting straight facts.

        (Bot Needs: Attach Files)
        """
        async with ctx.typing():
            buffer, delta = await backend.make_hifumi_fact_meme(text)

        await ctx.send(
            f"Requested by: {ctx.author} \N{BULLET} Took {delta:.2f} ms",
            file=File(buffer, "hifumi_fact.png"),
        )

    @commands.command()
    @commands.bot_has_permissions(embed_links=True)
    async def holo(self, ctx: SleepyContext) -> None:
        """Sends a random image of Holo from *Spice and Wolf*.

        (Bot Needs: Embed Links)
        """
        await self.send_nekobot_image_embed(ctx, image_type="holo")

    @commands.command()
    @commands.bot_has_permissions(embed_links=True)
    async def kanna(self, ctx: SleepyContext) -> None:
        """Sends a random image of Kanna from *Miss Kobayashi's Dragon Maid*.

        (Bot Needs: Embed Links)
        """
        await self.send_nekobot_image_embed(ctx, image_type="kanna")

    @commands.command()
    @commands.bot_has_permissions(attach_files=True)
    @commands.cooldown(1, 5, commands.BucketType.member)
    async def kannafact(
        self,
        ctx: SleepyContext,
        *,
        text: Annotated[str, commands.clean_content(fix_channel_mentions=True)],
    ) -> None:
        """Generates an image of Kanna spitting straight facts.

        (Bot Needs: Attach Files)
        """
        async with ctx.typing():
            buffer, delta = await backend.make_kanna_fact_meme(text)

        await ctx.send(
            f"Requested by: {ctx.author} \N{BULLET} Took {delta:.2f} ms",
            file=File(buffer, "kanna_fact.png"),
        )

    @commands.command(aliases=("kemo",))
    @commands.bot_has_permissions(embed_links=True)
    async def kemonomimi(self, ctx: SleepyContext) -> None:
        """Sends a random image of a kemonomimi character.

        (Bot Needs: Embed Links)
        """
        await self.send_nekobot_image_embed(ctx, image_type="kemonomimi")

    @commands.command()
    @commands.bot_has_permissions(attach_files=True)
    @commands.cooldown(1, 5, commands.BucketType.member)
    async def lolice(
        self,
        ctx: SleepyContext,
        *,
        image: PartialAsset = commands.parameter(converter=ImageAssetConverter),
    ) -> None:
        """Submits an image to the lolice.

        Image can either be a user, custom emoji, link, or
        attachment. Links and attachments must be under 40
        MB.

        (Bot Needs: Attach Files)
        """
        async with ctx.typing():
            try:
                image_bytes = await image.read()
            except discord.HTTPException:
                await ctx.send("Downloading the image failed. Try again later?")
                return

            buffer, delta = await backend.make_lolice_meme(io.BytesIO(image_bytes))

        await ctx.send(
            f"Requested by: {ctx.author} \N{BULLET} Took {delta:.2f} ms",
            file=File(buffer, "lolice.png"),
        )

    @commands.command(aliases=("mangasearch",))
    @commands.bot_has_permissions(embed_links=True)
    @commands.cooldown(1, 5, commands.BucketType.member)
    async def manga(self, ctx: GuildContext, *, query: Annotated[str, str.lower]) -> None:
        """Searches for a manga on MyAnimeList and returns the top 10 results.

        The search results displayed are based on whether or not this command
        was executed in an NSFW channel.

        **EXAMPLE:**
        ```
        manga Berserk
        ```
        """
        if len(query) < 3:
            await ctx.send("Search queries must be at least 3 characters long.")
            return

        search_url = "https://api.jikan.moe/v4/manga?limit=10"

        if ctx.guild is not None and not ctx.channel.is_nsfw():
            search_url += "&genre=9,12,49&genre_exclude=1"

        await ctx.typing()

        search = await ctx.get(search_url, cache__=True, q=query)
        results = search["data"]

        if not results:
            await ctx.send("No results found.")
            return

        embeds = []

        for item in results:
            id_ = item["mal_id"]

            embed = Embed(
                title=f"`{id_}` - {item['title']}", colour=0x2F3136, url=item["url"]
            )
            embed.set_thumbnail(url=item["images"]["webp"]["large_image_url"])
            embed.set_footer(text="Powered by jikan.moe")

            if item["publishing"]:
                embed.set_author(name="Currently Ongoing")
            else:
                embed.set_author(
                    name=f"{plural(item['chapters'] or 0, ',d'):Chapter}"
                    f" \N{BULLET} {plural(item['volumes'] or 0, ',d'):Volume}"
                )

            embed.description = (
                f"\U0001F1EC\U0001F1E7 English: {item['title_english'] or 'N/A'}"
                f"\n\U0001F1EF\U0001F1F5 Japanese: {item['title_japanese'] or 'N/A'}\n\n"
                + textwrap.shorten(item["synopsis"] or "No synopsis given.", 1990)
            )

            embed.add_field(name="Type", value=item["type"])
            embed.add_field(name="Status", value=item["status"])
            embed.add_field(name="Published", value=item["published"]["string"])
            embed.add_field(
                name="Genres",
                value="\n".join(g["name"] for g in item["genres"]) or "None",
            )
            embed.add_field(
                name="Authors",
                value="\n".join(a["name"] for a in item["authors"]) or "None",
            )
            embed.add_field(
                name="Serializations",
                value="\n".join(s["name"] for s in item["serializations"]) or "None",
            )
            embed.add_field(
                name=f"Score \N{BULLET} **Rank {item['rank'] or 'N/A'}**",
                value=f"{item['scored'] or 0}/10 ({item['scored_by'] or 0:,} scored)",
            )
            embed.add_field(
                name=f"Members \N{BULLET} **Rank {item['popularity'] or 'N/A'}**",
                value=f"{item['members']:,} ({item['favorites'] or 0:,} favourited)",
            )

            embeds.append(embed)

        await ctx.paginate(EmbedSource(embeds))

    @commands.command(aliases=("catgirl", "nekomimi"))
    @commands.bot_has_permissions(embed_links=True)
    async def neko(self, ctx: SleepyContext) -> None:
        """Sends a random image of a catgirl.

        (Bot Needs: Embed Links)
        """
        await self.send_nekobot_image_embed(ctx, image_type="neko")

    @commands.command()
    @commands.bot_has_permissions(attach_files=True)
    @commands.cooldown(1, 8, commands.BucketType.member)
    async def nichijou(
        self,
        ctx: SleepyContext,
        *,
        text: Annotated[str, commands.clean_content(fix_channel_mentions=True)],
    ):
        r""" "YOU. ARE. A. ___\_\_\_."

        (Bot Needs: Attach Files)
        """
        async with ctx.typing():
            buffer, delta = await backend.make_nichijou_gif_meme(text)

        await ctx.send(
            f"Requested by: {ctx.author} \N{BULLET} Took {delta:.2f} ms",
            file=File(buffer, "nichijou.gif"),
        )

    @commands.command()
    @commands.bot_has_permissions(attach_files=True)
    @commands.cooldown(1, 5, commands.BucketType.member)
    async def ritsudirt(
        self,
        ctx: SleepyContext,
        *,
        image: PartialAsset = commands.parameter(converter=ImageAssetConverter),
    ) -> None:
        """Generates a Ritsu dirt meme.

        Image can either be a user, custom emoji, link, or
        attachment. Links and attachments must be under 40
        MB.

        (Bot Needs: Attach Files)
        """
        async with ctx.typing():
            try:
                image_bytes = await image.read()
            except discord.HTTPException:
                await ctx.send("Downloading the image failed. Try again later?")
                return

            buffer, delta = await backend.make_ritsu_dirt_meme(io.BytesIO(image_bytes))

        await ctx.send(
            f"Requested by: {ctx.author} \N{BULLET} Took {delta:.2f} ms",
            file=File(buffer, "ritsu_dirt.png"),
        )

    @commands.command()
    @commands.bot_has_permissions(attach_files=True)
    @commands.cooldown(1, 5, commands.BucketType.member)
    async def ritsufact(
        self,
        ctx: SleepyContext,
        *,
        text: Annotated[str, commands.clean_content(fix_channel_mentions=True)],
    ) -> None:
        """Generates an image of Ritsu spitting straight facts.

        (Bot Needs: Attach Files)
        """
        async with ctx.typing():
            buffer, delta = await backend.make_ritsu_fact_meme(text)

        await ctx.send(
            f"Requested by: {ctx.author} \N{BULLET} Took {delta:.2f} ms",
            file=File(buffer, "ritsu_fact.png"),
        )

    @commands.command()
    @commands.bot_has_permissions(attach_files=True)
    @commands.cooldown(1, 5, commands.BucketType.member)
    async def trash(
        self,
        ctx: SleepyContext,
        *,
        image: PartialAsset = commands.parameter(converter=ImageAssetConverter),
    ) -> None:
        """Generates a trash waifu meme.

        Image can either be a user, custom emoji, link, or
        attachment. Links and attachments must be under 40
        MB.

        (Bot Needs: Attach Files)
        """
        async with ctx.typing():
            try:
                image_bytes = await image.read()
            except discord.HTTPException:
                await ctx.send("Downloading the image failed. Try again later?")
                return

            buffer, delta = await backend.make_trash_waifu_meme(io.BytesIO(image_bytes))

        await ctx.send(
            f"Requested by: {ctx.author} \N{BULLET} Took {delta:.2f} ms",
            file=File(buffer, "trash_waifu.png"),
        )
