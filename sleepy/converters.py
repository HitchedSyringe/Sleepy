"""
Copyright (c) 2018-present HitchedSyringe

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""


__all__ = (
    "GuildChannelConverter",
    "ImageAssetConversionFailure",
    "ImageAssetConverter",
    "ImageAssetTooLarge",
    "real_float",
)


import re
from inspect import Parameter
from typing import Optional

from discord import Asset, DiscordException, utils
from discord.ext import commands


class ImageAssetConversionFailure(commands.BadArgument):
    """Exception raised when the argument provided
    fails to convert to a :class:`discord.Asset` image.

    This inherits from :exc:`commands.BadArgument`.

    .. versionadded:: 3.0

    Attributes
    ----------
    argument: :class:`str`
        The argument supplied by the caller that could
        not be converted.
    """

    def __init__(self, argument):
        self.argument = argument

        super().__init__(f'Couldn\'t convert "{argument}" to Asset.')


class ImageAssetTooLarge(commands.BadArgument):
    """Exception raised when the argument provided
    exceeds the maximum conversion filesize.

    This inherits from :exc:`commands.BadArgument`.

    .. versionadded:: 3.0

    Attributes
    ----------
    argument: :class:`str`
        The argument supplied by the caller that exceeded
        the maximum conversion filesize.
    filesize: :class:`int`
        The argument's filesize in bytes.
    max_filesize: :class:`int`
        The converter's maximum filesize in bytes.
    """

    def __init__(self, argument, filesize, max_filesize):
        self.argument = argument
        self.filesize = filesize
        self.max_filesize = max_filesize

        super().__init__(
            f'"{argument}" exceeds the maximum filesize. ({filesize}/{max_filesize} B)'
        )


class GuildChannelConverter(commands.IDConverter):
    """Converts to a :class:`discord.abc.GuildChannel`.

    All lookups are via the local guild. If in a DM context,
    then the lookup is done by the global cache.

    The lookup strategy is as follows (in order):

    1. Lookup by ID.
    2. Lookup by mention.
    3. Lookup by name

    .. versionadded:: 2.0

    .. versionchanged:: 3.0
        Allow this converter to do a global cache lookup if
        in a DM context.
    """

    async def convert(self, ctx, argument):
        id_match = self._get_id_match(argument) or re.match(r'<#([0-9]+)>$', argument)
        guild = ctx.guild

        if id_match is None:
            if guild is not None:
                result = utils.get(guild.channels, name=argument)
            else:
                result = utils.get(ctx.bot.get_all_channels(), name=argument)
        else:
            channel_id = int(id_match.group(1))

            if guild is not None:
                result = guild.get_channel(channel_id)
            else:
                result = ctx.bot.get_channel(channel_id)

        if result is None:
            raise commands.ChannelNotFound(argument)

        return result


class ImageAssetConverter(commands.Converter):
    """Converts a user, custom emoji, image attachment,
    or image URL to a :class:`discord.Asset`.

    .. note::

        Due to an implementation detail, attachment conversion
        takes precedence over the other conversion types. This
        means that passed arguments will attempt to convert to
        attachments first before attemping to convert to users,
        emojis, or URLs.

    .. warning::

        Due to a limitation with the argument parser, only the
        first attachment in the message will be converted. This
        means that the attachment conversion behaviour will not
        work with the :class:`commands.Greedy` converter or the
        positional vars handling (i.e. *args).

    .. warning::

        Due to limitations with the checks, attachments and URLs
        are not guaranteed to be valid images.

    .. versionadded:: 2.0

    .. versionchanged:: 3.0

        * Raise :exc:`.ImageAssetConversionFailure` or
          :exc:`.ImageAssetTooLarge` instead of generic
          :exc:`commands.BadArgument`.
        * Raise :exc:`commands.TooManyArguments` if
          :attr:`Command.ignore_extra` is `False` and
          more than one attachment is supplied.
        * Added support for converting custom emojis.
        * Attachments and URLs are now checked for their
          filesize.

    Parameters
    ----------
    max_filesize: Optional[:class:`int`]
        The maximum filesize, in bytes, an attachment or URL
        can be. This will raise :exc:`.ImageAssetTooLarge` if
        an attachment or URL exceeds this filesize limit.
        ``None`` (the default) denotes disabling filesize
        checking.

        .. danger::

            Disabling filesize checking leaves you vulnerable to
            a denial-of-service attack. Unless you are doing your
            own internal checks, it is **highly recommended** to
            set a maximum filesize.

        .. note::

            Users and emojis always skip this check regardless of
            this setting.

        .. versionadded:: 3.0

    Attributes
    ----------
    max_filesize: Optional[:class:`int`]
        The maximum conversion filesize in bytes.
        ``None`` if this check is disabled.

        .. versionadded:: 3.0
    """

    def __init__(self, *, max_filesize=None):
        if max_filesize is not None and max_filesize <= 0:
            raise ValueError(f"invalid max_filesize {max_filesize} (must be > 0).")

        self.max_filesize = max_filesize

    async def convert(self, ctx, argument):
        try:
            user = await commands.UserConverter().convert(ctx, argument)
        except commands.UserNotFound:
            pass
        else:
            return user.avatar_url_as(static_format="png")

        try:
            emoji = await commands.PartialEmojiConverter().convert(ctx, argument)
        except commands.PartialEmojiConversionFailure:
            pass
        else:
            return emoji.url

        # NOTE: Unicode emojis can't be supported here due to
        # some ambiguities with emojis consisting of between
        # 2-4 characters, which ord() cannot take, meaning we
        # can't really use the twemoji cdn.

        url = argument.strip("<>")

        try:
            resp = await ctx.session.head(url, raise_for_status=True)
        except:
            raise ImageAssetConversionFailure(argument) from None

        if "image/" not in resp.content_type:
            raise ImageAssetConversionFailure(argument)

        if (
            self.max_filesize is not None
            and (filesize := int(resp.headers["Content-Length"])) > self.max_filesize
        ):
            raise ImageAssetTooLarge(url, filesize, self.max_filesize)

        return Asset(ctx.bot._connection, url)


def real_float(*, max_decimal_places):
    """Similar to the :class:`float` converter except
    this does not convert to NaN or Infinity and allows
    for limiting decimal places.

    This returns a callable that can be used as an
    argument converter.

    .. versionadded:: 3.0

    Parameters
    ----------
    max_decimal_places: :class:`int`
        The maximum amount of decimal places to allow
        for given float values.

    Returns
    -------
    Callable[[:class:`str`], :class:`float`]
        The converter callable.

    Raises
    ------
    TypeError
        ``max_decimal_places`` was not a :class:`int`.
    ValueError
        An invalid ``max_decimal_places`` value was given.
    """
    if max_decimal_places <= 0:
        raise ValueError(f"invalid max_decimal_places {max_decimal_places} (must be > 0).")

    def converter(arg):
        if arg.lower() in ("nan", "inf", "infinity") or arg.count(".") > 1:
            raise commands.BadArgument(f'Couldn\'t convert "{arg}" to float.')

        if (places := len(arg.partition(".")[2])) > max_decimal_places:
            raise commands.BadArgument(
                f"Too many decimal places. ({places} > {max_decimal_places})"
            )

        try:
            return float(arg)
        except ValueError:
            raise commands.BadArgument(f'Couldn\'t convert "{arg}" to float.') from None

    return converter


# Private since I only plan on using these for a
# handful of commands. I have no plans for these
# to be publicised since their behaviour is too
# confusing to document properly in addition to
# the countless ambiguities associated.
def _pseudo_bool_flag(*names):

    def convert(value):
        if value not in names:
            raise commands.BadArgument("Invalid flag.")

        return True

    return convert


def _pseudo_argument_flag(*names, **kwargs):
    sep = kwargs.get("separator") or "="

    def convert(value):
        try:
            flag, value = value.split(sep, 1)
        except ValueError:
            raise commands.BadArgument(
                "Flag and argument must be separated by " + sep
            ) from None

        # If flag is an empty string, then it probably means
        # that the separator is the flag name. I know this may
        # potentially introduce a bunch of ambiguity, but I'll
        # allow it for now since at least one command depends
        # on this behaviour.
        if flag and flag not in names:
            raise commands.BadArgument("Invalid flag.")

        return value

    return convert


def _new_asset_to_str(self):
    if not self._url:
        return ""

    if self._url.startswith("http"):
        return self._url

    return self.BASE + self._url


Asset.__str__ = _new_asset_to_str
Asset.__len__ = lambda self: len(str(self)) if self._url else 0


async def _new_asset_read(self):
    if not self._url:
        raise DiscordException("Invalid asset (no URL provided)")

    if self._state is None:
        raise DiscordException("Invalid state (no ConnectionState provided)")

    return await self._state.http.get_from_cdn(str(self))


Asset.read = _new_asset_read


_old_command_transform = commands.Command.transform


async def _new_command_transform(self, ctx, param):
    if isinstance(param.annotation, type):
        converter_type = param.annotation
    else:
        converter_type = type(param.annotation)

    if issubclass(converter_type, ImageAssetConverter) and ctx.message.attachments:
        # Figured I should include this here for completeness.
        if not self.ignore_extra and len(ctx.message.attachments) > 1:
            raise commands.TooManyArguments(
                "Too many attachments passed to " + self.qualified_name
            )

        attachment = ctx.message.attachments[0]
        mime = attachment.content_type
        url = attachment.url

        if mime is None or "image/" not in mime:
            raise ImageAssetConversionFailure(url)

        max_filesize = getattr(param.annotation, "max_filesize", None)

        if max_filesize is not None and attachment.size > max_filesize:
            raise ImageAssetTooLarge(url, attachment.size, max_filesize)

        param = Parameter(
            name=param.name,
            kind=param.kind,
            default=Asset(ctx.bot._connection, url),
            annotation=Optional[converter_type]
        )

    return await _old_command_transform(self, ctx, param)


commands.Command.transform = _new_command_transform
