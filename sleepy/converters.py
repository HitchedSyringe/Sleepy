"""
Copyright (c) 2018-present HitchedSyringe

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""


__all__ = (
    "ImageAssetConversionFailure",
    "ImageAssetConverter",
    "ImageAssetTooLarge",
    "real_float",
)


import math
from inspect import Parameter, isclass
from typing import Optional

from discord import Asset, DiscordException, Message
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


class ImageAssetConverter(commands.Converter):
    """Converts a user, custom emoji, image attachment,
    image URL, or message to a :class:`discord.Asset`.

    .. note::

        Due to an implementation detail, command arguments take
        precedence over attachments and replied messages, and
        will always be converted first.

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
          :attr:`Command.ignore_extra` is ``False`` and
          more than one attachment is supplied.
        * Added support for converting custom emojis.
        * Attachments and URLs are now checked for their
          filesize.

    .. versionchanged:: 3.2

        * Added support for replying to a message with image
          attachments.
        * Added support for resolving a message with image
          attachments via ID or URL.

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
        ``None`` if filesize checking is disabled.

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
            message = await commands.MessageConverter().convert(ctx, url)
            url = message.attachments[0].url
        except commands.MessageNotFound:
            # Ideally, we would want this to fail completely if
            # the message couldn't be resolved, however, this can
            # also be raised if the URL regex didn't find a match.
            # In any case, just ignore this exception altogether.
            pass
        except (IndexError, commands.ChannelNotReadable, commands.ChannelNotFound):
            raise ImageAssetConversionFailure(argument) from None

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


def real_float(*, max_decimal_places=None):
    """Similar to the :class:`float` converter except
    this does not convert to NaN or Infinity and allows
    for limiting decimal places.

    This returns a callable that can be used as an
    argument converter.

    .. versionadded:: 3.0

    .. versionchanged:: 3.2
        Allow ``None`` to be passed in ``max_decimal_places``.

    Parameters
    ----------
    max_decimal_places: Optional[:class:`int`]
        The maximum amount of decimal places to allow
        for float values. ``None`` denotes no maximum.
        Defaults to ``None``.

    Returns
    -------
    Callable[[:class:`str`], :class:`float`]
        The converter callable.

    Raises
    ------
    ValueError
        An invalid ``max_decimal_places`` value was given.
    """
    if max_decimal_places is not None and max_decimal_places <= 0:
        raise ValueError(
            f"invalid max_decimal_places {max_decimal_places} (must be > 0)."
        )

    def converter(arg):
        try:
            f_arg = float(arg)
        except ValueError:
            raise commands.BadArgument(f'Couldn\'t convert "{arg}" to float.') from None

        if not math.isfinite(f_arg):
            raise commands.BadArgument("Float must be a real finite value.")

        if (
            max_decimal_places is not None
            and (p := arg[::-1].find(".")) > max_decimal_places
        ):
            raise commands.BadArgument(
                f"Too many decimal places. ({p} > {max_decimal_places})"
            )

        return f_arg

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


# If there's nothing to actually process (i.e all
# checks for the existence of attachments fail),
# we return the passed param and just let original
# transfer method handle it like it normally would
# and, ideally, raise MissingRequiredArgument.
def _process_attachments(command, converter, ctx, param):
    ref = ctx.message.reference

    if ref is None:
        attachments = ctx.message.attachments
    elif isinstance(ref.resolved, Message):
        attachments = ref.resolved.attachments
    else:
        return param

    if not attachments:
        return param

    # Figured I should include this here for completeness.
    if not command.ignore_extra and len(attachments) > 1:
        raise commands.TooManyArguments("You can only upload one attachment.")

    attach = attachments[0]
    mime = attach.content_type

    if mime is None or "image/" not in mime:
        raise ImageAssetConversionFailure(attach.url)

    max_fs = converter.max_filesize

    if max_fs is not None and attach.size > max_fs:
        raise ImageAssetTooLarge(attach.url, attach.size, max_fs)

    return Parameter(
        name=param.name,
        kind=param.kind,
        default=Asset(ctx.bot._connection, attach.url),
        annotation=Optional[type(converter)]
    )


async def _new_command_transform(self, ctx, param):
    conv = param.annotation

    if isclass(conv) and issubclass(conv, ImageAssetConverter):
        param = _process_attachments(self, conv(), ctx, param)
    elif isinstance(conv, ImageAssetConverter):
        param = _process_attachments(self, conv, ctx, param)

    return await _old_command_transform(self, ctx, param)


commands.Command.transform = _new_command_transform
