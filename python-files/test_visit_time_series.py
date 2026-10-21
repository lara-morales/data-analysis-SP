import unittest
from datetime import date

from analyze_visit_time_series import _observed_months
from visit_model import Visit


def _visit(year: int, month: int, day: int = 1) -> Visit:
    return Visit(
        source_file="example.xlsx",
        visit_number="1",
        visit_date=date(year, month, day),
        country="Singapore",
        region="APAC",
        account="Example",
        products=(),
        demonstration_type="Client Training",
        demonstration_categories=("Training",),
        role="Other",
        workflows=(),
        workflow_source="Not recorded",
        challenges=(),
        challenge_recorded=False,
        solution_topics=(),
        solution_note_status="No solution note",
        solution_note="",
    )


class VisitTimeSeriesTests(unittest.TestCase):
    def test_span_keeps_internal_gaps_and_stops_at_the_last_visit(self) -> None:
        visits = [_visit(2024, 1, 3), _visit(2024, 3, 2), _visit(2026, 6, 30)]

        self.assertEqual(
            _observed_months(visits),
            [
                "2024-01",
                "2024-02",
                "2024-03",
                "2024-04",
                "2024-05",
                "2024-06",
                "2024-07",
                "2024-08",
                "2024-09",
                "2024-10",
                "2024-11",
                "2024-12",
                "2025-01",
                "2025-02",
                "2025-03",
                "2025-04",
                "2025-05",
                "2025-06",
                "2025-07",
                "2025-08",
                "2025-09",
                "2025-10",
                "2025-11",
                "2025-12",
                "2026-01",
                "2026-02",
                "2026-03",
                "2026-04",
                "2026-05",
                "2026-06",
            ],
        )
        self.assertNotIn("2026-07", _observed_months(visits))


if __name__ == "__main__":
    unittest.main()
