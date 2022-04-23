"""
Copyright (c) 2018-present HitchedSyringe

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""


from __future__ import annotations


__all__ = (
    "BaseView",
    "BotLinksView",
    "ConfirmationView",
    "EmbedSource",
    "PaginatorSource",
    "PaginationView",
)


import asyncio
from collections.abc import Collection
from typing import (
    TYPE_CHECKING,
    Any,
    Awaitable,
    Callable,
    Dict,
    Optional,
    Sequence,
    Tuple,
    Union,
    overload,
)

import discord
from discord.ext.menus import ListPageSource, PageSource
from discord.ui import Button, View, button
from discord.utils import MISSING, oauth_url

from .utils import DISCORD_SERVER_URL, GITHUB_URL, PERMISSIONS_VALUE


if TYPE_CHECKING:
    from discord.ext.commands import Bot, Paginator
    from discord.ext.menus import MenuPages
    from discord.ui import Item


class EmbedSource(ListPageSource):
    """A basic data source for a sequence of embeds.

    Subclasses :class:`menus.ListPageSource`.

    .. versionadded:: 2.0

    .. versionchanged:: 3.0
        Renamed ``show_page_numbers`` argument to ``show_page_count``.

    .. versionchanged:: 3.2

        * Removed ``show_page_count`` attribute. Page numbers are now
          natively shown within the pagination menu.
        * Allow ``per_page`` to be set, since bots are now allowed
          to send multiple embeds per message.
    """

    def __init__(
        self,
        entries: Sequence[discord.Embed],
        /,
        *,
        per_page: int = 1
    ) -> None:
        super().__init__(entries, per_page=per_page)

    @overload
    async def format_page(
        self,
        menu: Union[PaginationView, MenuPages],
        page: discord.Embed
    ) -> discord.Embed:
        ...

    @overload
    async def format_page(
        self,
        menu: Union[PaginationView, MenuPages],
        page: Sequence[discord.Embed]
    ) -> Dict[str, Any]:
        ...

    async def format_page(
        self,
        menu: Union[PaginationView, MenuPages],
        page: Union[discord.Embed, Sequence[discord.Embed]]
    ) -> Union[discord.Embed, Dict[str, Any]]:
        return {"embeds": page} if self.per_page > 1 else page  # type: ignore


class PaginatorSource(ListPageSource):
    """A data source for a :class:`commands.Paginator`.

    Subclasses :class:`menus.ListPageSource`.

    .. versionadded:: 3.0

    .. versionchanged:: 3.0
        Renamed ``show_page_numbers`` argument to ``show_page_count``.

    .. versionchanged:: 3.2
        Removed ``show_page_count`` attribute. Page numbers are now
        natively shown within the pagination menu.

    Parameters
    ----------
    paginator: :class:`commands.Paginator`
        The paginator to use as the data source.

    Attributes
    ----------
    paginator: :class:`commands.Paginator`
        The paginator used as the data source.
    """

    def __init__(self, paginator: Paginator, /) -> None:
        self.paginator: Paginator = paginator

        super().__init__(paginator.pages, per_page=1)

    async def format_page(
        self,
        menu: Union[PaginationView, MenuPages],
        page: str
    ) -> str:
        return page


class BaseView(View):
    """Base view class that the custom views inherit from.

    The following implement this base:

    * :class:`.ConfirmationView`
    * :class:`.PaginationView`

    .. versionadded:: 3.2

    Parameters
    ----------
    owner_id: Optional[:class:`int`]
        The user ID that owns the view.
    owner_ids: Optional[Collection[:class:`int`]]
        The user IDs that own the view, similar to :attr:`owner_id`.
        For performance reasons, it is recommended to use a
        :class:`set` for the collection. You cannot set both
        ``owner_id`` and ``owner_ids``.

        .. warning::
            If no owners are set, then all users can interact with
            this view.

    Attributes
    ----------
    owner_id: Optional[:class:`int`]
        The user ID that owns this menu.

        .. versionadded:: 3.3
    owner_ids: Optional[Collection[:class:`int`]]
        The user IDs that own this menu, similar to :attr:`owner_id`.

        .. versionchanged:: 3.3
            This is ``None`` if ``owner_ids`` was not passed.
    """

    def __init__(
        self,
        *,
        timeout: Optional[float] = 180,
        owner_id: Optional[int] = None,
        owner_ids: Optional[Collection[int]] = None
    ) -> None:
        super().__init__(timeout=timeout)

        if owner_ids and owner_id:
            raise TypeError("Both owner_ids and owner_id are set.")

        if owner_ids and not isinstance(owner_ids, Collection):
            raise TypeError(f"owner_ids must be a collection, not {type(owner_ids)!r}")

        self.owner_ids: Optional[Collection[int]] = owner_ids
        self.owner_id: Optional[int] = owner_id

    def reset_timeout(self) -> None:
        """Resets this view's timeout. Does nothing if no timeout was set."""
        super()._refresh_timeout()

    def can_use_menu(self, user: Union[discord.User, discord.Member]) -> bool:
        """:class:`bool`: Indicates whether a given user can use this menu.

        This **always** returns ``True`` if neither :attr:`owner_id` nor
        :attr:`owner_ids` are set, meaning that anyone can use this menu.

        .. versionadded:: 3.3
        """
        if self.owner_id is not None:
            return user.id == self.owner_id

        if self.owner_ids:
            return user.id in self.owner_ids

        return True

    async def interaction_check(self, itn: discord.Interaction) -> bool:
        # interaction.user can be MISSING. I don't know how likely
        # this is or how this would occur, but I'll just handle it
        # anyway and move on.
        if itn.user is MISSING:
            return False

        if not self.can_use_menu(itn.user):
            await itn.response.send_message("You can't use this menu. Sorry.", ephemeral=True)
            return False

        return True


