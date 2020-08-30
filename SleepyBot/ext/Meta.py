"""
© Copyright 2018-2020 HitchedSyringe, All Rights Reserved.

Redistributing, using or owning a copy of this software without explicit permissions
is against these licensing terms, your license(s) to this software can be revoked at
any time without explicit notice beforehand and at the time of revocation.
Your license is non-transferrable, the terms of this license only permit you to do the
following; Create pull requests and make modifications to this repository.

"""


import asyncio
import time
from collections import Counter
from datetime import datetime

import discord
from discord import Embed
from discord.ext import commands, flags, menus
from typing import Optional

from SleepyBot.utils import checks, converters, formatting, reaction_menus


_STATUS_EMOJI = {
    discord.Status.online: "<:online:713579666031509624>",
    discord.Status.offline: "<:offline:713579699351060612>",
    discord.Status.dnd: "<:dnd:713579761129095278>",
    discord.Status.idle: "<:idle:713579726026965052>",
}


# We're using :class:`menus.GroupByPageSource` as the primary source for the
# help command in order to ensure compatibility with :meth`HelpCommand.show_bot_help`.
# Although :class:`menus.ListPageSource` would work as well, there's a bit more overhead
# to it than this one, so essentially, we're just using the lesser of two evils.
class _HelpSource(menus.GroupByPageSource):
    """A special source used exclusively by the help paginator.

    This class is a subclass of :class:`menus.GroupByPageSource` and as a result,
    anything you can do with :class:`menus.GroupByPageSource`, you can also do with this page source.
    """

    def _apply_commands_formatting(self, embed, menu, commands):
        if self.is_paginating():
            embed.set_footer(text=f"Page {menu.current_page + 1}/{self.get_max_pages()}")

        cmds = sorted(commands, key=lambda c: c.name)
        for cmd in cmds:
            if isinstance(cmd, flags.FlagCommand):
                signature = cmd.old_signature
            else:
                signature = cmd.signature

            embed.add_field(
                name=f"**{cmd.qualified_name} {signature}**",
                value=cmd.short_doc or "No help given.",
                inline=False
            )

        return embed


    def format_group_page(self, menu, entry):
        embed = Embed(colour=0x2F3136)
        group = menu.bot.get_command(entry.key)

        self._apply_common_command_formatting(embed, group)

        return self._apply_commands_formatting(embed, menu, entry.items)


    def format_page(self, menu, entry):
        embed = Embed(title=f"{entry.key} Commands", colour=0x2F3136)

        cog = menu.bot.get_cog(entry.key)
        embed.description = (cog and cog.description) or None

        return self._apply_commands_formatting(embed, menu, entry.items)


class _HelpPaginatorInterface(reaction_menus.PaginatorInterface):
    """Paginator used exclusively by the help command.
    This is essentially the same as :class:`reaction_menus.PaginatorInterface` but with the only difference being
    the addition of the ``show_bot_help`` button.
    """

    @menus.button("\N{BLACK QUESTION MARK ORNAMENT}", position=menus.Last(2), lock=False)
    async def show_bot_help(self, payload):
        """Shows my usage help."""
        description = (
            "Welcome to the usage help page!",
            "I am designed to be easy to use and (mostly) user friendly.",
            "Understanding my signature is very simple:",
        )
        embed = Embed(title="Usage Help", description="\n".join(description), colour=0x2F3136)
        embed.set_footer(text=f"We were on page {self.current_page + 1} before this message.")

        syntax_list = (
            ("**<argument>**", "This means the argument is **__required__**"),
            ("**[argument]**", "This means the argument is **__optional__**"),
            ("**[A|B]**", "This means the argument can be **__either A or B__**"),
            ("**[argument...]**", "This means you can enter multiple arguments."),
        )

        for name, value in syntax_list:
            embed.add_field(name=name, value=value, inline=False)

        embed.add_field(
            name="Now that you understand the basics,",
            value="please note that __**you do not include the brackets!**__.",
            inline=False
        )

        await self.message.edit(content=None, embed=embed)

        async def _back_to_current_page():
            await asyncio.sleep(45)
            await self.show_current_page()

        self._task = self.bot.loop.create_task(_back_to_current_page())


