"""
Copyright (c) 2018-present HitchedSyringe

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published
by the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""


from __future__ import annotations

__all__ = (
    "BadImageArgument",
    "ImageAttachment",
    "ImageTooLarge",
    "ImageResourceConverter",
)


import asyncio
import inspect
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    ClassVar,
    FrozenSet,
    Optional,
    Tuple,
    Union,
    cast,
)

import discord
import yarl
from discord import AppCommandOptionType, Attachment, Interaction, app_commands
from discord.asset import AssetMixin
from discord.ext import commands
from discord.ext.commands.core import _AttachmentIterator

if TYPE_CHECKING:
    from discord.asset import _State

    from .context import Context as SleepyContext

    AssetLike = Union[
        discord.Asset,
        discord.PartialEmoji,
        discord.GuildSticker,
        "DiscordMediaURL",
    ]


class DiscordMediaURL(AssetMixin):

    __slots__: Tuple[str, ...] = ("_state", "_url", "_size", "_content_type")

    def __init__(self, state: _State, url: str, size: int, content_type: str) -> None:
        self._state: _State = state
        self._url: str = url
        self._size: int = size
        self._content_type: str = content_type

    def __str__(self) -> str:
        return self._url

    def __len__(self) -> int:
        return len(self._url)

    def __repr__(self) -> str:
        return f"<DiscordMediaURL url={self._url!r}>"

    def __eq__(self, other: "DiscordMediaURL") -> bool:
        return isinstance(other, DiscordMediaURL) and self._url == other.url

    def __hash__(self) -> int:
        return hash(self._url)

    @property
    def url(self) -> str:
        return self._url

    @property
    def size(self) -> int:
        return self._size

    @property
    def content_type(self) -> str:
        return self._content_type


class BadImageArgument(commands.BadArgument):
    """Exception raised when the image is not valid.

    This inherits from :exc:`commands.BadArgument`.

    .. versionadded:: 4.0

    Attributes
    -----------
    argument: Union[:class:`str`, :class:`discord.Attachment`]
        The image supplied by the caller that was not valid.
    """

    def __init__(self, argument: Union[str, Attachment]) -> None:
        self.argument: Union[str, Attachment] = argument

        super().__init__(f'Image "{argument}" is invalid.')


class ImageTooLarge(commands.BadArgument):
    """Exception raised when the image is too large.

    This inherits from :exc:`commands.BadArgument`.

    .. versionadded:: 4.0

    Attributes
    -----------
    argument: Union[:class:`str`, :class:`discord.Attachment`]
        The image supplied by the caller that was too large.
    max_size: :class:`int`
        The maximum filesize, in bytes, allowed for images.
    """

    def __init__(self, argument: Union[str, Attachment], max_size: int) -> None:
        self.argument: Union[str, Attachment] = argument
        self.max_size: int = max_size

        super().__init__(f'Image "{argument}" exceeds {max_size:,d} B in size.')


class ImageResourceConverter(commands.Converter["AssetLike"]):
    """Converts to a :class:`discord.Asset`-like object.

    This will convert the following (in order):

    1. Users (returns the display avatar)
    2. Guild Emojis (returns a :class:`discord.PartialEmoji`)
    3. Guild Stickers (returns a :class:`discord.GuildSticker`)
    4. Image URLs (returns a :class:`DiscordMediaURL` denoting contents)
        a. The returned object is similar to a :class:`discord.Asset`,
           but only exposes the size and content type (via the `size`
           and `content_type` properties) of the image.

    .. warning::

        Due to limitations with the checks, passed URLs are not 100%
        guaranteed to link to valid images. Callers are responsible
        for checking validity via an image processing library.

    .. versionadded:: 4.0

    Parameters
    ----------
    max_size: Optional[:class:`int`]
        The maximum acceptable size in bytes a passed image URL can be.
        If the image URL exceeds this value, then :exc:`.ImageTooLarge`
        will be raised. If this is ``None``, then size checking will be
        disabled. Defaults to `40_000_000` (40 MB).

        .. warning::

            Disabling size checking leaves you vulnerable to denial of
            service attacks. Unless you are performing your own internal
            checks, it is **highly recommended** to pass a maximum size.
    """

    # fmt: off
    TRUSTED_HOSTS: FrozenSet[str] = frozenset({
        "cdn.discordapp.com",
        "images-ext-1.discordapp.net",
        "images-ext-2.discordapp.net",
        "media.discordapp.net",
    })
    # fmt: on

    def __init__(self, *, max_size: Optional[int] = 40_000_000) -> None:
        self._max_size: Optional[int] = None
        self.max_size = max_size

    @property
    def max_size(self) -> Optional[int]:
        """Optional[:class:`int`]: The maximum acceptable size in bytes a passed
        image URL can be. ``None`` if size checking is disabled.
        """
        return self._max_size

    @max_size.setter
    def max_size(self, value: Optional[int]) -> None:
        if value is not None and value <= 0:
            raise ValueError(f"invalid max_size {value} (must be > 0).")

        self._max_size = value

    # Trick to allow instances of this inside Optional and Union.
    def __call__(self) -> None:
        pass

    def _is_trusted_url(self, url: str) -> bool:
        try:
            url_obj = yarl.URL(url)
        except Exception:
            return False

        return url_obj.host in self.TRUSTED_HOSTS

    async def _resolve_trusted_url(
        self, message: discord.Message, argument: str
    ) -> Optional[str]:
        embeds = message.embeds

        # If there are no message embed(s), then Discord likely hasn't
        # proxied the image(s) yet. We'll have to wait for the embeds
        # to populate before refetching the message.
        if not embeds:
            await asyncio.sleep(1)

            try:
                message = await message.fetch()
            except discord.HTTPException:
                return None

            embeds = message.embeds

        # In order to derive a safe URL from a string argument, we sift
        # through embeds to get a Discord proxied version of the image.
        # This means that "<url>" is essentially an invalid argument.
        # Also, this may not work 100% of the time... Too bad!
        embed = discord.utils.find(lambda e: e.url == argument, embeds)
        if embed is None:
            return None

        im = embed.image or embed.thumbnail
        if im is None or not (im.width or im.height):
            return None

        return im.url if im.url and self._is_trusted_url(im.url) else im.proxy_url

    async def convert(self, ctx: SleepyContext, argument: str) -> AssetLike:
        try:
            user = await commands.UserConverter().convert(ctx, argument)
        except commands.UserNotFound:
            pass
        else:
            return user.display_avatar

        try:
            return await commands.PartialEmojiConverter().convert(ctx, argument)
        except commands.PartialEmojiConversionFailure:
            pass

        try:
            return await commands.GuildStickerConverter().convert(ctx, argument)
        except commands.GuildStickerNotFound:
            pass

        url = argument.strip("<>")

        if not self._is_trusted_url(argument):
            if ctx.interaction is not None:
                raise BadImageArgument(argument)

            url = await self._resolve_trusted_url(ctx.message, argument)
            if not url:
                raise BadImageArgument(argument)

        try:
            async with ctx.session.head(url, raise_for_status=True) as r:
                size = r.content_length
                mime = r.content_type
        except Exception:
            raise BadImageArgument(argument) from None

        if size is None or "image/" not in mime:
            raise BadImageArgument(argument)

        max_size = self._max_size
        if max_size is not None and size > max_size:
            raise ImageTooLarge(argument, max_size)

        return DiscordMediaURL(ctx._state, url, size, mime)


class ImageAttachment(app_commands.Transformer):
    """Converts to an image attachment.

    This is similar in behaviour to :class:`discord.Attachment`, but does extra
    checking to ensure the attachment passed is an image attachment. This also
    allows for converting a replied message's attachments.

    .. note::

        The context message's image attachments **always** takes precedance over
        a replied message's image attachments when converting.

    .. note::

        Due to a Discord limitation, use of this converter in `commands.Greedy`
        is **not supported** in hybrid commands.

    .. warning::

        Due to limitations with the checks, passed attachments are not 100%
        guaranteed to be valid images. Callers are responsible for checking
        validity via an image processing library.

    .. versionadded:: 4.0

    Parameters
    ----------
    max_size: Optional[:class:`int`]
        The maximum acceptable size in bytes a passed image attachment can be.
        If the image attachment exceeds this value, then :exc:`.ImageTooLarge`
        will be raised. If this is ``None``, then size checking will be disabled.
        Defaults to `40_000_000` (40 MB).

        .. warning::

            Disabling size checking leaves you vulnerable to denial of service
            attacks. Unless you are performing your own internal checks, it is
            **highly recommended** to pass a maximum size.
    """

    __sleepy_converters_is_image_attachment__: ClassVar[bool] = True

    def __init__(self, *, max_size: Optional[int] = 40_000_000) -> None:
        self._max_size: Optional[int] = None
        self.max_size = max_size

    @property
    def max_size(self) -> Optional[int]:
        """Optional[:class:`int`]: The maximum acceptable size in bytes a passed
        image attachment can be. ``None`` if size checking is disabled.
        """
        return self._max_size

    @max_size.setter
    def max_size(self, value: Optional[int]) -> None:
        if value is not None and value <= 0:
            raise ValueError(f"invalid max_size {value} (must be > 0).")

        self._max_size = value

    @property
    def type(self) -> AppCommandOptionType:
        return AppCommandOptionType.attachment

    def _validate_image_attachment(self, attachment: Attachment) -> Attachment:
        mime = attachment.content_type
        if mime is None or "image/" not in mime:
            raise BadImageArgument(attachment)

        size = attachment.size
        max_size = self._max_size
        if max_size is not None and size > max_size:
            raise ImageTooLarge(attachment, max_size)

        return attachment

    async def transform(self, itn: Interaction, value: Any, /) -> Attachment:
        return self._validate_image_attachment(value)


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
    if attachments.is_empty() and replied is not None:
        to_handle = _AttachmentIterator(replied.attachments)
    else:
        to_handle = attachments

    if not to_handle.is_empty():
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

        if hasattr(converter, "__sleepy_converters_is_image_attachment__"):
            res = await _original_command_transform(self, ctx, new_param, to_handle)

            if inspect.isclass(converter):
                converter = converter()

            if isinstance(res, list):
                return [converter._validate_image_attachment(a) for a in res]

            return converter._validate_image_attachment(res)

    del to_handle

    return await _original_command_transform(self, ctx, param, attachments)


commands.Command.transform = _new_command_transform
