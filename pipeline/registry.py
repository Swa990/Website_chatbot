"""Step 5: product registry + coverage checker.

Registry  = the list of every product (id, name, category, url). It is the source of truth for
            "which products do you offer?" questions and for proving coverage.
Coverage  = for each product: is there at least one chunk (and one vector in the index)?

A product is a DIRECT child page of a category prefix defined in config/products.json
(prefix/<slug>). Products are collected from two places and cross-checked:
  - crawl:   pages we downloaded under the prefix
  - listing: links found on the category's own listing page
Pages deeper than a product (prefix/<slug>/...) are sub-pages of that product, not new products.

CLI:  python -m pipeline.registry --propose                  draft config/products.json from the crawled pages
      python -m pipeline.registry                      rebuild registry + coverage from existing files
      python -m pipeline.registry --prefixes [--depth N]   find category prefixes to put in the config
      python -m pipeline.registry --tree /en/loans         list crawled pages under a prefix
      python -m pipeline.registry --strict --index         fail if a product is uncovered; also check Chroma
"""
import argparse
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

DATA = Path("data")
PAGES_CSV = DATA / "pages.csv"
CHUNKS = DATA / "chunks.jsonl"
RAW_HTML = DATA / "raw" / "html"
REGISTRY_CSV = DATA / "registry.csv"
URL_PRODUCT = DATA / "url_product.json"   # url -> product_id (read by the embed step)
COVERAGE_MD = DATA / "coverage.md"
RULES = Path("config/products.json")


# ---------- helpers ----------
def _path(url: str) -> str:
    return "/" + urlparse(url).path.strip("/")


def load_rules(path: Path | None = None) -> list[dict]:
    path = Path(path or RULES)  # read RULES at call time, not at import time
    if not path.exists():
        return []
    rules = json.loads(path.read_text(encoding="utf-8")).get("rules", [])
    for r in rules:
        r["prefix"] = "/" + r["prefix"].strip("/")
        r["exclude_slugs"] = [s.lower() for s in r.get("exclude_slugs", [])]
    return rules


def read_pages() -> list[dict]:
    with PAGES_CSV.open(encoding="utf-8") as f:
        return [r for r in csv.DictReader(f) if r["type"] == "html"]


def product_name(row: dict, slug: str) -> str:
    """Page heading if there is a sensible one, else the page title without the site suffix."""
    h1 = (row.get("h1") or "").strip()
    if h1 and len(h1) <= 80:
        return h1
    title = re.split(r"\s+[|\-–]\s+", (row.get("title") or "").strip())[0].split(":")[0].strip()
    return title or slug.replace("-", " ").title()


def listing_children(listing_row: dict, prefix: str) -> dict[str, str] | None:
    """{slug_lower: absolute_url} for links on the listing page that point to prefix/<slug>.
    None if the listing page was not downloaded."""
    name = hashlib.sha1(listing_row["url"].encode()).hexdigest()[:12]
    f = RAW_HTML / f"{name}.json"
    if not f.exists():
        return None
    html = json.loads(f.read_text(encoding="utf-8"))["html"]
    found, pk = {}, prefix.lower()
    for a in BeautifulSoup(html, "html.parser").find_all("a", href=True):
        full = urljoin(listing_row["url"], a["href"].strip())
        p = _path(full)
        if p.lower().startswith(pk + "/"):
            rest = p[len(prefix) + 1:]
            if rest and "/" not in rest:
                found[rest.lower()] = full.split("#")[0].split("?")[0].rstrip("/")
    return found


