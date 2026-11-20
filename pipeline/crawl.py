


# """Step 1: polite crawler.
# - HTML pages: fetched with Crawl4AI (real browser, so JavaScript-rendered content is included)
#   by a few workers in parallel, but never faster than one request start per CRAWL_DELAY seconds
# - PDFs: found from links on crawled pages, downloaded with requests
# Rules: robots.txt respected (per host), delay between every request, public pages only.
# """
# import asyncio
# import hashlib
# import json
# import re
# import time
# from collections import deque
# from pathlib import Path
# from urllib.parse import urljoin, urlparse
# from urllib.robotparser import RobotFileParser

# import requests
# from bs4 import BeautifulSoup

# from .scope import Scope

# USER_AGENT = "TakeHomeRAGBot/1.0 (assessment project; polite crawler)"


# class Robots:
#     """robots.txt per host. If robots.txt cannot be read (network error / 5xx) we do NOT crawl that host."""

#     def __init__(self, session: requests.Session):
#         self.session = session
#         self.cache: dict[str, RobotFileParser | None] = {}

#     def _get(self, url: str):
#         p = urlparse(url)
#         origin = f"{p.scheme}://{p.netloc}"
#         if origin not in self.cache:
#             rp = RobotFileParser()
#             try:
#                 r = self.session.get(f"{origin}/robots.txt", timeout=15)
#                 if r.status_code == 200:
#                     rp.parse(r.text.splitlines())
#                 elif 400 <= r.status_code < 500:
#                     rp.parse([])  # no robots.txt -> everything allowed
#                 else:
#                     rp = None
#             except requests.RequestException:
#                 rp = None
#             if rp is None:
#                 print(f"  [robots] could not read robots.txt for {origin}; skipping that host")
#             self.cache[origin] = rp
#         return self.cache[origin]

#     def can_fetch(self, url: str) -> bool:
#         rp = self._get(url)
#         return bool(rp and rp.can_fetch(USER_AGENT, url))

#     def crawl_delay(self, url: str) -> float:
#         rp = self._get(url)
#         return float((rp.crawl_delay(USER_AGENT) if rp else 0) or 0)

#     def sitemaps(self, url: str) -> list[str]:
#         rp = self._get(url)
#         return list(rp.site_maps() or []) if rp else []


# def sitemap_urls(start_url: str, robots: Robots, session: requests.Session) -> list[str]:
#     p = urlparse(start_url)
#     queue = robots.sitemaps(start_url) or [f"{p.scheme}://{p.netloc}/sitemap.xml"]
#     seen, urls = set(), []
#     while queue and len(seen) < 30:
#         sm = queue.pop(0)
#         if sm in seen:
#             continue
#         seen.add(sm)
#         try:
#             r = session.get(sm, timeout=20)
#         except requests.RequestException:
#             continue
#         if r.status_code != 200:
#             continue
#         for loc in re.findall(r"<loc>\s*(.*?)\s*</loc>", r.text):
#             (queue if loc.lower().endswith(".xml") else urls).append(loc)
#     return urls


# def _parse(html: str, page_url: str, scope: Scope):
#     """Return (canonical_url, [absolute normalised links])."""
#     soup = BeautifulSoup(html, "html.parser")
#     tag = soup.find("link", rel="canonical")
#     href = tag.get("href") if tag else None
#     canonical = scope.normalize(urljoin(page_url, href)) if href else page_url
#     links = []
#     for a in soup.find_all("a", href=True):
#         h = a["href"].strip()
#         if h and not h.startswith(("mailto:", "tel:", "javascript:", "#")):
#             links.append(scope.normalize(urljoin(page_url, h)))
#     return canonical, links


# async def crawl_site(fetch, scope: Scope, html_dir: Path, seeds: list[str], robots, *,
#                      max_pages: int, delay: float, workers: int, resume: bool):
#     """Breadth-first crawl. `fetch(url)` is an async function returning the page HTML or None.
#     Returns (pages_saved, set_of_pdf_urls)."""
#     html_dir.mkdir(parents=True, exist_ok=True)
#     seen, queued, queue, pdf_urls = set(), set(), deque(), set()
#     saved = 0

