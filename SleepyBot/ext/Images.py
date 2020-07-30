"""
© Copyright 2018-2020 HitchedSyringe, All Rights Reserved.

Redistributing, using or owning a copy of this software without explicit permissions
is against these licensing terms, your license(s) to this software can be revoked at
any time without explicit notice beforehand and at the time of revocation.
Your license is non-transferrable, the terms of this license only permit you to do the
following; Create pull requests and make modifications to this repository.

"""


import random
from typing import Optional
from urllib.parse import quote as urlquote

import discord
from discord import Colour, Embed
from discord.ext import commands, flags

from SleepyBot.utils import checks, converters, formatting, reaction_menus


TTI_FONTS = (
    "arial",
    "comic",
    "dyslexic",
    "georgia",
    "impact",
    "lucida",
    "simsun",
    "tahoma",
    "times",
    "trebuchet",
    "verdana",
)


# TODO: Replace the NekoBot stuff with custom-made manipulations using PIL and a bunch of other libraries.


class Images(commands.Cog,
             command_attrs=dict(cooldown=commands.Cooldown(rate=1, per=5, type=commands.BucketType.member))):
    """Commands having to do with images and/or their manipulation."""

    async def cog_command_error(self, ctx: commands.Context, error):
        if isinstance(error, commands.BadArgument):
            # This is an attempt to make this less confusing for the end-user.
            raw_error = str(error)
            if raw_error == "Not a valid Image attachment or link.":
                await ctx.send(raw_error)
                error.handled = True


    @staticmethod
    async def _format_generic_image(ctx: commands.Context, *, url: str, provider: str, title=None, colour=None):
        """Sends the generic image message format.
        For internal use only.
        """
        embed = Embed(title=title, colour=colour)
        embed.set_image(url=url)
        embed.set_footer(text=f"Powered by {provider}")
        await ctx.send(embed=embed)


    @commands.command(aliases=["bpify"])
    @checks.bot_has_permissions(embed_links=True)
    @commands.cooldown(rate=1, per=10, type=commands.BucketType.member)
    async def blurpify(self, ctx: commands.Context, image: converters.ImageAssetConverter):
        """Blurpifies an image.
        Image can either be a link or attachment.
        (Bot Needs: Embed Links)
        """
        async with ctx.typing():
            response = await ctx.get("https://nekobot.xyz/api/imagegen", type="blurpify", image=str(image))

        await self._format_generic_image(ctx, url=response["message"], provider="nekobot.xyz", colour=Colour.blurple())


    @commands.command(aliases=["meow"])
    @checks.bot_has_permissions(embed_links=True, add_reactions=True, read_message_history=True)
    async def cats(self, ctx: commands.Context):
        """Gets a random series of images of cats.
        (Bot Needs: Embed Links, Add Reactions and Read Message History)
        """
        await ctx.trigger_typing()
        cats = await ctx.get("https://api.thecatapi.com/v1/images/search", limit=50)

        base_embed = Embed(title="\N{CAT FACE} Cats", colour=0x2F3136)
        base_embed.set_footer(text="Powered by api.thecatapi.com")

        embeds = tuple(base_embed.copy().set_image(url=cat["url"]) for cat in cats)
        await ctx.paginate(reaction_menus.EmbedSource(embeds))


    @commands.command()
    @checks.bot_has_permissions(embed_links=True)
    async def captcha(self, ctx: commands.Context, image: converters.ImageAssetConverter,
                      *, text: commands.clean_content(fix_channel_mentions=True)):
        """Generates a Google image captcha.
        (Bot Needs: Embed Links)
        """
        async with ctx.typing():
            response = await ctx.get(
                f"https://nekobot.xyz/api/imagegen?url={urlquote(str(image))}",
                type="captcha",
                username=text
            )

        await self._format_generic_image(ctx, url=response["message"], provider="nekobot.xyz", colour=0x2F3136)


    @commands.command(aliases=["cmm"])
    @checks.bot_has_permissions(embed_links=True)
    async def changemymind(self, ctx: commands.Context,
                           *, text: commands.clean_content(fix_channel_mentions=True)):
        """Generates a "change my mind" meme.
        (Bot Needs: Embed Links)
        """
        async with ctx.typing():
            response = await ctx.get(
                "https://nekobot.xyz/api/imagegen",
                type="changemymind",
                text=text,
                cache=True
            )

        await self._format_generic_image(ctx, url=response["message"], provider="nekobot.xyz", colour=0x2F3136)


    @commands.command()
    @checks.bot_has_permissions(embed_links=True)
    async def clyde(self, ctx: commands.Context,
                    *, text: commands.clean_content(fix_channel_mentions=True)):
        """Generates a Clyde bot message.
        (Bot Needs: Embed Links)
        """
        async with ctx.typing():
            response = await ctx.get(
                "https://nekobot.xyz/api/imagegen",
                type="clyde",
                text=text,
                cache=True
            )

        await self._format_generic_image(ctx, url=response["message"], provider="nekobot.xyz", colour=Colour.blurple())


    @commands.command(aliases=["df"])
    @checks.bot_has_permissions(embed_links=True)
    @commands.cooldown(rate=1, per=10, type=commands.BucketType.member)
    async def deepfry(self, ctx: commands.Context, image: converters.ImageAssetConverter):
        """Deep fries an image.
        Image can either be a link or attachment.
        (Bot Needs: Embed Links)
        """
        async with ctx.typing():
            response = await ctx.get(
                "https://nekobot.xyz/api/imagegen",
                type="deepfry",
                image=str(image),
                cache=True
            )

        await self._format_generic_image(ctx, url=response["message"], provider="nekobot.xyz", colour=0x2F3136)


    @commands.command(aliases=["doggos", "woof"])
    @checks.bot_has_permissions(embed_links=True, add_reactions=True, read_message_history=True)
    async def dogs(self, ctx: commands.Context):
        """Gets a random series of images of dogs.
        (Bot Needs: Embed Links, Add Reactions and Read Message History)
        """
        await ctx.trigger_typing()
        dogs = await ctx.get("https://dog.ceo/api/breeds/image/random/50")

        base_embed = Embed(title="\N{DOG FACE} Dogs", colour=0x2F3136)
        base_embed.set_footer(text="Powered by dog.ceo")

        embeds = tuple(base_embed.copy().set_image(url=dog) for dog in dogs["message"])
        await ctx.paginate(reaction_menus.EmbedSource(embeds))


    @commands.command(aliases=["quack"])
    @checks.bot_has_permissions(embed_links=True)
    @commands.cooldown(rate=2, per=5, type=commands.BucketType.member)
    async def duck(self, ctx: commands.Context):
        """Gets a random image of a duck.
        (Bot Needs: Embed Links)
        """
        await ctx.trigger_typing()
        duck = await ctx.get("https://random-d.uk/api/random")
        url = duck["url"]

        await self._format_generic_image(
            ctx, url=url, provider=duck["message"], title="Random \N{DUCK}", colour=0x2F3136
        )


    @commands.command(aliases=["floof"])
    @checks.bot_has_permissions(embed_links=True)
    @commands.cooldown(rate=2, per=5, type=commands.BucketType.member)
    async def fox(self, ctx: commands.Context):
        """Gets a random image of a fox.
        (Bot Needs: Embed Links)
        """
        await ctx.trigger_typing()
        fox = await ctx.get("https://randomfox.ca/floof/")

        await self._format_generic_image(
            ctx, url=fox["image"], provider="randomfox.ca", title="Random \N{FOX FACE}", colour=0x2F3136
        )


    @commands.command(aliases=["ipx"])
    @checks.bot_has_permissions(embed_links=True)
    async def iphonex(self, ctx: commands.Context, image: converters.ImageAssetConverter):
        """Fits an image onto an iPhone X screen.
        Image can either be a link or attachment.
        (Bot Needs: Embed Links)
        """
        async with ctx.typing():
            response = await ctx.get(f"https://nekobot.xyz/api/imagegen?url={urlquote(str(image))}", type="iphonex")

        await self._format_generic_image(ctx, url=response["message"], provider="nekobot.xyz", colour=0x2F3136)


    # XXX As of right now, this is disabled due to the feature being DOA on NekoBot's end.
    # @commands.command(aliases=["needsmorejpeg"])
    # @checks.bot_has_permissions(embed_links=True)
    # @commands.cooldown(rate=1, per=10, type=commands.BucketType.member)
    # async def jpegify(self, ctx: commands.Context, image: converters.ImageAssetConverter):
    #     """JPEGifies an image.
    #     Image can either be a link or attachment.
    #     (Bot Needs: Embed Links)
    #     """
    #     async with ctx.typing():
    #         response = await ctx.get(f"https://nekobot.xyz/api/imagegen?url={urlquote(str(image))}", type="jpeg")

    #     await self._format_generic_image(ctx, url=response["message"], provider="nekobot.xyz", colour=0x2F3136)


    @commands.command()
    @checks.bot_has_permissions(embed_links=True)
    @commands.cooldown(rate=1, per=10, type=commands.BucketType.member)
    async def magik(self, ctx: commands.Context, intensity: Optional[int], image: converters.ImageAssetConverter):
        """Heavily warps and distorts an image to an optional intensity.
        Image can either be a link or attachment.
        (Bot Needs: Embed Links)
        """
        if intensity is None:
            intensity = 1

        if intensity <= 0:
            await ctx.send("Intensity must be greater than 0.")
            return

        async with ctx.typing():
            response = await ctx.get(
                "https://nekobot.xyz/api/imagegen",
                type="magik",
                image=str(image),
                intensity=intensity
            )

        await self._format_generic_image(ctx, url=response["message"], provider="nekobot.xyz", colour=0x2F3136)


    @commands.command(aliases=["phcomment", "phc"])
    @commands.guild_only()
    @checks.bot_has_permissions(embed_links=True)
    async def pornhubcomment(self, ctx: commands.Context, user: Optional[discord.Member],
                             *, text: commands.clean_content(fix_channel_mentions=True)):
        """Generates a Pr0nHub comment.
        (Bot Needs: Embed Links)
        """
        if user is None:
            user = ctx.author

        async with ctx.typing():
            response = await ctx.get(
                "https://nekobot.xyz/api/imagegen",
                type="phcomment",
                image=str(user.avatar_url),
                text=text,
                username=user.display_name,
                cache=True
            )

        await self._format_generic_image(ctx, url=response["message"], provider="nekobot.xyz", colour=0x2F3136)


    @commands.command()
    @commands.guild_only()
    @checks.bot_has_permissions(embed_links=True)
    async def ship(self, ctx: commands.Context, first_user: discord.Member, second_user: discord.Member = None):
        """Ships two users.
        If no second user is specified, then the second user will default to you.
        (Bot Needs: Embed Links)

        EXAMPLE:
        (Ex. 1) ship HitchedSyringe#0598
        (Ex. 2) ship HitchedSyringe#0598 someotherperson#0194
        """
        if second_user is None:
            second_user = ctx.author

        if first_user == second_user:
            await ctx.send("You cannot ship the same user.")
            return

        async with ctx.typing():
            response = await ctx.get(
                "https://nekobot.xyz/api/imagegen",
                type="ship",
                user1=str(first_user.avatar_url),
                user2=str(second_user.avatar_url),
                cache=True
            )

        first_name = first_user.name
        second_name = second_user.name
        score = random.randint(0, 100)

        embed = Embed(title=f"{first_name} \N{HEAVY BLACK HEART} {second_name}", colour=0x2F3136)
        embed.set_author(name=first_name[:len(first_name) // 2] + second_name[len(second_name) // 2:])
        embed.set_image(url=response["message"])
        embed.set_footer(text="Powered by nekobot.xyz")
        embed.add_field(name=f"Confidence", value=f"**{score}%** | 0 {formatting.progress_bar(100, 10, score)} 100")

        await ctx.send(embed=embed)


    @flags.add_flag("--font", type=str.lower, default="arial", choices=TTI_FONTS)
    @flags.add_flag("--textcolour", "--textcolor", dest="fcolor", type=Colour, default="FFFFFF")
    @flags.add_flag("--bgcolour", "--bgcolor", dest="bcolor", type=Colour)
    @flags.add_flag("--size", type=int, default=35)
    @flags.command(aliases=["tti"])
    @checks.bot_has_permissions(embed_links=True)
    async def texttoimage(self, ctx: commands.Context,
                          text: commands.clean_content(fix_channel_mentions=True), **flags):
        """Converts text into an image.

        This uses a powerful "command-line" interface.
        The first argument is the text to convert.
        All following arguments are the option flags.
        Quotation marks must be used if a value has spaces.
        **All options are optional.**

        __The following options are valid:__

        `--font`: The text font to use.
        `--textcolour` or `--textcolor`: The colour of the text. Hexidecimal values are accepted.
        `--bgcolour` or `--bgcolor`: The colour of the background. Hexidecimal values are accepted. Omit for transparent.
        `--size`: The size of the text. (Default: 35; Min: 5; Max: 35)

        (Bot Needs: Embed Links)
        """
        size = flags["size"]
        if size > 35 or size < 5:
            await ctx.send("Text size must be greater than 5 and less than 35.")
            return

        flags["fcolor"] = str(flags["fcolor"])

        background_colour = flags["bcolor"]
        if background_colour is not None:
            flags["bcolor"] = str(background_colour)
        else:
            # Text can have transparent background, also this will cause an error if we don't remove it.
            del flags["bcolor"]

        await ctx.trigger_typing()
        url = await ctx.get("http://api.img4me.com/?type=png", text=text, cache=True, **flags)

        await self._format_generic_image(ctx, url=url, provider="api.img4me.com", colour=0x2F3136)


    @texttoimage.error
    async def on_texttoimage_error(self, ctx: commands.Context, error):
        error = getattr(error, "original", error)

        if isinstance(error, flags.ArgumentParsingError):
            await ctx.send(f"Argument parsing error: {error}")
            error.handled = True


    @commands.command()
    @checks.bot_has_permissions(embed_links=True)
    async def threats(self, ctx: commands.Context, image: converters.ImageAssetConverter):
        """Generates a "three threats to society" meme.
        Image can either be a link or attachment.
        (Bot Needs: Embed Links)
        """
        async with ctx.typing():
            # ``url``` argument collides with our positional argument of the same name,
            # so we'll just have to format it and urlquote it ourself instead.
            response = await ctx.get(f"https://nekobot.xyz/api/imagegen?url={urlquote(str(image))}", type="threats")

        await self._format_generic_image(ctx, url=response["message"], provider="nekobot.xyz", colour=0x2F3136)


    @commands.command()
    @commands.guild_only()
    @checks.bot_has_permissions(embed_links=True)
    async def trapcard(self, ctx: commands.Context, user: discord.Member, image: converters.ImageAssetConverter):
        """Generates a Yu-Gi-Oh trap card.
        Image can either be a link or attachment.
        (Bot Needs: Embed Links)
        """
        async with ctx.typing():
            response = await ctx.get(
                "https://nekobot.xyz/api/imagegen",
                type="trap",
                name=user.display_name,
                author=ctx.author.display_name,
                image=str(image)
            )

        await self._format_generic_image(ctx, url=response["message"], provider="nekobot.xyz", colour=0x2F3136)


    @commands.command()
    @checks.bot_has_permissions(embed_links=True)
    async def tweet(self, ctx: commands.Context, username: str,
                    *, text: commands.clean_content(fix_channel_mentions=True)):
        """Generates a tweet.
        Username is the Twitter handle without the "@".
        (Bot Needs: Embed Links)
        """
        async with ctx.typing():
            response = await ctx.get(
                "https://nekobot.xyz/api/imagegen",
                type="tweet",
                username=username,
                text=text,
                cache=True
            )

        await self._format_generic_image(ctx, url=response["message"], provider="nekobot.xyz", colour=0x1DA1F2)


    @commands.command(aliases=["www"])
    @commands.guild_only()
    @checks.bot_has_permissions(embed_links=True)
    async def whowouldwin(self, ctx: commands.Context, first_user: discord.Member, second_user: discord.Member = None):
        """Generates a "who would win" meme.
        If no second user is specified, then the second user will default to you.
        (Bot Needs: Embed Links)

        EXAMPLE:
        (Ex. 1) whowouldwin HitchedSyringe#0598
        (Ex. 2) whowouldwin HitchedSyringe#0598 someotherperson#0194
        """
        if second_user is None:
            second_user = ctx.author

        if first_user == second_user:
            await ctx.send("You cannot compare the same user.")
            return

        async with ctx.typing():
            response = await ctx.get(
                "https://nekobot.xyz/api/imagegen",
                type="whowouldwin",
                user1=str(first_user.avatar_url),
                user2=str(second_user.avatar_url),
                cache=True
            )

        await self._format_generic_image(ctx, url=response["message"], provider="nekobot.xyz", colour=0x2F3136)


def setup(bot):
    bot.add_cog(Images())
