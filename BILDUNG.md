# Bildung — Personal Literary Intelligence & Gamified Reading System

## Vision

Bildung is a gamified personal reading intelligence system. It tracks my reading life across literature and philosophy, assigns XP for books read, organizes reading into personal "streams" (my own intellectual storylines), generates LLM-powered quizzes to deepen and test understanding, and recommends what to read next — all built around a knowledge graph that stores *my personal relationship* to the material, not an encyclopedia of philosophy.

The name comes from the German concept of self-cultivation through education and culture — the idea behind the *Bildungsroman*. This system tracks and deepens my intellectual formation over time.

## Core Design Philosophy

**The LLM is the knowledge graph. The database is my personal graph.**

I am not trying to manually replicate what a large language model already knows about how Nietzsche responds to Schopenhauer or how Spinoza's substance monism resolves Descartes' interaction problem. The LLM already compresses that interconnected web of concepts in its weights. What the LLM does *not* know is: what I've read, when, in what order, why, how I grouped it, what I found difficult, and what connections matter to *me*.

So the database stores my reading autobiography — personal, subjective, curated. The LLM provides the intellectual substance at query time, using my graph as context.

## User Profile (for LLM context)

I am Sam, a 26-year-old Flemish Belgian based in Ghent. I read across Dutch, English, French, and German. My reading spans Russian literature, Flemish naturalism, Japanese literature, continental European literature, and serious philosophy (with particular depth in early modern philosophy, German Idealism, Buddhist philosophy/Madhyamaka, and Nietzsche). I maintain my reading list religiously. I am building toward eventually curating a specialized antiquarian bookshop focused on classic literature and philosophy.

My existing reading list is in a text file (`reading_list.txt`) in this repository. It is the ground truth source for seeding the database.

## Architecture

### Tech Stack

- **Language**: Python 3.12+
- **Package management**: `uv` exclusively. No bare `pip install`. All dependencies managed via `pyproject.toml` + `uv.lock`.
- **Graph database**: Neo4j (Docker container locally, or Neo4j Aura free tier)
- **Relational database**: PostgreSQL (Docker container locally) — for time-series/event data
- **Backend API**: FastAPI
- **Frontend**: React + TypeScript with D3.js for graph/skill tree visualization
- **LLM integration**: Anthropic API (Claude) for quiz generation, answer grading, and recommendations
- **Book metadata**: OpenLibrary API (free, no key needed) as primary source; Google Books API as fallback
- **Architecture reference**: This project follows similar patterns to my `finalysis` project (personal finance analytics). Look at that codebase for conventions around: project structure, config management, database setup, medallion-style data organization, and general Python/FastAPI patterns. Adapt those patterns here.

### Data Storage Split

**Neo4j** stores the knowledge graph — the things and their relationships:
- Work nodes
- Author nodes  
- Stream nodes (my personal groupings)
- Personal edges between works (why I read X because of Y)

**PostgreSQL** stores the time-series and event data — the things that happen over time:
- Reading events (started, finished, abandoned — with timestamps)
- Quiz questions (generated, stored)
- Quiz attempts (timestamped scores, per-question breakdown)
- XP ledger (every XP award with source, timestamp, breakdown)
- Spaced repetition schedule (next due date per question)
- User notes (timestamped, linked to work IDs)

### Why This Split

Graph queries like "find all works in my Russian Literature stream that connect to works in my Buddhist Philosophy stream" are natural Cypher. Time-series queries like "show my XP earned per week over the last 3 months" or "which questions are due for review today" are natural SQL. Don't force either into the wrong store.

## Data Model

### Neo4j Nodes

#### Work
```
(:Work {
  id: UUID,
  title: String,
  original_title: String?,        // e.g. original Russian/German/Dutch title
  year_published: Int?,
  page_count: Int?,
  original_language: String?,
  openlibrary_id: String?,        // for metadata lookups
  isbn: String?,
  status: "unread" | "reading" | "read" | "abandoned" | "to_read",
  date_read: Date?,
  density_rating: "light" | "moderate" | "dense" | "grueling"?,
  language_read_in: String?,      // language I actually read it in
  source_type: "primary" | "secondary" | "fiction",
  personal_note: String?,         // short, personal — not a summary
  edition_note: String?,          // "Veen translation is superior", "Everyman's Library edition"
  cover_url: String?
})
```