#     def enqueue(links):
#         """Every URL goes through the scope check, and is queued at most once."""
#         for link in links:
#             if link in seen or link in queued:
#                 continue
#             if scope.is_pdf(link):
#                 pdf_urls.add(link)
#             elif scope.is_page(link):
#                 queued.add(link)
#                 queue.append(link)

#     if resume:  # rebuild state from pages already on disk (only pages still in scope)
#         for f in sorted(html_dir.glob("*.json")):
#             try:
#                 page = json.loads(f.read_text(encoding="utf-8"))
#             except ValueError:  # half-written file from an interrupted run
#                 f.unlink()
#                 continue
#             if scope.is_page(page["url"]):
#                 seen.add(page["url"])
#                 saved += 1
#                 enqueue(_parse(page["html"], page["url"], scope)[1])
#         print(f"Resuming: {saved} pages already saved, {len(queue)} links waiting")
#     else:
#         for f in html_dir.glob("*.json"):
#             f.unlink()
#     enqueue(seeds)  # sitemap URLs are scope-checked too

#     claimed, active = saved, 0
#     lock, next_slot, started = asyncio.Lock(), 0.0, time.time()

#     async def throttle():  # global rate limit: one request START per `delay` seconds
#         nonlocal next_slot
#         loop = asyncio.get_running_loop()
#         async with lock:
#             now = loop.time()
#             wait = max(0.0, next_slot - now)
#             next_slot = max(now, next_slot) + delay
#         if wait:
#             await asyncio.sleep(wait)

#     async def worker():
#         nonlocal claimed, active, saved
#         while claimed < max_pages:
#             if not queue:
#                 if active == 0:
#                     return
#                 await asyncio.sleep(0.2)
#                 continue
#             url = queue.popleft()
#             if url in seen:
#                 continue
#             seen.add(url)
#             if not scope.is_page(url):
#                 continue
#             if not robots.can_fetch(url):
#                 print(f"  [robots] skipped {url}")
#                 continue
#             claimed += 1
#             active += 1
#             try:
#                 await throttle()
#                 html = await fetch(url)
#                 if not html:
#                     claimed -= 1
#                     continue
#                 canonical, links = _parse(html, url, scope)
#                 name = hashlib.sha1(url.encode()).hexdigest()[:12]
#                 (html_dir / f"{name}.json").write_text(
#                     json.dumps({"url": url, "canonical": canonical, "html": html}), encoding="utf-8")
#                 saved += 1
#                 enqueue(links)
#                 rate = (saved / max(time.time() - started, 1)) * 60
#                 print(f"  [{saved}] {url}  (waiting: {len(queue)}, ~{rate:.0f} pages/min)")
#             except Exception as e:  # one bad page must not stop the crawl
#                 claimed -= 1
#                 print(f"  [error] {url}: {e}")
#             finally:
#                 active -= 1

#     await asyncio.gather(*(worker() for _ in range(max(1, workers))))
#     return saved, pdf_urls


# def download_pdfs(pdf_urls, scope: Scope, pdf_dir: Path, session, robots, *,
#                   max_pdfs: int, max_pdf_mb: int, delay: float, resume: bool) -> int:
#     pdf_dir.mkdir(parents=True, exist_ok=True)
#     if not resume:
#         for f in pdf_dir.iterdir():
#             if f.is_file():
#                 f.unlink()
#     cap, saved = max_pdf_mb * 1024 * 1024, 0
#     for url in sorted(pdf_urls):
#         name = hashlib.sha1(url.encode()).hexdigest()[:12]
#         if (pdf_dir / f"{name}.pdf").exists():
#             saved += 1
#             continue
#         if saved >= max_pdfs:
#             break
#         if not robots.can_fetch(url):
#             print(f"  [robots] skipped {url}")
#             continue
#         time.sleep(max(delay, robots.crawl_delay(url)))
#         try:
#             r = session.get(url, timeout=60, stream=True)
#             if r.status_code != 200 or "pdf" not in r.headers.get("Content-Type", "").lower():
#                 continue
#             if int(r.headers.get("Content-Length") or 0) > cap:
#                 print(f"  [pdf too large] {url}")
#                 continue
#             data = b""
#             for part in r.iter_content(1 << 16):
#                 data += part
#                 if len(data) > cap:
#                     data = b""
#                     break
#             if not data:
#                 continue
#         except requests.RequestException as e:
#             print(f"  [pdf error] {url}: {e}")
#             continue
#         (pdf_dir / f"{name}.pdf").write_bytes(data)
#         (pdf_dir / f"{name}.json").write_text(json.dumps({"url": url}), encoding="utf-8")
#         saved += 1
#         print(f"  [pdf {saved}] {url}")
#     return saved