class SleepyHelpCommand(commands.HelpCommand):
    """The help command implementation for the bot.
    This subclasses :class:`commands.HelpCommand`.
    """

    async def _paginate(self, source):
        """Starts the help pagination session.
        For internal use only.
        """
        menu = _HelpPaginatorInterface(source)
        await menu.start(self.context)


    def _apply_common_command_formatting(self, embed, command) -> None:
        """Applies the command formatting to the embed.
        For internal use only.
        """
        embed.title = self.get_command_signature(command)

        if command.description:
            embed.description = f"{command.description}\n\n{command.help}"
        else:
            embed.description = command.help or "No help given."


    def command_not_found(self, string):
        return "That command wasn't found."


    def subcommand_not_found(self, command, string):
        if isinstance(command, commands.Group) and len(command.all_commands) > 0:
            return "That subcommand wasn't found."
        return "That command doesn't have any subcommands."


    def get_command_signature(self, command):
        if command.aliases:
            _joined_aliases = "|".join(command.aliases)
            command_format = f"[{command.name}|{_joined_aliases}]"
        else:
            command_format = command.name

        parent = command.full_parent_name
        if parent:
            command_format = f"{parent} {command_format}"

        if isinstance(command, flags.FlagCommand):
            # It's probably better to list what each flag actually does in the extended help string.
            signature = command.old_signature
        else:
            signature = command.signature

        return f"{command_format} {signature}"


    async def send_bot_help(self, mapping):
        key = lambda c: c.cog_name or "\u200bNo Category"
        entries = await self.filter_commands(self.context.bot.commands, sort=True)

        source = _HelpSource(entries, key=key, per_page=6)
        await self._paginate(source)


    async def send_cog_help(self, cog):
        key = lambda c: c.cog_name
        entries = await self.filter_commands(cog.get_commands(), sort=True, key=key)

        # Handle case where no commands can be shown under that extension.
        if not entries:
            embed = Embed(
                title=f"{cog.qualified_name} Commands",
                description=(cog and cog.description) or None,
                colour=0x2F3136
            )
            await self.context.send(embed=embed)
            return

        source = _HelpSource(entries, key=key, per_page=6)
        await self._paginate(source)


    async def send_command_help(self, command):
        # Singular commands don't need pagination.
        embed = Embed(colour=0x2F3136)
        self._apply_common_command_formatting(embed, command)
        await self.context.send(embed=embed)


    async def send_group_help(self, group):
        subcommands = group.commands
        if not subcommands:
            await self.send_command_help(group)
            return

        entries = await self.filter_commands(subcommands, sort=True)

        source = _HelpSource(entries, key=lambda c: c.full_parent_name, per_page=6)
        source.format_page = source.format_group_page
        # I'm honestly not gonna stress over this.
        # This command is the only command that uses this source anyway. Who cares.
        source._apply_common_command_formatting = self._apply_common_command_formatting
        await self._paginate(source)


class DefaultMemberMocker:
    """A class that mocks a member with no roles.
    This is useful for finding which channels are "secret."
    This class is only meant to be used in :meth:`abc.GuildChannel.permissions_for`.

    Attributes
    ----------
    id: :class:`int`
        This is always ``0``.
    """
    id = 0

    def __init__(self, guild):
        # Unfortunately, mocking default members isn't as easy in 1.4 due to changes to permissions_for.
        # We have to actually build a SnowflakeList ourself in order to properly mock.
        self._roles = discord.utils.SnowflakeList((guild.id,))


