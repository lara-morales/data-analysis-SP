import unittest
from pathlib import Path

from analyze_business_story import (
    YEAR_INPUTS,
    load_story_visits,
    top_demonstration_type_labels,
    yearly_counts,
    yearly_month_counts,
    yearly_quarter_counts,
)


class BusinessStoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        project_root = Path(__file__).resolve().parents[1]
        cls.datasets = load_story_visits(
            {
                year: project_root / "cleaned_data" / filename
                for year, filename in YEAR_INPUTS.items()
            }
        )

    def test_combined_year_counts_match_source_datasets(self) -> None:
        self.assertEqual(
            {year: len(visits) for year, visits in self.datasets.items()},
            {2024: 289, 2025: 220, 2026: 67},
        )

    def test_2026_is_a_partial_year_and_months_are_not_filled_with_zeros(self) -> None:
        month_counts = yearly_month_counts(self.datasets)

        self.assertEqual(sum(month_counts[2026].values()), 67)
        self.assertNotIn(7, month_counts[2026])
        self.assertEqual(sum(month_counts[2024][month] for month in range(1, 7)), 114)
        self.assertEqual(sum(month_counts[2025][month] for month in range(1, 7)), 198)

    def test_quarter_counts_reconcile_to_each_year_total_and_keep_partial_2026(self) -> None:
        quarter_counts = yearly_quarter_counts(self.datasets)

        self.assertEqual(dict(quarter_counts[2024]), {1: 44, 2: 70, 3: 77, 4: 98})
        self.assertEqual(dict(quarter_counts[2025]), {1: 119, 2: 79, 3: 15, 4: 7})
        self.assertEqual(dict(quarter_counts[2026]), {1: 46, 2: 21})
        for year, counts in quarter_counts.items():
            self.assertEqual(sum(counts.values()), len(self.datasets[year]))

    def test_region_counts_use_the_existing_region_mapping(self) -> None:
        region_counts = yearly_counts(self.datasets, "region")

        self.assertEqual(region_counts[2024]["APAC"], 188)
        self.assertEqual(region_counts[2025]["APAC"], 122)
        self.assertEqual(region_counts[2026]["EMEA"], 45)
        for year, counts in region_counts.items():
            self.assertEqual(sum(counts.values()), len(self.datasets[year]))

    def test_key_story_metrics_are_supported_by_records(self) -> None:
        topic_counts = yearly_counts(self.datasets, "solution_topics")
        demo_counts = yearly_counts(self.datasets, "demonstration_categories")
        demo_type_counts = yearly_counts(self.datasets, "demonstration_type")
        workflow_counts = yearly_counts(self.datasets, "workflows")
        months = yearly_month_counts(self.datasets)

        self.assertEqual(topic_counts[2024].most_common(1)[0], ("Excel and Office Tools", 136))
        self.assertEqual(topic_counts[2025].most_common(1)[0], ("Excel and Office Tools", 154))
        self.assertEqual(topic_counts[2026].most_common(1)[0], ("Screening", 45))
        self.assertEqual(demo_counts[2024]["Training"], 263)
        self.assertEqual(demo_counts[2025]["Training"], 181)
        self.assertEqual(demo_counts[2026]["Training"], 63)
        self.assertEqual(
            demo_counts[2024],
            {
                "Training": 263,
                "Product Demo or Help": 15,
                "Workflow Enrichment": 5,
                "Expert Presentation": 2,
                "Other": 2,
                "Subscription or Commercial": 6,
            },
        )
        self.assertEqual(
            demo_counts[2025],
            {
                "Training": 181,
                "Product Demo or Help": 18,
                "Workflow Enrichment": 6,
                "Other": 4,
                "Subscription or Commercial": 12,
                "Expert Presentation": 7,
            },
        )
        self.assertEqual(
            demo_counts[2026],
            {"Training": 63, "Workflow Enrichment": 4, "Product Demo or Help": 1},
        )
        self.assertEqual(demo_type_counts[2024]["Client Training"], 224)
        self.assertEqual(demo_type_counts[2025]["Client Training"], 102)
        self.assertEqual(demo_type_counts[2026]["Client Training"], 48)
        self.assertEqual(
            demo_type_counts[2025]["Client Training; New User Training"], 2
        )
        self.assertEqual(
            demo_type_counts[2026]["Client Training; New User Training"], 1
        )
        self.assertNotIn("Training", demo_type_counts[2024])
        self.assertEqual(workflow_counts[2024].most_common(1)[0][0], "Valuation and Company Analysis")
        self.assertEqual(workflow_counts[2025].most_common(1)[0][0], "Valuation and Company Analysis")
        self.assertEqual(workflow_counts[2026].most_common(1)[0][0], "Valuation and Company Analysis")
        self.assertEqual(sum(count for month, count in months[2025].items() if month <= 6), 198)
        self.assertEqual(sum(count for month, count in months[2026].items() if month <= 4), 61)

    def test_demonstration_type_chart_uses_only_the_five_most_frequent_exact_values(self) -> None:
        counts = yearly_counts(self.datasets, "demonstration_type")

        self.assertEqual(
            top_demonstration_type_labels(counts),
            [
                "Client Training",
                "New User Training",
                "Enhancement Demo",
                "Subscription Discussion",
                "Expert Presentation",
            ],
        )


if __name__ == "__main__":
    unittest.main()
