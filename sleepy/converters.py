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
)


import asyncio
from inspect import isclass
from typing import TYPE_CHECKING, Any, Callable, FrozenSet, Optional, Union, cast

import discord
from discord import Attachment
from discord.ext import commands
from discord.ext.commands.core import _AttachmentIterator
from yarl import URL

from .mimics import PartialAsset

if TYPE_CHECKING:
    from discord.state import ConnectionState
    from typing_extensions import Protocol

    from .context import Context as SleepyContext

    class _AttachmentLike(Protocol):
        width: Optional[int]
        height: Optional[int]

        # These are invariant in Attachment.
        @property
        def url(self) -> Optional[str]:
            ...

        @property
        def proxy_url(self) -> Optional[str]:
            ...


class ImageAssetConversionFailure(commands.BadArgument):
    """Exception raised when the argument provided fails to convert
    to a :class:`PartialAsset`.

    This inherits from :exc:`commands.BadArgument`.

    .. versionadded:: 3.0

    .. versionchanged:: 3.3
        Argument can now be a :class:`discord.Attachment`.

    Attributes
    ----------
    argument: Union[:class:`str`, :class:`discord.Attachment`]
        The argument supplied by the caller that could not be converted.
    """

    def __init__(self, argument: Union[str, Attachment]) -> None:
        self.argument: Union[str, Attachment] = argument

        super().__init__(f'Couldn\'t convert "{argument}" to PartialAsset.')


class ImageAssetTooLarge(commands.BadArgument):
    """Exception raised when the argument provided exceeds the maximum
    conversion filesize.

    This inherits from :exc:`commands.BadArgument`.

    .. versionadded:: 3.0

    .. versionchanged:: 3.3
        Argument can now be a :class:`discord.Attachment`.

    Attributes
    ----------
    argument: Union[:class:`str`, :class:`discord.Attachment`]
        The argument supplied by the caller that exceeded the maximum
        conversion filesize.
    filesize: :class:`int`
        The argument's filesize in bytes.
    max_filesize: :class:`int`
        The converter's maximum filesize in bytes.
    """

    def __init__(
        self, argument: Union[str, Attachment], filesize: int, max_filesize: int
    ) -> None:
        self.argument: Union[str, Attachment] = argument
        self.filesize: int = filesize
        self.max_filesize: int = max_filesize

        super().__init__(
            f'"{argument}" exceeds the maximum filesize. ({filesize}/{max_filesize} B)'
        )


