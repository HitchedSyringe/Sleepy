"""
Copyright (c) 2018-present HitchedSyringe

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""


import inspect
from datetime import datetime
from typing import Any, Dict, Optional, Sequence, Tuple

import pytest

from sleepy.utils import *


def _as_signature(*args: Any, **kwargs: Any) -> Tuple[Tuple[Any, ...], Dict[str, Any]]:
    return args, kwargs


@pytest.mark.parametrize(
    ("value", "value_format_spec", "format_spec", "expected"),
    [
        # No pipe separator in format spec (assume -s plural form).
        (0.375, None, "metre", "0.375 metres"),
        (0.375, ".2f", "metre", "0.38 metres"),
        (1, None, "metre", "1 metre"),
        (2, None, "metre", "2 metres"),
        # Using pipe separator in format spec (assume specified plural form).
        (0.375, None, "foot|feet", "0.375 feet"),
        (0.375, ".2f", "foot|feet", "0.38 feet"),
        (1, None, "foot|feet", "1 foot"),
        (2, None, "foot|feet", "2 feet"),
    ],
)
def test_plural(
    value: float, value_format_spec: str, format_spec: str, expected: str
) -> None:
    assert format(plural(value, value_format_spec), format_spec) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, "<:slash:821284209763024896>"),
        (True, "<:check:821284209401921557>"),
        (False, "<:x_:821284209792516096>"),
    ],
)
def test_bool_to_emoji(value: Optional[Any], expected: str) -> None:
    assert bool_to_emoji(value) == expected


@pytest.mark.parametrize(
    ("dt1", "dt2", "expected"),
    [
        (datetime(2022, 4, 20), datetime(2022, 4, 20), "Just now"),
        (datetime(2022, 4, 20), datetime(2022, 4, 20, 1, 0, 0), "1 hour ago"),
        (datetime(2022, 4, 20, 1, 0, 0), datetime(2022, 4, 20), "In 1 hour"),
        (datetime(2019, 4, 6), datetime(2022, 4, 20), "3 years and 2 weeks ago"),
        (datetime(2022, 4, 20), datetime(2019, 4, 6), "In 3 years and 2 weeks"),
        (datetime(2019, 4, 5), datetime(2022, 4, 20), "3 years, 2 weeks, and 1 day ago"),
        (datetime(2022, 4, 20), datetime(2019, 4, 5), "In 3 years, 2 weeks, and 1 day"),
    ],
)
def test_human_delta_not_brief_and_not_absolute(
    dt1: datetime, dt2: datetime, expected: str
) -> None:
    assert human_delta(dt1, dt2) == expected


@pytest.mark.parametrize(
    ("dt1", "dt2", "expected"),
    [
        (datetime(2022, 4, 20), datetime(2022, 4, 20), "Just now"),
        (datetime(2019, 4, 5), datetime(2022, 4, 20), "3 years ago"),
        (datetime(2022, 4, 20), datetime(2019, 4, 5), "In 3 years"),
    ],
)
def test_human_delta_brief_and_not_absolute(
    dt1: datetime, dt2: datetime, expected: str
) -> None:
    assert human_delta(dt1, dt2, brief=True) == expected


@pytest.mark.parametrize(
    ("dt1", "dt2", "expected"),
    [
        (datetime(2022, 4, 20), datetime(2022, 4, 20), "Just now"),
        (datetime(2019, 4, 6), datetime(2022, 4, 20), "3 years and 2 weeks"),
        (datetime(2022, 4, 20), datetime(2019, 4, 6), "3 years and 2 weeks"),
        (datetime(2019, 4, 5), datetime(2022, 4, 20), "3 years, 2 weeks, and 1 day"),
        (datetime(2022, 4, 20), datetime(2019, 4, 5), "3 years, 2 weeks, and 1 day"),
    ],
)
def test_human_delta_not_brief_and_absolute(
    dt1: datetime, dt2: datetime, expected: str
) -> None:
    assert human_delta(dt1, dt2, absolute=True) == expected


@pytest.mark.parametrize(
    ("dt1", "dt2", "expected"),
    [
        (datetime(2022, 4, 20), datetime(2022, 4, 20), "Just now"),
        (datetime(2019, 4, 5), datetime(2022, 4, 20), "3 years"),
        (datetime(2022, 4, 20), datetime(2019, 4, 5), "3 years"),
    ],
)
def test_human_delta_brief_and_absolute(
    dt1: datetime, dt2: datetime, expected: str
) -> None:
    assert human_delta(dt1, dt2, brief=True, absolute=True) == expected


@pytest.mark.parametrize(
    ("sequence", "joiner", "expected"),
    [
        # Default joiner
        ([], "and", ""),
        ([1], "and", "1"),
        ([1, 2], "and", "1 and 2"),
        ([1, 2, 3], "and", "1, 2, and 3"),
        # Passed joiner
        ([], "or", ""),
        ([4], "or", "4"),
        ([4, 5], "or", "4 or 5"),
        ([4, 5, 6], "or", "4, 5, or 6"),
    ],
)
def test_human_join(sequence: Sequence[Any], joiner: str, expected: str) -> None:
    assert human_join(sequence, joiner=joiner) == expected


@pytest.mark.parametrize(
    ("number", "sigfigs", "expected"),
    [
        # Default sigfigs value.
        (100, 3, "100\u200b"),
        (1000, 3, "1K"),
        (12400, 3, "12.4K"),
        (12490, 3, "12.5K"),
        (-12400, 3, "-12.4K"),
        (-12490, 3, "-12.5K"),
        (999999, 3, "1M"),
        (1000000, 3, "1M"),
        (-999999, 3, "-1M"),
        (-1000000, 3, "-1M"),
        # Passed sigfigs value.
        (127, 2, "130\u200b"),
        (-127, 2, "-130\u200b"),
        (12700, 2, "13K"),
        (-12700, 2, "-13K"),
        (1235000, 5, "1.235M"),
        (-1235000, 5, "-1.235M"),
    ],
)
def test_human_number_strip_trailing_zeroes(
    number: float,
    sigfigs: Optional[int],
    expected: str,
) -> None:
    assert human_number(number, sigfigs=sigfigs) == expected


@pytest.mark.parametrize(
    ("number", "sigfigs", "expected"),
    [
        # Default sigfigs value.
        (100, 3, "100\u200b"),
        (1000, 3, "1.00K"),
        (12400, 3, "12.4K"),
        (12490, 3, "12.5K"),
        (-12400, 3, "-12.4K"),
        (-12490, 3, "-12.5K"),
        (999999, 3, "1.00M"),
        (1000000, 3, "1.00M"),
        (-999999, 3, "-1.00M"),
        (-1000000, 3, "-1.00M"),
        # Passed sigfigs value.
        (127, 2, "130\u200b"),
        (-127, 2, "-130\u200b"),
        (12700, 2, "13K"),
        (-12700, 2, "-13K"),
        (1235000, 5, "1.2350M"),
        (-1235000, 5, "-1.2350M"),
    ],
)
def test_human_number_not_strip_trailing_zeroes(
    number: float,
    sigfigs: Optional[int],
    expected: str,
) -> None:
    assert human_number(number, sigfigs=sigfigs, strip_trailing_zeroes=False) == expected


@pytest.mark.parametrize(
    ("number", "sigfigs", "suffixes"),
    [
        # Empty suffixes sequence.
        (1234, 3, ""),
        (1234, 3, ()),
        (1234, 3, []),
        # Zero or negative sigfigs value.
        (1234, 0, "\u200bKMBTPEZY"),
        (1234, -1, "\u200bKMBTPEZY"),
    ],
)
def test_human_number_failures(
    number: float, sigfigs: Optional[int], suffixes: Sequence[str]
) -> None:
    with pytest.raises(ValueError):
        human_number(number, sigfigs=sigfigs, suffixes=suffixes)


@pytest.mark.parametrize(
    ("args", "kwargs", "expected"),
    [
        (*_as_signature(1, 2, c=3), (1, 2, 3)),
        (*_as_signature(4, c=5), (4, None, 5)),
        (*_as_signature(a=6, b=7, c=8), (6, 7, 8)),
    ],
)
def test_measure_performance_sync(
    args: Any, kwargs: Any, expected: Tuple[Any, Any, Any]
) -> None:
    def sync_test(a: Any, b: Optional[Any] = None, *, c: Any) -> Tuple[Any, Any, Any]:
        return a, b, c

    sync_wrap = measure_performance(sync_test)

    @measure_performance
    def sync_deco(a: Any, b: Optional[Any] = None, *, c: Any) -> Tuple[Any, Any, Any]:
        return a, b, c

    assert inspect.signature(sync_test) == inspect.signature(sync_wrap)
    assert inspect.signature(sync_test) == inspect.signature(sync_deco)

    assert sync_deco(*args, **kwargs)[0] == expected
    assert sync_wrap(*args, **kwargs)[0] == expected


@pytest.mark.parametrize(
    ("args", "kwargs", "expected"),
    [
        (*_as_signature(1, 2, c=3), (1, 2, 3)),
        (*_as_signature(4, c=5), (4, None, 5)),
        (*_as_signature(a=6, b=7, c=8), (6, 7, 8)),
    ],
)
@pytest.mark.asyncio
async def test_measure_performance_async(
    args: Any, kwargs: Any, expected: Tuple[Any, Any, Any]
) -> None:
    async def async_test(
        a: Any, b: Optional[Any] = None, *, c: Any
    ) -> Tuple[Any, Any, Any]:
        return a, b, c

    async_wrap = measure_performance(async_test)

    @measure_performance
    async def async_deco(
        a: Any, b: Optional[Any] = None, *, c: Any
    ) -> Tuple[Any, Any, Any]:
        return a, b, c

    assert inspect.signature(async_test) == inspect.signature(async_wrap)
    assert inspect.signature(async_test) == inspect.signature(async_deco)

    assert (await async_wrap(*args, **kwargs))[0] == expected
    assert (await async_deco(*args, **kwargs))[0] == expected


@pytest.mark.parametrize(
    ("text", "width", "placeholder", "expected"),
    [
        ("This is a long sentence.", 10, "...", "This is..."),
        ("This is a long sentence.", 20, "...", "This is a long se..."),
        ("This is a long sentence.", 30, "...", "This is a long sentence."),
        ("This is a long sentence.", 10, " [...]", "This [...]"),
    ],
)
def test_truncate(text: str, width: int, placeholder: str, expected: str) -> None:
    assert expected == truncate(text, width, placeholder=placeholder)


@pytest.mark.parametrize(
    ("text", "width", "placeholder"),
    [
        # Width value is less than placeholder length.
        ("This is a long sentence.", 2, "..."),
        # Zero or negative width value.
        ("This is a long sentence.", 0, "..."),
        ("This is a long sentence.", -1, "..."),
    ],
)
def test_truncate_failures(text: str, width: int, placeholder: str) -> None:
    with pytest.raises(ValueError):
        truncate(text, width, placeholder=placeholder)
