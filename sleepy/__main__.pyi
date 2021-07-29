from collections.abc import Callable
from typing import Any, Optional

import discord
from cachetools import TTLCache

from .bot import Sleepy
from .context import Context
from .http import _HTTPResponse


_SleepyBot = Sleepy[Context]


config_file: str
config: dict[str, Any]
prefixes: list[str] | Callable[[_SleepyBot, discord.Message], list[str]]
prefix: str
intents: discord.Intents
activity: discord.Streaming
http_cache: Optional[TTLCache[str, _HTTPResponse]]
bot: _SleepyBot
