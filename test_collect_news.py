import unittest
from datetime import date

from collect_news import (canonical_url, candidates, classify, economist_mirror_urls,
                          mirror_matches_article, publication_date)


class ArticleAccessTests(unittest.TestCase):
    def article(self, **extra):
        return {"title": "Reported news", "body_hint": "Subscribe | Sign in",
                "blocks": [{"selector": "article", "text": "Body",
                            "paragraphs": ["Detailed reporting. " * 25] * 4}], **extra}

    def test_verification_page_never_counts_as_article(self):
        self.assertEqual(classify(self.article(title="Bloomberg - Are you a robot?"))[0], "blocked")

    def test_browser_network_error_is_not_an_incomplete_article(self):
        data = {"url": "chrome-error://chromewebdata/", "title": "www.example.com",
                "body_hint": "ERR_CONNECTION_TIMED_OUT", "blocks": []}
        self.assertEqual(classify(data)[0], "error")

    def test_subscription_teaser_never_counts_as_article(self):
        self.assertEqual(classify(self.article(title="Subscribe to read"))[0], "paywall")

    def test_economist_explicit_server_paywall_takes_precedence_over_teaser(self):
        data = self.article(publisher_paywall=True)
        self.assertEqual(classify(data),
                         ("paywall", "Publisher returned only a subscription-gated article teaser"))

    def test_publisher_without_paywall_remains_readable(self):
        self.assertEqual(classify(self.article(publisher_paywall=False))[0], "readable")

    def test_economist_mirrors_only_for_dated_articles(self):
        article = "https://www.economist.com/china/2026/10/12/example?utm_source=foo"
        self.assertEqual(economist_mirror_urls(article), (
            "https://freedium-mirror.cfd/https://www.economist.com/china/2026/10/12/example",
            "https://wallhop.io/https://www.economist.com/china/2026/10/12/example"))
        self.assertEqual(economist_mirror_urls("https://www.economist.com/"), ())
        self.assertEqual(economist_mirror_urls("https://economist.com.attacker.test/2026/10/12/x"), ())

    def test_mirror_requires_article_title_not_a_generic_readable_page(self):
        article = {"title": "China is turning trash into treasure on a vast scale"}
        mirror = {"status": "readable", "title": "China is turning trash into treasure on a vast scale - Freedium"}
        self.assertTrue(mirror_matches_article(article, mirror))
        self.assertFalse(mirror_matches_article(article, {"status": "readable", "title": "Popular news - Freedium"}))
        self.assertFalse(mirror_matches_article(article, {**mirror, "status": "paywall"}))

    def test_paywall_with_recommended_article_paragraphs_is_not_readable(self):
        data = self.article(body_hint="A teaser. Continue reading this article with a Barron's subscription. What to Read Next")
        self.assertEqual(classify(data)[0], "paywall")

    def test_large_navigation_page_is_not_article_text(self):
        data = self.article(blocks=[{"text": "Navigation " * 2000, "paragraphs": []}])
        self.assertEqual(classify(data)[0], "incomplete")

    def test_short_teaser_is_incomplete(self):
        data = self.article(blocks=[{"text": "Intro", "paragraphs": ["Intro " * 20]}])
        self.assertEqual(classify(data)[0], "incomplete")

    def test_generic_subscribe_link_and_captcha_topic_are_not_access_blocks(self):
        self.assertEqual(classify(self.article(title="Why AI can solve CAPTCHA puzzles"))[0], "readable")

    def test_datadome_and_atlantic_verification_pages_are_blocked(self):
        self.assertEqual(classify(self.article(challenge_detected=True))[0], "blocked")
        self.assertEqual(classify(self.article(title="Your access has been blocked"))[0], "blocked")

    def test_chinese_security_challenge_is_blocked(self):
        data = {"title": "请稍候…", "body_hint": "正在进行安全验证，在验证您不是自动程序期间，将显示此页面。", "blocks": []}
        self.assertEqual(classify(data)[0], "blocked")

    def test_caixin_subscription_notice_is_paywall(self):
        data = self.article(body_hint="You've accessed an article available only to subscribers. Subscribe today for just $.99.")
        self.assertEqual(classify(data)[0], "paywall")

    def test_subscription_notice_after_body_hint_is_paywall(self):
        for notice in ("You have 73.92% of this article left to read. The rest is for subscribers only.",
                       "To enjoy the rest of this story, please consider signing up for a subscription."):
            with self.subTest(notice=notice):
                data = self.article()
                data['blocks'][0]['text'] = "Teaser text. " + notice
                self.assertEqual(classify(data)[0], "paywall")

    def test_tracking_dedup_keeps_content_identifiers(self):
        self.assertEqual(canonical_url("https://example.com/story?id=7&utm_source=x#comments"),
                         "https://example.com/story?id=7")
        self.assertNotEqual(canonical_url("https://example.com/story?id=7"),
                            canonical_url("https://example.com/story?id=8"))

    def test_discovery_rejects_other_domains_and_deduplicates_tracking_links(self):
        data = {"links": [
            {"title": "A long headline", "url": "https://news.example.com/article/7?utm_source=x"},
            {"title": "A duplicate headline", "url": "https://news.example.com/article/7?utm_source=y"},
            {"title": "Wrong host", "url": "https://example.com.attacker.test/article/8"},
        ]}
        result = candidates(data, {"name": "Example", "domain": "example.com", "article_pattern": "/article/"}, 12)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["canonical"], "https://news.example.com/article/7")

    def test_old_featured_stories_and_videos_are_not_recent_article_candidates(self):
        data = {"links": [
            {"title": "Old featured story", "url": "https://example.com/2026/01/12/old-story/"},
            {"title": "Recent video", "url": "https://example.com/video/2026/10/08/a-video/"},
            {"title": "Recent story", "url": "https://example.com/2026/10/08/a-story/"},
        ]}
        result = candidates(data, {"name": "Example", "domain": "example.com", "article_pattern": "/2026/"},
                            12, since=date(2026, 10, 1))
        self.assertEqual([x["title"] for x in result], ["Recent story"])

    def test_publication_date_ignores_empty_future_event_tag(self):
        data = {"dates": [{"date": "2026-10-14", "text": ""},
                          {"date": "2026-10-07", "text": "October 7, 2026"}]}
        self.assertEqual(publication_date(data), "2026-10-07")

    def test_publication_metadata_takes_precedence_over_widgets(self):
        data = {"metadata": {"article:published_time": "2026-10-07T19:20:00Z"},
                "dates": [{"date": "2026-10-14", "text": "Next event"}]}
        self.assertEqual(publication_date(data), "2026-10-07T19:20:00Z")


if __name__ == "__main__":
    unittest.main()
