"""Load, clean, and classify Manila visit workbooks.

Classification is deterministic and regex-based. Each chart reads one stated
field (or a documented fallback) so a count can be traced back to the export.
"""

from __future__ import annotations

import csv
import re
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from openpyxl import load_workbook

from solution_categories import is_non_solution_entry, solution_topic_categories


PLACEHOLDER_RE = re.compile(
    r"^\s*[\"']?(?:#n/?a|n/?a|none(?: mentioned)?|null|nan|x|=|-|--|"
    r"not available|not mentioned|unknown|nothing shared|did not mention(?:ed)?|"
    r"#name\?|#value!|#ref!|#div/0!|#null!|#num!|#spill!|#calc!|#field!)"
    r"[.,;:]*[\"']?\s*$",
    re.IGNORECASE,
)

# Months with no visits are omitted from charts. A country that is not in this
# map is reported as Unspecified and listed in the summary so it can be added.
COUNTRY_REGIONS = {
    "Australia": "APAC",
    "Belgium": "EMEA",
    "Cambodia": "APAC",
    "Canada": "Americas",
    "China": "APAC",
    "Denmark": "EMEA",
    "Fiji": "APAC",
    "Finland": "EMEA",
    "France": "EMEA",
    "Germany": "EMEA",
    "Hong Kong": "APAC",
    "Iceland": "EMEA",
    "India": "APAC",
    "Indonesia": "APAC",
    "Ireland": "EMEA",
    "Israel": "EMEA",
    "Italy": "EMEA",
    "Japan": "APAC",
    "Jordan": "EMEA",
    "Kenya": "EMEA",
    "Luxembourg": "EMEA",
    "Malaysia": "APAC",
    "Netherlands": "EMEA",
    "New Zealand": "APAC",
    "Norway": "EMEA",
    "Pakistan": "APAC",
    "Philippines": "APAC",
    "Portugal": "EMEA",
    "Saudi Arabia": "EMEA",
    "Singapore": "APAC",
    "South Africa": "EMEA",
    "South Korea": "APAC",
    "Spain": "EMEA",
    "Sweden": "EMEA",
    "Switzerland": "EMEA",
    "Taiwan": "APAC",
    "Thailand": "APAC",
    "United Arab Emirates": "EMEA",
    "United Kingdom": "EMEA",
    "United States": "Americas",
    "Vietnam": "APAC",
}

# First match wins. Functional roles come before seniority and "new user"
# language so "Finance Intern" stays in finance and "non-financial" does not.
ROLE_RULES = [
    ("Consulting and advisory", r"consultant|consulting|advisory|\badvisor\b"),
    (
        "Investment and finance",
        r"investment|portfolio|asset management|private equity|venture capital|"
        r"\bfunds?\b|\banalysts?\b|\bassociates?\b|valuation|corporate finance|"
        r"(?<!non-)(?:financials?|finances?)\b|\bfp\s*&\s*a\b|accounting|accountant|"
        r"\bbanks?\b|banking|\bcredits?\b|treasury|fixed income|\binvestors?\b|"
        r"\bcontrollers?\b",
    ),
    (
        "Corporate development and strategy",
        r"corporate development|corporate planning|corporate advisory|merger|"
        r"acquisition|\bm\s*&\s*a\b|\bstrategy\b",
    ),
    (
        "Research and analysis",
        r"research|economist|forensic|due diligence|data analyst|business intelligence",
    ),
    (
        "Sales and business development",
        r"\bsales\b|business development|commercial|account managers?|"
        r"investor relations?|\bir\b|marketing|relationship manager",
    ),
    (
        "Executive and leadership",
        r"\bchief\b|\bpresident\b|\bceo\b|\bcfo\b|\bcio\b|\bcoo\b|\bfounders?\b|"
        r"co-founder|\bprincipal\b|\bpartners?\b|head of",
    ),
    (
        "Operations and technical",
        r"procurement|maintenance|operations|supply chain|engineering|"
        r"information technology|\bit\b",
    ),
    (
        "Early-career and new users",
        r"\binterns?\b|\bstudents?\b|\btrainees?\b|newly hired|new users?",
    ),
]

