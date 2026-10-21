"""Generate a combined time-series report for Manila visits from 2024 to 2026."""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Callable

import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

from solution_categories import is_non_solution_entry, solution_topic_categories


@dataclass(frozen=True)
class VisitRecord:
    visit_date: date
    solution_topics: frozenset[str]


@dataclass
class TimeSeriesCounts:
    monthly_visits: Counter[str]
    quarterly_visits: Counter[str]
    month_by_year: Counter[tuple[int, int]]
    monthly_solution_topics: Counter[tuple[str, str]]
    yearly_solution_topics: Counter[tuple[int, str]]


def load_visit_records(input_paths: list[Path]) -> list[VisitRecord]:
    """Read cleaned visit CSVs and classify each visit's solution topics."""
    records: list[VisitRecord] = []
    for input_path in input_paths:
        with input_path.open(encoding="utf-8-sig", newline="") as handle:
            for line_number, row in enumerate(csv.DictReader(handle), start=2):
                date_text = (row.get("Visit Date Clean") or "").strip()
                try:
                    visit_date = datetime.strptime(date_text, "%Y-%m-%d").date()
                except ValueError as error:
                    raise ValueError(
                        f"Invalid or missing Visit Date Clean in {input_path} at CSV line {line_number}: "
                        f"{date_text!r}"
                    ) from error

                solutions_text = row.get("Solutions Discussed") or ""
                topics = (
                    set()
                    if is_non_solution_entry(solutions_text)
                    else set(solution_topic_categories(solutions_text))
                )
                records.append(VisitRecord(visit_date, frozenset(topics)))
    if not records:
        raise ValueError("No visit records were found in the supplied input files.")
    return records


def build_time_series(records: list[VisitRecord]) -> TimeSeriesCounts:
    """Aggregate visits and per-visit solution topics at monthly and quarterly grain."""
    monthly_visits: Counter[str] = Counter()
    quarterly_visits: Counter[str] = Counter()
    month_by_year: Counter[tuple[int, int]] = Counter()
    monthly_solution_topics: Counter[tuple[str, str]] = Counter()
    yearly_solution_topics: Counter[tuple[int, str]] = Counter()

    for record in records:
        year = record.visit_date.year
        month = record.visit_date.month
        month_key = record.visit_date.strftime("%Y-%m")
        quarter_key = f"{year} Q{(month - 1) // 3 + 1}"
        monthly_visits[month_key] += 1
        quarterly_visits[quarter_key] += 1
        month_by_year[(year, month)] += 1
        for topic in record.solution_topics:
            monthly_solution_topics[(month_key, topic)] += 1
            yearly_solution_topics[(year, topic)] += 1

    return TimeSeriesCounts(
        monthly_visits,
        quarterly_visits,
        month_by_year,
        monthly_solution_topics,
        yearly_solution_topics,
    )


def add_page(
    pdf: PdfPages,
    title: str,
    description: str,
    chart: Callable[[plt.Figure], None],
) -> None:
    figure = plt.figure(figsize=(11.69, 8.27))
    figure.text(0.07, 0.94, title, fontsize=18, fontweight="bold", color="#17324D")
    figure.text(0.07, 0.905, description, fontsize=9.5, color="#4F5D6B", wrap=True)
    chart(figure)
    figure.text(
        0.07,
        0.025,
        "Source: Cleaned Manila visit datasets | Solution topics use shared regex categories",
        fontsize=7,
        color="#6B7280",
    )
    pdf.savefig(figure, bbox_inches="tight")
    plt.close(figure)


def plot_monthly_timeline(figure: plt.Figure, counts: TimeSeriesCounts) -> None:
    axis = figure.add_axes((0.09, 0.17, 0.86, 0.65))
    months = sorted(counts.monthly_visits)
    values = [counts.monthly_visits[month] for month in months]
    colors = [("#1C7C8C" if month[:4] != "2026" else "#E08E45") for month in months]
    positions = list(range(len(months)))
    axis.bar(positions, values, color=colors)
    axis.set_xticks(positions, months, rotation=65, ha="right", fontsize=8)
    axis.set_ylabel("Number of visits")
    axis.set_title("Monthly visit volume (2026 data through June)")
    axis.grid(axis="y", alpha=0.25)
    axis.set_axisbelow(True)
    for position, value in zip(positions, values):
        axis.text(position, value, str(value), ha="center", va="bottom", fontsize=7)


