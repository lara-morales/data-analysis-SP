import unittest
from pathlib import Path

from narrative import activity_implication, activity_story
from visit_model import (
    clean_row,
    group_by_year,
    load_cleaned_csv,
    month_counts,
    quarter_counts,
    write_cleaned_csv,
    clean_table,
)
from generate_reports import generate


class BusinessStoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        project_root = Path(__file__).resolve().parents[1]
        visits = []
        for path in sorted((project_root / "raw-csv").glob("*.xlsx")):
            rows, fields = clean_table(path)
            temp = project_root / "output" / "cleaned" / f"{path.stem}_cleaned.csv"
            write_cleaned_csv(temp, rows, fields)
            loaded, skipped = load_cleaned_csv(temp)
            if skipped:
                raise AssertionError(skipped)
            visits.extend(loaded)
        cls.by_year = group_by_year(visits)

    def test_visit_counts_follow_the_visit_date(self) -> None:
        self.assertEqual(
            {year: len(visits) for year, visits in self.by_year.items()},
            {2024: 289, 2025: 220, 2026: 67},
        )

    def test_2026_stops_in_june_and_is_not_filled_with_zero_months(self) -> None:
        counts = {year: month_counts(visits) for year, visits in self.by_year.items()}

        self.assertEqual(sum(counts[2026].values()), 67)
        self.assertNotIn(7, counts[2026])
        self.assertEqual(sum(counts[2024][month] for month in range(1, 7)), 114)
        self.assertEqual(sum(counts[2025][month] for month in range(1, 7)), 198)
        self.assertEqual(counts[2026][5] + counts[2026][6], 6)

    def test_quarter_counts_reconcile_and_keep_partial_2026(self) -> None:
        quarters = {year: quarter_counts(visits) for year, visits in self.by_year.items()}

        self.assertEqual(dict(quarters[2024]), {1: 44, 2: 70, 3: 77, 4: 98})
        self.assertEqual(dict(quarters[2025]), {1: 119, 2: 79, 3: 15, 4: 7})
        self.assertEqual(dict(quarters[2026]), {1: 46, 2: 21})
        for year, counts in quarters.items():
            self.assertEqual(sum(counts.values()), len(self.by_year[year]))

    def test_activity_text_uses_the_may_and_june_count_instead_of_zero(self) -> None:
        text = f"{activity_story(self.by_year)} {activity_implication(self.by_year)}"

        self.assertIn("67 in 2026 (January–June)", text)
        self.assertIn("2026: 67", text)
        self.assertNotIn("0 records fall in May", text)
        self.assertIn("2025 is front-loaded: 198 of 220", text)

    def test_job_description_does_not_create_a_workflow(self) -> None:
        cleaned = clean_row(
            {
                "Visit Date": "2024-04-02",
                "Key Workflows": "Screening for target companies",
                "Team/User Job Description": "Financial analyst building valuation models in Excel",
                "Meeting Notes": "Also discussed private equity funds",
                "Solutions Discussed": "",
            },
            "example.xlsx",
        )

        self.assertEqual(cleaned["Workflow Categories"], "Screening and list building")
        self.assertEqual(cleaned["Workflow Source"], "Key Workflows")
        self.assertEqual(cleaned["Client Role Category"], "Investment and finance")

    def test_blank_workflows_can_fall_back_to_meeting_notes(self) -> None:
        cleaned = clean_row(
            {
                "Visit Date": "2024-04-02",
                "Key Workflows": "",
                "Meeting Notes": "Walked through peer comps in Excel",
            },
            "example.xlsx",
        )

        self.assertEqual(cleaned["Workflow Source"], "Meeting Notes")
        self.assertIn("Valuation and company analysis", cleaned["Workflow Categories"])
        self.assertIn("Excel and office workflows", cleaned["Workflow Categories"])

    def test_non_financial_is_not_classified_as_finance(self) -> None:
        cleaned = clean_row(
            {
                "Visit Date": "2024-04-02",
                "Team/User Job Description": "Client segment is non-financial corporate",
            },
            "example.xlsx",
        )

        self.assertNotEqual(cleaned["Client Role Category"], "Investment and finance")


class ReportGenerationTests(unittest.TestCase):
    def test_generate_writes_a_report_per_year_and_a_combined_story(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        generate(project_root / "raw-csv", project_root / "output")

        for year, visits in ((2024, 289), (2025, 220), (2026, 67)):
            report = project_root / "output" / "reports" / "by-year" / str(year) / "visit_analysis.pdf"
            summary = project_root / "output" / "reports" / "by-year" / str(year) / "visit_analysis_summary.csv"
            self.assertTrue(report.exists())
            self.assertTrue(summary.exists())
            self.assertGreater(report.stat().st_size, 1000)
            self.assertIn(str(visits), summary.read_text(encoding="utf-8"))
        combined = project_root / "output" / "reports" / "combined"
        self.assertTrue((combined / "business_story.pdf").exists())
        self.assertTrue((combined / "time_series.pdf").exists())


if __name__ == "__main__":
    unittest.main()
