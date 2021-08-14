from collections.abc import Callable
from typing import Optional

import discord
from discord.abc import GuildChannel
from discord.ext import commands

from .context import Context


class ImageAssetConversionFailure(commands.BadArgument):

    argument: str

    def __init__(self, argument: str) -> None: ...


class ImageAssetTooLarge(commands.BadArgument):

    argument: str
    filesize: int
    max_filesize: int

    def __init__(
        self,
        argument: str,
        filesize: int,
        max_filesize: int
    ) -> None: ...


class GuildChannelConverter(commands.IDConverter):

    async def convert(
        self,
        ctx: commands.Context,
        argument: str
    ) -> GuildChannel: ...


class ImageAssetConverter(commands.Converter):

    max_filesize = Optional[int]

    def __init__(
        self,
        *,
        max_filesize: Optional[int] = ...
    ) -> None: ...

    async def convert(  # type: ignore[override]
        self,
        ctx: Context,
        argument: str
    ) -> discord.Asset: ...


def real_float(*, max_decimal_places: int) -> Callable[[str], float]: ...
