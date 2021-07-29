import asyncio
from collections.abc import MutableMapping
from typing import Any, Union, Optional

import aiohttp
from discord.ext import commands
from multidict import CIMultiDictProxy
from yarl import URL


_HTTPResponse = Union[dict, str, bytes]
_HTTPCache = MutableMapping[str, _HTTPResponse]
_URL = Union[URL, str]


class HTTPRequestFailed(commands.CommandError):

    response: aiohttp.ClientResponse
    status: int
    reason: str
    headers: CIMultiDictProxy[str]
    data: _HTTPResponse

    def __init__(
        self,
        response: aiohttp.ClientResponse,
        data: _HTTPResponse
    ) -> None: ...


class HTTPRequester:

    def __init__(
        self,
        *,
        cache: Optional[_HTTPCache] = None,
        **kwargs: Any
    ) -> None: ...

    @property
    def cache(self) -> Optional[_HTTPCache]: ...

    @cache.setter
    def cache(self, value: Optional[_HTTPCache]) -> None: ...

    @property
    def loop(self) -> asyncio.AbstractEventLoop: ...

    @property
    def session(self) -> aiohttp.ClientSession: ...

    async def close(self) -> None: ...

    async def request(
        self,
        method: str,
        url: _URL,
        /,
        *,
        cache__: bool = False,
        **kwargs: Any
    ) -> _HTTPResponse: ...