#### Author
```
(:Author {
  id: UUID,
  name: String,
  birth_year: Int?,
  death_year: Int?,
  nationality: String?,
  primary_language: String?,
  openlibrary_id: String?
})
```

#### Stream
```
(:Stream {
  id: UUID,
  name: String,                   // "My Kant Path", "Russian Moral Fiction", "Flemish Roots"
  description: String?,
  color: String?,                 // for visualization
  created_at: DateTime
})
```

### Neo4j Relationships

```
(:Author)-[:WROTE]->(:Work)

(:Work)-[:READ_BECAUSE_OF {note: String?}]->(:Work)
// "I read this because that book led me to it"

(:Work)-[:BELONGS_TO {position: Int?}]->(:Stream)
// position = suggested reading order within stream

(:Author)-[:BELONGS_TO]->(:Stream)

(:Work)-[:SAME_THREAD_AS {note: String?}]->(:Work)
// personal: "these two changed how I think about the same thing"
```

Note: I do NOT store concept nodes or "influenced_by" / "responds_to" edges in the database. The LLM knows that. I store only relationships that are personal and autobiographical — things no LLM could know.

### PostgreSQL Tables

```sql
-- Reading events (immutable log)
CREATE TABLE reading_events (
    id UUID PRIMARY KEY,
    work_id UUID NOT NULL,           -- references Neo4j Work.id
    event_type VARCHAR NOT NULL,     -- 'started', 'finished', 'abandoned', 'added_to_list'
    event_date DATE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- XP ledger (immutable log, append-only)
CREATE TABLE xp_ledger (
    id UUID PRIMARY KEY,
    work_id UUID,                    -- NULL for quiz-only XP
    xp_type VARCHAR NOT NULL,        -- 'reading', 'mastery', 'connection'
    amount DECIMAL NOT NULL,
    breakdown JSONB,                 -- {"base": 200, "density_mult": 2.0, "language_mult": 1.3, ...}
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Quiz questions
CREATE TABLE quiz_questions (
    id UUID PRIMARY KEY,
    question_text TEXT NOT NULL,
    question_type VARCHAR NOT NULL,  -- 'comprehension', 'cross_work', 'cross_stream'
    related_work_ids UUID[],         -- which works this question spans
    related_stream_ids UUID[],       -- which streams this question spans
    difficulty INT,                  -- 1-5
    max_xp DECIMAL,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Quiz attempts
CREATE TABLE quiz_attempts (
    id UUID PRIMARY KEY,
    question_id UUID REFERENCES quiz_questions(id),
    answer_text TEXT NOT NULL,
    score DECIMAL NOT NULL,          -- 1-5 rubric from LLM grading
    xp_earned DECIMAL NOT NULL,
    llm_feedback TEXT,               -- explanation of score
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Spaced repetition schedule
CREATE TABLE srs_schedule (
    question_id UUID PRIMARY KEY REFERENCES quiz_questions(id),
    next_due DATE NOT NULL,
    interval_days INT NOT NULL DEFAULT 1,
    ease_factor DECIMAL NOT NULL DEFAULT 2.5,
    consecutive_correct INT NOT NULL DEFAULT 0
);
```

## XP System

### Reading XP Formula

```
reading_xp = base_xp × density_multiplier × language_multiplier × source_type_multiplier × connectivity_bonus
```

**Base XP** (from page count, diminishing returns):
- 0-150 pages: 100
- 151-300 pages: 175
- 301-500 pages: 225
- 501-800 pages: 300
- 801-1200 pages: 350
- 1200+ pages: 400

**Density multiplier** (self-reported after finishing):
- Light: 1.0×
- Moderate: 1.5×
- Dense: 2.0×
- Grueling: 3.0×

