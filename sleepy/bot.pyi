from collections.abc import Iterable, Mapping
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, TypeVar

import discord
from discord.ext import commands
from discord.utils import cached_property
from discord.webhook import _AsyncWebhook

from .context import Context
from .http import HTTPRequester


_CT = TypeVar("_CT", bound=Context)


class Sleepy(commands.Bot[_CT]):

    app_info: Optional[discord.AppInfo]
    config: Mapping[str, Any]
    extensions_directory: Path
    http_requester: HTTPRequester
    started_at: Optional[datetime]

    def __init__(
        self,
        config: Mapping[str, Any],
        /,
        *args: Any,
        **kwargs: Any
    ) -> None: ...

    @cached_property
    def webhook(self) -> _AsyncWebhook: ...

    @property
    def owner(self) -> Optional[discord.User]: ...

    def get_all_extensions(self) -> Iterable[str]: ...

    async def login(self, token: str, *, bot: bool = True) -> None: ...

    async def close(self) -> None: ...
