"""
© Copyright 2018-2020 HitchedSyringe, All Rights Reserved.

Redistributing, using or owning a copy of this software without explicit permissions
is against these licensing terms, your license(s) to this software can be revoked at
any time without explicit notice beforehand and at the time of revocation.
Your license is non-transferrable, the terms of this license only permit you to do the
following; Create pull requests and make modifications to this repository.

"""


__all__ = (
    "plural",
    "tchart",
    "simple_shorten",
    "parse_duration",
    "millify",
    "progress_bar",
    "humanise_sequence",
)


import datetime
import math
from decimal import Decimal
from typing import Sequence


class plural:
    """Helper class that allows for pluralising strings based on amount.

    Attributes
    ----------
    value: Union[:class:`float`, :class:`int`]
        The value to use for pluralisation.

    Examples
    --------
    .. testsetup::
        from utils.formatting import Plural
    .. doctest::
        >>> dogs = 7
        >>> print(f"I see {plural(dogs):dog}!")
        "I see 7 dogs!"
        >>> dogs = 1
        >>> print(f"Now there's only {plural(dogs):dog}...")
        "Now there's only 1 dog..."

        >>> geese = 5
        >>> print(f"There are {plural(geese):goose|geese} on the lake.")
        "There are 5 geese on the lake."
        >>> geese = 1
        >>> print(f"There is only {plural(geese):goose|geese} on the lake.")
        "There is only 1 goose on the lake."
    """

    __slots__ = ("value",)


    def __init__(self, value):
        self.value = value


    def __format__(self, format_spec):
        singular, _, plural = format_spec.partition("|")
        if abs(self.value) != 1:
            return f"{self.value} {plural or f'{singular}s'}"
        return f"{self.value} {singular}"


def tchart(items) -> str:
    """Renders a T-Chart using a series of key-values.
    Example:
    Dominique | 29
    Penelope  | 20
    Samuel    | 19
    Josephine | 12
    Sammy     | 10
    Bill      | 5

    Parameters
    ----------
    items: Iterable[Tuple[Any, Any]]
        An iterable of key-values.

    Returns
    -------
    :class:`str`
        The rendered T-Chart.
    """
    # Keys have to be strings.
    items = {str(k): v for k, v in items}

    width = len(max(items, key=len))
    return "\n".join(f"{k:<{width}} | {v}" for k, v in items.items())


def simple_shorten(text: str, max_width: int, *, placeholder: str = "..") -> str:
    """Shortens a string to a maximum width.
    If the string does not exceed the maximum width, the string is returned as is.

    .. note::

        The placeholder is considered when truncating and replaces the last
        x amount of characters at the end of the string.

    Parameters
    ----------
    text: :class:`str`
        The string to ensure stays a certain width.
    max_width: :class:`int`
        How many characters to ensure the string stays.
    *, placeholder: :class:`str`
        String that will appear at the end of the output text if it has been truncated.
        Defaults to ``..``.

    Returns
    -------
    :class:`str`
        The shortened string.

    Examples
    --------
    .. testsetup::
        from utils.formatting import simple_shorten
    .. doctest::
        >>> simple_shorten("The quick brown fox jumps over the lazy dog.", 20)
        "The quick brown fo.."
        >>> simple_shorten("The quick brown fox jumps over the lazy dog.", 15, placeholder="...")
        "The quick br..."
    """
    return (text[:max_width - len(placeholder)] + placeholder) if len(text) > max_width else text


