"""
Copyright (c) 2018-present HitchedSyringe

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""


from __future__ import annotations


__all__ = (
    "Context",
)


import asyncio
import copy
from typing import TYPE_CHECKING, Any, Callable, Optional, Sequence, Union

import discord
from discord.ext import commands
from discord.utils import cached_property

from .menus import ConfirmationView, PaginationView
from .utils import plural


if TYPE_CHECKING:
    from aiohttp import ClientSession
    from discord.abc import MessageableChannel
    from discord.ext.menus import PageSource

    from .http import HTTPResponseData, RequestUrl


class Context(commands.Context):
    """A custom context that provides some useful methods.

    This class subclasses :class:`commands.Context` and, as a
    result, anything that you can do with a :class:`commands.Context`,
    you can do with this context.

    .. versionadded:: 1.7
    """

    @property
    def loop(self) -> asyncio.AbstractEventLoop:
        """:class:`asyncio.AbstractEventLoop`: The bot's event loop.

        .. versionadded:: 3.0
        """
        return self.bot.loop

    @property
    def session(self) -> ClientSession:
        """:class:`aiohttp.ClientSession`: The http requester's client session."""
        return self.bot.http_requester.session

    @cached_property
    def replied_reference(self) -> Optional[discord.MessageReference]:
        """Optional[:class:`discord.MessageReference`]: The replied message reference.

        .. versionadded:: 3.0
        """
        reference = self.message.reference

        if reference is not None and isinstance(reference.resolved, discord.Message):
            return reference.resolved.to_reference()

        return None

    async def request(
        self,
        method: str,
        url: RequestUrl,
        /,
        *,
        cache__: bool = False,
        **kwargs: Any
    ) -> HTTPResponseData:
        """|coro|

        Same as :meth:`HTTPRequester.request`.

        .. versionadded:: 2.0

        .. versionchanged:: 3.0
            ``method`` and ``url`` are now positional-only arguments.
        """
        return await self.bot.http_requester.request(method, url, cache__=cache__, **kwargs)

    async def get(
        self,
        url: RequestUrl,
        /,
        *,
        cache__: bool = False,
        **kwargs: Any
    ) -> HTTPResponseData:
        """|coro|

        Similar to :meth:`request`, but slimmed down to only do GET requests.

        .. versionadded:: 1.10

        .. versionchanged:: 3.0
            ``url`` is now a positional-only argument.
        """
        return await self.request("GET", url, cache__=cache__, **kwargs)

    async def post(
        self,
        url: RequestUrl,
        /,
        *,
        cache__: bool = False,
        **kwargs: Any
    ) -> HTTPResponseData:
        """|coro|

        Similar to :meth:`request`, but slimmed down to only do POST requests.

        .. versionadded:: 1.10

        .. versionchanged:: 3.0
            ``url`` is now a positional-only argument.
        """
        return await self.request("POST", url, cache__=cache__, **kwargs)

    async def paginate(
        self,
        source: PageSource,
        /,
        *,
        delete_message_when_stopped: bool = True,
        remove_view_after: bool = False,
        disable_view_after: bool = True,
        wait: bool = False,
        **kwargs: Any
    ) -> discord.Message:
        """|coro|

        Starts a new pagination menu in this context's channel.

        .. versionadded:: 2.0

        .. versionchanged:: 3.2

            * Rewrote to use Discord's interactions menus. This
              resulted in the following kwargs being renamed to
              keep consistency or clarify purpose:

                - ``remove_reactions_after`` -> ``remove_view_after``
                - ``delete_message_after -> ``delete_message_when_stopped``

            * This now returns a :class:`discord.Message`.

        Parameters
        ----------
        source: :class:`menus.PageSource`
            The page source to paginate.

            .. versionchanged:: 3.0
                This is now a positional-only argument.
        delete_message_when_stopped: :class:`bool`
            Whether or not to delete the message when the user
            presses the stop button.
            Defaults to ``True``.
        remove_view_after: :class:`bool`
            Whether to remove the view after after it has finished
            interacting.
            Defaults to ``False``.

            .. note::

                ``delete_message_when_stopped`` takes priority over
                this setting in terms of cleanup behaviour.

        disable_view_after: :class:`bool`
            Whether or not to disable the view after it has finished
            interacting.
            Defaults to ``True``.

            .. note::

                ``remove_view_after`` and ``delete_message_when_stopped``
                takes priority over this setting in terms of cleanup
                behaviour.

            .. versionadded:: 3.2
        wait: :class:`bool`
            Whether or not to wait until the view has finished
            interacting before returning back to the caller.
            Defaults to ``False``.

            .. versionadded:: 3.2

        Returns
        -------
        :class:`discord.Message`
            The message that was sent.
        """
        view = PaginationView(
            self.bot,
            source,
            delete_message_when_stopped=delete_message_when_stopped,
            remove_view_after=remove_view_after,
            disable_view_after=disable_view_after,
            owner_ids={self.author.id, self.bot.owner_id, *self.bot.owner_ids},
            **kwargs
        )

        return await view.send_to(self, wait=wait)

    async def prompt(
        self,
        message: Union[str, discord.Message],
        /,
        *,
        delete_message_on_interact: bool = True,
        remove_view_after: bool = False,
        disable_view_after: bool = True,
        timeout: Optional[float] = 30
    ) -> Optional[bool]:
        """|coro|

        Starts a new confirmation menu in this context's channel.

        .. versionadded:: 1.7

        .. versionchanged:: 2.0
            Rewrote to use `discord.ext.menus`.

        .. versionchanged:: 3.2
            Rewrote to use Discord's interactions menus. This
            resulted in the following kwargs being renamed to
            keep consistency or clarify purpose:

                * ``remove_reactions_after`` -> ``remove_view_after``
                * ``delete_message_after -> ``delete_message_on_interact``

        Parameters
        ----------
        message: Union[:class:`str`, :class:`discord.Message`]
            The prompt message.
            If the message is a :class:`discord.Message`, then
            this will attach the menu to that message.

            .. versionchanged:: 3.0
                This is now a positional-only argument.
        delete_message_on_interact: :class:`bool`
            Whether or not to delete the message when the user
            interacts with the view.
            Defaults to ``True``.
        remove_view_after: :class:`bool`
            Whether or not to remove the view after after it has
            finished interacting.
            Defaults to ``False``.

            .. note::

                ``delete_message_on_interact`` takes priority over
                this setting in terms of cleanup behaviour.

        disable_view_after: :class:`bool`
            Whether or not to disable the view after it has finished
            interacting.
            Defaults to ``True``.

            .. note::

                ``remove_view_after`` and ``delete_message_on_interact``
                takes priority over this setting in terms of cleanup
                behaviour.

            .. versionadded:: 3.2
        timeout: :class:`float`
            The time, in seconds, before the prompt expires.
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
            owner_ids={self.author.id, self.bot.owner_id, *self.bot.owner_ids},
            timeout=timeout
        )

        if isinstance(message, discord.Message):
            message = await message.edit(view=view)
        else:
            message = await self.send(message, view=view)

        timed_out = await view.wait()

        try:
            if not timed_out and delete_message_on_interact:
                await message.delete()
            elif remove_view_after:
                await message.edit(view=None)
            elif disable_view_after and view.children:
                for child in view.children:
                    child.disabled = True  # type: ignore

                await message.edit(view=view)
        except discord.HTTPException:
            pass

        return view.result

    async def disambiguate(
        self,
        matches: Sequence[Any],
        /,
        formatter: Callable[[Any], str] = None,
        *,
        timeout: float = 30
    ) -> Any:
        """|coro|

        Starts a new disambiguation session.

        This allows a user to type a number corresponding to
        their desired option in a given sequence of matching
        items, returning either the item the user picks, or,
        in some cases, the only item in the sequence.

        .. versionadded:: 1.7

        .. versionchanged:: 2.0
            Renamed ``entry`` argument to ``formatter``.

        Parameters
        ----------
        matches: Sequence[Any]
            The matching items to disambiguate.

            .. versionchanged:: 3.0
                This is now a positional-only argument.
        formatter: Optional[Callable[[Any], :class:`str`]]
            A function that returns a string-like result.
            This is used to format the displayed matches.
        timeout: :class:`float`
            How long, in seconds, the user has to respond.
            Defaults to ``30``.

            .. versionadded:: 3.0

        Returns
        -------
        Any
            The item the user picked.

        Raises
        ------
        ValueError
            No results were found, the user took too long to
            respond, or there were too many invalid attempts.
        """
        if not matches:
            raise ValueError("No results found.")

        if len(matches) == 1:
            return matches[0]

        if formatter is None:
            # This is here to provide a slight speedup so we're not
            # unnecessarily calling a function every iteration.
            choices = "\n".join(f"{i}. {m}" for i, m in enumerate(matches, 1))
        else:
            choices = "\n".join(f"{i}. {formatter(m)}" for i, m in enumerate(matches, 1))

        await self.send(
            f"Too many matches. Type the number of the one you meant.\n>>> {choices}"
        )

        def check(m: discord.Message) -> bool:
            return (
                m.channel == self.channel
                and m.author == self.author
                and m.content.isdigit()
                # Filter out zero even though it's technically
                # valid (it returns the last item in matches)
                # in order to prevent confusion from end users.
                and m.content != "0"
            )

        # Essentially, the user will have 3 tries to enter a
        # correct input. After 3 tries, the disambiguation
        # will quit. A timeout will bypass this system and
        # quit the disambiguation anyway.
        for attempt in range(3):
            try:
                message = await self.bot.wait_for("message", check=check, timeout=timeout)
            except asyncio.TimeoutError:
                raise ValueError("You took too long to respond.") from None

            try:
                return matches[int(message.content) - 1]
            except IndexError:
                await self.send(f"Invalid option. {plural(2 - attempt):try|tries} remaining.")

        raise ValueError("Too many invalid attempts. Aborting...")

    async def copy_with(
        self,
        *,
        author: Optional[Union[discord.Member, discord.User]] = None,
        channel: Optional[MessageableChannel] = None,
        **properties: Any
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
        copied_message._update(properties)

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
