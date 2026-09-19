# CVInsight Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an independently implemented Vue 3 + FastAPI + SQLite platform that satisfies the five required conference-paper hot-topic functions and can be tested, built, and deployed.

**Architecture:** FastAPI owns validation, SQLite persistence, keyword extraction, statistics, and online title lookup. Vue 3 consumes REST endpoints and renders five routed views with ECharts. The visual language is recreated from the approved observatory design without importing Stitch source code.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy, Pydantic, SQLite, pytest, Vue 3, Vite, Vue Router, Axios, ECharts, Vitest.

---

## File map

- Create `backend/app/main.py`: FastAPI application, startup database initialization, and production static serving.
- Create `backend/app/config.py`, `db.py`, `models.py`, and `schemas.py`: configuration, SQLAlchemy session, tables, and API contracts.
- Create `backend/app/services/keywords.py`, `metrics.py`, `papers.py`, and `lookup.py`: deterministic domain logic.
- Create `backend/app/api/papers.py` and `stats.py`: REST endpoints.
- Create `backend/tests/`: database, keyword, metric, API, and failure-path tests.
- Create `frontend/src/`: Vue shell, routes, API client, components, views, styles, and utility tests.
- Create `data/demo_papers.csv`: explicitly labelled development fixture; never present it as a complete corpus.
- Create `codestyle.md` and deployment files.
- Update `README.md` and project design/plan documents only with verified facts and real evidence. PSP、AI 协作记录和博客草稿属于个人课程材料，保留在本地但不纳入 Git。

## Task 1: Scaffold both applications and a health test

**Files:** `backend/requirements.txt`, `backend/app/__init__.py`, `backend/app/main.py`, `backend/tests/test_health.py`, `frontend/package.json`, `frontend/index.html`, `.gitignore`

- [ ] **Step 1: Write the failing test**

~~~python
from fastapi.testclient import TestClient
from app.main import app

def test_health_endpoint_reports_service_status():
    response = TestClient(app).get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
~~~

- [ ] **Step 2: Verify RED**

Run from `backend`: `python -m pytest tests/test_health.py -q`. It must fail because the module or endpoint is absent.

- [ ] **Step 3: Implement the minimal FastAPI application**

~~~python
from fastapi import FastAPI

app = FastAPI(title="CVInsight API")

@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
~~~

- [ ] **Step 4: Verify GREEN**

Run `python -m pytest tests/test_health.py -q`; expect one passing test.

- [ ] **Step 5: Add manifests and ignore rules**

List FastAPI, Uvicorn, SQLAlchemy, pydantic-settings, python-multipart, httpx, scikit-learn, and pytest in the backend requirements. List Vue, Vue Router, Axios, ECharts, Vite, Vitest, and the Vue plugin in the frontend package. Ignore virtual environments, node_modules, dist, .env, database files, caches, and generated screenshots.

- [ ] **Step 6: Commit**

~~~powershell
git add backend frontend .gitignore
git commit -m "chore: scaffold Vue and FastAPI applications"
~~~

## Task 2: Add SQLite persistence and schemas

**Files:** `backend/app/config.py`, `db.py`, `models.py`, `schemas.py`, `backend/tests/conftest.py`, `test_models.py`

- [ ] **Step 1: Write the failing model test**

~~~python
def test_paper_persists_required_metadata(db_session):
    paper = Paper(
        title="A Test Vision Paper",
        conference="CVPR",
        year=2024,
        source="demo",
        source_url="https://example.test/paper",
    )
    db_session.add(paper)
    db_session.commit()
    loaded = db_session.query(Paper).one()
    assert loaded.conference == "CVPR"
    assert loaded.year == 2024
~~~

- [ ] **Step 2: Verify RED**

Run `python -m pytest tests/test_models.py -q`; it must fail because the model/session are absent.

- [ ] **Step 3: Implement the database**

Use `CVINSIGHT_DATABASE_URL` at runtime and a temporary SQLite file for tests. Define `Paper`, `Keyword`, and `PaperKeyword`; add a unique constraint on normalized title plus conference plus year, and cascade paper-keyword rows when a paper is deleted.

- [ ] **Step 4: Add Pydantic schemas**

