import unittest
from collections import Counter
from datetime import date
from pathlib import Path

from analyze_visit_time_series import (
    VisitRecord,
    build_time_series,
    load_visit_records,
)


class VisitTimeSeriesTests(unittest.TestCase):
    def test_monthly_and_quarterly_visit_counts(self) -> None:
        records = [
            VisitRecord(date(2024, 1, 3), frozenset()),
            VisitRecord(date(2024, 1, 20), frozenset()),
            VisitRecord(date(2024, 4, 2), frozenset()),
            VisitRecord(date(2026, 6, 30), frozenset()),
        ]

        counts = build_time_series(records)

        self.assertEqual(counts.monthly_visits["2024-01"], 2)
        self.assertEqual(counts.monthly_visits["2024-04"], 1)
        self.assertEqual(counts.monthly_visits["2026-06"], 1)
        self.assertEqual(counts.quarterly_visits["2024 Q1"], 2)
        self.assertEqual(counts.quarterly_visits["2024 Q2"], 1)
        self.assertEqual(counts.quarterly_visits["2026 Q2"], 1)

    def test_solution_topics_count_once_per_visit(self) -> None:
        records = [
            VisitRecord(
                date(2024, 2, 5),
                frozenset({"Screening", "Dashboards, Watchlists and Alerts"}),
            ),
            VisitRecord(
                date(2024, 2, 6),
                frozenset({"Screening"}),
            ),
        ]

        counts = build_time_series(records)

        self.assertEqual(counts.monthly_solution_topics[("2024-02", "Screening")], 2)
        self.assertEqual(
            counts.monthly_solution_topics[("2024-02", "Dashboards, Watchlists and Alerts")],
            1,
        )

    def test_combined_cleaned_datasets_cover_expected_years_and_visits(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        inputs = [
            project_root / "cleaned_data" / "raw-2024_cleaned.csv",
            project_root / "cleaned_data" / "2025-manila-visit_raw-final_cleaned.csv",
            project_root / "cleaned_data" / "raw-1h2026_cleaned.csv",
        ]

        records = load_visit_records(inputs)
        yearly_counts = build_time_series(records)

        self.assertEqual(len(records), 576)
        self.assertEqual(
            dict(sorted(Counter(record.visit_date.year for record in records).items())),
            {2024: 289, 2025: 220, 2026: 67},
        )
        self.assertEqual(yearly_counts.monthly_visits["2026-06"], 4)
        self.assertNotIn("2026-07", yearly_counts.monthly_visits)


if __name__ == "__main__":
    unittest.main()
