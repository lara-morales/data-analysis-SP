"""Shared landscape-page layout for the visit PDFs."""

from __future__ import annotations

import textwrap
from collections.abc import Callable, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.axes import Axes
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.figure import Figure
from matplotlib.patches import Patch


PAGE_SIZE = (11.69, 8.27)
# Presentation primaries: blue, red, and gold, kept soft enough for a long readout.
RED = "#3B6F9A"
BLACK = "#1A1A1A"
WHITE = "#FFFFFF"
INK = BLACK
MUTED = "#333333"
RULE = "#333333"
SERIES = ("#3B6F9A", "#B5524C", "#C4A15A", "#8A9096")
SOURCE_LINE = "Source: FY2024, FY2025, and FH12026 Manila CIQ CS Visit Reports"
REGION_COLORS = {
    "APAC": "#3B6F9A",
    "EMEA": "#B5524C",
    "Americas": "#C4A15A",
    "Unspecified": "#E6E6E6",
}
plt.rcParams.update(
    {
        "font.family": "Arial",
        "font.size": 10,
        "text.color": BLACK,
        "axes.labelcolor": BLACK,
        "xtick.color": BLACK,
        "ytick.color": BLACK,
        "axes.edgecolor": BLACK,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
    }
)


def series_colors(keys: Sequence[object]) -> dict[object, str]:
    return {key: SERIES[index % len(SERIES)] for index, key in enumerate(keys)}


def new_figure() -> Figure:
    figure = plt.figure(figsize=PAGE_SIZE)
    figure.patch.set_facecolor(WHITE)
    figure.patches.append(
        plt.Rectangle(
            (0, 0.985),
            1,
            0.015,
            transform=figure.transFigure,
            facecolor=RED,
            edgecolor="none",
            zorder=5,
            clip_on=False,
        )
    )
    figure.text(0.055, 0.968, "MNL VISITS", fontsize=8, color=RED, fontweight="bold", va="bottom")
    return figure


def wrap(text: str, width: int, max_lines: int | None = None) -> str:
    lines = textwrap.wrap(" ".join(text.split()), width=width) or [""]
    if max_lines is not None and len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1].rstrip(" ,;:.") + "…"
    return "\n".join(lines)


def draw_title(figure: Figure, title: str, body: str) -> None:
    figure.text(0.06, 0.945, title, fontsize=16, fontweight="bold", color=INK, va="top")
    figure.text(0.06, 0.89, wrap(body, 125), fontsize=9, color=MUTED, va="top", linespacing=1.35)


def draw_footer(figure: Figure, note: str | None = None) -> None:
    figure.patches.append(
        plt.Rectangle(
            (0.055, 0.038),
            0.89,
            0.004,
            transform=figure.transFigure,
            facecolor=BLACK,
            edgecolor="none",
            zorder=4,
        )
    )
    figure.text(0.055, 0.016, note or SOURCE_LINE, fontsize=8, color=BLACK, va="bottom")


def _implication(figure: Figure, note: str) -> float:
    """Bottom callout. Returns the top of the panel so the chart can sit above it."""
    if not note:
        return 0.055
    panel_y = 0.050
    panel_h = 0.100
    figure.patches.append(
        plt.Rectangle(
            (0.055, panel_y),
            0.89,
            panel_h,
            transform=figure.transFigure,
            facecolor="#F6F6F6",
            edgecolor="none",
            zorder=0,
        )
    )
    figure.patches.append(
        plt.Rectangle(
            (0.055, panel_y),
            0.007,
            panel_h,
            transform=figure.transFigure,
            facecolor=RED,
            edgecolor="none",
            zorder=1,
        )
    )
    figure.text(0.074, panel_y + panel_h - 0.012, "IMPLICATION", fontsize=8, color=RED, fontweight="bold", va="top")
    figure.text(
        0.074,
        panel_y + 0.012,
        wrap(note, 128, max_lines=3),
        fontsize=9.5,
        color=BLACK,
        va="bottom",
        linespacing=1.2,
    )
    return panel_y + panel_h


