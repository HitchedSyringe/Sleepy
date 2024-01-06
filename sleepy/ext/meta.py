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

import difflib
import inspect
import itertools
import re
import time
from collections import Counter
from os import path
from typing import TYPE_CHECKING, Dict, List, Mapping, Optional, Union

import discord
from discord import Colour, Embed, SelectOption
from discord.abc import GuildChannel
from discord.ext import commands
from discord.ext.menus import ListPageSource, PageSource
from discord.ui import Select
from discord.utils import escape_markdown, format_dt, oauth_url
from jishaku.paginators import WrappedPaginator
from typing_extensions import Annotated

from sleepy.menus import BotLinksView, PaginationView
from sleepy.utils import INVITE_PERMISSIONS, SOURCE_CODE_URL, bool_to_emoji

if TYPE_CHECKING:
    from sleepy.bot import Sleepy
    from sleepy.context import Context as SleepyContext, GuildContext


# fmt: off
# channel_type: icon
CHANNEL_ICON: Dict[str, str] = {
    "text":           "<:tc:828149291812913152>",
    "voice":          "<:vc:828151635791839252>",
    "stage_voice":    "<:sc:828149291750785055>",
    "news":           "<:ac:828419969133314098>",
    "forum":          "<:fc:999410787540021308>",
    "category":       "\N{CARD INDEX DIVIDERS}",
    "public_thread":  "<:thc:1010161857409056778>",
    "private_thread": "<:thc:1010161857409056778>",
}


# flag: emoji
BADGES: Dict[str, str] = {
    "bug_hunter":                  "<:bh:886251266517389332>",
    "bug_hunter_level_2":          "<:bh2:886251265342988320>",
    "early_supporter":             "<:es:886251265573666897>",
    "hypesquad":                   "<:he:886251265418477639>",
    "hypesquad_balance":           "<:hbl:886251265493958687>",
    "hypesquad_bravery":           "<:hbv:886251265951137792>",
    "hypesquad_brilliance":        "<:hbr:886251265875656814>",
    "partner":                     "<:po:886251265997299822>",
    "staff":                       "<:stl:886252968339460096>",
    "verified_bot_developer":      "<:vd:886251266211184700>",
    "discord_certified_moderator": "<:dcm:932853177894715392>",
}
# fmt: on


class _HomePageSource(PageSource):
    async def format_page(self, menu: "_HelpView", entries: None) -> Embed:
        prefix = menu.prefix

        embed = Embed(
            title="Welcome to the help menu!",
            description=(
                "Select a category using the dropdown below."
                f"\nUse `{prefix}help <category>` to see more info about a category."
                f"\nUse `{prefix}help <command>` to see more info about a command."
            ),
            colour=Colour.dark_embed(),
        )

        embed.add_field(
            name="How do I read the command signature?",
            value=(
                "Understanding the command signature is quite simple:"
                "\n`<argument>` \N{EM DASH} `argument` is **required**."
                "\n`[argument]` \N{EM DASH} `argument` is **optional**"
                "\n\u2570 `[argument=X]` \N{EM DASH} `argument` defaults to `X` if omitted."
                "\n`<A|B>` \N{EM DASH} argument can be **either** `A` or `B`."
                "\n`<argument...>` \N{EM DASH} multiple arguments can be entered."
                "\n`<name: <argument>>` \N{EM DASH} `name` is a flag."
                "\n\u2570 Flags can be used in any order unless said otherwise."
                "\n**Please do not include the brackets.**"
            ),
            inline=False,
        )

        return embed

    # These are needed for the pagination view to actually work.

    def is_paginating(self) -> bool:
        return False

    async def get_page(self, page_number: int) -> None:
        pass


