"""
© Copyright 2018-2020 HitchedSyringe, All Rights Reserved.

Redistributing, using or owning a copy of this software without explicit permissions
is against these licensing terms, your license(s) to this software can be revoked at
any time without explicit notice beforehand and at the time of revocation.
Your license is non-transferrable, the terms of this license only permit you to do the
following; Create pull requests and make modifications to this repository.

"""


import json
import re
from datetime import datetime, timezone
from urllib.parse import quote as urlquote

from discord import Embed
from discord.ext import commands

from SleepyBot.utils import checks, converters, reaction_menus


# These bans are mostly generalised.
NSFW_TAG_BLOCKLIST = (
    "child",
    "children",
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
)


def _has_any_banned_tags(tags) -> bool:
    """Whether or not there are any banned tags in the given tags list.
    Returns ``True`` if and only if the content has any tag specified on the blocklist.

    Parameters
    ----------
    tags: List[:class:`str`]
        The content's tags.

    Returns
    -------
    :class:`bool`
        Whether or not the content in question is tagged under a banned tag.
    """
    return any(tag in NSFW_TAG_BLOCKLIST for tag in tags)


def _safe_tag(value) -> str:
    """Pseudo-converter that verifies if each tag in the string isn't on the blocklist.
    Raises :exc:`commands.BadArgument` if any given tags are on the blocklist.
    """
    value = value.lower()

    # We do this to ensure that nobody bypasses the filter just by passing in something like "banned_tag tag".
    # This also allows people to use quotes without any trouble.
    if _has_any_banned_tags(re.split(r"\s", value)):
        raise commands.BadArgument("One or more tags entered involve banned content on Discord.")

    return value