Define `PaperCreate`, `PaperUpdate`, `PaperRead`, `PaperList`, `ImportSummary`, and `LookupResult`. Reject empty titles, conferences outside CVPR/ICCV/ECCV, and years outside 1990 through the current year.

- [ ] **Step 5: Verify GREEN and commit**

Run `python -m pytest tests/test_models.py -q`, then:

~~~powershell
git add backend/app backend/tests
git commit -m "feat: add SQLite paper and keyword persistence"
~~~

## Task 3: Implement keyword extraction and statistics with TDD

**Files:** `backend/app/services/keywords.py`, `metrics.py`, `backend/tests/test_keywords.py`, `test_metrics.py`

- [ ] **Step 1: Write failing keyword tests**

Test lowercasing, punctuation and whitespace removal, stop-word filtering, alias merging, and empty input.

~~~python
def test_normalize_keyword_merges_case_and_aliases():
    assert normalize_keyword(" Vision-Language Models ") == "vision-language model"
    assert normalize_keyword("VLM") == "vision-language model"
~~~

- [ ] **Step 2: Verify RED**

Run `python -m pytest tests/test_keywords.py -q`; it must fail because the service is absent.

- [ ] **Step 3: Implement keyword logic**

Use an explicit small alias dictionary, English stop words, title-plus-abstract TF-IDF fallback, and no more than ten deterministic terms per paper. Store whether each term came from provided keywords or TF-IDF.

- [ ] **Step 4: Write failing heat and graph tests**

~~~python
def test_heat_uses_paper_coverage_not_raw_token_count():
    rows = [
        {"keyword": "diffusion", "conference": "CVPR", "year": 2024, "paper_id": 1},
        {"keyword": "diffusion", "conference": "CVPR", "year": 2024, "paper_id": 2},
    ]
    assert calculate_heat(rows, total_papers=4) == 500.0
~~~

Also test safe growth when the previous year is zero and one co-occurring keyword pair produces one graph edge.

- [ ] **Step 5: Verify RED, implement, and verify GREEN**

Run `python -m pytest tests/test_metrics.py -q` before implementation and confirm the expected missing-function failure. Implement normalized heat, Top 10 sorting, safe year-over-year delta, graph nodes/edges, and trend series as pure Python functions. Run both test files and require all tests to pass.

- [ ] **Step 6: Commit**

~~~powershell
git add backend/app/services backend/tests
git commit -m "feat: add reproducible keyword and heat analytics"
~~~

## Task 4: Implement paper CRUD, search, import, and online lookup

**Files:** `backend/app/api/papers.py`, `backend/app/services/papers.py`, `lookup.py`, `backend/tests/test_papers_api.py`, `data/demo_papers.csv`

- [ ] **Step 1: Write failing API tests**

Cover create, exact title search, keyword fuzzy search, update, delete, duplicate import, CSV import summary, and online lookup failure without fabricated data.

~~~python
def test_paper_search_returns_exact_title(client):
    client.post("/api/papers", json={
        "title": "A Test Vision Paper",
        "conference": "CVPR",
        "year": 2024,
        "abstract": "diffusion vision",
    })
    response = client.get("/api/papers", params={"q": "A Test Vision Paper"})
    assert response.status_code == 200
    assert response.json()["total"] == 1
~~~

- [ ] **Step 2: Verify RED**

Run `python -m pytest tests/test_papers_api.py -q`; route tests must fail because routes are absent.

- [ ] **Step 3: Implement the service and routes**

Return paginated `{items,total,page,page_size}`. Normalize keywords before persistence. Treat duplicate title/conference/year rows as skipped import items and include per-row error messages. Use `UploadFile` for CSV/TXT.

- [ ] **Step 4: Implement the lookup adapter**

Read the configured public metadata endpoint from `CVINSIGHT_LOOKUP_URL`, use a short timeout, parse only returned fields, preserve the real source, and return an explicit 502 error on timeout, invalid response, or no match. Never synthesize missing metadata.

- [ ] **Step 5: Verify GREEN and seed demo data**

Run `python -m pytest tests/test_papers_api.py -q`. Add `python -m app.seed --file ../data/demo_papers.csv`; every fixture row must use `source=demo` and be described as development-only in the README.

- [ ] **Step 6: Commit**

