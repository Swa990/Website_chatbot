

# new version


"""Step 2a: raw HTML -> clean markdown (headings and tables kept)."""
import re

from bs4 import BeautifulSoup
from markdownify import markdownify

# Tags that never hold product facts. <header> and <aside> are NOT here on purpose:
# they can hold real content, so they are handled separately / by cross-page dedupe.
NOISE_TAGS = ["script", "style", "noscript", "svg", "iframe", "nav", "footer",
              "form", "button", "template"]
NOISE_ATTR = re.compile(r"cookie|consent|gdpr", re.I)
HIDDEN_STYLE = re.compile(r"display\s*:\s*none|visibility\s*:\s*hidden", re.I)
ICON_LINE = re.compile(r"^\s*(icon-[\w-]+\s*)+$")  # icon class names rendered as text


def clean_html(html: str) -> tuple[str, str]:
    """Return (title, markdown)."""
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(strip=True) if soup.title else ""
    if not title and soup.h1:
        title = soup.h1.get_text(strip=True)

    for tag in soup(NOISE_TAGS):
        tag.decompose()

    # A <header> with no <h1> is the site header (logo/menu); one with an <h1> is a page hero.
    for header in soup.find_all("header"):
        if header.find("h1") is None:
            header.decompose()

    # Hidden text, cookie banners (this also blocks hidden prompt-injection text)
    for el in soup.find_all(True):
        if el.attrs is None:  # already removed together with a parent
            continue
        attrs = " ".join([" ".join(el.get("class", [])), el.get("id", "")])
        if (el.get("hidden") is not None
                or el.get("aria-hidden") == "true"
                or HIDDEN_STYLE.search(el.get("style", ""))
                or NOISE_ATTR.search(attrs)):
            el.decompose()

    main = soup.find("main") or soup.find("article") or soup.body or soup
    md = markdownify(str(main), heading_style="ATX")
    lines = [l.rstrip() for l in md.splitlines() if not ICON_LINE.match(l)]
    md = re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()
    return title, md
