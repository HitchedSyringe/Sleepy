"""
Copyright © 2018-present HitchedSyringe

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""


from __future__ import annotations

import itertools
import os
import traceback
from typing import TYPE_CHECKING, List

import discord
from braceexpand import braceexpand
from discord import Embed
from discord.ext import commands
from jishaku import modules
from jishaku.features.baseclass import Feature
from jishaku.features.filesystem import FilesystemFeature
from jishaku.features.guild import GuildFeature
from jishaku.features.invocation import InvocationFeature
from jishaku.features.management import ManagementFeature
from jishaku.features.python import PythonFeature
from jishaku.features.root_command import RootCommand
from jishaku.features.shell import ShellFeature
from jishaku.paginators import WrappedPaginator
from typing_extensions import Annotated

from sleepy.utils import bool_to_emoji, find_extensions_in

if TYPE_CHECKING:
    from sleepy.bot import Sleepy
    from sleepy.context import Context as SleepyContext


ExtensionConverter = modules.ExtensionConverter


def _new_resolve_extensions(bot: Sleepy, name: str) -> List[str]:
    exts = []
    exts_dir = ".".join(bot.extensions_directory.parts)

    for ext in braceexpand(name):
        if ext.startswith("$."):
            ext = ext.replace("$", exts_dir, 1).lstrip(".")

        if ext.endswith(".*"):
            exts.extend(find_extensions_in(ext[:-2].replace(".", "/")))
        elif ext == "~":
            exts.append(__name__)
        else:
            exts.append(ext)

    return exts


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

    def cog_load(self) -> None:
        self._original_resolve_extensions = modules.resolve_extensions

        # Inject the custom extension resolving behaviour.
        # I figured this was the best way to do it rather
        # than writing my own extensions converter, which
        # would probably just end up copying the original.
        modules.resolve_extensions = _new_resolve_extensions

    def cog_unload(self) -> None:
        # Restore the original functionality.
        modules.resolve_extensions = self._original_resolve_extensions

    @Feature.Command(aliases=("pm",))
    async def dm(self, ctx: SleepyContext, user: discord.User, *, content: str) -> None:
        """Directly messages a user.

        User can either be a name, ID, or mention.

        This command does **not** send any Discord file
        attachments.
        """
        embed = Embed(
            description=content,
            colour=0x2F3136,
            timestamp=ctx.message.created_at or ctx.message.edited_at,
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
        """Shows the loaded and unloaded extensions.

        This doesn't include extensions in any subsequent folders.
        """
        stats = commands.Paginator(None, None, 1980)

        for ext in ctx.bot.get_all_extensions():
            stats.add_line(f"{bool_to_emoji(ext in ctx.bot.extensions)} `{ext}`")

        for page in stats.pages:
            await ctx.send(page)

    @Feature.Command(
        parent="jsk", name="load", aliases=("l",), require_var_positional=True
    )
    async def jsk_load(
        self, ctx: SleepyContext, *extensions: Annotated[List[str], ExtensionConverter]
    ) -> None:
        """Loads one or more extensions."""
        stats = WrappedPaginator(prefix="", suffix="", max_size=1980)

        for ext in itertools.chain(*extensions):
            try:
                await ctx.bot.load_extension(ext)
            except commands.ExtensionAlreadyLoaded:
                pass
            except Exception:
                tb = traceback.format_exc()
                stats.add_line(f"<:x_:821284209792516096> `{ext}`\n```py\n{tb}```")
            else:
                stats.add_line(f"<:check:821284209401921557> `{ext}`")

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

        If no extensions are passed, then all loaded extensions
        will be reloaded.
        """
        to_reload = (
            itertools.chain(*extensions) if extensions else tuple(ctx.bot.extensions)
        )

        stats = WrappedPaginator(prefix="", suffix="", max_size=1980)

        for ext in to_reload:
            try:
                await ctx.bot.reload_extension(ext)
            except commands.ExtensionNotLoaded:
                pass
            except Exception:
                tb = traceback.format_exc()
                stats.add_line(f"<:x_:821284209792516096> `{ext}`\n```py\n{tb}```")
            else:
                stats.add_line(f"<:check:821284209401921557> `{ext}`")

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

    @Feature.Command(
        parent="jsk", name="unload", aliases=("u",), require_var_positional=True
    )
    async def jsk_unload(
        self, ctx: SleepyContext, *extensions: Annotated[List[str], ExtensionConverter]
    ) -> None:
        """Unloads one or more extensions."""
        stats = WrappedPaginator(prefix="", suffix="", max_size=1980)

        for ext in itertools.chain(*extensions):
            if ext == __name__:
                stats.add_line(f"<:x_:821284209792516096> `{ext}` (Can't be unloaded)")
                continue

            try:
                await ctx.bot.unload_extension(ext)
            except commands.ExtensionNotLoaded:
                pass
            except Exception:
                tb = traceback.format_exc()
                stats.add_line(f"<:x_:821284209792516096> `{ext}`\n```py\n{tb}```")
            else:
                stats.add_line(f"<:check:821284209401921557> `{ext}`")

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

        If no server is given, then I will leave the
        current server instead.
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
