"""
Copyright (c) 2018-present HitchedSyringe

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""


from __future__ import annotations

# fmt: off
__all__ = (
    "Sleepy",
)
# fmt: on


import logging
import re
import traceback
from pathlib import Path
from typing import TYPE_CHECKING, Any, Generator, List, Mapping, Optional

import discord
from discord import Colour, Embed
from discord.ext import commands
from discord.utils import MISSING, cached_property, utcnow
from psutil import Process

from .context import Context
from .http import HTTPRequester, HTTPRequestFailed
from .utils import SOURCE_CODE_URL, find_extensions_in, human_join

if TYPE_CHECKING:
    from datetime import datetime

    from discord import AppInfo


_LOG: logging.Logger = logging.getLogger(__name__)


class Sleepy(commands.Bot):
    """The main Sleepy Discord bot class.

    Subclasses :class:`commands.Bot`.

    Parameters
    ----------
    config: Mapping[:class:`str`, Any]
        The loaded configuration values.

        .. versionadded:: 1.12

        .. versionchanged:: 3.0
            This is now a positional-only argument.

        .. versionchanged:: 3.3
            This is no longer a positional-only argument.
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
    config: Mapping[:class:`str`, Any]
        The bot's configuration values.

        .. versionadded:: 1.12
    extensions_directory: :class:`pathlib.Path`
        The directory the extensions are located in.
    http_requester: :class:`HTTPRequester`
        The bot's HTTP requester client.

        .. versionadded:: 1.10
    started_at: :class:`datetime.datetime`
        The bot's starting time as a UTC-aware datetime.

        .. versionadded:: 1.6

        .. versionchanged:: 2.1
            This is now set when ``ready`` rather than
            on initialization.

        .. versionchanged:: 3.0
            This is now set when logged in rather than
            on ``ready``.

        .. versionchanged:: 3.2
            This is now a UTC-aware datetime.

        .. versionchanged:: 3.3
            This now returns a :class:`datetime.datetime`.
    process: :class:`psutil.Process`
        The bot's OS process.

        .. versionadded:: 3.3
    """

    def __init__(self, config: Mapping[str, Any], *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

        if kwargs.get("case_insensitive_cogs"):
            # Accessing mangled attributes is considered bad practice,
            # but unfortunately, this is the good and only way.
            self._BotBase__cogs = commands.core._CaseInsensitiveDict()

        self.config: Mapping[str, Any] = config
        self.extensions_directory: Path = Path(config["extensions_directory"] or ".")
        self.http_requester: HTTPRequester = HTTPRequester(cache=kwargs.get("http_cache"))

        self.process: Process = MISSING
        self.started_at: datetime = MISSING

        # Cooldown mapping for people who excessively spam commands.
        self._spam_control: commands.CooldownMapping = (
            commands.CooldownMapping.from_cooldown(10, 12, commands.BucketType.user)
        )

    @cached_property
    def webhook(self) -> discord.Webhook:
        """:class:`discord.Webhook`: The bot's system webhook.

        .. versionadded:: 1.12

        .. versionchanged:: 2.1
            This is now a cached property.

        .. versionchanged:: 3.3
            Accessing this will now raise :exc:`RuntimeError` if there
            is no active HTTP requester session.
        """
        if self.http_requester.is_closed():
            raise RuntimeError("HTTP requester session is closed.")

        session = self.http_requester.session
        return discord.Webhook.partial(**self.config["discord_webhook"], session=session)

    @property
    def owner(self) -> Optional[discord.User]:
        """Optional[:class:`discord.User`]: The bot's owner.

        This first attempts to resolve the user using the owner IDs.
        If either the resolution attempt fails or no owner IDs were
        set, then the application information is used as a fallback.

        ``None`` is returned if both resolution attempts fail.

        .. versionadded:: 1.12

        .. versionchanged:: 3.0
            The bot's application info is now used as a fallback.
        """
        # We assume that one or the other is set, as enforced in __init__.
        if self.owner_id is not None:
            owner = self.get_user(self.owner_id)
        elif self.owner_ids and len(self.owner_ids) == 1:
            owner = self.get_user(next(iter(self.owner_ids)))
        else:
            owner = None

        if owner is None:
            app_info = self.application

            if app_info is not None:
                if app_info.team is None:
                    owner = app_info.owner
                else:
                    # :attr:`AppInfo.owner` is the team itself, so this
                    # is the only way of getting the application owner.
                    # We use :meth:`Bot.get_user` here for two reasons:
                    # * Consistency (i.e. returning :class:`discord.User`
                    #   instead of :class:`discord.TeamMember`)
                    # * :attr:`Team.owner` is O(n); this is O(1).
                    owner = self.get_user(app_info.team.owner_id)  # type: ignore

        return owner

    @property
    def owners(self) -> List[discord.User]:
        """List[:class:`discord.User`]: The bot's owners.

        This resolves the users using the owner IDs. If no owner IDs
        were set, then the application information is used as a
        fallback.

        Users that could not be resolved from the cache are excluded
        from the resulting list.

        .. versionadded:: 3.3
        """
        if self.owner_ids is not None:
            ids = set(self.owner_ids)
        elif self.owner_id is not None:
            ids = {self.owner_id}
        else:
            app_info = self.application

            if app_info is None:
                return []

            if app_info.team is None:
                ids = {app_info.owner.id}
            else:
                ids = {m.id for m in app_info.team.members}

        return [u for i in ids if (u := self.get_user(i)) is not None]

    async def _init_extensions(self) -> None:
        if self.config["enable_autoload"]:
            to_load = self.get_all_extensions()
        else:
            to_load = []
            exts_dir = "/".join(self.extensions_directory.parts)

            for ext in self.config["extensions_list"]:
                if ext.startswith("$/"):
                    ext = ext.replace("$/", f"{exts_dir}/", 1)

                if ext.endswith("/*"):
                    to_load.extend(find_extensions_in(Path(ext[:-1])))
                else:
                    to_load.append(".".join(ext.split("/")))

        total = 0
        loaded = 0

        for ext in to_load:
            total += 1

            try:
                await self.load_extension(ext)
            except (commands.ExtensionNotFound, ModuleNotFoundError):
                _LOG.warning("Extension '%s' was not found.", ext)
            except (commands.NoEntryPointError, commands.ExtensionAlreadyLoaded) as exc:
                _LOG.warning(exc)
            except commands.ExtensionFailed as exc:
                _LOG.warning("Failed to load extension '%s'.", ext, exc_info=exc.original)
            else:
                _LOG.debug("Loaded extension '%s'.", ext)
                logging.getLogger(ext).setLevel(logging.INFO)
                loaded += 1

        failed = total - loaded

        _LOG.info("Extensions: %s total; %s loaded; %s failed.", total, loaded, failed)

    def _populate_owner_information(self) -> None:
        owner_ids = set(self.config["owner_ids"])

        if not owner_ids or self.config["force_querying_owner_ids"]:
            # Should be fetched by the time we're here.
            app_info: AppInfo = self.application  # type: ignore

            if app_info.team is None:
                owner_ids.add(app_info.owner.id)
            else:
                owner_ids.update(m.id for m in app_info.team.members)

        if len(owner_ids) == 1:
            self.owner_id = owner_ids.pop()
        else:
            # If there's somehow no owner IDs, then I really
            # don't know if this is a bot we're dealing with.
            self.owner_ids = owner_ids

    async def setup_hook(self) -> None:
        from sys import version_info as python_version

        from aiohttp import __version__ as aiohttp_version

        from . import __version__

        # --- Populate general stuff. ---
        self.process = Process()
        self.started_at = utcnow()

        # --- Set up HTTP requester session. ---
        global_user_agent = (
            f"Sleepy-DiscordBot/{__version__} (+{SOURCE_CODE_URL})"
            f" Python/{python_version[0]}.{python_version[1]}"
            f" aiohttp/{aiohttp_version}"
        )

        await self.http_requester.start(headers={"User-Agent": global_user_agent})

        # --- Load configured extensions ---
        await self._init_extensions()

        # --- Populate owners if not initially set. ---
        if self.owner_id is None and not self.owner_ids:
            _LOG.debug("No owner IDs passed in '__init__', auto-detecting...")
            self._populate_owner_information()

        _LOG.info("Owner ID(s): %s", self.owner_id or self.owner_ids)
        _LOG.info("Sleepy %s booted successfully. Awaiting READY event...", __version__)

    def get_all_extensions(self) -> Generator[str, None, None]:
        """Returns a generator with the names of every recognized
        extension in the configured extensions directory.

        This is equivalent to passing :attr:`extensions_directory`
        in `.utils.find_extensions_in`.

        .. versionadded:: 3.0

        Yields
        ------
        :class:`str`
            The name of the recognized extension.
        """
        return find_extensions_in(self.extensions_directory)

    async def close(self) -> None:
        await self.http_requester.close()
        await super().close()

    async def on_ready(self) -> None:
        _LOG.info("Received a READY event.")

    async def on_resumed(self) -> None:
        _LOG.info("Received a RESUME event.")

    async def process_commands(self, message: discord.Message) -> None:
        author = message.author

        if author.bot:
            return

        ctx = await self.get_context(message, cls=Context)

        # Only process global cooldowns when a command is invoked.
        # This also has the side-effect of preventing CommandNotFound
        # from being raised.
        if not ctx.valid:
            return

        if await self.is_owner(author):
            await self.invoke(ctx)
            ctx.command.reset_cooldown(ctx)
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
                retry_after,
            )
            return

        await self.invoke(ctx)

    async def on_error(self, event_method: str, *args: Any, **kwargs: Any) -> None:
        p_args = "\n".join(f"[{i}] {a}" for i, a in enumerate(args)) or "N/A"
        k_args = "\n".join(f"{k}: {v}" for k, v in kwargs.items()) or "N/A"

        fmt = (
            'Unhandled exception in event handler "%s":'
            "\nPositional Arguments: --\n%s"
            "\nKeyword Arguments: --\n%s"
        )

        _LOG.exception(fmt, event_method, p_args, k_args)

        embed = Embed(
            title="Event Handler Error",
            description=f"```py\n{traceback.format_exc()}```",
            colour=Colour.dark_red(),
        )
        embed.set_author(name=event_method)

        embed.add_field(
            name="Positional Arguments", value=f"```py\n{p_args}```", inline=False
        )

        embed.add_field(
            name="Keyword Arguments", value=f"```py\n{k_args}```", inline=False
        )

        try:
            await self.webhook.send(embed=embed)
        except discord.HTTPException:
            pass

    async def on_command_error(self, ctx: Context, error: commands.CommandError) -> None:
        if isinstance(error, (commands.CommandInvokeError, commands.ConversionError)):
            ctx._refund_cooldown_token()
            return

        if (
            isinstance(error, (commands.DisabledCommand, commands.NoPrivateMessage))
            or ctx._already_handled_error
        ):
            return

        if isinstance(
            error, (commands.MissingRequiredArgument, commands.MissingRequiredAttachment)
        ):
            ctx._refund_cooldown_token()

            param = error.param
            msg = f"Missing required argument: `{param.name}`."
            sig = f"{ctx.command.qualified_name} {ctx.command.signature}"

            match = re.search(fr"<{param.name}(?: \(upload a file\)|\.{{3}})?>", sig)

            # Command signature may not be in a format we expect.
            if match is not None:
                start, end = match.span()
                msg += f"\n```\n{sig}\n{'^' * (end - start):>{end}}```"

            await ctx.send(msg)
        elif isinstance(error, commands.MissingRequiredFlag):
            ctx._refund_cooldown_token()
            await ctx.send(f"Missing required flag: `{error.flag.name}`.")
        elif isinstance(error, commands.MissingFlagArgument):
            ctx._refund_cooldown_token()
            await ctx.send(f"Flag `{error.flag.name}` requires an argument.")
        elif isinstance(error, commands.BadFlagArgument):
            ctx._refund_cooldown_token()
            await ctx.send(
                f"Invalid argument(s) for flag `{error.flag.name}`."
                "\nPlease double-check your input(s) and try again."
            )
        elif isinstance(error, commands.TooManyFlags):
            ctx._refund_cooldown_token()

            flag = error.flag

            await ctx.send(
                f"Too many arguments for flag `{flag.name}`"
                f" ({len(error.values)} > {flag.max_args})."
            )
        elif isinstance(error, (commands.BadArgument, commands.BadUnionArgument)):
            ctx._refund_cooldown_token()
            msg = "One or more of your command arguments were invalid."

            if ctx.current_parameter is not None:
                # This was likely raised while converting.
                msg = f"Invalid argument(s) for `{ctx.current_parameter.name}`."

            await ctx.send(f"{msg}\nPlease double-check your input(s) and try again.")
        elif isinstance(error, commands.ArgumentParsingError):
            ctx._refund_cooldown_token()
            await ctx.send(f"An error occurred while processing your input(s): {error}")
        elif isinstance(error, commands.CommandOnCooldown):
            await ctx.send(
                f"That command is on cooldown. Retry in **{error.retry_after:.2f}** second(s)."
            )
        elif isinstance(error, commands.MissingPermissions):
            perms = [
                p.replace('_', ' ').replace('guild', 'server').title()
                for p in error.missing_permissions
            ]

            await ctx.send(
                f"You need the `{human_join(perms)}` permission(s) to use that command."
            )
        elif isinstance(error, commands.BotMissingPermissions):
            perms = [
                p.replace('_', ' ').replace('guild', 'server').title()
                for p in error.missing_permissions
            ]

            await ctx.send(
                f"I need the `{human_join(perms)}` permission(s) to execute that command."
            )
        elif isinstance(error, commands.NotOwner):
            await ctx.send("You're not one of my higher-ups, scram!")
        elif isinstance(error, HTTPRequestFailed):
            await ctx.send(
                f"HTTP request failed with status code {error.status} {error.reason}"
            )
