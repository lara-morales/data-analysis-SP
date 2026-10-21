"""Build report sentences from visit counts.

The wording is derived from the files being rendered. Partial years, ties, and
months with no records are described from those counts rather than fixed text.
"""

from __future__ import annotations

from collections import Counter

from visit_model import (
    Visit,
    comparable_months,
    count_labels,
    format_leaders,
    leaders,
    month_counts,
    month_span,
    percent,
    quarter_counts,
    ranked,
    year_coverage_label,
)


def _years(by_year: dict[int, list[Visit]]) -> list[int]:
    return sorted(by_year)


def coverage_clause(by_year: dict[int, list[Visit]]) -> str:
    parts = []
    for year, visits in by_year.items():
        span = month_span(visit.visit_date.month for visit in visits)
        parts.append(f"{len(visits)} in {year} ({span})")
    if not parts:
        return "The files contain no dated visits."
    return "Dated visits are " + "; ".join(parts) + "."


def window_counts(by_year: dict[int, list[Visit]]) -> tuple[list[int], dict[int, int]]:
    window = comparable_months(by_year)
    totals = {
        year: sum(1 for visit in visits if visit.visit_date.month in window)
        for year, visits in by_year.items()
    }
    return window, totals


def front_loaded_years(by_year: dict[int, list[Visit]]) -> dict[int, tuple[int, int, int]]:
    """Years that have both halves and put at least 75% of visits in January–June."""
    found: dict[int, tuple[int, int, int]] = {}
    for year, visits in by_year.items():
        counts = month_counts(visits)
        if not any(month <= 6 for month in counts) or not any(month >= 7 for month in counts):
            continue
        first_half = sum(count for month, count in counts.items() if month <= 6)
        second_half = sum(count for month, count in counts.items() if month >= 7)
        total = first_half + second_half
        if total and first_half / total >= 0.75:
            found[year] = (first_half, second_half, total)
    return found


def activity_story(by_year: dict[int, list[Visit]]) -> str:
    return coverage_clause(by_year) + " Each line is one year, and a month with no visits in that year is not drawn."


def activity_implication(by_year: dict[int, list[Visit]]) -> str:
    window, totals = window_counts(by_year)
    if not window:
        return (
            "These files do not share a calendar month. Year totals are shown separately "
            "and are not ranked as like-for-like demand."
        )
    window_bits = "; ".join(f"{year}: {totals[year]}" for year in _years(by_year))
    sentences = [
        f"The months present in every year are {month_span(window)}.",
        f"Recorded visits in that window are {window_bits}.",
        "Months that are absent from a file are omitted, not plotted as zero.",
    ]
    for year, (first_half, second_half, total) in front_loaded_years(by_year).items():
        sentences.append(
            f"{year} is front-loaded: {first_half} of {total} visits ({percent(first_half, total)}) "
            f"fall in January–June, and {second_half} fall in July–December."
        )
    partial = [
        year
        for year, visits in by_year.items()
        if month_span(visit.visit_date.month for visit in visits) != "January–December"
    ]
    if partial:
        labels = ", ".join(year_coverage_label(by_year[year]) for year in partial)
        verb = "is" if len(partial) == 1 else "are"
        sentences.append(f"{labels} {verb} not a full-year total.")
    return " ".join(sentences)


def quarterly_story(by_year: dict[int, list[Visit]]) -> str:
    parts = []
    for year, visits in by_year.items():
        counts = quarter_counts(visits)
        detail = ", ".join(f"Q{quarter} {counts[quarter]}" for quarter in sorted(counts))
        parts.append(f"{year}: {detail}")
    return "Recorded visits by quarter are " + "; ".join(parts) + "."


def quarterly_implication(by_year: dict[int, list[Visit]]) -> str:
    sentences = []
    for year, visits in by_year.items():
        counts = quarter_counts(visits)
        missing = [quarter for quarter in (1, 2, 3, 4) if quarter not in counts]
        if missing:
            listed = ", ".join(f"Q{quarter}" for quarter in missing)
            sentences.append(f"{year} has no records in {listed}, so those quarters are omitted.")
        if 1 in counts and 3 in counts and 4 in counts:
            later = counts[3] + counts[4]
            if counts[1] > later:
                sentences.append(
                    f"{year} Q1 ({counts[1]}) is larger than Q3 and Q4 combined ({later})."
                )
    if not sentences:
        sentences.append("Every listed quarter is limited to months that contain at least one visit.")
    sentences.append("A change in logged quarters is not, by itself, a change in client demand.")
    return " ".join(sentences)


def _topic_counts(by_year: dict[int, list[Visit]]) -> dict[int, Counter[str]]:
    return {year: count_labels(visits, "solution_topics") for year, visits in by_year.items()}


def solution_story(by_year: dict[int, list[Visit]]) -> str:
    parts = []
    for year, visits in by_year.items():
        top = leaders(_topic_counts(by_year)[year])
        parts.append(f"{year}: {format_leaders(top)}")
    unclassified = {
        year: sum(1 for visit in visits if visit.solution_note_status == "Uncategorized")
        for year, visits in by_year.items()
    }
    extra = ""
    if any(unclassified.values()):
        bits = ", ".join(f"{count} in {year}" for year, count in unclassified.items() if count)
        extra = f" Notes that matched no topic: {bits}."
    return (
        "The most mentioned solution topic in each year was "
        + "; ".join(parts)
        + ". One visit can match several topics."
        + extra
    )


