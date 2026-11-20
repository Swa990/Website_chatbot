# # """The question-answering logic: rewrite -> retrieve -> gate -> generate -> verify.

# # Pure functions that take the vector store and the LLM as arguments, so they can be tested
# # without a network. Thresholds come from .env and are read at call time.
# # """
# # import json
# # import os
# # import re

# # from . import prompts


# # def _num(name: str, default: float) -> float:
# #     return float(os.getenv(name, default))


# # def text_of(response) -> str:
# #     """LangChain message -> plain string (content can be a string or a list of blocks)."""
# #     content = getattr(response, "content", response)
# #     if isinstance(content, list):
# #         return "".join(b.get("text", "") if isinstance(b, dict) else str(b) for b in content)
# #     return str(content)


# # # ---------- 1. follow-up handling ----------
# # def rewrite_queries(llm, message: str, history: list[dict]) -> list[str]:
# #     """Turn the latest message into 1-3 standalone search queries."""
# #     if not history:
# #         return [message]
# #     convo = "\n".join(f"{m['role']}: {m['content'][:500]}" for m in history)
# #     raw = text_of(llm.invoke([
# #         ("system", prompts.REWRITE_SYSTEM),
# #         ("human", f"Conversation so far:\n{convo}\n\nLatest message: {message}"),
# #     ])).strip()
# #     raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.M).strip()
# #     try:
# #         queries = [q.strip() for q in json.loads(raw)["queries"] if isinstance(q, str) and q.strip()][:3]
# #     except (ValueError, KeyError, TypeError):
# #         queries = []
# #     if not queries:  # rewriter failed: fall back to previous question + new message
# #         last_user = next((m["content"] for m in reversed(history) if m["role"] == "user"), "")
# #         queries = [f"{last_user} {message}".strip()]
# #     return queries


# # # ---------- 2. retrieval ----------
# # def retrieve(store, queries: list[str]):
# #     """Top chunks per query, interleaved so every query (every product in a comparison)
# #     gets a place in the context. Chunks farther than MAX_DISTANCE are dropped."""
# #     k = int(_num("K_PER_QUERY", 4))
# #     cap = int(_num("MAX_CONTEXT_CHUNKS", 10))
# #     max_distance = _num("MAX_DISTANCE", 0.6)
# #     per_query = [store.similarity_search_with_score(q, k=k) for q in queries]

# #     picked, seen = [], set()
# #     for rank in range(k):
# #         for results in per_query:
# #             if rank < len(results):
# #                 doc, dist = results[rank]
# #                 if dist <= max_distance and doc.page_content not in seen:
# #                     seen.add(doc.page_content)
# #                     picked.append((doc, dist))
# #     return picked[:cap]


# # def build_context(chunks) -> str:
# #     blocks = []
# #     for i, (doc, _) in enumerate(chunks, start=1):
# #         m = doc.metadata
# #         page = f' page="{m["page"]}"' if "page" in m else ""
# #         body = doc.page_content.replace("</source", "")  # stop page text from closing the tag
# #         blocks.append(f'<source id="{i}" title="{m.get("title", "")}" url="{m["url"]}"{page}>\n{body}\n</source>')
# #     return "\n\n".join(blocks)


# # # ---------- 3. checks on the answer ----------
# # _CITE = re.compile(r"\[(\d+)\]")
# # _LIST_MARK = re.compile(r"^\s*\d+[.)]\s", re.M)
# # _NUMBER = re.compile(r"\d+(?:\.\d+)?")


# # def numbers_in(text: str) -> set[str]:
# #     text = _LIST_MARK.sub("", _CITE.sub("", text)).replace(",", "")
# #     return set(_NUMBER.findall(text))


# # def unsupported_numbers(answer: str, context: str) -> set[str]:
# #     """Numbers written in the answer that appear nowhere in the retrieved text."""
# #     return numbers_in(answer) - numbers_in(context)


# # def not_found(reason: str) -> dict:
# #     return {"answer": prompts.FALLBACK, "sources": [], "status": "not_found", "reason": reason}


# # # ---------- 4. the whole flow ----------
# # def answer_question(message: str, history: list[dict], store, llm) -> dict:
# #     queries = rewrite_queries(llm, message, history)
# #     chunks = retrieve(store, queries)
# #     if not chunks:
# #         return not_found("no_relevant_chunks")

# #     context = build_context(chunks)
# #     resolved = "" if queries == [message] else f"\nResolved search queries: {' | '.join(queries)}"
# #     answer = text_of(llm.invoke([
# #         ("system", prompts.ANSWER_SYSTEM),
# #         ("human", f"Sources:\n{context}\n\nVisitor question: {message}{resolved}"),
# #     ])).strip()

