
# """One command: crawl -> clean -> chunk -> data/chunks.jsonl

#     python build.py                  # reads SITE_URL etc. from .env
#     python build.py --skip-crawl     # re-run clean/chunk on already downloaded files
# """
# import argparse
# import csv
# import hashlib
# import json
# import os
# import re
# from pathlib import Path

# from urllib.parse import urlparse

# from dotenv import load_dotenv

# from pipeline.chunk import chunk_page
# from pipeline.clean import clean_html
# from pipeline.dedupe import find_repeated, strip_repeated
# from pipeline.pdf import extract_pdf
# from pipeline.scope import Scope

# DATA = Path("data")
# RAW = DATA / "raw"
# OUT = DATA / "chunks.jsonl"
# PAGES_CSV = DATA / "pages.csv"
# PDF_TEXT = DATA / "pdf_text"  # extracted PDF text, for you to inspect
# SKIPPED = DATA / "skipped_pages.txt"  # pages with almost no text left, for you to review
# MIN_PAGE_CHARS = 200
# # Always excluded (non-product areas). EXCLUDE_PATHS in .env can only ADD to this list.
# DEFAULT_EXCLUDE = ["/en/media-center", "/en/investor-relations", "/en/careers", "/en/about-emirates-nbd",
#                    "/en/innovation", "/en/cio-corner", "/-/media/enbd/files/investor-relations"]


# def load_html_pages(scope: Scope) -> tuple[list[dict], int]:
#     items, ignored = [], 0
#     for path in sorted((RAW / "html").glob("*.json")):
#         page = json.loads(path.read_text(encoding="utf-8"))
#         if not scope.is_page(page["url"]):  # downloaded earlier, outside the current scope
#             ignored += 1
#             continue
#         title, md = clean_html(page["html"])
#         items.append({"url": page["url"], "canonical": page.get("canonical") or page["url"],
#                       "title": title, "md": md})
#     return items, ignored


# def drop_duplicate_pages(items: list[dict]) -> tuple[list[dict], int]:
#     """Same cleaned text under several URLs (e.g. an old and a new path): keep one.
#     Prefer the URL that equals the page's own canonical URL, then the shortest URL."""
#     groups: dict[str, list[dict]] = {}
#     for it in items:
#         key = hashlib.sha1(re.sub(r"\s+", " ", it["md"]).encode()).hexdigest()
#         groups.setdefault(key, []).append(it)
#     kept = []
#     for g in groups.values():
#         g.sort(key=lambda x: (x["url"] != x["canonical"], len(x["url"]), x["url"]))
#         kept.append(g[0])
#     return kept, len(items) - len(kept)


# def load_pdfs(scope: Scope) -> list[dict]:
#     PDF_TEXT.mkdir(parents=True, exist_ok=True)
#     for old in PDF_TEXT.glob("*.md"):
#         old.unlink()
#     docs = []
#     for pdf_path in sorted((RAW / "pdf").glob("*.pdf")):
#         url = json.loads(pdf_path.with_suffix(".json").read_text(encoding="utf-8"))["url"]
#         if not scope.is_pdf(url):
#             continue
#         try:
#             title, pages, n_tables = extract_pdf(pdf_path)
#         except Exception as e:  # damaged / encrypted PDF: report, keep going
#             print(f"  [pdf error] {url}: {e}")
#             continue
#         # running headers/footers repeat on most pages of one PDF -> remove
#         repeated = find_repeated([md for _, md in pages], min_share=0.5, min_docs=3)
#         pages = [(n, strip_repeated(md, repeated)) for n, md in pages]
#         (PDF_TEXT / f"{pdf_path.stem}.md").write_text(
#             f"SOURCE: {url}\nTABLES FOUND: {n_tables}\n\n" +
#             "\n\n".join(f"<!-- page {n} -->\n{md}" for n, md in pages), encoding="utf-8")
#         docs.append({"url": url, "title": title or pdf_path.stem, "pages": pages, "tables": n_tables})
#     return docs


