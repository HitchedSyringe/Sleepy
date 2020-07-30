"""
© Copyright 2018-2020 HitchedSyringe, All Rights Reserved.

Redistributing, using or owning a copy of this software without explicit permissions
is against these licensing terms, your license(s) to this software can be revoked at
any time without explicit notice beforehand and at the time of revocation.
Your license is non-transferrable, the terms of this license only permit you to do the
following; Create pull requests and make modifications to this repository.

"""


__all__ = ("CachedHTTPRequester", "HTTPError")


import asyncio
import json
import logging

import aiohttp
from cachetools import TTLCache
from discord.ext import commands


_LOG = logging.getLogger(__name__)


class HTTPError(commands.CommandError):
    """Exception that's thrown when an HTTP request fails.
    This inherits from :exc:`commands.CommandError`.

    Attributes
    ----------
    response: :class:`aiohttp.ClientResponse`
        The response of the failed HTTP request.
    status: :class:`int`
        The HTTP status code.
    data: Union[:class:`dict`, :class:`str`, :class:`bytes`]
        The data returned from the failed HTTP request.
    """

    def __init__(self, response, data):
        self.response = response
        self.status = response.status
        self.data = data

        super().__init__(f"{response.method} {response.url} responded with HTTP status code {self.status}.")


class CachedHTTPRequester:
    """All-in-one asynchronous requests handler class that handles both HTTP requests and caching.

    Attributes
    ----------
    bot: :class:`commands.Bot`
        The bot.
    session: :class:`aiohttp.ClientSession`
        The aiohttp session which handles the requests.
    loop: :class:`asyncio.AbstractEventLoop`
        The event loop.
    lock: :class:`asyncio.Lock`
        The lock.
    cache: :class:`cachetools.TTLCache`
        A TTL cache for caching requests.
    """

    __slots__ = ("bot", "cache", "lock", "loop", "session")


    def __init__(self, bot, session):
        self.bot = bot
        self.session = session

        self.loop = bot.loop
        self.lock = asyncio.Lock(loop=self.loop)
        self.cache = TTLCache(maxsize=64, ttl=7200)


    @classmethod
    async def start(cls, bot, headers=None):
        """|coro|

        Factory method which sets up and starts the CachedHTTPRequester session.

        Parameters
        ----------
        bot: :class:`commands.Bot`
            The bot.
        headers: Optional[:class:`dict`]
            The default HTTP headers to use for the session.

        Returns
        -------
        :class:`CachedHTTPRequester`
            The new opened HTTP requesting session.
        """
        session = aiohttp.ClientSession(loop=bot.loop, json_serialize=json.dumps, headers=headers)
        _LOG.info("Opened a new CachedHTTPRequester session.")
        return cls(bot, session)


    async def close(self) -> None:
        """|coro|

        Closes the session.
        """
        _LOG.info("Closed the CachedHTTPRequester session.")
        await self.session.close()


    def clear_cache(self, new_size: int = 64, ttl=7200) -> None:
        """Clears the cache, while also allowing for editing the cache's maximum size and time to live.

        Parameters
        ----------
        new_size: :class:`int`
            The new size for the cache.
            Defaults to ``64``.
        ttl: Union[:class:`float`, :class:`int`]
            The amount of time (in seconds) before an item is removed from the cache.
            Defaults to ``7200``.

        Raises
        ------
        :exc:`ValueError`
            Either ``new_size`` or ``ttl`` was set to a value below or equal to zero.
        """
        if new_size <= 0:
            raise ValueError("new_size cannot be a value below or equal to zero.")

        if ttl <= 0:
            raise ValueError("ttl cannot be a value below or equal to zero.")

        self.cache = TTLCache(maxsize=new_size, ttl=ttl)
        _LOG.info("Cleared cache; Set the size to %s items and ttl to %s seconds.", new_size, ttl)


    async def request(self, method: str, url, *, cache: bool = False, **parameters):
        """|coro|

        Does an HTTP request and caches the response (if desired.)

        .. note::

            Any kwargs that :meth:`aiohttp.ClientSession.request` takes must be suffixed with a double underscore.


        Parameters
        ----------
        method: :class:`str`
            The HTTP request method.
        url:
            The url to make an HTTP request to.
        *, cache: :class:`bool`
            Whether or not to cache the response.
            Defaults to ``False``.

        Returns
        -------
        Union[:class:`dict`, :class:`str`, :class:`bytes`]
            The response to the HTTP request.

        Raises
        ------
        :exc:`requester.HTTPError`
            The HTTP request failed.
        """
        async with self.lock:
            cache_key = f"{method}:{url}:<{''.join(f'{key}={value}' for key, value in parameters.items())}>"

            cached_entry = self.cache.get(cache_key)
            if cache and cached_entry is not None:
                _LOG.debug("%s %s got %s from the cache.", method, url, cached_entry)
                return cached_entry

            # We essentially sort out the session request kwargs from the parameters the url needs.
            # This allows for cleaner request calls, without having to pass a dictionary of parameters.
            kwargs = {}
            clean_parameters = {}
            for key, value in parameters.items():
                if key.endswith("__"):
                    kwargs[key.rstrip("__")] = value
                else:
                    clean_parameters[key] = value

            async with self.session.request(method, url, params=clean_parameters, **kwargs) as response:
                if "application/json" in response.headers["Content-Type"]:
                    data = await response.json(loads=json.loads)
                elif "text/" in response.headers["Content-Type"]:
                    data = await response.text("utf-8")
                else:
                    data = await response.read()

                # Actually, 1xx, 2xx and 3xx codes are all successes, however, I highly doubt that any urls that
                # return 1xx or 3xx status codes would give any useful data, so just assume an error if not 2xx status.
                if 200 <= response.status < 300:
                    _LOG.info("%s %s succeeded with HTTP status code %d.", method, url, response.status)
                    if cache:
                        self.cache[cache_key] = data
                        _LOG.debug("%s %s inserted %s into the cache.", method, url, data)
                    return data

                _LOG.warning("%s %s errored with HTTP status code %d.", method, url, response.status)
                raise HTTPError(response, data)
