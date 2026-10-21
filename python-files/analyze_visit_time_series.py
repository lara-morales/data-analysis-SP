"""Combined monthly and quarterly time-series PDF for cleaned visit files."""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from datetime import date
from pathlib import Path

from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.figure import Figure

from report_style import add_chart_page, add_text_page, bar_axis, series_colors, style_axis
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
    top_topics = [topic for topic, _count in topic_totals.most_common(8)]

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
        style_axis(axis)
        positions = list(range(len(months)))
        colors = series_colors(list(by_year))
        live_positions = [index for index, month in enumerate(months) if month in present]
        axis.bar(
            live_positions,
            [monthly[months[index]] for index in live_positions],
            color=[colors[int(months[index][:4])] for index in live_positions],
        )
        axis.set_xticks(positions, months, rotation=65, ha="right", fontsize=7)
        axis.set_ylabel("Visits")
        for position in live_positions:
            value = monthly[months[position]]
            axis.text(position, value, str(value), ha="center", va="bottom", fontsize=6.5)

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
        axis.legend(title="Coverage", frameon=False)

    def plot_quarterly(figure: Figure) -> None:
        axis = bar_axis(figure, (0.08, 0.24, 0.86, 0.58))
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
        for position, label in enumerate(labels):
            axis.text(position, quarterly[label], str(quarterly[label]), ha="center", va="bottom", fontsize=8)

    def plot_topics(figure: Figure) -> None:
        axis = bar_axis(figure, (0.08, 0.24, 0.72, 0.58))
        for topic in top_topics:
            runs: list[list[str]] = []
            current: list[str] = []
            previous: tuple[int, int] | None = None
            for month in months:
                if month not in present:
                    if current:
                        runs.append(current)
                        current = []
                    previous = None
                    continue
                year, month_number = int(month[:4]), int(month[5:])
                if previous is not None and (year, month_number) != _next_month(*previous):
                    runs.append(current)
                    current = []
                current.append(month)
                previous = (year, month_number)
            if current:
                runs.append(current)
            labeled = False
            for run in runs:
                positions = [months.index(month) for month in run]
                axis.plot(
                    positions,
                    [topic_monthly.get((month, topic), 0) for month in run],
                    marker="o",
                    linewidth=1.6,
                    label=topic if not labeled else None,
                )
                labeled = True
        axis.set_xticks(range(len(months)), months, rotation=65, ha="right", fontsize=7)
        axis.set_ylabel("Visits mentioning the topic")
        axis.legend(loc="upper left", bbox_to_anchor=(1.01, 1), fontsize=7, frameon=False)

    start = min(visit.visit_date for visit in visits)
    end = max(visit.visit_date for visit in visits)
    with PdfPages(pdf_path) as pdf:
        add_text_page(
            pdf,
            "Manila visits over time",
            [
                (
                    "Coverage",
                    f"{len(visits)} dated visits from {start:%b %d, %Y} to {end:%b %d, %Y}. "
                    + " ".join(f"{year_coverage_label(year_visits)}: {len(year_visits)}." for year_visits in by_year.values()),
                ),
                ("Gaps", gap_note + " " + partial_note),
                (
                    "Solution topics",
                    "A visit counts once for each matched topic in Solutions Discussed. "
                    "The topic chart shows the eight topics with the most visits across the whole span.",
                ),
            ],
        )
        add_chart_page(
            pdf,
            "Monthly visit volume",
            f"{start:%b %Y} through {end:%b %Y}. {partial_note}",
            plot_monthly,
            note=gap_note,
        )
        add_chart_page(
            pdf,
            "Same month compared across years",
            "Each line is one calendar year. A year stops where its file stops. A gap in recorded months breaks the line.",
            plot_by_year,
            note=partial_note,
        )
        add_chart_page(
            pdf,
            "Quarterly visit volume",
            "Only quarters with at least one visit are shown.",
            plot_quarterly,
            note=partial_note,
        )
        add_chart_page(
            pdf,
            "Solution topics over time",
            "Monthly visits for the eight most mentioned solution topics. A month with visits but no mention of that topic is zero. A month with no visits is a gap.",
            plot_topics,
            note="Topics are not exclusive. One visit can contribute to more than one line.",
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
