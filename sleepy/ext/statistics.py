"""
Copyright (c) 2018-present HitchedSyringe

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""


from __future__ import annotations

import asyncio
import logging
import textwrap
import traceback
from collections import Counter
from datetime import datetime, timezone
from os import path
from platform import python_version
from typing import TYPE_CHECKING, Any, Coroutine

import discord
import psutil
from discord import Colour, Embed
from discord.ext import commands, tasks
from discord.utils import format_dt

from sleepy import __version__
from sleepy.menus import BotLinksView, PaginatorSource
from sleepy.utils import human_delta, plural, tchart

if TYPE_CHECKING:
    from sleepy.bot import Sleepy
    from sleepy.context import Context as SleepyContext

    # Needs to be here in order to prevent overuse of `type: ignore`
    # due to monkey patches and custom attribute setting. This could
    # have been prevented by just simply adding these attributes to
    # the bot itself, but I'd rather keep this stuff separate.

    class StatsSleepy(Sleepy):
        identifies: int
        command_uses: Counter[str]
        socket_events: Counter[str]
        started_at: datetime

        _original_before_identify_hook: Coroutine[Any, Any, None]

    class StatsSleepyContext(SleepyContext):
        bot: StatsSleepy


_LOG: logging.Logger = logging.getLogger(__name__)


class GatewayWebhookHandler(logging.Handler):
    def __init__(self, bot: Sleepy) -> None:
        super().__init__(logging.INFO)

        self._queue: asyncio.Queue = asyncio.Queue()
        self._webhook: discord.Webhook = bot.webhook

        self._worker.start()

    @tasks.loop()
    async def _worker(self) -> None:
        rec = await self._queue.get()
        created = datetime.fromtimestamp(rec.created, timezone.utc)

        levels = {
            "INFO": "\N{INFORMATION SOURCE}\ufe0f",
            "WARNING": "\N{WARNING SIGN}\ufe0f",
        }
        lvl = levels.get(rec.levelname, "\N{CROSS MARK}")

        await self._webhook.send(
            textwrap.shorten(f"{lvl} [{format_dt(created, 'F')}] `{rec.message}`", 2000),
            username="Gateway Status",
            avatar_url="https://i.imgur.com/4PnCKB3.png",
        )

    def filter(self, record: logging.LogRecord) -> bool:
        return record.name in ("discord.gateway", "discord.shard")

    def emit(self, record: logging.LogRecord) -> None:
        self._queue.put_nowait(record)

    def close(self) -> None:
        self._worker.cancel()
        super().close()


class Statistics(
    commands.Cog,
    command_attrs={
        "cooldown": commands.CooldownMapping.from_cooldown(
            2, 3, commands.BucketType.member
        ),
    },
):
    """Commands having to do with statistics about me."""

    # ...also responsible for some logging & error handling stuff.

    ICON: str = "\N{BAR CHART}"

    def __init__(self, bot: StatsSleepy) -> None:
        self.bot: StatsSleepy = bot
        self.process: psutil.Process = psutil.Process()

        self.gw_handler = handler = GatewayWebhookHandler(bot)
        logging.getLogger("discord").addHandler(handler)

        bot._original_before_identify_hook = bot.before_identify_hook  # type: ignore

        # I decided to just monkey-patch this in rather than
        # including it in the bot class since I figured that
        # not everyone would want to be forced to use this.
        type(bot).before_identify_hook = _new_before_identify_hook  # type: ignore

        # Mainly for the ``about``` command. This removes the
        # need to iterate through guilds on each command invoke.
        self.total_guilds: int = 0
        self.total_members: int = 0
        self.total_text: int = 0
        self.total_voice: int = 0
        self.total_stage: int = 0

        name = "ext-statistics-cache-bot-counts"
        asyncio.create_task(self.cache_bot_counts(), name=name)

    def cog_unload(self) -> None:
        self.gw_handler.close()
        logging.getLogger("discord").removeHandler(self.gw_handler)

        # NOTE: We don't delete any statistics collected since doing
        # so would obliterate them every time this cog was reloaded.

        bot = self.bot

        type(bot).before_identify_hook = bot._original_before_identify_hook  # type: ignore
        del bot._original_before_identify_hook

    async def cache_bot_counts(self) -> None:
        await self.bot.wait_until_ready()

        for guild in self.bot.guilds:
            self.total_guilds += 1
            self.total_members += guild.member_count or 0
            self.total_text += len(guild.text_channels)
            self.total_voice += len(guild.voice_channels)
            self.total_stage += len(guild.stage_channels)

    async def send_brief_guild_info(self, guild: discord.Guild, *, joined: bool) -> None:
        member_count = guild.member_count
        bots = sum(m.bot for m in guild.members)

        embed = Embed(
            description=(
                f"\N{BLACK DIAMOND} **ID:** {guild.id}"
                f"\n\N{BLACK DIAMOND} **Owner:** {guild.owner} (ID: {guild.owner_id})"
                f"\n\N{BLACK DIAMOND} **Members:** {member_count or 0:,d} ({plural(bots, ',d'):bot})"
                f"\n\N{BLACK DIAMOND} **Channels:** {len(guild.channels)}"
                f"\n\N{BLACK DIAMOND} **Created:** {format_dt(guild.created_at, 'R')}"
                f"\n\N{BLACK DIAMOND} **Shard ID:** {guild.shard_id or 'N/A'}"
            ),
            timestamp=datetime.now(timezone.utc),
        )
        embed.set_author(name=guild)
        embed.set_thumbnail(url=guild.icon)

        if joined:
            embed.title = "Joined a new server!"

            if member_count is not None and (ratio := bots / member_count) > 0.5:
                embed.colour = 0xFFD257
                embed.add_field(
                    name="\N{WARNING SIGN} Potential Bot Farm Alert \N{WARNING SIGN}",
                    value="__Heads up! This server could be a bot farm.__"
                    "\nThis server was automatically flagged due to bots making"
                    f" up around **{ratio:.2%}** of its membership.",
                )
            else:
                embed.colour = 0x36BF38
        else:
            embed.title = "Left a server..."
            embed.colour = 0xF74519

        await self.bot.webhook.send(embed=embed)

    @commands.Cog.listener()
    async def on_command(self, ctx: StatsSleepyContext) -> None:
        ctx.bot.command_uses[ctx.command.qualified_name] += 1

    @commands.Cog.listener()
    async def on_command_error(self, ctx: SleepyContext, error: Exception) -> None:
        if (
            not isinstance(error, (commands.CommandInvokeError, commands.ConversionError))
            or ctx._already_handled_error
        ):
            return

        error = error.original

        fmt = (
            'Unhandled exception in command "%s":'
            "\nInvoker: %s (ID: %s)"
            "\nChannel: %s (ID: %s)"
            "\nContent: %s"
        )

        _LOG.exception(
            fmt,
            ctx.command.qualified_name,
            ctx.author,
            ctx.author.id,
            ctx.channel,
            ctx.channel.id,
            ctx.message.content,
            exc_info=error,
        )

        tb = traceback.format_exception(None, error, error.__traceback__, 4)

        embed = Embed(
            title="Command Error",
            description=f"```py\n{''.join(tb)}```",
            colour=Colour.red(),
        )
        embed.set_footer(text=f"Sent from: {ctx.channel} (ID: {ctx.channel.id})")

        embed.add_field(name="Command Name", value=ctx.command.qualified_name)
        embed.add_field(name="Invoker", value=f"{ctx.author} (ID: {ctx.author.id})")
        embed.add_field(
            name="Content",
            value=textwrap.shorten(ctx.message.content, width=512),
            inline=False,
        )

        await self.bot.webhook.send(embed=embed)

        try:
            await ctx.send(
                f"**Ah, Houston, we've had a problem.**```py\n{tb[-1]}```"
                "\nI've relayed some details about this to my higher-ups."
            )
        except discord.HTTPException:
            pass

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild) -> None:
        self.total_guilds += 1
        self.total_members += guild.member_count or 0
        self.total_text += len(guild.text_channels)
        self.total_voice += len(guild.voice_channels)
        self.total_stage += len(guild.stage_channels)

        await self.send_brief_guild_info(guild, joined=True)

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild) -> None:
        self.total_guilds -= 1
        self.total_members -= guild.member_count or 0
        self.total_text -= len(guild.text_channels)
        self.total_voice -= len(guild.voice_channels)
        self.total_stage -= len(guild.stage_channels)

        await self.send_brief_guild_info(guild, joined=False)

    @commands.Cog.listener()
    async def on_socket_event_type(self, event_type: str) -> None:
        self.bot.socket_events[event_type] += 1

    @commands.command(aliases=("info", "botinfo"))
    @commands.bot_has_permissions(embed_links=True)
    async def about(self, ctx: StatsSleepyContext) -> None:
        """Shows information about me.

        (Bot Needs: Embed Links)
        """
        embed = Embed(
            description=ctx.bot.description or ctx.bot.application.description,  # type: ignore
            colour=0x2F3136,
        )
        embed.set_author(name=ctx.me)
        embed.set_thumbnail(url=ctx.me.display_avatar.with_format("png"))
        embed.set_footer(text="Check out our links using the buttons below!")

        embed.add_field(
            name="About Me",
            value=(
                f"<:ar:862433028088135711> **Owner:** {ctx.bot.owner}"
                f"\n<:ar:862433028088135711> **Created:** {format_dt(ctx.me.created_at, 'R')}"
                f"\n<:ar:862433028088135711> **Booted:** {format_dt(ctx.bot.started_at, 'R')}"
                f"\n<:ar:862433028088135711> **Servers:** {self.total_guilds:,d}"
                "\n<:ar:862433028088135711> **Channels:**"
                f" <:tc:828149291812913152> {self.total_text:,d}"
                f" \N{BULLET} <:vc:828151635791839252> {self.total_voice:,d}"
                f" \N{BULLET} <:sc:828149291750785055> {self.total_stage:,d}"
                f"\n<:ar:862433028088135711> **Members:** {self.total_members:,d}"
                f" ({len(ctx.bot.users):,d} unique)"
            ),
        )
        embed.add_field(
            name="Technical Information",
            value=(
                f"\N{CRESCENT MOON} {__version__}"
                f" \N{BULLET} <:py:823367531724537887> {python_version()}"
                f" \N{BULLET} <:dpy:823367531690590248> {discord.__version__}"
                "\n<:ar:862433028088135711> **Memory Usage:**"
                f" {self.process.memory_full_info().uss / 1024**2:.2f} MiB"
                "\n<:ar:862433028088135711> **CPU Usage:**"
                f" {self.process.cpu_percent() / psutil.cpu_count():.2f}%"
                f"\n<:ar:862433028088135711> **Commands:** {len(ctx.bot.commands)}"
                f" ({sum(ctx.bot.command_uses.values()):,d} used)"
                f"\n<:ar:862433028088135711> **Extensions:** {len(ctx.bot.extensions)}"
                f"\n<:ar:862433028088135711> **Shards:** {ctx.bot.shard_count or 'N/A'}"
            ),
            inline=False,
        )

        await ctx.send(embed=embed, view=BotLinksView(ctx.me.id))

    @commands.command(hidden=True)
    @commands.is_owner()
    @commands.bot_has_permissions(embed_links=True)
    async def bothealth(self, ctx: SleepyContext) -> None:
        """Shows a brief summary of my current health.

        This command can only be used by my higher-ups.
        """
        # Lots of private methods being used here since
        # there isn't a cleaner way of doing this.

        embed = Embed(
            title="Health Diagnosis",
            colour=Colour.green(),
            timestamp=datetime.now(timezone.utc),
        )

        spammers = [e for e, b in ctx.bot._spam_control._cache.items() if b._tokens == 0]

        if spammers:
            embed.add_field(
                name=f"Spammers \N{BULLET} {len(spammers)}",
                value="\n".join(spammers) or "None",
                inline=False,
            )
            embed.colour = Colour.orange()

        tasks_dir = path.join("discord", "ext", "tasks", "__init__")
        # NOTE: Tasks status tracking won't exactly work well
        # if this extension is not in the actual configured
        # extensions directory. Furthermore, this also wont
        # work on any extensions outside of the directory
        # that this extension resides in.
        exts_dir = path.dirname(__file__)

        events = 0
        internal = 0
        bad_internal = []

        for task in asyncio.all_tasks(loop=ctx.loop):
            task_repr = repr(task)

            if exts_dir in task_repr or tasks_dir in task_repr:
                internal += 1

                if task.done() and task._exception is not None:
                    bad_internal.append(hex(id(task)))
                    continue

            if not task.done() and "Client._run_event" in task_repr:
                events += 1

        if bad_internal:
            embed.add_field(
                name=f"Failed Internal Tasks \N{BULLET} {len(bad_internal)}",
                value=', '.join(bad_internal),
                inline=False,
            )
            embed.colour = Colour.orange()

        global_rl_hit = not ctx.bot.http._global_over.is_set()

        if global_rl_hit:
            embed.colour = Colour.dark_red()

        embed.description = (
            "<:ar:862433028088135711> **Memory Usage:**"
            f" {self.process.memory_full_info().uss / 1024**2:.2f} MiB"
            "\n<:ar:862433028088135711> **CPU Usage:**"
            f" {self.process.cpu_percent() / psutil.cpu_count():.2f}%"
            f"\n<:ar:862433028088135711> **Events Waiting:** {events}"
            f"\n<:ar:862433028088135711> **Internal Tasks:** {internal}"
            f"\n<:ar:862433028088135711> **Hit Global Ratelimit:** {global_rl_hit}"
        )

        await ctx.send(embed=embed)

    @commands.command(aliases=("cs",), hidden=True)
    @commands.is_owner()
    async def commandstats(self, ctx: StatsSleepyContext) -> None:
        """Shows command usage data for the current session.

        This command can only be used by my higher-ups.
        """
        stats = ctx.bot.command_uses

        if not stats:
            await ctx.send("No command usage data yet. Try again later.")
            return

        total = sum(stats.values())

        delta = datetime.now(timezone.utc) - ctx.bot.started_at
        rate = total * 60 / delta.total_seconds()

        paginator = commands.Paginator("```py", max_size=1000)
        paginator.add_line(f"{total} total commands used. ({rate:.2f}/min)", empty=True)

        for line in tchart(dict(stats.most_common())).split("\n"):
            paginator.add_line(line)

        await ctx.paginate(PaginatorSource(paginator))

    # This is written like this because the bot is not
    # sharded as it is too small. This code is subject
    # to change as the bot grows, of course, implying
    # that it will actually grow.
    @commands.command(aliases=("gws",), hidden=True)
    @commands.is_owner()
    @commands.bot_has_permissions(embed_links=True)
    async def gatewaystats(self, ctx: StatsSleepyContext) -> None:
        """Shows gateway identifies/resumes for the current session.

        This command can only be used by my higher-ups.
        """
        resumes = ctx.bot.socket_events["RESUMED"]
        identifies = ctx.bot.identifies

        await ctx.send(
            f"{resumes + identifies:,d} total gateway events received."
            f"\n```py\nRESUME   | {resumes:,d}\nIDENTIFY | {identifies:,d}```"
        )

    @commands.command(aliases=("wss",))
    @commands.cooldown(1, 5, commands.BucketType.member)
    async def socketstats(self, ctx: StatsSleepyContext) -> None:
        """Shows observed socket events data for the current session."""
        stats = ctx.bot.socket_events
        total = sum(stats.values())

        delta = datetime.now(timezone.utc) - ctx.bot.started_at
        rate = total * 60 / delta.total_seconds()

        paginator = commands.Paginator("```py", max_size=1000)
        paginator.add_line(f"{total} total events observed. ({rate:.2f}/min)", empty=True)

        for line in tchart(dict(stats.most_common())).split("\n"):
            paginator.add_line(line)

        await ctx.paginate(PaginatorSource(paginator))

    @commands.command()
    async def uptime(self, ctx: StatsSleepyContext) -> None:
        """Shows my uptime, including the time I was booted."""
        started_at = ctx.bot.started_at

        await ctx.send(
            f"I was booted on {format_dt(started_at, 'F')} and have been"
            f" online for `{human_delta(started_at, absolute=True)}`."
        )


async def _new_before_identify_hook(self, shard_id: int, *, initial: bool) -> None:
    self.identifies += 1

    await self._original_before_identify_hook(shard_id, initial=initial)


async def setup(bot: StatsSleepy) -> None:
    # Allows preservation of the counters if this
    # cog gets unloaded/reloaded.
    if not hasattr(bot, "command_uses"):
        bot.command_uses = Counter()

    if not hasattr(bot, "socket_events"):
        bot.socket_events = Counter()

    if not hasattr(bot, "identifies"):
        bot.identifies = 0

    await bot.add_cog(Statistics(bot))
