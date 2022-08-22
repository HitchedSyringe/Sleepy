"""
Copyright (c) 2018-present HitchedSyringe

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""


from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Callable, Optional, Sequence, Tuple, Union

import discord
from discord.ext import commands
from discord.utils import find
from jishaku.paginators import WrappedPaginator
from typing_extensions import Annotated

from sleepy import checks
from sleepy.menus import PaginatorSource
from sleepy.utils import plural

if TYPE_CHECKING:
    from discord.abc import SnowflakeTime

    from sleepy.bot import Sleepy
    from sleepy.context import Context as SleepyContext, GuildContext


class HierarchyError(commands.BadArgument):
    pass


class BanEntryNotFound(commands.BadArgument):
    pass


class ReasonTooLong(commands.BadArgument):
    pass


def has_higher_role(member: discord.Member, target: discord.Member) -> bool:
    return member.id == member.guild.owner_id or member.top_role > target.top_role


class ActionableMember(commands.Converter[discord.Member]):
    @staticmethod
    async def convert(ctx: GuildContext, argument: str) -> discord.Member:
        member = await commands.MemberConverter().convert(ctx, argument)

        if member in (ctx.author, ctx.me):
            raise HierarchyError("There will be no self-harm or coups on my watch!")

        if not has_higher_role(ctx.me, member):
            raise HierarchyError(
                "I can't perform this action on that user due to role hierarchy."
            )

        if not has_higher_role(ctx.author, member):
            raise HierarchyError(
                "You can't perform this action on that user due to role hierarchy."
            )

        return member


class BanEntryConverter(commands.Converter[discord.BanEntry]):
    @staticmethod
    async def convert(ctx: GuildContext, argument: str) -> discord.BanEntry:
        try:
            return await ctx.guild.fetch_ban(discord.Object(id=argument))
        except discord.NotFound:
            raise BanEntryNotFound("That user isn't banned.") from None
        except ValueError:
            pass

        ban_entry = await find(
            lambda e: str(e.user) == argument, ctx.guild.bans(limit=None)
        )

        if ban_entry is None:
            raise BanEntryNotFound("That user isn't banned.")

        return ban_entry


class BannableUser(commands.Converter[Union[discord.Member, discord.User]]):
    @staticmethod
    async def convert(ctx, argument: str) -> Union[discord.Member, discord.User]:
        try:
            return await ActionableMember.convert(ctx, argument)
        except commands.MemberNotFound:
            pass

        return await commands.UserConverter().convert(ctx, argument)


class Reason(commands.Converter[str]):
    @staticmethod
    async def convert(ctx: SleepyContext, argument: str) -> str:
        tag = f"{ctx.author} (ID: {ctx.author.id}): "

        argument_len = len(argument)
        limit = 512 - len(tag)

        if argument_len > limit:
            raise ReasonTooLong(f"Reason is too long. ({argument_len} > {limit})")

        return tag + argument


def _no_reason(ctx: SleepyContext) -> str:
    return f"{ctx.author} (ID: {ctx.author.id}): No reason provided."


ReasonParameter = commands.parameter(
    converter=Reason, default=_no_reason, displayed_default="<no reason>"
)


class _CleanDaysPsuedoFlag(commands.Converter[int]):

    __RANGE: commands.Range = commands.Range[int, 0, 7]

    async def convert(self, ctx: SleepyContext, argument: str) -> int:
        flag, _, argument = argument.partition("=")

        if flag != "-clean" or not argument:
            raise commands.BadArgument

        return await self.__RANGE.convert(ctx, argument)


class MassbanFlags(commands.FlagConverter):

    reason: str = commands.flag(converter=Reason, default=_no_reason)
    clean_days: commands.Range[int, 0, 7] = commands.flag(name="clean", default=1)

    startswith: Optional[Tuple[str, ...]] = None
    endswith: Optional[Tuple[str, ...]] = None
    contains: Optional[Tuple[str, ...]] = None
    matches: str = commands.flag(
        aliases=("regex",),  # type: ignore
        default=None,
    )

    created: commands.Range[int, 1] = 0
    joined: commands.Range[int, 1] = 0
    joined_before: discord.Member = commands.flag(name="joined-before", default=None)
    joined_after: discord.Member = commands.flag(name="joined-after", default=None)

    has_no_avatar: bool = commands.flag(name="has-no-avatar", default=False)
    has_no_roles: bool = commands.flag(name="has-no-roles", default=False)

    show_users: bool = commands.flag(name="show-users", default=False)


class PurgeFlags(commands.FlagConverter):

    before: Optional[discord.PartialMessage] = None
    after: Optional[discord.PartialMessage] = None

    startswith: Optional[Tuple[str, ...]] = None
    endswith: Optional[Tuple[str, ...]] = None
    contains: Optional[Tuple[str, ...]] = None
    matches: str = commands.flag(
        aliases=("regex",),  # type: ignore
        default=None,
    )

    users: Tuple[discord.User, ...] = commands.flag(
        name="users",
        aliases=("user",),  # type: ignore
        default=None,
    )
    sent_by_bot: bool = commands.flag(name="sent-by-bot", default=False)
    has_embeds: bool = commands.flag(name="has-embeds", default=False)
    has_emojis: bool = commands.flag(name="has-emojis", default=False)
    has_attachments: bool = commands.flag(
        name="has-attachments",
        aliases=("has-files",),  # type: ignore
        default=False,
    )
    has_reactions: bool = commands.flag(name="has-reactions", default=False)

    logical_any: bool = commands.flag(name="any-applies", default=False)
    logical_not: bool = commands.flag(name="invert", default=False)


class Moderation(commands.Cog):
    """Commands having to do with server moderation.

    These obviously cannot be used in Private Messages.
    """

    ICON: str = "\N{SHIELD}"

    # Most of the command checks should have internal
    # guild checks already. This is just a fallback
    # to ensure nothing slips through.
    async def cog_check(self, ctx: SleepyContext) -> bool:
        if ctx.guild is None:
            raise commands.NoPrivateMessage()

        return True

    async def cog_command_error(self, ctx: SleepyContext, error: Exception) -> None:
        if isinstance(error, (commands.UserNotFound, commands.MemberNotFound)):
            await ctx.send("That user wasn't found.")
            ctx._already_handled_error = True
        elif isinstance(error, (commands.ChannelNotFound, commands.MessageNotFound)):
            await ctx.send("That message ID, link, or URL was invalid.")
            ctx._already_handled_error = True
        elif isinstance(error, (BanEntryNotFound, HierarchyError, ReasonTooLong)):
            await ctx.send(error)  # type: ignore
            ctx._already_handled_error = True

    @staticmethod
    async def do_purge(
        ctx: GuildContext,
        *,
        limit: int,
        check: Callable[[discord.Message], bool],
        before: Optional[SnowflakeTime] = None,
        after: Optional[SnowflakeTime] = None,
    ) -> None:
        if before is None:
            before = ctx.message

        try:
            deleted = await ctx.channel.purge(
                limit=limit, check=check, before=before, after=after
            )
        except discord.HTTPException:
            await ctx.send("Deleting the messages failed.\nTry again later?")
            return

        if deleted:
            await ctx.send(
                f"Deleted **{len(deleted)}/{limit}** messages.", delete_after=10
            )
        else:
            await ctx.send("No messages were deleted.")

    @staticmethod
    async def do_multiban(
        ctx: GuildContext,
        users: Sequence[Union[discord.Member, discord.User]],
        *,
        reason: str,
        clean_days: int,
    ) -> None:
        total = len(users)
        confirmed = await ctx.prompt(f"Shall I ban **{plural(total):user}**?")

        if not confirmed:
            await ctx.send("Aborted.")
            return

        await ctx.typing()

        failed = 0

        for user in users:
            try:
                await ctx.guild.ban(user, reason=reason, delete_message_days=clean_days)
            except discord.HTTPException:
                failed += 1

        await ctx.send(f"Banned **{total - failed}/{total} users**.")

    @commands.command(
        aliases=("hackban", "multiban"), usage="<users...> [-clean=1] [reason]"
    )
    @checks.has_guild_permissions(ban_members=True)
    @commands.bot_has_guild_permissions(ban_members=True)
    async def ban(
        self,
        ctx: GuildContext,
        users: Annotated[
            Sequence[Union[discord.Member, discord.User]], commands.Greedy[BannableUser]
        ],
        clean_days: Annotated[int, Optional[_CleanDaysPsuedoFlag]] = 1,
        *,
        reason: str = ReasonParameter,
    ) -> None:
        """Bans one or more users, deleting *x* days' worth of their messages.

        This command works on all users, regardless of whether they're
        a member of the server. Members with a higher role than you or
        myself are automatically excluded and ignored.

        User can either be a name, ID, or mention.

        Number of days' worth of messages to delete must be between 0
        and 7, inclusive. By default, this deletes 1 day's worth of
        the specified users' messages.

        (Permissions Needed: Ban Members)
        (Bot Needs: Ban Members)

        **EXAMPLES:**
        ```bnf
        <1> ban HitchedSyringe
        <2> ban @HitchedSyringe#0598 -clean=3
        <3> ban 140540589329481728 -clean=5 Spamming
        ```
        """
        user_count = len(users)

        if user_count == 0:
            await ctx.send("You must specify at least one user to ban.")
        elif user_count == 1:
            await ctx.guild.ban(users[0], reason=reason, delete_message_days=clean_days)
            await ctx.send("<a:sapphire_ok_hand:786093988679516160>")
        else:
            await self.do_multiban(ctx, users, reason=reason, clean_days=clean_days)

    @commands.command()
    @checks.has_permissions(manage_messages=True)
    async def cleanup(
        self, ctx: GuildContext, amount: commands.Range[int, 1, 2000] = 10
    ) -> None:
        """Deletes my messages and (if possible) any messages that look like they invoked me.

        Up to 2000 messages can be searched for. If no amount is specified,
        then the previous 10 messages that meet the above criteria will be
        deleted.

        (Permissions Needed: Manage Messages)
        (Bot Optionally Needs: Manage Messages)

        **EXAMPLE:**
        ```
        cleanup 100
        ```
        """
        if ctx.bot_permissions.manage_messages:
            # Shouts out to startswith for only taking tuples,
            # even though they're literally the same in almost
            # every manner other than mutability.
            prefixes = tuple(await ctx.bot.get_prefix(ctx.message))
            check = lambda m: m.author == ctx.me or m.content.startswith(prefixes)
        else:
            check = lambda m: m.author == ctx.me

        await self.do_purge(ctx, limit=amount, check=check)

    @commands.command()
    @checks.has_guild_permissions(kick_members=True)
    @commands.bot_has_guild_permissions(kick_members=True)
    async def kick(
        self,
        ctx: SleepyContext,
        member: Annotated[discord.Member, ActionableMember],
        *,
        reason: str = ReasonParameter,
    ) -> None:
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
        await member.kick(reason=reason)
        await ctx.send("<a:sapphire_ok_hand:786093988679516160>")

    @commands.command(usage="[options...]")
    @checks.has_guild_permissions(ban_members=True)
    @commands.bot_has_guild_permissions(ban_members=True)
    async def massban(self, ctx: GuildContext, *, options: MassbanFlags) -> None:
        """Bans multiple members from the server based on the given conditions.

        Members will only be banned **if and only if** ALL of the
        given conditions are met. Members with a higher role than
        you or myself are automatically excluded and ignored.

        This command's interface is similar to Discord's slash commands.
        Values with spaces must be surrounded by quotation marks.

        Options can be given in any order and, unless otherwise stated,
        are assumed to be optional.

        __**DANGER: If no conditions are given, then ALL members present
        on the server will be banned.**__

        The following options are valid:

        `reason: <reason>`
        > The reason for the ban.
        `clean: <integer>`
        > The number of days worth of a banned user's messages to delete.
        > Must be between 1 and 7, inclusive.
        > Defaults to `1`.
        `startswith: <prefixes...>`
        > Only target members whose usernames start with the given prefix(es).
        > Prefixes are case-sensitive.
        `contains: <substrings...>`
        > Only target members whose usernames contain the given substring(s).
        > Substrings are case-sensitive.
        `endswith: <suffixes...>`
        > Only target members whose usernames end with the given suffix(es).
        > Suffixes are case-sensitive.
        `[matches|regex]: <expression>`
        > Only target members whose usernames match with the given regex.
        `created: <integer>`
        > Only target members whose accounts were created less than specified
        > minutes ago.
        `joined: <integer>`
        > Only target members who joined less than specified minutes ago.
        `joined-before: <member>`
        > Only target members who joined before the given member.
        > Member can either be a name, ID, or mention.
        `joined-after: <member>`
        > Only target members who joined after the given member.
        > Member can either be a name, ID, or mention.
        `has-no-avatar: <true|false>`
        > If `true`, only target members that have a default avatar.
        `has-no-roles: <true|false>`
        > If `true`, only target members that do not have a role.
        `show-users: <true|false>`
        > If `true`, only show members that meet the banning criteria.

        (Permissions Needed: Ban Members)
        (Bot Needs: Ban Members)
        """
        checks = [lambda m: has_higher_role(ctx.author, m)]

        if options.has_no_avatar:
            checks.append(lambda m: m.avatar is None)

        if options.has_no_roles:
            checks.append(lambda m: len(m.roles) <= 1)

        if options.contains:
            checks.append(lambda m: any(sub in m.name for sub in options.contains))  # type: ignore

        if options.endswith:
            checks.append(lambda m: m.name.endswith(options.endswith))

        if options.startswith:
            checks.append(lambda m: m.name.startswith(options.startswith))

        if options.matches is not None:
            try:
                regex = re.compile(options.matches)
            except re.error as exc:
                await ctx.send(f"Invalid match regex: {exc}")
                return
            else:
                checks.append(lambda m: regex.match(m.name) is not None)

        now = datetime.now(timezone.utc)

        if options.created > 0:
            checks.append(
                lambda m: m.created_at > now - timedelta(minutes=options.created)
            )

        if options.joined > 0:
            checks.append(
                lambda m: m.joined_at is not None
                and m.joined_at > now - timedelta(minutes=options.joined)
            )

        if options.joined_before is not None:
            b_joined_at = options.joined_before.joined_at

            checks.append(
                lambda m: m.joined_at is not None
                and b_joined_at is not None
                and m.joined_at < b_joined_at
            )

        if options.joined_after is not None:
            a_joined_at = options.joined_after.joined_at

            checks.append(
                lambda m: m.joined_at is not None
                and a_joined_at is not None
                and m.joined_at > a_joined_at
            )

        if ctx.guild.chunked:
            members = ctx.guild.members
        else:
            async with ctx.typing():
                members = await ctx.guild.chunk()

        members = [m for m in members if all(c(m) for c in checks)]

        if not members:
            await ctx.send("No members met the criteria specified.")
            return

        if options.show_users:
            paginator = WrappedPaginator(prefix="```yaml", max_size=1000)
            members.sort(key=lambda m: m.joined_at or now)

            for member in members:
                paginator.add_line(
                    f"{member} (ID: {member.id})"
                    f"\n\tJoined: {member.joined_at}"
                    f"\n\tCreated: {member.created_at}"
                )

            await ctx.paginate(PaginatorSource(paginator))
            return

        await self.do_multiban(
            ctx,
            members,
            reason=options.reason,
            clean_days=options.clean_days,
        )

    @commands.group(
        aliases=("remove",), usage="[amount=10] [options...]", invoke_without_command=True
    )
    @checks.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    async def purge(
        self,
        ctx: GuildContext,
        amount: Annotated[int, Optional[commands.Range[int, 1, 2000]]] = 10,
        *,
        options: PurgeFlags,
    ) -> None:
        """Deletes a specified amount of messages.

        Up to 2000 messages can be searched for. If no amount is specified,
        then this will search for and remove the previous 10 messages that
        meet the given criteria.

        This command's interface is similar to Discord's slash commands.
        Values with spaces must be surrounded by quotation marks.

        Options can be given in any order and, unless otherwise stated,
        are assumed to be optional.

        By default, messages that meet *ALL* of the given conditions are
        deleted unless `any-applies: true` is passed, in which case only
        if ANY of the given conditions are met.

        The following options are valid:

        `before: <message>`
        > Only target messages sent before the given message.
        > Message can either be a link or ID.
        `after: <message>`
        > Only target messages sent after the given message.
        > Message can either be a link or ID.
        `startswith: <prefixes...>`
        > Only target messages that start with the given prefix(es).
        > Prefixes are case-sensitive.
        `contains: <substrings...>`
        > Only target messages that contain the given substring(s).
        > Substrings are case-sensitive.
        `endswith: <suffixes...>`
        > Only target messages that end with the given suffix(es).
        > Suffixes are case-sensitive.
        `[matches|regex]: <expression>`
        > Only target messages whose content matches the given regex.
        `[users|user]: <users...>`
        > Only Target messages sent by the given user(s).
        > Users can either be a name, ID, or mention.
        `sent-by-bot: <true|false>`
        > If `true`, only target messages sent by bots.
        `has-embeds: <true|false>`
        > If `true`, only target messages that contain embeds.
        `has-emojis: <true|false>`
        > If `true`, only target messages that contain custom emojis.
        `[has-files|has-attachments]: <true|false>`
        > If `true`, only target messages that contain file attachments.
        `has-reactions: <true|false>`
        > If `true`, only target messages that have reactions.
        `any-applies: <true|false>`
        > If `true`, delete messages that meet ANY of the given conditions.
        `invert: <true|false>`
        > If `true`, delete messages that do NOT meet the given conditions.

        (Permissions Needed: Manage Messages)
        (Bot Needs: Manage Messages)
        """
        checks = []

        if options.contains is not None:
            # For whatever reason, the typechecker still thinks this is None here.
            checks.append(lambda m: any(s in m.content for s in options.contains))  # type: ignore

        if options.endswith is not None:
            checks.append(lambda m: m.content.endswith(options.endswith))

        if options.startswith is not None:
            checks.append(lambda m: m.content.startswith(options.startswith))

        if options.users is not None:
            checks.append(lambda m: m.author in options.users)

        if options.sent_by_bot:
            checks.append(lambda m: m.author.bot)

        if options.has_embeds:
            checks.append(lambda m: bool(m.embeds))

        if options.has_emojis:
            emoji_regex = re.compile(r"<a?:[A-Za-z0-9_]{1,32}:[0-9]{15,20}>")
            checks.append(lambda m: emoji_regex.search(m.content) is not None)

        if options.has_attachments:
            checks.append(lambda m: bool(m.attachments))

        if options.has_reactions:
            checks.append(lambda m: bool(m.reactions))

        if options.matches is not None:
            try:
                regex = re.compile(options.matches)
            except re.error as exc:
                await ctx.send(f"Invalid match regex: {exc}")
                return
            else:
                checks.append(lambda m: regex.match(m.content))

        if checks:

            def check(m: discord.Message) -> bool:
                func = any if options.logical_any else all
                result = func(c(m) for c in checks)

                return not result if options.logical_not else result

        else:
            check = lambda _: True  # type: ignore

        await self.do_purge(
            ctx,
            limit=amount,
            check=check,
            before=options.before,
            after=options.after,
        )

    @purge.command(name="reactions")
    @checks.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True, read_message_history=True)
    async def purge_reactions(
        self, ctx: SleepyContext, amount: commands.Range[int, 0, 2000] = 10
    ) -> None:
        """Removes all reactions from a specified number of messages that have them.

        Up to 2000 messages can be searched for. If no amount is specified,
        then this will search for and remove reactions from the previous 10
        messages.

        (Permissions Needed: Manage Messages)
        (Bot Needs: Manage Messages and Read Message History)

        **EXAMPLE:**
        ```
        purge reactions 100
        ```
        """
        reactions = 0

        async for message in ctx.history(limit=amount, before=ctx.message):
            if message.reactions:
                reactions += sum(r.count for r in message.reactions)
                await message.clear_reactions()

        await ctx.send(f"Removed **{plural(reactions, ',d'):reaction}**.")

    @commands.command(usage="<member> [-clean=1] [reason]")
    @checks.has_guild_permissions(kick_members=True)
    @commands.bot_has_guild_permissions(ban_members=True)
    async def softban(
        self,
        ctx: GuildContext,
        user: Annotated[Union[discord.Member, discord.User], BannableUser],
        clean_days: Annotated[int, Optional[_CleanDaysPsuedoFlag]] = 1,
        *,
        reason: str = ReasonParameter,
    ) -> None:
        """Softbans a user.

        Softbanning is the act of banning and then instantly
        unbanning a user, essentially allowing you to kick a
        user while also deleting their messages.

        This command works on all users, regardless of whether
        they're a member of the server.

        User can either be a name, ID, or mention.

        Number of days' worth of messages to delete must be
        between 0 and 7, inclusive. By default, this deletes
        1 day's worth of the specified users' messages.

        (Permissions Needed: Kick Members)
        (Bot Needs: Ban Members)

        **EXAMPLES:**
        ```bnf
        <1> softban HitchedSyringe
        <2> softban @HitchedSyringe#0598 -clean=3
        <3> softban 140540589329481728 -clean=5 Spamming
        ```
        """
        await ctx.guild.ban(user, reason=reason, delete_message_days=clean_days)
        await ctx.guild.unban(user, reason=reason)

        await ctx.send("<a:sapphire_ok_hand:786093988679516160>")

    @commands.command(aliases=("pardon",))
    @checks.has_guild_permissions(ban_members=True)
    @commands.bot_has_guild_permissions(ban_members=True)
    async def unban(
        self,
        ctx: GuildContext,
        user: Annotated[discord.BanEntry, BanEntryConverter],
        *,
        reason: str = ReasonParameter,
    ) -> None:
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
        await ctx.guild.unban(user.user, reason=reason)

        msg = f"Unbanned {user.user} (ID: {user.user.id})."

        if user.reason:
            msg += f"\n>>> **Previous Ban Reason:**\n{user.reason}"

        await ctx.send(msg)


async def setup(bot: Sleepy) -> None:
    await bot.add_cog(Moderation())
