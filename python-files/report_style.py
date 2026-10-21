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


PAGE_SIZE = (11.69, 8.27)
INK = "#17324D"
MUTED = "#4F5D6B"
RULE = "#6B7280"
SERIES = ("#1C7C8C", "#465A8B", "#E08E45", "#6B4C7A", "#2F6F4E", "#B85C38")
SOURCE_LINE = "Source: Manila visit workbooks. Counts follow the field named on each page."


def series_colors(keys: Sequence[object]) -> dict[object, str]:
    return {key: SERIES[index % len(SERIES)] for index, key in enumerate(keys)}


def new_figure() -> Figure:
    figure = plt.figure(figsize=PAGE_SIZE)
    figure.patch.set_facecolor("white")
    return figure


def wrap(text: str, width: int) -> str:
    return textwrap.fill(" ".join(text.split()), width=width)


def draw_title(figure: Figure, title: str, body: str) -> None:
    figure.text(0.06, 0.945, title, fontsize=16, fontweight="bold", color=INK, va="top")
    figure.text(0.06, 0.89, wrap(body, 125), fontsize=9, color=MUTED, va="top", linespacing=1.35)


def draw_footer(figure: Figure, note: str | None = None) -> None:
    figure.text(0.06, 0.035, note or SOURCE_LINE, fontsize=7.5, color=RULE)


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
    figure = new_figure()
    figure.text(0.06, 0.955, title, fontsize=15, fontweight="bold", color=INK, va="top")
    figure.text(0.06, 0.905, wrap(body, 128), fontsize=8.5, color=MUTED, va="top", linespacing=1.3)
    if note:
        figure.text(0.06, 0.145, wrap(note, 140), fontsize=8, color=MUTED, va="top", linespacing=1.25)
    draw(figure)
    draw_footer(figure, footer)
    save_page(pdf, figure)


def add_text_page(pdf: PdfPages, title: str, paragraphs: list[tuple[str, str]]) -> None:
    figure = new_figure()
    figure.text(0.07, 0.90, title, fontsize=18, fontweight="bold", color=INK, va="top")
    cursor = 0.82
    for heading, paragraph in paragraphs:
        figure.text(0.07, cursor, heading, fontsize=11, fontweight="bold", color="#1C7C8C", va="top")
        wrapped = wrap(paragraph, 118)
        figure.text(0.07, cursor - 0.04, wrapped, fontsize=10, color=INK, va="top", linespacing=1.4)
        cursor -= 0.05 + 0.028 * (wrapped.count("\n") + 1) + 0.04
    draw_footer(figure)
    save_page(pdf, figure)


def style_axis(axis: Axes) -> None:
    axis.grid(axis="y", alpha=0.25)
    axis.set_axisbelow(True)
    axis.spines["top"].set_visible(False)
    axis.spines["right"].set_visible(False)


def bar_axis(figure: Figure, rect: tuple[float, float, float, float] = (0.08, 0.24, 0.86, 0.58)) -> Axes:
    axis = figure.add_axes(rect)
    style_axis(axis)
    return axis


def horizontal_bars(
    figure: Figure,
    labels: Sequence[str],
    values: Sequence[int],
    *,
    xlabel: str,
    rect: tuple[float, float, float, float] = (0.36, 0.22, 0.58, 0.60),
) -> None:
    axis = figure.add_axes(rect)
    style_axis(axis)
    if not labels:
        axis.axis("off")
        axis.text(0.5, 0.5, "No classified values in this extract", ha="center", va="center", color=MUTED)
        return
    pairs = list(zip(labels, values))
    pairs.reverse()
    axis.barh(
        [label for label, _value in pairs],
        [value for _label, value in pairs],
        color=SERIES[0],
    )
    axis.set_xlabel(xlabel)
    for index, (_label, value) in enumerate(pairs):
        axis.text(value, index, f" {value}", va="center", fontsize=8, color=INK)
    axis.margins(x=0.12)
    if len(labels) > 12:
        axis.tick_params(axis="y", labelsize=8)


def grouped_bars(
    figure: Figure,
    categories: Sequence[str],
    series: Sequence[tuple[str, Sequence[float | None], str]],
    *,
    ylabel: str,
    horizontal: bool = False,
    value_format: str = "{:.0f}",
    rect: tuple[float, float, float, float] = (0.10, 0.24, 0.82, 0.56),
) -> None:
    """Draw one group per category. Missing values are omitted, not drawn as zero."""
    axis = figure.add_axes(rect)
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
        labels = [value_format.format(value) if value else "" for value in heights]
        axis.bar_label(bars, labels=labels, padding=2, fontsize=6.5)
    if horizontal:
        axis.set_yticks(positions, list(categories), fontsize=8)
        axis.invert_yaxis()
        axis.set_xlabel(ylabel)
        axis.margins(x=0.18)
        axis.legend(title="Year", frameon=False, loc="center left", bbox_to_anchor=(1.02, 0.5))
    else:
        axis.set_xticks(positions, list(categories), rotation=25, ha="right")
        axis.set_ylabel(ylabel)
        axis.margins(y=0.18)
        axis.legend(title="Year", frameon=False, loc="upper right")
    axis.grid(axis="x" if horizontal else "y", alpha=0.25)
