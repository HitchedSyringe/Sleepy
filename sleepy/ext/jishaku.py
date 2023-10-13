"""
Copyright © 2018-present HitchedSyringe

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
import itertools
import os
import platform
import traceback
from importlib import metadata
from os import path
from typing import TYPE_CHECKING, List

import discord
import psutil
from discord import Colour, Embed
from discord.ext import commands
from jishaku.features.baseclass import Feature
from jishaku.features.filesystem import FilesystemFeature
from jishaku.features.guild import GuildFeature
from jishaku.features.invocation import InvocationFeature
from jishaku.features.management import ManagementFeature
from jishaku.features.python import PythonFeature
from jishaku.features.root_command import RootCommand
from jishaku.features.shell import ShellFeature
from jishaku.math import natural_size
from jishaku.modules import ExtensionConverter
from jishaku.paginators import WrappedPaginator
from typing_extensions import Annotated

from sleepy import __version__
from sleepy.utils import CHECKMARK_EMOJI, XMARK_EMOJI, bool_to_emoji, human_delta

if TYPE_CHECKING:
    from sleepy.bot import Sleepy
    from sleepy.context import Context as SleepyContext


class Owner(
    FilesystemFeature,
    GuildFeature,
    InvocationFeature,
    ManagementFeature,
    PythonFeature,
    RootCommand,
    ShellFeature,
    command_attrs={"hidden": True},
):
    """Commands that only my higher-ups can use.

    ||Ｃｏｎｓｏｏｍ　ｍａｇｎｅｔ　ｃｏｇ；　ｃｏｎｆｏｒｍ　ｔｏ　ｍａｇｎｅｔ　ｃｏｇ．||
    """

    ICON: str = "\N{MAGNET}"

    @Feature.Command(aliases=("pm",))
    async def dm(self, ctx: SleepyContext, user: discord.User, *, content: str) -> None:
        """Directly messages a user.

        User can either be a name, ID, or mention.

        This command does **not** send any Discord file attachments.
        """
        embed = Embed(
            description=content,
            colour=Colour.dark_embed(),
            timestamp=ctx.message.edited_at or ctx.message.created_at,
        )
        embed.set_author(
            name=f"{ctx.author} (ID: {ctx.author.id})", icon_url=ctx.author.display_avatar
        )
        embed.set_footer(
            text="This message was sent because you either previously "
            "contacted me or found a bug. I do not monitor this DM."
        )

        try:
            await user.send(embed=embed)
        except discord.HTTPException:
            await ctx.send("Sending your message failed.\nTry again later?")
        else:
            await ctx.send("Your message was sent successfully.")

    @Feature.Command(rest_is_raw=True)
    async def echo(self, ctx: SleepyContext, *, message: str) -> None:
        """Sends a message in the current channel as myself."""
        await ctx.send(message)

    @Feature.Command(parent="jsk", name="extensions", aliases=("exts",))
    async def jsk_extensions(self, ctx: SleepyContext) -> None:
        """Shows the loaded and unloaded configured extensions.

        Any duplicate entries or non-existent extensions are ignored.
        """
        stats = commands.Paginator(None, None, 1980)

        unique_entries = frozenset(ctx.bot._get_configured_extensions())
        for ext in unique_entries:
            ext_path = path.join(*ext.split("."))
            if not (path.isdir(ext_path) or path.isfile(ext_path + ".py")):
                continue

            stats.add_line(f"{bool_to_emoji(ext in ctx.bot.extensions)} `{ext}`")

        for page in stats.pages:
            await ctx.send(page)

    @Feature.Command(
        parent="jsk", name="load", aliases=("l",), require_var_positional=True
    )
    async def jsk_load(
        self, ctx: SleepyContext, *extensions: Annotated[List[str], ExtensionConverter]
    ) -> None:
        """Loads one or more extensions.

        Loaded and non-existent extensions are silently ignored.
        """
        stats = WrappedPaginator(prefix="", suffix="", max_size=1980)

        for ext in itertools.chain(*extensions):
            try:
                await ctx.bot.load_extension(ext)
            except (commands.ExtensionAlreadyLoaded, commands.ExtensionNotFound):
                pass
            except Exception as exc:
                limit = 2

                if isinstance(exc, commands.ExtensionFailed):
                    exc = exc.original
                    limit = 8

                tb = ''.join(
                    traceback.format_exception(type(exc), exc, exc.__traceback__, limit)
                )
                stats.add_line(f"{XMARK_EMOJI} `{ext}`\n```py\n{tb}```")
            else:
                stats.add_line(f"{CHECKMARK_EMOJI} `{ext}`")

        if not stats.pages:
            await ctx.send("No action was taken on the given extension(s).")
            return

        for page in stats.pages:
            await ctx.send(page)

    @Feature.Command(parent="jsk", name="reload", aliases=("r",))
    async def jsk_reload(
        self, ctx: SleepyContext, *extensions: Annotated[List[str], ExtensionConverter]
    ) -> None:
        """Reloads one or more extensions.

        If no extensions are passed, then all loaded extensions will be reloaded.
        Unloaded and non-existent extensions are silently ignored.
        """
        to_reload = (
            itertools.chain(*extensions) if extensions else tuple(ctx.bot.extensions)
        )

        stats = WrappedPaginator(prefix="", suffix="", max_size=1980)

        for ext in to_reload:
            try:
                await ctx.bot.reload_extension(ext)
            except (commands.ExtensionNotLoaded, commands.ExtensionNotFound):
                pass
            except Exception as exc:
                limit = 2

                if isinstance(exc, commands.ExtensionFailed):
                    exc = exc.original
                    limit = 8

                tb = "".join(
                    traceback.format_exception(type(exc), exc, exc.__traceback__, limit)
                )
                stats.add_line(f"{XMARK_EMOJI} `{ext}`\n```py\n{tb}```")
            else:
                stats.add_line(f"{CHECKMARK_EMOJI} `{ext}`")

        if not stats.pages:
            await ctx.send("No action was taken on the given extension(s).")
            return

        for page in stats.pages:
            await ctx.send(page)

    @Feature.Command(parent="jsk", name="shutdown", aliases=("die", "kys"))
    async def jsk_shutdown(self, ctx: SleepyContext) -> None:
        """Shuts me down."""
        await ctx.send("Just drank some anti-freeze. Now I am become dead.")
        await ctx.bot.close()

    @Feature.Command(parent="jsk", name="system", aliases=("sys",))
    @commands.bot_has_permissions(embed_links=True)
    async def jsk_system(self, ctx: SleepyContext) -> None:
        """Displays some brief information my system and vitals."""
        bot = ctx.bot
        process = psutil.Process()

        gen_info = [
            f"OS: {platform.platform()}",
            f"Bot Version: {__version__}",
            f"Python: {platform.python_version()}",
        ]

        gen_info.extend(
            f"\u25B8 {p}: {metadata.version(p)}"
            for p in ("aiohttp", "discord.py", "jishaku")
        )

        gen_info.append(f"Started: {bot.started_at}")
        gen_info.append(f"\u25B8 Uptime: {human_delta(bot.started_at, absolute=True)}")

        embed = Embed(
            title="\N{DESKTOP COMPUTER} System Information",
            colour=Colour.dark_embed(),
            description="```yml\n" + "\n".join(gen_info) + "\n```",
        )

        proc_info = [
            f"PID: {process.pid}",
        ]

        try:
            with process.oneshot():
                try:
                    proc_info.append(f"\u25B8 Name: {process.name()}")
                except psutil.AccessDenied:
                    pass

                try:
                    proc_info.append(f"\u25B8 Threads: {process.num_threads()}")
                except psutil.AccessDenied:
                    pass

                try:
                    mem = process.memory_full_info().uss
                    mem_perc = mem / psutil.virtual_memory().total
                    proc_info.append(f"RAM: {natural_size(mem)} ({mem_perc:.2%})")
                except psutil.AccessDenied:
                    pass

                try:
                    cpu_perc = process.cpu_percent() / psutil.cpu_count()
                    proc_info.append(f"CPU: {cpu_perc:.2f}%")
                except psutil.AccessDenied:
                    pass
        except psutil.AccessDenied:
            proc_info.append("[Failed to query more info]")

        embed.add_field(
            name="\N{GEAR} Process", value="```yml\n" + "\n".join(proc_info) + "\n```"
        )

        # From here, a lot of private methods are accessed since
        # there's no other (much cleaner) way to get this data.

        event = 0
        inner = 0
        bad_inner = []

        dpy_tasks_dir = path.join("discord", "ext", "tasks", "__init__")
        ext_dirs = [path.join(*e.split(".")) for e in bot.extensions]

        for task in asyncio.all_tasks(loop=bot.loop):
            task_repr = repr(task)

            if dpy_tasks_dir in task_repr or any(d in task_repr for d in ext_dirs):
                inner += 1

                if task.done() and task._exception is not None:
                    bad_inner.append(task.get_name())
                    continue

            if not task.done() and "Client._run_event" in task_repr:
                event += 1

        embed.add_field(
            name="\N{JIGSAW PUZZLE PIECE} Tasks/Events",
            value="```yml"
            f"\nGlobal Rate Limit: {not bot.http._global_over.is_set()}"
            f"\nEvents Waiting: {event}"
            f"\nInner Tasks: {inner}"
            f"\n\u25B8 Failed: {', '.join(bad_inner) or 'None'}"
            "\n```",
        )

        cooldown = bot._spam_control
        spammers = ", ".join(str(e) for e, b in cooldown._cache.items() if b._tokens == 0)

        embed.add_field(
            name="\N{SPEAKER WITH CANCELLATION STROKE} Current Spammers",
            value=spammers or "None",
            inline=False,
        )

        await ctx.send(embed=embed)

    @Feature.Command(
        parent="jsk", name="unload", aliases=("u",), require_var_positional=True
    )
    async def jsk_unload(
        self, ctx: SleepyContext, *extensions: Annotated[List[str], ExtensionConverter]
    ) -> None:
        """Unloads one or more extensions.

        Unloaded and non-existent extensions are silently ignored.
        """
        stats = WrappedPaginator(prefix="", suffix="", max_size=1980)

        for ext in itertools.chain(*extensions):
            if ext == __name__:
                stats.add_line(f"{XMARK_EMOJI} `{ext}` (Can't be unloaded)")
                continue

            try:
                await ctx.bot.unload_extension(ext)
            except Exception:
                pass
            else:
                stats.add_line(f"{CHECKMARK_EMOJI} `{ext}`")

        if not stats.pages:
            await ctx.send("No action was taken on the given extension(s).")
            return

        for page in stats.pages:
            await ctx.send(page)

    @Feature.Command(aliases=("leaveguild",))
    async def leaveserver(
        self, ctx: SleepyContext, *, guild: discord.Guild = commands.CurrentGuild
    ) -> None:
        """Forces me to leave a server.

        If no server is given, then I will leave the current server instead.
        """
        confirmed = await ctx.prompt(f"Leave {guild} (ID: {guild.id})?")

        if confirmed:
            await ctx.send(f"Left {guild} (ID: {guild.id}).")
            await guild.leave()
        else:
            await ctx.send("Aborted.")


async def setup(bot: Sleepy) -> None:
    os.environ["JISHAKU_RETAIN"] = "True"

    await bot.add_cog(Owner(bot=bot))
