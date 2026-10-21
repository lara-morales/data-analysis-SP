"""Clean and categorize a Manila visits CSV using deterministic regex rules.

This script reads a raw export from the Manila visit tracker, normalizes the
values that are missing or malformed, and derives consistent category columns for
analysis. The goal is to make the output reproducible and easy to explain without
resorting to machine learning or external processing.
"""

from __future__ import annotations

import argparse
import csv
import re
from datetime import date, datetime
from pathlib import Path

from openpyxl import load_workbook

from solution_categories import solution_topic_categories


# These values mean “no usable answer” in the source export. They become blank
# values in the cleaned file so charts do not count them as real responses.
PLACEHOLDER_RE = re.compile(
    r"^\s*(?:n/?a|none|null|nan|-|--|not available|unknown|"
    r"#name\?|#value!|#ref!|#div/0!|#null!|#num!|#spill!|#calc!|#field!)\s*$",
    re.IGNORECASE,
)


def normalize_text(value: str | None) -> str:
    """Normalize raw CSV text before it is used in analysis.

    This step removes Excel replacement characters, collapsed whitespace, and
    placeholder strings such as N/A or #N/A. It also handles values coming from
    Excel workbooks, where dates and blanks may arrive as Python objects rather
    than plain strings.
    """
    if value is None:
        return ""
    if isinstance(value, (datetime, date)):
        text = value.strftime("%m/%d/%Y")
    else:
        text = str(value)
    text = text.replace("\ufffd", "")
    text = re.sub(r"[\r\n\t]+", " ", text)
    text = re.sub(r"\s{2,}", " ", text).strip()
    return "" if PLACEHOLDER_RE.fullmatch(text) else text


def combined_text(row: dict[str, str], columns: tuple[str, ...]) -> str:
    """Merge several narrative columns into a single text blob.

    Some category rules rely on multiple fields from the same visit, such as the
    job description plus meeting notes. This helper joins them in a consistent
    order so the regex checks are applied across all relevant context.
    """
    return " ".join(normalize_text(row.get(column)) for column in columns)


def add_category(categories: list[str], text: str, pattern: str, label: str) -> None:
    """Append a category label only when the regex matches and the label is new.

    This avoids duplicate labels in multi-match fields and prevents the same
    category from being repeated multiple times in the same cleaned row.
    """
    if re.search(pattern, text, re.IGNORECASE) and label not in categories:
        categories.append(label)


def demonstration_category(text: str) -> str:
    """Map the raw demonstration description into a few broad business groups.

    The original column may contain free text such as 'Expert presentation' or
    'Product help'. This function converts those phrases into a stable, cleaner
    vocabulary used throughout the reporting process.
    """
    categories: list[str] = []
    add_category(categories, text, r"client training|new user training", "Training")
    add_category(categories, text, r"product help|enhancement demo", "Product Demo or Help")
    add_category(categories, text, r"subscription discussion", "Subscription or Commercial")
    add_category(categories, text, r"expert presentation", "Expert Presentation")
    add_category(categories, text, r"workflow enrichment", "Workflow Enrichment")
    return "; ".join(categories) if categories else "Other"


def role_category(text: str) -> str:
    """Assign a broad role bucket using ordered regex rules.

    The role text is often free-form, so only the presence of a few keyword sets
    is used to keep the classification transparent and explainable. Matching is
    done from top to bottom, meaning the earliest rule takes precedence.
    """
    if not text:
        return "Unspecified"
    rules = [
        (r"investment|portfolio|asset management|private equity|venture capital|fund manager|analyst|valuation|corporate finance", "Investment and Finance"),
        (r"research|economist|forensic|due diligence|data analyst", "Research and Analysis"),
        (r"corporate development|merger|acquisition|m&a|strategy", "Corporate Development and M&A"),
        (r"sales|business development|commercial|client coverage|marketing", "Sales and Business Development"),
        (r"chief|president|ceo|cfo|director|executive|partner", "Executive and Leadership"),
        (r"maintenance|operations|supply chain|engineering", "Operations and Technical"),
    ]
    for pattern, label in rules:
        if re.search(pattern, text, re.IGNORECASE):
            return label
    return "Other"


