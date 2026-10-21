"""Create an executive narrative PDF from the combined Manila visit datasets."""

from __future__ import annotations

import argparse
import csv
import textwrap
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Callable

import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

from analyze_visits import COUNTRY_REGIONS, clean
from solution_categories import is_non_solution_entry, solution_topic_categories


YEAR_INPUTS = {
    2024: "raw-2024_cleaned.csv",
    2025: "2025-manila-visit_raw-final_cleaned.csv",
    2026: "raw-1h2026_cleaned.csv",
}
COLORS = {2024: "#1C7C8C", 2025: "#465A8B", 2026: "#E08E45"}


@dataclass(frozen=True)
class StoryVisit:
    visit_date: date
    country: str
    region: str
    demonstration_type: str
    demonstration_categories: frozenset[str]
    workflows: frozenset[str]
    solution_topics: frozenset[str]
    role: str


def split_categories(value: str | None) -> frozenset[str]:
    """Split a semicolon-delimited derived category field into unique labels."""
    return frozenset(part.strip() for part in (value or "").split(";") if part.strip())


def load_story_visits(input_paths: dict[int, Path]) -> dict[int, list[StoryVisit]]:
    """Load the three year datasets while keeping each visit assigned by source year."""
    datasets: dict[int, list[StoryVisit]] = {}
    for year, input_path in input_paths.items():
        year_visits: list[StoryVisit] = []
        with input_path.open(encoding="utf-8-sig", newline="") as handle:
            for line_number, row in enumerate(csv.DictReader(handle), start=2):
                date_text = (row.get("Visit Date Clean") or "").strip()
                try:
                    visit_date = datetime.strptime(date_text, "%Y-%m-%d").date()
                except ValueError as error:
                    raise ValueError(
                        f"Invalid or missing Visit Date Clean in {input_path} at CSV line "
                        f"{line_number}: {date_text!r}"
                    ) from error
                if visit_date.year != year:
                    raise ValueError(
                        f"Expected {year} data in {input_path}, found {visit_date.year} "
                        f"at CSV line {line_number}."
                    )

                solution_text = row.get("Solutions Discussed") or ""
                country = clean(row.get("Country")) or "Unspecified"
                topics = (
                    frozenset()
                    if is_non_solution_entry(solution_text)
                    else frozenset(solution_topic_categories(solution_text))
                )
                year_visits.append(
                    StoryVisit(
                        visit_date=visit_date,
                        country=country,
                        region=COUNTRY_REGIONS.get(country, "Unspecified"),
                        demonstration_type=clean(row.get("Demonstration Type"))
                        or "Unspecified",
                        demonstration_categories=split_categories(
                            row.get("Demonstration Category")
                        ),
                        workflows=split_categories(row.get("Workflow Categories")),
                        solution_topics=topics,
                        role=(row.get("Client Role Category") or "Unspecified").strip(),
                    )
                )
        if not year_visits:
            raise ValueError(f"No visit records were found in {input_path}.")
        datasets[year] = year_visits
    return datasets


def yearly_counts(
    datasets: dict[int, list[StoryVisit]],
    attribute: str,
) -> dict[int, Counter[str]]:
    """Count a multi-label or single-label visit attribute by year."""
    results: dict[int, Counter[str]] = {}
    for year, visits in datasets.items():
        counts: Counter[str] = Counter()
        for visit in visits:
            value = getattr(visit, attribute)
            labels = value if isinstance(value, frozenset) else (value,)
            counts.update(labels)
        results[year] = counts
    return results


def yearly_month_counts(
    datasets: dict[int, list[StoryVisit]],
) -> dict[int, Counter[int]]:
    return {
        year: Counter(visit.visit_date.month for visit in visits)
        for year, visits in datasets.items()
    }


