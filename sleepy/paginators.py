"""
Copyright (c) 2018-present HitchedSyringe

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""


# fmt: off
__all__ = (
    "WrappedPaginator",
)
# fmt: on


from typing import Sequence

from discord.ext import commands


class WrappedPaginator(commands.Paginator):
    r"""A paginator which allows lines to be wrapped
    automatically should they not fit.

    .. versionadded:: 3.0

    Parameters
    ----------
    wrap_on: Sequence[:class:`str`]
        A sequence of delimiters to wrap on.
        Defaults to ``(" ", "\n")``.
    force_wrapping: :class:`bool`
        Whether or not to force wrapping at the maximum
        point if wrapping with the given delimiters are
        unsuccessful.
        Defaults to ``False``.
    wrap_with_delimiters: :class:`bool`
        Whether or not to include the wrapping delimiters
        at the beginning of a wrapped line.
        Defaults to ``True``.

    Attributes
    ----------
    wrap_on: Sequence[:class:`str`]
        The sequence of delimiters the paginator is
        wrapping on.
    force_wrapping: :class:`bool`
        Whether the paginator is forcing wrapping at the
        maximum point if wrapping with the given delimiters
        are unsuccessful.
    wrap_with_delimiters: :class:`bool`
        Whether the paginator is including the wrapping
        delimiters at the beginning of newly wrapped lines.
    """

    def __init__(
        self,
        prefix: str = "```",
        suffix: str = "```",
        max_size: int = 2000,
        linesep: str = "\n",
        wrap_on: Sequence[str] = (" ", "\n"),
        *,
        force_wrapping: bool = False,
        wrap_with_delimiters: bool = True,
    ) -> None:
        super().__init__(prefix, suffix, max_size, linesep)

        self.wrap_on: Sequence[str] = wrap_on
        self.force_wrapping: bool = force_wrapping
        self.wrap_with_delimiters: bool = wrap_with_delimiters

    @property
    def actual_max_size(self) -> int:
        """:class:`int`: The maximum size of the paginator with the
        prefix, suffix, and line separator lengths all accounted for.

        .. versionchanged:: 3.1.5
            This is now a read-only property.
        """
        return self.max_size - self._prefix_len - self._suffix_len - self._linesep_len * 2

    def add_line(self, line: str = "", /, *, empty: bool = False) -> None:
        """Adds a line to the current page.

        If the line exceeds :attr:`actual_max_size`, then
        the line will automatically wrap to the next page.

        Parameters
        ----------
        line: :class:`str`
            The line to add.
            Defaults to an empty string.
        empty: :class:`bool`
            Whether or not an empty line should be added.
            Defaults to ``False``.

        Raises
        ------
        RuntimeError
            The line cannot wrap to the next page with the
            given delimiters and :attr:`force_wrapping` is
            ``False``.
        """
        while len(line) > self.actual_max_size:
            for delimiter in self.wrap_on:
                point = line.rfind(delimiter, 0, self.actual_max_size + 1)

                if point > 0:
                    super().add_line(line[:point])

                    if self.wrap_with_delimiters:
                        point += len(delimiter)

                    line = line[point:]
                    break
            else:
                if not self.force_wrapping:
                    raise RuntimeError(f"Could not wrap with delimiters: {self.wrap_on}.")

                super().add_line(line[: self.actual_max_size - 1])
                line = line[self.actual_max_size - 1 :]

        super().add_line(line, empty=empty)
