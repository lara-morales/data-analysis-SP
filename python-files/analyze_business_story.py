"""Cross-year story PDF. Sentences and chart scales come from the loaded visits."""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from pathlib import Path

from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle

from narrative import (
    account_counts_by_year,
    action_items,
    account_year_callout,
    activity_story,
    demonstration_story,
    job_description_years_story,
    limits_implication,
    limits_story,
    method_implication,
    method_story,
    quarterly_story,
    region_story,
    region_watch_note_years,
    role_year_callout,
    solution_training_note_years,
    year_column_lines,
    workflow_story,
)
from report_style import (
    BLACK,
    RED,
    add_action_page,
    add_year_columns_page,
    add_text_page,
    bar_axis,
    draw_footer,
    grouped_bars,
    new_figure,
    region_pies,
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
    topic_labels = _theme_categories(by_year, "solution_topics", 8, skip_residual=False)
    workflow_labels = _theme_categories(by_year, "workflows", 5, skip_residual=True)
    demo_labels = _theme_categories(by_year, "demonstration_type", 5, skip_residual=False)
    role_counts = {year: count_labels(year_visits, "role") for year, year_visits in by_year.items()}
    role_labels = _theme_categories(by_year, "role", 8, skip_residual=False)
    account_by_year = account_counts_by_year(by_year)

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
        for label, count in ranked(role_counts[year]):
            summary_rows.append(("Client role", str(year), label, count))
        for label, count in ranked(account_by_year[year]):
            summary_rows.append(("Account", str(year), label, count))

    total = len(visits)
    with PdfPages(pdf_path) as pdf:
        cover = new_figure()
        cover.text(
            0.055,
            0.86,
            f"What {total} logged demos tell Manila",
            fontsize=26,
            fontweight="bold",
            color=BLACK,
        )
        cover.text(
            0.055,
            0.76,
            "Where to add associate capacity, what to product-train, and which accounts can book the next demo.",
            fontsize=12,
            color=BLACK,
        )
        slot_width = 0.84 / max(len(by_year), 1)
        for index, (_year, year_visits) in enumerate(by_year.items()):
            x = 0.055 + index * slot_width
            cover.patches.append(
                Rectangle(
                    (x, 0.40),
                    0.12,
                    0.008,
                    transform=cover.transFigure,
                    facecolor=RED,
                    edgecolor="none",
                )
            )
            cover.text(x, 0.62, "LOGGED DEMOS", fontsize=9, color=RED, fontweight="bold")
            cover.text(x, 0.48, str(len(year_visits)), fontsize=36, color=BLACK, fontweight="bold")
            cover.text(x, 0.34, year_coverage_label(year_visits), fontsize=12, color=BLACK)
        cover.text(
            0.055,
            0.22,
            "Set the next demo target on the months every year contains. FH1 2026 is January–June, so it is not a full year of lost demand.",
            fontsize=12,
            color=BLACK,
        )
        cover.text(
            0.055,
            0.14,
            "Each row is one logged demo. A repeat account is the fastest way to add the next one.",
            fontsize=12,
            color=BLACK,
        )
        draw_footer(cover)
        save_page(pdf, cover)

        add_chart_page = _chart_page(pdf)
        add_chart_page(
            "Monthly visits — when to roster associates for demos",
            activity_story(by_year),
            lambda figure: _line_chart(figure, by_year),
            note="Roster more associates in the months the line is high. That is when clients are requesting demos. Use the lighter months to train the bench on the workflows and solutions those demos require.",
        )
        quarter_keys = [str(quarter) for quarter in range(1, 5)]
        quarter_by_year = {
            year: Counter({str(quarter): count for quarter, count in quarter_counts(year_visits).items()})
            for year, year_visits in by_year.items()
        }
        add_chart_page(
            "Quarterly visits — where demo capacity is already tight",
            quarterly_story(by_year),
            lambda figure: grouped_bars(
                figure,
                [f"Q{quarter}" for quarter in range(1, 5)],
                _series(by_year, quarter_keys, quarter_by_year, skip_missing=True),
                ylabel="Recorded visits",
            ),
            note="Put the bench on the heavy quarter, when demo requests are already booked. Use the lighter quarter to train associates on the workflows and solutions they will need when the next heavy quarter arrives.",
        )
        add_chart_page(
            "Solution topics — modules to put in product training",
            "The eight solution topics clients ask to see most often, including AI Tools. One visit can match more than one topic.",
            lambda figure: grouped_bars(
                figure,
                topic_labels,
                _series(by_year, topic_labels, topic_counts),
                ylabel="Visits mentioning the topic",
                horizontal=True,
            ),
            note=solution_training_note_years(by_year),
        )
        add_chart_page(
            "Key workflows — the product path to rehearse before the call",
            workflow_story(by_year),
            lambda figure: grouped_bars(
                figure,
                workflow_labels,
                _series(by_year, workflow_labels, workflow_counts),
                ylabel="Visits mentioning the workflow",
                horizontal=True,
            ),
            note="Walk associates through valuation and company analysis, and through M&A, including the questions clients usually ask. They can then show the solution in the demo instead of stopping to find a specialist.",
        )
        add_chart_page(
            "Demonstration type — the session associates must be ready to run",
            demonstration_story(by_year),
            lambda figure: grouped_bars(
                figure,
                demo_labels,
                _series(by_year, demo_labels, demo_type_counts),
                ylabel="Visits",
                horizontal=True,
            ),
            note="Client Training is the session these clients book. Train associates to run it against the client’s workflow, so they can anticipate the questions and show the solution in the same demo.",
        )
        add_chart_page(
            "Job description — who will be in the room",
            job_description_years_story(by_year),
            lambda figure: grouped_bars(
                figure,
                role_labels,
                _series(by_year, role_labels, role_counts),
                ylabel="Visits",
                horizontal=True,
            ),
            note="Train associates on the demonstration types these roles book, so they know the client’s workflow and can anticipate the queries and the solutions to show. Investment and finance is that room in every year.",
        )
        add_year_columns_page(
            pdf,
            "Top visit roles — who the associate will meet",
            "The three roles with the most logged demos in each year. Unspecified and Other are visits without a usable job title.",
            year_column_lines(by_year, kind="role"),
            role_year_callout(by_year),
        )
        add_year_columns_page(
            pdf,
            "Top accounts — where the next demo can come from",
            "The three named accounts with the most logged demos in each year.",
            year_column_lines(by_year, kind="account"),
            account_year_callout(by_year),
        )
        region_panels = [
            (year_coverage_label(year_visits), ranked(region_counts[year]))
            for year, year_visits in by_year.items()
        ]
        add_chart_page(
            "Client region — where to aim demo coverage",
            region_story(by_year),
            lambda figure: region_pies(figure, region_panels),
            note=region_watch_note_years(by_year),
        )
        add_text_page(
            pdf,
            "How Manila should use these records",
            [
                ("What the files cover", limits_story(by_year)),
                ("What a demo target can use", limits_implication()),
                ("How the themes were read", method_story()),
                ("How to act on a chart", method_implication()),
            ],
        )
        add_action_page(
            pdf,
            action_items(visits, by_year=by_year),
            (
                f"What Manila can do with these {total} logged demos to take more of the requests that come in."
            ),
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
