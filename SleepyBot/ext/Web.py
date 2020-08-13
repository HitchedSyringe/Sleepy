"""
© Copyright 2018-2020 HitchedSyringe, All Rights Reserved.

Redistributing, using or owning a copy of this software without explicit permissions
is against these licensing terms, your license(s) to this software can be revoked at
any time without explicit notice beforehand and at the time of revocation.
Your license is non-transferrable, the terms of this license only permit you to do the
following; Create pull requests and make modifications to this repository.

"""


import random
import re
import textwrap
from collections import defaultdict
from datetime import datetime
from typing import Optional
from urllib.parse import quote as urlquote

import discord
import googletrans
from discord import Embed
from discord.ext import commands

from SleepyBot.utils import checks, formatting, reaction_menus
from SleepyBot.utils.requester import HTTPError


BRACKET_REGEX = re.compile(r"(\[(.+?)\])")


def _repl_brackets(match):
    """Helper that replaces bracketed words with hyperlinks."""
    word = match.group(2)
    return f"[{word}](https://{word.replace(' ', '-')}.urbanup.com)"


def _clean_currency(value: str) -> str:
    """Psuedo-converter that validates currency codes.
    Raises :exc:`commands.BadArgument` if the currency code doesn't follow the ISO 4217 standard.
    """
    if not value.isalpha() or len(value) != 3:
        raise commands.BadArgument("Currency codes must follow the ISO 4217 standard.")
    return value.upper()


def _format_term(term_data: dict) -> str:
    """Helper that formats the term in the disambiguation menu."""
    phonetics = term_data.get("phonetics")
    if phonetics:
        return f"{term_data['word']} {phonetics[0].get('text', '')}"

    return term_data["word"]


YOUTUBE_URL_REGEX = re.compile(r"(?:https?\:\/\/)?(?:www\.)?youtube\.com\/(c|user|channel)\/([\w\-]+)\/?")
YOUTUBE_ID_REGEX = re.compile(r"(?P<id>UC[\w\-]{21}[AQgw])")


def _youtube_channel(value: str) -> dict:
    """Psuedo-converter that validates YouTube channel URLs, usernames and IDs.
    Returns a :class:`dict` mapping the API filter route and value.
    """
    url_match = YOUTUBE_URL_REGEX.fullmatch(value.strip("<>"))

    if url_match is not None:
        path, argument = url_match.groups()
        return {"id" if path == "channel" else "forUsername": argument}

    return {"id" if YOUTUBE_ID_REGEX.fullmatch(value) is not None else "forUsername": value}


STEAM_URL_REGEX = re.compile(r"(?:https?\:\/\/)?(?:www\.)?steamcommunity\.com\/(?:profile|id)\/([\w\-]{2,})\/?")

STEAM_PERSONA_STATES = {
    0: "Offline",
    1: "Online",
    2: "Busy",
    3: "Away",
    4: "Snooze",
    5: "Looking to Trade",
    6: "Looking to Play",
}


def _resolve_steam_identifier(value: str) -> str:
    """Psuedo-converter that resolves the Steam account identifier from the URL, if given.
    Otherwise, the string is returned as-is.
    """
    url_match = STEAM_URL_REGEX.fullmatch(value.strip("<>"))
    if url_match is not None:
        return url_match.group(1)

    return value


# Unfortinately, we have to have two separate but similar psuedo-converter
# functions due to the weird syntax of the translate command.
def _parse_source(value: str) -> str:
    """Psuedo-converter that resolves the source language code.
    Raises :exc:`commands.BadArgument` if the input doesn't begin with `]` or the language code is invalid.
    """
    # Raising BadArgument probably shouldn't matter here since this gets wrapped in ``Optional`` anyway.
    if not value.startswith("]"):
        raise commands.BadArgument("You must specify a language to translate from.")

    code = value[1:].lower()

    if len(code) != 2 and code not in ("zh-cn", "zh-tw") and not code.isalpha():
        raise commands.BadArgument("Invalid language code.")

    return code


def _parse_destination(value: str) -> str:
    """Psuedo-converter that resolves the destination language code.
    Raises :exc:`commands.BadArgument` if the input doesn't begin with `}` or the language code is invalid.
    """
    if not value.startswith("}"):
        raise commands.BadArgument("You must specify a language to translate to.")

    code = value[1:].lower()

    if len(code) != 2 and code not in ("zh-cn", "zh-tw") and not code.isalpha():
        raise commands.BadArgument("Invalid language code.")

    return code


