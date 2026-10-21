"""PDF report for one set of cleaned Manila visits.

The charts read the derived columns in the cleaned CSV. They do not apply a
second, different set of rules.
"""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from pathlib import Path

from matplotlib.figure import Figure

from report_style import (
    INK,
    SERIES,
    add_chart_page,
    add_text_page,
    bar_axis,
    horizontal_bars,
)
from visit_model import (
    Visit,
    count_labels,
    load_cleaned_csv,
    month_span,
    percent,
    quarter_counts,
    ranked,
    year_coverage_label,
)


def _summary(analysis: str, counts: Counter[str] | list[tuple[str, int]]) -> list[tuple[str, str, int]]:
    pairs = counts.most_common() if isinstance(counts, Counter) else counts
    return [(analysis, label, count) for label, count in pairs]


def _top(counts: Counter[str], limit: int, *, skip_residual: bool = False) -> list[tuple[str, int]]:
    ordered = ranked(counts, skip_residual=skip_residual)
    if len(ordered) <= limit:
        return ordered
    head = ordered[:limit]
    rest = sum(count for _label, count in ordered[limit:])
    return head + [(f"Other ({len(ordered) - limit} more)", rest)]


def _vertical(figure: Figure, labels: list[str], values: list[int], ylabel: str) -> None:
    axis = bar_axis(figure, (0.08, 0.16, 0.86, 0.66))
    if not labels:
        axis.axis("off")
        axis.text(0.5, 0.5, "No dated visits", ha="center", color="#4F5D6B")
        return
    axis.bar(labels, values, color=SERIES[0])
    axis.set_ylabel(ylabel)
    axis.tick_params(axis="x", rotation=55, labelsize=8)
    for index, value in enumerate(values):
        axis.text(index, value, str(value), ha="center", va="bottom", fontsize=7, color=INK)
    axis.margins(y=0.15)


