"""Generate a PDF analysis report for Manila client visits.

This script reads a cleaned visit export, applies deterministic regex rules to
summarize the data, and saves a multi-page PDF plus a CSV summary of the counts.

The report intentionally excludes the derived ``Demonstration Category`` column.
All free-text grouping is deterministic and regex-based so the results are
auditable and reproducible without NLP or external models.
"""

from __future__ import annotations

import argparse
import csv
import re
from collections import Counter
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

from solution_categories import is_non_solution_entry, solution_topic_categories


# Placeholder values are common in exported spreadsheets when a field is blank,
# marked N/A, or has Excel error strings such as #N/A. These are treated as
# missing data so they do not distort trend or category counts.
PLACEHOLDER_RE = re.compile(
    r"^\s*[\"']?(?:#n/?a|n/?a|none(?: mentioned)?|null|nan|x|=|-|--|not available|not mentioned|unknown|nothing shared|did not mention(?:ed)?|"
    r"#name\?|#value!|#ref!|#div/0!|#null!|#num!|#spill!|#calc!|#field!)[.,;:]*[\"']?\s*$",
    re.I,
)


def clean(value: str | None) -> str:
    """Normalize a CSV cell so it can be safely counted or matched.

    The source export may contain Excel-style placeholders, line breaks, repeated
    whitespace, and other formatting variations. This function removes extra
    whitespace and converts known missing-value markers to an empty string so the
    downstream analysis is consistent.
    """
    text = re.sub(r"[\r\n\t]+", " ", value or "")
    text = re.sub(r"\s{2,}", " ", text).strip()
    return "" if PLACEHOLDER_RE.fullmatch(text) else text


def split_terms(value: str | None) -> list[str]:
    """Split a field with multiple named items into a clean list of terms.

    Some cells contain several products, solutions, or labels in one string,
    separated by semicolons, bullets, hyphens, or inline numbered and lettered
    lists. We split on those separators and remove list markers so each item is
    counted independently.
    """
    text = clean(value)
    if not text:
        return []
    terms = re.split(
        r"\s*;\s*|\s*(?:\n|•)\s*|\s+(?=-)|"
        r"\s+(?=(?:\d+[.)]|[a-z][.)])\s+)",
        text,
        flags=re.I,
    )
    cleaned_terms = []
    for term in terms:
        term = re.sub(r"^[\s.;]*(?:\d+[.)]?|[a-z][.)])\s+", "", term, flags=re.I)
        term = term.strip().strip("-.;:").strip()
        if term:
            cleaned_terms.append(term)
    return cleaned_terms


def count_terms(rows: list[dict[str, str]], column: str) -> Counter[str]:
    """Count each item in a multi-value field across every row.

    For example, if one visit mentions two products, that visit should count once
    for each product rather than as a single combined value. This ensures the
    chart reflects actual item prevalence instead of visit count alone.
    """
    counts: Counter[str] = Counter()
    for row in rows:
        counts.update(split_terms(row.get(column)))
    return counts


def unclassified_solution_label(label: str) -> str:
    """Shorten an unclassified source label for display without hiding its topic."""
    if len(label) <= 72:
        return label

    first_sentence = re.split(r"(?<=[.!?])\s+", label, maxsplit=1)[0]
    if len(first_sentence) <= 72:
        return first_sentence
    shortened = first_sentence[:69].rsplit(" ", 1)[0].rstrip(" ,;:")
    return f"{shortened}..."


def classify(text: str, rules: list[tuple[str, str]]) -> str:
    """Assign the first matching category from a rule list.

    The pattern list is ordered intentionally; the first match wins. This makes
    the classification deterministic and easy to explain because the same text
    always maps to the same group when it matches an earlier rule.
    """
    if not text.strip():
        return "Unspecified"
    for label, pattern in rules:
        if re.search(pattern, text, re.I):
            return label
    return "Other"


