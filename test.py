
from pipeline.embed import load_store
from llm import get_llm

# 1. Load vector database and LLM
store = load_store()
llm = get_llm()

# 2. User question
question = "Which credit cards does Emirates NBD offer?"

# 3. Retrieve relevant chunks
retrieved_docs = store.similarity_search(question, k=5)

# 4. Prepare context from retrieved documents
context = "\n\n".join(
    f"""
    Source: {doc.metadata.get('url', '')}
    Title: {doc.metadata.get('title', '')}
    Content: {doc.page_content}
    """
    for doc in retrieved_docs
)

# 5. Create prompt
prompt = f"""
You are an Emirates NBD website assistant.

Answer the user's question using ONLY the provided context.

Rules:
- Do not use outside knowledge.
- If the answer is not available in the context, say you could not find the information on the website.
- Be accurate with product names, fees, eligibility and benefits.
- Include the source URLs used in your answer.

Context:
{context}

User Question:
{question}

Answer:
"""

# 6. Pass retrieved context to LLM
response = llm.invoke(prompt)

# 7. Display answer
print("\nQUESTION:")
print(question)

print("\nRETRIEVED DOCUMENTS:")
for i, doc in enumerate(retrieved_docs, 1):
    print(f"\n{i}. {doc.metadata.get('title', '')}")
    print(f"URL: {doc.metadata.get('url', '')}")
    print(doc.page_content[:300])

print("\nGENERATED ANSWER:")
print(response.content)