# ---------- registry ----------
def build_registry(rules: list[dict], pages: list[dict]) -> tuple[list[dict], dict[str, str]]:
    by_key = {_path(r["url"]).lower(): r for r in pages}
    products: dict[str, dict] = {}

    for rule in rules:
        prefix, pk, excluded = rule["prefix"], rule["prefix"].lower(), set(rule["exclude_slugs"])
        for key, row in by_key.items():
            if not key.startswith(pk + "/"):
                continue
            rest = key[len(pk) + 1:]
            if "/" in rest or rest in excluded:
                continue
            products[key.strip("/")] = {
                "id": key.strip("/"), "name": product_name(row, rest), "category": rule["category"],
                "url": row["url"], "found_via": {"crawl"}}

        listing_row = by_key.get(pk)
        children = listing_children(listing_row, prefix) if listing_row else None
        if children is None:
            print(f"  [registry] listing page for '{rule['category']}' ({prefix}) was not downloaded; "
                  "using crawled pages only")
            continue
        for slug, url in children.items():
            if slug in excluded:
                continue
            pid = f"{pk.strip('/')}/{slug}"
            if pid in products:
                products[pid]["found_via"].add("listing")
            else:  # linked on the listing page but never downloaded
                products[pid] = {"id": pid, "name": slug.replace("-", " ").title(),
                                 "category": rule["category"], "url": url, "found_via": {"listing"}}

    # every crawled page -> its product (a product page or a sub-page below it)
    url_product = {}
    for row in pages:
        parts = _path(row["url"]).lower().strip("/").split("/")
        for n in range(len(parts), 0, -1):
            pid = "/".join(parts[:n])
            if pid in products:
                url_product[row["url"]] = pid
                break
    return sorted(products.values(), key=lambda p: (p["category"], p["name"].lower())), url_product


def write_registry(products: list[dict], url_product: dict[str, str]):
    with REGISTRY_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "name", "category", "url", "found_via"])
        for p in products:
            w.writerow([p["id"], p["name"], p["category"], p["url"], "+".join(sorted(p["found_via"]))])
    URL_PRODUCT.write_text(json.dumps(url_product, indent=0), encoding="utf-8")


# ---------- coverage ----------
def chunk_counts(url_product: dict[str, str]) -> Counter:
    counts = Counter()
    with CHUNKS.open(encoding="utf-8") as f:
        for line in f:
            pid = url_product.get(json.loads(line)["url"])
            if pid:
                counts[pid] += 1
    return counts


def write_coverage(products: list[dict], counts: Counter) -> list[dict]:
    missing = [p for p in products if counts[p["id"]] == 0]
    crawl_only = [p for p in products if p["found_via"] == {"crawl"}]
    listing_only = [p for p in products if p["found_via"] == {"listing"}]
    out = ["# Coverage report", "",
           f"Products in registry: **{len(products)}**  |  with at least one chunk: "
           f"**{len(products) - len(missing)}**  |  missing: **{len(missing)}**", ""]
    cats = defaultdict(list)
    for p in products:
        cats[p["category"]].append(p)
    out += ["| Category | Products | Covered |", "|---|---|---|"]
    for cat, items in cats.items():
        out.append(f"| {cat} | {len(items)} | {sum(counts[p['id']] > 0 for p in items)} |")
    out.append("")
    if missing:
        out += ["## MISSING (no chunk in the knowledge base)", ""]
        for p in missing:
            why = ("listed on the category page but its page was never downloaded"
                   if p["found_via"] == {"listing"} else "page downloaded but produced no chunks")
            out.append(f"- {p['category']} / {p['name']} - {p['url']}  ({why})")
        out.append("")
    if listing_only:
        out += ["## Linked on the listing page but not downloaded", ""] + \
               [f"- {p['name']} - {p['url']}" for p in listing_only] + [""]
    if crawl_only:
        out += ["## Found by crawl but NOT linked from the listing page (check these are current products)", ""] + \
               [f"- {p['name']} - {p['url']}" for p in crawl_only] + [""]
    out += ["## All products", "", "| Category | Product | Chunks | Page |", "|---|---|---|---|"]
    out += [f"| {p['category']} | {p['name']} | {counts[p['id']]} | {p['url']} |" for p in products]
    COVERAGE_MD.write_text("\n".join(out) + "\n", encoding="utf-8")
    return missing


def run(strict: bool = False) -> list[dict]:
    rules = load_rules()
    if not rules:
        print("Registry: no rules in config/products.json, skipped.")
        return []
    products, url_product = build_registry(rules, read_pages())
    write_registry(products, url_product)
    missing = write_coverage(products, chunk_counts(url_product))
    print(f"Registry: {len(products)} products -> {REGISTRY_CSV}")
    print(f"Coverage: {len(products) - len(missing)}/{len(products)} products have chunks -> {COVERAGE_MD}")
    for p in missing:
        print(f"  WARNING missing: {p['category']} / {p['name']} ({p['url']})")
    if strict and missing:
        raise SystemExit(f"{len(missing)} product(s) have no chunks (--strict-coverage)")
    return products