~~~powershell
git add backend/app/api backend/app/services backend/tests data/demo_papers.csv
git commit -m "feat: add paper CRUD import and lookup workflows"
~~~

## Task 5: Add statistics endpoints

**Files:** `backend/app/api/stats.py`, `backend/app/main.py`, `backend/tests/test_stats_api.py`

- [ ] **Step 1: Write failing endpoint tests**

Test overview counts, no more than ten sorted topics, graph nodes/links, trend series for selected conferences and years, and valid empty-database responses.

- [ ] **Step 2: Verify RED**

Run `python -m pytest tests/test_stats_api.py -q`; it must fail because the routes are absent.

- [ ] **Step 3: Implement the four endpoints**

Add `/api/stats/overview`, `/topics`, `/graph`, and `/trends`. Accept optional conference, year range, and keyword filters. Delegate all calculations to the shared metric service.

- [ ] **Step 4: Verify and commit**

Run `python -m pytest -q` from `backend`; require zero failures.

~~~powershell
git add backend/app backend/tests
git commit -m "feat: expose topic graph and trend statistics APIs"
~~~

## Task 6: Scaffold Vue and independently recreate the visual system

**Files:** `frontend/src/main.js`, `App.vue`, `router.js`, `api.js`, `styles/tokens.css`, `styles/base.css`, `components/AppShell.vue`, `utils/filters.js`, `utils/filters.spec.js`

- [ ] **Step 1: Write the failing utility test**

~~~javascript
import { describe, expect, it } from "vitest"
import { formatHeat } from "./filters"

describe("formatHeat", () => {
  it("formats normalized heat with one decimal place", () => {
    expect(formatHeat(12.345)).toBe("12.3%")
  })
})
~~~

- [ ] **Step 2: Verify RED**

Run `npm test -- --run src/utils/filters.spec.js` from `frontend`; it must fail because the helper is absent.

- [ ] **Step 3: Implement the Vue shell**

Create routes for overview, trends, papers, import, and about. Write fresh Vue templates and CSS with midnight blue surfaces, cyan focus, amber growth, coral decline, compact borders, serif headings, monospace metrics, and responsive loading/error/empty states. Do not paste Stitch markup or scripts.

- [ ] **Step 4: Implement the formatter and verify GREEN**

Run `npm test -- --run src/utils/filters.spec.js`; require one passing test.

- [ ] **Step 5: Commit**

~~~powershell
git add frontend
git commit -m "feat: scaffold Vue observatory application shell"
~~~

## Task 7: Implement analytics views

**Files:** `frontend/src/views/OverviewView.vue`, `TrendsView.vue`, `AboutView.vue`, `components/MetricCard.vue`, `KeywordGraph.vue`, `TrendChart.vue`

- [ ] **Step 1: Implement view states**

Every view must have loading, success, empty-database, and API-error states. Clicking a graph node must update the papers route with `keyword=<normalized-keyword>`.

- [ ] **Step 2: Implement overview**

Fetch overview, topics, and graph data. Show active filter range and source status. Never hard-code Stitch counts.

- [ ] **Step 3: Implement the ECharts graph**

Create nodes and links from the API, dispose on unmount, resize on container changes, and emit the selected keyword.

- [ ] **Step 4: Implement trends**

Provide conference toggles, year range, play/pause, reset, and speed controls. Use API series and display the exact heat formula.

- [ ] **Step 5: Implement about**

Explain data sources, CSV fields, provided-versus-TF-IDF keywords, normalized heat, limitations, and the difference between demo fixture and formal corpus.

- [ ] **Step 6: Verify and commit**

Run `npm test -- --run` and `npm run build`; require all tests and the production build to pass.

~~~powershell
git add frontend
git commit -m "feat: add overview graph and trend analytics views"
~~~

## Task 8: Implement paper management and import views

**Files:** `frontend/src/views/PapersView.vue`, `ImportView.vue`, `components/PaperTable.vue`, `PaperForm.vue`, `ImportResults.vue`

- [ ] **Step 1: Implement search and filters**

Bind query, conference, year, keyword, page size, and pagination to `/api/papers`. Show total results and active filters.

- [ ] **Step 2: Implement CRUD and details**

Add, edit, delete, and view details through the API. Use an accessible confirmation dialog for deletion and refresh the list after mutation.

