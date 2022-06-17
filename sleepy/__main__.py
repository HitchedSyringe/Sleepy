"""
Copyright (c) 2018-present HitchedSyringe

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""


import logging
import sys
from contextlib import contextmanager
from logging.handlers import RotatingFileHandler
from typing import Any, Dict, Generator, Optional

import yaml
from discord import AllowedMentions, Intents, Streaming
from discord.ext import commands

from . import __version__
from .bot import Sleepy


@contextmanager
def _setup_logging(*, log_filename: Optional[str] = None) -> Generator[None, None, None]:
    root_logger = logging.getLogger()

    try:
        stream_handler = logging.StreamHandler()

        formatter = logging.Formatter(
            fmt="[{asctime}] [{levelname:<8}] {name}: {message}",
            datefmt="%Y-%m-%d %H:%M:%S",
            style="{",
        )

        stream_handler.setFormatter(formatter)
        root_logger.addHandler(stream_handler)

        if log_filename is not None:
            from os import makedirs, path

            # Avoids an error when we try to write to a file with a
            # non-existant parent directory. Logically, this should
            # be silently handled from a user standpoint. This only
            # fails on Windows if we exceed the nested path limit.
            if log_parent := path.dirname(log_filename):
                makedirs(log_parent, exist_ok=True)

            file_handler = RotatingFileHandler(
                filename=log_filename,
                mode="w",
                maxBytes=33_554_432,  # 32 MiB
                backupCount=5,
                encoding="utf-8",
            )

            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)

        yield
    finally:
        for handler in root_logger.handlers:
            handler.close()
            root_logger.removeHandler(handler)


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
        url="https://youtube.com/watch?v=PobQzVsj7GE",
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
        max_messages=None,
    )


if __name__ == "__main__":
    try:
        import uvloop  # type: ignore
    except ModuleNotFoundError:
        pass
    else:
        uvloop.install()

    config = _load_config()
    bot = _create_bot(config)

    with _setup_logging():
        # discord.py logging
        logging.getLogger("discord").setLevel(logging.INFO)
        logging.getLogger("discord.http").setLevel(logging.WARNING)

        # bot logging
        logging.getLogger(__package__).setLevel(logging.DEBUG)

        bot.run(config["discord_auth_token"], log_handler=None)
