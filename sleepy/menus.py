"""
Copyright (c) 2018-present HitchedSyringe

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""


__all__ = (
    "ConfirmationPrompt",
    "EmbedSource",
    "PaginationMenu",
    "PaginatorSource",
)


import asyncio

import discord
from discord.ext import menus


class EmbedSource(menus.ListPageSource):
    """A basic data source for a sequence of embeds.

    This class subclasses :class:`menus.ListPageSource` and, as a
    result, anything you can do with :class:`menus.ListPageSource`,
    you can also do with this page source.

    .. versionadded:: 2.0

    Parameters
    ----------
    show_page_count: :class:`bool`
        Whether or not to show the page count on every page.
        If the source only has one page, then the page count
        will be hidden regardless of this setting.
        Defaults to ``True``.

        .. versionchanged:: 3.0
            Renamed to ``show_page_count``.
    """

    def __init__(self, entries, /, *, show_page_count=True):
        super().__init__(entries, per_page=1)

        self._show_page_count = show_page_count

    async def format_page(self, menu, page):
        max_pages = self.get_max_pages()

        if self._show_page_count and max_pages > 1:
            return {
                "embed": page,
                "content": f"Page {menu.current_page + 1}/{max_pages}"
            }

        return page


class PaginatorSource(menus.ListPageSource):
    """A data source for a :class:`commands.Paginator`.

    This class subclasses :class:`menus.ListPageSource` and, as a
    result, anything you can do with :class:`menus.ListPageSource`,
    you can also do with this page source.

    .. versionadded:: 3.0

    Parameters
    ----------
    paginator: :class:`commands.Paginator`
        The paginator to use as the data source.
    show_page_count: :class:`bool`
        Whether or not to show the page count on every page.
        If the source only has one page, then the page count
        will be hidden regardless of this setting.
        Defaults to ``True``.

        .. note::

            This does **not** consider the paginator's max
            page size.

        .. versionchanged:: 3.0
            Renamed to ``show_page_count``.

    Attributes
    ----------
    paginator: :class:`commands.Paginator`
        The paginator used as the data source.
    """

    def __init__(self, paginator, /, *, show_page_count=True):
        self.paginator = paginator
        self._show_page_count = show_page_count

        super().__init__(paginator.pages, per_page=1)

    async def format_page(self, menu, page):
        max_pages = self.get_max_pages()

        if self._show_page_count and max_pages > 1:
            page += f"Page {menu.current_page + 1}/{max_pages}"

        return page


class ConfirmationPrompt(menus.Menu):
    """A standard yes/no confirmation prompt.

    This class is a subclass of :class:`menus.Menu`, and as
    a result, anything you can do with a :class:`menus.Menu`,
    you can do with this menu.

    .. note::

        ``delete_message_after`` only modifies the reaction
        behaviour, not the timeout behaviour. This means the
        menu's message will **not** be deleted upon timeout.

    .. versionadded:: 2.0

    Parameters
    ----------
    message: Union[:class:`str`, :class:`discord.Message`]
        The message to attach the menu to.
        If the message is a :class:`str`, then the menu
        will send a new message with the given content.
    """

    def __init__(self, message, /, *, timeout=30, delete_message_after=True):
        super().__init__(timeout=timeout, delete_message_after=delete_message_after)

        if isinstance(message, discord.Message):
            self.message = message
        else:
            self._prompt_message = str(message)

        self._result = None

    async def send_initial_message(self, ctx, channel):
        return await channel.send(self._prompt_message)

    @menus.button("<:check:821284209401921557>")
    async def confirm(self, payload):
        self._result = True
        self.stop()

    @menus.button("<:x_:821284209792516096>")
    async def deny(self, payload):
        self._result = False
        self.stop()

    async def start(self, ctx, /, *, channel=None):
        """|coro|

        Starts the confirmation prompt.

        .. versionchanged:: 3.0
            Renamed to ``start``.

        Parameters
        ----------
        ctx: :class:`commands.Context`
            The invocation context to use.
        channel: Optional[:class:`discord.abc.Messageable`]
            The messageable to start the menu in.
            Defaults to the given context's channel if ``None``.

            .. versionadded:: 3.0

        Returns
        -------
        Optional[:class:`bool`]
            Whether or not the user confirmed the prompt.
            ``None`` if the prompt expired.
        """
        await super().start(ctx, channel=channel, wait=True)
        return self._result

    async def finalize(self, timed_out):
        if not timed_out:
            return

        self.delete_message_after = False

        try:
            await self.message.add_reaction("\N{ALARM CLOCK}")
        except discord.HTTPException:
            pass


class PaginationMenu(menus.MenuPages, inherit_buttons=False):
    """A pagination menu with some extra buttons and features.

    This class subclasses of :class:`menus.MenuPages`, and as
    a result, anything you can do with a :class:`menus.MenuPages`,
    you can do with this pagination menu.

    .. note::

        ``delete_message_after`` only modifies the reaction
        behaviour, not the timeout behaviour. This means the
        menu's message will **not** be deleted upon timeout.

    .. versionadded:: 2.0

    .. versionchanged:: 3.0
        Renamed to ``PaginationMenu``.
    """

    def __init__(self, source, /, *, delete_message_after=True, **kwargs):
        super().__init__(source, delete_message_after=delete_message_after, **kwargs)

        # Numbered page spam protection.
        self._choose_page_lock = asyncio.Semaphore()

    async def show_page_lazy(self, page_number, /, *, check_page_number=False):
        """|coro|

        Similar to :meth:`show_page`, except the page does
        not update if the given page number is the current
        page.

        .. versionadded:: 3.0

        Parameters
        ----------
        page_number: :class:`int`
            The page number to turn to.
        check_page_number: :class:`bool`
            Whether or not to check the given page number.
            Defaults to ``False``.
        """
        if self.current_page == page_number:
            return

        if check_page_number:
            await self.show_checked_page(page_number)
        else:
            await self.show_page(page_number)

    def _skip_double_triangle_buttons(self):
        return super()._skip_double_triangle_buttons()

    @menus.button(
        "<:rrwnd:862379040802865182>",
        position=menus.First(0),
        skip_if=_skip_double_triangle_buttons
    )
    async def go_to_first_page(self, payload):
        """Goes to the first page."""
        await self.show_page_lazy(0)

    @menus.button("<:back:862407042172715038>", position=menus.First(1))
    async def go_to_previous_page(self, payload):
        """Goes to the previous page."""
        await self.show_page_lazy(self.current_page - 1, check_page_number=True)

    @menus.button("<:fwd:862407042114125845>", position=menus.Last(0))
    async def go_to_next_page(self, payload):
        """Goes to the next page."""
        await self.show_page_lazy(self.current_page + 1, check_page_number=True)

    @menus.button(
        "<:ffwd:862378579794460723>",
        position=menus.Last(1),
        skip_if=_skip_double_triangle_buttons
    )
    async def go_to_last_page(self, payload):
        """Goes to the last page."""
        await self.show_page_lazy(self._source.get_max_pages() - 1)

    @menus.button("<:stop:862426265306923019>", position=menus.Last(2))
    async def stop_pages(self, payload):
        """Stops the pagination session."""
        self.delete_message_after = True
        self.stop()

    @menus.button(
        "<:123:862424263645986816>",
        position=menus.Last(3),
        skip_if=_skip_double_triangle_buttons,
        lock=False
    )
    async def choose_page(self, payload):
        """Allows you to type a page number to jump to."""
        if self._choose_page_lock.locked():
            return

        channel = self.message.channel
        to_delete = [await channel.send("Type the page number you wish to jump to.")]

        def page_check(m):
            return (
                m.channel == channel
                and m.author.id in (payload.user_id, self.bot.owner_id, *self.bot.owner_ids)
                and m.content.isdigit()
            )

        async with self._choose_page_lock:
            try:
                message = await self.bot.wait_for("message", check=page_check, timeout=30)

                # Since we wait for quite a while, we'll want to make
                # sure the menu hasn't been killed yet when either an
                # answer is received or the waiter times out.
                if not self._running:
                    return
            except asyncio.TimeoutError:
                to_delete.append(await channel.send("You took too long to respond."))
                await asyncio.sleep(5)
            else:
                to_delete.append(message)
                await self.show_page_lazy(int(message.content) - 1, check_page_number=True)

        try:
            await channel.delete_messages(to_delete)
        except discord.HTTPException:
            pass

    @menus.button("<:q_:862417417199157289>", position=menus.Last(4), lock=False)
    async def show_paginator_help(self, payload):
        """Shows this page."""
        help_text = (
            "**Pagination Menu Help**"
            "\n\nWelcome to the interactive pagination menu!"
            "\nThis allows you to navigate pages by simply __adding or removing__ reactions."
            "\nThe reactions this menu uses are as follows:\n\n"
            + "\n".join(f"> {e} | {b.action.__doc__}" for e, b in self.buttons.items())
            + f"\n\nWe were on page {self.current_page + 1} before this message."
        )

        # Make this button lazy.
        if self.message.content == help_text:
            return

        await self.message.edit(content=help_text, embed=None)
        await asyncio.sleep(60)

        if self._running:
            await self.show_page(self.current_page)
