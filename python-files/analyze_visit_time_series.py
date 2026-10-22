"""Combined monthly and quarterly time-series PDF for cleaned visit files."""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from datetime import date
from pathlib import Path

from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.figure import Figure

from report_style import INK, SERIES, add_chart_page, add_text_page, bar_axis, series_colors, style_axis
from visit_model import Visit, group_by_year, load_cleaned_csv, month_span, year_coverage_label


def _month_key(value: date) -> str:
    return f"{value.year:04d}-{value.month:02d}"


def _next_month(year: int, month: int) -> tuple[int, int]:
    return (year + 1, 1) if month == 12 else (year, month + 1)


def _observed_months(visits: list[Visit]) -> list[str]:
    """Every calendar month from the first visit to the last, without filling later years."""
    if not visits:
        return []
    start = min(visit.visit_date for visit in visits)
    end = max(visit.visit_date for visit in visits)
    months: list[str] = []
    year, month = start.year, start.month
    while (year, month) <= (end.year, end.month):
        months.append(f"{year:04d}-{month:02d}")
        year, month = _next_month(year, month)
    return months


def write_time_series(visits: list[Visit], pdf_path: Path, summary_path: Path) -> None:
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    if not visits:
        raise ValueError("No dated visits were available for the time series.")

    by_year = group_by_year(visits)
    months = _observed_months(visits)
    present = {_month_key(visit.visit_date) for visit in visits}
    monthly = Counter(_month_key(visit.visit_date) for visit in visits)
    quarterly: Counter[str] = Counter(
        f"{visit.visit_date.year} Q{(visit.visit_date.month - 1) // 3 + 1}" for visit in visits
    )
    topic_monthly: Counter[tuple[str, str]] = Counter()
    topic_totals: Counter[str] = Counter()
    for visit in visits:
        key = _month_key(visit.visit_date)
        for topic in visit.solution_topics:
            topic_monthly[(key, topic)] += 1
            topic_totals[topic] += 1
    ranked_topics = [topic for topic, _count in topic_totals.most_common()]
    top_topics = ranked_topics[:5]
    if "AI Tools" in ranked_topics and "AI Tools" not in top_topics:
        top_topics.append("AI Tools")

    summary_rows: list[tuple[str, str, str, int]] = []
    for month in months:
        if month in present:
            summary_rows.append(("Monthly visits", month, "All dated visits", monthly[month]))
    for quarter, count in sorted(quarterly.items()):
        summary_rows.append(("Quarterly visits", quarter, "All dated visits", count))
    for (month, topic), count in sorted(topic_monthly.items()):
        summary_rows.append(("Monthly solution topic", month, topic, count))
    for year, year_visits in by_year.items():
        summary_rows.append(("Yearly visits", str(year), year_coverage_label(year_visits), len(year_visits)))

    gap_months = [month for month in months if month not in present]
    gap_note = (
        "Months inside the date span with no visits are left blank rather than drawn as zero: "
        + ", ".join(gap_months)
        + "."
        if gap_months
        else "Every month from the first visit through the last visit has at least one record."
    )
    partial = [
        year_coverage_label(year_visits)
        for year_visits in by_year.values()
        if month_span(visit.visit_date.month for visit in year_visits) != "January–December"
    ]
    partial_note = (
        f"Partial coverage: {', '.join(partial)}. Later months are not in the file and are not plotted as zero."
        if partial
        else "Each year in this extract covers January–December."
    )

    def plot_monthly(figure: Figure) -> None:
        axis = bar_axis(figure)
        colors = series_colors(list(by_year))
        run: list[int] = []
        previous: tuple[int, int] | None = None
        labeled_years: set[int] = set()

        def draw_run(indexes: list[int]) -> None:
            if not indexes:
                return
            year = int(months[indexes[0]][:4])
            axis.plot(
                indexes,
                [monthly[months[index]] for index in indexes],
                marker="o",
                linewidth=2,
                color=colors[year],
                label=str(year) if year not in labeled_years else None,
            )
            labeled_years.add(year)

        for index, month in enumerate(months):
            if month not in present:
                draw_run(run)
                run = []
                previous = None
                continue
            year, month_number = int(month[:4]), int(month[5:])
            year_changed = previous is not None and year != previous[0]
            month_gap = previous is not None and (year, month_number) != _next_month(*previous)
            if year_changed or month_gap:
                draw_run(run)
                run = []
            run.append(index)
            previous = (year, month_number)
        draw_run(run)
        tick_indexes = [index for index, month in enumerate(months) if int(month[5:]) in (1, 7)]
        axis.set_xticks(
            tick_indexes,
            [date(int(months[index][:4]), int(months[index][5:]), 1).strftime("%b %Y") for index in tick_indexes],
            rotation=0,
        )
        axis.set_ylabel("Visits")
        axis.legend(title="Year", frameon=False, ncol=len(by_year), loc="upper left")

    def plot_by_year(figure: Figure) -> None:
        axis = bar_axis(figure)
        colors = series_colors(list(by_year))
        for year, year_visits in by_year.items():
            counts = Counter(visit.visit_date.month for visit in year_visits)
            month_numbers = sorted(counts)
            runs: list[list[int]] = []
            current: list[int] = []
            previous: int | None = None
            for month in month_numbers:
                if previous is not None and month != previous + 1:
                    runs.append(current)
                    current = []
                current.append(month)
                previous = month
            if current:
                runs.append(current)
            labeled = False
            for run in runs:
                axis.plot(
                    run,
                    [counts[month] for month in run],
                    marker="o",
                    linewidth=2,
                    color=colors[year],
                    label=year_coverage_label(year_visits) if not labeled else None,
                )
                labeled = True
        axis.set_xticks(range(1, 13), ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])
        axis.set_ylabel("Visits")
        axis.legend(title="Coverage", frameon=False, loc="upper left")
        axis.margins(y=0.18)

    def plot_quarterly(figure: Figure) -> None:
        axis = bar_axis(figure)
        labels = sorted(quarterly, key=lambda label: (int(label[:4]), int(label[-1])))
        colors = series_colors(list(by_year))
        positions = list(range(len(labels)))
        axis.bar(
            positions,
            [quarterly[label] for label in labels],
            color=[colors[int(label[:4])] for label in labels],
        )
        axis.set_xticks(positions, labels, rotation=35, ha="right")
        axis.set_ylabel("Visits")
        peak = max(quarterly.values()) if quarterly else 0
        axis.set_ylim(0, peak * 1.18 if peak else 1)
        for position, label in enumerate(labels):
            axis.text(position, quarterly[label], str(quarterly[label]), ha="center", va="bottom", fontsize=8)

    def plot_topics(figure: Figure) -> None:
        # One panel per topic. Several lines on one axis hide each other.
        panels = top_topics[:6]
        band = getattr(figure, "chart_rect", (0.08, 0.20, 0.86, 0.58))
        left, bottom, width, height = band
        columns = 3 if len(panels) > 4 else 2
        rows = 2
        gap_x, gap_y = 0.06, 0.08
        panel_width = (width - gap_x * (columns - 1)) / columns
        panel_height = (height - gap_y * (rows - 1)) / rows
        rects = []
        for index in range(len(panels)):
            column = index % columns
            row = index // columns
            rects.append(
                (
                    left + column * (panel_width + gap_x),
                    bottom + (rows - 1 - row) * (panel_height + gap_y),
                    panel_width,
                    panel_height,
                )
            )
        tick_indexes = [index for index, month in enumerate(months) if int(month[5:]) in (1, 7)]
        tick_labels = [
            date(int(months[index][:4]), int(months[index][5:]), 1).strftime("%b %y")
            for index in tick_indexes
        ]
        for topic, rect in zip(panels, rects):
            axis = figure.add_axes(rect)
            style_axis(axis)
            axis.plot(
                range(len(months)),
                [topic_monthly.get((month, topic), 0) if month in present else None for month in months],
                marker="o",
                linewidth=1.6,
                color=SERIES[0],
            )
            axis.set_title(topic, fontsize=9, loc="left", color=INK)
            axis.set_xticks(tick_indexes, tick_labels, fontsize=7)
            axis.set_ylabel("Visits", fontsize=8)

    start = min(visit.visit_date for visit in visits)
    end = max(visit.visit_date for visit in visits)
    with PdfPages(pdf_path) as pdf:
        add_text_page(
            pdf,
            "MNL visits over time — where to add demo capacity",
            [
                (
                    "Coverage",
                    f"{len(visits)} dated visits from {start:%b %d, %Y} to {end:%b %d, %Y}. "
                    + " ".join(f"{year_coverage_label(year_visits)}: {len(year_visits)}." for year_visits in by_year.values())
                    + " Use the peaks to roster associates, and compare years only on months every file contains.",
                ),
                ("Gaps", gap_note + " " + partial_note),
                (
                    "Solution topics",
                    "Each panel is a solution clients ask to see, including AI Tools. "
                    "A visit can appear in more than one panel.",
                ),
            ],
        )
        add_chart_page(
            pdf,
            "Monthly visits — when the bench needs more associates",
            f"{start:%b %Y} through {end:%b %Y}. {partial_note}",
            plot_monthly,
            note="Roster extra associates onto the peaks. Each color is one year. A break inside a year is a month with no logged demo, not a month plotted as zero.",
        )
        add_chart_page(
            pdf,
            "Same month across years — the window for the demo target",
            "Each line is one calendar year and stops where that file stops. Compare January–June when FH1 2026 is in the set.",
            plot_by_year,
            note="Publish the next demo target on the months every year contains. Do not score FH1 2026 against a full year.",
        )
        add_chart_page(
            pdf,
            "Quarterly visits — where demo capacity is already tight",
            "Only quarters with at least one visit are shown. A missing quarter was not in that file.",
            plot_quarterly,
            note=partial_note,
        )
        add_chart_page(
            pdf,
            "Solution topics over time — what to keep in product training",
            "Each panel is one solution topic. A month with visits but no mention of that topic is zero. A month with no visits breaks the line.",
            plot_topics,
            note="Train the modules that stay in the requests, including AI Tools. Associates who can show them can take the next demo.",
        )

    with summary_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(("analysis", "period", "category", "visit_count"))
        writer.writerows(summary_rows)


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Create a combined time-series PDF.")
    parser.add_argument("--input", type=Path, nargs="+", required=True)
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
    write_time_series(visits, output, summary)
    print(f"Wrote time series for {len(visits)} visits to {output}")


if __name__ == "__main__":
    main()
