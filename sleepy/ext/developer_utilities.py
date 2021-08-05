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
from discord.ext import commands
from sleepy import checks
from sleepy.http import HTTPRequestFailed
from sleepy.menus import PaginatorSource
from sleepy.paginators import WrappedPaginator


# lang: compile command
COLIRU_COMMANDS = {
    # C Lang
    "c": "mv main.cpp main.c && gcc -std=c11 -O2 -Wall -Wextra -pedantic main.c && ./a.out",

    # C++
    "cpp": "g++ -std=c++1z -O2 -Wall -Wextra -pedantic -pthread main.cpp -lstdc++fs && ./a.out",
    "c++": "g++ -std=c++1z -O2 -Wall -Wextra -pedantic -pthread main.cpp -lstdc++fs && ./a.out",
    "cc": "g++ -std=c++1z -O2 -Wall -Wextra -pedantic -pthread main.cpp -lstdc++fs && ./a.out",
    "h": "g++ -std=c++1z -O2 -Wall -Wextra -pedantic -pthread main.cpp -lstdc++fs && ./a.out",
    "hpp": "g++ -std=c++1z -O2 -Wall -Wextra -pedantic -pthread main.cpp -lstdc++fs && ./a.out",
    "h++": "g++ -std=c++1z -O2 -Wall -Wextra -pedantic -pthread main.cpp -lstdc++fs && ./a.out",

    # Python
    "py": "python3 main.cpp",
    "python": "python3 main.cpp",

    # Haskell
    "hs": "runhaskell main.cpp",
    "haskell": "runhaskell main.cpp",
}


def codeblock_payload(value):
    try:
        lang, src = value.strip("`").split("\n", 1)
    except ValueError:
        raise commands.BadArgument(
            "Code must be wrapped in codeblocks with a language to compile with."
        ) from None

    if not lang:
        raise commands.BadArgument("You must provide a language to compile with.")

    try:
        cmd = COLIRU_COMMANDS[lang.lower()]
    except KeyError:
        raise commands.BadArgument("Invalid language to compile with.") from None

    return json.dumps({"cmd": cmd, "src": src})


class DeveloperUtilities(
    commands.Cog,
    name="Developer Utilities",
    command_attrs={"cooldown": commands.Cooldown(2, 5, commands.BucketType.member)}
):
    """Commands that serve as utilities for developers."""

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

    @commands.command(aliases=("openeval",))
    @commands.cooldown(1, 6, commands.BucketType.member)
    async def coliru(self, ctx, *, code: codeblock_payload):
        """Compiles and runs code on Coliru.

        You must pass a codeblock highlighting the language you
        wish to compile to. Coliru currently only supports `c`,
        `c++`, `haskell`, and `python`.

        The C++ compiler uses g++ -std=c++14 and Python support
        is 3.5.2. For Stacked's sake, please do not spam or
        abuse this.

        **EXAMPLE:**
        ```
        coliru
        ``\u200b`c++
        #include <iostream>

        int main()
        {
            std::cout << "Hello world!" << std::endl;
            return 0;
        }
        ``\u200b`
        ```
        """
        async with ctx.typing():
            try:
                output = await ctx.post("https://coliru.stacked-crooked.com/compile", data__=code)
            except HTTPRequestFailed:
                await ctx.send("Coliru took too long to respond.\nTry again later?")
                return

            output = output.replace("`", "\u200b`")

            if len(output) < 1955:
                await ctx.send(f"```\n{output}```\nPowered by `coliru.stacked-crooked.com`")
                return

            try:
                id_ = await ctx.post("https://coliru.stacked-crooked.com/share", data__=code)
            except HTTPRequestFailed:
                await ctx.send("Creating the share link failed.\nTry again later?")
            else:
                await ctx.send(
                    "Output was too long to post; see the share link below:\n"
                    f"<https://coliru.stacked-crooked.com/a/{id_}>"
                )

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
    bot.add_cog(DeveloperUtilities())
