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

import io
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Dict, Literal, Optional, Tuple, Union, cast
from urllib.parse import quote

import numpy as np
from discord import Colour, Embed, File
from discord.ext import commands
from jishaku.functools import executor_function
from matplotlib import pyplot as plt, use as matplotlib_use
from matplotlib.dates import AutoDateLocator, DateFormatter, datestr2num
from matplotlib.figure import Figure
from typing_extensions import Annotated

from sleepy.http import HTTPRequestFailed
from sleepy.utils import human_number, measure_performance

if TYPE_CHECKING:
    from typing import TypedDict

    from matplotlib.axes import Axes

    from sleepy.bot import Sleepy
    from sleepy.context import Context as SleepyContext

    class CovidHistoryData(TypedDict):
        country: str
        cases: Dict[str, int]
        deaths: Dict[str, int]
        recovered: Dict[str, int]
        vaccines: Optional[Dict[str, int]]

    class PartialCovidStatsData(TypedDict):
        updated: int
        cases: int
        todayCases: int
        casesPerOneMillion: int
        deaths: int
        todayDeaths: int
        deathsPerOneMillion: int
        recovered: int
        active: int
        tests: int
        testsPerOneMillion: int
        population: int

    class CovidStatsData(PartialCovidStatsData):
        todayRecovered: int
        recoveredPerOneMillion: int
        activePerOneMillion: int
        critical: int
        criticalPerOneMillion: int


# We don't need any GUI elements since all plots are static.
matplotlib_use("agg")


# The COVID-19 historical plot's length & width in inches.
FIGSIZE_INCHES: Tuple[int, int] = (8, 6)


# disease.sh API takes comma-separated arguments to denote
# requesting data for multiple entities. The commands below
# are not designed to handle this functionality, therefore,
# this pseudo-converter scrubs end-user input to prevent
# the API from returning data for multiple sources.
def _sanitized_input(value: str, /) -> str:
    if "," in value:
        raise commands.BadArgument("Your input cannot contain commas.")

    return quote(value)


class CovidGeneralPlotFlags(commands.FlagConverter):
    log: bool = commands.flag(
        description="Whether to plot on a logarithmic scale. (Default: False)",
        default=False,
    )
    # TODO: Add lastdays compatibility.
    # lastdays: Union[Literal["all"], int] = commands.flag(
    #     default="all",
    #     converter=commands.Range[int, 30],
    #     description="The past days' worth of data to plot. (Default: all)",
    # )


class CovidCountryPlotFlags(CovidGeneralPlotFlags):
    country: Annotated[str, _sanitized_input]


