from collections.abc import Sequence
from typing import Any, Optional

import discord
from discord.abc import Messageable
from discord.ext import commands, menus  # type: ignore[attr-defined]


class EmbedSource(menus.ListPageSource):  # type: ignore[misc]

    def __init__(
        self,
        entries: Sequence[discord.Embed],
        /,
        *,
        show_page_count: bool = True
    ) -> None: ...


class PaginatorSource(menus.ListPageSource):  # type: ignore[misc]

    paginator: commands.Paginator

    def __init__(
        self,
        paginator: commands.Paginator,
        /,
        *,
        per_page: int = 1,
        show_page_count: bool = True
    ) -> None: ...


class ConfirmationPrompt(menus.Menu):  # type: ignore[misc]

    def __init__(
        self,
        message: discord.Message | str,
        /,
        *,
        timeout: float = 30,
        delete_message_after: bool = True
    ) -> None: ...

    async def start(
        self,
        ctx: commands.Context,
        /,
        *,
        channel: Optional[Messageable] = None
    ) -> Optional[bool]: ...


class PaginationMenu(menus.MenuPages):  # type: ignore[misc]

    def __init__(
        self,
        source: menus.PageSource,
        /,
        *,
        delete_message_after: bool = True,
        **kwargs: Any
    ) -> None: ...

    async def show_page_lazy(
        self,
        page_number: int,
        /,
        *,
        check_page_number: bool = False
    ) -> None: ...