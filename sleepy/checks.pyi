from typing import Any

from discord.ext import commands
from discord.ext.commands.core import _CheckDecorator


class MissingAnyPermissions(commands.CheckFailure):

    missing_perms: list[str]

    def __init__(self, missing_perms: list[str], *args: Any) -> None: ...


class BotMissingAnyPermissions(commands.CheckFailure):

    missing_perms: list[str]

    def __init__(self, missing_perms: list[str], *args: Any) -> None: ...


def has_permissions(
    *,
    check_any: bool = ...,
    **permissions: bool
) -> _CheckDecorator: ...


def has_guild_permissions(
    *,
    check_any: bool = ...,
    **permissions: bool
) -> _CheckDecorator: ...


def bot_has_any_permissions(**permissions: bool) -> _CheckDecorator: ...


def bot_has_any_guild_permissions(**permissions: bool) -> _CheckDecorator: ...


def is_guild_owner() -> _CheckDecorator: ...


def is_guild_manager() -> _CheckDecorator: ...


def is_guild_admin() -> _CheckDecorator: ...


def guild_manager_or_permissions(**permissions: bool) -> _CheckDecorator: ...


def guild_admin_or_permissions(**permissions: bool) -> _CheckDecorator: ...


def can_start_menu(*, check_embed: bool = ...) -> _CheckDecorator: ...


def is_in_guilds(*guild_ids: int) -> _CheckDecorator: ...


def is_in_channels(*channel_ids: int) -> _CheckDecorator: ...


def are_users(*user_ids: int) -> _CheckDecorator: ...