# These rules translate free-text role descriptions into broader client groups.
# They intentionally use a conservative set of keywords so it is easy to audit
# why a given value falls into a specific category.
JOB_RULES = [
    ("Consulting and advisory", r"consultant|consulting|advisory|advisor|valuation firm|professional services"),
    ("Investment and finance", r"investment|portfolio|asset management|private equity|private markets?|venture capital|funds?|analyst|associate|valuation|corporate finance|financial|finance|accounting|accountant|bank(?:ing|er)?\b|credit|treasury|fixed income|investor|ratings|equities|trading|modeller|modeler|risk management"),
    ("Corporate development and M&A", r"corporate development|merger|acquisition|m&a|deal sourcing|transaction"),
    ("Research and analysis", r"research|economist|forensic|due diligence|data analyst|market intelligence|specialist|tracking peers|tracking and analyz|industry outlook|macro.?economic|data sets?|peer analysis|company comparables|sustainability|esg"),
    ("Sales and business development", r"sales|business development|commercial|client coverage|marketing|relationship manager|account manager|partnerships|investor relations?|\bir\b"),
    ("Client administration and support", r"\bpoc\b|admin|assistant|cashier|subscription|client support"),
    ("Executive and leadership", r"chief|president|\bceo\b|\bcfo\b|\bcio\b|\bcoo\b|director|executive|founder|principal|partner|manager|head of|officer|team lead|supervisor"),
    ("Operations and technical", r"maintenance|operations|supply chain|engineering|information technology|\bit\b|systems|business controller|controller|product manager|data management|procurement|technical poc|excel templates|office tools|formulas"),
    ("Corporate strategy and planning", r"strategy|strategic|planning|corporate|generalist|business analyst"),
    ("Academia and education", r"academia|academic|professor|university|lecturer|faculty"),
    ("Early-career and new users", r"intern|student|graduate|trainee|newly hired|new user|user is new|new to (?:the )?(?:platform|ciq|capital iq)|tenured"),
    ("Product session participant (role not stated)", r"training|walkthrough|introductory session|conducted demo|capital iq.*meeting"),
]

# These workflow rules capture the work clients say they are trying to do with
# the product or service so the output can be aligned to real client tasks.
WORKFLOW_RULES = [
    ("Screening and list building", r"screen|list creation|list building|target compan|sourc(?:e|ing) (?:for |potential )?compan|pull(?:ing)? (?:a )?(?:set|list) of compan|sector(?:s)? and geograph|identify potential compan|company list"),
    ("Valuation and company analysis", r"comparables?|\bcomps\b|peer|benchmark|valuation|financials?|multiples?|share price|stock price|company analysis|equities analysis|equity analysis|company profile|estimates?|company data|\banalyst\b|\bassociate\b|business controller|investment professional|financial reporting|corporate investing"),
    ("M&A and transactions", r"m&a|merger|acquisition|transaction|deal|buyers?|investors?|leveraged buyout|\blbo\b|capital structure|investment banking|\bib workflow\b"),
    ("Market and news research", r"news|industry research|market research|market intelligence|macro|market data|data coverage|datasets?|data sets|filings?|company research|industry outlook|broker report|research work|\bgeneralist workflow\b|document intelligence|chat.?iq|renewable|competition|competitors|trends?|investor relations?|\bir workflow\b|business intelligence|strategy team|strategic business development"),
    ("Excel and office workflows", r"excel|office|powerpoint|ppt|word|template|plug.?in"),
    ("Alerts and dashboards", r"alert|dashboard|watchlist"),
    ("Private markets", r"private market|private compan(?:y|ies)|private equity|\bpe workflow\b|venture capital|fund"),
    ("Metals and mining", r"metals|mining|commodity|commodities|cost curve"),
    ("Credit, fixed income and capital markets", r"fixed income|debt capital|credit|risk management|probability of default|ratings analytics|deposit and loan|loan ranking|bond|debt market|audit"),
    ("Portfolio and investment monitoring", r"monitor(?:ing)? .*compan|monitor(?:ing)? investments?|track(?:ing)?|holdings|portfolio|investment team|investment management|\bim workflow\b|secondary market|investment opportunit|peer companies"),
    ("Data and model integration", r"model|formula|data pull|data gathering|data collection|integration|migration|refresh|export|auto.?fill|populate|pull data"),
    ("Product learning and navigation", r"training|walkthrough|introductory demo|introductory session|query call|navigat|overview|how to|familiariz|new to|new users?|newly hired|trainee|intern|student|assignment|discover.*(?:feature|platform)|learn.*platform|totally new|hasn't used|not used"),
    ("Platform support and setup", r"troubleshoot|installation|install(?:ation)? of software|it support|software setup|set.?up issues"),
    ("Academic and educational research", r"academia|academic|professor|university|lecturer|faculty"),
    ("Consulting and advisory workflows", r"consultant|consulting|corporate adviser|\badvisor\b|advisory"),
    ("Client administration and access", r"\bpoc\b|admin team|subscription|user access|access/relationship|requesting user access|relationship with s&p"),
    ("Business leadership and management", r"founder|co-founder|\bceo\b|\bcfo\b|\bcio\b|\bcoo\b|director|principal|ex(?:e)?cutive assistant|executive|managing partner|project manager|overseeing teams|chairman|\bmanager\b|head of"),
]

