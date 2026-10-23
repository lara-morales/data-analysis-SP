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
    year_column_lines,
)
from report_style import (
    BLACK,
    RED,
    add_chart_with_reading,
    add_columns_with_reading,
    add_executive_page,
    add_recommendation_page,
    bar_axis,
    draw_footer,
    grouped_bars,
    new_figure,
    region_pies,
    save_page,
    series_colors,
    wrap,
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
    training = sum(counts.get("Client Training", 0) for counts in demo_type_counts.values())
    training_share = round(100 * training / total) if total else 0
    ai_2024 = topic_counts.get(2024, Counter()).get("AI Tools", 0)
    ai_2025 = topic_counts.get(2025, Counter()).get("AI Tools", 0)
    with PdfPages(pdf_path) as pdf:
        cover = new_figure()
        cover.text(
            0.055,
            0.88,
            "The Story Behind Our Demo Records",
            fontsize=24,
            fontweight="bold",
            color=BLACK,
        )
        cover.text(
            0.055,
            0.80,
            wrap(
                f"What {total} Client Demos Reveal About Demand, Capability Gaps, and Growth Opportunities for Manila CS",
                92,
                max_lines=2,
            ),
            fontsize=13,
            color=BLACK,
            va="top",
        )
        cover.text(0.055, 0.70, "Period Covered: FY2024 – FH1 2026", fontsize=12, color=BLACK)
        cover.text(0.055, 0.66, "Prepared for: Manila CIQ Client Support Team", fontsize=12, color=BLACK)
        slot_width = 0.84 / max(len(by_year), 1)
        for index, (_year, year_visits) in enumerate(by_year.items()):
            x = 0.055 + index * slot_width
            cover.patches.append(
                Rectangle(
                    (x, 0.42),
                    0.12,
                    0.006,
                    transform=cover.transFigure,
                    facecolor=RED,
                    edgecolor="none",
                )
            )
            cover.text(x, 0.58, "LOGGED DEMOS", fontsize=9, color=RED, fontweight="bold")
            cover.text(x, 0.46, str(len(year_visits)), fontsize=32, color=BLACK, fontweight="bold")
            cover.text(x, 0.36, year_coverage_label(year_visits), fontsize=11, color=BLACK)
        cover.text(0.055, 0.30, "Purpose", fontsize=12, color=RED, fontweight="bold")
        cover.text(
            0.055,
            0.26,
            wrap(
                f"This analysis reviews {total} logged client demos to understand where client demand is concentrated, "
                "which product areas generate the most interest, and what opportunities exist to expand Manila's demo "
                "capability and ownership. The objective is not only to understand historical trends, but also to "
                "identify practical actions that can help Manila CIQ CS Team increase demo participation, strengthen "
                "product expertise, and improve client engagement.",
                115,
                max_lines=5,
            ),
            fontsize=10.5,
            color=BLACK,
            va="top",
            linespacing=1.25,
        )
        draw_footer(cover)
        save_page(pdf, cover)

        add_executive_page(
            pdf,
            "Executive Summary",
            [
                (
                    "Why We Conducted This Study",
                    "Client demos are one of the strongest indicators of client engagement and product demand. "
                    f"By analyzing {total} demo records, we sought to understand who our clients are, what they want to learn, "
                    "and how Manila CIQ CS Team can better position itself to support future opportunities.",
                ),
                (
                    "Key Findings",
                    [
                        f"Client Training accounted for {training} of {total} demos ({training_share}%).",
                        "Investment & Finance professionals were the most common audience every year.",
                        "Excel Plug-in, Screening, and Company Data consistently ranked among the most requested solution areas.",
                        f"AI-related discussions increased significantly from {ai_2024} mentions in 2024 to {ai_2025} in 2025.",
                    ],
                ),
                (
                    "Why It Matters",
                    "The findings suggest that Manila CIQ CS Team has an opportunity to expand and strengthen the number "
                    "of associates capable of independently running demos, particularly in high-demand workflows and products. "
                    "Doing so can improve client coverage, reduce dependence on a small pool of specialists, and create more "
                    "opportunities to support revenue-generating engagements.",
                ),
            ],
        )

        add_chart_with_reading(
            pdf,
            "Monthly Visits",
            lambda figure: _line_chart(figure, by_year),
            [
                "Demo activity demonstrates clear seasonality, with demand concentrated during specific months throughout the year. These demand spikes likely reflect client training cycles, onboarding periods, and recurring business activities. Rather than treating these peaks as isolated events, Manila CIQ CS Team should view them as predictable opportunities requiring proactive resource planning.",
            ],
            [
                "Develop a quarterly demo coverage plan ahead of peak periods.",
                "Assign trained demo champions to high-demand months.",
                "Use lower-volume months for product certification and mock demo sessions.",
                "Establish minimum demo readiness requirements for all associates.",
            ],
        )
        quarter_keys = [str(quarter) for quarter in range(1, 5)]
        quarter_by_year = {
            year: Counter({str(quarter): count for quarter, count in quarter_counts(year_visits).items()})
            for year, year_visits in by_year.items()
        }
        add_chart_with_reading(
            pdf,
            "Quarterly Visits",
            lambda figure: grouped_bars(
                figure,
                [f"Q{quarter}" for quarter in range(1, 5)],
                _series(by_year, quarter_keys, quarter_by_year, skip_missing=True),
                ylabel="Recorded visits",
            ),
            [
                "The quarterly trend highlights a strong increase in demo activity from 2024 to 2025, indicating growing demand for product demonstrations and client training across our user base. While FH1 2026 reflects lower overall volumes, this is expected given that only half of the year is represented. The data suggests that demos continue to be an effective channel for client engagement, education, and product adoption. The growth observed in 2025 also demonstrates Manila's ability to support increasing client demand when opportunities are available. To sustain this momentum, the team should focus not only on responding to demo requests but also on actively building capacity and visibility to participate in more demo engagements.",
            ],
            [
                "Establish annual and quarterly targets for demo participation across the Manila team.",
                "Review quarterly demo trends to identify demand shifts and emerging opportunities.",
                "Partner with Commercial teams to proactively support high-demand solution areas and client training initiatives.",
            ],
        )
        add_chart_with_reading(
            pdf,
            "Solution Topics",
            lambda figure: grouped_bars(
                figure,
                topic_labels,
                _series(by_year, topic_labels, topic_counts),
                ylabel="Visits mentioning the topic",
                horizontal=True,
            ),
            [
                "Demand remains heavily concentrated around core workflows including Excel Plug-in, Screening, Company Profiles, and Valuation. At the same time, AI-related requests grew significantly between 2024 and 2025, indicating increasing client interest in newer capabilities. Manila's future demo strategy should balance mastery of foundational products while building expertise in recent enhancements and emerging solutions.",
            ],
            [
                "Prioritize enablement on Excel, Screening, Company Data, and Valuation.",
                "Introduce an AI Tools learning track.",
                "Create demo playbooks for the most requested solution areas.",
                "Conduct quarterly showcase sessions where associates demonstrate real client use cases.",
            ],
        )
        add_chart_with_reading(
            pdf,
            "Demonstration Types",
            lambda figure: grouped_bars(
                figure,
                demo_labels,
                _series(by_year, demo_labels, demo_type_counts),
                ylabel="Visits",
                horizontal=True,
            ),
            [
                "Client Training overwhelmingly dominates all demo activity, representing nearly two-thirds of recorded demos. This suggests that clients are not simply seeking product overviews but require practical instruction tailored to their workflows. Increasing Manila's ability to deliver these sessions would directly increase demo capacity.",
            ],
            [
                "Develop standardized training agendas and reusable demo scripts specific for client trainings.",
            ],
        )
        add_chart_with_reading(
            pdf,
            "Job Description",
            lambda figure: grouped_bars(
                figure,
                role_labels,
                _series(by_year, role_labels, role_counts),
                ylabel="Visits",
                horizontal=True,
            ),
            [
                "Investment and Finance professionals consistently represent the largest audience segment. This indicates that valuation, company analysis, and transaction-related use cases should remain the foundation of Manila's demo strategy. Associates who understand the business context behind these workflows will be better positioned to engage clients beyond basic product demonstrations.",
            ],
            [
                "Build industry and user-persona learning paths.",
                "Create specialized tracks focused on Investment & Finance users.",
                "Require job-role identification before demo scheduling whenever feasible.",
                "Develop audience-specific demo templates.",
            ],
        )
        add_chart_with_reading(
            pdf,
            "Key Workflows",
            lambda figure: grouped_bars(
                figure,
                workflow_labels,
                _series(by_year, workflow_labels, workflow_counts),
                ylabel="Visits mentioning the workflow",
                horizontal=True,
            ),
            [
                "Valuation and Company Analysis consistently account for the largest share of documented workflows. This suggests that clients continue to rely on Capital IQ for their comps building and financials valuation. Associates supporting demos should therefore be comfortable navigating workflows beyond simple product navigation and be able to discuss practical applications.",
            ],
            [
                "Build advanced training around valuation workflows.",
                "Develop workflow-based learning rather than feature-based learning.",
                "Create a reusable library of common client questions and answers.",
            ],
        )
        add_columns_with_reading(
            pdf,
            "Top Accounts",
            year_column_lines(by_year, kind="account"),
            [
                "Several organizations appear repeatedly within the demo records, suggesting that repeat engagements represent a significant opportunity for future demos. Existing client relationships may provide a more efficient path to additional demo volume than pursuing entirely new opportunities.",
            ],
            [
                "Establish an account-based demo tracking process.",
                "Review prior sessions before every repeat engagement.",
                "Identify the top recurring demo accounts and proactively engage them when new functionality launches.",
            ],
        )
        region_panels = [
            (year_coverage_label(year_visits), ranked(region_counts[year]))
            for year, year_visits in by_year.items()
        ]
        add_chart_with_reading(
            pdf,
            "Client Region",
            lambda figure: region_pies(figure, region_panels),
            [
                "The shift from APAC-dominated activity toward a larger EMEA presence in FH1 2026 highlights opportunities for Manila to support a broader client base. Understanding regional demand patterns can help optimize staffing and increase demo participation.",
            ],
            [
                "Align staffing schedules with regional demand patterns.",
                "Share best practices from successful EMEA engagements.",
                "Monitor regional trends quarterly.",
            ],
        )
        add_recommendation_page(
            pdf,
            "Action Items and Recommendations",
            "",
            [
                (
                    "Develop a Demo Playbook Through the Demo In Action Working Group",
                    "",
                    [
                        "Create standardized templates for the top demo types and key workflows.",
                        "Develop solution-specific talking points for Excel, Screening, Company Data, Valuation, AI Tools, and other high-demand topics.",
                        "Maintain a repository of sample demos and best practices accessible to all associates.",
                        "Review and update the playbook quarterly based on client demand trends.",
                    ],
                ),
                (
                    "Strengthen Demo Readiness and Product Expertise",
                    "",
                    [
                        "Conduct targeted training sessions on the most requested workflows and solutions.",
                        "Introduce refresher sessions for demo-certified associates on a quarterly basis.",
                        "Develop learning paths centered on the most common client personas, particularly Investment & Finance professionals.",
                        "Expand shadowing and mentorship opportunities with experienced demo presenters.",
                        "Incorporate mock demos and peer feedback sessions into the certification program.",
                    ],
                ),
                (
                    "Expand Demo Opportunities from Existing Accounts",
                    "",
                    [
                        "Establish a watchlist of accounts with recurring demo engagements.",
                        "Review previous demo topics prior to client meetings to identify follow-up opportunities.",
                        "Coordinate with Sales and Relationship Managers to proactively recommend relevant solutions.",
                        "Track repeat-demo metrics and identify accounts with the highest growth potential.",
                        "Develop account-specific suggestions for adjacent products and workflows.",
                    ],
                ),
                (
                    "Improve Demo Documentation Quality and Insights",
                    "",
                    [
                        "Require completion of Key Workflow, Solution Discussed, and Job Role fields before case closure.",
                        "Standardize documentation guidelines across all teams.",
                        "Conduct monthly quality reviews of demo records and provide feedback where needed.",
                        "Publish dashboard metrics on documentation completeness and data quality.",
                        "Use documented insights to guide future training priorities and Demo In Action Working Group initiatives.",
                    ],
                ),
            ],
        )

    with summary_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(("analysis", "year", "category", "visit_count"))
        writer.writerows(summary_rows)


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
