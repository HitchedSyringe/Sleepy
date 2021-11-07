"""
Copyright (c) 2018-present HitchedSyringe

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""


# Only run if this module is being executed as a script
# since the config loading system may break in some cases.
if __name__ != "__main__":
    exit(0)


import logging
import sys

import yaml
from discord import AllowedMentions, Intents, Streaming
from discord.ext import commands

from . import __version__
from .bot import Sleepy


# --- Logging setup ---

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


# --- Bot setup ---

try:
    config_file = sys.argv[1]
except IndexError:
    config_file = "config.yaml"

with open(config_file) as f:
    config = yaml.safe_load(f)

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
    reactions=True
)

# Since I figure some people want to use this file and
# may want to use different caching classes or maybe not
# do caching at all, I'll just leave this to be optional.
try:
    from cachetools import TTLCache
except ImportError:
    http_cache = None
else:
    # 64 items with TTL of 4 hours (14400 seconds).
    http_cache = TTLCache(64, 14400)

# This does setup for uvloop for those who wish to gain the
# potential performance benefit. This is left as optional
# since some either might not want to use it or this code
# is running on Windows, which uvloop doesn't support.
try:
    import uvloop
except ImportError:
    pass
else:
    uvloop.install()

bot = Sleepy(
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

bot.run(config["discord_auth_token"])
