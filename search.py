"""Quick retrieval check:  python search.py "minimum balance for savings account" """
import sys

from dotenv import load_dotenv

from pipeline.embed import load_store

load_dotenv()
query = " ".join(sys.argv[1:]) or input("Question: ")
store = load_store()
query = "list the credit cards you have"

results = store.similarity_search_with_score(query, k=10)

for i, (doc, score) in enumerate(results, 1):
    print(f"\nRANK: {i}")
    print(f"DISTANCE: {score:.4f}")
    print(f"URL: {doc.metadata.get('url')}")
    print(f"CONTENT: {doc.page_content[:500]}")