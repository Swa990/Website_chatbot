
# """Step 4: embed every chunk and store it in a local Chroma vector database.

# Embedding model (set in .env):
#   EMBEDDING_PROVIDER=local   -> BAAI/bge-small-en-v1.5 on your CPU, no API key (default)
#   EMBEDDING_PROVIDER=openai  -> text-embedding-3-small, needs OPENAI_API_KEY

# The SAME model must be used at question time; data/index_info.json records which one
# built the index and load_store() refuses to open it with a different one.
# """
# import json
# import os
# from pathlib import Path

# CHUNKS = Path("data/chunks.jsonl")
# DB_DIR = Path("data/chroma")
# INFO = Path("data/index_info.json")
# COLLECTION = "site_chunks"
# BATCH = 64


# def get_embeddings():
#     """Return (embedding_object, 'provider:model')."""
#     provider = os.getenv("EMBEDDING_PROVIDER", "local").lower()
#     if provider == "openai":
#         from langchain_openai import OpenAIEmbeddings
#         model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
#         return OpenAIEmbeddings(model=model), f"openai:{model}"
#     from langchain_huggingface import HuggingFaceEmbeddings
#     model = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
#     emb = HuggingFaceEmbeddings(model_name=model, encode_kwargs={"normalize_embeddings": True})
#     return emb, f"local:{model}"


# def load_chunks(path: Path = CHUNKS):
#     from langchain_core.documents import Document
#     ids, docs = [], []
#     with Path(path).open(encoding="utf-8") as f:
#         for line in f:
#             r = json.loads(line)
#             meta = {k: r[k] for k in ("url", "title", "section", "page") if k in r}
#             ids.append(r["id"])
#             docs.append(Document(page_content=r["text"], metadata=meta))
#     if len(set(ids)) != len(ids):
#         raise ValueError("Duplicate chunk ids in chunks.jsonl")
#     return ids, docs


# def open_store(embeddings, reset: bool = False):
#     import chromadb
#     from chromadb.config import Settings
#     from langchain_chroma import Chroma

#     DB_DIR.mkdir(parents=True, exist_ok=True)
#     client = chromadb.PersistentClient(path=str(DB_DIR), settings=Settings(anonymized_telemetry=False))
#     if reset:  # full rebuild: chunks of pages removed from the site must disappear too
#         try:
#             client.delete_collection(COLLECTION)
#         except Exception:
#             pass
#     return Chroma(client=client, collection_name=COLLECTION, embedding_function=embeddings,
#                   collection_metadata={"hnsw:space": "cosine"})


# def build_index(chunks_path: Path = CHUNKS) -> int:
#     ids, docs = load_chunks(chunks_path)
#     if not docs:
#         raise SystemExit(f"No chunks in {chunks_path}. Run the crawl/chunk step first.")

#     embeddings, name = get_embeddings()
#     print(f"Embedding {len(docs)} chunks with {name} ...")

#     INFO.unlink(missing_ok=True)
#     store = open_store(embeddings, reset=True)

#     for i in range(0, len(docs), BATCH):
#         store.add_documents(docs[i:i + BATCH], ids=ids[i:i + BATCH])
#         print(f"  stored {min(i + BATCH, len(docs))}/{len(docs)}")

#     stored = len(store.get(include=[])["ids"])
#     if stored != len(docs):
#         raise RuntimeError(f"Stored {stored} vectors but expected {len(docs)}")

#     INFO.parent.mkdir(parents=True, exist_ok=True)
#     INFO.write_text(json.dumps({"embedding": name, "chunks": stored, "collection": COLLECTION}),
#                     encoding="utf-8")
#     print(f"Vector database ready: {stored} chunks in {DB_DIR}")
#     return stored


# def load_store():
#     """Open the existing index for querying (used by the chat API and search.py)."""
#     embeddings, name = get_embeddings()

#     if not INFO.exists():
#         raise FileNotFoundError(f"Index metadata not found at {INFO}. Run the embedding step first.")

#     built_with = json.loads(INFO.read_text(encoding="utf-8"))["embedding"]
#     if built_with != name:
#         raise RuntimeError(f"Index was built with '{built_with}' but .env now selects '{name}'. "
#                            "Use the same model, or rebuild the index.")

#     return open_store(embeddings, reset=False)