# Challenge categories describe the main barriers people cite during a visit, such
# as data issues, unfamiliarity with the workflow, or integration problems.
CHALLENGE_RULES = [
    ("Data access and coverage", r"data|coverage|missing|not available|availability|available|dataset|source|pricing|critical mineral|estimate|financial information|financials?|limitation|small .*compan|discrepanc|up.?to.?date|out of date|not as up to date|price.*accurate|niche industr|\bubo\b|beneficial owner|private ratings?|automated ratings?"),
    ("Migration and integration", r"migrat|legacy|convert|factset|refinitiv|bloomberg|competitor|dual.access|template|plug.?in|formula|refresh|mismatch|do not match|excel.*ppt|ppt.*excel"),
    ("Workflow complexity and efficiency", r"difficult|challenge|multiple|browse|streamline|manual|takes? time|time to|trouble|pain point|delay|inefficient|hard to|benchmark|screen|filter|export|track|convenient|finding|screener|heading|automated way|fund holdings|narrow.*criteria|collaborat|pitch book|models?|modeling|modelling|visuali[sz]ation|transaction|search criteria"),
    ("Product adoption and learning", r"new|beginner|fresh to|learn|familiar|navigat|understand|training|never used|hasn't used|not used|not usually used|nothing about|not aware|discover.*(?:feature|platform)|assignment|joined the firm"),
    ("Configuration and access", r"setup|set up|setting up|install|access|permission|download|login|account|not showing|not visible|alert|user list|users? (?:are )?updated|updated/correct"),
    ("Product usability and technical issues", r"error|bug|not working|unable to|cannot|can't|doesn't|does not|issue|functionality|feature request|enhancement|collaborative|scroll|formula|convenient|answers are pulled slow|needs improvement|reliably used|additional .*cap"),
    ("Market and business conditions", r"m&a slowing|overpaid|underutilized|tariffs|trades globally|market conditions"),
]

COUNTRY_REGIONS = {
    "Australia": "APAC",
    "Cambodia": "APAC",
    "Canada": "Americas",
    "China": "APAC",
    "Fiji": "APAC",
    "Hong Kong": "APAC",
    "India": "APAC",
    "Indonesia": "APAC",
    "Japan": "APAC",
    "Jordan": "EMEA",
    "Malaysia": "APAC",
    "New Zealand": "APAC",
    "Philippines": "APAC",
    "Pakistan": "APAC",
    "Portugal": "EMEA",
    "Saudi Arabia": "EMEA",
    "Singapore": "APAC",
    "South Korea": "APAC",
    "Taiwan": "APAC",
    "Thailand": "APAC",
    "Vietnam": "APAC",
    "Belgium": "EMEA",
    "Denmark": "EMEA",
    "Finland": "EMEA",
    "France": "EMEA",
    "Germany": "EMEA",
    "Iceland": "EMEA",
    "Ireland": "EMEA",
    "Israel": "EMEA",
    "Italy": "EMEA",
    "Kenya": "EMEA",
    "Luxembourg": "EMEA",
    "Netherlands": "EMEA",
    "Norway": "EMEA",
    "South Africa": "EMEA",
    "Spain": "EMEA",
    "Sweden": "EMEA",
    "Switzerland": "EMEA",
    "United Arab Emirates": "EMEA",
    "United Kingdom": "EMEA",
    "United States": "Americas",
}


def add_page(pdf: PdfPages, title: str, description: str, chart) -> None:
    """Render one chart and add it to a multi-page PDF report.

    Each page includes a short narrative sentence so a stakeholder can understand
    the chart without needing to inspect the raw spreadhseet columns.
    """
    figure = plt.figure(figsize=(11.69, 8.27))
    figure.text(0.07, 0.94, title, fontsize=18, fontweight="bold", color="#17324D")
    figure.text(0.07, 0.905, description, fontsize=9.5, color="#4F5D6B", wrap=True)
    chart(figure)
    figure.text(0.07, 0.025, "Source: Cleaned Manila visit dataset | Regex-based categorization", fontsize=7, color="#6B7280")
    pdf.savefig(figure, bbox_inches="tight")
    plt.close(figure)


