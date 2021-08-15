from collections.abc import Sequence

from discord.ext import commands


class WrappedPaginator(commands.Paginator):

    wrap_on: Sequence[str]
    force_wrapping: bool
    wrap_with_delimiters: bool

    def __init__(
        self,
        prefix: str = ...,
        suffix: str = ...,
        max_size: int = ...,
        linesep: str = ...,
        wrap_on: Sequence[str] = ...,
        *,
        force_wrapping: bool = ...,
        wrap_with_delimiters: bool = ...
    ) -> None: ...

    @property
    def actual_max_size(self) -> int: ...

    def add_line(
        self,
        line: str = ...,
        /,
        *,
        empty: bool = ...
    ) -> None: ...
