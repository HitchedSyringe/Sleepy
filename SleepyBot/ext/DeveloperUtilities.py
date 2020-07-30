"""
© Copyright 2018-2020 HitchedSyringe, All Rights Reserved.

Redistributing, using or owning a copy of this software without explicit permissions
is against these licensing terms, your license(s) to this software can be revoked at
any time without explicit notice beforehand and at the time of revocation.
Your license is non-transferrable, the terms of this license only permit you to do the
following; Create pull requests and make modifications to this repository.

"""


import base64
import binascii
import json
import re
import textwrap
import unicodedata
from datetime import datetime
from urllib.parse import quote as urlquote

import discord
from discord import Colour, Embed
from discord.ext import commands

from SleepyBot.utils import checks
from SleepyBot.utils.requester import HTTPError


class CodeBlock:
    """Converts to a codeblock for use in Coliru."""
    supported = "Coliru currently only supports `c`, `cpp`, `haskell`, and `python`."

    def __init__(self, argument):
        try:
            language, self.src = argument.strip("`").split("\n", 1)
        except ValueError:
            raise commands.BadArgument("Codeblocks must use the following markdown:\n\\`\\`\\`lang\ncode\n\\`\\`\\`")

        if not language:
            raise commands.BadArgument(f"You must provide a language to compile with.\n{self.supported}")

        # Mappings are from R. Danny.
        cmd_mappings = {
            "c": "mv main.cpp main.c && gcc -std=c11 -O2 -Wall -Wextra -pedantic main.c && ./a.out",
            "cpp": "g++ -std=c++1z -O2 -Wall -Wextra -pedantic -pthread main.cpp -lstdc++fs && ./a.out",
            "py": "python3 main.cpp",  # python shorthand alias
            "python": "python3 main.cpp",
            "hs": "runhaskell main.cpp",  # haskell shorthand alias
            "haskell": "runhaskell main.cpp",
        }

        # Add cpp aliases.
        for cpp_alias in ("c++", "cc", "h", "hpp", "h++"):
            cmd_mappings[cpp_alias] = cmd_mappings["cpp"]

        try:
            self.cmd = cmd_mappings[language.lower()]
        except KeyError:
            raise commands.BadArgument(f"Cannot compile with that language.\n{self.supported}")


