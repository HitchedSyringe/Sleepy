"""
Copyright (c) 2018-present HitchedSyringe

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""


from __future__ import annotations


__all__ = (
    "Sleepy",
)


import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any, Generator, Mapping, Optional

import discord
from discord.ext import commands
from discord.utils import cached_property, utcnow

from . import __version__
from .context import Context
from .http import HTTPRequester, HTTPRequestFailed
from .utils import find_extensions_in, human_join


if TYPE_CHECKING:
    from datetime import datetime


_LOG = logging.getLogger(__name__)


class Sleepy(commands.Bot):
    """The main Sleepy Discord bot class.

    Subclasses :class:`commands.Bot`.

    .. versionchanged:: 1.4
        Renamed to ``DiscordBot``.

    .. versionchanged:: 1.12.3
        Renamed to ``Sleepy``.

    Parameters
    ----------
    config: Mapping[:class:`str`, Any]
        The loaded configuration values.

        .. versionadded:: 1.12
    http_cache: Optional[:class:`MutableMapping`]
        A mapping to store the data received from requests
        made by the HTTP requester.

        .. versionadded:: 3.0
    case_insensitive_cogs: :class:`bool`
        Whether the cogs should be case-insensitive.
        Useful for making help more user-friendly.
        This cannot be changed once initialised.
        Defaults to ``False``.

        .. warning::

            Enabling this setting will alter the internal
            behaviour of :meth:`Bot.get_cog`, allowing it
            to resolve a cog regardless of its name case.
            For example, both ``"Owner"`` and ``"OwNeR"``
            resolve to the ``Owner`` cog.

        .. versionadded:: 3.0

    Attributes
    ----------
    app_info: Optional[:class:`discord.AppInfo`]
        The bot's cached application information upon
        logging in.
        ``None`` if not logged in.

        .. versionadded:: 1.12

        .. versionchanged:: 2.0
            This is now set upon logging in.
    config: Mapping[:class:`str`, Any]
        The bot's configuration values.

        .. versionadded:: 1.12
    extensions_directory: :class:`pathlib.Path`
        The directory the extensions are located in.

        .. versionchanged:: 3.0
            Renamed to ``extensions_directory``.
    http_requester: :class:`HTTPRequester`
        The bot's HTTP requester client.

        .. versionadded:: 1.10

        .. versionchanged:: 2.0
            Renamed to ``http_requester``.
    started_at: Optional[:class:`datetime.datetime`]
        The bot's starting time as a UTC-aware datetime.
        ``None`` if not logged in.

        .. versionadded:: 1.6

        .. versionchanged:: 2.1
            This is now set when ``ready`` rather than
            on initialization.

        .. versionchanged:: 3.0

            * Renamed to ``started_at``.
            * This is now set when logged in rather
              than on ``ready``.

        .. versionchanged:: 3.2
            This is now a UTC-aware datetime.
    """

    extensions_directory: Path

    def __init__(self, config: Mapping[str, Any], /, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

        if kwargs.get("case_insensitive_cogs"):
            # Accessing mangled attributes is considered bad practice,
            # but unfortunately, this is the good and only way.
            self._BotBase__cogs = commands.core._CaseInsensitiveDict()

        self.app_info: Optional[discord.AppInfo] = None
        self.config: Mapping[str, Any] = config
        self.started_at: Optional[datetime] = None

        self.extensions_directory = exts_dir = Path(config["extensions_directory"] or ".")

        headers = {
            "User-Agent": f"Sleepy-Discord-Bot/{__version__} (https://github.com/HitchedSyringe/Sleepy)"
        }
        self.http_requester: HTTPRequester = \
            HTTPRequester(cache=kwargs.get("http_cache"), headers=headers)

        # Cooldown mapping for people who excessively spam commands.
        self._spam_control: commands.CooldownMapping = \
            commands.CooldownMapping.from_cooldown(10, 12, commands.BucketType.user)

        if config["enable_autoload"]:
            to_load = self.get_all_extensions()
        else:
            to_load = []

            for ext in config["extensions_list"]:
                if ext.startswith("$/"):
                    ext = ext.replace("$", "/".join(exts_dir.parts), 1).strip("/")

                if ext.endswith("/*"):
                    to_load.extend(find_extensions_in(Path(ext[:-1])))
                else:
                    to_load.append(".".join(ext.split("/")))

        total = 0
        loaded = 0
        for ext in to_load:
            total += 1

            try:
                self.load_extension(ext)
            except Exception as exc:
                _LOG.warning('Failed to load extension "%s".', ext, exc_info=exc)
            else:
                _LOG.info('Loaded extension "%s".', ext)
                logging.getLogger(ext).setLevel(logging.INFO)
                loaded += 1

        _LOG.info("Extensions stats: %d loaded; %d failed; %d total", loaded, total - loaded, total)

    @cached_property
    def webhook(self) -> discord.Webhook:
        """:class:`discord.Webhook`: The bot's system webhook.

        .. versionadded:: 1.12

        .. versionchanged:: 2.1
            This is now a cached property.
        """
        return discord.Webhook.partial(
            **self.config["discord_webhook"],
            session=self.http_requester.session
        )

    @property
    def owner(self) -> Optional[discord.User]:
        """Optional[:class:`discord.User`]: The bot's owner.

        This first attempts to resolve a user from the configured
        owner IDs. If no user could be resolved, then this falls
        back to getting the application owner using the bot's
        cached application information. If both above attempts
        fail, then ``None`` will be returned instead.

        .. versionadded:: 1.12

        .. versionchanged:: 2.0
            Renamed to ``app_owner``.

        .. versionchanged:: 3.0

            * Renamed to ``owner``.
            * :attr:`app_info` is now used as a fallback.
        """
        if self.owner_id is not None:
            owner = self.get_user(self.owner_id)
        elif self.owner_ids is not None and len(self.owner_ids) == 1:
            owner = self.get_user(next(iter(self.owner_ids)))
        else:
            owner = None

        # NOTE: Doing a fallback like this could pose a potential
        # security issue if the app owners are different from the
        # configured owners. Essentially, this potentially impacts
        # any users who decide to use this in a check. This likely
        # isn't that big of a concern since I figure most people
        # would actually set their local owner configurations in
        # line with their app owner settings since there's no real
        # reason not to. Nonetheless, this is still worth mentioning.
        if owner is None and self.app_info is not None:
            if self.app_info.team is None:
                owner = self.app_info.owner
            else:
                # :attr:`AppInfo.owner` is the team itself, so this
                # is the only way of getting the application owner.
                # We use :meth:`Bot.get_user` here for two reasons:
                # * Consistency (i.e. returning :class:`discord.User`
                #   instead of :class:`discord.TeamMember`)
                # * :attr:`Team.owner` is O(n); this is O(1).
                owner = self.get_user(self.app_info.team.owner_id)  # type: ignore

        return owner

    async def __boot(self) -> None:
        self.started_at = utcnow()
        self.app_info = await self.application_info()

        # Might as well manually populate the owner info if not
        # initially given since :meth:`is_owner` just makes the
        # same API call we just did internally. Also, this is
        # better because it bothers to populate from both local
        # config and the application information itself.
        if self.owner_id is None and not self.owner_ids:
            configured_owner_ids = self.config["owner_ids"]

            if len(configured_owner_ids) == 1:
                self.owner_id = configured_owner_ids[0]
            else:
                # Doing this in case `None` was passed for this.
                self.owner_ids = set(configured_owner_ids)
                app_info = self.app_info

                if self.owner_ids:
                    if app_info.team is None:
                        self.owner_ids.add(app_info.owner.id)
                    else:
                        self.owner_ids.update(m.id for m in app_info.team.members)
                else:
                    self.owner_id = app_info.owner.id

        await self.wait_until_ready()

        _LOG.info("Boot Successful! Running Sleepy %s", __version__)
        _LOG.info("| User: %s (ID: %s)", self.user, self.user.id)  # type: ignore

        if self.owner_id is not None:
            _LOG.info("| Owner ID: %s", self.owner_id)
        else:
            _LOG.info("| Owner IDS (%s): %s", len(self.owner_ids), self.owner_ids)

        # _LOG.info("| Shard IDS (%s): %s", self.shard_count, self.shard_ids)

    def get_all_extensions(self) -> Generator[str, None, None]:
        """Returns a generator of all recognized extensions
        in the configured extensions directory.

        This is equivalent to passing :attr:`extensions_directory`
        in `.utils.find_extensions_in`.

        .. versionadded:: 3.0

        Yields
        ------
        :class:`str`
            The name of the recognized extension.
        """
        return find_extensions_in(self.extensions_directory)

    async def login(self, token: str) -> None:
        await super().login(token)
        # This has to be a task since wait_until_ready
        # will block from ever actually reaching ready.
        self.loop.create_task(self.__boot())

    async def close(self) -> None:
        await self.http_requester.close()
        await super().close()

    async def on_ready(self) -> None:
        _LOG.info("Bot ready.")

    async def on_resumed(self) -> None:
        _LOG.info("Bot resumed.")

    async def process_commands(self, message: discord.Message) -> None:
        author = message.author

        if author.bot:
            return

        ctx = await self.get_context(message, cls=Context)

        # Only process global cooldowns when a command is invoked.
        if not ctx.valid:
            return

        if await self.is_owner(author):  # type: ignore
            await self.invoke(ctx)
            ctx.command.reset_cooldown(ctx)  # type: ignore
            return

        current = message.edited_at or message.created_at
        retry_after = self._spam_control.update_rate_limit(message, current.timestamp())

        if retry_after is not None:
            _LOG.warning(
                "%s (ID %s) is spamming in %s (ID: %s), retry_after: %.2fs",
                author,
                author.id,
                message.channel,
                message.channel.id,
                retry_after
            )
            return

        await self.invoke(ctx)

    async def on_command_error(self, ctx: Context, error: commands.CommandError) -> None:
        ignored = (
            commands.CommandNotFound,
            commands.DisabledCommand,
            commands.NoPrivateMessage,
            commands.PrivateMessageOnly,
        )

        if isinstance(error, ignored) or hasattr(error, "handled__"):
            return

        if isinstance(error, (commands.CommandInvokeError, commands.ConversionError)):
            ctx._refund_cooldown_token()
            return

        if isinstance(error, commands.MissingRequiredArgument):
            ctx._refund_cooldown_token()

            msg = f"Missing required argument: `{error.param.name}`."
            param_match = re.search(
                fr"<{error.param.name}(?:\.{{3}})?>",
                f"{ctx.command.qualified_name} {ctx.command.signature}"  # type: ignore
            )

            # Command signature may not be in a format we expect.
            if param_match is not None:
                start, end = param_match.span()
                msg += f"\n```\n{param_match.string}\n{'^' * (end - start):>{end}}```"

            await ctx.send(msg)
        elif isinstance(error, commands.MissingRequiredFlag):
            ctx._refund_cooldown_token()
            await ctx.send(f"`{error.flag.name}` is a required flag that is missing.")
        elif isinstance(error, commands.MissingFlagArgument):
            ctx._refund_cooldown_token()
            await ctx.send(f"The `{error.flag.name}` flag requires a value.")
        elif isinstance(error, commands.TooManyFlags):
            ctx._refund_cooldown_token()

            flag = error.flag
            await ctx.send(f"The `{flag.name}` flag takes a maximum of {flag.max_args} value(s).")
        elif isinstance(error, (commands.BadArgument, commands.BadUnionArgument)):
            ctx._refund_cooldown_token()
            await ctx.send("Bad argument: Please double-check your input arguments and try again.")
        elif isinstance(error, commands.ArgumentParsingError):
            ctx._refund_cooldown_token()
            await ctx.send(f"An error occurred while processing your arguments: {error}")
        elif isinstance(error, commands.CommandOnCooldown):
            await ctx.send(f"You are on cooldown. Try again in **{error.retry_after:.2f}** seconds.")
        elif isinstance(error, commands.MissingPermissions):
            perms = [
                p.replace('_', ' ').replace('guild', 'server').title()
                for p in error.missing_permissions
            ]

            await ctx.send(f"You need the `{human_join(perms)}` permission(s) to use that command.")
        elif isinstance(error, commands.BotMissingPermissions):
            perms = [
                p.replace('_', ' ').replace('guild', 'server').title()
                for p in error.missing_permissions
            ]

            await ctx.send(f"I need the `{human_join(perms)}` permission(s) to execute that command.")
        elif isinstance(error, commands.NotOwner):
            await ctx.send("Huh? You're not one of my higher-ups! Scram, skid!")
        elif isinstance(error, HTTPRequestFailed):
            await ctx.send(f"HTTP request failed with status code {error.status} {error.reason}")
