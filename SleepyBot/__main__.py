"""
© Copyright 2018-2020 HitchedSyringe, All Rights Reserved.

Redistributing, using or owning a copy of this software without explicit permissions
is against these licensing terms, your license(s) to this software can be revoked at
any time without explicit notice beforehand and at the time of revocation.
Your license is non-transferrable, the terms of this license only permit you to do the
following; Create pull requests and make modifications to this repository.

"""


import configparser
import json
import logging
import sys

import discord
from discord.ext import commands

from .bot import Sleepy


# --- Load config ---
config = configparser.ConfigParser(allow_no_value=True, converters={"json": lambda x: json.loads(x)})
# Allows the user to specify a config file to load instead of looking for the default.
config.read(sys.argv[1] if len(sys.argv) > 1 else "config.ini")

# --- Setup the bot ---
bot = Sleepy(
    config,
    command_prefix=commands.when_mentioned_or(*config["Discord Bot Config"].getjson("prefixes")),
    description=config["Discord Bot Config"]["description"],
    allowed_mentions=discord.AllowedMentions(everyone=False, users=False, roles=False)
)

# --- Setup logging ---
logging.basicConfig(
    datefmt="%Y-%m-%d %H:%M:%S",
    format="[{asctime}] [{levelname:<7}] {name}: {message}",
    style="{"
)

# Set logging levels for discord.py
logging.getLogger("discord").setLevel(logging.INFO)
logging.getLogger("discord.http").setLevel(logging.WARNING)

# Set logging levels for bot components.
logging.getLogger("SleepyBot").setLevel(logging.DEBUG)
# Ensure that logging is enabled in the extensions directory.
logging.getLogger(str(bot.exts_directory.as_posix()).replace("/", ".")).setLevel(logging.DEBUG)
logging.getLogger("SleepyBot.utils.requester").setLevel(logging.INFO)

# --- Run the bot ---
bot.run(config["Secrets"]["discord_bot_token"], reconnect=True)