class Covid(commands.Cog, name="COVID-19"):
    """Commands related to the COVID-19 pandemic."""

    ICON: str = "\N{MICROBE}"

    # Defined up here in case I ever need to change
    # the API base for whatever reason.
    BASE: str = "https://disease.sh/v3/covid-19"

    async def cog_command_error(self, ctx: SleepyContext, error: Exception) -> None:
        if isinstance(error, (commands.BadArgument, commands.MaxConcurrencyReached)):
            await ctx.send(error)  # type: ignore
            ctx._already_handled_error = True

    @executor_function
    @measure_performance
    def plot_historical_data(
        self,
        country: str,
        cases: Dict[str, int],
        deaths: Dict[str, int],
        recovered: Dict[str, int],
        vaccines: Optional[Dict[str, int]] = None,
        *,
        logarithmic: bool,
    ) -> io.BytesIO:
        # For reference, dates are in MM/DD/YYYY format, where MM and DD
        # do not always have a leading zero, e.g. dates can be 1/1/2023.
        timeline = datestr2num(np.fromiter(cases.keys(), dtype="U10"))

        c_counts = np.fromiter(cases.values(), dtype=int)
        d_counts = np.fromiter(deaths.values(), dtype=int)
        r_counts = np.fromiter(recovered.values(), dtype=int)
        # Equation for estimating the number of active cases:
        # active = cases - deaths - recoveries
        a_counts = c_counts - d_counts - r_counts

        dark_embed = str(Colour.dark_embed())

        # Have to use object-oriented interface since pyplot isn't threadsafe.
        fig = Figure(figsize=FIGSIZE_INCHES, facecolor=dark_embed)

        sp_kw = {"facecolor": dark_embed, "axisbelow": True}
        # Calculating margins is faster than saving with bbox_inches="tight".
        # For reference, the values below are in inches.
        # fmt: off
        gs_kw = {
            "left":   0.575 / FIGSIZE_INCHES[0],
            "right":  1 - 0.175 / FIGSIZE_INCHES[0],
            "top":    1 - 0.55 / FIGSIZE_INCHES[1],
            "bottom": 1.285 / FIGSIZE_INCHES[1],
        }
        # fmt: on

        if vaccines is None:
            axes: Axes = fig.subplots(subplot_kw=sp_kw, gridspec_kw=gs_kw)  # type: ignore
            axes.set_title("COVID-19 Cases & Outcomes", color="lightgrey", loc="left")
            axes.spines[["top", "bottom"]].set_color("white")

            # Hardcoded since there's no way to determine these dynamically.
            # These are ultimately arbitrary values based on looks alone.
            # fmt: off
            suptitle_y   = 1.117
            footnotes_y  = -0.225
            copyrights_y = -0.29
            legend_y     = -0.15
            # fmt: on
        else:
            gs_kw["hspace"] = 0
            axes, v_axes = fig.subplots(
                2, sharex=True, subplot_kw=sp_kw, gridspec_kw=gs_kw
            )

            axes.set_title(
                "COVID-19 Cases & Outcomes, and Vaccinations",
                color="lightgrey",
                loc="left",
            )
            axes.spines.top.set_color("white")

            self._apply_axes_style(v_axes, logarithmic=logarithmic)
            v_axes.spines.top.set_color("grey")
            v_axes.spines.bottom.set_color("white")

            v_axes.plot(
                datestr2num(np.fromiter(vaccines.keys(), dtype="U10")),
                np.fromiter(vaccines.values(), dtype=np.int64),
                "--",
                color="#FFDC82",
                label="Vaccinations",
                dashes=(6, 2),
            )

            # fmt: off
            suptitle_y   = 1.235
            footnotes_y  = -1.45
            copyrights_y = -1.58
            legend_y     = -1.3
            # fmt: on

        self._apply_axes_style(axes, logarithmic=logarithmic)
        axes.spines.top.set_linewidth(1.5)

        axes.plot(timeline, a_counts, ":", color="aqua", label="Active*")
        axes.plot(timeline, r_counts, "-.", color="#65B558", label="Recoveries**")
        axes.plot(timeline, d_counts, "--", color="#ED7734", label="Deaths")
        axes.plot(timeline, c_counts, "-", color="#1F94E2", label="Cases")

        axes.fill_between(timeline, c_counts, r_counts, color="#0D87D8", alpha=0.5)  # type: ignore
        axes.fill_between(timeline, r_counts, d_counts, color="#52A046", alpha=0.5)  # type: ignore
        axes.fill_between(timeline, d_counts, color="#FF5E00", alpha=0.5)

        fig.suptitle(
            country,
            x=0,
            y=suptitle_y,
            transform=axes.transAxes,
            ha="left",
            color="white",
            fontsize="xx-large",
            fontweight="bold",
        )

        footnotes = (
            "*Estimated from data on cases, deaths, and recoveries."
            "\n**As of 21st July, 2021, maintenance of recovery data has ceased."
            "\n***As of 10th March, 2023, maintenance of cases and deaths data has ceased."
        )
        fig.text(
            0,
            footnotes_y,
            footnotes,
            transform=axes.transAxes,
            fontsize=8,
            color="lightgrey",
        )

        copyrights = (
            "\N{COPYRIGHT SIGN} Sleepy 2020-present"
            "\nSource(s): John Hopkins University and Our World in Data."
        )
        fig.text(
            0.5,
            copyrights_y,
            copyrights,
            transform=axes.transAxes,
            fontsize=8,
            color="darkgrey",
            ha="center",
        )

        fig.legend(
            labelcolor="white",
            facecolor="0.125",
            edgecolor="none",
            ncol=5,
            loc="lower left",
            bbox_transform=axes.transAxes,
            bbox_to_anchor=(-0.015, legend_y, 1.03, 0),
            mode="expand",
        )

        buffer = io.BytesIO()

        fig.savefig(buffer, format="png")
        plt.close(fig)

        buffer.seek(0)

        return buffer

    @staticmethod
    def _apply_axes_style(axes: Axes, *, logarithmic: bool) -> None:
        axes.spines[["right", "left"]].set_visible(False)

        axes.yaxis.grid(color="dimgrey", alpha=0.25)

        axes.tick_params(colors="white", labelsize="medium")

        axes.xaxis.set_major_locator(AutoDateLocator(minticks=3, maxticks=8))
        axes.xaxis.set_major_formatter(DateFormatter("%b %Y"))

        if logarithmic:
            # We use symlog here so zeroes are plotted, since log(0) = -inf,
            # which matplotlib doesn't plot. This is more straight forward
            # than having to keep track of an arbitrary offset.
            axes.set_yscale("symlog", linthresh=1)  # type: ignore

        axes.yaxis.set_tick_params(which="both", left=False)
        axes.yaxis.set_major_formatter(lambda x, _: human_number(x))

    @staticmethod
    def _get_formatted_stats(
        data: PartialCovidStatsData, *, handle_as_state: bool = False
    ) -> Embed:
        population = data["population"]
        cases = data["cases"]
        deaths = data["deaths"]
        today_cases = data["todayCases"]
        today_deaths = data["todayDeaths"]

        embed = Embed(
            title="Current COVID-19 Statistics",
            description=f"{population:,d} Total Population",
            colour=Colour.dark_embed(),
            timestamp=datetime.fromtimestamp(data["updated"] / 1000, timezone.utc),
        )
        embed.set_footer(text="Powered by disease.sh \N{BULLET} Source: Worldometer")

        embed.add_field(
            name=f"Cases \N{BULLET} {cases:,d}",
            value="```diff"
            f"\n{today_cases:{'+' if today_cases > 0 else ''},d} today"
            f"\n~{data['casesPerOneMillion']:,.0f}/1M persons"
            "\n```",
        )
        embed.add_field(
            name=f"Deaths \N{BULLET} {deaths:,d}",
            value="```diff"
            f"\n{today_deaths:{'+' if today_deaths > 0 else ''},d} today"
            f"\n~{data['deathsPerOneMillion']:,.0f}/1M persons"
            "\n```",
        )

        if handle_as_state:
            # U.S. state data doesn't provide as much information as country
            # data, but we can infer some of the missing information from the
            # given information.

            active = data["active"]
            recovered = data["recovered"]

            # disease.sh doesn't seem to properly scrape recoveries sometimes.
            if recovered > 0:
                recoveries_field_name = f"Recoveries \N{BULLET} {recovered:,d}"
            else:
                recovered = (cases - deaths - active) if active > 0 else 0
                recoveries_field_name = f"Est. Recoveries \N{BULLET} {recovered:,d}"

            # Some entities can have a population of 0 for some reason.
            # At that point, we really can't infer anything else.
            pop_ratio = 1_000_000 / population if population > 0 else 0

            embed.add_field(
                name=recoveries_field_name,
                value=f"```diff\n~{pop_ratio * recovered:,.0f}/1M persons\n```",
            )
            embed.add_field(
                name=f"Active Cases \N{BULLET} {active:,d}",
                value=f"```diff\n~{pop_ratio * active:,.0f}/1M persons\n```",
            )
        else:
            data = cast("CovidStatsData", data)  # So Pyright is happy.

            today_recovered = data["todayRecovered"]
            today_active = today_cases - today_deaths - today_recovered

            embed.add_field(
                name=f"Recoveries \N{BULLET} {data['recovered']:,d}",
                value="```diff"
                f"\n{today_recovered:{'+' if today_recovered > 0 else ''},d} today"
                f"\n~{data['recoveredPerOneMillion']:,.0f}/1M persons"
                "\n```",
            )
            embed.add_field(
                name=f"Active Cases \N{BULLET} {data['active']:,d}",
                value="```diff\n"
                f"{today_active:{'+' if today_active > 0 else ''},d} est. today"
                f"\n~{data['activePerOneMillion']:,.0f}/1M persons"
                "\n```",
            )
            embed.add_field(
                name=f"Critical Cases \N{BULLET} {data['critical']:,d}",
                value=f"```\n~{data['criticalPerOneMillion']:,.0f}/1M persons\n```",
            )

        embed.add_field(
            name=f"Tests \N{BULLET} {data['tests']:,d}",
            value=f"```\n~{data['testsPerOneMillion']:,.0f}/1M persons\n```",
        )

        return embed

    async def _get_world_history_data(
        self, ctx: SleepyContext, *, lastdays: Union[Literal["all"], int] = "all"
    ) -> CovidHistoryData:
        hist_url = f"{self.BASE}/historical/all"
        vaxx_url = f"{self.BASE}/vaccine/coverage"

        data = await ctx.get(hist_url, cache__=True, lastdays=lastdays)
        data["vaccines"] = await ctx.get(vaxx_url, cache__=True, lastdays=lastdays)
        data["country"] = "World"

        return data

    async def _get_country_history_data(
        self,
        ctx: SleepyContext,
        country: str,
        *,
        lastdays: Union[Literal["all"], int] = "all",
    ) -> Optional[CovidHistoryData]:
        hist_url = f"{self.BASE}/historical/{country}"

        try:
            hist = await ctx.get(hist_url, cache__=True, lastdays=lastdays)
        except HTTPRequestFailed as exc:
            # disease.sh tends to 502 sometimes (rather quite often).
            if exc.status == 404:
                return None
            raise

        data = hist["timeline"]
        # This needs to be done because some country spellings that are
        # valid when fetching general history aren't valid when fetching
        # vaccine history (e.g. "United States" is invalid whereas "USA"
        # is valid in this case).
        data["country"] = valid_country = hist["country"]
        vaxx_url = f"{self.BASE}/vaccine/coverage/countries/{valid_country}"

        try:
            vaxx = await ctx.get(vaxx_url, cache__=True, lastdays=lastdays)
        except HTTPRequestFailed:
            # XXX: Don't know whether to fail here on a non 404 status.
            # For now, just ignore any errors coming from this.
            pass
        else:
            data["vaccines"] = vaxx["timeline"]

        return data

    @commands.hybrid_group()
    async def covid19(self, ctx: SleepyContext) -> None:
        """COVID-19 commands."""
        await ctx.send_help(ctx.command)

    @covid19.group(name="current")
    @commands.bot_has_permissions(embed_links=True)
    async def covid19_current(self, ctx: SleepyContext) -> None:
        """Current COVID-19 statistics commands."""
        await ctx.send_help(ctx.command)

    @covid19_current.command(name="world")
    async def covid19_current_world(self, ctx: SleepyContext) -> None:
        """Shows current COVID-19 statistics for the world.

        (Bot Needs: Embed Links)
        """
        data = await ctx.get(f"{self.BASE}/all", cache__=True)

        embed = self._get_formatted_stats(data)
        embed.description += f" \N{BULLET} {data['affectedCountries']} Affected Countries"  # type: ignore
        embed.set_author(name="The World", icon_url="http://tny.im/nDe")
        await ctx.send(embed=embed)

    @covid19_current.command(name="country")
    async def covid19_current_country(
        self, ctx: SleepyContext, *, country: Annotated[str, _sanitized_input]
    ) -> None:
        """Shows current COVID-19 statistics for a given country.

        (Bot Needs: Embed Links)

        **EXAMPLE:**
        ```
        covid19 current country USA
        ```
        """
        try:
            data = await ctx.get(f"{self.BASE}/countries/{country}", cache__=True)
        except HTTPRequestFailed as exc:
            if exc.status == 404:
                await ctx.send(exc.data["message"], ephemeral=True)
                return
            raise

        embed = self._get_formatted_stats(data)
        embed.set_author(name=data["country"], icon_url=data["countryInfo"]["flag"])
        await ctx.send(embed=embed)

    @covid19_current.command(name="states")
    async def covid19_current_states(
        self, ctx: SleepyContext, *, state: Annotated[str, _sanitized_input]
    ) -> None:
        """Shows current COVID-19 statistics for a given U.S. state, territory, or entity.

        (Bot Needs: Embed Links)

        **EXAMPLE:**
        ```
        covid19 current states New York
        ```
        """
        try:
            data = await ctx.get(f"{self.BASE}/states/{state}", cache__=True)
        except HTTPRequestFailed as exc:
            if exc.status == 404:
                await ctx.send(exc.data["message"], ephemeral=True)
                return
            raise

        embed = self._get_formatted_stats(data, handle_as_state=True)
        embed.set_author(name=data["state"])
        await ctx.send(embed=embed)

    @covid19.group(name="graph")
    @commands.bot_has_permissions(attach_files=True)
    @commands.cooldown(1, 8, commands.BucketType.member)
    @commands.max_concurrency(5, commands.BucketType.guild)
    async def covid19_graph(self, ctx: SleepyContext) -> None:
        """COVID-19 historical data graph commands."""
        await ctx.send_help(ctx.command)

    @covid19_graph.command(name="world", usage="[options...]")
    async def covid19_graph_world(
        self, ctx: SleepyContext, *, options: CovidGeneralPlotFlags
    ) -> None:
        """Shows a graph of the world's COVID-19 historical data.

        The following options are valid:

        `log: <True|False>`
        > Whether to plot the data on a logarithmic scale.
        > Defaults to `False` if omitted.

        (Bot Needs: Attach Files)
        """
        async with ctx.typing():
            hist = await self._get_world_history_data(ctx)
            buf, dt = await self.plot_historical_data(**hist, logarithmic=options.log)

        await ctx.send(
            f"Powered by disease.sh \N{BULLET} Took {dt:.2f} ms.",
            file=File(buf, "covid19_history_plot.png"),
        )

    @covid19_graph.command(name="country", usage="country: <country> [options...]")
    async def covid19_graph_country(
        self, ctx: SleepyContext, *, options: CovidCountryPlotFlags
    ) -> None:
        """Shows a graph of a given country's COVID-19 historical data.
        By default, the data is plotted linearly.

        The following options are valid:

        `country: <country>` **Required**
        > The country to plot historical data for.
        `log: <True|False>`
        > Whether to plot the data on a logarithmic scale.
        > Defaults to `False` if omitted.

        (Bot Needs: Attach Files)

        **EXAMPLES:**
        ```bnf
        <1> covid19 graph country country: USA
        <2> covid19 graph country country: USA logarithmic: true
        ```
        """
        async with ctx.typing():
            hist = await self._get_country_history_data(ctx, options.country)
            if hist is None:
                await ctx.send("Historical data is unavailable for that country.")
                return

            buf, dt = await self.plot_historical_data(**hist, logarithmic=options.log)

        await ctx.send(
            f"Powered by disease.sh \N{BULLET} Took {dt:.2f} ms.",
            file=File(buf, "covid19_history_plot.png"),
        )

    # TODO: Add U.S. state historical data plot command.


async def setup(bot: Sleepy) -> None:
    await bot.add_cog(Covid())
