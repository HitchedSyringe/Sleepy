"""
© Copyright 2018-2020 HitchedSyringe, All Rights Reserved.

Redistributing, using or owning a copy of this software without explicit permissions
is against these licensing terms, your license(s) to this software can be revoked at
any time without explicit notice beforehand and at the time of revocation.
Your license is non-transferrable, the terms of this license only permit you to do the
following; Create pull requests and make modifications to this repository.

"""


import asyncio
import contextlib
import copy
import inspect
import io
import logging
import subprocess
import textwrap
import time
import traceback
from functools import partial
from typing import Optional

import discord
from discord import Embed
from discord.ext import commands

from SleepyBot.utils import checks


LOG = logging.getLogger(__name__)


def _clean_code(value: str) -> str:
    """Pseudo-converter that codeblocks and returns the raw text inside."""
    # handle codeblocks ```py\n\n```
    if value.startswith("```") and value.endswith("```"):
        return "\n".join(value.split("\n")[1:-1])

    # handle one-liners
    return value.strip("` \n")


class PerfMocker:
    """An awaitable mock object."""

    def __init__(self):
        self.loop = asyncio.get_event_loop()


    def permissions_for(self, obj):
        perms = discord.Permissions.all()

        # pylint: disable=assigning-non-slot
        perms.administrator = False
        # Lie and say we don't have embed links and add reactions in order to prevent paginations.
        # This shouldn't hurt any user checks since most of those have owner overrides anyway.
        perms.embed_links = False
        perms.add_reactions = False
        # pylint: enable=assigning-non-slot

        return perms


    # We need these in order to slightly tamper with the message sending interface.
    def __getattr__(self, attr):
        return self


    def __call__(self, *args, **kwargs):
        return self


    def __await__(self):
        future = self.loop.create_future()
        future.set_result(self)
        return future.__await__()


class AnyTextChannel(commands.Converter):
    """Converts to a :class:`discord.TextChannel`.
    This first does a guild-wide lookup before doing a global + ID lookup.
    """

    @staticmethod
    async def convert(ctx: commands.Context, argument):
        try:
            return await commands.TextChannelConverter().convert(ctx, argument)
        except commands.BadArgument:
            if not argument.isdigit():
                raise commands.BadArgument("Invalid channel.") from None

            channel = ctx.bot.get_channel(int(argument, base=10))
            if channel is None:
                raise commands.BadArgument("Invalid channel.") from None
            return channel