**Language multiplier**:
- Mother tongue (Dutch): 1.0×
- Strong second language (English): 1.0× (effectively native)
- Third language (French): 1.3×
- Fourth language (German): 1.3×
- Other: 1.5×

**Source type multiplier**:
- Primary philosophical text: 1.5×
- Secondary literature / criticism: 1.0×
- Fiction: 1.0×

**Connectivity bonus** (computed by LLM at enrichment time):
- How many streams does this work contribute to?
- 1 stream: 1.0×
- 2 streams: 1.2×
- 3+ streams: 1.4×

### Mastery XP

Earned per quiz question. Each question has a max_xp value (harder questions = more XP). Your score (1-5) determines the fraction earned:
- Score 5: 100% of max_xp
- Score 4: 75%
- Score 3: 50%
- Score 2: 25%
- Score 1: 0%

### Levels Per Stream

Each stream has a level computed from reading XP + mastery XP within that stream.

| Level | Name | Reading XP Required | Mastery XP Required |
|-------|------|-------------------|-------------------|
| 1-3 | Novice | 300 / 600 / 1000 | 0 / 50 / 150 |
| 4-6 | Student | 1500 / 2200 / 3000 | 300 / 500 / 800 |
| 7-9 | Scholar | 4000 / 5500 / 7000 | 1200 / 1800 / 2500 |
| 10 | Master | 10000 | 4000 |

Both thresholds must be met. You can't level up just by reading without understanding, and vice versa.

### Overall Level

Aggregate of all stream levels, weighted by stream size. Simple formula: average of all stream levels, rounded.

## Key User Flows

### Flow 1: "I want to add a book"
1. User searches by title/author → hits OpenLibrary API
2. Select the correct work/edition
3. Metadata auto-populates the Work node (title, author, year, pages, cover, language)
4. User sets: status (to_read / reading / read), assigns to stream(s)
5. If status = "read": user sets density rating, language read in, optional note
6. System computes and awards reading XP
7. XP ledger entry created in Postgres

### Flow 2: "Quiz me"
1. System queries Postgres for SRS-due questions
2. If not enough due questions, generates new ones via LLM:
   - Sends the LLM: recent reads, stream contents, past quiz performance
   - LLM generates questions that test connections *within and between* streams
   - Questions stored in Postgres
3. User answers in free text
4. LLM grades on 1-5 rubric with feedback
5. Mastery XP awarded, SRS schedule updated
6. Stream levels recomputed

### Flow 3: "What should I read next?"
1. User selects a stream (or asks globally)
2. System sends the LLM: stream contents (read + to_read works), reading order, notes, quiz performance
3. LLM recommends next book with reasoning: "You've done X and Y but skipped Z which would consolidate..."
4. User can add recommendation to to_read list directly

### Flow 4: "Show me my map"
1. Frontend fetches graph from Neo4j: streams, works, authors, edges
2. D3 force-directed visualization:
   - Clusters = streams (colored by stream color)
   - Node size = reading XP from that work
   - Node brightness/color = mastery (gray → green based on quiz performance on related questions)
   - Edges = personal links between works
3. Click a node → see details, notes, quiz history, related works
4. Zoom out → see overall intellectual landscape

### Flow 5: "Daily review"
1. System surfaces 3-5 SRS-due questions
2. Quick free-text answers
3. Graded, XP awarded
4. Streak counter incremented
5. Takes ~5 minutes

## MVP Scope (Phase 1)

The MVP is deliberately minimal. Get books into the database, display them, and prove the infrastructure works.

### MVP Deliverables:
1. **Docker Compose** with Neo4j + PostgreSQL containers
2. **Reading list ingestion**: Parse `reading_list.txt`, create Work and Author nodes in Neo4j, enrich with OpenLibrary metadata (title, author, year, pages, cover)
3. **FastAPI backend** with endpoints:
   - `GET /works` — list all works with filters (status, stream)
   - `GET /works/{id}` — single work detail
   - `POST /works` — add a new work (with OpenLibrary lookup)
   - `PATCH /works/{id}` — update status, rating, notes
   - `GET /streams` — list streams
   - `POST /streams` — create a stream
   - `POST /works/{id}/assign-stream` — assign work to stream
   - `GET /stats` — basic stats (total read, XP earned, per-stream breakdown)