class _CommandSource(ListPageSource):
    def __init__(
        self,
        embed: Embed,
        prefix: str,
        cmds: List[commands.Command],
        *,
        per_page: int = 10,
    ) -> None:
        super().__init__(cmds, per_page=per_page)

        self.embed: Embed = embed
        self.prefix: str = prefix
        self.cmds: List[commands.Command] = cmds

    async def format_page(
        self, menu: PaginationView, cmds: List[commands.Command]
    ) -> Embed:
        embed = self.embed.copy()
        embed.set_footer(
            text=f'Use "{self.prefix}help <command>" to see more info about a command.'
        )

        if cmds:
            fmt_cmds = "\n".join(
                f"`{c.qualified_name}` \N{EM DASH} {c.short_doc or '???'}" for c in cmds
            )
            embed.add_field(
                name=f"Commands ({len(self.cmds)} total)", value=fmt_cmds, inline=False
            )

        return embed


class _HelpView(PaginationView):
    def __init__(
        self, ctx: SleepyContext, mapping: Dict[commands.Cog, List[commands.Command]]
    ) -> None:
        bot = ctx.bot

        self.bot: Sleepy = bot
        self.prefix: str = ctx.clean_prefix
        self.mapping: Dict[commands.Cog, List[commands.Command]] = mapping
        self._use_home_page_layout: bool = True

        super().__init__(
            _HomePageSource(),
            owner_ids={ctx.author.id, bot.owner_id, *bot.owner_ids},  # type: ignore
        )

        # Have to do this here since AttributeError is raised otherwise.
        self.category_select.options = [
            SelectOption(
                label=cog.qualified_name,
                description=cog.description.split("\n", 1)[0] or None,
                emoji=getattr(cog, "ICON", "\N{GEAR}"),
            )
            for cog, cmds in mapping.items()
            if cmds
        ]

    def _do_items_setup(self) -> None:
        self.add_item(self.category_select)

        if self._use_home_page_layout:
            bot_links = BotLinksView(self.bot.application_id)  # type: ignore

            for button in bot_links.children:
                self.add_item(button)

            self._use_home_page_layout = False

        super()._do_items_setup()

    @discord.ui.select(placeholder="Select a category...")
    async def category_select(
        self, itn: discord.Interaction, select: Select["_HelpView"]
    ) -> None:
        cog = self.bot.get_cog(select.values[0])

        # The cog may have been unloaded while this was open.
        if cog is None:
            await itn.response.send_message(
                "That category somehow doesn't exist.", ephemeral=True
            )
            return

        cmds = self.mapping[cog]

        if not cmds:
            await itn.response.send_message(
                "That category has no visible commands.", ephemeral=True
            )
            return

        embed = Embed(
            title=cog.qualified_name,
            description=cog.description,
            colour=Colour.dark_embed(),
        )
        source = _CommandSource(embed, self.prefix, cmds)
        await self.change_source(source, itn)


