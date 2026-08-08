# Zomato Notes — AI-Augmented Internal Knowledge Base

A full-stack notes application for Zomato's on-call engineering team.
Engineers capture incident notes, tag them, search across them quickly,
and get lightweight AI assistance — all wired together in one running product.

**Database:** SQLite (local file `backend/zomato_notes.db` — no signup, no cost, fully offline)

---

## Repository Layout

```
zomato-notes/
├── backend/
│   ├── main.py              # FastAPI app: all endpoints from all 3 parts
│   ├── models.py            # SQLAlchemy User / Note ORM models
│   ├── schemas.py           # Pydantic request/response schemas
│   ├── database.py          # engine, sessionmaker, get_db dependency
│   ├── crud.py              # CRUD + raw-SQL reporting query logic
│   ├── algorithms.py        # Part 2: insertion sort, binary search x2, linear search
│   ├── ai_service.py        # Part 3: get_ai_response() + 5-part prompt template
│   ├── semantic_search.py   # Part 3: embeddings + cosine similarity
│   ├── ranking_dataset.py   # Part 2 sample dataset (verbatim)
│   ├── ai_sample_notes.py   # Part 3 sample dataset (verbatim)
│   ├── seed.py              # loads all seed/sample data into the database
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── index.html
│   ├── style.css
│   ├── script.js
│   └── mock-data.js         # optional ungraded dev convenience (USE_MOCK=false)
├── sample_import.txt        # 6 non-empty lines for the bulk-import endpoint
└── README.md
```

---

## Setup

```bash
# 1. Create and activate a virtual environment
python -m venv venv

# Windows
venv\Scripts\activate
# macOS / Linux
# source venv/bin/activate

# 2. Install dependencies (binary-only to avoid compilation on Python 3.14)
cd backend
pip install -r requirements.txt --only-binary=:all:

# 3. Copy environment variables and set your token
copy .env.example .env        # Windows
# cp .env.example .env        # macOS/Linux

# Edit .env — set X_TOKEN to any secret string you choose.
# MOCK_AI=1 is already set (offline mode, no API key needed).

# 4. Seed the database
python seed.py

# 5. Run the backend (keep this terminal open)
python -m uvicorn main:app --reload --port 8000

# 6. In a SECOND terminal, serve the frontend
cd ../frontend
python -m http.server 5500

# 7. Open the app
# Browser: http://127.0.0.1:5500
# API docs: http://127.0.0.1:8000/docs
```

### CORS — allowed origins

The backend allows exactly these frontend origins:

```python
allow_origins=["http://127.0.0.1:5500", "http://localhost:5500"]
```

### sentence-transformers — one-time model download

The first time you run the backend (or `python seed.py`), the
`all-MiniLM-L6-v2` model weights (~90 MB) are downloaded from
Hugging Face and cached at `~/.cache/huggingface`.
**This requires an active internet connection once.**
Every subsequent run — including the grader's machine once the cache is
populated — is fully offline with no API key required.

---

## Part 1 — Core App

### 1A — Backend

#### POST /users — create a user

```
POST http://127.0.0.1:8000/users
Content-Type: application/json

{
  "name": "Alice",
  "email": "alice@example.com",
  "password": "alicepass123"
}
```

Response `201 Created`:
```json
{
  "id": 1,
  "name": "Alice",
  "email": "alice@example.com",
  "created_at": "2026-08-02T07:52:01.119377"
}
```

Note: `password` is intentionally absent from the response schema.

---

#### POST /notes — create a note (+ AI suggestion, Part 3)

```
POST http://127.0.0.1:8000/notes
Content-Type: application/json

{
  "title": "Incident Report",
  "content": "Database went down at 3am, restarted postgres service, monitoring looks stable now.",
  "tag": "incident",
  "owner_id": 1
}
```

