"""
© Copyright 2018-2020 HitchedSyringe, All Rights Reserved.

Redistributing, using or owning a copy of this software without explicit permissions
is against these licensing terms, your license(s) to this software can be revoked at
any time without explicit notice beforehand and at the time of revocation.
Your license is non-transferrable, the terms of this license only permit you to do the
following; Create pull requests and make modifications to this repository.

"""


import re
from collections import Counter
from datetime import datetime
from typing import Optional

import discord
from discord.ext import commands, flags, menus

from SleepyBot.utils import checks, formatting


CUSTOM_EMOJI_REGEX = re.compile(r"<(a?):([\w_]+):(\d+)>")


# Although these two checks could be combined into a singular check,
# they're separate for the sake of clarity in user-facing error messages.
def _author_can_perform_action(ctx, target) -> bool:
    """Whether or not the author can perform the moderation action.
    This returns ``True`` if and only if ANY of the following apply:
        - The author's top role is higher than the target user's top role.
        - The author is the guild owner.
        - The author is a bot owner.
    """
    checks = (
        ctx.author.id in ctx.bot.owner_ids,
        ctx.author == ctx.guild.owner,
        ctx.author.top_role > target.top_role,
    )
    return any(checks)


def _bot_can_perform_action(ctx, target) -> bool:
    """Whether or not the bot can perform the moderation action.
    This returns ``True`` if and only if EITHER of the following apply:
        - The bot's top role is higher than the target user's top role.
        - The bot is the guild owner. (Probably unlikely)
    """
    return ctx.me.top_role > target.top_role or ctx.me == ctx.guild.owner


class _BannableMemberSource(menus.GroupByPageSource):
    """A special page source used exclusively by the ``massban`` command.

    This class is a subclass of :class:`menus.GroupByPageSource` and as a result,
    anything you can do with :class:`menus.GroupByPageSource`, you can also do with this page source.
    """

    def __init__(self, entries, *, per_page=8):
        key = lambda x: f"Members that meet the specified banning criteria. ({len(entries)} total)"
        super().__init__(entries, key=key, per_page=per_page)


    def format_page(self, menu, entry):
        joined = "\n".join(f"{m} (ID: {m.id})\n- Joined: {m.joined_at}\n- Created: {m.created_at}" for m in entry.items)
        return f"{entry.key}\n```yaml\n{joined}\n```\nPage {menu.current_page + 1}/{menu.source.get_max_pages()}"


class Reason(commands.Converter):
    """Converts an argument into a proper reason for the audit log."""

    @staticmethod
    async def convert(ctx: commands.Context, argument):
        reason = f"{ctx.author} (ID: {ctx.author.id}): {argument}"

        if len(reason) > 512:
            raise commands.BadArgument(
                f"Reason is too long. ({len(argument)}/{512 - len(reason) + len(argument)})"
            )

        return reason


class BannableUser(commands.Converter):
    """Converts to a :class:`discord.Member` or :class:`discord.Object`.
    This allows for both normal banning and hackbanning.
    Raises :exc:`commands.BadArgument` if nothing is resolved or if the internal role hierarchy checks failed.
    """

    @staticmethod
    async def convert(ctx: commands.Context, argument):
        try:
            user = await commands.MemberConverter().convert(ctx, argument)
        except commands.BadArgument:
            try:
                argument = int(argument, base=10)
            except ValueError:
                raise commands.BadArgument("Invalid user.") from None

            # Attempt to resolve a member. If we fail, then it's probably a hackban case.
            user = ctx.guild.get_member(argument)
            if user is None:
                if ctx.guild.chunked:
                    return discord.Object(argument)

                try:
                    user = await ctx.guild.fetch_member(argument)
                except discord.NotFound:
                    return discord.Object(argument)

        if not _bot_can_perform_action(ctx, user):
            raise commands.BadArgument("I cannot perform this action on this user due to role hierarchy.")

        if not _author_can_perform_action(ctx, user):
            raise commands.BadArgument("You cannot perform this action on this user due to role hierarchy.")

        return user


