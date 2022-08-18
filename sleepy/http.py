"""
Copyright (c) 2018-present HitchedSyringe

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""


from __future__ import annotations

__all__ = (
    "HTTPRequester",
    "HTTPRequestFailed",
)


import asyncio
import logging
from collections.abc import MutableMapping
from typing import TYPE_CHECKING, Any, Callable, Optional, Tuple, Union

import aiohttp
from discord.ext import commands
from discord.utils import MISSING

if TYPE_CHECKING:
    from multidict import CIMultiDictProxy
    from yarl import URL

    RequestUrl = Union[str, URL]


try:
    import orjson
except ModuleNotFoundError:
    import json

    def _to_json(obj: Any) -> str:
        return json.dumps(obj, separators=(",", ":"))

    _from_json = json.loads
else:

    def _to_json(obj: Any) -> str:
        return orjson.dumps(obj).decode("utf-8")

    _from_json = orjson.loads


_LOG: logging.Logger = logging.getLogger(__name__)


class HTTPRequestFailed(commands.CommandError):
    """Exception raised when an HTTP request fails.

    This inherits from :exc:`commands.CommandError`.

    .. versionadded:: 1.10

    .. versionchanged:: 2.0
        This now subclasses :exc:`commands.CommandError`
        for ease of use with command error handlers.

    Attributes
    ----------
    response: :class:`aiohttp.ClientResponse`
        The response of the failed request.
    status: :class:`int`
        The HTTP status code.
    reason: :class:`str`
        The HTTP status reason.

        .. versionadded:: 3.0
    headers: multidict.CIMultiDictProxy[:class:`str`]
        The response headers.

        .. versionadded:: 3.0
    data: Any
        The data returned from the failed request.
    """

    def __init__(self, response: aiohttp.ClientResponse, data: Any) -> None:
        self.response: aiohttp.ClientResponse = response
        self.status: int = response.status
        self.reason: str = response.reason  # type: ignore
        self.headers: CIMultiDictProxy[str] = response.headers
        self.data: Any = data

        fmt = "{0.method} {0.url} failed with HTTP status {0.status} {0.reason}."
        super().__init__(fmt.format(response))


class HTTPRequester:
    """An HTTP requests handler that optionally implements caching.

    .. versionadded:: 1.10

    .. versionchanged:: 2.0
        Classes can now be manually constructed.

    .. versionchanged:: 3.2
        Removed the `loop` kwarg and property.

    .. versionchanged:: 3.3
        Sessions are no longer implicitly started during
        class construction. The new :meth:`start` method
        must now be explicitly called with `await`.

    Parameters
    ----------
    cache: Optional[:class:`MutableMapping`]
        The mapping to use for caching the received data.
        ``None`` (the default) denotes disabling caching
        HTTP requests entirely.

        .. versionadded:: 3.0
    json_loads: Callable[[:class:`str`], Any]
        A callable to use for JSON deserialization.
        By default, this is either `json.loads` or `orjson.loads`,
        depending on whether `orjson` is installed.

        .. versionadded:: 3.3
    """

    __slots__: Tuple[str, ...] = ("_cache", "_lock", "_json_loads", "__session")

    def __init__(
        self,
        *,
        cache: Optional[MutableMapping[str, Any]] = None,
        json_loads: Callable[[str], Any] = _from_json,
    ) -> None:
        if cache is not None and not isinstance(cache, MutableMapping):
            raise TypeError(f"cache must be MutableMapping, not {type(cache)!r}.")

        self._cache: Optional[MutableMapping[str, Any]] = cache
        self._lock: asyncio.Lock = asyncio.Lock()
        self._json_loads: Callable[[str], Any] = json_loads
        self.__session: aiohttp.ClientSession = MISSING

    @property
    def cache(self) -> Optional[MutableMapping[str, Any]]:
        """Optional[:class:`MutableMapping`]: The mapping used for caching received data.

        .. versionadded:: 3.0
        """
        return self._cache

    @cache.setter
    def cache(self, value: Optional[MutableMapping[str, Any]]) -> None:
        if value is not None and not isinstance(value, MutableMapping):
            raise TypeError(f"cache must be MutableMapping or None, not {type(value)!r}.")

        self._cache = value

    @property
    def session(self) -> aiohttp.ClientSession:
        """:class:`aiohttp.ClientSession`: The client session used for handling requests."""
        return self.__session

    def is_closed(self):
        """:class:`bool`: Indicates whether the underlying HTTP client session is closed.

        .. versionadded:: 3.3
        """
        return self.__session is MISSING or self.__session.closed

    async def start(self, **session_kwargs: Any) -> None:
        """|coro|

        Starts this HTTP requester session.

        .. versionadded:: 3.3

        Parameters
        ----------
        session_kwargs
            The remaining parameters to be passed to the
            :class:`aiohttp.ClientSession` constructor.

        Raises
        ------
        RuntimeError
            This HTTP requester session is already active.
        """
        if not self.is_closed():
            raise RuntimeError("HTTP requester session is active.")

        session_kwargs.setdefault("json_serialize", _to_json)

        self.__session = aiohttp.ClientSession(**session_kwargs)

        _LOG.info("New HTTP requester session started.")

    async def close(self) -> None:
        """|coro|

        Closes this HTTP requester session.
        """
        if self.is_closed():
            return

        if self.__session is not MISSING:
            await self.__session.close()
            self.__session = MISSING

        _LOG.info("Closed HTTP requester session.")

    async def _perform_http_request(
        self, method: str, url: RequestUrl, /, **options: Any
    ) -> Any:
        if self.is_closed():
            raise RuntimeError("HTTP requester session is closed.")

        # Allows this to work with params__ in case an API requires
        # a parameter that is the same name as a reserved keyword.
        params = options.pop("params__", {})
        params.update(options)

        kwargs = {k[:-2]: params.pop(k) for k in options if k.endswith("__")}

        async with self.__session.request(method, url, params=params, **kwargs) as resp:
            if "application/json" in resp.content_type:
                data = await resp.json(loads=self._json_loads)
            elif "text/" in resp.content_type:
                data = await resp.text("utf-8")
            else:
                data = await resp.read()

            # aiohttp takes care of HTTP 1xx and 3xx internally, so
            # it's probably safe to exclude these from the range of
            # successful status codes.
            if not 200 <= resp.status < 300:
                _LOG.warning(
                    "%s %s failed with HTTP status %s.", method, url, resp.status
                )
                raise HTTPRequestFailed(resp, data)

            _LOG.info("%s %s succeeded with HTTP status %s.", method, url, resp.status)
            return data

    async def request(
        self, method: str, url: RequestUrl, /, *, cache__: bool = False, **options: Any
    ) -> Any:
        """|coro|

        Performs an HTTP request and optionally caches the response.

        .. versionchanged:: 3.0
            Renamed ``cache`` parameter to ``cache__``.

        Parameters
        ----------
        method: :class:`str`
            The HTTP request method.

            .. versionchanged:: 3.0
                This is now a positional-only argument.
        url: Union[:class:`str`, :class:`yarl.URL`]
            The URL to make a request to.

            .. versionchanged:: 3.0
                This is now a positional-only argument.
        cache__: :class:`bool`
            Whether or not to cache the response data.
            If :attr:`cache` is ``None``, then caching the data will
            be disabled regardless of this setting.
            Defaults to ``False``.
        options:
            The remaining parameters to be passed into either the URL
            itself or the :meth:`aiohttp.ClientSession.request` method.
            For the latter case, options must be suffixed with a dunder.

        Returns
        -------
        Any
            The raw response data.

        Raises
        ------
        :exc:`.HTTPRequestFailed`
            The request returned a status code of either 4xx or 5xx.
        RuntimeError
            The underlying HTTP client session was closed when trying
            to fetch data.
        """
        if not cache__ or self._cache is None:
            return await self._perform_http_request(method, url, **options)

        async with self._lock:
            key = f"{method}:{url}:<{' '.join(f'{k}={v}' for k, v in options.items())}>"

            if (cached := self._cache.get(key)) is not None:
                _LOG.debug("%s %s got %s from the cache.", method, url, cached)
                return cached

            data = await self._perform_http_request(method, url, **options)

            self._cache[key] = data
            _LOG.debug("Inserted %s into the cache.", data)

            return data
