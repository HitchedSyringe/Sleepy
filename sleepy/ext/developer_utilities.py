"""
Copyright (c) 2018-present HitchedSyringe

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published
by the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""


from __future__ import annotations

import base64
import binascii
import json
import re
import unicodedata
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, Optional, Tuple, Union
from urllib.parse import quote

import discord
from discord import Embed
from discord.ext import commands
from discord.ui import button
from discord.utils import escape_mentions, snowflake_time
from jishaku.paginators import WrappedPaginator
from typing_extensions import Annotated

from sleepy.http import HTTPRequestFailed
from sleepy.menus import BaseView, PaginatorSource

if TYPE_CHECKING:
    from discord.ui import Button

    from sleepy.bot import Sleepy
    from sleepy.context import Context as SleepyContext
    from sleepy.http import HTTPRequester


class PistonView(BaseView):

    __slots__: Tuple[str, ...] = ("_message", "body", "ctx")

    def __init__(self, ctx: SleepyContext, body: Dict[str, Any]) -> None:
        super().__init__(owner_id=ctx.author.id, timeout=300)

        self.ctx: SleepyContext = ctx
        self.body: Dict[str, Any] = body
        self._message: Optional[discord.Message] = None

    async def on_timeout(self) -> None:
        try:
            await self._message.delete()  # type: ignore
        except discord.HTTPException:
            pass

    async def show_formatted_result(
        self,
        data: Dict[str, Any],
        out: str,
        *,
        interaction: Optional[discord.Interaction] = None,
    ) -> None:
        message_content = (
            f"**{data['language']} {data['version']}** \N{BULLET} `Powered by Piston`"
            f"\n{out}\nExit code: {data['run']['code']}"
        )

        if interaction is None:
            self._message = await self.ctx.send(message_content, view=self)
        else:
            await interaction.response.edit_message(content=message_content)

    @button(
        label="Repeat Execution",
        emoji="\N{CLOCKWISE RIGHTWARDS AND LEFTWARDS OPEN CIRCLE ARROWS}",
    )
    async def repeat(self, itn: discord.Interaction, button: Button) -> None:
        data, out = await execute_on_piston(self.ctx, self.body)

        if data is None:
            await itn.response.send_message(out, ephemeral=True)
        else:
            await self.show_formatted_result(data, out, interaction=itn)

    @button(emoji="\N{WASTEBASKET}", style=discord.ButtonStyle.danger)
    async def dispose(self, itn: discord.Interaction, button: Button) -> None:
        await self._message.delete()  # type: ignore
        self.stop()


class PistonPayload(commands.Converter[Dict[str, Any]]):

    PAYLOAD_REGEX: re.Pattern = re.compile(
        r"""
        (?s)(?P<args>(?:[^\n\r\f\v]*\n)*?)?\s*
        ```(?:(?P<lang>\S+)\n)?\s*(?P<src>.*)```
        (?:\n?(?P<stdin>(?:[^\n\r\f\v]\n?)+)+|)
        """,
        re.X,
    )

    async def convert(self, ctx: SleepyContext, argument: str) -> Dict[str, Any]:
        payload_match = self.PAYLOAD_REGEX.search(argument)

        if payload_match is None:
            raise commands.BadArgument("Invalid body format.")

        args, language, src, stdin = payload_match.groups()

        if not src:
            raise commands.BadArgument("You must provide code to compile.")

        if not language:
            raise commands.BadArgument("You must provide a language to compile with.")

        language = language.lower()

        try:
            # This will only be used within this cog.
            version = ctx.cog.piston_runtimes[language]  # type: ignore
        except KeyError:
            raise commands.BadArgument("Invalid language to compile with.") from None

        return {
            "language": language,
            "version": version,
            "files": [{"content": src}],
            "args": [a for a in args.rstrip().split("\n") if a],
            "stdin": stdin,
        }


async def execute_on_piston(
    ctx: SleepyContext, body: Dict[str, Any]
) -> Tuple[Optional[Dict[str, Any]], str]:
    try:
        data = await ctx.post("https://emkc.org/api/v2/piston/execute", json__=body)
    except HTTPRequestFailed as exc:
        msg = exc.data.get("message", "Compilation failed. Try again later?")
        return None, msg

    out = data["run"]["output"]

    try:
        out += data["compile"]["stderr"]
    except (KeyError, TypeError):
        pass

    if not out:
        fmt_out = "Your code produced no output."
    elif len(out) < 1000 and out.count("\n") < 50:
        fmt_out = "```\n" + escape_mentions(out.replace("`", "`\u200b")) + "\n```"
    else:
        paste = await create_paste(ctx, out)

        if paste is None:
            fmt_out = "Output was too long and uploading it failed."
        else:
            fmt_out = f"Output was too long, so I've uploaded it here:\n<{paste}>"

    return data, fmt_out


async def create_paste(ctx: SleepyContext, data: Dict[str, Any]) -> Optional[str]:
    # Defined here in case it needs to be changed for w/e reason.
    hb_url = "https://www.toptal.com/developers/hastebin"

    try:
        doc = await ctx.post(f"{hb_url}/documents", data__=data)
    except HTTPRequestFailed:
        return None

    return f"{hb_url}/raw/{doc['key']}"


class DeveloperUtilities(
    commands.Cog,
    name="Developer Utilities",
    command_attrs={
        "cooldown": commands.CooldownMapping.from_cooldown(
            2, 5, commands.BucketType.member
        ),
    },
):
    """Commands that serve as utilities for developers."""

    ICON: str = "\N{WRENCH}"

    def __init__(self, bot: Sleepy) -> None:
        self.piston_runtimes: Dict[str, Any] = {}

        name = "ext-developer-utilities-fetch-piston-runtimes"
        bot.loop.create_task(self.fetch_piston_runtimes(bot.http_requester), name=name)

    @staticmethod
    async def send_formatted_nodes_embed(
        ctx: SleepyContext,
        endpoint: str,
        *,
        name: str,
        colour: Optional[Union[int, discord.Colour]] = None,
        **params: Any,
    ) -> None:
        resp = await ctx.get(
            f"https://idevision.net/api/public/{endpoint}", cache__=True, **params
        )

        nodes = resp["nodes"]

        if not nodes:
            await ctx.send("No results found.")
            return

        embed = Embed(
            title=f"Results for `{params['query']}`",
            description="\n".join(f"[`{k}`]({v})" for k, v, in nodes.items()),
            colour=colour,
        )
        embed.set_footer(
            text=f"Took {float(resp['query_time']) * 1000:.2f} ms "
            "\N{BULLET} Powered by idevision.net"
        )
        embed.set_author(name=name)

        await ctx.send(embed=embed)

    async def fetch_piston_runtimes(self, http_requester: HTTPRequester) -> None:
        resp = await http_requester.request(
            "GET", "https://emkc.org/api/v2/piston/runtimes"
        )

        for runtime in resp:
            self.piston_runtimes[runtime["language"]] = version = runtime["version"]

            for alias in runtime["aliases"]:
                self.piston_runtimes[alias] = version

    @commands.command()
    async def charinfo(self, ctx: SleepyContext, *, chars: str) -> None:
        """Gets information about the characters in a given string.

        **EXAMPLES:**
        ```bnf
        <1> charinfo \N{FACE WITH TEARS OF JOY}
        <2> charinfo \N{POSTAL HORN}Honk
        ```
        """

        def format_char_info(c: str) -> str:
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
    async def piston(
        self, ctx: SleepyContext, *, body: Annotated[Dict[str, Any], PistonPayload]
    ) -> None:
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
        await ctx.typing()

        data, out = await execute_on_piston(ctx, body)

        if data is None:
            await ctx.send(out)
        else:
            view = PistonView(ctx, body)
            await view.show_formatted_result(data, out)

    @piston.error
    async def on_piston_error(self, ctx: SleepyContext, error: Exception) -> None:
        if isinstance(error, commands.BadArgument):
            await ctx.send(error)  # type: ignore
            ctx._already_handled_error = True

    @commands.command(aliases=("msgraw",))
    @commands.cooldown(1, 5, commands.BucketType.member)
    async def messageraw(
        self, ctx: SleepyContext, message: discord.PartialMessage = None
    ) -> None:
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

        **EXAMPLES:**
        ```bnf
        <1> messageraw 822821140563420311
        <2> messageraw 408971234510995765-822821140563420311
        <3> messageraw https://discord.com/channels/523593711372795755/408971234510995765/822821140563420311
        ```
        """
        if message is None:
            message = ctx.replied_message or ctx.message

        try:
            raw = await ctx.bot.http.get_message(message.channel.id, message.id)
        except discord.NotFound:
            await ctx.send("That message wasn't found.")
            return
        except discord.Forbidden:
            await ctx.send("I do not have permission to access that message.")
            return

        data = WrappedPaginator(prefix="```json", max_size=1980)

        for line in json.dumps(raw, indent=4).split("\n"):
            data.add_line(line.replace("`", "\u200b`"))

        await ctx.paginate(PaginatorSource(data))

    @commands.command(aliases=("pt",))
    async def parsetoken(self, ctx: SleepyContext, *, token: str) -> None:
        """Analyzes a Discord API authorisation token.

        **EXAMPLE:**
        ```
        parsetoken NzE3MjU5NzIxNDk5NjIyNjUy.2QunZF.fXxn5Qyohgp7mhEOjW67YWV54Iz
        ```

        **Disclaimer: The token featured above in the example
        is a fake token. Don't leak your own token using this.**
        """
        token_match = re.fullmatch(
            r"([A-Za-z0-9_-]{23,28})\.([A-Za-z0-9_-]{6,7})\.([A-Za-z0-9_-]{27,})", token
        )

        if token_match is None:
            await ctx.send("Invalid Discord API authorisation token.")
            return

        enc_user_id, enc_ts, hmac = token_match.groups()

        try:
            user_id = base64.b64decode(enc_user_id).decode("ascii")
        except (binascii.Error, UnicodeError):
            await ctx.send("Decoding the user ID failed.")
            return

        if not user_id.isnumeric():
            await ctx.send("The decoded user ID seems to be invalid.")
            return

        try:
            ts = int.from_bytes(base64.urlsafe_b64decode(f"{enc_ts}=="), "big")
        except (binascii.Error, ValueError):
            await ctx.send("Decoding the token creation timestamp failed.")
            return

        created = datetime.fromtimestamp(ts, timezone.utc)

        # We usually have to add the token epoch if before 2015.
        if created.year < 2015:
            created = datetime.fromtimestamp(ts + 1293840000, timezone.utc)

        try:
            user = await commands.UserConverter().convert(ctx, user_id)
        except commands.UserNotFound:
            user_created = snowflake_time(int(user_id))

            await ctx.send(
                "**Token Information**"
                "\n```ldif"
                f"\nUser ID: {user_id}"
                f"\nUser Created: {user_created}"
                f"\nToken Created: {created}"
                f"\nHMAC: {hmac}"
                "\n```"
                "\n*Limited info is shown since user couldn't be resolved.*"
            )
        else:
            await ctx.send(
                "**Token Information**"
                "\n```ldif"
                f"\nUser: {user}"
                f"\nID: {user_id}"
                f"\nUser Created: {user.created_at}"
                f"\nToken Created: {created}"
                f"\nHMAC: {hmac}"
                "\n```"
            )

    @commands.command()
    @commands.bot_has_permissions(embed_links=True)
    async def pypi(
        self, ctx: SleepyContext, *, package: Annotated[str, str.lower]
    ) -> None:
        """Shows information about a package on PyPI.

        (Bot Needs: Embed Links)

        **EXAMPLE:**
        ```
        pypi discord.py
        ```
        """
        try:
            resp = await ctx.get(
                f"https://pypi.org/pypi/{quote(package, safe='')}/json", cache__=True
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
            colour=0x006DAD,
        )
        embed.set_thumbnail(
            url="https://cdn-images-1.medium.com/max/1200/1*2FrV8q6rPdz6w2ShV6y7bw.png"
        )
        embed.set_footer(text="Powered by pypi.org")
        embed.add_field(
            name="Information",
            value=f"**Author:** {data['author'] or 'N/A'}"
            f"\n> **Email:** {data['author_email'] or 'N/A'}"
            f"\n**Maintainer:** {data['maintainer'] or 'N/A'}"
            f"\n> **Email:** {data['maintainer_email'] or 'N/A'}"
            f"\n**License:** {data['license'] or 'None provided.'}"
            f"\n**Python Requirements:** {data['requires_python'] or 'N/A'}",
        )

        urls = data["project_urls"]

        if urls is not None:
            links = "\n".join(f"[{n}]({u})" for n, u in urls.items() if u != "UNKNOWN")

            if links:
                embed.add_field(name="Links", value=links)

        if keywords := data["keywords"]:
            embed.add_field(name="Keywords", value=keywords, inline=False)

        await ctx.send(embed=embed)

    @commands.group(
        aliases=("readthefuckingmanual", "rtfd", "readthefuckingdocs"),
        invoke_without_command=True,
    )
    @commands.bot_has_permissions(embed_links=True)
    async def rtfm(self, ctx: SleepyContext, *, query: str) -> None:
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
            name="RTFM: discord.py",
            colour=0x5865F2,
            location="https://discordpy.readthedocs.io/en/latest",
            query=query,
        )

    @rtfm.command(name="master", aliases=("main", "latest"))
    @commands.bot_has_permissions(embed_links=True)
    async def rtfm_master(self, ctx: SleepyContext, *, query: str) -> None:
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
            name="RTFM: discord.py (master branch)",
            colour=0x5865F2,
            location="https://discordpy.readthedocs.io/en/latest",
            query=query,
        )

    @rtfm.command(name="python", aliases=("py",))
    @commands.bot_has_permissions(embed_links=True)
    async def rtfm_python(self, ctx: SleepyContext, *, query: str) -> None:
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
            name="RTFM: Python",
            colour=0x5865F2,
            location="https://docs.python.org/3",
            query=query,
        )

    @commands.command(aliases=("readthefuckingsource",))
    @commands.bot_has_permissions(embed_links=True)
    async def rtfs(self, ctx: SleepyContext, *, query: str) -> None:
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
            name="RTFS: discord.py",
            colour=0x5865F2,
            library="discord.py",
            query=query,
        )


async def setup(bot: Sleepy) -> None:
    await bot.add_cog(DeveloperUtilities(bot))