def save_page(pdf: PdfPages, figure: Figure) -> None:
    pdf.savefig(figure)
    plt.close(figure)


def add_chart_page(
    pdf: PdfPages,
    title: str,
    body: str,
    draw: Callable[[Figure], None],
    *,
    note: str = "",
    footer: str | None = None,
) -> None:
    """Title, reading, chart, and an implication panel in separate bands."""
    figure = new_figure()
    figure.text(0.055, 0.945, title, fontsize=16, fontweight="bold", color=BLACK, va="top")
    body_text = wrap(body, 118, max_lines=3)
    body_lines = body_text.count("\n") + 1
    figure.text(0.055, 0.895, body_text, fontsize=10, color=BLACK, va="top", linespacing=1.25)
    panel_top = _implication(figure, note)
    chart_bottom = panel_top + 0.07
    chart_top = 0.895 - body_lines * 0.032 - 0.04
    figure.chart_rect = (0.055, chart_bottom, 0.89, max(0.28, chart_top - chart_bottom))  # type: ignore[attr-defined]
    draw(figure)
    draw_footer(figure, footer)
    save_page(pdf, figure)


def add_action_page(pdf: PdfPages, items: list[tuple[str, str]], intro: str) -> None:
    """Last page. Each item stays above the footer."""
    figure = new_figure()
    figure.text(0.055, 0.945, "Actions for the Manila team", fontsize=16, fontweight="bold", color=BLACK, va="top")
    intro_text = wrap(intro, 118, max_lines=2)
    figure.text(0.055, 0.895, intro_text, fontsize=10, color=BLACK, va="top", linespacing=1.25)
    cursor = 0.895 - (intro_text.count("\n") + 1) * 0.03 - 0.028
    for index, (heading, paragraph) in enumerate(items, start=1):
        if cursor < 0.10:
            break
        figure.text(0.055, cursor, f"{index}", fontsize=12, fontweight="bold", color=RED, va="top")
        figure.text(0.085, cursor, heading, fontsize=11, fontweight="bold", color=BLACK, va="top")
        wrapped = wrap(paragraph, 125, max_lines=3)
        figure.text(0.085, cursor - 0.03, wrapped, fontsize=9.5, color=BLACK, va="top", linespacing=1.2)
        cursor -= 0.05 + 0.022 * (wrapped.count("\n") + 1)
    draw_footer(figure)
    save_page(pdf, figure)


def add_concentration_page(
    pdf: PdfPages,
    title: str,
    intro: str,
    left_heading: str,
    left_items: list[str],
    left_note: str,
    right_heading: str,
    right_items: list[str],
    right_note: str,
    callout: str,
) -> None:
    """Two ranked lists and a callout, with no chart. Long names stay readable as text."""
    figure = new_figure()
    figure.text(0.055, 0.945, title, fontsize=16, fontweight="bold", color=BLACK, va="top")
    intro_text = wrap(intro, 118, max_lines=2)
    figure.text(0.055, 0.895, intro_text, fontsize=10, color=BLACK, va="top", linespacing=1.25)
    columns = (
        (0.055, left_heading, left_items[:4], left_note),
        (0.52, right_heading, right_items[:4], right_note),
    )
    for x, heading, items, note in columns:
        figure.text(x, 0.80, heading, fontsize=12, fontweight="bold", color=RED, va="top")
        cursor = 0.75
        for item in items:
            bullet = wrap(item, 52, max_lines=2)
            figure.text(x, cursor, "•  " + bullet, fontsize=10, color=BLACK, va="top", linespacing=1.2)
            cursor -= 0.028 + 0.026 * (bullet.count("\n") + 1)
        figure.text(x, 0.36, wrap(note, 55, max_lines=2), fontsize=9, color=BLACK, va="top", linespacing=1.25)
    figure.patches.append(
        plt.Rectangle(
            (0.055, 0.075),
            0.89,
            0.17,
            transform=figure.transFigure,
            facecolor="#F6F6F6",
            edgecolor="none",
            zorder=0,
        )
    )
    figure.patches.append(
        plt.Rectangle(
            (0.055, 0.075),
            0.007,
            0.17,
            transform=figure.transFigure,
            facecolor=RED,
            edgecolor="none",
            zorder=1,
        )
    )
    figure.text(0.074, 0.225, "IMPLICATION", fontsize=8, color=RED, fontweight="bold", va="top")
    figure.text(0.074, 0.155, wrap(callout, 118, max_lines=3), fontsize=10, color=BLACK, va="center", linespacing=1.25)
    draw_footer(figure)
    save_page(pdf, figure)


