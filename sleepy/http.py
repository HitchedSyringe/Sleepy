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
from typing import TYPE_CHECKING, Any, Dict, Optional, Tuple, Union

import aiohttp
from discord.ext import commands


_LOG = logging.getLogger(__name__)


if TYPE_CHECKING:
    from multidict import CIMultiDictProxy
    from yarl import URL

    HTTPResponseData = Union[str, bytes, Dict[str, Any]]
    RequestUrl = Union[str, URL]


class HTTPRequestFailed(commands.CommandError):
    """Exception raised when an HTTP request fails.

    This inherits from :exc:`commands.CommandError`.

    .. versionadded:: 1.10

    .. versionchanged:: 2.0

        * Renamed to ``HTTPError``.
        * This now subclasses :exc:`commands.CommandError`
          for ease of use with command error handlers.

    .. versionchanged:: 3.0
        Renamed to ``HTTPRequestFailed``.

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
    data: Union[:class:`dict`, :class:`str`, :class:`bytes`]
        The data returned from the failed request.
    """

    def __init__(self, response: aiohttp.ClientResponse, data: HTTPResponseData) -> None:
        self.response: aiohttp.ClientResponse = response
        self.status = status = response.status  # type: int
        self.reason: str = response.reason
        self.headers: CIMultiDictProxy[str] = response.headers
        self.data: HTTPResponseData = data

        super().__init__(
            f"{response.method} {response.url} failed with HTTP status code {status}."
        )


class HTTPRequester:
    """An HTTP requests handler that optionally implements caching.

    .. versionadded:: 1.10

    .. versionchanged:: 2.0

        * Renamed to ``CachedHTTPRequester``.
        * Classes can now be manually constructed.

    .. versionchanged:: 3.0
        Renamed to ``HTTPRequester``.

    .. versionchanged:: 3.2
        Removed the `loop` kwarg and property.

    Parameters
    ----------
    cache: Optional[:class:`MutableMapping`]
        The mapping to use for caching the received data.
        ``None`` (the default) denotes disabling caching
        HTTP requests entirely.

        .. versionadded:: 3.0
    """

    __slots__: Tuple[str, ...] = ("_cache", "_request_lock", "__session")

    def __init__(
        self,
        *,
        cache: Optional[MutableMapping[str, Any]] = None,
        **kwargs: Any
    ) -> None:
        if cache is not None and not isinstance(cache, MutableMapping):
            raise TypeError(f"cache must be MutableMapping or NoneType, not {type(cache)!r}.")

        self._cache: Optional[MutableMapping[str, Any]] = cache
        self._request_lock: asyncio.Lock = asyncio.Lock()
        self.__session: aiohttp.ClientSession = aiohttp.ClientSession(**kwargs)

        _LOG.info("Started a new session.")

    @property
    def cache(self) -> Optional[MutableMapping[str, Any]]:
        """Optional[:class:`MutableMapping`]: The mapping used for caching received data.

        .. versionadded:: 3.0
        """
        return self._cache

    @cache.setter
    def cache(self, value: Optional[MutableMapping[str, Any]]) -> None:
        if value is not None and not isinstance(value, MutableMapping):
            raise TypeError(f"cache must be MutableMapping or NoneType, not {type(value)!r}.")

        self._cache = value

    @property
    def session(self) -> aiohttp.ClientSession:
        """:class:`aiohttp.ClientSession`: The client session used for handling requests."""
        return self.__session

    async def close(self) -> None:
        """|coro|

        Closes the session.
        """
        await self.__session.close()
        _LOG.info("Session closed.")

    async def __request(
        self,
        method: str,
        url: RequestUrl,
        /,
        **kwargs: Any
    ) -> HTTPResponseData:
        # Allows this to work with params__ in case an API requires
        # a parameter that is the same name as a reserved keyword.
        params = kwargs.pop("params__", {})
        params.update(kwargs.copy())

        kwargs = {k[:-2]: params.pop(k) for k in kwargs if k.endswith("__")}

        async with self.__session.request(method, url, params=params, **kwargs) as resp:
            if "application/json" in resp.content_type:
                data = await resp.json()
            elif "text/" in resp.content_type:
                data = await resp.text("utf-8")
            else:
                data = await resp.read()

            # aiohttp takes care of HTTP 1xx and 3xx internally, so
            # it's probably safe to exclude these from the range of
            # successful status codes.
            if not 200 <= resp.status < 300:
                _LOG.warning("%s %s failed with HTTP status %s.", method, url, resp.status)
                raise HTTPRequestFailed(resp, data)

            _LOG.info("%s %s succeeded with HTTP status %s.", method, url, resp.status)
            return data

    async def request(
        self,
        method: str,
        url: RequestUrl,
        /,
        *,
        cache__: bool = False,
        **kwargs: Any
    ) -> HTTPResponseData:
        """|coro|

        Performs an HTTP request and optionally caches the response.

        .. note::

            Any kwargs that :meth:`aiohttp.ClientSession.request`
            takes must be suffixed with a dunder.

        .. versionchanged:: 3.0
            Renamed ``cache`` argument to ``cache__``.

        Parameters
        ----------
        method: :class:`str`
            The HTTP method.

            .. versionchanged:: 3.0
                This is now a positional-only argument.
        url: Union[:class:`str`, :class:`yarl.URL`]
            The URL to make a request to.

            .. versionchanged:: 3.0
                This is now a positional-only argument.
        cache__: :class:`bool`
            Whether or not to cache the response data.
            If :attr:`cache` is ``None``, then caching
            the data will be disabled regardless of
            this setting.
            Defaults to ``False``.

        Returns
        -------
        Union[:class:`dict`, :class:`str`, :class:`bytes`]
            The raw response data.

        Raises
        ------
        :exc:`.HTTPRequestFailed`
            The request returned a status code of either 4xx or 5xx.
        """
        if not cache__ or self._cache is None:
            return await self.__request(method, url, **kwargs)

        async with self._request_lock:
            key = f"{method}:{url}:<{' '.join(f'{k}={v}' for k, v in kwargs.items())}>"

            if (cached := self._cache.get(key)) is not None:
                _LOG.debug("%s %s got %s from the cache.", method, url, cached)
                return cached

            data = await self.__request(method, url, **kwargs)

            self._cache[key] = data
            _LOG.debug("Inserted %s into the cache.", data)

            return data
