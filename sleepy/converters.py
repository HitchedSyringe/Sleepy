"""
Copyright (c) 2018-present HitchedSyringe

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""


from __future__ import annotations


__all__ = (
    "ImageAssetConversionFailure",
    "ImageAssetConverter",
    "ImageAssetTooLarge",
    "real_float",
)


import math
from inspect import Parameter, isclass
from typing import TYPE_CHECKING, Any, Callable, Optional

from discord import Message
from discord.ext import commands

from .mimics import PartialAsset


if TYPE_CHECKING:
    from discord import Attachment
    from discord.state import ConnectionState

    from .context import Context as SleepyContext

    AnyContext = commands.Context[Any]


class ImageAssetConversionFailure(commands.BadArgument):
    """Exception raised when the argument provided
    fails to convert to a :class:`PartialAsset`.

    This inherits from :exc:`commands.BadArgument`.

    .. versionadded:: 3.0

    Attributes
    ----------
    argument: :class:`str`
        The argument supplied by the caller that could
        not be converted.
    """

    def __init__(self, argument: str) -> None:
        self.argument: str = argument

        super().__init__(f'Couldn\'t convert "{argument}" to PartialAsset.')


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

    def __init__(self, argument: str, filesize: int, max_filesize: int) -> None:
        self.argument: str = argument
        self.filesize: int = filesize
        self.max_filesize: int = max_filesize

        super().__init__(
            f'"{argument}" exceeds the maximum filesize. ({filesize}/{max_filesize} B)'
        )


class ImageAssetConverter(commands.Converter[PartialAsset]):
    """Converts a user, custom emoji, image attachment,
    image URL, or message to a :class:`PartialAsset`.

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
        * This now returns :class:`PartialAsset` instances.

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

    def __init__(self, *, max_filesize: Optional[int] = None) -> None:
        if max_filesize is not None and max_filesize <= 0:
            raise ValueError(f"invalid max_filesize {max_filesize} (must be > 0).")

        self.max_filesize: Optional[int] = max_filesize

    def _convert_attachment(
        self,
        state: ConnectionState,
        attachment: Attachment
    ) -> PartialAsset:
        mime = attachment.content_type

        if mime is None or "image/" not in mime:
            raise ImageAssetConversionFailure(attachment.url)

        max_fs = self.max_filesize

        if max_fs is not None and attachment.size > max_fs:
            raise ImageAssetTooLarge(attachment.url, attachment.size, max_fs)

        return PartialAsset(state, url=attachment.url)

    async def convert(self, ctx: SleepyContext, argument: str) -> PartialAsset:
        try:
            user = await commands.UserConverter().convert(ctx, argument)
        except commands.UserNotFound:
            pass
        else:
            avatar = user.display_avatar.with_static_format("png")
            return PartialAsset(avatar._state, url=avatar.url)

        try:
            emoji = await commands.PartialEmojiConverter().convert(ctx, argument)
        except commands.PartialEmojiConversionFailure:
            pass
        else:
            return PartialAsset(emoji._state, url=emoji.url)

        # NOTE: Unicode emojis can't be supported here due to
        # some ambiguities with emojis consisting of between
        # 2-4 characters, which ord() cannot take, meaning we
        # can't really use the twemoji cdn.

        url = argument.strip("<>")

        try:
            message = await commands.MessageConverter().convert(ctx, url)

            return self._convert_attachment(message._state, message.attachments[0])
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

        filesize = int(resp.headers["Content-Length"])

        if self.max_filesize is not None and filesize > self.max_filesize:
            raise ImageAssetTooLarge(url, filesize, self.max_filesize)

        return PartialAsset(ctx.bot._connection, url=url)


def real_float(*, max_decimal_places: Optional[int] = None) -> Callable[[str], float]:
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

    def converter(arg: str) -> float:
        try:
            f_arg = float(arg)
        except ValueError:
            raise commands.BadArgument(f'Couldn\'t convert "{arg}" to float.') from None

        if not math.isfinite(f_arg):
            raise commands.BadArgument("Float must be a real finite value.")

        decimal_places = arg[::-1].find(".")

        if max_decimal_places is not None and decimal_places > max_decimal_places:
            raise commands.BadArgument(
                f"Too many decimal places. ({decimal_places} > {max_decimal_places})"
            )

        return f_arg

    return converter


# Private since I only plan on using these for a
# handful of commands. I have no plans for these
# to be publicised since their behaviour is too
# confusing to document properly in addition to
# the countless ambiguities associated.
def _pseudo_bool_flag(*names: str) -> Callable[[str], bool]:

    def convert(value: str) -> bool:
        if value not in names:
            raise commands.BadArgument("Invalid flag.")

        return True

    return convert


_old_command_transform = commands.Command.transform


# If there's nothing to actually process (i.e all
# checks for the existence of attachments fail),
# we return the passed param and just let original
# transfer method handle it like it normally would
# and, ideally, raise MissingRequiredArgument.
def _process_attachments(
    command: commands.Command,
    converter: ImageAssetConverter,
    ctx: AnyContext,
    param: Parameter
) -> Parameter:
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

    asset = converter._convert_attachment(ctx.bot._connection, attachments[0])
    converter_cls = type(converter)

    return param.replace(default=asset, annotation=Optional[converter_cls])


async def _new_command_transform(self, ctx: AnyContext, param: Parameter) -> Any:
    conv = param.annotation

    if self._is_typing_optional(conv):
        conv = conv.__args__[0]

    if isclass(conv) and issubclass(conv, ImageAssetConverter):
        param = _process_attachments(self, conv(), ctx, param)
    elif isinstance(conv, ImageAssetConverter):
        param = _process_attachments(self, conv, ctx, param)

    return await _old_command_transform(self, ctx, param)


commands.Command.transform = _new_command_transform