def add_year_columns_page(
    pdf: PdfPages,
    title: str,
    intro: str,
    columns: list[tuple[str, list[str]]],
    callout: str,
) -> None:
    """One column per year. Each column is that year's top names."""
    figure = new_figure()
    figure.text(0.055, 0.945, title, fontsize=16, fontweight="bold", color=BLACK, va="top")
    intro_text = wrap(intro, 118, max_lines=2)
    figure.text(0.055, 0.895, intro_text, fontsize=10, color=BLACK, va="top", linespacing=1.25)
    count = max(len(columns), 1)
    width = 0.88 / count
    for index, (heading, items) in enumerate(columns):
        x = 0.055 + index * width
        figure.text(x, 0.78, heading, fontsize=13, fontweight="bold", color=SERIES[index % len(SERIES)], va="top")
        cursor = 0.70
        for item in items:
            bullet = wrap(item, 40, max_lines=3)
            figure.text(x, cursor, bullet, fontsize=11, color=BLACK, va="top", linespacing=1.25)
            cursor -= 0.04 + 0.03 * (bullet.count("\n") + 1)
    figure.patches.append(
        plt.Rectangle(
            (0.055, 0.075),
            0.89,
            0.16,
            transform=figure.transFigure,
            facecolor="#F7F7F7",
            edgecolor="none",
            zorder=0,
        )
    )
    figure.patches.append(
        plt.Rectangle(
            (0.055, 0.075),
            0.007,
            0.16,
            transform=figure.transFigure,
            facecolor=RED,
            edgecolor="none",
            zorder=1,
        )
    )
    figure.text(0.074, 0.215, "IMPLICATION", fontsize=8, color=RED, fontweight="bold", va="top")
    figure.text(0.074, 0.15, wrap(callout, 118, max_lines=3), fontsize=10, color=BLACK, va="center", linespacing=1.25)
    draw_footer(figure)
    save_page(pdf, figure)


def add_text_page(pdf: PdfPages, title: str, paragraphs: list[tuple[str, str]]) -> None:
    figure = new_figure()
    figure.text(0.055, 0.945, title, fontsize=16, fontweight="bold", color=BLACK, va="top")
    cursor = 0.87
    for heading, paragraph in paragraphs:
        if cursor < 0.10:
            break
        figure.text(0.055, cursor, heading, fontsize=12, fontweight="bold", color=RED, va="top")
        wrapped = wrap(paragraph, 115, max_lines=4)
        figure.text(0.055, cursor - 0.032, wrapped, fontsize=10.5, color=BLACK, va="top", linespacing=1.3)
        cursor -= 0.055 + 0.028 * (wrapped.count("\n") + 1)
    draw_footer(figure)
    save_page(pdf, figure)


def chart_band(figure: Figure, *, left: float = 0.08) -> tuple[float, float, float, float]:
    """Plot area reserved by the page, below the heading and above the note."""
    band = getattr(figure, "chart_rect", None)
    if band is None:
        return (left, 0.22, 0.92 - left, 0.50)
    _x, bottom, _width, height = band
    return (left, bottom, 0.94 - left, height)


