"""
© Copyright 2018-2020 HitchedSyringe, All Rights Reserved.

Redistributing, using or owning a copy of this software without explicit permissions
is against these licensing terms, your license(s) to this software can be revoked at
any time without explicit notice beforehand and at the time of revocation.
Your license is non-transferrable, the terms of this license only permit you to do the
following; Create pull requests and make modifications to this repository.

"""


__all__ = ("TriviaSession",)


import asyncio
import logging
import random
import re
import time
from collections import Counter

import discord
from discord import Embed
from discord.utils import escape_mentions

from SleepyBot.utils import formatting


_LOG = logging.getLogger(__name__)


_FAIL_REVEAL_MESSAGES = (
    "Time's up! The answer was **{answer}**.",
    "I know this one! It's **{answer}**.",
    "Easy: **{answer}**.",
    "I happen to be an expert on this. The answer is **{answer}**.",
    "I don't know how you missed this one... The answer was **{answer}**.",
    "What? Nobody got this one? The answer was **{answer}**.",
)


_FAIL_NO_REVEAL_MESSAGES = (
    "Moving on...",
    "Maybe you'll get the next one...",
    "On to the next question...",
    "I'm sure you'll know the answer of the next one.",
    "Time's up! Let's move on to the next question, shall we?",
    "\N{PENSIVE FACE} Let's move on...",
)


# Sometimes our answers might have these, so we'll
# have to build a small translation table and regex them out.
_SMART_QUOTE_MAPPINGS = {
    "\u2018": "'",  # Left single quote
    "\u2019": "'",  # Right single quote
    "\u201C": '"',  # Left double quote
    "\u201D": '"',  # Right double quote
}


def _replace_quote(match):
    return _SMART_QUOTE_MAPPINGS.get(match.group(0), "")


_SMART_QUOTE_REGEX = re.compile("|".join(_SMART_QUOTE_MAPPINGS.keys()))


