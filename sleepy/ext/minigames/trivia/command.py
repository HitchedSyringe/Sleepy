"""
Copyright (c) 2018-present HitchedSyringe

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

__all__ = (
    "TriviaFlags",
    "trivia_command",
)


from typing import TYPE_CHECKING, Tuple

import yaml
from discord import Colour, Embed
from discord.ext import commands
from typing_extensions import Annotated

from sleepy.utils import _as_argparse_dict, human_join, tchart

from .categories import CATEGORIES
from .question import TriviaQuestion
from .session import TriviaSession

if TYPE_CHECKING:
    from pathlib import Path

    from sleepy.context import Context as SleepyContext

    from ..cog import Minigames


def resolve_category(name: str) -> Path:
    path = CATEGORIES.joinpath(f"{name}.yaml").resolve()

    if not path.is_file() or not path.is_relative_to(CATEGORIES):  # type: ignore
        raise commands.BadArgument(f"Category '{name}' is invalid.")

    return path


class TriviaFlags(commands.FlagConverter):
    categories: Tuple[Annotated["Path", resolve_category], ...]
    maximum_score: commands.Range[int, 5, 30] = commands.flag(
        name="maximum-score",
        default=10,
        aliases=("max-score",),  # type: ignore
    )
    question_time_limit: commands.Range[int, 15, 50] = commands.flag(
        name="question-time-limit", default=20
    )
    bot_plays: bool = commands.flag(name="bot-plays", default=True)
    reveal_answer_after: bool = commands.flag(name="reveal-answer-after", default=True)
    show_hints: bool = commands.flag(name="show-hints", default=True)


async def trivia_command(
    cog: Minigames, ctx: SleepyContext, *, options: TriviaFlags
) -> None:
    category_credits = []
    questions = []

    async with ctx.typing():
        for category in set(options.categories):
            try:
                with category.open() as data:
                    data = yaml.safe_load(data)
            except OSError:
                await ctx.send("Something went wrong while reading a category.")
                return

            author = data.pop("AUTHOR", None)
            name = category.stem

            if author is not None:
                category_credits.append(f"`{name} (by {author})`")
            else:
                category_credits.append(f"`{name}`")

            questions.extend(
                TriviaQuestion(name, q, author=author, **d) for q, d in data.items()
            )

    options_dict = _as_argparse_dict(options)
    del options_dict["categories"]

    embed = Embed(title="A new trivia session is starting!", colour=Colour.dark_embed())
    embed.set_footer(text=f"Started by {ctx.author}")

    embed.add_field(name="Categories", value=human_join(category_credits), inline=False)

    settings_chart = tchart(options_dict, lambda s: s.replace('_', ' ').title())

    embed.add_field(name="Settings", value=f"```py\n{settings_chart}```")

    await ctx.send(embed=embed)

    session = TriviaSession.from_context(ctx, questions, **options_dict)

    await session.start()
