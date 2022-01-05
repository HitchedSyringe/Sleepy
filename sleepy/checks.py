"""
Copyright (c) 2018-present HitchedSyringe

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""


__all__ = (
    "BotMissingAnyPermissions",
    "MissingAnyPermissions",
    "are_users",
    "bot_has_any_guild_permissions",
    "bot_has_any_permissions",
    "guild_admin_or_permissions",
    "guild_manager_or_permissions",
    "has_guild_permissions",
    "has_permissions",
    "is_guild_admin",
    "is_guild_manager",
    "is_guild_owner",
    "is_in_channels",
    "is_in_guilds",
)


from typing import Any, Callable, Dict, List, TypeVar

from discord import Permissions
from discord.ext import commands

from .utils import human_join


T = TypeVar("T")


class MissingAnyPermissions(commands.CheckFailure):
    """Exception raised when the command invoker lacks
    any of the permissions specified to run a command.

    This inherits from :exc:`commands.CheckFailure`.

    .. versionadded:: 3.0

    Attributes
    -----------
    missing_permissions: list[:class:`str`]
        The permissions that the command invoker is
        missing. These are the parameters passed to
        :func:`has_permissions`.
    """

    def __init__(self, missing_permissions: List[str], *args: Any) -> None:
        self.missing_permissions: List[str] = missing_permissions

        missing = [
            p.replace("_", " ").replace("guild", "server").title()
            for p in missing_permissions
        ]

        super().__init__(
            f"You are missing either {human_join(missing, joiner='or')} to run this command.",
            *args
        )


class BotMissingAnyPermissions(commands.CheckFailure):
    """Exception raised when the bot's member lacks any
    of the permissions specified to run a command.

    This inherits from :exc:`commands.CheckFailure`.

    .. versionadded:: 3.0

    Attributes
    -----------
    missing_permissions: list[:class:`str`]
        The permissions that the bot's member is
        missing. These are the parameters passed
        to :func:`bot_has_any_permissions`.
    """
    def __init__(self, missing_permissions: List[str], *args: Any) -> None:
        self.missing_permissions: List[str] = missing_permissions

        missing = [
            p.replace("_", " ").replace("guild", "server").title()
            for p in missing_permissions
        ]

        super().__init__(
            f"Bot requires either {human_join(missing, joiner='or')} to run this command.",
            *args
        )


def _has_any_permissions(permissions: Permissions, to_check: Dict[str, bool], /) -> bool:
    return any(getattr(permissions, n, None) == v for n, v in to_check.items())


def has_permissions(*, check_any: bool = False, **permissions: bool) -> Callable[[T], T]:
    """Similar to :func:`commands.has_permissions` except
    allows the option to check for either all or any given
    permissions.

    If ``check_any`` is ``True``, then this check will only
    succeed if the user has at least **one** of the given
    permissions. Otherwise, :exc:`.MissingAnyPermissions`,
    which is inherited from :exc:`commands.CheckFailure`,
    is raised.

    .. versionchanged:: 3.0

        * Replaced the `check` kwarg with `check_any`, which
          now takes a :class:`bool` instead of a callable.
        * Raise :exc:`.MissingAnyPermissions` instead of the
          generic :exc:`commands.CheckFailure` if `check_any`
          is ``True`` and the user has none of the specified
          permissions.

    .. versionchanged:: 3.2
        Raise :exc:`TypeError` for passing invalid permissions.

    Parameters
    ----------
    check_any: :class:`bool`
        Whether or not to check if the user has **ANY** of
        the given permissions. ``False`` denotes checking
        for **ALL** of the given permissions.
        Defaults to ``False``.
    permissions: Any
        An argument list of permissions to check for.

    Raises
    ------
    TypeError
        One or more permissions given were invalid.
    :exc:`commands.MissingPermissions`
        The user was missing one of the given permissions.
    :exc:`MissingAnyPermissions`
        The user was missing all of the given permissions.
        This only applies if ``check_any`` is ``True``.
    """
    if invalid := set(permissions) - set(Permissions.VALID_FLAGS):
        raise TypeError(f"Invalid permission(s): {', '.join(invalid)}")

    async def predicate(ctx: commands.Context) -> bool:
        if await ctx.bot.is_owner(ctx.author):
            return True

        if not check_any:
            return commands.has_permissions(**permissions).predicate

        channel_permissions = ctx.channel.permissions_for(ctx.author)  # type: ignore

        if not _has_any_permissions(channel_permissions, permissions):
            raise MissingAnyPermissions(list(permissions))

        return True

    return commands.check(predicate)


def has_guild_permissions(*, check_any: bool = False, **permissions: bool) -> Callable[[T], T]:
    """Similar to :func:`has_permissions`, but operates on
    guild-wide permissions instead of the current channel
    permissions.

    .. versionchanged:: 3.0

        * Replaced the `check` kwarg with `check_any`, which
          now takes a :class:`bool` instead of a callable.
        * Raise :exc:`.MissingAnyPermissions` instead of the
          generic :exc:`commands.CheckFailure` if `check_any`
          is ``True`` and the user has none of the specified
          permissions.

    .. versionchanged:: 3.2
        Raise :exc:`TypeError` for passing invalid permissions.

    Parameters
    ----------
    check_any: :class:`bool`
        Whether or not to check if the user has **ANY** of
        the given permissions. ``False`` denotes checking
        for **ALL** of the given permissions.
        Defaults to ``False``.
    permissions: Any
        An argument list of permissions to check for.

    Raises
    ------
    TypeError
        One or more permissions given were invalid.
    :exc:`commands.MissingPermissions`
        The user was missing one of the given permissions.
    :exc:`.MissingAnyPermissions`
        The user was missing all of the given permissions.
        This only applies if ``check_any`` is ``True``.
    :exc:`commands.NoPrivateMessage`
        The command was executed in a private message.
    """
    if invalid := set(permissions) - set(Permissions.VALID_FLAGS):
        raise TypeError(f"Invalid permission(s): {', '.join(invalid)}")

    async def predicate(ctx: commands.Context) -> bool:
        if ctx.guild is None:
            raise commands.NoPrivateMessage()

        if await ctx.bot.is_owner(ctx.author):
            return True

        if not check_any:
            return commands.has_guild_permissions(**permissions).predicate

        guild_permissions = ctx.author.guild_permissions  # type: ignore

        if not _has_any_permissions(guild_permissions, permissions):
            raise MissingAnyPermissions(list(permissions))

        return True

    return commands.check(predicate)


def bot_has_any_permissions(**permissions: bool) -> Callable[[T], T]:
    """Similar to :func:`commands.bot_has_permissions`,
    but checks if the bot's member has **ANY** of the
    given permissions.

    This raises :exc:`BotMissingAnyPermissions` if the
    bot is missing all of the given permissions.

    .. versionadded:: 3.0

    .. versionchanged:: 3.2
        Raise :exc:`TypeError` for passing invalid permissions.

    Parameters
    ----------
    permissions: Any
        An argument list of permissions to check for.

    Raises
    ------
    TypeError
        One or more permissions given were invalid.
    :exc:`BotMissingAnyPermissions`
        The bot was missing all of the given permissions.
    """
    if invalid := set(permissions) - set(Permissions.VALID_FLAGS):
        raise TypeError(f"Invalid permission(s): {', '.join(invalid)}")

    def predicate(ctx: commands.Context) -> bool:
        channel_permissions = ctx.channel.permissions_for(ctx.me)  # type: ignore

        if not _has_any_permissions(channel_permissions, permissions):
            raise BotMissingAnyPermissions(list(permissions))

        return True

    return commands.check(predicate)


def bot_has_any_guild_permissions(**permissions: bool) -> Callable[[T], T]:
    """Similar to :func:`bot_has_any_permissions`, but
    operates on guild-wide permissions instead of the
    current channel permissions.

    .. versionadded:: 3.0

    .. versionchanged:: 3.2
        Raise :exc:`TypeError` for passing invalid permissions.

    Parameters
    ----------
    permissions: Any
        An argument list of permissions to check for.

    Raises
    ------
    TypeError
        One or more permissions given were invalid.
    :exc:`BotMissingAnyPermissions`
        The bot was missing all of the given permissions.
    :exc:`commands.NoPrivateMessage`
        The command was executed in a private message.
    """
    if invalid := set(permissions) - set(Permissions.VALID_FLAGS):
        raise TypeError(f"Invalid permission(s): {', '.join(invalid)}")

    def predicate(ctx: commands.Context) -> bool:
        if ctx.guild is None:
            raise commands.NoPrivateMessage()

        guild_permissions = ctx.me.guild_permissions  # type: ignore

        if not _has_any_permissions(guild_permissions, permissions):
            raise BotMissingAnyPermissions(list(permissions))

        return True

    return commands.check(predicate)


def is_guild_owner() -> Callable[[T], T]:
    """A :func:`commands.check` that checks if the user
    invoking this command is the guild owner.

    .. versionadded:: 3.0

    Raises
    ------
    :exc:`commands.NoPrivateMessage`
        The command was executed in a private message.
    """

    async def predicate(ctx: commands.Context) -> bool:
        if ctx.guild is None:
            raise commands.NoPrivateMessage()

        if await ctx.bot.is_owner(ctx.author):
            return True

        return ctx.author.id == ctx.guild.owner_id

    return commands.check(predicate)


def is_guild_manager() -> Callable[[T], T]:
    """A :func:`commands.check` that checks if the
    user invoking this command has the ``manage_guild``
    permission.

    Equivalent to: ::

        has_guild_permissions(manage_guild=True)

    .. versionchanged:: 2.0
        Renamed to ``is_guild_manager``.

    Raises
    ------
    :exc:`commands.MissingPermissions`
        The user does not have the ``manage_guild``
        permission.
    :exc:`commands.NoPrivateMessage`
        The command was executed in a private message.
    """
    return has_guild_permissions(manage_guild=True)


def is_guild_admin() -> Callable[[T], T]:
    """Same as :func:`is_guild_manager`, except checks
    for the ``administrator`` permission instead.

    Equivalent to: ::

        has_guild_permissions(administrator=True)

    .. versionchanged:: 2.0
        Renamed to ``is_guild_admin``.

    Raises
    ------
    :exc:`commands.MissingPermissions`
        The user does not have the ``administrator``
        permission.
    :exc:`commands.NoPrivateMessage`
        The command was executed in a private message.
    """
    return has_guild_permissions(administrator=True)


def guild_manager_or_permissions(**permissions: bool) -> Callable[[T], T]:
    """A :func:`commands.check` that checks if the
    user invoking this command has the ``manage_guild``
    permission or any of the given permissions.

    Equivalent to: ::

        has_guild_permissions(check_any=True, manage_guild=True, **permissions)

    .. versionchanged:: 2.0
        Renamed to ``manager_or_permissions``.

    .. versionchanged:: 3.0

        * Renamed to ``guild_manager_or_permissions``.
        * Raise :exc:`.MissingAnyPermissions` instead of the
          generic :exc:`commands.CheckFailure`.

    .. versionchanged:: 3.2
        Raise :exc:`TypeError` for passing invalid permissions.

    Parameters
    ----------
    permissions: Any
        An argument list of permissions to check for.

    Raises
    ------
    TypeError
        One or more permissions given were invalid.
    :exc:`.MissingAnyPermissions`
        The user was missing all of the given permissions.
    """
    return has_guild_permissions(check_any=True, manage_guild=True, **permissions)


def guild_admin_or_permissions(**permissions: bool) -> Callable[[T], T]:
    """Similar to :func:`guild_manager_or_permissions`,
    except checks for the ``administrator`` permission
    or any of the given permissions instead.

    Equivalent to: ::

        has_guild_permissions(check_any=True, administrator=True, **permissions)

    .. versionchanged:: 2.0
        Renamed to ``admin_or_permissions``.

    .. versionchanged:: 3.0

        * Renamed to ``guild_admin_or_permissions``.
        * Raise :exc:`.MissingAnyPermissions` instead of the
          generic :exc:`commands.CheckFailure`.

    .. versionchanged:: 3.2
        Raise :exc:`TypeError` for passing invalid permissions.

    Parameters
    ----------
    permissions: Any
        An argument list of permissions to check for.

    Raises
    ------
    TypeError
        One or more permissions given were invalid.
    :exc:`MissingAnyPermissions`
        The user was missing all of the given permissions.
    """
    return has_guild_permissions(check_any=True, administrator=True, **permissions)


def is_in_guilds(*guild_ids: int) -> Callable[[T], T]:
    """A :func:`commands.check` that checks if the user
    invoking this command is a member of any of the given
    guilds.

    Parameters
    ----------
    guild_ids: :class:`int`
        The guild IDs to check for.

    Raises
    ------
    :exc:`commands.NoPrivateMessage`
        The command was executed in a private message.
    """

    async def predicate(ctx: commands.Context) -> bool:
        if ctx.guild is None:
            raise commands.NoPrivateMessage()

        return ctx.guild.id in guild_ids or await ctx.bot.is_owner(ctx.author)

    return commands.check(predicate)


def is_in_channels(*channel_ids: int) -> Callable[[T], T]:
    """Same as :func:`is_in_guilds`, except checks if
    the user is invoking this command in any of the
    given channels.

    Parameters
    ----------
    channel_ids: :class:`int`
        The channel IDs to check for.
    """

    async def predicate(ctx: commands.Context) -> bool:
        return ctx.channel.id in channel_ids or await ctx.bot.is_owner(ctx.author)

    return commands.check(predicate)


def are_users(*user_ids: int) -> Callable[[T], T]:
    """Same as :func:`is_in_guilds`, except checks if
    the user invoking this command is any of the given
    users.

    Parameters
    ----------
    user_ids: :class:`int`
        The user IDs to check for.
    """

    async def predicate(ctx: commands.Context) -> bool:
        return ctx.author.id in user_ids or await ctx.bot.is_owner(ctx.author)

    return commands.check(predicate)
