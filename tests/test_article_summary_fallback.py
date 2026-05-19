import unittest

from ai_news_finder.collectors import rss
from ai_news_finder.generators.report import _story_summary


class ArticleSummaryFallbackTests(unittest.TestCase):
    def test_report_uses_summary_candidate_when_read_more_links_exist(self) -> None:
        story = {
            "title": "I pay for Gemini, ChatGPT, and Claude - Android Authority",
            "read_more_links": [
                {
                    "url": "https://www.androidauthority.com/example",
                    "source": "Android Authority",
                }
            ],
            "all_summaries": [
                (
                    "The comparison weighs paid versions of Gemini, ChatGPT, and Claude "
                    "against everyday assistant tasks, highlighting where each product "
                    "feels strongest for mobile users and research workflows."
                )
            ],
        }

        summary = _story_summary(story)

        self.assertIn("comparison weighs paid versions", summary)
        self.assertNotIn("No summary available", summary)

    def test_article_details_fall_back_to_best_metadata_summary(self) -> None:
        title = "Gemini, ChatGPT, and Claude compared - Android Authority"
        snippets = [
            (
                "Android Authority compares paid AI chatbot subscriptions across "
                "Gemini, ChatGPT, and Claude, focusing on daily usefulness, mobile "
                "integration, reasoning quality, and which service offers the best value."
            )
        ]

        summary = rss._best_article_summary(title, snippets)

        self.assertTrue(summary.startswith("Android Authority compares paid AI"))


if __name__ == "__main__":
    unittest.main()