def parse_duration(duration, *, brief: bool = False) -> str:
    """Parses a duration (in seconds) into a human-readable string.

    Parameters
    ----------
    duration: Union[:class:`datetime.timedelta`, :class:`int`, :class:`float`]
        The duration to parse.
    *, brief: :class:`bool`
        Whether or not to return the first component only of the parsed duration.
        Defaults to ``False``.

    Returns
    -------
    :class:`str`
        The parsed, human-readable duration string.

    Examples
    --------
    .. testsetup::
        from utils.formatting import parse_duration
    .. doctest::
        >>> parse_duration(datetime.datetime(year=2020) - datetime.datetime(year=2019))
        "1 year"
        >>> parse_duration(3630.13)
        "1 hour, 31 seconds"
        >>> parse_duration(68630, brief=True)
        "19 hours"
    """
    # handle a timedelta case.
    if isinstance(duration, datetime.timedelta):
        duration = duration.total_seconds()

    minutes, seconds = divmod(duration, 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    weeks, days = divmod(days, 7)
    # Estimate i'm using for weeks in a month is found here: https://www.mathsisfun.com/measure/weeks.html
    # This isn't exactly the most accurate.
    months, weeks = divmod(weeks, 13 / 3)
    years, months = divmod(months, 12)

    # Need to round these since we used a float.
    weeks = round(weeks)
    seconds = round(seconds)

    # Convert everything but seconds to an int. to drop the trailing zeroes.
    diff = []
    if years > 0:
        diff.append(f"{plural(int(years)):year}")
    if months > 0:
        diff.append(f"{plural(int(months)):month}")
    if weeks > 0:
        diff.append(f"{plural(int(weeks)):week}")
    if days > 0:
        diff.append(f"{plural(int(days)):day}")
    if hours > 0:
        diff.append(f"{plural(int(hours)):hour}")
    if minutes > 0:
        diff.append(f"{plural(int(minutes)):minute}")
    if seconds > 0:
        diff.append(f"{plural(seconds):second}")

    if not brief:
        # Just return "0 seconds" if our duration is/around 0 seconds.
        return ", ".join(diff) or "0 seconds"
    return diff[0] if diff else "0 seconds"


def millify(number, precision: int = 0, remove_trailing_zeroes: bool = True,
            suffixes: list = ['', 'K', 'M', 'B', 'T', 'P', 'E', 'Z', 'Y']) -> str:
    """Millifies a long number to the given precision. (i.e 100,000 -> 100K)
    This shortens numbers using a base 10 scale and can also be used with negative numbers.

    Parameters
    ----------
    number: Union[:class:`int`, :class:`float`]
        The number to millify.
    precision: :class:`int`
        The number of decimals to round to (if any).
        Defaults to ``0``.
    remove_trailing_zeroes: :class:`bool`
        Whether or not to remove trailing zeroes.
        Defaults to ``True``.
    suffixes: List[:class:`str`]
        A list of :class:`str` representing the suffixes to use for each power of 10.
        The order of the list is in ascending order.
        Defaults to ``['', 'K', 'M', 'B', 'T', 'P', 'E', 'Z', 'Y']``.

    Returns
    -------
    :class:`str`
        The millified, human-readable number string.

    Examples
    --------
    .. testsetup::
        from utils.formatting import millify
    .. doctest::
        >>> millify(123456, 2)
        "123.46K"
        >>> millify(123456789, 2)
        "123.5M"
    """
    # Gets the magnitude & index for the abbreviation suffix.
    # We fit the max to the amount of suffixes in order to prevent IndexErrors.
    magnitude = max(0, min(len(suffixes) - 1,
                           int(math.floor(0 if number == 0 else math.log10(abs(number)) // 3))))
    number = round(number / 1000**magnitude, precision)  # Shortens our number.
    if remove_trailing_zeroes:
        # Decimal is weird and reverses our round operation.
        # To prevent this, we have to pass number in as a string.
        decimal = Decimal(str(number))
        number = decimal.quantize(Decimal(1)) if decimal == decimal.to_integral() else decimal.normalize()
    return f"{number}{suffixes[magnitude]}"


# The progress bar emojis.
_EMPTY_RIGHT = "<:pb_r_e:715774890682089563>"
_EMPTY_LEFT = "<:pb_l_e:715774890266984531>"
_EMPTY_CENTRE = "<:pb_b_e:715774890246144041>"
_FULL_RIGHT = "<:pb_r_f:715774890548002867>"
_FULL_LEFT = "<:pb_l_f:715774890577231902>"
_FULL_CENTRE = "<:pb_b_f:715774890279436289>"

def progress_bar(maximum: int, per: int, progress: int) -> str:
    """Constructs a progress bar.

    Parameters
    ----------
    maximum: :class:`int`
        The maximum value of the progress bar.
    per: :class:`int`
        The value each "portion" of the progress bar represents.
    progress: :class:`int`
        The value the progress bar is currently at.

    Returns
    -------
    :class:`str`
        The constructed progress bar.

    Raises
    ------
    :exc:`ValueError`
        Either ``per`` was set to a value equal to zero or greater than ``maximum``
        or ``progress`` was greater than ``maximum``.
    """
    if per > maximum or per == 0:
        raise ValueError("per cannot be a value equal to zero or greater than maximum.")

    if progress > maximum:
        raise ValueError("progress cannot be greater than maximum.")

    total = maximum // per
    filled = progress // per

    if filled == total:
        return _FULL_RIGHT + (_FULL_CENTRE * total) + _FULL_LEFT

    if filled == 0:
        return _EMPTY_RIGHT + (_EMPTY_CENTRE * total) + _EMPTY_LEFT

    # We have to add 1 to filled and subtract 1 from empty in order to have a proper, almost-filled bar.
    empty = (total - filled) - 1
    return _FULL_RIGHT + (_FULL_CENTRE * (filled + 1)) + (_EMPTY_CENTRE * empty) + _EMPTY_LEFT


def humanise_sequence(sequence, *, joiner: str = "and") -> str:
    """Gets a human-readable, comma-separted list, with the last element joined with a given joiner.
    If only one item is in the sequence, then that single item is returned instead.

    This uses an Oxford comma, because without one, the output would be difficult to interpret.

    Parameters
    ----------
    sequence: Sequence[:class:`str`]
        The sequence of items to join.
    joiner: :class:`str`
        The joiner that joins the last item of the sequence with the rest of the sequence.
        Defaults to ``and``.

    Returns
    -------
    :class:`str`
        The human-readable list.

    Raises
    ------
    :exc:`ValueError`
        The sequence passed is empty.
    """
    if not sequence:
        raise ValueError("Sequence cannot be empty.")

    if len(sequence) == 1:
        return sequence[0]

    return ", ".join(sequence[:-1]) + f" {joiner} {sequence[-1]}"