# def main():
#     load_dotenv()
#     ap = argparse.ArgumentParser()
#     ap.add_argument("--url", default=os.getenv("SITE_URL"))
#     ap.add_argument("--include", default=None)
#     ap.add_argument("--exclude", default=None)
#     ap.add_argument("--workers", type=int, default=int(os.getenv("WORKERS", 3)))
#     ap.add_argument("--page-wait", type=float, default=float(os.getenv("PAGE_WAIT", 1.5)))
#     ap.add_argument("--fresh", action="store_true", help="delete downloaded pages and crawl from zero (default: continue)")
#     ap.add_argument("--no-text-mode", action="store_true", help="load images too (slower); use if pages come out empty")
#     ap.add_argument("--max-pages", type=int, default=int(os.getenv("MAX_PAGES", 1500)))
#     ap.add_argument("--max-pdfs", type=int, default=int(os.getenv("MAX_PDFS", 300)))
#     ap.add_argument("--max-pdf-mb", type=int, default=int(os.getenv("MAX_PDF_MB", 20)))
#     ap.add_argument("--delay", type=float, default=float(os.getenv("CRAWL_DELAY", 1.0)))
#     ap.add_argument("--skip-crawl", action="store_true")
#     ap.add_argument("--skip-embed", action="store_true", help="stop after chunks.jsonl")
#     args = ap.parse_args()

#     # Scope: .env value if set, otherwise: include = path of the start URL, exclude = DEFAULT_EXCLUDE
#     include = args.include if args.include is not None else os.getenv(
#         "INCLUDE_PATH", urlparse(args.url).path.rstrip("/") if args.url else "")
#     exclude_raw = args.exclude if args.exclude is not None else os.getenv("EXCLUDE_PATHS")
#     extra = [e.strip() for e in (exclude_raw or "").split(",") if e.strip()]
#     exclude = DEFAULT_EXCLUDE + [e for e in extra if e not in DEFAULT_EXCLUDE]
#     print(f"Scope: include='{include}'  exclude={exclude}\n")

#     if not args.skip_crawl:
#         if not args.url:
#             ap.error("Provide --url or set SITE_URL in .env")
#         from pipeline.crawl import crawl  # imported here so --skip-crawl needs no browser
#         print(f"Crawling {args.url} ...")
#         n_pages, n_pdfs = crawl(args.url, RAW, args.max_pages, args.max_pdfs, args.max_pdf_mb,
#                                 args.delay, include, exclude, args.workers, args.page_wait,
#                                 resume=not args.fresh, text_mode=not args.no_text_mode)
#         print(f"Downloaded {n_pages} pages and {n_pdfs} PDFs.\n")

#     # ---- HTML pages: clean -> remove site-wide menu/footer text -> drop duplicates
#     first = next(iter(sorted((RAW / "html").glob("*.json"))), None)
#     start = args.url or (json.loads(first.read_text(encoding="utf-8"))["url"] if first else "")
#     scope = Scope(start, include, exclude)
#     items, ignored = load_html_pages(scope)
#     repeated = find_repeated([i["md"] for i in items], min_share=0.5, min_docs=10)
#     for i in items:
#         i["md"] = strip_repeated(i["md"], repeated)
#     short = [i for i in items if len(i["md"]) < MIN_PAGE_CHARS]
#     items = [i for i in items if len(i["md"]) >= MIN_PAGE_CHARS]
#     items, n_dupes = drop_duplicate_pages(items)

#     DATA.mkdir(exist_ok=True)
#     SKIPPED.write_text("\n".join(f"{len(i['md'])}\t{i['url']}" for i in short), encoding="utf-8")

#     # ---- PDFs
#     pdfs = load_pdfs(scope)

#     # ---- chunk and write
#     DATA.mkdir(exist_ok=True)
#     total, rows = 0, []
#     with OUT.open("w", encoding="utf-8") as f:
#         def write(stem: str, chunks):
#             nonlocal total
#             for i, c in enumerate(chunks):
#                 f.write(json.dumps({"id": f"{stem}-{i}", "text": c.page_content, **c.metadata},
#                                    ensure_ascii=False) + "\n")
#             total += len(chunks)
#             return len(chunks)

