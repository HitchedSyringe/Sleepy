"""
Copyright (c) 2018-present HitchedSyringe

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""


import difflib
import inspect
from collections import defaultdict
from os import path
from typing import Optional, Union

import discord
from discord import ActivityType, ChannelType, Embed, Status
from discord.ext import commands, flags, menus
from discord.utils import oauth_url, format_dt as fmt_dt, utcnow
from sleepy import checks
from sleepy.paginators import WrappedPaginator
from sleepy.utils import (
    bool_to_emoji,
    plural,
    progress_bar,
)


# (channel_type, is_locked): emoji
CHANNEL_EMOJI = {
    (ChannelType.text, True): "<:tc:828149291812913152> ",
    (ChannelType.voice, True): "<:vc:828151635791839252> ",
    (ChannelType.stage_voice, True): "<:sc:828149291750785055> ",
    (ChannelType.news, True): "<:ac:828419969133314098> ",
    (ChannelType.category, True): "",
    (ChannelType.store, True): "<:st:865637489855430686> ",
    (ChannelType.public_thread, True): "<:thc:917442358377869373> ",

    (ChannelType.text, False): "<:ltc:828149291533074544> ",
    (ChannelType.voice, False): "<:lvc:828149291628625960> ",
    (ChannelType.stage_voice, False): "<:lsc:828149291590746112> ",
    (ChannelType.news, False): "<:lac:828149291578556416> ",
    (ChannelType.category, False): "",
    (ChannelType.store, False): "<:ltc:828149291533074544> ",
    (ChannelType.private_thread, False): "<:thc:917442358377869373> ",
}


# flag: emoji
BADGES = {
    "bug_hunter": "<:bh:886251266517389332>",
    "bug_hunter_level_2": "<:bh2:886251265342988320>",
    "early_supporter": "<:es:886251265573666897>",
    "hypesquad": "<:he:886251265418477639>",
    "hypesquad_balance": "<:hbl:886251265493958687>",
    "hypesquad_bravery": "<:hbv:886251265951137792>",
    "hypesquad_brilliance": "<:hbr:886251265875656814>",
    "partner": "<:po:886251265997299822>",
    "staff": "<:stl:886252968339460096>",
    "verified_bot_developer": "<:vd:886251266211184700>",
}


class BotHelpPageSource(menus.ListPageSource):

    def __init__(self, mapping, *, prefix, per_page):
        super().__init__(
            sorted(mapping, key=lambda c: c.qualified_name),
            per_page=per_page
        )

        self.mapping = mapping
        self.prefix = prefix

    async def format_page(self, menu, cogs):
        embed = Embed(
            title="Command Catalogue",
            description=(
                "Use the reactions below to interact with this menu."
                "\nUnderstanding my command syntax is simple:"
                "```lasso"
                "\n<argument> means the argument is 𝗿𝗲𝗾𝘂𝗶𝗿𝗲𝗱."
                "\n[argument] means the argument is 𝗼𝗽𝘁𝗶𝗼𝗻𝗮𝗹."
                "\n[A|B] means 𝗲𝗶𝘁𝗵𝗲𝗿 𝗔 𝗼𝗿 𝗕."
                "\n[argument...] means 𝗺𝘂𝗹𝘁𝗶𝗽𝗹𝗲 arguments can be entered."
                "```"
                "\nWhatever you do, **do not include the brackets.**"
                f"\nUse `{self.prefix}help <command|category>` for more info"
                " on a command or category.\nFor additional help, please check"
                " out my [support server](https://discord.gg/xHgh2Xg)."
            ),
            colour=0x2F3136
        )
        max_pages = self.get_max_pages()

        if max_pages > 1:
            embed.set_footer(text=f"Page {menu.current_page + 1}/{max_pages}")

        for cog in cogs:
            cmds = self.mapping.get(cog)

            if not cmds:
                return

            if cog.description:
                value = cog.description.split("\n", 1)[0] + "\n"
            else:
                value = "No help given.\n"

            current_size = len(value)
            cmd_names = []

            for cmd in cmds:
                cmd_name = f"`{cmd.name}`"
                # Account for the separator.
                current_size += len(cmd_name) + 1

                if current_size > 800:
                    break

                cmd_names.append(cmd_name)

            value += " ".join(cmd_names)
            hidden_cmds = len(cmds) - len(cmd_names)

            if hidden_cmds > 0:
                value += f"\n[+{hidden_cmds} not shown.]"

            embed.add_field(name=cog.qualified_name, value=value, inline=False)

        return embed


class GroupPageSource(menus.ListPageSource):

    def __init__(self, group, cmds, *, prefix, per_page):
        super().__init__(cmds, per_page=per_page)

        self.title = group.qualified_name
        self.description = group.description

        self.cmds = cmds
        self.prefix = prefix

    async def format_page(self, menu, cmds):
        embed = Embed(title=self.title, description=self.description, colour=0x2F3136)
        max_pages = self.get_max_pages()

        if max_pages > 1:
            embed.set_footer(
                text=f"Page {menu.current_page + 1}/{max_pages} ({len(self.cmds)} commands)"
            )

        for cmd in cmds:
            sig = cmd.signature if not isinstance(cmd, flags.FlagCommand) else cmd.old_signature

            embed.add_field(
                name=f"{cmd.qualified_name} {sig}",
                value=cmd.short_doc or "No help given.",
                inline=False
            )

        return embed


class SleepyHelpCommand(commands.HelpCommand):

    def _apply_formatting(self, embed_like, command):
        embed_like.title = self.get_command_signature(command)
        embed_like.description = (
            f"{command.description}\n\n{command.help}"
            if command.description else
            command.help or "No help given."
        )

    async def command_not_found(self, string):
        cmds = await self.filter_commands(self.context.bot.commands, sort=True)
        close = difflib.get_close_matches(string, (c.name for c in cmds))

        if not close:
            return "That command wasn't found."

        return (
            "That command wasn't found. Did you mean...\n```bnf\n"
            + "\n".join(f"<{i}> {c}" for i, c in enumerate(close, 1))
            + "```"
        )

    async def subcommand_not_found(self, command, string):
        if not isinstance(command, commands.Group):
            return "That command isn't a group command."

        if subcmds := await self.filter_commands(command.commands, sort=True):
            close = difflib.get_close_matches(string, (c.name for c in subcmds))

            if not close:
                return "That subcommand wasn't found."

            return (
                "That subcommand wasn't found. Did you mean...\n```bnf\n"
                + "\n".join(f"<{i}> {c}" for i, c in enumerate(close, 1))
                + "```"
            )

        return "That command doesn't have any visible subcommands."

    def get_command_signature(self, command):
        if command.aliases:
            aliases = "|".join(command.aliases)
            command_format = f"[{command.name}|{aliases}]"
        else:
            command_format = command.name

        parent = command.full_parent_name

        if parent:
            command_format = f"{parent} {command_format}"

        # It's probably better to list what each flag
        # actually does in the extended help string.
        if isinstance(command, flags.FlagCommand):
            return f"{command_format} {command.old_signature}"

        return f"{command_format} {command.signature}"

    async def send_bot_help(self, mapping):
        cmds = await self.filter_commands(self.context.bot.commands, sort=True)
        sorted_mapping = defaultdict(list)

        for cmd in cmds:
            if cmd.cog is not None:
                sorted_mapping[cmd.cog].append(cmd)

        await self.context.paginate(
            BotHelpPageSource(sorted_mapping, prefix=self.context.clean_prefix, per_page=4)
        )

    async def send_cog_help(self, cog):
        cmds = await self.filter_commands(cog.get_commands(), sort=True)

        if not cmds:
            await self.context.send("That category doesn't have any visible commands.")
            return

        await self.context.paginate(
            GroupPageSource(cog, cmds, prefix=self.context.clean_prefix, per_page=6)
        )

    async def send_command_help(self, command):
        embed = Embed(colour=0x2F3136)
        self._apply_formatting(embed, command)

        await self.context.send(embed=embed)

    async def send_group_help(self, group):
        cmds = await self.filter_commands(group.commands, sort=True)

        if not cmds:
            await self.send_command_help(group)
            return

        source = GroupPageSource(group, cmds, prefix=self.context.clean_prefix, per_page=6)
        self._apply_formatting(source, group)

        await self.context.paginate(source)


class Meta(commands.Cog):
    """Utility commands relating either to me or Discord itself."""

    def __init__(self, bot):
        self.bot = bot
        self.old_help_command = bot.help_command

        command_attrs = {
            "cooldown": commands.CooldownMapping.from_cooldown(1, 3, commands.BucketType.user),
            "checks": (checks.can_start_menu(check_embed=True).predicate,),
            "help": "Shows help about me, a command, or a category.",
        }

        bot.help_command = help_command = SleepyHelpCommand(command_attrs=command_attrs)
        help_command.cog = self

        # Pertains to the prefixes command and is here so
        # I don't have to repeatedly perform lookups just
        # to figure out whether to drop the dupe mention.
        self.mentionable = bot.config["mentionable"] or not bot.config["prefixes"]

    def cog_unload(self):
        self.bot.help_command = self.old_help_command

    @commands.command()
    @commands.bot_has_permissions(embed_links=True)
    async def avatar(self, ctx, *, user: discord.User = None):
        """Shows an enlarged version of a user's avatar.

        User can either be a name, ID, or mention.

        If no user is given, then your own avatar will be
        shown instead.

        (Bot Needs: Embed Links)

        **EXAMPLES:**
        ```bnf
        <1> avatar @HitchedSyringe#0598
        <2> avatar 140540589329481728
        <3> avatar HitchedSyringe
        ```
        """
        if user is None:
            user = ctx.author

        url = user.display_avatar.with_static_format("png")

        embed = Embed(colour=0x2F3136, description=f"**[Avatar Link]({url})**")
        embed.set_author(name=user)
        embed.set_image(url=url)

        await ctx.send(embed=embed)

    @commands.command(aliases=("feedback", "suggest", "complain"))
    @commands.cooldown(1, 60, commands.BucketType.user)
    async def contact(self, ctx, *, content):
        """Directly contacts my higher-ups.

        This is a quick and easy method to request features
        or bug fixes without having to be in my server.

        If possible, I will try to communicate the status of
        your request via private messages. This command does
        **not** send any file attachments.

        You may only send one message per minute.

        **EXAMPLE:**
        ```
        contact I found a bug in one of the commands!
        ```
        """
        # Thanks Discord Nitro.
        if len(content) > 2048:
            await ctx.send("The message is too long to post.")
            return

        embed = Embed(
            description=content,
            colour=0x2F3136,
            timestamp=ctx.message.created_at or ctx.message.edited_at
        )
        embed.set_author(
            name=f"{ctx.author} (ID: {ctx.author.id})",
            icon_url=ctx.author.display_avatar
        )
        embed.set_footer(text=f"Sent from: {ctx.channel} (ID: {ctx.channel.id})")

        try:
            await ctx.bot.webhook.send(embed=embed)
        except discord.HTTPException:
            await ctx.send("Sending your message failed.\nTry again later?")
        else:
            await ctx.send("Your message was sent successfully.")

    @commands.command(aliases=("hi",))
    async def hello(self, ctx):
        """Shows my brief introduction."""
        await ctx.send("Hello! \N{WAVING HAND SIGN} I am a bot made by HitchedSyringe#0598.")

    @commands.command()
    async def invite(self, ctx):
        """Gives you the invite link to join me to your server."""
        await ctx.send(f"<{oauth_url(ctx.me.id, permissions=discord.Permissions(388166))}>")

    @commands.command()
    async def ping(self, ctx):
        """Pong!

        Not all bots need a ping command.

        Ping commands are simply just a vague indicator of whether
        or not Discord is currently dying (as usual) or how crappy
        your internet is. Checking https://discordstatus.com/ or
        doing a speedtest is far more effective than typing a line
        of text and shooting it at a dumb Discord bot made by some
        internet rando you'll never meet in real life. If you need
        to check if your bot is alive, then consider implementing
        some kind of hello command. This only panders to the lazy
        and technologically illiterate zoomers who only know how
        to use TikTok and Instagram and can't be bothered to click
        away from Discord for any reason. Discord isn't your Swiss
        Army knife.

        Since you only seem to care about what this command has to
        say about Discord's current deathbed status or the current
        state of your cheap 7.2 mbps internet, I'll wrap this rant
        up. Let's face it, you probably didn't even read this wall
        of text, hell, you probably aren't even reading this right
        now, thanks to your utterly miniscule attention span.

        As for me, I'm no better than any of you.
        """
        # The reason this also uses edited_at is to allow this
        # to work for those who want allow command invokations
        # on message edits.
        ref = ctx.message.edited_at or ctx.message.created_at
        delta = abs(utcnow() - ref).total_seconds() * 1000

        await ctx.send(
            "\N{TABLE TENNIS PADDLE AND BALL} **Pong!**```ldif"
            f"\nDiscord API Latency: {ctx.bot.latency * 1000:.2f} ms"
            f"\nCommand processing time: {delta:.2f} ms```"
        )

    @commands.command(aliases=("perms",))
    @commands.guild_only()
    @commands.bot_has_permissions(embed_links=True)
    async def permissions(
        self,
        ctx,
        user: Optional[discord.Member],
        channel: discord.abc.GuildChannel = None
    ):
        """Shows a user's permissions optionally in another channel.

        User can either be a name, ID, or mention. The same
        applies to the channel argument.

        If no user is given, then your own permissions will
        be shown instead.

        If no channel is given, then the permissions in the
        current channel will be shown instead.

        **EXAMPLES:**
        ```bnf
        <1> permissions HitchedSyringe
        <2> permissions @HitchedSyringe#0598
        <3> permissions 140540589329481728 #general
        ```
        """
        if user is None:
            user = ctx.author

        if channel is None:
            channel = ctx.channel

        embed = Embed(
            description=f"Showing permissions in {CHANNEL_EMOJI[(channel.type, True)]}"
                        f"{channel.name} (ID: {channel.id})",
            colour=0x2F3136
        )
        embed.set_author(name=f"{user} (ID: {user.id})", icon_url=user.display_avatar)

        perms = [
            f"{bool_to_emoji(v)} {p.replace('_', ' ').replace('guild', 'server').title()}"
            for p, v in channel.permissions_for(user)
        ]

        # Do "ceiling division" (or just reverse floor division)
        # so the first column is longer than the second column.
        half = -(len(perms) // -2)
        embed.add_field(name="\u200b", value="\n".join(perms[:half]))
        embed.add_field(name="\u200b", value="\n".join(perms[half:]))

        await ctx.send(embed=embed)

    @commands.command(aliases=("debugperms",), hidden=True)
    @commands.is_owner()
    @commands.bot_has_permissions(embed_links=True)
    async def debugpermissions(
        self,
        ctx,
        channel_id: int,
        user: discord.User = None
    ):
        """Shows a channel's resolved permissions as an optional user.

        If no user is given, then my permissions in the
        given channel will be shown instead.

        This command can only be used by my higher-ups.
        """
        channel = ctx.bot.get_channel(channel_id)

        if channel is None:
            await ctx.send("Invalid channel ID.")
            return

        if user is None:
            user = channel.guild.me
        else:
            user = channel.guild.get_member(user.id)

            if user is None:
                await ctx.send("That user isn't a member of the channel's guild.")
                return

        await self.permissions(ctx, user, channel)

    @commands.command()
    async def prefixes(self, ctx):
        """Shows my command prefixes."""
        prefixes = await ctx.bot.get_prefix(ctx.message)

        # Remove the extra mention to prevent potential
        # confusion for the end user as it would appear
        # twice otherwise.
        if self.mentionable:
            del prefixes[0]

        await ctx.send(
            "**Prefixes**\n>>> "
            + "\n".join(f"{i}. {p}" for i, p in enumerate(prefixes, 1))
        )

    @commands.command(aliases=("guildinfo",), usage="")
    @commands.guild_only()
    @commands.bot_has_permissions(embed_links=True)
    async def serverinfo(self, ctx, *, guild=None):
        """Shows information about the server.

        An optional argument can be passed in order to get
        information about a specific server. (Owner Only)

        (Bot Needs: Embed Links)
        """
        if guild is not None and await ctx.bot.is_owner(ctx.author):
            # The reason this is down here instead of up in the
            # command arguments itself is because I would rather
            # have this be silent if the user isn't the owner.
            guild = await commands.GuildConverter().convert(ctx, guild)
        else:
            guild = ctx.guild

        embed = Embed(colour=0x2F3136, description=guild.description or Embed.Empty)
        embed.set_author(name=guild.name)
        embed.set_image(url=guild.banner)
        embed.set_thumbnail(url=guild.icon)

        embed.add_field(
            name="Information",
            value=(
                f"<:ar:862433028088135711> **ID:** {guild.id}"
                f"\n<:ar:862433028088135711> **Owner:** {guild.owner.mention}"
                f"\n<:ar:862433028088135711> **Created:** {fmt_dt(guild.created_at, 'R')}"
                "\n<:ar:862433028088135711> **Members:**"
                f" <:sm:829503770454523994> {guild.member_count:,d}"
                f" \N{BULLET} <:nb:829503770060390471> {len(guild.premium_subscribers):,d}"
                f" \N{BULLET} <:bt:833117614690533386> {sum(m.bot for m in guild.members):,d}"
                "\n<:ar:862433028088135711> **Channels:**"
                f" <:tc:828149291812913152> {len(guild.text_channels)}"
                f" \N{BULLET} <:vc:828151635791839252> {len(guild.voice_channels)}"
                f" \N{BULLET} <:sc:828149291750785055> {len(guild.stage_channels)}"
                f"\n<:ar:862433028088135711> **Locale:** {guild.preferred_locale}"
                f"\n<:ar:862433028088135711> **Upload Limit:** {guild.filesize_limit // 1e6} MB"
                f"\n<:ar:862433028088135711> **Bitrate Limit:** {guild.bitrate_limit // 1e3} kbps"
                f"\n<:ar:862433028088135711> **Shard ID:** {guild.shard_id or 'N/A'}"
            ),
            inline=False
        )

        if guild.features:
            embed.add_field(
                name="Features",
                value="\n".join(
                    f"\N{SMALL BLUE DIAMOND} {f.replace('_', ' ').title()}"
                    for f in guild.features
                )
            )

        if guild.emojis:
            e_count = len(guild.emojis)
            e_shown = " ".join(map(str, guild.emojis[:25]))

            if e_count > 25:
                e_shown += f" (+{e_count - 15} more)"

            embed.add_field(
                name=f"Emojis \N{BULLET} {e_count} / {guild.emoji_limit * 2}",
                value=e_shown,
                inline=False
            )

        # Get roles in reverse order, excluding @everyone.
        if roles := guild.roles[:0:-1]:
            r_count = len(roles)
            r_shown = " ".join(r.mention for r in roles[:15])

            if r_count > 15:
                r_shown += f" (+{r_count - 15} more)"

            embed.add_field(name=f"Roles \N{BULLET} {r_count}", value=r_shown, inline=False)

        tier = guild.premium_tier
        boosts = guild.premium_subscription_count

        if tier == 3:
            next_ = "Maximum boost tier achieved!"
        else:
            next_ = f"{plural((2, 7, 14)[tier] - boosts):boost} needed to reach tier {tier + 1}."

        embed.add_field(
            name=f"Server Boosts \N{BULLET} Tier {tier}",
            value=f"**{plural(boosts, ',d'):boost}** \N{BULLET} {next_}"
                  f"\n\n0 {progress_bar(progress=boosts if boosts < 14 else 14, maximum=14)} 14",
            inline=False
        )

        await ctx.send(embed=embed)

    # NOTE: This command will 100% break if one of the following occurs:
    # * The configured extensions directory is different from the one on
    #   the GitHub repository.
    # * A command on a non-existent extension in the GitHub repository
    #   is passed.
    # * The base URL links to a respository hosted elsewhere other than
    #   GitHub that doesn't structure URLs like GitHub.
    # Considering the first two cases, I've made it relatively simple to
    # modify this in the case that either of the above apply or may apply.
    # Just change the ``base`` value to link to your fork. I should also
    # note that this is hard-coded to view the master branch. As for the
    # third case, you're on your own.
    @commands.command()
    async def source(self, ctx, *, command=None):
        """Sends a link to my full source code or for a specific command."""
        base = "https://github.com/HitSyr/Sleepy"

        if command is None:
            await ctx.send(f"<{base}>")
            return

        if command == "help":
            src = type(self.bot.help_command)
            filename = inspect.getsourcefile(src)
        else:
            cmd = ctx.bot.get_command(command)

            if cmd is None:
                await ctx.send("That command wasn't found.")
                return

            src = cmd.callback
            filename = src.__code__.co_filename

        try:
            tail, head = inspect.getsourcelines(src)
        except (TypeError, OSError):
            await ctx.send("Failed to get the source for that command.")
            return

        module = src.__module__

        if module.startswith("jishaku"):
            base = "https://github.com/Gorialis/jishaku"
            loc = module.replace(".", "/") + ".py"
        elif module.startswith("discord"):
            base = "https://github.com/Rapptz/discord.py"
            loc = module.replace(".", "/") + ".py"
        else:
            loc = path.relpath(filename).replace("\\", "/")

        await ctx.send(f"<{base}/blob/master/{loc}#L{head}-L{head + len(tail) - 1}>")

    @commands.command(aliases=("dir",))
    @commands.guild_only()
    @commands.bot_has_permissions(embed_links=True)
    async def tree(self, ctx):
        """Shows a tree-like view of the server's channels.

        (Bot Needs: Embed Links)
        """
        total = 0
        default = ctx.guild.default_role
        tree = WrappedPaginator(None, None)

        for category, channels in ctx.guild.by_category():
            if category is not None:
                total += 1
                tree.add_line(f"**{category.name}**")

            for channel in channels:
                total += 1
                allow, deny = channel.overwrites_for(default).pair()
                perms = discord.Permissions((default.permissions.value & ~deny.value) | allow.value)

                if ctx.guild.rules_channel == channel:
                    icon = "<:rc:828149291712774164> "
                elif perms.read_messages:
                    # Only text channels, store channels, and categories can
                    # be NSFW. In this case, we only need to care about text
                    # and store channels (if those are even still a thing).
                    if (
                        isinstance(channel, (discord.TextChannel, discord.StoreChannel))
                        and channel.is_nsfw()
                    ):
                        icon = "<:ntc:828149291683807282> "
                    else:
                        icon = CHANNEL_EMOJI[(channel.type, True)]
                else:
                    icon = CHANNEL_EMOJI[(channel.type, False)]

                tree.add_line(f"{icon}{channel.name}")

        for page in tree.pages:
            embed = Embed(description=page, colour=0x2F3136)
            embed.set_author(name=ctx.guild.name, icon_url=ctx.guild.icon)
            embed.set_footer(text=f"{total} total channels.")

            await ctx.send(embed=embed)

    @commands.command(aliases=("memberinfo", "ui", "mi"))
    @commands.bot_has_permissions(embed_links=True)
    async def userinfo(self, ctx, *, user: Union[discord.Member, discord.User] = None):
        """Shows information about a user.

        If no user is given, then your own info will be
        shown instead.

        (Bot Needs: Embed Links)

        **EXAMPLES:**
        ```bnf
        <1> userinfo @HitchedSyringe#0598
        <2> userinfo 140540589329481728
        <3> userinfo HitchedSyringe
        ```
        """
        if user is None:
            user = ctx.author

        avatar_url = user.avatar.with_static_format("png")

        embed = Embed(
            description=" ".join(v for k, v in BADGES.items() if getattr(user.public_flags, k)),
            colour=0x2F3136
        )
        embed.set_author(name=user)
        embed.set_thumbnail(url=avatar_url)

        embed.add_field(
            name="Information",
            value=f"{user.mention} \N{BULLET} **[Avatar]({avatar_url})**"
                  f"\n<:ar:862433028088135711> **ID:** {user.id}"
                  f"\n<:ar:862433028088135711> **Created:** {fmt_dt(user.created_at, 'R')}"
                  f"\n<:ar:862433028088135711> **Bot:** {bool_to_emoji(user.bot)}"
                  "\n<:ar:862433028088135711> **Shared Servers:** "
                  + str(len(ctx.bot.guilds if user == ctx.me else user.mutual_guilds))
        )

        if isinstance(user, discord.User):
            embed.set_footer(text="This user is not a member of this server.")
            await ctx.send(embed=embed)
            return

        # Better than calling `Embed.set_field_at`.
        embed._fields[0]["value"] += (
            f"\n<:ar:862433028088135711> **Nick:** {user.nick}"
            "\n<:ar:862433028088135711> **Joined:** "
            + ("N/A" if user.joined_at is None else fmt_dt(user.joined_at, 'R'))
            + "\n<:ar:862433028088135711> **Boosted:** "
            + "N/A" if user.premium_since is None else fmt_dt(user.premium_since, 'R')
        )

        if roles := user.roles[:0:-1]:
            # Get roles in reverse order, excluding @everyone.
            role_count = len(roles)

            embed.add_field(
                name=f"Roles \N{BULLET} {role_count}",
                value=" ".join(r.mention for r in roles)
                      if role_count < 42 else
                      "Too many roles to show.",
                inline=False
            )

        # status_type: emoji
        status_emojis = {
            Status.dnd: "<:dnd:786093986900738079>",
            Status.idle: "<:idle:786093987148202035>",
            Status.offline: "<:offline:786093987227893790>",
            Status.online: "<:online:786093986975711272>",
        }

        embed.add_field(
            name="Status",
            value=f"{status_emojis[user.mobile_status]} | \N{MOBILE PHONE} Mobile"
                  f"\n{status_emojis[user.desktop_status]} | \N{DESKTOP COMPUTER}\ufe0f Desktop"
                  f"\n{status_emojis[user.web_status]} | \N{GLOBE WITH MERIDIANS} Web"
        )

        if (activity := user.activity) is not None:
            if isinstance(activity, discord.CustomActivity):
                embed.add_field(
                    name="Activity",
                    value=f"{activity.emoji or ''} {activity.name}"
                )
            else:
                # activity type: activity type name
                activity_verbs = {
                    ActivityType.unknown: "",
                    ActivityType.playing: "**Playing**",
                    ActivityType.streaming: "**Streaming**",
                    ActivityType.watching: "**Watching**",
                    ActivityType.listening: "**Listening to**",
                    ActivityType.competing: "**Competing in**",
                }

                embed.add_field(
                    name="Activity",
                    value=f"{activity_verbs[activity.type]} {activity.name}"
                )

        await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(Meta(bot))
