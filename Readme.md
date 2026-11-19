# Website RAG Chatbot

A chatbot that answers questions about one website, using only what the website says.
It shows the page each answer came from, and says so when the website does not cover the question.

## How it works

**1. Build (one command):** crawl the website, clean the pages, cut them into chunks, turn each chunk into a
vector (embedding), and store the vectors in a database.

**2. Chat (every message):** the question is turned into a vector, the closest chunks are found, and an AI model writes
the answer from those chunks only. The answer comes back with links to the source pages.

The AI model is used for two things only: understanding follow-up questions, and writing the answer from the
retrieved text. It has no internet access and no tools.

## Run it

```bash
pip install -r requirements.txt
crawl4ai-setup                  # installs the browser used by the crawler
cp .env.example .env            # then edit .env (see below)

python build.py                 # builds the knowledge base
uvicorn api.main:app --reload   # starts the chatbot, then open http://localhost:8000
```

**Settings in `.env`**

| Setting | Meaning |
|---|---|
| `SITE_URL` | The website to read |
| `ANTHROPIC_API_KEY` | Key for the chat model (the only key needed; building the knowledge base needs none) |
| `MAX_DISTANCE` | How close a chunk must be to the question to be used (default 0.6) |

To use OpenAI instead: set `LLM_PROVIDER=openai`, `OPENAI_API_KEY` and `LLM_MODEL`, and run `pip install langchain-openai`.
Never commit `.env`.

**Other build commands**

| Command | What it does |
|---|---|
| `python build.py --report` | Shows how many pages the crawl will cover. Downloads nothing. |
| `python build.py --skip-crawl` | Rebuilds from pages already downloaded. |
| `python build.py --fresh` | Deletes downloaded pages and crawls again (use when the website changed). |

## Files

**Run these**

| File | What it does |
|---|---|
| `build.py` | Builds the knowledge base from the website: crawl, clean, chunk, embed, store. |
| `api/main.py` | Starts the chat server and serves the chat page. |
| `search.py` | Shows which chunks are found for a question (no AI model). Used to tune `MAX_DISTANCE`. |
| `check_kb.py` | Checks the knowledge base: chunk counts, leftover menu text, repeated text, samples. |

**`pipeline/` (builds the knowledge base)**

| File | What it does |
|---|---|
| `scope.py` | Decides which URLs to crawl and gives each URL one standard form. |
| `crawl.py` | Polite crawler: follows `robots.txt`, limits request rate, reads JavaScript pages, downloads PDFs. |
| `clean.py` | Turns HTML into clean text. Removes menus, footers, banners and hidden text. Keeps headings and tables. |
| `dedupe.py` | Removes text repeated on most pages (menus, footers). |
| `tables.py` | Rewrites table rows as single lines so a value never loses its column name. |
| `pdf.py` | Reads PDFs page by page, including tables. |
| `chunk.py` | Cuts pages into chunks of about 400 tokens by heading. Each chunk starts with its page title and section. |
| `embed.py` | Creates the vectors and stores them in the Chroma database. |

**`api/` (answers questions)**

| File | What it does |
|---|---|
| `rag.py` | The answering steps: understand the question, find chunks, ask the model, check the answer. |
| `prompts.py` | All prompt text in one place. |
| `llm.py` | Creates the chat model from `.env`. |
| `db.py` | Saves conversations and messages in SQLite. |

**Other:** `web/index.html` is the chat screen. `.env.example` is the settings template.

## What each chunk stores

`text`, `url` (the source link), `title` (the link label), `section` (the heading), and `page` (PDF page number, PDFs only).

## Chat API

`POST /chat` with `{"conversation_id": "...optional...", "message": "your question"}` returns:

```json
{
  "conversation_id": "9f2c...",
  "answer": "The annual fee is ... [1]",
  "sources": [{"id": 1, "title": "Page title", "url": "https://...", "page": null}],
  "status": "answered",
  "reason": "ok"
}
```

`status` is `answered` or `not_found`. When it is `not_found`, `reason` says why:
`no_relevant_chunks`, `model_not_found`, `no_citation` or `unsupported_numbers`.

## How wrong answers are prevented

1. If no chunk is close enough to the question, the bot declines without calling the model.
2. The model may use only the supplied chunks. If the answer is not there, it must say so.
3. An answer with no source citation is not shown.
4. Every number in the answer must appear in the retrieved text.
5. Page text is treated as data, never as instructions, and hidden page text is removed.

## Limitations

- "Which products do you offer?" is answered by search, so a long list may be incomplete.
- Tables inside PDFs may not be extracted perfectly.
- `MAX_DISTANCE` is a starting value and needs tuning on real questions.
- Refreshing the knowledge base means a full rebuild (`python build.py --fresh`).

## Crawling rules followed

Public pages only, `robots.txt` respected, at most one request started per second, no logins, no personal data.

## Use of AI assistants

Claude (Anthropic) was used to help write the code, the tests and this README. The author ran the build on the
website, reviewed the code, and is responsible for the design choices.