def check_index(store, strict: bool = False) -> list[dict]:
    """Registry vs the vector index: every product must have at least one stored vector."""
    with REGISTRY_CSV.open(encoding="utf-8") as f:
        products = list(csv.DictReader(f))
    missing = [p for p in products if not store.get(where={"product_id": p["id"]}, include=[])["ids"]]
    with COVERAGE_MD.open("a", encoding="utf-8") as f:
        f.write(f"\n## Vector index check\n\n{len(products) - len(missing)}/{len(products)} products "
                "have at least one vector in the index.\n")
        for p in missing:
            f.write(f"- NOT IN INDEX: {p['name']} - {p['url']}\n")
    print(f"Index check: {len(products) - len(missing)}/{len(products)} products found in the vector index")
    for p in missing:
        print(f"  WARNING not in index: {p['name']} ({p['url']})")
    if strict and missing:
        raise SystemExit(f"{len(missing)} product(s) not in the vector index")
    return missing


# ---------- proposing category rules (a draft for you to review) ----------
PROPOSED = Path("config/products.proposed.json")


def propose_rules(min_children: int = 3) -> list[dict]:
    """A category listing page is a page that exists AND has several pages directly below it
    (e.g. /x/cards/credit-cards with /x/cards/credit-cards/<card>). Pages that only group other
    categories (>= 2 of their children are themselves such listing pages) are skipped."""
    pages = read_pages()
    by_key = {_path(r["url"]).lower(): r for r in pages}
    children = defaultdict(list)
    for key in by_key:
        parent, _, slug = key.rpartition("/")
        children[parent].append(slug)
    candidates = {k for k in by_key if len(children.get(k, [])) >= min_children}
    rules = []
    for key in sorted(candidates):
        if sum(1 for slug in children[key] if f"{key}/{slug}" in candidates) >= 2:
            continue  # groups other categories, e.g. /en/cards
        row = by_key[key]
        rules.append({"category": product_name(row, key.rsplit("/", 1)[-1]), "prefix": _path(row["url"]),
                      "exclude_slugs": [], "pages_below": len(children[key]),
                      "examples": sorted(children[key])[:3]})
    return rules


def write_proposal(rules: list[dict]):
    PROPOSED.parent.mkdir(parents=True, exist_ok=True)
    PROPOSED.write_text(json.dumps({"rules": rules}, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"{len(rules)} possible product categories (listing page + {3}+ pages directly below it):\n")
    for r in rules:
        print(f"  {r['pages_below']:4d} pages  {r['prefix']:55s} {r['category'][:30]:30s} e.g. {', '.join(r['examples'])}")
    print(f"\nDraft written to {PROPOSED}. Review it: delete every rule that is NOT a product category "
          f"(help pages, offers, news...), then save the result as {RULES}.")


# ---------- discovery helpers (for writing config/products.json) ----------
def show_prefixes(depth: int):
    groups = defaultdict(list)
    for r in read_pages():
        seg = _path(r["url"]).strip("/").split("/")
        if len(seg) == depth + 1:                        # a direct child of a depth-N prefix
            groups["/" + "/".join(seg[:depth])].append(seg[-1])
    print(f"Prefixes (depth {depth}) with pages directly below them. A product category looks like a prefix\n"
          "whose children are product names:\n")
    for prefix, kids in sorted(groups.items()):
        print(f"  {prefix:55s} {len(kids):4d} pages   e.g. {', '.join(sorted(kids)[:3])}")


def show_tree(prefix: str):
    rows = [r for r in read_pages() if _path(r["url"]).lower().startswith(prefix.lower())]
    for r in sorted(rows, key=lambda r: r["url"]):
        print(f"  {_path(r['url'])}   |   {(r.get('h1') or r.get('title') or '')[:60]}")
    print(f"\n{len(rows)} pages")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--propose", action="store_true", help="draft category rules from the crawled pages")
    ap.add_argument("--prefixes", action="store_true")
    ap.add_argument("--depth", type=int, default=3)
    ap.add_argument("--tree")
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--index", action="store_true", help="also check the Chroma index")
    a = ap.parse_args()
    if a.propose:
        write_proposal(propose_rules())
    elif a.prefixes:
        show_prefixes(a.depth)
    elif a.tree:
        show_tree(a.tree)
    else:
        run(strict=a.strict)
        if a.index:
            from dotenv import load_dotenv
            load_dotenv()
            from pipeline.embed import load_store
            check_index(load_store(), strict=a.strict)