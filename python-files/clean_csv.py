"""Clean one Manila visit export into the derived CSV used by the reports.

Run this for a single file, or use generate_reports.py to clean every workbook
in raw-csv and write the PDFs.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from visit_model import clean_table, write_cleaned_csv


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Clean a Manila visit workbook or CSV.")
    parser.add_argument("input_file", type=Path, help="Raw .xlsx or .csv export.")
    parser.add_argument("-o", "--output", type=Path, help="Cleaned CSV path.")
    args = parser.parse_args()

    input_path = args.input_file if args.input_file.is_absolute() else project_root / args.input_file
    output_path = args.output or (project_root / "output" / "cleaned" / f"{input_path.stem}_cleaned.csv")
    if not output_path.is_absolute():
        output_path = project_root / output_path

    rows, fieldnames = clean_table(input_path)
    write_cleaned_csv(output_path, rows, fieldnames)
    print(f"Wrote {len(rows)} cleaned rows to {output_path}")


if __name__ == "__main__":
    main()
