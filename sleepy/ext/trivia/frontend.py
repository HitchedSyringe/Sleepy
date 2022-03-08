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


import aiofiles
import logging
import traceback
import yaml
from discord import Embed, HTTPException
from discord.ext import commands, flags
from sleepy.utils import human_join, tchart

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


class TriviaMinigame(
    commands.Cog,
    name="Trivia Minigame",
    command_attrs={"cooldown": commands.Cooldown(1, 6, commands.BucketType.member)}
):
    """Commands having to do with the Trivia minigame."""

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
    async def on_trivia_session_end(self, session, send_results):
        _LOG.info(
            "Stopped session started by %s (ID: %s) in %s (ID: %d).",
            session.owner,
            session.owner.id,
            session.channel,
            session.channel.id
        )

        if session.scores and send_results:
            top_ten = session.scores.most_common(10)
            highest = top_ten[0][1]

            winners = [
                p.mention for p, s in session.scores.items()
                if s == highest and not p.bot
            ]

            if winners:
                msg = f"\N{PARTY POPPER} {human_join(winners)} won! Congrats!"
            else:
                msg = "Good game everyone! \N{SMILING FACE WITH SMILING EYES}"

            msg += f"\n\n**Trivia Results** (Top 10)\n```hs\n{tchart(dict(top_ten))}```"

            await session.channel.send(msg, allowed_mentions=AllowedMentions(users=False))

        # Just in case it's removed somehow before getting here.
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
        session.stop(send_results=False)

    @flags.add_flag("--categories", type=str.lower, nargs="+", required=True)
    @flags.add_flag("--max-score", type=int, default=10)
    @flags.add_flag("--answer-time-limit", type=int, default=20)
    @flags.add_flag("--no-bot", action="store_false", dest="bot_plays")
    @flags.add_flag("--no-reveal-answer", action="store_false", dest="reveal_answer")
    @flags.add_flag("--no-hints", action="store_false", dest="give_hints")
    @flags.group(invoke_without_command=True, usage="<--categories> [options...]")
    @commands.bot_has_permissions(embed_links=True)
    async def trivia(self, ctx, **flags):
        """Starts a new trivia session.

        This uses a powerful "command-line" interface.
        Values with spaces must be surrounded by quotation marks.
        **All options except `--categories` are optional.**

        __The following options are valid:__

        `--categories`
        > The categories to involve the questions from. **Required**
        > Valid categories: `christmas`, `newyear`, `usabbreviations`,
        > `uscapitals`, `usflags`, `usmap`, `worldcapitals`, `worldflags`,
        > `worldmap`
        `--max-score`
        > The amount of points required to win.
        > Must be between 5 and 30, inclusive.
        > Defaults to `10`.
        `--answer-time-limit`
        > The time, in seconds, alotted to answer a question.
        > Must be between 15 and 50, inclusive.
        > Defaults to `20`.

        __The remaining options do not take any arguments and are simply just flags:__

        `--no-bot`
        > If passed, I won't award myself points if nobody
        > has correctly answered the question in time.
        `--no-reveal-answer`
        > If passed, I won't reveal the answer if nobody
        > has correctly answered the question in time.
        `--no-hints`
        > If passed, I won't slowly reveal portions of the
        > answer as the timer dwindles.

        (Bot Needs: Embed Links)
        """
        if ctx.channel.id in self.active_sessions:
            await ctx.send("There's already an active trivia session in this channel.")
            return

        if not 5 <= flags["max_score"] <= 30:
            await ctx.send("Maximum score must be between 5 and 30, inclusive.")
            return

        if not 15 <= flags["answer_time_limit"] <= 50:
            await ctx.send("Answer time limit must be between 15 and 50, inclusive.")
            return

        creds = []
        questions = []

        async with ctx.typing():
            for category in set(flags.pop("categories")):
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

        embed = Embed(title="A new trivia session is starting!", colour=0x2F3136)
        embed.set_footer(text=f"Started by {ctx.author}")
        embed.add_field(name="Categories", value=human_join(creds), inline=False)
        embed.add_field(
            name="Settings",
            value=f"```py\n{tchart(flags, lambda s: s.replace('_', ' ').title())}```"
        )

        await ctx.send(embed=embed)

        self.active_sessions[ctx.channel.id] = TriviaSession.start(ctx, questions, **flags)

    @trivia.error
    async def on_trivia_error(self, ctx, error):
        if isinstance(error, flags.ArgumentParsingError):
            await ctx.send(
                "An error occurred while processing your flag arguments."
                "\nPlease double-check your input arguments and try again."
            )
            error.handled__ = True

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
            or session.owner == ctx.author
            or await ctx.bot.is_owner(ctx.author)
        ):
            await ctx.send("Trivia session stopped.")
            session.stop()
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
