"""Cross-year story PDF. Sentences and chart scales come from the loaded visits."""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from pathlib import Path

from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.figure import Figure

from narrative import (
    activity_implication,
    activity_story,
    demonstration_implication,
    demonstration_story,
    limits_implication,
    limits_story,
    method_implication,
    method_story,
    quarterly_implication,
    quarterly_story,
    region_implication,
    region_story,
    solution_implication,
    solution_story,
    workflow_implication,
    workflow_story,
)
from report_style import (
    INK,
    MUTED,
    add_text_page,
    bar_axis,
    draw_footer,
    grouped_bars,
    new_figure,
    save_page,
    series_colors,
)
from visit_model import (
    Visit,
    count_labels,
    group_by_year,
    load_cleaned_csv,
    month_counts,
    quarter_counts,
    ranked,
    year_coverage_label,
)


def _series(
    by_year: dict[int, list[Visit]],
    categories: list[str],
    counts_by_year: dict[int, Counter[str]],
    *,
    as_percent: bool = False,
    skip_missing: bool = False,
):
    colors = series_colors(list(by_year))
    series = []
    for year, visits in by_year.items():
        denominator = len(visits) or 1
        values: list[float | None] = []
        for category in categories:
            if skip_missing and category not in counts_by_year[year]:
                values.append(None)
                continue
            count = counts_by_year[year].get(category, 0)
            values.append(count / denominator * 100 if as_percent else count)
        series.append((year_coverage_label(visits), values, colors[year]))
    return series


def _contiguous(months: list[int]) -> list[list[int]]:
    runs: list[list[int]] = []
    current: list[int] = []
    previous: int | None = None
    for month in months:
        if previous is not None and month != previous + 1:
            runs.append(current)
            current = []
        current.append(month)
        previous = month
    if current:
        runs.append(current)
    return runs


def _line_chart(figure: Figure, by_year: dict[int, list[Visit]]) -> None:
    axis = bar_axis(figure)
    colors = series_colors(list(by_year))
    for year, visits in by_year.items():
        counts = month_counts(visits)
        months = sorted(counts)
        labeled = False
        for run in _contiguous(months):
            axis.plot(
                run,
                [counts[month] for month in run],
                marker="o",
                linewidth=2,
                color=colors[year],
                label=year_coverage_label(visits) if not labeled else None,
            )
            labeled = True
    axis.set_xticks(range(1, 13), ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])
    axis.set_ylabel("Recorded visits")
    axis.legend(title="Coverage", frameon=False)
    axis.margins(y=0.2)


def _theme_categories(by_year: dict[int, list[Visit]], attribute: str, limit: int, *, skip_residual: bool) -> list[str]:
    totals: Counter[str] = Counter()
    for visits in by_year.values():
        totals.update(count_labels(visits, attribute))
    return [label for label, _count in ranked(totals, skip_residual=skip_residual)[:limit]]


