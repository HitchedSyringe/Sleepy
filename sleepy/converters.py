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
from inspect import isclass
from typing import TYPE_CHECKING, Any, Callable, Optional, cast

from discord import Attachment
from discord.ext import commands
from discord.ext.commands.core import _AttachmentIterator

from .mimics import PartialAsset

if TYPE_CHECKING:
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
    """Converts a user, custom emoji, image attachment, or image
    URL to a :class:`PartialAsset`.

    This also allows for converting replied messages containing
    image attachments.

    .. warning::

        Due to an implementation detail, image attachments take
        precedence over command arguments and replied messages
        during conversion. In this case, the conversion order
        is as follows:

        1) Image Attachments
        2) Replied Messages
        3) Command Arguments

        In the case of using :class:`commands.Greedy`, only the
        argument type with the highest precedence is converted.
        For example, if both image attachments and image URLs are
        passed, then only the former will be converted, while the
        latter is completely ignored and discarded.

        Furthermore, conversion of image attachments and replied
        messages are **not** supported with :class:`typing.Union`.

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

    .. versionchanged:: 3.3

        * Removed support for resolving a message with image
          attachments via ID or URL.
        * Refactored to use discord.py's attachment conversion.
        * Added support for :class:`commands.Greedy`.

    Parameters
    ----------
    max_filesize: Optional[:class:`int`]
        The maximum filesize, in bytes, an attachment or URL
        can be. This will raise :exc:`.ImageAssetTooLarge` if
        an attachment or URL exceeds this filesize limit.
        ``None`` denotes disabling filesize checking.
        Defaults to ``40_000_000`` (40 MB).

        .. warning::

            Disabling filesize checking leaves you vulnerable to
            a denial-of-service attack. Unless you are doing your
            own internal checks, it is **highly recommended** to
            set a maximum filesize.

        .. note::

            Users and emojis always skip this check regardless of
            this setting.

        .. versionadded:: 3.0

        .. versionchanged::
            Changed default value to ``40_000_000`` (40 MB).

    Attributes
    ----------
    max_filesize: Optional[:class:`int`]
        The maximum conversion filesize in bytes.
        ``None`` if filesize checking is disabled.

        .. versionadded:: 3.0
    """

    def __init__(self, *, max_filesize: Optional[int] = 40_000_000) -> None:
        if max_filesize is not None and max_filesize <= 0:
            raise ValueError(f"invalid max_filesize {max_filesize} (must be > 0).")

        self.max_filesize: Optional[int] = max_filesize

    # Trick to allow instances of this inside Optional and Union.
    def __call__(self) -> None:
        pass

    def _convert_attachment(
        self, state: ConnectionState, attachment: Attachment
    ) -> PartialAsset:
        mime = attachment.content_type

        if mime is None or "image/" not in mime:
            raise ImageAssetConversionFailure(attachment.url)

        size = attachment.size
        max_size = self.max_filesize

        if max_size is not None and size > max_size:
            raise ImageAssetTooLarge(attachment.url, size, max_size)

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
            resp = await ctx.session.head(url, raise_for_status=True)
        except:
            raise ImageAssetConversionFailure(argument) from None

        size = resp.content_length

        if size is None or "image/" not in resp.content_type:
            raise ImageAssetConversionFailure(argument)

        max_size = self.max_filesize

        if max_size is not None and size > max_size:
            raise ImageAssetTooLarge(url, size, max_size)

        return PartialAsset(ctx.bot._connection, url=url)


def real_float(*, max_decimal_places: Optional[int] = None) -> Callable[[str], float]:
    """Similar to the :class:`float` converter except this does
    not convert to ``nan`` or ``inf`` and allows for limiting
    the number of decimal places.

    This returns a callable that can be used as an argument
    converter.

    .. versionadded:: 3.0

    .. versionchanged:: 3.2
        Allow ``None`` to be passed in ``max_decimal_places``.

    Parameters
    ----------
    max_decimal_places: Optional[:class:`int`]
        The maximum amount of decimal places to allow for float
        values.
        ``None`` denotes no maximum.
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


_original_command_transform = commands.Command.transform


async def _iac_transform(
    converter: ImageAssetConverter,
    command: commands.Command,
    ctx: AnyContext,
    param: commands.Parameter,
    attachments: _AttachmentIterator,
) -> Any:
    value = await _original_command_transform(command, ctx, param, attachments)

    if isinstance(value, Attachment):
        return converter._convert_attachment(ctx.bot._connection, value)

    if isinstance(value, list):
        state = ctx.bot._connection
        return [converter._convert_attachment(state, a) for a in value]

    return value


async def _new_command_transform(
    self: commands.Command,
    ctx: AnyContext,
    param: commands.Parameter,
    attachments: _AttachmentIterator,
) -> Any:
    # Keeps Pyright quiet while also avoiding a type ignore.
    ctx = cast("SleepyContext", ctx)
    replied = ctx.replied_message

    # In this case, we ideally want to make sure that the
    # original message had no attachments before checking
    # to see if the replied message has attachments. The
    # reason we don't overwrite the passed attachments is
    # to preserve the original :class:`discord.Attachment`
    # conversion behaviour.
    if not attachments.data and replied is not None:
        to_handle = _AttachmentIterator(replied.attachments)
    else:
        to_handle = attachments

    # Allows passing a command argument or using a replied message
    # alongside an image attachment. Note that there is precedence
    # involved here due to an implementation detail. For reference,
    # the following conversion order is as follows:
    #
    # 1) Image Attachments
    # 2) Replied Messages
    # 3) Command Arguments
    #
    # Unfortunately, this also makes working with commands.Greedy
    # really hairy. In that case, only the argument type with the
    # highest precedence is converted. Everything below is quietly
    # ignored and (eventually) discarded.
    if to_handle.index < len(to_handle.data):
        converter = param.converter

        # Attempt to resolve the converter itself and spoof the
        # param accordingly to work with the attachment handling.
        # We don't overwrite the original parameter for the same
        # reason as outlined above.
        if isinstance(converter, commands.Greedy):
            converter = converter.converter
            new_param = param.replace(annotation=commands.Greedy[Attachment])
        elif self._is_typing_optional(param.annotation):
            converter = param.annotation.__args__[0]
            new_param = param.replace(annotation=Optional[Attachment])
        else:
            new_param = param.replace(annotation=Attachment)

        if isclass(converter) and issubclass(converter, ImageAssetConverter):
            converter = converter()
            return await _iac_transform(converter, self, ctx, new_param, to_handle)

        if isinstance(converter, ImageAssetConverter):
            return await _iac_transform(converter, self, ctx, new_param, to_handle)

    return await _original_command_transform(self, ctx, param, attachments)


commands.Command.transform = _new_command_transform
