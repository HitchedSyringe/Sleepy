"""
© Copyright 2018-2020 HitchedSyringe, All Rights Reserved.

Redistributing, using or owning a copy of this software without explicit permissions
is against these licensing terms, your license(s) to this software can be revoked at
any time without explicit notice beforehand and at the time of revocation.
Your license is non-transferrable, the terms of this license only permit you to do the
following; Create pull requests and make modifications to this repository.

"""


__all__ = ("ContentSource", "EmbedSource", "ConfirmationPrompt", "PaginatorInterface")


import asyncio

import discord
from discord import Embed
from discord.ext import commands, menus


class ContentSource(menus.ListPageSource):
    """A basic data source for a sequence of content strings.
    This takes :class:`str`, List[:class:`str`], and :class:`commands.Paginator`

    This class is a subclass of :class:`menus.ListPageSource` and as a result,
    anything you can do with :class:`menus.ListPageSource`, you can also do with this page source.

    Attributes
    ----------
    paginator: :class:`commands.Paginator`
        The paginator derived from the data.
    """

    def __init__(self, data, *, prefix: str = "", suffix: str = "", max_size: int = 1980,
                 per_page: int = 1, show_page_numbers: bool = True):
        self._show_page_numbers = show_page_numbers

        if not isinstance(data, commands.Paginator):
            self.paginator = commands.Paginator(prefix=prefix, suffix=suffix, max_size=max_size)

            if isinstance(data, str):
                split = data.split('\n')
                for line in split:
                    self.paginator.add_line(line)
            elif isinstance(data, list):
                for line in data:
                    self.paginator.add_line(line)
        else:
            self.paginator = data

        super().__init__(self.paginator.pages, per_page=per_page)


    async def format_page(self, menu, page):
        if self._show_page_numbers and self.is_paginating():
            page += f"Page {menu.current_page + 1}/{self.get_max_pages()}"
        return page


class EmbedSource(menus.ListPageSource):
    """A basic data source for a sequence of embeds.
    This takes a List[:class:`discord.Embed`].

    This class is a subclass of :class:`menus.ListPageSource` and as a result,
    anything you can do with :class:`menus.ListPageSource`, you can also do with this page source.
    """

    def __init__(self, data, *, show_page_numbers: bool = True):
        self._show_page_numbers = show_page_numbers

        super().__init__(data, per_page=1)


    async def format_page(self, menu, page):
        if self._show_page_numbers and self.is_paginating():
            # This is mainly to not overwrite the footer, however, it may look a bit jarring.
            return {"embed": page, "content": f"Page {menu.current_page + 1}/{self.get_max_pages()}"}
        return page


# Somewhat derived from the README on GitHub.
class ConfirmationPrompt(menus.Menu):
    """A standard yes/no confirmation prompt.

    This class is a subclass of :class:`menus.Menu` and as a result,
    anything you can do with a :class:`menus.Menu`, you can do with this menu.
    """

    def __init__(self, prompt_message, *, timeout, delete_message_after=True):
        super().__init__(timeout=timeout, delete_message_after=delete_message_after)

        if isinstance(prompt_message, discord.Message):
            self.message = prompt_message
        else:
            self._prompt_message = str(prompt_message)

        self._result = None


    async def send_initial_message(self, ctx, channel):
        return await self.ctx.send(self._prompt_message)


    @menus.button("<:checkmark:512814665705979914>")
    async def confirm(self, payload):
        self._result = True
        self.stop()


    @menus.button("<:xmark:512814698136076299>", position=menus.Last(2))
    async def deny(self, payload):
        self._result = False
        self.stop()


    async def prompt(self, ctx):
        """|coro|

        Starts the confirmation prompt.

        Parameters
        -----------
        ctx: :class:`commands.Context`
            The invocation context to use.

        Returns
        -------
        Optional[:class:`bool`]
            Whether or not the prompt was confirmed by the user.
            Returns ``None`` if the prompt expired.

        Raises
        -------
        :exc:`menus.MenuError`
            An error occurred when verifying permissions.
        :exc:`discord.HTTPException`
            Adding a reaction failed.
        """
        await self.start(ctx, wait=True)
        return self._result


