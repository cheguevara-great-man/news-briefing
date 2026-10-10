import json
import os
import re
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit

from collect_news import SCRIPT_DIR, default_cache_dir


class ConfigurationTests(unittest.TestCase):
    def test_explicit_cache_directory_wins(self):
        news_home = Path.home()
        with patch.dict(os.environ, {"NEWS_BRIEFING_CACHE": "~/my-news-cache",
                                    "USERPROFILE": str(news_home), "HOME": str(news_home)}, clear=True):
            self.assertEqual(default_cache_dir(), news_home / "my-news-cache")

    @unittest.skipUnless(os.name == 'nt', 'Windows cache path')
    def test_windows_cache_is_outside_repository(self):
        news_home = Path.home()
        with patch.dict(os.environ, {"LOCALAPPDATA": str(news_home / 'local-app-data')}, clear=True):
            self.assertEqual(default_cache_dir(), news_home / 'local-app-data' / 'NewsBriefing')

    @unittest.skipIf(os.name == 'nt', 'Unix cache path')
    def test_xdg_cache_location(self):
        news_home = Path.home()
        with patch.dict(os.environ, {"XDG_CACHE_HOME": str(news_home / 'xdg-cache')}, clear=True):
            self.assertEqual(default_cache_dir(), news_home / 'xdg-cache' / 'news-briefing')

    def test_sources_have_valid_patterns_and_matching_hosts(self):
        sources = json.loads((SCRIPT_DIR / 'sources.json').read_text(encoding='utf-8'))
        seen = set()
        for source in sources:
            with self.subTest(source=source['name']):
                host = urlsplit(source['url']).hostname
                self.assertTrue(host == source['domain'] or host.endswith('.' + source['domain']))
                re.compile(source['article_pattern'])
                self.assertNotIn(source['url'], seen)
                seen.add(source['url'])

    def test_invalid_cli_settings_fail_before_browser_connection(self):
        for flags in (['--timeout', '0'], ['--days', '-1'], ['--read-per-source', '1']):
            with self.subTest(flags=flags):
                result = subprocess.run(
                    [sys.executable, str(SCRIPT_DIR / 'collect_news.py'), *flags],
                    capture_output=True, text=True, encoding='utf-8')
                self.assertEqual(result.returncode, 2)
                self.assertNotIn('Traceback', result.stderr)


if __name__ == '__main__':
    unittest.main()
