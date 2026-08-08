"""
main.py — FastAPI application: all endpoints from all 3 parts.
Part 1A tasks: CRUD, dependency injection, middleware, CORS, background task,
               bulk import, raw-SQL reports.
"""
import os
import time
import asyncio
import json
import logging
from typing import Optional

from fastapi import (
    FastAPI, Depends, HTTPException, Header, BackgroundTasks,
    UploadFile, File, Query, Request, Response
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from dotenv import load_dotenv

import crud
import schemas
from database import engine, Base, get_db
from models import User, Note
from algorithms import (
    insertion_sort_by_key,
    binary_search_iterative,
    binary_search_recursive,
    linear_search,
)
from ai_service import get_ai_response, PROMPT_TEMPLATE
from semantic_search import rank_notes_by_query

load_dotenv()

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Create DB tables on startup
# ---------------------------------------------------------------------------
Base.metadata.create_all(bind=engine)

# ---------------------------------------------------------------------------
# App instance
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Zomato Notes",
    description="AI-Augmented Internal Knowledge Base",
    version="1.0.0",
)

# ---------------------------------------------------------------------------
# Task 6 — CORS
# Allowed origin: the exact origin the frontend is served from.
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5500", "http://localhost:5500"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Task 5 — Custom ASGI middleware: X-Process-Time header on every response
# ---------------------------------------------------------------------------
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    elapsed = time.perf_counter() - start
    response.headers["X-Process-Time"] = f"{elapsed:.6f}s"
    return response

# ---------------------------------------------------------------------------
# Task 4 — Auth-gate dependency (x-token header)
# Applied only to DELETE /notes/{id}
# ---------------------------------------------------------------------------
VALID_TOKEN = os.getenv("X_TOKEN", "zomato-secret")

def verify_token(x_token: str = Header(...)):
    if x_token != VALID_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid or missing x-token")

# ---------------------------------------------------------------------------
# Task 7 — Background task: simulated indexing step
# ---------------------------------------------------------------------------
def simulate_indexing(note_id: int):
    """Runs after POST /notes returns — simulates a 2-3 second indexing delay."""
    time.sleep(2)
    logger.info(f"[Background] Note {note_id} indexing complete.")

# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.get("/", tags=["Health"])
def root():
    return {"message": "Zomato Notes API is running"}

# ===========================================================================
# USERS
# ===========================================================================

@app.post("/users", response_model=schemas.UserResponse, status_code=201, tags=["Users"])
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    """Create a new user. Email must be unique."""
    existing = crud.get_user_by_email(db, user.email)
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    return crud.create_user(db, user)

# ===========================================================================
# NOTES
# ===========================================================================