def style_axis(axis: Axes) -> None:
    axis.grid(axis="y", color="#E6E6E6", linewidth=0.8)
    axis.set_axisbelow(True)
    axis.spines["top"].set_visible(False)
    axis.spines["right"].set_visible(False)
    axis.spines["left"].set_color(BLACK)
    axis.spines["bottom"].set_color(BLACK)
    axis.tick_params(colors=BLACK, labelsize=9)
    axis.xaxis.label.set_color(BLACK)
    axis.yaxis.label.set_color(BLACK)
    axis.xaxis.label.set_size(10)
    axis.yaxis.label.set_size(10)


def bar_axis(figure: Figure, rect: tuple[float, float, float, float] | None = None) -> Axes:
    axis = figure.add_axes(rect or chart_band(figure))
    style_axis(axis)
    return axis


def _axis_label(label: str, width: int = 42) -> str:
    """One line. A second line collides with the next category when the chart is full."""
    text = " ".join(str(label).split())
    if len(text) <= width:
        return text
    return text[: width - 1].rstrip() + "…"


def horizontal_bars(
    figure: Figure,
    labels: Sequence[str],
    values: Sequence[int],
    *,
    xlabel: str,
    rect: tuple[float, float, float, float] | None = None,
) -> None:
    """Ranking chart. Horizontal bars keep long category names readable."""
    axis = figure.add_axes(rect or chart_band(figure, left=0.40))
    style_axis(axis)
    if not labels:
        axis.axis("off")
        axis.text(0.5, 0.5, "No classified values in this extract", ha="center", va="center", color=MUTED)
        return
    pairs = [(_axis_label(label, 58), value) for label, value in zip(labels, values)]
    pairs.reverse()
    axis.barh(
        [label for label, _value in pairs],
        [value for _label, value in pairs],
        color=SERIES[0],
        height=0.62,
    )
    axis.set_xlabel(xlabel)
    axis.tick_params(axis="y", labelsize=8 if len(pairs) > 12 else 9)
    for index, (_label, value) in enumerate(pairs):
        axis.text(value, index, f"  {value}", va="center", fontsize=9, color=INK)
    axis.margins(x=0.15)


def grouped_bars(
    figure: Figure,
    categories: Sequence[str],
    series: Sequence[tuple[str, Sequence[float | None], str]],
    *,
    ylabel: str,
    horizontal: bool = False,
    value_format: str = "{:.0f}",
    rect: tuple[float, float, float, float] | None = None,
) -> None:
    """Draw one group per category. Missing values are omitted, not drawn as zero."""
    x, y, width, height = rect or chart_band(figure, left=0.36 if horizontal else 0.10)
    legend_band = 0.05
    axis = figure.add_axes((x, y, width, max(0.28, height - legend_band)))
    style_axis(axis)
    if not categories or not series:
        axis.axis("off")
        axis.text(0.5, 0.5, "No classified values in this extract", ha="center", va="center", color=MUTED)
        return
    count = len(series)
    width = min(0.8 / count, 0.24)
    positions = list(range(len(categories)))
    for index, (name, values, color) in enumerate(series):
        offset = (index - (count - 1) / 2) * width
        coords = []
        heights = []
        for position, value in zip(positions, values):
            if value is None:
                continue
            coords.append(position + offset)
            heights.append(value)
        if not coords:
            continue
        if horizontal:
            bars = axis.barh(coords, heights, height=width, color=color, label=name)
        else:
            bars = axis.bar(coords, heights, width=width, color=color, label=name)
        if len(categories) <= 10:
            labels = [value_format.format(value) if value else "" for value in heights]
            axis.bar_label(bars, labels=labels, padding=2, fontsize=6.5)
    if horizontal:
        axis.set_yticks(
            positions,
            [_axis_label(label, 42) for label in categories],
            fontsize=7.5 if len(categories) > 10 else 8,
        )
        axis.invert_yaxis()
        axis.set_xlabel(ylabel)
        axis.margins(x=0.18)
    else:
        axis.set_xticks(positions, list(categories))
        axis.set_ylabel(ylabel)
        axis.margins(y=0.22)
    axis.grid(axis="x" if horizontal else "y", alpha=0.25)
    handles, labels = axis.get_legend_handles_labels()
    if handles:
        figure.legend(
            handles,
            labels,
            frameon=False,
            fontsize=8,
            ncol=min(count, 4),
            loc="lower left",
            bbox_to_anchor=(x, y + height - legend_band + 0.005),
            bbox_transform=figure.transFigure,
        )