class Web(commands.Cog,
          command_attrs=dict(cooldown=commands.Cooldown(rate=2, per=5, type=commands.BucketType.member))):
    """Commands that grab data from various websites/APIs.
    These are usually intended to serve as utilities in a sense.
    """

    def __init__(self, bot):
        self._google_api_keys = defaultdict(lambda: set(bot.config["Secrets"].getjson("google_api_keys")))
        self._translator = googletrans.Translator()


    @staticmethod
    def _format_xkcd_comic(comic: dict) -> Embed:
        """Formats the xkcd comic data into a readable embed.
        For internal use only.
        """
        embed = Embed(
            title=f"Comic #{comic['num']} {comic['title']}",
            description=comic["alt"],
            url=f"https://xkcd.com/{comic['num']}",
            timestamp=datetime(month=int(comic["month"]), year=int(comic["year"]), day=int(comic["day"])),
            colour=0x708090
        )
        embed.set_image(url=comic["img"])
        embed.set_footer(text="Powered by xkcd.com")
        return embed


    async def _do_google_search(self, ctx, *, query: str, images: bool = False, cache: bool = False):
        """Performs a search on Google, while also managing API keys.
        For internal use only.
        """
        api_keys = self._google_api_keys["customsearch"]

        await ctx.trigger_typing()

        while api_keys:
            key = next(iter(api_keys))

            try:
                response = await ctx.get(
                    "https://www.googleapis.com/customsearch/v1?searchInformation,items(title,link,snippet)",
                    key=key,
                    cx=ctx.bot.config["Secrets"]["google_search_engine_id"],
                    q=query,
                    safe="off" if ctx.channel.is_nsfw() else "active",
                    searchType="image" if images else "search_type_undefined",
                    cache=cache
                )
            except HTTPError as exc:
                if exc.status == 403 and exc.data["error"]["errors"][0]["reason"] == "dailyLimitExceeded":
                    api_keys.remove(key)
                    continue
                raise

            break
        else:
            await ctx.send("Well this is embarassing.\nI seem to have exceeded my usage quota on Google.")
            return

        results = response.get("items")
        if results is None:
            await ctx.send("No results found.")
            return

        base_embed = Embed(colour=0x4C8BF5)
        base_embed.set_author(
            name=f"Results for '{formatting.simple_shorten(query, 64)}'",
            url=f"https://www.google.com/search?q={urlquote(query)}"
        )

        total_results = response["searchInformation"]["formattedTotalResults"]
        query_time = response["searchInformation"]["formattedSearchTime"]
        base_embed.set_footer(
            text=f"About {total_results} results. ({query_time} seconds) | Powered by Google"
        )

        embeds = []
        for result in results:
            embed = base_embed.copy()

            if images:
                embed.title = result["snippet"]  # title and snippet are essentially the same in this case.
                url = result.get("link")
                if url is not None:
                    embed.set_image(url=url)
            else:
                embed.title = result.get("title")
                embed.url = result.get("url")
                embed.description = result["snippet"]

            embeds.append(embed)

        await ctx.paginate(reaction_menus.EmbedSource(embeds))


    @commands.command()
    @checks.bot_has_permissions(embed_links=True)
    async def countryinfo(self, ctx: commands.Context, *, country_name: str):
        """Gets information about a country.
        (Bot Needs: Embed Links)

        EXAMPLE:
        (Ex. 1) countryinfo United States of America
        (Ex. 2) countryinfo China
        (Ex. 3) countryinfo UK
        """
        await ctx.trigger_typing()
        try:
            response = await ctx.get(f"https://restcountries.eu/rest/v2/name/{urlquote(country_name)}", cache=True)
        except HTTPError as exc:
            if exc.status == 404:
                await ctx.send("Could not find a country with that name.")
                return
            raise

        try:
            country = await ctx.disambiguate(response, lambda x: f"{x['name']} ({x['alpha2Code']})")
        except ValueError as exc:
            await ctx.send(str(exc))
            return

        iso_two = country['alpha2Code']

        embed = Embed(title=f"{country['name']} ({iso_two})", colour=0x2F3136)
        embed.set_footer(text="Powered by restcountries.eu")

        # Although the API itself *does* provide country flags, they're in .svg format and can't be used in embeds.
        # So instead, I'll use this alternate method of getting the flags for now.
        embed.set_thumbnail(
            url=f"https://raw.githubusercontent.com/hjnilsson/country-flags/master/png1000px/{iso_two.lower()}.png"
        )

        population = f"{country['population']:,d}" if country["population"] is not None else "N/A"

        if country["latlng"]:
            latitude, longitude = country["latlng"]
            location = f"(Lat. {latitude:.2f}°, Lon. {longitude:.2f}°)"
        else:
            location = "N/A"

        area = f"{country['area']:,.2f} km²" if country["area"] is not None else "N/A"

        description = (
            f"**Capital City:** {country['capital'] or 'N/A'}",
            f"**Population:** {population}",
            f"**Location:** {location}",
            f"**Land Area:** {area}",
            f"**Demonym:** {country['demonym'] or 'N/A'}",
            f"**Region:** {country['region'] or 'N/A'}",
            f"**Subregion:** {country['subregion'] or 'N/A'}",
            f"**Native Name:** {country['nativeName']}",
            f"**ISO2 Code:** {iso_two}",
            f"**ISO3 Code:** {country['alpha3Code']}",
            f"**GINI Index:** {country['gini'] or 'N/A'}",
            f"**Web Domain Endings:** {', '.join(country['topLevelDomain']) or 'N/A'}",
        )
        embed.description = "\n".join(f"<:arrow:713872522608902205> {e}" for e in description)

        embed.add_field(name="**Timezones**", value="\n".join(country["timezones"]))
        embed.add_field(
            name="**Languages**",
            value="\n".join(f"{l['name']} ({l['nativeName']})" for l in country["languages"]) or "N/A"
        )
        embed.add_field(
            name="**Currencies**",
            value="\n".join(f"[{c['code']}] {c['name']} ({c['symbol']})" for c in country["currencies"]) or "N/A",
            inline=False
        )
        embed.add_field(
            name="**Regional Blocs**",
            value="\n".join(f"{b['name']} ({b['acronym']})" for b in country["regionalBlocs"]) or "N/A",
            inline=False
        )

        await ctx.send(embed=embed)


    @commands.command(aliases=["dictionary", "definition"])
    @checks.bot_has_permissions(embed_links=True, add_reactions=True, read_message_history=True)
    @commands.cooldown(rate=1, per=5, type=commands.BucketType.member)
    async def define(self, ctx: commands.Context, *, term: str):
        """Shows the dictionary definition of a word or phrase.
        This command only takes words or phrases in the English language. (Sorry non-English speakers)
        (Bot Needs: Embed Links, Add Reactions and Read Message History)

        EXAMPLE: define aloof
        """
        await ctx.trigger_typing()
        try:
            response = await ctx.get(f"https://api.dictionaryapi.dev/api/v2/entries/en/{urlquote(term)}", cache=True)
        except HTTPError as exc:
            if exc.status == 404:
                await ctx.send("Could not find the definition(s) for that word.")
                return
            raise

        try:
            term_data = await ctx.disambiguate(response, _format_term)
        except ValueError as exc:
            await ctx.send(str(exc))
            return

        base_embed = Embed(
            description=term_data.get("origin", Embed.Empty),
            url=f"https://www.google.com/search?q=define:+{urlquote(term)}",
            colour=0x1B1F40
        )

        phonetics = term_data.get("phonetics")
        if phonetics:
            phonetic = phonetics[0]
            base_embed.set_author(
                name=f"{term_data['word']} {phonetic.get('text', '')}",
                url=phonetic.get("audio", Embed.Empty)
            )
        else:
            base_embed.set_author(name=term_data['word'])

        base_embed.set_footer(text="Powered by api.dictionaryapi.dev")

        embeds = []
        for meaning in term_data["meanings"]:
            embed = base_embed.copy()

            part_of_speech = meaning["partOfSpeech"]
            # Cross references are the only camelCase part of speech so we should humanise them.
            embed.title = part_of_speech if part_of_speech != "crossReference" else "xref"

            for index, definition in enumerate(meaning["definitions"], 1):
                field_value = f"{definition.get('definition', '[No definition provided for some reason]')}\n"

                example = definition.get("example")
                synonyms = definition.get("synonyms")

                if example is not None:
                    field_value += f"*{example}*\n"

                if synonyms is not None:
                    # Due to char limits we only display a certain amount of synonyms.
                    field_value += f"Similar: `{', '.join(synonyms[:10])}`"

                embed.add_field(
                    name=f"#{index}",
                    value=field_value or "[No examples or synonyms provided]",
                    inline=False
                )

            embeds.append(embed)

        if embeds:
            await ctx.paginate(reaction_menus.EmbedSource(embeds))
        else:
            # Strange case with this API where nothing else is returned but the word and phonetic.
            await ctx.send("That word exists in the dictionary, but for some reason, no further info was returned.")


    # I don't know what I was on when I actually considered adding this. ok lol.
    @commands.command()
    async def exchangerate(self, ctx: commands.Context,
                           base: _clean_currency, amount: Optional[float] = 1, *currencies: _clean_currency):
        """Calculates the exchange rate between two or more currencies.
        Optionally, you can specify the amount of the base currency to convert from.
        By default, the amount to convert from is 1. The max is 10000000000000.
        You may only convert to 15 different currencies at a time.

        Currencies must be the ISO 4217 three letter code (i.e. USD for United States Dollar, EUR for Euro, etc.)
        *This only displays exchange rates published by the European Central Bank.*

        EXAMPLE:
        (Ex. 1) exchangerate GBP USD
        (Ex. 2) exchangerate EUR 3 USD
        (Ex. 3) exchangerate USD 10.25 MXN CNY PHP NZD
        """
        # We'll just cap it at 10,000,000,000,000 in order to prevent overflows.
        if amount <= 0 or amount > 10_000_000_000_000:
            await ctx.send("Amount must be greater than 0 and less than 10000000000000.")
            return

        if not currencies:
            await ctx.send("You must enter at least one currency to convert to.")
            return

        if base in currencies:
            # Bit of a niche thing to prevent users from doing base -> base only.
            await ctx.send("You cannot convert the base currency to itself.")
            return

        # Don't penalise people for putting in the same currency to convert to.
        currencies = frozenset(currencies)

        if len(currencies) > 15:
            await ctx.send("You may only convert to 15 different currencies at a time.")
            return

        await ctx.trigger_typing()
        try:
            response = await ctx.get(
                "https://api.exchangeratesapi.io/api/latest?",
                base=base,
                symbols=",".join(currencies),
                cache=True
            )
        except HTTPError as exc:
            if exc.status == 400:
                await ctx.send("Either the base currency or one of the currencies to convert to were invalid.")
                return
            raise

        # According to the ISO 4217 standard, currencies can have decimal precision between 0-4 places.
        # As of writing, ECB doesn't have any currencies that exceed 2 decimal places.
        rates = "\n".join(f"{amount:.2f} {base} = {v * amount:.2f} {n}" for n, v in response["rates"].items())
        await ctx.send(f"**Exchange Rates**\n{rates}\n`Powered by api.exchangeratesapi.io`")


    @commands.group(invoke_without_command=True, aliases=["search"])
    @checks.bot_has_permissions(embed_links=True, add_reactions=True, read_message_history=True)
    @commands.cooldown(rate=1, per=5, type=commands.BucketType.member)
    async def google(self, ctx: commands.Context, *, query: str):
        """Searches for something on Google, returning the top 10 results.
        Safe mode is enabled based on whether or not you're in an NSFW channel.
        Subcommand "imagesearch" searches through Google images.
        (Bot Needs: Embed Links, Add Reactions and Read Message History)

        EXAMPLE: google lectures
        """
        await self._do_google_search(ctx, query=query, images=False, cache=True)


    @google.command(name="imagesearch")
    async def google_imagesearch(self, ctx: commands.Context, *, query: str):
        """Searches for something on Google images, returning the top 10 results.
        Safe mode is enabled based on whether or not you're in an NSFW channel.
        (Bot Needs: Embed Links, Add Reactions and Read Message History)

        EXAMPLE: google imagesearch kites
        """
        await self._do_google_search(ctx, query=query, images=True, cache=True)


    @commands.command()
    @checks.bot_has_permissions(embed_links=True, add_reactions=True, read_message_history=True)
    @commands.cooldown(rate=1, per=5, type=commands.BucketType.member)
    async def lyrics(self, ctx: commands.Context, *, song: str):
        """Gets a song's lyrics.
        (Bot Needs: Embed Links, Add Reactions and Read Message History)

        EXAMPLE: lyrics Haddaway - What is love
        """
        await ctx.trigger_typing()
        try:
            response = await ctx.get("https://some-random-api.ml/lyrics", title=song, cache=True)
        except HTTPError as exc:
            if exc.status == 404:
                await ctx.send("Couldn't find that song's lyrics.")
                return
            raise

        # Weird case where the API succeeds, but returns an invalid JSON response.
        if "error" in response:
            await ctx.send("Couldn't find that song's lyrics.")
            return

        base_embed = Embed(
            colour=0xFFFF64,
            title=formatting.simple_shorten(response["title"], 128),
            url=response["links"]["genius"]
        )
        base_embed.set_author(name=response["author"])
        base_embed.set_thumbnail(url=response["thumbnail"]["genius"])
        base_embed.set_footer(text="Powered by some-random-api.ml")

        # 720 characters for smaller embeds I guess.
        paginator = commands.Paginator(prefix="", suffix="", max_size=720)
        for line in response["lyrics"].split("\n"):
            paginator.add_line(line)

        embeds = []
        for page in paginator.pages:
            embed = base_embed.copy()
            embed.description = page
            embeds.append(embed)

        await ctx.paginate(reaction_menus.EmbedSource(embeds))


    @commands.command(aliases=["pdex", "pokédex"])
    @checks.bot_has_permissions(embed_links=True)
    async def pokedex(self, ctx: commands.Context, *, pokemon: str.lower):
        """Gets basic information about a Pokémon.
        (Bot Needs: Embed Links)

        EXAMPLE: pokedex Litwick
        """
        await ctx.trigger_typing()
        try:
            sp = await ctx.get(f"https://pokeapi.co/api/v2/pokemon-species/{pokemon}", cache=True)
            poke = await ctx.get(f"https://pokeapi.co/api/v2/pokemon/{pokemon}", cache=True)
        except HTTPError as exc:
            if exc.status == 404:
                await ctx.send("Couldn't find that Pokémon's information.")
                return
            raise

        embed = Embed(
            title=poke["name"].title(),
            url=f"https://www.pokemon.com/us/pokedex/{pokemon}",
            colour=0x3B4CCA
        )
        embed.description = next(
            (f["flavor_text"] for f in sp["flavor_text_entries"] if f["language"]["name"] == "en"), None
        )
        embed.set_thumbnail(url=poke["sprites"]["front_default"])
        embed.set_footer(text="Powered by pokeapi.co")

        embed.add_field(name="Pokédex Order", value=poke["order"], inline=False)
        embed.add_field(name="Base Experience", value=poke["base_experience"])
        embed.add_field(name="Base Happiness", value=sp["base_happiness"])
        embed.add_field(name="Capture Rate", value=sp["capture_rate"])
        embed.add_field(name="Weight", value=f"{poke['weight'] / 10} kg ({poke['weight'] / 4.536:.1f} lbs.)")

        feet, inches = divmod(round(poke['height'] * 3.93701), 12)
        # Zero pad the inches value just to look nicer.
        embed.add_field(name="Height", value=f"{poke['height'] / 10} m ({feet}′{inches:02d}″)")

        embed.add_field(name="Colour", value=sp["color"]["name"].title())

        previous_evolution = sp["evolves_from_species"]
        if previous_evolution is not None:
            embed.add_field(name="Previous Evolution", value=previous_evolution["name"].title())

        embed.add_field(name="Abilities", value="\n".join(a["ability"]["name"].title() for a in poke["abilities"]))
        embed.add_field(name="Types", value="\n".join(pt["type"]["name"].title() for pt in poke["types"]))

        stats = {stat["stat"]["name"].title(): stat["base_stat"] for stat in poke["stats"]}
        embed.add_field(name="Stats", value=f"```dns\n{formatting.tchart(stats.items())}\n```", inline=False)

        await ctx.send(embed=embed)


    @commands.command(aliases=["ss", "snapshot"])
    @checks.bot_has_permissions(embed_links=True)
    @commands.cooldown(rate=1, per=10, type=commands.BucketType.member)  # So we don't overload magmachain.
    async def screenshot(self, ctx: commands.Context, url: str):
        """Screenshots a website.
        NOTE: This does not take NSFW channel status into consideration.
        (Bot Needs: Embed Links)

        EXAMPLE: screenshot google.com
        """
        async with ctx.typing():
            response = await ctx.get(
                "https://magmachain.herokuapp.com/api/v1",
                headers__=dict(website=url.strip("<>")),
                cache=True
            )

        embed = Embed(
            title="Snapshot",
            description=f"[Link to Website]({response['website']})",
            color=0x2F3136,
            timestamp=datetime.utcnow()
        )
        embed.set_image(url=response["snapshot"])
        embed.set_footer(text="Powered by magmachain.herokuapp.com")
        await ctx.send(embed=embed)


    @commands.command()
    @checks.bot_has_permissions(embed_links=True)
    async def steaminfo(self, ctx: commands.Context, *, account: _resolve_steam_identifier):
        """Gets information about a Steam account.
        Argument can either be a Steam ID 64, vanity username, or link.
        (Bot Needs: Embed Links)

        EXAMPLE:
        (Ex. 1) steaminfo <https://www.steamcommunity.com/profiles/76561192109582121>
        (Ex. 2) steaminfo <https://www.steamcommunity.com/id/SomeUser>
        (Ex. 3) steaminfo 76561192109582121
        (Ex. 4) steaminfo SomeUser
        """
        await ctx.trigger_typing()

        steam_api_key = ctx.bot.config["Secrets"]["steam_api_key"]

        # The endpoint only takes Steam ID 64s, we'll have to try to resolve an ID if we get a vanity.
        # For reference, Steam IDs are usually 17 digit decimals with a hex starting with 0x1100001.
        # We check the latter case since it's more likely to be a steam ID than a vanity.
        if not (account.isdigit() and hex(int(account)).startswith("0x1100001")):
            try:
                resolve_steam_id = await ctx.get(
                    "https://api.steampowered.com/ISteamUser/ResolveVanityURL/v1/?&url_type=1",
                    key=steam_api_key,
                    vanityurl=account,
                    cache=True
                )
            except HTTPError as e:
                await ctx.send(f"Steam API failed with HTTP status code {e.status}.")
                return

            account = resolve_steam_id["response"].get("steamid")

            if account is None:
                await ctx.send("Could not find a Steam user associated with that Steam ID 64, vanity username, or URL.")
                return

        try:
            resolve_account_data = await ctx.get(
                "https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v2/?",
                key=steam_api_key,
                steamids=account,
                cache=True
            )
        except HTTPError as e:
            await ctx.send(f"Steam API failed with HTTP status code {e.status}.")
            return

        accounts = resolve_account_data["response"].get("players")

        if accounts is None:
            await ctx.send("Could not find a Steam user associated with that Steam ID 64, vanity username, or URL.")
            return

        account_data = accounts[0]

        av_hash = account_data["avatarhash"]

        avatar_url = f"https://steamcdn-a.akamaihd.net/steamcommunity/public/images/avatars/{av_hash[:2]}/{av_hash}_full.jpg"

        status = account_data["personastate"]

        embed = Embed(
            description=f"**[Steam Avatar link]({avatar_url})**\n",
            colour=0x53A4C4 if status != 0 else 0x555555
        )
        embed.set_author(name=account_data["personaname"], url=account_data["profileurl"])
        embed.set_thumbnail(url=avatar_url)
        embed.set_footer(text="Powered by Steam | Only showing basic public information.")

        # Used to calculate the SteamID & SteamID3.
        steam_id64 = int(account_data["steamid"])
        id_y_component = steam_id64 % 2
        id_w_component = steam_id64 - (id_y_component + 76561197960265728)

        description = (
            f"**Steam ID 64:** {steam_id64}",
            f"**Steam ID:** STEAM_0:{id_y_component}:{round(id_w_component / 2)}",
            f"**Steam ID 3:** [U:1:{id_y_component + id_w_component}]",
            f"**Status:** {STEAM_PERSONA_STATES.get(status, 'Unknown')}",
        )

        embed.description += "\n".join(f"<:arrow:713872522608902205> {entry}" for entry in description)

        await ctx.send(embed=embed)


    @commands.command()
    @checks.bot_has_permissions(embed_links=True)
    @commands.cooldown(rate=1, per=5, type=commands.BucketType.member)  # Curb possibility of being blocked.
    async def translate(self, ctx: commands.Context,
                        destination: _parse_destination, source: Optional[_parse_source] = "auto",
                        *, message: commands.clean_content(fix_channel_mentions=True)):
        """Translates a message using Google translate.
        The supported language codes are listed [here](https://cloud.google.com/translate/docs/languages).

        To specify a language to translate to, prefix the language code with `}`.
        Optionally, to specify a source language to translate from, prefix the language code with `]`.
        Please note that both the source language and destination language must be specified **BEFORE** the message.

        EXAMPLE:
        (Ex. 1) translate }es ]en Hello!
        (Ex. 2) translate }en Hola!
        """
        await ctx.trigger_typing()
        try:
            transl = await ctx.bot.loop.run_in_executor(None, self._translator.translate, message, destination, source)
        except ValueError as exc:
            await ctx.send(str(exc).capitalize())
            return
        except Exception as exc:
            await ctx.send(f"An error occurred while translating: {exc}")
            return

        embed = Embed(description=formatting.simple_shorten(transl.text, 2048), colour=0x4C8BF5)
        embed.set_author(name=str(ctx.author), icon_url=ctx.author.avatar_url)
        embed.set_thumbnail(
            url="https://media.discordapp.net/attachments/507971834570997765/741472907103961158/translate.png"
        )

        src = googletrans.LANGUAGES.get(transl.src, '(Auto-detected)').title()
        dest = googletrans.LANGUAGES.get(transl.dest, 'Unknown').title()

        embed.set_footer(
            text=f"{src} ({transl.src}) \N{RIGHTWARDS ARROW} {dest} ({transl.dest}) | Powered by Google Translate"
        )

        await ctx.send(embed=embed)


    @commands.command(aliases=["urban"])
    @checks.bot_has_permissions(embed_links=True, add_reactions=True, read_message_history=True)
    @commands.cooldown(rate=1, per=5, type=commands.BucketType.member)
    async def urbandict(self, ctx: commands.Context, *, term: str):
        """Searches for a term on Urban Dictionary.
        (Bot Needs: Embed Links)

        EXAMPLE: urbandict gl2u
        """
        await ctx.trigger_typing()
        response = await ctx.get("https://api.urbandictionary.com/v0/define?", term=term, cache=True)

        if not response["list"]:
            await ctx.send("That term isn't on Urban Dictionary.")
            return

        embeds = []
        for entry in response["list"]:
            embed = Embed(
                description=textwrap.shorten(BRACKET_REGEX.sub(_repl_brackets, entry["definition"]), 2000),
                timestamp=discord.utils.parse_time(entry['written_on'][0:-1]),
                colour=0x1D2439
            )
            embed.set_author(name=entry["word"], url=entry["permalink"])

            embed.add_field(
                name="**Example**",
                value=textwrap.shorten(BRACKET_REGEX.sub(_repl_brackets, entry["example"]), 1000),
                inline=False
            )
            embed.add_field(name=":thumbsup:", value=entry["thumbs_up"])
            embed.add_field(name=":thumbsdown:", value=entry["thumbs_down"])
            embed.set_footer(text=f"Written by: {entry['author']} | Powered by Urban Dictionary")

            embeds.append(embed)

        await ctx.paginate(reaction_menus.EmbedSource(embeds))


    @commands.command()
    @checks.bot_has_permissions(embed_links=True)
    async def weather(self, ctx: commands.Context, *, location: str):
        """Gets the current weather data for a location.
        Location arguments can be: US Zipcode, UK Postcode, Canada Postalcode,
        IP address, Latitude/Longitude (decimal degree) or city name.
        (Bot Needs: Embed Links)

        EXAMPLE:
        (Ex. 1) weather London
        (Ex. 2) weather Munich, Germany
        (Ex. 3) weather Wuhan, Hubei, China
        (Ex. 4) weather 72201
        (Ex. 5) weather BR1 1AH
        (Ex. 6) weather A2B 3C4
        (Ex. 7) weather 138.192.233.169
        (Ex. 8) weather 35.73 51.33
        """
        await ctx.trigger_typing()
        try:
            response = await ctx.get(
                "https://api.weatherapi.com/v1/current.json",
                key=ctx.bot.config["Secrets"]["weatherapi_api_key"],
                q=location,
                cache=True
            )
        except HTTPError as exc:
            if exc.status == 400:
                await ctx.send("That location either wasn't found or doesn't have any data available.")
                return
            raise

        wx = response["current"]
        loc = response["location"]

        embed = Embed(
            # Not the cleanest way to derive a full location name.
            # This approach only includes what is available and given.
            # So we don't end up with a name like "Singapore, , Singapore"
            title=", ".join(name for name in (loc['name'], loc['region'], loc['country']) if name),
            description=f"(Lat. {loc['lat']}°, Lon. {loc['lon']}°)",
            # Have the colour change based on whether or not it is daytime in that location.
            colour=0xE3C240 if wx["is_day"] == 1 else 0x1D50A8,
            timestamp=datetime.fromtimestamp(wx["last_updated_epoch"])
        )
        embed.set_author(name=wx["condition"]["text"], icon_url=f"https:{wx['condition']['icon']}")
        embed.set_footer(text="Powered by weatherapi.com")

        embed.add_field(
            name="Temperature",
            value=f"{wx['temp_c']}°C ({wx['temp_f']}°F)\nFeels Like: {wx['feelslike_c']}°C ({wx['feelslike_f']}°F)",
        )
        embed.add_field(name="Wind Speed", value=f"{wx['wind_kph']} kph ({wx['wind_mph']} mph) {wx['wind_dir']}")
        embed.add_field(name="Wind Gust", value=f"{wx['gust_kph']} kph ({wx['gust_mph']} mph)")
        embed.add_field(name="Precipitation", value=f"{wx['precip_mm']} mm ({wx['precip_in']} in.)")
        embed.add_field(name="Humidity", value=f"{wx['humidity']}%")
        embed.add_field(name="Cloud Coverage", value=f"{wx['cloud']}%")
        embed.add_field(name="Atmospheric Pressure", value=f"{wx['pressure_mb']} mb ({wx['pressure_in']} in. Hg)")
        embed.add_field(name="Visibility", value=f"{wx['vis_km']} km ({wx['vis_miles']} mi)")
        embed.add_field(name="UV Index", value=wx["uv"])

        await ctx.send(embed=embed)


    @commands.command(aliases=["wiki"])
    @checks.bot_has_permissions(embed_links=True)
    async def wikipedia(self, ctx: commands.Context, *, query: str):
        """Searches for something on Wikipedia.
        (Bot Needs: Embed Links)

        EXAMPLE: wikipedia anteater
        """
        # We have to narrow down titles and provide room for disambiguations.
        # This mostly to prevent people from passing "title1|title2|title3"
        # and (somewhat) prevent returning blank disambiguation pages.
        titles = await ctx.get("https://en.wikipedia.org/w/api.php", action="opensearch", search=query, cache=True)

        try:
            title = await ctx.disambiguate(titles[1], lambda x: discord.utils.escape_markdown(x))
        except ValueError as exc:
            await ctx.send(str(exc))
            return

        response = await ctx.get(
            "https://en.wikipedia.org/w/api.php?prop=extracts&explaintext&exintro",
            action="query",
            format="json",
            exsectionformat="plain",
            exchars=1024,  # Truncate the summary text around 1024 chars.
            titles=title,
            cache=True
        )

        pages = response["query"]["pages"]

        embed = Embed(description=pages[list(pages.keys())[0]]["extract"], colour=0xE3E3E3)
        embed.set_author(
            name=formatting.simple_shorten(title, 128),
            url=f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}"
        )
        embed.set_thumbnail(url="https://upload.wikimedia.org/wikipedia/commons/6/61/Wikipedia-logo-transparent.png")
        embed.set_footer(text="Powered by en.wikipedia.org")

        await ctx.send(embed=embed)


    @commands.group(invoke_without_command=True)
    @checks.bot_has_permissions(embed_links=True)
    async def xkcd(self, ctx: commands.Context, number: int = None):
        """Shows a comic from xkcd.
        If no comic number is given, then a random comic is shown instead.
        Subcommand "latest" shows the latest xkcd comic.
        (Bot Needs: Embed Links)

        EXAMPLE: xkcd 407
        """
        await ctx.trigger_typing()

        if number is None:
            # Because of how xkcd's api is designed, we need to get the total number of comics on the site.
            # We can get the total number by getting the latest comic.
            latest = await ctx.get("https://xkcd.com/info.0.json", cache=True)

            number = random.randint(1, latest["num"])

        try:
            comic = await ctx.get(f"https://xkcd.com/{number}/info.0.json", cache=True)
        except HTTPError as exc:
            if exc.status == 404:
                await ctx.send("Invalid comic number.")
                return
            raise

        await ctx.send(embed=self._format_xkcd_comic(comic))


    @xkcd.command(name="latest", aliases=["l"])
    async def xkcd_latest(self, ctx: commands.Context):
        """Shows the latest xkcd comic.
        (Bot Needs: Embed Links)
        """
        comic = await ctx.get("https://xkcd.com/info.0.json", cache=True)
        await ctx.send(embed=self._format_xkcd_comic(comic))


    @commands.command(aliases=["ytinfo"])
    @checks.bot_has_permissions(embed_links=True)
    async def youtubeinfo(self, ctx: commands.Context, channel: _youtube_channel):
        """Gets information about a YouTube channel.
        Argument can either be a channel ID, username, or link.
        Links are generally the easiest and most accurate.
        (Bot Needs: Embed Links)

        EXAMPLE:
        (Ex. 1) youtubeinfo <https://www.youtube.com/channel/UC57ZBb_D-YRsCxnsdHGSxSQ>
        (Ex. 2) youtubeinfo <https://www.youtube.com/user/SampleUser>
        (Ex. 3) youtubeinfo <https://www.youtube.com/c/SampleUser>
        (Ex. 4) youtubeinfo UC57ZBb_D-YRsCxnsdHGSxSQ
        (Ex. 5) youtubeinfo SampleUser
        """
        api_keys = self._google_api_keys["youtube"]

        await ctx.trigger_typing()

        while api_keys:
            key = next(iter(api_keys))

            try:
                response = await ctx.get(
                    "https://www.googleapis.com/youtube/v3/channels",
                    part="statistics,snippet",
                    key=key,
                    cache=True,
                    **channel
                )
            except HTTPError as exc:
                if exc.status == 403 and exc.data["error"]["errors"][0]["reason"] == "quotaExceeded":
                    api_keys.remove(key)
                    continue
                raise

            break
        else:
            await ctx.send("Well this is embarassing.\nI seem to have exceeded my usage quota for YouTube.")
            return

        results = response.get("items")
        if not results:
            await ctx.send("YouTube channel not found.")
            return

        data = results[0]
        stats = data["statistics"]
        snippet = data["snippet"]

        embed = Embed(
            description=snippet["localized"]["description"],
            colour=0xFF0000,
            timestamp=datetime.strptime(snippet["publishedAt"], "%Y-%m-%dT%H:%M:%SZ")
        )
        embed.set_author(name=snippet["title"], url=f"https://www.youtube.com/channel/{data['id']}")
        embed.set_thumbnail(url=snippet["thumbnails"]["high"]["url"])
        embed.set_footer(text="Powered by YouTube | Channel created")

        if not stats["hiddenSubscriberCount"]:
            embed.add_field(name="Subscribers", value=formatting.millify(int(stats['subscriberCount']), 2))

        embed.add_field(name="Views", value=f"{int(stats['viewCount']):,d}")
        embed.add_field(name="Videos", value=f"{int(stats['videoCount']):,d}")
        embed.add_field(name="Country", value=snippet.get("country", "N/A"))
        embed.add_field(name="Channel ID", value=data['id'])

        await ctx.send(embed=embed)


    @exchangerate.error
    @translate.error
    async def on_entity_error(self, ctx: commands.Context, error):
        error = getattr(error, "original", error)

        if isinstance(error, commands.BadArgument):
            await ctx.send(str(error))
            error.handled = True


def setup(bot):
    bot.add_cog(Web(bot))