#         for it in items:
#             stem = hashlib.sha1(it["url"].encode()).hexdigest()[:12]
#             n = write(stem, chunk_page(it["url"], it["title"], it["md"]))
#             rows.append([it["url"], it["title"], "html", len(it["md"]), n])

#         for d in pdfs:
#             stem = hashlib.sha1(d["url"].encode()).hexdigest()[:12]
#             n = 0
#             for page_no, md in d["pages"]:
#                 n += write(f"{stem}-p{page_no}", chunk_page(d["url"], d["title"], md, page=page_no))
#             rows.append([d["url"], d["title"], "pdf", sum(len(m) for _, m in d["pages"]), n])

#     with PAGES_CSV.open("w", newline="", encoding="utf-8") as f:
#         w = csv.writer(f)
#         w.writerow(["url", "title", "type", "chars", "chunks"])
#         w.writerows(rows)

#     print(f"Menu/footer lines removed (site-wide): {len(repeated)}")
#     print(f"Downloaded pages ignored (outside scope): {ignored}")
#     print(f"HTML pages kept: {len(items)} | too short, skipped: {len(short)} | duplicate pages dropped: {n_dupes}")
#     print(f"PDFs processed: {len(pdfs)} (tables found: {sum(d['tables'] for d in pdfs)})")
#     print(f"Chunks written: {total} -> {OUT}")
#     print(f"Review: {PAGES_CSV} (every kept URL), {SKIPPED} (pages dropped for lack of text), {PDF_TEXT}/ (PDF text)")

#     if not args.skip_embed:
#         from pipeline.embed import build_index  # heavy imports only when needed
#         build_index(OUT)


# if __name__ == "__main__":
#     main()


"""One command: crawl -> clean -> chunk -> data/chunks.jsonl

    python build.py                  # reads SITE_URL etc. from .env
    python build.py --skip-crawl     # re-run clean/chunk on already downloaded files
"""
import argparse
import csv
import hashlib
import json
import os
import re
from pathlib import Path

from urllib.parse import urlparse

from dotenv import load_dotenv

os.environ.setdefault("CRAWL4AI_NO_CLOUD_NOTICE", "1")  # hide the Crawl4AI advertising banner

from pipeline.chunk import chunk_page
from pipeline.clean import clean_html
from pipeline.dedupe import find_repeated, strip_repeated
from pipeline import registry
from pipeline.pdf import extract_pdf
from pipeline.scope import Scope

DATA = Path("data")
RAW = DATA / "raw"
OUT = DATA / "chunks.jsonl"
PAGES_CSV = DATA / "pages.csv"
PDF_TEXT = DATA / "pdf_text"  # extracted PDF text, for you to inspect
SKIPPED = DATA / "skipped_pages.txt"  # pages with almost no text left, for you to review
MIN_PAGE_CHARS = 200
# Always excluded (non-product areas). EXCLUDE_PATHS in .env can only ADD to this list.
DEFAULT_EXCLUDE = ["/en/media-center", "/en/investor-relations", "/en/careers", "/en/about-emirates-nbd",
                   "/en/innovation", "/en/cio-corner", "/-/media/enbd/files/investor-relations"]


def load_html_pages(scope: Scope) -> tuple[list[dict], int]:
    items, ignored = [], 0
    for path in sorted((RAW / "html").glob("*.json")):
        page = json.loads(path.read_text(encoding="utf-8"))
        if not scope.is_page(page["url"]):  # downloaded earlier, outside the current scope
            ignored += 1
            continue
        title, md = clean_html(page["html"])
        items.append({"url": page["url"], "canonical": page.get("canonical") or page["url"],
                      "title": title, "md": md})
    return items, ignored


