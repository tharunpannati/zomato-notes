"""
seed.py — Loads all seed/sample data into the database.
Run once after setup: python seed.py

Safe to run multiple times — skips rows that already exist.
"""
import sys
import os

# Ensure the backend directory is on the path when run directly
sys.path.insert(0, os.path.dirname(__file__))

from database import SessionLocal, engine, Base
from models import User, Note
from ranking_dataset import RANKING_DATASET
from ai_sample_notes import AI_SAMPLE_NOTES

# ---------------------------------------------------------------------------
# Exact seed data from spec
# ---------------------------------------------------------------------------
SEED_USERS = [
    {"id": 1, "name": "Alice", "email": "alice@example.com", "password": "alicepass123"},
    {"id": 2, "name": "Bob",   "email": "bob@example.com",   "password": "bobpass123"},
]

SEED_NOTES = [
    {"id": 1,  "owner_id": 1, "title": "Standup Summary",    "tag": "work",
     "content": "Discussed sprint progress, blockers on the payments API integration, and the plan for the demo on Friday."},
    {"id": 2,  "owner_id": 1, "title": "Sprint Retro Notes", "tag": "work",
     "content": "Retro highlighted communication gaps between frontend and backend teams and agreed on daily syncs going forward."},
    {"id": 3,  "owner_id": 2, "title": "One on One",         "tag": "work",
     "content": "Quick check-in, no blockers, discussed career growth goals for next quarter."},
    {"id": 4,  "owner_id": 1, "title": "Morning Run",        "tag": "health",
     "content": "Ran 5km along the river trail before breakfast, felt great."},
    {"id": 5,  "owner_id": 2, "title": "Doctor Visit",       "tag": "health",
     "content": "Annual checkup went well, blood pressure normal, scheduled next visit in six months."},
    {"id": 6,  "owner_id": 1, "title": "Pasta Recipe",       "tag": "recipes",
     "content": "Boil pasta, saute garlic in olive oil, add tomatoes, basil, and a pinch of chili flakes."},
    {"id": 7,  "owner_id": 2, "title": "Smoothie Recipe",    "tag": "recipes",
     "content": "Blend banana, spinach, almond milk, and a spoon of peanut butter for breakfast."},
    {"id": 8,  "owner_id": 1, "title": "Flight Booking",     "tag": "travel",
     "content": "Booked a round trip flight for the December vacation, window seat confirmed."},
    {"id": 9,  "owner_id": 2, "title": "Random Thought",     "tag": "random",
     "content": "Maybe the library needs a better recommendation system based on reading history."},
    {"id": 10, "owner_id": 1, "title": "Quote To Remember",  "tag": "random",
     "content": "Done is better than perfect, keep shipping."},
]


def seed():
    # Make sure tables exist
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # ----------------------------------------------------------------
        # 1. Seed users
        # ----------------------------------------------------------------
        for u in SEED_USERS:
            exists = db.query(User).filter(User.email == u["email"]).first()
            if not exists:
                db.add(User(
                    id=u["id"],
                    name=u["name"],
                    email=u["email"],
                    password=u["password"],
                ))
                print(f"  [users]   + {u['name']} ({u['email']})")
            else:
                print(f"  [users]   ~ {u['name']} already exists, skipping")
        db.commit()

        # ----------------------------------------------------------------
        # 2. Seed base notes (SEED_NOTES)
        # ----------------------------------------------------------------
        for n in SEED_NOTES:
            exists = db.query(Note).filter(Note.id == n["id"]).first()
            if not exists:
                db.add(Note(
                    id=n["id"],
                    title=n["title"],
                    content=n["content"],
                    tag=n["tag"],
                    owner_id=n["owner_id"],
                ))
                print(f"  [notes]   + '{n['title']}'")
            else:
                print(f"  [notes]   ~ '{n['title']}' already exists, skipping")
        db.commit()

        # ----------------------------------------------------------------
        # 3. Seed Part 2 ranking dataset (owner_id=1, tag="kb-demo")
        #    Titles are already alphabetically sorted — do NOT sort them.
        # ----------------------------------------------------------------
        for item in RANKING_DATASET:
            exists = db.query(Note).filter(
                Note.title == item["title"],
                Note.tag == "kb-demo"
            ).first()
            if not exists:
                db.add(Note(
                    title=item["title"],
                    content=item["content"],
                    tag="kb-demo",
                    owner_id=1,
                ))
                print(f"  [ranking] + '{item['title']}'")
            else:
                print(f"  [ranking] ~ '{item['title']}' already exists, skipping")
        db.commit()

        # ----------------------------------------------------------------
        # 4. Seed Part 3 AI sample notes (owner_id=2, tag="ai-demo")
        # ----------------------------------------------------------------
        for item in AI_SAMPLE_NOTES:
            exists = db.query(Note).filter(
                Note.title == item["title"],
                Note.tag == "ai-demo"
            ).first()
            if not exists:
                db.add(Note(
                    title=item["title"],
                    content=item["content"],
                    tag="ai-demo",
                    owner_id=2,
                ))
                print(f"  [ai]      + '{item['title']}'")
            else:
                print(f"  [ai]      ~ '{item['title']}' already exists, skipping")
        db.commit()

        print("\nSeeding complete.")

    except Exception as e:
        db.rollback()
        print(f"\nSeeding failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    print("Seeding database...\n")
    seed()
