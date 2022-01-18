"""
Copyright (c) 2018-present HitchedSyringe

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""


__all__ = (
    "NoActiveSession",
    "TriviaMinigame",
    "has_active_session",
)


from typing import Tuple

import aiofiles
import logging
import traceback
import yaml
from discord import Embed, HTTPException
from discord.ext import commands
from sleepy.utils import _as_argparse_dict, human_join, tchart

from .backend import TriviaQuestion, TriviaSession
from .categories import CATEGORIES


class NoActiveSession(commands.CheckFailure):

    def __init__(self, channel):
        self.channel = channel

        super().__init__(f"{channel} has no active trivia session.")


def has_active_session():

    async def predicate(ctx):
        if ctx.channel.id not in ctx.cog.active_sessions:
            raise NoActiveSession(ctx.channel)

        return True

    return commands.check(predicate)


_LOG = logging.getLogger(__name__)


class TriviaFlags(commands.FlagConverter):

    categories: Tuple[str, ...]
    max_score: int = commands.flag(name="max-score", default=10)
    answer_time_limit: int = commands.flag(name="answer-time-limit", default=20)
    bot_plays: bool = commands.flag(name="bot-plays", default=True)
    reveal_answer: bool = commands.flag(name="reveal-answer", default=True)
    give_hints: bool = commands.flag(name="show-hints", default=True)


class TriviaMinigame(
    commands.Cog,
    name="Trivia Minigame",
    command_attrs={
        "cooldown": commands.CooldownMapping.from_cooldown(1, 6, commands.BucketType.member),
    }
):
    """Commands having to do with the Trivia minigame."""

    ICON = "\N{WHITE QUESTION MARK ORNAMENT}"

    def __init__(self):
        self.active_sessions = {}

    def cog_unload(self):
        for session in self.active_sessions.values():
            session.stop()

        self.active_sessions.clear()

    async def cog_command_error(self, ctx, error):
        if isinstance(error, NoActiveSession):
            await ctx.send("There is no active trivia session in this channel.")
            error.handled__ = True

    @commands.Cog.listener()
    async def on_trivia_session_start(self, session):
        _LOG.info(
            "%s (ID: %s) started a new session in %s (ID: %s).",
            session.owner,
            session.owner.id,
            session.channel,
            session.channel.id
        )

    @commands.Cog.listener()
    async def on_trivia_session_end(self, session):
        _LOG.info(
            "Stopped session started by %s (ID: %s) in %s (ID: %d).",
            session.owner,
            session.owner.id,
            session.channel,
            session.channel.id
        )

        self.active_sessions.pop(session.channel.id, None)

    @commands.Cog.listener()
    async def on_trivia_session_error(self, session, error):
        owner = session.owner
        channel = session.channel

        _LOG.error(
            "Something went wrong in session started by %s (ID: %s) in %s (ID: %d).",
            owner,
            owner.id,
            channel,
            channel.id,
            exc_info=error
        )

        tb = traceback.format_exception(None, error, error.__traceback__, 4)

        embed = Embed(
            title="Trivia Session Error",
            description=f"```py\n{''.join(tb)}```",
            colour=0xFC284F
        )
        embed.add_field(name="Owner", value=f"{owner} (ID: {owner.id})")
        embed.add_field(name="Channel", value=f"{channel} (ID: {channel.id})")

        await session.bot.webhook.send(embed=embed)

        try:
            await channel.send(
                "An unexpected error has forced your trivia session to stop."
                f"\n```py\n{tb[-1]}```\nI've relayed some details about this "
                "to my higher-ups."
            )
        except HTTPException:
            pass

        # This internally dispatches trivia_session_end so this
        # session should be removed from the active sessions.
        await session.end_game(send_results=False)

    @commands.group(invoke_without_command=True, usage="categories: <categories...> [options...]")
    @commands.bot_has_permissions(embed_links=True)
    async def trivia(self, ctx, *, options: TriviaFlags):
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
        `max-score: <integer>`
        > The amount of points required to win.
        > Must be between 5 and 30, inclusive.
        > Defaults to `10`.
        `answer-time-limit: <integer>`
        > The time, in seconds, alotted to answer a question.
        > Must be between 15 and 50, inclusive.
        > Defaults to `20`.
        `bot-plays: <true|false>`
        > If `true` (the default), I will award myself points if
        > nobody has correctly answered the question in time.
        `reveal-answer: <true|false>`
        > If `true` (the default), I will reveal the answer if
        > nobody has correctly answered the question in time.
        `show-hints: <true|false>`
        > If `true` (the default), then I will slowly reveal
        > portions of the answer as the time dwindles.

        (Bot Needs: Embed Links)
        """
        if ctx.channel.id in self.active_sessions:
            await ctx.send("There's already an active trivia session in this channel.")
            return

        if not 5 <= options.max_score <= 30:
            await ctx.send("Maximum score must be between 5 and 30, inclusive.")
            return

        if not 15 <= options.answer_time_limit <= 50:
            await ctx.send("Answer time limit must be between 15 and 50, inclusive.")
            return

        creds = []
        questions = []

        async with ctx.typing():
            for category in set(options.categories):
                category_path = CATEGORIES.joinpath(category + ".yaml").resolve()

                if not category_path.is_relative_to(CATEGORIES):
                    await ctx.send("Nice try with the path traversal, buddy.")
                    return

                try:
                    async with aiofiles.open(category_path) as data:
                        data = yaml.safe_load(await data.read())
                except FileNotFoundError:
                    await ctx.send("One or more of the given categories were invalid.")
                    return

                author = data.pop("AUTHOR", None)

                if author is not None:
                    creds.append(f"`{category} (by {author})`")
                else:
                    creds.append(f"`{category}`")

                questions.extend(
                    TriviaQuestion(category, q, author=author, **d)
                    for q, d in data.items()
                )

        kwargs = _as_argparse_dict(options)
        del kwargs["categories"]

        embed = Embed(title="A new trivia session is starting!", colour=0x2F3136)
        embed.set_footer(text=f"Started by {ctx.author}")
        embed.add_field(name="Categories", value=human_join(creds), inline=False)
        embed.add_field(
            name="Settings",
            value=f"```py\n{tchart(kwargs, lambda s: s.replace('_', ' ').title())}```"
        )

        await ctx.send(embed=embed)

        self.active_sessions[ctx.channel.id] = TriviaSession.start(ctx, questions, **kwargs)

    @trivia.command(name="stop")
    @has_active_session()
    async def trivia_stop(self, ctx):
        """Stops the current trivia session.

        You must either be the starter, the bot owner, or a
        user with the `Manage Messages` permission in order
        to do this.
        """
        session = self.active_sessions[ctx.channel.id]

        if (
            ctx.channel.permissions_for(ctx.author).manage_messages
            or session.starter == ctx.author
            or await ctx.bot.is_owner(ctx.author)
        ):
            await ctx.send("Trivia session stopped.")
            await session.end_game()
        else:
            await ctx.send("You do not have permission to manage this session.")

    @trivia.command(name="scores", aliases=("scoreboard",))
    @has_active_session()
    async def trivia_scores(self, ctx):
        """Shows the player scores in the current trivia session."""
        session = self.active_sessions[ctx.channel.id]

        if session.scores:
            await ctx.send(
                f"**Trivia Scoreboard** (Showing top 10 players)"
                f"\n```hs\n{tchart(dict(session.scores.most_common(10)))}```"
            )
        else:
            await ctx.send("Nobody has scored any points yet.")