def drop_duplicate_pages(items: list[dict]) -> tuple[list[dict], int]:
    """Same cleaned text under several URLs (e.g. an old and a new path): keep one.
    Prefer the URL that equals the page's own canonical URL, then the shortest URL."""
    groups: dict[str, list[dict]] = {}
    for it in items:
        key = hashlib.sha1(re.sub(r"\s+", " ", it["md"]).encode()).hexdigest()
        groups.setdefault(key, []).append(it)
    kept = []
    for g in groups.values():
        g.sort(key=lambda x: (x["url"] != x["canonical"], len(x["url"]), x["url"]))
        kept.append(g[0])
    return kept, len(items) - len(kept)


def load_pdfs(scope: Scope) -> list[dict]:
    PDF_TEXT.mkdir(parents=True, exist_ok=True)
    for old in PDF_TEXT.glob("*.md"):
        old.unlink()
    docs = []
    for pdf_path in sorted((RAW / "pdf").glob("*.pdf")):
        url = json.loads(pdf_path.with_suffix(".json").read_text(encoding="utf-8"))["url"]
        if not scope.is_pdf(url):
            continue
        try:
            title, pages, n_tables = extract_pdf(pdf_path)
        except Exception as e:  # damaged / encrypted PDF: report, keep going
            print(f"  [pdf error] {url}: {e}")
            continue
        # running headers/footers repeat on most pages of one PDF -> remove
        repeated = find_repeated([md for _, md in pages], min_share=0.5, min_docs=3)
        pages = [(n, strip_repeated(md, repeated)) for n, md in pages]
        (PDF_TEXT / f"{pdf_path.stem}.md").write_text(
            f"SOURCE: {url}\nTABLES FOUND: {n_tables}\n\n" +
            "\n\n".join(f"<!-- page {n} -->\n{md}" for n, md in pages), encoding="utf-8")
        docs.append({"url": url, "title": title or pdf_path.stem, "pages": pages, "tables": n_tables})
    return docs


