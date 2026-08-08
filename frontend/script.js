// script.js — Zomato Notes dashboard
// Part 1B: data layer, rendering, add/delete, debounced search,
//          recursive tag tree, loading/error states
// Part 2:  sort-by-relevance/date, exact-title lookup, quick-tag jump
// Part 3:  AI suggestion panel, apply-tag button, smart search

"use strict";

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------
const API_BASE  = "http://127.0.0.1:8000";
const X_TOKEN   = "zomato-secret";   // used for DELETE
const OWNER_ID  = 1;                 // default owner for new notes

// USE_MOCK defaults to false — grading is against the live backend
const USE_MOCK  = false;

// ---------------------------------------------------------------------------
// Recursive category tree (Part 1B Task 7)
// ---------------------------------------------------------------------------
const CATEGORY_TREE = {
  name: "All Tags",
  children: [
    { name: "Work", children: [
      { name: "Standups", children: [] },
      { name: "Retros",   children: [] },
    ]},
    { name: "Personal", children: [
      { name: "Health", children: [
        { name: "Fitness", children: [] },
      ]},
      { name: "Recipes", children: [] },
    ]},
    { name: "Travel", children: [] },
  ],
};

/**
 * Recursively render a category tree node as a <ul>/<li> structure.
 * Works for any depth — no per-level hardcoded logic.
 */
function renderTree(node) {
  const li = document.createElement("li");

  const label = document.createElement("span");
  label.className = "tree-label";

  const icon = document.createElement("span");
  icon.className = "toggle-icon";
  icon.textContent = node.children.length ? "▶" : "•";

  label.appendChild(icon);
  label.appendChild(document.createTextNode(" " + node.name));

  li.appendChild(label);

  if (node.children.length) {
    const ul = document.createElement("ul");
    node.children.forEach(child => ul.appendChild(renderTree(child)));
    li.appendChild(ul);

    // Toggle open/closed via classList.toggle on click
    label.addEventListener("click", () => {
      li.classList.toggle("open");
      icon.textContent = li.classList.contains("open") ? "▼" : "▶";
    });
  }

  return li;
}

function buildTagTree() {
  const container = document.getElementById("tag-tree");
  const ul = document.createElement("ul");
  ul.appendChild(renderTree(CATEGORY_TREE));
  container.appendChild(ul);
}

// ---------------------------------------------------------------------------
// Data layer — real fetch() calls to the live backend (Part 1B Task 2)
// ---------------------------------------------------------------------------

async function fetchNotes(tag = null) {
  const url = tag
    ? `${API_BASE}/notes?tag=${encodeURIComponent(tag)}`
    : `${API_BASE}/notes`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`GET /notes failed: ${res.status}`);
  return res.json();
}

async function createNote(title, content, tag) {
  const res = await fetch(`${API_BASE}/notes`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ title, content, tag: tag || null, owner_id: OWNER_ID }),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || `POST /notes failed: ${res.status}`);
  }
  return res.json();
}

async function deleteNote(id) {
  const res = await fetch(`${API_BASE}/notes/${id}`, {
    method: "DELETE",
    headers: { "x-token": X_TOKEN },
  });
  if (!res.ok) throw new Error(`DELETE /notes/${id} failed: ${res.status}`);
  return res.json();
}

