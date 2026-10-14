"""Collect news through an existing Chrome browser over its local CDP endpoint.

Discovery and article reading are separate: the caller selects worthwhile stories.
Only tabs created by this process are closed. No browser UI interaction is needed.
"""

import argparse
import asyncio
import hashlib
import json
import os
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from playwright.async_api import async_playwright

SCRIPT_DIR = Path(__file__).resolve().parent


def default_cache_dir():
    override = os.environ.get("NEWS_BRIEFING_CACHE")
    if override:
        return Path(override).expanduser()
    if os.name == "nt":
        root = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(root) / "NewsBriefing"
    root = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(root) / "news-briefing"


DEFAULT_CACHE = default_cache_dir()
TRACKING_KEYS = {"mod", "srnd", "module", "pgtype", "tpcc", "utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term", "syn-25a6b1a6"}

EXTRACT = r"""() => {
  const clean = node => {
    const copy = node.cloneNode(true);
    copy.querySelectorAll('script,style,nav,footer,form').forEach(x => x.remove());
    return copy.textContent.replace(/\s+/g, ' ').trim();
  };
  const selectors = ['[name="articleBody"]', '[itemprop="articleBody"]',
    '[data-testid="article-body"]', '.article__body', '.article-body',
    '.article-content', '.body__inner-container', '.story-body', '.post-content',
    '#article-body-preview', '#article-body', '#content--body',
    '.wysiwyg--all-content', '.t-content__body', '.ArticleBody-articleBody',
    '.post-body-content', '#news-body', '.article__content', 'article'];
  const blocks = [];
  for (const selector of selectors) {
    for (const node of document.querySelectorAll(selector)) {
      const paragraphs = [...node.querySelectorAll('p')].map(clean).filter(t => t.length >= 60);
      const text = node.innerText || clean(node);
      if (text.trim()) blocks.push({selector, text, paragraphs});
    }
  }
  const metadata = Object.fromEntries([...document.querySelectorAll('meta')]
    .map(m => [m.getAttribute('property') || m.name, m.content]).filter(x => x[0]));
  const canonical = document.querySelector('link[rel="canonical"]')?.href;
  const links = [...document.querySelectorAll('a[href]')].map(a => ({
    url: a.href, title: clean(a) || a.getAttribute('aria-label') || '',
    date: a.closest('article')?.querySelector('time')?.dateTime || ''
  })).filter(a => a.title.length > 18 && a.title.length < 500);
  // The Economist can serve an article teaser with no visible subscription
  // notice. Its server-rendered data explicitly says whether it is gated.
  let publisher_paywall = false;
  if (/(^|\.)economist\.com$/.test(location.hostname)) {
    const nextData = document.querySelector('script#__NEXT_DATA__')?.textContent;
    if (nextData) {
      try {
        const props = JSON.parse(nextData).props?.pageProps || {};
        publisher_paywall = props.walled === true && props.auth?.isSubscriber === false;
      } catch (_) { /* Not every page contains article data. */ }
    }
  }
  return {url:location.href, canonical, title:document.title, metadata, blocks, links,
    structured_data:[...document.querySelectorAll('script[type="application/ld+json"]')].map(s => s.textContent),
    publisher_paywall,
    challenge_detected:[...document.scripts].some(s => s.src.includes('captcha-delivery.com')),
    dates:[...document.querySelectorAll('time')].map(t => ({date:t.dateTime,text:t.innerText})),
    body_hint:(document.body?.innerText || '').slice(0,6000)};
}"""


def canonical_url(url):
    parts = urlsplit(url)
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
             if k not in TRACKING_KEYS and not k.startswith("utm_")]
    return urlunsplit((parts.scheme, parts.netloc.lower(), parts.path, urlencode(query), ""))


def economist_mirror_urls(url):
    """Try known text mirrors only for dated Economist articles."""
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or parts.hostname not in ("economist.com", "www.economist.com"):
        return ()
    if not re.search(r"/20\d{2}/\d{2}/\d{2}/", parts.path):
        return ()
    article_url = canonical_url(url)
    return (f"https://freedium-mirror.cfd/{article_url}",
            f"https://wallhop.io/{article_url}")


def mirror_matches_article(article, mirror):
    """Avoid accepting a mirror's generic landing page as article content."""
    if mirror.get("status") != "readable":
        return False
    original_title = article.get("title", "").strip().lower()
    mirror_title = mirror.get("title", "").strip().lower()
    if original_title and original_title != "economist.com":
        return original_title in mirror_title
    return False


