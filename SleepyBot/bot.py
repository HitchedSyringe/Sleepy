"""
© Copyright 2018-2020 HitchedSyringe, All Rights Reserved.

Redistributing, using or owning a copy of this software without explicit permissions
is against these licensing terms, your license(s) to this software can be revoked at
any time without explicit notice beforehand and at the time of revocation.
Your license is non-transferrable, the terms of this license only permit you to do the
following; Create pull requests and make modifications to this repository.

"""


__all__ = ("Sleepy",)


import datetime
import logging
from pathlib import Path

import discord
from discord.ext import commands, tasks

from . import __version__
from .utils import context, formatting
from .utils.requester import CachedHTTPRequester, HTTPError


_LOG = logging.getLogger(__name__)


class Sleepy(commands.AutoShardedBot):
    """The main Slee.py Discord bot class.

    This class is a subclass of :class:`commands.AutoShardedBot` and as a result
    anything that you can do with a :class:`commands.AutoShardedBot` you can do with
    this bot.

    Attributes
    ----------
    config: :class:`configparser.ConfigParser`
        The config values loaded from file.
    app_info: :class:`discord.AppInfo`
        The bot's application information.
        This is here in order to save on api calls and make it easier to get the bot info.
        .. note::

            This attribute is ``None`` upon initialisation and is only set upon logging in.
            Additionally, this attribute does **not** automatically update.
    start_time: :class:`datetime.datetime`
        A UTC datetime representing when the bot was initialised.
    version: :class:`str`
        A string representing the current build version of the bot.
    http_requester: :class:`requester.CachedHTTPRequester`
        The HTTP requester class used for making and caching HTTP requests.
        .. note::

            This attribute is ``None`` upon initialisation and is only set upon logging in.
    prefixes: List[:class:`str`]
        The bot's configured prefixes.
    blocklist: Set[:class:`int`]
        The user/guild IDs which are blocked from using the bot.
    spam_control: :class:`commands.CooldownMapping`
        The cooldown mapping used for users who excessively spam commands.
    exts_directory: :class:`pathlib.Path`
        The directory the extensions are located in.
    all_exts: Set[:class:`str`]
        The extensions detected by the extension loader.
        .. note::

            This attribute is an empty :class:`set` upon initialisation and is only populated
            when all extensions are loaded.
            If the autoloader is enabled, all extensions beginning with `__` are not included.
    """

    def __init__(self, config, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.config = config
        self.app_info = None

        self.start_time = datetime.datetime.utcnow()
        self.version = __version__

        self.http_requester = None

        main_config = config["Discord Bot Config"]
        self.prefixes = main_config.getjson("prefixes")
        self.blocklist = set(main_config.getjson("blocklist"))

        # Cooldown mapping for people who excessively spam commands.
        self.spam_control = commands.CooldownMapping.from_cooldown(10, 12, commands.BucketType.user)

        exts_dir = config["Extension Config"]["exts_directory"]
        self.exts_directory = Path(exts_dir) if exts_dir is not None else Path(".")

        self.all_exts = set()

        self._boot_task.start()  # pylint: disable=maybe-no-member


    @property
    def webhook(self):
        """:class:`discord.Webhook`: The webhook used for error reporting/contact messages.
        This is aquired through :meth:`discord.Webhook.from_url`.
        """
        return discord.Webhook.from_url(
            url=self.config["Secrets"]["webhook_url"],
            adapter=discord.AsyncWebhookAdapter(self.http_requester.session)
        )


    @property
    def app_owner(self):
        """:class:`discord.User`: The bot's app owner or team app owner (if the bot is a team app).
        This is acquired through :attr:`app_info`.
        """
        return self.app_info.team.owner if self.app_info.team else self.app_info.owner


    async def login(self, *args, **kwargs) -> None:
        headers = {
            "User-Agent": f"Discord-Sleepy/v{__version__}",
        }
        self.http_requester = await CachedHTTPRequester.start(self, headers=headers)
        await super().login(*args, **kwargs)


    async def close(self) -> None:
        await self.http_requester.close()
        await super().close()


    @tasks.loop(count=1)
    async def _boot_task(self) -> None:
        """One-off task that contains the important startup stuff that should only run once.
        This loop fires and completes upon initialisation.
        For internal use only.
        """
        self.app_info = await self.application_info()
        # Application_info populates owner_ids (already a set) so just union them.
        self.owner_ids |= frozenset(self.config["Discord Bot Config"].getjson("owner_ids"))

        await self.wait_until_ready()

        self._load_configured_extensions()

        _LOG.info("Boot Successful! Running Sleepy Version: %s", __version__)
        _LOG.info("Logged in as: %s (ID: %s)", self.user, self.user.id)
        _LOG.info("Owner IDS (%s): %s", len(self.owner_ids), self.owner_ids)
        _LOG.info("Shard IDS (%s): %s", self.shard_count, self.shard_ids)

        await self.set_default_presence()


    def _load_configured_extensions(self) -> None:
        """Loads the extensions in the extensions directory.
        This populates :attr:`all_exts`.
        For internal use only.
        """
        exts_config = self.config["Extension Config"]

        if exts_config.getboolean("autoload_enabled"):
            exts = self.exts_directory.rglob("*.py")
            to_load = frozenset(
                e.with_suffix("").as_posix().replace("/", ".") for e in exts if not e.stem.startswith("__")
            )
        else:
            to_load = frozenset(exts_config.getjson("exts"))

            exts_dir = exts_config["exts_directory"]
            if exts_dir is not None:
                cleaned = self.exts_directory.as_posix().replace("/", ".")
                to_load = frozenset(f"{cleaned}.{ext}" for ext in to_load)

        for ext in to_load:
            try:
                self.load_extension(ext)
            except commands.ExtensionError as exc:
                _LOG.warning("Failed to load extension `%s`.", ext, exc_info=exc)
            else:
                _LOG.info("Loaded extension `%s`.", ext)
                self.all_exts.add(ext)

        detected = len(to_load)
        loaded = len(self.all_exts)
        _LOG.info("Extensions: %d detected; %d loaded; %d failed", detected, loaded, detected - loaded)


    async def set_default_presence(self) -> None:
        """Sets the default presence configured."""
        presence_config = self.config["Default Presence Config"]
        presence = presence_config.getjson("presence")
        if presence is None:
            return

        data = presence.pop("activity")
        if presence_config.getboolean("doing_activity"):
            guilds = 0
            members = 0
            channels = 0
            for guild in self.guilds:
                guilds += 1
                members += guild.member_count
                channels += len(guild.channels)

            data["name"] = data["name"].format(
                bot=self,
                unique=len(self.users),
                members=members,
                channels=channels,
                guilds=guilds,
                prefix=self.prefixes[0] if self.prefixes else f"@{self.user} "
            )

            presence["activity"] = discord.Activity(**data)

        await self.change_presence(**presence)
        _LOG.info("Set the bot's default presence.")


    async def on_ready(self) -> None:
        _LOG.info("Bot Ready.")


    async def on_resumed(self) -> None:
        _LOG.info('Bot Resumed.')


    async def process_commands(self, message: discord.Message) -> None:
        if message.author.bot:
            return

        # To prevent potential abuse, bot owners cannot bypass the user blocklist.
        if message.author.id in self.blocklist:
            return

        if message.author.id not in self.owner_ids:  # Bot owner bypass.
            if message.guild is not None and message.guild.id in self.blocklist:
                return

            bucket = self.spam_control.get_bucket(message)
            current = message.created_at.replace(tzinfo=datetime.timezone.utc).timestamp()
            retry_after = bucket.update_rate_limit(current)
            if retry_after is not None:
                # TODO: (Maybe) Auto block or actual notification system.
                location = f"{message.guild} (ID: {message.guild.id})" if message.guild is not None else "DMs"
                logging_format = "%s (ID %s) spamming in %s, retry_after: %.2fs"
                _LOG.warning(logging_format, message.author, message.author.id, location, retry_after)
                return

        ctx = await self.get_context(message, cls=context.Context)
        await self.invoke(ctx)


    async def on_command(self, ctx: commands.Context) -> None:
        if ctx.author.id in self.owner_ids:
            ctx.command.reset_cooldown(ctx)


    async def on_command_error(self, ctx: commands.Context, error) -> None:
        error = getattr(error, "original", error)

        if isinstance(error, (commands.CommandNotFound, commands.DisabledCommand, commands.NoPrivateMessage)):
            return

        # This approach allows for granular control of whether or not to handle errors in
        # the global error handler rather than just only in local handlers.
        if hasattr(error, "handled"):
            return

        if isinstance(error, (commands.CommandInvokeError, commands.ConversionError)):
            ctx.command.reset_cooldown(ctx)
            return

        if isinstance(error, commands.MissingRequiredArgument):
            ctx.command.reset_cooldown(ctx)
            await ctx.send(f"Missing required argument: `{error.param.name}`.")
        elif isinstance(error, (commands.BadArgument, commands.BadUnionArgument)):
            ctx.command.reset_cooldown(ctx)
            await ctx.send("Bad argument: Please double-check your input arguments and try again.")
        elif isinstance(error, commands.ArgumentParsingError):
            ctx.command.reset_cooldown(ctx)
            await ctx.send(f"An error occurred while processing your arguments: {error}")
        elif isinstance(error, commands.CommandOnCooldown):
            await ctx.send(
                f"This command is currently on cooldown, please retry in **{error.retry_after:.2f} seconds**."
            )
        elif isinstance(error, commands.NotOwner):
            await ctx.send("Only my owner(s) can use this command.")
        elif isinstance(error, commands.MissingPermissions):
            perms = tuple(p.replace('_', ' ').replace('guild', 'server').title() for p in error.missing_perms)
            await ctx.send(
                f"You need the `{formatting.humanise_sequence(perms)}` permission(s) in order to use this command."
            )
        elif isinstance(error, commands.BotMissingPermissions):
            perms = tuple(p.replace('_', ' ').replace('guild', 'server').title() for p in error.missing_perms)
            await ctx.send(
                f"I need the `{formatting.humanise_sequence(perms)}` permission(s) in order to run that command."
            )
        elif isinstance(error, commands.CheckFailure):
            await ctx.send(str(error))
        elif isinstance(error, HTTPError):  # requester error
            await ctx.send(f"Request failed: Got HTTP status code {error.status} {error.response.reason}")


    async def on_guild_join(self, guild: discord.Guild) -> None:
        if guild.id in self.blocklist:
            await guild.leave()
