"""PDF report for one set of cleaned Manila visits.

The charts read the derived columns in the cleaned CSV. They do not apply a
second, different set of rules.
"""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from datetime import datetime
from pathlib import Path

from matplotlib.figure import Figure

from narrative import (
    account_concentration_note,
    account_concentration_story,
    account_counts,
    action_items,
    concentration_callout,
    concentration_lines,
    job_description_note,
    job_description_story,
    named_account_ranking,
    region_watch_note,
    role_ranking,
    solution_training_note,
)
from report_style import (
    INK,
    SERIES,
    add_action_page,
    add_chart_page,
    add_concentration_page,
    add_text_page,
    bar_axis,
    horizontal_bars,
    region_pies,
)
from visit_model import (
    Visit,
    count_labels,
    leaders,
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
    axis = bar_axis(figure)
    if not labels:
        axis.axis("off")
        axis.text(0.5, 0.5, "No dated visits", ha="center", color="#4F5D6B")
        return
    axis.bar(labels, values, color=SERIES[0])
    axis.set_ylabel(ylabel)
    axis.tick_params(axis="x", labelsize=9)
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
    accounts = account_counts(visits)

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
    summary_rows.extend(_summary("Account", ranked(accounts)))
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
                        "Workflow, solution, and challenge charts can count a visit in more than one bar. "
                        "The companion CSV lists every category."
                    ),
                ),
                (
                    "How Manila can use this file",
                    (
                        "Staff the months clients already request a demo, train associates on the modules "
                        "on the solution page, including AI Tools, and send someone back to accounts that "
                        "have already booked."
                    ),
                ),
            ],
        )
        month_axis = [datetime.strptime(month, "%Y-%m").strftime("%b") for month in months]
        peak_month, peak_month_count = max(monthly.items(), key=lambda item: (item[1], item[0]))
        peak_quarter, peak_quarter_count = max(quarterly.items(), key=lambda item: (item[1], item[0]))
        add_chart_page(
            pdf,
            "Monthly visits — when to roster more associates",
            f"Each column is a month with at least one logged demo. The busiest month is {peak_month} ({peak_month_count} visits, {percent(peak_month_count, len(visits))}). A missing month was not in this file.",
            lambda figure: _vertical(figure, month_axis, [monthly[month] for month in months], "Visits"),
            note="Put more associates on the peak month. That is when demo requests are already coming in.",
        )
        add_chart_page(
            pdf,
            "Quarterly visits — where demo capacity is already tight",
            f"Q{peak_quarter} is the heaviest quarter in this file ({peak_quarter_count} visits, {percent(peak_quarter_count, len(visits))}). Quarters with no visits are omitted.",
            lambda figure: _vertical(
                figure,
                quarter_labels,
                [quarterly[int(label[1])] for label in quarter_labels],
                "Visits",
            ),
            note="Cover the heavy quarter first. That is where the demo requests are.",
        )
        type_chart = _top(demo_types, 8)
        type_lead = leaders(demo_types)
        type_label, type_count = type_lead[0]
        add_chart_page(
            pdf,
            "Demonstration type — the session associates must be ready to run",
            "Each bar is the Demonstration Type written on the visit. Combined selections stay as their own bar.",
            lambda figure: horizontal_bars(
                figure,
                [label for label, _count in type_chart],
                [count for _label, count in type_chart],
                xlabel="Visits",
            ),
            note=(
                f"'{type_label}' is {type_count} of {len(visits)} visits ({percent(type_count, len(visits))}). "
                "More associates who can run that session means more demo requests the team can accept."
            ),
        )
        region_lead = leaders(regions)
        region_label, region_count = region_lead[0]
        region_pairs = ranked(regions)
        add_chart_page(
            pdf,
            "Client region — where to aim demo coverage",
            f"Each slice is the share of logged demos. {region_label} is {region_count} of {len(visits)} visits ({percent(region_count, len(visits))}). Blank country: {blank_country}.",
            lambda figure: region_pies(figure, [(coverage, region_pairs)]),
            note=region_watch_note(region_pairs),
        )
        country_chart = _top(countries, 8)
        country_label, country_count = country_chart[0]
        add_chart_page(
            pdf,
            "Client country — which local examples to prepare",
            f"Top countries by logged demos. {blank_country} visits have no country. The summary lists every country.",
            lambda figure: horizontal_bars(
                figure,
                [label for label, _count in country_chart],
                [count for _label, count in country_chart],
                xlabel="Visits",
            ),
            note=(
                f"{country_label} is the most common country ({country_count} visits, {percent(country_count, len(visits))}). "
                "Use a local example from these countries so the client can see the next step and book again."
            ),
        )
        add_chart_page(
            pdf,
            "Client Profile: Job Description — who the associate will meet",
            job_description_story(visits),
            lambda figure: horizontal_bars(
                figure,
                [label for label, _count in ranked(roles)],
                [count for _label, count in ranked(roles)],
                xlabel="Visits",
            ),
            note=job_description_note(visits),
        )
        add_concentration_page(
            pdf,
            "Account concentration — relationships that can add the next demo",
            account_concentration_story(visits),
            "Top visit roles",
            concentration_lines(role_ranking(visits), "visits"),
            job_description_note(visits),
            "Top accounts",
            concentration_lines(named_account_ranking(visits), "visits"),
            account_concentration_note(visits),
            concentration_callout(visits),
        )
        workflow_chart = ranked(workflows, skip_residual=True)[:8]
        workflow_lead = leaders(Counter(dict(workflow_chart))) if workflow_chart else []
        add_chart_page(
            pdf,
            "Key workflows — the product path to train before the call",
            f"Taken from Key Workflows, or Meeting Notes only when that field is empty. {no_workflow} of {len(visits)} visits have no classified workflow. One visit can appear in more than one bar.",
            lambda figure: horizontal_bars(
                figure,
                [label for label, _count in workflow_chart],
                [count for _label, count in workflow_chart],
                xlabel="Visits mentioning the workflow",
            ),
            note=(
                (
                    f"Start the demo on {workflow_lead[0][0]} ({workflow_lead[0][1]} visits). "
                    if workflow_lead
                    else "No workflow was classified. "
                )
                + "Associates who can run that path can take the demo. Fill the blank workflow notes so the follow-up can be picked up."
            ),
        )
        topic_chart = [(label, count) for label, count in ranked(topics) if count]
        add_chart_page(
            pdf,
            "Solution topics — modules to put in the standard demo",
            f"Every solution topic in Solutions Discussed, including AI Tools and the other datasets. {no_solution} of {len(visits)} visits have no classified topic. One visit can match several topics.",
            lambda figure: horizontal_bars(
                figure,
                [label for label, _count in topic_chart],
                [count for _label, count in topic_chart],
                xlabel="Visits mentioning the topic",
            ),
            note=solution_training_note(visits),
        )
        challenge_chart = ranked(challenges)[:8]
        add_chart_page(
            pdf,
            "Workflow challenges — what the associate should be ready to answer",
            f"{no_challenge} of {len(visits)} visits have no challenge note. {uncategorized_challenges} notes matched no theme. One note can match more than one theme.",
            lambda figure: horizontal_bars(
                figure,
                [label for label, _count in challenge_chart],
                [count for _label, count in challenge_chart],
                xlabel="Visits mentioning the challenge",
            ),
            note=(
                (
                    f"The most common matched barrier is {challenge_chart[0][0]} ({challenge_chart[0][1]} visits). "
                    if challenge_chart
                    else "No challenge theme was matched. "
                )
                + "An associate who can answer that in the room is more likely to be asked back for another demo."
            ),
        )
        product_chart = _top(products, 8)
        add_chart_page(
            pdf,
            "Products discussed — the desktop associates should know cold",
            "Each product is counted once per visit. A visit that names two products is in both bars.",
            lambda figure: horizontal_bars(
                figure,
                [label for label, _count in product_chart],
                [count for _label, count in product_chart],
                xlabel="Visits naming the product",
            ),
            note=(
                (
                    f"{product_chart[0][0]} is named on {product_chart[0][1]} visits. "
                    if product_chart
                    else "No product was named. "
                )
                + "Associates who can open the demo on that product can take the request."
            ),
        )
        add_action_page(
            pdf,
            action_items(visits),
            (
                f"What Manila can do with the {len(visits)} demos in {coverage} to take more of the requests that come in."
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