class ImageAssetConverter(commands.Converter[PartialAsset]):
    """Converts a user, custom emoji, sticker, image attachment,
    or image URL to a :class:`PartialAsset`.

    This also allows for converting replied messages containing
    image attachments.

    .. warning::

        Due to an implementation detail, image attachments take
        precedence over command arguments and replied messages
        during conversion. In this case, the conversion order
        is as follows:

        1) Context Message Image Attachments
        2) Replied Message Image Attachments
        3) Users
        4) Guild Emojis
        5) Guild Stickers
        6) Image URLs

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
        * Added support for guild stickers.

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

            Users, guild emojis, and guild stickers always skip
            this check, regardless of this setting.

        .. versionadded:: 3.0

        .. versionchanged:: 3.3
            Set default value to ``40_000_000`` (40 MB).

    Attributes
    ----------
    max_filesize: Optional[:class:`int`]
        The maximum conversion filesize in bytes.
        ``None`` if filesize checking is disabled.

        .. versionadded:: 3.0
    """

    # fmt: off
    TRUSTED_HOSTS: FrozenSet[str] = frozenset({
        "cdn.discordapp.com",
        "images-ext-1.discordapp.net",
        "images-ext-2.discordapp.net",
        "media.discordapp.net",
    })
    # fmt: on

    def __init__(self, *, max_filesize: Optional[int] = 40_000_000) -> None:
        if max_filesize is not None and max_filesize <= 0:
            raise ValueError(f"invalid max_filesize {max_filesize} (must be > 0).")

        self.max_filesize: Optional[int] = max_filesize

    # Trick to allow instances of this inside Optional and Union.
    def __call__(self) -> None:
        pass

    def _is_trusted(self, url: str) -> bool:
        try:
            url_obj = URL(url)
        except Exception:
            return False

        return url_obj.host in self.TRUSTED_HOSTS

    def _resolve_safe_url(self, attachment_like: _AttachmentLike) -> Optional[str]:
        if not (attachment_like.width or attachment_like.height):
            return None

        # Using the source url as-is can be dangerous, thus, we choose
        # to use Discord's cached version of the image (the proxy URL)
        # instead, unless the source URL originates from Discord. It's
        # worth noting that there is no 100% guarantee that the proxy
        # URL will actually work. In this case... too bad I guess.

        if attachment_like.url is not None and self._is_trusted(attachment_like.url):
            return attachment_like.url

        return attachment_like.proxy_url

    def _convert_attachment(
        self, state: ConnectionState, attachment: Attachment
    ) -> PartialAsset:
        url = self._resolve_safe_url(attachment)
        mime = attachment.content_type

        if url is None or mime is None or "image/" not in mime:
            raise ImageAssetConversionFailure(attachment)

        size = attachment.size
        max_size = self.max_filesize

        if max_size is not None and size > max_size:
            raise ImageAssetTooLarge(attachment, size, max_size)

        return PartialAsset(state, url=url)

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

        try:
            sticker = await commands.GuildStickerConverter().convert(ctx, argument)
        except commands.GuildStickerNotFound:
            pass
        else:
            return PartialAsset(sticker._state, url=sticker.url)

        url = argument.strip("<>")

        if not self._is_trusted(url):
            # If there are no message embeds, then Discord likely hasn't
            # cached the image(s) yet. We'll have to wait for the embeds
            # to populate before refetching the message.
            if not (embeds := ctx.message.embeds):
                await asyncio.sleep(1)

                try:
                    message = await ctx.message.fetch()
                except discord.HTTPException:
                    raise ImageAssetConversionFailure(argument) from None
                else:
                    embeds = message.embeds

            # In order to safely derive a PartialAsset from a string
            # argument, we need to sift through embeds so we can get
            # a Discord cached version of the image. This means that
            # passing "<url>" is now an invalid argument. Also, this
            # may not work 100% of the time. Too bad.
            embed = discord.utils.find(lambda e: e.url == argument, embeds)

            if embed is None or not (image := embed.image or embed.thumbnail):
                raise ImageAssetConversionFailure(argument)

            url = self._resolve_safe_url(image)

            if url is None:
                raise ImageAssetConversionFailure(argument)

        try:
            resp = await ctx.session.head(url, raise_for_status=True)
        except Exception:
            raise ImageAssetConversionFailure(argument) from None

        size = resp.content_length

        if size is None or "image/" not in resp.content_type:
            raise ImageAssetConversionFailure(argument)

        max_size = self.max_filesize

        if max_size is not None and size > max_size:
            raise ImageAssetTooLarge(url, size, max_size)

        return PartialAsset(ctx.bot._connection, url=url)


# Private since I only plan on using these for a
# handful of commands. I have no plans for these
# to be publicised since their behaviour is too
# confusing to document properly in addition to
# the countless ambiguities associated.
def _positional_bool_flag(*names: str) -> Callable[[str], bool]:
    def convert(value: str) -> bool:
        if value not in names:
            raise commands.BadArgument(f"{value} is not a valid flag.")

        return True

    return convert


_original_command_transform = commands.Command.transform


async def _iac_transform(
    converter: ImageAssetConverter,
    command: commands.Command,
    ctx: SleepyContext,
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
    ctx: commands.Context,
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
    # the conversion order is as follows:
    #
    # 1) Context Message Image Attachments
    # 2) Replied Message Image Attachments
    # 3) Users
    # 4) Guild Emojis
    # 5) Guild Stickers
    # 6) Image URLs
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
