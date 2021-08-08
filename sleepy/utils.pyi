from collections.abc import (
    Callable,
    Coroutine,
    Iterable,
    Mapping,
    Sequence,
)
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional
from typing_extensions import Literal


_AnyCallable = Callable[..., Any]
_AnyCoro = Coroutine[Any, Any, Any]
_DatetimeFormatStyle = Literal["f", "F", "d", "D", "t", "T", "R"]


class plural:

    def __init__(
        self,
        value: float,
        /,
        value_format_spec: Optional[str] = None
    ) -> None: ...

    def __format__(self, spec: str) -> str: ...


def awaitable(func: _AnyCallable) -> _AnyCoro: ...


def bool_to_emoji(value: Optional[Any]) -> str: ...


def find_extensions_in(path: Path | str) -> Iterable[str]: ...


def human_delta(
    delta: timedelta | float,
    /,
    *,
    brief: bool = False,
    absolute: bool = False
) -> str: ...


def human_join(sequence: Sequence[Any], /, *, joiner: str = "and") -> str: ...


def human_number(
    number: float,
    /,
    sigfigs: int = 3,
    *,
    strip_trailing_zeroes: bool = True,
    suffixes: Sequence[str] = ...
) -> str: ...


def human_timestamp(
    timestamp: datetime | float,
    /,
    formatting: Optional[_DatetimeFormatStyle] = None
) -> str: ...


def measure_performance(
    func: _AnyCallable | _AnyCoro
) -> Callable[..., tuple[Any, float]] | Coroutine[Any, Any, tuple[Any, float]]: ...


def progress_bar(*, maximum: int, progress: float, per: int = 1) -> str: ...


def tchart(
    items: Mapping[Any, Any],
    /,
    keys_formatter: Optional[Callable[[Any], str]] = None
) -> str: ...


def truncate(
    text: str,
    /,
    width: int,
    *,
    placeholder: str = "..."
) -> str: ...