class TriviaSession:
    """A class that manages and handles a trivia minigame session.
    This class should only be created using :meth:`TriviaSession.start`.

    Attributes
    ----------
    bot: :class:`commands.Bot`
        The bot.
    channel: :class:`discord.TextChannel`
        The channel the session was created in.
    starter: :class:`discord.Member`
        The member who started the session.
    ctx: :class:`commands.Context`
        The invokation context.
    settings: :class:`dict`
        Settings for the session, with values for the following:
         - max_score: :class:`int`
         - question_delay: :class:`float`
         - allow_bot_participation: :class:`bool`
         - reveal_answer: :class:`bool`
         - allow_skipping: :class:`bool`
         - show_hints: :class:`bool`
    current_question_number: :class:`int`
        The question number the session is currently on.
    player_scores: :class:`collections.Counter`
        A counter mapping :class:`discord.Member` to :class:`int` scores.
    """

    __slots__ = (
        "bot",
        "channel",
        "starter",
        "ctx",
        "settings",
        "__data",
        "current_question_number",
        "player_scores",
        "_last_response",
        "__tasks",
    )

    def __init__(self, ctx, data: dict, **settings):
        self.bot = ctx.bot
        self.channel = ctx.channel
        self.starter = ctx.author
        self.ctx = ctx
        self.settings = settings

        self.__data = []
        # Due to YAML's ambiguous syntax, answers like ``yes/no``, ``true/false`` and ``on/off``
        # will load as the boolean values ``True/False``, respectively. This isn't necessarily
        # desirable as an answer, so this function aims to undo that for bools.
        for question, raw_data in data.items():
            # Start off with a set to ensure that the answers are uniquified.
            raw_answers = set()
            for answer in raw_data["Answers"]:
                if answer is True:
                    raw_answers.update(("True", "Yes", "On"))
                elif answer is False:
                    raw_answers.update(("False", "No", "Off"))
                else:
                    raw_answers.add(str(answer))

            # Convert to tuple since sets don't have indices.
            self.__data.append((question, raw_data.get("Image"), tuple(raw_answers)))

        random.shuffle(self.__data)

        self.current_question_number = 0
        self.player_scores = Counter()
        self._last_response = time.time()

        self.__tasks = []


    @classmethod
    def start(cls, ctx, data: dict, **settings):
        """|meth|

        A factory method that starts a new trivia session.
        This allows the session to manage the running and cancellation of its own tasks.

        Parameters
        ----------
        ctx: :class:`commands.Context`
            The invokation context.
        data: :class:`dict`
            A dictionary of :class:`str` questions mapping to a List[:class:`str`] of answers.

        Returns
        -------
        :class:`TriviaSession`
            The newly run trivia session.
        """
        session = cls(ctx, data, **settings)

        loop = ctx.bot.loop
        session.__tasks.append(loop.create_task(session._internal_loop()))

        _LOG.debug("Started new trivia session in %s (ID: %d)", ctx.channel, ctx.channel.id)

        return session


    async def _internal_loop(self) -> None:
        """|coro|

        The internal loop that runs the trivia session.
        For internal use only.
        """
        max_score = self.settings["max_score"]
        show_hints = self.settings["show_hints"]

        delay = self.settings["question_delay"]
        timeout = delay * 4

        for question, image, answers in self.__data:
            self.current_question_number += 1

            await self.ctx.trigger_typing()
            await asyncio.sleep(3)  # Small delay so we're not rapid firing questions at the user.

            embed = Embed(
                title=f"Question #{self.current_question_number}",
                description=question,
                colour=0x2F3136
            )

            if image is not None:
                embed.set_image(url=image)

            if show_hints:
                embed.set_footer(text="Hints will be revealed soon.")
                message = await self.ctx.send(embed=embed)

                # Reveal hints as the question timer dwindles.
                hint_task = self.bot.loop.create_task(self._reveal_hints(message, question, answers[0], delay))
                self.__tasks.append(hint_task)

                should_continue = await self._wait_for_answer(answers, delay, timeout)

                hint_task.cancel()
                self.__tasks.remove(hint_task)
            else:
                embed.set_footer(text="Hints are disabled for this session.")
                await self.ctx.send(embed=embed)

                should_continue = await self._wait_for_answer(answers, delay, timeout)

            if should_continue is False:
                break

            if any(score >= max_score for score in self.player_scores.values()):
                await self.end_game()
                break

        else:
            await self.ctx.send("Huh. It seems that I've exhausted my question bank.")
            await self.end_game()


    async def _reveal_hints(self, message, question: str, answer: str, delay, *, max_hints: int = 3) -> None:
        """|coro|

        Slowly reveals the hints to the users playing the game.
        For internal use only.

        Parameters
        ----------
        message: :class:`discord.Message`
            The question message.
        question: :class:`str`
            The current question.
        answer: :class:`str`
            A correct answer to the current question.
        delay: Union[:class:`int`, :class:`float`]
            How long users have to respond (in seconds).
        *, max_hints: :class:`int`
            The maximum amount of hints to give to the user.
            .. note::

                This amount is forced to ``1`` if the answer is less than 5 characters long.
        """
        hint_delay = (delay * 0.475) / max_hints
        embed = message.embeds[0].copy()

        # For answers less than 5 chars, we don't want to reveal the whole answer or make the question too easy.
        # The reason we're not setting this beforehand is so the hint delay stays the same.
        if len(answer) < 5:
            max_hints = 1
        else:
            # Probably niche but it saves us a call to this if max_hints is 1.
            embed.set_footer(text=f"The next hint will be revealed in {hint_delay:0.2f} seconds.")

        for hint_number in range(1, max_hints + 1):
            await asyncio.sleep(hint_delay)

            hint = "".join(l if i % 5 < hint_number or l == " " else "-" for i, l in enumerate(answer))
            embed.description = f"{question}\n`{hint}`"

            if hint_number == max_hints:
                embed.set_footer(text="No more hints will be revealed, time to answer!")

            try:
                await message.edit(embed=embed)
            except discord.NotFound:
                # So we're not constantly sending a guaranteed 404.
                message = await self.ctx.send(embed=embed)


    async def _wait_for_answer(self, answers, question_delay, session_timeout) -> bool:
        """|coro|

        Waits for the correct answer, then updates scores and gives a response.
        This response is in the form of ``True``, ``False`` or ``None``.

        Parameters
        ----------
        answers: Iterable[:class:`str`]
            An iterable of valid answers to the current question.
        question_delay: Union[:class:`int`, :class:`float`]
            How long users have to respond (in seconds).
        session_timeout: Union[:class:`int`, :class:`float`]
            How long before the session ends due to no responses (in seconds).

        Returns
        -------
        :class:`bool`
            Whether or not the session was interrupted or stopped.
        """
        try:
            message = await self.bot.wait_for(
                "message",
                check=self._check_answers(answers),
                timeout=question_delay
            )
        except asyncio.TimeoutError:
            if time.time() - self._last_response >= session_timeout:
                await self.ctx.send("Hello? Is anybody there..? Alright then, I guess I'll stop.")
                self.stop()
                return False

            if self.settings["reveal_answer"]:
                reply = random.choice(_FAIL_REVEAL_MESSAGES).format(answer=answers[0])
            else:
                reply = random.choice(_FAIL_NO_REVEAL_MESSAGES)

            if self.settings["allow_bot_participation"]:
                self.player_scores[self.ctx.me] += 1
                reply += " **+1 point** for me!"

        else:
            author = message.author
            self.player_scores[author] += 1
            reply = f"You got it, {escape_mentions(author.display_name)}! **+1 point** for you!"

        await self.ctx.send(reply)

        return True


    def _check_answers(self, answers):
        """A :func:`.check` that checks for the correct answer.

        .. note::

            The ``predicate`` attribute for this function is **not** a coroutine.

        Parameters
        ----------
        answers: Iterable[:class:`str`]
            The answers which the predicate must check for.
        """
        def predicate(message):
            if message.channel != self.ctx.channel or message.author.bot:
                return False

            self._last_response = time.time()

            guess = _SMART_QUOTE_REGEX.sub(_replace_quote, message.content.lower())

            for answer in map(str.lower, answers):
                # Exact matches
                if " " in answer and answer in guess:
                    return True

                if answer in guess.split(" "):
                    return True

            return False

        return predicate


    async def send_scoreboard(self, top: int = 10) -> str:
        """Helper that sends a human-readable scoreboard showing the scores of the top-x players.

        Parameters
        ----------
        top: :class:`int`
            The amount of players to show on the scoreboard from the top.
            Defaults to ``10``.

        Returns
        -------
        :class:`discord.Message`
            The message sent.
        """
        top_scores = {m.display_name: s for m, s in self.player_scores.most_common(top)}

        return await self.ctx.send(
            f"**Trivia Scores (Showing top {top} players)**\n```hs\n{formatting.tchart(top_scores.items())}\n```"
        )


    async def end_game(self) -> None:
        """This stops the trivia session, while also showing player scores.
        This dispatches an event which can be handled through :func:`on_trivia_session_end`.
        """
        if self.player_scores:
            await self.send_scoreboard()

        self.stop()


    def stop(self, *, dispatch_event: bool = True) -> None:
        """Stops the trivia session.
        This optionally dispatches an event which can be handled through :func:`on_trivia_session_end`.

        Parameters
        ----------
        *, dispatch_event: :class:`bool`
            Whether or not to dispatch ``trivia_session_end``.
            This is useful for indicating a forced stop, whereas handling this event would be unnecessary.
            Defaults to ``True``.
        """
        for task in self.__tasks:
            task.cancel()
        self.__tasks.clear()

        if dispatch_event:
            self.bot.dispatch("trivia_session_end", self)

        _LOG.debug("Stopping trivia session in %s (ID: %d)", self.channel, self.channel.id)
