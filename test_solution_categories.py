import csv
import unittest
from pathlib import Path

from solution_categories import is_non_solution_entry, solution_topic_categories


class SolutionTopicCategoriesTests(unittest.TestCase):
    def test_excel_plugin_variants_share_one_topic(self) -> None:
        variants = ("Excel Plugin", "Excel Plug-In", "Excel Plug In", "Excel Plugins", "Plugin")

        for variant in variants:
            with self.subTest(variant=variant):
                self.assertEqual(solution_topic_categories(variant), ["Excel and Office Tools"])

    def test_help_and_training_resources_share_one_topic(self) -> None:
        variants = (
            "Helpful Links",
            "Help Page",
            "Helpful Page",
            "Platform Training Webinars",
            "S&P Capital IQ Pro Academy",
            "24/7 Support",
        )

        for variant in variants:
            with self.subTest(variant=variant):
                self.assertEqual(
                    solution_topic_categories(variant),
                    ["Helpful Pages"],
                )

    def test_ai_help_is_not_mistaken_for_help_resources(self) -> None:
        self.assertEqual(solution_topic_categories("Ask AI Help"), ["AI Tools"])

    def test_report_builder_case_variants_share_one_topic(self) -> None:
        variants = ("Report builder", "Report Builder", "Report builder tools")

        for variant in variants:
            with self.subTest(variant=variant):
                self.assertEqual(solution_topic_categories(variant), ["Report Builder"])

    def test_platform_overview_variants_share_one_topic(self) -> None:
        variants = (
            "Gave the client a high level overview of the Capital IQ Pro Platform",
            "Gave client a high level overview of the Capital IQ Pro Platforn",
            "Gave the client a high level overview of the CIQ Pro Platform",
            "Gave the client a high level overview of the platform and tailored it accordingly",
            "Gave the client an overview of the platform and also tailored the session the key areas that she would like to focus on",
        )

        for variant in variants:
            with self.subTest(variant=variant):
                self.assertIn("Platform Overview", solution_topic_categories(variant))

    def test_2024_platform_overview_source_entries_are_all_categorized(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        cleaned_path = project_root / "cleaned_data" / "raw-2024_cleaned.csv"
        with cleaned_path.open(encoding="utf-8-sig", newline="") as handle:
            rows = csv.DictReader(handle)
            overview_entries = [
                row["Solutions Discussed"]
                for row in rows
                if "overview" in row.get("Solutions Discussed", "").casefold()
                and "platform" in row.get("Solutions Discussed", "").casefold()
                and row.get("Solutions Discussed", "").casefold().startswith("gave ")
            ]

        self.assertTrue(overview_entries)
        for entry in overview_entries:
            with self.subTest(entry=entry):
                self.assertIn("Platform Overview", solution_topic_categories(entry))

    def test_screener_keyfield_and_add_steps_are_categorized(self) -> None:
        variants = (
            "Search for the keyfield: IQ_INDUSTRY_CLASSIFICATION > In: Energy and Industrials > Applies to: Target/Issuer > Add",
            "3000 > Add",
            "Companies Screener",
        )

        for variant in variants:
            with self.subTest(variant=variant):
                self.assertEqual(solution_topic_categories(variant), ["Screening"])

    def test_list_variants_are_grouped_with_dashboards_and_alerts(self) -> None:
        variants = (
            "Lists",
            "Company List",
            "List Creation",
            "Saved Lists",
            "Dashboard, Lists and Alerts",
        )

        for variant in variants:
            with self.subTest(variant=variant):
                self.assertIn("Dashboards, Watchlists and Alerts", solution_topic_categories(variant))
                self.assertNotIn("Screening", solution_topic_categories(variant))

    def test_transaction_keyfields_are_not_misclassified_as_screening(self) -> None:
        self.assertEqual(
            solution_topic_categories("Search for the keyfield: SPTR_TRANSACTION_VALUE > Between: 0"),
            ["Transactions and Deal Data"],
        )

    def test_crm_objective_prompt_is_classified_by_actual_solution(self) -> None:
        description = (
            "What is the objective of the meeting? Training for new user of Pro. "
            "What do they do? People data and business analytics."
        )

        self.assertEqual(solution_topic_categories(description), ["Product Training and Learning"])

    def test_empty_crm_wish_list_answer_is_not_a_solution(self) -> None:
        description = "What would they love to have? NA Other qualitative inputs, feedback, positive comments... NA"

        self.assertTrue(is_non_solution_entry(description))
        self.assertEqual(solution_topic_categories(description), [])

    def test_private_equity_and_api_request_has_two_relevant_topics(self) -> None:
        self.assertEqual(
            solution_topic_categories("Looking for PE firms in niche industries > API"),
            ["Private Markets and Specialized Datasets", "APIs and Data Integration"],
        )

    def test_product_fit_rationale_is_not_displayed_as_solution_category(self) -> None:
        rationale = (
            "as client is onto Data Science and Optimization, this would be the best "
            "product fit for her and her team."
        )

        self.assertTrue(is_non_solution_entry(rationale))
        self.assertEqual(solution_topic_categories(rationale), [])

    def test_other_unclassified_text_is_not_silently_dropped(self) -> None:
        self.assertFalse(is_non_solution_entry("A unique client-specific request with no matching topic"))

    def test_long_descriptions_return_each_matching_topic(self) -> None:
        description = (
            "Settings Dashboards Corporate Profiles Financials ChatIQ Peer Comps "
            "Ownership Investment and Market Research Doc Intelligence Transactions "
            "Deal Profile Transaction Comps Screening AI Assisted Screener Chart Builder News"
        )

        self.assertEqual(
            solution_topic_categories(description),
            [
                "AI Tools",
                "Company Profiles and Financial Data",
                "Screening",
                "Transactions and Deal Data",
                "Peer Comps and Valuation",
                "Dashboards, Watchlists and Alerts",
                "News, Research and Market Data",
                "Charting and Visualization",
                "Platform Navigation and Settings",
            ],
        )


if __name__ == "__main__":
    unittest.main()
