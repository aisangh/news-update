import unittest

from ai_news_finder.collectors import rss
from ai_news_finder.generators.report import _newsletter_brief, _story_summary


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

    def test_article_details_fall_back_to_multi_sentence_article_summary(self) -> None:
        title = "Gemini, ChatGPT, and Claude compared - Android Authority"
        snippets = [
            (
                "Android Authority compares paid AI chatbot subscriptions across Gemini, "
                "ChatGPT, and Claude, focusing on daily usefulness, mobile integration, "
                "reasoning quality, and which service offers the best value. Gemini stands "
                "out for Android integration and access to Google services, while ChatGPT "
                "is described as a stronger general-purpose assistant for research and "
                "polished answers. Claude is treated as especially useful for longer writing "
                "tasks and nuanced analysis, though its mobile experience may not be as "
                "deeply tied into the operating system. The article frames the winner around "
                "which subscription feels most useful day after day rather than raw model "
                "benchmarks alone."
            )
        ]

        summary = rss._best_article_summary(title, snippets)

        self.assertTrue(summary.startswith("Android Authority compares paid AI"))
        self.assertGreaterEqual(len(summary.split(".")), 4)

    def test_json_ld_article_body_is_available_for_detailed_summary(self) -> None:
        html = """
        <html><head>
        <script type="application/ld+json">
        {
          "@type": "NewsArticle",
          "description": "Short metadata for the article.",
          "articleBody": "Mashable reports that a new AI feature is rolling out to users this week. The article explains who can access it, what the launch changes, and why it matters for people already using competing AI tools. It also compares the product with rival assistants and notes where the experience still falls short. The piece closes by outlining what users should watch as the feature expands beyond the first launch markets."
        }
        </script>
        </head><body></body></html>
        """
        parser = rss._MetaSummaryParser()
        parser.feed(html)

        texts = rss._jsonld_article_texts(parser.json_ld_blocks)
        summary = rss._best_article_summary("Mashable AI feature rollout", texts)

        self.assertIn("Mashable reports", summary)
        self.assertIn("compares the product", summary)

    def test_newsletter_fallback_does_not_tell_reader_to_open_article_link(self) -> None:
        brief = _newsletter_brief({"title": "Sparse GNews story"})

        self.assertNotIn("open the article link", brief["takeaway"])
        self.assertNotIn("watchlist item", brief["takeaway"])


if __name__ == "__main__":
    unittest.main()
