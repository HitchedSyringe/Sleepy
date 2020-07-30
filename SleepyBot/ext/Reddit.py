"""
© Copyright 2018-2020 HitchedSyringe, All Rights Reserved.

Redistributing, using or owning a copy of this software without explicit permissions
is against these licensing terms, your license(s) to this software can be revoked at
any time without explicit notice beforehand and at the time of revocation.
Your license is non-transferrable, the terms of this license only permit you to do the
following; Create pull requests and make modifications to this repository.

"""


import io
import re
import yarl

import discord
from discord import Embed
from discord.ext import commands

from SleepyBot.utils import checks, formatting, reaction_menus
from SleepyBot.utils.requester import HTTPError


# Merely an attempt to save requests.
def _clean_subreddit(value: str) -> str:
    """Pseudo-converter that cleans up any r/ and /r/ arguments and returns the raw subreddit name.
    Raises :exc:`commands.BadArgument` if the name doesn't meet Reddit's subreddit naming convention.
    """
    reddit_match = re.fullmatch(r"(?:\/?r\/)?([\w\-]{1,21})", value)

    if reddit_match is None:
        raise commands.BadArgument("Invalid subreddit.")
    return reddit_match.group(1)


class MediaSubmissionURL(commands.Converter):
    """Converts a v.redd.it submission into a Reddit video URL.
    This also works for normal Reddit submission URLs.
    """
    # We need to compile the regex before finding matches.
    # re.match doesn't seem to like yarl.URL...
    VALID_PATH = re.compile(r"/r/[\w\-]{1,21}/comments/[A-Za-z0-9]+(?:/.+)?")

    async def convert(self, ctx: commands.context, argument):
        try:
            url = yarl.URL(argument.strip("<>"))
        except:
            raise commands.BadArgument("Invalid link.") from None

        await ctx.trigger_typing()
        if url.host == "v.redd.it":
            # If we got v.redd.it, we'll have to fetch the "main" url.
            async with ctx.session.get(url) as response:
                url = response.url

        if not url.host.endswith(".reddit.com") and self.VALID_PATH.match(url) is None:
            raise commands.BadArgument("Not a Reddit link.")

        try:
            response = await ctx.get(url / ".json", cache=True)
        except HTTPError as exc:
            raise commands.BadArgument(f"Reddit API failed with HTTP status code {exc.status}.") from None

        try:
            submission = response[0]["data"]["children"][0]["data"]
        except (KeyError, IndexError, TypeError):
            raise commands.BadArgument("Failed to get submission data.") from None

        try:
            media = submission["media"]["reddit_video"]
        except (KeyError, TypeError):
            # Handle crossposts.
            try:
                media = submission["crosspost_parent_list"][0]["media"]["reddit_video"]
            except (KeyError, IndexError, TypeError):
                raise commands.BadArgument("Failed to get media information") from None

        try:
            return yarl.URL(media["fallback_url"])
        except KeyError:
            raise commands.BadArgument("Failed to get fallback link.") from None


class Reddit(commands.Cog,
             command_attrs=dict(cooldown=commands.Cooldown(rate=1, per=5, type=commands.BucketType.member))):
    """Commands related to Reddit."""

    async def cog_command_error(self, ctx, error):
        error = getattr(error, "original", error)

        if isinstance(error, commands.BadArgument):
            # This is an attempt to make this less confusing for the end-user.
            raw_error = str(error)
            if not raw_error.startswith("Invalid"):
                await ctx.send(raw_error)
                error.handled = True


    @commands.command()
    @checks.bot_has_permissions(embed_links=True, add_reactions=True, read_message_history=True)
    async def reddit(self, ctx: commands.Context, subreddit: _clean_subreddit):
        """Shows a subreddit's top weekly submissions.
        (Bot Needs: Embed Links, Add Reactions and Read Message History)

        EXAMPLE:
        (Ex. 1) reddit help
        (Ex. 2) reddit r/help
        (Ex. 3) reddit /r/help
        """
        await ctx.trigger_typing()
        try:
            # Sort by top this week.
            response = await ctx.get(f"https://www.reddit.com/r/{subreddit}/.json?sort=top&t=week", cache=True)
        except HTTPError as exc:
            if exc.status == 403:  # private/quarantined
                await ctx.send("That subreddit is either private or quarantined and cannot be accessed.")
                return
            elif exc.status == 404:  # nonexistent/banned
                await ctx.send("That subreddit either wasn't found or is currently banned and cannot be accessed.")
                return
            raise

        embeds = []
        for child in response["data"]["children"]:
            post = child["data"]

            # Sort out NSFW posts if we're in an SFW channel.
            if not ctx.channel.is_nsfw() and post["over_18"]:
                continue

            embed = Embed(
                title=formatting.simple_shorten(post["title"], 128),
                description=formatting.simple_shorten(post["selftext"], 1024),
                url=f"https://www.reddit.com/{post['id']}",
                colour=0xFF5700
            )
            embed.set_author(
                name=f"/u/{post['author']} (Posted in /r/{subreddit})",
                url=f"https://www.reddit.com/user/{post['author']}"
            )
            embed.set_footer(text=f"👍 {post['ups']:,d} | Powered by Reddit")
            embed.set_image(url=post["url"])

            # -- Future proofing for whenever Reddit allows both selftext and images on posts I guess. --
            # Embeds can only take certain image types. This is just to prevent us from getting empty embeds.
            compatible_image = embed.image.url.lower().endswith(("png", "jpeg", "jpg", "gif", "gifv", "webp"))
            if not (compatible_image or embed.description):
                continue

            embeds.append(embed)

        if not embeds:
            await ctx.send("Either no posts were found or you're trying to browse an NSFW subreddit in an SFW channel.")
        else:
            await ctx.paginate(reaction_menus.EmbedSource(embeds))


    @commands.command(aliases=["vredditdownloader"])
    async def vreddit(self, ctx: commands.Context, *, url: MediaSubmissionURL):
        """Downloads a Reddit video submission.

        Both v.redd.it and regular Reddit links are supported.
        """
        # We have to directly use the session since our requester doesn't return response headers.
        async with ctx.session.get(url) as response:
            if response.status != 200:
                await ctx.send("Failed to download the video.")
                return

            filesize_limit = ctx.guild.filesize_limit if ctx.guild is not None else 8388608
            if int(response.headers["Content-Length"]) > filesize_limit:
                await ctx.send("The video is too big to be uploaded.")
                return

            data = await response.read()
            await ctx.send(file=discord.File(fp=io.BytesIO(data), filename=f"{url.parts[1]}.mp4"))


def setup(bot):
    bot.add_cog(Reddit())