WORKFLOW_RULES = [
    ("Screening and list building", r"screen|list creation|list building|target compan"),
    ("Valuation and company analysis", r"comparables?|\bcomps\b|\bpeers?\b|valuation|financials?|multiples?"),
    ("M&A and transactions", r"\bm\s*&\s*a\b|merger|acquisition|transaction|\bdeals?\b|\bbuyers?\b|\binvestors?\b"),
    ("Market and news research", r"\bnews\b|industry research|market research|\bmacro\b|market data|filings?"),
    ("Excel and office workflows", r"\bexcel\b|\boffice\b|powerpoint|\bppt\b|\bword\b|template|plug.?in"),
    ("Alerts and dashboards", r"\balerts?\b|dashboard|watchlist"),
    ("Private markets", r"private market|private compan|private equity|venture capital|\bfunds?\b"),
    ("Metals and mining", r"metals|mining|commodit(?:y|ies)|cost curve"),
    ("Data and model integration", r"\bmodels?\b|formula|data pull|data gathering|integration|migration"),
    ("Product learning", r"training|navigate|overview|how to|familiariz|new to"),
]

CHALLENGE_RULES = [
    (
        "Migration and competitor conversion",
        r"migrat|legacy|convert|factset|refinitiv|bloomberg|dual[- ]access|competitor",
    ),
    (
        "Data coverage",
        r"limited coverage|\bcoverage\b|not available|missing data|pricing data|"
        r"critical mineral|out of date|not up[- ]to[- ]date|niche industr|"
        r"difficult to find|can't find|cannot find|private compan",
    ),
    (
        "Manual effort and complexity",
        r"difficult|pain point|takes time|time to|streamline|manual|inefficient|"
        r"overwhelming|multiple sources",
    ),
    (
        "Learning and navigation",
        r"new to|very new|never used|not familiar|familiariz|navigat|hasn't used|not used",
    ),
    (
        "Access and setup",
        r"set(?:ting)? up|install|\bpermission\b|\baccess\b|\blog[- ]?in\b",
    ),
    (
        "Excel, export and models",
        r"\bexcel\b|export|heading|refresh|\bmodels?\b|formula|plug[- ]?in",
    ),
    (
        "Monitoring and alerts",
        r"\balerts?\b|track(?:ing)?|automated way|watchlist",
    ),
]

COMPETITOR_RULES = [
    (r"\bbloomberg\b", "Bloomberg"),
    (r"factset", "FactSet"),
    (r"refinitiv|datastream", "Refinitiv"),
    (r"pitchbook", "PitchBook"),
    (r"preqin", "Preqin"),
    (r"capital iq|ciq legacy|\blegacy\b", "S&P Capital IQ Legacy"),
    (r"similar platform|other vendor|competitor", "Other or unnamed competitor"),
]

DEMONSTRATION_RULES = [
    (r"client training|new user training|onboarding", "Training"),
    (r"product help|enhancement demo|sales demo", "Product Demo or Help"),
    (r"subscription discussion", "Subscription or Commercial"),
    (r"expert presentation", "Expert Presentation"),
    (r"workflow enrichment", "Workflow Enrichment"),
    (r"service review|quarterly review|account review", "Account Review"),
]

DERIVED_FIELDS = [
    "Visit Date Clean",
    "Visit Date Valid",
    "Primary Visit Owner",
    "Client Region",
    "Demonstration Category",
    "Client Role Category",
    "Workflow Categories",
    "Workflow Source",
    "Challenge Categories",
    "Competitor Categories",
    "Solution Categories",
    "Solution Note Status",
    "Data Quality Flags",
    "Source File",
]

