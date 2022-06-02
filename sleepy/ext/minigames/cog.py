"""
Copyright (c) 2018-present HitchedSyringe

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""


from __future__ import annotations

import logging

# fmt: off
__all__ = (
    "HasActiveMinigameSession",
    "Minigames",
    "no_active_minigame_session",
)
# fmt: on


import traceback
from typing import TYPE_CHECKING, Callable, Dict, TypeVar, Union

import discord
from discord.ext import commands

from sleepy.menus import PaginatorSource

from .trivia import TriviaFlags, trivia_command

T = TypeVar("T")


if TYPE_CHECKING:
    from collections import Counter

    from discord import Member, User

    from sleepy.bot import Sleepy
    from sleepy.context import Context as SleepyContext

    from .base_session import BaseSession


_LOG: logging.Logger = logging.getLogger(__name__)


def no_active_minigame_session() -> Callable[[T], T]:
    """A :func:`commands.check` that checks if the channel this
    command is invoked in has an active minigame session.

    .. versionadded:: 3.3

    Raises
    ------
    :exc:`HasActiveMinigameSession`
        The invoking channel already has an active minigame session.
    """

    def predicate(ctx: commands.Context) -> bool:
        # This will only be used within this cog.
        if ctx.channel.id in ctx.cog.sessions:  # type: ignore
            message = "This channel already has an active minigame session."
            raise HasActiveMinigameSession(message)

        return True

    return commands.check(predicate)


def _generate_scoreboard(scores: Counter[Union[Member, User]]) -> commands.Paginator:
    paginator = commands.Paginator(prefix="**Scoreboard**\n```hs", max_size=800)

    def as_name(user: Union[Member, User]) -> str:
        return user.display_name

    max_width = len(max(map(as_name, scores), key=len))

    for (user, score) in scores.most_common():
        paginator.add_line(f"{as_name(user):<{max_width}} | {score}")

    return paginator


class HasActiveMinigameSession(commands.CheckFailure):
    """Exception raised when the invoking channel already has an
    active minigame session.

    This inherits from :exc:`commands.CheckFailure`.

    .. versionadded:: 3.3
    """

    pass


class Minigames(commands.Cog):
    """Commands having to do with various minigames."""

    ICON: str = "\N{GAME DIE}"

    def __init__(self) -> None:
        self.sessions: Dict[int, BaseSession] = {}

    async def cog_unload(self) -> None:
        for session in self.sessions.values():
            await session.stop()

        self.sessions.clear()

    async def cog_command_error(self, ctx: SleepyContext, error: Exception) -> None:
        if isinstance(error, HasActiveMinigameSession):
            ctx._already_handled_error = True
            await ctx.send(error)  # type: ignore

    @commands.Cog.listener()
    async def on_minigame_session_start(self, session: BaseSession) -> None:
        self.sessions[session.channel.id] = session
        _LOG.info("New session %s was started.", session)

    @commands.Cog.listener()
    async def on_minigame_session_error(
        self, session: BaseSession, error: Exception
    ) -> None:
        if isinstance(error, discord.HTTPException) or hasattr(error, "handled__"):
            return

        _LOG.exception("Unhandled exception in session %s.", session, exc_info=error)

        channel = session.channel
        host = session.host
        bot: Sleepy = session.bot  # type: ignore

        tb = traceback.format_exception(None, error, error.__traceback__, 4)

        embed = discord.Embed(
            title="Minigame Session Error",
            description=f"```py\n{''.join(tb)}```",
            colour=0xFC284F,
        )
        embed.add_field(name="Owner", value=f"{host} (ID: {host.id})")
        embed.add_field(name="Channel", value=f"{channel} (ID: {channel.id})")

        await bot.webhook.send(embed=embed)

        try:
            await channel.send(
                "An unexpected error has forced the minigame session to stop."
                f"\n```py\n{tb[-1]}```"
                "\nI've relayed some details about this to my higher-ups."
            )
        except discord.HTTPException:
            pass

        await session.stop()

    @commands.Cog.listener()
    async def on_minigame_session_end(self, session: BaseSession) -> None:
        # Just in case this was somehow removed before we got here.
        self.sessions.pop(session.channel.id, None)
        _LOG.info("Session %s was stopped successfully.", session)

    @commands.group(invoke_without_command=True)
    @commands.guild_only()
    async def minigame(self, ctx: commands.Context) -> None:
        """Various minigame-related commands."""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @minigame.command(usage="categories: <categories...> [options...]")
    @no_active_minigame_session()
    @commands.bot_has_permissions(embed_links=True)
    async def trivia(self, ctx: commands.Context, *, options: TriviaFlags) -> None:
        """Starts a new trivia session.

        This command's interface is similar to Discord's slash commands.
        Values with spaces must be surrounded by quotation marks.

        Options can be given in any order and, unless otherwise stated,
        are assumed to be optional.

        The following options are valid:

        `categories: <categories...>` **Required**
        > The categories to involve the questions from.
        > This is case-sensitive.
        > Valid categories: `christmas`, `newyear`, `usabbreviations`,
        > `uscapitals`, `usflags`, `usmap`, `worldcapitals`, `worldflags`,
        > `worldmap`
        `[maximum-score|max-score]: <integer>`
        > The amount of points required to win.
        > Must be between 5 and 30, inclusive.
        > Defaults to `10`.
        `question-time-limit: <integer>`
        > The time, in seconds, alotted to answer a question.
        > Must be between 15 and 50, inclusive.
        > Defaults to `20`.
        `bot-plays: <true|false>`
        > If `true` (the default), I will award myself points if
        > nobody has correctly answered the question in time.
        `reveal-answer-after: <true|false>`
        > If `true` (the default), I will reveal the answer if
        > nobody has correctly answered the question in time.
        `show-hints: <true|false>`
        > If `true` (the default), then I will slowly reveal
        > portions of the answer as the time dwindles.

        (Bot Needs: Embed Links)
        """
        await trivia_command(self, ctx, options=options)

    @minigame.command()
    async def scores(self, ctx: SleepyContext) -> None:
        """Shows the current minigame session's scores, if applicable."""
        session = self.sessions.get(ctx.channel.id)

        if session is None:
            await ctx.send("This channel has no active minigame session.")
        elif scores := session.scores:
            scoreboard = _generate_scoreboard(scores)
            await ctx.paginate(PaginatorSource(scoreboard))
        else:
            await ctx.send("There are no player scores to show.")

    @minigame.command()
    async def stop(self, ctx: commands.Context) -> None:
        """Stops the current minigame session.

        You must either be the host, the bot owner, or a user
        with the `Manage Messages` permission to do this.
        """
        session = self.sessions.get(ctx.channel.id)

        if session is None:
            await ctx.send("This channel has no active minigame session.")
        elif session.is_manager(ctx.author):  # type: ignore
            await session.stop()
            await ctx.send("Minigame session stopped.")
        else:
            await ctx.send("You cannot manage this minigame session.")
