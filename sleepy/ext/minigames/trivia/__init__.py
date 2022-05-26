"""
Copyright (c) 2018-present HitchedSyringe

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""


from __future__ import annotations

__all__ = (
    "CATEGORIES",
    "TriviaFlags",
    "TriviaSession",
    "TriviaQuestion",
    "trivia_command",
)


from typing import TYPE_CHECKING, Tuple

import aiofiles
import yaml
from discord import Embed
from discord.ext import commands

from sleepy.utils import _as_argparse_dict, human_join, tchart

from .categories import CATEGORIES
from .question import TriviaQuestion
from .session import TriviaSession

if TYPE_CHECKING:
    from ..cog import Minigames


class TriviaFlags(commands.FlagConverter):
    categories: Tuple[str, ...]
    maximum_score: commands.Range[int, 5, 30] = commands.flag(
        name="maximum-score", default=10, aliases=("max-score",)  # type: ignore
    )
    question_time_limit: commands.Range[int, 15, 50] = commands.flag(
        name="question-time-limit", default=20
    )
    bot_plays: bool = commands.flag(name="bot-plays", default=True)
    reveal_answer_after: bool = commands.flag(name="reveal-answer-after", default=True)
    show_hints: bool = commands.flag(name="show-hints", default=True)


async def trivia_command(
    cog: Minigames, ctx: commands.Context, *, options: TriviaFlags
) -> None:
    category_credits = []
    questions = []

    async with ctx.typing():
        for category in set(options.categories):
            category_path = CATEGORIES.joinpath(f"{category}.yaml").resolve()

            if not category_path.is_relative_to(CATEGORIES):  # type: ignore
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
                category_credits.append(f"`{category} (by {author})`")
            else:
                category_credits.append(f"`{category}`")

            questions.extend(
                TriviaQuestion(category, q, author=author, **d) for q, d in data.items()
            )

    options_dict = _as_argparse_dict(options)
    del options_dict["categories"]

    embed = Embed(title="A new trivia session is starting!", colour=0x2F3136)
    embed.set_footer(text=f"Started by {ctx.author}")

    embed.add_field(name="Categories", value=human_join(category_credits), inline=False)

    settings_chart = tchart(options_dict, lambda s: s.replace('_', ' ').title())

    embed.add_field(name="Settings", value=f"```py\n{settings_chart}```")

    await ctx.send(embed=embed)

    session = TriviaSession.from_context(ctx, questions, **options_dict)

    await session.start()