class PaginatorInterface(menus.MenuPages):
    """A message and reaction-based pagination menu.

    This class is a subclass of :class:`menus.MenuPages` and as a result,
    anything you can do with a :class:`menus.MenuPages`, you can do with this pagination menu.
    """

    def __init__(self, source, *, delete_message_after=True, **kwargs):
        super().__init__(source, delete_message_after=delete_message_after, **kwargs)

        self._task = None
        self._update_lock = asyncio.Semaphore(value=2)


    async def update(self, payload):
        async with self._update_lock:
            if self._update_lock.locked():
                # We're being overloaded, or a button is taking its sweet time,
                # so just ignore any button presses for the time being.
                return

            if isinstance(self._task, asyncio.Task):
                self._task.cancel()

            await super().update(payload)


    # NOTE: The default method throws AttributeError when used.
    # This is because the method incorrectly uses ``paginating`` (which PageSource doesn't have)
    # instead of ``is_paginating``. Maybe Danny forgot to properly port this bit over from RoboDanny?
    # As of writing, this issue has yet to be fixed, so for the time being, just override it with the fix.
    async def show_current_page(self):
        if self._source.is_paginating():
            await self.show_page(self.current_page)


    async def finalize(self, timed_out):
        # In case of an outstanding task.
        if isinstance(self._task, asyncio.Task):
            self._task.cancel()


    def _less_than_two_pages(self):
        """Same as :meth:`Menupages._skip_double_triangle_buttons`.
        For internal use only.
        """
        return super()._skip_double_triangle_buttons()


    @menus.button("\N{BLACK LEFT-POINTING TRIANGLE}\ufe0f", position=menus.First(1))
    async def go_to_previous_page(self, payload):
        """Goes to the previous page."""
        await super().go_to_previous_page(payload)


    @menus.button("\N{BLACK RIGHT-POINTING TRIANGLE}\ufe0f", position=menus.Last(0))
    async def go_to_next_page(self, payload):
        """Goes to the next page."""
        await super().go_to_next_page(payload)


    # Essentially, the double triangle buttons have the same behaviour as the default,
    # but the only difference is that we don't do anything if we're either on the
    # first or last page of the paginator.
    @menus.button("\N{BLACK LEFT-POINTING DOUBLE TRIANGLE WITH VERTICAL BAR}\ufe0f",
                  position=menus.First(0), skip_if=_less_than_two_pages)
    async def go_to_first_page(self, payload):
        """Goes to the first page."""
        if self.current_page != 0:
            await self.show_page(0)


    @menus.button("\N{BLACK RIGHT-POINTING DOUBLE TRIANGLE WITH VERTICAL BAR}\ufe0f",
                  position=menus.Last(1), skip_if=_less_than_two_pages)
    async def go_to_last_page(self, payload):
        """Goes to the last page."""
        last_page = self._source.get_max_pages() - 1
        if self.current_page != last_page:
            await self.show_page(last_page)


    @menus.button("\N{BLACK SQUARE FOR STOP}\ufe0f", position=menus.Last(2))
    async def stop_pages(self, payload):
        """Stops the pagination session."""
        await super().stop_pages(payload)


    # Lock status shouln't matter on this one.
    @menus.button("\N{INPUT SYMBOL FOR NUMBERS}", position=menus.Last(1), skip_if=_less_than_two_pages, lock=False)
    async def select_page(self, payload):
        """Allows you to type a page number to navigate to."""
        to_delete = [await self.ctx.send("What page do you want to navigate to? **Only type the page number.**")]

        def is_page_number(message):
            checks = (
                message.channel.id == self.ctx.channel.id,
                message.author.id in (self._author_id, *self.bot.owner_ids),
                message.content.isdigit(),
            )
            return all(checks)

        try:
            message = await self.bot.wait_for("message", check=is_page_number, timeout=30)
        except asyncio.TimeoutError:
            to_delete.append(await self.ctx.send("You took too long to respond."))
            await asyncio.sleep(4)
        else:
            to_delete.append(message)

            page_number = int(message.content)
            max_pages = self.source.get_max_pages()
            if page_number == 0 or page_number > max_pages:
                to_delete.append(await self.ctx.send(f"Page number must be between 1 and {max_pages}."))
                await asyncio.sleep(4)
            else:
                await self.show_page(page_number - 1)

        try:
            await self.message.channel.delete_messages(to_delete)
        except discord.HTTPException:  # Can't do it so just ignore.
            pass


    @menus.button("\N{INFORMATION SOURCE}\ufe0f", position=menus.Last(2))
    async def show_paginator_help(self, payload):
        """Shows this page."""
        message = [
            ">>> **Menu Help**\n",
            "Welcome to the interactive pagination menu!",
            "This allows you to navigate through pages of text by simply using reactions.",
            "Note: Unlike other paginator menus, this responds to both adding and removing reactions.",
            "The reactions this menu uses are as follows:\n",
        ]

        for emoji, button in self.buttons.items():
            message.append(f"{emoji} {button.action.__doc__}")

        message.append(f"\nWe were on page {self.current_page + 1} before this message.")

        await self.message.edit(content="\n".join(message), embed=None)

        async def _back_to_current_page():
            await asyncio.sleep(45)
            await self.show_current_page()

        self._task = self.bot.loop.create_task(_back_to_current_page())