# def describe_seeds(seeds: list[str], scope: Scope) -> None:
#     """Print how many sitemap URLs are in scope, grouped by the first two path segments."""
#     from collections import Counter
#     inside = [u for u in seeds if scope.is_page(u)]
#     pdfs = sum(1 for u in seeds if scope.is_pdf(u))
#     print(f"Sitemap lists {len(seeds)} URLs: {len(inside)} pages in scope, {pdfs} PDFs, "
#           f"{len(seeds) - len(inside) - pdfs} outside scope (skipped).")
#     groups = Counter("/".join(urlparse(u).path.strip("/").split("/")[:2]) for u in inside)
#     for name, n in groups.most_common(12):
#         print(f"    {n:5d}  /{name}")
#     print()


# def crawl(start_url, out_dir, max_pages=1500, max_pdfs=300, max_pdf_mb=20, delay=1.0,
#           include="", exclude=None, workers=3, page_wait=1.5, resume=False, text_mode=True):
#     from crawl4ai import AsyncWebCrawler, BrowserConfig, CacheMode, CrawlerRunConfig

#     out_dir = Path(out_dir)
#     scope = Scope(start_url, include, exclude or [])
#     session = requests.Session()
#     session.headers["User-Agent"] = USER_AGENT
#     robots = Robots(session)
#     start = scope.normalize(start_url)
#     delay = max(delay, robots.crawl_delay(start))
#     sitemap = [scope.normalize(u) for u in sitemap_urls(start, robots, session)]
#     describe_seeds(sitemap, scope)
#     seeds = [start] + sitemap

#     browser_cfg = BrowserConfig(headless=True, user_agent=USER_AGENT, verbose=False,
#                                 text_mode=text_mode)  # no images: faster page loads
#     run_cfg = CrawlerRunConfig(cache_mode=CacheMode.BYPASS, page_timeout=45000, verbose=False,
#                                wait_until="domcontentloaded", delay_before_return_html=page_wait)

#     async def run():
#         async with AsyncWebCrawler(config=browser_cfg) as crawler:
#             async def fetch(url):
#                 result = await crawler.arun(url=url, config=run_cfg)
#                 status = getattr(result, "status_code", None)
#                 if not result.success or not result.html or (status and status >= 400):
#                     print(f"  [skip] {url} (status {status})")
#                     return None
#                 return result.html
#             return await crawl_site(fetch, scope, out_dir / "html", seeds, robots,
#                                     max_pages=max_pages, delay=delay, workers=workers, resume=resume)

#     pages, pdf_urls = asyncio.run(run())
#     pdfs = download_pdfs(pdf_urls, scope, out_dir / "pdf", session, robots, max_pdfs=max_pdfs,
#                          max_pdf_mb=max_pdf_mb, delay=delay, resume=resume)
#     return pages, pdfs



"""Step 1: polite crawler.
- HTML pages: fetched with Crawl4AI (real browser, so JavaScript-rendered content is included)
  by a few workers in parallel, but never faster than one request start per CRAWL_DELAY seconds
- PDFs: found from links on crawled pages, downloaded with requests
Rules: robots.txt respected (per host), delay between every request, public pages only.
"""
import asyncio
import hashlib
import json
import re
import time
from collections import deque
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

from .scope import Scope

USER_AGENT = "TakeHomeRAGBot/1.0 (assessment project; polite crawler)"


