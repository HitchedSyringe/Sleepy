"""
Copyright (c) 2018-present HitchedSyringe

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""


import io
import random
import re
import textwrap
from datetime import datetime
from typing import Optional
from urllib.parse import quote

import discord
import yarl
from discord import Embed, File
from discord.ext import commands
from discord.utils import parse_time as discord_parse_time
from googletrans import Translator, LANGUAGES
from sleepy import checks, menus, utils
from sleepy.converters import _pseudo_argument_flag, real_float
from sleepy.http import HTTPRequestFailed
from sleepy.paginators import WrappedPaginator


def clean_subreddit(value):
    if (match := re.search(r"(?:\/?[rR]\/)?([\w]{3,21})", value)) is None:
        raise commands.BadArgument("Invalid subreddit.")

    return match.group(1).lower()


class RedditSubmissionURL(commands.Converter):

    async def convert(self, ctx, argument):
        try:
            url = yarl.URL(argument.strip("<>"))
        except:
            raise commands.BadArgument("Invalid link.") from None

        await ctx.trigger_typing()

        # Need to fetch the main Reddit URL.
        if url.host == "v.redd.it":
            async with ctx.session.get(url) as fetched:
                url = fetched.url

        # Reddit has too many stupid redirects for stuff.
        if url.host is None or not url.host.endswith(".reddit.com"):
            raise commands.BadArgument("Invalid Reddit or v.redd.it link.")

        try:
            resp = await ctx.get(url / ".json", cache__=True)
        except HTTPRequestFailed as exc:
            raise commands.BadArgument(
                f"Reddit API failed with HTTP status {exc.status}"
            ) from None

        try:
            submission = resp[0]["data"]["children"][0]["data"]
        except (KeyError, IndexError, TypeError):
            raise commands.BadArgument("Failed to get submission data.") from None

        try:
            media = submission["media"]["reddit_video"]
        except (KeyError, TypeError):
            # Handle crossposts.
            try:
                media = submission["crosspost_parent_list"][0]["media"]["reddit_video"]
            except (KeyError, IndexError, TypeError):
                raise commands.BadArgument("Failed to get media information") from None

        try:
            return media["fallback_url"]
        except KeyError:
            raise commands.BadArgument("Failed to get fallback link.") from None


class SteamAccountMeta:

    __slots__ = ("id", "id_3", "id_64")

    # Steam Base ID used for ID conversion calculations.
    # Side note: this isn't in the official docs.
    BASE_ID_64 = 76561197960265728

    URL_REGEX = re.compile(
        r"(?:https?\:\/\/)?(?:w{3}\.?)?steamcommunity\.com\/"
        r"(?:id|profile)\/([\w\-]{2,32})\/?"
    )

    def __init__(self, id_, id_3, id_64):
        self.id = id_
        self.id_3 = id_3
        self.id_64 = id_64

    @classmethod
    async def convert(cls, ctx, argument):
        # Steam ID 3
        if (id_3_match := re.fullmatch(r"U:1:([0-9]+)", argument.strip("[]"))) is not None:
            return cls.from_id_3(int(id_3_match.group(1)))

        # Steam ID
        if (id_match := re.fullmatch(r"STEAM_0:([01]):([0-9]+)", argument)) is not None:
            a_type, id_n = id_match.groups()
            return cls.from_id(int(a_type), int(id_n))

        # Get argument from URL.
        if (url_match := cls.URL_REGEX.fullmatch(argument.strip("<>"))) is not None:
            argument = url_match.group(1)

        # Steam ID 64
        try:
            id_64 = int(argument)
        except ValueError:
            pass
        else:
            # The last 32 bytes of a Steam ID is usually
            # equal to the hex value 0x1100001. This is
            # here mainly to handle the possibility of
            # a vanity being comprised of only numbers.
            # The only way this check would actually
            # return a false positive would be if the
            # user has a custom URL that mimicks an ID.
            if id_64 >> 32 == 0x1100001:
                return cls.from_id_64(id_64)

        # ID resolve through vanity.
        resp = await ctx.get(
            "https://api.steampowered.com/ISteamUser/ResolveVanityURL/v1",
            key=ctx.cog.steam_api_key,
            vanityurl=argument.lower(),
            cache__=True
        )

        try:
            return cls.from_id_64(int(resp["response"]["steamid"]))
        except KeyError:
            raise commands.BadArgument("That Steam user wasn't found.") from None

    # These are mainly here so as to not repeat any
    # mathematical operations later on. Essentially,
    # if either a SteamID, SteamID3, or SteamID64 is
    # found, the other two IDs can simply be resolved
    # through somewhat simple math.

    @classmethod
    def from_id(cls, account_type, number_id):
        id_3_n = number_id * 2 + account_type

        return cls(
            f"STEAM_0:{account_type}:{number_id}",
            f"[U:1:{id_3_n}]",
            cls.BASE_ID_64 + id_3_n
        )

    @classmethod
    def from_id_3(cls, number_id):
        a_type = number_id % 2
        id_n = number_id + a_type

        return cls(f"STEAM_0:{a_type}:{id_n}", f"[U:1:{number_id}]", cls.BASE_ID_64 + id_n)

    @classmethod
    def from_id_64(cls, id_64):
        id_3_n = id_64 - cls.BASE_ID_64
        a_type = id_3_n % 2

        return cls(
            f"STEAM_0:{a_type}:{round((id_3_n - a_type) / 2)}",
            f"[U:1:{id_3_n}]",
            id_64
        )


# NOTE: Some channels have a /user and /c URL. In many
# cases, one of these is the correct username that the
# YouTube API accepts (usually the former). In other
# cases, both of these are correct. Because of the
# current ambiguity this possesses, I'll just allow
# all types of URLs to be recognized, including the
# variant of /c which is no /c.
YOUTUBE_URL = re.compile(
    r"(?:https?\:\/\/)?(?:w{3}\.?)?youtube\.com"
    r"(?:\/c|\/user|\/channel)?\/([\w\-]+)"
)


def youtube_channel_kwargs(value):
    if (match := YOUTUBE_URL.fullmatch(value.strip("<>"))) is not None:
        value = match.group(1)

    if re.fullmatch(r"UC[\w\-]{21}[AQgw]", value) is not None:
        return {"id": value}

    return {"forUsername": value.lower()}


class Web(
    commands.Cog,
    command_attrs={"cooldown": commands.Cooldown(2, 5, commands.BucketType.member)}
):
    """Commands that grab data from various websites and APIs.

    These are usually intended to serve as utilities in a sense.
    """

    def __init__(self, config):
        self.steam_api_key = config["steam_api_key"]
        self.weatherapi_api_key = config["weatherapi_api_key"]

        self.google_api_key = config["google_api_key"]
        self.google_search_engine_id = config["google_search_engine_id"]

        self.translator = translator = Translator()
        translator.translate = utils.awaitable(translator.translate)

    @staticmethod
    async def do_calculation(ctx, route, expr):
        await ctx.trigger_typing()

        try:
            resp = await ctx.get(
                f"https://newton.vercel.app/api/v2/{route}/{quote(expr.replace('/', '(over)'))}",
                cache__=True
            )
        except HTTPRequestFailed:
            await ctx.send("Calculating the expression failed. Try again later?")
            return

        result = resp["result"]

        if len(result) > 1962:
            await ctx.send("The result is too long to post.")
        else:
            await ctx.send(f"```\n{result}```\n`Powered by newton.varcel.app`")

    async def do_google_search(self, ctx, query, *, search_images=False):
        await ctx.trigger_typing()

        url = "https://www.googleapis.com/customsearch/v1?searchInformation,items(title,link,snippet)"

        if not ctx.channel.is_nsfw():
            url += "&safe=active"

        if search_images:
            url += "&searchType=image"

        resp = await ctx.get(
            url,
            cache__=True,
            key=self.google_api_key,
            cx=self.google_search_engine_id,
            q=query
        )

        try:
            results = resp["items"]
        except KeyError:
            await ctx.send("No results found.")
            return

        total = resp["searchInformation"]["formattedTotalResults"]
        delta = resp["searchInformation"]["formattedSearchTime"]

        embeds = []
        for result in results:
            if search_images:
                url = result["link"]

                embed = Embed(
                    title=result["title"],
                    description=f"[Image Link]({url})",
                    url=result["image"]["contextLink"],
                    colour=0x4285F4
                )
                embed.set_image(url=url)
            else:
                embed = Embed(
                    title=result["title"],
                    description=result["snippet"],
                    colour=0x4285F4,
                    url=result["link"]
                )

            embed.set_author(
                name=f"Results for '{utils.truncate(query, 64)}'",
                url=f"https://google.com/search?q={quote(query)}"
            )
            embed.set_footer(
                text=f"About {total} results. ({delta} seconds) "
                     "\N{BULLET} Powered by Google Search"
            )

            embeds.append(embed)

        await ctx.paginate(menus.EmbedSource(embeds))

    # This function exists as a way to save memory when caching
    # data from PokeAPI. In this case, we're only caching what
    # we need for the command and then discarding the rest.
    # Perhaps whenever PokeAPI releases their GraphQL endpoint,
    # I can come back and revisit this.
    @staticmethod
    async def get_pokemon_info(ctx, name):
        http = ctx.bot.http_requester

        async with http._request_lock:
            if http.cache is not None:
                key = f"<GET:PokeAPI:{name}>"

                if (cached := http.cache.get(key)) is not None:
                    return cached

            poke = await ctx.get(f"https://pokeapi.co/api/v2/pokemon/{name}")
            spec = await ctx.get(poke["species"]["url"])

            pokemon_name = poke["name"]

            slimmed_data = {
                "name": pokemon_name.title(),
                "pokedex_url": f"https://pokemon.com/us/pokedex/{pokemon_name}",
                "flavour_text": next(
                    (
                        f["flavor_text"] for f in spec["flavor_text_entries"]
                        if f["language"]["name"] == "en"
                    ),
                    None
                ),
                "front_sprite_url": poke["sprites"]["front_default"],
                "order": poke["order"],
                "base_experience": poke["base_experience"],
                "base_happiness": spec["base_happiness"],
                "capture_rate": spec["capture_rate"],
                "weight": poke["weight"],
                "height": poke["height"],
                "colour": spec["color"]["name"].title(),
                "abilities": "\n".join(a["ability"]["name"].title() for a in poke["abilities"]),
                "types": "\n".join(t["type"]["name"].title() for t in poke["types"]),
                "stats": {s["stat"]["name"].title(): s["base_stat"] for s in poke["stats"]},
            }

            try:
                slimmed_data["evolves_from"] = spec["evolves_from_species"]["name"].title()
            except TypeError:
                slimmed_data["evolves_from"] = None

            if http.cache is not None:
                http.cache[key] = slimmed_data

            return slimmed_data

    @staticmethod
    async def send_formatted_comic_embed(ctx, comic):
        number = comic["num"]

        embed = Embed(
            title=comic['title'],
            description=comic["alt"],
            url=f"https://xkcd.com/{number}",
            colour=0x708090
        )
        embed.timestamp = datetime(
            month=int(comic["month"]),
            year=int(comic["year"]),
            day=int(comic["day"])
        )
        embed.set_author(name=f"#{number}")
        embed.set_image(url=comic["img"])
        embed.set_footer(text="Powered by xkcd.com")

        await ctx.send(embed=embed)

    # NOTE: Endpoints not included due to either limited
    # functionality or existing functional equivalent: `abs`,
    # `arccos`, `arcsin`, `arctan`, `cosine`, `sine`, `tan`.
    @commands.group(
        aliases=("calc", "calculator", "math"),
        invoke_without_command=True
    )
    async def calculate(self, ctx, *, expression):
        """Evaluates the solution to the given expression.

        Answers are returned as exact values.

        **EXAMPLES:**
        ```bnf
        <1> calculate 2^2 + 3(24)
        <2> calculate 2x + 4x^2 - x
        <3> calculate 2(25) + 19 == 69
        ```
        """
        await self.do_calculation(ctx, "simplify", expression)

    @calculate.command(name="antiderivative", aliases=("integral", "indefiniteintegral", "∫"))
    async def calculate_antiderivative(self, ctx, *, expression):
        """Finds the antiderivative of the given expression.

        ||Friendly reminder to include the `+ c` in the answer. \N{SLIGHTLY SMILING FACE}||

        **EXAMPLES:**
        ```bnf
        <1> calculate antiderivative 4x^3 + x^2 + 8x
        <2> calculate antiderivative log(x)
        ```
        """
        await self.do_calculation(ctx, "integrate", expression)

    @calculate.command(name="definiteintegral", aliases=("areaunderthecurve",))
    async def calculate_definiteintegral(self, ctx, a: int, b: int, *, expression):
        """Evaluates the definite integral of the given expression from `a` to `b`.

        Answers are rounded to the nearest ones place.

        This doesn't work with negative `a` or `b` values.

        **EXAMPLES:**
        ```bnf
        <1> calculate definiteintegral 2 3 x + 3
        <2> calculate definiteintegral 3 7 ln(x^3)
        ```
        """
        await self.do_calculation(ctx, "area", f"{a}:{b} | {expression}")

    @calculate.command(name="derivative", aliases=("diff", "differencial"))
    async def calculate_derivative(self, ctx, *, expression):
        """Finds the derivative of the given expression.

        **EXAMPLES:**
        ```bnf
        <1> calculate derivative x^2 + 2x + 3
        <2> calculate derivative log(x - 8)^2
        ```
        """
        await self.do_calculation(ctx, "derive", expression)

    @calculate.command(name="factor")
    async def calculate_factor(self, ctx, *, expression):
        """Factors the given expression.

        If the expression can't be factored, then the input
        expression will be returned as-is.

        **EXAMPLES:**
        ```bnf
        <1> calculate factor x^2 + 6x + 9
        <2> calculate factor x^4 + 18x^3 + 116x^2 + 318x + 315
        ```
        """
        await self.do_calculation(ctx, "factor", expression)

    @calculate.command(name="logarithm", aliases=("log",))
    async def calculate_logarithm(self, ctx, base: int, *, expression):
        """Calculates the logarithm with the given base of the given expression.

        **EXAMPLES:**
        ```bnf
        <1> calculate logarithm 2 8
        <2> calculate logarithm 8 5(14) / 2
        ```
        """
        await self.do_calculation(ctx, "log", f"{base} | {expression}")

    @calculate.command(name="tangentline")
    async def calculate_tangentline(self, ctx, x: int, *, expression):
        """Finds the tangent line to the given expression at a given x value.

        **EXAMPLES:**
        ```bnf
        <1> calculate tangentline 2 x^2
        <2> calculate tangentline 3 ln(x^3)
        ```
        """
        await self.do_calculation(ctx, "tangent", f"{x} | {expression}")

    # NOTE: Commented because this consistently returns incorrect
    # answers. See https://github.com/aunyks/newton-api/issues/12
    # @calculate.command(name="xintercepts", aliases=("xints", "zeroes"))
    # async def calculate_zeroes(self, ctx, *, expression):
    #     """Finds the x-intercepts of the given expression.

    #     **EXAMPLES:**
    #     ```bnf
    #     <1> calculate xintercepts x^2 + 2x + 3
    #     <2> calculate xintercepts log(x) - 1
    #     ```
    #     """
    #     await self.do_calculation(ctx, "zeroes", expression)

    @commands.command()
    @commands.bot_has_permissions(embed_links=True)
    async def countryinfo(self, ctx, *, country: str.lower):
        """Gets information about a country.

        (Bot Needs: Embed Links)

        **EXAMPLES:**
        ```bnf
        <1> countryinfo United States of America
        <2> countryinfo China
        <3> countryinfo UK
        """
        resp = await ctx.get(
            f"https://restcountries.com/v2/name/{quote(country)}",
            cache__=True
        )

        try:
            data = await ctx.disambiguate(resp, lambda x: x["name"])
        except ValueError as exc:
            await ctx.send(exc)
            return
        except TypeError:
            # This doesn't return HTTP 404 when a country isn't
            # found, but rather, a dictionary response with the
            # HTTP status. If we're here, then either the input
            # country wasn't found or we got some other "HTTP"
            # error response.
            await ctx.send("Could not find a country with that name.")
            return

        lat, long = data["latlng"]

        try:
            area_km = data["area"]
        except KeyError:
            area = "N/A"
        else:
            area = f"{area_km:,.2f} km² ({area_km / 2.59:,.2f} mi²)"

        embed = Embed(
            title=data["name"],
            description=(
                f"\N{SMALL BLUE DIAMOND} **Capital City:** {data.get('capital', 'N/A')}"
                f"\n\N{SMALL BLUE DIAMOND} **Region:** {data.get('continent', 'N/A')}"
                f"\n\N{SMALL BLUE DIAMOND} **Subregion:** {data['region']}"
                f"\n\N{SMALL BLUE DIAMOND} **Location:** (Lat. {lat:.2f}°, Lon. {long:.2f}°)"
                f"\n\N{SMALL BLUE DIAMOND} **Population:** {data['population']:,d}"
                f"\n\N{SMALL BLUE DIAMOND} **Demonym:** {data['demonym']}"
                f"\n\N{SMALL BLUE DIAMOND} **Land Area:** {area}"
                f"\n\N{SMALL BLUE DIAMOND} **Native Name:** {data['nativeName']}"
                f"\n\N{SMALL BLUE DIAMOND} **ISO 2 Code:** {data['alpha2Code']}"
                f"\n\N{SMALL BLUE DIAMOND} **ISO 3 Code:** {data['alpha3Code']}"
                f"\n\N{SMALL BLUE DIAMOND} **IOC Code:** {data.get('cioc', 'N/A')}"
                f"\n\N{SMALL BLUE DIAMOND} **Gini Index:** {data.get('gini', 'N/A')}"
                f"\n\N{SMALL BLUE DIAMOND} **Top Level Domains:** {', '.join(data['topLevelDomain'])}"
            ),
            colour=0x2F3136
        )
        embed.set_footer(text="Powered by restcountries.com")
        embed.set_thumbnail(url=data["flags"]["png"])

        embed.add_field(
            name="Languages",
            value="\n".join(i['name'] for i in data["languages"])
        )
        embed.add_field(
            name="Currencies",
            value="\n".join(f"{c['name']} ({c['symbol']})" for c in data["currencies"])
        )
        embed.add_field(name="Timezones", value="\n".join(data["timezones"]))

        try:
            embed.add_field(
                name="Regional Blocs",
                value="\n".join(
                    f"{b['name']} ({b['acronym']})"
                    for b in data["regionalBlocs"]),
                inline=False
            )
        except KeyError:
            pass

        await ctx.send(embed=embed)

    @commands.command(aliases=("dictionary", "definition"))
    @checks.can_start_menu(check_embed=True)
    @commands.cooldown(1, 5, commands.BucketType.member)
    async def define(self, ctx, *, term: str.lower):
        """Shows the definition of a word or phrase.

        This command only takes words or phrases in the
        English language. (Sorry non-English speakers)

        (Bot Needs: Embed Links, Add Reactions, and Read Message History)

        **EXAMPLE:**
        ```
        define aloof
        ```
        """
        try:
            resp = await ctx.get(
                f"https://api.dictionaryapi.dev/api/v2/entries/en/{quote(term)}",
                cache__=True
            )
        except HTTPRequestFailed as exc:
            if exc.status == 404:
                await ctx.send("Could not find the definition(s) for that word.")
                return

            raise

        # NOTE: A lot of this data processing is very messy
        # due to how inconsistent and volatile the data from
        # this API is.

        def format_term(term):
            if phonetics := term.get("phonetics"):
                return f"{term['word']} {phonetics[0].get('text', '')}"

            return term["word"]

        try:
            data = await ctx.disambiguate(resp, format_term)
        except ValueError as exc:
            await ctx.send(exc)
            return

        base_embed = Embed(
            description=data.get("origin") or Embed.Empty,
            url=f"https://google.com/search?q=define:+{quote(term)}",
            colour=0x1B1F40
        )
        base_embed.set_footer(text="Powered by dictionaryapi.dev")

        if phonetics := data.get("phonetics"):
            phonetic = phonetics[0]
            base_embed.set_author(name=f"{data['word']} {phonetic.get('text', '')}")

            if audio := phonetic.get("audio"):
                # The API doesn't construct a full URL so I'm forced
                # to add it in using the private attribute.
                base_embed._author["url"] = "https:" + audio
        else:
            base_embed.set_author(name=data["word"])

        embeds = []
        for meaning in data["meanings"]:
            embed = base_embed.copy()

            speech_part = meaning["partOfSpeech"]
            # Humanise camelCase part of speech. In this case,
            # it's usually a cross reference.
            embed.title = "xref" if speech_part == "crossReference" else speech_part

            for index, def_ in enumerate(meaning["definitions"], 1):
                value = def_.get("definition", "[No definition provided for some reason]")

                # These two fields can either be nonexistant or an empty list.
                if example := def_.get("example"):
                    value += f"\n*{example}*"

                if synonyms := def_.get("synonyms"):
                    value += f"\nSimilar: `{', '.join(synonyms[:5])}`"

                embed.add_field(name=f"#{index}", value=value, inline=False)

            embeds.append(embed)

        if embeds:
            await ctx.paginate(menus.EmbedSource(embeds))
        else:
            # Strange case with this API where nothing but the word
            # and phonetic is returned.
            await ctx.send(
                "That word exists in the dictionary, but no further "
                "information was returned for some reason."
            )

    # I don't know what I was on when I actually considered adding this. ok lol.
    @commands.command(aliases=("er", "forex"), require_var_positional=True)
    async def exchangerate(
        self,
        ctx,
        base: str.upper,
        amount: Optional[real_float(max_decimal_places=4)] = 1,
        *currencies: str.upper
    ):
        """Shows the exchange rate between two or more currencies.

        Currency rates tracks foreign exchange references rates
        published by the European Central Bank.

        You can optionally specify the base currency conversion
        amount up to 4 decimal places. By default, this amount
        is 1. The max is 1000000000.

        Currencies must be the ISO 4217 three letter code (i.e.
        USD for United States Dollar, EUR for Euro, etc.). You
        may only convert to 15 different currencies at a time.

        For a list of supported currencies, refer to:
        <https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html>

        **EXAMPLES:**
        ```bnf
        <1> exchangerate GBP USD
        <2> exchangerate EUR 3 USD
        <3> exchangerate USD 10.25 MXN CNY PHP NZD
        ```
        """
        if not 0 < amount <= 1_000_000_000:
            await ctx.send("Conversion amount must be greater than 0 and less than 1000000000.")
            return

        # Probably a niche O(n) check but it saves an HTTP request
        # that would simply include converting base -> base.
        if base in currencies:
            await ctx.send("You cannot convert the base currency to itself.")
            return

        currencies = frozenset(currencies)

        if len(currencies) > 15:
            await ctx.send("You may only convert to 15 different currencies at a time.")
            return

        try:
            resp = await ctx.get(
                "https://api.vatcomply.com/rates",
                cache__=True,
                base=base,
                symbols=",".join(currencies)
            )
        except HTTPRequestFailed as exc:
            if exc.status == 400:
                await ctx.send(exc.data[0]["msg"])
                return

            raise

        updated = datetime.strptime(resp["date"], "%Y-%m-%d")

        # According to the ISO 4217 standard, currencies can
        # have decimal precision between 0-4 places. As of
        # writing, ECB doesn't have any currencies that exceed
        # 2 decimal places.
        await ctx.send(
            "**Exchange Rates** "
            f"(Updated {utils.human_timestamp(updated, 'R')})\n"
            + "\n".join(
                f"{amount:.2f} {base} = {v * amount:.2f} {n}"
                for n, v in resp["rates"].items()
            )
            + "\n`Powered by vatcomply.com`"
        )

    @commands.group(invoke_without_command=True, aliases=("search",))
    @checks.can_start_menu(check_embed=True)
    @commands.cooldown(1, 5, commands.BucketType.member)
    async def google(self, ctx, *, query: str.lower):
        """Searches for something on Google, returning the top 10 results.

        Safe mode is enabled based on whether or not you're
        in an NSFW channel.

        (Bot Needs: Embed Links, Add Reactions, and Read Message History)

        **EXAMPLE:**
        ```
        google lectures
        ```
        """
        await self.do_google_search(ctx, query, search_images=False)

    @google.command(name="imagesearch")
    async def google_imagesearch(self, ctx, *, query: str.lower):
        """Searches for something on Google images, returning the top 10 results.

        Safe mode is enabled based on whether or not you're
        in an NSFW channel.

        (Bot Needs: Embed Links, Add Reactions, and Read Message History)

        **EXAMPLE:**
        ```
        google imagesearch kites
        ```
        """
        await self.do_google_search(ctx, query, search_images=True)

    @commands.command(aliases=("lyrics",))
    @checks.can_start_menu(check_embed=True)
    @commands.cooldown(1, 5, commands.BucketType.member)
    async def genius(self, ctx, *, song_title: str.lower):
        """Gets a song's lyrics.

        (Bot Needs: Embed Links, Add Reactions, and Read Message History)

        **EXAMPLE:**
        ```
        lyrics Haddaway - What is love
        ```
        """
        await ctx.trigger_typing()

        try:
            resp = await ctx.get(
                "https://some-random-api.ml/lyrics",
                cache__=True,
                title=song_title
            )
        except HTTPRequestFailed as exc:
            if exc.status == 404:
                await ctx.send("Couldn't find that song's lyrics.")
                return

            raise

        # Weird case where the API returns an error response
        # with HTTP status code 200.
        if "error" in resp:
            await ctx.send("Couldn't find that song's lyrics.")
            return

        paginator = WrappedPaginator(None, None, 720)

        for line in resp["lyrics"].split("\n"):
            paginator.add_line(line)

        embeds = []
        for page in paginator.pages:
            embed = Embed(
                title=utils.truncate(resp["title"], 128),
                description=page,
                colour=0xFFFF64,
                url=resp["links"]["genius"]
            )
            embed.set_author(name=resp["author"])
            embed.set_thumbnail(url=resp["thumbnail"]["genius"])
            embed.set_footer(text="Powered by some-random-api.ml")

            embeds.append(embed)

        await ctx.paginate(menus.EmbedSource(embeds))

    @commands.command(aliases=("pdex", "pokédex"))
    @commands.bot_has_permissions(embed_links=True)
    async def pokedex(self, ctx, *, pokemon: str.lower):
        """Gets basic information about a Pokémon.

        (Bot Needs: Embed Links)

        **EXAMPLE:**
        ```
        pokedex Litwick
        ```
        """
        try:
            data = await self.get_pokemon_info(ctx, pokemon)
        except HTTPRequestFailed as exc:
            if exc.status == 404:
                await ctx.send("Couldn't find that Pokémon's information.")
                return

            raise

        embed = Embed(
            title=data["name"],
            description=data["flavour_text"],
            url=data["pokedex_url"],
            colour=0x3B4CCA
        )
        embed.set_thumbnail(url=data["front_sprite_url"])
        embed.set_footer(text="Powered by pokeapi.co")

        embed.add_field(name="Pokédex Order", value=data["order"], inline=False)
        embed.add_field(name="Base Experience", value=data["base_experience"])
        embed.add_field(name="Base Happiness", value=data["base_happiness"])
        embed.add_field(name="Capture Rate", value=data["capture_rate"])

        weight = data["weight"]
        embed.add_field(name="Weight", value=f"{weight / 10} kg ({weight / 4.536:.1f} lbs.)")

        height = data["height"]
        feet, inches = divmod(round(height * 3.93701), 12)
        embed.add_field(name="Height", value=f"{height / 10} m ({feet}′{inches:02d}″)")

        embed.add_field(name="Colour", value=data["colour"])

        if (evolves_from := data["evolves_from"]) is not None:
            embed.add_field(name="Previous Evolution", value=evolves_from)

        embed.add_field(name="Abilities", value=data["abilities"])
        embed.add_field(name="Types", value=data["types"])
        embed.add_field(
            name="Stats",
            value=f"```dns\n{utils.tchart(data['stats'])}```",
            inline=False
        )

        await ctx.send(embed=embed)

    @commands.command()
    @checks.can_start_menu()
    async def reddit(self, ctx, subreddit: clean_subreddit):
        """Shows a subreddit's top weekly submissions.

        The posts displayed are based on whether or not
        this command was executed in an NSFW channel.

        (Bot Needs: Embed Links, Add Reactions, and Read Message History)

        **EXAMPLES:**
        ```bnf
        <1> reddit help
        <2> reddit r/help
        ```
        """
        try:
            resp = await ctx.get(
                f"https://reddit.com/r/{subreddit}/hot.json",
                cache__=True
            )
        except HTTPRequestFailed as exc:
            # For reference:
            # - 403 -> either private or quarantined.
            # - 404 -> either nonexistent or banned.
            if exc.status in (403, 404):
                await ctx.send("I can't access any posts on that subreddit.")
                return

            raise

        embeds = []
        for child in resp["data"]["children"]:
            post = child["data"]

            if not ctx.channel.is_nsfw() and post["over_18"]:
                continue

            embed = Embed(
                title=utils.truncate(post["title"], 128),
                description=utils.truncate(post["selftext"], 1024),
                url=f"https://reddit.com/{post['id']}",
                colour=0xFF5700
            )
            embed.set_author(
                name=f"u/{post['author']} (r/{subreddit})",
                url=f"https://reddit.com/user/{post['author']}"
            )
            embed.set_footer(
                text=f"\N{UPWARDS BLACK ARROW}\ufe0f {post['ups']:,d} "
                     "\N{BULLET} Powered by Reddit"
            )

            if not embed.description:
                media_url = post["url"]

                embed.description = f"[Media Link]({media_url})"
                embed.set_image(url=media_url)

            embeds.append(embed)

        if not embeds:
            await ctx.send("That subreddit doesn't have any posts.")
        else:
            await ctx.paginate(menus.EmbedSource(embeds))

    @commands.command(aliases=("ss", "snapshot"))
    @commands.bot_has_permissions(embed_links=True)
    @commands.cooldown(1, 10, commands.BucketType.member)  # So we don't overload magmafuck.
    async def screenshot(self, ctx, url):
        """Screenshots a website.

        **DISCLAIMER:** Due to a limitation with the service,
        websites are not checked for any NSFW content before
        screenshotting.

        (Bot Needs: Embed Links)

        **EXAMPLE:**
        ```
        screenshot google.com
        ```
        """
        async with ctx.typing():
            try:
                resp = await ctx.get(
                    "https://magmafuck.herokuapp.com/api/v1",
                    headers__={"website": url.strip("<>")}
                )
            except HTTPRequestFailed as exc:
                # MagmaChain is a Heroku free tier service so it fluctuates often.
                if exc.status == 503:
                    await ctx.send("MagmaChain is down right now. Try again later?")
                    return

                raise

        # Sometimes, a TypeError gets thrown internally on MagmaChain's
        # end and, for some reason, causes the API to return a response
        # containing the traceback (as a string) on HTTP status 200.
        if not isinstance(resp, dict):
            await ctx.send("Something went wrong internally on MagmaChain's end. Try again later?")
            return

        embed = Embed(
            title="Snapshot",
            description=f"[Link to Website]({resp['website']})",
            color=0x2F3136,
            timestamp=datetime.utcnow()
        )
        embed.set_image(url=resp["snapshot"])
        embed.set_footer(
            text=f"Requested by: {ctx.author} \N{BULLET} Powered by magmafuck.herokuapp.com"
        )

        await ctx.send(embed=embed)

    @commands.command()
    @commands.bot_has_permissions(embed_links=True)
    async def steaminfo(self, ctx, *, account: SteamAccountMeta):
        """Gets information about a Steam account.

        Argument can either be a Steam ID 64, vanity username, or link.

        (Bot Needs: Embed Links)

        **EXAMPLES:**
        ```bnf
        <1> steaminfo https://steamcommunity.com/profiles/76561192109582121
        <2> steaminfo https://steamcommunity.com/id/ReallyCoolExampleVanity
        <3> steaminfo 76561192109582121
        <4> steaminfo ReallyCoolExampleVanity
        ```
        """
        resp = await ctx.get(
            "https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v2",
            key=self.steam_api_key,
            steamids=account.id_64,
            cache__=True
        )

        accounts = resp["response"]["players"]

        if not accounts:
            await ctx.send("That Steam user wasn't found.")
            return

        data = accounts[0]
        status = data["personastate"]
        avatar_url = data["avatarfull"]

        steam_statuses = (
            "Offline",
            "Online",
            "Busy",
            "Away",
            "Snooze",
            "Looking to Trade",
            "Looking to Play",
        )

        embed = Embed(
            description=(
                f"**[Avatar Link]({avatar_url})**"
                f"\n\N{SMALL BLUE DIAMOND} **Steam ID 64:** {account.id_64}"
                f"\n\N{SMALL BLUE DIAMOND} **Steam ID:** {account.id}"
                f"\n\N{SMALL BLUE DIAMOND} **Steam ID 3:** {account.id_3}"
                f"\n\N{SMALL BLUE DIAMOND} **Status:** {steam_statuses[status]}"
            ),
            colour=0x555555 if status == 0 else 0x53A4C4
        )
        embed.set_author(name=data["personaname"], url=data["profileurl"])
        embed.set_footer(text="Showing basic public information. \N{BULLET} Powered by Steam")
        embed.set_thumbnail(url=avatar_url)

        await ctx.send(embed=embed)

    @commands.command(aliases=("tr",))
    @commands.bot_has_permissions(embed_links=True)
    @commands.cooldown(1, 5, commands.BucketType.member)  # Curb possibility of being blocked.
    async def translate(
        self,
        ctx,
        destination: _pseudo_argument_flag(">", separator=">"),
        source: Optional[_pseudo_argument_flag("$", separator="$")] = "auto",
        *,
        text: commands.clean_content(fix_channel_mentions=True) = None
    ):
        """Translates some text using Google Translate.
        This allows you to either provide text or use a
        message's text content via replying.

        To specify a source or destination language, prefix
        the language with either a `$` or `>`, respectively,
        prior to the text argument.

        Specifying the source language is optional, but
        may improve translation accuracy. If the source
        language is omitted, then it will automatically
        be determined when translating.

        For a list of valid languages, refer to:
        <https://cloud.google.com/translate/docs/languages>

        **EXAMPLES:**
        ```bnf
        <1> translate >spanish Hello!
        <2> translate >ja Goodbye!
        <3> translate >english $german Guten tag!
        <4> translate >en $tl Salamat po!
        ```
        """
        if text is None:
            ref = ctx.message.reference

            if ref is None or not isinstance(ref.resolved, discord.Message):
                await ctx.send("You must provide some text to translate.")
                return

            text = ref.resolved.content

            # It's unfortunate that we have to do this check twice, but
            # messages can have no text content and the translator will
            # throw a TypeError if an empty string is passed.
            if not text:
                await ctx.send("That message doesn't have any text content.")
                return

        try:
            tsl = await self.translator.translate(text, destination, source)
        except ValueError:
            await ctx.send("Invalid source or destination language.")
            return
        except Exception as exc:
            await ctx.send(f"An error occurred while translating: {exc}")
            return

        embed = Embed(description=utils.truncate(tsl.text, 2048), colour=0x4285F4)
        embed.set_author(name=ctx.author, icon_url=ctx.author.avatar_url)
        embed.set_thumbnail(
            url="https://cdn.discordapp.com/attachments/507971834570997765/861166905569050624/translate2021.png"
        )

        embed.set_footer(
            text=f"{LANGUAGES.get(tsl.src, '(Auto-detected)').title()} ({tsl.src}) "
                 "\N{THREE-D BOTTOM-LIGHTED RIGHTWARDS ARROWHEAD} "
                 f"{LANGUAGES.get(tsl.dest, 'Unknown').title()} ({tsl.dest}) "
                 "\N{BULLET} Powered by Google Translate"
        )

        await ctx.send(embed=embed)

    @translate.error
    async def on_translate_error(self, ctx, error):
        if isinstance(error, commands.BadArgument):
            await ctx.send("Destination language must begin with `>`.")
            error.handled__ = True

    @commands.command(aliases=("urban", "urbanup"))
    @checks.can_start_menu(check_embed=True)
    @commands.cooldown(1, 5, commands.BucketType.member)
    async def urbandict(self, ctx, *, term: str.lower):
        """Searches for a term on Urban Dictionary.

        (Bot Needs: Embed Links)

        **EXAMPLE:**
        ```
        urbandict gl2u
        ```
        """
        resp = await ctx.get(
            "https://api.urbandictionary.com/v0/define",
            cache__=True,
            term=term
        )

        entries = resp["list"]

        if not entries:
            await ctx.send("That term isn't on Urban Dictionary.")
            return

        def apply_hyperlinks(string):

            def hyperlink_brackets(m):
                word = m.group(1).strip("[]")
                return f"[{word}](http://{word.replace(' ', '-')}.urbanup.com)"

            return re.sub(r"(\[.+?])", hyperlink_brackets, string)

        embeds = []
        for entry in entries:
            embed = Embed(
                description=textwrap.shorten(apply_hyperlinks(entry["definition"]), 2000),
                timestamp=discord_parse_time(entry["written_on"][:-1]),
                colour=0x1D2439
            )
            embed.set_author(name=entry["word"], url=entry["permalink"])
            embed.set_footer(
                text=f"Written by: {entry['author']} \N{BULLET} Powered by Urban Dictionary"
            )

            if example := entry["example"]:
                embed.add_field(
                    name="Example",
                    value=textwrap.shorten(apply_hyperlinks(example), 1000),
                    inline=False
                )

            embed.add_field(name=":thumbsup:", value=entry["thumbs_up"])
            embed.add_field(name=":thumbsdown:", value=entry["thumbs_down"])

            embeds.append(embed)

        await ctx.paginate(menus.EmbedSource(embeds))

    @commands.command(aliases=("vredditdownloader",))
    @commands.bot_has_permissions(attach_files=True)
    async def vreddit(self, ctx, *, url: RedditSubmissionURL):
        """Downloads a Reddit video submission.
        Both v.redd.it and regular Reddit links are
        supported.

        Due to a limitation with how Reddit handles
        and stores videos internally, this command
        can only download videos **without** audio.

        (Bot Needs: Attach Files)
        """
        # We have to directly use the session since our requester
        # doesn't return response headers. Also, it's better not
        # to read the data anyway before checking its size.
        async with ctx.session.get(url) as resp:
            if resp.status != 200:
                await ctx.send("Failed to download the video.")
                return

            limit = ctx.guild.filesize_limit if ctx.guild is not None else 8_388_608

            if int(resp.headers["Content-Length"]) > limit:
                await ctx.send("The video is too big to be uploaded.")
                return

            await ctx.send(
                f"Requested by {ctx.author} (ID: {ctx.author.id})",
                file=File(io.BytesIO(await resp.read()), "submission.mp4")
            )

    @reddit.error
    @steaminfo.error
    @vreddit.error
    async def on_entity_command_error(self, ctx, error):
        if isinstance(error, commands.BadArgument):
            await ctx.send(error)
            error.handled__ = True

    @commands.command()
    @commands.bot_has_permissions(embed_links=True)
    async def weather(self, ctx, *, location: str.lower):
        """Gets the current weather data for a location.

        Location can be either a US zip code, UK postal code,
        Canadian postal code, IP address, latitude/longitude
        (decimal degree), or city name.

        (Bot Needs: Embed Links)

        **EXAMPLES:**
        ```bnf
        <1> weather London
        <2> weather Munich, Germany
        <3> weather Wuhan, Hubei, China
        <4> weather 72201
        <5> weather BR1 1AH5
        <6> weather A2B 3C4
        <7> weather 138.192.233.169
        <8> weather 35.73 51.33
        ```
        """
        try:
            resp = await ctx.get(
                "https://api.weatherapi.com/v1/current.json",
                cache__=True,
                key=self.weatherapi_api_key,
                q=location
            )
        except HTTPRequestFailed as exc:
            if exc.status == 400:
                await ctx.send("Current weather data is unavailable for that location.")
                return

            raise

        data = resp["current"]
        loc = resp["location"]
        region = loc["region"]

        embed = Embed(
            title=f"{loc['name']}, {region + ', ' if region else ''}{loc['country']}",
            description=f"(Lat. {loc['lat']}°, Lon. {loc['lon']}°)",
            colour=0xE3C240 if data["is_day"] == 1 else 0x1D50A8,
            timestamp=datetime.utcfromtimestamp(data["last_updated_epoch"])
        )

        condition = data["condition"]

        embed.set_author(name=condition["text"], icon_url=f"https:{condition['icon']}")
        embed.set_footer(text="Powered by weatherapi.com \N{BULLET} Last Updated")

        embed.add_field(
            name="Temperature",
            value=f"{data['temp_c']}°C ({data['temp_f']}°F)\n"
                  f"Feels Like: {data['feelslike_c']}°C ({data['feelslike_f']}°F)",
        )
        embed.add_field(
            name="Wind Speed",
            value=f"{data['wind_kph']} kph ({data['wind_mph']} mph) {data['wind_dir']}"
        )
        embed.add_field(
            name="Wind Gust",
            value=f"{data['gust_kph']} kph ({data['gust_mph']} mph)"
        )
        embed.add_field(
            name="Precipitation",
            value=f"{data['precip_mm']} mm ({data['precip_in']} in.)"
        )
        embed.add_field(name="Humidity", value=f"{data['humidity']}%")
        embed.add_field(name="Cloud Coverage", value=f"{data['cloud']}%")
        embed.add_field(
            name="Atmospheric Pressure",
            value=f"{data['pressure_mb']} mb ({data['pressure_in']} in. Hg)"
        )
        embed.add_field(
            name="Visibility",
            value=f"{data['vis_km']} km ({data['vis_miles']} mi)"
        )
        embed.add_field(name="UV Index", value=data["uv"])

        await ctx.send(embed=embed)

    @commands.command(aliases=("wiki",))
    @commands.bot_has_permissions(embed_links=True)
    async def wikipedia(self, ctx, *, article):
        """Searches for something on Wikipedia.

        (Bot Needs: Embed Links)

        **EXAMPLES:**
        ```bnf
        <1> wikipedia Shakespeare
        <2> wikipedia Python (Programming Language)
        ```
        """
        try:
            resp = await ctx.get(
                f"https://en.wikipedia.org/api/rest_v1/page/summary/{quote(article)}?redirect=true",
                cache__=True,
            )
        except HTTPRequestFailed as exc:
            if exc.status == 404:
                await ctx.send("That article wasn't found.")
                return

            raise

        embed = Embed(
            description=resp["extract"],
            colour=0xE3E3E3,
            timestamp=datetime.strptime(resp["timestamp"], "%Y-%m-%dT%H:%M:%SZ")
        )
        embed.set_author(
            name=utils.truncate(resp["title"], 128),
            url=resp["content_urls"]["desktop"]["page"],
            icon_url="https://w.wiki/3dCP"
        )
        embed.set_footer(text="Powered by Wikipedia \N{BULLET} Last Edited")

        try:
            embed.set_thumbnail(url=resp["originalimage"]["source"])
        except KeyError:
            pass

        await ctx.send(embed=embed)

    @commands.group(invoke_without_command=True)
    @commands.bot_has_permissions(embed_links=True)
    async def xkcd(self, ctx, number: int = None):
        """Shows a comic from xkcd.

        If no comic number is given, then the latest
        comic will be shown instead.

        (Bot Needs: Embed Links)

        **EXAMPLE:**
        ```
        xkcd 407
        ```
        """
        if number is None:
            comic_url = "https://xkcd.com/info.0.json"
        elif number == 404:
            await ctx.send("Nice try, but I won't be searching for that comic.")
            return
        else:
            comic_url = f"https://xkcd.com/{number}/info.0.json"

        try:
            comic = await ctx.get(comic_url, cache__=True)
        except HTTPRequestFailed as exc:
            if exc.status == 404:
                await ctx.send("Invalid comic number.")
                return

            raise

        await self.send_formatted_comic_embed(ctx, comic)

    @xkcd.command(name="random", aliases=("r",))
    async def xkcd_random(self, ctx):
        """Shows a random xkcd comic.

        (Bot Needs: Embed Links)
        """
        # This command is written this way in order to avoid
        # picking comic 404, since it doesn't actually exist.
        # Getting the 1-403 bound doesn't need a request and
        # also has the benefit of skipping a cache lookup as
        # opposed to the previous (non-working) approach.
        if random.random() < 0.5:
            number = random.randint(1, 403)
        else:
            # Because of how xkcd's API is designed, we need
            # to get the total number of comics on the site.
            # This can be done by getting the latest comic.
            resp = await ctx.get("https://xkcd.com/info.0.json", cache__=True)
            number = random.randint(405, resp["num"])

        comic = await ctx.get(
            f"https://xkcd.com/{number}/info.0.json",
            cache__=True
        )

        await self.send_formatted_comic_embed(ctx, comic)

    @commands.command(aliases=("ytinfo",))
    @commands.bot_has_permissions(embed_links=True)
    async def youtubeinfo(self, ctx, channel: youtube_channel_kwargs):
        """Gets information about a YouTube channel.

        Argument can either be a channel ID, username, or link.
        Links are generally the easiest and most accurate.

        (Bot Needs: Embed Links)

        **EXAMPLES:**
        ```bnf
        <1> youtubeinfo https://youtube.com/channel/UC57ZBb_D-YRsCxnsdHGSxSQ
        <2> youtubeinfo https://youtube.com/user/SomeReallyCoolVanityHere
        <3> youtubeinfo https://youtube.com/c/SomeReallyCoolVanityHere
        <4> youtubeinfo https://youtube.com/SomeReallyCoolVanityHere
        <5> youtubeinfo UC57ZBb_D-YRsCxnsdHGSxSQ
        <6> youtubeinfo SomeReallyCoolVanityHere
        ```
        """
        resp = await ctx.get(
            "https://www.googleapis.com/youtube/v3/channels?part=statistics,snippet",
            cache__=True,
            key=self.google_api_key,
            maxResults=1,
            **channel
        )

        try:
            results = resp["items"]
        except KeyError:
            await ctx.send("YouTube channel not found.")
            return

        data = results[0]
        stats = data["statistics"]
        snippet = data["snippet"]
        channel_id = data["id"]

        embed = Embed(description=snippet["localized"]["description"], colour=0xFF0000)

        try:
            embed.timestamp = datetime.strptime(snippet["publishedAt"], "%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            # For some reason, it seems that only channels created
            # after some date in 2019(?) have fractions of seconds
            # in their creation timestamps.
            embed.timestamp = datetime.strptime(snippet["publishedAt"], "%Y-%m-%dT%H:%M:%S.%fZ")

        embed.set_author(
            name=snippet["title"],
            url=f"https://youtube.com/channel/{channel_id}"
        )
        embed.set_thumbnail(url=snippet["thumbnails"]["high"]["url"])
        embed.set_footer(text="Powered by YouTube \N{BULLET} Created")

        if not stats["hiddenSubscriberCount"]:
            embed.add_field(
                name="Subscribers",
                value=utils.human_number(int(stats["subscriberCount"]))
            )

        embed.add_field(name="Views", value=f"{int(stats['viewCount']):,d}")
        embed.add_field(name="Videos", value=f"{int(stats['videoCount']):,d}")

        try:
            embed.add_field(name="Country", value=snippet["country"])
        except KeyError:
            pass

        embed.add_field(name="Channel ID", value=channel_id)

        await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(Web(bot.config))