def workflow_categories(text: str) -> str:
    """Group a visit narrative into one or more workflow themes.

    A single meeting may touch several use cases. To avoid losing that nuance,
    each matching workflow category is appended and then joined with a semicolon.
    """
    categories: list[str] = []
    rules = [
        (r"screen|list creation|list building|target compan", "Screening and List Building"),
        (r"comparables?|peer|valuation|financials?|multiples?", "Valuation and Company Analysis"),
        (r"m&a|merger|acquisition|transaction|deal|buyers?|investors?", "M&A and Transactions"),
        (r"news|industry research|market research|macro|market data|filings?", "Market and News Research"),
        (r"excel|office|powerpoint|ppt|word|template|plug.?in", "Excel and Office Workflows"),
        (r"alert|dashboard|watchlist", "Alerts and Dashboards"),
        (r"private market|private compan|private equity|venture capital|fund", "Private Markets"),
        (r"metals|mining|commodity|commodities|cost curve", "Metals and Mining"),
        (r"model|formula|data pull|data gathering|integration|migration", "Data and Model Integration"),
        (r"training|navigate|overview|how to|familiariz|new to", "Product Learning"),
    ]
    for pattern, label in rules:
        add_category(categories, text, pattern, label)
    return "; ".join(categories) if categories else "Unspecified"


def competitor_categories(text: str) -> str:
    """Identify competitors or alternative platforms mentioned in the notes.

    This function does not use AI or external lookup services; it simply searches
    for common vendor names and labels them consistently in the cleaned dataset.
    """
    categories: list[str] = []
    rules = [
        (r"\bbloomberg\b", "Bloomberg"),
        (r"factset", "FactSet"),
        (r"refinitiv|datastream", "Refinitiv"),
        (r"pitchbook", "PitchBook"),
        (r"preqin", "Preqin"),
        (r"capital iq|ciq legacy|legacy", "S&P Capital IQ Legacy"),
        (r"similar platform|other vendor|competitor", "Other or Unnamed Competitor"),
    ]
    for pattern, label in rules:
        add_category(categories, text, pattern, label)
    return "; ".join(categories) if categories else "None Mentioned"


def parse_date(value: str) -> tuple[str, bool]:
    """Convert a US-style date string to ISO format for sorting and reporting.

    The export sometimes includes blanks or invalid values, so this function
    returns both the cleaned date and a boolean flag used later in the data
    quality checks.
    """
    text = normalize_text(value)
    if not text:
        return "", False
    try:
        parsed = datetime.strptime(text, "%m/%d/%Y")
    except ValueError:
        return "", False
    return parsed.strftime("%Y-%m-%d"), True


def clean_row(row: dict[str, str]) -> dict[str, str]:
    """Return one cleaned and enriched row ready for downstream analysis.

    This function keeps the original source data, adds standardized date and owner
    fields, and derives category columns that make charts and reporting simpler.
    """
    clean = {column: normalize_text(value) for column, value in row.items()}
    date_clean, date_valid = parse_date(row.get("Visit Date", ""))
    clean["Visit Date Clean"] = date_clean
    clean["Visit Date Valid"] = "Yes" if date_valid else "No"

    # Support both the current export and the older team-member column name.
    owner_column = "Visit: Owner Name" if "Visit: Owner Name" in row else "Visit Team Member"
    owners = [normalize_text(value) for value in row.get(owner_column, "").split(",") if normalize_text(value)]
    clean["Primary Visit Owner"] = owners[0] if owners else ""

    # Merge narrative fields that help explain the work, the customer role, and
    # the discussion topics. This gives the regex classification more context than
    # any one field alone.
    demo_text = normalize_text(row.get("Demonstration Type"))
    workflow_text = combined_text(row, ("Team/User Job Description", "Key Workflows", "Workflow Challenges", "Meeting Notes", "Miscellaneous Notes"))
    competitor_text = combined_text(row, ("Competitor Products Mentioned/Discussed", "Current Subscriptions/Competitors", "Meeting Notes", "Miscellaneous Notes"))
    solution_text = combined_text(row, ("Products Discussed", "Solutions Discussed", "Meeting Notes"))
    clean["Demonstration Category"] = demonstration_category(demo_text)
    clean["Client Role Category"] = role_category(normalize_text(row.get("Team/User Job Description")))
    clean["Workflow Categories"] = workflow_categories(workflow_text)
    clean["Competitor Categories"] = competitor_categories(competitor_text)
    solution_topics = solution_topic_categories(solution_text)
    clean["Solution Categories"] = "; ".join(solution_topics) if solution_topics else "Unspecified"

    # Data-quality flags create a visible audit trail instead of silently hiding
    # incomplete or inconsistent rows from the analysis.
    flags: list[str] = []
    if not date_valid:
        flags.append("Invalid or missing visit date")
    if not normalize_text(row.get("Account")):
        flags.append("Missing account")
    if not normalize_text(row.get("Key Workflows")):
        flags.append("Missing key workflows")
    if not normalize_text(row.get("Team/User Job Description")):
        flags.append("Missing user role")
    if not normalize_text(row.get(owner_column)):
        flags.append("Missing visit owner")
    clean["Data Quality Flags"] = "; ".join(flags) if flags else "OK"
    return clean


