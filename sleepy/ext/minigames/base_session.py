"""
Copyright (c) 2018-present HitchedSyringe

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""


from __future__ import annotations

# fmt: off
__all__ = (
    "BaseSession",
)
# fmt: on


import asyncio
import logging
from typing import TYPE_CHECKING, Any, Optional, Tuple, Union

if TYPE_CHECKING:
    from collections import Counter

    from discord import Member, TextChannel, Thread, User, VoiceChannel
    from discord.ext.commands import Bot, Context
    from typing_extensions import Self

    TextGuildChannel = Union[TextChannel, Thread, VoiceChannel]


_LOG: logging.Logger = logging.getLogger(__name__)


class BaseSession:
    """Base minigame session class that the custom sessions inherit from.

    The following implement this base:

    * :class:`.trivia.TriviaSession`

    .. versionadded:: 3.3

    Parameters
    ----------
    bot: :class:`commands.Bot`
        The bot instance.
    channel: Union[:class:`discord.TextChannel`, :class:`discord.VoiceChannel`]
        The channel to run the session in.
    host: :class:`discord.Member`
        The member that is hosting the session.

    Attributes
    ----------
    bot: :class:`commands.Bot`
        The bot instance.
    channel: Union[:class:`discord.TextChannel`, :class:`discord.Thread`, :class:`discord.VoiceChannel`]
        The channel that this session is running in.
    host: :class:`discord.Member`
        The member that is hosting this session.
    scores: Optional[Counter[Union[:class:`discord.Member`, :class:`discord.User`]]]
        The player scores. By default, this is ``None``.
    """

    __slots__: Tuple[str, ...] = (
        "bot",
        "channel",
        "host",
        "scores",
        "__task",
    )

    def __init__(self, bot: Bot, channel: TextGuildChannel, host: Member) -> None:
        self.bot: Bot = bot
        self.channel: TextGuildChannel = channel
        self.host: Member = host
        self.scores: Optional[Counter[Union[User, Member]]] = None

        self.__task: Optional[asyncio.Task] = None

    def __str__(self) -> str:
        return f"{type(self).__name__} (ID: {self.channel.id}; Host ID: {self.host.id})"

    @classmethod
    def from_context(cls, ctx: Context, *args: Any, **kwargs: Any) -> Self:
        """Constructs a :class:`BaseSession` from an invokation context."""
        return cls(ctx.bot, ctx.channel, ctx.author, *args, **kwargs)  # type: ignore

    def __done_callback(self, future: asyncio.Future[None]) -> None:
        try:
            future.result()
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            name = f"minigames-session-error-{self.channel.id}"
            asyncio.create_task(self.on_error(exc), name=name)

            self.bot.dispatch("minigame_session_error", self, exc)

    def is_manager(self, member: Member) -> bool:
        """:class:`bool`: Indicates whether the given member can
        manage this session.

        A member can manage a session if they are either the host
        or a bot owner, or have the `Manage Messages` permission.
        """
        ids = {self.host.id, self.bot.owner_id, *self.bot.owner_ids}  # type: ignore

        # Skip having to query channel permissions.
        if member.id in ids:
            return True

        return self.channel.permissions_for(member).manage_messages

    def is_stopped(self) -> bool:
        """:class:`bool`: Indicates whether this session has been stopped."""
        return self.__task is None or self.__task.done()

    async def start(self) -> None:
        """|coro|

        Starts the session.
        """
        name = f"minigames-session-callback-{self.channel.id}"

        task = asyncio.create_task(self.callback(), name=name)
        task.add_done_callback(self.__done_callback)

        self.__task = task

        self.bot.dispatch("minigame_session_start", self)

    async def on_error(self, error: Exception) -> None:
        """|coro|

        Handles reporting of errors while updating the session from events.
        The default behaviour is to log the exception.

        This may be overriden by subclasses.

        Parameters
        ----------
        error: :class:`Exception`
            The exception which was raised during the session.
        """
        # Some users may wish to take other actions during or beyond logging
        # which would require awaiting, such as stopping an erroring session.
        _LOG.exception("Unhandled exception during session %s:", self, exc_info=error)

    async def callback(self) -> None:
        """|coro|

        The callback associated with this minigame session.

        Subclasses must implement this.
        """
        raise NotImplementedError

    async def stop(self) -> None:
        """|coro|

        Stops the session.
        """
        if self.__task is not None:
            self.__task.cancel()
            self.__task = None

        self.bot.dispatch("minigame_session_end", self)
