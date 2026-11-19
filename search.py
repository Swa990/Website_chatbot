"""Quick retrieval check:  python search.py "minimum balance for savings account" """
import sys

from dotenv import load_dotenv

from pipeline.embed import load_store

load_dotenv()
query = " ".join(sys.argv[1:]) or input("Question: ")
store = load_store()
for rank, (doc, dist) in enumerate(store.similarity_search_with_score(query, k=5), start=1):
    m = doc.metadata
    page = f" (page {m['page']})" if "page" in m else ""
    print(f"\n#{rank}  distance={dist:.3f}  {m.get('title', '')} > {m.get('section', '')}")
    print(f"    {m['url']}{page}")
    print("    " + doc.page_content.replace("\n", " ")[:300])