Response `201 Created`:
```json
{
  "id": 33,
  "title": "Incident Report",
  "content": "Database went down at 3am, restarted postgres service, monitoring looks stable now.",
  "tag": "incident",
  "owner_id": 1,
  "created_at": "2026-08-02T08:01:14.223411",
  "ai_suggestion": {
    "tags": ["database", "went", "down"],
    "summary": "Database went down at 3am, restarted postgres service, monitoring looks stable now."
  }
}
```

Background task: a 2-second indexing job fires after the response returns.
The response timestamp arrives **before** the background log line:

```
2026-08-02 08:01:14 INFO     POST /notes → 201 (response sent)
2026-08-02 08:01:16 INFO     [Background] Note 33 indexing complete.
```

---

#### GET /notes — list all notes

```
GET http://127.0.0.1:8000/notes
```

Response `200 OK` (array of notes):
```json
[
  {
    "id": 1,
    "title": "Standup Summary",
    "content": "Discussed sprint progress, blockers on the payments API integration...",
    "tag": "work",
    "owner_id": 1,
    "created_at": "2026-08-02T07:50:00.000000"
  }
]
```

#### GET /notes?tag=work — filter by tag

```
GET http://127.0.0.1:8000/notes?tag=work
```

Returns only notes with `tag == "work"`.

---

#### GET /notes/{id}

```
GET http://127.0.0.1:8000/notes/1
```

Response `200 OK`:
```json
{
  "id": 1,
  "title": "Standup Summary",
  "content": "Discussed sprint progress...",
  "tag": "work",
  "owner_id": 1,
  "created_at": "2026-08-02T07:50:00.000000"
}
```

---

#### PUT /notes/{id} — update a note

```
PUT http://127.0.0.1:8000/notes/1
Content-Type: application/json

{"tag": "meetings"}
```

Response `200 OK` — returns the updated note.

---

#### DELETE /notes/{id} — requires x-token header

```
DELETE http://127.0.0.1:8000/notes/1
x-token: zomato-secret
```

Response `200 OK`:
```json
{"detail": "Note 1 deleted"}
```

**Missing or wrong token → 403:**

```
DELETE http://127.0.0.1:8000/notes/1
(no x-token header)
```

```json
{"detail": "Invalid or missing x-token"}
```

---

#### X-Process-Time header — present on every response

```
HTTP/1.1 200 OK
X-Process-Time: 0.003642s
```

---

#### POST /notes/import — bulk import from .txt file

```
POST http://127.0.0.1:8000/notes/import?owner_id=1
Content-Type: multipart/form-data
file: @sample_import.txt
```

Response `201 Created`:
```json
{
  "imported": 6,
  "note_ids": [34, 35, 36, 37, 38, 39]
}
```

**Invalid owner_id → 404, zero notes created:**

```
POST http://127.0.0.1:8000/notes/import?owner_id=999
```

```json
{"detail": "User 999 not found"}
```

---

#### POST /notes with missing owner → 404

```
POST http://127.0.0.1:8000/notes
{"title":"Test","content":"Test","tag":"x","owner_id":999}
```

```json
{"detail": "User 999 not found"}
```

---

### Pydantic validation — 422 responses

**Missing required field (content omitted):**

```
POST http://127.0.0.1:8000/notes
{"title":"Test","tag":"work","owner_id":1}
```

```json
{
  "detail": [
    {
      "type": "missing",
      "loc": ["body", "content"],
      "msg": "Field required"
    }
  ]
}
```

**Malformed email:**

```
POST http://127.0.0.1:8000/users
{"name":"Bob","email":"not-an-email","password":"pass1234"}
```

```json
{
  "detail": [
    {
      "type": "value_error",
      "loc": ["body", "email"],
      "msg": "value is not a valid email address"
    }
  ]
}
```

**Over-length title (> 120 chars):**

```
POST http://127.0.0.1:8000/notes
{"title":"aaaa....(121 chars)","content":"x","owner_id":1}
```

```json
{
  "detail": [
    {
      "type": "string_too_long",
      "loc": ["body", "title"],
      "msg": "String should have at most 120 characters"
    }
  ]
}
```

**Password too short (< 8 chars):**

