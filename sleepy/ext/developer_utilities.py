"""
Copyright (c) 2018-present HitchedSyringe

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""


import base64
import binascii
import json
import re
import unicodedata
from datetime import datetime
from urllib.parse import quote

import discord
from discord import Embed
from discord.ext import commands, menus
from discord.utils import escape_mentions
from sleepy import checks
from sleepy.http import HTTPRequestFailed
from sleepy.menus import PaginatorSource
from sleepy.paginators import WrappedPaginator


class DisposableResultMenu(menus.Menu):

    def __init__(self, content):
        # This menu is set up to only delete itself if the
        # bin button is pressed. Otherwise, the bin button
        # will simply be cleared on timeout.
        super().__init__(clear_reactions_after=True, timeout=300)

        self._content = content

    async def send_initial_message(self, ctx, channel):
        return await channel.send(self._content)

    @menus.button("\N{WASTEBASKET}\ufe0f")
    async def dispose(self, payload):
        self.delete_message_after = True
        self.stop()


class PistonPayload(commands.Converter):

    PAYLOAD_REGEX = re.compile(
        r"""
        (?s)(?P<args>(?:[^\n\r\f\v]*\n)*?)?\s*
        ```(?:(?P<lang>\S+)\n)?\s*(?P<src>.*)```
        (?:\n?(?P<stdin>(?:[^\n\r\f\v]\n?)+)+|)
        """,
        re.X
    )

    async def convert(self, ctx, argument):
        payload_match = self.PAYLOAD_REGEX.search(argument)

        if payload_match is None:
            raise commands.BadArgument("Invalid body format.")

        args, language, src, stdin = payload_match.groups()

        if not language:
            raise commands.BadArgument("You must provide a language to compile with.")

        language = language.lower()

        try:
            version = ctx.cog.piston_runtimes[language]
        except KeyError:
            raise commands.BadArgument("Invalid language to compile with.") from None

        return {
            "language": language,
            "version": version,
            "files": [{"content": src}],
            "args": [a for a in args.rstrip().split("\n") if a],
            "stdin": stdin
        }


class DeveloperUtilities(
    commands.Cog,
    name="Developer Utilities",
    command_attrs={"cooldown": commands.Cooldown(2, 5, commands.BucketType.member)}
):
    """Commands that serve as utilities for developers."""

    def __init__(self, bot):
        self.piston_runtimes = {}

        bot.loop.create_task(self.fetch_piston_runtimes(bot.http_requester))

    @staticmethod
    async def send_formatted_nodes_embed(
        ctx,
        endpoint,
        *,
        embed_author_name,
        colour=None,
        **params
    ):
        resp = await ctx.get(
            f"https://idevision.net/api/public/{endpoint}",
            cache__=True,
            **params
        )

        nodes = resp["nodes"]

        if not nodes:
            await ctx.send("No results found.")
            return

        embed = Embed(
            title=f"Results for `{params['query']}`",
            description="\n".join(f"[`{k}`]({v})" for k, v, in nodes.items()),
            colour=colour
        )
        embed.set_footer(
            text=f"Took {float(resp['query_time']) * 1000:.2f} ms "
                 "\N{BULLET} Powered by idevision.net"
        )
        embed.set_author(name=embed_author_name)

        await ctx.send(embed=embed)

    async def fetch_piston_runtimes(self, http):
        resp = await http.request("GET", "https://emkc.org/api/v2/piston/runtimes")

        for runtime in resp:
            self.piston_runtimes[runtime["language"]] = ver = runtime["version"]

            for alias in runtime["aliases"]:
                self.piston_runtimes[alias] = ver

    @commands.command()
    async def charinfo(self, ctx, *, chars):
        """Gets information about the characters in a given string.

        **EXAMPLES:**
        ```bnf
        <1> charinfo \N{FACE WITH TEARS OF JOY}
        <2> charinfo \N{POSTAL HORN}Honk
        ```
        """
        def format_char_info(c):
            code = format(ord(c), "x")

            return (
                f"`\\U{code:>08}`: {unicodedata.name(c, '<Unknown>')} - {c}"
                f" \N{EM DASH} <https://fileformat.info/info/unicode/char/{code}>"
            )

        output = "\n".join(map(format_char_info, chars))

        if len(output) < 2000:
            await ctx.send(output)
        else:
            await ctx.send("The output is too long to post.")

    @commands.command(aliases=("openeval", "runcode", "executecode", "execcode"))
    @commands.cooldown(1, 4, commands.BucketType.member)
    async def piston(self, ctx, *, body: PistonPayload):
        """Runs code on Engineer Man's Piston API.

        Body must be in the following format:
        ```sql
        [params...] -- one per line
        ``\u200b`<language>
        <code>
        ``\u200b`
        [stdin]
        ```
        Like always, **do not include the brackets**.

        For a list of supported languages, please refer here:
        <https://github.com/engineer-man/piston#Supported-Languages>

        **EXAMPLES:**
        ```bnf
        <1> piston
        ``\u200b`elixir
        IO.puts("hello world")
        ``\u200b`
        <2> piston
        this is a command line argument!
        here's another one!
        foo
        bar
        ``\u200b`py
        import sys
        print(sys.argv)
        print(input())  # Print from stdin.
        ``\u200b`
        hello world!
        ```
        """
        await ctx.trigger_typing()

        try:
            resp = await ctx.post("https://emkc.org/api/v2/piston/execute", json__=body)
        except HTTPRequestFailed as exc:
            await ctx.send(exc.data.get("message", "Compiling your code failed. Try again later?"))
            return

        run = resp["run"]
        result = run["output"]

        try:
            result += resp["compile"]["stderr"]
        except (KeyError, TypeError):
            pass

        if not result:
            result = "Your code produced no output.\n"
        elif len(result) < 1000 and result.count("\n") < 50:
            result = "```\n" + escape_mentions(result.replace("`", "`\u200b")) + "\n```"
        else:
            try:
                key = await ctx.post(
                    "https://www.toptal.com/developers/hastebin/documents",
                    data__=result
                )
            except HTTPRequestFailed:
                await ctx.send("The output was too long and uploading it failed.")
                return

            result = (
                "The output was too long, so I've uploaded it here:"
                f"\n<https://www.toptal.com/developers/hastebin/{key['key']}>\n"
            )

        menu = DisposableResultMenu(
            f"**{resp['language']} ({resp['version']})**\n{result}"
            f"\nExit code: {run['code']}\n`Powered by Piston`"
        )
        await menu.start(ctx)

    @piston.error
    async def on_piston_error(self, ctx, error):
        if isinstance(error, commands.BadArgument):
            await ctx.send(error)
            error.handled__ = True

    @commands.command(aliases=("msgraw",))
    @checks.can_start_menu()
    @commands.cooldown(1, 5, commands.BucketType.member)
    async def messageraw(self, ctx, message: discord.PartialMessage = None):
        """Shows the raw JSON data for a given message.

        Message can either be an ID, link, or, alternatively,
        the `{channel ID}-{message ID}` format, which can be
        retrieved by shift-clicking on `Copy ID`. Note that
        the first option only allows for getting data from a
        message in the current channel. To get data from a
        message outside the current channel, use the latter
        two options.

        If no message is given, then the raw JSON data for
        the replied message, if applicable, otherwise, the
        invoking message, will be shown instead.

        (Bot Needs: Add Reactions and Read Message History)

        **EXAMPLES:**
        ```bnf
        <1> messageraw 822821140563420311
        <2> messageraw 408971234510995765-822821140563420311
        <3> messageraw https://discord.com/channels/523593711372795755/408971234510995765/822821140563420311
        ```
        """
        if message is None:
            if ctx.replied_reference is None:
                message = ctx.message
            else:
                message = ctx.channel.get_partial_message(ctx.replied_reference.message_id)

        try:
            raw = await ctx.bot.http.get_message(message.channel.id, message.id)
        except discord.NotFound:
            await ctx.send("That message wasn't found.")
            return
        except discord.Forbidden:
            await ctx.send("I do not have permission to access that message.")
            return

        data = WrappedPaginator("```json", max_size=1980)

        for line in json.dumps(raw, indent=4).split("\n"):
            data.add_line(line.replace("`", "\u200b`"))

        await ctx.paginate(PaginatorSource(data))

    @commands.command(aliases=("pt",))
    async def parsetoken(self, ctx, *, token):
        """Analyzes a Discord API authorisation token.

        **EXAMPLE:**
        ```
        parsetoken NzE3MjU5NzIxNDk5NjIyNjUy.2QunZF.fXxn5Qyohgp7mhEOjW67YWV54Iz
        ```

        **Disclaimer: The token featured above in the example
        is a fake token. Don't leak your own token using this.**
        """
        token_match = re.fullmatch(r"([\w-]{23,28})\.([\w-]{6,7})\.([\w-]{27})", token)

        if token_match is None:
            await ctx.send("Invalid Discord API authorisation token.")
            return

        enc_user_id, enc_ts, hmac = token_match.groups()

        try:
            user_id = base64.b64decode(enc_user_id, validate=True).decode("utf-8")
        except (binascii.Error, UnicodeError):
            await ctx.send("Decoding the user ID failed.")
            return

        try:
            user = await commands.UserConverter().convert(ctx, user_id)
        except commands.UserNotFound:
            # The user doesn't exist, so we'll just create a "partial"
            # user here with the info that we have.
            user = discord.Object(user_id)
            user.bot = "Unknown"
            type(user).__repr__ = lambda _: "Unknown"

        try:
            ts = int.from_bytes(base64.b64decode(enc_ts + "==", validate=True), "big")
        except (binascii.Error, ValueError):
            await ctx.send("Decoding the generation timestamp failed.")
            return

        generated_at = datetime.utcfromtimestamp(ts)

        # We usually have to add the token epoch if before 2015.
        if generated_at.year < 2015:
            generated_at = datetime.utcfromtimestamp(ts + 1293840000)

        await ctx.send(
            f"**{user} (ID: {user_id})**```ldif\nBot: {user.bot}\nUser Created: "
            f"{user.created_at}\nToken Generated: {generated_at}\nHMAC: {hmac}```"
        )

    @commands.command()
    @commands.bot_has_permissions(embed_links=True)
    async def pypi(self, ctx, *, package: str.lower):
        """Shows information about a package on PyPI.

        (Bot Needs: Embed Links)

        **EXAMPLE:**
        ```
        pypi discord.py
        ```
        """
        try:
            resp = await ctx.get(
                f"https://pypi.org/pypi/{quote(package, safe='')}/json",
                cache__=True
            )
        except HTTPRequestFailed as exc:
            if exc.status == 404:
                await ctx.send("That PyPI package wasn't found.")
                return

            raise

        data = resp["info"]

        embed = Embed(
            title=f"{data['name']} {data['version']}",
            description=data["summary"],
            url=data["release_url"],
            colour=0x006DAD
        )
        embed.set_thumbnail(url="https://cdn-images-1.medium.com/max/1200/1*2FrV8q6rPdz6w2ShV6y7bw.png")
        embed.set_footer(text="Powered by pypi.org")
        embed.add_field(
            name="Information",
            value=(
                f"**Author/Maintainer:** {data['author'] or data['maintainer']}"
                f"\n> **E-mail:** {data['author_email'] or data['maintainer_email'] or 'N/A'}"
                f"\n**License:** {data['license'] or 'None provided.'}"
                f"\n**Python Requirements:** {data['requires_python'] or 'N/A'}"
                f"\n**Keywords:** {data['keywords'] or 'N/A'}"
            )
        )

        urls = data["project_urls"]

        if (
            urls is not None
            and (links := "\n".join(f"[{n}]({u})" for n, u in urls.items() if u != "UNKNOWN"))
        ):
            embed.add_field(name="Links", value=links)

        await ctx.send(embed=embed)

    @commands.group(
        aliases=("readthefuckingmanual", "rtfd", "readthefuckingdocs"),
        invoke_without_command=True
    )
    @commands.bot_has_permissions(embed_links=True)
    async def rtfm(self, ctx, *, query):
        """Gives a documentation link for a discord.py entity.

        (Bot Needs: Embed Links)

        **EXAMPLES:**
        ```bnf
        <1> rtfm Messageable
        <2> rtfm Context.invoke()
        ```
        """
        await self.send_formatted_nodes_embed(
            ctx,
            "rtfm.sphinx",
            embed_author_name="RTFM: discord.py",
            colour=0x5865F2,
            location="https://discordpy.readthedocs.io/en/latest",
            query=query
        )

    @rtfm.command(name="master", aliases=("main",))
    @commands.bot_has_permissions(embed_links=True)
    async def rtfm_master(self, ctx, *, query):
        """Gives a documentation link for a discord.py entity (master branch).

        (Bot Needs: Embed Links)

        **EXAMPLES:**
        ```bnf
        <1> rtfm Messageable
        <2> rtfm Context.invoke()
        ```
        """
        await self.send_formatted_nodes_embed(
            ctx,
            "rtfm.sphinx",
            embed_author_name="RTFM: discord.py (master branch)",
            colour=0x5865F2,
            location="https://discordpy.readthedocs.io/en/master",
            query=query
        )

    @rtfm.command(name="python", aliases=("py",))
    @commands.bot_has_permissions(embed_links=True)
    async def rtfm_python(self, ctx, *, query):
        """Gives a documentation link for a Python 3 entity.

        (Bot Needs: Embed Links)

        **EXAMPLES:**
        ```bnf
        <1> rtfm python RuntimeError
        <2> rtfm python print()
        <3> rtfm python asyncio.get_event_loop()
        ```
        """
        await self.send_formatted_nodes_embed(
            ctx,
            "rtfm.sphinx",
            embed_author_name="RTFM: Python",
            colour=0x5865F2,
            location="https://docs.python.org/3",
            query=query
        )

    @commands.command(aliases=("readthefuckingsource",))
    @commands.bot_has_permissions(embed_links=True)
    async def rtfs(self, ctx, *, query):
        """Searches the GitHub repository of discord.py.

        (Bot Needs: Embed Links)

        **EXAMPLES:**
        ```bnf
        <1> rtfs Messageable
        <2> rtfs Context.invoke()
        ```
        """
        await self.send_formatted_nodes_embed(
            ctx,
            "rtfs",
            embed_author_name="RTFS: discord.py",
            colour=0x5865F2,
            library="discord.py",
            query=query
        )


def setup(bot):
    bot.add_cog(DeveloperUtilities(bot))
