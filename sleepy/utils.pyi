from collections.abc import (
    Callable,
    Coroutine,
    Generator,
    Mapping,
    Sequence,
)
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, TypeVar, overload
from typing_extensions import Literal


_RT = TypeVar("_RT")
_AnyCallable = Callable[..., _RT]
_AnyCoro = Coroutine[Any, Any, _RT]

_DatetimeFormatStyle = Literal["f", "F", "d", "D", "t", "T", "R"]


class plural:

    def __init__(
        self,
        value: float,
        /,
        value_format_spec: Optional[str] = ...
    ) -> None: ...

    def __format__(self, spec: str) -> str: ...


def awaitable(func: _AnyCallable[Any]) -> _AnyCoro[Any]: ...


def bool_to_emoji(value: Optional[Any]) -> str: ...


def find_extensions_in(path: Path | str) -> Generator[str, None, None]: ...


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
    sigfigs: Optional[int] = ...,
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
def measure_performance(func: _AnyCallable[Any]) -> _AnyCallable[tuple[Any, float]]: ...


@overload
def measure_performance(func: _AnyCoro[Any]) -> _AnyCoro[tuple[Any, float]]: ...


def progress_bar(*, maximum: int, progress: float, per: int = ...) -> str: ...


def randint(a: int, b: int, /, *, seed: Optional[Any] = ...) -> int: ...


def tchart(
    items: Mapping[Any, Any],
    /,
    keys_formatter: Optional[Callable[[Any], str]] = ...
) -> str: ...


def truncate(text: str, /, width: int, *, placeholder: str = ...) -> str: ...
