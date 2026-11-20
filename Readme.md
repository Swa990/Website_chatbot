# Website RAG Chatbot

A Retrieval-Augmented Generation (RAG) chatbot that answers questions using content from a specified website. It retrieves relevant website content, generates answers grounded in that content, and provides source links. If the website does not contain the required information, the chatbot returns a fallback response.

## Live Demo

[Try the Website RAG Chatbot](https://websitechatbot-jnnwqyajsj2tdzl4xrzy4j.streamlit.app/)

## How It Works

**1. Knowledge Base Creation**

- Crawl public website pages and PDFs.
- Clean HTML and extract text and tables.
- Remove repeated content.
- Split content into heading-based chunks.
- Generate embeddings and store them in ChromaDB.

**2. Question Answering**

- Rewrite follow-up questions using conversation history.
- Retrieve relevant chunks from ChromaDB.
- Filter chunks based on retrieval relevance.
- Generate answers using the retrieved content.
- Validate citations and numerical information.
- Return the answer with source links.

The LLM is used for query rewriting and answer generation. It does not have web-search tools or direct internet access.

## Setup

```bash
pip install -r requirements.txt
crawl4ai-setup
cp .env.example .env
```

Configure your environment variables in `.env`.

```env
SITE_URL=https://www.example.com

LLM_PROVIDER=openai
LLM_BASE_URL=your_model_endpoint
LLM_API_KEY=your_api_key
LLM_MODEL=your_model_name

EMBEDDING_PROVIDER=local
EMBEDDING_MODEL=BAAI/bge-base-en-v1.5

MAX_DISTANCE=0.6
```

The OpenAI-compatible configuration also supports models hosted through compatible inference endpoints.

Never commit `.env` or API keys.

## Run

Build the knowledge base:

```bash
python build.py
```

Generate embeddings and create the ChromaDB index:

```bash
python -m pipeline.embed
```

Start the chatbot:

```bash
streamlit run app.py
```

To reuse previously downloaded website content:

```bash
python build.py --skip-crawl
```

## Project Structure

```text
project/
├── app.py
├── build.py
├── search.py
├── check_kb.py
├── db.py
├── llm.py
├── pipeline/
│   ├── scope.py
│   ├── crawler.py
│   ├── clean.py
│   ├── dedupe.py
│   ├── tables.py
│   ├── pdf.py
│   ├── chunk.py
│   ├── embed.py
│   ├── Rag.py
│   └── prompts.py
├── data/
├── requirements.txt
├── .env.example
└── README.md
```

## Main Components

| Component | Responsibility |
|---|---|
| `build.py` | Orchestrates crawling, cleaning, extraction, deduplication and chunk creation. |
| `scope.py` | URL normalization and crawl scope management. |
| `crawler.py` | Website crawling, robots.txt handling and PDF downloading. |
| `clean.py` | HTML cleaning and Markdown conversion. |
| `dedupe.py` | Removes repeated content across pages. |
| `tables.py` | Converts tables into self-contained text records. |
| `pdf.py` | Extracts PDF text and tables page by page. |
| `chunk.py` | Splits content into chunks while preserving headings. |
| `embed.py` | Generates embeddings and stores them in ChromaDB. |
| `Rag.py` | Handles query rewriting, retrieval, answer generation and validation. |
| `prompts.py` | Contains LLM prompts. |
| `llm.py` | Initializes the chat model from environment settings. |
| `db.py` | Stores conversations and messages in SQLite. |
| `app.py` | Provides the Streamlit chatbot interface. |

## Chunk Metadata

Each chunk contains:

- `text`: Extracted website content.
- `url`: Source page URL.
- `title`: Page title.
- `section`: Heading or section name.
- `page`: PDF page number, when applicable.

Chunking uses a target size of 1,500 characters with 150 characters of overlap.

## Conversation Storage

SQLite stores conversation history separately from the ChromaDB knowledge base.

- ChromaDB stores website content and embeddings.
- SQLite stores conversation IDs, user messages, assistant responses and source information.

Conversation history is used to understand follow-up questions.

## Answer Validation

The RAG pipeline includes the following checks:

1. If no relevant chunks are retrieved, the chatbot returns a fallback response.
2. The LLM is instructed to answer using only the retrieved content.
3. Answers without valid source citations are rejected.
4. Numerical information is checked against the retrieved text.
5. Website content is treated as data rather than instructions.

## Limitations

- Broad product-discovery questions may return incomplete lists.
- Complex PDF tables may not be extracted perfectly.
- Retrieval thresholds require evaluation and tuning.
- Website changes require rebuilding the knowledge base.

## Crawling Policy

- Public website pages only.
- Respect `robots.txt`.
- Apply request-rate limits.
- No login-protected pages or personal data.

## Use of AI Assistants

AI coding assistants were used to support code development and documentation. The implementation, testing and design decisions were reviewed by the author.
