"""
Copyright (c) 2018-present HitchedSyringe

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""


from __future__ import annotations

# fmt: off
__all__ = (
    "TriviaSession",
)
# fmt: on


import asyncio
import random
import re
import time
from collections import Counter
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Tuple, Union

import discord

from sleepy.utils import human_join, tchart

from ..base_session import BaseSession
from .question import TriviaQuestion

if TYPE_CHECKING:
    from discord.ext.commands import Bot, Context
    from typing_extensions import Self

    from ..base_session import TextGuildChannel


_TIMEOUT_MSGS_REVEAL: Tuple[str, ...] = (
    "Time's up! The answer is ||{0}||.",
    "I know this one! It's ||{0}||.",
    "Easy: ||{0}||.",
    "I happen to be an expert on this. The answer is ||{0}||.",
    "I don't know how you missed this one... The answer is ||{0}||.",
    "What? Nobody got this one? The answer is ||{0}||.",
)


_TIMEOUT_MSGS: Tuple[str, ...] = (
    "Moving on...",
    "Maybe you'll get the next one.",
    "On to the next question!",
    "I'm sure you'll know the answer of the next one.",
    "Time's up! Let's move on to the next question, shall we?",
    "\N{PENSIVE FACE} Let's move on...",
)


# Sometimes the guesses might have these, so we'll have
# to build a small translation table and regex them out.
_SMART_QUOTES: Dict[str, str] = {
    "\u2018": "'",  # Left single quote
    "\u2019": "'",  # Right single quote
    "\u201C": '"',  # Left double quote
    "\u201D": '"',  # Right double quote
}


_SMART_QUOTE_REGEX: re.Pattern = re.compile("|".join(_SMART_QUOTES))


class TriviaSession(BaseSession):

    __slots__: Tuple[str, ...] = (
        "questions",
        "maximum_score",
        "question_time_limit",
        "bot_plays",
        "reveal_answer_after",
        "show_hints",
        "_last_interaction",
    )

    def __init__(
        self,
        bot: Bot,
        channel: TextGuildChannel,
        host: discord.Member,
        questions: List[TriviaQuestion],
        **options: Any,
    ) -> None:
        super().__init__(bot, channel, host)

        random.shuffle(questions)

        self.questions: List[TriviaQuestion] = questions
        self.scores: Counter[Union[discord.User, discord.Member]] = Counter()

        self.maximum_score: int = options.get("maximum_score", 10)
        self.question_time_limit: int = options.get("question_time_limit", 20)
        self.bot_plays: bool = options.get("bot_plays", True)
        self.reveal_answer_after: bool = options.get("reveal_answer_after", True)
        self.show_hints: bool = options.get("show_hints", True)

        self._last_interaction: float = time.monotonic()

    if TYPE_CHECKING:

        @classmethod
        def from_context(
            cls, ctx: Context, questions: List[TriviaQuestion], **options: Any
        ) -> Self:
            ...

    @property
    def _expiry_timestamp(self) -> float:
        return (self.question_time_limit * 4) + time.monotonic()

    async def callback(self) -> None:
        for question in self.questions:
            await self.channel.typing()
            await asyncio.sleep(5)

            category, text, answers, image_url, author = question

            embed = discord.Embed(description=text, colour=0x2F3136)
            embed.set_image(url=image_url)

            embed.add_field(name="Category", value=category)
            embed.add_field(name="Author(s)", value=author or "Unknown")

            check = self._get_answer_check(answers)

            try:
                if self.show_hints:
                    embed.set_footer(text="Hints will be revealed soon.")
                    question_message = await self.channel.send(embed=embed)

                    # In this case, the timeout isn't needed since
                    # this will "time out" anyway when `_do_hints`
                    # completes, since `Bot.wait_for` should never
                    # complete if no correct answers are given.
                    done, pending = await asyncio.wait(
                        (
                            asyncio.ensure_future(
                                self.bot.wait_for("message", check=check)
                            ),
                            asyncio.ensure_future(
                                self._do_hints(question, question_message)
                            ),
                        ),
                        return_when=asyncio.FIRST_COMPLETED,
                    )

                    for task in pending:
                        task.cancel()

                    message = done.pop().result()

                    if message is None:
                        raise asyncio.TimeoutError
                else:
                    embed.set_footer(text="No hints! Give it your best shot!")
                    await self.channel.send(embed=embed)

                    message = await self.bot.wait_for(
                        "message", check=check, timeout=self.question_time_limit
                    )
            except asyncio.TimeoutError:
                if self._last_interaction >= self._expiry_timestamp:
                    await self.channel.send("Alright... I guess I'll stop now.")
                    await self.stop()
                    return

                if self.reveal_answer_after:
                    msg = random.choice(_TIMEOUT_MSGS_REVEAL).format(answers[0])
                else:
                    msg = random.choice(_TIMEOUT_MSGS)

                if self.bot_plays:
                    self.scores[self.bot.user] += 1  # type: ignore
                    msg += " **+1 point** for me!"

                await self.channel.send(msg)
            else:
                self.scores[message.author] += 1
                await message.reply(
                    "Correct! **+1 point** for you!", mention_author=False
                )

            if max(self.scores.values()) >= self.maximum_score:
                break
        else:
            await self.channel.send("I've run out of questions to ask!")

        await self.stop(skip_sending_results=False)

    async def on_error(self, error: Exception) -> None:
        if isinstance(error, discord.HTTPException):
            # If some issue occurs with sending/editing messages
            # due to permissions or w/e, I'd rather the session
            # just silently terminate itself ASAP.
            await self.stop()

    async def _do_hints(self, question: TriviaQuestion, message: discord.Message) -> None:
        answer = question.answers[0]
        embed = message.embeds[0]

        # We don't want to make questions with answers
        # less than five characters long too easy.
        max_hints = 3 if len(answer) > 5 else 1
        delay = self.question_time_limit / max_hints

        await asyncio.sleep(5 if max_hints == 1 else delay)

        for number in range(1, max_hints + 1):
            if self.is_stopped():
                break

            hint = "".join(
                a if i % 5 < number or a.isspace() else "-" for i, a in enumerate(answer)
            )

            embed.description = (
                f"{question.text}\n```yaml\nHint {number}/{max_hints}: {hint}```"
            )

            if number == max_hints:
                embed.set_footer(text="No more hints. Give it your best shot!")
            else:
                embed.set_footer(text=f"Next hint in {delay:0.2f} seconds.")

            try:
                message = await message.edit(embed=embed)
            except discord.NotFound:
                message = await self.channel.send(embed=embed)

            await asyncio.sleep(delay)

    def _get_answer_check(self, answers: List[str]) -> Callable[[discord.Message], bool]:
        def predicate(message: discord.Message) -> bool:
            if message.channel != self.channel or message.author.bot:
                return False

            self._last_interaction = time.monotonic()

            guess = _SMART_QUOTE_REGEX.sub(
                lambda m: _SMART_QUOTES.get(m.group(0), ""), message.content.lower()
            )

            return any(
                (" " in a and a.lower() in guess) or a.lower() in guess.split()
                for a in answers
            )

        return predicate

    async def stop(self, *, skip_sending_results: bool = True) -> None:
        await super().stop()

        if (scores := self.scores) and not skip_sending_results:
            top = scores.most_common(10)
            max_ = top[0][1]

            if winners := [p for (p, s) in top if s == max_ and not p.bot]:
                message = f"\N{PARTY POPPER} {human_join(winners)} won! Congrats!"
            else:
                message = "Good game everyone! \N{SMILING FACE WITH SMILING EYES}"

            scoreboard = tchart(dict(top), lambda u: u.display_name)
            message += f"\n\n**Final Results** (Top 10)\n```hs\n{scoreboard}\n```"

            await self.channel.send(message)
