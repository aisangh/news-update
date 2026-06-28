import unittest
from unittest.mock import patch

from ai_news_finder.collectors import rss
from ai_news_finder.generators.report import _newsletter_brief, _story_summary
from ai_news_finder.processors.dedup import group_stories
from ai_news_finder.processors.filter import filter_ai_stories
from ai_news_finder.processors.scorer import select_top_stories


class ArticleSummaryFallbackTests(unittest.TestCase):
    def test_report_does_not_use_feed_headline_as_summary_when_read_more_links_exist(self) -> None:
        story = {
            "title": "I pay for Gemini, ChatGPT, and Claude - Android Authority",
            "all_titles": [
                "I tried Claude, ChatGPT, and Copilot for a month to find a real Gemini alternative on Android Android Police"
            ],
            "read_more_links": [
                {
                    "url": "https://www.androidauthority.com/example",
                    "source": "Android Authority",
                }
            ],
            "all_summaries": [
                "I tried Claude, ChatGPT, and Copilot for a month to find a real Gemini alternative on Android Android Police"
            ],
        }

        summary = _story_summary(story)

        self.assertEqual(summary, "No summary available for this story.")

    def test_report_uses_detailed_summary_when_read_more_links_exist(self) -> None:
        story = {
            "title": "I pay for Gemini, ChatGPT, and Claude - Android Authority",
            "read_more_links": [
                {
                    "url": "https://www.androidauthority.com/example",
                    "source": "Android Authority",
                }
            ],
            "detailed_summary": (
                "Android Authority compares paid versions of Gemini, ChatGPT, and Claude "
                "after using all three subscriptions in everyday workflows. The article "
                "explains why Claude became the writer's default assistant for reminders, "
                "file cleanup, recurring tasks, and work that needs reliable first drafts. "
                "It also contrasts that experience with ChatGPT and Gemini, arguing that "
                "the winner is the service that keeps proving useful without repeated "
                "corrections or extra setup."
            ),
        }

        summary = _story_summary(story)

        self.assertIn("Android Authority compares paid versions", summary)
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

    def test_article_match_rejects_unrelated_same_person_story(self) -> None:
        title = "Pope Leo XIV to launch his first encyclical on artificial intelligence with Anthropic"
        unrelated = (
            "One Pokemon fan traveled across the land and searched far and wide to "
            "find Pope Leo XIV with a Popplio card in hand for a delightful interaction."
        )
        related = (
            "Pope Leo XIV and Anthropic co-founder Christopher Olah will launch an "
            "encyclical about artificial intelligence, human dignity, and AI safety."
        )

        self.assertFalse(rss._article_matches_title(title, unrelated))
        self.assertTrue(rss._article_matches_title(title, related))

    def test_article_title_match_rejects_related_but_wrong_article(self) -> None:
        expected = "Pope Leo XIV to launch his first encyclical on artificial intelligence with Anthropic"
        wrong = ["Pope Leo condemns use of AI warfare and the spiral of annihilation it brings"]
        right = ["Pope Leo XIV to launch his first encyclical, a document on artificial intelligence, with Anthropic's co-founder"]

        self.assertFalse(rss._article_title_matches(expected, wrong))
        self.assertTrue(rss._article_title_matches(expected, right))

    def test_newsletter_fallback_does_not_tell_reader_to_open_article_link(self) -> None:
        brief = _newsletter_brief({"title": "Sparse GNews story"})

        self.assertNotIn("open the article link", brief["takeaway"])
        self.assertNotIn("watchlist item", brief["takeaway"])

    def test_read_more_links_resolve_google_news_with_matching_source_home(self) -> None:
        story = group_stories([
            {
                "title": "OpenAI whistleblower ditches Nvidia - TheStreet",
                "url": "https://news.google.com/rss/articles/story-one?oc=5",
                "source": "TheStreet",
                "source_home": "https://www.thestreet.com",
                "summary": "",
            },
            {
                "title": "OpenAI whistleblower ditches Nvidia - Mashable",
                "url": "https://news.google.com/rss/articles/story-two?oc=5",
                "source": "Mashable",
                "source_home": "https://mashable.com",
                "summary": "",
            },
        ])[0]

        def fake_discover(title: str, source_home: str) -> str:
            host = source_home.removeprefix("https://www.").removeprefix("https://")
            return f"https://{host}/resolved-article"

        with patch.object(rss, "discover_article_url", side_effect=fake_discover):
            links = rss._read_more_links(story, limit=3)

        self.assertEqual(links[0]["url"], "https://thestreet.com/resolved-article")
        self.assertEqual(links[1]["url"], "https://mashable.com/resolved-article")

    def test_read_more_links_resolve_google_news_from_source_label_when_home_missing(self) -> None:
        story = {
            "title": "I pay for Gemini, ChatGPT, and Claude - Android Authority",
            "all_urls": ["https://news.google.com/rss/articles/story-one?oc=5"],
            "all_sources": ["Android Authority"],
            "all_source_homes": [""],
        }

        with patch.object(rss, "discover_article_url", return_value="https://www.androidauthority.com/real-article") as discover:
            links = rss._read_more_links(story, limit=1)

        self.assertEqual(links[0]["url"], "https://www.androidauthority.com/real-article")
        discover.assert_called_once_with(
            "I pay for Gemini, ChatGPT, and Claude - Android Authority",
            "https://www.androidauthority.com",
        )

    def test_publisher_site_search_extracts_matching_article_link(self) -> None:
        html = """
        <html><body>
          <a href="https://www.androidauthority.com/gemini-chatgpt-claude-clear-winner-3666267/">
            I pay for Gemini, ChatGPT, and Claude, and there's a clear winner
          </a>
        </body></html>
        """

        class Response:
            text = html

            def raise_for_status(self) -> None:
                return None

        class Session:
            def get(self, *args, **kwargs):
                return Response()

        with patch.object(rss, "_session", return_value=Session()):
            url = rss._discover_from_publisher_search(
                "I pay for Gemini, ChatGPT, and Claude - Android Authority",
                "https://www.androidauthority.com",
            )

        self.assertEqual(
            url,
            "https://www.androidauthority.com/gemini-chatgpt-claude-clear-winner-3666267/",
        )

    def test_known_slug_discovery_for_pbs_newshour(self) -> None:
        expected_url = (
            "https://www.pbs.org/newshour/world/"
            "pope-leo-xiv-to-launch-his-first-encyclical-on-artificial-intelligence"
        )

        with patch.object(rss, "fetch_article_details", return_value={"url": expected_url}):
            url = rss._discover_from_known_slug(
                "Pope Leo XIV to launch his first encyclical on artificial intelligence - PBS",
                "https://www.pbs.org",
            )

        self.assertEqual(url, expected_url)

    def test_enrichment_uses_raw_article_text_for_longer_summary(self) -> None:
        story = {
            "title": "OpenAI whistleblower ditches Nvidia - TheStreet",
            "url": "https://www.thestreet.com/openai-whistleblower-ditches-nvidia",
            "all_urls": ["https://www.thestreet.com/openai-whistleblower-ditches-nvidia"],
            "sources": ["TheStreet"],
            "all_sources": ["TheStreet"],
            "all_source_homes": ["https://www.thestreet.com"],
            "summary": "OpenAI whistleblower ditches Nvidia - TheStreet",
        }
        article_text = (
            "TheStreet reports that an OpenAI whistleblower has shifted attention away "
            "from Nvidia after reassessing which AI infrastructure companies look most "
            "exposed to changing demand. The article explains that the investor argument "
            "centers on whether the market has already priced in Nvidia's dominant role "
            "in AI accelerators. It then walks through why software, cloud infrastructure, "
            "and newer chip competitors could benefit if spending patterns broaden beyond "
            "one supplier. The piece also notes that Nvidia remains central to the current "
            "AI buildout, but the whistleblower's move is framed as a bet on the next phase "
            "of the trade rather than a rejection of AI demand. The conclusion focuses on "
            "what investors should watch next, including earnings guidance, hyperscaler "
            "capital spending, and signs that AI hardware demand is spreading across more "
            "vendors."
        )

        with patch.object(rss, "fetch_article_details", return_value={
            "url": story["url"],
            "article_text": article_text,
            "detailed_summary": "",
            "meta_summary": "Short meta summary.",
        }):
            rss.enrich_story_summaries([story])

        self.assertGreaterEqual(len(story["detailed_summary"].split()), 90)
        self.assertIn("hyperscaler capital spending", story["detailed_summary"])

    def test_enrichment_rejects_short_metadata_as_detailed_summary(self) -> None:
        story = {
            "title": "Pope Leo XIV to launch his first encyclical on artificial intelligence - PBS",
            "url": "https://www.pbs.org/example",
            "all_urls": ["https://www.pbs.org/example"],
            "sources": ["PBS"],
            "all_sources": ["PBS"],
            "all_source_homes": ["https://www.pbs.org"],
            "summary": "The Pope Is Hooking Up With a Co-Founder of Anthropic for Collab on AI Gizmodo",
            "all_summaries": [
                "The Pope Is Hooking Up With a Co-Founder of Anthropic for Collab on AI Gizmodo"
            ],
        }

        with patch.object(rss, "fetch_article_details", return_value={
            "url": story["url"],
            "article_text": "",
            "detailed_summary": "The Pope Is Hooking Up With a Co-Founder of Anthropic for Collab on AI Gizmodo",
            "meta_summary": "Short metadata only.",
        }):
            rss.enrich_story_summaries([story])

        self.assertNotIn("detailed_summary", story)
        self.assertEqual(_story_summary(story), "No summary available for this story.")

    def test_filter_excludes_stock_market_ai_noise(self) -> None:
        stories = [
            {
                "title": "OpenAI stock jumps after earnings beat and analyst upgrade",
                "summary": "The stock gained after investors reacted to quarterly revenue and guidance.",
            },
            {
                "title": "OpenAI launches a new reasoning model for developers",
                "summary": "The company shipped a new model with stronger coding and agentic workflows.",
            },
        ]

        filtered = filter_ai_stories(stories)

        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["title"], "OpenAI launches a new reasoning model for developers")

    def test_select_top_stories_prefers_richer_story_when_sources_match(self) -> None:
        groups = [
            {
                "title": "OpenAI model release",
                "url": "https://example.com/ai-model",
                "sources": ["TechCrunch", "The Verge", "Wired"],
                "source_count": 3,
                "summary": "OpenAI released a new model.",
                "all_titles": ["OpenAI model release"],
                "all_summaries": ["OpenAI released a new model."],
                "all_urls": ["https://example.com/ai-model"],
            },
            {
                "title": "OpenAI model release",
                "url": "https://example.com/ai-model-detailed",
                "sources": ["TechCrunch", "The Verge", "Wired"],
                "source_count": 3,
                "summary": (
                    "OpenAI released a new model that improves coding, reasoning, and "
                    "tool use across agent workflows."
                ),
                "detailed_summary": (
                    "OpenAI released a new model that improves coding, reasoning, and "
                    "tool use across agent workflows. The launch adds stronger planning "
                    "behavior, better instruction following, and more reliable output for "
                    "developers building AI products."
                ),
                "all_titles": ["OpenAI model release"],
                "all_summaries": [
                    "OpenAI released a new model that improves coding, reasoning, and tool use across agent workflows.",
                ],
                "all_urls": ["https://example.com/ai-model-detailed"],
                "read_more_links": [{"url": "https://example.com/ai-model-detailed"}],
            },
        ]

        selected, _stats = select_top_stories(groups, limit=1)

        self.assertEqual(selected[0]["url"], "https://example.com/ai-model-detailed")

    def test_select_top_stories_balances_company_and_topic_spread(self) -> None:
        groups = [
            {
                "title": "OpenAI releases new model for developers",
                "url": "https://example.com/openai-1",
                "sources": ["TechCrunch", "The Verge", "Wired"],
                "source_count": 3,
                "summary": "OpenAI released a new model for developers.",
                "all_titles": ["OpenAI releases new model for developers"],
                "all_summaries": ["OpenAI released a new model for developers."],
                "all_urls": ["https://example.com/openai-1"],
            },
            {
                "title": "OpenAI updates ChatGPT memory and search",
                "url": "https://example.com/openai-2",
                "sources": ["Reuters", "The Verge", "BBC"],
                "source_count": 3,
                "summary": "OpenAI improved ChatGPT memory and search.",
                "all_titles": ["OpenAI updates ChatGPT memory and search"],
                "all_summaries": ["OpenAI improved ChatGPT memory and search."],
                "all_urls": ["https://example.com/openai-2"],
            },
            {
                "title": "Anthropic opens up a new safety feature",
                "url": "https://example.com/anthropic-1",
                "sources": ["Reuters", "Fortune", "CNBC"],
                "source_count": 3,
                "summary": "Anthropic opened up a new safety feature.",
                "all_titles": ["Anthropic opens up a new safety feature"],
                "all_summaries": ["Anthropic opened up a new safety feature."],
                "all_urls": ["https://example.com/anthropic-1"],
            },
            {
                "title": "Apple Vision Pro exec is reportedly leaving for OpenAI",
                "url": "https://example.com/apple-openai",
                "sources": ["TechCrunch", "Bloomberg.com", "9to5Mac"],
                "source_count": 3,
                "summary": "Apple hardware talent is moving to OpenAI.",
                "all_titles": ["Apple Vision Pro exec is reportedly leaving for OpenAI"],
                "all_summaries": ["Apple hardware talent is moving to OpenAI."],
                "all_urls": ["https://example.com/apple-openai"],
            },
            {
                "title": "China's Zhipu is closing in on top U.S. AI models",
                "url": "https://example.com/zhipu",
                "sources": ["CNBC", "AP News"],
                "source_count": 2,
                "summary": "Zhipu is closing in on U.S. AI models.",
                "all_titles": ["China's Zhipu is closing in on top U.S. AI models"],
                "all_summaries": ["Zhipu is closing in on U.S. AI models."],
                "all_urls": ["https://example.com/zhipu"],
            },
        ]

        selected, _stats = select_top_stories(groups, limit=4)

        self.assertLessEqual(
            sum(1 for story in selected if "openai" in story["title"].lower()),
            2,
        )
        self.assertTrue(any("anthropic" in story["title"].lower() for story in selected))
        self.assertTrue(any("zhipu" in story["title"].lower() for story in selected))

    def test_filter_excludes_press_release_and_classroom_noise(self) -> None:
        stories = [
            {
                "title": "OpenAI launches new AI teaching tools in a press release",
                "summary": "A press release says the company is rolling out training for schools.",
            },
            {
                "title": "OpenAI launches a new reasoning model for developers",
                "summary": "The company shipped a new model with stronger coding and agentic workflows.",
            },
        ]

        filtered = filter_ai_stories(stories)

        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["title"], "OpenAI launches a new reasoning model for developers")

    def test_publisher_boilerplate_is_removed_from_summary(self) -> None:
        text = (
            "Paul Meade is leaving for OpenAI. Previously, he worked as a tech reporter "
            "at Adweek. You can contact or verify outreach from Anthony by emailing "
            "anthony.ha@techcrunch.com. The first StrictlyVC of 2026 hits SF on April 30."
        )

        cleaned = rss._clean_feed_text(text)

        self.assertNotIn("Previously", cleaned)
        self.assertNotIn("contact or verify outreach", cleaned)
        self.assertNotIn("StrictlyVC", cleaned)


if __name__ == "__main__":
    unittest.main()
