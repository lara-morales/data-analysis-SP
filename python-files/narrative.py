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
    sentences.append(
        "Manila should roster associates to the heavy months and set the demo target on the shared window, not on a missing half-year."
    )
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
    sentences.append(
        "Staff associate capacity to the heavy quarter, and do not set a demo target against a quarter this file does not contain."
    )
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
    parts = []
    for year, visits in by_year.items():
        top = leaders(_topic_counts(by_year)[year])
        if not top:
            continue
        label, count = top[0]
        parts.append(f"{year}: {label} is {percent(count, len(visits))} of visits")
    lead = ". ".join(parts)
    return (
        f"{lead}. Train associates on the leading topic first so they can run that module without a specialist in the room. "
        "The next topics can sit in the same demo. One visit can match several topics, so the bars are not a split of 100%."
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
        "Product training should follow the leading workflow, because that is the job the client brings to the demo. "
        + "; ".join(parts)
        + ". A visit can match more than one workflow."
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
        "Give every associate a product-training path for that session before they take a live demo. "
        "Keep enhancement and subscription calls on a separate checklist so they do not use the same script."
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


_REGION_HOURS = {
    "APAC": "APAC shares Manila's business day, so take those training requests the same day.",
    "EMEA": "EMEA morning arrives in the Manila afternoon, so watch the queue after lunch for those training requests.",
    "Americas": "Americas morning arrives in the Manila evening, so keep a later slot when those training requests come in.",
}


def region_watch_note(pairs: list[tuple[str, int]]) -> str:
    """How Manila should cover training requests from the regions in this file."""
    present = [(label, count) for label, count in pairs if count and label != "Unspecified"]
    if not present:
        return "Country is blank on these visits, so the time zone of the training request is not known."
    sentences = [_REGION_HOURS[label] for label, _count in present[:3] if label in _REGION_HOURS]
    return " ".join(sentences)


def region_watch_note_years(by_year: dict[int, list[Visit]]) -> str:
    """Name the shift in where training requests are coming from."""
    leads: list[tuple[int, str]] = []
    for year, visits in by_year.items():
        present = [
            (label, count)
            for label, count in ranked(count_labels(visits, "region"))
            if count and label != "Unspecified"
        ]
        if present:
            leads.append((year, present[0][0]))
    if not leads:
        return "Country is blank on these visits, so the time zone of the training request is not known."
    groups: list[tuple[list[int], str]] = []
    for year, region in leads:
        if groups and groups[-1][1] == region:
            groups[-1][0].append(year)
        else:
            groups.append(([year], region))
    bits = []
    for years, region in groups:
        label = ", ".join(year_coverage_label(by_year[year]) for year in years)
        bits.append(f"{label}: {region}")
    closing = _REGION_HOURS.get(leads[-1][1], "")
    return f"Where the requests came from — {'; '.join(bits)}. {closing}"


def solution_training_note(visits: list[Visit]) -> str:
    counts = count_labels(visits, "solution_topics")
    ordered = [(label, count) for label, count in ranked(counts) if count]
    if not ordered:
        return "No solution topic was written down, so the team cannot yet see which module to train."
    lead, lead_count = ordered[0]
    ai = counts.get("AI Tools", 0)
    return (
        f"Train associates on {lead} first ({lead_count} visits). "
        f"AI Tools is in {ai} visits, so include it with the other datasets on this page. "
        "Associates who can show these modules can take the next demo request."
    )


def solution_training_note_years(by_year: dict[int, list[Visit]]) -> str:
    bits = []
    for year, visits in by_year.items():
        count = count_labels(visits, "solution_topics").get("AI Tools", 0)
        bits.append(f"{year}: {count}")
    return (
        "Train associates on these modules, starting with Excel, Screening, and company data, and include AI Tools "
        f"({'; '.join(bits)}). When the client’s workflow calls for transactions, peer comps, dashboards, or news, "
        "the associate should be able to open that solution in the same demo."
    )


def region_implication(by_year: dict[int, list[Visit]]) -> str:
    parts = []
    for year, visits in by_year.items():
        counts = count_labels(visits, "region")
        detail = ", ".join(
            f"{label} {percent(count, len(visits))}" for label, count in ranked(counts)
        )
        parts.append(f"{year_coverage_label(visits)}: {detail}")
    return (
        "Each pie is that year's mix of logged demos. "
        + ". ".join(parts)
        + ". Brief associates with examples from the largest slice so the demo feels local, and do not read the slice as market size."
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
        "Roster associates to the heavy months and product-train them on the leading session type. "
        "A lower total is not, by itself, lost demand, because these files do not show declined demos. "
        "Compare FH1 2026 only with the same months in earlier years when setting the next demo target."
    )


def method_story() -> str:
    return (
        "Solution topics come only from Solutions Discussed. Workflows come from Key Workflows, "
        "or from Meeting Notes when Key Workflows is blank. Roles come from Team/User Job Description. "
        "Demonstration type is the value selected on the visit. "
        "Challenges come from Workflow Challenges and Consequences of living without Solution."
    )


def method_implication() -> str:
    return (
        "Train associates on the leading bar first. One visit can match more than one topic, so the bars are not competing audiences. "
        "A blank workflow or challenge note is a demo the next associate cannot prepare for. Require both fields at close."
    )


def account_counts(visits: list[Visit]) -> Counter[str]:
    return Counter(visit.account for visit in visits)


def named_account_ranking(visits: list[Visit]) -> list[tuple[str, int]]:
    """Rank accounts that have a name. Unknown means the Account field was blank."""
    return [(account, count) for account, count in ranked(account_counts(visits)) if account != "Unknown"]


def _top_share(ranking: list[tuple[str, int]], total: int, limit: int) -> tuple[int, str]:
    chosen = ranking[:limit]
    share = sum(count for _account, count in chosen)
    return share, percent(share, total)


def job_description_story(visits: list[Visit]) -> str:
    counts = count_labels(visits, "role")
    classified = Counter(
        {label: count for label, count in counts.items() if label not in {"Other", "Unspecified"}}
    )
    lead = format_leaders(leaders(classified)) if classified else "no classified role"
    other = counts.get("Other", 0)
    blank = counts.get("Unspecified", 0)
    return (
        f"The largest classified audience is {lead}. "
        f"Other is {other} ({percent(other, len(visits))}) and Unspecified is {blank} "
        f"({percent(blank, len(visits))}). "
        "The role comes only from Team/User Job Description."
    )


def job_description_note(visits: list[Visit]) -> str:
    counts = count_labels(visits, "role")
    residual = counts.get("Other", 0) + counts.get("Unspecified", 0)
    return (
        f"Train associates on the demonstration types this role books, so they know the client’s workflow "
        f"and can anticipate the queries and the solutions to show. "
        f"{residual} of {len(visits)} visits ({percent(residual, len(visits))}) still have no usable job title."
    )


def account_concentration_story(visits: list[Visit]) -> str:
    ranking = named_account_ranking(visits)
    unknown = account_counts(visits).get("Unknown", 0)
    if not ranking:
        return f"No account name was recorded. {unknown} visits have a blank Account field."
    lead_name, lead_count = ranking[0]
    top_share, top_pct = _top_share(ranking, len(visits), 5)
    singles = sum(1 for _account, count in ranking if count == 1)
    repeats = sum(1 for _account, count in ranking if count >= 2)
    return (
        f"{lead_name} has the most visits ({lead_count}, {percent(lead_count, len(visits))}). "
        f"The five most visited named accounts are {top_share} visits ({top_pct}). "
        f"{repeats} named accounts appear at least twice and {singles} appear once. "
        f"Blank Account: {unknown}."
    )


def concentration_lines(ranking: list[tuple[str, int]], unit: str, limit: int = 4) -> list[str]:
    """Top lines for the concentration page. Equal counts share one line, as in the sample."""
    lines: list[str] = []
    for name, count in ranking[:limit]:
        lines.append(f"{name}: {count} {unit}")
    return lines


def role_ranking(visits: list[Visit]) -> list[tuple[str, int]]:
    return ranked(count_labels(visits, "role"))


def concentration_callout(visits: list[Visit]) -> str:
    ranking = named_account_ranking(visits)
    roles = role_ranking(visits)
    role_name = roles[0][0] if roles else "the leading role"
    if not ranking:
        return "The Account field is blank for these visits, so name the account before assigning follow-up."
    account_name, account_count = ranking[0]
    return (
        f"Before the next demo with {account_name} ({account_count} visits), brief the associate on the last "
        f"demonstration type, the workflow, and the solution already shown. The room is usually {role_name}. "
        "Continuing that conversation is how the return visit becomes another booked demo."
    )


def combined_concentration_lines(
    by_year: dict[int, list[Visit]],
    attribute: str,
    *,
    named_only: bool = False,
    limit: int = 4,
) -> list[str]:
    """One line per leader, with the count in each year so the list replaces a grouped chart."""
    per_year = {
        year: account_counts(visits) if named_only else count_labels(visits, attribute)
        for year, visits in by_year.items()
    }
    totals: Counter[str] = Counter()
    for counts in per_year.values():
        totals.update(counts)
    if named_only:
        totals.pop("Unknown", None)
    lines = []
    for label, count in ranked(totals)[:limit]:
        detail = ", ".join(f"{year}: {per_year[year].get(label, 0)}" for year in sorted(by_year))
        lines.append(f"{label}: {count} visits ({detail})")
    return lines


def year_column_lines(by_year: dict[int, list[Visit]], *, kind: str, limit: int = 3) -> list[tuple[str, list[str]]]:
    """Top names inside each year, for a three-column page."""
    columns: list[tuple[str, list[str]]] = []
    for _year, visits in by_year.items():
        if kind == "account":
            ranking = named_account_ranking(visits)[:limit]
        else:
            ranking = ranked(count_labels(visits, "role"))[:limit]
        lines = [f"{index}. {label} — {count} visits" for index, (label, count) in enumerate(ranking, start=1)]
        columns.append((year_coverage_label(visits), lines))
    return columns


def role_year_callout(by_year: dict[int, list[Visit]]) -> str:
    del by_year
    return (
        "Investment and finance is the client in the room every year. Train associates on Client Training "
        "and on valuation and company analysis, so they know that workflow and can anticipate the queries "
        "and the solutions to show. Where the role is Unspecified or Other, get the job title before the demo."
    )


def account_year_callout(by_year: dict[int, list[Visit]]) -> str:
    del by_year
    return (
        "Before the next demo, brief the associate on the last demonstration type, workflow, and solution "
        "shown to that account. Asian Development Bank and BDO Unibank led 2024, Apis Partners returned in "
        "2024 and 2025, and the first half of 2026 is led by Oxera, Swedfund, and Arc Group."
    )


def combined_concentration_callout(by_year: dict[int, list[Visit]]) -> str:
    accounts = top_named_accounts(by_year, 1)
    roles = combined_concentration_lines(by_year, "role", limit=1)
    account = accounts[0] if accounts else "the leading named account"
    role = roles[0].split(":", 1)[0] if roles else "the leading role"
    return (
        f"Before the next call, brief the associate on the last demonstration type, workflow, and solution "
        f"shown to {account}. The room is usually {role}, so train that conversation until the associate "
        "can anticipate the queries and show the solution without starting the demo over."
    )


def account_concentration_note(visits: list[Visit]) -> str:
    ranking = named_account_ranking(visits)
    if not ranking:
        return "Record the account name before the call so an associate can prepare a follow-up demo."
    repeats = [(account, count) for account, count in ranking if count >= 3]
    if not repeats:
        return (
            "No named account has three or more visits in this file. "
            "The book is wide rather than concentrated, so a standard first-session outline matters more than a custom deck per account."
        )
    return (
        "Give a prepared associate to the accounts that already return. "
        "A known account is the fastest next demo."
    )


def job_description_years_story(by_year: dict[int, list[Visit]]) -> str:
    parts = []
    for year, visits in by_year.items():
        counts = count_labels(visits, "role")
        classified = Counter(
            {label: count for label, count in counts.items() if label not in {"Other", "Unspecified"}}
        )
        parts.append(f"{year}: {format_leaders(leaders(classified)) if classified else 'none classified'}")
    return (
        "The largest classified job family in each year was "
        + "; ".join(parts)
        + ". Other and Unspecified stay on the chart because they are part of the audience record."
    )


def job_description_years_note(by_year: dict[int, list[Visit]]) -> str:
    parts = []
    for year, visits in by_year.items():
        counts = count_labels(visits, "role")
        residual = counts.get("Other", 0) + counts.get("Unspecified", 0)
        parts.append(f"{year}: {percent(residual, len(visits))}")
    return (
        "Share of visits with no usable job family (Other or Unspecified): "
        + "; ".join(parts)
        + ". Compare classified roles only after reading that residual. A shift in Other can be a form change, not a new audience."
    )


def top_named_accounts(by_year: dict[int, list[Visit]], limit: int = 8) -> list[str]:
    totals: Counter[str] = Counter()
    for visits in by_year.values():
        for account, count in named_account_ranking(visits):
            totals[account] += count
    return [account for account, _count in ranked(totals)[:limit]]


def account_counts_by_year(by_year: dict[int, list[Visit]]) -> dict[int, Counter[str]]:
    return {year: account_counts(visits) for year, visits in by_year.items()}


def account_years_story(by_year: dict[int, list[Visit]]) -> str:
    parts = []
    for year, visits in by_year.items():
        ranking = named_account_ranking(visits)
        if not ranking:
            parts.append(f"{year}: no named account")
            continue
        name, count = ranking[0]
        parts.append(f"{year}: {name} ({count})")
    return (
        "The most visited named account in each year was "
        + "; ".join(parts)
        + ". The chart shows the eight named accounts with the most visits across all files. A zero means that account has no visit in that year."
    )


def account_years_note(by_year: dict[int, list[Visit]]) -> str:
    names = top_named_accounts(by_year, 8)
    present = {year: account_counts(visits) for year, visits in by_year.items()}
    multi_year = [
        account
        for account in names
        if sum(1 for counts in present.values() if counts.get(account, 0) > 0) >= 2
    ]
    unknown = {year: account_counts(visits).get("Unknown", 0) for year, visits in by_year.items()}
    unknown_bits = ", ".join(f"{year}: {count}" for year, count in unknown.items())
    return (
        f"{len(multi_year)} of these eight accounts appear in at least two years. "
        "Keep a running brief for those relationships instead of starting each year from a blank demo. "
        f"Blank Account fields: {unknown_bits}."
    )


def _leading_topic(visits: list[Visit]) -> str:
    return format_leaders(leaders(count_labels(visits, "solution_topics")))


def _leading_workflow(visits: list[Visit]) -> str:
    counts = Counter(dict(ranked(count_labels(visits, "workflows"), skip_residual=True)))
    return format_leaders(leaders(counts)) if counts else "no classified workflow"


def action_items(visits: list[Visit], *, by_year: dict[int, list[Visit]] | None = None) -> list[tuple[str, str]]:
    """Recommendations that cite this extract. Partial years are not treated as full years of zero."""
    total = len(visits) or 1
    demo_counts = count_labels(visits, "demonstration_type")
    demo_lead = leaders(demo_counts)
    demo_label, demo_count = demo_lead[0] if demo_lead else ("Unspecified", 0)
    ranking = named_account_ranking(visits)
    top_share, top_pct = _top_share(ranking, total, 5)
    repeat_accounts = sum(1 for _account, count in ranking if count >= 3)
    no_workflow = sum(1 for visit in visits if not ranked(Counter(visit.workflows), skip_residual=True))
    region_lead = leaders(count_labels(visits, "region"))
    region_label, region_count = region_lead[0] if region_lead else ("Unspecified", 0)

    ai_count = count_labels(visits, "solution_topics").get("AI Tools", 0)
    items = [
        (
            "Cover the hours training requests come in",
            (
                f"{region_label} is {region_count} of {len(visits)} visits ({percent(region_count, total)}). "
                + _REGION_HOURS.get(region_label, "Staff the hours those clients are at their desk.")
                + " Associates on that window can accept the demo when the request arrives."
            ),
        ),
        (
            "Train the bench on the modules clients ask to see",
            (
                f"The visits center on {_leading_topic(visits)}, and on {_leading_workflow(visits)}. "
                f"AI Tools is in {ai_count} visits. "
                "Associates who can show these can take the demo instead of handing it to one specialist."
            ),
        ),
        (
            "Go back to accounts that already booked",
            (
                f"{repeat_accounts} named accounts have three or more visits. "
                f"The top five are {top_share} of {len(visits)} visits ({top_pct}). "
                "Brief the associate on the last workflow and the solution already shown, so the return visit continues that conversation."
            ),
        ),
        (
            "Have more associates ready for the session clients book",
            (
                f"'{demo_label}' is {demo_count} of {len(visits)} visits ({percent(demo_count, total)}). "
                "Practice that session until more of the bench can run it. "
                "More people who can run it means more demo requests the team can accept."
            ),
        ),
        (
            "Write the workflow down so someone else can take the follow-up",
            (
                f"{no_workflow} visits have no workflow. "
                "Fill Key Workflows before the visit is closed. "
                "Another associate can then take the next demo from the last conversation."
            ),
        ),
    ]
    if not by_year or len(by_year) < 2:
        return items
    window, window_totals = window_counts(by_year)
    if window:
        bits = "; ".join(f"{year}: {window_totals[year]}" for year in sorted(by_year))
        items[0] = (
            "Count demos on the months every file contains",
            (
                f"January–June logged demos are {bits}. "
                "Use that window when setting how many demos Manila should take next. "
                + _REGION_HOURS.get(region_label, "")
            ),
        )
    return items
