"""
Copyright (c) 2018-present HitchedSyringe

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""


import re
from datetime import datetime, timedelta
from typing import Optional

import discord
from discord.ext import commands, flags
from discord.utils import find
from sleepy import checks
from sleepy.menus import PaginatorSource
from sleepy.paginators import WrappedPaginator
from sleepy.utils import plural


CUSTOM_EMOJI_REGEX = re.compile(r"<a?:[\w_]+:[0-9]{15,20}>")


class CannotPerformAction(commands.BadArgument):
    pass


class BanEntryNotFound(commands.BadArgument):

    def __init__(self, argument):
        super().__init__(f'User "{argument}" isn\'t banned.')


class ReasonTooLong(commands.BadArgument):

    def __init__(self, argument_length, max_length):
        super().__init__(f"Reason is too long. ({argument_length} > {max_length})")


class ActionableMember(commands.Converter):

    @staticmethod
    async def convert(ctx, argument):
        member = await commands.MemberConverter().convert(ctx, argument)

        if member == ctx.author:
            raise CannotPerformAction("Why would you want to do that to yourself?")

        if member == ctx.guild.owner:
            raise CannotPerformAction("I will not allow you to overthrow the owner.")

        if ctx.me.top_role <= member.top_role:
            raise CannotPerformAction("I can't do this action on that user due to role hierarchy.")

        if ctx.author.top_role <= member.top_role:
            raise CannotPerformAction("You can't do this action on that user due to role hierarchy.")

        return member


class BanEntry(commands.Converter):

    @staticmethod
    async def convert(ctx, argument):
        try:
            return await ctx.guild.fetch_ban(discord.Object(id=int(argument, base=10)))
        except discord.NotFound:
            raise BanEntryNotFound(argument) from None
        except ValueError:
            pass

        if (ban := find(lambda u: str(u.user) == argument, await ctx.guild.bans())) is None:
            raise BanEntryNotFound(argument)

        return ban


class BannableUser(commands.Converter):

    @staticmethod
    async def convert(ctx, argument):
        try:
            return await ActionableMember.convert(ctx, argument)
        except commands.MemberNotFound:
            pass

        return await commands.UserConverter().convert(ctx, argument)


class Reason(commands.Converter):

    @staticmethod
    async def convert(ctx, argument):
        tag = f"{ctx.author} (ID: {ctx.author.id}): "

        if (arg_len := len(argument)) > (limit := 512 - len(tag)):
            raise ReasonTooLong(arg_len, limit)

        return tag + argument


def psuedo_object_converter(value):
    try:
        return discord.Object(value)
    except TypeError:
        raise commands.BadArgument("Invalid snowflake ID.") from None


class Moderation(commands.Cog):
    """Commands having to do with server moderation.

    These obviously cannot be used in Private Messages.
    """

    # Most of the command checks should have internal
    # guild checks already. This is just a fallback
    # to ensure nothing slips through.
    async def cog_check(self, ctx):
        if ctx.guild is None:
            raise commands.NoPrivateMessage()

        return True

    async def cog_command_error(self, ctx, error):
        if isinstance(error, flags.ArgumentParsingError):
            await ctx.send(
                "An error occurred while processing your flag arguments."
                "\nPlease double-check your input arguments and try again."
            )
            error.handled__ = True
        elif isinstance(error, (commands.UserNotFound, commands.MemberNotFound)):
            await ctx.send("That user wasn't found.")
            error.handled__ = True
        elif isinstance(error, BanEntryNotFound):
            await ctx.send("That user isn't banned.")
            error.handled__ = True
        elif isinstance(error, (CannotPerformAction, ReasonTooLong)):
            await ctx.send(error)
            error.handled__ = True

    @staticmethod
    async def do_purge_strategy(ctx, *, limit, check, before=None, after=None):
        if before is None:
            before = ctx.message

        try:
            deleted = await ctx.channel.purge(limit=limit, check=check, before=before, after=after)
        except discord.HTTPException:
            await ctx.send("Deleting the messages failed.\nTry again later?")
            return

        # try:
        #     await ctx.message.delete()
        # except discord.HTTPException:  # oh well.
        #     pass

        if deleted:
            await ctx.send(f"Deleted **{len(deleted)}/{limit}** messages.", delete_after=10)
        else:
            await ctx.send("No messages were deleted.")

    @staticmethod
    async def do_multi_ban(ctx, users, *, reason, delete_message_days):
        total = len(users)
        confirmed = await ctx.prompt(
            f"This will ban **{plural(total, ',d'):user}** for:\n>>> {reason}\nAre you sure?"
        )

        if not confirmed:
            await ctx.send("Aborted.")
            return

        await ctx.trigger_typing()

        failed = 0
        for user in users:
            try:
                await ctx.guild.ban(user, reason=reason, delete_message_days=delete_message_days)
            except discord.HTTPException:
                failed += 1

        await ctx.send(f"Banned **{total - failed}/{total} users** for:\n>>> {reason}")

    @commands.command(aliases=("hackban",))
    @checks.has_guild_permissions(ban_members=True)
    @commands.bot_has_guild_permissions(ban_members=True)
    async def ban(
        self,
        ctx,
        user: BannableUser,
        delete_message_days: Optional[int] = 0,
        *,
        reason: Reason = None
    ):
        """Bans a user, optionally deleting *x* days worth of their messages.

        This command works on all users, regardless of whether
        they're a member of the server.

        User can either be a name, ID, or mention.

        (Permissions Needed: Ban Members)
        (Bot Needs: Ban Members)

        **EXAMPLES:**
        ```bnf
        <1> ban HitchedSyringe
        <2> ban @HitchedSyringe#0598 3
        <3> ban 140540589329481728 5 Spamming
        ```
        """
        if not 0 <= delete_message_days <= 7:
            await ctx.send(
                "Number of days worth of messages to delete must be between 1 and 7, inclusive."
            )
            return

        if reason is None:
            reason = f"{ctx.author} (ID: {ctx.author.id}): No reason provided."

        await ctx.guild.ban(user, reason=reason, delete_message_days=delete_message_days)

        await ctx.send("<a:sapphire_ok_hand:786093988679516160>")

    @commands.command()
    @checks.has_permissions(manage_messages=True)
    async def cleanup(self, ctx, amount: int = 10):
        """Deletes my messages and (if possible) any messages that look like they invoked me.

        If no amount is specified, then the previous 10
        messages that meet the above criteria will be
        deleted.

        (Permissions Needed: Manage Messages)
        (Bot Optionally Needs: Manage Messages)

        **EXAMPLE:**
        ```
        cleanup 100
        ```
        """
        if ctx.channel.permissions_for(ctx.me).manage_messages:
            # Shouts out to startswith for only taking tuples,
            # even though they're literally the same in almost
            # every manner other than mutability.
            prefixes = tuple(await ctx.bot.get_prefix(ctx.message))
            check = lambda m: m.author == ctx.me or m.content.startswith(prefixes)
        else:
            check = lambda m: m.author == ctx.me

        await self.do_purge_strategy(ctx, limit=amount, check=check)

    @commands.command()
    @checks.has_guild_permissions(kick_members=True)
    @commands.bot_has_guild_permissions(kick_members=True)
    async def kick(self, ctx, member: ActionableMember, *, reason: Reason = None):
        """Kicks a member.

        Member can either be a name, ID, or mention.

        (Permissions Needed: Kick Members)
        (Bot Needs: Kick Members)

        **EXAMPLES:**
        ```bnf
        <1> kick HitchedSyringe
        <2> kick @HitchedSyringe#0598 Spamming
        <3> kick 140540589329481728 Being annoying
        ```
        """
        if reason is None:
            reason = f"{ctx.author} (ID: {ctx.author.id}): No reason provided."

        await member.kick(reason=reason)

        await ctx.send("<a:sapphire_ok_hand:786093988679516160>")

    @flags.add_flag("--reason", "-r", type=Reason)
    @flags.add_flag("--delete-message-days", "-dmd", type=int, default=0)
    @flags.add_flag("--contains", nargs="+")
    @flags.add_flag("--endswith", "--ends", nargs="+")
    @flags.add_flag("--startswith", "--starts", nargs="+")
    @flags.add_flag("--matches", "--regex")
    @flags.add_flag("--created", type=int)
    @flags.add_flag("--joined", type=int)
    @flags.add_flag("--joined-before", type=discord.Member)
    @flags.add_flag("--joined-after", type=discord.Member)
    @flags.add_flag("--no-avatar", action="store_const", const=lambda m: m.avatar is None)
    @flags.add_flag("--no-roles", action="store_const", const=lambda m: len(m.roles) <= 1)
    @flags.add_flag("--show", "-s", action="store_true")
    @flags.command(usage="[options...]")
    @checks.has_guild_permissions(ban_members=True)
    @commands.bot_has_guild_permissions(ban_members=True)
    async def massban(self, ctx, **flags):
        """Bans multiple members from the server based on the given conditions.

        This uses a powerful "command-line" interface.
        Values with spaces must be surrounded by quotation marks.
        **All options are optional.**

        Members are only banned **if and only if** all conditions
        are met.

        **If no conditions are passed, then ALL members will be
        selected for banning.**

        Members can either be a name, ID, or mention.

        __The following options are valid:__

        `--reason` or `-r`
        > The reason for the ban.
        `--delete-message-days` or `-dmd`
        > The number of days worth of a banned user's messages to delete.
        `--contains`
        > Target members whose usernames contain the given substring(s).
        > Substrings are case-sensitive.
        `--endswith` or `--ends`
        > Target members whose usernames end with the given substring(s).
        > Substrings are case-sensitive.
        `--startswith` or `--starts`
        > Target members whose usernames start with the given substring(s).
        > Substrings are case-sensitive.
        `--matches` or `--regex`
        > Target members whose usernames match with the given regex.
        `--created`
        > Target members whose accounts were created less than specified minutes ago.
        `--joined`
        > Target members who joined less than specified minutes ago.
        `--joined-before`
        > Target members who joined before the member given.
        `--joined-after`
        > Target members who joined after the member given.

        __The remaining options do not take any arguments and are simply just flags:__

        `--no-avatar`
        > Target members that have a default avatar.
        `--no-roles`
        > Target members that do not have a role.
        `--show` or `-s`
        > Show members that meet the criteria for banning instead of actually banning them.

        (Permissions Needed: Ban Members)
        (Bot Needs: Ban Members)
        """
        delete_message_days = flags.pop("delete_message_days")

        if not 0 <= delete_message_days <= 7:
            await ctx.send(
                "Number of days worth of messages to delete must be between 0 and 7, inclusive."
            )
            return

        checks = [
            lambda m: (
                not m.bot
                and m != ctx.guild.owner
                and ctx.author.top_role > m.top_role
                and ctx.me.top_role > m.top_role
            ),
            *filter(callable, flags.values())
        ]

        if contains := flags["contains"]:
            checks.append(lambda m: any(sub in m.name for sub in contains))

        if ends := flags["endswith"]:
            checks.append(lambda m: m.name.endswith(tuple(ends)))

        if starts := flags["startswith"]:
            checks.append(lambda m: m.name.startswith(tuple(starts)))

        if (matches := flags["matches"]) is not None:
            try:
                regex = re.compile(matches)
            except re.error as exc:
                await ctx.send(f"Invalid match regex: {exc}")
                return
            else:
                checks.append(lambda m: regex.match(m.name))

        now = datetime.utcnow()

        if (c_minutes := flags["created"]) is not None:
            if c_minutes <= 0:
                await ctx.send("Created minutes ago must be greater than 0.")
                return

            checks.append(lambda m: m.created_at > now - timedelta(minutes=c_minutes))

        if (j_minutes := flags["joined"]) is not None:
            if j_minutes <= 0:
                await ctx.send("Joined minutes ago must be greater than 0.")
                return

            checks.append(lambda m: m.joined_at and m.joined_at > now - timedelta(minutes=j_minutes))

        if (before := flags["joined_before"]) is not None:
            checks.append(lambda m: m.joined_at and before.joined_at and m.joined_at < before.joined_at)

        if (after := flags["joined_after"]) is not None:
            checks.append(lambda m: m.joined_at and after.joined_at and m.joined_at > after.joined_at)

        members = [m for m in ctx.guild.members if all(c(m) for c in checks)]
        if not members:
            await ctx.send("No members met the criteria specified.")
            return

        if flags["show"]:
            perms = ctx.channel.permissions_for(ctx.me)

            if not (perms.add_reactions and perms.read_message_history):
                await ctx.send(
                    "I need the `Add Reactions` and `Read Message History` permissions"
                    " to show members that meet the given banning criteria."
                )
                return

            paginator = WrappedPaginator("```yaml", max_size=1000)
            members.sort(key=lambda m: m.joined_at or now)

            for member in members:
                paginator.add_line(
                    f"{member} (ID: {member.id})"
                    f"\n\tJoined: {member.joined_at}"
                    f"\n\tCreated: {member.created_at}"
                )

            await ctx.paginate(PaginatorSource(paginator))
            return

        await self.do_multi_ban(
            ctx,
            members,
            reason=flags["reason"] or f"{ctx.author} (ID: {ctx.author.id}): No reason provided.",
            delete_message_days=delete_message_days
        )

    @commands.command()
    @checks.has_guild_permissions(ban_members=True)
    @commands.bot_has_guild_permissions(ban_members=True)
    async def multiban(
        self,
        ctx,
        users: commands.Greedy[BannableUser],
        delete_message_days: Optional[int] = 0,
        *,
        reason: Reason = None
    ):
        """Bans multiple users, optionally deleting *x* days worth of their messages.

        Users can either be a name, ID, or mention.

        Passing an ID of a user not in the server will
        ban that user anyway.

        (Permissions Needed: Ban Members)
        (Bot Needs: Ban Members)

        **EXAMPLES:**
        ```bnf
        <1> multiban HitchedSyringe 3
        <2> multiban @HitchedSyringe#0598 140540589329481728 5 Trolling
        ```
        """
        if not 0 <= delete_message_days <= 7:
            await ctx.send(
                "Number of days worth of messages to delete must be between 0 and 7, inclusive."
            )
            return

        if not users:
            await ctx.send("You must specify at least 1 user to ban.")
            return

        if reason is None:
            reason = f"{ctx.author} (ID: {ctx.author.id}): No reason provided."

        await self.do_multi_ban(ctx, users, reason=reason, delete_message_days=delete_message_days)

    @commands.group(aliases=("remove",), invoke_without_command=True)
    @checks.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    async def purge(self, ctx, amount: int = 10):
        """Deletes a specified amount of messages.

        If no amount is specified, then the previous 10
        messages will be deleted.

        (Permissions Needed: Manage Messages)
        (Bot Needs: Manage Messages)

        **EXAMPLE:**
        ```
        purge 100
        ```
        """
        await self.do_purge_strategy(ctx, limit=amount, check=lambda _: True)

    @purge.command(name="bots")
    async def purge_bots(self, ctx, prefix: Optional[str], amount: int = 10):
        """Deletes a bot user's messages and optionally any messages with a prefix.

        If no amount is specified, then the previous 10
        messages that meet the above criteria will be
        deleted.

        (Permissions Needed: Manage Messages)
        (Bot Needs: Manage Messages)

        **EXAMPLES:**
        ```bnf
        <1> purge bots 100
        <2> purge bots ! 100
        ```
        """
        await self.do_purge_strategy(
            ctx,
            limit=amount,
            check=lambda m: (
                (m.webhook_id is None and m.author.bot)
                or (prefix is not None and m.content.startswith(prefix))
            )
        )

    @purge.command(name="contains")
    async def purge_contains(self, ctx, substring, amount: int = 10):
        """Deletes messages that contain a substring.

        Substring is case-sensitive and must be at
        least 3 characters long.

        If no amount is specified, then the previous
        10 messages that meet the above criteria will
        be deleted.

        (Permissions Needed: Manage Messages)
        (Bot Needs: Manage Messages)

        **EXAMPLES:**
        ```bnf
        <1> purge contains fuc 100
        <2> purge contains "i am" 100
        ```
        """
        if len(substring) < 3:
            await ctx.send("Substrings must be at least 3 characters long.")
        else:
            await self.do_purge_strategy(
                ctx,
                limit=amount,
                check=lambda m: substring in m.content
            )

    @flags.add_flag("--amount", type=int, default=10)
    @flags.add_flag("--before", type=psuedo_object_converter)
    @flags.add_flag("--after", type=psuedo_object_converter)
    @flags.add_flag("--startswith", "--starts", nargs="+")
    @flags.add_flag("--endswith", "--ends", nargs="+")
    @flags.add_flag("--contains", nargs="+")
    @flags.add_flag("--matches", "--regex")
    @flags.add_flag("--users", "--user", nargs="+", type=discord.User)
    @flags.add_flag("--bot", action="store_const", const=lambda m: m.author.bot)
    @flags.add_flag("--embeds", action="store_const", const=lambda m: m.embeds)
    @flags.add_flag("--emoji", action="store_const", const=lambda m: CUSTOM_EMOJI_REGEX.match(m.content))
    @flags.add_flag("--files", "--attachments", action="store_const", const=lambda m: m.attachments)
    @flags.add_flag("--any", action="store_true")
    @flags.add_flag("--not", action="store_true")
    @purge.command(cls=flags.FlagCommand, name="custom", aliases=("advanced",), usage="[options...]")
    async def purge_custom(self, ctx, **flags):
        """An advanced purge command that allows for granular control over filtering messages for deletion.

        This uses a powerful "command-line" interface.
        Values with spaces must be surrounded by quotation marks.
        **All options are optional.**

        By default, messages that meet ALL of the conditions given
        are deleted, unless `--any` is passed, in which case only
        if ANY are met.

        If no flags or options are passed, then the previous 10
        messages will be deleted.

        Users can either be a name, ID, or mention.

        __The following options are valid **(All options are optional.)**:__

        `--amount`
        > The number of messages to search for and delete.
        > Must be between 1 and 2000, inclusive.
        > Defaults to `10` if omitted.
        `--before`
        > Target messages before the given message ID.
        `--after`
        > Target messages after the given message ID.
        `--startswith` or `--starts`
        > Target messages that start with the given substring(s).
        > Substrings are case-sensitive.
        `--endswith` or `--ends`
        > Target messages that end with the given substring(s).
        > Substrings are case-sensitive.
        `--contains`
        > Target messages that contain the given substring(s).
        > Substrings are case-sensitive.
        `--matches` or `--regex`
        > Target messages whose content matches the given regex.
        `--users` or `--user`
        > Target messages sent by the given user(s).

        __The remaining options do not take any arguments and are simply just flags:__

        `--bot`
        > Target messages sent by a bot user.
        `--embeds`
        > Target messages that contain embeds.
        `--emoji`
        > Target messages that contain a custom emoji.
        `--files` or `--attachments`
        > Target messages that contain file attachments.
        `--any`
        > Targeted messages are only deleted if ANY conditions given are met.
        `--not`
        > Delete messages that do NOT meet the conditions given.

        (Permissions Needed: Manage Messages)
        (Bot Needs: Manage Messages)
        """
        checks = [v for v in flags.values() if callable(v)]

        if contains := flags["contains"]:
            checks.append(lambda m: any(sub in m.content for sub in contains))

        if ends := flags["endswith"]:
            checks.append(lambda m: m.content.endswith(tuple(ends)))

        if starts := flags["startswith"]:
            checks.append(lambda m: m.content.startswith(tuple(starts)))

        if users := flags["users"]:
            checks.append(lambda m: m.author in users)

        matches = flags["matches"]
        if matches is not None:
            try:
                regex = re.compile(matches)
            except re.error as exc:
                await ctx.send(f"Invalid match regex: {exc}")
                return
            else:
                checks.append(lambda m: regex.match(m.content))

        if checks:
            def check(m):
                func = any if flags["any"] else all
                result = func(c(m) for c in checks)

                if flags["not"]:
                    return not result

                return result
        else:
            check = lambda _: True

        await self.do_purge_strategy(
            ctx,
            limit=flags["amount"],
            check=check,
            before=flags["before"],
            after=flags["after"]
        )

    @purge.command(name="embeds")
    async def purge_embeds(self, ctx, amount: int = 10):
        """Deletes messages that contain a rich embed.

        If no amount is specified, then the previous 10
        messages that meet the above criteria will be
        deleted.

        (Permissions Needed: Manage Messages)
        (Bot Needs: Manage Messages)

        **EXAMPLE:**
        ```
        purge embeds 100
        ```
        """
        await self.do_purge_strategy(ctx, limit=amount, check=lambda m: m.embeds)

    @purge.command(name="emojis")
    async def purge_emojis(self, ctx, amount: int = 10):
        """Deletes messages that contain a custom emoji.

        If no amount is specified, then the previous 10
        messages that meet the above criteria will be
        deleted.

        (Permissions Needed: Manage Messages)
        (Bot Needs: Manage Messages)

        **EXAMPLE:**
        ```
        purge emojis 100
        ```
        """
        await self.do_purge_strategy(
            ctx,
            limit=amount,
            check=lambda m: CUSTOM_EMOJI_REGEX.match(m.content) is not None
        )

    @purge.command(name="files", aliases=("attachments",))
    async def purge_files(self, ctx, amount: int = 10):
        """Deletes messages that contain an attachment.

        If no amount is specified, then the previous 10
        messages that meet the above criteria will be
        deleted.

        (Permissions Needed: Manage Messages)
        (Bot Needs: Manage Messages)

        **EXAMPLE:**
        ```
        purge files 100
        ```
        """
        await self.do_purge_strategy(ctx, limit=amount, check=lambda m: m.attachments)

    @purge.command(name="reactions")
    @checks.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True, read_message_history=True)
    async def purge_reactions(self, ctx, amount: int = 10):
        """Removes all reactions from any messages that have them.

        If no amount is specified, then reactions will
        be removed from the previous 10 messages.

        (Permissions Needed: Manage Messages)
        (Bot Needs: Manage Messages and Read Message History)

        **EXAMPLE:**
        ```
        purge reactions 100
        ```
        """
        if not 1 <= amount <= 2000:
            await ctx.send("Amount must be between 0 and 2000, inclusive.")

        total = 0
        async for msg in ctx.history(limit=amount, before=ctx.message).filter(lambda m: m.reactions):
            total += sum(r.count for r in msg.reactions)
            await msg.clear_reactions()

        await ctx.send(f"Removed **{plural(total, ',d'):reaction}**.")

    @purge.command(name="users", aliases=("user",))
    async def purge_users(self, ctx, users: commands.Greedy[discord.User], amount: int = 10):
        """Deletes a user or list of users' messages.

        If no amount is specified, then the previous 10
        messages that meet the above criteria will be
        deleted.

        (Permissions Needed: Manage Messages)
        (Bot Needs: Manage Messages)

        **EXAMPLES:**
        ```bnf
        <1> purge users HitchedSyringe#0598 100
        <2> purge users @HitchedSyringe#0598 140540589329481728 100
        ```
        """
        if users:
            await self.do_purge_strategy(ctx, limit=amount, check=lambda m: m.author in users)
        else:
            await ctx.send("You must specify at least **1 user** to purge messages for.")

    @commands.command()
    @checks.has_guild_permissions(kick_members=True)
    @commands.bot_has_guild_permissions(ban_members=True)
    async def softban(
        self,
        ctx,
        member: BannableUser,
        delete_message_days: Optional[int] = 1,
        *,
        reason: Reason = None
    ):
        """Softbans a user.

        Softbanning is the act of banning and then instantly
        unbanning a user, essentially allowing you to kick a
        user while also deleting their messages.

        This command works on all users, regardless of whether
        they're a member of the server.

        User can either be a name, ID, or mention.

        If the number of days worth of the users's messages
        to delete isn't specified, then 1 day's worth of the
        user's messages will be deleted.

        (Permissions Needed: Kick Members)
        (Bot Needs: Ban Members)

        **EXAMPLES:**
        ```bnf
        <1> softban HitchedSyringe
        <2> softban @HitchedSyringe#0598 3
        <3> softban 140540589329481728 5 Spamming
        ```
        """
        if not 1 <= delete_message_days <= 7:
            await ctx.send(
                "Number of days worth of messages to delete must be between 1 and 7, inclusive."
            )
            return

        if reason is None:
            reason = f"{ctx.author} (ID: {ctx.author.id}): No reason provided."

        await ctx.guild.ban(member, reason=reason, delete_message_days=delete_message_days)
        await ctx.guild.unban(member, reason=reason)

        await ctx.send("<a:sapphire_ok_hand:786093988679516160>")

    @commands.command(aliases=("pardon",))
    @checks.has_guild_permissions(ban_members=True)
    @commands.bot_has_guild_permissions(ban_members=True)
    async def unban(self, ctx, user: BanEntry, *, reason: Reason = None):
        """Unbans a user.

        You can either pass a user's ID or name#discrim combination.
        The former is typically the easiest to use.

        (Permissions Needed: Ban Members)
        (Bot Needs: Ban Members)

        **EXAMPLES:**
        ```bnf
        <1> unban HitchedSyringe#0598
        <2> unban 140540589329481728 Appealed
        ```
        """
        if reason is None:
            reason = f"{ctx.author} (ID: {ctx.author.id}): No reason provided."

        await ctx.guild.unban(user.user, reason=reason)

        await ctx.send(
            f"Unbanned {user.user} (ID: {user.user.id})\n>>> **Ban Reason:**\n{user.reason}"
        )


def setup(bot):
    bot.add_cog(Moderation())
