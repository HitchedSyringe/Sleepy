"""
© Copyright 2018-2020 HitchedSyringe, All Rights Reserved.

Redistributing, using or owning a copy of this software without explicit permissions
is against these licensing terms, your license(s) to this software can be revoked at
any time without explicit notice beforehand and at the time of revocation.
Your license is non-transferrable, the terms of this license only permit you to do the
following; Create pull requests and make modifications to this repository.

"""


__all__ = (
    "has_permissions",
    "has_guild_permissions",
    "bot_has_permissions",
    "bot_has_guild_permissions",
    "is_guild_manager",
    "is_guild_admin",
    "manager_or_permissions",
    "admin_or_permissions",
    "is_in_channels",
    "is_in_guilds",
    "are_users",
)


from discord.ext import commands


# (Mostly) based on a "just works" basis.


def _check_permissions(member, permissions: dict, channel=None, *, check=all):
    """|coro|

    Checks the user's permissions.
    For internal use only.

    Parameters
    ----------
    member: :class:`discord.Member`
        The member to check permissions for.
    permissions: :class:`dict`
        A dictionary of the specified permissions.
        This dictionary has :class:`str` keys and :class:`bool` values,
        Where ``True`` indicates a permission to check for.
    channel: Optional[:class:`discord.abc.GuildChannel`]
        The guild channel to get the member's permissions from.
        If no channel is specified, then the member's guild permissions are retrieved instead.
    *, check:
        A function that returns a boolean-like result.

    Returns
    -------
    :class:`bool`
        Whether or not the user has any or all of the specified permissions.
    """
    if channel:
        member_permissions = member.permissions_in(channel)
    else:
        member_permissions = member.guild_permissions

    return check(getattr(member_permissions, name, None) == value for name, value in permissions.items())


def has_permissions(*, check=all, **permissions):
    """Similar to :func:`commands.has_permissions` but allows for customised checking.

    .. note::

        The ``predicate`` attribute for this function is **not** a coroutine.
        This **always** returns ``True`` if you're the bot owner.
    """
    def predicate(ctx: commands.Context):
        if ctx.author.id in ctx.bot.owner_ids:
            return True

        if not _check_permissions(ctx.author, permissions, ctx.channel, check=check):
            raise commands.MissingPermissions(permissions)
        return True
    return commands.check(predicate)


def has_guild_permissions(*, check=all, **permissions):
    """Similar to :func:`commands.has_guild_permissions` but allows for customised checking.

    .. note::

        The ``predicate`` attribute for this function is **not** a coroutine.
        This **always** returns ``True`` if you're the bot owner.
    """
    def predicate(ctx: commands.Context):
        if ctx.guild is None:
            raise commands.NoPrivateMessage()

        if ctx.author.id in ctx.bot.owner_ids:
            return True

        if not _check_permissions(ctx.author, permissions, None, check=check):
            raise commands.MissingPermissions(permissions)
        return True
    return commands.check(predicate)


def bot_has_permissions(*, check=all, **permissions):
    """Similar to :func:`commands.bot_has_permissions` but allows for customised checking.

    .. note::

        The ``predicate`` attribute for this function is **not** a coroutine.
    """
    def predicate(ctx: commands.Context):
        if not _check_permissions(ctx.me, permissions, ctx.channel, check=check):
            raise commands.BotMissingPermissions(permissions)
        return True
    return commands.check(predicate)


def bot_has_guild_permissions(*, check=all, **permissions):
    """Similar to :func:`commands.bot_has_guild_permissions` but allows for customised checking.

    .. note::

        The ``predicate`` attribute for this function is **not** a coroutine.
    """
    def predicate(ctx: commands.Context):
        if ctx.guild is None:
            raise commands.NoPrivateMessage()

        if not _check_permissions(ctx.me, permissions, None, check=check):
            raise commands.BotMissingPermissions(permissions)
        return True
    return commands.check(predicate)


def is_guild_manager():
    """A :func:`.check` that checks if the member has the Manage Guild permission.

    .. note::

        The ``predicate`` attribute for this function is **not** a coroutine.
        This **always** returns ``True`` if you're the bot owner.
        This does **not** account for channel overrides.
    """
    def predicate(ctx: commands.Context):
        return has_guild_permissions(check=all, manage_guild=True).predicate(ctx)
    return commands.check(predicate)


def is_guild_admin():
    """A :func:`.check` that checks if the member has the Administrator permission.

    .. note::

        The ``predicate`` attribute for this function is **not** a coroutine.
        This **always** returns ``True`` if you're the bot owner.
        This does **not** account for channel overrides.
    """
    def predicate(ctx: commands.Context):
        return has_guild_permissions(check=all, administrator=True).predicate(ctx)
    return commands.check(predicate)


def manager_or_permissions(**permissions):
    """A :func:`.check` that checks if the member has the Manage Guild permission
    or any of the specified guild-level permissions.

    .. note::

        The ``predicate`` attribute for this function is **not** a coroutine.
        This **always** returns ``True`` if you're the bot owner.
        This does **not** account for channel overrides.
    """
    def predicate(ctx: commands.Context):
        return has_guild_permissions(check=any, manage_guild=True, **permissions).predicate(ctx)
    return commands.check(predicate)


def admin_or_permissions(**permissions):
    """A :func:`.check` that checks if the member has the Administrator permission
    or any of the specified guild-level permissions.

    .. note::

        The ``predicate`` attribute for this function is **not** a coroutine.
        This **always** returns ``True`` if you're the bot owner.
        This does **not** account for channel overrides.
    """
    def predicate(ctx: commands.Context):
        return has_guild_permissions(check=any, administrator=True, **permissions).predicate(ctx)
    return commands.check(predicate)


def is_in_channels(*channel_ids: int):
    """A :func:`.check` that checks if the command was invoked in any of the specified channels.

    .. note::

        The ``predicate`` attribute for this function is **not** a coroutine.
        This **always** returns ``True`` if you're the bot owner.
    """
    def predicate(ctx: commands.Context):
        return ctx.channel.id in channel_ids or ctx.author.id in ctx.bot.owner_ids
    return commands.check(predicate)


def is_in_guilds(*guild_ids: int):
    """A :func:`.check` that checks if the command was invoked in any of the specified guilds.

    .. note::

        The ``predicate`` attribute for this function is **not** a coroutine.
        This **always** returns ``True`` if you're the bot owner.
    """
    def predicate(ctx: commands.Context):
        if ctx.guild is None:
            raise commands.NoPrivateMessage()

        return ctx.guild.id in guild_ids or ctx.author.id in ctx.bot.owner_ids
    return commands.check(predicate)


def are_users(*user_ids: int):
    """A :func:`.check` that checks if the command was invoked by any of the specified users.

    .. note::

        The ``predicate`` attribute for this function is **not** a coroutine.
        This **always** returns ``True`` if you're the bot owner.
    """
    def predicate(ctx: commands.Context):
        return ctx.author.id in user_ids or ctx.author.id in ctx.bot.owner_ids
    return commands.check(predicate)
