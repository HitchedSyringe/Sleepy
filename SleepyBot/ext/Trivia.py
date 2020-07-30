"""
© Copyright 2018-2020 HitchedSyringe, All Rights Reserved.

Redistributing, using or owning a copy of this software without explicit permissions
is against these licensing terms, your license(s) to this software can be revoked at
any time without explicit notice beforehand and at the time of revocation.
Your license is non-transferrable, the terms of this license only permit you to do the
following; Create pull requests and make modifications to this repository.

"""


from pathlib import Path

import aiofiles
import yaml
from discord import Embed
from discord.ext import commands, flags

from SleepyBot.utils import checks, formatting
from SleepyBot.utils.trivia_session import TriviaSession


BASE_PATH = Path(__file__).parent.parent / "utils/trivia_categories"


PATHS = frozenset(BASE_PATH.glob("*.yaml"))


class Trivia(commands.Cog,
             command_attrs=dict(cooldown=commands.Cooldown(rate=1, per=6, type=commands.BucketType.member))):
    """Commands having to do with the Trivia minigame."""

    def __init__(self):
        self._active_trivia_sessions = set()


    def cog_unload(self):
        for session in self._active_trivia_sessions:
            session.stop(dispatch_event=False)


    def get_trivia_session(self, channel):
        """Gets the trivia session corresponding to the given channel.
        If no session is hosted in the given channel, then ``None`` is returned instead.

        Parameters
        ----------
        channel: :class:`discord.TextChannel`
            The text channel a session is hosted in.

        Returns
        -------
        Optional[:class:`TriviaSession`]
            The trivia session associated with the given channel.
            ``None`` if no trivia session is associated with the given channel.
        """
        return next((s for s in self._active_trivia_sessions if s.channel == channel), None)


    @commands.Cog.listener()
    async def on_trivia_session_end(self, session: TriviaSession) -> None:
        self._active_trivia_sessions.discard(session)


    @flags.add_flag("--categories", type=str.lower, nargs="+", required=True, choices=frozenset(c.stem for c in PATHS))
    @flags.add_flag("--max-score", type=int, default=10)
    @flags.add_flag("--question-delay", type=float, default=20)
    @flags.add_flag("--disallow-bot", action="store_false", dest="allow_bot_participation")
    @flags.add_flag("--disallow-reveal", action="store_false", dest="reveal_answer")
    @flags.add_flag("--disable-hints", action="store_false", dest="show_hints")
    @flags.group(invoke_without_command=True, usage="[options...]")
    @checks.bot_has_permissions(embed_links=True)
    async def trivia(self, ctx: commands.Context, **flags):
        """Starts a new trivia session.

        This uses a powerful "command-line" interface.
        Quotation marks must be used if a value has spaces.
        **All options except `--categories` are optional.**

        __The following options are valid:__

        `--categories`: The question categories to base my bank of questions on. **Required**
        `--max-score`: The maximum amount of points a user needs in order to win. (Default: 10; Min: 5; Max: 30)
        `--question-delay`: The time, in seconds, users have to answer. (Default: 20; Min: 10; Max: 50)

        __The remaining options do not take any arguments and are simply just flags:__

        `--disallow-bot`: I don't get to participate in the game. :(
        `--disallow-reveal`: The answer won't be revealed if time's up and nobody has guessed it yet.
        `--disable-hints`: Hints will not be given.

        (Bot Needs: Embed Links)
        """
        if self.get_trivia_session(ctx.channel) is not None:
            await ctx.send("There's already an active trivia session in this channel.")
            return

        if not 5 <= flags["max_score"] <= 30:
            await ctx.send("Maximum score must be greater than 5 and less than 30.")
            return

        if not 10 <= flags["question_delay"] <= 50:
            await ctx.send("Question delay must be greater than 10 and less than 50.")
            return

        categories = flags.pop("categories")
        category_credits = []
        data = {}
        async with ctx.typing():
            for category in categories:
                path = next(p for p in PATHS if p.stem == category)

                async with aiofiles.open(path, "r") as raw_data:
                    category_list = yaml.safe_load(await raw_data.read())

                author = category_list.pop("AUTHOR", None)
                if author is not None:
                    category_credits.append(f"`{category} (by {author})`")
                else:
                    category_credits.append(f"`{category}`")

                data.update(category_list)

        embed = Embed(title="Trivia Session Starting!", colour=0x2F3136)
        embed.add_field(name="**Categories**", value=formatting.humanise_sequence(category_credits))
        await ctx.send(embed=embed)

        session = TriviaSession.start(ctx, data, **flags)
        self._active_trivia_sessions.add(session)


    @trivia.error
    async def on_trivia_error(self, ctx: commands.Context, error):
        error = getattr(error, "original", error)

        if isinstance(error, flags.ArgumentParsingError):
            await ctx.send(f"Argument parsing error: {error}")
            error.handled = True


    @trivia.command(name="stop")
    async def trivia_stop(self, ctx: commands.Context):
        """Stops the current trivia session.
        You must either be the starter or a user with the Manage Messages permission in order to do this.
        """
        session = self.get_trivia_session(ctx.channel)
        if session is None:
            await ctx.send("There's no active trivia session in this channel.")
            return

        checks = (
            ctx.channel.permissions_for(ctx.author).manage_messages,
            ctx.author == session.starter,
            ctx.author.id in ctx.bot.owner_ids,
        )

        if any(checks):
            await session.end_game()
            await ctx.send("Trivia session stopped.")
        else:
            await ctx.send(
                "You must either be the starter or a user with the `Manage Messages` permission in order to do this."
            )


    @trivia.command(name="scores", aliases=["scoreboard"])
    async def trivia_scores(self, ctx: commands.Context):
        """Shows the player scores in the current trivia session."""
        session = self.get_trivia_session(ctx.channel)
        if session is None:
            await ctx.send("There's no active trivia session in this channel.")
            return

        if session.player_scores:
            await session.send_scoreboard()
        else:
            await ctx.send("Nobody has scored any points yet.")


def setup(bot):
    bot.add_cog(Trivia())