def write_visit_report(visits: list[Visit], pdf_path: Path, summary_path: Path) -> None:
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    if not visits:
        raise ValueError(f"No dated visits to report for {pdf_path.name}.")

    dates = [visit.visit_date for visit in visits]
    span = month_span(date.month for date in dates)
    coverage = year_coverage_label(visits) if len({date.year for date in dates}) == 1 else (
        f"{min(dates):%b %Y}–{max(dates):%b %Y}"
    )
    sources = sorted({visit.source_file for visit in visits if visit.source_file})
    source_name = ", ".join(sources) if sources else "cleaned visit file"

    monthly: Counter[str] = Counter(visit.visit_date.strftime("%Y-%m") for visit in visits)
    months = sorted(monthly)
    quarterly = quarter_counts(visits)
    quarter_labels = [f"Q{quarter}" for quarter in sorted(quarterly)]
    countries = count_labels(visits, "country")
    regions = count_labels(visits, "region")
    demo_types = count_labels(visits, "demonstration_type")
    demo_categories = count_labels(visits, "demonstration_categories")
    roles = count_labels(visits, "role")
    workflows = count_labels(visits, "workflows")
    topics = count_labels(visits, "solution_topics")
    challenges = count_labels(visits, "challenges")
    products: Counter[str] = Counter()
    for visit in visits:
        products.update(visit.products)

    no_workflow = sum(1 for visit in visits if not ranked(Counter(visit.workflows), skip_residual=True))
    no_solution = sum(1 for visit in visits if visit.solution_note_status != "Categorized")
    no_challenge = sum(1 for visit in visits if not visit.challenge_recorded)
    uncategorized_challenges = sum(
        1 for visit in visits if visit.challenge_recorded and not visit.challenges
    )
    blank_country = sum(1 for visit in visits if visit.country == "Unspecified")

    summary_rows: list[tuple[str, str, int]] = [("Dated visits", coverage, len(visits))]
    summary_rows.extend(_summary("Monthly visits", [(month, monthly[month]) for month in months]))
    summary_rows.extend(
        _summary("Quarterly visits", [(f"Q{quarter}", quarterly[quarter]) for quarter in sorted(quarterly)])
    )
    summary_rows.extend(_summary("Country", ranked(countries)))
    summary_rows.extend(_summary("Region", ranked(regions)))
    summary_rows.extend(_summary("Demonstration type", ranked(demo_types)))
    summary_rows.extend(_summary("Demonstration category", ranked(demo_categories)))
    summary_rows.extend(_summary("Client role", ranked(roles)))
    summary_rows.extend(_summary("Workflow", ranked(workflows)))
    summary_rows.extend(_summary("Solution topic", ranked(topics)))
    summary_rows.extend(
        _summary(
            "Uncategorized solution note",
            [
                (visit.solution_note[:120], 1)
                for visit in visits
                if visit.solution_note_status == "Uncategorized" and visit.solution_note
            ],
        )
    )
    summary_rows.extend(_summary("Challenge", ranked(challenges)))
    summary_rows.extend(_summary("Product", ranked(products)))

    from matplotlib.backends.backend_pdf import PdfPages

    with PdfPages(pdf_path) as pdf:
        add_text_page(
            pdf,
            f"Manila visits, {coverage}",
            [
                (
                    "What is in this file",
                    (
                        f"{len(visits)} dated visits from {min(dates):%b %d, %Y} to {max(dates):%b %d, %Y} "
                        f"({span}). Source: {source_name}. One row is one logged visit. "
                        "Repeat accounts are counted once per visit, not collapsed to one client."
                    ),
                ),
                (
                    "Fields that were blank",
                    (
                        f"{no_workflow} visits have no classified workflow. "
                        f"{no_solution} visits have no classified solution topic. "
                        f"{no_challenge} visits have no challenge note, and "
                        f"{uncategorized_challenges} challenge notes matched no theme. "
                        f"{blank_country} visits have no country. "
                        "Those rows stay in the visit total and are omitted from the theme charts."
                    ),
                ),
                (
                    "How to read the charts",
                    (
                        "Demonstration type, country, region, role, and product charts count each visit once. "
                        "Workflow, solution, challenge, and demonstration-category charts can count a visit "
                        "in more than one bar. The companion CSV lists every category, including notes that "
                        "matched no rule."
                    ),
                ),
            ],
        )
        add_chart_page(
            pdf,
            "Monthly visits",
            "Months with no visits are omitted. They are not shown as zero.",
            lambda figure: _vertical(figure, months, [monthly[month] for month in months], "Visits"),
        )
        add_chart_page(
            pdf,
            "Quarterly visits",
            "Quarters with no visits are omitted. A partial year will not show later quarters.",
            lambda figure: _vertical(
                figure,
                quarter_labels,
                [quarterly[int(label[1])] for label in quarter_labels],
                "Visits",
            ),
        )
        type_chart = _top(demo_types, 12)
        add_chart_page(
            pdf,
            "Demonstration type",
            "Exact Demonstration Type values. Combined selections are kept as written and are not split.",
            lambda figure: horizontal_bars(
                figure,
                [label for label, _count in type_chart],
                [count for _label, count in type_chart],
                xlabel="Visits",
            ),
        )
        category_chart = ranked(demo_categories)
        add_chart_page(
            pdf,
            "Demonstration category",
            "Regex groups of Demonstration Type. A visit with two types is counted in both bars, so the bars can add up to more than the visit total.",
            lambda figure: horizontal_bars(
                figure,
                [label for label, _count in category_chart],
                [count for _label, count in category_chart],
                xlabel="Visits matching the category",
            ),
        )
        add_chart_page(
            pdf,
            "Client region",
            "Country is mapped to APAC, EMEA, or Americas. Blank or unmapped countries are Unspecified. "
            + (
                "Unmapped country names are in the summary under Country."
                if any(visit.region == "Unspecified" and visit.country != "Unspecified" for visit in visits)
                else f"Blank country: {blank_country} visits."
            ),
            lambda figure: horizontal_bars(
                figure,
                [label for label, _count in ranked(regions)],
                [count for _label, count in ranked(regions)],
                xlabel="Visits",
            ),
        )
        country_chart = _top(countries, 12)
        add_chart_page(
            pdf,
            "Client country",
            f"Top countries by visits. {blank_country} visits have no country and are labeled Unspecified. The summary lists every country.",
            lambda figure: horizontal_bars(
                figure,
                [label for label, _count in country_chart],
                [count for _label, count in country_chart],
                xlabel="Visits",
            ),
        )
        add_chart_page(
            pdf,
            "Client role",
            "Taken only from Team/User Job Description. Other means the note did not match a role rule. Unspecified means the field was blank. "
            f"Other is {roles.get('Other', 0)} ({percent(roles.get('Other', 0), len(visits))}) and Unspecified is {roles.get('Unspecified', 0)} ({percent(roles.get('Unspecified', 0), len(visits))}).",
            lambda figure: horizontal_bars(
                figure,
                [label for label, _count in ranked(roles)],
                [count for _label, count in ranked(roles)],
                xlabel="Visits",
            ),
        )
        workflow_chart = ranked(workflows, skip_residual=True)[:10]
        add_chart_page(
            pdf,
            "Key workflows",
            f"Classified from Key Workflows, or from Meeting Notes when that field is empty. {no_workflow} of {len(visits)} visits have no classified workflow and are not in the bars. A visit can appear in more than one bar.",
            lambda figure: horizontal_bars(
                figure,
                [label for label, _count in workflow_chart],
                [count for _label, count in workflow_chart],
                xlabel="Visits mentioning the workflow",
            ),
        )
        topic_chart = ranked(topics)[:12]
        add_chart_page(
            pdf,
            "Solution topics",
            f"Classified from Solutions Discussed only. {no_solution} of {len(visits)} visits have no classified topic. A visit can match several topics, so the bars are not a split of 100%.",
            lambda figure: horizontal_bars(
                figure,
                [label for label, _count in topic_chart],
                [count for _label, count in topic_chart],
                xlabel="Visits mentioning the topic",
            ),
        )
        challenge_chart = ranked(challenges)[:10]
        add_chart_page(
            pdf,
            "Workflow challenges",
            f"{no_challenge} of {len(visits)} visits have no challenge note. {uncategorized_challenges} notes matched no theme. The bars count only matched themes, and one note can match more than one theme.",
            lambda figure: horizontal_bars(
                figure,
                [label for label, _count in challenge_chart],
                [count for _label, count in challenge_chart],
                xlabel="Visits mentioning the challenge",
            ),
        )
        product_chart = _top(products, 10)
        add_chart_page(
            pdf,
            "Products discussed",
            "Each product named in Products Discussed is counted once per visit. A visit that names two products is in both bars.",
            lambda figure: horizontal_bars(
                figure,
                [label for label, _count in product_chart],
                [count for _label, count in product_chart],
                xlabel="Visits naming the product",
            ),
        )

    with summary_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(("analysis", "category", "visit_count"))
        writer.writerows(summary_rows)


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Create a PDF analysis for one cleaned visit file.")
    parser.add_argument("--input", type=Path, required=True, help="Cleaned visit CSV.")
    parser.add_argument("--output", type=Path, required=True, help="PDF path.")
    parser.add_argument("--summary", type=Path, required=True, help="Summary CSV path.")
    args = parser.parse_args()

    def resolve(path: Path) -> Path:
        return path if path.is_absolute() else project_root / path

    visits, skipped = load_cleaned_csv(resolve(args.input))
    for message in skipped:
        print(message)
    write_visit_report(visits, resolve(args.output), resolve(args.summary))
    print(f"Wrote {len(visits)} visits to {resolve(args.output)}")


if __name__ == "__main__":
    main()
