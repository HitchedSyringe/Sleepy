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


from collections.abc import Collection
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional, Sequence, Union, overload

import discord
from discord.ext.menus import ListPageSource, PageSource
from discord.ui import Button, Modal, Select, TextInput, View, button, select
from discord.utils import MISSING, oauth_url

from .utils import DISCORD_SERVER_URL, PERMISSIONS_VALUE, SOURCE_CODE_URL

if TYPE_CHECKING:
    from discord.ext.commands import Context, Paginator
    from discord.ext.menus import MenuPages
    from discord.ui import Item


class EmbedSource(ListPageSource):
    """A basic data source for a sequence of embeds.

    Subclasses :class:`menus.ListPageSource`.

    .. versionadded:: 2.0

    .. versionchanged:: 3.0
        Renamed ``show_page_numbers`` parameter to ``show_page_count``.

    .. versionchanged:: 3.2

        * Removed ``show_page_count`` parameter. Page numbers are now
          natively shown within the pagination menu.
        * Allow ``per_page`` parameter to be set, since bots are now
          allowed to send multiple embeds per message.
    """

    def __init__(self, entries: Sequence[discord.Embed], *, per_page: int = 1) -> None:
        super().__init__(entries, per_page=per_page)

    @overload
    async def format_page(
        self, menu: Union[PaginationView, MenuPages], page: discord.Embed
    ) -> discord.Embed:
        ...

    @overload
    async def format_page(
        self, menu: Union[PaginationView, MenuPages], page: Sequence[discord.Embed]
    ) -> Dict[str, Any]:
        ...

    async def format_page(
        self,
        menu: Union[PaginationView, MenuPages],
        page: Union[discord.Embed, Sequence[discord.Embed]],
    ) -> Union[discord.Embed, Dict[str, Any]]:
        return {"embeds": page} if self.per_page > 1 else page  # type: ignore


class PaginatorSource(ListPageSource):
    """A data source for a :class:`commands.Paginator`.

    Subclasses :class:`menus.ListPageSource`.

    .. versionadded:: 3.0

    .. versionchanged:: 3.0
        Renamed ``show_page_numbers`` parameter to ``show_page_count``.

    .. versionchanged:: 3.2
        Removed ``show_page_count`` parameter. Page numbers are now
        natively shown within the pagination menu.

    Parameters
    ----------
    paginator: :class:`commands.Paginator`
        The paginator to use as the data source.

        .. versionchanged:: 3.3
            This is no longer a positional-only argument.

    Attributes
    ----------
    paginator: :class:`commands.Paginator`
        The paginator used as the data source.
    """

    def __init__(self, paginator: Paginator) -> None:
        self.paginator: Paginator = paginator

        super().__init__(paginator.pages, per_page=1)

    async def format_page(self, menu: Union[PaginationView, MenuPages], page: str) -> str:
        return page


class _DisambiguationSource(ListPageSource):
    def __init__(
        self,
        matches: Sequence[Any],
        formatter: Optional[Callable[[Any], str]] = None,
        *,
        sort: bool = False,
    ) -> None:
        self._formatter: Optional[Callable[[Any], str]] = formatter

        if sort:
            matches = sorted(matches, key=formatter)

        super().__init__(matches, per_page=6)

    async def format_page(self, menu: _DisambiguationView, page: Sequence[Any]) -> str:
        page_content = ""
        menu.dropdown.options.clear()

        for index, match in enumerate(page, menu.current_page * self.per_page):
            if self._formatter is not None:
                match = self._formatter(match)

            page_content += f"\n\N{BULLET} {match}"

            menu.dropdown.add_option(label=match, value=str(index))

        return f"**Too many matches. Which one did you mean?**{page_content}"


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
        owner_ids: Optional[Collection[int]] = None,
    ) -> None:
        super().__init__(timeout=timeout)

        if owner_ids and owner_id:
            raise TypeError("Both owner_ids and owner_id are set.")

        if owner_ids and not isinstance(owner_ids, Collection):
            raise TypeError(
                f"owner_ids must be a collection, not {type(owner_ids).__name__}"
            )

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

        if self.can_use_menu(itn.user):
            return True

        await itn.response.send_message("You can't use this menu. Sorry.", ephemeral=True)
        return False

    async def on_error(
        self, itn: discord.Interaction, error: Exception, item: Item["BaseView"]
    ) -> None:
        if itn.response.is_done():
            await itn.followup.send("Sorry, but something went wrong.", ephemeral=True)
        else:
            await itn.response.send_message(
                "Sorry, but something went wrong.", ephemeral=True
            )