class SleepyHelpCommand(commands.HelpCommand):

    if TYPE_CHECKING:
        context: SleepyContext

    def __init__(self) -> None:
        command_attrs = {
            "checks": (commands.bot_has_permissions(embed_links=True).predicate,),
            "help": "Shows help about me, a command, or a category.",
        }

        super().__init__(command_attrs=command_attrs)

    def _format_command(self, command: commands.Command) -> Embed:
        embed = Embed(
            title=command.qualified_name,
            description=command.help or "No help given.",
            colour=Colour.dark_embed(),
        )
        embed.add_field(
            name="Usage",
            value=f"```ansi\n{self.get_command_signature(command)} ```",
            inline=False,
        )

        if command.aliases:
            fmt_aliases = " ".join(f"`{a}`" for a in command.aliases)
            embed.add_field(name="Aliases", value=fmt_aliases)

        cog = command.cog
        if cog is not None:
            icon = getattr(cog, "ICON", "\N{GEAR}")
            embed.add_field(name="Category", value=f"{icon} {cog.qualified_name}")

        return embed

    async def command_not_found(self, string: str) -> str:
        cmds = await self.filter_commands(self.context.bot.commands)

        close = difflib.get_close_matches(string, (c.name for c in cmds))
        if close:
            fmt_close = "\n".join(f"\N{BULLET} {m}" for m in close)
            return f"That command wasn't found. Did you mean...\n{fmt_close}"

        return "That command wasn't found."

    async def subcommand_not_found(self, command: commands.Command, string: str) -> str:
        if not isinstance(command, commands.Group):
            return "That command isn't a group command."

        subcmds = await self.filter_commands(command.commands)
        if subcmds:
            close = difflib.get_close_matches(string, (c.name for c in subcmds))
            if close:
                fmt_close = "\n".join(f"\N{BULLET} {m}" for m in close)
                return f"That subcommand wasn't found. Did you mean...\n{fmt_close}"

            return "That subcommand wasn't found."

        return "That command has no visible subcommands."

    def get_command_signature(self, command: commands.Command) -> str:
        ctx = self.context
        sig = command.signature

        # Don't bother with the fancypants formatting if the user is on a phone,
        # since Discord still has yet to bother with proper codeblock formatting
        # on the mobile app. Unfortunately this also only works if the user used
        # this command in a guild channel.
        if isinstance(ctx.author, discord.Member) and ctx.author.is_on_mobile():
            return f"{ctx.clean_prefix}{command.qualified_name} {sig}"

        def colourize_param(m: re.Match) -> str:
            """Assumes that parameters are formatted in one of the following ways:
            - `<X>`
            - `<X...>`
            - `<X>...`
            - `[X]`
            - `[X...]`
            - `[X]...`

            Where `X` can be one or more characters from the set `\\w\\s-|.()<>="'`.
            """
            opening, body, closing = m.groups()
            name, _, default = body.partition("=")

            # Colour the param name either blue or yellow, depending on whether
            # the param is optional or required, respectively.
            middle = f"\u001b[0;{'34' if opening == '[' else '33'}m"

            if name.endswith("..."):
                # Colour the trailing ellipses in param names grey.
                middle += f"{name[:-3]}\u001b[30m..."
            else:
                middle += name

            if default:
                # Colour the equals sign grey and the default value fuchsia.
                middle += f"\u001b[30m=\u001b[35m{default}"

            return f"\u001b[30m{opening}{middle}\u001b[30;1m{closing}"

        fmt_sig = re.sub(r"(\[|<)([\w\s\-|.()<>=\"']+)(\]|>)", colourize_param, sig)

        # Make the command signature grey if nothing ended up being substituted.
        if fmt_sig == sig:
            fmt_sig = f"\u001b[0;30m{sig}"

        return f"\u001b[0;37;1m{ctx.clean_prefix}\u001b[32m{command.qualified_name} {fmt_sig}"

    async def send_bot_help(
        self, mapping: Mapping[Optional[commands.Cog], List[commands.Command]]
    ) -> None:
        ctx = self.context

        def key(command: commands.Command) -> str:
            cog = command.cog
            return cog is not None and cog.qualified_name  # type: ignore -- This is fine.

        cmds = await self.filter_commands(ctx.bot.commands, sort=True, key=key)

        sorted_mapping = {}

        for cog_name, cmds in itertools.groupby(cmds, key=key):
            cog = ctx.bot.get_cog(cog_name)
            sorted_mapping[cog] = sorted(cmds, key=lambda c: c.qualified_name)

        view = _HelpView(ctx, sorted_mapping)
        await view.send_to(ctx)

    async def send_cog_help(self, cog: commands.Cog) -> None:
        ctx = self.context
        cmds = await self.filter_commands(cog.get_commands(), sort=True)

        if not cmds:
            await ctx.send("That category has no visible commands.")
            return

        embed = Embed(
            title=cog.qualified_name,
            description=cog.description,
            colour=Colour.dark_embed(),
        )
        await ctx.paginate(_CommandSource(embed, ctx.clean_prefix, cmds))

    async def send_command_help(self, command: commands.Command) -> None:
        await self.context.send(embed=self._format_command(command))

    async def send_group_help(self, group: commands.Group) -> None:
        cmds = await self.filter_commands(group.commands, sort=True)

        if not cmds:
            await self.send_command_help(group)
            return

        embed = self._format_command(group)
        source = _CommandSource(embed, self.context.clean_prefix, cmds)
        await self.context.paginate(source)


