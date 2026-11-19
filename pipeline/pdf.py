"""Step 2b: PDF -> markdown per page, tables kept as tables (pdfplumber)."""
import re

import pdfplumber


def _cell(c) -> str:
    return re.sub(r"\s+", " ", c or "").strip()


def _table_md(rows) -> str:
    rows = [[_cell(c) for c in r] for r in rows]
    rows = [r for r in rows if any(r)]
    if len(rows) < 2:
        return ""
    width = max(len(r) for r in rows)
    if width < 2:
        return ""
    rows = [r + [""] * (width - len(r)) for r in rows]
    lines = ["| " + " | ".join(rows[0]) + " |", "| " + " | ".join(["---"] * width) + " |"]
    lines += ["| " + " | ".join(r) + " |" for r in rows[1:]]
    return "\n".join(lines)


def extract_pdf(path) -> tuple[str, list[tuple[int, str]], int]:
    """Return (title, [(page_number, markdown), ...], number_of_tables_found)."""
    pages, n_tables = [], 0
    with pdfplumber.open(path) as pdf:
        for number, page in enumerate(pdf.pages, start=1):
            tables = page.find_tables()
            n_tables += len(tables)
            boxes = [t.bbox for t in tables]

            def outside(obj, boxes=boxes):
                try:
                    x = (obj["x0"] + obj["x1"]) / 2
                    y = (obj["top"] + obj["bottom"]) / 2
                except KeyError:
                    return True
                return not any(b[0] <= x <= b[2] and b[1] <= y <= b[3] for b in boxes)

            text = (page.filter(outside).extract_text() if boxes else page.extract_text()) or ""
            parts = [text.strip()] + [_table_md(t.extract()) for t in tables]
            pages.append((number, "\n\n".join(p for p in parts if p)))
    first = next((l.strip() for _, md in pages for l in md.splitlines() if l.strip()), "")
    return first[:120], pages, n_tables