# if __name__ == "__main__":  # python -m pipeline.embed -> re-embed without re-crawling
#     from dotenv import load_dotenv
#     load_dotenv()
#     build_index()



"""Step 4: embed every chunk and store it in a local Chroma vector database.

Embedding model (set in .env):
  EMBEDDING_PROVIDER=local   -> BAAI/bge-small-en-v1.5 on your CPU, no API key (default)
  EMBEDDING_PROVIDER=openai  -> text-embedding-3-small, needs OPENAI_API_KEY

The SAME model must be used at question time; data/index_info.json records which one
built the index and load_store() refuses to open it with a different one.
"""
import json
import os
from pathlib import Path

CHUNKS = Path("data/chunks.jsonl")
DB_DIR = Path("data/chroma")
INFO = Path("data/index_info.json")
URL_PRODUCT = Path("data/url_product.json")  # written by pipeline/registry.py
COLLECTION = "site_chunks"
BATCH = 64


def get_embeddings():
    """Return (embedding_object, 'provider:model')."""
    provider = os.getenv("EMBEDDING_PROVIDER", "local").lower()
    if provider == "openai":
        from langchain_openai import OpenAIEmbeddings
        model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
        return OpenAIEmbeddings(model=model), f"openai:{model}"
    from langchain_huggingface import HuggingFaceEmbeddings
    model = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
    emb = HuggingFaceEmbeddings(model_name=model, encode_kwargs={"normalize_embeddings": True})
    return emb, f"local:{model}"


def load_chunks(path: Path = CHUNKS):
    from langchain_core.documents import Document
    ids, docs = [], []
    url_product = json.loads(URL_PRODUCT.read_text(encoding="utf-8")) if URL_PRODUCT.exists() else {}
    with Path(path).open(encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            meta = {k: r[k] for k in ("url", "title", "section", "page") if k in r}
            if r["url"] in url_product:
                meta["product_id"] = url_product[r["url"]]
            ids.append(r["id"])
            docs.append(Document(page_content=r["text"], metadata=meta))
    if len(set(ids)) != len(ids):
        raise ValueError("Duplicate chunk ids in chunks.jsonl")
    return ids, docs


def open_store(embeddings, reset: bool = False):
    import chromadb
    from chromadb.config import Settings
    from langchain_chroma import Chroma

    DB_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(DB_DIR), settings=Settings(anonymized_telemetry=False))
    if reset:  # full rebuild: chunks of pages removed from the site must disappear too
        try:
            client.delete_collection(COLLECTION)
        except Exception:
            pass  # collection did not exist yet
    return Chroma(client=client, collection_name=COLLECTION, embedding_function=embeddings,
                  collection_metadata={"hnsw:space": "cosine"})  # score = cosine distance (0 = identical)


def build_index(chunks_path: Path = CHUNKS) -> int:
    ids, docs = load_chunks(chunks_path)
    if not docs:
        raise SystemExit(f"No chunks in {chunks_path}. Run the crawl/chunk step first.")
    embeddings, name = get_embeddings()
    print(f"Embedding {len(docs)} chunks with {name} ...")
    store = open_store(embeddings, reset=True)
    for i in range(0, len(docs), BATCH):
        store.add_documents(docs[i:i + BATCH], ids=ids[i:i + BATCH])
        print(f"  stored {min(i + BATCH, len(docs))}/{len(docs)}")

    stored = len(store.get(include=[])["ids"])
    if stored != len(docs):
        raise RuntimeError(f"Stored {stored} vectors but expected {len(docs)}")
    INFO.write_text(json.dumps({"embedding": name, "chunks": stored, "collection": COLLECTION}),
                    encoding="utf-8")
    print(f"Vector database ready: {stored} chunks in {DB_DIR}")
    return stored


def load_store():
    """Open the existing index for querying (used by the chat API and search.py)."""
    embeddings, name = get_embeddings()
    built_with = json.loads(INFO.read_text(encoding="utf-8"))["embedding"]
    if built_with != name:
        raise RuntimeError(f"Index was built with '{built_with}' but .env now selects '{name}'. "
                           "Use the same model, or rebuild the index.")
    return open_store(embeddings, reset=False)


if __name__ == "__main__":  # python -m pipeline.embed  -> re-embed without re-crawling
    from dotenv import load_dotenv
    load_dotenv()
    build_index()