class Meta(commands.Cog):
    """Utility commands relating either to me or Discord itself.

    ||This has absolutely nothing to do with a certain American
    multinational technology conglomerate.||
    """

    ICON: str = "\N{INFORMATION SOURCE}"

    def __init__(self, bot: Sleepy) -> None:
        self.bot: Sleepy = bot
        self.old_help_command: Optional[commands.HelpCommand] = bot.help_command

        bot.help_command = help_command = SleepyHelpCommand()
        help_command.cog = self

        # Pertains to the prefixes command and is here so
        # I don't have to repeatedly perform lookups just
        # to figure out whether to drop the dupe mention.
        self.mentionable: bool = bot.config["mentionable"] or not bot.config["prefixes"]

    def cog_unload(self) -> None:
        self.bot.help_command = self.old_help_command

    @staticmethod
    def _get_channel_icon(
        channel: Union[GuildChannel, discord.Thread],
        viewer: Union[discord.Member, discord.Role],
    ) -> str:
        # Skip cache lookup and just use the ID itself directly.
        if channel.id == channel.guild._rules_channel_id:
            return "<:rc:828149291712774164>"

        icon = CHANNEL_ICON[channel.type.name]

        if channel.type.name != "category":
            perms = channel.permissions_for(viewer)

            if not (perms.connect or perms.read_messages):
                icon += "\N{LOCK}"
            elif channel.is_nsfw():  # type: ignore -- all channel types should have this.
                icon += "\N{NO ONE UNDER EIGHTEEN SYMBOL}"

        return icon

    @commands.command()
    @commands.bot_has_permissions(embed_links=True)
    async def avatar(
        self, ctx: SleepyContext, *, user: discord.User = commands.Author
    ) -> None:
        """Shows an enlarged version of a user's avatar.

        User can either be a name, ID, or mention.

        If no user is given, then your own avatar will be shown instead.

        (Bot Needs: Embed Links)

        **EXAMPLES:**
        ```bnf
        <1> avatar hitchedsyringe
        <2> avatar 140540589329481728
        <3> avatar HitchedSyringe
        ```
        """
        url = user.display_avatar.with_static_format("png")

        embed = Embed(colour=Colour.dark_embed(), description=f"**[Avatar Link]({url})**")
        embed.set_author(name=user)
        embed.set_image(url=url)

        await ctx.send(embed=embed)

    @commands.command(aliases=("feedback", "suggest", "complain"))
    @commands.cooldown(1, 60, commands.BucketType.user)
    async def contact(
        self, ctx: SleepyContext, *, content: commands.Range[str, 1, 2048]
    ) -> None:
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
        embed = Embed(
            description=content,
            colour=Colour.dark_embed(),
            timestamp=ctx.message.created_at or ctx.message.edited_at,
        )
        embed.set_author(
            name=f"{ctx.author} (ID: {ctx.author.id})", icon_url=ctx.author.display_avatar
        )
        embed.set_footer(text=f"Sent from: {ctx.channel} (ID: {ctx.channel.id})")

        try:
            await ctx.bot.webhook.send(embed=embed)
        except discord.HTTPException:
            await ctx.send("Sending your message failed.\nTry again later?")
        else:
            await ctx.send("Your message was sent successfully.")

    @commands.command(aliases=("hi",))
    async def hello(self, ctx: SleepyContext) -> None:
        """Shows my brief introduction."""
        await ctx.send("Hello! \N{WAVING HAND SIGN} I am a bot made by hitchedsyringe.")

    @commands.command()
    async def invite(self, ctx: SleepyContext) -> None:
        """Gives you the invite link to join me to your server."""
        permissions = discord.Permissions(INVITE_PERMISSIONS)
        await ctx.send(f"<{oauth_url(ctx.bot.application_id, permissions=permissions)}>")  # type: ignore

    @commands.command()
    async def ping(self, ctx: SleepyContext) -> None:
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
        api_start = time.perf_counter()
        await ctx.typing()
        api_delta = time.perf_counter() - api_start

        await ctx.send(
            "\N{TABLE TENNIS PADDLE AND BALL} **Pong!**"
            "```ldif"
            f"\nDiscord API Latency: {api_delta * 1000:.2f} ms"
            f"\nDiscord Gateway Latency: {ctx.bot.latency * 1000:.2f} ms"
            "```"
        )

    @commands.command(aliases=("perms",))
    @commands.guild_only()
    @commands.bot_has_permissions(embed_links=True)
    async def permissions(
        self,
        ctx: SleepyContext,
        user: Annotated[discord.Member, Optional[discord.Member]] = commands.Author,
        channel: Union[GuildChannel, discord.Thread] = commands.CurrentChannel,
    ) -> None:
        """Shows a user's permissions optionally in another channel.

        User can either be a name, ID, or mention. The same applies
        to the channel argument.

        If no user is given, then your own permissions will be shown
        instead.

        If no channel is given, then the permissions in the current
        channel will be shown instead.

        **EXAMPLES:**
        ```bnf
        <1> permissions HitchedSyringe
        <2> permissions hitchedsyringe
        <3> permissions 140540589329481728 #general
        ```
        """
        embed = Embed(
            title=f"Permissions for {channel.mention}", colour=Colour.dark_embed()
        )
        embed.set_author(name=f"{user} (ID: {user.id})", icon_url=user.display_avatar)

        perms_readable = [
            f"{bool_to_emoji(v)} {p.replace('_', ' ').replace('guild', 'server').title()}"
            for p, v in channel.permissions_for(user)
        ]

        # Do "ceiling division" (or just reverse floor division)
        # so the first column is longer than the second column.
        half = -(len(perms_readable) // -2)
        embed.add_field(name="\u200b", value="\n".join(perms_readable[:half]))
        embed.add_field(name="\u200b", value="\n".join(perms_readable[half:]))

        await ctx.send(embed=embed)

    @commands.command()
    async def prefixes(self, ctx: SleepyContext) -> None:
        """Shows my command prefixes."""
        prefixes: List[str] = await ctx.bot.get_prefix(ctx.message)  # type: ignore

        # Remove the extra mention to prevent potential
        # confusion for the end user as it would appear
        # twice otherwise.
        if self.mentionable:
            del prefixes[0]

        await ctx.send(
            "**Prefixes**\n>>> "
            + "\n".join(f"{i}. {p}" for i, p in enumerate(prefixes, 1))
        )

    @commands.command(aliases=("guildinfo", "gi", "si"), usage="")
    @commands.guild_only()
    @commands.bot_has_permissions(embed_links=True)
    async def serverinfo(self, ctx: GuildContext, *, server: str = None):
        """Shows information about the server.

        An optional argument can be passed in order to get
        information about a specific server. (Owner Only)

        (Bot Needs: Embed Links)
        """
        if server is not None and await ctx.bot.is_owner(ctx.author):
            # The reason this is down here instead of up in the
            # command arguments itself is because I would rather
            # have this be silent if the user isn't the owner.
            guild = await commands.GuildConverter().convert(ctx, server)
        else:
            guild = ctx.guild

        embed = Embed(colour=Colour.dark_embed(), description=guild.description)
        embed.set_author(name=guild.name)

        if guild.icon is not None:
            embed.set_thumbnail(url=guild.icon)

        if guild.banner is not None:
            embed.set_image(url=guild.banner)

        embed.add_field(
            name="\N{INFORMATION SOURCE} Information",
            value=f"`ID:` {guild.id}"
            f"\n`Owner:` {guild.owner}"
            f"\n`Created:` {format_dt(guild.created_at, 'R')}"
            f"\n`Locale:` {guild.preferred_locale}"
            f"\n`Vanity URL:` {guild.vanity_url or 'N/A'}"
            f"\n`Security Level:` {guild.verification_level.name.title()}"
            f"\n`MFA Level:` {guild.mfa_level.name.replace('_', ' ').title()}"
            f"\n`NSFW Filter:` {guild.explicit_content_filter.name.replace('_', ' ').title()}"
            f"\n`Upload Limit:` {guild.filesize_limit // 1e6} MB"
            f"\n`Max Bitrate:` {guild.bitrate_limit // 1e3} kbps"
            f"\n`Max Members:` {guild.max_members:,d}"
            f"\n`Shard ID:` {'N/A' if guild.shard_id is None else guild.shard_id}",
        )

        if guild.chunked:
            members = guild.members
        else:
            async with ctx.typing():
                members = await guild.chunk()

        rb_info = "N/A"

        if guild.premium_subscription_count > 0:
            recent = max(members, key=lambda m: m.premium_since or guild.created_at)

            if recent.premium_since is not None:
                rb_info = f"{recent} ({format_dt(recent.premium_since, 'R')})"

        channels = Counter(map(type, guild.channels))

        total_emojis = 0
        animated = 0

        for emoji in guild.emojis:
            total_emojis += 1

            if emoji.animated:
                animated += 1

        embed.add_field(
            name="\N{BAR CHART} Statistics",
            value=f"`Members:` {guild.member_count:,d}"
            f"\n<:bt:833117614690533386> {sum(m.bot for m in members):,d}"
            f" \N{BULLET} <:nb:829503770060390471> {len(guild.premium_subscribers):,d}"
            f"\n`Channels:` {sum(channels.values())}"
            f"\n{CHANNEL_ICON['category']} {channels[discord.CategoryChannel]}"
            f" \N{BULLET} {CHANNEL_ICON['text']} {channels[discord.TextChannel]}"
            f" \N{BULLET} {CHANNEL_ICON['voice']} {channels[discord.VoiceChannel]}"
            f"\n{CHANNEL_ICON['stage_voice']} {channels[discord.StageChannel]}"
            f" \N{BULLET} {CHANNEL_ICON['public_thread']} {len(guild.threads):,d}"
            f" \N{BULLET} {CHANNEL_ICON['forum']} {channels[discord.ForumChannel]}"
            f"\n`Roles:` {len(guild.roles)}"
            f"\n`Emojis:` {total_emojis} / {guild.emoji_limit * 2}"
            f"\n\u251D`Regular:` {total_emojis - animated}"
            f"\n\u2570`Animated:` {animated}"
            f"\n`Stickers:` {len(guild.stickers)} / {guild.sticker_limit}"
            f"\n`Boosts:` {guild.premium_subscription_count} \u2012 Tier {guild.premium_tier}"
            f"\n\u2570`Recent:` {rb_info}",
        )

        if features := ", ".join(f.replace('_', ' ').title() for f in guild.features):
            embed.add_field(
                name=f"\N{SPARKLES} Features \N{BULLET} {len(guild.features)}",
                value=f"```\n{features}\n```",
                inline=False,
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
    @commands.command(aliases=("src",))
    async def source(self, ctx: SleepyContext, *, command: str = None) -> None:
        """Sends a link to my full source code or for a specific command."""
        base = SOURCE_CODE_URL

        if command is None:
            await ctx.send(f"<{base}>")
            return

        if command == "help":
            src = type(self.bot.help_command)
            filename: str = inspect.getsourcefile(src)  # type: ignore
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
    async def tree(self, ctx: GuildContext) -> None:
        """Shows a tree-like view of the server's channels.

        (Bot Needs: Embed Links)
        """
        tree = WrappedPaginator(prefix="", suffix="")
        guild = ctx.guild
        total = 0

        for category, channels in guild.by_category():
            if category is not None:
                total += 1
                tree.add_line(f"**{category.name}**")

            for channel in channels:
                total += 1
                icon = self._get_channel_icon(channel, guild.default_role)
                tree.add_line(f"{icon} {channel.name}")

        for page in tree.pages:
            embed = Embed(description=page, colour=Colour.dark_embed())
            embed.set_author(name=guild.name, icon_url=guild.icon)
            embed.set_footer(text=f"{total} total channels.")

            await ctx.send(embed=embed)

    @commands.command(aliases=("memberinfo", "ui", "mi"))
    @commands.bot_has_permissions(embed_links=True)
    async def userinfo(
        self,
        ctx: SleepyContext,
        *,
        user: Union[discord.Member, discord.User] = commands.Author,
    ) -> None:
        """Shows information about a user.

        If no user is given, then your own info will be shown instead.

        (Bot Needs: Embed Links)

        **EXAMPLES:**
        ```bnf
        <1> userinfo hitchedsyringe
        <2> userinfo 140540589329481728
        <3> userinfo HitchedSyringe
        ```
        """
        embed = Embed(
            description=" ".join(
                v for k, v in BADGES.items() if getattr(user.public_flags, k)
            )
        )
        embed.set_author(name=user)
        embed.set_thumbnail(url=user.display_avatar)

        if user.banner is not None:
            embed.set_image(url=user.banner)

        shared = len(ctx.bot.guilds if user == ctx.me else user.mutual_guilds)

        embed.add_field(
            name="\N{INFORMATION SOURCE} General Information",
            value=f"`Mention:` {user.mention}"
            f"\n`ID:` {user.id}"
            f"\n`Created:` {format_dt(user.created_at, 'R')}"
            f"\n`Is Bot User:` {bool_to_emoji(user.bot)}"
            f"\n`Is System User:` {bool_to_emoji(user.system)}"
            f"\n`Shared Servers:` {shared}",
        )

        if isinstance(user, discord.User):
            embed.colour = Colour.dark_embed()
            embed.set_footer(text="This user is not a member of this server.")
        else:
            embed.colour = user.colour.value or Colour.dark_embed()

            embed.add_field(
                name="\N{BUST IN SILHOUETTE} Member Information",
                value=f"`Nickname:` {escape_markdown(user.nick) if user.nick else 'N/A'}"
                f"\n`Joined:` {format_dt(user.joined_at, 'R') if user.joined_at else 'N/A'}"
                f"\n`Boosted:` {format_dt(user.premium_since, 'R') if user.premium_since else 'N/A'}"
                f"\n`Top Role:` {user.top_role.name}"
                f"\n`Colour:` {user.colour}",
            )

            if roles := user.roles[:0:-1]:
                r_count = len(roles)
                r_shown = ", ".join(r.mention for r in roles[:15])

                if r_count > 15:
                    r_shown += f" (+{r_count - 15} more)"

                embed.add_field(
                    name=f"Roles \N{BULLET} {r_count}", value=r_shown, inline=False
                )

            # fmt: off
            # status_type: emoji
            status_icons = {
                "dnd":     "<:dnd:786093986900738079>",
                "idle":    "<:idle:786093987148202035>",
                "offline": "<:offline:786093987227893790>",
                "online":  "<:online:786093986975711272>",
            }
            # fmt: on

            embed.add_field(
                name="Status",
                value=(
                    f"{status_icons[user.mobile_status.name]} | \N{MOBILE PHONE}"
                    f"\n{status_icons[user.desktop_status.name]} | \N{DESKTOP COMPUTER}"
                    f"\n{status_icons[user.web_status.name]} | \N{GLOBE WITH MERIDIANS}"
                ),
            )

            if user.activity is not None:
                activity = user.activity

                if activity.type.name in ("custom", "unknown"):
                    embed.add_field(name="Activity", value=str(activity))
                else:
                    # fmt: off
                    # activity_type: verb
                    activity_verbs = {
                        "playing":   "Playing",
                        "streaming": "Streaming",
                        "watching":  "Watching",
                        "listening": "Listening to",
                        "competing": "Competing in",
                    }
                    # fmt: on

                    embed.add_field(
                        name="Activity",
                        value=f"**{activity_verbs[activity.type.name]}** {activity.name}",
                    )

        await ctx.send(embed=embed)


async def setup(bot: Sleepy) -> None:
    await bot.add_cog(Meta(bot))
