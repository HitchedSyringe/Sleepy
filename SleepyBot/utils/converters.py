"""
© Copyright 2018-2020 HitchedSyringe, All Rights Reserved.

Redistributing, using or owning a copy of this software without explicit permissions
is against these licensing terms, your license(s) to this software can be revoked at
any time without explicit notice beforehand and at the time of revocation.
Your license is non-transferrable, the terms of this license only permit you to do the
following; Create pull requests and make modifications to this repository.

"""


__all__ = ("GuildChannelConverter", "ImageAssetConverter")


from inspect import Parameter
from typing import Optional

from discord import Asset, DiscordException, utils
from discord.ext import commands


class GuildChannelConverter(commands.Converter):
    """Converts to a :class:`discord.GuildChannel`.
    This does a guild-wide lookup.

    :exc:`commands.BadArgument` is raised if no channel is found.
    """

    @staticmethod
    async def convert(ctx: commands.Context, argument):
        if argument.isdigit():
            result = ctx.guild.get_channel(int(argument, base=10))
        else:
            def channel_check(chan):
                return chan.mention == argument or chan.name == argument

            result = utils.find(channel_check, ctx.guild.channels)

        if result is None:
            #raise commands.BadArgument(f'Channel "{argument}" not found.')
            raise commands.BadArgument("Invalid channel.")

        return result


async def _is_image_mimetype(session, url) -> bool:
    """Returns whether or not the given URL is an image URL.
    This checks via mimetype.
    For internal use only.

    Parameters
    ----------
    session: :class:`aiohttp.ClientSession`
        The client session used to make the HEAD request.
    url:
        The URL to check the mimetype for.

    Returns
    -------
    :class:`bool`
        Whether or not the URL is an image URL.
    """
    try:
        async with session.head(url) as response:
            return response.headers["Content-Type"].startswith("image/")
    except Exception:
        return False


class ImageAssetConverter(commands.Converter):
    """Converts to a :class:`discord.Asset`, while ensuring that the asset is an image.
    This also allows checking for attachments.

    :exc:`commands.BadArgument` is raised if no asset could be resolved from the given URL.
    """

    @staticmethod
    async def convert(ctx: commands.Context, argument):
        url = argument.strip("<>")

        if await _is_image_mimetype(ctx.session, url):
            return Asset(ctx.bot._connection, url)

        raise commands.BadArgument("Not a valid Image attachment or link.")


# Most of this Asset modifying stuff was derived from discord-ext-alternatives by NCPlayz.
Asset.__str__ = lambda x: '' if x._url is None else (x._url if x._url.startswith("http") else x.BASE + x._url)

# Although this isn't necessary, it's probably better to just make it work with the new str() behaviour.
Asset.__len__ = lambda x: len(str(x))


async def _new_read(self):
    if not self._url:
        raise DiscordException('Invalid asset (no URL provided)')

    if self._state is None:
        raise DiscordException('Invalid state (no ConnectionState provided)')

    return await self._state.http.get_from_cdn(str(self))


Asset.read = _new_read


# Mess with the commands transform in order to ensure the attachments functionality works with the AssetConverter.
_old_transform = commands.Command.transform


async def _new_transform(self, ctx: commands.Context, param):
    if param.annotation is ImageAssetConverter and param.default is param.empty and ctx.message.attachments:
        url = ctx.message.attachments[0].url

        if await _is_image_mimetype(ctx.session, url):
            param = Parameter(
                name=param.name,
                kind=param.kind,
                default=Asset(ctx.bot._connection, url),
                annotation=Optional[param.annotation]
            )

    return await _old_transform(self, ctx, param)


commands.Command.transform = _new_transform
