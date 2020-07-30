"""
© Copyright 2018-2020 HitchedSyringe, All Rights Reserved.

Redistributing, using or owning a copy of this software without explicit permissions
is against these licensing terms, your license(s) to this software can be revoked at
any time without explicit notice beforehand and at the time of revocation.
Your license is non-transferrable, the terms of this license only permit you to do the
following; Create pull requests and make modifications to this repository.

"""


import io
from datetime import datetime
from functools import partial
from typing import Optional
from urllib.parse import quote as urlquote

from discord import Embed, File
from discord.ext import commands
from matplotlib import figure, pyplot as plt
from matplotlib.ticker import FuncFormatter, MultipleLocator
from cachetools import LRUCache

from SleepyBot.utils import checks, formatting
from SleepyBot.utils.requester import HTTPError


def _toggle_logarithmic(value: str) -> bool:
    """Pseudo-converter that allows for a psuedo flag argument.
    Returns ``True`` if and only if ``--logarithmic``, ``--log`` or ``-l`` is passed.
    Raises :exc:`commands.BadArgument` if anything else is passed.
    """
    if value not in ("--logarithmic", "--log", "-l"):
        # We can't return a bool/value here since the conversion would be successful,
        # so we have to raise an exception for it to fail.
        raise commands.BadArgument("Invalid flag. Must be `--logarithmic`, `--log` or `-l`")
    return True


def _clean_input(value: str) -> str:
    """Pseudo-converter that cleans user input ensures the API only returns one entity."""
    # This approach prevents some valid input such as "Iran, Islamic republic of." Probably doesn't matter.
    # Also, this is the best I can come up with to word this error and have it make sense to the end user.
    if "," in value:
        raise commands.BadArgument(
            "Due to the way my data source processes arguments, commas are not allowed in your input."
        )
    return value


