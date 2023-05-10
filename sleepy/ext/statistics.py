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

import asyncio
import logging
import platform
import textwrap
import traceback
from collections import Counter
from datetime import datetime, timezone
from importlib import metadata
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

    def cog_load(self) -> None:
        bot = self.bot

        handler = GatewayWebhookHandler(bot)
        logging.getLogger("discord").addHandler(handler)
        self.gw_handler: GatewayWebhookHandler = handler

        bot._original_before_identify_hook = bot.before_identify_hook  # type: ignore
        # I decided to just monkey-patch this in rather than
        # including it in the bot class since I figured that
        # not everyone would want to be forced to use this.
        type(bot).before_identify_hook = _new_before_identify_hook  # type: ignore

    def cog_unload(self) -> None:
        self.gw_handler.close()
        logging.getLogger("discord").removeHandler(self.gw_handler)

        # NOTE: We don't delete any statistics collected since doing
        # so would obliterate them every time this cog was reloaded.

        bot = self.bot

        type(bot).before_identify_hook = bot._original_before_identify_hook  # type: ignore
        del bot._original_before_identify_hook

    async def send_brief_guild_info(self, guild: discord.Guild, *, joined: bool) -> None:
        member_count = guild.member_count
        bots = sum(m.bot for m in guild.members)

        embed = Embed(
            description=f"`ID:` {guild.id}"
            f"\n`Owner:` {guild.owner} (ID: {guild.owner_id})"
            f"\n`Members:` {member_count or 0:,d} ({plural(bots, ',d'):bot})"
            f"\n`Channels:` {len(guild.channels)}"
            f"\n`Created:` {format_dt(guild.created_at, 'R')}"
            f"\n`Shard ID:` {'N/A' if guild.shard_id is None else guild.shard_id}",
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
        await self.send_brief_guild_info(guild, joined=True)

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild) -> None:
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
        bot = ctx.bot

        embed = Embed(description=bot.description, colour=Colour.dark_embed())
        embed.set_author(name=ctx.me, icon_url=ctx.me.display_avatar)
        embed.set_footer(text="Check out our links using the buttons below!")

        guilds = 0
        members = 0
        channels = 0

        for guild in bot.guilds:
            guilds += 1

            if not guild.unavailable:
                members += guild.member_count or 0
                channels += len(guild.channels)

        embed.add_field(
            name="\N{ROBOT FACE} About Me",
            value=f"`Owners:` {', '.join(map(str, bot.owners))}"
            f"\n`Created:` {format_dt(ctx.me.created_at, 'R')}"
            f"\n`Booted:` {format_dt(bot.started_at, 'R')}"
            f"\n`Servers:` {guilds:,d}"
            f"\n`Channels:` {channels:,d}"
            f"\n`Members:` {members:,d}"
            f"\n\u2570`Unique:` {len(bot.users):,d}"
            f"\n`Commands Used:` {sum(bot.command_uses.values()):,d}"
            "\n||Wowee!! Another Discord bot.||",
        )

        process = psutil.Process()
        memory_usage = process.memory_full_info().uss / 1024**2
        cpu_usage = process.cpu_percent() / psutil.cpu_count()

        embed.add_field(
            name="\N{CONTROL KNOBS} Technical Information",
            value=f"`Sleepy Version:` {__version__}"
            f"\n\u25B8 <:py:823367531724537887> {platform.python_version()}"
            f"\n\u25B8 <:dpy:823367531690590248> {metadata.version('discord.py')}"
            f"\n`Memory Usage:` {memory_usage:.2f} MiB"
            f"\n`CPU Usage:` {cpu_usage:.2f}%"
            f"\n`Shards:` {bot.shard_count or 'N/A'}"
            f"\n`Loaded Extensions:` {len(bot.extensions)}"
            f"\n`Loaded Categories:` {len(bot.cogs)}"
            f"\n`Registered Commands:` {len(bot.commands)}",
        )

        await ctx.send(embed=embed, view=BotLinksView(ctx.me.id))

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
