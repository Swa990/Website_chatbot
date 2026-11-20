
from pipeline.embed import load_store
from pipeline.Rag import answer_question
from llm import get_llm

store = load_store()
llm = get_llm()

query = "list the credit cards you have"

for i in range(3):
    print(f"\n{'=' * 70}")
    print(f"RUN {i + 1}")

    result = answer_question(query, [], store, llm)

    print("\nSTATUS:", result["status"])
    print("\nANSWER:", result["answer"])
    print("\nSOURCES:")

    for source in result["sources"]:
        print(source)