class Meta(commands.Cog):
    """Commands relating to me or Discord itself."""

    def __init__(self, bot):
        self.bot = bot
        self._old_help_command = bot.help_command

        bot.help_command = SleepyHelpCommand(
            command_attrs={
                "cooldown": commands.Cooldown(1, 3, commands.BucketType.user),
                "checks": [
                    checks.bot_has_permissions(embed_links=True, add_reactions=True, read_message_history=True).predicate,
                ],
                "help": "Shows help about me, a command, or a category.",
            }
        )
        bot.help_command.cog = self

        # XXX Only used in source command, which isn't available yet.
        # # Load the associated links.
        # self._links = self.bot.config["Discord Bot Config"].getjson("links")


    def cog_unload(self):
        self.bot.help_command = self._old_help_command


    @staticmethod
    def _format_permissions(member: discord.Member, channel: discord.abc.GuildChannel) -> Embed:
        """Formats a user's channel permissions in an easy to see embed.
        For internal use only.

        Parameters
        ----------
        member: :class:`discord.Member`
            The member to get permissions for.
        channel: :class:`discord.abc.GuildChannel`
            A guild channel to get the permissions from.
            This can be a text channel, voice channel or category channel.

        Returns
        -------
        :class:`discord.Embed`
            The formatted permissions.
        """
        embed = Embed(colour=0x2F3136)
        embed.set_author(
            name=f"Permissions for {member} (ID: {member.id}) in {channel.name} (ID: {channel.id})",
            icon_url=member.avatar_url
        )

        allowed_perms = []
        denied_perms = []
        for permission, value in channel.permissions_for(member):
            # Make the permission name human-readable.
            permission_name = permission.replace('_', ' ').replace('guild', 'server').title()
            if value:
                allowed_perms.append(permission_name)
            else:
                denied_perms.append(permission_name)

        embed.add_field(name="Allowed", value="\n".join(sorted(allowed_perms)) or None)
        embed.add_field(name="Denied", value="\n".join(sorted(denied_perms)) or None)

        return embed


    @commands.command()
    @checks.bot_has_permissions(embed_links=True)
    async def avatar(self, ctx: commands.Context, *, user: discord.User = None):
        """Gets an enlarged version of a user's avatar. (if possible)
        If no user is given, then your own avatar is returned instead.
        (Bot Needs: Embed Links)

        EXAMPLE:
        (Ex. 1) avatar @HitchedSyringe#0598
        (Ex. 2) avatar 140540589329481728
        (Ex. 3) avatar HitchedSyringe
        """
        if user is None:
            user = ctx.author

        url = user.avatar_url_as(static_format="png")

        embed = Embed(colour=0x2F3136, description=f"**[Link to Avatar]({url})**")
        embed.set_author(name=str(user))
        embed.set_image(url=url)
        await ctx.send(embed=embed)


    @commands.command(aliases=["feedback", "suggest", "complain"])
    @commands.cooldown(rate=1, per=60, type=commands.BucketType.user)
    async def contact(self, ctx: commands.Context, *, content: str):
        """Directly contacts my owner(s).
        This is a quick and easy method to request features or bug fixes without having to be in my server.

        If possible, I will try to communicate the status of your request via private messages.
        This command does not send any Discord file attachments to the owner(s).
        You can only send one message to my owner(s) per minute.

        EXAMPLE:
        (Ex. 1) contact Found a bug, here's info.
        (Ex. 2) contact I have a suggestion for the betterment of the bot!
        """
        embed = Embed(title="Message", description=content, colour=0x2F3136, timestamp=ctx.message.created_at)
        embed.set_author(name=f"{ctx.author} (ID: {ctx.author.id})", icon_url=ctx.author.avatar_url)

        guild_info = f"{ctx.guild} (ID: {ctx.guild.id})" if ctx.guild is not None else "None (Private Messages)"
        embed.add_field(
            name="**Sent From**",
            value=f"**Guild:** {guild_info}\n**Channel:** {ctx.channel} (ID: {ctx.channel.id})"
        )

        # TODO: Add ability to send attachments whenever there's a cleaner way to implement it.

        try:
            await ctx.bot.webhook.send(embed=embed)
        except discord.HTTPException:
            await ctx.send("An error occurred while sending your message.\nTry again later?")
        else:
            await ctx.send("Your message was successfully sent.")


    @commands.command()
    async def invite(self, ctx: commands.Context):
        """Gives you the invite link to join me to your server."""
        await ctx.send(f"<{discord.utils.oauth_url(ctx.bot.user.id, discord.Permissions(388166))}>")


    # The easter egg here is a rant on why ping commands absolutely suck mad pp :^)
    # Highly doubt people would really do "help ping" since the command is pretty straight forward and overused.
    @commands.command()
    async def ping(self, ctx: commands.Context):
        """Pong!

        Not all bots need a ping command. Ping commands aren't special, nor are they a bot selling point.
        They're simply just a vague indicator of whether or not Discord is dying or how shite your internet is.
        Just check <https://status.discord.com> for the former and just use a speedtester for the latter.
        Both solutions provide better detail on your issue than a dumb Discord bot made by some rando on the internet.
        If you need to check if your bot is alive, consider implementing some kind of hello command.
        Ping commands only pander to the lazy users who can't be bothered to click off of Discord for any reason.
        Discord isn't your swiss army knife.

        Yes, I just ranted about how pointless ping commands are in a working ping command helpstring.
        Does it matter? Are you any more educated about how pointless this command really is?
        Actually, you probably couldn't care less about what I just said. You just skimmed this whole thing.
        You only care about what this has to say about Discord's lifesupport status or your 7.2 mbps internet.
        As for me, I'm no better than any of you.

        Keep enjoying your little ping pong commands, while I continue to do what I want to do.
        """
        # await ctx.send("Not all bots need a ping command.")
        typing_start = time.perf_counter()
        await ctx.trigger_typing()
        typing_diff = (time.perf_counter() - typing_start) * 1000

        await ctx.send(
            "\N{TABLE TENNIS PADDLE AND BALL} **Pong!**\n"
            f"```ldif\nWebsocket: {ctx.bot.latency * 1000:.2f} ms\nTyping: {typing_diff:.2f} ms\n```"
        )


    @commands.command(aliases=["perms"])
    @commands.guild_only()
    @checks.bot_has_permissions(embed_links=True)
    async def permissions(self, ctx: commands.Context,
                          user: Optional[discord.Member], channel: converters.GuildChannelConverter = None):
        """Shows a user's permissions optionally in another channel.
        If no user is given, then your own permissions are returned instead.
        If no channel is given, then the permissions in the current channel are returned instead.

        EXAMPLE:
        (Ex. 1) permissions HitchedSyringe
        (Ex. 2) permissions @HitchedSyringe#0598
        (Ex. 3) permissions 140540589329481728 #general
        """
        if user is None:
            user = ctx.author

        if channel is None:
            channel = ctx.channel

        await ctx.send(embed=self._format_permissions(user, channel))


    @commands.command(aliases=["debugperms"], hidden=True)
    @commands.is_owner()
    @checks.bot_has_permissions(embed_links=True)
    async def debugpermissions(self, ctx: commands.Context, channel_id: int, user_id: int = None):
        """Shows a channel's resolved permissions as an optional user. (Owner only)
        If no user is given, then my permissions in the given channel are returned instead.
        """
        channel = ctx.bot.get_channel(channel_id)
        if channel is None:
            await ctx.send("Invalid channel ID.")
            return

        if user_id is None:
            user = channel.guild.me
        else:
            user = channel.guild.get_member(user_id)
            if user is None:
                await ctx.send("Invalid user ID.")
                return

        await ctx.send(embed=self._format_permissions(user, channel))


    @commands.command()
    async def prefixes(self, ctx: commands.Context):
        """Shows my command prefixes."""
        prefixes = await ctx.bot.get_prefix(ctx.message)
        del prefixes[0]  # Remove the extra mention. This is to prevent confusion from seeing the mention appear twice.

        show_prefixes = "\n".join(f"{index}. {prefix}" for index, prefix in enumerate(prefixes, 1))
        await ctx.send(f"**Prefixes**\n>>> {show_prefixes}")


    @commands.command(aliases=["guildinfo"])
    @commands.guild_only()
    @checks.bot_has_permissions(embed_links=True)
    async def serverinfo(self, ctx: commands.Context, *, guild_id: int = None):
        """Shows information about the server.
        Optionally, a server ID can be entered in order to get information about a specific server. (Owner Only)
        (Bot Needs: Embed Links)
        """
        # We only care about guild_id if we're the owner.
        if guild_id is not None and ctx.author.id in ctx.bot.owner_ids:
            guild = ctx.bot.get_guild(guild_id)
            if guild is None:
                await ctx.send("Invalid server ID.")
                return
        else:
            guild = ctx.guild

        embed = Embed(colour=0x2F3136, description=f"**[Link to Icon]({guild.icon_url})**\n")
        embed.set_author(name=guild.name)
        embed.set_thumbnail(url=guild.icon_url_as(static_format="png"))

        if guild.banner is not None:
            embed.description += f"**[Link to Banner]({guild.banner})**\n"
            embed.set_image(url=guild.banner)

        created_ago = formatting.parse_duration(datetime.now() - guild.created_at, brief=True)
        # Humanize features list.
        guild_features = ", ".join(feature.title().replace("_", " ") for feature in guild.features) or None

        mock_member = DefaultMemberMocker(ctx.guild)
        secret = Counter()
        totals = Counter()
        for channel in guild.channels:
            channel_type = type(channel)
            totals[channel_type] += 1
            perms = channel.permissions_for(mock_member)
            # Channel is probably private if we can't read or connect.
            if not (perms.read_messages or perms.connect):
                secret[channel_type] += 1

        description = (
            f"**Owner:** {guild.owner}",
            f"**ID:** {guild.id}",
            f"**Region:** {guild.region}",
            f"**Verification Level:** {guild.verification_level}",
            (
                f"**Channels:** <:text_channel:587389191550271488> {totals[discord.TextChannel]} "
                f"(<:locked_text_channel:587389191525105736> {secret[discord.TextChannel]}) | "
                f"<:voice_channel:587389191524974592> {totals[discord.VoiceChannel]} "
                f"(<:locked_voice_channel:587389191554334739> {secret[discord.VoiceChannel]})"
            ),
            # It's confusing to show a float upload limit to a user, so let's just hide it.
            f"**Upload Limit:** {guild.filesize_limit / 1e6:.0f} MB",
            f"**Created:** {created_ago} ago ({guild.created_at:%a, %b %d, %Y @ %#I:%M %p} UTC)",
            f"**Features:** {guild_features}",
            f"**Shard ID:** {guild.shard_id}",
        )

        embed.description += "\n".join(f"<:arrow:713872522608902205> {entry}" for entry in description)

        # Find the bots, mods (manage guild) and admins (administrator) on the server.
        mods = 0
        admins = 0
        bots = 0
        for member in guild.members:
            if member.bot:
                bots += 1
            # Go ahead and include bots as admins or mods (if applicable).
            perms = member.guild_permissions
            if perms.administrator:
                admins += 1
            elif perms.manage_guild:
                mods += 1

        member_info = (
            f"**Mods:** {mods:,d}",
            f"**Admins:** {admins:,d}",
            f"**Bots:** {bots:,d}",
            f"**Server Boosters:** {len(guild.premium_subscribers):,d}",
        )
        embed.add_field(
            name=f"**Members [{guild.member_count:,d}]**",
            value="\n".join(f"<:arrow:713872522608902205> {entry}" for entry in member_info),
            inline=False
        )

        guild_roles = guild.roles[1:]  # exclude @everyone.
        if guild_roles:
            # We have to reverse the role order so the highest role appears first.
            roles = " ".join(role.mention for role in reversed(guild_roles))
            embed.add_field(
                name=f"**Roles [{len(guild_roles)}]**",
                value=roles if len(roles) < 1024 else "Too many roles to show.",
                inline=False
            )

        if guild.emojis:
            emoji_list = "".join(map(str, guild.emojis))
            embed.add_field(
                name=f"**Emojis [{len(guild.emojis)} / {guild.emoji_limit}]**",
                value=emoji_list if len(emoji_list) < 1024 else "Too many emojis to show.",
                inline=False
            )

        # Create the shorthands.
        tier = guild.premium_tier
        boosts = guild.premium_subscription_count

        boost_progress = formatting.progress_bar(30, 2, boosts)

        if tier == 3:
            next_level = "Maximum server boost tier achieved!"
        else:
            # Index is tier, value is boosts needed.
            by_tier = (2, 15, 30)
            next_level = f"{formatting.plural(by_tier[tier] - boosts):boost} needed to reach tier {tier + 1}."

        embed.add_field(
            name=f"**Server Boosts [{boosts:,d}]**",
            value=f"**Boost Tier {tier}** | {next_level}\n\n0 {boost_progress} 30",
            inline=False
        )

        await ctx.send(embed=embed)


    # XXX Haha it's not public and I don't know if it ever will be.
    # @commands.command(aliases=["sauce"])
    # async def source(self, ctx: commands.Context):
    #     """Gives you a link to my source code."""
    #     await ctx.send(f"<{self._links['Source']}>")


    @commands.command(aliases=["dir"])
    @commands.guild_only()
    @checks.bot_has_permissions(embed_links=True, add_reactions=True, read_message_history=True)
    async def tree(self, ctx: commands.Context):
        """Shows a tree-like view of the server's channels.
        (Bot Needs: Embed Links, Add Reactions and Read Message History)
        """
        mock_member = DefaultMemberMocker(ctx.guild)
        paginator = commands.Paginator(prefix="", suffix="")

        for category, channels in ctx.guild.by_category():
            if category is not None:
                paginator.add_line(f"**{category.name}**")

            for channel in channels:
                perms = channel.permissions_for(mock_member)

                if isinstance(channel, discord.TextChannel):
                    if perms.read_messages:
                        paginator.add_line(f"<:text_channel:587389191550271488> {channel.name}")
                    else:
                        paginator.add_line(f"<:locked_text_channel:587389191525105736> {channel.name}")
                else:
                    if perms.connect:
                        paginator.add_line(f"<:voice_channel:587389191524974592> {channel.name}")
                    else:
                        paginator.add_line(f"<:locked_voice_channel:587389191554334739> {channel.name}")


        base_embed = Embed(title="Server Channels", colour=0x2F3136)
        base_embed.set_author(name=ctx.guild.name, icon_url=ctx.guild.icon_url)
        base_embed.set_footer(text=f"{len(ctx.guild.channels)} total channels.")

        embeds = []
        for page in paginator.pages:
            embed = base_embed.copy()
            embed.description = page
            embeds.append(embed)

        await ctx.paginate(reaction_menus.EmbedSource(embeds))


    @commands.command(aliases=["memberinfo"])
    @commands.guild_only()
    @checks.bot_has_permissions(embed_links=True)
    async def userinfo(self, ctx: commands.Context, *, user: discord.Member = None):
        """Shows information about a user.
        If no user is given, then your own info is returned instead.
        (Bot Needs: Embed Links)

        EXAMPLE:
        (Ex. 1) userinfo @HitchedSyringe#0598
        (Ex. 2) userinfo 140540589329481728
        (Ex. 3) userinfo HitchedSyringe
        """
        if user is None:
            user = ctx.author

        embed = Embed(description=f"{user.mention}\n**[Link to Avatar]({user.avatar_url})**\n", colour=0x2F3136)
        embed.set_author(name=str(user))
        embed.set_thumbnail(url=user.avatar_url_as(static_format="png"))

        now = datetime.utcnow()
        created_ago = formatting.parse_duration(now - user.created_at, brief=True)
        joined_ago = formatting.parse_duration(now - user.joined_at, brief=True)
        shared_servers = sum(1 for guild in ctx.bot.guilds if user in guild.members)

        description = [
            f"**User ID:** {user.id}",
            f"**Nickname:** {user.nick}",
            f"**Shared Servers:** {shared_servers}",
            f"**Bot:** {ctx.tick(user.bot)}",
            f"**Created:** {created_ago} ago ({user.created_at:%a, %b %d, %Y @ %#I:%M %p} UTC)",
            f"**Joined:** {joined_ago} ago ({user.joined_at:%a, %b %d, %Y @ %#I:%M %p} UTC)",
            f"**Nitro Booster:** {ctx.tick(bool(user.premium_since))}",
        ]

        if user.premium_since is not None:
            premium_ago = formatting.parse_duration(now - user.premium_since, brief=True)
            description.append(f"**Boosted:** {premium_ago} ago ({user.premium_since:%a, %b %d, %Y @ %#I:%M %p} UTC)")

        embed.description += "\n".join(f"<:arrow:713872522608902205> {entry}" for entry in description)

        user_roles = user.roles[1:]  # exclude @everyone.
        if user_roles:
            # We have to reverse the role order so the highest role appears first.
            roles = " ".join(role.mention for role in reversed(user_roles))
            embed.add_field(
                name=f"**Roles [{len(user_roles)}]**",
                value=roles if len(roles) < 1024 else "Too many roles to show.",
                inline=False
            )

        # Match the icon with the status.
        statuses = (
            f"{_STATUS_EMOJI[user.mobile_status]}  |  \N{MOBILE PHONE} Mobile Status",
            f"{_STATUS_EMOJI[user.desktop_status]}  |  \N{DESKTOP COMPUTER}\ufe0f Desktop Status",
            f"{_STATUS_EMOJI[user.web_status]}  |  \N{GLOBE WITH MERIDIANS} Web Status",
        )
        embed.add_field(name="**Status**", value="\n".join(statuses))

        if user.activity is not None:
            if isinstance(user.activity, discord.CustomActivity) and user.activity.emoji is not None:
                activity_name = f"{user.activity.emoji} {user.activity.name}"
            else:
                activity_name = user.activity.name
            embed.add_field(name="**Activity**", value=activity_name)

        await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(Meta(bot))