# #     if answer.upper().startswith("NOT_FOUND"):
# #         return not_found("model_not_found")

# #     cited = sorted({int(n) for n in _CITE.findall(answer) if 1 <= int(n) <= len(chunks)})
# #     if not cited:  # an answer we cannot trace to a page is not shown
# #         return not_found("no_citation")

# #     bad = unsupported_numbers(answer, context)
# #     if bad:
# #         return not_found("unsupported_numbers:" + ",".join(sorted(bad)))

# #     sources = []
# #     for n in cited:
# #         m = chunks[n - 1][0].metadata
# #         sources.append({"id": n, "title": m.get("title", ""), "url": m["url"], "page": m.get("page")})
# #     return {"answer": answer, "sources": sources, "status": "answered", "reason": "ok"}






# import json
# import os
# import re

# from . import prompts


# def _debug_enabled() -> bool:
#     return os.getenv("RAG_DEBUG", "false").lower() == "true"


# def text_of(response) -> str:
#     content = getattr(response, "content", response)

#     if isinstance(content, list):
#         return "".join(
#             block.get("text", "") if isinstance(block, dict) else str(block)
#             for block in content
#         )

#     return str(content)


# # ---------- 1. follow-up handling ----------

# def rewrite_queries(llm, message: str, history: list[dict]) -> list[str]:
#     if not history:
#         return [message]

#     convo = "\n".join(
#         f"{m['role']}: {m['content'][:500]}"
#         for m in history
#     )

#     raw = text_of(llm.invoke([
#         ("system", prompts.REWRITE_SYSTEM),
#         ("human", f"Conversation so far:\n{convo}\n\nLatest message: {message}")
#     ])).strip()

#     raw = re.sub(r"^```(?:json)?\s*|```$", "", raw, flags=re.M).strip()

#     try:
#         queries = [
#             q.strip()
#             for q in json.loads(raw)["queries"]
#             if isinstance(q, str) and q.strip()
#         ][:3]
#     except (ValueError, KeyError, TypeError):
#         queries = []

#     if not queries:
#         last_user = next(
#             (m["content"] for m in reversed(history) if m["role"] == "user"),
#             ""
#         )
#         queries = [f"{last_user} {message}".strip()]

#     return list(dict.fromkeys(queries))


# # ---------- 2. basic similarity retrieval ----------

# def retrieve(store, queries: list[str]):
#     k = int(os.getenv("K_PER_QUERY", "10"))

#     retrieved = []
#     seen = set()

#     for query in queries:
#         results = store.similarity_search_with_score(query, k=k)

#         if _debug_enabled():
#             print(f"\n{'=' * 70}")
#             print(f"QUERY: {query}")
#             print(f"RETRIEVED: {len(results)}")

#         for rank, (doc, distance) in enumerate(results, start=1):
#             # key = (doc.page_content, doc.metadata.get("url", ""))
#             key = re.sub(r"\s+", " ", doc.page_content).strip().lower()

#             if key in seen:
#                 continue

#             seen.add(key)
#             retrieved.append((doc, distance))

#             if _debug_enabled():
#                 print(f"\nRANK: {rank}")
#                 print(f"DISTANCE: {distance:.4f}")
#                 print(f"URL: {doc.metadata.get('url', 'Unknown')}")
#                 print(f"TITLE: {doc.metadata.get('title', 'Unknown')}")
#                 print(f"CONTENT: {doc.page_content[:500]}")

#     if _debug_enabled():
#         print(f"\n{'=' * 70}")
#         print(f"TOTAL RETRIEVED DOCUMENTS: {len(retrieved)}")

#     return retrieved


# # ---------- 3. context building ----------

# def build_context(chunks) -> str:
#     blocks = []

#     for i, (doc, _) in enumerate(chunks, start=1):
#         metadata = doc.metadata

#         title = metadata.get("title", "")
#         url = metadata.get("url", "Unknown")
#         page = f' page="{metadata["page"]}"' if "page" in metadata else ""

#         body = doc.page_content.replace("</source", "")

#         blocks.append(
#             f'<source id="{i}" title="{title}" url="{url}"{page}>\n'
#             f'{body}\n'
#             f'</source>'
#         )

#     return "\n\n".join(blocks)


# # ---------- 4. answer verification ----------