4. **Simple React frontend**:
   - Book list view with filters
   - Add book (search OpenLibrary)
   - Book detail page (metadata, notes, stream assignment)
   - Stream list view
   - Basic stats dashboard (total books, XP, per-stream levels)
5. **XP calculation** on book completion (reading XP only — no quizzes yet)
6. **Seed data** from reading_list.txt

### NOT in MVP:
- Quiz system
- LLM integration
- Graph visualization
- Spaced repetition
- Recommendations
- Daily review

## Phase 2: Quiz Engine + LLM Integration
- Quiz generation via Anthropic API
- Free-text answer grading
- Mastery XP
- SRS scheduling
- Daily review flow

## Phase 3: Visualization + Gamification
- D3 force-directed graph / skill tree visualization
- Stream map with brightness/color encoding
- Level progression UI
- Streak tracking
- Achievement system (optional)

## Phase 4: Recommendations + Intelligence
- LLM-powered "what to read next"
- Conversation mining (import Claude chat exports, extract reading-relevant content)
- Cross-stream connection detection

## Project Structure

```
bildung/
├── BILDUNG.md                  # This file — project philosophy & spec
├── CLAUDE.md                   # Claude Code instructions (conventions, commands)
├── reading_list.txt            # Ground truth reading list
├── pyproject.toml              # uv-managed dependencies
├── uv.lock
├── docker-compose.yml          # Neo4j + PostgreSQL
├── .env.example                # Environment variables template
├── alembic/                    # PostgreSQL migrations
│   └── versions/
├── src/
│   └── bildung/
│       ├── __init__.py
│       ├── main.py             # FastAPI app entrypoint
│       ├── config.py           # Settings (pydantic-settings)
│       ├── models/
│       │   ├── postgres.py     # SQLAlchemy models for PG tables
│       │   └── neo4j.py        # Neo4j node/relationship schemas (Pydantic)
│       ├── db/
│       │   ├── postgres.py     # PG connection/session management
│       │   └── neo4j.py        # Neo4j driver management
│       ├── services/
│       │   ├── openlibrary.py  # OpenLibrary API client
│       │   ├── works.py        # Work CRUD operations
│       │   ├── streams.py      # Stream CRUD operations
│       │   ├── xp.py           # XP calculation engine
│       │   ├── quiz.py         # (Phase 2) Quiz generation + grading
│       │   └── srs.py          # (Phase 2) Spaced repetition scheduler
│       ├── routers/
│       │   ├── works.py
│       │   ├── streams.py
│       │   ├── quiz.py         # (Phase 2)
│       │   └── stats.py
│       └── ingestion/
│           └── reading_list.py # Parse reading_list.txt → seed DB
├── frontend/
│   ├── package.json
│   ├── src/
│   │   ├── App.tsx
│   │   ├── components/
│   │   ├── pages/
│   │   └── services/           # API client
│   └── public/
└── tests/
    ├── test_xp.py
    ├── test_works.py
    └── test_ingestion.py
```

## CLAUDE.md Content (for Claude Code)

Create a `CLAUDE.md` file in the project root with the following content so that Claude Code understands the project conventions:

