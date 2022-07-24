"""
Copyright (c) 2018-present HitchedSyringe

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""


from __future__ import annotations

__all__ = (
    "DISCORD_SERVER_URL",
    "PERMISSIONS_VALUE",
    "SOURCE_CODE_URL",
    "plural",
    "bool_to_emoji",
    "find_extensions_in",
    "human_delta",
    "human_join",
    "human_number",
    "measure_performance",
    "progress_bar",
    "tchart",
    "truncate",
)


import math
import random
import time
from asyncio import iscoroutinefunction
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Any,
    Awaitable,
    Callable,
    Dict,
    Generator,
    Mapping,
    Optional,
    Sequence,
    Tuple,
    TypeVar,
    Union,
    cast,
    overload,
)

from dateutil.relativedelta import relativedelta

if TYPE_CHECKING:
    from discord.ext.commands import FlagConverter
    from typing_extensions import ParamSpec

    _R = TypeVar("_R")
    _P = ParamSpec("_P")

    AsyncFunc = Callable[_P, Awaitable[_R]]


DISCORD_SERVER_URL: str = "https://discord.gg/xHgh2Xg"
SOURCE_CODE_URL: str = "https://github.com/HitSyr/Sleepy"

PERMISSIONS_VALUE: int = 274878295110


class plural:
    """A formatting helper class that pluralises a string
    based on the given numerical value.

    .. versionadded:: 1.7

    .. versionchanged:: 3.0
        Raise :exc:`TypeError` if passed ``value`` is
        not a :class:`int` or :class:`float`.

    Parameters
    ----------
    value: :class:`float`
        The value which the pluralisation is based on.

        .. versionchanged:: 3.0
            This is now a positional-only argument.
    value_format_spec: Optional[:class:`str`]
        The formatting spec for the numerical value
        itself.

        .. versionadded:: 3.0

    Examples
    --------
    .. testsetup::
        from sleepy.utils import plural

    .. doctest::
        >>> format(plural(1), "tree")
        "1 tree"
        >>> format(plural(10), "car")
        "10 cars"
        >>> format(plural(10000, ",d"), "foot|feet")
        "10,000 feet"
        >>> f"There are {plural(7):bird} in the nest."
        "There are 7 birds in the nest."
        >>> f"I see {plural(4):goose|geese} on the lake."
        "I see 4 geese on the lake."
        >>> f"Mount Everest is {plural(29032, ',d'):foot|feet} tall!"
        "Mount Everest is 29,032 feet tall!"
        >>> f"It is {plural(-3.6213, '.2f'):degree} Celcius outside."
        "It is -3.62 degrees Celcius outside."
    """

    __slots__: Tuple[str, ...] = ("__value", "__value_fmt")

    def __init__(self, value: float, /, value_format_spec: Optional[str] = None) -> None:
        if not isinstance(value, (int, float)):
            raise TypeError(f"Expected value to be int or float, not {type(value)!r}.")

        self.__value: float = value
        self.__value_fmt: str = value_format_spec or ""

    def __format__(self, spec: str) -> str:
        singular, _, plural = spec.partition("|")
        value = self.__value

        if abs(value) == 1:
            return f"{value:{self.__value_fmt}} {singular}"

        return f"{value:{self.__value_fmt}} {plural or f'{singular}s'}"


def _as_argparse_dict(flag_converter: FlagConverter) -> Dict[str, Any]:
    flags = flag_converter.get_flags().values()
    return {f.attribute: getattr(flag_converter, f.attribute) for f in flags}


def bool_to_emoji(value: Optional[Any]) -> str:
    """Returns an emoji based on a given boolean-like value.

    This exists to assist with humanizing :class:`bool` values.

    This returns one of the following:

    * `<:check:821284209401921557>` if `value` evaluates to `True`.
    * `<:x_:821284209792516096>` if `value` evaluates to `False`.
    * `<:slash:821284209763024896>` if `value` is `None`.

    .. versionadded:: 3.0

    Parameters
    ----------
    value: Optional[Any]
        A boolean-like value to return an emoji for.

    Returns
    -------
    :class:`str`
        The emoji result.
    """
    if value is None:
        return "<:slash:821284209763024896>"

    return "<:check:821284209401921557>" if value else "<:x_:821284209792516096>"


def find_extensions_in(path: Union[str, Path]) -> Generator[str, None, None]:
    """Returns a generator with the names of every
    recognized extension in the given path.

    .. versionadded:: 3.0

    Parameters
    ----------
    path: Union[:class:`str`, :class:`pathlib.Path`]
        The path to find extensions in.

    Yields
    ------
    :class:`str`
        The name of the recognized extension.
    """
    if not isinstance(path, Path):
        path = Path(path)

    if not path.is_dir():
        return

    # Module-style extensions.
    for extension in path.glob("*/__init__.py"):
        yield ".".join(extension.parent.parts).lstrip(".")

    # Python file extensions.
    for extension in path.glob("*.py"):
        yield ".".join(extension.with_suffix("").parts).lstrip(".")


def human_delta(
    dt1: datetime,
    dt2: Optional[datetime] = None,
    *,
    brief: bool = False,
    absolute: bool = False,
) -> str:
    """Humanizes the delta between two given datetimes.

    .. versionadded:: 1.9

    .. versionchanged:: 3.0

        * Renamed ``duration`` parameter to ``delta``.
        * Return ``"Just now"`` if the delta is 0, otherwise,
          indicate if the delta is negative or positive in the
          returned string. This behaviour can be disabled via
          passing ``absolute=True``.

    .. versionchanged:: 3.1
        Replaced ``delta`` argument with the ``datetime1``
        and ``datetime2`` arguments.

    .. versionchanged:: 3.2

        * Renamed ``datetime1`` and ``datetime2`` parameters to
          ``dt1`` and ``dt2``, respectively.
        * Naive datetimes passed are now internally converted
          to be UTC-aware

    Parameters
    ----------
    dt1: :class:`datetime.datetime`
    dt2: Optional[:class:`datetime.datetime`]
        The datetimes to humanize the delta of.
        This delta is calculated via `dt2 - dt1`.
        If not given, then the second datetime defaults to
        the current time as a UTC-aware datetime.

        .. note::

            Naive datetimes are automatically converted to
            be UTC-aware. Additionally, microseconds are
            disregarded internally when calculating.

        .. versionchanged:: 3.3
            This is no longer a positional-only argument.
    brief: :class:`bool`
        Whether or not to only return the first component of
        the humanised delta.
        Defaults to ``False``.

        .. versionadded:: 2.0
    absolute: :class:`bool`
        Whether or not to return the humanised delta only,
        without indicating whether it is past or future tense.
        Defaults to ``False``.

        .. versionadded:: 3.0

    Returns
    -------
    :class:`str`
        The human-readable delta.

    Examples
    --------
    .. testsetup::
        from sleepy.utils import human_delta

    .. doctest::
        >>> human_delta(datetime.datetime(2019, 1, 1), datetime.datetime(2020, 1, 1))
        "1 year ago"
        >>> human_delta(datetime.datetime(2020, 4, 20), datetime.datetime(2010, 3, 15))
        "In 10 years, 1 month, and 5 days"
        >>> human_delta(datetime.datetime(2024, 2, 29), datetime.datetime(2020, 3, 10), absolute=True)
        "3 years, 11 months, 2 weeks, and 19 days"
        >>> human_delta(datetime.datetime(2024, 2, 29), datetime.datetime(2022, 1, 11), brief=True)
        "In 2 years"
    """
    dt1 = dt1.replace(microsecond=0)

    if dt1.tzinfo is None:
        dt1 = dt1.replace(tzinfo=timezone.utc)

    if dt2 is None:
        dt2 = datetime.now(timezone.utc)
    elif dt2.tzinfo is None:
        dt2 = dt2.replace(tzinfo=timezone.utc)

    dt2 = dt2.replace(microsecond=0)

    if dt1 == dt2:
        return "Just now"

    delta = abs(relativedelta(dt1, dt2))

    # This is written this way instead of using the much
    # more obvious getattr approach to allow for ease in
    # transitioning to i18n at some point in the future.
    values = (
        (delta.years, "year"),
        (delta.months, "month"),
        (delta.weeks, "week"),
        # We'll have to subtract the days converted to weeks
        # from the day count since it isn't done internally.
        (delta.days - (delta.weeks * 7), "day"),
        (delta.hours, "hour"),
        (delta.minutes, "minute"),
        (delta.seconds, "second"),
    )

    counts = [format(plural(v, ",d"), n) for v, n in values if v > 0]
    humanised = counts[0] if brief else human_join(counts)

    if absolute:
        return humanised

    if dt1 > dt2:
        return f"In {humanised}"

    return f"{humanised} ago"


def human_join(sequence: Sequence[Any], /, *, joiner: str = "and") -> str:
    """Returns a human-readable, comma-separted sequence, with
    the last element joined with a given joiner.

    This uses an Oxford comma, because without one, the output
    would be difficult to interpret.

    .. versionadded:: 1.6

    .. versionchanged:: 2.0

        * Raise :exc:`ValueError` if the given sequence is empty.
        * Processed strings now use an Oxford comma.

    .. versionchanged:: 3.0

        * Passing empty sequences will now return an empty string.
        * Allow passing sequences with non-string values.

    Parameters
    ----------
    sequence: Sequence[Any]
        The sequence of items to join.

        .. versionchanged:: 3.0
            This is now a positional-only argument.
    joiner: :class:`str`
        The string that joins the last item with the rest
        of the sequence.
        Defaults to ``"and"``.

    Returns
    -------
    :class:`str`
        The human-readable list.

    Examples
    --------
    .. testsetup::
        from sleepy.utils import human_join

    .. doctest::
        >>> human_join(["one"])
        "one"
        >>> human_join(["one", "two"])
        "one and two"
        >>> human_join(["one", "two", "three"])
        "one, two, and three"
        >>> human_join(["yes", "no"], joiner="or")
        "yes or no"
        >>> human_join([1, 2, 3, 4, 5], joiner="or")
        "1, 2, 3, 4, or 5"
    """
    if not sequence:
        return ""

    sequence_size = len(sequence)

    if sequence_size == 1:
        return str(sequence[0])

    if sequence_size == 2:
        return f"{sequence[0]} {joiner} {sequence[1]}"

    return ", ".join(map(str, sequence[:-1])) + f", {joiner} {sequence[-1]}"


def human_number(
    number: float,
    /,
    sigfigs: Optional[int] = 3,
    *,
    strip_trailing_zeroes: bool = True,
    suffixes: Sequence[str] = "\u200bKMBTPEZY",
):
    r"""Humanizes a given number.

    This shortens numbers using a base-1000 scale.

    .. versionadded:: 1.10

    .. versionchanged:: 3.0

        * Renamed ``precision`` parameter to ``sigfigs``.
        * Renamed ``remove_trailing_zeroes`` parameter to
        ``strip_trailing_zeroes``.
        * Raise :exc:`ValueError` if ``suffixes`` is an empty sequence.

    .. versionchanged:: 3.1.5
        Raise :exc:`ValueError` if ``sigfigs`` is negative or 0.

    Parameters
    ----------
    number: :class:`float`
        The number to humanize.

        .. versionchanged:: 3.0
            This is now a positional-only argument.
    sigfigs: Optional[:class:`int`]
        The number of significant figures to round to.
        If ``None`` is passed, then the number will not
        be rounded.
        Defaults to ``3``.

        .. versionchanged:: 3.1.5
            Allow passing ``None`` to denote no rounding.
    strip_trailing_zeroes: :class:`bool`
        Whether or not to strip trailing zeroes.
        Defaults to ``True``.

        .. versionchanged:: 3.0
            This is now a keyword-only argument.
    suffixes: Sequence[:class:`str`]
        The suffixes to use for each power of 1000.
        The order of the sequence is in ascending order.
        Defaults to ``"\u200bKMBTPEZY"``.

        .. versionchanged:: 3.0
            This is now a keyword-only argument.

    Returns
    -------
    :class:`str`
        The shortened, human-readable number.

    Raises
    ------
    ValueError
        ``suffixes`` was an empty sequence.

    Examples
    --------
    .. testsetup::
        from sleepy.utils import human_number

    .. doctest::
        >>> human_number(-543210)
        "-543K"
        >>> human_number(123456789, 4)
        "123.5M"
        >>> human_number(1201.56, None)
        "1.20156K"
        >>> human_number(12023, 2, suffixes=("", " thousand"))
        "12 thousand"
        >>> human_number(38000, strip_trailing_zeroes=False)
        "38.0K"
    """
    if not suffixes:
        raise ValueError("suffixes cannot be an empty sequence.")

    if sigfigs is not None:
        if sigfigs <= 0:
            raise ValueError(f"invalid sigfigs {sigfigs} (must be > 0)")

        if number != 0:
            number = round(number, sigfigs - 1 - math.floor(math.log10(abs(number))))

    magnitude = 0

    if (absolute := abs(number)) >= 1000:
        magnitude = min(len(suffixes) - 1, int(math.log10(absolute) / 3))
        number /= 1000**magnitude

    # Normal float numbers in Python generally do not have
    # trailing zeroes unless it's something like e.g. 1.0.
    if strip_trailing_zeroes and isinstance(number, float) and number.is_integer():
        return str(number).rstrip("0").rstrip(".") + suffixes[magnitude]

    return f"{number}{suffixes[magnitude]}"


@overload
def measure_performance(func: AsyncFunc[_P, _R]) -> AsyncFunc[_P, Tuple[_R, float]]:
    ...


@overload
def measure_performance(func: Callable[_P, _R]) -> Callable[_P, Tuple[_R, float]]:
    ...


def measure_performance(
    func: Union[Callable[_P, _R], AsyncFunc[_P, _R]]
) -> Union[Callable[_P, Tuple[_R, float]], AsyncFunc[_P, Tuple[_R, float]]]:
    """A decorator that returns a function or coroutine's
    execution time in milliseconds.

    .. versionadded:: 3.0

    Example
    -------
    .. code-block:: python3

        @measure_performance
        def foo():
            ...

        # later...

        result, delta = foo()


        # with a coroutine:

        @measure_performance
        async def foo():
            ...

        # later...

        result, delta = await foo()
    """
    # The asyncio method is used so @asyncio.coroutine decorated
    # functions actually work. I doubt anyone still uses them in
    # however since they've been deprecated since Python 3.8.
    # Maybe this can be switched to use inspect instead at some
    # point in the future.
    if iscoroutinefunction(func):

        @wraps(func)
        async def async_deco(*args: _P.args, **kwargs: _P.kwargs) -> Tuple[_R, float]:
            start = time.perf_counter()
            result = await func(*args, **kwargs)
            return result, (time.perf_counter() - start) * 1000

        return async_deco
    else:
        func = cast("Callable[_P, _R]", func)

        @wraps(func)
        def deco(*args: _P.args, **kwargs: _P.kwargs) -> Tuple[_R, float]:
            start = time.perf_counter()
            result = func(*args, **kwargs)
            return result, (time.perf_counter() - start) * 1000

        return deco


def progress_bar(*, progress: int, maximum: int, per: int = 1) -> str:
    """Constructs a progress bar.

    .. versionadded:: 2.0

    .. versionchanged:: 3.0

        * Re-ordered the arguments to ``progress``, ``maximum``,
        and ``per``.
        * Raise :exc:`ValueError` if any of the following apply:

            * ``maximum`` is negative or 0.
            * ``per`` is negative, 0, or greater than ``maximum``.
            * ``progress`` is less than maximum.

    Parameters
    ----------
    progress: :class:`float`
        The value the progress bar is currently at.

        .. versionchanged:: 3.0
            This is now a keyword-only argument.
    maximum: :class:`int`
        The maximum value of the progress bar.

        .. versionchanged:: 3.0
            This is now a keyword-only argument.
    per: :class:`int`
        The value of each portion of the progress bar.
        Defaults to ``1``.

        .. versionchanged:: 3.0
            This is now a keyword-only argument.

    Returns
    -------
    :class:`str`
        The constructed progress bar.

    Raises
    ------
    ValueError
        An invalid ``per``, ``maximum``, or ``progress``
        value was given.
    """
    if maximum <= 0:
        raise ValueError(f"invalid maximum {maximum} (must be > 0)")

    if per > maximum or per <= 0:
        raise ValueError(f"invalid per {per} (must be > 0 and < `maximum` value)")

    if progress > maximum:
        raise ValueError(f"invalid progress {progress} (must be < `maximum` value)")

    total = maximum // per
    filled = int(progress // per)

    # Have to subtract in these cases to account for the
    # the edge pieces, since we're doing the simple-but-
    # not-so-simple approach of calculating the body.

    FR = "<:pb_r_f:786093987336421376>"
    EL = "<:pb_l_e:786093986745942037>"
    FB = "<:pb_b_f:786093986703605830>"
    EB = "<:pb_b_e:786093986233188363>"

    if filled == total:
        FL = "<:pb_l_f:786093987076374548>"
        return FR + FB * (total - 2) + FL

    if filled == 0:
        ER = "<:pb_r_e:786093986838347836>"
        return ER + EB * (total - 2) + EL

    return FR + FB * (filled - 1) + EB * (total - filled - 1) + EL


def randint(a: int, b: int, *, seed: Optional[Any] = None) -> int:
    """Similar to :func:`random.randint` except allows for setting a
    seed without having to create a :class:`random.Random` instance
    or modify the global one.

    .. versionadded:: 3.1.8

    Parameters
    ----------
    a: :class:`int`
        The lower limit of the range.

        .. versionchanged:: 3.3
            This is no longer a positional-only argument.
    b: :class:`int`
        The upper limit of the range.

        .. versionchanged:: 3.3
            This is no longer a positional-only argument.
    seed: Optional[Any]
        The seed for randomisation.

    Returns
    -------
    :class:`int`
        The randomly generated integer.
    """
    return random.Random(seed).randint(a, b)


def tchart(
    items: Mapping[Any, Any], /, keys_formatter: Optional[Callable[[Any], str]] = None
) -> str:
    """Renders a T-Chart.

    .. versionadded:: 1.13.3

    .. versionchanged:: 3.0

        * Function now takes only mapping objects.
        * Empty mappings are now allowed.

    Parameters
    ----------
    items: :class:`Mapping`
        The items to form into a T-Chart.

        .. versionchanged:: 3.0
            This is now a positional-only argument.
    keys_formatter: Optional[Callable[[Any], :class:`str`]]
        A function that returns a string-like result.
        This is used to format the left hand column values.

        .. versionadded:: 3.0

    Returns
    -------
    :class:`str`
        The rendered T-Chart.
    """
    if not items:
        return ""

    if keys_formatter is None:
        keys_formatter = str

    width = len(max(map(keys_formatter, items), key=len))

    return "\n".join(f"{keys_formatter(k):<{width}} | {v}" for k, v in items.items())


def truncate(text: str, width: int, *, placeholder: str = "...") -> str:
    """Truncates a long string to the given width.

    If the string does not exceed the given width,
    then the string is returned as is. Otherwise,
    enough characters are truncated so that both
    the output text and the ``placeholder`` fit
    within the given width.

    .. versionadded:: 1.6

    .. versionchanged:: 1.13.1
        Changed suffix to ``".."``.

    .. versionchanged:: 1.14

        * Allow specification of a placeholder.
        * Fixed truncation process.

    .. versionchanged:: 3.0

        * Renamed ``max_width`` parameter to ``width``.
        * Raise :exc:`ValueError` if ``width`` is less
          than the length of the placeholder.

    Parameters
    ----------
    text: :class:`str`
        The string to truncate.

        .. versionchanged:: 3.0
            This is now a positional-only argument.

        .. versionchanged:: 3.3
            This is no longer a positional-only argument.
    width: :class:`int`
        The maximum length of the string.
    placeholder: :class:`str`
        String that will appear at the end of the
        output text if it has been truncated.
        Defaults to ``"..."``.

    Returns
    -------
    :class:`str`
        The truncated string.

    Raises
    ------
    ValueError
        An invalid ``width`` was given.

    Examples
    --------
    .. testsetup::
        from sleepy.utils import truncate

    .. doctest::
        >>> truncate("This is an extremely long sentence.", 20)
        "This is an extremely..."
        >>> truncate("This is also an extremely long sentence.", 16, placeholder=" [...]")
        "This is also an [...]"
    """
    placeholder_length = len(placeholder)

    if placeholder_length > width:
        raise ValueError("placeholder is too large for maximum width.")

    if len(text) < width:
        return text

    return text[: width - placeholder_length].rstrip() + placeholder