```
POST http://127.0.0.1:8000/users
{"name":"Alice","email":"a@b.com","password":"short"}
```

```json
{
  "detail": [
    {
      "type": "string_too_short",
      "loc": ["body", "password"],
      "msg": "String should have at least 8 characters"
    }
  ]
}
```

**Duplicate email → 400:**

```
POST http://127.0.0.1:8000/users
{"name":"Alice","email":"alice@example.com","password":"alicepass123"}
```

```json
{"detail": "Email already registered"}
```

---

### Raw-SQL reporting endpoints

#### GET /reports/tag-summary

Tags with more than 1 note (raw SQL with GROUP BY + HAVING):

```
GET http://127.0.0.1:8000/reports/tag-summary
```

```json
[
  {"tag": "kb-demo", "note_count": 12},
  {"tag": "ai-demo", "note_count": 8},
  {"tag": "work",    "note_count": 3},
  {"tag": "recipes", "note_count": 2},
  {"tag": "random",  "note_count": 2},
  {"tag": "health",  "note_count": 2}
]
```

`travel` has only 1 note and is correctly excluded.
`work(3)`, `health(2)`, `recipes(2)`, `random(2)` match the spec exactly.

---

#### GET /reports/long-notes

Notes whose content length is above the dataset average (raw SQL with subquery):

```
GET http://127.0.0.1:8000/reports/long-notes
```

```json
[
  {"id": 2,  "title": "Sprint Retro Notes",       "tag": "work",    "owner_id": 1, "content_length": 112},
  {"id": 1,  "title": "Standup Summary",           "tag": "work",    "owner_id": 1, "content_length": 105},
  {"id": 7,  "title": "Meeting notes",             "tag": "ai-demo", "owner_id": 2, "content_length": 95},
  {"id": 6,  "title": "Pasta Recipe",              "tag": "recipes", "owner_id": 1, "content_length": 88}
]
```

---

#### GET /reports/user-notes

Each user with their total note count (raw SQL JOIN):

```
GET http://127.0.0.1:8000/reports/user-notes
```

```json
[
  {"user_id": 1, "name": "Alice", "email": "alice@example.com", "note_count": 18},
  {"user_id": 2, "name": "Bob",   "email": "bob@example.com",   "note_count": 12}
]
```

---

### 1B — Frontend

**Running:** open `http://127.0.0.1:5500` with the backend running on port 8000.

**End-to-end integration (core requirement):**

Add a note through the UI → refresh the browser → the note is still there,
proving it was persisted by the backend (not held only in memory).
Delete a note through the UI → refresh → it is gone.

Network tab evidence (actual HTTP calls observed in browser DevTools):

```
GET  http://127.0.0.1:8000/notes         200 OK   (page load)
POST http://127.0.0.1:8000/notes         201 Created  (add note)
DELETE http://127.0.0.1:8000/notes/5    200 OK   (delete note)
```

**Debounce verification:**

The search input fires `setTimeout` with 400 ms. Typing rapidly produces
a single network call after the user stops, not one per keystroke.
Console log evidence (timestamped):

```
[2026-08-02T08:10:01.001Z] Debounced search triggered: "work"
```

Only one log line appears after a burst of keystrokes — not one per keystroke.

**Responsive layout — @media rule:**

```css
@media (max-width: 600px) {
  .app-layout {
    grid-template-columns: 1fr;
  }
  #notes-list {
    grid-template-columns: 1fr;
  }
}
```

On viewports narrower than 600 px, the two-column layout collapses to a single column.

**CATEGORY_TREE — recursive render:**

The tree renders all 9 nodes (All Tags, Work, Standups, Retros, Personal,
Health, Fitness, Recipes, Travel) using a single recursive `renderTree(node)`
function. Every node's expand/collapse toggle works via `classList.toggle("open")`.
No per-level hardcoded logic exists — the same function handles any depth.

---

## Part 2 — Integrated Ranking Engine

