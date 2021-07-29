import asyncio
from collections.abc import Callable, Sequence
from typing import Any, Optional

import aiohttp
import discord
from discord.abc import Messageable, User
from discord.ext import commands, menus  # type: ignore[attr-defined]
from discord.utils import cached_property

from .http import _HTTPResponse, _URL


class Context(commands.Context):

    @property
    def loop(self) -> asyncio.AbstractEventLoop: ...

    @property
    def session(self) -> aiohttp.ClientSession: ...

    @cached_property
    def replied_reference(self) -> Optional[discord.MessageReference]: ...

    async def request(
        self,
        method: str,
        url: _URL,
        /,
        *,
        cache__: bool = False,
        **kwargs: Any
    ) -> _HTTPResponse: ...

    async def get(
        self,
        url: _URL,
        /,
        *,
        cache__: bool = False,
        **kwargs: Any
    ) -> _HTTPResponse: ...

    async def post(
        self,
        url: _URL,
        /,
        *,
        cache__: bool = False,
        **kwargs: Any
    ) -> _HTTPResponse: ...

    async def paginate(self, source: menus.PageSource, /, **kwargs: Any) -> None: ...

    async def prompt(
        self,
        message: discord.Message | str,
        /,
        *,
        timeout: float = 30,
        delete_message_after: bool = True
    ) -> Optional[bool]: ...

    async def disambiguate(
        self,
        matches: Sequence[str],
        /,
        formatter: Optional[Callable[[Any], str]] = None,
        *,
        timeout: float = 30
    ) -> Any: ...

    async def copy_with(
        self,
        *,
        author: Optional[User] = None,
        channel: Optional[Messageable] = None,
        **properties: Any
    ) -> "Context": ...
