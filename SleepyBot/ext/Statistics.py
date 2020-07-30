"""
© Copyright 2018-2020 HitchedSyringe, All Rights Reserved.

Redistributing, using or owning a copy of this software without explicit permissions
is against these licensing terms, your license(s) to this software can be revoked at
any time without explicit notice beforehand and at the time of revocation.
Your license is non-transferrable, the terms of this license only permit you to do the
following; Create pull requests and make modifications to this repository.

"""


import asyncio
import logging
import os
import pkg_resources
import platform
import textwrap
import traceback
from collections import Counter
from datetime import datetime

import discord
import psutil
from discord import Colour, Embed
from discord.ext import commands, tasks

from SleepyBot.utils import checks, formatting, reaction_menus


LOG = logging.getLogger(__name__)


class GatewayHandler(logging.Handler):
    """Logging handler that sends updates to a channel via a webhook."""

    def __init__(self, cog):
        self.cog = cog
        super().__init__(logging.INFO)


    def filter(self, record):
        return record.name in ("discord.gateway", "discord.shard")


    def emit(self, record):
        self.cog._gateway_record_queue.put_nowait(record)


class Statistics(commands.Cog,
                 command_attrs=dict(cooldown=commands.Cooldown(rate=2, per=3, type=commands.BucketType.member))):
    """Commands having to do with my usage statistics."""
    # ...also responsible for some logging & error handling stuff.

    def __init__(self, bot):
        self.bot = bot
        self.hook = bot.webhook
        self.process = psutil.Process()

        self._gateway_record_queue = asyncio.Queue(loop=bot.loop)

        self._gateway_handler = handler = GatewayHandler(self)
        logging.getLogger("discord").addHandler(handler)

        self._old_on_error = bot.on_error
        # Monkey patch the on_error.
        type(bot).on_error = on_error

        self._links = {
            "Invite": discord.utils.oauth_url(bot.user.id, discord.Permissions(388166)),
            **bot.config["Discord Bot Config"].getjson("links")
        }

        # The only non-blocking way to do this.
        self._notify_gateway_status.start()  # pylint: disable=maybe-no-member


    def cog_unload(self):
        self._notify_gateway_status.cancel()  # pylint: disable=maybe-no-member
        logging.getLogger("discord").removeHandler(self._gateway_handler)

        type(self.bot).on_error = self._old_on_error


    @tasks.loop()
    async def _notify_gateway_status(self) -> None:
        """Constantly looping task loop that sends updates for any gateway events.
        For internal use only.
        """
        record = await self._gateway_record_queue.get()

        created = datetime.utcfromtimestamp(record.created)

        levels = {
            "INFO": "\N{INFORMATION SOURCE}",
            "WARNING": "\N{WARNING SIGN}",
        }
        level = levels.get(record.levelname, "\N{CROSS MARK}")

        status_message = f"{level} `[{created:%a, %b %d, %Y @ %#I:%M %p} UTC] {record.message}`"
        await self.hook.send(status_message, username="Gateway Status", avatar_url="https://i.imgur.com/4PnCKB3.png")


    @staticmethod
    def _get_brief_guild_info(guild, joined: bool) -> Embed:
        """Formats the joined/left guild info into a brief and simple to read embed.
        For internal use only.
        """
        if joined:
            embed = Embed(title="Joined a new guild!", colour=0x36BF38, timestamp=guild.me.joined_at)
        else:
            embed = Embed(title="Left a guild...", colour=0xF74519)

        embed.set_thumbnail(url=guild.icon_url)
        guild_info = (
            f"**Name:** {guild.name}",
            f"**ID:** {guild.id}",
            f"**Owner:** {guild.owner} (ID: {guild.owner.id})",
            f"**Members:** {guild.member_count:,d}",
            f"**Channels:** {len(guild.channels):,d}",
            f"**Guild Created:** {guild.created_at:%a, %b %d, %Y @ %#I:%M %p} UTC",
            f"**Shard ID:** {guild.shard_id if guild.shard_id is not None else 'N/A'}",
        )
        embed.description = "\n".join(f"<:arrow:713872522608902205> {entry}" for entry in guild_info)
        embed.set_footer(text="Showing brief information.")

        return embed


    @commands.Cog.listener()
    async def on_command(self, ctx: commands.Context) -> None:
        location = f"{ctx.guild} (ID: {ctx.guild.id})" if ctx.guild is not None else "DMs"
        LOG.info("[Command | %s] %s (ID: %s) >> %s", location, ctx.author, ctx.author.id, ctx.message.content)
        self.bot.command_stats[ctx.command.qualified_name] += 1


    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error) -> None:
        if not isinstance(error, (commands.CommandInvokeError, commands.ConversionError)):
            return

        error = getattr(error, "original", error)

        try:
            await ctx.send(
                f">>> **Something went wrong...**\n```py\n{type(error).__name__}: {error}\n```\n"
                "The above error was automatically reported to my developer(s)."
            )
        except discord.HTTPException:
            pass

        tb = "".join(traceback.format_exception(type(error), error, error.__traceback__, 4))

        embed = Embed(
            title="Command Error",
            colour=Colour.red(),
            description=f"```py\n{tb}\n```",
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="**Command Name**", value=ctx.command.qualified_name)
        embed.add_field(name="**Invoker**", value=f"{ctx.author} (ID: {ctx.author.id})")

        guild_info = f"{ctx.guild} (ID: {ctx.guild.id})" if ctx.guild is not None else "None (DMs)"
        embed.add_field(
            name="**Location**",
            value=f"**Guild:** {guild_info}\n**Channel:** {ctx.channel} (ID: {ctx.channel.id})",
            inline=False
        )
        embed.add_field(
            name="**Message Content**",
            value=textwrap.shorten(ctx.message.content, width=512),
            inline=False
        )

        #details = "\n".join(f"{field.name}: {field.value}".replace('\n', ' | ') for field in embed.fields)
        #LOG.error("The following exception occurred:\n%s\n---Traceback---\n%s", details, tb)

        await self.hook.send(embed=embed)


    @commands.Cog.listener()
    async def on_guild_join(self, guild) -> None:
        if guild in self.bot.blocklist:
            # I might consider putting some kind of alert system here, but at the end of the day,
            # the bot just instantly leaves the server so it probably doesn't even matter.
            return
        await self.hook.send(embed=self._get_brief_guild_info(guild, joined=True))


    @commands.Cog.listener()
    async def on_guild_remove(self, guild) -> None:
        if guild in self.bot.blocklist:
            # Don't log our insta-leave.
            return
        await self.hook.send(embed=self._get_brief_guild_info(guild, joined=False))


    @commands.Cog.listener()
    async def on_socket_response(self, message) -> None:
        self.bot.socket_stats[message.get("t")] += 1


    @commands.command(aliases=["info", "botinfo"])
    @checks.bot_has_permissions(embed_links=True)
    async def about(self, ctx: commands.Context):
        """Shows information about me.
        (Bot Needs: Embed Links)
        """
        embed = Embed(colour=0x2F3136, title="About Me", description=ctx.bot.description)
        embed.set_author(name=ctx.me)
        embed.set_thumbnail(url=ctx.me.avatar_url_as(static_format="png"))

        unique = len(ctx.bot.users)

        # Get member, online member, text channel, voice channel, category channel and guild count.
        members = 0
        online = 0
        text = 0
        voice = 0
        category = 0
        guilds = 0
        for guild in ctx.bot.guilds:
            guilds += 1
            text += len(guild.text_channels)
            voice += len(guild.voice_channels)
            category += len(guild.categories)
            for member in guild.members:
                members += 1
                if member.status is not discord.Status.offline:
                    online += 1

        created_ago = formatting.parse_duration(datetime.utcnow() - ctx.me.created_at, brief=True)

        general_info = (
            f"**Owner:** {ctx.bot.app_owner}",
            f"**Created:** {created_ago} ago ({ctx.me.created_at:%a, %b %d, %Y @ %#I:%M %p} UTC)",
            f"**Version:** {ctx.bot.version}",
            f"**Servers:** {guilds:,d}",
            (
                f"**Channels:** {text:,d} <:text_channel:587389191550271488> | "
                f"{voice:,d} <:voice_channel:587389191524974592> | {category:,d} 📁 "
                f"| {text + voice + category:,d} total"
            ),
            f"**Members:** {members:,d} total | {unique:,d} unique | {online:,d} online",
        )
        embed.add_field(
            name="**General**",
            value="\n".join(f"<:arrow:713872522608902205> {entry}" for entry in general_info),
            inline=False
        )

        python_version = platform.python_version()
        python_url = f"https://www.python.org/downloads/release/python-{python_version.replace('.', '')}/"
        discordpy_version = pkg_resources.get_distribution("discord.py").version

        loaded = len(ctx.bot.extensions)
        total_exts = len(ctx.bot.all_exts)

        used_commands = sum(ctx.bot.command_stats.values())
        registered_commands = len(ctx.bot.commands)

        memory_usage = self.process.memory_full_info().uss / 1024**2
        cpu_usage = self.process.cpu_percent() / psutil.cpu_count()

        technical_info = (
            (
                f"**Running:** [Python {python_version}]({python_url}) | "
                f"[discord.py {discordpy_version}](https://www.github.com/Rapptz/discord.py/)"
            ),
            f"**Uptime:** {formatting.parse_duration(datetime.utcnow() - ctx.bot.start_time)}",
            f"**Booted:** {ctx.bot.start_time:%a, %b %d, %Y @ %#I:%M %p} UTC",
            f"**Memory Usage:** {memory_usage:.2f} MiB",
            f"**CPU Usage:** {cpu_usage:.2f}%",
            f"**Commands:** {registered_commands} registered | {used_commands:,d} used",
            f"**Extensions:** {total_exts} total | {loaded} loaded | {total_exts - loaded} unloaded",
            f"**Shards:** {ctx.bot.shard_count}",
        )
        embed.add_field(
            name="**Technical**",
            value="\n".join(f"<:arrow:713872522608902205> {entry}" for entry in technical_info),
            inline=False
        )

        embed.add_field(
            name="**My Links**",
            value="\n".join(f"[{n}]({l})" for n, l in self._links.items()),
            inline=False
        )

        embed.set_footer(text="Now rewritten twice woooo!")

        await ctx.send(embed=embed)


    @commands.command(hidden=True)
    @commands.is_owner()
    @checks.bot_has_permissions(embed_links=True)
    async def bothealth(self, ctx: commands.Context):
        """Shows a brief summary of my current health. (Owner only)"""
        # Lots of private methods being used here since there isn't a cleaner way of doing this.

        embed = Embed(title="Bot Health Diagnosis", timestamp=datetime.utcnow())

        spammers = [entity for entity, bucket in self.bot.spam_control._cache.items() if bucket._tokens == 0]

        embed.add_field(
            name=f"**Current Spammers [{len(spammers)}]**",
            value="\n".join(spammers) or "None",
            inline=False
        )

        tasks_dir = os.path.join("discord", "ext", "tasks", "__init__")
        ext_dir = str(self.bot.exts_directory)
        event_waiters = []
        inner_tasks = []
        bad_inner_tasks = []
        for task in asyncio.all_tasks(loop=self.bot.loop):
            if 'Client._run_event' in repr(task) and not task.done():
                event_waiters.append(task)

            if ext_dir in repr(task) or tasks_dir in repr(task):
                inner_tasks.append(task)

                if task.done() and task._exception is not None:
                    bad_inner_tasks.append(hex(id(task)))

        embed.add_field(
            name=f"**Internal Tasks [{len(inner_tasks)}]**",
            value=f"**Failed ({len(bad_inner_tasks)}):** {', '.join(bad_inner_tasks) or None}",
            inline=False
        )

        global_ratelimit = not self.bot.http._global_over.is_set()

        if global_ratelimit:
            embed.colour = Colour.dark_red()
        elif bad_inner_tasks or spammers:
            embed.colour = Colour.orange()
        else:
            embed.colour = Colour.green()

        memory_usage = self.process.memory_full_info().uss / 1024**2
        cpu_usage = self.process.cpu_percent() / psutil.cpu_count()

        description = (
            f"**Memory Usage:** {memory_usage:.2f} MiB",
            f"**CPU Usage:** {cpu_usage:.2f}%",
            f"**Events Waiting:** {len(event_waiters)}",
            f"**Global Ratelimit:** {global_ratelimit}",
        )
        embed.description = "\n".join(f"<:arrow:713872522608902205> {entry}" for entry in description)

        await ctx.send(embed=embed)


    @commands.command(aliases=["cs"], hidden=True)
    @commands.is_owner()
    @checks.bot_has_permissions(add_reactions=True, read_message_history=True)
    async def commandstats(self, ctx: commands.Context):
        """Shows command usage data for the current session. (Owner only)"""
        counter = self.bot.command_stats
        if counter:
            total = sum(counter.values())
            uptime = datetime.utcnow() - self.bot.start_time
            per_minute = total / (uptime.total_seconds() / 60)
            chart = formatting.tchart(counter.most_common())

            data = f"{total} total commands used. ({per_minute:.2f}/min):\n```py\n{chart}\n```"
            await ctx.paginate(reaction_menus.ContentSource(data, show_page_numbers=False))
        else:
            # Probably niche since this will only be seen if this command was the first command run.
            await ctx.send("No commands have been used yet.\nTry this command again later.")


    @commands.command(aliases=["wss"])
    @checks.bot_has_permissions(add_reactions=True, read_message_history=True)
    @commands.cooldown(rate=1, per=5, type=commands.BucketType.member)
    async def socketstats(self, ctx: commands.Context):
        """Shows observed websocket response data for the current session."""
        counter = self.bot.socket_stats
        total = sum(counter.values())
        uptime = datetime.utcnow() - self.bot.start_time
        per_minute = total / (uptime.total_seconds() / 60)
        chart = formatting.tchart(counter.most_common())

        data = f"{total} total websocket events observed. ({per_minute:.2f}/min):\n```py\n{chart}\n```"
        await ctx.paginate(reaction_menus.ContentSource(data, show_page_numbers=False))


    @commands.command()
    async def uptime(self, ctx: commands.Context):
        """Shows my uptime, including the time I was booted up."""
        uptime = formatting.parse_duration(datetime.utcnow() - ctx.bot.start_time)
        await ctx.send(f"```ldif\nUptime: {uptime}\nBooted: {ctx.bot.start_time:%a, %b %d, %Y @ %#I:%M %p} UTC\n```")


async def on_error(self, event: str, *args, **kwargs) -> None:
    embed = Embed(
        title="Event Error",
        description=f"```py\n{traceback.format_exc()}\n```",
        colour=Colour.dark_red(),
        timestamp=datetime.utcnow()
    )
    embed.add_field(name="Event", value=event, inline=False)

    arguments = "\n".join(f"[{index}]: {argument}" for index, argument in enumerate(args))
    embed.add_field(name="Arguments", value=f"```py\n{arguments or None}\n```", inline=False)

    # keyword_arguments = "\n".join(f"[{index}]: {key} | {value}" for index, key, value in enumerate(kwargs.items()))
    # embed.add_field(name="Keyword Arguments", value=f"```py\n{keyword_arguments or None}\n```", inline=False)

    await self.webhook.send(embed=embed)


def setup(bot):
    # Allows preservation of the counters if this cog gets unloaded.
    if not hasattr(bot, "command_stats"):
        bot.command_stats = Counter()

    if not hasattr(bot, "socket_stats"):
        bot.socket_stats = Counter()

    bot.add_cog(Statistics(bot))