@app.post("/notes", response_model=schemas.NoteResponseWithAI, status_code=201, tags=["Notes"])
def create_note(
    note: schemas.NoteCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Create a note. Validates owner exists (404 if not).
    Fires a background indexing task after returning.
    Returns an ai_suggestion field (populated in Part 3).
    """
    # Task 3 — owner-existence check
    owner = crud.get_user(db, note.owner_id)
    if not owner:
        raise HTTPException(status_code=404, detail=f"User {note.owner_id} not found")

    db_note = crud.create_note(db, note)

    # Task 7 — register background indexing job
    background_tasks.add_task(simulate_indexing, db_note.id)

    # Part 3 — call get_ai_response() server-side with the note's content
    ai_suggestion = None
    try:
        raw = get_ai_response(db_note.content, PROMPT_TEMPLATE)
        ai_suggestion = json.loads(raw)
    except Exception as exc:
        logger.warning(f"[AI] parse/call failed for note {db_note.id}: {exc}. raw={locals().get('raw','')}")
        ai_suggestion = None   # note is still created — never crash

    response = schemas.NoteResponseWithAI.model_validate(db_note)
    response.ai_suggestion = ai_suggestion
    return response


@app.get("/notes/search", tags=["Notes - Ranking"])
def search_notes(
    keyword: Optional[str] = Query(None),
    sort_by: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """
    Part 2 — Task 1: Insertion-sort powered search.

    Mode 1 — ?keyword=<value>
      Scores each note by the case-insensitive count of keyword occurrences
      in its content (string methods only, no regex), then returns the top 5
      sorted descending by score via insertion_sort_by_key.

    Mode 2 — ?sort_by=date
      Attaches a numeric created_at_epoch key to each note and sorts descending
      by creation time using the same insertion_sort_by_key — proving reuse.
    """
    all_notes = crud.get_notes(db)

    if sort_by == "date":
        # Attach epoch timestamp to each note dict
        notes_dicts = []
        for n in all_notes:
            d = {
                "id": n.id,
                "title": n.title,
                "content": n.content,
                "tag": n.tag,
                "owner_id": n.owner_id,
                "created_at": n.created_at.isoformat(),
                "created_at_epoch": n.created_at.timestamp(),
            }
            notes_dicts.append(d)
        sorted_notes = insertion_sort_by_key(notes_dicts, key="created_at_epoch")
        return sorted_notes

    if keyword:
        kw = keyword.lower()
        notes_dicts = []
        for n in all_notes:
            # Case-insensitive count using string methods only (no regex)
            score = n.content.lower().count(kw)
            d = {
                "id": n.id,
                "title": n.title,
                "content": n.content,
                "tag": n.tag,
                "owner_id": n.owner_id,
                "created_at": n.created_at.isoformat(),
                "score": score,
            }
            notes_dicts.append(d)
        sorted_notes = insertion_sort_by_key(notes_dicts, key="score")
        # Return top 5
        return sorted_notes[:5]

    raise HTTPException(
        status_code=400,
        detail="Provide ?keyword=<value> or ?sort_by=date"
    )


@app.get("/notes/lookup", tags=["Notes - Ranking"])
def lookup_note(
    title: str = Query(...),
    algo: str = Query("iterative"),
    db: Session = Depends(get_db),
):
    """
    Part 2 — Tasks 2 & 3: Exact-title binary search.

    Queries the DB ORDER BY title ASC (a real SQL-level sort, not a Python
    built-in) to get an alphabetically-sorted title list, then uses whichever
    binary search function the `algo` param selects.

    algo=iterative  → binary_search_iterative
    algo=recursive  → binary_search_recursive
    """
    # SQL-level alphabetical sort — NOT a Python built-in
    notes = db.query(Note).order_by(Note.title.asc()).all()

    sorted_titles = [n.title for n in notes]

    if algo == "recursive":
        idx = binary_search_recursive(
            sorted_titles, title, 0, len(sorted_titles) - 1
        )
    else:
        idx = binary_search_iterative(sorted_titles, title)

    if idx == -1:
        raise HTTPException(status_code=404, detail="Note not found")

    found = notes[idx]
    return {
        "id": found.id,
        "title": found.title,
        "content": found.content,
        "tag": found.tag,
        "owner_id": found.owner_id,
        "created_at": found.created_at.isoformat(),
        "algo_used": algo,
        "index_found": idx,
    }


@app.get("/notes/quickfind", tags=["Notes - Ranking"])
def quickfind_note(
    tag: str = Query(...),
    db: Session = Depends(get_db),
):
    """
    Part 2 — Task 4: Linear search with found-flag.

    Fetches all notes for the requested tag scope, then calls
    linear_search(notes, key="tag", value=<tag>) to return the first match.
    Returns a clear "not found" response (not a crash) for unknown tags.
    """
    all_notes = crud.get_notes(db)
    notes_dicts = [
        {
            "id": n.id,
            "title": n.title,
            "content": n.content,
            "tag": n.tag,
            "owner_id": n.owner_id,
            "created_at": n.created_at.isoformat(),
        }
        for n in all_notes
    ]

    result = linear_search(notes_dicts, key="tag", value=tag)

    if result is None:
        raise HTTPException(status_code=404, detail="Not found")

    return result


@app.get("/notes/smartsearch", tags=["Notes - AI"])
def smart_search(
    q: str = Query(...),
    db: Session = Depends(get_db),
):
    """
    Part 3 — Task 4 & 5: Local semantic search (no LLM call).

    Computes the query embedding and ranks the AI sample dataset notes
    (tag='ai-demo') by cosine similarity using all-MiniLM-L6-v2.
    Returns the top 3 with their similarity scores.
    Fully offline after the first model download — no API key needed.
    """
    # Fetch the ai-demo notes (the Part 3 sample dataset)
    ai_notes = crud.get_notes(db, tag="ai-demo")
    notes_dicts = [
        {
            "id": n.id,
            "title": n.title,
            "content": n.content,
            "tag": n.tag,
            "owner_id": n.owner_id,
            "created_at": n.created_at.isoformat(),
        }
        for n in ai_notes
    ]

    if not notes_dicts:
        raise HTTPException(status_code=404, detail="No ai-demo notes found. Run seed.py first.")

    results = rank_notes_by_query(q, notes_dicts, top_k=3)
    return results


@app.get("/notes", response_model=list[schemas.NoteResponse], tags=["Notes"])
def list_notes(tag: Optional[str] = Query(None), db: Session = Depends(get_db)):
    """List all notes. Filter by tag with ?tag=<value>."""
    return crud.get_notes(db, tag=tag)


@app.get("/notes/{note_id}", response_model=schemas.NoteResponse, tags=["Notes"])
def get_note(note_id: int, db: Session = Depends(get_db)):
    note = crud.get_note(db, note_id)
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    return note


@app.put("/notes/{note_id}", response_model=schemas.NoteResponse, tags=["Notes"])
def update_note(note_id: int, data: schemas.NoteUpdate, db: Session = Depends(get_db)):
    updated = crud.update_note(db, note_id, data)
    if not updated:
        raise HTTPException(status_code=404, detail="Note not found")
    return updated


@app.delete("/notes/{note_id}", status_code=200, tags=["Notes"],
            dependencies=[Depends(verify_token)])
def delete_note(note_id: int, db: Session = Depends(get_db)):
    """
    Delete a note. Requires correct x-token header.
    Returns 401/403 when token is missing or wrong.
    """
    deleted = crud.delete_note(db, note_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Note not found")
    return {"detail": f"Note {note_id} deleted"}

# ===========================================================================
# BULK IMPORT
# ===========================================================================

@app.post("/notes/import", status_code=201, tags=["Notes"])
async def import_notes(
    owner_id: int = Query(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    Task 8 — Bulk import notes from a .txt file.
    Each non-empty line becomes one Note owned by owner_id.
    Rejects with 404 if owner_id does not exist (no partial import).
    """
    # Owner-existence check before processing any lines
    owner = crud.get_user(db, owner_id)
    if not owner:
        raise HTTPException(status_code=404, detail=f"User {owner_id} not found")

    content = await file.read()
    lines = content.decode("utf-8").splitlines()
    non_empty = [line.strip() for line in lines if line.strip()]

    created = []
    for line in non_empty:
        note_data = schemas.NoteCreate(
            title=line[:120],   # use first 120 chars as title
            content=line,
            tag=None,
            owner_id=owner_id,
        )
        db_note = crud.create_note(db, note_data)
        created.append(db_note.id)

    return {"imported": len(created), "note_ids": created}

# ===========================================================================
# REPORTS — raw SQL
# ===========================================================================

@app.get("/reports/tag-summary", tags=["Reports"])
def tag_summary(db: Session = Depends(get_db)):
    """
    Task 9 — Raw SQL: tags with more than 1 note, each with its count.
    """
    return crud.report_tag_summary(db)


@app.get("/reports/long-notes", tags=["Reports"])
def long_notes(db: Session = Depends(get_db)):
    """
    Task 9 — Raw SQL with subquery: notes whose content length is above average.
    """
    return crud.report_long_notes(db)


@app.get("/reports/user-notes", tags=["Reports"])
def user_notes(db: Session = Depends(get_db)):
    """
    Task 9 — Raw SQL JOIN: each user with their total note count.
    """
    return crud.report_user_notes(db)