def default_output(input_path: Path) -> Path:
    """Build the default cleaned output path alongside the project data folder."""
    project_root = Path(__file__).resolve().parents[1]
    return project_root / "cleaned_data" / f"{input_path.stem}_cleaned.csv"


def read_csv_rows(input_path: Path) -> tuple[list[dict[str, str]], list[str]]:
    """Read CSVs and Excel workbooks, preferring UTF-8 for CSV files.

    Some exports are saved with Windows-1252 encoding instead of UTF-8, and the
    latest raw source is provided as an .xlsx workbook. This function handles both
    formats so the rest of the cleaning pipeline remains the same.
    """
    if input_path.suffix.lower() == ".xlsx":
        workbook = load_workbook(input_path, read_only=True, data_only=True)
        for sheet_name in workbook.sheetnames:
            worksheet = workbook[sheet_name]
            rows = list(worksheet.iter_rows(values_only=True))
            if not rows or all(cell is None for cell in rows[0]):
                continue
            headers = [str(header).strip() if header is not None else "" for header in rows[0]]
            cleaned_rows: list[dict[str, str]] = []
            for values in rows[1:]:
                record: dict[str, str] = {}
                for index, value in enumerate(values[: len(headers)]):
                    record[headers[index]] = normalize_text(value)
                cleaned_rows.append(record)
            return cleaned_rows, headers
        raise ValueError(f"No usable worksheet data found in workbook: {input_path}")

    raw = input_path.read_bytes()
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            text = raw.decode(encoding)
            reader = csv.DictReader(text.splitlines())
            rows = list(reader)
            return rows, list(reader.fieldnames or [])
        except UnicodeDecodeError:
            continue
    raise UnicodeError(f"Could not decode CSV as UTF-8 or Windows-1252: {input_path}")


def main() -> None:
    """Clean the selected source CSV and save the enriched output file."""
    project_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Clean a Manila visits CSV.")
    parser.add_argument("input_csv", type=Path, help="Path to the raw CSV file.")
    parser.add_argument("-o", "--output", type=Path, help="Output CSV path; defaults to cleaned_data.")
    args = parser.parse_args()

    # Resolve the input/output paths relative to the project root so running the
    # script from another folder still points to the same data location.
    input_path = args.input_csv if args.input_csv.is_absolute() else project_root / args.input_csv
    output_path = args.output or default_output(input_path)
    if not output_path.is_absolute():
        output_path = project_root / output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Read the raw export, clean every row, and append derived columns used for
    # analysis and reporting.
    rows, fieldnames = read_csv_rows(input_path)
    cleaned_rows = [clean_row(row) for row in rows]

    # These analysis helper columns are appended after the source fields so the
    # cleaned file remains easy to inspect and still keeps the original raw data.
    added_fields = [
        "Visit Date Clean", "Visit Date Valid", "Primary Visit Owner",
        "Demonstration Category", "Client Role Category", "Workflow Categories",
        "Competitor Categories", "Solution Categories", "Data Quality Flags",
    ]
    output_fields = fieldnames + [field for field in added_fields if field not in fieldnames]
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=output_fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(cleaned_rows)
    print(f"Wrote {len(cleaned_rows)} cleaned rows to {output_path}")


if __name__ == "__main__":
    main()