# _CITE = re.compile(r"\[(\d+)\]")
# _LIST_MARK = re.compile(r"^\s*\d+[.)]\s", re.M)
# _NUMBER = re.compile(r"\d+(?:\.\d+)?")


# def numbers_in(text: str) -> set[str]:
#     text = _LIST_MARK.sub("", _CITE.sub("", text)).replace(",", "")
#     return set(_NUMBER.findall(text))


# def unsupported_numbers(answer: str, context: str) -> set[str]:
#     return numbers_in(answer) - numbers_in(context)


# def not_found(reason: str) -> dict:
#     return {
#         "answer": prompts.FALLBACK,
#         "sources": [],
#         "status": "not_found",
#         "reason": reason
#     }


# # ---------- 5. complete RAG pipeline ----------

# def answer_question(message: str, history: list[dict], store, llm) -> dict:
#     queries = rewrite_queries(llm, message, history)

#     if _debug_enabled():
#         print("\nSEARCH QUERIES:", queries)

#     chunks = retrieve(store, queries)

#     if not chunks:
#         return not_found("no_relevant_chunks")

#     context = build_context(chunks)

#     resolved = (
#         ""
#         if queries == [message]
#         else f"\nResolved search queries: {' | '.join(queries)}"
#     )

#     answer = text_of(llm.invoke([
#         ("system", prompts.ANSWER_SYSTEM),
#         (
#             "human",
#             f"Sources:\n{context}\n\n"
#             f"Visitor question: {message}{resolved}"
#         )
#     ])).strip()

#     if _debug_enabled():
#         print("\nGENERATED ANSWER:")
#         print(answer)

#     if answer.upper().startswith("NOT_FOUND"):
#         return not_found("model_not_found")

#     cited = sorted({
#         int(number)
#         for number in _CITE.findall(answer)
#         if 1 <= int(number) <= len(chunks)
#     })

#     if not cited:
#         return not_found("no_citation")

#     bad = unsupported_numbers(answer, context)

#     if bad:
#         return not_found(
#             "unsupported_numbers:" + ",".join(sorted(bad))
#         )

#     sources = []

#     for number in cited:
#         metadata = chunks[number - 1][0].metadata

#         sources.append({
#             "id": number,
#             "title": metadata.get("title", ""),
#             "url": metadata.get("url", ""),
#             "page": metadata.get("page")
#         })

#     return {
#         "answer": answer,
#         "sources": sources,
#         "status": "answered",
#         "reason": "ok"
#     }



# reranker code



import json
import re

from sentence_transformers import CrossEncoder
from . import prompts


RETRIEVAL_K = 30
RERANK_TOP_K = 10
RERANKER_MODEL = "BAAI/bge-reranker-base"

_reranker = None


def get_reranker():
    global _reranker

    if _reranker is None:
        _reranker = CrossEncoder(
            RERANKER_MODEL,
            device="cpu",
            max_length=512
        )

    return _reranker


def debug_enabled():
    import os
    return os.getenv("RAG_DEBUG", "false").lower() == "true"


def text_of(response):
    content = getattr(response, "content", response)

    if isinstance(content, list):
        return "".join(
            block.get("text", "") if isinstance(block, dict) else str(block)
            for block in content
        )

    return str(content)


# ---------- 1. follow-up handling ----------

def rewrite_queries(llm, message: str, history: list[dict]) -> list[str]:
    if not history:
        return [message]

    convo = "\n".join(
        f"{m['role']}: {m['content'][:500]}"
        for m in history
    )

    raw = text_of(llm.invoke([
        ("system", prompts.REWRITE_SYSTEM),
        ("human", f"Conversation so far:\n{convo}\n\nLatest message: {message}")
    ])).strip()

    raw = re.sub(r"^```(?:json)?\s*|```$", "", raw, flags=re.M).strip()

    try:
        queries = [
            q.strip()
            for q in json.loads(raw)["queries"]
            if isinstance(q, str) and q.strip()
        ][:3]
    except (ValueError, KeyError, TypeError):
        queries = []

    if not queries:
        last_user = next(
            (m["content"] for m in reversed(history) if m["role"] == "user"),
            ""
        )
        queries = [f"{last_user} {message}".strip()]

    return list(dict.fromkeys(queries))


# ---------- 2. similarity retrieval + reranking ----------