def plot_monthly_comparison(figure: plt.Figure, counts: TimeSeriesCounts) -> None:
    axis = figure.add_axes((0.10, 0.16, 0.83, 0.66))
    years = sorted({year for year, _ in counts.month_by_year})
    months = list(range(1, 13))
    for year in years:
        values = [
            counts.month_by_year.get((year, month))
            for month in months
        ]
        available = [index for index, value in enumerate(values) if value is not None]
        axis.plot(
            [months[index] for index in available],
            [values[index] for index in available],
            marker="o",
            linewidth=2,
            label=str(year),
        )
    axis.set_xticks(months, [date(2000, month, 1).strftime("%b") for month in months])
    axis.set_ylabel("Number of visits")
    axis.set_title("Monthly pattern by year")
    axis.grid(alpha=0.25)
    axis.set_axisbelow(True)
    axis.legend(title="Year")
    axis.text(
        0.99,
        0.02,
        "2026 includes January–June only; later months are not plotted as zero.",
        transform=axis.transAxes,
        ha="right",
        fontsize=8,
        color="#4F5D6B",
    )


def plot_quarterly_timeline(figure: plt.Figure, counts: TimeSeriesCounts) -> None:
    axis = figure.add_axes((0.09, 0.17, 0.86, 0.65))
    quarters = sorted(
        counts.quarterly_visits,
        key=lambda label: (int(label[:4]), int(label[-1])),
    )
    values = [counts.quarterly_visits[quarter] for quarter in quarters]
    colors = [("#E08E45" if quarter.startswith("2026") else "#1C7C8C") for quarter in quarters]
    positions = list(range(len(quarters)))
    axis.bar(positions, values, color=colors)
    axis.set_xticks(positions, quarters, rotation=35, ha="right")
    axis.set_ylabel("Number of visits")
    axis.set_title("Quarterly visit volume")
    axis.grid(axis="y", alpha=0.25)
    axis.set_axisbelow(True)
    for position, value in zip(positions, values):
        axis.text(position, value, str(value), ha="center", va="bottom", fontsize=8)


