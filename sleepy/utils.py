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
from datetime import datetime, timedelta
from functools import partial, wraps
from inspect import isawaitable
from pathlib import Path


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

    This wraps the function in a :class:`asyncio.Future`
    via :meth:`loop.run_in_executor`.

    .. versionadded:: 3.0

    Example
    -------
    .. code-block::

        @awaitable
        def blocking_sync_func():
            ...

        # later...

        await blocking_sync_func()
    """
    loop = asyncio.get_event_loop()

    @wraps(func)
    def decorator(*args, **kwargs):
        return loop.run_in_executor(None, partial(func, *args, **kwargs))

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


def human_delta(delta, /, *, brief=False, absolute=False):
    """Humanizes a given delta.

    .. versionadded:: 1.9

    .. versionchanged:: 3.0

        * Renamed to ``human_delta``.
        * Renamed ``duration`` argument to ``delta``.
        * Return ``"Just now"`` if the delta is 0, otherwise,
          indicate if the delta is negative or positive in the
          returned string. This behaviour can be disabled via
          passing ``absolute=True``.

    Parameters
    ----------
    delta: Union[:class:`datetime.timedelta`, :class:`float`]
        The delta to humanize (in seconds).

        .. versionchanged:: 3.0
            This is now a positional-only argument.
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
        >>> human_delta(datetime.datetime(2020, 1, 1) - datetime.datetime(2019, 1, 1))
        "1 year ago"
        >>> human_delta(-3630.13)
        "In 1 hour and 30 seconds"
        >>> human_delta(70694)
        "19 hours, 38 minutes, and 14 seconds ago"
        >>> human_delta(-3780, indicate_tense=False)
        "1 hour and 3 minutes"
    """
    if isinstance(delta, timedelta):
        delta -= timedelta(microseconds=delta.microseconds)
        delta = int(delta.total_seconds())
    else:
        delta = round(delta)

    if delta == 0:
        return "Just now"

    # Seconds to years/months values are estimates.
    years, seconds = divmod(abs(delta), 31536000)
    months, seconds = divmod(seconds, 2404800)
    weeks, seconds = divmod(seconds, 604800)
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)

    difference = []

    if years > 0:
        difference.append(f"{plural(years, ',d'):year}")
    if months > 0:
        difference.append(f"{plural(months):month}")
    if weeks > 0:
        difference.append(f"{plural(weeks):week}")
    if days > 0:
        difference.append(f"{plural(days):day}")
    if hours > 0:
        difference.append(f"{plural(hours):hour}")
    if minutes > 0:
        difference.append(f"{plural(minutes):minute}")
    if seconds > 0:
        difference.append(f"{plural(seconds):second}")

    humanised = difference[0] if brief else human_join(difference)

    if absolute:
        return humanised

    if delta < 0:
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
        "1.20K"
        >>> human_number(-543210)
        "-543K"
        >>> human_number(123456789, 4)
        "123.5M"
        >>> human_number(38000, 2, remove_trailing_zeroes=True)
        "38K"
        >>> human_number(12023, 2, suffixes=("", " thousand"))
        "12 thousand"
    """
    if not suffixes:
        raise ValueError("suffixes cannot be an empty sequence.")

    ordinal = 0

    if number != 0:
        while abs(number) >= 1000 and ordinal < len(suffixes):
            number /= 1000
            ordinal += 1

        number = round(
            number,
            (sigfigs - 1) - math.floor(math.log10(abs(number)))
        )

    if strip_trailing_zeroes:
        number = str(number).rstrip("0").rstrip(".")

    return f"{number}{suffixes[ordinal]}"


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
    # The reason I don't use a proper if-else here
    # is because, for some dumb reason (that I am
    # probably unaware of), Python keeps returning
    # the else result regardless of what type the
    # function actually is.

    # I'm using `asyncio.iscoroutinefunction` instead of
    # `inspect.iscoroutinefunction` here in case someone
    # out there, for whatever reason, decides to use this
    # with a function decorated with `asyncio.coroutine`.
    # I highly doubt that anyone out there still uses the
    # decorator given that it has been deprecated since
    # Python 3.8.
    if asyncio.iscoroutinefunction(func) or isawaitable(func):

        @wraps(func)
        async def decorator(*args, **kwargs):
            start = time.perf_counter()
            result = await func(*args, **kwargs)
            return result, (time.perf_counter() - start) * 1000

        return decorator

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
        return _FR + (_FB * (total - 2)) + _FL

    if filled == 0:
        return _ER + (_EB * (total - 2)) + _EL

    return _FR + (_FB * (filled - 1)) + (_EB * (total - filled - 1)) + _EL


def tchart(items, /, formatter=None):
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
    formatter: Optional[Callable[[Any], :class:`str`]]
        A function that returns a string-like result.

        .. versionadded:: 3.0

    Returns
    -------
    :class:`str`
        The rendered T-Chart.
    """
    if not items:
        return ""

    if formatter is None:
        formatter = str

    width = len(max(map(formatter, items), key=len))

    return "\n".join(f"{formatter(k):<{width}} | {v}" for k, v in items.items())


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