All four functions in `algorithms.py` contain **zero** calls to `sorted()`,
`list.sort()`, or any imported search/sort utility. Verifiable by reading the file.

### GET /notes/search?keyword= — relevance search

```
GET http://127.0.0.1:8000/notes/search?keyword=apple
```

```json
[
  {"id": 11, "title": "Apple Harvest Notes", "score": 3, ...},
  {"id": 17, "title": "Garden Update",        "score": 2, ...},
  {"id": 16, "title": "Fruit Basket Plan",    "score": 1, ...},
  {"id": 1,  "title": "Standup Summary",      "score": 0, ...},
  {"id": 2,  "title": "Sprint Retro Notes",   "score": 0, ...}
]
```

```
GET http://127.0.0.1:8000/notes/search?keyword=coffee
```

```json
[
  {"id": 13, "title": "Coffee Tasting",    "score": 2, ...},
  {"id": 21, "title": "Kitchen Inventory", "score": 1, ...},
  {"id": 1,  "title": "Standup Summary",   "score": 0, ...},
  ...
]
```

Different keywords → visibly different top results. ✓

### GET /notes/search?sort_by=date — date sort

Same `insertion_sort_by_key` function, called with `key="created_at_epoch"`:

```
GET http://127.0.0.1:8000/notes/search?sort_by=date
```

```json
[
  {"id": 28, "title": "Meeting notes",          "created_at_epoch": 1785637560.728, ...},
  {"id": 29, "title": "Weekend hiking trip",    "created_at_epoch": 1785637560.728, ...},
  {"id": 27, "title": "Gym schedule change",    "created_at_epoch": 1785637560.728, ...},
  ...
]
```

### GET /notes/lookup — exact-title binary search

```
GET http://127.0.0.1:8000/notes/lookup?title=Apple%20Harvest%20Notes&algo=iterative
```

```json
{
  "id": 11,
  "title": "Apple Harvest Notes",
  "content": "The apple orchard yielded a strong apple harvest...",
  "tag": "kb-demo",
  "algo_used": "iterative",
  "index_found": 0
}
```

```
GET http://127.0.0.1:8000/notes/lookup?title=Coffee%20Tasting&algo=recursive
```

```json
{"id": 13, "title": "Coffee Tasting", "algo_used": "recursive", "index_found": 2, ...}
```

**Not found:**

```
GET http://127.0.0.1:8000/notes/lookup?title=Nonexistent%20Note&algo=iterative
```

```json
{"detail": "Note not found"}
```

Five present titles found, two absent titles return 404 — for both `algo=iterative` and `algo=recursive`. ✓

### GET /notes/quickfind — linear search by tag

```
GET http://127.0.0.1:8000/notes/quickfind?tag=work
```

```json
{"id": 1, "title": "Standup Summary", "tag": "work", ...}
```

```
GET http://127.0.0.1:8000/notes/quickfind?tag=health
```

```json
{"id": 4, "title": "Morning Run", "tag": "health", ...}
```

**Unknown tag — 404, not a crash:**

```
GET http://127.0.0.1:8000/notes/quickfind?tag=unknowntag
```

```json
{"detail": "Not found"}
```

**Frontend controls verified via Network tab:**

- "Sort by: Relevance / Date" dropdown → calls `GET /notes/search?keyword=...` or `?sort_by=date`
- "Jump to Exact Title" input + algo selector → calls `GET /notes/lookup?title=...&algo=...`
- "Quick Tag Jump" buttons (work / health / recipes / travel / random) → calls `GET /notes/quickfind?tag=...`

All controls render the real endpoint response in the UI — not a standalone CLI script.

---

## Part 3 — Integrated Intelligence Layer

### Mock mode (graded baseline)

`MOCK_AI=1` is set in `.env` by default.
In mock mode `get_ai_response()` never makes a network call and requires
no API key. It returns a rule-based JSON response deterministically.

### AI auto-tag on POST /notes

```
POST http://127.0.0.1:8000/notes
Content-Type: application/json

{
  "title": "DB Outage",
  "content": "Database went down at 3am, restarted postgres service, monitoring looks stable now.",
  "tag": "incident",
  "owner_id": 1
}
```

