"""
Copyright (c) 2018-present HitchedSyringe

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""


__all__ = (
    "HTTPRequester",
    "HTTPRequestFailed",
)


import asyncio
import logging
from collections.abc import MutableMapping

import aiohttp
from discord.ext import commands


_LOG = logging.getLogger(__name__)


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

    def __init__(self, response, data):
        self.response = response
        self.status = status = response.status
        self.reason = response.reason
        self.headers = response.headers
        self.data = data

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

    Parameters
    ----------
    cache: Optional[:class:`MutableMapping`]
        The mapping to use for caching the received data.
        ``None`` (the default) denotes disabling caching
        HTTP requests entirely.

        .. versionadded:: 3.0
    loop: :class:`asyncio.AbstractEventLoop`
        The event loop to use for HTTP requests.

        .. versionadded:: 2.0
    """

    __slots__ = ("_cache", "_loop", "_request_lock", "__session")

    def __init__(self, cache=None, **kwargs):
        if cache is not None and not isinstance(cache, MutableMapping):
            raise TypeError(
                f"Expected cache to be MutableMapping or NoneType, not {type(cache).__name__}."
            )

        self._cache = cache

        self._loop = loop = kwargs.pop("loop", None) or asyncio.get_event_loop()
        self._request_lock = asyncio.Lock(loop=loop)
        self.__session = aiohttp.ClientSession(loop=loop, **kwargs)

        _LOG.info("Started a new session.")

    @property
    def cache(self):
        """Optional[:class:`MutableMapping`]: The mapping used for caching received data.

        .. versionadded:: 3.0
        """
        return self._cache

    @cache.setter
    def cache(self, value):
        if value is not None and not isinstance(value, MutableMapping):
            raise TypeError(
                f"Expected MutableMapping or NoneType, received {type(value).__name__} instead."
            )

        self._cache = value

    @property
    def loop(self):
        """:class:`asyncio.AbstractEventLoop`: The event loop used for HTTP requests.

        .. versionadded:: 2.0

        .. versionchanged:: 3.0
            This is now a read-only property.
        """
        return self._loop

    @property
    def session(self):
        """:class:`aiohttp.ClientSession`: The client session used for handling requests."""
        return self.__session

    async def close(self):
        """|coro|

        Closes the session.
        """
        await self.__session.close()
        _LOG.info("Session closed.")

    async def request(self, method, url, /, *, cache__=False, **kwargs):
        """|coro|

        Performs an HTTP request and optionally caches the response.

        .. note::

            Any kwargs that :meth:`aiohttp.ClientSession.request`
            takes must be suffixed with a dunder.

        .. versionchanged:: 3.0
            ``method`` and ``url`` are now positional-only arguments.

        Parameters
        ----------
        method: :class:`str`
            The HTTP method.
        url: Union[:class:`str`, :class:`yarl.URL`]
            The URL to make a request to.
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
        async with self._request_lock:
            if cache__ and self._cache is not None:
                key = f"{method}:{url}:<{' '.join(f'{k}={v}' for k, v in kwargs.items())}>"

                if (cached := self._cache.get(key)) is not None:
                    _LOG.debug("%s %s got %s from the cache.", method, url, cached)
                    return cached

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
                if 200 <= resp.status < 300:
                    _LOG.info(
                        "%s %s succeeded with HTTP status code %s.",
                        method,
                        url,
                        resp.status
                    )

                    if cache__ and self._cache is not None:
                        self._cache[key] = data
                        _LOG.debug("Inserted %s into the cache.", data)

                    return data

                _LOG.warning(
                    "%s %s failed with HTTP status code %s.",
                    method,
                    url,
                    resp.status
                )
                raise HTTPRequestFailed(resp, data)
