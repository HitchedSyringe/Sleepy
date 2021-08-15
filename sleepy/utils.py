"""
Copyright (c) 2018-present HitchedSyringe

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""


__all__ = (
    "plural",
    "awaitable",
    "bool_to_emoji",
    "find_extensions_in",
    "human_delta",
    "human_join",
    "human_number",
    "human_timestamp",
    "measure_performance",
    "progress_bar",
    "tchart",
    "truncate",
)


import asyncio
import math
import time
from datetime import datetime
from functools import partial, wraps
from pathlib import Path

from dateutil.relativedelta import relativedelta


_DEFAULT_SHORT_NUMBER_SUFFIXES = (
    "",
    "K",
    "M",
    "B",
    "T",
    "P",
    "E",
    "Z",
    "Y",
)


# Emojis used for the progress bar.
_FR = "<:pb_r_f:786093987336421376>"
_ER = "<:pb_r_e:786093986838347836>"
_FL = "<:pb_l_f:786093987076374548>"
_EL = "<:pb_l_e:786093986745942037>"
_FB = "<:pb_b_f:786093986703605830>"
_EB = "<:pb_b_e:786093986233188363>"


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

    __slots__ = ("__value", "__value_fmt")

    def __init__(self, value, /, value_format_spec=None):
        if not isinstance(value, (int, float)):
            raise TypeError(f"Expected value to be int or float, not {type(value)!r}.")

        self.__value = value
        self.__value_fmt = value_format_spec or ""

    def __format__(self, spec):
        singular, _, plural = spec.partition("|")
        value = self.__value

        if abs(value) == 1:
            return f"{value:{self.__value_fmt}} {singular}"

        return f"{value:{self.__value_fmt}} {plural or singular + 's'}"


def awaitable(func):
    """A decorator that transforms a sync function into
    an awaitable function.

    .. versionadded:: 3.0

    .. versionchanged:: 3.1
        This now returns a coroutine instead of a
        :class:`asyncio.Future`.

    Example
    -------
    .. code-block::

        @awaitable
        def blocking_sync_func():
            ...

        # later...

        await blocking_sync_func()
    """

    @wraps(func)
    async def decorator(*args, **kwargs):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, partial(func, *args, **kwargs))

    return decorator


def bool_to_emoji(value):
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


def find_extensions_in(path):
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


def human_delta(datetime1, datetime2=None, /, *, brief=False, absolute=False):
    """Humanizes the delta between two given datetimes.

    .. versionadded:: 1.9

    .. versionchanged:: 3.0

        * Renamed to ``human_delta``.
        * Renamed ``duration`` argument to ``delta``.
        * Return ``"Just now"`` if the delta is 0, otherwise,
          indicate if the delta is negative or positive in the
          returned string. This behaviour can be disabled via
          passing ``absolute=True``.

    .. versionchanged:: 3.1
        Replaced ``delta`` argument with the ``datetime1``
        and ``datetime2`` arguments.

    Parameters
    ----------
    datetime1: :class:`datetime.datetime`
    datetime2: Optional[:class:`datetime.datetime`]
        The datetimes to humanize the delta of.
        The second datetime will default to the value of
        :meth:`datetime.datetime.utcnow` if not given.
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
    """
    datetime1 = datetime1.replace(microsecond=0)

    if datetime2 is None:
        datetime2 = datetime.utcnow()

    datetime2 = datetime2.replace(microsecond=0)

    if datetime1 == datetime2:
        return "Just now"

    delta = abs(relativedelta(datetime1, datetime2))

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

    if datetime1 > datetime2:
        return "In " + humanised

    return humanised + " ago"


def human_join(sequence, /, *, joiner="and"):
    """Returns a human-readable, comma-separted sequence,
    with the last element joined with a given joiner.

    This uses an Oxford comma, because without one, the
    output would be difficult to interpret.

    .. versionadded:: 1.6

    .. versionchanged:: 2.0

        * Renamed to ``humanise_sequence``.
        * Raise :exc:`ValueError` if the given sequence
          is empty.
        * Processed strings now use an Oxford comma.

    .. versionchanged:: 3.0

        * Renamed to ``human_join``.
        * Passing empty sequences will now return an empty
          string.
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
        return sequence[0]

    if sequence_size == 2:
        return f"{sequence[0]} {joiner} {sequence[1]}"

    return ", ".join(map(str, sequence[:-1])) + f", {joiner} {sequence[-1]}"


