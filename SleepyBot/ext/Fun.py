"""
© Copyright 2018-2020 HitchedSyringe, All Rights Reserved.

Redistributing, using or owning a copy of this software without explicit permissions
is against these licensing terms, your license(s) to this software can be revoked at
any time without explicit notice beforehand and at the time of revocation.
Your license is non-transferrable, the terms of this license only permit you to do the
following; Create pull requests and make modifications to this repository.

"""


import json
import random
import re
import unicodedata
from collections import Counter
from typing import Optional

import discord
import emoji
from discord import Embed
from discord.ext import commands, menus
from discord.utils import escape_mentions

from SleepyBot.utils import checks, converters, formatting
from SleepyBot.utils.requester import HTTPError


# + is positive, - is negative, no sign is neutral.
EIGHT_BALL_RESPONSES = (
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


# item: defeated by
RPS_MATCHES = {
    "rock": "paper",
    "paper": "scissors",
    "scissors": "rock",
}


CUSTOM_EMOJI_REGEX = re.compile(r"<(?:a?):([\w_]+):(?:\d+)>")


def _resolve_char(value: str) -> tuple:
    """Resolves the name of a character.
    We first do a lookup for unicodes, then custom emotes and finally, everything else.
    Returns a Tuple[:class:`str`, :class:`str`] containing the raw character and name.
    If the name can't be resolved, then the returned name is \"unknown emote\".
    For internal use only.
    """
    emote_name = emoji.UNICODE_EMOJI.get(value)
    if emote_name is not None:
        return (value, emote_name.strip(":"))

    custom_match = CUSTOM_EMOJI_REGEX.fullmatch(value)
    if custom_match is not None:
        # Just assume here that we can use this emoji.
        return (value, custom_match.group(1))

    if len(value) == 1:
        return (value, unicodedata.name(value, "unknown emote"))

    return (value, "unknown emote")


class PollMenu(menus.Menu):
    """A menu implementation that allows users to vote through reactions.
    This counts up the votes and shows the results upon closure.
    """
    BUTTON_EMOJIS = (
        "\N{DIGIT ONE}\ufe0f\N{COMBINING ENCLOSING KEYCAP}",
        "\N{DIGIT TWO}\ufe0f\N{COMBINING ENCLOSING KEYCAP}",
        "\N{DIGIT THREE}\ufe0f\N{COMBINING ENCLOSING KEYCAP}",
        "\N{DIGIT FOUR}\ufe0f\N{COMBINING ENCLOSING KEYCAP}",
        "\N{DIGIT FIVE}\ufe0f\N{COMBINING ENCLOSING KEYCAP}",
        "\N{DIGIT SIX}\ufe0f\N{COMBINING ENCLOSING KEYCAP}",
        "\N{DIGIT SEVEN}\ufe0f\N{COMBINING ENCLOSING KEYCAP}",
        "\N{DIGIT EIGHT}\ufe0f\N{COMBINING ENCLOSING KEYCAP}",
        "\N{DIGIT NINE}\ufe0f\N{COMBINING ENCLOSING KEYCAP}",
        "\N{KEYCAP TEN}",
    )


    def __init__(self, question, *options):
        super().__init__(timeout=60, delete_message_after=True)

        # The reason we map buttons to options instead of emoji to options is because
        # these numerical keycap buttons may return differently in payload.emoji.
        # Since the emoji-button mapping is a bit more reliable, we'll just create a button-option
        # mapping in order to spare us the headache of having to deal with these unicodes.
        self._options_mapping = {}

        for index, option in enumerate(options):
            # The position kwarg ensures that buttons are reacted in numerical order.
            button = menus.Button(self.BUTTON_EMOJIS[index], self.record_poll_vote, position=menus.Last(2))
            self._options_mapping[button] = option
            self.add_button(button)

        self.votes = Counter()
        self._question = question


    def reaction_check(self, payload):
        return payload.message_id == self.message.id and payload.user_id != self.ctx.me.id


    # I'm not gonna bother tracking whether the user already casted a vote or not.
    # It's a pain in the neck to do and the implementation is pretty messy as a whole.
    async def record_poll_vote(self, payload):
        option = self._options_mapping[self.buttons[payload.emoji]]
        if payload.event_type == "REACTION_ADD":
            self.votes[option] += 1
        elif payload.event_type == "REACTION_REMOVE":
            self.votes[option] -= 1


    async def send_initial_message(self, ctx, channel):
        embed = Embed(
            title="React with one of the following to cast your vote!",
            description="\n".join(f"{b.emoji}: {o}" for b, o in self._options_mapping.items()),
            colour=0x2F3136
        )
        embed.set_footer(text="Results will be shown after the 1 minute voting period has ended.")

        return await ctx.send(content=self._question, embed=embed)


    async def finalize(self, timed_out):
        votes = +self.votes

        embed = Embed(
            title="Voting has concluded and the results are in!",
            colour=0x2F3136
        )

        if votes:
            embed.description = f"```\n{formatting.tchart(votes.most_common())}\n```"
            embed.set_footer(
                text=f"Total: {sum(votes.values())} | Started by: {self.ctx.author} (ID: {self.ctx.author.id})"
            )
        else:
            embed.description = "Looks like nobody casted a single vote..."
            embed.set_footer(text=f"Started by: {self.ctx.author} (ID: {self.ctx.author.id})")

        await self.ctx.send(content=self._question, embed=embed)


class Fun(commands.Cog):
    """Commands that provide a little entertainment for the chat.
    Don't take these too seriously.

    *This totally isn't a dumping ground for all the janky and/or clunky commands.
    """

    # This implementation ensures that a user will always have the same value returned for them.
    # Now users won't be able to roll for a chance to get a bigger penis size or higher IQ score.
    @staticmethod
    def _randint_by_seed(a: int, b: int, *, seed) -> int:
        """Same as :func:`random.randint` but allows for generating with a custom seed.
        For internal use only.
        """
        _previous_state = random.getstate()
        random.seed(seed)
        value = random.randint(a, b)
        random.setstate(_previous_state)

        return value


    @commands.command(name="8ball")
    async def ball8(self, ctx: commands.Context, *, question: commands.clean_content):
        """Asks the magic 8 ball a question.

        EXAMPLE: 8ball Am I the fairest of them all?
        """
        if len(question) > 1500:
            await ctx.send(f"Your question is too long! ({len(question)} > 1500)")
        else:
            await ctx.send(f"{question}\n```diff\n{random.choice(EIGHT_BALL_RESPONSES)}\n```")


    @commands.command(name="ascii", aliases=["asciiart", "asskey"])
    @commands.cooldown(rate=1, per=4, type=commands.BucketType.member)
    async def _ascii(self, ctx: commands.Context, *, text: commands.clean_content(fix_channel_mentions=True)):
        """Generates ASCII art out of the given text using a random font.

        EXAMPLE: ascii hello there!
        """
        await ctx.trigger_typing()
        # We have to get all of the fonts in order to use random fonts.
        fonts = await ctx.get("https://artii.herokuapp.com/fonts_list", cache=True)
        font = random.choice(fonts.split("\n"))

        ascii_text = await ctx.get("https://artii.herokuapp.com/make", text=text, font=font, cache=True)

        output = f"```\n{ascii_text}\nPowered by artii.herokuapp.com | Font: {font}```"
        if len(output) > 2000:
            await ctx.send("The result is too long to post.")
        else:
            await ctx.send(output)


    @commands.command()
    @checks.bot_has_permissions(embed_links=True)
    @commands.cooldown(rate=1, per=5, type=commands.BucketType.member)
    async def caption(self, ctx: commands.Context, image: converters.ImageAssetConverter):
        """Captions an image.
        Image can either be a link or attachment.
        """
        image_url = str(image)

        headers = {
            "Content-Type": "application/json; charset=utf-8"
        }
        payload = {
            "Content": image_url,
            "Type": "CaptionRequest"
        }

        await ctx.trigger_typing()
        try:
            caption = await ctx.post(
                "https://captionbot.azurewebsites.net/api/messages",
                headers__=headers,
                json__=payload
            )
        except HTTPError:
            await ctx.send("Failed to get data.")
        else:
            embed = Embed(title=f'"{caption}"', colour=0x2F3136)
            embed.set_image(url=image_url)
            embed.set_footer(text="Powered by captionbot.azurewebsites.net")
            await ctx.send(embed=embed)


    @caption.error
    async def on_caption_error(self, ctx: commands.Context, error):
        error = getattr(error, "original", error)

        if isinstance(error, commands.BadArgument):
            await ctx.send(str(error))
            error.handled = True


    @commands.command(aliases=["cb"])
    @commands.cooldown(rate=1, per=3, type=commands.BucketType.member)
    async def chatbot(self, ctx: commands.Context, *, message: str):
        """Allows you to interact with a highly intelligent chatbot AI.

        EXAMPLE: chatbot hello there!
        """
        async with ctx.typing():
            chatbot = await ctx.get("https://some-random-api.ml/chatbot", message=message)

        await ctx.send(f"{chatbot['response']}\n`Powered by some-random-api.ml`.")


    @commands.command(aliases=["cnorris"])
    async def chucknorris(self, ctx: commands.Context):
        """Tells a Chuck Norris joke/fact."""
        await ctx.trigger_typing()
        response = await ctx.get("https://api.icndb.com/jokes/random?escape=javascript")

        await ctx.send(f"{response['value']['joke']}\n`Powered by api.icndb.com`")


    @commands.command()
    async def clap(self, ctx: commands.Context, *, text: commands.clean_content):
        """:clap:

        EXAMPLE: clap hello there!
        """
        clapped = re.sub(r"\s", "\N{CLAPPING HANDS SIGN}", text)

        if len(clapped) > 1998:
            await ctx.send("The result is too long to post.")
        else:
            await ctx.send(f"\N{CLAPPING HANDS SIGN}{clapped}\N{CLAPPING HANDS SIGN}")


    @commands.command(aliases=["pun"])
    async def dadjoke(self, ctx: commands.Context):
        """Tells a dad joke (or a pun, whatever you want to call it.)"""
        await ctx.trigger_typing()
        response = await ctx.get("https://icanhazdadjoke.com/", headers__=dict(Accept="application/json"))

        await ctx.send(f"{response['joke']}\n`Powered by icanhazdadjoke.com`")


    @commands.command(aliases=["emojidick", "emojidong", "emojipp", "emojipeen"])
    async def emojipenis(self, ctx: commands.Context, character: commands.clean_content):
        """\\_\\_\\_\\_\\_\\_ penis

        EXAMPLE:
        (Ex. 1) emojipenis :flag_us:
        (Ex. 2) emojipenis :custom_emoji:
        (Ex. 3) emojipenis a
        """
        char_raw, char_name = _resolve_char(character)

        # Thanks @emoji_penis on Twitter.
        base = (
            f"{char_name.lower().replace('_', ' ')} penis",
            f"{char_raw}{char_raw}",
            f"{char_raw}{char_raw}{char_raw}",
            f"  {char_raw}{char_raw}{char_raw}",
            f"    {char_raw}{char_raw}{char_raw}",
            f"     {char_raw}{char_raw}{char_raw}",
            f"       {char_raw}{char_raw}{char_raw}",
            f"        {char_raw}{char_raw}{char_raw}",
            f"         {char_raw}{char_raw}{char_raw}",
            f"          {char_raw}{char_raw}{char_raw}",
            f"          {char_raw}{char_raw}{char_raw}",
            f"      {char_raw}{char_raw}{char_raw}{char_raw}",
            f" {char_raw}{char_raw}{char_raw}{char_raw}{char_raw}{char_raw}",
            f" {char_raw}{char_raw}{char_raw}  {char_raw}{char_raw}{char_raw}",
            f"    {char_raw}{char_raw}       {char_raw}{char_raw}",
        )

        content = "\n".join(base)

        if len(content) > 2000:
            await ctx.send("The result is too long to post. (Pun intended)")
        else:
            await ctx.send(content)


    @commands.command(aliases=["fite", "1v1"])
    @commands.guild_only()
    async def fight(self, ctx: commands.Context, user: discord.Member):
        """Fights someone.

        EXAMPLE:
        (Ex. 1) fight HitchedSyringe
        (Ex. 2) fight @HitchedSyringe#0598
        (Ex. 3) fight 140540589329481728
        """
        if user == ctx.author:
            await ctx.send("You look stupid trying to fight yourself.")
            return

        display_name = escape_mentions(user.display_name)

        if user.id in ctx.bot.owner_ids or user == ctx.me:
            await ctx.send(f"You got into a fight with {display_name} and got erased from existence.")
            return

        if random.randint(0, 1) == 1:
            await ctx.send(f"You got into a fight with {display_name} and whooped him.")
        else:
            await ctx.send(
                f"You got into a fight with {display_name} and got your nose bloodied.\nMaybe get that checked up?"
            )


    @commands.command()
    @commands.guild_only()
    @commands.cooldown(rate=1, per=3, type=commands.BucketType.member)
    async def insult(self, ctx: commands.Context, user: discord.Member):
        """Insults someone.

        EXAMPLE:
        (Ex. 1) insult HitchedSyringe
        (Ex. 2) insult @HitchedSyringe#0598
        (Ex. 3) insult 140540589329481728
        """
        if user == ctx.author:
            await ctx.send("This isn't a command for self-deprecation.\nInsult somebody besides yourself.")
            return

        if user == ctx.me:
            await ctx.send(
                "How original. No one else had thought of trying to get the bot to insult itself. "
                "I applaud your creativity. *yawn*\nPerhaps this is why you don't have friends: "
                "you don't add anything new to the conversation and are more of a bot than I, giving "
                "predictable answers, and being absolutely dull to have an actual conversation with."
            )
            return

        await ctx.trigger_typing()
        # We could either have a tuple somewhere full of insults that have zero proof I wrote them
        # or insults that aren't original and have a slight chance of being awful, but aren't hardcoded at all.
        # tbh, I'd choose the latter.
        response = await ctx.get("https://evilinsult.com/generate_insult.php", lang="en", type="json")

        data = json.loads(response)
        await ctx.send(f"{escape_mentions(user.display_name)}: {data['insult']}\n`Powered by evilinsult.com`")


    @commands.command()
    @commands.guild_only()
    async def iq(self, ctx: commands.Context, user: discord.Member = None):
        """Calculates a user's IQ.
        If no user is specified, then your own IQ will be calculated instead.
        100% accurate or your money back.

        EXAMPLE:
        (Ex. 1) rate HitchedSyringe
        (Ex. 2) rate @HitchedSyringe#0598
        (Ex. 3) rate 140540589329481728
        """
        if user is None:
            user = ctx.author

        if user.id in ctx.bot.owner_ids or user == ctx.me:
            iq = 1000
        else:
            iq = self._randint_by_seed(0, 1000, seed=user.id)

        await ctx.send(f"{escape_mentions(user.display_name)}'s IQ is at least **{iq} points**.")


    # At least you won't have to try to be featured on LWIAY.
    @commands.command(aliases=["dongsize", "dicksize", "peensize", "ppsize"])
    @commands.guild_only()
    async def penissize(self, ctx: commands.Context, user: discord.Member = None):
        """Gets a user's pp length.
        If no user is specified, then your own pp length will be calculated instead.
        100% accurate or your money back.

        EXAMPLE:
        (Ex. 1) penissize HitchedSyringe
        (Ex. 2) penissize @HitchedSyringe#0598
        (Ex. 3) penissize 140540589329481728
        """
        if user is None:
            user = ctx.author

        if user.id in ctx.bot.owner_ids or user == ctx.me:
            # haha guys i'm so funny and original i should really be a comedian.
            await ctx.send("The result is too long to post.")
        else:
            length = self._randint_by_seed(0, 40, seed=user.id)
            await ctx.send(f"{escape_mentions(user.display_name)}'s penis length: `8{'=' * length}D`")


    @commands.command()
    @commands.guild_only()  # Wouldn't make sense to have instances of these running in DMs.
    @commands.cooldown(rate=1, per=8, type=commands.BucketType.member)
    @checks.bot_has_permissions(embed_links=True, add_reactions=True, read_message_history=True)
    async def poll(self, ctx: commands.Context, question: commands.clean_content, *options: str):
        """Creates a quick voting poll for users to react to.
        Users will have 60 seconds to cast their vote before the poll closes.
        Quotation marks must be used if any arguments have spaces.
        You should note that this does not actively prevent users from voting twice.
        (Bot Needs: Embed Links, Add Reactions and Read Message History)

        EXAMPLE: poll "What colour is the sky?" blue red yellow "The sky does not exist"
        """
        if len(options) < 2:
            await ctx.send("You must have at least 2 options to choose from.")
            return

        if len(options) > 10:
            await ctx.send("You can only have up to 10 options.")
            return

        if len(question) > 1500:
            await ctx.send(f"The question is too long to post. ({len(question)} > 1500)")
            return

        poll = PollMenu(question, *options)
        await poll.start(ctx)


    @commands.group(name="random")
    async def _random(self, ctx: commands.Context):
        """A group of commands that provide some pseudo-randomness."""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)


    @_random.command(name="choose")
    async def random_choose(self, ctx: commands.Context, *choices: commands.clean_content):
        """Randomly chooses between multiple choices.
        Quotation marks must be used if a value has spaces.

        EXAMPLE: random choose bread cheese eggs milk "grilled onion"
        """
        if len(choices) < 2:
            await ctx.send("You must give me at least 2 options to choose from.")
        else:
            await ctx.send(f"I choose {random.choice(choices)}!")


    @_random.command(name="choosebestof")
    async def random_choosebestof(self, ctx: commands.Context,
                                  times: Optional[int], *choices: commands.clean_content):
        """Randomly chooses between multiple choices x amount of times.
        You can only recursively choose up to 10000 times and only the top 10 results are shown.
        Quotation marks must be used if a value has spaces.

        EXAMPLE:
        (Ex. 1) random choosebestof oranges blueberries "granny smith apples"
        (Ex. 2) random choosebestof 10 bread cheese eggs milk "grilled onion"
        """
        if len(choices) < 2:
            await ctx.send("You must give me at least 2 options to choose from.")
            return

        if times is None:
            times = len(choices) ** 2

        if times <= 0 or times > 10000:
            await ctx.send("Times must be greater than 0 and less than 10000.")
            return

        top_ten = Counter(random.choice(choices) for _ in range(times + 1)).most_common(10)
        content = "\n".join(
            f"{i}. {e} ({formatting.plural(c):time}; {c / times:.2%})" for i, (e, c) in enumerate(top_ten, 1)
        )

        if len(content) > 2000:
            await ctx.send("The result is too long to post.")
        else:
            await ctx.send(content)


    @_random.command(name="coin")
    async def _random_coin(self, ctx: commands.Context):
        """Flips a coin."""
        await ctx.send(f"You flipped **{random.choice(('Heads', 'Tails'))}**!")


    @_random.command(name="colour", aliases=["color"])
    @checks.bot_has_permissions(embed_links=True)
    async def _random_colour(self, ctx: commands.Context):
        """Displays a random hexidecimal and RGB colour code.
        (Bot Needs: Embed Links)
        """
        colour = discord.Colour(int(hex(random.randint(0, 16777215)), 16))

        embed = Embed(title="Random Colour", colour=colour)
        embed.add_field(name="Hex", value=str(colour).upper(), inline=False)
        embed.add_field(name="RGB", value=colour.to_rgb())
        await ctx.send(embed=embed)


    @_random.command(name="dice", aliases=["die"])
    async def _random_dice(self, ctx: commands.Context, sides: int = 6):
        """Rolls an x-sided die.
        A die can have a maximum of 120 sides and a minimum of 3 sides.
        If no number of sides is given, then a 6-sided die is rolled instead.

        EXAMPLE: random dice 12
        """
        if sides < 3 or sides > 120:
            await ctx.send("Sides must be greater than 3 and less than 120.")
        else:
            await ctx.send(f"You rolled a **{random.randint(1, sides)}**!")


    @_random.command(name="integer", aliases=["int", "number"])
    async def _random_integer(self, ctx: commands.Context, minimum: int = 0, maximum: int = 100):
        """Randomly chooses an integer between an optional minimum and maximum.
        The highest maximum integer is 10000000000000 and the lowest minimum integer is -10000000000000.

        EXAMPLE: random integer 1 10
        """
        if maximum > 10_000_000_000_000:
            await ctx.send("Maximum cannot exceed 10000000000000.")
        elif minimum < -10_000_000_000_000:
            await ctx.send("Minimum cannot be less than -10000000000000.")
        elif minimum >= maximum:
            await ctx.send("The maximum value must be greater than the minimum value.")
        else:
            await ctx.send(f"You got **{random.randint(minimum, maximum)}**!")


    @commands.command()
    @commands.guild_only()
    async def rate(self, ctx: commands.Context, user: discord.Member = None):
        """Rates a user out of 10.
        If no user is specified, then you will be rated instead.
        100% accurate or your money back.

        EXAMPLE:
        (Ex. 1) rate HitchedSyringe
        (Ex. 2) rate @HitchedSyringe#0598
        (Ex. 3) rate 140540589329481728
        """
        if user is None:
            user = ctx.author

        if user.id in ctx.bot.owner_ids or user == ctx.me:
            rating = 10
        else:
            rating = self._randint_by_seed(0, 10, seed=user.id)

        await ctx.send(f"I would give {escape_mentions(user.display_name)} a **{rating}/10**!")


    @commands.command(aliases=["rps"])
    async def rockpaperscissors(self, ctx: commands.Context, choice: str.lower):
        """Plays a game of rock, paper, scissors against me.

        EXAMPLE: rockpaperscissors rock
        """
        items = tuple(RPS_MATCHES.keys())

        if choice not in items:
            await ctx.send("Your choice must either be `rock`, `paper`, or `scissors`.")
            return

        bot_choice = random.choice(items)

        if bot_choice == choice:
            await ctx.send("We both tied.")
        elif bot_choice == RPS_MATCHES[choice]:
            await ctx.send(f"My `{bot_choice}` beats your `{choice}`, I win!")
        else:
            await ctx.send(f"Your `{choice}` beats my `{bot_choice}`, you win!")


    @commands.command()
    @commands.guild_only()  # Wouldn't make sense to allow this in a DM.
    @checks.bot_has_permissions(embed_links=True)
    async def say(self, ctx: commands.Context, *, content: str):
        """Says a custom message in chat through the bot.
        If possible, I will attempt to delete the message that invoked this command.
        (Bot Needs: Embed Links; Bot Optionally Needs: Manage Messages)

        EXAMPLE: say hello world!
        """
        embed = Embed(colour=0x2F3136, description=content)
        embed.set_author(name=f"{ctx.author} (ID: {ctx.author.id})", icon_url=ctx.author.avatar_url)
        embed.set_footer(
            text=f"This message is user-generated content and does not reflect the views or values of {ctx.me.name}."
        )

        # TODO: (Maybe) Add a way to add attachments whenever there's a cleaner way to implement it.

        await ctx.send(embed=embed)

        if ctx.channel.permissions_for(ctx.me).manage_messages:
            try:
                await ctx.message.delete()
            except discord.HTTPException:
                pass


    @commands.command()
    async def sheriff(self, ctx: commands.Context, character: commands.clean_content):
        """howdy. i'm the sheriff of \\_\\_\\_\\_\\_\\_

        EXAMPLE:
        (Ex. 1) sheriff \\:flag_us\\:
        (Ex. 2) sheriff \\:weed\\:
        (Ex. 3) sheriff a
        """
        char_raw, char_name = _resolve_char(character)

        # Thanks @EverySheriff on Twitter.
        base = (
            "⠀ ⠀ ⠀  🤠",
            f"　   {char_raw}{char_raw}{char_raw}",
            f"    {char_raw}   {char_raw}　{char_raw}",
            f"   👇   {char_raw}{char_raw} 👇",
            f"  　  {char_raw}　{char_raw}",
            f"　   {char_raw}　 {char_raw}",
            f"　   👢     👢",
            f"howdy. i'm the sheriff of {char_name.lower().replace('_', ' ')}",
        )

        content = "\n".join(base)

        if len(content) > 2000:
            await ctx.send("The result is too long to post.")
        else:
            await ctx.send(content)


def setup(bot):
    bot.add_cog(Fun())