def retrieve(store, queries: list[str]):
    candidates = []
    seen = set()

    for query in queries:
        results = store.similarity_search_with_score(
            query,
            k=RETRIEVAL_K
        )

        if debug_enabled():
            print(f"\nQUERY: {query}")
            print(f"INITIAL RETRIEVAL: {len(results)}")

        for doc, distance in results:
            key = re.sub(
                r"\s+",
                " ",
                doc.page_content
            ).strip().lower()

            if key in seen:
                continue

            seen.add(key)
            candidates.append((doc, distance))

    if not candidates:
        return []

    reranker = get_reranker()

    pairs = [
        (query, doc.page_content)
        for doc, _ in candidates
        for query in queries
    ]

    scores = reranker.predict(
        pairs,
        batch_size=16,
        show_progress_bar=False
    )

    query_count = len(queries)

    reranked = []

    for i, (doc, distance) in enumerate(candidates):
        start = i * query_count
        end = start + query_count

        relevance_score = float(max(scores[start:end]))

        reranked.append((
            doc,
            distance,
            relevance_score
        ))

    reranked.sort(
        key=lambda x: x[2],
        reverse=True
    )

    final_results = reranked[:RERANK_TOP_K]

    if debug_enabled():
        print(f"\nINITIAL CANDIDATES: {len(candidates)}")
        print(f"AFTER RERANKING: {len(final_results)}")

        for rank, (doc, distance, score) in enumerate(final_results, 1):
            print(f"\nRANK: {rank}")
            print(f"RERANK SCORE: {score:.4f}")
            print(f"CHROMA DISTANCE: {distance:.4f}")
            print(f"URL: {doc.metadata.get('url', 'Unknown')}")
            print(f"TITLE: {doc.metadata.get('title', 'Unknown')}")
            print(f"CONTENT: {doc.page_content[:500]}")

    return [
        (doc, distance)
        for doc, distance, _ in final_results
    ]


# ---------- 3. context building ----------

def build_context(chunks):
    blocks = []

    for i, (doc, _) in enumerate(chunks, start=1):
        metadata = doc.metadata

        title = metadata.get("title", "")
        url = metadata.get("url", "Unknown")
        page = f' page="{metadata["page"]}"' if "page" in metadata else ""

        body = doc.page_content.replace("</source", "")

        blocks.append(
            f'<source id="{i}" title="{title}" url="{url}"{page}>\n'
            f'{body}\n'
            f'</source>'
        )

    return "\n\n".join(blocks)


# ---------- 4. answer verification ----------

_CITE = re.compile(r"\[(\d+)\]")
_LIST_MARK = re.compile(r"^\s*\d+[.)]\s", re.M)
_NUMBER = re.compile(r"\d+(?:\.\d+)?")


def numbers_in(text: str) -> set[str]:
    text = _LIST_MARK.sub("", _CITE.sub("", text)).replace(",", "")
    return set(_NUMBER.findall(text))


def unsupported_numbers(answer: str, context: str) -> set[str]:
    return numbers_in(answer) - numbers_in(context)


def not_found(reason: str) -> dict:
    return {
        "answer": prompts.FALLBACK,
        "sources": [],
        "status": "not_found",
        "reason": reason
    }


# ---------- 5. complete RAG pipeline ----------

def answer_question(message: str, history: list[dict], store, llm) -> dict:
    queries = rewrite_queries(llm, message, history)

    if debug_enabled():
        print("\nSEARCH QUERIES:", queries)

    chunks = retrieve(store, queries)

    if not chunks:
        return not_found("no_relevant_chunks")

    context = build_context(chunks)

    resolved = (
        ""
        if queries == [message]
        else f"\nResolved search queries: {' | '.join(queries)}"
    )

    answer = text_of(llm.invoke([
        ("system", prompts.ANSWER_SYSTEM),
        (
            "human",
            f"Sources:\n{context}\n\n"
            f"Visitor question: {message}{resolved}"
        )
    ])).strip()

    if debug_enabled():
        print("\nGENERATED ANSWER:")
        print(answer)

    if answer.upper().startswith("NOT_FOUND"):
        return not_found("model_not_found")

    cited = sorted({
        int(number)
        for number in _CITE.findall(answer)
        if 1 <= int(number) <= len(chunks)
    })

    if not cited:
        return not_found("no_citation")

    bad = unsupported_numbers(answer, context)

    if bad:
        return not_found(
            "unsupported_numbers:" + ",".join(sorted(bad))
        )

    sources = []

    for number in cited:
        metadata = chunks[number - 1][0].metadata

        sources.append({
            "id": number,
            "title": metadata.get("title", ""),
            "url": metadata.get("url", ""),
            "page": metadata.get("page")
        })

    return {
        "answer": answer,
        "sources": sources,
        "status": "answered",
        "reason": "ok"
    }
