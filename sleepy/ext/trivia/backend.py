"""
Copyright (c) 2018-present HitchedSyringe

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""


__all__ = (
    "TriviaSession",
    "TriviaQuestion",
)


import asyncio
import random
import re
import time
from collections import Counter, namedtuple

import discord
from discord import Embed

from sleepy.utils import human_join, tchart


TIMEOUT_MSGS_REVEAL = (
    "Time's up! The answer is ||{0}||.",
    "I know this one! It's ||{0}||.",
    "Easy: ||{0}||.",
    "I happen to be an expert on this. The answer is ||{0}||.",
    "I don't know how you missed this one... The answer is ||{0}||.",
    "What? Nobody got this one? The answer is ||{0}||.",
)


TIMEOUT_MSGS = (
    "Moving on...",
    "Maybe you'll get the next one.",
    "On to the next question!",
    "I'm sure you'll know the answer of the next one.",
    "Time's up! Let's move on to the next question, shall we?",
    "\N{PENSIVE FACE} Let's move on...",
)


# Sometimes the guesses might have these, so we'll have
# to build a small translation table and regex them out.
SMART_QUOTES = {
    "\u2018": "'",  # Left single quote
    "\u2019": "'",  # Right single quote
    "\u201C": '"',  # Left double quote
    "\u201D": '"',  # Right double quote
}


SMART_QUOTE_REGEX = re.compile("|".join(SMART_QUOTES))


TriviaQuestion = namedtuple(
    "TriviaQuestion",
    "category text answers image_url author",
    defaults=(None, None)
)


class TriviaSession:

    __slots__ = (
        "bot",
        "channel",
        "owner",
        "questions",
        "scores",
        "max_score",
        "answer_time_limit",
        "bot_plays",
        "reveal_answer",
        "give_hints",
        "_last_guess",
        "__core_loop",
    )

    def __init__(
        self,
        ctx,
        questions,
        /,
        *,
        max_score=10,
        answer_time_limit=20,
        bot_plays=True,
        reveal_answer=True,
        give_hints=True
    ):
        self.bot = ctx.bot
        self.channel = ctx.channel
        self.owner = ctx.author
        self.questions = questions
        self.scores = Counter()

        self.max_score = max_score
        self.answer_time_limit = answer_time_limit
        self.bot_plays = bot_plays
        self.reveal_answer = reveal_answer
        self.give_hints = give_hints

        self._last_guess = time.time()
        self.__core_loop = None

    @classmethod
    def start(cls, ctx, questions, /, **settings):
        random.shuffle(questions)

        session = cls(ctx, questions, **settings)
        session.__core_loop = task = ctx.loop.create_task(session.__internal_loop())
        task.add_done_callback(session.__error_handler)

        ctx.bot.dispatch("trivia_session_start", session)

        return session

    def __error_handler(self, fut):
        try:
            fut.result()
        except asyncio.CancelledError:
            pass
        except discord.HTTPException:
            # If some issue occurs with sending/editing messages
            # due to permissions or w/e, I'd rather the session
            # just silently terminate itself ASAP.
            asyncio.create_task(self.end_game(send_results=False))
        except Exception as exc:
            self.bot.dispatch("trivia_session_error", self, exc)

    async def __internal_loop(self):
        for question in self.questions:
            await self.channel.trigger_typing()
            await asyncio.sleep(5)

            embed = Embed(description=question.text, colour=0x2F3136)
            embed.add_field(name="Category", value=question.category)
            embed.add_field(name="Author(s)", value=question.author or "Unknown")

            if question.image_url is not None:
                embed.set_image(url=question.image_url)

            check = self._get_answer_check(question.answers)

            try:
                if self.give_hints:
                    embed.set_footer(text="Hints will be revealed soon.")
                    msg = await self.channel.send(embed=embed)

                    # In this case, the timeout isn't needed since
                    # this will "time out" anyway when `_do_hints`
                    # completes, since `Bot.wait_for` should never
                    # complete if no correct answers are given.
                    done, pending = await asyncio.wait(
                        (
                            asyncio.ensure_future(self.bot.wait_for("message", check=check)),
                            asyncio.ensure_future(self._do_hints(question, msg)),
                        ),
                        return_when=asyncio.FIRST_COMPLETED
                    )

                    for task in pending:
                        task.cancel()

                    message = done.pop().result()

                    if message is None:
                        raise asyncio.TimeoutError()
                else:
                    embed.set_footer(text="No hints! Give it your best shot!")
                    await self.channel.send(embed=embed)

                    message = await self.bot.wait_for(
                        "message",
                        check=check,
                        timeout=self.answer_time_limit
                    )
            except asyncio.TimeoutError:
                if time.time() - self._last_guess >= self.answer_time_limit * 4:
                    await self.channel.send("Nobody's participating... I guess I'll stop now.")
                    await self.end_game(send_results=False)
                    return

                if self.reveal_answer:
                    msg = random.choice(TIMEOUT_MSGS_REVEAL).format(question.answers[0])
                else:
                    msg = random.choice(TIMEOUT_MSGS)

                if self.bot_plays:
                    self.scores[self.bot.user] += 1
                    msg += " **+1 point** for me!"

                await self.channel.send(msg)
            else:
                self.scores[message.author] += 1
                await message.reply("Correct! **+1 point** for you!", mention_author=False)

            if max(self.scores.values()) >= self.max_score:
                break
        else:
            await self.channel.send("I've run out of questions to ask!")

        await self.end_game()

    async def _do_hints(self, question, message):
        answer = question.answers[0]
        embed = message.embeds[0]

        # We don't want to make questions with answers
        # less than five characters long too easy.
        max_hints = 3 if len(answer) > 5 else 1
        delay = self.answer_time_limit / max_hints

        await asyncio.sleep(5 if max_hints == 1 else delay)

        for number in range(1, max_hints + 1):
            if self.__core_loop.cancelled():
                break

            hint = "".join(
                a if i % 5 < number or a.isspace() else "-"
                for i, a in enumerate(answer)
            )

            embed.description = f"{question.text}\n```yaml\nHint {number}/{max_hints}: {hint}```"

            if number == max_hints:
                embed.set_footer(text="No more hints. Give it your best shot!")
            else:
                embed.set_footer(text=f"Next hint in {delay:0.2f} seconds.")

            try:
                message = await message.edit(embed=embed)
            except discord.NotFound:
                message = await self.channel.send(embed=embed)

            await asyncio.sleep(delay)

    def _get_answer_check(self, answers):

        def predicate(message):
            if message.channel != self.channel or message.author.bot:
                return False

            self._last_guess = time.time()

            guess = SMART_QUOTE_REGEX.sub(
                lambda m: SMART_QUOTES.get(m.group(0), ""),
                message.content.lower()
            )

            return any(
                (" " in a and a.lower() in guess)
                or a.lower() in guess.split()
                for a in answers
            )

        return predicate

    async def end_game(self, *, send_results=True):
        if self.scores and send_results:
            top_ten = self.scores.most_common(10)
            highest = top_ten[0][1]

            winners = [
                p.mention for p, s in self.scores.items()
                if s == highest and not p.bot
            ]

            if winners:
                msg = f"\N{PARTY POPPER} {human_join(winners)} won! Congrats!"
            else:
                msg = "Good game everyone! \N{SMILING FACE WITH SMILING EYES}"

            msg += f"\n\n**Trivia Results** (Top 10)\n```hs\n{tchart(dict(top_ten))}```"

            await self.channel.send(msg, allowed_mentions=discord.AllowedMentions(users=False))

        self.bot.dispatch("trivia_session_end", self)
        self.__core_loop.cancel()

    def stop(self):
        self.__core_loop.cancel()