class Robots:
    """robots.txt per host. If robots.txt cannot be read (network error / 5xx) we do NOT crawl that host."""

    def __init__(self, session: requests.Session):
        self.session = session
        self.cache: dict[str, RobotFileParser | None] = {}

    def _get(self, url: str):
        p = urlparse(url)
        origin = f"{p.scheme}://{p.netloc}"
        if origin not in self.cache:
            rp = RobotFileParser()
            try:
                r = self.session.get(f"{origin}/robots.txt", timeout=15)
                if r.status_code == 200:
                    rp.parse(r.text.splitlines())
                elif 400 <= r.status_code < 500:
                    rp.parse([])  # no robots.txt -> everything allowed
                else:
                    rp = None
            except requests.RequestException:
                rp = None
            if rp is None:
                print(f"  [robots] could not read robots.txt for {origin}; skipping that host")
            self.cache[origin] = rp
        return self.cache[origin]

    def can_fetch(self, url: str) -> bool:
        rp = self._get(url)
        return bool(rp and rp.can_fetch(USER_AGENT, url))

    def crawl_delay(self, url: str) -> float:
        rp = self._get(url)
        return float((rp.crawl_delay(USER_AGENT) if rp else 0) or 0)

    def sitemaps(self, url: str) -> list[str]:
        rp = self._get(url)
        return list(rp.site_maps() or []) if rp else []


def sitemap_urls(start_url: str, robots: Robots, session: requests.Session) -> list[str]:
    p = urlparse(start_url)
    queue = robots.sitemaps(start_url) or [f"{p.scheme}://{p.netloc}/sitemap.xml"]
    seen, urls = set(), []
    while queue and len(seen) < 30:
        sm = queue.pop(0)
        if sm in seen:
            continue
        seen.add(sm)
        try:
            r = session.get(sm, timeout=20)
        except requests.RequestException:
            continue
        if r.status_code != 200:
            continue
        for loc in re.findall(r"<loc>\s*(.*?)\s*</loc>", r.text):
            (queue if loc.lower().endswith(".xml") else urls).append(loc)
    return urls


def _parse(html: str, page_url: str, scope: Scope):
    """Return (canonical_url, [absolute normalised links])."""
    soup = BeautifulSoup(html, "html.parser")
    tag = soup.find("link", rel="canonical")
    href = tag.get("href") if tag else None
    canonical = scope.normalize(urljoin(page_url, href)) if href else page_url
    links = []
    for a in soup.find_all("a", href=True):
        h = a["href"].strip()
        if h and not h.startswith(("mailto:", "tel:", "javascript:", "#")):
            links.append(scope.normalize(urljoin(page_url, h)))
    return canonical, links


async def crawl_site(fetch, scope: Scope, html_dir: Path, seeds: list[str], robots, *,
                     max_pages: int, delay: float, workers: int, resume: bool):
    """Breadth-first crawl. `fetch(url)` is an async function returning the page HTML or None.
    Returns (pages_saved, set_of_pdf_urls, pages_found_but_not_downloaded)."""
    html_dir.mkdir(parents=True, exist_ok=True)
    seen, queued, queue, pdf_urls = set(), set(), deque(), set()
    saved = 0

    def enqueue(links):
        """Every URL goes through the scope check, and is queued at most once."""
        for link in links:
            if link in seen or link in queued:
                continue
            if scope.is_pdf(link):
                pdf_urls.add(link)
            elif scope.is_page(link):
                queued.add(link)
                queue.append(link)

    if resume:  # rebuild state from pages already on disk (only pages still in scope)
        for f in sorted(html_dir.glob("*.json")):
            try:
                page = json.loads(f.read_text(encoding="utf-8"))
            except ValueError:  # half-written file from an interrupted run
                f.unlink()
                continue
            if scope.is_page(page["url"]):
                seen.add(page["url"])
                saved += 1
                enqueue(_parse(page["html"], page["url"], scope)[1])
        print(f"Resuming: {saved} pages already saved, {len(queue)} links waiting")
    else:
        for f in html_dir.glob("*.json"):
            f.unlink()
    enqueue(seeds)  # sitemap URLs are scope-checked too

    claimed, active = saved, 0
    lock, next_slot, started = asyncio.Lock(), 0.0, time.time()

    async def throttle():  # global rate limit: one request START per `delay` seconds
        nonlocal next_slot
        loop = asyncio.get_running_loop()
        async with lock:
            now = loop.time()
            wait = max(0.0, next_slot - now)
            next_slot = max(now, next_slot) + delay
        if wait:
            await asyncio.sleep(wait)

    async def worker():
        nonlocal claimed, active, saved
        while claimed < max_pages:
            if not queue:
                if active == 0:
                    return
                await asyncio.sleep(0.2)
                continue
            url = queue.popleft()
            if url in seen:
                continue
            seen.add(url)
            if not scope.is_page(url):
                continue
            if not robots.can_fetch(url):
                print(f"  [robots] skipped {url}")
                continue
            claimed += 1
            active += 1
            try:
                await throttle()
                html = await fetch(url)
                if not html:
                    claimed -= 1
                    continue
                canonical, links = _parse(html, url, scope)
                name = hashlib.sha1(url.encode()).hexdigest()[:12]
                (html_dir / f"{name}.json").write_text(
                    json.dumps({"url": url, "canonical": canonical, "html": html}), encoding="utf-8")
                saved += 1
                enqueue(links)
                rate = (saved / max(time.time() - started, 1)) * 60
                print(f"  [{saved}] {url}  (waiting: {len(queue)}, ~{rate:.0f} pages/min)")
            except Exception as e:  # one bad page must not stop the crawl
                claimed -= 1
                print(f"  [error] {url}: {e}")
            finally:
                active -= 1

    await asyncio.gather(*(worker() for _ in range(max(1, workers))))
    return saved, pdf_urls, len(queue)