class DevUtils(commands.Cog,
               name="Developer Utilities",
               command_attrs=dict(cooldown=commands.Cooldown(rate=2, per=5, type=commands.BucketType.member))):
    """Commands that serve as utilities for developers."""

    @commands.command()
    async def charinfo(self, ctx: commands.Context, *, chars: str):
        """Gets information on characters in the given string.

        EXAMPLE:
        (Ex. 1) charinfo 😂
        (Ex. 2) charinfo 📯Honk
        """
        def to_string(char):
            digit = f"{ord(char):x}"
            name = unicodedata.name(char, "<Unknown>")
            return f"`\\U{digit:>08}`: {name} - {char} \N{EM DASH} <http://www.fileformat.info/info/unicode/char/{digit}>"

        output = "\n".join(map(to_string, chars))
        if len(output) < 2000:
            await ctx.send(output)
        else:
            await ctx.send("The output is too long to post.")


    @commands.command()
    @commands.cooldown(rate=1, per=6, type=commands.BucketType.member)
    async def coliru(self, ctx: commands.Context, *, code: CodeBlock):
        """Compiles and runs code on Coliru.

        You must pass a codeblock highlighting the language you want to compile to.
        Coliru currently only supports `c`, `cpp`, `haskell`, and `python`.

        The C++ compiler uses g++ -std=c++14 and Python support is 3.5.2.
        For stacked's sake, please do not spam or abuse this.

        EXAMPLE: coliru
        \\`\\`\\`cpp
        #include <iostream>
        using namespace std;

        int main()
        {
            cout < "Hello World";
            return 0;
        }
        \\`\\`\\`
        """
        payload = json.dumps({"cmd": code.cmd, "src": code.src})

        async with ctx.typing():
            try:
                output = await ctx.post("https://coliru.stacked-crooked.com/compile", data__=payload)
            except HTTPError:
                await ctx.send("An error occurred while compiling.\nTry again later?")
                return

            if len(output) < 2000:
                await ctx.send(f"```{output}```")
            else:
                # Output too long to post, so try creating a shared link.
                try:
                    shared_link = await ctx.post("https://coliru.stacked-crooked.com/share", data__=payload)
                except HTTPError:
                    await ctx.send("An error occurred while creating the shared link.\nTry again later?")
                else:
                    await ctx.send(f"The output was too long.\nLink: <https://coliru.stacked-crooked.com/a/{shared_link}>")


    @commands.command(aliases=["pt"])
    async def parsetoken(self, ctx: commands.Context, *, token: str):
        """Parses and decodes a Discord API authorisation token.

        EXAMPLE: parsetoken NzE3MjU5NzIxNDk5NjIyNjUy.2QunZF.fXxn5Qyohgp7mhEOjW67YWV54Iz

        Disclaimer: The token featured above in the example is a fake token.
        Don't leak your own token using this.
        """
        match = re.fullmatch(r"([a-zA-Z0-9]{24})\.([\w\-]{6})\.([\w\-]{27})", token)
        if match is None:
            await ctx.send("Invalid token.\nPlease send a valid Discord API authorisation token.")
            return

        enc_user_id, enc_timestamp, hmac = match.groups()

        try:
            user_id = int(base64.standard_b64decode(enc_user_id))
        except (binascii.Error, UnicodeDecodeError):
            await ctx.send("Failed to decode user ID.")
            return

        user = ctx.bot.get_user(user_id)
        if user is None:
            try:
                user = await ctx.bot.fetch_user(user_id)
            except discord.HTTPException:
                # The user doesn't exist, so we'll just create a "partial" user here with the info that we have.
                # Alternatively, I could have used a getattr call but this looks a little more elegant.
                class PartialTokenUser:
                    def __str__(self):
                        return "Unknown"

                user = PartialTokenUser()
                user.bot = "Unknown"

        try:
            timestamp = int.from_bytes(base64.standard_b64decode(enc_timestamp + "=="), "big")
        except (binascii.Error, UnicodeDecodeError):
            await ctx.send("Failed to decode token creation timestamp.")
            return

        created_at = datetime.utcfromtimestamp(timestamp)
        # We usually have to add the token epoch for tokens dating before 2015. Thanks, Discord.
        if created_at.year < 2015:
            created_at = datetime.utcfromtimestamp(timestamp + 1293840000)

        await ctx.send(f"**{user} (ID: {user_id})**\n```ldif\nBot: {user.bot}\nCreated: {created_at}\nHMAC: {hmac}\n```")


    @commands.command()
    @checks.bot_has_permissions(embed_links=True)
    async def pypi(self, ctx: commands.Context, *, package: str):
        """Gets information on a pypi package.
        (Bot Needs: Embed Links)

        EXAMPLE: pypi discord.py
        """
        await ctx.trigger_typing()
        try:
            response = await ctx.get(f"https://pypi.org/pypi/{urlquote(package, safe='')}/json", cache=True)
        except HTTPError as exc:
            if exc.status == 404:
                await ctx.send("That pypi package was not found.")
                return
            raise

        data = response["info"]

        embed = Embed(
            title=f"{data['name']} {data['version']}",
            description=data["summary"] or "No short description.",
            url=data["release_url"],
            colour=0x006DAD
        )
        embed.set_author(name=data["author"])
        embed.set_thumbnail(url="https://cdn-images-1.medium.com/max/1200/1*2FrV8q6rPdz6w2ShV6y7bw.png")
        embed.add_field(
            name="Classifiers",
            value=textwrap.shorten("\n".join(data["classifiers"]), width=460) or "No classifiers."
        )
        embed.add_field(name="Keywords", value=data["keywords"] or "No keywords.", inline=False)
        embed.set_footer(text="Powered by pypi.org")
        await ctx.send(embed=embed)


    @commands.command(aliases=["rtfs", "readthefuckingsource"])
    @checks.bot_has_permissions(embed_links=True)
    async def readtheeffingsource(self, ctx: commands.Context, *, query: str):
        """Searches the GitHub repository of discord.py.
        The search algorithm currently is a fuzzy search.
        (Bot Needs: Embed Links)

        EXAMPLE:
        (Ex. 1) readtheeffingsource Messageable
        (Ex. 2) readtheeffingsource Context.invoke
        """
        await ctx.trigger_typing()
        results = await ctx.get("https://rtfs.eviee.me/dpy", search=query, cache=True)

        if not results:
            await ctx.send("No results found.")
        else:
            # Have to convert to set before sorting because the API returns duplicate objects for some reason.
            objects = sorted(set(f"[`{result['path']}`]({result['url']})" for result in results[:12]))

            embed = Embed(title=f"Results for `{query}`", description="\n".join(objects), colour=Colour.blurple())
            embed.set_footer(text="Powered by rtfs.eviee.me")
            await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(DevUtils())