class BanEntry(commands.Converter):
    """Converts to a :class:`discord.BanEntry`."""

    @staticmethod
    async def convert(ctx: commands.Context, argument):
        if argument.isdigit():
            # Do a lookup by ID instead.
            try:
                return await ctx.guild.fetch_ban(discord.Object(id=int(argument, base=10)))
            except discord.NotFound:
                raise commands.BadArgument("This user has not been banned before.") from None

        ban_entry = discord.utils.find(lambda u: str(u.user) == argument, await ctx.guild.bans())

        if ban_entry is None:
            raise commands.BadArgument("This user has not been banned before.")

        return ban_entry


class Moderation(commands.Cog):
    """Commands having to do with server moderation.
    These cannot be used in Private Messages.
    """

    # Most of the guild-related checks used *should* already raise this,
    # this is mostly a fallback just in case.
    async def cog_check(self, ctx: commands.Context):
        if ctx.guild is None:
            raise commands.NoPrivateMessage()

        return True


    async def cog_command_error(self, ctx: commands.Context, error):
        error = getattr(error, "original", error)

        if isinstance(error, flags.ArgumentParsingError):
            await ctx.send(f"Argument parsing error: {error}")
            error.handled = True
        elif isinstance(error, commands.BadArgument):
            # This is an attempt to make this less confusing for the end-user.
            raw_error = str(error)
            if raw_error.startswith(("I cannot", "Reason", "This user", "You cannot")):
                await ctx.send(raw_error)
                error.handled = True


    @staticmethod
    async def _do_purge_strategy(ctx, *, limit: int, check, **kwargs) -> None:
        """Performs a purge strategy and then sends a messsage giving the users who had their messages removed.
        For internal use only.
        """
        if limit <= 0 or limit > 2000:
            await ctx.send("Search limit must be greater than zero and less than 2000.")
            return

        try:
            deleted_messages = await ctx.channel.purge(
                limit=limit, check=check, before=kwargs.pop("before", ctx.message), **kwargs
            )
        except discord.HTTPException as exc:
            await ctx.send(f"An error occurred while trying to delete the messages: `{exc}`\nTry again later?")
            return

        # try:
        #     await ctx.message.delete()
        # except discord.HTTPException:  # oh well.
        #     pass

        if not deleted_messages:
            await ctx.send("No messages were deleted.")
            return

        authors = Counter(m.author.display_name for m in deleted_messages)
        contents = (
            f"Deleted **{formatting.plural(len(deleted_messages)):message}** in {ctx.channel.mention}.",
            f"```py\n{formatting.tchart(authors.most_common())}\n```",
        )

        to_send = "\n".join(contents)

        if len(to_send) > 2000:
            await ctx.send(contents[0], delete_after=10)
        else:
            await ctx.send(to_send, delete_after=10)


    @commands.command()
    @checks.has_guild_permissions(ban_members=True)
    @checks.bot_has_guild_permissions(ban_members=True)
    async def ban(self, ctx: commands.Context,
                  user: BannableUser, delete_message_days: Optional[int] = 0, *, reason: Reason = None):
        """Bans a user from the server, optionally deleting messages from x days ago.
        Passing an ID of a user not in the server will ban that user anyway.
        (Permissions Needed: Ban Members)
        (Bot Needs: Ban Members)

        EXAMPLE:
        (Ex. 1) ban HitchedSyringe
        (Ex. 2) ban @HitchedSyringe#0598 3
        (Ex. 3) ban 140540589329481728 5 Spamming
        """
        if delete_message_days < 0 or delete_message_days > 7:
            await ctx.send("Number of days must be within 0 and 7.")
            return

        if reason is None:
            reason = f"{ctx.author} (ID: {ctx.author.id}): No reason provided."

        await ctx.guild.ban(user, reason=reason, delete_message_days=delete_message_days)
        await ctx.send("<a:sapphire_ok_hand:618630481986191380>")


    @commands.command()
    @checks.has_permissions(manage_messages=True)
    async def cleanup(self, ctx: commands.Context, search: int = 10):
        """Cleans up my messages and (if possible) any messages that look like they invoked me from the channel.
        If no search limit is specified, then the previous 10 messages that meet the above criteria are deleted.
        (Permissions Needed: Manage Messages)
        (Bot Optionally Needs: Manage Messages)

        EXAMPLE: cleanup 100
        """
        if ctx.channel.permissions_for(ctx.me).manage_messages:
            prefixes = tuple(await ctx.bot.get_prefix(ctx.message))  # thanks startswith
            check = lambda m: m.author == ctx.me or m.content.startswith(prefixes)
        else:
            check = lambda m: m.author == ctx.me

        await self._do_purge_strategy(ctx, limit=search, check=check)


    @commands.command()
    @checks.has_guild_permissions(kick_members=True)
    @checks.bot_has_guild_permissions(kick_members=True)
    async def kick(self, ctx: commands.Context, member: discord.Member, *, reason: Reason = None):
        """Kicks a member from the server.
        (Permissions Needed: Kick Members)
        (Bot Needs: Kick Members)

        EXAMPLE:
        (Ex. 1) kick HitchedSyringe
        (Ex. 2) kick @HitchedSyringe#0598 Spamming
        (Ex. 3) kick 140540589329481728 Attempting to incite a raid.
        """
        if not _bot_can_perform_action(ctx, member):
            await ctx.send("I cannot perform this action on this user due to role hierarchy.")
            return

        if not _author_can_perform_action(ctx, member):
            await ctx.send("You cannot perform this action on this user due to role hierarchy.")
            return

        if reason is None:
            reason = f"{ctx.author} (ID: {ctx.author.id}): No reason provided."

        await member.kick(reason=reason)
        await ctx.send("<a:sapphire_ok_hand:618630481986191380>")


    @flags.add_flag("--reason", "-r", type=Reason)
    @flags.add_flag("--delete-message-days", "-dmd", type=int, default=0)
    @flags.add_flag("--contains", type=str, nargs="+")
    @flags.add_flag("--endswith", "--ends", type=str, nargs="+")
    @flags.add_flag("--startswith", "--starts", type=str, nargs="+")
    @flags.add_flag("--created", type=int)
    @flags.add_flag("--joined", type=int)
    @flags.add_flag("--joined-before", type=discord.Member)
    @flags.add_flag("--joined-after", type=discord.Member)
    @flags.add_flag("--no-avatar", action="store_const", const=lambda m: m.avatar is None)
    @flags.add_flag("--no-roles", action="store_const", const=lambda m: not m.roles)
    @flags.add_flag("--show", "-s", action="store_true")
    @flags.command(usage="[options...]")
    @checks.has_guild_permissions(ban_members=True)
    @checks.bot_has_guild_permissions(ban_members=True)
    async def massban(self, ctx: commands.Context, **flags):
        """Bans multiple members from the server based on the given conditions.

        This uses a powerful "command-line" interface.
        Quotation marks must be used if a value has spaces.
        **All options are optional.**

        Users are only banned **if and only if** all conditions are met.
        **If no conditions are passed, then ALL members are selected for banning.**

        __The following options are valid:__

        `--reason` or `-r`: The reason for the ban.
        `--delete-message-days` or `-dmd`: How many days worth of a banned user's messages to delete.
        `--contains`: Target any members whose names that contain the given substring(s).
        `--endswith` or `--ends`: Target any members whose names end with the given substring(s).
        `--startswith` or `--starts`: Target any members whose names start with the given substring(s).
        `--created`: Target members whose accounts were created less than specified minutes ago.
        `--joined`: Target members that joined less than specified minutes ago.
        `--joined-before`: Target members who joined before the member given.
        `--joined-after`: Target members who joined after the member given.

        __The remaining options do not take any arguments and are simply just flags:__

        `--no-avatar`: Target members that have a default avatar.
        `--no-roles`: Target members that do not have a role.
        `--show` or `-s`: Show members that meet the criteria for banning instead of actually banning them.

        (Permissions Needed: Ban Members)
        (Bot Needs: Ban Members)
        """
        delete_message_days = flags["delete_message_days"]
        if delete_message_days < 0 or delete_message_days > 7:
            await ctx.send("Number of days must be within 0 and 7.")
            return

        contains = flags["contains"]
        ends = flags["endswith"]
        starts = flags["startswith"]
        created_minutes = flags["created"]
        joined_minutes = flags["joined"]
        before = flags["joined_before"]
        after = flags["joined_after"]
        no_avatar = flags["no_avatar"]
        no_roles = flags["no_roles"]

        guild_members = ctx.guild.members
        now = datetime.utcnow()

        filters = [
            lambda m: not m.bot,
            lambda m: _bot_can_perform_action(ctx, m) and _author_can_perform_action(ctx, m),
        ]

        if contains:
            filters.append(lambda m: any(sub in m.name for sub in contains))

        if ends:
            filters.append(lambda m: m.name.endswith(ends))

        if starts:
            filters.append(lambda m: m.name.startswith(starts))

        if created_minutes is not None:
            if created_minutes <= 0:
                await ctx.send("Created minutes ago must be greater than 0.")
            filters.append(lambda m: m.created_at > now - datetime.timedelta(minutes=created_minutes))

        if joined_minutes is not None:
            if joined_minutes <= 0:
                await ctx.send("Joined minutes ago must be greater than 0.")
            filters.append(lambda m: m.joined_at and m.joined_at > now - datetime.timedelta(minutes=joined_minutes))

        if before is not None:
            filters.append(lambda m: m.joined_at and before.joined_at and m.joined_at < before.joined_at)

        if after is not None:
            filters.append(lambda m: m.joined_at and after.joined_at and m.joined_at > after.joined_at)

        if no_avatar is not None:
            filters.append(no_avatar)

        if no_roles is not None:
            filters.append(no_roles)

        members = {m for m in guild_members if all(f(m) for f in filters)}
        total_members = len(members)

        if total_members == 0:
            await ctx.send("No members met the criteria specified.")
            return

        if flags["show"]:
            perms = ctx.channel.permissions_for(ctx.me)

            if not perms.add_reactions and not perms.read_message_history:
                await ctx.send(
                    "I need the `Add Reactions` and `Read Message History` permissions to show members to ban."
                )
                return

            source = _BannableMemberSource(sorted(members, key=lambda m: m.joined_at or now))
            await ctx.paginate(source)
            return

        reason = flags["reason"] or f"{ctx.author} (ID: {ctx.author.id}): No reason provided."

        confirmation = await ctx.prompt(
            f"This will ban **{formatting.plural(total_members):member}** for:\n>>> {reason}\nAre you sure?"
        )

        if not confirmation:
            await ctx.send("Aborting...")
            return

        failed = 0
        for member in members:
            try:
                await member.ban(reason=reason, delete_message_days=delete_message_days)
            except discord.HTTPException:
                failed += 1

        await ctx.send(f"Banned **{total_members - failed}/{total_members} members** for:\n>>> {reason}")


    @commands.command()
    @checks.has_guild_permissions(ban_members=True)
    @checks.bot_has_guild_permissions(ban_members=True)
    async def multiban(self, ctx: commands.Context,
                       users: commands.Greedy[BannableUser], delete_message_days: Optional[int] = 0,
                       *, reason: Reason = None):
        """Bans multiple users from the server, optionally deleting their messages from x days ago.
        Passing an ID of a user not in the server will ban that user anyway.
        (Permissions Needed: Ban Members)
        (Bot Needs: Ban Members)

        EXAMPLE:
        (Ex. 1) multiban HitchedSyringe 3
        (Ex. 2) multiban @HitchedSyringe#0598 140540589329481728 5 Spamming
        """
        if delete_message_days < 0 or delete_message_days > 7:
            await ctx.send("Number of days must be within 0 and 7.")
            return

        total_users = len(users)

        if total_users == 0:
            await ctx.send("You must specify at least **1 user** to ban.")
            return

        if reason is None:
            reason = f"{ctx.author} (ID: {ctx.author.id}): No reason provided."

        confirmation = await ctx.prompt(
            f"This will ban **{formatting.plural(total_users):user}** for:\n>>> {reason}\nAre you sure?"
        )

        if not confirmation:
            await ctx.send("Aborting...")
            return

        failed = 0
        for user in users:
            try:
                await ctx.guild.ban(user, reason=reason, delete_message_days=delete_message_days)
            except discord.HTTPException:
                failed += 1

        await ctx.send(f"Banned **{total_users - failed}/{total_users} users** for:\n>>> {reason}")


    @commands.group(aliases=["remove"], invoke_without_command=True)
    @checks.has_permissions(manage_messages=True)
    @checks.bot_has_permissions(manage_messages=True)
    async def purge(self, ctx: commands.Context, search: int = 10):
        """Deletes x amount of messages.
        If no search limit is specified, then the previous 10 messages are deleted.
        (Permissions Needed: Manage Messages)
        (Bot Needs: Manage Messages)

        EXAMPLE: purge 100
        """
        await self._do_purge_strategy(ctx, limit=search, check=lambda m: True)


    @purge.command(name="bots")
    async def purge_bots(self, ctx: commands.Context, prefix: Optional[str], search: int = 10):
        """Deletes a bot user's messages and optionally any messages with a prefix.
        If no search limit is specified, then the previous 10 messages that meet the above criteria are deleted.
        (Permissions Needed: Manage Messages)
        (Bot Needs: Manage Messages)

        EXAMPLE:
        (Ex. 1) purge bots 100
        (Ex. 2) purge bots ! 100
        """
        if prefix is not None:
            check = lambda m: (m.webhook_id is None and m.author.bot) or m.content.startswith(prefix)
        else:
            check = lambda m: m.webhook_id is None and m.author.bot

        await self._do_purge_strategy(ctx, limit=search, check=check)


    @purge.command(name="contains")
    async def purge_contains(self, ctx: commands.Context, substring: str, search: int = 10):
        """Deletes messages that contain a substring.
        Substrings must be at least 3 characters long.
        If no search limit is specified, then the previous 10 messages that meet the above criteria are deleted.
        (Permissions Needed: Manage Messages)
        (Bot Needs: Manage Messages)

        EXAMPLE:
        (Ex. 1) purge contains fuc 100
        (Ex. 2) purge contains "i am" 100
        """
        if len(substring) < 3:
            await ctx.send("Substrings must be at least 3 characters long.")
        else:
            await self._do_purge_strategy(ctx, limit=search, check=lambda m: substring in m.content)


    @flags.add_flag("--after", type=int)
    @flags.add_flag("--before", type=int)
    @flags.add_flag("--contains", type=str, nargs="+")
    @flags.add_flag("--endswith", "--ends", type=str, nargs="+")
    @flags.add_flag("--search", type=int, default=10)
    @flags.add_flag("--startswith", "--starts", type=str, nargs="+")
    @flags.add_flag("--users", "--user", nargs="+", type=discord.User)
    @flags.add_flag("--bot", action="store_const", const=lambda m: m.author.bot)
    @flags.add_flag("--embeds", action="store_const", const=lambda m: m.embeds)
    @flags.add_flag("--emoji", action="store_const", const=lambda m: CUSTOM_EMOJI_REGEX.match(m.content) is not None)
    @flags.add_flag("--files", "--attachments", action="store_const", const=lambda m: m.attachments)
    @flags.add_flag("--any", action="store_true")
    @flags.add_flag("--not", action="store_true")
    @purge.command(name="custom", aliases=["advanced"], cls=flags.FlagCommand, usage="[options...]")
    async def purge_custom(self, ctx: commands.Context, **flags):
        """An advanced purge command that allows for granular control over filtering messages for deletion.

        This uses a powerful "command-line" interface.
        Quotation marks must be used if a value has spaces.
        **All options are optional.**

        By default, messages that meet ALL of the conditions given are deleted,
        unless `--any` is passed, in which case only if ANY are met.
        If no flags or options are passed, then the previous 10 messages are deleted.

        __The following options are valid **(All options are optional.)**:__

        `--after`: Target any messages after the given message ID.
        `--before`: Target any messages before the given message ID.
        `--contains`: Target any messages that contain the given substring(s).
        `--endswith` or `--ends`: Target any messages that end with the given substring(s).
        `--search`: The number of messages to search for and delete. (Default: 10; Max: 2000)
        `--startswith` or `--starts`: Target any messages that start with the given substring(s).
        `--users` or `--user`: Target any messages sent by the given user(s).

        __The remaining options do not take any arguments and are simply just flags:__

        `--bot`: Target any messages sent by a bot user.
        `--embeds`: Target any messages that contain embeds.
        `--emoji`: Target any messages that contain a custom emoji.
        `--files` or `--attachments`: Target any messages that contain file attachments.
        `--any`: Targeted messages are only deleted if ANY conditions given are met.
        `--not`: Ignore targeted messages and instead delete messages that do NOT meet the conditions given.

        (Permissions Needed: Manage Messages)
        (Bot Needs: Manage Messages)

        EXAMPLE: purge custom --search 100 --emoji --users @HitchedSyringe#0598
        """
        contains = flags["contains"]
        ends = flags["endswith"]
        starts = flags["startswith"]
        users = flags["users"]
        bots = flags["bot"]
        embeds = flags["embeds"]
        emoji = flags["emoji"]
        files = flags["files"]

        checks = []

        if contains:
            checks.append(lambda m: any(sub in m.content for sub in contains))

        if ends:
            checks.append(lambda m: m.content.endswith(ends))

        if starts:
            checks.append(lambda m: m.content.startswith(starts))

        if users is not None:
            checks.append(lambda m: m.author in users)

        if bots is not None:
            checks.append(bots)

        if embeds is not None:
            checks.append(embeds)

        if emoji is not None:
            checks.append(emoji)

        if files is not None:
            checks.append(files)

        if checks:
            operation = any if flags["any"] else all

            def check(m):
                result = operation(check(m) for check in checks)
                if flags["not"]:
                    return not result
                return result
        else:
            check = lambda m: True

        await self._do_purge_strategy(
            ctx,
            limit=flags["search"],
            check=check,
            before=flags["before"],
            after=flags["after"]
        )


    @purge.command(name="embeds")
    async def purge_embeds(self, ctx: commands.Context, search: int = 10):
        """Deletes messages that contain a rich embed.
        If no search limit is specified, then the previous 10 messages that meet the above criteria are deleted.
        (Permissions Needed: Manage Messages)
        (Bot Needs: Manage Messages)

        EXAMPLE: purge embeds 100
        """
        await self._do_purge_strategy(ctx, limit=search, check=lambda m: m.embeds)


    @purge.command(name="emojis")
    async def purge_emojis(self, ctx: commands.Context, search: int = 10):
        """Deletes messages that contain a custom emoji.
        If no search limit is specified, then the previous 10 messages that meet the above criteria are deleted.
        (Permissions Needed: Manage Messages)
        (Bot Needs: Manage Messages)

        EXAMPLE: purge emojis 100
        """
        await self._do_purge_strategy(
            ctx,
            limit=search,
            check=lambda m: CUSTOM_EMOJI_REGEX.match(m.content) is not None
        )


    @purge.command(name="files", aliases=["attachments"])
    async def purge_files(self, ctx: commands.Context, search: int = 10):
        """Deletes messages that contain an attachment.
        If no search limit is specified, then the previous 10 messages that meet the above criteria are deleted.
        (Permissions Needed: Manage Messages)
        (Bot Needs: Manage Messages)

        EXAMPLE: purge files 100
        """
        await self._do_purge_strategy(ctx, limit=search, check=lambda m: m.attachments)


    @purge.command(name="reactions")
    @checks.has_permissions(manage_messages=True)
    @checks.bot_has_permissions(manage_messages=True, read_message_history=True)
    async def purge_reactions(self, ctx: commands.Context, search: int = 10):
        """Removes all reactions from any messages that have them.
        If no search limit is specified, then reactions are removed from the previous 10 messages.
        (Permissions Needed: Manage Messages)
        (Bot Needs: Manage Messages and Read Message History)

        EXAMPLE: purge reactions 100
        """
        if search <= 0 or search > 2000:
            await ctx.send("Search limit must be greater than 0 and less than 2000.")

        total_reactions = 0
        async for message in ctx.history(limit=search, before=ctx.message).filter(lambda m: m.reactions):
            total_reactions += sum(reaction.count for reaction in message.reactions)
            await message.clear_reactions()

        await ctx.send(f"Removed **{formatting.plural(total_reactions):reaction}**.")


    @purge.command(name="users", aliases=["user"])
    async def purge_users(self, ctx: commands.Context, users: commands.Greedy[discord.User], search: int = 10):
        """Deletes a user or list of users' messages.
        If no search limit is specified, then the previous 10 messages that meet the above criteria are deleted.
        (Permissions Needed: Manage Messages)
        (Bot Needs: Manage Messages)

        EXAMPLE:
        (Ex. 1) purge users HitchedSyringe#0598 100
        (Ex. 2) purge users @HitchedSyringe#0598 140540589329481728 100
        """
        if not users:
            await ctx.send("You must specify at least **1 user** to purge messages for.")
            return

        await self._do_purge_strategy(ctx, limit=search, check=lambda m: m.author in users)


    @commands.command()
    @checks.has_guild_permissions(kick_members=True)
    @checks.bot_has_guild_permissions(ban_members=True)
    async def softban(self, ctx: commands.Context,
                      user: BannableUser, delete_message_days: Optional[int] = 1, *, reason: Reason = None):
        """Bans and then unbans a user, deleting messages from x days ago.
        This allows you to kick a member, while also deleting their messages.
        If the number of days worth of messages to delete from isn't specified,
        then all messages from the user dating back to 1 day are deleted.
        (Permissions Needed: Kick Members)
        (Bot Needs: Ban Members)

        EXAMPLE:
        (Ex. 1) softban HitchedSyringe
        (Ex. 2) softban @HitchedSyringe#0598 3
        (Ex. 3) softban 140540589329481728 5 Spamming
        """
        if delete_message_days <= 0 or delete_message_days > 7:
            await ctx.send("Number of days must be greater than 0 and less than 7.")
            return

        if reason is None:
            reason = f"{ctx.author} (ID: {ctx.author.id}): No reason provided."

        await ctx.guild.ban(user, reason=reason, delete_message_days=delete_message_days)
        await ctx.guild.unban(user, reason=reason)
        await ctx.send("<a:sapphire_ok_hand:618630481986191380>")


    @commands.command()
    @checks.has_guild_permissions(ban_members=True)
    @checks.bot_has_guild_permissions(ban_members=True)
    async def unban(self, ctx: commands.Context, user: BanEntry, *, reason: Reason = None):
        """Unbans a user from the server.
        You can either pass a user's ID or name#discrim. The former is typically the easiest.
        (Permissions Needed: Ban Members)
        (Bot Needs: Ban Members)

        EXAMPLE:
        (Ex. 1) unban HitchedSyringe#0598
        (Ex. 2) unban 140540589329481728
        """
        if reason is None:
            reason = f"{ctx.author} (ID: {ctx.author.id}): No reason provided."

        await ctx.guild.unban(user.user, reason=reason)
        if user.reason is not None:
            await ctx.send(f"Unbanned {user.user} (ID: {user.user.id}), previously banned for:\n>>> {user.reason}")
        else:
            await ctx.send(f"Unbanned {user.user} (ID: {user.user.id})")


def setup(bot):
    bot.add_cog(Moderation())
