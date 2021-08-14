from collections.abc import (
    Callable,
    Coroutine,
    Iterable,
    Mapping,
    Sequence,
)
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, overload
from typing_extensions import Literal


_AnyCallable = Callable[..., Any]
_AnyCoro = Coroutine[Any, Any, Any]
_DatetimeFormatStyle = Literal["f", "F", "d", "D", "t", "T", "R"]


class plural:

    def __init__(
        self,
        value: float,
        /,
        value_format_spec: Optional[str] = ...
    ) -> None: ...

    def __format__(self, spec: str) -> str: ...


def awaitable(func: _AnyCallable) -> _AnyCoro: ...


def bool_to_emoji(value: Optional[Any]) -> str: ...


def find_extensions_in(path: Path | str) -> Iterable[str]: ...


def human_delta(
    datetime1: datetime,
    datetime2: Optional[datetime] = ...,
    /,
    *,
    brief: bool = ...,
    absolute: bool = ...
) -> str: ...


def human_join(sequence: Sequence[Any], /, *, joiner: str = ...) -> str: ...


def human_number(
    number: float,
    /,
    sigfigs: int = ...,
    *,
    strip_trailing_zeroes: bool = ...,
    suffixes: Sequence[str] = ...
) -> str: ...


def human_timestamp(
    timestamp: datetime | float,
    /,
    formatting: Optional[_DatetimeFormatStyle] = ...
) -> str: ...


@overload
def measure_performance(func: _AnyCallable) -> Callable[..., tuple[Any, float]]: ...


@overload
def measure_performance(func: _AnyCoro) -> Coroutine[Any, Any, tuple[Any, float]]: ...


def progress_bar(*, maximum: int, progress: float, per: int = ...) -> str: ...


def tchart(
    items: Mapping[Any, Any],
    /,
    keys_formatter: Optional[Callable[[Any], str]] = ...
) -> str: ...


def truncate(text: str, /, width: int, *, placeholder: str = ...) -> str: ...
