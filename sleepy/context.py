"""
Copyright (c) 2018-present HitchedSyringe

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""


from __future__ import annotations

# fmt: off
__all__ = (
    "Context",
)
# fmt: on


import asyncio
import copy
from typing import TYPE_CHECKING, Any, Callable, Optional, Sequence, Union

import discord
from discord.ext import commands
from discord.utils import MISSING, cached_property

from .menus import (
    ConfirmationView,
    PaginationView,
    _DisambiguationSource,
    _DisambiguationView,
)

if TYPE_CHECKING:
    from aiohttp import ClientSession
    from discord.abc import MessageableChannel
    from discord.ext.menus import PageSource

    from .bot import Sleepy
    from .http import RequestUrl


class Context(commands.Context["Sleepy"]):
    """A custom context class that provides some useful shorthands.

    Subclasses :class:`commands.Context`.

    .. versionadded:: 1.7
    """

    channel: Union[
        discord.TextChannel, discord.VoiceChannel, discord.Thread, discord.DMChannel
    ]
    command: commands.Command[Any, ..., Any]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

        # Exists to allow for granular control over what errors
        # should and shouldn't be handled by the global command
        # error handler. This must be manually set by the user.
        self._already_handled_error: bool = False

    @property
    def loop(self) -> asyncio.AbstractEventLoop:
        """:class:`asyncio.AbstractEventLoop`: The bot's event loop.

        .. versionadded:: 3.0
        """
        return self.bot.loop

    @property
    def session(self) -> ClientSession:
        """:class:`aiohttp.ClientSession`: The HTTP requester's underlying client session."""
        return self.bot.http_requester.session

    @cached_property
    def replied_message(self) -> Optional[discord.Message]:
        """Optional[:class:`discord.Message`]: The message that is being replied to.

        .. versionadded:: 3.3
        """
        reference = self.message.reference

        if reference is not None and isinstance(reference.resolved, discord.Message):
            return reference.resolved

        return None

    async def request(
        self, method: str, url: RequestUrl, /, *, cache__: bool = False, **options: Any
    ) -> Any:
        """|coro|

        Same as :meth:`HTTPRequester.request`.

        .. versionadded:: 2.0

        .. versionchanged:: 3.0
            ``method`` and ``url`` are now positional-only arguments.
        """
        return await self.bot.http_requester.request(
            method, url, cache__=cache__, **options
        )

    async def get(
        self, url: RequestUrl, /, *, cache__: bool = False, **options: Any
    ) -> Any:
        """|coro|

        Similar to :meth:`request` except slimmed down to only do GET requests.

        .. versionadded:: 1.10

        .. versionchanged:: 3.0
            ``url`` is now a positional-only argument.
        """
        return await self.request("GET", url, cache__=cache__, **options)

    async def post(
        self, url: RequestUrl, /, *, cache__: bool = False, **options: Any
    ) -> Any:
        """|coro|

        Similar to :meth:`request` except slimmed down to only do POST requests.

        .. versionadded:: 1.10

        .. versionchanged:: 3.0
            ``url`` is now a positional-only argument.
        """
        return await self.request("POST", url, cache__=cache__, **options)

    async def paginate(
        self,
        source: PageSource,
        *,
        enable_stop_button: bool = True,
        delete_message_when_stopped: bool = True,
        remove_view_on_timeout: bool = False,
        disable_view_on_timeout: bool = True,
        ephemeral: bool = False,
        wait: bool = False,
        **kwargs: Any,
    ) -> discord.Message:
        """|coro|

        Starts a new pagination menu.

        .. versionadded:: 2.0

        .. versionchanged:: 3.2

            * Rewrote to use Discord's interactions menus. This
              resulted in the following parameters being renamed
              to keep consistency or clarify purpose:

                - ``remove_reactions_after`` -> ``remove_view_after``
                - ``delete_message_after -> ``delete_message_when_stopped``

            * This now returns a :class:`discord.Message`.

        .. versionchanged:: 3.3

            * Renamed ``remove_view_after`` parameter to ``remove_view_on_timeout``.
            * Renamed ``disable_view_after`` parameter to ``disable_view_on_timeout``.

        Parameters
        ----------
        source: :class:`menus.PageSource`
            The page source to paginate.

            .. versionchanged:: 3.0
                This is now a positional-only argument.

            .. versionchanged:: 3.3
                This is no longer a positional-only argument.
        enable_stop_button: :class:`bool`
            Whether or not to enable the stop button.
            Defaults to ``True``.

            .. versionadded:: 3.3
        delete_message_when_stopped: :class:`bool`
            Whether or not to delete the message once the stop button is
            pressed.
            This has no effect if ``enable_stop_button`` is ``False``.
            Defaults to ``True``.
        remove_view_on_timeout: :class:`bool`
            Whether or not to remove the view after it has timed out.
            This has no effect if ``enable_stop_button`` is ``False``.
            Defaults to ``False``.

            .. note::

                ``delete_message_when_stopped`` takes priority over
                this setting in terms of cleanup behaviour.

        disable_view_on_timeout: :class:`bool`
            Whether or not to disable the view after it has timed out.
            This has no effect if ``enable_stop_button`` is ``False``.
            Defaults to ``True``.

            .. note::

                ``remove_view_on_timeout`` takes priority over this setting.

            .. versionadded:: 3.2
        ephemeral: :class:`bool`
            Whether or not the send the view in an ephemeral message.
            This is ignored if the context is not interaction-based.
            Defaults to ``False``.

            .. versionadded:: 3.3
        wait: :class:`bool`
            Whether or not to wait until the view has finished
            interacting before returning back to the caller.
            Defaults to ``False``.

            .. versionadded:: 3.2
        kwargs:
            The remaining parameters to be passed to the
            :class:`PaginationView` constructor.

        Returns
        -------
        :class:`discord.Message`
            The message that was sent.
        """
        view = PaginationView(
            source,
            enable_stop_button=enable_stop_button,
            delete_message_when_stopped=delete_message_when_stopped,
            remove_view_on_timeout=remove_view_on_timeout,
            disable_view_on_timeout=disable_view_on_timeout,
            owner_ids={self.author.id, self.bot.owner_id, *self.bot.owner_ids},  # type: ignore
            **kwargs,
        )

        return await view.send_to(self, ephemeral=ephemeral, wait=wait)

    async def prompt(
        self,
        message: str,
        *,
        delete_message_on_interact: bool = True,
        remove_view_on_timeout: bool = False,
        disable_view_on_timeout: bool = True,
        ephemeral: bool = False,
        timeout: Optional[float] = 30,
    ) -> Optional[bool]:
        """|coro|

        Starts a new confirmation menu.

        .. versionadded:: 1.7

        .. versionchanged:: 2.0
            Rewrote to use `discord.ext.menus`.

        .. versionchanged:: 3.2
            Rewrote to use Discord's interactions menus. This
            resulted in the following parameters being renamed
            to keep consistency or clarify purpose:

                * ``remove_reactions_after`` -> ``remove_view_after``
                * ``delete_message_after -> ``delete_message_on_interact``

        .. versionchanged:: 3.3

            * Renamed ``remove_view_after`` parameter to ``remove_view_on_timeout``.
            * Renamed ``disable_view_after`` parameter to ``disable_view_on_timeout``.

        Parameters
        ----------
        message: :class:`str`
            The prompt message.

            .. versionchanged:: 3.0
                This is now a positional-only argument.

            .. versionchanged:: 3.3

                * This is no longer a positional-only argument.
                * This no longer takes a :class:`discord.Message`.
        delete_message_on_interact: :class:`bool`
            Whether or not to delete the message when the user
            interacts with the view.
            Defaults to ``True``.
        remove_view_on_timeout: :class:`bool`
            Whether or not to remove the view after it has timed out.
            Defaults to ``False``.

            .. note::

                ``delete_message_on_interact`` takes priority over
                this setting in terms of cleanup behaviour.

        disable_view_on_timeout: :class:`bool`
            Whether or not to disable the view after it has timed out.
            Defaults to ``True``.

            .. note::

                ``remove_view_after`` and ``delete_message_on_interact``
                takes priority over this setting in terms of cleanup
                behaviour.

            .. versionadded:: 3.2
        ephemeral: :class:`bool`
            Whether or not the send the view in an ephemeral message.
            This is ignored if the context is not interaction-based.
            Defaults to ``False``.

            .. versionadded:: 3.3
        timeout: Optional[:class:`float`]
            The time, in seconds, before the prompt expires.
            ``None`` denotes no timeout.
            Defaults to ``30``.

        Returns
        -------
        Optional[:class:`bool`]
            Whether or not the user confirmed the prompt.
            ``None`` if the prompt expired.

        Raises
        ------
        :exc:`discord.HTTPException`
            Attaching the menu to the given message failed.
        """
        view = ConfirmationView(
            owner_ids={self.author.id, self.bot.owner_id, *self.bot.owner_ids},  # type: ignore
            timeout=timeout,
        )

        confirmation = await self.send(message, view=view, ephemeral=ephemeral)
        timed_out = await view.wait()

        try:
            if not timed_out and delete_message_on_interact:
                await confirmation.delete()
            elif remove_view_on_timeout:
                await confirmation.edit(view=None)
            elif disable_view_on_timeout and view.children:
                for child in view.children:
                    child.disabled = True  # type: ignore

                await confirmation.edit(view=view)
        except discord.HTTPException:
            pass

        return view.result

    async def disambiguate(
        self,
        matches: Sequence[Any],
        /,
        formatter: Optional[Callable[[Any], str]] = None,
        *,
        timeout: Optional[float] = 30,
        ephemeral: bool = False,
        sort: bool = True,
    ) -> Any:
        """|coro|

        Starts a new disambiguation session.

        This allows a user to select their desired option in a
        given sequence of matching items, returning either the
        item the user picks, or, if applicable, the only item
        in the sequence.

        .. versionadded:: 1.7

        .. versionchanged:: 2.0
            Renamed ``entry`` parameter to ``formatter``.

        .. versionchanged:: 3.3
            Rewrote to use Discord's select menus.

        Parameters
        ----------
        matches: Sequence[Any]
            The matching items to disambiguate.

            .. versionchanged:: 3.0
                This is now a positional-only argument.
        formatter: Optional[Callable[[Any], :class:`str`]]
            A function that returns a string-like result.
            This is used to format the displayed matches.
        timeout: Optional[:class:`float`]
            How long, in seconds, the user has to respond.
            ``None`` denotes no timeout.
            Defaults to ``30``.

            .. versionadded:: 3.0
        ephemeral: :class:`bool`
            Whether or not the send the view in an ephemeral message.
            This is ignored if the context is not interaction-based.
            Defaults to ``False``.

            .. versionadded:: 3.3
        sort: :class:`bool`
            Whether or not the displayed matches should be sorted.
            Defaults to ``True``.

            .. versionadded:: 3.3

        Returns
        -------
        Any
            The item the user picked.

        Raises
        ------
        ValueError
            Either no results were found, or the session timed out.
        """
        if not matches:
            raise ValueError("No results found.")

        if len(matches) == 1:
            return matches[0]

        source = _DisambiguationSource(matches, formatter, sort=sort)
        view = _DisambiguationView(source, timeout=timeout)

        await view.send_to(self, ephemeral=ephemeral, wait=True)

        if view.selection is MISSING:
            raise ValueError("You took too long to respond.")

        return view.selection

    async def copy_with(
        self,
        *,
        author: Optional[Union[discord.Member, discord.User]] = None,
        channel: Optional[MessageableChannel] = None,
        **properties: Any,
    ) -> "Context":
        """|coro|

        Returns a new :class:`Context` instance with
        the given message properties applied.

        This creates a shallow copy of this context's
        message and applies the passed properties to
        it. If no properties are passed, then the new
        :class:`Context` instance will be identical
        to this context.

        .. versionadded:: 3.0

        Parameters
        ----------
        author: Optional[:class:`discord.abc.User`]
            The new user that sent the message.
            Defaults to :attr:`author` if ``None``.
        channel: Optional[:class:`discord.abc.Messageable`]
            The new messageable the message was sent from.
            Defaults to :attr:`channel` if ``None``.
        properties: Any
            An argument list of message properties to apply.

        Returns
        -------
        :class:`Context`
            The new context with the applied message properties.
        """
        copied_message = copy.copy(self.message)
        copied_message._update(properties)  # type: ignore -- This is fine.

        if author is not None:
            copied_message.author = author

        if channel is not None:
            copied_message.channel = channel

        return await self.bot.get_context(copied_message, cls=type(self))

    # This method exists as a way to allow granular control over
    # which command exceptions get forgiven in terms of cooldown.
    # Unfortunately, this has to touch a lot of private methods
    # because there isn't a better or cleaner way to do this.
    def _refund_cooldown_token(self) -> None:
        if not self.valid:
            return

        mapping = self.command._buckets

        if not mapping.valid:
            return

        message = self.message
        current = message.edited_at or message.created_at
        bucket = mapping.get_bucket(message, current.timestamp())

        if bucket._tokens == bucket.rate:
            return

        bucket._tokens += 1


if TYPE_CHECKING:

    class GuildContext(Context):
        author: discord.Member
        guild: discord.Guild
        channel: Union[discord.TextChannel, discord.VoiceChannel, discord.Thread]
        me: discord.Member