def region_pies(
    figure: Figure,
    panels: Sequence[tuple[str, Sequence[tuple[str, int]]]],
) -> None:
    """One pie per period. Labels sit in a legend so they do not cover the slices."""
    band = chart_band(figure, left=0.06)
    x, bottom, width, height = band
    shown = [panel for panel in panels if any(count for _label, count in panel[1])]
    if not shown:
        axis = figure.add_axes(band)
        axis.axis("off")
        axis.text(0.5, 0.5, "No regional visits in this extract", ha="center", va="center", color=MUTED)
        return
    order: list[str] = []
    for _title, pairs in shown:
        for label, count in pairs:
            if count and label not in order:
                order.append(label)
    slot = width / len(shown)
    for index, (title, pairs) in enumerate(shown):
        axis = figure.add_axes((x + index * slot + slot * 0.06, bottom + 0.08, slot * 0.82, max(0.28, height - 0.12)))
        labels = [label for label, count in pairs if count]
        values = [count for _label, count in pairs if count]
        colors = [REGION_COLORS.get(label, SERIES[i % len(SERIES)]) for i, label in enumerate(labels)]
        _wedges, _texts, autotexts = axis.pie(
            values,
            colors=colors,
            startangle=90,
            autopct=lambda share: f"{share:.0f}%" if share >= 6 else "",
            pctdistance=0.62,
            wedgeprops={"linewidth": 1, "edgecolor": "white"},
        )
        axis.set_title(title, fontsize=12, color=BLACK, pad=4, fontweight="bold")
        for wedge, autotext in zip(_wedges, autotexts):
            red, green, blue = wedge.get_facecolor()[:3]
            luminance = 0.299 * red + 0.587 * green + 0.114 * blue
            autotext.set_color(WHITE if luminance < 0.55 else BLACK)
            autotext.set_fontsize(9)
            autotext.set_fontweight("bold")
    figure.legend(
        [Patch(facecolor=REGION_COLORS.get(label, SERIES[0]), edgecolor="none", label=label) for label in order],
        order,
        frameon=False,
        ncol=len(order),
        loc="lower center",
        bbox_to_anchor=(0.5, bottom + 0.01),
        bbox_transform=figure.transFigure,
        fontsize=8,
    )


def stacked_share_bars(
    figure: Figure,
    categories: Sequence[str],
    series: Sequence[tuple[str, Sequence[float], str]],
) -> None:
    """100% stacked bars. Use this when each bar is a mix that adds to 100%."""
    axis = figure.add_axes((0.14, 0.28, 0.72, 0.48))
    style_axis(axis)
    if not categories or not series:
        axis.axis("off")
        axis.text(0.5, 0.5, "No classified values in this extract", ha="center", va="center", color=MUTED)
        return
    offsets = [0.0] * len(categories)
    for name, values, color in series:
        bars = axis.barh(list(categories), list(values), left=offsets, color=color, label=name, height=0.55)
        for bar, value, offset in zip(bars, values, offsets):
            if value >= 8:
                axis.text(
                    offset + value / 2,
                    bar.get_y() + bar.get_height() / 2,
                    f"{value:.0f}%",
                    ha="center",
                    va="center",
                    color="white",
                    fontsize=8,
                )
        offsets = [offset + value for offset, value in zip(offsets, values)]
    axis.set_xlabel("Share of dated visits (%)")
    axis.set_xlim(0, 100)
    axis.invert_yaxis()
    axis.legend(frameon=False, ncol=min(4, len(series)), loc="lower center", bbox_to_anchor=(0.5, 1.04))
