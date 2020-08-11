"""
© Copyright 2018-2020 HitchedSyringe, All Rights Reserved.

Redistributing, using or owning a copy of this software without explicit permissions
is against these licensing terms, your license(s) to this software can be revoked at
any time without explicit notice beforehand and at the time of revocation.
Your license is non-transferrable, the terms of this license only permit you to do the
following; Create pull requests and make modifications to this repository.

"""


__all__ = ("Context",)


import asyncio
import io

import discord
from discord.ext import commands

from SleepyBot.utils import formatting
from SleepyBot.utils.reaction_menus import ConfirmationPrompt, PaginatorInterface


_TICK_MATCHES = {
    True: "<:checkmark:512814665705979914>",
    False: "<:xmark:512814698136076299>",
}


class Context(commands.Context):
    """A custom context class that provides some more helpful and useful methods.

    This class is a subclass of :class:`commands.Context` and as a result,
    anything that you can do with a :class:`commands.Context`, you can do with this context.
    """

    @property
    def session(self):
        """:class:`aiohttp.ClientSession`: Same as :attr:`CachedHTTPRequester.session`."""
        return self.bot.http_requester.session


    async def request(self, method: str, url, *, cache: bool = False, **parameters):
        """|coro|

        Same as :meth:`CachedHTTPRequester.request`.

        """
        return await self.bot.http_requester.request(method, url, cache=cache, **parameters)


    async def get(self, *args, **kwargs):
        """|coro|

        Same as :meth:`request`, but slimmed down to do only GET requests.

        """
        return await self.request("GET", *args, **kwargs)


    async def post(self, *args, **kwargs):
        """|coro|

        Same as :meth:`request`, but slimmed down to do only POST requests.

        """
        return await self.request("POST", *args, **kwargs)


    async def paginate(self, source, **kwargs) -> None:
        """|coro|

        Initilises and starts a :class:`reaction_menus.PaginatorInterface` prompt.

        Parameters
        ----------
        source: :class:`menus.PageSource`
            The page source to paginate.
        """
        menu = PaginatorInterface(source, **kwargs)
        await menu.start(self)


    async def prompt(self, prompt_message, *, timeout=30, delete_message_after: bool = True):
        """|coro|

        Initilises and starts a :class:`reaction_menus.ConfirmationPrompt` prompt.

        Parameters
        ----------
        prompt_message: Union[:class:`str`, :class:`discord.Message`]
            The prompt message to confirm.
        *, timeout: Union[:class:`int`, :class:`float`]
            The time (in seconds) before the prompt expires.
            Defaults to ``30``.
        delete_message_after: :class:`bool`
            Whether or not to delete the message if the prompt either expires or gets a response.
            Defaults to ``True``.

        Returns
        -------
        Optional[:class:`bool`]
            Whether or not the prompt was confirmed by the user.
            ``None`` if the prompt expired.
        """
        prompt = ConfirmationPrompt(prompt_message, timeout=timeout, delete_message_after=delete_message_after)
        return await prompt.prompt(self)


    async def disambiguate(self, matches: list, repl=lambda match: match):
        """|coro|

        Allows the user choose between matching items in a list,
        returning the item the user picks, or if only one item is in the list,
        returning that item instead.

        Parameters
        ----------
        matches: List[Any]
            A list of matching items to disambiguate between.
        repl:
            A function that returns a string-like result.

        Returns
        -------
        Any
            The item the user picked, or the only item in the given list of matches.

        Raises
        ------
        :exc:`ValueError`
            Either no results were found, the user took too long to respond,
            or there were too many invalid attempts.
        """
        if not matches:
            raise ValueError("No results found.")

        if len(matches) == 1:
            return matches[0]

        disambiguations = "\n".join(f"{index}. {repl(match)}" for index, match in enumerate(matches, 1))
        await self.send(f"Too many matches, which one did you mean? **Only say the number.**\n>>> {disambiguations}")


        def is_valid_item(message):
            checks = (
                message.channel == self.channel,
                message.author == self.author,
                message.content.isdigit(),
                # While zero *is* technically a valid number (giving us the last item),
                # letting this be valid would leave the user slightly confused.
                # Sinze zero should never appear on the disambiguation list, we can simply just filter it out.
                message.content != "0",
            )
            return all(checks)

        for attempt in range(3):  # Give the user 3 attempts.
            try:
                message = await self.bot.wait_for("message", check=is_valid_item, timeout=30)
            except asyncio.TimeoutError:
                raise ValueError("You took too long to respond.") from None

            index = int(message.content)

            try:
                return matches[index - 1]
            except IndexError:
                if attempt == 2:
                    raise ValueError("Too many invalid attempts.")
                await self.send(f"Invalid number.\n{formatting.plural(2 - attempt):attempt} remaining.")


    async def safe_send(self, content: str, *, disable_mentions: bool = False, filename: str = "message", **kwargs):
        """|coro|

        Same as :meth:`send`, but with a few safeguards added in.
        1) If the message content is too long, then it is sent as a ``.txt`` file instead.
        2) If ``disable_mentions`` is ``True``, then all user mentions are disabled.

        .. note::

            This internally overwrites ``allowed_mentions`` and ``file``.

        Parameters
        ----------
        content: :class:`str`
            The message content to send.
        *, disable_mentions: :class:`bool`
            Whether or not to disable all mentions.
            Defaults to ``False``.
        filename: :class:`str`
            The name of the text file to send.
            You cannot change the file extension.
            Defaults to ``message``.
        """
        if disable_mentions:
            kwargs["allowed_mentions"] = discord.AllowedMentions(everyone=False, users=False, roles=False)

        if len(content) > 2000:
            kwargs["file"] = discord.File(fp=io.BytesIO(content.encode()), filename=f"{filename}.txt")
            return await self.send(**kwargs)
        else:
            return await self.send(content, **kwargs)


    @staticmethod
    def tick(option, show_option: bool = False) -> str:
        """Returns an emoji based on the option.

        Parameters
        ----------
        option: Any
            The option to return an emoji for.
            If the option is ``True``, this returns a checkmark.
            If the option is ``False``, this returns an x mark.
            Anything else returns \N{WHITE QUESTION MARK ORNAMENT}.
        show_option: :class:`bool`
            Whether or not to show the option passed alongside the emoji result.
            Defaults to ``False``.

        Returns
        -------
        :class:`str`
            The emoji result, optionally with the given option shown alongside it.
        """
        emoji = _TICK_MATCHES.get(option, "\N{WHITE QUESTION MARK ORNAMENT}")

        if show_option:
            return f"{emoji}: {option}"
        return emoji
