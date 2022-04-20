"""
Copyright (c) 2018-present HitchedSyringe

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""


import logging
import sys
from typing import Any, Dict

import yaml
from discord import AllowedMentions, Intents, Streaming
from discord.ext import commands

from . import __version__
from .bot import Sleepy


def _set_up_logging() -> None:
    logging.basicConfig(
        datefmt="%Y-%m-%d %H:%M:%S",
        format="[{asctime}] [{levelname:<7}] {name}: {message}",
        style="{"
    )

    # discord.py logging
    logging.getLogger("discord").setLevel(logging.INFO)
    logging.getLogger("discord.http").setLevel(logging.WARNING)

    # bot logging
    logging.getLogger("sleepy").setLevel(logging.DEBUG)
    logging.getLogger("sleepy.http").setLevel(logging.INFO)


def _load_config() -> Dict[str, Any]:
    try:
        config_file = sys.argv[1]
    except IndexError:
        config_file = "config.yaml"

    with open(config_file) as f:
        return yaml.safe_load(f)


def _create_bot(config: Dict[str, Any]) -> Sleepy:
    prefixes = config["prefixes"]

    if not prefixes:
        prefix = "@mention "
        prefixes = commands.when_mentioned
    elif config["mentionable"]:
        prefix = prefixes[0]
        prefixes = commands.when_mentioned_or(*prefixes)
    else:
        prefix = prefixes[0]

    activity = Streaming(
        name=f"{prefix}help \N{BULLET} Sleepy v{__version__}",
        url="https://youtube.com/watch?v=PobQzVsj7GE"
    )

    intents = Intents(
        emojis=True,
        guilds=True,
        messages=True,
        members=True,
        presences=True,
        message_content=True,
    )

    # Since I figure some people want to use this file and
    # may want to use different caching classes or maybe not
    # do caching at all, I'll just leave this to be optional.
    try:
        from cachetools import TTLCache  # type: ignore
    except ModuleNotFoundError:
        http_cache = None
    else:
        # 64 items with TTL of 4 hours (14400 seconds).
        http_cache = TTLCache(64, 14400)

    return Sleepy(
        config,
        prefixes,
        http_cache=http_cache,
        case_insensitive_cogs=config["case_insensitive_cogs"],
        description=config["description"],
        activity=activity,
        allowed_mentions=AllowedMentions(everyone=False, roles=False),
        intents=intents,
        max_messages=None
    )


if __name__ == "__main__":
    _set_up_logging()

    try:
        import uvloop  # type: ignore
    except ModuleNotFoundError:
        pass
    else:
        uvloop.install()

    config = _load_config()
    bot = _create_bot(config)

    bot.run(config["discord_auth_token"])