def main():
    load_dotenv()
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default=os.getenv("SITE_URL"))
    ap.add_argument("--include", default=None)
    ap.add_argument("--exclude", default=None)
    ap.add_argument("--workers", type=int, default=int(os.getenv("WORKERS", 3)))
    ap.add_argument("--page-wait", type=float, default=float(os.getenv("PAGE_WAIT", 1.5)))
    ap.add_argument("--fresh", action="store_true", help="delete downloaded pages and crawl from zero (default: continue)")
    ap.add_argument("--no-text-mode", action="store_true", help="load images too (slower); use if pages come out empty")
    ap.add_argument("--max-pages", type=int, default=int(os.getenv("MAX_PAGES", 3000)))
    ap.add_argument("--max-pdfs", type=int, default=int(os.getenv("MAX_PDFS", 600)))
    ap.add_argument("--max-pdf-mb", type=int, default=int(os.getenv("MAX_PDF_MB", 20)))
    ap.add_argument("--delay", type=float, default=float(os.getenv("CRAWL_DELAY", 1.0)))
    ap.add_argument("--skip-crawl", action="store_true")
    ap.add_argument("--report", action="store_true", help="only print the sitemap breakdown, then exit")
    ap.add_argument("--strict-coverage", action="store_true", help="stop with an error if any registry product has no chunks")
    ap.add_argument("--skip-embed", action="store_true", help="stop after chunks.jsonl")
    args = ap.parse_args()

    # Scope: .env value if set, otherwise: include = path of the start URL, exclude = DEFAULT_EXCLUDE
    include = args.include if args.include is not None else os.getenv(
        "INCLUDE_PATH", urlparse(args.url).path.rstrip("/") if args.url else "")
    exclude_raw = args.exclude if args.exclude is not None else os.getenv("EXCLUDE_PATHS")
    extra = [e.strip() for e in (exclude_raw or "").split(",") if e.strip()]
    exclude = DEFAULT_EXCLUDE + [e for e in extra if e not in DEFAULT_EXCLUDE]
    print(f"Scope: include='{include}'  exclude={exclude}\n")

    if args.report:
        if not args.url:
            ap.error("Provide --url or set SITE_URL in .env")
        from pipeline.crawl import report
        report(args.url, include, exclude)
        return

    if not args.skip_crawl:
        if not args.url:
            ap.error("Provide --url or set SITE_URL in .env")
        from pipeline.crawl import crawl  # imported here so --skip-crawl needs no browser
        print(f"Crawling {args.url} ...")
        n_pages, n_pdfs = crawl(args.url, RAW, args.max_pages, args.max_pdfs, args.max_pdf_mb,
                                args.delay, include, exclude, args.workers, args.page_wait,
                                resume=not args.fresh, text_mode=not args.no_text_mode)
        print(f"Downloaded {n_pages} pages and {n_pdfs} PDFs.\n")

    # ---- HTML pages: clean -> remove site-wide menu/footer text -> drop duplicates
    first = next(iter(sorted((RAW / "html").glob("*.json"))), None)
    start = args.url or (json.loads(first.read_text(encoding="utf-8"))["url"] if first else "")
    scope = Scope(start, include, exclude)
    items, ignored = load_html_pages(scope)
    repeated = find_repeated([i["md"] for i in items], min_share=0.5, min_docs=10)
    for i in items:
        i["md"] = strip_repeated(i["md"], repeated)
    short = [i for i in items if len(i["md"]) < MIN_PAGE_CHARS]
    items = [i for i in items if len(i["md"]) >= MIN_PAGE_CHARS]
    items, n_dupes = drop_duplicate_pages(items)

    DATA.mkdir(exist_ok=True)
    SKIPPED.write_text("\n".join(f"{len(i['md'])}\t{i['url']}" for i in short), encoding="utf-8")

    # ---- PDFs
    pdfs = load_pdfs(scope)

    # ---- chunk and write
    DATA.mkdir(exist_ok=True)
    total, rows = 0, []
    with OUT.open("w", encoding="utf-8") as f:
        def write(stem: str, chunks):
            nonlocal total
            for i, c in enumerate(chunks):
                f.write(json.dumps({"id": f"{stem}-{i}", "text": c.page_content, **c.metadata},
                                   ensure_ascii=False) + "\n")
            total += len(chunks)
            return len(chunks)

        for it in items:
            stem = hashlib.sha1(it["url"].encode()).hexdigest()[:12]
            n = write(stem, chunk_page(it["url"], it["title"], it["md"]))
            h1 = re.search(r"^#\s+(.+)$", it["md"], re.M)
            rows.append([it["url"], it["title"], "html", len(it["md"]), n, h1.group(1).strip() if h1 else ""])

        for d in pdfs:
            stem = hashlib.sha1(d["url"].encode()).hexdigest()[:12]
            n = 0
            for page_no, md in d["pages"]:
                n += write(f"{stem}-p{page_no}", chunk_page(d["url"], d["title"], md, page=page_no))
            rows.append([d["url"], d["title"], "pdf", sum(len(m) for _, m in d["pages"]), n, ""])

    with PAGES_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["url", "title", "type", "chars", "chunks", "h1"])
        w.writerows(rows)

    print(f"Menu/footer lines removed (site-wide): {len(repeated)}")
    print(f"Downloaded pages ignored (outside scope): {ignored}")
    print(f"HTML pages kept: {len(items)} | too short, skipped: {len(short)} | duplicate pages dropped: {n_dupes}")
    print(f"PDFs processed: {len(pdfs)} (tables found: {sum(d['tables'] for d in pdfs)})")
    print(f"Chunks written: {total} -> {OUT}")
    print(f"Review: {PAGES_CSV} (every kept URL), {SKIPPED} (pages dropped for lack of text), {PDF_TEXT}/ (PDF text)")

    registry.run(strict=args.strict_coverage)  # writes data/registry.csv, url_product.json, coverage.md

    if not args.skip_embed:
        from pipeline.embed import build_index, load_store  # heavy imports only when needed
        build_index(OUT)
        if registry.REGISTRY_CSV.exists():
            registry.check_index(load_store(), strict=args.strict_coverage)


if __name__ == "__main__":
    main()