- [ ] **Step 3: Implement online fallback**

When local search returns no rows, show an online lookup action. Display source and require an explicit save action before inserting the result.

- [ ] **Step 4: Implement single and batch import**

Provide title lookup, CSV/TXT upload, preview, processing status, success/error counts, and per-row messages. Clearly distinguish unsaved lookup results from SQLite records.

- [ ] **Step 5: Verify and commit**

Run `npm run build`, start the backend with the demo database, and manually verify papers and import routes against the API.

~~~powershell
git add frontend
git commit -m "feat: add paper management and import views"
~~~

## Task 9: Add production serving and deployment configuration

**Files:** `backend/app/main.py`, `deploy/Dockerfile`, `deploy/docker-compose.yml`, `deploy/nginx.conf`, `README.md`

- [ ] **Step 1: Write the production serving smoke test**

Test that the application still returns 200 from `/api/health` and serves the built Vue index when `frontend/dist/index.html` exists.

- [ ] **Step 2: Implement serving and CORS**

Mount the Vue dist directory only when it exists, keep API routes under `/api`, and read allowed origins from environment variables.

- [ ] **Step 3: Add container files**

Use a Node build stage and Python runtime stage. Persist SQLite under `/app/data`, expose port 8000, and keep external lookup settings in environment variables.

- [ ] **Step 4: Verify production locally**

Run `npm run build`, start Uvicorn or the container, then request `http://127.0.0.1:8000/api/health` and `http://127.0.0.1:8000/`; both must return HTTP 200.

- [ ] **Step 5: Commit**

~~~powershell
git add backend deploy README.md
git commit -m "build: add production serving and deployment configuration"
~~~

## Task 10: Complete assignment documentation and evidence

**Files:** `README.md`, `codestyle.md`, deployment documentation, and project design/plan records

- [ ] **Step 1: Add code standards**

Cite PEP 8, the official Vue Style Guide, and MDN HTML/CSS guidance at the top. Add project naming, imports, component, API error, and test rules.

- [ ] **Step 2: Record PSP estimates and actual time**

Create estimate and actual columns before the remaining work and update actual minutes after each session.

- [ ] **Step 3: Record real AI collaboration**

Record the actual Stitch prompt as the prototype-design case and add real Vue/FastAPI coding and debugging exchanges with the observed issue, accepted change, rejected suggestion, and verification command. Do not manufacture a Bug or conversation.

- [ ] **Step 4: Update README and blog with verified facts**

Include assignment link, repository, student number, data source, algorithm, run steps, prototype link, deployment link only after online verification, screenshots/GIFs, and the AI code declaration. Replace the current incorrect second-assignment goal text.

- [ ] **Step 5: Commit documentation**

~~~powershell
git add README.md codestyle.md deploy docs/superpowers .gitignore
git commit -m "docs: document assignment process and AI collaboration"
~~~

## Task 11: Verify, tag, and merge

**Files:** repository metadata only.

- [ ] **Step 1: Run backend verification**

~~~powershell
Set-Location backend
python -m pytest -q
Set-Location ..
~~~

Record the exact passing count.

- [ ] **Step 2: Run frontend verification**

~~~powershell
Set-Location frontend
npm test -- --run
npm run build
Set-Location ..
~~~

Record the exact passing count and build exit code.

- [ ] **Step 3: Run the requirement checklist**

Verify all API-backed features, five Vue routes, SQLite persistence, source labels, empty/error states, README, codestyle, project design/plan records, and local production health check. PSP、AI 记录和博客作为本地课程材料单独核对，不作为 Git 项目内容。Report any unmet item instead of marking it complete.

- [ ] **Step 4: Confirm readable Git history**

Run `git log --oneline --decorate --graph --all`; confirm at least 15 meaningful total commits and that development happened on `dev`.

- [ ] **Step 5: Merge and tag after verification**

~~~powershell
git switch main
git merge --no-ff dev -m "merge: release CVInsight 1.0.0"
git tag -a 1.0.0 -m "CVInsight 1.0.0"
~~~

- [ ] **Step 6: Re-run the complete verification on merged main**

Run the backend suite, frontend suite/build, and production health checks again from the merged commit. Report actual results and any external cloud-deployment blocker.
