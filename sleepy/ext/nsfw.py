"""
Copyright (c) 2018-present HitchedSyringe

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""


from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, FrozenSet, Iterable

from discord import Colour, Embed
from discord.ext import commands
from typing_extensions import Annotated

from sleepy.converters import ImageAssetConverter
from sleepy.http import HTTPRequestFailed
from sleepy.menus import EmbedSource

if TYPE_CHECKING:
    from sleepy.bot import Sleepy
    from sleepy.context import Context as SleepyContext, GuildContext
    from sleepy.mimics import PartialAsset


# fmt: off
# These bans are mostly generalised.
NSFW_TAG_BLOCKLIST: FrozenSet[str] = frozenset({
    "adolescent",
    "child",
    "children",
    "cp",
    "cub",
    "cubs",
    "ephebophile",
    "ephebophiles",
    "ephebophilia",
    "hebephile",
    "hebephiles",
    "hebephilia",
    "kid",
    "kids",
    "loli",
    "lolis",
    "lolicon",
    "lolicons",
    "minor",
    "minors",
    "paedo",
    "paedos",
    "paedophile",
    "paedophiles",
    "paedophilia",
    "pedo",
    "pedos",
    "pedophile",
    "pedophiles",
    "pedophilia",
    "shota",
    "shotas",
    "shotacon",
    "shotacons",
    "toddler",
    "toddlers",
    "toddlercon",
    "toddlercons",
    "tween",
    "tweens",
    "underage",
    "underaged",
    "young",
    "youth",
})
# fmt: on


def has_any_banned_tags(tags: Iterable[str]) -> bool:
    return any(t in NSFW_TAG_BLOCKLIST for t in tags)


def ensure_safe_tags(value: str) -> str:
    value = value.lower()

    # We do this to ensure that nobody bypasses the filter
    # just by passing in something like "banned_tag tag".
    # This also allows people to use quotes without any
    # trouble.
    if has_any_banned_tags(value.split()):
        raise commands.BadArgument("One or more tags involve banned content on Discord.")

    return value


# neckbeard cog but even worse.
class NSFW(
    commands.Cog,
    command_attrs={
        "cooldown": commands.CooldownMapping.from_cooldown(
            2, 5, commands.BucketType.member
        ),
    },
):
    """Don't lie, you know what this category encompasses."""

    ICON: str = "\N{NO ONE UNDER EIGHTEEN SYMBOL}"

    def __init__(self, saucenao_api_key: str) -> None:
        self.saucenao_api_key: str = saucenao_api_key

    async def cog_check(self, ctx: GuildContext) -> bool:
        # The channel should be able to be NSFW checked here.
        if ctx.guild is not None and not ctx.channel.is_nsfw():
            raise commands.NSFWChannelRequired(ctx.channel)

        return True

    async def cog_command_error(self, ctx: SleepyContext, error: Exception) -> None:
        if isinstance(error, commands.NSFWChannelRequired):
            await ctx.send("This command can only be used in an NSFW channel.")
            ctx._already_handled_error = True
        elif isinstance(error, commands.BadArgument):
            await ctx.send(error)  # type: ignore
            ctx._already_handled_error = True

    @staticmethod
    async def send_nekobot_image_embed(ctx: SleepyContext, *, image_type: str) -> None:
        resp = await ctx.get("https://nekobot.xyz/api/image", type=image_type)

        embed = Embed(colour=Colour(resp["color"]))
        embed.set_image(url=resp["message"])
        embed.set_footer(text="Powered by nekobot.xyz")

        await ctx.send(embed=embed)

    @commands.command()
    @commands.bot_has_permissions(embed_links=True)
    async def anal(self, ctx: SleepyContext) -> None:
        """Sends a random image of an4l.

        (Bot Needs: Embed Links)
        """
        await self.send_nekobot_image_embed(ctx, image_type="anal")

    @commands.command()
    @commands.bot_has_permissions(embed_links=True)
    async def analhentai(self, ctx: SleepyContext) -> None:
        """Sends a random image of an4l h3nt4i.

        (Bot Needs: Embed Links)
        """
        await self.send_nekobot_image_embed(ctx, image_type="hanal")

    @commands.command(aliases=("aass",))
    @commands.bot_has_permissions(embed_links=True)
    async def animeass(self, ctx: SleepyContext) -> None:
        """Sends a random image of anime 4$$.

        (Bot Needs: Embed Links)
        """
        await self.send_nekobot_image_embed(ctx, image_type="hass")

    @commands.command(aliases=("animetits", "animetitties"))
    @commands.bot_has_permissions(embed_links=True)
    async def animeboobs(self, ctx: SleepyContext) -> None:
        """Sends a random image of anime b00bs.

        (Bot Needs: Embed Links)
        """
        await self.send_nekobot_image_embed(ctx, image_type="hboobs")

    @commands.command(aliases=("amidriff",))
    @commands.bot_has_permissions(embed_links=True)
    async def animemidriff(self, ctx: SleepyContext) -> None:
        """Sends a random image of anime midriff.

        (Bot Needs: Embed Links)
        """
        await self.send_nekobot_image_embed(ctx, image_type="hmidriff")

    @commands.command(aliases=("athighs",))
    @commands.bot_has_permissions(embed_links=True)
    async def animethighs(self, ctx: SleepyContext) -> None:
        """Sends a random image of anime thighs.

        (Bot Needs: Embed Links)
        """
        await self.send_nekobot_image_embed(ctx, image_type="hthigh")

    @commands.command()
    @commands.bot_has_permissions(embed_links=True)
    async def ass(self, ctx: SleepyContext) -> None:
        """Sends a random image of 4$$.

        (Bot Needs: Embed Links)
        """
        await self.send_nekobot_image_embed(ctx, image_type="ass")

    @commands.command(aliases=("tits", "titties"))
    @commands.bot_has_permissions(embed_links=True)
    async def boobs(self, ctx: SleepyContext) -> None:
        """Sends a random image of b00bs.

        (Bot Needs: Embed Links)
        """
        await self.send_nekobot_image_embed(ctx, image_type="boobs")

    @commands.command(require_var_positional=True)
    @commands.bot_has_permissions(embed_links=True)
    @commands.cooldown(1, 5, commands.BucketType.member)
    async def danbooru(
        self, ctx: SleepyContext, *tags: Annotated[str, ensure_safe_tags]
    ) -> None:
        """Searches for something on Danbooru using the given tags.

        Due to a Danbooru limitation, you can only search
        for up to two tags at a time.

        (Bot Needs: Embed Links)

        **EXAMPLES:**
        ```bnf
        <1> danbooru long_hair
        <2> danbooru uniform two-tone_hair
        ```
        """
        await ctx.typing()

        try:
            resp = await ctx.get(
                "https://danbooru.donmai.us/post/index.json?limit=200",
                cache__=True,
                tags=" ".join(tags),
            )
        except HTTPRequestFailed as exc:
            # Hit the two tag limit.
            if exc.status == 422:
                await ctx.send(exc.data["message"])
                return

            raise

        if not resp:
            await ctx.send("The search returned no results.")
            return

        embeds = []

        for post in resp:
            # Have to use this instead of the more elegant
            # tag exclusions due to the fact that doing so
            # keeps throwing a 422.
            if has_any_banned_tags(post["tags"].split(" ")):
                continue

            try:
                url = post["file_url"]
            except KeyError:
                continue

            embed = Embed(
                description=f"[Media Link]({url})",
                colour=0x9EECFF,
                timestamp=datetime.fromisoformat(post["created_at"]).replace(
                    tzinfo=timezone.utc
                ),
            )
            embed.set_author(name=post["author"])
            embed.set_image(url=url)
            embed.set_footer(text="Powered by danbooru.donmai.us")

            if sauce := post["source"]:
                embed.add_field(name="Source", value=sauce)

            embeds.append(embed)

        if not embeds:
            await ctx.send(
                "The returned results either all involve banned content"
                " on Discord or, for some reason, lack image links."
            )
        else:
            await ctx.paginate(EmbedSource(embeds))

    @commands.command(require_var_positional=True)
    @commands.bot_has_permissions(embed_links=True)
    @commands.cooldown(1, 5, commands.BucketType.member)
    async def e621(
        self, ctx: SleepyContext, *tags: Annotated[str, ensure_safe_tags]
    ) -> None:
        """Searches for something on E621 using the given tags.

        Due to an E621 limitation, you can only search
        for up to 40 tags at a time.

        (Bot Needs: Embed Links)

        **EXAMPLES:**
        ```bnf
        <1> e621 brown_hair
        <2> e621 feline two-tone_hair
        ```
        """
        from sleepy import __version__
        from sleepy.utils import SOURCE_CODE_URL

        headers = {
            # This needs to be done since the default user agent gets blocked.
            # In this case, we strip the Python and aiohttp versions since that
            # seems to trip the blocking mechanism.
            "User-Agent": f"Sleepy-DiscordBot ({SOURCE_CODE_URL} {__version__})",
        }

        await ctx.typing()

        try:
            resp = await ctx.get(
                "https://e621.net/posts.json",
                headers__=headers,
                cache__=True,
                tags=" ".join(tags),
            )
        except HTTPRequestFailed as exc:
            # Hit the 40 tag limit.
            if exc.status == 422:
                await ctx.send(exc.data["message"])
                return

            raise

        results = resp["posts"]

        if not results:
            await ctx.send("No results found.")
            return

        embeds = []

        for post in results:
            if has_any_banned_tags(post["tags"]["general"]):
                continue

            url = post["file"]["url"]

            if url is None:
                continue

            embed = Embed(
                description=f"[Media Link]({url})",
                colour=0x3B6AA3,
                timestamp=datetime.fromisoformat(post["created_at"]).replace(
                    tzinfo=timezone.utc
                ),
            )
            embed.set_image(url=url)
            embed.set_footer(text="Powered by e621.net")

            if sauces := post["sources"]:
                embed.add_field(name="Source(s)", value="\n".join(sauces))

            embeds.append(embed)

        if not embeds:
            await ctx.send(
                "The returned results either all involve banned content"
                " on Discord or, for some reason, lack image links."
            )
        else:
            await ctx.paginate(EmbedSource(embeds))

    @commands.command(name="4knude", aliases=("fourknude",))
    @commands.bot_has_permissions(embed_links=True)
    async def fourknude(self, ctx: SleepyContext) -> None:
        """Sends a random nud3 image in crisp 4K resolution.

        (Bot Needs: Embed Links)
        """
        await self.send_nekobot_image_embed(ctx, image_type="4k")

    @commands.command()
    @commands.bot_has_permissions(embed_links=True)
    async def hentai(self, ctx: SleepyContext) -> None:
        """Sends a random h3nt41 image.

        (Bot Needs: Embed Links)
        """
        await self.send_nekobot_image_embed(ctx, image_type="hentai")

    @commands.command()
    @commands.bot_has_permissions(embed_links=True)
    async def lewdkitsune(self, ctx: SleepyContext) -> None:
        """Sends a random image of l3wd kitsunes.

        (Bot Needs: Embed Links)
        """
        await self.send_nekobot_image_embed(ctx, image_type="hkitsune")

    # This was intentionally left out due to some images
    # looking like they shouldn't be allowed on Discord.
    # This will be added in officially when said images
    # are no longer being served.
    # @commands.command(aliases=("catgirlhentai",))
    # @commands.bot_has_permissions(embed_links=True)
    # async def nekohentai(self, ctx: SleepyContext) -> None:
    #     """Sends a random catgirl h3nt41 image.

    #     (Bot Needs: Embed Links)
    #     """
    #     await self.send_nekobot_image_embed(ctx, image_type="hneko")

    @commands.command()
    @commands.bot_has_permissions(embed_links=True)
    async def paizuri(self, ctx: SleepyContext) -> None:
        """Sends a random image of p41zur1.

        (Bot Needs: Embed Links)
        """
        await self.send_nekobot_image_embed(ctx, image_type="paizuri")

    @commands.command(aliases=("pgif",))
    @commands.bot_has_permissions(embed_links=True)
    async def porngif(self, ctx: SleepyContext) -> None:
        """Sends a random pr0n GIF.

        (Bot Needs: Embed Links)
        """
        await self.send_nekobot_image_embed(ctx, image_type="pgif")

    @commands.command()
    @commands.bot_has_permissions(embed_links=True)
    async def pussy(self, ctx: SleepyContext) -> None:
        """Sends a random image of pu$$y.

        (Bot Needs: Embed Links)
        """
        await self.send_nekobot_image_embed(ctx, image_type="pussy")

    @commands.command(aliases=("r34",), require_var_positional=True)
    @commands.bot_has_permissions(embed_links=True)
    @commands.cooldown(1, 5, commands.BucketType.member)
    async def rule34(
        self, ctx: SleepyContext, *tags: Annotated[str, ensure_safe_tags]
    ) -> None:
        """Searches for something on Rule34 using the given tags.

        (Bot Needs: Embed Links)

        **EXAMPLES:**
        ```bnf
        <1> rule34 brown_hair
        <2> rule34 speech_bubble two-tone_hair
        ```
        """
        await ctx.typing()

        resp = await ctx.get(
            "https://rule34.xxx/index.php?page=dapi&s=post&q=index&json=1&limit=100",
            cache__=True,
            tags=f"{' '.join(tags)} {' '.join(f'-{t}' for t in NSFW_TAG_BLOCKLIST)}",
        )

        if not resp:
            await ctx.send("The search returned no results.")
            return

        embeds = []

        for post in resp:
            url = post["file_url"]

            embed = Embed(description=f"[Media Link]({url})", colour=0x77E371)
            embed.set_author(name=post["owner"])
            embed.set_image(url=url)
            embed.set_footer(text="Powered by rule34.xxx")

            embeds.append(embed)

        await ctx.paginate(EmbedSource(embeds))

    @commands.command(aliases=("sauce",))
    @commands.bot_has_permissions(embed_links=True)
    @commands.cooldown(1, 8, commands.BucketType.member)
    async def saucenao(
        self,
        ctx: SleepyContext,
        *,
        image: Annotated["PartialAsset", ImageAssetConverter(max_filesize=20_000_000)],
    ) -> None:
        """Reverse searches an image using SauceNAO.

        Image can either be a user, custom emoji, link, or
        attachment. Links and attachments must be under 20
        MB.

        (Bot Needs: Embed Links)
        """
        await ctx.typing()

        resp = await ctx.get(
            "https://saucenao.com/search.php?db=999&output_type=2&numres=24",
            api_key=self.saucenao_api_key,
            url=str(image),
        )

        # Don't know why, nor do I want to know why, but for
        # whatever reason, SauceNAO doesn't use HTTP statuses.
        status = resp["header"]["status"]

        # Invalid file or SauceNAO failed to download a remote image.
        if status in (-3, -4, -6):
            await ctx.send(
                "SauceNAO failed to process your image. "
                "Make sure your image is in a valid image format."
            )
            return

        results = resp.get("results")

        if status != 0 or results is None:
            await ctx.send("SauceNAO failed to process your image. Try again later?")
            return

        embeds = []

        for result in results:
            meta = result["header"]

            embed = Embed(title=meta["index_name"], colour=0x2F3136)
            # For some reason, thumbnail URLs sometimes have spaces in them.
            embed.set_image(url=meta["thumbnail"].replace(" ", "%20"))
            embed.set_footer(
                text=f"{meta['similarity']}% similar \N{BULLET} Powered by saucenao.com"
            )

            data = result["data"]

            try:
                embed.add_field(
                    name="External Links", value="\n".join(data.pop("ext_urls"))
                )
            except KeyError:
                pass

            embed.description = "\n".join(
                f"**{k.replace('_', ' ').title()}:** "
                # For whatever reason, Xamayon decided that it was okay
                # to leave the creator field as a list for index ID 38.
                f"{', '.join(v) if k == 'creator' and meta['index_id'] == 38 else v}"
                for k, v in data.items()
            )

            embeds.append(embed)

        await ctx.paginate(EmbedSource(embeds))

    @commands.command(aliases=("tentai",))
    @commands.bot_has_permissions(embed_links=True)
    async def tentacle(self, ctx: SleepyContext) -> None:
        """You've seen enough to know what this entails.

        (Bot Needs: Embed Links)
        """
        await self.send_nekobot_image_embed(ctx, image_type="tentacle")

    @commands.command()
    @commands.bot_has_permissions(embed_links=True)
    async def thighs(self, ctx: SleepyContext) -> None:
        """Sends a random image of thighs.

        (Bot Needs: Embed Links)
        """
        await self.send_nekobot_image_embed(ctx, image_type="thigh")

    @commands.command(require_var_positional=True)
    @commands.bot_has_permissions(embed_links=True)
    @commands.cooldown(1, 5, commands.BucketType.member)
    async def yandere(
        self, ctx: SleepyContext, *tags: Annotated[str, ensure_safe_tags]
    ) -> None:
        """Searches for something on Yande.re using the given tags.

        Due to a Yande.re limitation, you can only search
        for up to 6 tags at a time.

        (Bot Needs: Embed Links)

        **EXAMPLES:**
        ```bnf
        <1> yandere brown_hair
        <2> yandere text two-tone_hair
        ```
        """
        await ctx.typing()

        try:
            resp = await ctx.get(
                "https://yande.re/post.json?limit=100", cache__=True, tags=" ".join(tags)
            )
        except HTTPRequestFailed as exc:
            # Assuming from testing, there's probably a hard limit of 6 tags.
            if exc.status == 500:
                await ctx.send("You cannot search for more than 6 tags at a time.")
                return

            raise

        if not resp:
            await ctx.send("The search returned no results.")
            return

        embeds = []

        for post in resp:
            # Same reason as danbooru/e621 but in this case,
            # I get a 500 instead.
            if has_any_banned_tags(post["tags"].split(" ")):
                continue

            media_url = post["file_url"]

            embed = Embed(
                description=f"[Media Link]({media_url})",
                colour=0xFF9ED0,
                timestamp=datetime.fromtimestamp(post["created_at"], timezone.utc),
            )
            embed.set_author(name=post["author"])
            embed.set_image(url=media_url)
            embed.set_footer(text="Powered by yande.re")

            if sauce := post["source"]:
                embed.add_field(name="Source", value=sauce)

            embeds.append(embed)

        if not embeds:
            await ctx.send("All returned results involve banned content on Discord.")
        else:
            await ctx.paginate(EmbedSource(embeds))

    @commands.command()
    @commands.bot_has_permissions(embed_links=True)
    async def yaoi(self, ctx: SleepyContext) -> None:
        """Sends a random y401 image.

        (Bot Needs: Embed Links)
        """
        await self.send_nekobot_image_embed(ctx, image_type="yaoi")


async def setup(bot: Sleepy) -> None:
    await bot.add_cog(NSFW(bot.config["saucenao_api_key"]))
