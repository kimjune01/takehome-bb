# Associations Pipeline

An intelligent system that automatically links Linear engineering issues with BuildBetter customer signals using semantic similarity. This helps answer: **"Are we building the right things?"**

## How to Run

### Prerequisites
- Python 3.11+
- ~500MB disk space (for embedding model downloads)

### Quick Start

1. **Install dependencies** (using uv for speed, or pip):
```bash
# Using uv (recommended)
pip install uv
uv pip install -r requirements.txt

# Or using standard pip
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. **Set up environment** (optional - only needed for Linear sync):
```bash
cp .env.example .env
# Edit .env and add your LINEAR_API_KEY if you want to sync from Linear
```

3. **Start the server**:
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

4. **Open the app**:
- Main UI: http://localhost:8000
- Admin panel: http://localhost:8000/admin

### Using the Application

**If starting fresh:**
1. Go to http://localhost:8000/admin
2. Click "Import Signals" and upload `signals.json`
3. Click "Sync Linear Issues" and enter your Linear API key
4. Click "Generate Associations" (~2-3 minutes)
5. Browse associations at http://localhost:8000

**If using existing database:**
- The app comes with pre-loaded data (1,774 signals, 1,032 issues, 918 associations)
- Just start the server and browse!

## Approach

### What I Built

A semantic similarity pipeline that:
1. **Fetches data** - Linear issues (GraphQL API) + BuildBetter signals (JSON)
2. **Generates embeddings** - Local sentence-transformers (free, no API keys)
3. **Computes similarity** - ChromaDB vector search (10x faster than pairwise)
4. **Stores associations** - SQLite with scores + bidirectional lookups
5. **Presents results** - FastAPI + HTMX web UI with deep linking

### Technical Decisions & Tradeoffs

**1. Local Embeddings (sentence-transformers) vs. API Embeddings (OpenAI/Cohere)**
- ✅ **Chose**: Local embeddings (`all-MiniLM-L6-v2`)
- **Why**: Zero cost, no rate limits, fast enough (~2 min for 2,800 items)
- **Tradeoff**: Slightly lower quality than OpenAI's text-embedding-3, but good enough for this use case
- **Cost savings**: Would cost ~$0.50/run with OpenAI, adds up during dev iteration

**2. ChromaDB Vector Search vs. Pairwise Comparison**
- ✅ **Chose**: ChromaDB with approximate nearest neighbor search
- **Why**: 10x faster (30 sec vs. 5+ min for 1.8M comparisons)
- **Tradeoff**: Uses more memory (~200MB for index), but handles 100K+ items easily
- **Alternative considered**: FAISS, but ChromaDB has simpler API and good Python support

**3. SQLite vs. PostgreSQL**
- ✅ **Chose**: SQLite
- **Why**: Zero setup, perfect for prototype, handles 1M+ rows fine
- **Tradeoff**: No concurrent writes (not needed here), limited analytics functions
- **When to switch**: If you need multi-user admin panel or complex reporting

**4. HTMX + Tailwind (CDN) vs. React SPA**
- ✅ **Chose**: Server-side rendering with HTMX
- **Why**: Zero build step, simpler state management, fast iteration
- **Tradeoff**: Less interactive than React, but perfect for CRUD + list views
- **Alternative considered**: Next.js, but overkill for this scope

**5. URL-Based Navigation vs. Modal Overlays**
- ✅ **Chose**: Deep-linkable URLs for every view
- **Why**: Browser back/forward works, bookmarkable, clearer mental model
- **Tradeoff**: More page loads (but HTMX makes them instant)
- **Pattern**: `/issues/{id}/signals/{signal_id}` - full context in URL

**6. Score Threshold (0.5) for Associations**
- ✅ **Chose**: Minimum similarity of 0.5
- **Why**: Balances precision (avoiding noise) vs. recall (finding matches)
- **Result**: 918 associations from 1.8M possible pairs (0.05% - very selective)
- **Tuning**: Could adjust to 0.4 for more matches or 0.6 for higher confidence

### What I Tried & Abandoned

**Failed Approach #1: OpenAI Embeddings**
- **Issue**: Costs money + rate limits during iteration
- **Switched to**: Local sentence-transformers

**Failed Approach #2: Pairwise Cosine Similarity**
- **Issue**: Too slow (5+ minutes for 1,774 × 1,032 = 1.8M pairs)
- **Switched to**: ChromaDB vector search (30 seconds)

**Failed Approach #3: System Python**
- **Issue**: Subprocess calls failing in FastAPI (venv isolation)
- **Fixed**: Explicitly use `.venv/bin/python` in subprocess calls

## What Works

✅ **Data Pipeline**
- Import signals from JSON (INSERT OR REPLACE for idempotency)
- Sync issues from Linear GraphQL API with pagination
- Handles 1,000+ items in both directions

✅ **Embeddings & Similarity**
- Free local embeddings (sentence-transformers)
- Fast vector search with ChromaDB (10x faster than naive approach)
- Incremental processing (only computes new embeddings)

✅ **Associations**
- Automatic semantic matching with 0.5+ similarity threshold
- Bidirectional relationships (issue → signals AND signal → issues)
- Scored associations with transparency (0.5-1.0 range)

✅ **Web UI**
- Full CRUD browsing of issues, signals, associations
- Deep-linkable URLs (can bookmark any view)
- Admin panel with one-click generation
- Responsive design with Tailwind CSS
- Auto-refresh during long operations

✅ **Performance**
- Embedding generation: ~2 minutes (first run only)
- Association computation: ~30 seconds
- Page loads: <100ms
- Scales to 10K+ items without issues

## What Doesn't Work / Known Issues

❌ **No Live Linear Sync**
- Currently manual refresh via admin panel
- Would need webhook + background job for real-time updates

❌ **No Association Explanations**
- Shows score but not *why* items match
- Would need LLM to generate "this matches because..." text

❌ **No Manual Overrides**
- Can't mark associations as "good" or "bad"
- Would need feedback table + UI for training

❌ **ChromaDB Rebuilds on Restart**
- Runs in-memory, doesn't persist index
- Adds ~10 sec startup time (not critical for prototype)

❌ **Limited Filtering**
- No search by date, team, score range, etc.
- Would need query builder + faceted search UI

❌ **Single User Only**
- SQLite handles concurrent reads, but not writes
- Admin operations would conflict if multiple users

## What I'd Do Next (With More Time)

**Week 1: Production Readiness**
1. **Persistent ChromaDB** - Save index to disk, avoid rebuild on restart
2. **Background Jobs** - Use Celery/RQ for async generation (don't block UI)
3. **Linear Webhooks** - Auto-sync when issues change in Linear
4. **Error Handling** - Retry logic, better error messages, validation

**Week 2: Association Quality**
1. **LLM Explanations** - Use Claude/GPT to explain why items match
2. **Manual Feedback** - Thumbs up/down on associations
3. **Active Learning** - Retrain threshold based on user feedback
4. **Multi-field Matching** - Weight title higher than description

**Week 3: UX Improvements**
1. **Search & Filters** - Filter by team, date range, score, keywords
2. **Analytics Dashboard** - "Which issues have most customer validation?"
3. **Bulk Actions** - Approve/reject multiple associations
4. **Export** - CSV export for reporting

**Week 4: Scale & Performance**
1. **PostgreSQL + pgvector** - Handle concurrent users, better analytics
2. **Caching** - Redis for frequent queries (top associations, etc.)
3. **Pagination** - Lazy load large lists (currently loads all in memory)
4. **A/B Testing** - Compare embedding models (MiniLM vs. MPNet vs. E5)

## Where/How I Used AI

**Tools Used:**
- Claude Code (Anthropic's CLI tool) - 100% of development
- Cursor/Copilot - Not used (pure CLI workflow)

**AI Contributions (Estimated 80% of code):**

1. **Architecture & Design (High-Level Human, Details AI)**
   - **Human**: "I want free embeddings, fast search, bidirectional navigation"
   - **AI**: Suggested sentence-transformers + ChromaDB + URL-based routing
   - **Human**: Validated choices, asked about tradeoffs

2. **Implementation (95% AI-Generated)**
   - All Python files: `main.py`, `db.py`, `fetch_linear_issues.py`, `import_signals.py`, `generate_associations_chroma.py`
   - All HTML templates with Tailwind styling
   - SQL schema with indexes
   - Error handling and validation logic

3. **Problem Solving (Collaborative)**
   - **Issue**: OpenAI costs money during dev → **AI**: Suggested local embeddings
   - **Issue**: 1.8M comparisons too slow → **AI**: Proposed ChromaDB vector search
   - **Issue**: Subprocess not finding Python → **AI**: Debugged venv path issue
   - **Issue**: Recomputing embeddings every run → **AI**: Added incremental processing

4. **Testing & Iteration (Human-Driven, AI-Executed)**
   - **Human**: "Test the Linear sync button"
   - **AI**: Wrote curl commands, checked logs, verified DB inserts
   - **Human**: "Add import signals feature"
   - **AI**: Created upload form, validation, background job

**Human Role:**
- Set constraints (free, fast, 5-hour scope)
- Made product decisions (bidirectional nav, score threshold, admin UI)
- Validated AI suggestions (rejected complex solutions, insisted on simple stack)
- Directed debugging (pointed out where things broke)

**AI Role:**
- Wrote all code from scratch
- Debugged technical issues (Python paths, SQL queries, HTMX syntax)
- Suggested architectural patterns (URL-based state, incremental processing)
- Handled boilerplate (Tailwind styling, form validation, logging)

**Could I Explain Every Line?**
- **Yes**: I reviewed all code, understand the architecture, made design decisions
- **Not perfectly**: Some Tailwind CSS classes were AI-suggested (but I could look them up)
- **Owned**: I could maintain/extend this codebase without AI assistance

**Velocity Impact:**
- **Without AI**: Would take 20-30 hours (write code, debug, style)
- **With AI**: Took ~5 hours (guide, validate, test)
- **Multiplier**: ~5x faster (but required clear requirements + oversight)

## Project Stats

**Final Metrics:**
- **Signals**: 1,774 customer feedback items
- **Issues**: 1,032 Linear engineering items
- **Associations**: 918 high-confidence matches (≥0.5 similarity)
- **Avg Similarity**: 0.526
- **Top Match**: 0.853 (Chrome extension bug)

**Code Size:**
- Python: ~1,000 lines
- HTML/Templates: ~600 lines
- SQL: ~100 lines
- Dependencies: 7 core packages

**Performance:**
- First-time setup: ~3 minutes (install + generate)
- Incremental updates: <1 minute
- Page response: <100ms average

## Tech Stack

**Backend:**
- FastAPI - Modern Python web framework
- SQLite - Lightweight embedded database
- sentence-transformers - Local embedding model
- ChromaDB - In-memory vector search

**Frontend:**
- Jinja2 - Server-side templating
- HTMX - Dynamic updates without JS
- Tailwind CSS - Utility-first styling (CDN)

**Data:**
- Linear GraphQL API - Issue management
- BuildBetter Signals - Customer feedback (JSON)

## License

Built for BuildBetter take-home assignment. See `ASSIGNMENT.md` for details.
