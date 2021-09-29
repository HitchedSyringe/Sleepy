"""
© Copyright 2018-2020 HitchedSyringe, All Rights Reserved.

Redistributing, using or owning a copy of this software without explicit permissions
is against these licensing terms, your license(s) to this software can be revoked at
any time without explicit notice beforehand and at the time of revocation.
Your license is non-transferrable, the terms of this license only permit you to do the
following; Create pull requests and make modifications to this repository.

"""


import io
from urllib.parse import quote as urlquote

from discord import Embed, File
from discord.ext import commands, flags

from SleepyBot.utils import checks, converters
from SleepyBot.utils.requester import HTTPError


class Weeb(commands.Cog,
           command_attrs=dict(cooldown=commands.Cooldown(rate=2, per=5, type=commands.BucketType.member))):
    """Commands having to do with weeaboo stuff.
    Pretty sure the name was implicit.
    """

    async def cog_command_error(self, ctx: commands.Context, error):
        if isinstance(error, commands.BadArgument):
            await ctx.send(str(error))
            error.handled = True


    @staticmethod
    async def _format_nekobot_image(ctx, *, url: str, colour=None, show_requester: bool = False):
        """Sends the generic image message format for nekobot images.
        For internal use only.
        """
        embed = Embed(colour=colour)
        embed.set_image(url=url)
        embed.set_footer(
            text=f"Powered by nekobot.xyz | Requested by: {ctx.author}" if show_requester else "Powered by nekobot.xyz"
        )
        await ctx.send(embed=embed)


    @commands.command()
    @checks.bot_has_permissions(embed_links=True)
    @commands.cooldown(rate=1, per=5, type=commands.BucketType.member)
    async def animeface(self, ctx: commands.Context, image: converters.ImageAssetConverter):
        """Detects and highlights anime faces in an image.
        Image can either be a link or attachment.
        (Bot Needs: Embed Links)
        """
        async with ctx.typing():
            response = await ctx.get(
                'https://nekobot.xyz/api/imagegen',
                type="animeface",
                image=str(image),
            )


        await self._format_nekobot_image(ctx, url=response["message"], colour=0x2F3136)


    @commands.command()
    @checks.bot_has_permissions(embed_links=True)
    @commands.cooldown(rate=1, per=5, type=commands.BucketType.member)
    async def awooify(self, ctx: commands.Context, image: converters.ImageAssetConverter):
        """Awooifies an image.
        Image can either be a link or attachment.
        (Bot Needs: Embed Links)
        """
        async with ctx.typing():
            response = await ctx.get(f"https://nekobot.xyz/api/imagegen?url={urlquote(str(image))}", type="awooify")

        await self._format_nekobot_image(ctx, url=response["message"], colour=0x2F3136, show_requester=True)


    @commands.command(aliases=["france"])
    @checks.bot_has_permissions(embed_links=True)
    @commands.cooldown(rate=1, per=5, type=commands.BucketType.member)
    async def baguette(self, ctx: commands.Context, image: converters.ImageAssetConverter):
        """Turns an image into an anime girl eating a baguette.
        Image can either be a link or attachment.
        (Bot Needs: Embed Links)
        """
        async with ctx.typing():
            response = await ctx.get(f"https://nekobot.xyz/api/imagegen?url={urlquote(str(image))}", type="baguette")

        await self._format_nekobot_image(ctx, url=response["message"], colour=0x2F3136, show_requester=True)


    @commands.command(aliases=["bp"])
    @checks.bot_has_permissions(embed_links=True)
    @commands.cooldown(rate=1, per=5, type=commands.BucketType.member)
    async def bodypillow(self, ctx: commands.Context, image: converters.ImageAssetConverter):
        """Turns an image into an anime body pillow.
        Image can either be a link or attachment.
        (Bot Needs: Embed Links)
        """
        async with ctx.typing():
            response = await ctx.get(f"https://nekobot.xyz/api/imagegen?url={urlquote(str(image))}", type="bodypillow")

        await self._format_nekobot_image(ctx, url=response["message"], colour=0x2F3136, show_requester=True)


    @commands.command()
    @checks.bot_has_permissions(embed_links=True)
    async def coffee(self, ctx: commands.Context):
        """Sends a random image of an anime girl drinking coffee.
        (Bot Needs: Embed Links)
        """
        response = await ctx.get("https://nekobot.xyz/api/image", type="coffee")

        await self._format_nekobot_image(ctx, url=response["message"], colour=0x2F3136)


    @commands.command()
    @checks.bot_has_permissions(embed_links=True)
    @commands.cooldown(rate=1, per=5, type=commands.BucketType.member)
    async def fact(self, ctx: commands.Context, *, text: commands.clean_content(fix_channel_mentions=True)):
        """Generates an image of an anime girl spitting straight facts.
        (Bot Needs: Embed Links)
        """
        async with ctx.typing():
            response = await ctx.get("https://nekobot.xyz/api/imagegen", type="fact", text=text, cache=True)

        await self._format_nekobot_image(ctx, url=response["message"], colour=0x2F3136)


    @commands.command()
    @checks.bot_has_permissions(embed_links=True)
    async def food(self, ctx: commands.Context):
        """Sends a random image of anime food.
        (Bot Needs: Embed Links)
        """
        response = await ctx.get("https://nekobot.xyz/api/image", type="food")

        await self._format_nekobot_image(ctx, url=response["message"], colour=0x2F3136)


    @commands.command()
    @checks.bot_has_permissions(embed_links=True)
    async def gah(self, ctx: commands.Context):
        """GAH!
        (Bot Needs: Embed Links)
        """
        response = await ctx.get("https://nekobot.xyz/api/image", type="gah", cache=True)

        await self._format_nekobot_image(ctx, url=response["message"], colour=0x2F3136)


    @commands.command()
    @checks.bot_has_permissions(embed_links=True)
    async def holo(self, ctx: commands.Context):
        """Sends a random image of Holo from Ookami to Koushinryou.
        (Bot Needs: Embed Links)
        """
        response = await ctx.get("https://nekobot.xyz/api/image", type="holo")

        await self._format_nekobot_image(ctx, url=response["message"], colour=0x2F3136)


    @commands.command()
    @checks.bot_has_permissions(embed_links=True)
    @commands.cooldown(rate=1, per=5, type=commands.BucketType.member)
    async def kannafact(self, ctx: commands.Context, *, text: commands.clean_content(fix_channel_mentions=True)):
        """Generates an image of Kanna spitting straight facts.
        (Bot Needs: Embed Links)
        """
        async with ctx.typing():
            response = await ctx.get("https://nekobot.xyz/api/imagegen", type="kannagen", text=text, cache=True)

        await self._format_nekobot_image(ctx, url=response["message"], colour=0x2F3136)


    @commands.command(aliases=["kemo"])
    @checks.bot_has_permissions(embed_links=True)
    async def kemonomimi(self, ctx: commands.Context):
        """Sends a random image of a kemonomimi character.
        (Bot Needs: Embed Links)
        """
        response = await ctx.get("https://nekobot.xyz/api/image", type="kemonomimi")

        await self._format_nekobot_image(ctx, url=response["message"], colour=0x2F3136)


    @commands.command()
    @checks.bot_has_permissions(embed_links=True)
    @commands.cooldown(rate=1, per=5, type=commands.BucketType.member)
    async def lolice(self, ctx: commands.Context, image: converters.ImageAssetConverter):
        """Submits an image to the lolice.
        Image can either be a link or attachment.
        (Bot Needs: Embed Links)
        """
        async with ctx.typing():
            response = await ctx.get(f"https://nekobot.xyz/api/imagegen?url={urlquote(str(image))}", type="lolice")

        await self._format_nekobot_image(ctx, url=response["message"], colour=0x2F3136, show_requester=True)


    @commands.command()
    @checks.bot_has_permissions(attach_files=True)
    @commands.cooldown(rate=1, per=8, type=commands.BucketType.member)
    async def nichijou(self, ctx: commands.Context, *, text: commands.clean_content(fix_channel_mentions=True)):
        """Generates a custom nichijou gif.
        (Bot Needs: Attach Files)
        """
        async with ctx.typing():
            data = await ctx.get(f"https://i.ode.bz/auto/nichijou?text={urlquote(text)}", cache=True)

        await ctx.send(f"Requested by: {ctx.author}", file=File(io.BytesIO(data), filename="nichijou.gif"))


    @commands.command(aliases=["catgirl", "nekomimi"])
    @checks.bot_has_permissions(embed_links=True)
    async def neko(self, ctx: commands.Context):
        """Sends a random image of a catgirl.
        (Bot Needs: Embed Links)
        """
        response = await ctx.get("https://nekobot.xyz/api/image", type="neko")

        await self._format_nekobot_image(ctx, url=response["message"], colour=0x2F3136)


    @commands.command()
    @checks.bot_has_permissions(embed_links=True)
    @commands.cooldown(rate=1, per=5, type=commands.BucketType.member)
    async def trash(self, ctx: commands.Context, image: converters.ImageAssetConverter):
        """Generates a trash waifu meme.
        Image can either be a link or attachment.
        (Bot Needs: Embed Links)
        """
        async with ctx.typing():
            response = await ctx.get(f"https://nekobot.xyz/api/imagegen?url={urlquote(str(image))}", type="trash")

        await self._format_nekobot_image(ctx, url=response["message"], colour=0x2F3136, show_requester=True)


def setup(bot):
    bot.add_cog(Weeb())