# Residual labels are real rows, but they are not themes. Charts that rank
# themes omit them and report their counts in the caption instead.
RESIDUAL_LABELS = {"", "Unspecified", "Uncategorized", "Not recorded"}
MONTH_NAMES = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)


@dataclass(frozen=True)
class Visit:
    source_file: str
    visit_number: str
    visit_date: date
    country: str
    region: str
    account: str
    products: tuple[str, ...]
    demonstration_type: str
    demonstration_categories: tuple[str, ...]
    role: str
    workflows: tuple[str, ...]
    workflow_source: str
    challenges: tuple[str, ...]
    challenge_recorded: bool
    solution_topics: tuple[str, ...]
    solution_note_status: str
    solution_note: str


def normalize_text(value: object) -> str:
    """Collapse whitespace and turn spreadsheet placeholders into blanks."""
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%m/%d/%Y")
    if isinstance(value, date):
        return value.strftime("%m/%d/%Y")
    text = str(value).replace("\ufffd", "")
    text = text.replace("\u2013", "-").replace("\u2014", "-")
    text = re.sub(r"[\r\n\t]+", " ", text)
    text = re.sub(r"\s{2,}", " ", text).strip()
    return "" if PLACEHOLDER_RE.fullmatch(text) else text


def coerce_date(value: object) -> date | None:
    """Parse a visit date from an Excel value or a common export string."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = normalize_text(value)
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%d-%b-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _matches(text: str, rules: list[tuple[str, str]]) -> list[str]:
    found: list[str] = []
    for label, pattern in rules:
        if re.search(pattern, text, re.IGNORECASE) and label not in found:
            found.append(label)
    return found


def first_match(text: str, rules: list[tuple[str, str]], *, empty: str, default: str) -> str:
    if not text.strip():
        return empty
    for label, pattern in rules:
        if re.search(pattern, text, re.IGNORECASE):
            return label
    return default


def role_category(text: str) -> str:
    return first_match(text, ROLE_RULES, empty="Unspecified", default="Other")


def demonstration_categories(text: str) -> list[str]:
    if not text.strip():
        return ["Unspecified"]
    found: list[str] = []
    for pattern, label in DEMONSTRATION_RULES:
        if re.search(pattern, text, re.IGNORECASE) and label not in found:
            found.append(label)
    return found or ["Other"]


def workflow_categories(text: str) -> list[str]:
    return _matches(text, WORKFLOW_RULES)


def challenge_categories(text: str) -> list[str]:
    return _matches(text, CHALLENGE_RULES)


def competitor_categories(text: str) -> list[str]:
    found: list[str] = []
    for pattern, label in COMPETITOR_RULES:
        if re.search(pattern, text, re.IGNORECASE) and label not in found:
            found.append(label)
    return found


def split_terms(value: str) -> list[str]:
    """Split a multi-value cell and keep the first spelling of each item."""
    text = normalize_text(value)
    if not text:
        return []
    parts = re.split(
        r"\s*;\s*|\s*(?:\n|•)\s*|\s+(?=-)|"
        r"\s+(?=(?:\d+[.)]|[a-z][.)])\s+)",
        text,
        flags=re.IGNORECASE,
    )
    terms: list[str] = []
    seen: set[str] = set()
    for part in parts:
        term = re.sub(r"^[\s.;]*(?:\d+[.)]?|[a-z][.)])\s+", "", part, flags=re.IGNORECASE)
        term = term.strip().strip("-.;:").strip()
        key = term.casefold()
        if term and key not in seen:
            seen.add(key)
            terms.append(term)
    return terms


def split_labels(value: str | None) -> tuple[str, ...]:
    return tuple(part.strip() for part in (value or "").split(";") if part.strip())


def region_for_country(country: str) -> str:
    if not country:
        return "Unspecified"
    return COUNTRY_REGIONS.get(country, "Unspecified")


def _joined(labels: list[str]) -> str:
    return "; ".join(labels)


def _workflow_text(row: dict[str, object]) -> tuple[str, str]:
    """Use the workflow field. Meeting notes fill in only when that field is empty."""
    key_workflows = normalize_text(row.get("Key Workflows"))
    if key_workflows:
        return key_workflows, "Key Workflows"
    meeting_notes = normalize_text(row.get("Meeting Notes"))
    if meeting_notes:
        return meeting_notes, "Meeting Notes"
    return "", "Not recorded"


def clean_row(row: dict[str, object], source_file: str) -> dict[str, str]:
    """Return one export row plus the derived columns the reports chart."""
    cleaned = {column: normalize_text(value) for column, value in row.items()}
    visit_date = coerce_date(row.get("Visit Date"))
    cleaned["Visit Date Clean"] = visit_date.isoformat() if visit_date else ""
    cleaned["Visit Date Valid"] = "Yes" if visit_date else "No"

    owner_column = "Visit: Owner Name" if "Visit: Owner Name" in row else "Visit Team Member"
    owners = split_terms(normalize_text(row.get(owner_column)))
    cleaned["Primary Visit Owner"] = owners[0] if owners else ""

    country = cleaned.get("Country", "")
    cleaned["Client Region"] = region_for_country(country)
    demo_text = cleaned.get("Demonstration Type", "")
    cleaned["Demonstration Category"] = _joined(demonstration_categories(demo_text))
    cleaned["Client Role Category"] = role_category(cleaned.get("Team/User Job Description", ""))

    workflow_text, workflow_source = _workflow_text(row)
    workflows = workflow_categories(workflow_text)
    cleaned["Workflow Source"] = workflow_source
    if workflows:
        cleaned["Workflow Categories"] = _joined(workflows)
    elif workflow_source == "Not recorded":
        cleaned["Workflow Categories"] = ""
    else:
        cleaned["Workflow Categories"] = "Uncategorized"

    challenge_text = " ".join(
        normalize_text(row.get(column))
        for column in ("Workflow Challenges", "Consequences of living without Solution")
    ).strip()
    challenges = challenge_categories(challenge_text)
    if not challenge_text:
        cleaned["Challenge Categories"] = ""
    elif challenges:
        cleaned["Challenge Categories"] = _joined(challenges)
    else:
        cleaned["Challenge Categories"] = "Uncategorized"

    competitor_text = " ".join(
        normalize_text(row.get(column))
        for column in (
            "Competitor Products Mentioned/Discussed",
            "Current Subscriptions/Competitors",
            "Meeting Notes",
            "Miscellaneous Notes",
        )
    )
    competitors = competitor_categories(competitor_text)
    cleaned["Competitor Categories"] = _joined(competitors) if competitors else "None mentioned"

    solution_text = normalize_text(row.get("Solutions Discussed"))
    if not solution_text:
        cleaned["Solution Categories"] = ""
        cleaned["Solution Note Status"] = "No solution note"
    elif is_non_solution_entry(solution_text):
        cleaned["Solution Categories"] = ""
        cleaned["Solution Note Status"] = "Non-solution note"
    else:
        topics = solution_topic_categories(solution_text)
        cleaned["Solution Categories"] = _joined(topics)
        cleaned["Solution Note Status"] = "Categorized" if topics else "Uncategorized"

    flags: list[str] = []
    if visit_date is None:
        flags.append("Invalid or missing visit date")
    if not cleaned.get("Account"):
        flags.append("Missing account")
    if not cleaned.get("Country"):
        flags.append("Missing country")
    if not normalize_text(row.get("Key Workflows")):
        flags.append("Missing key workflows")
    if not cleaned.get("Team/User Job Description"):
        flags.append("Missing user role")
    if not cleaned["Primary Visit Owner"]:
        flags.append("Missing visit owner")
    if not solution_text:
        flags.append("Missing solutions discussed")
    cleaned["Data Quality Flags"] = "; ".join(flags) if flags else "OK"
    cleaned["Source File"] = source_file
    return cleaned


def visit_from_cleaned_row(row: dict[str, str]) -> Visit | None:
    """Build a visit from a cleaned CSV row. Undated rows are returned as None."""
    visit_date = coerce_date(row.get("Visit Date Clean") or row.get("Visit Date"))
    if visit_date is None:
        return None
    country = normalize_text(row.get("Country")) or "Unspecified"
    solution_status = (row.get("Solution Note Status") or "").strip() or "No solution note"
    topics = split_labels(row.get("Solution Categories")) if solution_status == "Categorized" else ()
    challenge_labels = split_labels(row.get("Challenge Categories"))
    return Visit(
        source_file=(row.get("Source File") or "").strip(),
        visit_number=normalize_text(row.get("Visit: Visit Number")),
        visit_date=visit_date,
        country=country,
        region=(row.get("Client Region") or "").strip() or region_for_country(country if country != "Unspecified" else ""),
        account=normalize_text(row.get("Account")) or "Unknown",
        products=tuple(split_terms(row.get("Products Discussed"))),
        demonstration_type=normalize_text(row.get("Demonstration Type")) or "Unspecified",
        demonstration_categories=split_labels(row.get("Demonstration Category")) or ("Unspecified",),
        role=(row.get("Client Role Category") or "").strip() or "Unspecified",
        workflows=split_labels(row.get("Workflow Categories")),
        workflow_source=(row.get("Workflow Source") or "").strip() or "Not recorded",
        challenges=tuple(label for label in challenge_labels if label not in RESIDUAL_LABELS),
        challenge_recorded=bool(challenge_labels),
        solution_topics=topics,
        solution_note_status=solution_status,
        solution_note=normalize_text(row.get("Solutions Discussed")),
    )


def read_table(path: Path) -> tuple[list[dict[str, object]], list[str], str]:
    """Read the visit sheet from a workbook or CSV.

    Workbooks often contain an empty extra sheet. The sheet that contains
    Visit Date and the most data rows is the one that is cleaned.
    """
    if path.suffix.lower() == ".xlsx":
        workbook = load_workbook(path, read_only=True, data_only=True)
        best: tuple[int, str, list[str], list[dict[str, object]]] | None = None
        try:
            for sheet_name in workbook.sheetnames:
                worksheet = workbook[sheet_name]
                rows = list(worksheet.iter_rows(values_only=True))
                if not rows:
                    continue
                headers = [str(header).strip() if header is not None else "" for header in rows[0]]
                if "Visit Date" not in headers:
                    continue
                records: list[dict[str, object]] = []
                for values in rows[1:]:
                    if values is None or all(cell is None or str(cell).strip() == "" for cell in values):
                        continue
                    record: dict[str, object] = {}
                    for index, header in enumerate(headers):
                        if not header:
                            continue
                        record[header] = values[index] if index < len(values) else None
                    records.append(record)
                if best is None or len(records) > best[0]:
                    best = (len(records), sheet_name, headers, records)
        finally:
            workbook.close()
        if best is None:
            raise ValueError(f"No worksheet with a Visit Date column was found in {path.name}.")
        return best[3], [header for header in best[2] if header], best[1]

    raw = path.read_bytes()
    last_error: UnicodeError | None = None
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            text = raw.decode(encoding)
        except UnicodeError as error:
            last_error = error
            continue
        reader = csv.DictReader(text.splitlines())
        headers = list(reader.fieldnames or [])
        if "Visit Date" not in headers and "Visit Date Clean" not in headers:
            raise ValueError(f"{path.name} has no Visit Date column.")
        return list(reader), headers, path.name
    raise UnicodeError(f"Could not decode {path} as UTF-8 or Windows-1252: {last_error}")


def clean_table(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    records, headers, _sheet = read_table(path)
    cleaned_rows = [clean_row(record, path.name) for record in records]
    output_fields = list(headers) + [field for field in DERIVED_FIELDS if field not in headers]
    return cleaned_rows, output_fields


def write_cleaned_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def load_cleaned_csv(path: Path) -> tuple[list[Visit], list[str]]:
    """Load dated visits. Undated rows are returned separately as messages."""
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        visits: list[Visit] = []
        skipped: list[str] = []
        for line_number, row in enumerate(reader, start=2):
            visit = visit_from_cleaned_row(row)
            if visit is None:
                skipped.append(f"{path.name} line {line_number} has no usable visit date")
            else:
                visits.append(visit)
    return visits, skipped


def discover_source_files(raw_dir: Path) -> list[Path]:
    files = [
        path
        for path in list(raw_dir.glob("*.xlsx")) + list(raw_dir.glob("*.csv"))
        if not path.name.startswith("~$")
    ]
    return sorted(files, key=lambda path: path.name.casefold())


def group_by_year(visits: list[Visit]) -> dict[int, list[Visit]]:
    grouped: dict[int, list[Visit]] = {}
    for visit in visits:
        grouped.setdefault(visit.visit_date.year, []).append(visit)
    return dict(sorted(grouped.items()))


def month_counts(visits: list[Visit]) -> Counter[int]:
    return Counter(visit.visit_date.month for visit in visits)


def quarter_counts(visits: list[Visit]) -> Counter[int]:
    return Counter((visit.visit_date.month - 1) // 3 + 1 for visit in visits)


def count_labels(visits: list[Visit], attribute: str) -> Counter[str]:
    counts: Counter[str] = Counter()
    for visit in visits:
        value = getattr(visit, attribute)
        labels = value if isinstance(value, tuple) else (value,)
        counts.update(label for label in labels if label)
    return counts


def ranked(counts: Counter[str], *, skip_residual: bool = False) -> list[tuple[str, int]]:
    """Sort by count, then by name, so ties do not depend on row order."""
    items = [
        (label, count)
        for label, count in counts.items()
        if not (skip_residual and label in RESIDUAL_LABELS)
    ]
    return sorted(items, key=lambda item: (-item[1], item[0].casefold()))


def month_span(months: list[int] | set[int]) -> str:
    """Describe observed months without filling gaps with zeros."""
    ordered = sorted(set(months))
    if not ordered:
        return "no dated visits"
    if ordered == list(range(ordered[0], ordered[-1] + 1)):
        if ordered[0] == 1 and ordered[-1] == 12:
            return "January–December"
        if ordered[0] == ordered[-1]:
            return MONTH_NAMES[ordered[0] - 1]
        return f"{MONTH_NAMES[ordered[0] - 1]}–{MONTH_NAMES[ordered[-1] - 1]}"
    return ", ".join(MONTH_NAMES[month - 1] for month in ordered)


def year_coverage_label(visits: list[Visit]) -> str:
    if not visits:
        return "No visits"
    year = visits[0].visit_date.year
    span = month_span(visit.visit_date.month for visit in visits)
    if span == "January–December":
        return f"{year}"
    return f"{year} ({span})"


def comparable_months(by_year: dict[int, list[Visit]]) -> list[int]:
    """Months that are present in every year. Missing months are not zeros."""
    month_sets = [{visit.visit_date.month for visit in visits} for visits in by_year.values() if visits]
    if not month_sets:
        return []
    return sorted(set.intersection(*month_sets))


def percent(part: int, whole: int) -> str:
    if whole <= 0:
        return "n/a"
    return f"{part / whole:.0%}"


def leaders(counts: Counter[str], *, skip_residual: bool = False) -> list[tuple[str, int]]:
    ordered = ranked(counts, skip_residual=skip_residual)
    if not ordered:
        return []
    top_count = ordered[0][1]
    return [item for item in ordered if item[1] == top_count]


def format_leaders(items: list[tuple[str, int]]) -> str:
    if not items:
        return "none classified"
    if len(items) == 1:
        label, count = items[0]
        return f"{label} ({count})"
    count = items[0][1]
    labels = " and ".join(label for label, _count in items)
    return f"{labels} ({count} each)"