class Owner(commands.Cog, command_attrs=dict(hidden=True)):
    """Commands that only my owner(s) can use."""

    def __init__(self):
        self._repl_sessions = set()
        self._last_eval_result = None


    async def cog_check(self, ctx: commands.Context):
        if ctx.author.id not in ctx.bot.owner_ids:
            raise commands.NotOwner()
        return True


    @commands.command(aliases=["pm"])
    async def dm(self, ctx: commands.Context, user_id: int, *, content: str):
        """Sends a user a direct message as me.
        This command does not send any Discord file attachments to the recipient.
        """
        user = ctx.bot.get_user(user_id)
        if user is None:
            await ctx.send("Invalid user ID.")
            return

        embed = Embed(title="Message", description=content, colour=0x2F3136, timestamp=ctx.message.created_at)
        embed.set_author(name=f"{ctx.author} (ID: {ctx.author.id})", icon_url=ctx.author.avatar_url)
        embed.set_footer(text="This DM was sent because you gave feedback or found a bug, I do not monitor this DM.")

        # TODO: Add ability to send attachments whenever there's a cleaner way to implement it.

        try:
            await user.send(embed=embed)
        except discord.HTTPException:
            await ctx.send("An error occurred while sending your message.\nTry again later?")
        else:
            await ctx.send("Your message was successfully sent.")


    @commands.command(aliases=["repeat"])
    async def do(self, ctx: commands.Context, times: int, *, command: str):
        """Runs and repeats a command x number of times, while also attempting to avoid cooldowns and converters."""
        message = copy.copy(ctx.message)
        message.content = ctx.prefix + command

        new_ctx = await ctx.bot.get_context(message, cls=type(ctx))

        for _ in range(times):
            await new_ctx.reinvoke()


    @commands.command()
    async def echo(self, ctx: commands.Context, *, message: str):
        """Sends a message in the current channel as me."""
        await ctx.send(message)


    @commands.command(name="eval")
    @checks.bot_has_permissions(attach_files=True)
    async def _eval(self, ctx: commands.Context, *, body: _clean_code):
        """Evaluates some code."""
        env = {
            "author": ctx.author,
            "bot": ctx.bot,
            "channel": ctx.channel,
            "ctx": ctx,
            "guild": ctx.guild,
            "message": ctx.message,
            "_": self._last_eval_result,  # Make this REPL-like
        }
        env.update(globals())


        stdout = io.StringIO()
        src = f"async def func():\n{textwrap.indent(body, '       ')}"

        try:
            with contextlib.redirect_stdout(stdout):
                exec(src, env)
        except Exception as exc:
            await ctx.send(f"```py\n{type(exc).__name__}: {exc}\n```")
            return


        try:
            func = env["func"]
            result = await func()
        except Exception:
            result = traceback.format_exc()
            status_reaction = "<:xmark:512814698136076299>"
        else:
            status_reaction = "<a:sapphire_ok_hand:618630481986191380>"

        if ctx.channel.permissions_for(ctx.me).add_reactions:
            await ctx.message.add_reaction(status_reaction)

        output = stdout.getvalue()

        if result is None:
            if output:
                await ctx.safe_send(f"```py\n{output}\n```", filename="eval_result")
            # Don't do anything if the evaluation returned ``None``
        else:
            self._last_eval_result = result
            await ctx.safe_send(f"```py\n{output}{result}\n```", filename="eval_result")


    @commands.command(aliases=["exts"])
    @checks.bot_has_permissions(embed_links=True)
    async def extensions(self, ctx: commands.Context):
        """Shows the loaded and unloaded extensions.
        NOTE: Unloaded extensions are extensions detected in the extensions directory that aren't loaded.
        This doesn't include extensions in any subsequent folders.
        """
        embed = Embed(
            title="\N{GEAR}\ufe0f Extensions",
            description=f"Showing statuses of **{len(ctx.bot.all_exts)} total extensions**:\n",
            colour=0x2F3136
        )
        embed.description += "\n".join(f"{ctx.tick(ext in ctx.bot.extensions)} `{ext}`" for ext in ctx.bot.all_exts)

        await ctx.send(embed=embed)


    @commands.command(aliases=["leaveguild"])
    @checks.bot_has_permissions(add_reactions=True, read_message_history=True)
    async def leaveserver(self, ctx: commands.Context, guild_id: int = None):
        """Forces me to leave a server.
        If no server ID is given, then I will leave the current server instead.
        (Bot Needs: Add Reactions and Read Message History)
        """
        if guild_id is not None:
            guild = ctx.bot.get_guild(guild_id)
            if guild is None:
                await ctx.send("Invalid server ID.")
                return
        else:
            guild = ctx.guild

        confirmation = await ctx.prompt(f"Are you sure you want to remove me from {guild} (ID: {guild.id})?")

        if confirmation:
            await ctx.send(f"Left {guild} (ID: {guild.id}).")
            await guild.leave()
        else:
            await ctx.send("Aborting...")


    @commands.command(aliases=["l"])
    @checks.bot_has_permissions(embed_links=True)
    async def load(self, ctx: commands.Context, *exts: str):
        """Loads one or more extensions.
        If no extensions are passed, then this loads all extensions in the extensions directory.
        """
        if not exts:
            exts = ctx.bot.all_exts
        else:
            if ctx.bot.config["Extension Config"]["exts_directory"] is not None:
                cleaned = str(ctx.bot.exts_directory.as_posix()).replace("/", ".")
                exts = frozenset(f"{cleaned}.{ext}" for ext in exts)
            else:
                exts = frozenset(exts)

        statuses = []
        for ext in exts:
            try:
                ctx.bot.load_extension(ext)
            except (commands.ExtensionAlreadyLoaded, commands.ExtensionNotFound):
                pass
            except commands.ExtensionError as exc:
                statuses.append(f"{ctx.tick(False)} ``{ext}``\n> {type(exc).__name__}: {exc}")
            else:
                statuses.append(f"{ctx.tick(True)} ``{ext}``")
                # Add it to the registered extensions if it isn't there already.
                ctx.bot.all_exts.add(ext)

        if statuses:
            embed = Embed(title="\N{INBOX TRAY} Loaded Extensions", description="\n".join(statuses), colour=0x2F3136)
            await ctx.send(embed=embed)
        else:
            await ctx.send("The extensions given were either already loaded or not found!")


    @commands.command()
    @checks.bot_has_permissions(attach_files=True)
    async def perf(self, ctx: commands.Context, *, command: str):
        """Checks the executing performance of a command, while also attempting to suppress HTTP calls."""
        message = copy.copy(ctx.message)
        message.content = ctx.prefix + command

        new_ctx = await ctx.bot.get_context(message, cls=type(ctx))

        new_ctx._state = new_ctx.channel = PerfMocker()

        if new_ctx.command is None:
            await ctx.send("Invalid command.")
            return

        start = time.perf_counter()
        try:
            await new_ctx.command.invoke(new_ctx)
        except commands.CommandError:
            success = False
            await ctx.safe_send(f"```py\n{traceback.format_exc()}\n```", filename="command_error")
        else:
            success = True

        await ctx.send(f"Status: {ctx.tick(success)} | Took {(time.perf_counter() - start) * 1000:.2f} ms.")


    @commands.command(name="reload", aliases=["r"])
    @checks.bot_has_permissions(embed_links=True)
    async def _reload(self, ctx: commands.Context, *exts: str):
        """Reloads one or more extensions.
        If no extensions are passed, then this reloads all loaded extensions.
        """
        if not exts:
            exts = tuple(ctx.bot.extensions.keys())
        else:
            if ctx.bot.config["Extension Config"]["exts_directory"] is not None:
                cleaned = str(ctx.bot.exts_directory.as_posix()).replace("/", ".")
                exts = frozenset(f"{cleaned}.{ext}" for ext in exts)
            else:
                exts = frozenset(exts)


        statuses = []
        for ext in exts:
            try:
                ctx.bot.reload_extension(ext)
            except (commands.ExtensionNotLoaded, commands.ExtensionNotFound):
                pass
            except commands.ExtensionError as exc:
                statuses.append(f"{ctx.tick(False)} ``{ext}``\n> {type(exc).__name__}: {exc}")
            else:
                statuses.append(f"{ctx.tick(True)} ``{ext}``")

        if statuses:
            embed = Embed(
                title="\N{ANTICLOCKWISE DOWNWARDS AND UPWARDS OPEN CIRCLE ARROWS} Reloaded Extensions",
                description="\n".join(statuses),
                colour=0x2F3136
            )
            await ctx.send(embed=embed)
        else:
            await ctx.send("The extensions given were either unloaded or not found!")


    # Most of repl is partly based off of R. Danny.
    @commands.command()
    @checks.bot_has_permissions(attach_files=True)
    async def repl(self, ctx: commands.Context):
        """Runs an interactive REPL session in the current channel."""
        if ctx.channel.id in self._repl_sessions:
            await ctx.send("Already running a REPL session in this channel.\nType `exit` or `quit` to exit.")
            return

        self._repl_sessions.add(ctx.channel.id)
        env = {
            "author": ctx.author,
            "bot": ctx.bot,
            "channel": ctx.channel,
            "ctx": ctx,
            "guild": ctx.guild,
            "message": ctx.message,
            "_": None,
        }

        await ctx.send("REPL session started, enter code to execute or evaluate.\nType `exit` or `quit` to exit.")


        def check(message):
            checks = (
                message.channel.id == ctx.channel.id,
                message.author.id == ctx.author.id,
                message.content.startswith("`")
            )
            return all(checks)


        while True:
            try:
                message = await ctx.bot.wait_for("message", check=check, timeout=600)
            except asyncio.TimeoutError:
                await ctx.send("REPL session expired. Exiting.")
                self._repl_sessions.remove(ctx.channel.id)
                break

            body = _clean_code(message.content)

            if body in ("exit()", "exit", "quit"):
                await ctx.send("REPL session closed. Exiting.")
                self._repl_sessions.remove(ctx.channel.id)
                break


            executor = exec

            if body.count("\n") == 0:
                # One-liner means it's probably an expression.
                # Unless it's something like ``if condition: do_something()``, which we catch anyway.
                try:
                    src = compile(body, "<repl session>", "eval")
                except SyntaxError:
                    # This could either be a genuine SyntaxError, or we passed code that should be used in exec().
                    # Either way, this will get handled later on, so we shouldn't have to worry about it here.
                    pass
                else:
                    executor = eval

            if executor is exec:
                try:
                    src = compile(body, "<repl session>", "exec")
                except SyntaxError as exc:
                    if exc.text is None:
                        await ctx.send(f"```py\nSyntaxError: {exc}\n```")
                    else:
                        await ctx.send(f"```py\n{exc.text}{'^':>{exc.offset}}\nSyntaxError: {exc}\n```")

                    continue


            env["message"] = message
            stdout = io.StringIO()

            try:
                with contextlib.redirect_stdout(stdout):
                    result = executor(src, env)

                    if inspect.isawaitable(result):
                        result = await result

            except Exception:
                result = traceback.format_exc()
            else:
                env["_"] = result

            output = stdout.getvalue()

            if result is None and output:
                await ctx.safe_send(f"```py\n{output}\n```", filename="repl_result")
            else:
                await ctx.safe_send(f"```py\n{output}{result}\n```", filename="repl_result")


    @commands.command(aliases=["sh"])
    @checks.bot_has_permissions(attach_files=True)
    async def shell(self, ctx: commands.Context, *, body: _clean_code):
        """Runs shell commands."""
        # The reason we're not using :func:`asyncio.create_subprocess_shell` here is
        # because it's deprecated in Python 3.8 and doesn't even work on Windows.
        _partial_runner = partial(subprocess.run, body, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        async with ctx.typing():
            result = await ctx.bot.loop.run_in_executor(None, _partial_runner)

        stdout = result.stdout.decode()
        stderr = result.stderr.decode()
        output = f"stdout:\n{stdout}\nstderr:\n{stderr}" if stderr else stdout

        await ctx.safe_send(f"```sh\n{output}\n```", filename="shell_result")


    @commands.command(aliases=["die", "kys"])
    async def shutdown(self, ctx: commands.Context):
        """Shuts me down."""
        await ctx.send("Drinking anti-freeze...")
        LOG.info("Shutdown command was executed. Shutting down...")
        await ctx.bot.logout()


    @commands.command()
    async def sudo(self, ctx: commands.Context, channel: Optional[AnyTextChannel], user: discord.User, *, command: str):
        """Runs a command as another user optionally in another channel.
        If no channel is given, the command is ran in the current channel.
        """
        message = copy.copy(ctx.message)
        message.content = ctx.prefix + command
        message.channel = channel or ctx.channel
        message.author = message.channel.guild.get_member(user.id) or user

        new_ctx = await ctx.bot.get_context(message, cls=type(ctx))
        await ctx.bot.invoke(new_ctx)


    @commands.command(aliases=["u"])
    @checks.bot_has_permissions(embed_links=True)
    async def unload(self, ctx: commands.Context, *exts: str):
        """Unloads one or more extensions.
        If no extensions are passed, then this unloads all loaded extensions (excluding core).
        """
        if not exts:
            exts = tuple(ctx.bot.extensions.keys())
        else:
            if ctx.bot.config["Extension Config"]["exts_directory"] is not None:
                cleaned = str(ctx.bot.exts_directory.as_posix()).replace("/", ".")
                exts = frozenset(f"{cleaned}.{ext}" for ext in exts)
            else:
                exts = frozenset(exts)

        statuses = []
        for ext in exts:
            if ext == __name__:
                continue

            try:
                ctx.bot.unload_extension(ext)
            except commands.ExtensionNotLoaded:
                pass
            except commands.ExtensionError as exc:
                statuses.append(f"{ctx.tick(False)} ``{ext}``\n> {type(exc).__name__}: {exc}")
            else:
                statuses.append(f"{ctx.tick(True)} ``{ext}``")

        if statuses:
            embed = Embed(title="\N{OUTBOX TRAY} Unloaded Extensions", description="\n".join(statuses), colour=0x2F3136)
            await ctx.send(embed=embed)
        else:
            await ctx.send("The extensions given were either already unloaded or not found!")


def setup(bot):
    bot.add_cog(Owner())
