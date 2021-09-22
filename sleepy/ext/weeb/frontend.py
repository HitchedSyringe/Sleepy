"""
Copyright (c) 2018-present HitchedSyringe

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""


__all__ = (
    "Weeb",
)


import io
import textwrap

import discord
from discord import Colour, Embed, File
from discord.ext import commands
from PIL import UnidentifiedImageError
from PIL.Image import DecompressionBombError
from sleepy.converters import (
    ImageAssetConverter,
    ImageAssetConversionFailure,
    ImageAssetTooLarge,
)
from sleepy.http import HTTPRequestFailed
from sleepy.utils import plural

from . import backend
from .templates import TEMPLATES


NEKOBOT_IMAGE_COMMANDS = (
    {
        "name": "animecoffee",
        "help": "Sends a random image of an anime girl drinking coffee.",
        "type": "coffee",
    },
    {
        "name": "animefood",
        "help": "Sends a random image of anime food.",
        "type": "food",
    },
    {
        "name": "holo",
        "help": "Sends a random image of Holo from *Spice and Wolf*.",
    },
    {
        "name": "kemonomimi",
        "aliases": ("kemo",),
        "help": "Sends a random image of a kemonomimi character.",
    },
    {
        "name": "neko",
        "aliases": ("catgirl", "nekomimi"),
        "help": "Sends a random image of a catgirl.",
    },
    {
        "name": "kanna",
        "help": "Sends a random image of Kanna from *Miss Kobayashi's Dragon Maid*.",
    },
)


# ネックビアードコグ
class Weeb(
    commands.Cog,
    command_attrs={"cooldown": commands.Cooldown(2, 5, commands.BucketType.member)}
):
    """Commands having to do with weeaboo stuff.

    Pretty sure the name was implicit.
    """

    def __init__(self):
        # Nekobot commands are handled this way in order to
        # allow for ease in supporting any new image endpoints.
        # (and it also keeps us from having several methods that
        # essentially all run the same code with little variance)
        for attrs in NEKOBOT_IMAGE_COMMANDS:
            attrs["help"] += "\n\n(Bot Needs: Embed Links)"

            # Unfortunately, we have to construct the command
            # this way due to how injection works for this.
            @commands.command(**attrs)
            @commands.bot_has_permissions(embed_links=True)
            async def nekobot_image_command(cog, ctx):
                resp = await ctx.get(
                    "https://nekobot.xyz/api/image",
                    # Can't really get the type any other way...
                    type=ctx.command.__original_kwargs__.get("type", ctx.command.name)
                )

                embed = Embed(colour=Colour(resp["color"]))
                embed.set_image(url=resp["message"])
                embed.set_footer(text="Powered by nekobot.xyz")

                await ctx.send(embed=embed)

            nekobot_image_command.cog = self

            # Make the command will appear in the cog help menu.
            self.__cog_commands__ += (nekobot_image_command,)

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
        elif isinstance(error, (commands.BadArgument, commands.MaxConcurrencyReached)):
            await ctx.send(error)
            error.handled__ = True

    @commands.command(aliases=("animeinfo",))
    @commands.bot_has_permissions(embed_links=True)
    @commands.cooldown(1, 5, commands.BucketType.member)
    async def anime(self, ctx, *, query: str.lower):
        """Shows information about an anime on MyAnimeList.

        The search results displayed are based on whether
        or not this command was executed in an NSFW channel.

        **EXAMPLE:**
        ```
        anime K-ON!
        ```
        """
        if len(query) < 3:
            await ctx.send("Search queries must be at least 3 characters long.")
            return

        search_url = "https://api.jikan.moe/v3/search/anime?limit=1"

        if not ctx.channel.is_nsfw():
            search_url += "&genre=9,12&genre_exclude=1"

        await ctx.trigger_typing()

        try:
            search = await ctx.get(search_url, cache__=True, q=query)
        except HTTPRequestFailed as exc:
            if exc.status == 503:
                await ctx.send("Jikan failed to fetch from MyAnimeList.")
                return

            raise

        try:
            partial = search["results"][0]
        except IndexError:
            await ctx.send("No results found.")
            return

        id_ = partial["mal_id"]

        embed = Embed(
            title=f"`{id_}` - {partial['title']}",
            colour=0x2F3136,
            url=partial["url"]
        )
        embed.set_author(name=f"{plural(partial['episodes'], ',d'):Episode}")
        embed.set_thumbnail(url=partial["image_url"])
        embed.set_footer(text="Powered by jikan.moe")

        embed.add_field(name="Type", value=partial["type"])

        full = await ctx.get(f"https://api.jikan.moe/v3/anime/{id_}/", cache__=True)

        embed.description = (
            f"\U0001F1EC\U0001F1E7 English: {full['title_english'] or 'N/A'}"
            f"\n\U0001F1EF\U0001F1F5 Japanese: {full['title_japanese'] or 'N/A'}\n\n"
            + textwrap.shorten(full["synopsis"] or "No synopsis given.", 1990)
        )

        embed.add_field(name="Status", value=full["status"])
        embed.add_field(name="Aired", value=full["aired"]["string"])
        embed.add_field(name="Duration", value=full["duration"])
        embed.add_field(name="Rating", value=full["rating"])
        embed.add_field(
            name="Genres",
            value="\n".join(g["name"] for g in full["genres"])
        )
        embed.add_field(
            name="Studios",
            value="\n".join(s["name"] for s in full["studios"]) or "None"
        )
        embed.add_field(
            name="Producers",
            value="\n".join(p["name"] for p in full["producers"]) or "None"
        )
        embed.add_field(
            name="Licensors",
            value="\n".join(i["name"] for i in full["licensors"]) or "None"
        )
        embed.add_field(
            name=f"Score \N{BULLET} **Rank {full['rank'] or 'N/A'}**",
            value=f"{partial['score']}/10 ({full['scored_by'] or 0:,} scored)"
        )
        embed.add_field(
            name=f"Members \N{BULLET} **Rank {full['popularity'] or 'N/A'}**",
            value=f"{partial['members']:,} ({full['favorites'] or 0:,} favourited)"
        )

        await ctx.send(embed=embed)

    @commands.command()
    @commands.cooldown(1, 8, commands.BucketType.member)
    async def animeface(
        self,
        ctx,
        *,
        image: ImageAssetConverter(max_filesize=40_000_000)
    ):
        """Detects and highlights anime faces in an image.

        Image can either be a user, custom emoji, link, or
        attachment. Links and attachments must be under 40
        MB.

        (Bot Needs: Attach Files)
        """
        async with ctx.typing():
            try:
                buffer, delta = await backend.detect_anime_faces(
                    io.BytesIO(await image.read())
                )
            except discord.HTTPException:
                await ctx.send("Downloading the image failed. Try again later?")
                return

        if buffer is None:
            await ctx.send("I didn't detect any anime faces.")
        else:
            await ctx.send(
                f"Requested by: {ctx.author} \N{BULLET} Took {delta:.2f} ms",
                file=File(buffer, "detected_anime_faces.png")
            )

    @commands.command()
    @commands.bot_has_permissions(attach_files=True)
    @commands.cooldown(1, 5, commands.BucketType.member)
    async def awooify(
        self,
        ctx,
        *,
        image: ImageAssetConverter(max_filesize=40_000_000)
    ):
        """Awooifies an image.

        Image can either be a user, custom emoji, link, or
        attachment. Links and attachments must be under 40
        MB.

        (Bot Needs: Attach Files)
        """
        async with ctx.typing():
            try:
                buffer, delta = await backend.do_awooify(
                    io.BytesIO(await image.read())
                )
            except discord.HTTPException:
                await ctx.send("Downloading the image failed. Try again later?")
                return

        await ctx.send(
            f"Requested by: {ctx.author} \N{BULLET} Took {delta:.2f} ms",
            file=File(buffer, "awooify.png")
        )

    @commands.command(aliases=("france",))
    @commands.bot_has_permissions(attach_files=True)
    @commands.cooldown(1, 5, commands.BucketType.member)
    async def baguette(
        self,
        ctx,
        *,
        image: ImageAssetConverter(max_filesize=40_000_000)
    ):
        """Turns an image into an anime girl eating a baguette.

        Image can either be a user, custom emoji, link, or
        attachment. Links and attachments must be under 40
        MB.

        (Bot Needs: Attach Files)
        """
        async with ctx.typing():
            try:
                buffer, delta = await backend.make_baguette_meme(
                    io.BytesIO(await image.read())
                )
            except discord.HTTPException:
                await ctx.send("Downloading the image failed. Try again later?")
                return

        await ctx.send(
            f"Requested by: {ctx.author} \N{BULLET} Took {delta:.2f} ms",
            file=File(buffer, "baguette.png")
        )

    @commands.command(aliases=("bp",))
    @commands.bot_has_permissions(attach_files=True)
    @commands.cooldown(1, 5, commands.BucketType.member)
    async def bodypillow(
        self,
        ctx,
        *,
        image: ImageAssetConverter(max_filesize=40_000_000)
    ):
        """Turns an image into an anime body pillow.

        Image can either be a user, custom emoji, link, or
        attachment. Links and attachments must be under 40
        MB.

        (Bot Needs: Attach Files)
        """
        async with ctx.typing():
            try:
                buffer, delta = await backend.make_bodypillow_meme(
                    io.BytesIO(await image.read())
                )
            except discord.HTTPException:
                await ctx.send("Downloading the image failed. Try again later?")
                return

        await ctx.send(
            f"Requested by: {ctx.author} \N{BULLET} Took {delta:.2f} ms",
            file=File(buffer, "bodypillow.png")
        )

    # What a stupid command lmao.
    @commands.command()
    @commands.bot_has_permissions(attach_files=True)
    async def gah(self, ctx):
        """GAH!

        (Bot Needs: Attach Files)
        """
        await ctx.send(file=File(TEMPLATES / "gah.gif"))

    @commands.command(aliases=("hatsunemiku",))
    @commands.bot_has_permissions(embed_links=True)
    async def miku(self, ctx):
        """Shows a random image of Hatsune Miku.

        (Bot Needs: Embed Links)
        """
        resp = await ctx.get("https://miku-for.us/api/v2/random")

        embed = Embed(colour=0x2F3136)
        embed.set_image(url=resp["url"])
        embed.set_footer(text="Powered by miku-for.us")

        await ctx.send(embed=embed)

    @commands.command()
    @commands.bot_has_permissions(attach_files=True)
    @commands.cooldown(1, 5, commands.BucketType.member)
    async def hifumifact(
        self,
        ctx,
        *,
        text: commands.clean_content(fix_channel_mentions=True)
    ):
        """Generates an image of Hifumi spitting straight facts.

        (Bot Needs: Attach Files)
        """
        async with ctx.typing():
            buffer, delta = await backend.make_hifumi_fact_meme(text)

        await ctx.send(
            f"Requested by: {ctx.author} \N{BULLET} Took {delta:.2f} ms",
            file=File(buffer, "hifumi_fact.png")
        )

    @commands.command()
    @commands.bot_has_permissions(attach_files=True)
    @commands.cooldown(1, 5, commands.BucketType.member)
    async def kannafact(
        self,
        ctx,
        *,
        text: commands.clean_content(fix_channel_mentions=True)
    ):
        """Generates an image of Kanna spitting straight facts.

        (Bot Needs: Attach Files)
        """
        async with ctx.typing():
            buffer, delta = await backend.make_kanna_fact_meme(text)

        await ctx.send(
            f"Requested by: {ctx.author} \N{BULLET} Took {delta:.2f} ms",
            file=File(buffer, "kanna_fact.png")
        )

    @commands.command()
    @commands.bot_has_permissions(attach_files=True)
    @commands.cooldown(1, 5, commands.BucketType.member)
    async def lolice(
        self,
        ctx,
        *,
        image: ImageAssetConverter(max_filesize=40_000_000)
    ):
        """Submits an image to the lolice.

        Image can either be a user, custom emoji, link, or
        attachment. Links and attachments must be under 40
        MB.

        (Bot Needs: Attach Files)
        """
        async with ctx.typing():
            try:
                buffer, delta = await backend.make_lolice_meme(
                    io.BytesIO(await image.read())
                )
            except discord.HTTPException:
                await ctx.send("Downloading the image failed. Try again later?")
                return

        await ctx.send(
            f"Requested by: {ctx.author} \N{BULLET} Took {delta:.2f} ms",
            file=File(buffer, "lolice.png")
        )

    @commands.command(aliases=("mangainfo",))
    @commands.bot_has_permissions(embed_links=True)
    @commands.cooldown(1, 5, commands.BucketType.member)
    async def manga(self, ctx, *, query: str.lower):
        """Shows information about a manga on MyAnimeList.

        The search results displayed are based on whether
        or not this command was executed in an NSFW channel.

        **EXAMPLE:**
        ```
        manga Berserk
        ```
        """
        if len(query) < 3:
            await ctx.send("Search queries must be at least 3 characters long.")
            return

        search_url = "https://api.jikan.moe/v3/search/manga?limit=1"

        if not ctx.channel.is_nsfw():
            search_url += "&genre=9,12&genre_exclude=1"

        await ctx.trigger_typing()

        try:
            search = await ctx.get(search_url, cache__=True, q=query)
        except HTTPRequestFailed as exc:
            if exc.status == 503:
                await ctx.send("Jikan failed to fetch from MyAnimeList.")
                return

            raise

        try:
            partial = search["results"][0]
        except IndexError:
            await ctx.send("No results found.")
            return

        id_ = partial["mal_id"]

        embed = Embed(
            title=f"`{id_}` - {partial['title']}",
            colour=0x2F3136,
            url=partial["url"]
        )
        embed.set_thumbnail(url=partial["image_url"])
        embed.set_footer(text="Powered by jikan.moe")
        embed.set_author(
            name=f"{plural(partial['chapters'], ',d'):Chapter} "
                 f"\N{BULLET} {plural(partial['volumes'], ',d'):Volume}"
        )

        embed.add_field(name="Type", value=partial["type"])

        full = await ctx.get(f"https://api.jikan.moe/v3/manga/{id_}/", cache__=True)

        embed.description = (
            f"\U0001F1EC\U0001F1E7 English: {full['title_english'] or 'N/A'}"
            f"\n\U0001F1EF\U0001F1F5 Japanese: {full['title_japanese'] or 'N/A'}\n\n"
            + textwrap.shorten(full["synopsis"] or "No synopsis given.", 1990)
        )

        embed.add_field(name="Status", value=full["status"])
        embed.add_field(name="Published", value=full["published"]["string"])
        embed.add_field(
            name="Genres",
            value="\n".join(g["name"] for g in full["genres"])
        )
        embed.add_field(
            name="Authors",
            value="\n".join(a["name"] for a in full["authors"])
        )
        embed.add_field(
            name="Serializations",
            value="\n".join(s["name"] for s in full["serializations"]) or "None"
        )
        embed.add_field(
            name=f"Score \N{BULLET} **Rank {full['rank'] or 'N/A'}**",
            value=f"{partial['score']}/10 ({full['scored_by'] or 0:,} scored)"
        )
        embed.add_field(
            name=f"Members \N{BULLET} **Rank {full['popularity'] or 'N/A'}**",
            value=f"{partial['members']:,} ({full['favorites'] or 0:,} favourited)"
        )

        await ctx.send(embed=embed)

    @commands.command()
    @commands.bot_has_permissions(attach_files=True)
    @commands.cooldown(1, 8, commands.BucketType.member)
    async def nichijou(
        self,
        ctx,
        *,
        text: commands.clean_content(fix_channel_mentions=True)
    ):
        r""""YOU. ARE. A. ___\_\_\_."

        (Bot Needs: Attach Files)
        """
        async with ctx.typing():
            buffer, delta = await backend.make_nichijou_gif_meme(text)

        await ctx.send(
            f"Requested by: {ctx.author} \N{BULLET} Took {delta:.2f} ms",
            file=File(buffer, "nichijou.gif")
        )

    @commands.command()
    @commands.bot_has_permissions(attach_files=True)
    @commands.cooldown(1, 5, commands.BucketType.member)
    async def ritsudirt(
        self,
        ctx,
        *,
        image: ImageAssetConverter(max_filesize=40_000_000)
    ):
        """Generates a Ritsu dirt meme.

        Image can either be a user, custom emoji, link, or
        attachment. Links and attachments must be under 40
        MB.

        (Bot Needs: Attach Files)
        """
        async with ctx.typing():
            try:
                buffer, delta = await backend.make_ritsu_dirt_meme(
                    io.BytesIO(await image.read())
                )
            except discord.HTTPException:
                await ctx.send("Downloading the image failed. Try again later?")
                return

        await ctx.send(
            f"Requested by: {ctx.author} \N{BULLET} Took {delta:.2f} ms",
            file=File(buffer, "ritsu_dirt.png")
        )

    @commands.command()
    @commands.bot_has_permissions(attach_files=True)
    @commands.cooldown(1, 5, commands.BucketType.member)
    async def ritsufact(
        self,
        ctx,
        *,
        text: commands.clean_content(fix_channel_mentions=True)
    ):
        """Generates an image of Ritsu spitting straight facts.

        (Bot Needs: Attach Files)
        """
        async with ctx.typing():
            buffer, delta = await backend.make_ritsu_fact_meme(text)

        await ctx.send(
            f"Requested by: {ctx.author} \N{BULLET} Took {delta:.2f} ms",
            file=File(buffer, "ritsu_fact.png")
        )

    @commands.command()
    @commands.bot_has_permissions(attach_files=True)
    @commands.cooldown(1, 5, commands.BucketType.member)
    async def trash(
        self,
        ctx,
        *,
        image: ImageAssetConverter(max_filesize=40_000_000)
    ):
        """Generates a trash waifu meme.

        Image can either be a user, custom emoji, link, or
        attachment. Links and attachments must be under 40
        MB.

        (Bot Needs: Attach Files)
        """
        async with ctx.typing():
            try:
                buffer, delta = await backend.make_trash_waifu_meme(
                    io.BytesIO(await image.read())
                )
            except discord.HTTPException:
                await ctx.send("Downloading the image failed. Try again later?")
                return

        await ctx.send(
            f"Requested by: {ctx.author} \N{BULLET} Took {delta:.2f} ms",
            file=File(buffer, "trash_waifu.png")
        )
