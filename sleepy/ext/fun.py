"""
Copyright (c) 2018-present HitchedSyringe

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""


import colorsys
import io
import json
import random
import re
import unicodedata
from collections import Counter
from typing import Optional

import discord
import emoji
import pyfiglet
from discord import Embed, File
from discord.ext import commands, menus
from PIL import Image, ImageDraw
from sleepy import checks
from sleepy.converters import _pseudo_argument_flag
from sleepy.utils import (
    awaitable,
    measure_performance,
    plural,
    randint as s_randint,
    tchart,
)


# + is positive, - is negative, no sign is neutral.
BALL_RESPONSES = (
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
OWO_TRANSLATIONS = {
    re.compile(r"[lr]"): "w",
    re.compile(r"[LR]"): "W",
    re.compile(r"([Nn])([aeiou])"): "\\1y\\2",
    re.compile(r"([Nn])([AEIOU])"): "\\1Y\\2",
    re.compile(r"([ao])^[a-zA-Z]"): "h\\1",
    re.compile(r"([AO])^[a-zA-Z]"): "H\\1",
}


class resolve_emote_char(commands.Converter):

    @staticmethod
    async def convert(ctx, argument):
        argument = await commands.clean_content().convert(ctx, argument)

        try:
            emoji_name = emoji.UNICODE_EMOJI_ENGLISH[argument]
        except KeyError:
            pass
        else:
            return argument, emoji_name.strip(":")

        if len(argument) == 1:
            return argument, unicodedata.name(argument, "unknown emote")

        try:
            custom = commands.PartialEmojiConverter().convert(ctx, argument)
        except commands.PartialEmojiConversionFailure:
            pass
        else:
            # Assume that we can use this emoji.
            return custom.name, str(custom)

        return argument, "unknown emote"


class PollMenu(menus.Menu):

    def __init__(self, question, options):
        super().__init__(timeout=60, delete_message_after=True)

        self.__options = {}

        for i, option in enumerate(options, 1):
            # NOTE: This will break if there are more than 10 options.
            emoji = "\N{KEYCAP TEN}" if i == 10 else f"{i}\ufe0f\N{COMBINING ENCLOSING KEYCAP}"

            self.__options[emoji] = option
            self.add_button(menus.Button(emoji, self.record_poll_vote))

        self.votes = Counter()
        self.question = question

    def reaction_check(self, payload):
        return payload.message_id == self.message.id and payload.user_id != self.ctx.me.id

    # I'm not gonna bother tracking whether the user
    # has already voted or not since it's not only a
    # pain in the neck to do, but it also may provide
    # some kind of vector for a memory leak depending
    # on how many users are interacting with this.
    async def record_poll_vote(self, payload):
        try:
            option = self.__options[payload.emoji.name]
        except KeyError:
            return

        if payload.event_type == "REACTION_ADD":
            self.votes[option] += 1
        elif payload.event_type == "REACTION_REMOVE":
            self.votes[option] -= 1

    async def send_initial_message(self, ctx, channel):
        embed = Embed(
            title="React with one of the following to cast your vote!",
            description="\n".join(f"{e}: {c}" for e, c in self.__options.items()),
            colour=0x2F3136
        )
        embed.set_footer(text="You have 1 minute to cast your vote.")

        return await channel.send(content=self.question, embed=embed)

    async def finalize(self, timed_out):
        if (votes := +self.votes):
            embed = Embed(
                title="Voting has concluded and the results are in!",
                description=f"```\n{tchart(dict(votes.most_common()))}```",
                colour=0x2F3136
            )
            embed.set_footer(
                text=f"{plural(sum(votes.values()), ',d'):vote} casted."
                     f" \N{BULLET} Started by: {self.ctx.author}"
            )
        else:
            embed = Embed(
                title="Voting has concluded and... nobody casted a vote?",
                description="The point of this was to cast a vote, you know.",
                colour=0x2F3136
            )
            embed.set_footer(text=f"Started by: {self.ctx.author}")

        await self.ctx.send(self.question, embed=embed)


class Fun(
    commands.Cog,
    command_attrs={"cooldown": commands.Cooldown(2, 5, commands.BucketType.member)}
):
    """Commands provided for your entertainment and not to be taken seriously.

    ||This totally isn't a dumping ground for janky commands! Not at all!||
    """

    def __init__(self):
        # This is here to create our own asynchronous and
        # performance-measured instance of figlet_format
        # without actually modifying the normal global one.
        self.figlet_format = awaitable(measure_performance(pyfiglet.figlet_format))

    @staticmethod
    @awaitable
    def create_colour_preview(colour):
        buffer = io.BytesIO()

        image = Image.new("RGBA", (256, 256))
        ImageDraw.Draw(image).regular_polygon((128, 128, 127), 4, 45, colour)

        image.save(buffer, "png")

        buffer.seek(0)

        return buffer

    @commands.command(name="8ball")
    async def _8ball(self, ctx, *, question: commands.clean_content):
        """Asks the magic 8 ball a question.

        **EXAMPLE:**
        ```
        8ball Am I the fairest of them all?
        ```
        """
        q_length = len(question)

        if q_length > 1500:
            await ctx.send(f"Your question is too long. ({q_length} > 1500)")
        else:
            await ctx.send(f"{question}```diff\n{random.choice(BALL_RESPONSES)}```")

    @commands.command()
    async def advice(self, ctx):
        """Gives some advice."""
        resp = await ctx.get("https://api.adviceslip.com/advice")
        data = json.loads(resp)

        await ctx.send(f"{data['slip']['advice']}\n`Powered by adviceslip.com`")

    @commands.command(aliases=("asskeyart", "figlet"))
    @commands.cooldown(1, 5, commands.BucketType.member)
    async def asciiart(
        self,
        ctx,
        font: Optional[_pseudo_argument_flag("--font")] = None,
        *,
        text: commands.clean_content(fix_channel_mentions=True)
    ):
        """Generates ASCII art out of the given text.

        By default, this chooses a random font to render
        the text with. To specify a font to render with,
        prefix the font name with `--font=` prior to the
        text argument.

        For a list of valid font names, refer to:
        <https://artii.herokuapp.com/fonts_list>

        **EXAMPLE:**
        ```bnf
        <1> asciiart hello there!
        <2> asciiart --font=taxi____ woah, cool!
        ```
        """
        font = random.choice(pyfiglet.FigletFont.getFonts()) if font is None else font.lower()

        try:
            output, delta = await self.figlet_format(text, font)
        except pyfiglet.FontNotFound:
            await ctx.send("That font wasn't found.")
            return

        if not output:
            await ctx.send("Sorry, but my renderer doesn't support the given text.")
            return

        content = (
            f"Requested by: {ctx.author} \N{BULLET} Font: `{font}` "
            f"\N{BULLET} Took {delta:.2f} ms\n```\n{output}```"
        )

        if len(content) < 2000:
            await ctx.send(content)
        else:
            await ctx.send("The result is too long to post.")

    @commands.group(name="choose", invoke_without_command=True)
    async def choose(self, ctx, *choices: commands.clean_content):
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
        ctx,
        times: Optional[int],
        *choices: commands.clean_content
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
        elif not 0 < times <= 10001:
            await ctx.send("Times must be between 1 and 10001, inclusive.")
            return

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
    async def chucknorris(self, ctx):
        """Tells a Chuck Norris joke/fact."""
        resp = await ctx.get("https://api.icndb.com/jokes/random?escape=javascript")

        await ctx.send(f"{resp['value']['joke']}\n`Powered by icndb.com`")

    @commands.command()
    async def clap(self, ctx, *, text: commands.clean_content):
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
    async def colour(self, ctx, *, colour: discord.Colour = None):
        """Shows a representation of a given colour.

        Colour can either be a name, 6 digit hex value
        prefixed with either a `0x`, `#`, or `0x#`; or
        CSS RGB function (e.g. `rgb(103, 173, 242)`).

        For a list of valid colour names, refer to:
        <https://discordpy.readthedocs.io/en/latest/api.html#discord.Colour>

        If no colour is given, then a random colour will
        be shown instead.

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
    async def compliment(self, ctx, *, user: discord.Member):
        """Compliments a user.

        User can either be a name, ID, or mention.

        **EXAMPLES:**
        ```bnf
        <1> compliment HitchedSyringe
        <2> compliment @HitchedSyringe#0598
        <3> compliment 140540589329481728
        ```
        """
        if user == ctx.author:
            await ctx.send("Stop trying to boost your fragile ego.")
        else:
            resp = await ctx.get("https://complimentr.com/api")

            await ctx.send(
                f"{user.mention} {resp['compliment']}.\n`Powered by complimentr.com`",
                allowed_mentions=discord.AllowedMentions(users=False)
            )

    @commands.command(aliases=("pun",))
    async def dadjoke(self, ctx):
        """Tells a dad joke (or a pun, whatever you want to call it.)"""
        resp = await ctx.get(
            "https://icanhazdadjoke.com/",
            headers__={"Accept": "application/json"}
        )

        await ctx.send(f"{resp['joke']}\n`Powered by icanhazdadjoke.com`")

    @commands.command(aliases=("emojidick", "emojidong", "emojipp"))
    async def emojipenis(self, ctx, *, emote: resolve_emote_char):
        """"___\\_\\_\\_ penis"

        **EXAMPLES:**
        ```bnf
        <1> emojipenis \N{AUBERGINE}
        <2> emojipenis :custom_emoji:
        <3> emojipenis =
        ```
        """
        char, name = emote

        content = (
            f"{name.lower().replace('_', ' ')} penis\n"
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
    async def emojivagina(self, ctx, *, emote: resolve_emote_char):
        """"___\\_\\_\\_ vagina"

        **EXAMPLES:**
        ```bnf
        <1> emojivagina \N{MOUTH}
        <2> emojivagina :custom_emoji:
        <3> emojivagina =
        ```
        """
        char, name = emote

        content = (
            f"{name.lower().replace('_', ' ')} vagina\n"
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
    async def fight(self, ctx, *, user: discord.Member):
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
                allowed_mentions=discord.AllowedMentions(users=False)
            )
        elif random.random() < 0.5:
            await ctx.send(
                f"You fought {user.mention} and whooped them.",
                allowed_mentions=discord.AllowedMentions(users=False)
            )
        else:
            await ctx.send(
                f"You fought {user.mention} and got your nose bloodied.\nGo see a doctor.",
                allowed_mentions=discord.AllowedMentions(users=False)
            )

    @commands.command()
    async def flipcoin(self, ctx):
        """Flips a coin."""
        await ctx.send(f"You flipped **{'Heads' if random.random() < 0.5 else 'Tails'}**!")

    @commands.command(aliases=("bored", "boredidea"))
    @commands.bot_has_permissions(embed_links=True)
    async def idea(self, ctx):
        """Gives you something to do for when you're bored."""
        data = await ctx.get("http://boredapi.com/api/activity/")

        await ctx.send(data["activity"] + ".\n`Powered by boredapi.com`")

    @commands.command(aliases=("roast",))
    @commands.guild_only()
    async def insult(self, ctx, *, user: discord.Member):
        """Insults someone.

        User can either be a name, ID, or mention.

        **Disclaimer:** This command was made for
        the purpose of entertainment only. Please
        do **not** use this to harass others.

        **EXAMPLES:**
        ```bnf
        <1> insult HitchedSyringe
        <2> insult @HitchedSyringe#0598
        <3> insult 140540589329481728
        ```
        """
        if user == ctx.author:
            await ctx.send("Self-deprecation isn't cool.\nInsult somebody besides yourself.")
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
                allowed_mentions=discord.AllowedMentions(users=False)
            )

    @commands.command()
    @commands.guild_only()
    async def iq(self, ctx, *, user: discord.Member = None):
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
        if user is None:
            user = ctx.author

        if await ctx.bot.is_owner(user) or user == ctx.me:
            iq = 1000
        else:
            iq = s_randint(0, 1000, seed=user.id)

        await ctx.send(
            f"{user.mention} has at least **{iq}** IQ.",
            allowed_mentions=discord.AllowedMentions(users=False)
        )

    @commands.command()
    async def owoify(self, ctx, *, text: commands.clean_content):
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
    async def penissize(self, ctx, *, user: discord.Member = None):
        """Calculates a user's pp length.
        100% accurate or your money back.

        User can either be a name, ID, or mention.

        If no user is specified, then your own pp
        length will be calculated instead.

        **EXAMPLES:**
        ```bnf
        <1> penissize HitchedSyringe
        <2> penissize @HitchedSyringe#0598
        <3> penissize 140540589329481728
        ```
        """
        if user is None:
            user = ctx.author

        if await ctx.bot.is_owner(user) or user == ctx.me:
            # haha guys i'm so funny and original i should really be a comedian.
            await ctx.send("The result is too long to post.")
        else:
            await ctx.send(
                f"{user.mention}'s penis length: `8{'=' * s_randint(0, 40, seed=user.id)}D`",
                allowed_mentions=discord.AllowedMentions(users=False)
            )

    @commands.command()
    async def picknumber(self, ctx, minimum: int, maximum: int):
        """Picks a random number between a given minimum and maximum, inclusive.

        The hard range is ±1000000000, inclusive.

        **EXAMPLE:**
        ```
        picknumber 1 10
        ```
        """
        if minimum < -1_000_000_000 or maximum > 1_000_000_000:
            await ctx.send("Range must fall between ±1000000000, inclusive.")
        elif minimum >= maximum:
            await ctx.send("The maximum value must be greater than the minimum value.")
        else:
            await ctx.send(f"You got **{random.randint(minimum, maximum)}**!")

    @commands.command()
    @commands.guild_only()  # Wouldn't make sense to have instances running in DMs.
    @checks.can_start_menu(check_embed=True)
    @commands.cooldown(1, 5, commands.BucketType.member)
    async def poll(self, ctx, question: commands.clean_content, *options):
        """Creates a quick reaction-based voting poll.

        Users will have 60 seconds to cast their vote before
        the poll closes. Note that this does **NOT** prevent
        users from voting twice.

        Quotation marks must be used for values containing
        spaces.

        (Bot Needs: Embed Links, Add Reactions, and Read Message History)

        **EXAMPLE:**
        ```
        poll "What colour is the sky?" blue red "What is the sky?"
        ```
        """
        if not 2 <= len(options) <= 10:
            await ctx.send("You must have between 2 and 10 options, inclusive.")
            return

        q_length = len(question)

        if q_length < 1500:
            await PollMenu(question, options).start(ctx)
        else:
            await ctx.send(f"The poll question is too long. ({q_length} > 1500)")

    @commands.command(aliases=("expression",))
    async def quote(self, ctx):
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
    async def rate(self, ctx, *, user: discord.Member = None):
        """Rates a user out of 10.
        100% accurate or your money back.

        User can either be a name, ID, or mention.

        If no user is specified, then you will be
        rated instead.

        **EXAMPLES:**
        ```bnf
        <1> rate HitchedSyringe
        <2> rate @HitchedSyringe#0598
        <3> rate 140540589329481728
        ```
        """
        if user is None:
            user = ctx.author

        if await ctx.bot.is_owner(user) or user == ctx.me:
            rate = 10
        else:
            rate = s_randint(0, 10, seed=user.id)

        await ctx.send(
            f"I would give {user.mention} a **{rate}/10**!",
            allowed_mentions=discord.AllowedMentions(users=False)
        )

    @commands.command(aliases=("rps",))
    async def rockpaperscissors(self, ctx, choice: str.lower):
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
    async def rolldice(self, ctx, sides: int = 6):
        """Rolls a die with a given amount of sides.

        The die must have between 3 and 120 sides, inclusive.
        By default, this rolls 6-sided die.

        **EXAMPLE:**
        ```
        rolldice 12
        ```
        """
        if not 3 <= sides <= 120:
            await ctx.send("Sides must be greater than 3 and less than 120.")
        else:
            await ctx.send(f"You rolled a **{random.randint(1, sides)}**!")

    @commands.command()
    @commands.bot_has_permissions(embed_links=True)
    async def say(self, ctx, *, content):
        """Lets me speak on your behalf.

        This command only accepts and displays text.
        Any file attachments will be ignored.

        (Bot needs: Embed Links)

        **EXAMPLE:**
        ```
        say hello world!
        ```
        """
        # Thanks Discord Nitro.
        if len(content) > 2048:
            await ctx.send("The message is too long to post.")
            return

        embed = Embed(
            colour=0x2F3136,
            description=content,
            timestamp=ctx.message.created_at or ctx.message.edited_at
        )
        embed.set_author(
            name=f"{ctx.author} (ID: {ctx.author.id})",
            icon_url=ctx.author.avatar_url
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
    async def sheriff(self, ctx, *, emote: resolve_emote_char):
        """"howdy. i'm the sheriff of ___\\_\\_\\_"

        **EXAMPLES:**
        ```bnf
        <1> sheriff \N{FACE WITH TEARS OF JOY}
        <2> sheriff :custom_emoji:
        <3> sheriff =
        ```
        """
        char, name = emote

        content = (
            f"⠀ ⠀ ⠀  \N{FACE WITH COWBOY HAT}\n　   {char * 3}\n"
            f"    {char}   {char}　{char}\n"
            f"   \N{WHITE DOWN POINTING BACKHAND INDEX}   {char * 2} "
            f"\N{WHITE DOWN POINTING BACKHAND INDEX}\n  　  {char}　"
            f"{char}\n　   {char}　 {char}\n"
            f"　   \N{WOMANS BOOTS}     \N{WOMANS BOOTS}\n"
            f"howdy. i'm the sheriff of {name.lower().replace('_', ' ')}"
        )

        if len(content) < 2000:
            await ctx.send(content)
        else:
            await ctx.send("The result is too long to post.")

    @commands.command()
    async def uselessfact(self, ctx):
        """Gives an utterly useless and pointless fact."""
        resp = await ctx.get("https://useless-facts.sameerkumar.website/api")

        await ctx.send(f"{resp['data']}\n`Powered by sameerkumar.website`")

    @commands.command(aliases=("yomama",))
    @commands.guild_only()
    async def yomomma(self, ctx, *, user: discord.Member):
        """Makes an insulting joke about a user's mom.

        It literally just tells a yo momma joke.

        User can either be a name, ID, or mention.

        **Disclaimer:** This command was made for
        the purpose of entertainment only. Please
        do **not** use this to harass others.

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
                allowed_mentions=discord.AllowedMentions(users=False)
            )


def setup(bot):
    bot.add_cog(Fun())
