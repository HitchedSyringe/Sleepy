"""
Copyright (c) 2018-present HitchedSyringe

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""


from __future__ import annotations

import colorsys
import io
import json
import random
import re
import unicodedata
from collections import Counter
from typing import TYPE_CHECKING, Any, Dict, Iterable, List, Optional, Set, Tuple, Union

import discord
import emoji
import pyfiglet
from discord import Embed, File
from discord.ext import commands
from discord.ui import View, select
from discord.utils import MISSING, escape_markdown
from jishaku.functools import executor_function
from PIL import Image, ImageDraw
from typing_extensions import Annotated

from sleepy.utils import measure_performance, plural, randint, tchart

if TYPE_CHECKING:
    from discord.ui import Item, Select
    from typing_extensions import Self

    from sleepy.bot import Sleepy
    from sleepy.context import Context as SleepyContext


# + is positive, - is negative, no sign is neutral.
BALL_RESPONSES: Tuple[str, ...] = (
    "+ It is certain.",
    "+ It is decidedly so.",
    "+ Without a doubt.",
    "+ Yes definitely.",
    "+ You may rely on it.",
    "+ As I see it, yes.",
    "+ Most likely.",
    "+ Outlook good.",
    "+ Yes.",
    "+ Signs point to yes.",
    "Reply hazy try again.",
    "Ask again later.",
    "Better not tell you now.",
    "Cannot predict now.",
    "Concentrate and ask again.",
    "- Don't count on it.",
    "- My reply is no.",
    "- My sources say no.",
    "- Outlook not so good.",
    "- Very doubtful.",
)


# regex: repl
OWO_TRANSLATIONS: Dict[re.Pattern, str] = {
    re.compile(r"[lr]"): "w",
    re.compile(r"[LR]"): "W",
    re.compile(r"([Nn])([aeiou])"): "\\1y\\2",
    re.compile(r"([Nn])([AEIOU])"): "\\1Y\\2",
    re.compile(r"([ao])^[a-zA-Z]"): "h\\1",
    re.compile(r"([AO])^[a-zA-Z]"): "H\\1",
}


class EmoteData:

    __slots__: Tuple[str, ...] = ("char", "name")

    def __init__(self, char: str, name: str) -> None:
        self.char: str = char
        self.name: str = name

    @classmethod
    async def convert(cls, ctx: SleepyContext, argument: str) -> Self:
        argument = await commands.clean_content().convert(ctx, argument)

        try:
            emoji_data = emoji.EMOJI_DATA[argument]
        except KeyError:
            pass
        else:
            return cls(argument, emoji_data["en"].strip(":").replace("_", " "))

        if len(argument) == 1:
            return cls(argument, unicodedata.name(argument, "unknown emote"))

        try:
            custom = await commands.PartialEmojiConverter().convert(ctx, argument)
        except commands.PartialEmojiConversionFailure:
            pass
        else:
            # Assume that we can use this emoji.
            return cls(custom.name, str(custom))

        return cls(argument, "unknown emote")


class PollView(View):

    __slots__: Tuple[str, ...] = (
        "prompt",
        "starter",
        "votes",
        "_message",
        "__voted",
    )

    def __init__(
        self,
        *,
        starter: Union[discord.User, discord.Member],
        prompt: str,
        choices: Iterable[str],
    ) -> None:
        super().__init__(timeout=60)

        self.prompt: str = prompt.strip()
        self.starter: Union[discord.User, discord.Member] = starter
        self.votes: Counter[str] = Counter()

        self._message: discord.Message = MISSING
        self.__voted: Set[int] = set()

        for choice in choices:
            self.vote.add_option(label=choice.strip())

    # This is overrided to remove the reset-timeout-on-interaction
    # logic, thus, forcing this view to time out in the given time.
    async def _scheduled_task(
        self, item: Item["PollView"], itn: discord.Interaction
    ) -> None:
        try:
            allow = await self.interaction_check(itn)

            if not allow:
                return

            await item.callback(itn)
        except Exception as e:
            return await self.on_error(itn, e, item)

    async def send_to(self, destination: discord.abc.Messageable) -> None:
        embed = Embed(
            title="Everyone will be voting on:", description=self.prompt, colour=0x2F3136
        )
        embed.set_author(
            name=f"{self.starter} is calling a vote!",
            icon_url=self.starter.display_avatar,
        )
        embed.set_footer(
            text="Use the dropdown below to cast your vote! Voting ends in 1 minute."
        )

        self._message = await destination.send(embed=embed, view=self)

    async def interaction_check(self, itn: discord.Interaction) -> bool:
        if itn.user is MISSING:
            return False

        if itn.user.id in self.__voted:
            await itn.response.send_message("You've already voted!", ephemeral=True)
            return False

        return True

    async def on_timeout(self) -> None:
        del self.__voted

        try:
            await self._message.delete()
        except discord.HTTPException:
            pass

        votes = self.votes
        channel = self._message.channel

        if not votes:
            await channel.send("Nobody voted? Oh well. Better luck next time.")
            return

        embed = Embed(
            title="Voting has ended and the results are in!",
            description=f"```\n{tchart(dict(votes.most_common()))}```",
            colour=0x2F3136,
        )
        embed.set_footer(
            text=f"Started by: {self.starter}",
            icon_url=self.starter.display_avatar,
        )
        embed.add_field(name="Everyone voted on:", value=self.prompt)
        embed.add_field(name="Total Votes", value=format(sum(votes.values()), ","))

        await channel.send(embed=embed)

    @select(placeholder="Select an option.")
    async def vote(self, itn: discord.Interaction, select: Select) -> None:
        self.votes[select.values[0]] += 1
        self.__voted.add(itn.user.id)

        await itn.response.send_message(
            "Your vote was successfully recorded.", ephemeral=True
        )


class FigletFlags(commands.FlagConverter):
    font: Optional[Annotated[str, str.lower]] = None
    text: Annotated[str, commands.clean_content(fix_channel_mentions=True)]


class PollFlags(commands.FlagConverter):
    prompt: commands.Range[str, 1, 1000]
    choices: List[commands.Range[str, 1, 100]] = commands.flag(name="choice", max_args=15)


class Fun(
    commands.Cog,
    command_attrs={
        "cooldown": commands.CooldownMapping.from_cooldown(
            2, 5, commands.BucketType.member
        ),
    },
):
    """Commands made for entertaining and nothing more.

    ||Totally not a dumping ground for janky commands.||
    """

    ICON: str = "\N{CIRCUS TENT}"

    def __init__(self) -> None:
        self.figlet_format: Any = measure_performance(pyfiglet.figlet_format)

    @staticmethod
    @executor_function
    def create_colour_preview(colour: Tuple[int, int, int]) -> io.BytesIO:
        buffer = io.BytesIO()

        image = Image.new("RGBA", (256, 256))
        ImageDraw.Draw(image).regular_polygon((128, 128, 127), 4, 45, colour)

        image.save(buffer, "png")

        buffer.seek(0)

        return buffer

    @commands.command(name="8ball")
    async def _8ball(
        self, ctx: SleepyContext, *, question: commands.Range[str, 1, 1500]
    ) -> None:
        """Asks the magic 8 ball a question.

        **EXAMPLE:**
        ```
        8ball Am I the fairest of them all?
        ```
        """
        question = await commands.clean_content().convert(ctx, question)

        await ctx.send(f"{question}\n```diff\n{random.choice(BALL_RESPONSES)}```")

    @commands.command()
    async def advice(self, ctx: SleepyContext) -> None:
        """Gives some advice."""
        resp = await ctx.get("https://api.adviceslip.com/advice")
        data = json.loads(resp)

        await ctx.send(f"{data['slip']['advice']}\n`Powered by adviceslip.com`")

    @commands.command(aliases=("asskeyart", "figlet"), usage="text: <text> [options...]")
    @commands.cooldown(1, 5, commands.BucketType.member)
    async def asciiart(self, ctx: SleepyContext, *, options: FigletFlags) -> None:
        """Generates ASCII art out of the given text.

        This command's interface is similar to Discord's slash commands.
        Values with spaces must be surrounded by quotation marks.

        Options can be given in any order and, unless otherwise stated,
        are assumed to be optional.

        The following options are valid:

        `text: <text>` **Required**
        > The text to render into ASCII art.
        `font: <font>`
        > The font to render the text with.
        > If omitted, then a random font will be chosen.
        > For a list of valid font names, refer to:
        > <https://archive.ph/INsmY>

        **EXAMPLES:**
        ```bnf
        <1> asciiart text: hello there!
        <2> asciiart font: taxi____ text: woah, cool!
        ```
        """
        if options.font is None:
            options.font = random.choice(pyfiglet.FigletFont.getFonts())

        try:
            output, delta = self.figlet_format(options.text, options.font)
        except pyfiglet.FontNotFound:
            await ctx.send("That font wasn't found.")
            return

        if not output:
            await ctx.send("Sorry, but my renderer doesn't support the given text.")
            return

        content = (
            f"Requested by: {ctx.author} \N{BULLET} Font: `{options.font}` "
            f"\N{BULLET} Took {delta:.2f} ms\n```\n{output}```"
        )

        if len(content) < 2000:
            await ctx.send(content)
        else:
            await ctx.send("The result is too long to post.")

    @commands.group(name="choose", invoke_without_command=True)
    async def choose(
        self, ctx: SleepyContext, *choices: Annotated[str, commands.clean_content]
    ) -> None:
        """Chooses between the given choices.

        Quotation marks must be used for values containing spaces.

        **EXAMPLE:**
        ```
        choose bread eggs "cheddar cheese"
        ```
        """
        if len(choices) < 2:
            await ctx.send("You must give me at least 2 options to choose from.")
            return

        choice = random.choice(choices)

        if len(choice) < 1990:
            await ctx.send(f"I choose {choice}!")
        else:
            await ctx.send("The option I chose was too long to post.")

    @choose.command(name="bestof")
    async def choose_bestof(
        self,
        ctx: SleepyContext,
        times: Optional[commands.Range[int, 1, 10001]],
        *choices: Annotated[str, commands.clean_content],
    ):
        """Recursively chooses between the given choices.

        You can only recursively choose between 1 and 10001
        times, inclusive.

        Any values containing spaces must be surrounded by
        quotation marks.

        **EXAMPLES:**
        ```bnf
        <1> choose bestof oranges "honey dew"
        <2> choose bestof 10 milk "choccy milk"
        ```
        """
        choices_count = len(choices)

        if choices_count < 2:
            await ctx.send("I need at least 2 options to choose from.")
            return

        if times is None:
            times = min(10001, max(1, choices_count**2))

        counter = Counter(random.choices(choices, k=times))

        result = "\n".join(
            f"{i}. {e} ({plural(c, ',d'):time} \N{BULLET} {c / times:.2%})"
            for i, (e, c) in enumerate(counter.most_common(10), 1)
        )

        if len(result) < 2000:
            await ctx.send(result)
        else:
            await ctx.send("The result is too long to post.")

    @commands.command(aliases=("cnorris",))
    async def chucknorris(self, ctx: SleepyContext) -> None:
        """Tells a Chuck Norris joke/fact."""
        resp = await ctx.get("https://api.icndb.com/jokes/random?escape=javascript")

        await ctx.send(f"{resp['value']['joke']}\n`Powered by icndb.com`")

    @commands.command()
    async def clap(
        self, ctx: SleepyContext, *, text: Annotated[str, commands.clean_content]
    ) -> None:
        """\N{CLAPPING HANDS SIGN}

        **EXAMPLE:**
        ```
        clap hello there!
        ```
        """
        clapped = (
            "\N{CLAPPING HANDS SIGN}"
            + "\N{CLAPPING HANDS SIGN}".join(text.split())
            + "\N{CLAPPING HANDS SIGN}"
        )

        if len(clapped) < 2000:
            await ctx.send(clapped)
        else:
            await ctx.send("The result is too long to post.")

    @commands.command(aliases=("color",))
    @commands.bot_has_permissions(embed_links=True, attach_files=True)
    @commands.cooldown(1, 5, commands.BucketType.member)  # mainly because using PIL.
    async def colour(self, ctx: SleepyContext, *, colour: discord.Colour = None) -> None:
        """Shows a representation of a given colour.

        Colour can either be a name, 6 digit hex value prefixed with either a
        `0x`, `#`, or `0x#`; or CSS RGB function (e.g. `rgb(103, 173, 242)`).

        For a list of valid colour names, refer to:
        <https://discordpy.readthedocs.io/en/latest/api.html#discord.Colour>

        If no colour is given, then a random colour will be shown instead.

        (Bot Needs: Embed Links and Attach Files)

        **EXAMPLES:**
        ```bnf
        <1> colour red
        <2> colour #2F3136
        <2> colour 0x32A852
        <2> colour 0x#FA9C69
        <3> colour rgb(106, 63, 227)
        ```
        """
        if colour is None:
            colour = discord.Colour.random()

        # colorsys doesn't convert RGB nicely to human-readable
        # HSV, so we'll have to do a few extra calculations in
        # order to make the display values look right.
        r, g, b = colour.to_rgb()
        h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)

        embed = Embed(colour=colour)
        embed.set_thumbnail(url="attachment://preview.png")
        embed.add_field(name="Decimal", value=colour.value)
        embed.add_field(name="Hex", value=str(colour).upper())
        embed.add_field(name="\u200b", value="\u200b")
        embed.add_field(name="RGB", value=f"({r}, {g}, {b})")
        embed.add_field(name="HSV", value=f"({h * 360:.0f}°, {s:.0%}, {v:.0%})")
        embed.add_field(name="\u200b", value="\u200b")

        colour_preview = await self.create_colour_preview((r, g, b))

        await ctx.send(embed=embed, file=File(colour_preview, "preview.png"))

    @commands.command()
    @commands.guild_only()
    async def compliment(self, ctx: SleepyContext, *, user: discord.Member) -> None:
        """Compliments a user.

        User can either be a name, ID, or mention.

        **EXAMPLES:**
        ```bnf
        <1> compliment HitchedSyringe
        <2> compliment @HitchedSyringe#0598
        <3> compliment 140540589329481728
        ```
        """
        if user == ctx.me:
            await ctx.send("I know I'm perfection! Compliment someone who needs it!")
        else:
            resp = await ctx.get("https://complimentr.com/api")

            await ctx.send(
                f"{user.mention} {resp['compliment']}.\n`Powered by complimentr.com`",
                allowed_mentions=discord.AllowedMentions(users=False),
            )

    @commands.command(aliases=("pun",))
    async def dadjoke(self, ctx: SleepyContext) -> None:
        """Tells a dad joke (or a pun, whatever you want to call it.)"""
        resp = await ctx.get(
            "https://icanhazdadjoke.com/", headers__={"Accept": "application/json"}
        )

        await ctx.send(f"{resp['joke']}\n`Powered by icanhazdadjoke.com`")

    @commands.command(aliases=("emojidick", "emojidong", "emojipp"))
    async def emojipenis(self, ctx: SleepyContext, *, emote: EmoteData) -> None:
        """ "___\\_\\_\\_ penis"

        **EXAMPLES:**
        ```bnf
        <1> emojipenis \N{AUBERGINE}
        <2> emojipenis :custom_emoji:
        <3> emojipenis =
        ```
        """
        char = emote.char

        content = escape_markdown(
            f"{emote.name.lower().replace('_', ' ')} penis\n"
            f"{char * 2}\n{char * 3}\n  {char * 3}\n    {char * 3}\n"
            f"     {char * 3}\n       {char * 3}\n        {char * 3}\n"
            f"         {char * 3}\n          {char * 3}\n"
            f"          {char * 3}\n      {char * 4}\n {char * 6}\n"
            f" {char * 3}  {char * 3}\n    {char * 2}       {char * 2}"
        )

        if len(content) < 2000:
            await ctx.send(content)
        else:
            await ctx.send("The result is too long to post. (Pun intended)")

    @commands.command(aliases=("emojipussy", "emojivulva", "emojiclit"))
    async def emojivagina(self, ctx: SleepyContext, *, emote: EmoteData) -> None:
        """ "___\\_\\_\\_ vagina"

        **EXAMPLES:**
        ```bnf
        <1> emojivagina \N{MOUTH}
        <2> emojivagina :custom_emoji:
        <3> emojivagina =
        ```
        """
        char = emote.char

        content = escape_markdown(
            f"{emote.name.lower().replace('_', ' ')} vagina\n"
            f"         {char}\n       {char * 2}\n  {char * 4}\n"
            f" {char * 2}  {char * 2}\n{char * 2}    {char * 2}\n"
            f"{char * 2}    {char * 2}\n {char * 2}  {char * 2}\n"
            f"  {char * 4}\n       {char * 2}\n         {char}"
        )

        if len(content) < 2000:
            await ctx.send(content)
        else:
            await ctx.send("The result is too long to post.")

    @commands.command(aliases=("fite", "1v1"))
    @commands.guild_only()
    async def fight(self, ctx: SleepyContext, *, user: discord.Member) -> None:
        """Fights someone.

        User can either be a name, ID, or mention.

        **EXAMPLES:**
        ```bnf
        <1> fight HitchedSyringe
        <2> fight @HitchedSyringe#0598
        <3> fight 140540589329481728
        ```
        """
        if user == ctx.author:
            await ctx.send("You look stupid trying to fight yourself.")
        elif await ctx.bot.is_owner(user) or user == ctx.me:
            await ctx.send(
                f"You fought {user.mention} and got erased from existence.",
                allowed_mentions=discord.AllowedMentions(users=False),
            )
        elif random.random() < 0.5:
            await ctx.send(
                f"You fought {user.mention} and whooped them.",
                allowed_mentions=discord.AllowedMentions(users=False),
            )
        else:
            await ctx.send(
                f"You fought {user.mention} and got your nose bloodied.\nGo see a doctor.",
                allowed_mentions=discord.AllowedMentions(users=False),
            )

    @commands.command()
    async def flipcoin(self, ctx: SleepyContext):
        """Flips a coin."""
        flip = "Heads" if random.random() < 0.5 else "Tails"
        await ctx.send(f"You flipped **{flip}**!")

    @commands.command(aliases=("bored", "boredidea"))
    @commands.bot_has_permissions(embed_links=True)
    async def idea(self, ctx: SleepyContext) -> None:
        """Gives you something to do for when you're bored."""
        data = await ctx.get("http://boredapi.com/api/activity/")

        await ctx.send(data["activity"] + ".\n`Powered by boredapi.com`")

    @commands.command(aliases=("roast",))
    @commands.guild_only()
    async def insult(self, ctx: SleepyContext, *, user: discord.Member) -> None:
        """Insults someone.

        User can either be a name, ID, or mention.

        **Disclaimer:** This command was made for entertainment
        purposes only. __Do not use this to harass others.__

        **EXAMPLES:**
        ```bnf
        <1> insult HitchedSyringe
        <2> insult @HitchedSyringe#0598
        <3> insult 140540589329481728
        ```
        """
        if user == ctx.author:
            await ctx.send(
                "Self-deprecation isn't cool.\nInsult somebody besides yourself."
            )
        elif user == ctx.me:
            await ctx.send(
                "How original. No one else had thought of trying to get me to insult myself."
                " I applaud your creativity. \N{YAWNING FACE}\nPerhaps the reason you have"
                " no friends is that you add nothing new to any conversation. You are more"
                " of a bot than I, giving predictable answers and being absolutely dull to"
                " have an actual conversation with."
            )
        else:
            insult = await ctx.get("https://evilinsult.com/generate_insult.php?lang=en")

            await ctx.send(
                f"{user.mention} {insult}\n`Powered by evilinsult.com`",
                allowed_mentions=discord.AllowedMentions(users=False),
            )

    @commands.command()
    @commands.guild_only()
    async def iq(
        self, ctx: SleepyContext, *, user: discord.Member = commands.Author
    ) -> None:
        """Calculates a user's IQ.
        100% accurate or your money back.

        User can either be a name, ID, or mention.

        If no user is specified, then your own IQ
        will be calculated instead.

        **EXAMPLES:**
        ```bnf
        <1> rate HitchedSyringe
        <2> rate @HitchedSyringe#0598
        <3> rate 140540589329481728
        ```
        """
        if await ctx.bot.is_owner(user) or user == ctx.me:
            iq = 1000
        else:
            iq = randint(0, 1000, seed=user.id)

        await ctx.send(
            f"{user.mention} has at least **{iq}** IQ.",
            allowed_mentions=discord.AllowedMentions(users=False),
        )

    @commands.command()
    async def owoify(
        self, ctx: SleepyContext, *, text: Annotated[str, commands.clean_content]
    ) -> None:
        """OwOifies some text.

        **EXAMPLE:**
        ```
        owoify hello there!
        ```
        """
        for regex, replacement in OWO_TRANSLATIONS.items():
            text = regex.sub(replacement, text)

        if len(text) < 2000:
            await ctx.send(text)
        else:
            # This was physically painful to write out.
            await ctx.send("The wesuwt is too wong to post. OwO *nuzzles you*.")

    # At least you won't have to try to be featured on LWIAY.
    @commands.command(aliases=("dongsize", "dicksize", "peensize", "ppsize"))
    @commands.guild_only()
    async def penissize(
        self, ctx: SleepyContext, *, user: discord.Member = commands.Author
    ) -> None:
        """Calculates a user's pp length. 100% accurate or your money back.

        User can either be a name, ID, or mention.

        If no user is specified, then your own pp length will be calculated
        instead.

        **EXAMPLES:**
        ```bnf
        <1> penissize HitchedSyringe
        <2> penissize @HitchedSyringe#0598
        <3> penissize 140540589329481728
        ```
        """
        if await ctx.bot.is_owner(user) or user == ctx.me:
            # haha guys i'm so funny and original i should really be a comedian.
            await ctx.send("The result is too long to post.")
        else:
            shaft = "=" * randint(0, 40, seed=user.id)

            await ctx.send(
                f"{user.mention}'s penis length: `8{shaft}D`",
                allowed_mentions=discord.AllowedMentions(users=False),
            )

    @commands.command()
    async def picknumber(
        self,
        ctx: SleepyContext,
        minimum: commands.Range[int, -1_000_000_000],
        maximum: commands.Range[int, None, 1_000_000_000],
    ) -> None:
        """Picks a random number between a given minimum and maximum, inclusive.

        The widest possible range is ±1000000000, inclusive.

        **EXAMPLE:**
        ```
        picknumber 1 10
        ```
        """
        if minimum >= maximum:
            await ctx.send("The maximum value must be greater than the minimum value.")
        else:
            await ctx.send(f"You got **{random.randint(minimum, maximum)}**!")

    @commands.command(usage="prompt: <prompt> <choice: <choice>...>")
    @commands.guild_only()  # No need to have instances running in DMs.
    @commands.bot_has_permissions(embed_links=True)
    @commands.cooldown(1, 25, commands.BucketType.member)
    async def poll(self, ctx: SleepyContext, *, options: PollFlags) -> None:
        """Creates a quick dropdown-based poll.

        Users will have 1 minute to vote before the poll closes.

        This command's interface is similar to Discord's slash commands.

        Options can be given in any order. **All options are required.**

        The following options are valid:

        `prompt: <prompt>`
        > What users will be voting on, i.e. the topic.
        > This cannot exceed 1000 characters.
        `<choice: <choice>...>`
        > The choices to choose from.
        > Choices must be explicitly prefixed with `choice:`, e.g.
        > `choice: apple choice: orange choice: None of the above.`
        > Between 2 and 15 unique choices, inclusive, are required.
        > Each choice must not exceed 100 characters.
        > Duplicate choices are automatically filtered out.

        (Bot Needs: Embed Links)
        """
        unique = frozenset(options.choices)

        if len(unique) >= 2:
            poll = PollView(starter=ctx.author, prompt=options.prompt, choices=unique)
            await poll.send_to(ctx)
        else:
            await ctx.send("Polls must have a minimum of 2 unique choices.")
            ctx._refund_cooldown_token()

    @commands.command(aliases=("expression",))
    async def quote(self, ctx: SleepyContext) -> None:
        """Shows a random inspiring expression/quote."""
        data = await ctx.get(
            "https://api.forismatic.com/api/1.0/?method=getQuote&format=json&lang=en"
        )

        await ctx.send(
            f"> {data['quoteText']}\n- {data['quoteAuthor'] or 'Unknown'}"
            "\n`Powered by forismatic.com`"
        )

    @commands.command()
    @commands.guild_only()
    async def rate(
        self, ctx: SleepyContext, *, user: discord.Member = commands.Author
    ) -> None:
        """Rates a user out of 10. 100% accurate or your money back.

        User can either be a name, ID, or mention.

        If no user is specified, then you will be rated instead.

        **EXAMPLES:**
        ```bnf
        <1> rate HitchedSyringe
        <2> rate @HitchedSyringe#0598
        <3> rate 140540589329481728
        ```
        """
        if await ctx.bot.is_owner(user) or user == ctx.me:
            rate = 10
        else:
            rate = randint(0, 10, seed=user.id)

        await ctx.send(
            f"I would give {user.mention} a **{rate}/10**!",
            allowed_mentions=discord.AllowedMentions(users=False),
        )

    @commands.command(aliases=("rps",))
    async def rockpaperscissors(
        self, ctx: SleepyContext, choice: Annotated[str, str.lower]
    ) -> None:
        """Play a game of rock paper scissors against yours truly.

        **EXAMPLE:**
        ```
        rockpaperscissors rock
        ```
        """
        items = ("rock", "paper", "scissors")

        if choice not in items:
            await ctx.send("Choice must be either `rock`, `paper`, or `scissors`.")
            return

        bot_choice = random.choice(items)

        if bot_choice == choice:
            await ctx.send("We both tied.")
        elif items[items.index(choice) - 1] == bot_choice:
            await ctx.send(f"Your `{choice}` beats my `{bot_choice}`, you win!")
        else:
            await ctx.send(f"My `{bot_choice}` beats your `{choice}`, I win!")

    @commands.command(aliases=("rolldie",))
    async def rolldice(
        self, ctx: SleepyContext, sides: commands.Range[int, 3, 120] = 6
    ) -> None:
        """Rolls a die with a given amount of sides.

        The die must have between 3 and 120 sides, inclusive.
        By default, this rolls 6-sided die.

        **EXAMPLE:**
        ```
        rolldice 12
        ```
        """
        await ctx.send(f"You rolled a **{random.randint(1, sides)}**!")

    @commands.command()
    @commands.bot_has_permissions(embed_links=True)
    async def say(
        self, ctx: SleepyContext, *, content: commands.Range[str, 1, 2048]
    ) -> None:
        """Lets me speak on your behalf.

        This command only accepts and displays text.
        Any file attachments will be ignored.

        (Bot needs: Embed Links)

        **EXAMPLE:**
        ```
        say hello world!
        ```
        """
        embed = Embed(
            colour=0x2F3136,
            description=content,
            timestamp=ctx.message.created_at or ctx.message.edited_at,
        )
        embed.set_author(
            name=f"{ctx.author} (ID: {ctx.author.id})", icon_url=ctx.author.display_avatar
        )
        embed.set_footer(
            text="This message is user-generated and does not reflect "
            f"the views or values of {ctx.me.name}."
        )

        await ctx.send(embed=embed)

        try:
            await ctx.message.delete()
        except discord.HTTPException:
            pass

    @commands.command()
    async def sheriff(self, ctx: SleepyContext, *, emote: EmoteData) -> None:
        """ "howdy. i'm the sheriff of ___\\_\\_\\_"

        **EXAMPLES:**
        ```bnf
        <1> sheriff \N{FACE WITH TEARS OF JOY}
        <2> sheriff :custom_emoji:
        <3> sheriff =
        ```
        """
        char = emote.char

        content = escape_markdown(
            f"⠀ ⠀ ⠀  \N{FACE WITH COWBOY HAT}\n　   {char * 3}\n"
            f"    {char}   {char}　{char}\n"
            f"   \N{WHITE DOWN POINTING BACKHAND INDEX}   {char * 2} "
            f"\N{WHITE DOWN POINTING BACKHAND INDEX}\n  　  {char}　"
            f"{char}\n　   {char}　 {char}\n"
            f"　   \N{WOMANS BOOTS}     \N{WOMANS BOOTS}\n"
            f"howdy. i'm the sheriff of {emote.name.lower().replace('_', ' ')}"
        )

        if len(content) < 2000:
            await ctx.send(content)
        else:
            await ctx.send("The result is too long to post.")

    @commands.command()
    async def uselessfact(self, ctx: SleepyContext) -> None:
        """Gives an utterly useless and pointless fact."""
        resp = await ctx.get("https://useless-facts.sameerkumar.website/api")

        await ctx.send(f"{resp['data']}\n`Powered by sameerkumar.website`")

    @commands.command(aliases=("yomama",))
    @commands.guild_only()
    async def yomomma(self, ctx: SleepyContext, *, user: discord.Member) -> None:
        """Makes an insulting joke about a user's mom.

        It literally just tells a yo momma joke.

        User can either be a name, ID, or mention.

        **Disclaimer:** This command was made for entertainment
        purposes only. __Do not use this to harass others.__

        **EXAMPLES:**
        ```bnf
        <1> yomomma HitchedSyringe
        <2> yomomma @HitchedSyringe#0598
        <3> yomomma 140540589329481728
        ```
        """
        if user == ctx.author:
            await ctx.send("Hey! Don't make fun of your own mom!")
        elif user == ctx.me:
            await ctx.send(
                "How original, trying to make me insult my own mom. "
                "You really must be some kind of comedic genius."
            )
        else:
            resp = await ctx.get("https://api.yomomma.info/")

            await ctx.send(
                f"{user.mention} {resp['joke']}\n`Powered by yomomma.info`",
                allowed_mentions=discord.AllowedMentions(users=False),
            )


async def setup(bot: Sleepy) -> None:
    await bot.add_cog(Fun())
