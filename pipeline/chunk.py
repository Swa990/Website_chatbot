# """Step 3: split markdown into heading-based chunks using LangChain."""
# from langchain_core.documents import Document
# from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

# # ~1500 chars is roughly 350-400 tokens
# CHUNK_SIZE = 1500
# CHUNK_OVERLAP = 150
# MIN_CHARS = 80  # drop tiny fragments

# header_splitter = MarkdownHeaderTextSplitter(
#     headers_to_split_on=[("#", "h1"), ("##", "h2"), ("###", "h3")],
#     strip_headers=False,
# )
# size_splitter = RecursiveCharacterTextSplitter(
#     chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP,
#     separators=["\n\n", "\n", ". ", " "],
# )


# def chunk_page(url: str, title: str, markdown: str) -> list[Document]:
#     sections = header_splitter.split_text(markdown)  # 1) split by headings
#     pieces = size_splitter.split_documents(sections)  # 2) cap long sections

#     chunks = []
#     for p in pieces:
#         text = p.page_content.strip()
#         if len(text) < MIN_CHARS:
#             continue
#         # most specific heading available
#         section = p.metadata.get("h3") or p.metadata.get("h2") or p.metadata.get("h1") or ""
#         # prefix so each chunk is self-describing when retrieved alone
#         prefix = f"{title} > {section}" if section else title
#         chunks.append(Document(
#             page_content=f"{prefix}\n\n{text}",
#             metadata={"url": url, "title": title, "section": section},
#         ))
#     return chunks



"""Step 3: heading-based chunks with LangChain splitters."""
from langchain_core.documents import Document
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

from .tables import tables_to_records

CHUNK_SIZE = 1500    # characters, roughly 350-400 tokens
CHUNK_OVERLAP = 150
MIN_CHARS = 80       # drop tiny fragments

header_splitter = MarkdownHeaderTextSplitter(
    headers_to_split_on=[("#", "h1"), ("##", "h2"), ("###", "h3")], strip_headers=False)
size_splitter = RecursiveCharacterTextSplitter(
    chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP, separators=["\n\n", "\n", ". ", " "])


def chunk_page(url: str, title: str, markdown: str, page: int | None = None) -> list[Document]:
    """HTML pages are split by headings first. PDF pages (page given) have no markdown
    headings, so they are only size-split; the PDF page number is kept for citation."""
    markdown = tables_to_records(markdown)
    sections = (header_splitter.split_text(markdown) if page is None
                else [Document(page_content=markdown)])
    chunks = []
    for p in size_splitter.split_documents(sections):
        text = p.page_content.strip()
        if len(text) < MIN_CHARS:
            continue
        section = p.metadata.get("h3") or p.metadata.get("h2") or p.metadata.get("h1") or ""
        prefix = f"{title} > {section}" if section else title
        meta = {"url": url, "title": title, "section": section}
        if page is not None:
            meta["page"] = page
        chunks.append(Document(page_content=f"{prefix}\n\n{text}", metadata=meta))
    return chunks