def download_pdfs(pdf_urls, scope: Scope, pdf_dir: Path, session, robots, *,
                  max_pdfs: int, max_pdf_mb: int, delay: float, resume: bool) -> tuple[int, int]:
    pdf_dir.mkdir(parents=True, exist_ok=True)
    if not resume:
        for f in pdf_dir.iterdir():
            if f.is_file():
                f.unlink()
    cap, saved = max_pdf_mb * 1024 * 1024, 0
    for url in sorted(pdf_urls):
        name = hashlib.sha1(url.encode()).hexdigest()[:12]
        if (pdf_dir / f"{name}.pdf").exists():
            saved += 1
            continue
        if saved >= max_pdfs:
            break
        if not robots.can_fetch(url):
            print(f"  [robots] skipped {url}")
            continue
        time.sleep(max(delay, robots.crawl_delay(url)))
        try:
            r = session.get(url, timeout=60, stream=True)
            if r.status_code != 200 or "pdf" not in r.headers.get("Content-Type", "").lower():
                continue
            if int(r.headers.get("Content-Length") or 0) > cap:
                print(f"  [pdf too large] {url}")
                continue
            data = b""
            for part in r.iter_content(1 << 16):
                data += part
                if len(data) > cap:
                    data = b""
                    break
            if not data:
                continue
        except requests.RequestException as e:
            print(f"  [pdf error] {url}: {e}")
            continue
        (pdf_dir / f"{name}.pdf").write_bytes(data)
        (pdf_dir / f"{name}.json").write_text(json.dumps({"url": url}), encoding="utf-8")
        saved += 1
        print(f"  [pdf {saved}] {url}")
    return saved


def describe_seeds(seeds: list[str], scope: Scope, pages_per_min: int = 30) -> None:
    """Print what the sitemap contains: what is crawled, and exactly why the rest is skipped."""
    from collections import Counter
    reasons = Counter(scope.reason(u) for u in seeds)
    in_scope = [u for u in seeds if scope.reason(u) == "in-scope"]
    print(f"Sitemap lists {len(seeds)} URLs. {len(in_scope)} pages in scope, {reasons['pdf']} PDFs.")

    skipped = {k: v for k, v in reasons.items() if k not in ("in-scope", "pdf")}
    if skipped:
        print("Skipped, and why:")
        for reason, n in sorted(skipped.items(), key=lambda kv: -kv[1]):
            line = f"    {n:5d}  {reason}"
            if reason in ("outside-include", "other-site"):
                tops = Counter(
                    (urlparse(u).netloc if reason == "other-site" else "/" + urlparse(u).path.strip("/").split("/")[0])
                    for u in seeds if scope.reason(u) == reason).most_common(4)
                line += "   e.g. " + ", ".join(f"{k} ({v})" for k, v in tops)
            print(line)

    print("Crawled, by section:")
    groups = Counter("/" + "/".join(urlparse(u).path.strip("/").split("/")[:2]) for u in in_scope)
    for name, n in groups.most_common(40):
        print(f"    {n:5d}  {name}")
    print(f"At about {pages_per_min} pages/min, {len(in_scope)} pages take roughly "
          f"{len(in_scope) / pages_per_min:.0f} minutes.\n")