class BotLinksView(View):
    """View class which contains URL buttons leading to
    associated links with the bot.

    Currently, this only includes the following links:

    * Invite URL (generated via :func:`discord.utils.oauth_url`)
    * Discord Server (returned via `~.utils.DISCORD_SERVER_URL`)
    * Source Code (returned via `~.utils.SOURCE_CODE_URL`)

    .. versionadded:: 3.2

    Parameters
    ----------
    client_id: int
        The client's user ID.
    """

    def __init__(self, client_id: int) -> None:
        super().__init__(timeout=None)

        invite = oauth_url(client_id, permissions=discord.Permissions(PERMISSIONS_VALUE))

        buttons = (
            Button(label="Invite me!", emoji="\N{INBOX TRAY}", url=invite),
            Button(
                label="Support Server",
                emoji="<:dc:871952362175086624>",
                url=DISCORD_SERVER_URL,
            ),
            Button(
                label="Source Code", emoji="<:gh:871952362019901502>", url=SOURCE_CODE_URL
            ),
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
    async def confirm(
        self, itn: discord.Interaction, button: Button["ConfirmationView"]
    ) -> None:
        self.result = True
        self.stop()

    @button(emoji="<:x_:821284209792516096>", style=discord.ButtonStyle.red)
    async def deny(
        self, itn: discord.Interaction, button: Button["ConfirmationView"]
    ) -> None:
        self.result = False
        self.stop()


class _PageSelectModal(Modal, title="Jump to page"):

    page_number_input: TextInput["_PageSelectModal"] = TextInput(
        label="What page do you want to go to?",
        placeholder="Type the page number here.",
        min_length=1,
    )

    def __init__(self, view: PaginationView) -> None:
        self.view: PaginationView = view

        max_pages = view.source.get_max_pages()

        # Should be fine doing this without a check since this modal
        # can never be initialized if the page source doesn't have a
        # max page count.
        self.page_number_input.max_length = len(str(max_pages))

        # Doing this will fail if the view source changes while this
        # modal is active. I doubt this will happen, however.
        self._source_max_pages: int = max_pages

        super().__init__()

    # Mainly here just in case. There's not really a need for it otherwise.
    async def interaction_check(self, itn: discord.Interaction) -> bool:
        return await self.view.interaction_check(itn)

    async def on_submit(self, itn: discord.Interaction) -> None:
        page_number_input = str(self.page_number_input)

        if not page_number_input.isdecimal():
            await itn.response.send_message("Invalid page number.", ephemeral=True)
            return

        page_number = int(page_number_input) - 1

        # This could've all been replaced with show_checked_page,
        # but silently ignoring exceptions in this case would be
        # bad UX.

        if 0 <= page_number < self._source_max_pages:
            try:
                await self.view.show_page(page_number, itn)
            except IndexError:
                pass
            else:
                return

        await itn.response.send_message("That page is out of bounds.", ephemeral=True)


class PaginationView(BaseView):
    """A view which allows for pagination of items.

    This view is similar to :class:`menus.MenuPages` except this
    uses message components rather than reactions. This is fully
    compatible with :class:`menu.PageSource` instances.

    .. warning::

        Due to implementation details regarding the :class:`View` and
        :class:`PageSource` classes, this view **cannot** be sent via
        :meth:`Messageable.send` as there is necessary setup that must
        be done prior. Calling either :meth:`send_to`, :meth:`attach_to`,
        :meth:`reply_to`, or :meth:`respond_to` is preferred as these
        methods will interally perform this setup for you.

    .. versionadded:: 3.2

    .. versionchanged:: 3.3

        * Renamed ``remove_view_after`` parameter to ``remove_view_on_timeout``.
        * Renamed ``disable_view_after`` parameter to ``disable_view_on_timeout``.
        * Removed the ``bot`` parameter & attribute.

    Parameters
    ----------
    source: :class:`menus.PageSource`
        The page source to paginate.
    enable_stop_button: :class:`bool`
        Whether or not to enable the stop button.
        Defaults to ``True``.

        .. versionadded:: 3.3
    delete_message_when_stopped: :class:`bool`
        Whether or not to delete the message once the stop button is pressed.
        This has no effect if ``enable_stop_button`` is ``False``.
        Defaults to ``True``.
    remove_view_on_timeout: :class:`bool`
        Whether or not to remove the view after it has timed out.
        This has no effect if ``enable_stop_button`` is ``False``.
        Defaults to ``False``.
    disable_view_on_timeout: :class:`bool`
        Whether or not to disable the view after it has timed out.
        This has no effect if ``enable_stop_button`` is ``False``.
        Defaults to ``True``.

        .. note::

            ``remove_view_on_timeout`` takes priority over this setting.

    Attributes
    ----------
    current_page: :class:`int`
        The current page that we are on.
        Zero-indexed between [0, :attr:`PageSource.max_pages`).
    message: Optional[:class:`discord.Message`]
        This view's cached message. May not necessarily be up to date.
        ``None`` if this wasn't initially set through either :meth:`send_to`,
        :meth:`attach_to`, :meth:`reply_to`, :meth:`respond_to`, or otherwise.
    """

    def __init__(
        self,
        source: PageSource,
        *,
        enable_stop_button: bool = True,
        delete_message_when_stopped: bool = True,
        remove_view_on_timeout: bool = False,
        disable_view_on_timeout: bool = True,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)

        self._enable_stop_button: bool = enable_stop_button
        self._delete_message_when_stopped: bool = delete_message_when_stopped
        self._remove_view_on_timeout: bool = remove_view_on_timeout
        self._disable_view_on_timeout: bool = disable_view_on_timeout

        self._page_select_modal: Optional[_PageSelectModal] = None

        self.current_page: int = 0
        self.message: Optional[discord.Message] = None
        self._source: PageSource = source

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
        if self._remove_view_on_timeout:
            await self.message.edit(view=None)  # type: ignore
        elif self._disable_view_on_timeout:
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

            self.page_number.emoji = "\N{INPUT SYMBOL FOR NUMBERS}"
            self.page_number.disabled = False
        else:
            self.page_number.emoji = None
            self.page_number.disabled = True

        self.add_item(self.previous_page)
        self.add_item(self.page_number)
        self.add_item(self.next_page)

        if more_than_two:
            self.add_item(self.last_page)

        if self._enable_stop_button:
            self.add_item(self.stop_menu)

        self._update_items(0)

    async def _prepare_once(self) -> Dict[str, Any]:
        await self._source._prepare_once()

        page = await self._source.get_page(0)
        return await self._get_kwargs_from_page(page)

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

    async def respond_to(
        self,
        interaction: discord.Interaction,
        *,
        edit_message: bool = False,
        ephemeral: bool = False,
        wait: bool = False,
    ) -> discord.Message:
        """|coro|

        Sends the view as either a response or followup to the
        given interaction, depending on whether the interaction
        has been responded to already.

        If the given interaction has already been responded to,
        then this will automatically perform a followup.

        This is a convenience method for doing the necessary
        setup for this view.

        .. versionadded:: 3.3

        Parameters
        ----------
        interaction: :class:`discord.Interaction`
            The interaction to respond to or followup with.
        edit_message: :class:`bool`
            Whether or not to edit the original interaction message
            instead.
            Defaults to ``False``.
        ephemeral: :class:`bool`
            Whether or not the response or followup message should
            be ephemeral. This is ignored if `edit_message` is set
            to ``True``.
            Defaults to ``False``.
        wait: :class:`bool`
            Whether or not to wait until the view has finished
            interacting before returning back to the caller.
            Defaults to ``False``.

        Returns
        -------
        :class:`discord.Message`
            The message that was sent or edited as a response or followup.
        """
        kwargs = await self._prepare_once()

        if interaction.response.is_done():
            if edit_message:
                message = await interaction.edit_original_response(**kwargs, view=self)
            else:
                message = await interaction.followup.send(
                    **kwargs, ephemeral=ephemeral, view=self
                )
        else:
            if edit_message:
                await interaction.response.edit_message(**kwargs, view=self)
            else:
                await interaction.response.send_message(
                    **kwargs, ephemeral=ephemeral, view=self
                )

            message = await interaction.original_response()

        if wait:
            await self.wait()

        return message

    async def reply_to(
        self,
        message_or_ctx: Union[discord.Message, Context],
        *,
        mention_author: Optional[bool] = None,
        ephemeral: bool = False,
        wait: bool = False,
    ) -> discord.Message:
        """|coro|

        Sends the view as a reply to the given message or context.

        This is a convenience method for doing the necessary setup
        for this view.

        .. versionchanged:: 3.3
            This can now take an invokation context.

        Parameters
        ----------
        message_or_ctx: Union[:class:`discord.Message`, :class:`commands.Context`]
            The message or context to reply to.
        mention_author: Optional[:class:`bool`]
            Whether or not to mention the replied message author.
            If not set, the defaults given by ``allowed_mentions``
            are used instead.
            Defaults to ``None``.
        ephemeral: :class:`bool`
            Whether or not the send the view in an ephemeral message.
            This is only used for interaction-based contexts.
            Defaults to ``False``.

            .. versionadded:: 3.3
        wait: :class:`bool`
            Whether or not to wait until the view has finished
            interacting before returning back to the caller.
            Defaults to ``False``.

        Returns
        -------
        :class:`discord.Message`
            The message that was sent as a reply.
        """
        kwargs = await self._prepare_once()

        # Message.reply doesn't take the ephemeral kwarg.
        if isinstance(message_or_ctx, Context):
            kwargs["ephemeral"] = ephemeral

        message = await message_or_ctx.reply(
            **kwargs, mention_author=mention_author, view=self
        )

        if wait:
            await self.wait()

        return message

    async def attach_to(
        self, message: discord.Message, *, wait: bool = False
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
        kwargs = await self._prepare_once()
        message = await message.edit(**kwargs, view=self)

        if wait:
            await self.wait()

        return message

    async def send_to(
        self,
        destination: discord.abc.Messageable,
        *,
        ephemeral: bool = False,
        wait: bool = False,
    ) -> discord.Message:
        """|coro|

        Sends the view to the given destination.

        This is a convenience method for doing the necessary
        setup for this view.

        Parameters
        ----------
        destination: :class:`discord.abc.Messageable`
            The destination to send the view.
        ephemeral: :class:`bool`
            Whether or not the send the view in an ephemeral message.
            This is only used for interaction-based contexts.
            Defaults to ``False``.

            .. versionadded:: 3.3
        wait: :class:`bool`
            Whether or not to wait until the view has finished
            interacting before returning back to the caller.
            Defaults to ``False``.

        Returns
        -------
        :class:`discord.Message`
            The message that was sent.
        """
        kwargs = await self._prepare_once()

        if isinstance(destination, Context):
            kwargs["ephemeral"] = ephemeral

        message = await destination.send(**kwargs, view=self)

        if wait:
            await self.wait()

        return message

    async def change_source(
        self, source: PageSource, interaction: Optional[discord.Interaction] = None
    ) -> None:
        """|coro|

        Changes the :class:`menus.PageSource` to a different
        one at runtime.

        Once the change has been set, the view is moved to
        the first page of the new source if it was started.
        This effectively changes the :attr:`current_page`
        to 0.

        .. versionchanged:: 3.3
            Raise :exc:`RuntimeError` if :attr:`message` is ``None``.

        Parameters
        ----------
        source: :class:`menus.PageSource`
            The page source to change to.
        interaction: Optional[:class:`discord.Interaction`]
            The interaction to use to edit the message, if necessary.
            If this is ``None``, then :attr:`message` is used to edit
            the message.

            .. versionadded:: 3.3

        Raises
        ------
        TypeError
            A :class:`menus.PageSource` was not passed.
        RuntimeError
            This view didn't have an associated message to edit,
            that is, no interaction was passed and :attr:`message`
            was left as ``None``.
        """
        if not isinstance(source, PageSource):
            raise TypeError(f"Expected PageSource, not {type(source).__name__}.")

        self._source = source
        self.current_page = 0

        self.clear_items()
        self._do_items_setup()

        await source._prepare_once()
        await self.show_page(0, interaction)

    async def show_page(
        self, page_number: int, interaction: Optional[discord.Interaction] = None
    ) -> None:
        """|coro|

        Prepares the page at the given page number and updates
        this view accordingly.

        Page numbers are zero-indexed between `[0, n)` where n
        is the page source's maximum page count, if applicable,
        as provided by :meth:`PageSource.get_max_pages`.

        .. versionchanged:: 3.3
            Raise :exc:`RuntimeError` if :attr:`message` is ``None``
            and no interaction was passed.

        Parameters
        ----------
        page_number: :class:`int`
            The page number to show.
        interaction: Optional[:class:`discord.Interaction`]
            The interaction to use to edit the message, if necessary.
            If this is ``None`` or the given interaction has already
            responded, then :attr:`message` is used to edit the message
            instead.

            .. versionadded:: 3.3

        Raises
        ------
        RuntimeError
            This view didn't have an associated message to edit,
            that is, no interaction was passed and :attr:`message`
            was left as ``None``.
        """
        self.current_page = page_number

        page = await self._source.get_page(page_number)
        kwargs = await self._get_kwargs_from_page(page)

        self._update_items(page_number)

        if interaction is not None and not interaction.response.is_done():
            await interaction.response.edit_message(**kwargs, view=self)
            return

        if self.message is None:
            raise RuntimeError("No associated message to edit.")

        self.message = await self.message.edit(**kwargs, view=self)

    async def show_checked_page(
        self, page_number: int, interaction: Optional[discord.Interaction] = None
    ) -> None:
        """|coro|

        Similar to :meth:`show_page` except runs some checks on the
        given page number before actually showing the page. This does
        nothing if the page number is invalid, i.e. doesn't point to
        a page.

        .. versionchanged:: 3.3
            Raise :exc:`RuntimeError` if :attr:`message` is ``None``
            and no interaction was passed.

        Parameters
        ----------
        page_number: :class:`int`
            The page number to show.
        interaction: Optional[:class:`discord.Interaction`]
            The interaction to use to edit the message, if necessary.
            If this is ``None``, then :attr:`message` is used to edit
            the message.

            .. versionadded:: 3.3

        Raises
        ------
        RuntimeError
            This view didn't have an associated message to edit,
            that is, no interaction was passed and :attr:`message`
            was left as ``None``.
        """
        max_pages = self._source.get_max_pages()

        if max_pages is None or 0 <= page_number < max_pages:
            try:
                await self.show_page(page_number, interaction)
            except IndexError:
                pass

    async def on_timeout(self) -> None:
        if self._page_select_modal is not None:
            self._page_select_modal.stop()
            self._page_select_modal = None

        if self.message is not None:
            try:
                await self._do_items_cleanup()
            except discord.HTTPException:
                pass

    @button(emoji="<:rrwnd:862379040802865182>")
    async def first_page(
        self, itn: discord.Interaction, button: Button["PaginationView"]
    ) -> None:
        await self.show_page(0, itn)

    @button(emoji="<:back:862407042172715038>")
    async def previous_page(
        self, itn: discord.Interaction, button: Button["PaginationView"]
    ) -> None:
        await self.show_checked_page(self.current_page - 1, itn)

    @button(style=discord.ButtonStyle.primary)
    async def page_number(
        self, itn: discord.Interaction, button: Button["PaginationView"]
    ) -> None:
        if self._page_select_modal is None:
            self._page_select_modal = _PageSelectModal(self)

        await itn.response.send_modal(self._page_select_modal)

    @button(emoji="<:fwd:862407042114125845>")
    async def next_page(
        self, itn: discord.Interaction, button: Button["PaginationView"]
    ) -> None:
        await self.show_checked_page(self.current_page + 1, itn)

    @button(emoji="<:ffwd:862378579794460723>")
    async def last_page(
        self, itn: discord.Interaction, button: Button["PaginationView"]
    ) -> None:
        # This call is safe since the button itself is already
        # handled initially when the view starts.
        await self.show_page(self._source.get_max_pages() - 1, itn)

    @button(emoji="\N{OCTAGONAL SIGN}", label="Stop", style=discord.ButtonStyle.danger)
    async def stop_menu(
        self, itn: discord.Interaction, button: Button["PaginationView"]
    ) -> None:
        self.stop()

        if self._page_select_modal is not None:
            self._page_select_modal.stop()
            self._page_select_modal = None

        if self.message is not None:
            # Ensure nothing goes awry during cleanup.
            try:
                if self._delete_message_when_stopped:
                    await self.message.delete()
                else:
                    self._remove_view_on_timeout = True
                    await self._do_items_cleanup()
            except discord.HTTPException:
                pass


class _DisambiguationView(PaginationView):
    def __init__(
        self, source: _DisambiguationSource, *, timeout: Optional[float] = None
    ) -> None:
        self.selection: Any = MISSING

        super().__init__(source, enable_stop_button=False, timeout=timeout)
        self.add_item(self.dropdown)

    @select(placeholder="Select which option you meant.")
    async def dropdown(
        self, itn: discord.Interaction, select: Select["_DisambiguationView"]
    ) -> None:
        self.stop()

        self.selection = self._source.entries[int(select.values[0])]

        if self._page_select_modal is not None:
            self._page_select_modal.stop()
            self._page_select_modal = None

        if self.message is not None:
            try:
                await self.message.delete()
            except discord.HTTPException:
                pass