def solution_implication(by_year: dict[int, list[Visit]]) -> str:
    if not by_year:
        return "No dated visits were available."
    return (
        "A visit can match several topics, so the bars overlap and are not a split of 100%. "
        "The summary CSV lists every topic, including notes that matched none."
    )


def _substantive_workflows(visits: list[Visit]) -> Counter[str]:
    counts = count_labels(visits, "workflows")
    return Counter(dict(ranked(counts, skip_residual=True)))


def workflow_story(by_year: dict[int, list[Visit]]) -> str:
    parts = []
    for year, visits in by_year.items():
        parts.append(f"{year}: {format_leaders(leaders(_substantive_workflows(visits)))}")
    return (
        "Among visits with a classified workflow, the leading theme was "
        + "; ".join(parts)
        + ". Job titles are not used to assign the workflow."
    )


def workflow_implication(by_year: dict[int, list[Visit]]) -> str:
    parts = []
    for year, visits in by_year.items():
        classified = sum(1 for visit in visits if _substantive_workflows([visit]))
        parts.append(f"{year}: {classified} of {len(visits)} visits have a classified workflow, {len(visits) - classified} do not")
    return (
        "Workflow text is Key Workflows, or Meeting Notes only when Key Workflows is empty. "
        + "; ".join(parts)
        + ". Categories can overlap."
    )


def demonstration_story(by_year: dict[int, list[Visit]]) -> str:
    parts = []
    for year, visits in by_year.items():
        counts = count_labels(visits, "demonstration_type")
        parts.append(f"{year}: {format_leaders(leaders(counts))}")
    return (
        "The chart uses the original Demonstration Type text, including combined selections. "
        "The most frequent selection was " + "; ".join(parts) + "."
    )


def demonstration_implication(by_year: dict[int, list[Visit]]) -> str:
    totals = {year: len(visits) for year, visits in by_year.items()}
    counts = {year: count_labels(visits, "demonstration_type") for year, visits in by_year.items()}
    top_overall = leaders(Counter({
        label: sum(year_counts[label] for year_counts in counts.values())
        for label in {label for year_counts in counts.values() for label in year_counts}
    }))
    if not top_overall:
        return "No demonstration type was recorded."
    label = top_overall[0][0]
    shares = ", ".join(
        f"{percent(counts[year][label], totals[year])} of {year}" for year in _years(by_year)
    )
    return (
        f"'{label}' accounts for {shares}. "
        "Combined selections such as 'Client Training; New User Training' stay as their own value. "
        "The summary lists every selection; the chart shows the five most frequent."
    )


def region_story(by_year: dict[int, list[Visit]]) -> str:
    parts = []
    for year, visits in by_year.items():
        counts = count_labels(visits, "region")
        top = leaders(counts)
        share = percent(top[0][1], len(visits)) if top else "n/a"
        parts.append(f"{year}: {format_leaders(top)} of {len(visits)} ({share})")
    unmapped = sorted({
        visit.country
        for visits in by_year.values()
        for visit in visits
        if visit.region == "Unspecified" and visit.country != "Unspecified"
    })
    mapping = (
        f" Countries with no region mapping: {', '.join(unmapped)}."
        if unmapped
        else " Blank countries are Unspecified and are not assigned to a region."
    )
    return "The leading region was " + "; ".join(parts) + "." + mapping


def region_implication(by_year: dict[int, list[Visit]]) -> str:
    parts = []
    for year, visits in by_year.items():
        counts = count_labels(visits, "region")
        detail = ", ".join(
            f"{label} {percent(count, len(visits))}" for label, count in ranked(counts)
        )
        parts.append(f"{year_coverage_label(visits)}: {detail}")
    return (
        "Percentages use each year's dated visits as the denominator. "
        + ". ".join(parts)
        + ". This is where logged visits were recorded, not regional market size."
    )


def limits_story(by_year: dict[int, list[Visit]]) -> str:
    total = sum(len(visits) for visits in by_year.values())
    bits = ", ".join(f"{len(visits)} in {year_coverage_label(visits)}" for visits in by_year.values())
    return (
        f"These files contain {total} dated visits ({bits}). "
        "A row is one logged visit, not one unique client. "
        "The export has no prospect list, invitation count, or booking outcome."
    )


def limits_implication() -> str:
    return (
        "The report can describe when visits were logged and which topics, workflows, "
        "and session types were written down. It cannot say how many demos were missed, "
        "why a year is higher or lower, or which outreach would increase bookings. "
        "Those questions need pipeline and attendance data in addition to visit reports."
    )


def method_story() -> str:
    return (
        "Solution topics come only from Solutions Discussed. Workflows come from Key Workflows, "
        "or from Meeting Notes when Key Workflows is blank. Roles come from Team/User Job Description. "
        "Demonstration type is the source value; demonstration category is a regex grouping of that value. "
        "Challenges come from Workflow Challenges and Consequences of living without Solution."
    )


def method_implication() -> str:
    return (
        "A visit counts once per matched topic, workflow, or challenge, and may appear in more than one. "
        "Rules are regular expressions, so a new phrasing stays in the summary as uncategorized until a rule is added. "
        "Counts are not revenue, satisfaction, or evidence that a session caused adoption."
    )
