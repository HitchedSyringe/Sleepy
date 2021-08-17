"""
Copyright (c) 2018-present HitchedSyringe

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""


from datetime import datetime

from discord import Colour, Embed
from discord.ext import commands
from sleepy import checks, converters, menus
from sleepy.http import HTTPRequestFailed


NEKOBOT_IMAGE_COMMANDS = (
    {
        "name": "anal",
        "help": "Sends a random image of an4l.",
    },
    {
        "name": "analhentai",
        "help": "Sends a random image of an4l h3nt4i.",
        "type": "hanal",
    },
    {
        "name": "animeass",
        "aliases": ("aass",),
        "help": "Sends a random image of anime 4$$.",
        "type": "hass",
    },
    {
        "name": "animeboobs",
        "aliases": ("animetits", "animetitties"),
        "help": "Sends a random image of anime b00bs.",
        "type": "hboobs",
    },
    {
        "name": "animemidriff",
        "aliases": ("amidriff",),
        "help": "Sends a random image of anime midriff.",
        "type": "hmidriff",
    },
    {
        "name": "animethighs",
        "aliases": ("athighs",),
        "help": "Sends a random image of anime thighs.",
        "type": "hthigh",
    },
    {
        "name": "ass",
        "help": "Sends a random image of 4$$.",
    },
    {
        "name": "boobs",
        "aliases": ("tits", "titties"),
        "help": "Sends a random image of b00bs.",
    },
    {
        "name": "4Knude",
        "aliases": ("4knude", "fourknude"),
        "help": "Sends nud3s in crisp 4K resolution.",
        "type": "4k",
    },
    {
        "name": "hentai",
        "help": "Sends a random h3nt41 image.",
    },
    # NOTE: This was intentionally left out due to some
    # images seemingly depicting what looks, to me at
    # least, like underage characters. I've left this
    # commented here in case NekoBot decides to remove
    # the offending images from the serving pool.
    # {
    #     "name": "nekohentai",
    #     "aliases": ("catgirlhentai",),
    #     "help": "Sends a random catgirl h3nt41 image.",
    #     "type": "hneko",
    # },
    {
        "name": "lewdkitsune",
        "help": "Sends a random image of l3wd kitsunes.",
        "type": "hkitsune",
    },
    {
        "name": "paizuri",
        "help": "Sends a random image of p41zur1.",
    },
    {
        "name": "porngif",
        "aliases": ("pgif",),
        "help": "Sends a random pr0n GIF.",
        "type": "pgif",
    },
    {
        "name": "pussy",
        "help": "Sends a random image of pu$$y.",
    },
    {
        "name": "tentacle",
        "aliases": ("tentai",),
        "help": "You've seen enough to know what this entails.",
    },
    {
        "name": "thighs",
        "help": "Sends a random image of thighs.",
        "type": "thigh",
    },
    {
        "name": "yaoi",
        "help": "Sends a random y401 image.",
    },
)


# These bans are mostly generalised.
NSFW_TAG_BLOCKLIST = (
    "adolescent",
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


def has_any_banned_tags(tags):
    return any(t in NSFW_TAG_BLOCKLIST for t in tags)


def ensure_safe_tags(value):
    value = value.lower()

    # We do this to ensure that nobody bypasses the filter
    # just by passing in something like "banned_tag tag".
    # This also allows people to use quotes without any
    # trouble.
    if has_any_banned_tags(value.split()):
        raise commands.BadArgument(
            "One or more tags involve banned content on Discord."
        )

    return value


# neckbeard cog but even worse.
class NSFW(
    commands.Cog,
    command_attrs={"cooldown": commands.Cooldown(2, 5, commands.BucketType.member)}
):
    """Don't act like you don't already know what this encompasses."""

    def __init__(self, config):
        self.saucenao_api_key = config["saucenao_api_key"]

        # Same process and reasoning as in Weeb.
        for attrs in NEKOBOT_IMAGE_COMMANDS:
            attrs["help"] += "\n\n(Bot Needs: Embed Links)"

            @commands.command(**attrs)
            @commands.bot_has_permissions(embed_links=True)
            async def nekobot_image_command(cog, ctx):
                resp = await ctx.get(
                    "https://nekobot.xyz/api/image",
                    type=ctx.command.__original_kwargs__.get("type", ctx.command.name)
                )

                embed = Embed(colour=Colour(resp["color"]))
                embed.set_image(url=resp["message"])
                embed.set_footer(text="Powered by nekobot.xyz")

                await ctx.send(embed=embed)

            nekobot_image_command.cog = self

            self.__cog_commands__ += (nekobot_image_command,)

    async def cog_check(self, ctx):
        if ctx.guild is not None and not ctx.channel.is_nsfw():
            raise commands.NSFWChannelRequired(ctx.channel)

        return True

    async def cog_command_error(self, ctx, error):
        if isinstance(error, commands.NSFWChannelRequired):
            await ctx.send("This command can only be used in an NSFW channel.")
            error.handled__ = True
        elif isinstance(error, commands.BadArgument):
            await ctx.send(error)
            error.handled__ = True

    @staticmethod
    def safe_query(tags, sep, *, exclude_prefix):
        return (
            sep.join(tags)
            + sep
            + sep.join(exclude_prefix + t for t in NSFW_TAG_BLOCKLIST)
        )

    @commands.command(require_var_positional=True)
    @checks.can_start_menu(check_embed=True)
    @commands.cooldown(1, 5, commands.BucketType.member)
    async def danbooru(self, ctx, *tags: ensure_safe_tags):
        """Searches for something on Danbooru using the given tags.

        Due to a Danbooru limitation, you can only search
        for up to two tags at a time.

        (Bot Needs: Embed Links, Add Reactions, and Read Message History)

        **EXAMPLES:**
        ```bnf
        <1> danbooru long_hair
        <2> danbooru uniform two-tone_hair
        ```
        """
        await ctx.trigger_typing()

        try:
            resp = await ctx.get(
                "https://danbooru.donmai.us/post/index.json?limit=200",
                cache__=True,
                tags=" ".join(tags)
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
            if has_any_banned_tags(post["tags"]):
                continue

            try:
                url = post["file_url"]
            except KeyError:
                continue

            embed = Embed(
                description=f"[Media Link]({url})",
                colour=0x9EECFF,
                timestamp=datetime.strptime(post["created_at"], "%Y-%m-%d %H:%M:%S")
            )
            embed.set_author(name=post["author"])
            embed.set_image(url=url)
            embed.set_footer(text="Powered by danbooru.donmai.us")

            if sauce := post["source"]:
                embed.add_field(name="Source", value=sauce)

            embeds.append(embed)

        if not embeds:
            await ctx.send(
                "All results either involve banned content on "
                "Discord or, for some reason, lack image links."
            )
        else:
            await ctx.paginate(menus.EmbedSource(embeds))

    @commands.command(require_var_positional=True)
    @checks.can_start_menu(check_embed=True)
    @commands.cooldown(1, 5, commands.BucketType.member)
    async def e621(self, ctx, *tags: ensure_safe_tags):
        """Searches for something on E621 using the given tags.

        Due to an E621 limitation, you can only search
        for up to 40 tags at a time.

        (Bot Needs: Embed Links, Add Reactions, and Read Message History)

        **EXAMPLES:**
        ```bnf
        <1> e621 brown_hair
        <2> e621 feline two-tone_hair
        ```
        """
        await ctx.trigger_typing()

        try:
            resp = await ctx.get(
                "https://e621.net/posts.json",
                cache__=True,
                tags=" ".join(tags)
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
                timestamp=datetime.strptime(post["created_at"], "%Y-%m-%dT%H:%M:%S.%f-04:00")
            )
            embed.set_image(url=url)
            embed.set_footer(text="Powered by e621.net")

            if sauces := post["sources"]:
                embed.add_field(name="Source(s)", value="\n".join(sauces))

            embeds.append(embed)

        if not embeds:
            await ctx.send("All results lack image links for some reason.")
        else:
            await ctx.paginate(menus.EmbedSource(embeds))

    @commands.command(aliases=("r34",), require_var_positional=True)
    @checks.can_start_menu(check_embed=True)
    @commands.cooldown(1, 5, commands.BucketType.member)
    async def rule34(self, ctx, *tags: ensure_safe_tags):
        """Searches for something on Rule34 using the given tags.

        (Bot Needs: Embed Links, Add Reactions, and Read Message History)

        **EXAMPLES:**
        ```bnf
        <1> rule34 brown_hair
        <2> rule34 speech_bubble two-tone_hair
        ```
        """
        await ctx.trigger_typing()

        resp = await ctx.get(
            "https://rule34.xxx/index.php?page=dapi&s=post&q=index&json=1&limit=100",
            cache__=True,
            tags=self.safe_query(tags, " ", exclude_prefix="-")
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

        await ctx.paginate(menus.EmbedSource(embeds))

    @commands.command(aliases=("sauce",))
    @checks.can_start_menu(check_embed=True)
    @commands.cooldown(1, 8, commands.BucketType.member)
    async def saucenao(
        self,
        ctx,
        *,
        image: converters.ImageAssetConverter(max_filesize=20_000_000)
    ):
        """Reverse searches an image using SauceNAO.

        Image can either be a user, custom emoji, link, or
        attachment. Links and attachments must be under 20
        MB.

        (Bot Needs: Embed Links, Add Reactions, and Read Message History)
        """
        await ctx.trigger_typing()

        resp = await ctx.get(
            "https://saucenao.com/search.php?db=999&output_type=2&numres=24",
            api_key=self.saucenao_api_key,
            url=str(image)
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

            if (urls := data.pop("ext_urls", None)) is not None:
                embed.add_field(name="External Links", value="\n".join(urls))

            embed.description = "\n".join(
                f"**{k.replace('_', ' ').title()}:** "
                # For whatever reason, Xamayon decided that it was okay
                # to leave the creator field as a list for index ID 38.
                f"{', '.join(v) if k == 'creator' and meta['index_id'] == 38 else v}"
                for k, v in data.items()
            )

            embeds.append(embed)

        await ctx.paginate(menus.EmbedSource(embeds))

    @commands.command(require_var_positional=True)
    @checks.can_start_menu(check_embed=True)
    @commands.cooldown(1, 5, commands.BucketType.member)
    async def yandere(self, ctx, *tags: ensure_safe_tags):
        """Searches for something on Yande.re using the given tags.

        Due to a Yande.re limitation, you can only search
        for up to 6 tags at a time.

        (Bot Needs: Embed Links, Add Reactions, and Read Message History)

        **EXAMPLES:**
        ```bnf
        <1> yandere brown_hair
        <2> yandere text two-tone_hair
        ```
        """
        await ctx.trigger_typing()

        try:
            resp = await ctx.get(
                "https://yande.re/post.json?limit=100",
                cache__=True,
                tags=" ".join(tags)
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
            if has_any_banned_tags(post["tags"]):
                continue

            media_url = post["file_url"]

            embed = Embed(
                description=f"[Media Link]({media_url})",
                colour=0xFF9ED0,
                timestamp=datetime.utcfromtimestamp(post["created_at"])
            )
            embed.set_author(name=post["author"])
            embed.set_image(url=media_url)
            embed.set_footer(text="Powered by yande.re")

            if sauce := post["source"]:
                embed.add_field(name="Source", value=sauce)

            embeds.append(embed)

        if not embeds:
            await ctx.send("All results involve banned content on Discord")
        else:
            await ctx.paginate(menus.EmbedSource(embeds))


def setup(bot):
    bot.add_cog(NSFW(bot.config))