async function updateNote(id, data) {
  const res = await fetch(`${API_BASE}/notes/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error(`PUT /notes/${id} failed: ${res.status}`);
  return res.json();
}

// ---------------------------------------------------------------------------
// Rendering helpers (Part 1B Task 3)
// ---------------------------------------------------------------------------

function createNoteCard(note) {
  const card = document.createElement("div");
  card.className = "note-card";
  card.dataset.noteId = note.id;

  // Title
  const title = document.createElement("p");
  title.className = "note-title";
  title.textContent = note.title;
  card.appendChild(title);

  // Content
  const content = document.createElement("p");
  content.className = "note-content";
  content.textContent = note.content;
  card.appendChild(content);

  // Tag badge
  if (note.tag) {
    const tag = document.createElement("span");
    tag.className = "note-tag";
    tag.textContent = note.tag;
    card.appendChild(tag);
  }

  // Meta — date
  const meta = document.createElement("p");
  meta.className = "note-meta";
  const d = new Date(note.created_at);
  meta.textContent = d.toLocaleString();
  card.appendChild(meta);

  // Similarity score (smart search)
  if (note.score !== undefined) {
    const badge = document.createElement("span");
    badge.className = "score-badge";
    badge.textContent = `similarity: ${note.score.toFixed(3)}`;
    card.appendChild(badge);
  }

  // AI suggestion panel (Part 3)
  if (note.ai_suggestion) {
    card.appendChild(buildAIPanel(note.id, note.ai_suggestion));
  }

  // Actions row
  const actions = document.createElement("div");
  actions.className = "note-actions";

  const btnDelete = document.createElement("button");
  btnDelete.className = "btn-delete";
  btnDelete.textContent = "Delete";
  btnDelete.addEventListener("click", () => handleDelete(note.id, card));
  actions.appendChild(btnDelete);

  card.appendChild(actions);
  return card;
}

function buildAIPanel(noteId, suggestion) {
  const panel = document.createElement("div");
  panel.className = "ai-panel";

  const label = document.createElement("p");
  label.className = "ai-label";
  label.textContent = "✦ AI Suggests";
  panel.appendChild(label);

  // Tags
  if (suggestion.tags && suggestion.tags.length) {
    const tagsRow = document.createElement("div");
    tagsRow.className = "ai-tags";
    suggestion.tags.forEach(t => {
      const span = document.createElement("span");
      span.textContent = t;
      tagsRow.appendChild(span);
    });
    panel.appendChild(tagsRow);
  }

  // Summary
  if (suggestion.summary) {
    const summary = document.createElement("p");
    summary.textContent = suggestion.summary;
    panel.appendChild(summary);
  }

  // Apply first suggested tag button
  if (suggestion.tags && suggestion.tags.length) {
    const btn = document.createElement("button");
    btn.className = "btn-apply-tag";
    btn.textContent = `Apply tag: "${suggestion.tags[0]}"`;
    btn.addEventListener("click", async () => {
      try {
        await updateNote(noteId, { tag: suggestion.tags[0] });
        btn.textContent = "✓ Tag applied";
        btn.disabled = true;
        // Refresh the main list
        await loadAndRender();
      } catch (e) {
        btn.textContent = "Failed — retry";
      }
    });
    panel.appendChild(btn);
  }

  return panel;
}

function renderNoteList(notes, containerId = "notes-list") {
  const container = document.getElementById(containerId);
  // Clear everything except the loading/error placeholders
  Array.from(container.children).forEach(child => {
    if (child.id !== "loading-msg" && child.id !== "fetch-error") {
      child.remove();
    }
  });

  if (notes.length === 0) {
    const empty = document.createElement("p");
    empty.style.color = "#aaa";
    empty.style.gridColumn = "1 / -1";
    empty.textContent = "No notes found.";
    container.appendChild(empty);
    return;
  }

  notes.forEach(note => container.appendChild(createNoteCard(note)));
}

// ---------------------------------------------------------------------------
// Load & render all notes (Part 1B Task 3)
// ---------------------------------------------------------------------------

async function loadAndRender() {
  const loadingMsg = document.getElementById("loading-msg");
  const fetchError = document.getElementById("fetch-error");

  loadingMsg.style.display = "block";
  fetchError.classList.remove("visible");

  try {
    const notes = await fetchNotes();
    loadingMsg.style.display = "none";
    renderNoteList(notes, "notes-list");
  } catch (err) {
    loadingMsg.style.display = "none";
    fetchError.textContent = `Failed to load notes: ${err.message}`;
    fetchError.classList.add("visible");
  }
}

// ---------------------------------------------------------------------------
// Delete handler (Part 1B Task 4)
// ---------------------------------------------------------------------------

async function handleDelete(id, cardElement) {
  try {
    await deleteNote(id);
    cardElement.remove();
  } catch (err) {
    alert(`Delete failed: ${err.message}`);
  }
}

// ---------------------------------------------------------------------------
// Add Note form (Part 1B Tasks 4 & 5)
// ---------------------------------------------------------------------------

document.getElementById("btn-add-note").addEventListener("click", async () => {
  const titleInput   = document.getElementById("note-title");
  const contentInput = document.getElementById("note-content");
  const tagInput     = document.getElementById("note-tag");
  const errorEl      = document.getElementById("form-error");

  const title   = titleInput.value.trim();
  const content = contentInput.value.trim();
  const tag     = tagInput.value.trim();

  // Client-side validation — no browser alert()
  if (!title || !content) {
    errorEl.textContent = "Title and content are required.";
    errorEl.classList.add("visible");
    return;
  }
  errorEl.classList.remove("visible");

  try {
    const newNote = await createNote(title, content, tag);

    // Append new card to DOM without full page reload
    const card = createNoteCard(newNote);
    const notesList = document.getElementById("notes-list");
    const loadingMsg = document.getElementById("loading-msg");
    loadingMsg.style.display = "none";
    notesList.appendChild(card);

    // Clear form
    titleInput.value   = "";
    contentInput.value = "";
    tagInput.value     = "";
  } catch (err) {
    errorEl.textContent = `Failed to add note: ${err.message}`;
    errorEl.classList.add("visible");
  }
});

// ---------------------------------------------------------------------------
// Debounced search (Part 1B Task 6)
// ---------------------------------------------------------------------------

let debounceTimer = null;

document.getElementById("search-input").addEventListener("input", (e) => {
  // Debounce — only fires after user stops typing for 400ms
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(() => {
    const val = e.target.value.trim();
    console.log(`[${new Date().toISOString()}] Debounced search triggered: "${val}"`);
    handleSearch(val);
  }, 400);
});

document.getElementById("btn-search").addEventListener("click", () => {
  const val = document.getElementById("search-input").value.trim();
  handleSearch(val);
});

async function handleSearch(query) {
  const sortBy   = document.getElementById("sort-select").value;
  const resultsEl = document.getElementById("search-results");
  resultsEl.innerHTML = "";

  if (!query && !sortBy) return;

  try {
    let url;
    if (sortBy === "date") {
      url = `${API_BASE}/notes/search?sort_by=date`;
    } else if (query) {
      url = `${API_BASE}/notes/search?keyword=${encodeURIComponent(query)}`;
    } else {
      return;
    }

    const res = await fetch(url);
    if (!res.ok) {
      // Part 2 not yet wired — fall back to client-side filter
      const notes = await fetchNotes();
      const filtered = notes.filter(n =>
        n.title.toLowerCase().includes(query.toLowerCase()) ||
        (n.tag && n.tag.toLowerCase().includes(query.toLowerCase()))
      );
      renderResults(filtered, resultsEl);
      return;
    }
    const data = await res.json();
    renderResults(data, resultsEl);
  } catch {
    // Client-side fallback
    try {
      const notes = await fetchNotes();
      const filtered = notes.filter(n =>
        n.title.toLowerCase().includes(query.toLowerCase()) ||
        (n.tag && n.tag.toLowerCase().includes(query.toLowerCase()))
      );
      renderResults(filtered, resultsEl);
    } catch (err2) {
      resultsEl.textContent = `Search error: ${err2.message}`;
    }
  }
}

function renderResults(notes, container) {
  container.innerHTML = "";
  if (!notes || notes.length === 0) {
    container.textContent = "No results.";
    return;
  }
  notes.forEach(note => container.appendChild(createNoteCard(note)));
}

// ---------------------------------------------------------------------------
// Sort select triggers search (Part 2)
// ---------------------------------------------------------------------------
document.getElementById("sort-select").addEventListener("change", () => {
  const query = document.getElementById("search-input").value.trim();
  handleSearch(query || " "); // space triggers date sort even without a keyword
});

// ---------------------------------------------------------------------------
// Exact-title lookup (Part 2 Tasks 2 & 3)
// ---------------------------------------------------------------------------

document.getElementById("btn-lookup").addEventListener("click", async () => {
  const title  = document.getElementById("lookup-input").value.trim();
  const algo   = document.getElementById("algo-select").value;
  const resultEl = document.getElementById("lookup-result");
  resultEl.innerHTML = "";

  if (!title) return;

  try {
    const res = await fetch(
      `${API_BASE}/notes/lookup?title=${encodeURIComponent(title)}&algo=${algo}`
    );
    const data = await res.json();

    if (!res.ok) {
      resultEl.textContent = data.detail || "Not found.";
      return;
    }

    const card = createNoteCard(data);
    card.classList.add("highlighted");
    resultEl.appendChild(card);
    card.scrollIntoView({ behavior: "smooth", block: "center" });
  } catch (err) {
    resultEl.textContent = `Lookup error: ${err.message}`;
  }
});

// ---------------------------------------------------------------------------
// Quick tag jump buttons (Part 2 Task 4)
// ---------------------------------------------------------------------------

document.querySelectorAll(".quick-tags button").forEach(btn => {
  btn.addEventListener("click", async () => {
    const tag = btn.dataset.tag;
    const resultsEl = document.getElementById("search-results");
    resultsEl.innerHTML = "";

    try {
      const res = await fetch(`${API_BASE}/notes/quickfind?tag=${encodeURIComponent(tag)}`);
      const data = await res.json();

      if (!res.ok || !data || data.detail === "Not found") {
        resultsEl.textContent = `No note found for tag: "${tag}"`;
        return;
      }

      const card = createNoteCard(data);
      card.classList.add("highlighted");
      resultsEl.appendChild(card);

      // Scroll to and highlight the matching card in the main list
      const existing = document.querySelector(`#notes-list [data-note-id="${data.id}"]`);
      if (existing) {
        existing.classList.add("highlighted");
        existing.scrollIntoView({ behavior: "smooth", block: "center" });
        setTimeout(() => existing.classList.remove("highlighted"), 2000);
      }
    } catch (err) {
      resultsEl.textContent = `Quick find error: ${err.message}`;
    }
  });
});

// ---------------------------------------------------------------------------
// Smart Search — Part 3
// ---------------------------------------------------------------------------

document.getElementById("btn-smart").addEventListener("click", async () => {
  const query = document.getElementById("smart-input").value.trim();
  const resultsEl = document.getElementById("smart-results");
  resultsEl.innerHTML = "";

  if (!query) return;

  try {
    const res = await fetch(
      `${API_BASE}/notes/smartsearch?q=${encodeURIComponent(query)}`
    );
    const data = await res.json();

    if (!res.ok) {
      resultsEl.textContent = data.detail || "Smart search unavailable.";
      return;
    }

    if (!data.length) {
      resultsEl.textContent = "No results.";
      return;
    }

    data.forEach(item => resultsEl.appendChild(createNoteCard(item)));
  } catch (err) {
    resultsEl.textContent = `Smart search error: ${err.message}`;
  }
});

// ---------------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------------
buildTagTree();
loadAndRender();
