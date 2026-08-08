"""
ai_service.py — Part 3: get_ai_response() + the 5-part prompt template.

Two modes:
  MOCK_AI=1  (default / graded baseline)
    Deterministic offline mock — no API key, no network, no signup needed.
    Returns a rule-based canned response: first 3 significant words as tags,
    first sentence truncated to 20 words as summary.

  MOCK_AI=0  (optional real path)
    Sends a chat-completion request to Groq's free API tier using the
    standardised system/user/assistant message-role format.
"""

import os
import json
import logging
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 5-Part Prompt Template (verbatim in repository — Part 3 Task 2)
# ---------------------------------------------------------------------------
PROMPT_TEMPLATE = """\
## Instructions
You are a note-tagging assistant for Zomato's on-call engineering team.
Read the note content provided by the user and return a structured JSON response.

## Context
Engineers capture short incident notes during on-call shifts.
Tags help them retrieve notes quickly under pressure.
A concise summary helps skim notes without reading the full content.

## Input
The user message contains the full text of a single note.

## Constraints
- Return ONLY a valid JSON object — no text, explanation, or markdown before or after it.
- The JSON object must have exactly two keys: "tags" and "summary".
- "tags": a list of 1–3 short, lowercase keyword strings relevant to the note.
- "summary": one sentence of at most 20 words that captures the note's key point.
- Do not include any text outside the JSON object.

## Output Format
{"tags": ["keyword1", "keyword2"], "summary": "One concise sentence of at most 20 words."}
"""

# ---------------------------------------------------------------------------
# Mock AI — deterministic, offline, no API key required
# ---------------------------------------------------------------------------
# Common English stop-words to skip when picking "significant" words
_STOPWORDS = {
    "the","a","an","and","or","but","in","on","at","to","for","of","with",
    "is","was","are","were","be","been","being","have","has","had","do","does",
    "did","will","would","could","should","may","might","shall","can","it",
    "its","this","that","these","those","i","we","you","he","she","they",
    "my","our","your","his","her","their","from","by","as","so","if","no",
    "not","up","out","about","after","before","into","than","then","there",
    "when","where","which","who","how","what","all","also","just","over",
}

def _mock_response(note_content: str) -> str:
    """
    Rule-based canned response — used when MOCK_AI=1.
    Tags: first 3 significant (non-stopword) words from the content.
    Summary: first sentence, truncated to 20 words.
    """
    # Extract tags — first 3 significant words (lowercase, alpha only)
    words = note_content.lower().split()
    significant = []
    for w in words:
        cleaned = "".join(c for c in w if c.isalpha())
        if cleaned and cleaned not in _STOPWORDS and cleaned not in significant:
            significant.append(cleaned)
        if len(significant) == 3:
            break

    tags = significant if significant else ["general"]

    # Summary — first sentence, max 20 words
    first_sentence = note_content.split(".")[0].strip()
    summary_words = first_sentence.split()[:20]
    summary = " ".join(summary_words)
    if not summary.endswith("."):
        summary += "."

    return json.dumps({"tags": tags, "summary": summary})


# ---------------------------------------------------------------------------
# Real AI path — Groq free tier (optional, only when MOCK_AI=0)
# ---------------------------------------------------------------------------

def _real_response(user_message: str, system_prompt: str) -> str:
    """
    Sends a chat-completion request to Groq using the standardised
    system / user / assistant message-role format.
    Requires GROQ_API_KEY in the environment.
    """
    try:
        from groq import Groq   # pip install groq  (optional dependency)
    except ImportError:
        raise RuntimeError(
            "groq package not installed. Run: pip install groq  "
            "or set MOCK_AI=1 to use the offline mock."
        )

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY not set. Add it to your .env file "
            "or set MOCK_AI=1 to use the offline mock."
        )

    client = Groq(api_key=api_key)
    chat = client.chat.completions.create(
        model="llama3-8b-8192",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_message},
        ],
        temperature=0.2,
        max_tokens=200,
    )
    return chat.choices[0].message.content


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def get_ai_response(user_message: str, system_prompt: str = PROMPT_TEMPLATE) -> str:
    """
    Returns a JSON string with keys "tags" and "summary".

    Behaviour:
      MOCK_AI=1  → deterministic offline mock (no API key, no internet).
                   This is the graded default.
      MOCK_AI=0  → real Groq API call (requires GROQ_API_KEY in .env).
    """
    mock_mode = os.getenv("MOCK_AI", "1") == "1"

    if mock_mode:
        logger.info("[AI] Mock mode — returning rule-based response.")
        return _mock_response(user_message)
    else:
        logger.info("[AI] Real mode — calling Groq API.")
        return _real_response(user_message, system_prompt)
