"""
crud.py — CRUD operations and raw-SQL reporting queries.
Part 1A — Tasks 3, 9
"""
from sqlalchemy.orm import Session
from sqlalchemy import text
from models import User, Note
from schemas import UserCreate, NoteCreate, NoteUpdate


# ---------------------------------------------------------------------------
# User CRUD
# ---------------------------------------------------------------------------

def create_user(db: Session, user: UserCreate) -> User:
    db_user = User(
        name=user.name,
        email=user.email,
        password=user.password,   # plaintext for demo only — never do this in production
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def get_user(db: Session, user_id: int) -> User | None:
    return db.query(User).filter(User.id == user_id).first()


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.query(User).filter(User.email == email).first()


# ---------------------------------------------------------------------------
# Note CRUD
# ---------------------------------------------------------------------------

def create_note(db: Session, note: NoteCreate) -> Note:
    db_note = Note(
        title=note.title,
        content=note.content,
        tag=note.tag,
        owner_id=note.owner_id,
    )
    db.add(db_note)
    db.commit()
    db.refresh(db_note)
    return db_note


def get_notes(db: Session, tag: str | None = None) -> list[Note]:
    query = db.query(Note)
    if tag:
        query = query.filter(Note.tag == tag)
    return query.all()


def get_note(db: Session, note_id: int) -> Note | None:
    return db.query(Note).filter(Note.id == note_id).first()


def update_note(db: Session, note_id: int, data: NoteUpdate) -> Note | None:
    db_note = get_note(db, note_id)
    if not db_note:
        return None
    if data.title is not None:
        db_note.title = data.title
    if data.content is not None:
        db_note.content = data.content
    if data.tag is not None:
        db_note.tag = data.tag
    db.commit()
    db.refresh(db_note)
    return db_note


def delete_note(db: Session, note_id: int) -> bool:
    db_note = get_note(db, note_id)
    if not db_note:
        return False
    db.delete(db_note)
    db.commit()
    return True


# ---------------------------------------------------------------------------
# Reporting — raw SQL queries (no ORM query builder)
# ---------------------------------------------------------------------------

def report_tag_summary(db: Session) -> list[dict]:
    """
    Raw SQL: tags with more than 1 note, each with its note count.
    """
    sql = text("""
        SELECT tag, COUNT(*) AS note_count
        FROM notes
        WHERE tag IS NOT NULL
        GROUP BY tag
        HAVING COUNT(*) > 1
        ORDER BY note_count DESC
    """)
    rows = db.execute(sql).fetchall()
    return [{"tag": row[0], "note_count": row[1]} for row in rows]


def report_long_notes(db: Session) -> list[dict]:
    """
    Raw SQL with subquery: notes whose content length is above the average
    content length across all notes.
    """
    sql = text("""
        SELECT id, title, tag, owner_id,
               LENGTH(content) AS content_length
        FROM notes
        WHERE LENGTH(content) > (
            SELECT AVG(LENGTH(content)) FROM notes
        )
        ORDER BY content_length DESC
    """)
    rows = db.execute(sql).fetchall()
    return [
        {
            "id": row[0],
            "title": row[1],
            "tag": row[2],
            "owner_id": row[3],
            "content_length": row[4],
        }
        for row in rows
    ]


def report_user_notes(db: Session) -> list[dict]:
    """
    Raw SQL JOIN: each user with their total note count.
    """
    sql = text("""
        SELECT u.id, u.name, u.email, COUNT(n.id) AS note_count
        FROM users u
        LEFT JOIN notes n ON u.id = n.owner_id
        GROUP BY u.id, u.name, u.email
        ORDER BY note_count DESC
    """)
    rows = db.execute(sql).fetchall()
    return [
        {
            "user_id": row[0],
            "name": row[1],
            "email": row[2],
            "note_count": row[3],
        }
        for row in rows
    ]