class Covid(commands.Cog,
            command_attrs=dict(cooldown=commands.Cooldown(rate=1, per=6, type=commands.BucketType.member))):
    """Commands related to the COVID-19 coronavirus pandemic."""

    def __init__(self):
        # NOTE: The generated graph cache is discarded upon cog reload/unload.
        self.plot_cache = LRUCache(16)


    @staticmethod
    def get_plotting_values(data: dict) -> tuple:
        """Converts the dictionary data into plottable values.
        Essentially makes the data compatible for use with :func:`plot`.

        Parameters
        ----------
        data: :class:`dict`
            The values to retrieve for plotting.

        Returns
        -------
        Tuple[Tuple[Union[:class:`int`, :class:`str`]]]
            The plotting values.
        """
        # Probably doesn't matter where we get the datestamps from.
        timeline = tuple(data["cases"].keys())
        cases = tuple(data["cases"].values())
        deaths = tuple(data["deaths"].values())
        recovered = tuple(data["recovered"].values())
        # Calculate the active cases per day.
        # For reference, the equation is: active = cases - (deaths + recoveries)
        active = tuple(c - (d + r) for c, d, r in zip(cases, deaths, recovered))

        # Shortens any long chains of 0 confirmed cases. Allows for clearer viewing of the spike.
        index = 0
        while cases[index] == 0:
            index += 1

        def logarify_values(values: tuple) -> tuple:
            return tuple(value if value != 0 else 1 for value in values)

        return (
            timeline[index:],
            cases[index:],
            logarify_values(deaths[index:]),
            logarify_values(recovered[index:]),
            logarify_values(active[index:])
        )


    @staticmethod
    def plot(timeline: tuple, cases: tuple, deaths: tuple,
             recovered: tuple, active: tuple, *, logarithmic: bool = False) -> io.BytesIO:
        """Generates a graph using the given data.

        Parameters
        ----------
        timeline: Tuple[:class:`str`]
            A tuple of string dates.
        cases: Tuple[:class:`int`]
            A tuple of numbers of cases ordered chronologically.
        deaths: Tuple[:class:`int`]
            A tuple of numbers of deaths ordered chronologically.
        recovered: Tuple[:class:`int`]
            A tuple of numbers of recoveries ordered chronologically.
        active: Tuple[:class:`int`]
            A tuple of numbers of active cases ordered chronologically.
        logarithmic: :class:`bool`
            Whether or not to logarithmically graph the data.
            If ``False``, the data is linearly graphed.
            Defaults to ``False``. (Linear)

        Returns
        -------
        :class:`io.BytesIO`
            The filestream containing the figure data in PNG format.
        """
        # Running direct pyplot operations through an executor might raise RuntimeError.
        # For this, we're using a figure object directly since pyplot uses tkinter which doesn't like asyncio.
        fig = figure.Figure()
        axs = fig.subplots()

        for spine in axs.spines.values():
            spine.set_visible(False)

        if logarithmic:
            axs.set_yscale("log")

        axs.xaxis.set_major_locator(MultipleLocator(7))

        axs.plot(timeline, active, ".-", color="#57ffe3", alpha=0.5)
        axs.plot(timeline, recovered, ".-", color="lightgreen")
        axs.plot(timeline, deaths, ".-", color="#ff5e00")
        axs.plot(timeline, cases, ".-", color="#3aa9f2")

        axs.fill_between(timeline, cases, recovered, color="#3aa9f2", alpha=0.5)
        axs.fill_between(timeline, recovered, deaths, color="lightgreen", alpha=0.5)
        if not logarithmic:
            axs.fill_between(timeline, deaths, color="#ff5e00", alpha=0.5)

        axs.set_xticks(range(0, len(timeline), 15))
        fig.autofmt_xdate(rotation=30, ha="center")

        axs.grid(True)

        axs.set_xlabel("Timeline (MM/DD/YY)", color="white")
        axs.set_ylabel("Amount", color="white")
        axs.set_title(f"COVID-19 Historical Graph ({'Logarithmic' if logarithmic else 'Linear'})", color="white")

        axs.tick_params(axis="x", colors="white")
        axs.tick_params(axis="y", colors="white")

        legend = axs.legend(("Active", "Recovered", "Deaths", "Cases"), facecolor='0.1', loc="upper left")
        for text in legend.get_texts():
            text.set_color("white")

        if not logarithmic:
            axs.set_ylim(ymin=1)

        axs.yaxis.set_major_formatter(FuncFormatter(lambda x, pos: formatting.millify(int(x), precision=1)))

        final_buffer = io.BytesIO()
        fig.savefig(final_buffer, format="png", transparent=True)
        plt.close(fig)
        final_buffer.seek(0)

        return final_buffer


    @commands.group(invoke_without_command=True, aliases=["covid19", "covid", "corona"], usage="")
    @checks.bot_has_permissions(embed_links=True, attach_files=True)
    async def coronavirus(self, ctx: commands.Context, logarithmic: Optional[_toggle_logarithmic] = False):
        """Shows global statistics on the COVID-19 coronavirus pandemic.
        Passing `--logarithmic`, `--log` or `-l` shows the logarithmic graph for historic data.
        If no logarithmic flag is passed, the graphing mode for historic data defaults to linear.
        (Bot Needs: Embed Links and Attach Files)
        """
        async with ctx.typing():
            current = await ctx.get("https://disease.sh/v3/covid-19/all", cache=True)
            countries = await ctx.get("https://disease.sh/v3/covid-19/countries?sort=cases", cache=True)

            # Get our cache key. We need these to be unique in order to differentiate between the
            # logarithmic graph and the linear graph when checking.
            cache_key = f"World:{'LOG' if logarithmic else 'LIN'}"
            graph_buffer = self.plot_cache.get(cache_key)

            if graph_buffer is None:
                # Don't need to cache the historical data since we're only fetching it once
                # to build the graph which is then cached later.
                historic = await ctx.get("https://disease.sh/v3/covid-19/historical/all", lastdays="all")

                plotting_values = self.get_plotting_values(historic)
                partial_plotter = partial(self.plot, logarithmic=logarithmic, *plotting_values)

                # Run the plotting operation in an executor, stopping it from blocking the thread loop.
                # We're basically good to go here since all image stuff is handled within the function.
                # Afterwards, we cache the result of the graph.
                self.plot_cache[cache_key] = graph_buffer = await ctx.bot.loop.run_in_executor(None, partial_plotter)
            else:
                # We will have to seek to the beginning of the stream upon retrieving.
                graph_buffer.seek(0)

        # Build chart to show top infected countries.
        chart = {}
        for c in countries[:5]:
            c_new_cases = c["todayCases"]
            chart[c["country"]] = f"{c['cases']:,d} {f'({c_new_cases:+,d})' if c_new_cases != 0 else ''}"

        embed = Embed(
            description=f"**Top 5 countries with the most cases:**\n```dns\n{formatting.tchart(chart.items())}\n```",
            colour=0x2F3136,
            timestamp=datetime.utcfromtimestamp(current["updated"] / 1000) # Updated timestamp is in ms.
        )
        embed.set_author(name="Global COVID-19 Statistics")
        embed.set_footer(text="Powered by disease.sh")

        # We'll define new cases, deaths, etc. for string formatting reasons. We don't want to show (+0).
        new_cases = current["todayCases"]
        new_deaths = current["todayDeaths"]
        new_recovered = current["todayRecovered"]

        embed.add_field(
            name="Cases",
            value=f"{current['cases']:,d} {f'({new_cases:+,d})' if new_cases != 0 else ''}"
        )
        embed.add_field(name="Tests", value=f"{current['tests']:,d}")
        embed.add_field(
            name="Deaths",
            value=f"{current['deaths']:,d} {f'({new_deaths:+,d})' if new_deaths != 0 else ''}"
        )
        embed.add_field(name="Cases Per Million", value=f"{current['casesPerOneMillion']:,.2f}")
        embed.add_field(name="Tests Per Million", value=f"{current['testsPerOneMillion']:,.2f}")
        embed.add_field(name="Deaths Per Million", value=f"{current['deathsPerOneMillion']:,.2f}")
        embed.add_field(
            name="Recovered",
            value=f"{current['recovered']:,d} {f'({new_recovered:+,d})' if new_recovered != 0 else ''}"
        )
        embed.add_field(name="Active Cases", value=f"{current['active']:,d}")
        embed.add_field(name="Critical Cases", value=f"{current['critical']:,d}")
        embed.add_field(name="Recovered Per Million", value=f"{current['recoveredPerOneMillion']:,.2f}")
        embed.add_field(name="Active Per Million", value=f"{current['activePerOneMillion']:,.2f}")
        embed.add_field(name="Critical Per Million", value=f"{current['criticalPerOneMillion']:,.2f}")
        embed.add_field(name="Population", value=f"{current['population']:,d}")
        embed.add_field(name="Affected Countries", value=current['affectedCountries'])
        embed.set_thumbnail(
            url="https://upload.wikimedia.org/wikipedia/commons/2/22/Earth_Western_Hemisphere_transparent_background.png"
        )
        embed.set_image(url="attachment://covid19_historical_graph.png")
        await ctx.send(file=File(fp=graph_buffer, filename="covid19_historical_graph.png"), embed=embed)


    @coronavirus.command(name="country", usage="<country>")
    async def coronavirus_country(self, ctx: commands.Context,
                                  logarithmic: Optional[_toggle_logarithmic] = False, *, country: _clean_input):
        """Shows a country's statistics on the COVID-19 coronavirus pandemic.
        Passing `--logarithmic`, `--log` or `-l` before the country shows the logarithmic graph for historic data.
        If no logarithmic flag is passed, the graphing mode for historic data defaults to linear.
        (Bot Needs: Embed Links and Attach Files)

        EXAMPLE:
        (Ex. 1) coronavirus country USA
        (Ex. 2) coronavirus country --logarithmic USA
        """
        async with ctx.typing():
            try:
                current = await ctx.get(f"https://disease.sh/v3/covid-19/countries/{urlquote(country)}", cache=True)
            except HTTPError as exc:
                if exc.status == 404:
                    await ctx.send(exc.data["message"])
                    return
                raise

            country = current["country"]

            cache_key = f"{country}:{'LOG' if logarithmic else 'LIN'}"
            graph_buffer = self.plot_cache.get(cache_key)

            if graph_buffer is None:
                try:
                    historic = await ctx.get(f"https://disease.sh/v3/covid-19/historical/{country}", lastdays="all")
                except HTTPError:
                    # Either worldometers has data on a country that jhucsse historical doesn't
                    # or the "country" is actually considered a province on jhucsse's end.
                    # Either way, there's nothing we can really do without overcomplicating things.
                    graph_buffer = None
                else:
                    plotting_values = self.get_plotting_values(historic["timeline"])
                    partial_plotter = partial(self.plot, logarithmic=logarithmic, *plotting_values)

                    self.plot_cache[cache_key] = graph_buffer = await ctx.bot.loop.run_in_executor(None, partial_plotter)
            else:
                graph_buffer.seek(0)

        country_info = current["countryInfo"]

        embed = Embed(colour=0x2F3136, timestamp=datetime.utcfromtimestamp(current["updated"] / 1000))
        embed.set_author(name=f"{country} ({country_info['iso2'] or 'N/A'}) COVID-19 Statistics")
        embed.set_footer(text="Powered by disease.sh")

        new_cases = current["todayCases"]
        new_deaths = current["todayDeaths"]
        new_recovered = current["todayRecovered"]

        embed.add_field(
            name="Cases",
            value=f"{current['cases']:,d} {f'({new_cases:+,d})' if new_cases != 0 else ''}"
        )
        embed.add_field(name="Tests", value=f"{current['tests']:,d}")
        embed.add_field(
            name="Deaths",
            value=f"{current['deaths']:,d} {f'({new_deaths:+,d})' if new_deaths != 0 else ''}"
        )
        embed.add_field(name="Cases Per Million", value=f"{current['casesPerOneMillion']:,.2f}")
        embed.add_field(name="Tests Per Million", value=f"{current['testsPerOneMillion']:,.2f}")
        embed.add_field(name="Deaths Per Million", value=f"{current['deathsPerOneMillion']:,.2f}")
        embed.add_field(
            name="Recovered",
            value=f"{current['recovered']:,d} {f'({new_recovered:+,d})' if new_recovered != 0 else ''}"
        )
        embed.add_field(name="Active Cases", value=f"{current['active']:,d}")
        embed.add_field(name="Critical Cases", value=f"{current['critical']:,d}")
        embed.add_field(name="Recovered Per Million", value=f"{current['recoveredPerOneMillion']:,.2f}")
        embed.add_field(name="Active Per Million", value=f"{current['activePerOneMillion']:,.2f}")
        embed.add_field(name="Critical Per Million", value=f"{current['criticalPerOneMillion']:,.2f}")
        embed.add_field(name="Population", value=f"{current['population']:,d}")
        embed.add_field(name="Continent", value=current['continent'] or "N/A")
        embed.set_thumbnail(url=country_info["flag"])

        if graph_buffer is not None:
            embed.set_image(url=f"attachment://covid19_historical_graph.png")
            await ctx.send(file=File(fp=graph_buffer, filename="covid19_historical_graph.png"), embed=embed)
        else:
            embed.description = "No graph provided since historical data is unavailable for this location."
            await ctx.send(embed=embed)


    @coronavirus.command(name="unitedstates", aliases=["us", "usa"])
    @checks.bot_has_permissions(embed_links=True)
    @commands.cooldown(rate=2, per=5, type=commands.BucketType.member)
    async def coronavirus_unitedstates(self, ctx: commands.Context, *, entity: _clean_input):
        """Shows a U.S. entity's statistics on the COVID-19 coronavirus pandemic.
        This includes statistics from states, territories, repatriated citizens, veteran affairs,
        federal prisons, the U.S. military, and the Navajo Nation.
        (Bot Needs: Embed Links)

        EXAMPLE: coronavirus unitedstates New York
        """
        await ctx.trigger_typing()
        try:
            current = await ctx.get(f"https://disease.sh/v3/covid-19/states/{urlquote(entity)}", cache=True)
        except HTTPError as exc:
            if exc.status == 404:
                await ctx.send(exc.data["message"])
                return
            raise

        name = current['state']

        embed = Embed(colour=0x2F3136, timestamp=datetime.utcfromtimestamp(current["updated"] / 1000))
        embed.set_author(name=f"{name} COVID-19 Coronavirus Statistics")
        # This won't show for all states worldometers supports.
        # It should just show up as blank if we put a url that leads nowhere.
        # Nothing I can really do anyway to check validity of the slug...
        embed.set_thumbnail(url=f"https://cdn.civil.services/us-states/flags/{name.lower().replace(' ','-')}-large.png")
        embed.set_footer(text="Powered by disease.sh")

        cases = current["cases"]
        deaths = current["deaths"]
        active = current["active"]

        new_cases = current["todayCases"]
        new_deaths = current["todayDeaths"]

        embed.add_field(name="Cases", value=f"{cases:,d} {f'({new_cases:+,d})' if new_cases != 0 else ''}")
        embed.add_field(name="Tests", value=f"{current['tests']:,d}")
        embed.add_field(name="Deaths", value=f"{deaths:,d} {f'({new_deaths:+,d})' if new_deaths != 0 else ''}")
        embed.add_field(name="Cases Per Million", value=f"{current['casesPerOneMillion']:,.2f}")
        embed.add_field(name="Tests Per Million", value=f"{current['testsPerOneMillion']:,.2f}")
        embed.add_field(name="Deaths Per Million", value=f"{current['deathsPerOneMillion']:,.2f}")
        embed.add_field(name="Active Cases", value=f"{active:,d}")
        # Have to calculate recoveries here since states doesn't actually give me the value.
        # For reference, the equation is: recoveries = cases - (active + deaths)
        embed.add_field(name="Recovered", value=f"{cases - (active + deaths):,d}")
        await ctx.send(embed=embed)


    @coronavirus_country.error
    @coronavirus_unitedstates.error
    async def on_covid_entity_error(self, ctx: commands.Context, error):
        error = getattr(error, "original", error)

        if isinstance(error, commands.BadArgument):
            await ctx.send(str(error))
            error.handled = True


def setup(bot):
    bot.add_cog(Covid())