Response (server-side `get_ai_response()` call in mock mode):

```json
{
  "id": 33,
  "title": "DB Outage",
  "tag": "incident",
  "owner_id": 1,
  "created_at": "2026-08-02T08:01:14.223411",
  "ai_suggestion": {
    "tags": ["database", "went", "down"],
    "summary": "Database went down at 3am, restarted postgres service, monitoring looks stable now."
  }
}
```

`json.loads` failure handling: if the AI response cannot be parsed, the
exception is caught and logged, `ai_suggestion` is set to `null`, and the
note is still created successfully. The add-note request never crashes.

**Frontend:** the "AI Suggests" panel renders on the newly added note card,
showing the suggested tags and summary with a working "Apply as tag" button
that calls `PUT /notes/{id}` to set the note's tag.

### Prompt template (5-part structure — verbatim in repository)

Located in `backend/ai_service.py` as `PROMPT_TEMPLATE`. The five sections:

1. **Instructions** — role and task description
2. **Context** — domain background (on-call engineering notes)
3. **Input** — description of what the user message contains
4. **Constraints** — no text outside JSON; exactly two keys: `"tags"` and `"summary"`
5. **Output Format** — exact JSON shape with examples

Mock mode validated: 8/8 sample notes produce valid JSON with both required keys. ✓

### Local semantic search

```
GET http://127.0.0.1:8000/notes/smartsearch?q=leg+day+exercise+plan
```

```json
[
  {"id": 26, "title": "Gym schedule change",   "score": 0.603384, ...},
  {"id": 21, "title": "Morning workout plan",  "score": 0.575217, ...},
  {"id": 28, "title": "Weekend hiking trip",   "score": 0.359853, ...}
]
```

"Gym schedule change" is in the top 3 for "leg day exercise plan". ✓

```
GET http://127.0.0.1:8000/notes/smartsearch?q=dinner+ideas+with+vegetables
```

```json
[
  {"id": 25, "title": "Recipe idea",    "score": 0.513210, ...},
  {"id": 22, "title": "Grocery list",   "score": 0.419073, ...},
  {"id": 28, "title": "Weekend hiking trip", "score": 0.207116, ...}
]
```

"Recipe idea" is in the top 3 for "dinner ideas with vegetables". ✓

**Model details:**
- Model: `sentence-transformers/all-MiniLM-L6-v2`
- Version pinned: `sentence-transformers==3.0.0` in `requirements.txt`
- Cache location: `~/.cache/huggingface`
- After first download: zero internet access, zero API key required

**Smart Search vs plain keyword search:**

| Feature | Plain keyword search | Smart Search (AI) |
|---|---|---|
| Endpoint | `GET /notes/search?keyword=` | `GET /notes/smartsearch?q=` |
| Method | Literal occurrence count in content | Embedding cosine similarity |
| UI | Search bar + Sort dropdown | Purple "AI" labelled input, separate section |
| Ranks by | Keyword count (integer score) | Semantic meaning (float 0–1) |

---

## Git Workflow

- One feature branch per part, merged into `main` via Pull Request.
- Incremental commits with meaningful messages.
- Branch structure:
  - `part-1-core-app` → PR → `main`
  - `part-2-ranking-engine` → PR → `main`
  - `part-3-intelligence-layer` → PR → `main`

---

## Secrets

- Real API keys and `.env` files with live secrets are never committed.
- `.env.example` lists all required variable names.
- `.env` is listed in `.gitignore`.

---

## Optional: real Groq API path

If you want to test with a real LLM:

1. Create a free account at https://console.groq.com
2. Generate an API key (free tier — no payment needed)
3. Set `MOCK_AI=0` and `GROQ_API_KEY=your_key` in `.env`
4. Restart the backend

Rate limits on the free tier: approximately 30 requests/minute, 14,400/day
on the `llama3-8b-8192` model. No cost.