def classify(data):
    if data.get("url", "").startswith("chrome-error://"):
        return "error", "Browser network error page; check connectivity and proxy configuration"
    hint = (data.get("title", "") + "\n" + data.get("body_hint", "")).lower()
    if data.get("challenge_detected") or re.search(r"are you a robot|we.ve detected unusual activity|verify you are human|access denied|your access has been blocked|checking your browser|complete the captcha|enable javascript and cookies|正在进行安全验证|验证您不是自动程序", hint):
        return "blocked", "Verification or access-control page"
    if data.get("publisher_paywall"):
        return "paywall", "Publisher returned only a subscription-gated article teaser"
    article_hint = hint + "\n" + "\n".join(block.get("text", "") for block in data.get("blocks", [])).lower()
    if re.search(r"subscribe to read|subscribe to unlock|subscription required|continue reading this article with|subscribe to continue reading|you have reached your.*limit|you.ve reached your.*limit|you.ve accessed an article available only to subscribers|the rest is for subscribers only|to enjoy the rest of this story", article_hint):
        return "paywall", "Subscription page remains"
    blocks = data.get("blocks", [])
    if not blocks:
        return "incomplete", "No article body found"
    # Count substantive paragraphs, not navigation or the total page size.
    best = max(blocks, key=lambda block: sum(len(p) for p in block["paragraphs"]))
    paragraphs = best["paragraphs"]
    if len(paragraphs) >= 3 and sum(map(len, paragraphs)) >= 900:
        return "readable", "Article paragraphs available; editorial review still required"
    return "incomplete", "Only a teaser or too little article text"


def publication_date(data):
    metadata = data.get("metadata", {})
    for key in ("article:published_time", "article.published", "article_published_time", "parsely-pub-date", "date"):
        if metadata.get(key):
            return metadata[key]
    for raw in data.get("structured_data", []):
        try:
            nodes = json.loads(raw)
        except (ValueError, TypeError):
            continue
        nodes = nodes if isinstance(nodes, list) else [nodes]
        for node in nodes:
            if isinstance(node, dict) and "@graph" in node:
                nodes.extend(node["@graph"])
            if isinstance(node, dict) and node.get("datePublished"):
                return node["datePublished"]
    # Event widgets can precede the article. Ignore empty, unrelated time tags.
    for item in data.get("dates", []):
        if item.get("date") and item.get("text", "").strip():
            return item["date"]
    match = re.search(r"/(20\d{2})/(\d{2})/(\d{2})/", data.get("url", ""))
    return "-".join(match.groups()) if match else ""


def candidates(data, source, limit, since=None):
    found = {}
    for link in data.get("links", []):
        host = urlsplit(link["url"]).hostname or ""
        if host != source["domain"] and not host.endswith("." + source["domain"]):
            continue
        if not re.search(source["article_pattern"], link["url"], re.I):
            continue
        if re.search(r"/(?:videos?|podcasts?)/", link["url"], re.I):
            continue
        date_match = re.search(r"/(20\d{2})/(\d{2})/(\d{2})/", link["url"])
        if since and date_match:
            try:
                published = datetime(*map(int, date_match.groups())).date()
            except ValueError:
                continue
            if published < since:
                continue
        url = canonical_url(link["url"])
        if url not in found:
            found[url] = {"source": source["name"], "url": link["url"], "canonical": url,
                          "title": link["title"], "date": link.get("date", "")}
    return list(found.values())[:limit]


def cache_path(cache_dir, kind, url):
    digest = hashlib.sha256(canonical_url(url).encode()).hexdigest()
    return cache_dir / kind / (digest + ".json")