def human_number(
    number,
    /,
    sigfigs=3,
    *,
    strip_trailing_zeroes=True,
    suffixes=_DEFAULT_SHORT_NUMBER_SUFFIXES
):
    """Humanizes a given number.

    This shortens numbers using a base-1000 scale.

    .. versionadded:: 1.10

    .. versionchanged:: 3.0

        * Renamed to ``human_number``.
        * Renamed ``precision`` argument to ``sigfigs``.
        * Renamed ``remove_trailing_zeroes`` argument to
        ``strip_trailing_zeroes``.
        * Raise :exc:`ValueError` if ``suffixes`` is an empty sequence.

    Parameters
    ----------
    number: :class:`float`
        The number to humanize.

        .. versionchanged:: 3.0
            This is now a positional-only argument.
    sigfigs: :class:`int`
        The number of significant figures to round to.
        Defaults to ``3``.
    strip_trailing_zeroes: :class:`bool`
        Whether or not to strip trailing zeroes.
        Defaults to ``True``.

        .. versionchanged:: 3.0
            This is now a keyword-only argument.
    suffixes: Sequence[:class:`str`]
        The suffixes to use for each power of 1000.
        The order of the sequence is in ascending order.
        Defaults to ``("", "K", "M", "B", "T", "P", "E", "Z", "Y")``.

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
        >>> human_number(1201.56)
        "1.2K"
        >>> human_number(-543210)
        "-543K"
        >>> human_number(123456789, 4)
        "123.5M"
        >>> human_number(38000, 2, strip_trailing_zeroes=False)
        "38.0K"
        >>> human_number(12023, 2, suffixes=("", " thousand"))
        "12 thousand"
    """
    if not suffixes:
        raise ValueError("suffixes cannot be an empty sequence.")

    number = round(number, sigfigs - 1 - math.floor(math.log10(abs(number))))
    magnitude = 0

    if (absolute := abs(number)) >= 1000:
        magnitude = min(len(suffixes) - 1, int(math.log10(absolute) / 3))
        number /= 1000**magnitude

        if "." in number and strip_trailing_zeroes:
            number = str(number).rstrip("0").rstrip(".")

    return f"{number}{suffixes[magnitude]}"


def human_timestamp(timestamp, /, formatting=None):
    """Humanizes a given timestamp using Discord's new timestamp
    markdown.

    All formatted timestamps are locale-independent.

    +-------------+----------------------------+-----------------+
    |    Style    |       Example Output       |   Description   |
    +=============+============================+=================+
    | t           | 22:57                      | Short Time      |
    +-------------+----------------------------+-----------------+
    | T           | 22:57:58                   | Long Time       |
    +-------------+----------------------------+-----------------+
    | d           | 17/05/2016                 | Short Date      |
    +-------------+----------------------------+-----------------+
    | D           | 17 May 2016                | Long Date       |
    +-------------+----------------------------+-----------------+
    | f (default) | 17 May 2016 22:57          | Short Date Time |
    +-------------+----------------------------+-----------------+
    | F           | Tuesday, 17 May 2016 22:57 | Long Date Time  |
    +-------------+----------------------------+-----------------+
    | R           | 5 years ago                | Relative Time   |
    +-------------+----------------------------+-----------------+

    Note that the exact output depends on the user's locale setting
    in the client. The example output presented is using the ``en-GB``
    locale.

    .. versionadded:: 3.0

    Parameters
    ----------
    timestamp: Union[:class:`datetime.datetime`, :class:`float`]
        The timestamp to humanize.
    formatting: Optional[:class:`str`]
        How the timestamp should be formatted.

    Returns
    --------
    :class:`str`
        The formatted string.
    """
    if isinstance(timestamp, datetime):
        timestamp = timestamp.timestamp()

    if formatting is None:
        return f"<t:{int(timestamp)}>"

    return f"<t:{int(timestamp)}:{formatting}>"


def measure_performance(func):
    """A decorator that returns a function or coroutine's
    execution time in milliseconds.

    .. versionadded:: 3.0

    Example
    -------
    .. code-block::

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
    # I'm using `asyncio.iscoroutinefunction` instead of
    # `inspect.iscoroutinefunction` here in case someone
    # out there, for whatever reason, decides to use this
    # with a function decorated with `asyncio.coroutine`.
    # I highly doubt that anyone out there still uses the
    # decorator given that it has been deprecated since
    # Python 3.8.
    if asyncio.iscoroutinefunction(func):

        @wraps(func)
        async def decorator(*args, **kwargs):
            start = time.perf_counter()
            result = await func(*args, **kwargs)
            return result, (time.perf_counter() - start) * 1000

    else:

        @wraps(func)
        def decorator(*args, **kwargs):
            start = time.perf_counter()
            result = func(*args, **kwargs)
            return result, (time.perf_counter() - start) * 1000

    return decorator


def progress_bar(*, progress, maximum, per=1):
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

    if filled == total:
        return _FR + _FB * (total - 2) + _FL

    if filled == 0:
        return _ER + _EB * (total - 2) + _EL

    return _FR + _FB * (filled - 1) + _EB * (total - filled - 1) + _EL


def tchart(items, /, keys_formatter=None):
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


def truncate(text, /, width, *, placeholder="..."):
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

        * Renamed to ``truncate``.
        * Renamed ``max_width`` argument to ``width``.
        * Raise :exc:`ValueError` if ``width`` is less
          than the length of the placeholder.

    Parameters
    ----------
    text: :class:`str`
        The string to truncate.

        .. versionchanged:: 3.0
            This is now a positional-only argument.
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

    return text[:width - placeholder_length].rstrip() + placeholder