def bar_chart(figure, labels: list[str], values: list[int], *, horizontal: bool = False) -> None:
    """Draw a simple bar or horizontal bar chart inside a figure.

    We use a horizontal layout when labels are long (for example, regions or
    product categories), because it keeps the text readable while still comparing
    counts clearly.
    """
    axis = figure.add_axes((0.10, 0.14, 0.84, 0.68))
    if horizontal:
        labels, values = labels[::-1], values[::-1]
        axis.barh(labels, values, color="#1C7C8C")
        axis.set_xlabel("Number of visits")
        if len(labels) > 20:
            axis.tick_params(axis="y", labelsize=8)
    else:
        axis.bar(labels, values, color="#1C7C8C")
        axis.set_ylabel("Number of visits")
        axis.tick_params(axis="x", rotation=35)
    axis.grid(axis="y", alpha=0.25)
    axis.set_axisbelow(True)
    for index, value in enumerate(values):
        if horizontal:
            axis.text(value, index, f" {value}", va="center", fontsize=8)
        else:
            axis.text(index, value, str(value), ha="center", va="bottom", fontsize=8)


def main() -> None:
    """Create the PDF report and companion CSV summary for the cleaned data.

    This is the orchestration function for the script. It resolves file paths,
    reads the cleaned export, builds each chart and summary table, and writes the
    final artifacts to the output folder.
    """
    project_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Create a PDF analysis of Manila visits.")
    parser.add_argument("--input", type=Path, default=project_root / "cleaned_data" / "2025-manila-visit_cleaned.csv")
    parser.add_argument("--output", type=Path, default=project_root / "output" / "manila_visit_analysis.pdf")
    parser.add_argument("--summary", type=Path, default=project_root / "output" / "manila_visit_analysis_summary.csv")
    args = parser.parse_args()

    # Resolve relative paths against the project root so the script behaves the
    # same way when it is run from any working directory.
    for path_name in ("input", "output", "summary"):
        path = getattr(args, path_name)
        if not path.is_absolute():
            setattr(args, path_name, project_root / path)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.summary.parent.mkdir(parents=True, exist_ok=True)

    # Read the cleaned CSV and convert the standardized date into a real Python
    # datetime object for monthly and quarterly trend charts.
    with args.input.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        row["parsed_date"] = datetime.strptime(clean(row["Visit Date Clean"]), "%Y-%m-%d")

    # summary_rows accumulates every chart category so the same underlying counts
    # are available in CSV form as a transparent audit trail.
    summary_rows: list[tuple[str, str, int]] = []
    with PdfPages(args.output) as pdf:
        # 1–2. Time trends: monthly detail followed by quarterly direction.
        monthly = Counter(row["parsed_date"].strftime("%Y-%m") for row in rows)
        months = sorted(monthly)
        summary_rows.extend(("Monthly visits", month, monthly[month]) for month in months)
        add_page(pdf, "Monthly Visit Trend", "Counts completed visits by calendar month to show seasonality and periods of higher demand.", lambda fig: bar_chart(fig, months, [monthly[m] for m in months]))

        quarterly = Counter(f"{row['parsed_date'].year} Q{(row['parsed_date'].month - 1) // 3 + 1}" for row in rows)
        quarters = sorted(quarterly)
        summary_rows.extend(("Quarterly visits", quarter, quarterly[quarter]) for quarter in quarters)
        add_page(pdf, "Quarterly Visit Trend", "Aggregates visits into calendar quarters to reveal broader momentum than monthly fluctuations.", lambda fig: bar_chart(fig, quarters, [quarterly[q] for q in quarters]))

        # 3. Product reach: count how often each product appears across visits.
        products = count_terms(rows, "Products Discussed")
        product_labels, product_values = zip(*products.most_common(15)) if products else ([], [])
        summary_rows.extend(("Products discussed", label, value) for label, value in products.most_common())
        add_page(pdf, "Visits by Product", "Ranks products discussed during visits; multi-product visits contribute once to each product named.", lambda fig: bar_chart(fig, list(product_labels), list(product_values), horizontal=True))

        # 4. Geography: show where the demand is concentrated by client country.
        countries = Counter(clean(row.get("Country")) or "Unspecified" for row in rows)
        country_labels, country_values = zip(*countries.most_common())
        summary_rows.extend(("Visits by country", label, value) for label, value in countries.most_common())
        add_page(pdf, "Visits by Client Country", "Shows where demo demand is concentrated, providing a practical geographic view of the client base.", lambda fig: bar_chart(fig, list(country_labels), list(country_values), horizontal=True))

        regions = Counter(
            COUNTRY_REGIONS.get(country, "Unspecified")
            for country in (clean(row.get("Country")) for row in rows)
        )
        region_labels, region_values = zip(*regions.most_common())
        summary_rows.extend(("Visits by region", label, value) for label, value in regions.most_common())
        add_page(pdf, "Visits by Client Region", "Groups client countries into APAC, EMEA, and Americas to show regional demand alongside the country-level view.", lambda fig: bar_chart(fig, list(region_labels), list(region_values), horizontal=True))

        # 5. Use the original Demonstration Type field; do not use the derived category.
        demo_types = Counter(clean(row["Demonstration Type"]) or "Unspecified" for row in rows)
        type_labels, type_values = zip(*demo_types.most_common())
        summary_rows.extend(("Demonstration type", label, value) for label, value in demo_types.most_common())
        add_page(pdf, "Visits by Demonstration Type", "Uses the original Demonstration Type field to compare the purpose of visits; Demonstration Category is excluded.", lambda fig: bar_chart(fig, list(type_labels), list(type_values), horizontal=True))

        # 6–7. Client profile: role mix and concentration of repeat accounts.
        job_counts = Counter(classify(clean(row["Team/User Job Description"]), JOB_RULES) for row in rows)
        job_labels, job_values = zip(*job_counts.most_common())
        summary_rows.extend(("Client job category", label, value) for label, value in job_counts.most_common())
        add_page(pdf, "Client Profile: Job Description", "Groups free-text job descriptions into transparent regex-based role families to identify the audiences receiving demos.", lambda fig: bar_chart(fig, list(job_labels), list(job_values), horizontal=True))

        accounts = Counter(clean(row["Account"]) or "Unknown" for row in rows)
        account_labels, account_values = zip(*accounts.most_common(15))
        summary_rows.extend(("Client account", label, value) for label, value in accounts.most_common())
        add_page(pdf, "Client Profile: Account Concentration", "Highlights the accounts with the most recorded visits; this helps separate repeat engagement from broad market reach.", lambda fig: bar_chart(fig, list(account_labels), list(account_values), horizontal=True))

        # 8–9. Match workflow and challenge notes to the relevant regex groups.
        workflow_counts: Counter[str] = Counter()
        challenge_counts: Counter[str] = Counter()
        for row in rows:
            workflow_text = " ".join(clean(row.get(column)) for column in ("Key Workflows", "Team/User Job Description"))
            challenge_text = " ".join(clean(row.get(column)) for column in ("Workflow Challenges", "Consequences of living without Solution"))
            workflow_counts[classify(workflow_text, WORKFLOW_RULES)] += 1
            challenge_counts[classify(challenge_text, CHALLENGE_RULES)] += 1

        workflow_labels, workflow_values = zip(*workflow_counts.most_common())
        summary_rows.extend(("Key workflow", label, value) for label, value in workflow_counts.most_common())
        add_page(pdf, "Client Profile: Key Workflows", "Categorizes the stated workflows so Manila can align future demos with the tasks clients most often need to complete.", lambda fig: bar_chart(fig, list(workflow_labels), list(workflow_values), horizontal=True))

        challenge_labels, challenge_values = zip(*challenge_counts.most_common())
        summary_rows.extend(("Workflow challenge", label, value) for label, value in challenge_counts.most_common())
        add_page(pdf, "Client Profile: Workflow Challenges", "Groups challenge and consequence narratives to identify recurring adoption barriers that future visits can address.", lambda fig: bar_chart(fig, list(challenge_labels), list(challenge_values), horizontal=True))

        # 10. Rank the solutions explicitly recorded in the Solutions Discussed field.
        solutions = count_terms(rows, "Solutions Discussed")
        solution_chart_counts: Counter[str] = Counter()
        for label, count in solutions.items():
            if is_non_solution_entry(label):
                continue
            topics = solution_topic_categories(label)
            if topics:
                solution_chart_counts.update({topic: count for topic in topics})
            else:
                solution_chart_counts[unclassified_solution_label(label)] += count
        solution_labels, solution_values = zip(*solution_chart_counts.most_common(20)) if solution_chart_counts else ([], [])
        summary_rows.extend(("Solutions discussed", label, value) for label, value in solutions.most_common())
        summary_rows.extend(("Solution topic category", label, value) for label, value in solution_chart_counts.most_common())
        add_page(pdf, "Solutions and Datasets Discussed", "Groups aliases into shared solution topics and identifies multiple topics in long notes; original source labels remain in the summary CSV.", lambda fig: bar_chart(fig, list(solution_labels), list(solution_values), horizontal=True))

    # Write the same aggregated counts to a CSV file so a reviewer can validate the
    # report without reopening the PDF.
    with args.summary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(("analysis", "category", "visit_count"))
        writer.writerows(summary_rows)
    print(f"Wrote {len(rows)} rows across 11 analysis pages to {args.output}")
    print(f"Wrote chart data summary to {args.summary}")


if __name__ == "__main__":
    main()