async def collect(args):
    cache_dir = Path(args.cache)
    sources = json.loads(Path(args.sources).read_text(encoding="utf-8"))
    if args.discover:
        jobs = [{"url": source["url"], "source": source["name"], "config": source} for source in sources]
    else:
        jobs = []
        if args.input:
            incoming = json.loads(Path(args.input).read_text(encoding="utf-8"))
            incoming = incoming.get("candidates", incoming.get("results", [])) if isinstance(incoming, dict) else incoming
            jobs.extend({"url": item} if isinstance(item, str) else item for item in incoming)
        jobs.extend({"url": url} for url in args.urls)
        if not jobs:
            raise ValueError("Use --discover, --input, or --urls")
    jobs = list({canonical_url(job["url"]): job for job in jobs}.values())
    started = time.monotonic()
    global_limit = asyncio.Semaphore(args.concurrency)
    domain_limits = {}
    kind = "discovery" if args.discover else "articles"
    since = (datetime.now(timezone(timedelta(hours=8))) - timedelta(days=args.days)).date()

    async with async_playwright() as playwright:
        browser = await playwright.chromium.connect_over_cdp(args.endpoint)
        session = await browser.new_browser_cdp_session()
        baseline_pages = {page for context in browser.contexts for page in context.pages}
        page_ids = {}

        async def one(job):
            url = job["url"]
            host = urlsplit(url).hostname or ""
            # Sibling subdomains share one slot for configured publishers.
            domain = next((s["domain"] for s in sources if host == s["domain"] or host.endswith("." + s["domain"])), host)
            domain_limit = domain_limits.setdefault(domain, asyncio.Semaphore(1))
            async with domain_limit, global_limit:
                path = cache_path(cache_dir, kind, url)
                cached = None
                if path.exists() and not args.refresh:
                    try:
                        cached = json.loads(path.read_text(encoding="utf-8"))
                    except (OSError, ValueError):
                        pass
                ttl = 900 if args.discover else 86400
                if cached and cached.get("status") != "readable":
                    ttl = 900
                if cached and time.time() - cached.get("cached_at", 0) < ttl:
                    result = {**cached, "cache_hit": True, "elapsed_seconds": 0}
                    if args.discover:
                        links = [{"url": item["url"], "title": item["title"], "date": item.get("date", "")}
                                 for item in result.get("candidates", [])]
                        result["candidates"] = candidates({"links": links}, job["config"], args.limit, since)
                    result["published_at"] = result.get("published_at") or publication_date(result)
                    print(json.dumps({"source": result.get("source"), "status": result["status"], "cache_hit": True, "url": url}), flush=True)
                    return result

                begin = time.monotonic()
                target_id = None
                source_name = next((s["name"] for s in sources if s["domain"] == domain), domain)
                result = {"requested_url": url, "source": job.get("source", source_name), "cache_hit": False}
                try:
                    created = await session.send("Target.createTarget", {"url": url, "background": True})
                    target_id = created["targetId"]
                    page = None
                    deadline = begin + args.timeout
                    # Match by CDP target ID so extension redirects cannot lose the page.
                    while page is None and time.monotonic() < deadline:
                        for context in browser.contexts:
                            for candidate in context.pages:
                                if candidate in baseline_pages:
                                    continue
                                if candidate in page_ids:
                                    if page_ids[candidate] == target_id:
                                        page = candidate
                                        break
                                    continue
                                candidate_session = await context.new_cdp_session(candidate)
                                try:
                                    info = await candidate_session.send("Target.getTargetInfo")
                                    page_ids[candidate] = info["targetInfo"]["targetId"]
                                    if info["targetInfo"]["targetId"] == target_id:
                                        page = candidate
                                        break
                                finally:
                                    await candidate_session.detach()
                            if page:
                                break
                        if not page:
                            await asyncio.sleep(0.2)
                    if page is None:
                        raise TimeoutError("Created tab did not become available")
                    await page.wait_for_load_state("domcontentloaded", timeout=max(500, int((deadline-time.monotonic())*1000)))
                    last_size = None
                    stable = 0
                    data = {}
                    while time.monotonic() < deadline:
                        try:
                            data = await page.evaluate(EXTRACT)
                        except Exception:
                            # Some extension rules navigate to an alternate page.
                            await asyncio.sleep(0.5)
                            continue
                        size = sum(len(block["text"]) for block in data["blocks"]) if not args.discover else len(data["links"])
                        stable = stable + 1 if size == last_size else 0
                        last_size = size
                        status, reason = classify(data)
                        age = time.monotonic() - begin
                        if args.discover and data["links"] and stable >= 2 and age >= 3:
                            break
                        if not args.discover and status == "readable" and stable >= 2 and age >= 3:
                            break
                        if status in ("blocked", "error") and age >= 4:
                            break
                        # Give the extension time to restore delayed content.
                        if status == "paywall" and age >= 8 and stable >= 2:
                            break
                        await asyncio.sleep(0.6)
                    result.update(data)
                    result["published_at"] = publication_date(data)
                    result["status"], result["reason"] = classify(data)
                    if args.discover:
                        result["candidates"] = candidates(data, job["config"], args.limit, since)
                        if result["candidates"] and result["status"] != "blocked":
                            result["status"] = "discovered"
                            result["reason"] = "Candidate links found; article bodies not read yet"
                    elif data.get("blocks"):
                        best = max(data["blocks"], key=lambda block: sum(len(p) for p in block["paragraphs"]))
                        result["text"] = best["text"]
                        result["paragraphs"] = best["paragraphs"]
                    result.pop("links", None)
                    result.pop("blocks", None)
                except Exception as error:
                    result.update(status="error", reason=str(error)[:300])
                finally:
                    if target_id:
                        try:
                            await session.send("Target.closeTarget", {"targetId": target_id})
                        except Exception:
                            pass
                result["elapsed_seconds"] = round(time.monotonic() - begin, 2)
                result["cached_at"] = time.time()
                path.parent.mkdir(parents=True, exist_ok=True)
                temp = path.with_suffix(".tmp")
                temp.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
                temp.replace(path)
                print(json.dumps({"source": result["source"], "status": result["status"], "elapsed_seconds": result["elapsed_seconds"], "url": url}), flush=True)
                return result

        results = await asyncio.gather(*(one(job) for job in jobs))
        if not args.discover:
            async def try_mirrors(job, article):
                if article.get("status") not in ("paywall", "incomplete", "blocked"):
                    return article
                for mirror_url in economist_mirror_urls(job["url"]):
                    mirrored = await one({"url": mirror_url})
                    if mirror_matches_article(article, mirrored):
                        article.update(
                            status="readable",
                            reason="Article paragraphs retrieved from mirror; editorial review still required",
                            original_status=article["status"],
                            retrieved_via=mirror_url,
                            text=mirrored["text"],
                            paragraphs=mirrored["paragraphs"],
                            body_hint=mirrored.get("body_hint", ""),
                        )
                        return article
                return article

            results = await asyncio.gather(*(try_mirrors(job, article) for job, article in zip(jobs, results)))
        await session.detach()
    report = {"collected_at": datetime.now(timezone.utc).isoformat(),
              "elapsed_seconds": round(time.monotonic()-started, 2), "results": results}
    if args.discover:
        report["candidates"] = [candidate for result in results for candidate in result.get("candidates", [])]
    output = Path(args.output) if args.output else cache_dir / ("discovery-latest.json" if args.discover else "articles-latest.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    counts = {status: sum(result["status"] == status for result in results) for status in sorted({r["status"] for r in results})}
    print(json.dumps({"output": str(output), "elapsed_seconds": report["elapsed_seconds"], "counts": counts,
                      "candidates": len(report.get("candidates", []))}), flush=True)
    return report


async def run(args):
    discovery_args = argparse.Namespace(**vars(args))
    if args.discover and args.read_per_source:
        discovery_args.output = None
    report = await collect(discovery_args)
    if args.discover and args.read_per_source:
        urls = [item["url"] for source in report["results"]
                for item in source.get("candidates", [])[:args.read_per_source]]
        if urls:
            reading_args = argparse.Namespace(**vars(args))
            reading_args.discover = False
            reading_args.input = None
            reading_args.urls = urls
            await collect(reading_args)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--discover", action="store_true")
    parser.add_argument("--sources", default=str(SCRIPT_DIR / "sources.json"))
    parser.add_argument("--input", help="JSON URL list, candidate list, or discovery report")
    parser.add_argument("--urls", nargs="*", default=[])
    parser.add_argument("--output")
    parser.add_argument("--cache", default=str(DEFAULT_CACHE))
    parser.add_argument("--endpoint", default=os.environ.get("NEWS_BRIEFING_CDP", "http://127.0.0.1:9230"))
    parser.add_argument("--concurrency", type=int, default=3, choices=range(1, 7))
    parser.add_argument("--timeout", type=float, default=18)
    parser.add_argument("--limit", type=int, default=12, help="Maximum candidate links per source")
    parser.add_argument("--days", type=int, default=7, help="Ignore older candidates when a URL contains a publication date")
    parser.add_argument("--read-per-source", type=int, default=0, help="After discovery, automatically read this many candidates per publisher")
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    if args.timeout <= 0 or args.limit <= 0 or args.days <= 0 or args.read_per_source < 0:
        parser.error("timeout, limit and days must be positive; read-per-source must not be negative")
    if args.read_per_source and not args.discover:
        parser.error("read-per-source requires --discover")
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