def report(start_url: str, include: str, exclude: list[str]) -> None:
    """Sitemap size report only: no browser, no page downloads."""
    scope = Scope(start_url, include, exclude)
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    robots = Robots(session)
    start = scope.normalize(start_url)
    describe_seeds([scope.normalize(u) for u in sitemap_urls(start, robots, session)], scope)


def crawl(start_url, out_dir, max_pages=1500, max_pdfs=300, max_pdf_mb=20, delay=1.0,
          include="", exclude=None, workers=3, page_wait=1.5, resume=False, text_mode=True):
    from crawl4ai import AsyncWebCrawler, BrowserConfig, CacheMode, CrawlerRunConfig

    out_dir = Path(out_dir)
    scope = Scope(start_url, include, exclude or [])
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    robots = Robots(session)
    start = scope.normalize(start_url)
    delay = max(delay, robots.crawl_delay(start))
    sitemap = [scope.normalize(u) for u in sitemap_urls(start, robots, session)]
    describe_seeds(sitemap, scope)
    seeds = [start] + sitemap

    browser_cfg = BrowserConfig(headless=True, user_agent=USER_AGENT, verbose=False,
                                text_mode=text_mode)  # no images: faster page loads
    run_cfg = CrawlerRunConfig(cache_mode=CacheMode.BYPASS, page_timeout=45000, verbose=False,
                               wait_until="domcontentloaded", delay_before_return_html=page_wait)

    async def run():
        async with AsyncWebCrawler(config=browser_cfg) as crawler:
            async def fetch(url):
                result = await crawler.arun(url=url, config=run_cfg)
                status = getattr(result, "status_code", None)
                if not result.success or not result.html or (status and status >= 400):
                    print(f"  [skip] {url} (status {status})")
                    return None
                return result.html
            return await crawl_site(fetch, scope, out_dir / "html", seeds, robots,
                                    max_pages=max_pages, delay=delay, workers=workers, resume=resume)

    pages, pdf_urls, waiting = asyncio.run(run())
    pdfs, pdfs_left = download_pdfs(pdf_urls, scope, out_dir / "pdf", session, robots, max_pdfs=max_pdfs,
                                    max_pdf_mb=max_pdf_mb, delay=delay, resume=resume)

    # ---- completeness: what the sitemap lists in scope but we do not have on disk
    html_dir = out_dir / "html"
    missing = [u for u in sitemap if scope.is_page(u)
               and not (html_dir / f"{hashlib.sha1(u.encode()).hexdigest()[:12]}.json").exists()]
    (out_dir.parent / "not_downloaded.txt").write_text("\n".join(missing), encoding="utf-8")
    print("\n=== CRAWL COMPLETENESS ===")
    if waiting:
        print(f"!! STOPPED BY THE PAGE LIMIT (MAX_PAGES={max_pages}): {waiting} more pages were found but not "
              "downloaded. The knowledge base is INCOMPLETE. Raise MAX_PAGES or narrow the scope, then run again.")
    if pdfs_left:
        print(f"!! STOPPED BY THE PDF LIMIT (MAX_PDFS={max_pdfs}): {pdfs_left} more PDFs were found but not "
              "downloaded. Raise MAX_PDFS and run again.")
    print(f"Sitemap pages in scope that are NOT on disk: {len(missing)} "
          f"(failed, redirected, or not reached) -> {out_dir.parent / 'not_downloaded.txt'}")
    for u in missing[:5]:
        print(f"    {u}")
    if not waiting and not pdfs_left and not missing:
        print("Complete: every in-scope sitemap page was downloaded.")
    print()
    return pages, pdfs