def write_business_story(
    visits: list[Visit],
    pdf_path: Path,
    summary_path: Path,
) -> None:
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    by_year = group_by_year(visits)
    if not by_year:
        raise ValueError("No dated visits were available for the business story.")

    topic_counts = {year: count_labels(year_visits, "solution_topics") for year, year_visits in by_year.items()}
    workflow_counts = {year: count_labels(year_visits, "workflows") for year, year_visits in by_year.items()}
    demo_type_counts = {year: count_labels(year_visits, "demonstration_type") for year, year_visits in by_year.items()}
    region_counts = {year: count_labels(year_visits, "region") for year, year_visits in by_year.items()}
    topic_labels = _theme_categories(by_year, "solution_topics", 7, skip_residual=False)
    workflow_labels = _theme_categories(by_year, "workflows", 6, skip_residual=True)
    demo_labels = _theme_categories(by_year, "demonstration_type", 5, skip_residual=False)
    region_labels = [label for label, _count in ranked(sum(region_counts.values(), Counter()))]

    summary_rows: list[tuple[str, str, str, int]] = []
    for year, year_visits in by_year.items():
        summary_rows.append(("Yearly visits", str(year), "All dated visits", len(year_visits)))
        for month, count in sorted(month_counts(year_visits).items()):
            summary_rows.append(("Monthly visits", f"{year}-{month:02d}", "All dated visits", count))
        for quarter, count in sorted(quarter_counts(year_visits).items()):
            summary_rows.append(("Quarterly visits", f"{year} Q{quarter}", "All dated visits", count))
        for label, count in ranked(region_counts[year]):
            summary_rows.append(("Region", str(year), label, count))
        for label, count in ranked(topic_counts[year]):
            summary_rows.append(("Solution topic", str(year), label, count))
        for label, count in ranked(workflow_counts[year]):
            summary_rows.append(("Workflow", str(year), label, count))
        for label, count in ranked(demo_type_counts[year]):
            summary_rows.append(("Demonstration type", str(year), label, count))

    total = len(visits)
    with PdfPages(pdf_path) as pdf:
        cover = new_figure()
        cover.patch.set_facecolor("#F4F7F8")
        cover.text(0.07, 0.86, "MANILA CLIENT VISITS", fontsize=12, fontweight="bold", color="#1C7C8C")
        cover.text(
            0.07,
            0.74,
            f"What {total} dated visit records show",
            fontsize=26,
            fontweight="bold",
            color=INK,
        )
        cover.text(
            0.07,
            0.64,
            "Activity, session types, workflows, solution topics, and region",
            fontsize=12,
            color=MUTED,
        )
        colors = series_colors(list(by_year))
        slot_width = 0.84 / max(len(by_year), 1)
        for index, (year, year_visits) in enumerate(by_year.items()):
            x = 0.07 + index * slot_width
            cover.text(x, 0.50, "RECORDED VISITS", fontsize=8, color=MUTED)
            cover.text(x, 0.40, str(len(year_visits)), fontsize=28, color=colors[year], fontweight="bold")
            cover.text(x, 0.33, year_coverage_label(year_visits), fontsize=10, color=MUTED)
        cover.text(
            0.07,
            0.20,
            "Compare months that appear in every year. A partial year is labeled with its months and is not treated as a full year of zero activity.",
            fontsize=10,
            color=INK,
        )
        cover.text(
            0.07,
            0.12,
            "Rows are logged visits, not unique clients. Topic and workflow bars can overlap.",
            fontsize=9,
            color=MUTED,
        )
        draw_footer(cover, "Source: cleaned Manila visit files grouped by the visit date.")
        save_page(pdf, cover)

        add_chart_page = _chart_page(pdf)
        add_chart_page(
            "Read the months that were actually logged",
            activity_story(by_year),
            lambda figure: _line_chart(figure, by_year),
            note=activity_implication(by_year),
        )
        quarter_keys = [str(quarter) for quarter in range(1, 5)]
        quarter_by_year = {
            year: Counter({str(quarter): count for quarter, count in quarter_counts(year_visits).items()})
            for year, year_visits in by_year.items()
        }
        add_chart_page(
            "Quarterly cadence, with missing quarters left out",
            quarterly_story(by_year),
            lambda figure: grouped_bars(
                figure,
                [f"Q{quarter}" for quarter in range(1, 5)],
                _series(by_year, quarter_keys, quarter_by_year, skip_missing=True),
                ylabel="Recorded visits",
            ),
            note=quarterly_implication(by_year),
        )
        add_chart_page(
            "Solution topics mentioned in the visit notes",
            solution_story(by_year),
            lambda figure: grouped_bars(
                figure,
                topic_labels,
                _series(by_year, topic_labels, topic_counts),
                ylabel="Visits mentioning the topic",
                horizontal=True,
                rect=(0.32, 0.22, 0.48, 0.60),
            ),
            note=solution_implication(by_year),
        )
        add_chart_page(
            "Workflows written in the visit notes",
            workflow_story(by_year),
            lambda figure: grouped_bars(
                figure,
                workflow_labels,
                _series(by_year, workflow_labels, workflow_counts),
                ylabel="Visits mentioning the workflow",
                horizontal=True,
                rect=(0.32, 0.22, 0.48, 0.60),
            ),
            note=workflow_implication(by_year),
        )
        add_chart_page(
            "Demonstration type, as selected",
            demonstration_story(by_year),
            lambda figure: grouped_bars(
                figure,
                demo_labels,
                _series(by_year, demo_labels, demo_type_counts),
                ylabel="Visits",
                horizontal=True,
                rect=(0.30, 0.22, 0.50, 0.60),
            ),
            note=demonstration_implication(by_year),
        )
        add_chart_page(
            "Where the logged visits were based",
            region_story(by_year),
            lambda figure: grouped_bars(
                figure,
                region_labels,
                _series(by_year, region_labels, region_counts, as_percent=True),
                ylabel="Share of dated visits (%)",
                value_format="{:.0f}%",
            ),
            note=region_implication(by_year),
        )
        add_text_page(
            pdf,
            "What these records can and cannot support",
            [
                ("Scope", limits_story(by_year)),
                ("Limit", limits_implication()),
                ("Method", method_story()),
                ("Interpretation", method_implication()),
            ],
        )

    with summary_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(("analysis", "year", "category", "visit_count"))
        writer.writerows(summary_rows)


def _chart_page(pdf: PdfPages):
    def add(title: str, body: str, draw, note: str = "") -> None:
        from report_style import add_chart_page as draw_page

        draw_page(pdf, title, body, draw, note=note)

    return add


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Create the cross-year Manila visit story.")
    parser.add_argument("--input", type=Path, nargs="+", required=True, help="Cleaned visit CSVs.")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    args = parser.parse_args()

    def resolve(path: Path) -> Path:
        return path if path.is_absolute() else project_root / path

    visits: list[Visit] = []
    for path in args.input:
        loaded, skipped = load_cleaned_csv(resolve(path))
        visits.extend(loaded)
        for message in skipped:
            print(message)
    output = resolve(args.output)
    summary = resolve(args.summary)
    write_business_story(visits, output, summary)
    print(f"Wrote business story for {len(visits)} visits to {output}")


if __name__ == "__main__":
    main()
