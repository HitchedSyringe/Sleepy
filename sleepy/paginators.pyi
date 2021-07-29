from collections.abc import Sequence

from discord.ext import commands


class WrappedPaginator(commands.Paginator):

    wrap_on: Sequence[str]
    force_wrapping: bool
    wrap_with_delimiters: bool
    actual_max_size: int

    def __init__(
        self,
        prefix: str = "```",
        suffix: str = "```",
        max_size: int = 2000,
        linesep: str = "\n",
        wrap_on: Sequence[str] = (" ", "\n"),
        *,
        force_wrapping: bool = False,
        wrap_with_delimiters: bool = True
    ) -> None: ...

    def add_line(
        self,
        line: str = "",
        /,
        *,
        empty: bool = False
    ) -> None: ...