def yearly_quarter_counts(
    datasets: dict[int, list[StoryVisit]],
) -> dict[int, Counter[int]]:
    return {
        year: Counter((visit.visit_date.month - 1) // 3 + 1 for visit in visits)
        for year, visits in datasets.items()
    }


def top_demonstration_type_labels(
    demo_type_counts: dict[int, Counter[str]],
    limit: int = 5,
) -> list[str]:
    totals: Counter[str] = Counter()
    for counts in demo_type_counts.values():
        totals.update(counts)
    return [label for label, _ in totals.most_common(limit)]


def add_page(
    pdf: PdfPages,
    title: str,
    story: str,
    implication: str,
    chart: Callable[[plt.Figure], None] | None = None,
) -> None:
    figure = plt.figure(figsize=(11.69, 8.27))
    figure.text(0.07, 0.95, title, fontsize=18, fontweight="bold", color="#17324D")
    wrapped_story = textwrap.fill(story, width=142)
    story_lines = wrapped_story.count("\n") + 1
    figure.text(
        0.07,
        0.895,
        wrapped_story,
        fontsize=9.5,
        color="#374151",
        va="top",
        linespacing=1.2,
    )
    if chart is not None:
        chart(figure)
        chart_top = min(0.79, 0.895 - story_lines * 0.022 - 0.045)
        for axis in figure.axes:
            position = axis.get_position()
            bottom = 0.35
            axis.set_position(
                (position.x0, bottom, position.width, max(0.31, chart_top - bottom))
            )
    wrapped_interpretation = textwrap.fill(implication, width=150)
    figure.text(
        0.07,
        0.19,
        "WHAT THIS MEANS",
        fontsize=8.5,
        fontweight="bold",
        color="#1C7C8C",
    )
    figure.text(
        0.07,
        0.16,
        wrapped_interpretation,
        fontsize=8.2,
        color="#4F5D6B",
        va="top",
        linespacing=1.15,
    )
    figure.text(
        0.07,
        0.025,
        "Source: FY2024, FY2025, and FH12026 Visit Reports.",
        fontsize=7.5,
        color="#6B7280",
    )
    pdf.savefig(figure, bbox_inches="tight")
    plt.close(figure)


def plot_monthly_recording(figure: plt.Figure, month_counts: dict[int, Counter[int]]) -> None:
    axis = figure.add_axes((0.10, 0.28, 0.82, 0.52))
    month_positions = list(range(1, 13))
    for year, counts in sorted(month_counts.items()):
        months = [month for month in month_positions if counts.get(month, 0)]
        axis.plot(
            months,
            [counts[month] for month in months],
            marker="o",
            linewidth=2,
            color=COLORS[year],
            label=str(year),
        )
    axis.set_xticks(month_positions, [date(2000, month, 1).strftime("%b") for month in month_positions])
    axis.set_ylabel("Recorded visits")
    axis.set_title("Monthly recorded visits by dataset year")
    axis.grid(alpha=0.25)
    axis.set_axisbelow(True)
    axis.legend(title="Dataset year", loc="upper right")
    axis.annotate(
        "Sharp reduction in recorded\n2025 visits after May",
        xy=(6, month_counts[2025][6]),
        xytext=(7.2, max(month_counts[2025].values()) * 0.7),
        arrowprops={"arrowstyle": "->", "color": "#465A8B"},
        fontsize=8,
        color="#465A8B",
    )
    axis.annotate(
        "2026 H1 ends in June",
        xy=(6, month_counts[2026][6]),
        xytext=(7.4, max(month_counts[2024].values()) * 0.45),
        arrowprops={"arrowstyle": "->", "color": "#E08E45"},
        fontsize=8,
        color="#9A5B22",
    )
    label_offsets = {2024: 7, 2025: -9, 2026: 12}
    for year, counts in sorted(month_counts.items()):
        for month in month_positions:
            if counts.get(month, 0):
                axis.annotate(
                    str(counts[month]),
                    (month, counts[month]),
                    textcoords="offset points",
                    xytext=(0, label_offsets[year]),
                    ha="center",
                    fontsize=6.5,
                    color=COLORS[year],
                )


def plot_quarterly_visits(
    figure: plt.Figure,
    quarter_counts: dict[int, Counter[int]],
) -> None:
    axis = figure.add_axes((0.12, 0.28, 0.78, 0.52))
    positions = range(1, 5)
    width = 0.24
    for offset, (year, counts) in enumerate(sorted(quarter_counts.items())):
        quarters = [quarter for quarter in positions if quarter in counts]
        bars = axis.bar(
            [quarter + (offset - 1) * width for quarter in quarters],
            [counts[quarter] for quarter in quarters],
            width=width,
            color=COLORS[year],
            label=str(year),
        )
        axis.bar_label(bars, labels=[str(counts[q]) for q in quarters], padding=2, fontsize=7)
    axis.set_xticks(list(positions), [f"Q{quarter}" for quarter in positions])
    axis.set_ylabel("Recorded visits")
    axis.set_title("Quarterly recorded visits (unobserved quarters omitted)")
    axis.grid(axis="y", alpha=0.25)
    axis.set_axisbelow(True)
    axis.legend(title="Dataset year")
    axis.margins(y=0.16)
    axis.text(
        0.99,
        0.96,
        "2026 data ends in Q2",
        transform=axis.transAxes,
        ha="right",
        va="top",
        fontsize=8,
        color="#6B7280",
    )


def plot_region_mix(
    figure: plt.Figure,
    region_counts: dict[int, Counter[str]],
    visit_totals: dict[int, int],
) -> None:
    regions = ["APAC", "EMEA", "Americas", "Unspecified"]
    axis = figure.add_axes((0.16, 0.28, 0.74, 0.52))
    positions = list(range(len(regions)))
    width = 0.24
    for offset, (year, counts) in enumerate(sorted(region_counts.items())):
        bars = axis.bar(
            [position + (offset - 1) * width for position in positions],
            [counts.get(region, 0) / visit_totals[year] * 100 for region in regions],
            width=width,
            color=COLORS[year],
            label=str(year),
        )
        percentages = [
            counts.get(region, 0) / visit_totals[year] * 100 for region in regions
        ]
        axis.bar_label(
            bars,
            labels=[f"{value:.0f}%" if value else "" for value in percentages],
            padding=2,
            fontsize=6.5,
        )
    axis.set_xticks(positions, regions)
    axis.set_ylabel("Share of recorded visits (%)")
    axis.set_title("Regional mix of recorded visits")
    axis.grid(axis="y", alpha=0.25)
    axis.set_axisbelow(True)
    axis.legend(title="Dataset year")
    axis.margins(y=0.16)


def plot_yearly_topic_comparison(
    figure: plt.Figure,
    topic_counts: dict[int, Counter[str]],
) -> list[str]:
    totals: Counter[str] = Counter()
    for counts in topic_counts.values():
        totals.update(counts)
    topics = [topic for topic, _ in totals.most_common(7)]
    axis = figure.add_axes((0.24, 0.27, 0.68, 0.53))
    positions = list(range(len(topics)))
    width = 0.24
    for offset, (year, counts) in enumerate(sorted(topic_counts.items())):
        values = [counts.get(topic, 0) for topic in topics]
        bars = axis.bar(
            [position + (offset - 1) * width for position in positions],
            values,
            width=width,
            color=COLORS[year],
            label=str(year),
        )
        axis.bar_label(
            bars,
            labels=[str(value) if value else "" for value in values],
            padding=2,
            fontsize=6.5,
        )
    axis.set_xticks(positions, topics, rotation=25, ha="right")
    axis.set_ylabel("Visits mentioning topic")
    axis.set_title("Most frequently discussed solution topics")
    axis.grid(axis="y", alpha=0.25)
    axis.set_axisbelow(True)
    axis.legend(title="Dataset year")
    axis.margins(y=0.16)
    return topics


def plot_workflow_comparison(
    figure: plt.Figure,
    workflow_counts: dict[int, Counter[str]],
) -> None:
    totals: Counter[str] = Counter()
    for counts in workflow_counts.values():
        totals.update(counts)
    workflows = [workflow for workflow, _ in totals.most_common(6)]
    axis = figure.add_axes((0.28, 0.27, 0.63, 0.53))
    positions = list(range(len(workflows)))
    width = 0.24
    for offset, (year, counts) in enumerate(sorted(workflow_counts.items())):
        values = [counts.get(workflow, 0) for workflow in workflows]
        bars = axis.bar(
            [position + (offset - 1) * width for position in positions],
            values,
            width=width,
            color=COLORS[year],
            label=str(year),
        )
        axis.bar_label(
            bars,
            labels=[str(value) if value else "" for value in values],
            padding=2,
            fontsize=6.5,
        )
    axis.set_xticks(positions, workflows, rotation=25, ha="right")
    axis.set_ylabel("Visits mentioning workflow")
    axis.set_title("Client jobs most often represented in visit notes")
    axis.grid(axis="y", alpha=0.25)
    axis.set_axisbelow(True)
    axis.legend(title="Dataset year")
    axis.margins(y=0.16)


def plot_demonstration_mix(
    figure: plt.Figure,
    demo_type_counts: dict[int, Counter[str]],
) -> None:
    labels = top_demonstration_type_labels(demo_type_counts)
    axis = figure.add_axes((0.31, 0.28, 0.59, 0.52))
    positions = list(range(len(labels)))
    height = 0.24
    for offset, (year, counts) in enumerate(sorted(demo_type_counts.items())):
        values = [counts.get(label, 0) for label in labels]
        bars = axis.barh(
            [position + (offset - 1) * height for position in positions],
            values,
            height=height,
            color=COLORS[year],
            label=str(year),
        )
        axis.bar_label(
            bars,
            labels=[str(value) if value else "" for value in values],
            padding=2,
            fontsize=6.5,
        )
    axis.set_yticks(positions, labels, fontsize=8)
    axis.invert_yaxis()
    axis.set_xlabel("Visits")
    axis.set_title("Most frequent original Demonstration Type selections")
    axis.grid(axis="x", alpha=0.25)
    axis.set_axisbelow(True)
    axis.legend(title="Dataset year")
    axis.text(
        0.99,
        -0.15,
        "Top 5 exact source selections; combined values remain intact.",
        transform=axis.transAxes,
        ha="right",
        va="top",
        fontsize=7.5,
        color="#6B7280",
    )
    axis.margins(x=0.14)


def build_summary_rows(
    datasets: dict[int, list[StoryVisit]],
    topic_counts: dict[int, Counter[str]],
    workflow_counts: dict[int, Counter[str]],
    demo_counts: dict[int, Counter[str]],
    month_counts: dict[int, Counter[int]],
    quarter_counts: dict[int, Counter[int]],
    region_counts: dict[int, Counter[str]],
) -> list[tuple[str, str, str, int]]:
    rows: list[tuple[str, str, str, int]] = []
    for year, visits in sorted(datasets.items()):
        rows.append(("Yearly visits", str(year), "All visits", len(visits)))
        rows.extend(
            ("Monthly visits", f"{year}-{month:02d}", "All visits", count)
            for month, count in sorted(month_counts[year].items())
        )
        rows.extend(
            ("Quarterly visits", f"{year} Q{quarter}", "All visits", count)
            for quarter, count in sorted(quarter_counts[year].items())
        )
        rows.extend(
            ("Region visits", str(year), region, count)
            for region, count in region_counts[year].most_common()
        )
        rows.extend(
            ("Solution topic", str(year), topic, count)
            for topic, count in topic_counts[year].most_common()
        )
        rows.extend(
            ("Workflow", str(year), workflow, count)
            for workflow, count in workflow_counts[year].most_common()
        )
        rows.extend(
            ("Demonstration category", str(year), label, count)
            for label, count in demo_counts[year].most_common()
        )
        type_counts = Counter(visit.demonstration_type for visit in visits)
        rows.extend(
            ("Demonstration type", str(year), label, count)
            for label, count in type_counts.most_common()
        )
    return rows


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(
        description="Create a business-storytelling report from 2024–2026 Manila visits."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=project_root
        / "output"
        / "manila_visit_business_story_2024_2026_storytelling_v4.pdf",
    )
    parser.add_argument(
        "--summary",
        type=Path,
        default=project_root
        / "output"
        / "manila_visit_business_story_2024_2026_storytelling_v4_summary.csv",
    )
    args = parser.parse_args()
    output_path = args.output if args.output.is_absolute() else project_root / args.output
    summary_path = args.summary if args.summary.is_absolute() else project_root / args.summary
    output_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)

    input_paths = {
        year: project_root / "cleaned_data" / filename
        for year, filename in YEAR_INPUTS.items()
    }
    datasets = load_story_visits(input_paths)
    visit_totals = {year: len(visits) for year, visits in datasets.items()}
    topic_counts = yearly_counts(datasets, "solution_topics")
    workflow_counts = yearly_counts(datasets, "workflows")
    demo_counts = yearly_counts(datasets, "demonstration_categories")
    demo_type_counts = yearly_counts(datasets, "demonstration_type")
    country_counts = yearly_counts(datasets, "country")
    region_counts = yearly_counts(datasets, "region")
    role_counts = yearly_counts(datasets, "role")
    month_counts = yearly_month_counts(datasets)
    quarter_counts = yearly_quarter_counts(datasets)
    summary_rows = build_summary_rows(
        datasets,
        topic_counts,
        workflow_counts,
        demo_counts,
        month_counts,
        quarter_counts,
        region_counts,
    )

    h1_totals = {
        year: sum(count for month, count in month_counts[year].items() if month <= 6)
        for year in datasets
    }
    h1_share = h1_totals[2025] / visit_totals[2025]
    h1_2026_share = h1_totals[2026] / visit_totals[2026]
    overall_visit_total = sum(visit_totals.values())
    top_solution = {
        year: topic_counts[year].most_common(1)[0]
        for year in datasets
        if topic_counts[year]
    }
    top_workflow = {
        year: workflow_counts[year].most_common(1)[0]
        for year in datasets
        if workflow_counts[year]
    }
    latest_focus = ", ".join(
        f"{topic} ({count})" for topic, count in topic_counts[2026].most_common(3)
    )
    first_half_2024 = sum(
        month_counts[2024].get(month, 0) for month in range(1, 7)
    )
    top_demo_type = top_demonstration_type_labels(demo_type_counts)[0]
    top_demo_type_counts = {
        year: demo_type_counts[year].get(top_demo_type, 0) for year in datasets
    }
    top_demo_type_shares = {
        year: top_demo_type_counts[year] / visit_totals[year] for year in datasets
    }
    screening_shares = {
        year: topic_counts[year].get("Screening", 0) / visit_totals[year]
        for year in datasets
    }
    excel_shares = {
        year: topic_counts[year].get("Excel and Office Tools", 0) / visit_totals[year]
        for year in datasets
    }

    with PdfPages(output_path) as pdf:
        cover = plt.figure(figsize=(11.69, 8.27))
        cover.patch.set_facecolor("#F4F7F8")
        cover.text(0.08, 0.84, "MANILA CLIENT VISITS", fontsize=12, fontweight="bold", color="#1C7C8C")
        cover.text(
            0.08,
            0.72,
            "What 576 visit records reveal\nabout Manila's demo activity",
            fontsize=26,
            fontweight="bold",
            color="#17324D",
            linespacing=1.25,
        )
        cover.text(
            0.08,
            0.52,
            "2024–2026 H1 | Activity, session types, workflows, and regional mix",
            fontsize=12,
            color="#4F5D6B",
        )
        cover.text(0.08, 0.39, "RECORDED VISITS", fontsize=9, color="#4F5D6B")
        cover.text(0.08, 0.30, f"{visit_totals[2024]}", fontsize=27, color="#1C7C8C", fontweight="bold")
        cover.text(0.08, 0.25, "FY2024", fontsize=10, color="#4F5D6B")
        cover.text(0.38, 0.39, "RECORDED VISITS", fontsize=9, color="#4F5D6B")
        cover.text(0.38, 0.30, f"{visit_totals[2025]}", fontsize=27, color="#465A8B", fontweight="bold")
        cover.text(0.38, 0.25, "FY2025", fontsize=10, color="#4F5D6B")
        cover.text(0.68, 0.39, "RECORDED VISITS", fontsize=9, color="#4F5D6B")
        cover.text(0.68, 0.30, f"{visit_totals[2026]}", fontsize=27, color="#E08E45", fontweight="bold")
        cover.text(0.68, 0.25, "FH12026 (Jan–Jun)", fontsize=10, color="#4F5D6B")
        cover.text(
            0.08,
            0.15,
            f"{top_demo_type} is the most frequent exact Demonstration Type selection "
            f"({top_demo_type_counts[2024]} in 2024; {top_demo_type_counts[2025]} in 2025; "
            f"{top_demo_type_counts[2026]} in 2026 H1).",
            fontsize=10,
            color="#17324D",
        )
        cover.text(
            0.08,
            0.105,
            "Interpret recorded activity with caution: later-period volumes and partial-year coverage "
            "limit direct demand comparisons.",
            fontsize=9,
            color="#4F5D6B",
        )
        cover.text(
            0.08,
            0.06,
            "Source: FY2024, FY2025, and FH12026 Visit Reports.",
            fontsize=8,
            color="#6B7280",
        )
        pdf.savefig(cover, bbox_inches="tight")
        plt.close(cover)

        add_page(
            pdf,
            "1. Read the activity curve before reading the demand story",
            (
                f"The dataset contains {visit_totals[2024]} visits in 2024, "
                f"{visit_totals[2025]} in 2025, and {visit_totals[2026]} in 2026 H1. "
                f"However, {h1_totals[2025]} of the 2025 records ({h1_share:.0%}) fall in "
                f"January–June, and {h1_totals[2026]} of 2026 H1 records ({h1_2026_share:.0%}) "
                "fall in January–June by definition. There are only "
                f"{visit_totals[2025] - h1_totals[2025]} records in July–December 2025 and "
                f"{visit_totals[2026] - sum(count for month, count in month_counts[2026].items() if month <= 4)} "
                "in May–June 2026."
            ),
            (
                f"The 2025 file is strongly front-loaded: {h1_totals[2025]} of "
                f"{visit_totals[2025]} records ({h1_share:.0%}) are from January–June, "
                f"compared with {first_half_2024} of {visit_totals[2024]} in the same 2024 period "
                f"({first_half_2024 / visit_totals[2024]:.0%}); it leaves "
                f"{visit_totals[2025] - h1_totals[2025]} in July–December. In 2026, "
                f"{visit_totals[2026] - h1_totals[2026]} records fall in May–June. "
                f"The 2025 H1 count is {h1_totals[2025] - first_half_2024} higher than 2024 H1, "
                "even though the 2025 full-year "
                f"count is lower by {(visit_totals[2024] - visit_totals[2025]) / visit_totals[2024]:.0%}. "
                "This reversal shows why full-year totals alone can mislead when activity is "
                "concentrated in different reporting periods."
            ),
            lambda figure: plot_monthly_recording(figure, month_counts),
        )

        add_page(
            pdf,
            "2. Quarterly cadence shows both opportunity and a coverage gap",
            (
                f"Recorded visits by quarter were 2024: "
                f"{', '.join(f'Q{q} {quarter_counts[2024][q]}' for q in sorted(quarter_counts[2024]))}; "
                f"2025: {', '.join(f'Q{q} {quarter_counts[2025][q]}' for q in sorted(quarter_counts[2025]))}; "
                f"and 2026 H1: {', '.join(f'Q{q} {quarter_counts[2026][q]}' for q in sorted(quarter_counts[2026]))}. "
                "The sharp 2025 second-half drop and the unavailable 2026 second half limit demand comparisons."
            ),
            (
                f"2024 peaks in Q4 ({quarter_counts[2024][4]} visits). In 2025, Q1 and Q2 "
                f"account for {quarter_counts[2025][1] + quarter_counts[2025][2]} of "
                f"{visit_totals[2025]} records, while Q3 and Q4 total "
                f"{quarter_counts[2025][3] + quarter_counts[2025][4]}. The 2026 comparison "
                f"covers Q1–Q2 only ({quarter_counts[2026][1] + quarter_counts[2026][2]} visits). "
                f"2025 Q1 alone ({quarter_counts[2025][1]}) exceeds its Q3–Q4 combined count "
                f"({quarter_counts[2025][3] + quarter_counts[2025][4]}) by "
                f"{quarter_counts[2025][1] - quarter_counts[2025][3] - quarter_counts[2025][4]}. "
                "This is a material shift in the timing of logged sessions, not evidence by itself "
                "of a matching change in underlying client interest."
            ),
            lambda figure: plot_quarterly_visits(figure, quarter_counts),
        )

        add_page(
            pdf,
            "3. Practical tool use is the common thread",
            (
                f"The most-mentioned solution topic was {top_solution[2024][0]} in 2024 "
                f"({top_solution[2024][1]} visits) and {top_solution[2025][0]} in 2025 "
                f"({top_solution[2025][1]}). In 2026 H1, {top_solution[2026][0]} leads "
                f"({top_solution[2026][1]}), followed by {latest_focus.split(', ', 1)[1] if ', ' in latest_focus else latest_focus}."
            ),
            (
                f"Excel and Office Tools leads in 2024 ({topic_counts[2024]['Excel and Office Tools']} "
                f"visits; {excel_shares[2024]:.0%} of visits) "
                f"and 2025 ({topic_counts[2025]['Excel and Office Tools']}; "
                f"{excel_shares[2025]:.0%}). Screening "
                f"leads 2026 H1 ({topic_counts[2026]['Screening']}; "
                f"{screening_shares[2026]:.0%}). Screening mentions rise from "
                f"{screening_shares[2024]:.0%} of 2024 records to {screening_shares[2025]:.0%} "
                f"in 2025 and {screening_shares[2026]:.0%} in 2026 H1. These are "
                "overlapping topic mentions in visit notes, not exclusive groups or demand estimates."
            ),
            lambda figure: plot_yearly_topic_comparison(figure, topic_counts),
        )

        add_page(
            pdf,
            "4. The work customers bring is broader than product navigation",
            (
                f"{top_workflow[2024][0]} is the leading recorded workflow in 2024 "
                f"({top_workflow[2024][1]} visits), 2025 ({top_workflow[2025][1]}), "
                f"and 2026 H1 ({top_workflow[2026][1]}). Valuation/company analysis and "
                "M&A/transactions are recurring use cases; Excel workflows are also prominent."
            ),
            (
                f"Valuation and Company Analysis appears in {workflow_counts[2024]['Valuation and Company Analysis']} "
                f"2024 visits ({workflow_counts[2024]['Valuation and Company Analysis'] / visit_totals[2024]:.0%}), "
                f"{workflow_counts[2025]['Valuation and Company Analysis']} 2025 visits "
                f"({workflow_counts[2025]['Valuation and Company Analysis'] / visit_totals[2025]:.0%}), "
                f"and {workflow_counts[2026]['Valuation and Company Analysis']} 2026 H1 visits "
                f"({workflow_counts[2026]['Valuation and Company Analysis'] / visit_totals[2026]:.0%}). "
                "Its position as the top workflow is consistent, though its share of the dataset "
                "falls from about one-half in 2024–2025 to two-fifths in 2026 H1. M&A/transactions "
                f"is another recurring job ({workflow_counts[2024]['M&A and Transactions']}, "
                f"{workflow_counts[2025]['M&A and Transactions']}, and "
                f"{workflow_counts[2026]['M&A and Transactions']} mentions, respectively). "
                "Workflow categories can overlap and 'Unspecified' is substantial, especially "
                f"in 2026 ({workflow_counts[2026]['Unspecified']} of {visit_totals[2026]} records)."
            ),
            lambda figure: plot_workflow_comparison(figure, workflow_counts),
        )

        add_page(
            pdf,
            "5. Training remains the dominant engagement format",
            (
                "The chart uses the original Demonstration Type field, preserving each selected "
                "value exactly—including combined selections such as "
                "'Client Training; New User Training'. No derived training/demo categories are "
                "used here. The most frequent source selection is "
                + "; ".join(
                    f"{year}: {demo_type_counts[year].most_common(1)[0][0]} "
                    f"({demo_type_counts[year].most_common(1)[0][1]} visits)"
                    for year in datasets
                )
                + "."
            ),
            (
                "The exact values show client training and new-user training as distinct selections, "
                "with some visits carrying both. These counts describe the source selection for a "
                "visit and retain combined values as their own selections; they are not recategorized "
                "into derived demonstration groups. The exact 'Client Training' selection accounts "
                f"for {top_demo_type_shares[2024]:.0%} of 2024 records, "
                f"{top_demo_type_shares[2025]:.0%} of 2025 records, and "
                f"{top_demo_type_shares[2026]:.0%} of 2026 H1 records. The top-five chart is a "
                "concise view; the summary CSV retains all selections."
            ),
            lambda figure: plot_demonstration_mix(figure, demo_type_counts),
        )

        countries_by_year = {year: country_counts[year].most_common(3) for year in datasets}
        role_unknown_shares = {
            year: (
                role_counts[year].get("Other", 0) + role_counts[year].get("Unspecified", 0)
            )
            / visit_totals[year]
            for year in datasets
        }
        add_page(
            pdf,
            "6. Regional mix shifts, while core jobs persist",
            (
                "The leading recorded region is "
                + "; ".join(
                    f"{year}: {region_counts[year].most_common(1)[0][0]} "
                    f"({region_counts[year].most_common(1)[0][1]} of {visit_totals[year]} visits, "
                    f"{region_counts[year].most_common(1)[0][1] / visit_totals[year]:.0%})"
                    for year in datasets
                )
                + ". Country mix also varies: "
                + "; ".join(
                    f"{year}: {', '.join(f'{country} ({count})' for country, count in top)}"
                    for year, top in countries_by_year.items()
                )
                + ". Client-role classification also leaves substantial records in Other or Unspecified, "
                "so audience comparisons are less reliable than solution/workflow comparisons. "
                + "; ".join(
                    f"{year}: {role_unknown_shares[year]:.0%} Other/Unspecified"
                    for year in datasets
                )
                + "."
            ),
            (
                f"APAC's share moves from {region_counts[2024]['APAC'] / visit_totals[2024]:.0%} "
                f"in 2024 to {region_counts[2025]['APAC'] / visit_totals[2025]:.0%} in 2025 and "
                f"{region_counts[2026]['APAC'] / visit_totals[2026]:.0%} in 2026 H1, while EMEA "
                f"moves from {region_counts[2024]['EMEA'] / visit_totals[2024]:.0%} to "
                f"{region_counts[2025]['EMEA'] / visit_totals[2025]:.0%} and then "
                f"{region_counts[2026]['EMEA'] / visit_totals[2026]:.0%}. The region percentages use each year's "
                "total recorded visits as the denominator. "
                "They indicate where records were concentrated in each dataset, not regional market "
                "size or conversion. The 2026 EMEA majority is limited to H1 and should not be read "
                "as a full-year or permanent regional shift."
            ),
            lambda figure: plot_region_mix(figure, region_counts, visit_totals),
        )

        add_page(
            pdf,
            "7. What recorded demo volume can tell us",
            (
                f"The three source periods contain {overall_visit_total} recorded visits: "
                f"{visit_totals[2024]} in 2024, {visit_totals[2025]} in 2025, and "
                f"{visit_totals[2026]} in 2026 H1. Visit records capture sessions that were logged; "
                "they do not contain a prospect denominator or acquisition-channel attribution."
            ),
            (
                "The report can describe the mix and timing of completed, recorded sessions, "
                "including recurring topics and workflows. It cannot determine how many potential "
                "demos were missed, what caused year-to-year changes, or which outreach activity "
                "would increase bookings. Those questions require pipeline, invitation, booking, "
                "and attendance data in addition to visit reports."
            ),
        )

        add_page(
            pdf,
            "Method and interpretation",
            (
                "This report combines the cleaned 2024 and 2025 datasets with 2026 H1. "
                "Solution topics are assigned with the shared deterministic regex rules. "
                "A visit is counted once per matched topic; one visit may match multiple topics. "
                "Workflow and demonstration categories are the derived labels already present "
                "in the cleaned datasets."
            ),
            (
                "Counts describe visit records, not unique customers. Multi-label topic and workflow "
                "counts can overlap. The dataset does not measure revenue, conversion, satisfaction, "
                "or whether a session caused subsequent product adoption."
            ),
        )

    with summary_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(("analysis", "year", "category", "visit_count"))
        writer.writerows(summary_rows)
    print(f"Wrote business story for {overall_visit_total} visits to {output_path}")
    print(f"Wrote supporting counts to {summary_path}")


if __name__ == "__main__":
    main()