class NSFW(commands.Cog,
           command_attrs=dict(cooldown=commands.Cooldown(rate=2, per=5, type=commands.BucketType.member))):
    """You know what this encompasses. Don't act like you don't."""
    # neckbeard cog but even worse.

    async def cog_check(self, ctx: commands.Context):
        if ctx.guild is None:  # Account for user settings filter.
            raise commands.NoPrivateMessage()

        if not ctx.channel.is_nsfw():
            raise commands.NSFWChannelRequired(ctx.channel)

        return True


    async def cog_command_error(self, ctx: commands.Context, error):
        error = getattr(error, "original", error)

        if isinstance(error, commands.NSFWChannelRequired):
            await ctx.send("This command can only be used in an NSFW channel.")
            error.handled = True
        elif isinstance(error, commands.BadArgument):
            await ctx.send(str(error))
            error.handled = True


    @staticmethod
    async def _format_generic_image(ctx, *, url: str, provider: str, colour=None):
        """Sends the generic image message format.
        For internal use only.
        """
        embed = Embed(colour=colour)
        embed.set_image(url=url)
        embed.set_footer(text=f"Powered by {provider}")
        await ctx.send(embed=embed)


    @commands.command()
    @checks.bot_has_permissions(embed_links=True)
    async def anal(self, ctx: commands.Context):
        """Sends a random image of an4l.
        (Bot Needs: Embed Links)
        """
        response = await ctx.get("https://nekobot.xyz/api/image", type="anal")

        await self._format_generic_image(ctx, url=response["message"], provider="nekobot.xyz", colour=0x2F3136)


    @commands.command(aliases=["analh"])
    @checks.bot_has_permissions(embed_links=True)
    async def analhentai(self, ctx: commands.Context):
        """Sends a random image of an4l h3nt4i.
        (Bot Needs: Embed Links)
        """
        response = await ctx.get("https://nekobot.xyz/api/image", type="hanal")

        await self._format_generic_image(ctx, url=response["message"], provider="nekobot.xyz", colour=0x2F3136)


    @commands.command(aliases=["aass"])
    @checks.bot_has_permissions(embed_links=True)
    async def animeass(self, ctx: commands.Context):
        """Sends a random image of anime 4$$.
        (Bot Needs: Embed Links)
        """
        response = await ctx.get("https://nekobot.xyz/api/image", type="hass")

        await self._format_generic_image(ctx, url=response["message"], provider="nekobot.xyz", colour=0x2F3136)


    @commands.command(aliases=["amidriff"])
    @checks.bot_has_permissions(embed_links=True)
    async def animemidriff(self, ctx: commands.Context):
        """Sends a random image of anime midriff.
        (Bot Needs: Embed Links)
        """
        response = await ctx.get("https://nekobot.xyz/api/image", type="hmidriff")

        await self._format_generic_image(ctx, url=response["message"], provider="nekobot.xyz", colour=0x2F3136)


    @commands.command(aliases=["athighs"])
    @checks.bot_has_permissions(embed_links=True)
    async def animethighs(self, ctx: commands.Context):
        """Sends a random image of anime thighs.
        (Bot Needs: Embed Links)
        """
        response = await ctx.get("https://nekobot.xyz/api/image", type="hthigh")

        await self._format_generic_image(ctx, url=response["message"], provider="nekobot.xyz", colour=0x2F3136)


    @commands.command()
    @checks.bot_has_permissions(embed_links=True)
    async def ass(self, ctx: commands.Context):
        """Sends a random 4$$ image.
        (Bot Needs: Embed Links)
        """
        response = await ctx.get("https://nekobot.xyz/api/image", type="ass")

        await self._format_generic_image(ctx, url=response["message"], provider="nekobot.xyz", colour=0x2F3136)


    @commands.command()
    @checks.bot_has_permissions(embed_links=True, add_reactions=True, read_message_history=True)
    @commands.cooldown(rate=1, per=5, type=commands.BucketType.member)
    async def danbooru(self, ctx: commands.Context, *tags: _safe_tag):
        """Searches for something on Danbooru using the given tags.
        (Bot Needs: Embed Links, Add Reactions and Read Message History)

        EXAMPLE:
        (Ex. 1) danbooru long_hair
        (Ex. 2) danbooru uniform two-tone_hair
        """
        if not tags:
            await ctx.send("You must enter at least one tag to search for.")
            return

        await ctx.trigger_typing()
        results = await ctx.get(
            "https://danbooru.donmai.us/post/index.json",
            limit=200,
            tags=" ".join(tags),
            cache=True
        )

        if not results:
            await ctx.send("No results found.")
            return

        posts = [r for r in results if not _has_any_banned_tags(r["tags"]) and r.get("file_url") is not None]
        if not posts:
            await ctx.send("All results either involve banned content on Discord or lack image links for some reason.")
            return

        base_embed = Embed(title="Danbooru", colour=0x9EECFF)
        base_embed.set_footer(text="Powered by danbooru.donmai.us")

        embeds = []
        for post in posts:
            embed = base_embed.copy()
            embed.set_author(name=post["author"])
            embed.set_image(url=post["file_url"])
            embed.timestamp = datetime.strptime(post["created_at"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)

            sauce = post["source"]
            if sauce:
                embed.add_field(name="Source", value=sauce)

            embeds.append(embed)

        await ctx.paginate(reaction_menus.EmbedSource(embeds))


    @commands.command()
    @checks.bot_has_permissions(embed_links=True)
    async def doujin(self, ctx: commands.Context):
        """Gets a random doujin from nhentai.
        (Bot Needs: Embed Links)
        """
        # Have to manually grab using bot session since this breaks when using our requester.
        async with ctx.session.get("http://nhentai.net/random/") as resp:
            await self._format_generic_image(ctx, url=str(resp.url), provider="nhentai.net", colour=0x2F3136)


    @commands.command()
    @checks.bot_has_permissions(embed_links=True, add_reactions=True, read_message_history=True)
    @commands.cooldown(rate=1, per=5, type=commands.BucketType.member)
    async def e621(self, ctx: commands.Context, *tags: _safe_tag):
        """Searches for something on E621 using the given tags.
        (Bot Needs: Embed Links, Add Reactions and Read Message History)

        EXAMPLE:
        (Ex. 1) e621 brown_hair
        (Ex. 2) e621 feline two-tone_hair
        """
        if not tags:
            await ctx.send("You must enter at least one tag to search for.")
            return

        await ctx.trigger_typing()
        response = await ctx.get("https://e621.net/posts.json", tags=" ".join(tags), cache=True)

        results = response["posts"]
        if not results:
            await ctx.send("No results found.")
            return

        # e621 actually has 8 categories for tags: general, species, character, copyright, artist, invalid, lore & meta
        # We only check general tags since this is mostly where the banned tags would reside.
        posts = [r for r in results if r["file"]["url"] is not None and not _has_any_banned_tags(r["tags"]["general"])]
        if not posts:
            await ctx.send("All results either involve banned content on Discord or lack image links for some reason.")
            return

        base_embed = Embed(title="E621", colour=0x3B6AA3)
        base_embed.set_footer(text="Powered by e621.net")

        embeds = []
        for post in posts:
            embed = base_embed.copy()
            embed.set_image(url=post["file"]["url"])
            embed.timestamp = datetime.strptime(post["created_at"], "%Y-%m-%dT%H:%M:%S.%f-04:00")
            embed.timestamp.replace(tzinfo=timezone.utc)

            sauces = "\n".join(post["sources"])
            if sauces:
                embed.add_field(name="**Source(s)**", value=sauces)

            embeds.append(embed)

        await ctx.paginate(reaction_menus.EmbedSource(embeds))


    @commands.command(aliases=["4k"])
    @checks.bot_has_permissions(embed_links=True)
    async def fourk(self, ctx: commands.Context):
        """Sends a random nud3 image in 4K.
        (Bot Needs: Embed Links)
        """
        response = await ctx.get("https://nekobot.xyz/api/image", type="4k")

        await self._format_generic_image(ctx, url=response["message"], provider="nekobot.xyz", colour=0x2F3136)


    @commands.command()
    @checks.bot_has_permissions(embed_links=True)
    async def hentai(self, ctx: commands.Context):
        """Sends a random h3nt41 image.
        (Bot Needs: Embed Links)
        """
        response = await ctx.get("https://nekobot.xyz/api/image", type="hentai")

        await self._format_generic_image(ctx, url=response["message"], provider="nekobot.xyz", colour=0x2F3136)


    @commands.command()
    @checks.bot_has_permissions(embed_links=True)
    async def lewdkitsune(self, ctx: commands.Context):
        """Sends a random image of l3wd kitsunes.
        (Bot Needs: Embed Links)
        """
        response = await ctx.get("https://nekobot.xyz/api/image", type="lewdkitsune")

        await self._format_generic_image(ctx, url=response["message"], provider="nekobot.xyz", colour=0x2F3136)


    @commands.command()
    @checks.bot_has_permissions(embed_links=True)
    async def paizuri(self, ctx: commands.Context):
        """Shows a random image of p41zur1.
        (Bot Needs: Embed Links)
        """
        response = await ctx.get("https://nekobot.xyz/api/image", type="paizuri")

        await self._format_generic_image(ctx, url=response["message"], provider="nekobot.xyz", colour=0x2F3136)


    @commands.command()
    @checks.bot_has_permissions(embed_links=True)
    async def pgif(self, ctx: commands.Context):
        """Sends a random pr0n GIF.
        (Bot Needs: Embed Links)
        """
        response = await ctx.get("https://nekobot.xyz/api/image", type="pgif")

        await self._format_generic_image(ctx, url=response["message"], provider="nekobot.xyz", colour=0x2F3136)


    @commands.command()
    @checks.bot_has_permissions(embed_links=True)
    async def pussy(self, ctx: commands.Context):
        """Sends a random image of pu$$y.
        (Bot Needs: Embed Links)
        """
        response = await ctx.get("https://nekobot.xyz/api/image", type="pussy")

        await self._format_generic_image(ctx, url=response["message"], provider="nekobot.xyz", colour=0x2F3136)


    @commands.command(aliases=["r34"])
    @checks.bot_has_permissions(embed_links=True, add_reactions=True, read_message_history=True)
    @commands.cooldown(rate=1, per=5, type=commands.BucketType.member)
    async def rule34(self, ctx: commands.Context, *tags: _safe_tag):
        """Searches for something on Rule34 using the given tags.
        (Bot Needs: Embed Links, Add Reactions and Read Message History)

        EXAMPLE:
        (Ex. 1) rule34 brown_hair
        (Ex. 2) rule34 speech_bubble two-tone_hair
        """
        if not tags:
            await ctx.send("You must enter at least one tag to search for.")
            return

        await ctx.trigger_typing()
        response = await ctx.get(
            "https://rule34.xxx/index.php",
            page="dapi",
            s="post",
            q="index",
            #deleted="show",
            json=1,
            limit=100,
            tags=" ".join(tags),
            cache=True
        )

        if not response:
            await ctx.send("No results were found for the given tag(s).")
            return

        results = json.loads(response)

        posts = [r for r in results if not _has_any_banned_tags(r["tags"])]
        if not posts:
            # We probably won't ever get to this point.
            await ctx.send("All results involve banned content on Discord.")
            return

        base_embed = Embed(title="Rule 34", colour=0x77E371)
        base_embed.set_footer(text="Powered by rule34.xxx")

        embeds = []
        for post in posts:
            embed = base_embed.copy()
            embed.set_author(name=post["owner"])
            embed.set_image(url=f"https://img.rule34.xxx/images/{post['directory']}/{post['image']}")

            embeds.append(embed)

        await ctx.paginate(reaction_menus.EmbedSource(embeds))


    @commands.command(aliases=["sauce"])
    @checks.bot_has_permissions(embed_links=True, add_reactions=True, read_message_history=True)
    @commands.cooldown(rate=1, per=5, type=commands.BucketType.member)
    async def saucenao(self, ctx: commands.Context, image: converters.ImageAssetConverter):
        """Reverse searches an image on SauceNAO.
        Image can either be a link or attachment.
        (Bot Needs: Embed Links, Add Reactions and Read Message History)
        """
        await ctx.trigger_typing()
        # ``url``` argument collides with our positional argument of the same name,
        # so we'll just have to format it and urlquote it ourself instead.
        # Also, since we're dealing with attachments here, I'm not gonna bother caching this.
        response = await ctx.get(f"https://saucenao.com/search.php?url={urlquote(str(image))}", db=999, output_type=2)

        results = response.get("results")
        if results is None:
            await ctx.send(
                "Something went wrong while trying to process your image.\n"
                "Make sure that your image is either a GIF, JPG, PNG, BMP, SVG or WEBP."
            )
            return

        embeds = []
        for result in results:
            header = result["header"]

            embed = Embed(colour=0x1D1D1D)
            # Sometimes, for whatever reason, URLs may have spaces in them, so we'll have to fix it ourselves.
            embed.set_image(url=header["thumbnail"].replace(" ", "%20"))
            embed.set_footer(
                text=f"{header['index_name']} | {header['similarity']}% similarity | Powered by saucenao.com"
            )

            data = result["data"]

            ext_urls = data.pop("ext_urls", None)
            if ext_urls is not None:
                embed.add_field(name="**Associated Links**", value="\n".join(ext_urls))

            # Thanks saucenao API for having the most confusing return values in existence.
            embed.description = "\n".join(
                f"**{k.replace('_', ' ').title()}:** {', '.join(v) if isinstance(v, list) else v}" for k, v in data.items()
            )

            embeds.append(embed)

        await ctx.paginate(reaction_menus.EmbedSource(embeds))


    @commands.command()
    @checks.bot_has_permissions(embed_links=True)
    async def tentacle(self, ctx: commands.Context):
        """You've seen enough hentai to know what this entails.
        (Bot Needs: Embed Links)
        """
        response = await ctx.get("https://nekobot.xyz/api/image", type="tentacle")

        await self._format_generic_image(ctx, url=response["message"], provider="nekobot.xyz", colour=0x2F3136)


    @commands.command()
    @checks.bot_has_permissions(embed_links=True)
    async def thighs(self, ctx: commands.Context):
        """Sends a random image of thighs.
        (Bot Needs: Embed Links)
        """
        response = await ctx.get("https://nekobot.xyz/api/image", type="thigh")

        await self._format_generic_image(ctx, url=response["message"], provider="nekobot.xyz", colour=0x2F3136)


    @commands.command()
    @checks.bot_has_permissions(embed_links=True, add_reactions=True, read_message_history=True)
    @commands.cooldown(rate=1, per=5, type=commands.BucketType.member)
    async def yandere(self, ctx: commands.Context, *tags: _safe_tag):
        """Searches for something on Yande.re using the given tags.
        (Bot Needs: Embed Links, Add Reactions and Read Message History)

        EXAMPLE:
        (Ex. 1) yandere brown_hair
        (Ex. 2) yandere text two-tone_hair
        """
        if not tags:
            await ctx.send("You must enter at least one tag to search for.")
            return

        await ctx.trigger_typing()
        results = await ctx.get("https://yande.re/post/index.json", limit=100, tags=" ".join(tags), cache=True)

        if not results:
            await ctx.send("No results found.")
            return

        posts = [r for r in results if not _has_any_banned_tags(r["tags"])]
        if not posts:
            # We probably won't ever get to this point.
            await ctx.send("All results involve banned content on Discord.")
            return

        base_embed = Embed(title="Yande.re", colour=0xFF9ED0)
        base_embed.set_footer(text="Powered by yande.re")

        embeds = []
        for post in posts:
            embed = base_embed.copy()
            embed.set_author(name=post["author"])
            embed.set_image(url=post["file_url"])
            embed.timestamp = datetime.utcfromtimestamp(post["created_at"])

            sauce = post["source"]
            if sauce:
                embed.add_field(name="Source", value=sauce)

            embeds.append(embed)

        await ctx.paginate(reaction_menus.EmbedSource(embeds))


def setup(bot):
    bot.add_cog(NSFW())