class BotLinksView(View):
    """View class which contains URL buttons leading to
    associated links with the bot.

    Currently, this only includes the following links:

    * Invite URL (generated via :func:`discord.utils.oauth_url`)
    * Discord Server (returned via `~.utils.DISCORD_SERVER_URL`)
    * GitHub Repository (returned via `~.utils.GITHUB_URL`)

    .. versionadded:: 3.2

    Parameters
    ----------
    client_id: int
        The client's user ID.
    """

    buttons: Tuple[Button, ...]

    def __init__(self, client_id: int) -> None:
        super().__init__(timeout=None)

        invite = oauth_url(client_id, permissions=discord.Permissions(PERMISSIONS_VALUE))

        self.buttons = buttons = (
            Button(label="Invite me!", emoji="\N{INBOX TRAY}", url=invite),
            Button(label="Server", emoji="<:dc:871952362175086624>", url=DISCORD_SERVER_URL),
            Button(label="GitHub", emoji="<:gh:871952362019901502>", url=GITHUB_URL)
        )

        for button in buttons:
            self.add_item(button)


class ConfirmationView(BaseView):
    """A standard yes/no confirmation prompt view.

    This is a lower level interface to :meth:`Context.prompt`
    in case you do not want the extra handling and features.

    .. versionadded:: 3.2

    Attributes
    ----------
    result: Optional[:class:`bool`]
        Whether the user clicked the ``confirm`` button.
        ``None`` if this view expired.
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.result: Optional[bool] = None

    @button(emoji="<:check:821284209401921557>", style=discord.ButtonStyle.green)
    async def confirm(self, itn: discord.Interaction, button: Button) -> None:
        self.result = True
        self.stop()

    @button(emoji="<:x_:821284209792516096>", style=discord.ButtonStyle.red)
    async def deny(self, itn: discord.Interaction, button: Button) -> None:
        self.result = False
        self.stop()


class PaginationView(BaseView):
    """A view which allows for pagination of items.

    This view is mostly based off of :class:`menus.MenuPages`
    and runs similar to it, the only difference being that
    the new interactions system is used rather than reactions.
    This is also fully compatible with :class:`menu.PageSource`
    instances.

    .. warning::

        Due to implementation details regarding the :class:`View`
        and :class:`PageSource` classes, this view **cannot** be
        sent via :meth:`Messageable.send` as there is necessary
        setup that must be done beforehand. Calling either the
        :meth:`send_to`, :meth:`attach_to`, or :meth:`reply_to`
        methods is preferred as these will interally perform the
        setup for you.

    .. versionadded:: 3.2

    Parameters
    ----------
    bot: :class:`commands.Bot`
        The bot instance.
    source: :class:`menus.PageSource`
        The page source to paginate.
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

    Attributes
    ----------
    bot: :class:`commands.Bot`
        The passed bot instance.
    current_page: :class:`int`
        The current page that we are on.
        Zero-indexed between [0, :attr:`PageSource.max_pages`).
    message: Optional[:class:`discord.Message`]
        This view's message.
        ``None`` if this wasn't initially set through either
        :meth:`send_to`, :meth:`attach_to`, :meth:`reply_to`,
        or otherwise.
    """

    def __init__(
        self,
        bot: Bot,
        source: PageSource,
        *,
        delete_message_when_stopped: bool = False,
        remove_view_after: bool = False,
        disable_view_after: bool = True,
        **kwargs: Any
    ) -> None:
        super().__init__(**kwargs)

        self._delete_message_when_stopped: bool = delete_message_when_stopped
        self._remove_view_after: bool = remove_view_after
        self._disable_view_after: bool = disable_view_after

        self._lock: asyncio.Lock = asyncio.Lock()
        self._source: PageSource = source

        self.bot: Bot = bot
        self.current_page: int = 0
        self.message: Optional[discord.Message] = None

        self.clear_items()
        self._do_items_setup()

    @property
    def source(self) -> PageSource:
        """:class:`menus.PageSource`: The source where the data comes from."""
        return self._source

    async def _get_kwargs_from_page(self, page: int) -> Dict[str, Any]:
        data = await discord.utils.maybe_coroutine(self._source.format_page, self, page)  # type: ignore

        if isinstance(data, dict):
            return data

        if isinstance(data, str):
            return {"content": data, "embed": None}

        if isinstance(data, discord.Embed):
            return {"content": None, "embed": data}

        return {}

    async def _do_items_cleanup(self) -> None:
        if self._remove_view_after:
            await self.message.edit(view=None)  # type: ignore
            return

        if self._disable_view_after:
            for child in self.children:
                child.disabled = True  # type: ignore

            await self.message.edit(view=self)  # type: ignore

    def _do_items_setup(self) -> None:
        if not self._source.is_paginating():
            return

        max_pages = self._source.get_max_pages()
        more_than_two = max_pages is not None and max_pages > 2

        if more_than_two:
            self.add_item(self.first_page)

        self.add_item(self.previous_page)
        self.add_item(self.page_number)
        self.add_item(self.next_page)

        if more_than_two:
            self.add_item(self.last_page)

        self.add_item(self.stop_menu)

        if more_than_two:
            self.add_item(self.select_page)

        self._update_items(0)

    async def _start(
        self,
        action: Callable[..., Awaitable[discord.Message]],
        *,
        wait: bool,
        mention_author: Optional[bool] = None
    ) -> discord.Message:
        await self._source._prepare_once()

        page = await self._source.get_page(0)
        kwargs = await self._get_kwargs_from_page(page)

        # Message.edit doesn't take the mention_author kwarg.
        if mention_author is not None:
            kwargs["mention_author"] = mention_author

        self.message = message = await action(**kwargs, view=self)

        if wait:
            await self.wait()

        return message

    def _update_items(self, page_number: int) -> None:
        on_first = page_number == 0

        self.first_page.disabled = on_first
        self.previous_page.disabled = on_first

        if (max_pages := self._source.get_max_pages()) is None:
            self.page_number.label = self.current_page + 1  # type: ignore
            return

        self.page_number.label = f"{self.current_page + 1} / {max_pages}"

        on_last = page_number == max_pages - 1

        self.next_page.disabled = on_last
        self.last_page.disabled = on_last

    async def reply_to(
        self,
        message: discord.Message,
        *,
        mention_author: Optional[bool] = None,
        wait: bool = False
    ) -> discord.Message:
        """|coro|

        Sends the view as a reply to the given message.

        This is a convenience method for doing the necessary
        setup for this view.

        Parameters
        ----------
        message: :class:`discord.Message`
            The message to reply to.
        mention_author: Optional[:class:`bool`]
            Whether or not to mention the replied message author.
            If not set, the defaults given by ``allowed_mentions``
            are used instead.
            Defaults to ``None``.
        wait: :class:`bool`
            Whether or not to wait until the view has finished
            interacting before returning back to the caller.
            Defaults to ``False``.

        Returns
        -------
        :class:`discord.Message`
            The message that was sent as a reply.
        """
        return await self._start(message.reply, wait=wait, mention_author=mention_author)

    async def attach_to(
        self,
        message: discord.Message,
        *,
        wait: bool = False
    ) -> discord.Message:
        """|coro|

        Attaches the view to the given message.

        This is a convenience method for doing the necessary
        setup for this view.

        Parameters
        ----------
        message: :class:`discord.Message`
            The message to attach the view to.
        wait: :class:`bool`
            Whether or not to wait until the view has finished
            interacting before returning back to the caller.
            Defaults to ``False``.

        Returns
        -------
        :class:`discord.Message`
            The message that was edited.
        """
        return await self._start(message.edit, wait=wait)

    async def send_to(
        self,
        destination: discord.abc.Messageable,
        *,
        wait: bool = False
    ) -> discord.Message:
        """|coro|

        Sends the view to the given destination.

        This is a convenience method for doing the necessary
        setup for this view.

        Parameters
        ----------
        destination: :class:`discord.abc.Messageable`
            The destination to send the view.
        wait: :class:`bool`
            Whether or not to wait until the view has finished
            interacting before returning back to the caller.
            Defaults to ``False``.

        Returns
        -------
        :class:`discord.Message`
            The message that was sent.
        """
        return await self._start(destination.send, wait=wait)

    async def change_source(self, source: PageSource) -> None:
        """|coro|

        Changes the :class:`menus.PageSource` to a different
        one at runtime.

        Once the change has been set, the view is moved to
        the first page of the new source if it was started.
        This effectively changes the :attr:`current_page`
        to 0.

        .. versionchanged:: 3.3
            Raise :exc:`RuntimeError` if :attr:`message` is ``None``.

        Raises
        ------
        TypeError
            A :class:`menus.PageSource` was not passed.
        RuntimeError
            This view didn't have an associated message to edit,
            that is, :attr:`message` was left as ``None``.
        """
        if not isinstance(source, PageSource):
            raise TypeError(f"Expected PageSource, not {type(source)!r}.")

        self._source = source
        self.current_page = 0

        self.clear_items()
        self._do_items_setup()

        await source._prepare_once()
        await self.show_page(0)

    async def show_page(self, page_number: int) -> None:
        """|coro|

        Shows the page at the given page number and updates
        this view.

        Page numbers are zero-indexed between `[0, n)` where n
        is the page source's maximum page count, if applicable,
        as provided by :meth:`PageSource.get_max_pages`.

        .. versionchanged:: 3.3
            Raise :exc:`RuntimeError` if :attr:`message` is ``None``.

        Parameters
        ----------
        page_number: :class:`int`
            The page number to show.

        Raises
        ------
        RuntimeError
            This view didn't have an associated message to edit,
            that is, :attr:`message` was left as ``None``.
        """
        if self.message is None:
            raise RuntimeError("PaginationView has no associated message to edit.")

        self.current_page = page_number

        page = await self._source.get_page(page_number)
        kwargs = await self._get_kwargs_from_page(page)

        self._update_items(page_number)
        self.message = await self.message.edit(**kwargs, view=self)  # type: ignore

    async def show_checked_page(self, page_number: int) -> None:
        """|coro|

        Similar to :meth:`show_page`, but runs some checks
        on the given page number before actually showing
        the page. This does nothing if the page number is
        invalid, i.e. doesn't point to a page.

        .. versionchanged:: 3.3
            Raise :exc:`RuntimeError` if :attr:`message` is ``None``.

        Parameters
        ----------
        page_number: :class:`int`
            The page number to show.

        Raises
        ------
        RuntimeError
            This view didn't have an associated message to edit,
            that is, :attr:`message` was left as ``None``.
        """
        max_pages = self._source.get_max_pages()

        if max_pages is not None and not 0 <= page_number < max_pages:
            return

        try:
            await self.show_page(page_number)
        except IndexError:
            pass

    async def on_timeout(self) -> None:
        try:
            await self._do_items_cleanup()
        except discord.HTTPException:
            pass

    async def on_error(self, itn: discord.Interaction, item: Item, error: Exception) -> None:
        if itn.response.is_done():
            await itn.followup.send("Sorry, but something went wrong.", ephemeral=True)
        else:
            await itn.response.send_message("Sorry, but something went wrong.", ephemeral=True)

    @button(emoji="<:rrwnd:862379040802865182>")
    async def first_page(self, itn: discord.Interaction, button: Button) -> None:
        await self.show_page(0)

    @button(emoji="<:back:862407042172715038>")
    async def previous_page(self, itn: discord.Interaction, button: Button) -> None:
        await self.show_checked_page(self.current_page - 1)

    @button(style=discord.ButtonStyle.primary, disabled=True)
    async def page_number(self, itn: discord.Interaction, button: Button) -> None:
        pass

    @button(emoji="<:fwd:862407042114125845>")
    async def next_page(self, itn: discord.Interaction, button: Button) -> None:
        await self.show_checked_page(self.current_page + 1)

    @button(emoji="<:ffwd:862378579794460723>")
    async def last_page(self, itn: discord.Interaction, button: Button) -> None:
        # This call is safe since the button itself is already
        # handled initially when the view starts.
        await self.show_page(self._source.get_max_pages() - 1)

    @button(emoji="\N{OCTAGONAL SIGN}", label="Stop", style=discord.ButtonStyle.danger)
    async def stop_menu(self, itn: discord.Interaction, button: Button) -> None:
        self.stop()

        if self._delete_message_when_stopped:
            await self.message.delete()  # type: ignore
        else:
            self._remove_view_after = True
            await self._do_items_cleanup()

    @button(emoji="\N{PAGE WITH CURL}", label="Jump to page...")
    async def select_page(self, itn: discord.Interaction, button: Button) -> None:
        if self._lock.locked():
            await itn.response.send_message("I'm already awaiting your response.", ephemeral=True)
            return

        async with self._lock:
            old_timeout = self.timeout

            if old_timeout is not None:
                self.timeout = old_timeout + 35

            await itn.response.send_message("Type the page number to jump to.", ephemeral=True)

            def page_check(m: discord.Message) -> bool:
                return (
                    m.channel == self.message.channel  # type: ignore
                    and self.can_use_menu(m.author)
                    and m.content.isdigit()
                    and m.content != "0"
                )

            # Since we wait for quite a while, we'll want to make
            # sure the menu hasn't been killed yet within the 30s
            # of waiting when either an answer is received or the
            # waiter times out.

            try:
                message = await self.bot.wait_for("message", check=page_check, timeout=30)
            except asyncio.TimeoutError:
                if not self.is_finished():
                    await itn.followup.send("You took too long to respond.", ephemeral=True)
                    await asyncio.sleep(5)

                return

            if self.is_finished():
                return

            if old_timeout is not None:
                self.timeout = old_timeout

            await self.show_checked_page(int(message.content) - 1)

            try:
                await message.delete()
            except discord.HTTPException:
                pass
