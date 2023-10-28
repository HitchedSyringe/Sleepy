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
    BadImageArgument,
    ImageAttachment,
    ImageResourceConverter,
    ImageTooLarge,
)
from sleepy.menus import EmbedSource
from sleepy.utils import plural

from . import backend

if TYPE_CHECKING:
    from discord import Attachment

    from sleepy.context import Context as SleepyContext, GuildContext
    from sleepy.converters import AssetLike


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

        if isinstance(error, (BadImageArgument, UnidentifiedImageError)):
            await ctx.send("The image was either invalid or could not be read.")
            ctx._already_handled_error = True
        elif isinstance(error, ImageTooLarge):
            max_size_mb = error.max_size / 1e6

            await ctx.send(f"Images cannot exceed {max_size_mb:.0f} MB in size.")
            ctx._already_handled_error = True
        elif isinstance(error, DecompressionBombError):
            await ctx.send("Go be Ted Kaczynski somewhere else.")
            ctx._already_handled_error = True
        elif isinstance(error, (commands.BadArgument, commands.MaxConcurrencyReached)):
            await ctx.send(error)  # type: ignore
            ctx._already_handled_error = True

    def cog_load(self) -> None:
        self._original_gif_loading_strategy = GIP.LOADING_STRATEGY
        GIP.LOADING_STRATEGY = GIP.LoadingStrategy.RGB_AFTER_DIFFERENT_PALETTE_ONLY

    def cog_unload(self) -> None:
        GIP.LOADING_STRATEGY = self._original_gif_loading_strategy

    @commands.command(aliases=("animesearch",))
    @commands.bot_has_permissions(embed_links=True)
    @commands.cooldown(1, 5, commands.BucketType.member)
    async def anime(self, ctx: GuildContext, *, query: commands.Range[str, 3]) -> None:
        """Searches for an anime on MyAnimeList and returns the top 10 results.

        The search results displayed are based on whether or not this command
        was executed in an NSFW channel.

        **EXAMPLE:**
        ```
        anime K-ON!
        ```
        """
        search_url = "https://api.jikan.moe/v4/anime?limit=10"

        if ctx.guild is not None and not ctx.channel.is_nsfw():
            search_url += "&genres_exclude=9,12,49,58"

        await ctx.typing()

        search = await ctx.get(search_url, cache__=True, q=query.lower())

        results = search["data"]

        if not results:
            await ctx.send("No results found.")
            return

        embeds = []

        for item in results:
            id_ = item["mal_id"]

            embed = Embed(
                title=f"`{id_}` - {item['title']}",
                colour=Colour.dark_embed(),
                url=item["url"],
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
    @commands.cooldown(1, 8, commands.BucketType.member)
    async def animeface(
        self,
        ctx: SleepyContext,
        attachment: Annotated["Attachment", ImageAttachment] = None,
        url: Annotated["AssetLike", ImageResourceConverter] = None,
    ) -> None:
        """Detects and highlights anime faces in an image.

        Image can either be a user, server emoji, server sticker, link,
        or attachment, with the latter always taking precedence over the
        other image types. Links and attachments must be under 40 MB. If
        no image is given, then your display avatar will be used instead.

        (Bot Needs: Attach Files)
        """
        image = attachment or url or ctx.author.display_avatar

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
    @commands.bot_has_permissions(attach_files=True)
    @commands.cooldown(1, 5, commands.BucketType.member)
    async def awooify(
        self,
        ctx: SleepyContext,
        attachment: Annotated["Attachment", ImageAttachment] = None,
        url: Annotated["AssetLike", ImageResourceConverter] = None,
    ) -> None:
        """Awooifies an image.

        Image can either be a user, server emoji, server sticker, link,
        or attachment, with the latter always taking precedence over the
        other image types. Links and attachments must be under 40 MB. If
        no image is given, then your display avatar will be used instead.

        (Bot Needs: Attach Files)
        """
        image = attachment or url or ctx.author.display_avatar

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
        attachment: Annotated["Attachment", ImageAttachment] = None,
        url: Annotated["AssetLike", ImageResourceConverter] = None,
    ) -> None:
        """Turns an image into an anime girl eating a baguette.

        Image can either be a user, server emoji, server sticker, link,
        or attachment, with the latter always taking precedence over the
        other image types. Links and attachments must be under 40 MB. If
        no image is given, then your display avatar will be used instead.

        (Bot Needs: Attach Files)
        """
        image = attachment or url or ctx.author.display_avatar

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
        attachment: Annotated["Attachment", ImageAttachment] = None,
        url: Annotated["AssetLike", ImageResourceConverter] = None,
    ) -> None:
        """Turns an image into an anime body pillow.

        Image can either be a user, server emoji, server sticker, link,
        or attachment, with the latter always taking precedence over the
        other image types. Links and attachments must be under 40 MB. If
        no image is given, then your display avatar will be used instead.

        (Bot Needs: Attach Files)
        """
        image = attachment or url or ctx.author.display_avatar

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

    @commands.command()
    @commands.bot_has_permissions(attach_files=True)
    @commands.cooldown(1, 5, commands.BucketType.member)
    async def lolice(
        self,
        ctx: SleepyContext,
        attachment: Annotated["Attachment", ImageAttachment] = None,
        url: Annotated["AssetLike", ImageResourceConverter] = None,
    ) -> None:
        """Submits an image to the lolice.

        Image can either be a user, server emoji, server sticker, link,
        or attachment, with the latter always taking precedence over the
        other image types. Links and attachments must be under 40 MB. If
        no image is given, then your display avatar will be used instead.

        (Bot Needs: Attach Files)
        """
        image = attachment or url or ctx.author.display_avatar

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
    async def manga(self, ctx: GuildContext, *, query: commands.Range[str, 3]) -> None:
        """Searches for a manga on MyAnimeList and returns the top 10 results.

        The search results displayed are based on whether or not this command
        was executed in an NSFW channel.

        **EXAMPLE:**
        ```
        manga Berserk
        ```
        """
        search_url = "https://api.jikan.moe/v4/manga?limit=10"

        if ctx.guild is not None and not ctx.channel.is_nsfw():
            search_url += "&genres_exclude=9,12,49,58"

        await ctx.typing()

        search = await ctx.get(search_url, cache__=True, q=query.lower())
        results = search["data"]

        if not results:
            await ctx.send("No results found.")
            return

        embeds = []

        for item in results:
            id_ = item["mal_id"]

            embed = Embed(
                title=f"`{id_}` - {item['title']}",
                colour=Colour.dark_embed(),
                url=item["url"],
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
        attachment: Annotated["Attachment", ImageAttachment] = None,
        url: Annotated["AssetLike", ImageResourceConverter] = None,
    ) -> None:
        """Generates a Ritsu dirt meme.

        Image can either be a user, server emoji, server sticker, link,
        or attachment, with the latter always taking precedence over the
        other image types. Links and attachments must be under 40 MB. If
        no image is given, then your display avatar will be used instead.

        (Bot Needs: Attach Files)
        """
        image = attachment or url or ctx.author.display_avatar

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
        attachment: Annotated["Attachment", ImageAttachment] = None,
        url: Annotated["AssetLike", ImageResourceConverter] = None,
    ) -> None:
        """Generates a trash waifu meme.

        Image can either be a user, server emoji, server sticker, link,
        or attachment, with the latter always taking precedence over the
        other image types. Links and attachments must be under 40 MB. If
        no image is given, then your display avatar will be used instead.

        (Bot Needs: Attach Files)
        """
        image = attachment or url or ctx.author.display_avatar

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
