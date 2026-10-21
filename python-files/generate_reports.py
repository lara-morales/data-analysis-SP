"""Clean the raw visit workbooks and write the PDF reports.

From the project folder:

    .venv/bin/python python-files/generate_reports.py

Years and partial coverage come from the visit dates, so the same command works
after a later refresh of any of the source files.

    output/cleaned/                  one cleaned CSV per source file
    output/reports/by-year/<year>/   visit analysis PDF and summary
    output/reports/combined/         cross-year story and time series
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from analyze_business_story import write_business_story
from analyze_visit_time_series import write_time_series
from analyze_visits import write_visit_report
from visit_model import (
    clean_table,
    discover_source_files,
    group_by_year,
    load_cleaned_csv,
    write_cleaned_csv,
    year_coverage_label,
)


def _resolve(path: Path, project_root: Path) -> Path:
    return path if path.is_absolute() else project_root / path


def generate(raw_dir: Path, output_dir: Path, years: set[int] | None = None) -> None:
    """Clean every source file, then write the yearly and combined PDFs."""
    sources = discover_source_files(raw_dir)
    if not sources:
        raise FileNotFoundError(f"No .xlsx or .csv files found in {raw_dir}")

    cleaned_dir = output_dir / "cleaned"
    cleaned_paths: list[Path] = []
    for source in sources:
        rows, fields = clean_table(source)
        cleaned_path = cleaned_dir / f"{source.stem}_cleaned.csv"
        write_cleaned_csv(cleaned_path, rows, fields)
        cleaned_paths.append(cleaned_path)
        print(f"Cleaned {len(rows)} rows from {source.name} -> {cleaned_path}")

    visits = []
    for cleaned_path in cleaned_paths:
        loaded, skipped = load_cleaned_csv(cleaned_path)
        visits.extend(loaded)
        for message in skipped:
            print(message)

    by_year = group_by_year(visits)
    selected = years if years else set(by_year)
    missing = sorted(selected - set(by_year))
    if missing:
        raise ValueError(f"No dated visits found for year(s): {', '.join(map(str, missing))}")

    for year, year_visits in by_year.items():
        if year not in selected:
            continue
        year_dir = output_dir / "reports" / "by-year" / str(year)
        pdf_path = year_dir / "visit_analysis.pdf"
        summary_path = year_dir / "visit_analysis_summary.csv"
        write_visit_report(year_visits, pdf_path, summary_path)
        print(f"Wrote {year_coverage_label(year_visits)} ({len(year_visits)} visits) -> {pdf_path}")

    combined_dir = output_dir / "reports" / "combined"
    write_business_story(
        visits,
        combined_dir / "business_story.pdf",
        combined_dir / "business_story_summary.csv",
    )
    write_time_series(
        visits,
        combined_dir / "time_series.pdf",
        combined_dir / "time_series_summary.csv",
    )
    print(f"Wrote combined reports for {len(visits)} visits -> {combined_dir}")


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(
        description="Clean raw-csv workbooks and write visit analysis PDFs."
    )
    parser.add_argument("--raw-dir", type=Path, default=project_root / "raw-csv")
    parser.add_argument("--output-dir", type=Path, default=project_root / "output")
    parser.add_argument(
        "--year",
        type=int,
        nargs="*",
        help="Limit the yearly PDFs to these visit years. Combined reports still use every year.",
    )
    args = parser.parse_args()
    try:
        generate(
            _resolve(args.raw_dir, project_root),
            _resolve(args.output_dir, project_root),
            set(args.year) if args.year else None,
        )
    except (FileNotFoundError, ValueError) as error:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