```markdown
# Bildung — Project Conventions

## Stack
- Python 3.12+, FastAPI, SQLAlchemy 2.0 (async), Neo4j Python driver
- Frontend: React + TypeScript, Vite, TailwindCSS, D3.js
- Databases: PostgreSQL 16 + Neo4j 5
- Package management: `uv` only. Never use pip directly.

## Commands
- `uv run uvicorn src.bildung.main:app --reload` — start backend
- `uv run alembic upgrade head` — run PG migrations
- `uv run pytest -v` — run tests
- `cd frontend && npm run dev` — start frontend
- `docker compose up -d` — start Neo4j + PostgreSQL

## Code Standards
- Type hints on all function signatures
- Pydantic v2 models for all request/response validation
- Async database operations (both PG and Neo4j)
- Use `uv add <package>` to add dependencies, never pip
- All config via pydantic-settings, loaded from .env
- Neo4j queries in Cypher, keep them in service functions not inline in routers
- PostgreSQL via SQLAlchemy async, Alembic for migrations

## Architecture Reference
- This project follows patterns from the `finalysis` project (personal finance analytics)
- Similar medallion-style data organization principles
- Similar config management and project structure conventions
- Adapt those patterns to the dual-database (Neo4j + PostgreSQL) setup here

## Testing
- pytest with pytest-asyncio
- Test XP calculations thoroughly — these are the core game mechanic
- Test Neo4j queries with a test database
```

## Reading List Format

The `reading_list.txt` file is my ground truth. The ingestion script should be flexible enough to parse it — it may be semi-structured (title + author per line, possibly with status markers, dates, or groupings). The ingestion pipeline should:

1. Parse each entry, extracting title and author at minimum
2. Search OpenLibrary API for metadata enrichment (page count, year, ISBN, cover)
3. Create Author node in Neo4j (deduplicated)
4. Create Work node in Neo4j with OpenLibrary metadata
5. Create WROTE relationship
6. Log ingestion results (matched/unmatched/ambiguous)
7. Handle failures gracefully — if OpenLibrary doesn't find a match, create the node with whatever info we have and flag it for manual review

## Environment Variables

```
# PostgreSQL
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=bildung
POSTGRES_USER=bildung
POSTGRES_PASSWORD=bildung_dev

# Neo4j
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=bildung_dev

# Anthropic (Phase 2)
ANTHROPIC_API_KEY=

# OpenLibrary
# No key needed — free API
```

## Implementation Plan (Step by Step)

### Step 1: Project Scaffolding
- Initialize project with `uv init`
- Set up `pyproject.toml` with core dependencies: fastapi, uvicorn, sqlalchemy[asyncio], asyncpg, neo4j, pydantic, pydantic-settings, httpx, alembic
- Create `docker-compose.yml` with Neo4j 5 + PostgreSQL 16
- Create `.env` and `.env.example`
- Create `CLAUDE.md`
- Create project directory structure

### Step 2: Database Setup
- Write SQLAlchemy models for all PostgreSQL tables
- Write Alembic migration for initial schema
- Write Neo4j connection manager (async driver)
- Write Neo4j initialization script (constraints, indexes)
- Test both connections

### Step 3: OpenLibrary Integration
- Build async HTTP client for OpenLibrary Search API
- Search by title + author → return structured metadata
- Handle: no results, multiple results (return top match), missing fields
- Rate limiting (be respectful — they're a nonprofit)

### Step 4: Reading List Ingestion
- Parse `reading_list.txt` (be flexible with format)
- For each entry: search OpenLibrary, create Author + Work nodes, create WROTE edge
- Log results: matched, unmatched, ambiguous
- Store in Neo4j

### Step 5: Core API (Works + Authors)
- FastAPI routers for CRUD on works
- Search/filter works by status, stream, author
- Update work status (triggers reading event in PG + XP calculation)
- Get work detail with full metadata

### Step 6: Streams
- CRUD for streams
- Assign/remove works to streams
- List works per stream

### Step 7: XP Engine
- Implement XP formula (reading XP only for MVP)
- On work completion: calculate XP, write to xp_ledger
- Compute stream levels from XP
- Stats endpoint: total XP, per-stream XP, levels

### Step 8: Frontend MVP
- React + Vite + TailwindCSS setup
- Book list page with filters
- Add book page (OpenLibrary search)
- Book detail page
- Stream management
- Basic stats dashboard

### Step 9: Integration Testing
- End-to-end: add book → complete → XP calculated → stats updated
- Ingestion pipeline test with sample data
- API endpoint tests

---

*This document is the single source of truth for the Bildung project. All implementation decisions should refer back to this spec.*