def plot_solution_topic_timeline(figure: plt.Figure, counts: TimeSeriesCounts) -> None:
    axis = figure.add_axes((0.10, 0.16, 0.83, 0.66))
    topic_totals = Counter()
    for (_, topic), count in counts.monthly_solution_topics.items():
        topic_totals[topic] += count
    topics = [topic for topic, _ in topic_totals.most_common(8)]
    months = sorted(counts.monthly_visits)
    for topic in topics:
        axis.plot(
            months,
            [counts.monthly_solution_topics.get((month, topic), 0) for month in months],
            marker="o",
            linewidth=1.7,
            label=topic,
        )
    axis.set_xticks(range(len(months)), months, rotation=65, ha="right", fontsize=8)
    axis.set_ylabel("Visits mentioning topic")
    axis.set_title("Monthly trend for the eight most-discussed solution topics")
    axis.grid(alpha=0.25)
    axis.set_axisbelow(True)
    axis.legend(loc="upper left", bbox_to_anchor=(1.01, 1), fontsize=8)


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(
        description="Create a combined time-series PDF analysis of Manila visits."
    )
    parser.add_argument(
        "--input",
        type=Path,
        nargs="+",
        default=[
            project_root / "cleaned_data" / "raw-2024_cleaned.csv",
            project_root / "cleaned_data" / "2025-manila-visit_raw-final_cleaned.csv",
            project_root / "cleaned_data" / "raw-1h2026_cleaned.csv",
        ],
        help="One or more cleaned visit CSVs to combine.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=project_root / "output" / "manila_visit_time_series_2024_2026.pdf",
    )
    parser.add_argument(
        "--summary",
        type=Path,
        default=project_root / "output" / "manila_visit_time_series_2024_2026_summary.csv",
    )
    args = parser.parse_args()

    input_paths = [
        path if path.is_absolute() else project_root / path
        for path in args.input
    ]
    output_path = args.output if args.output.is_absolute() else project_root / args.output
    summary_path = args.summary if args.summary.is_absolute() else project_root / args.summary
    output_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)

    records = load_visit_records(input_paths)
    counts = build_time_series(records)
    years = sorted({record.visit_date.year for record in records})
    yearly_visits = Counter(record.visit_date.year for record in records)
    summary_rows: list[tuple[str, str, str, int]] = []

    summary_rows.extend(
        ("Monthly visits", month, "All visits", count)
        for month, count in sorted(counts.monthly_visits.items())
    )
    summary_rows.extend(
        ("Quarterly visits", quarter, "All visits", count)
        for quarter, count in sorted(counts.quarterly_visits.items())
    )
    summary_rows.extend(
        ("Monthly visits by year", f"{year}-{month:02d}", "All visits", count)
        for (year, month), count in sorted(counts.month_by_year.items())
    )
    summary_rows.extend(
        ("Monthly solution topic", month, topic, count)
        for (month, topic), count in sorted(counts.monthly_solution_topics.items())
    )
    summary_rows.extend(
        ("Yearly solution topic", str(year), topic, count)
        for (year, topic), count in sorted(counts.yearly_solution_topics.items())
    )
    summary_rows.extend(
        ("Yearly visits", str(year), "All visits", yearly_visits[year])
        for year in years
    )

    with PdfPages(output_path) as pdf:
        figure = plt.figure(figsize=(11.69, 8.27))
        figure.text(
            0.07,
            0.91,
            "Manila Client Visits: Combined Time-Series Analysis",
            fontsize=20,
            fontweight="bold",
            color="#17324D",
        )
        figure.text(
            0.07,
            0.83,
            f"Coverage: {min(record.visit_date for record in records):%b %d, %Y} "
            f"to {max(record.visit_date for record in records):%b %d, %Y}",
            fontsize=13,
            color="#4F5D6B",
        )
        figure.text(
            0.07,
            0.73,
            f"Combined visits: {len(records):,}\n"
            + "\n".join(f"{year}: {yearly_visits[year]:,} visits" for year in years),
            fontsize=14,
            color="#17324D",
            linespacing=1.8,
        )
        figure.text(
            0.07,
            0.48,
            "Report contents",
            fontsize=14,
            fontweight="bold",
            color="#17324D",
        )
        figure.text(
            0.07,
            0.42,
            "Monthly visit volume across the full period; month-of-year comparison; "
            "quarterly volume; and monthly trends for the most-discussed solution topics.",
            fontsize=11,
            color="#4F5D6B",
            wrap=True,
        )
        figure.text(
            0.07,
            0.29,
            "Interpretation notes",
            fontsize=14,
            fontweight="bold",
            color="#17324D",
        )
        figure.text(
            0.07,
            0.22,
            "2026 data covers January through June only. Missing later months are shown as "
            "unavailable, not zero. A visit contributes at most once to each solution topic; "
            "a visit may contribute to multiple topics. Topic labels use the shared regex rules.",
            fontsize=10.5,
            color="#4F5D6B",
            wrap=True,
        )
        figure.text(
            0.07,
            0.06,
            "Source: Cleaned Manila visit datasets",
            fontsize=8,
            color="#6B7280",
        )
        pdf.savefig(figure, bbox_inches="tight")
        plt.close(figure)

        add_page(
            pdf,
            "Monthly Visit Volume",
            "Each bar is one calendar month. 2026 is shown through June only.",
            lambda figure: plot_monthly_timeline(figure, counts),
        )
        add_page(
            pdf,
            "Month-of-Year Comparison",
            "Compares the same calendar months across years. Unavailable 2026 months are omitted rather than treated as zero.",
            lambda figure: plot_monthly_comparison(figure, counts),
        )
        add_page(
            pdf,
            "Quarterly Visit Volume",
            "Quarterly totals smooth month-to-month variation; 2026 includes Q1 and Q2 through June.",
            lambda figure: plot_quarterly_timeline(figure, counts),
        )
        add_page(
            pdf,
            "Solution Topics Over Time",
            "Monthly visit counts for the eight most-discussed solution topics across the combined period. "
            "Each visit counts once per topic, even if its text repeats that topic.",
            lambda figure: plot_solution_topic_timeline(figure, counts),
        )

    with summary_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(("analysis", "period", "category", "visit_count"))
        writer.writerows(summary_rows)
    print(f"Wrote {len(records)} visits across {len(years)} years to {output_path}")
    print(f"Wrote time-series data to {summary_path}")


if __name__ == "__main__":
    main()
