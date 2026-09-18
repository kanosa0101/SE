# CVInsight Visual Fidelity and Data Extensions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax.

**Goal:** Rebuild the Vue application against the Stitch reference at near 1:1 visual fidelity, add the three approved extension features, and crawl/import approximately 1,500 real CVPR/ICCV/ECCV papers from 2022–2025.

**Architecture:** Keep FastAPI, SQLAlchemy, SQLite, Vue 3, Vue Router, Axios, and ECharts. Add a rate-limited CVF crawler with on-disk HTML cache and manifest, extend the statistics API with topic inspection, yearly evolution, quality audit, and exports, then bind the Vue observatory layout to those APIs. Stitch HTML remains a visual reference only; the final application uses independently written Vue templates and CSS.

**Tech Stack:** Python 3.14-compatible FastAPI, SQLAlchemy, httpx, BeautifulSoup4, pytest; Vue 3, Vite, Vue Router, Axios, ECharts, Vitest, Vue Test Utils; SQLite; Docker Compose.

---

## File map

- Create backend/app/crawlers/cvf.py for CVF directory discovery, detail parsing, caching, throttling, retries, and manifest records.
- Create backend/app/crawlers/__init__.py for the crawler package.
- Create backend/scripts/crawl_cvf.py for the command-line crawl and CSV output.
- Create backend/tests/fixtures/cvf_index.html and backend/tests/fixtures/cvf_detail.html for deterministic parser tests.
- Create backend/tests/test_cvf_crawler.py for index/detail parsing, URL deduplication, and missing-field behavior.
- Create backend/tests/test_extensions_api.py for inspector, evolution, quality, and export endpoints.
- Modify backend/requirements.txt to add beautifulsoup4.
- Modify backend/app/models.py to persist crawl metadata and indexes.
- Modify backend/app/schemas.py for crawl metadata, inspector, evolution, quality, and export response types.
- Modify backend/app/db.py to apply additive SQLite columns when opening an existing v1 database.
- Modify backend/app/services/papers.py to serialize crawl metadata, export CSV/BibTeX, and preserve source fields.
- Modify backend/app/services/metrics.py to calculate topic inspection, yearly evolution, and quality audit values.
- Modify backend/app/api/papers.py and backend/app/api/stats.py to expose the new endpoints.
- Create frontend/src/components/TelemetryBar.vue for the original telemetry control strip.
- Create frontend/src/components/ConferenceChips.vue for CVPR/ICCV/ECCV filter chips.
- Create frontend/src/components/TopicInspectorDrawer.vue for the “了解更多” extension.
- Create frontend/src/components/EvolutionPanel.vue for animated yearly keyword rankings.
- Create frontend/src/components/DataQualityCard.vue for the quality audit extension.
- Modify frontend/src/styles/tokens.css and frontend/src/styles/base.css to match the Stitch token system.
- Modify frontend/src/components/AppShell.vue, MetricCard.vue, KeywordGraph.vue, TrendChart.vue.
- Modify frontend/src/views/OverviewView.vue, TrendsView.vue, PapersView.vue, ImportView.vue, AboutView.vue.
- Modify frontend/src/api.js for extension endpoints and export downloads.
- Create frontend/src/components/TopicInspectorDrawer.spec.js and frontend/src/components/EvolutionPanel.spec.js.
- Modify frontend/src/components/PaperTable.spec.js and frontend/src/utils/filters.spec.js where the new interactions need coverage.
- Modify README.md, docs/blog-draft.md, docs/ai-collaboration.md, and docs/psp.md with actual crawl and validation evidence after the run.

---

### Task 1: Establish the extension branch baseline and add parser dependencies

**Files:**
- Modify: backend/requirements.txt
- Test: backend/tests/test_health.py

- [ ] Step 1: Confirm the development branch starts at the released baseline

Run:

~~~powershell
git status --short --branch
git log --oneline --decorate -n 3
~~~

Expected: branch is dev, worktree is clean, and HEAD contains the v1.0.0 merge commit.

- [ ] Step 2: Add the parser dependency

Add exactly this dependency line to backend/requirements.txt:

~~~text
beautifulsoup4>=4.12,<5
~~~

Keep all existing dependency ranges unchanged.

- [ ] Step 3: Install and verify the dependency

Run:

~~~powershell
Set-Location backend
pip install -r requirements.txt
python -c "from bs4 import BeautifulSoup; print(BeautifulSoup('<p>ok</p>', 'html.parser').get_text())"
~~~

Expected: the final line prints ok.

- [ ] Step 4: Run the unchanged backend baseline

Run:

~~~powershell
python -m pytest -q
~~~

Expected: 13 passed, with only the known third-party deprecation warnings if they remain.

- [ ] Step 5: Commit the dependency change

~~~powershell
git add backend/requirements.txt
git commit -m "build: add html parser dependency"
~~~

---

### Task 2: Build a deterministic CVF parser before network crawling

**Files:**
- Create: backend/app/crawlers/__init__.py
- Create: backend/app/crawlers/cvf.py
- Create: backend/tests/fixtures/cvf_index.html
- Create: backend/tests/fixtures/cvf_detail.html
- Create: backend/tests/test_cvf_crawler.py

- [ ] Step 1: Write index and detail fixtures

The index fixture must include two paper links with one duplicate link. The detail fixture must include a title, an author list, an abstract block, a PDF link, and a CVF paper URL. Use the same structural selectors seen in the public CVF pages, but keep the fixture text short and synthetic.

- [ ] Step 2: Write failing parser tests

Add tests with these assertions:

~~~python
def test_parse_index_deduplicates_paper_links():
    links = parse_index(index_html, "https://openaccess.thecvf.com")
    assert links == [
        "https://openaccess.thecvf.com/content/CVPR2024/html/A_Test_Paper_CVPR_2024_paper.html"
    ]


def test_parse_detail_extracts_required_metadata():
    record = parse_detail(detail_html, "CVPR", 2024, detail_url)
    assert record.title == "A Test Paper"
    assert record.conference == "CVPR"
    assert record.year == 2024
    assert record.abstract == "A concise abstract."
    assert record.source_url == detail_url
    assert record.pdf_url.endswith(".pdf")


def test_missing_abstract_is_not_a_parser_crash():
    record = parse_detail(detail_without_abstract, "ECCV", 2024, detail_url)
    assert record.abstract is None
    assert record.parse_warnings == ["missing_abstract"]
~~~

Run:

~~~powershell
python -m pytest tests/test_cvf_crawler.py -q
~~~

Expected: FAIL because the crawler module does not exist.

- [ ] Step 3: Implement the parser data types

Define a typed dataclass:

~~~python
@dataclass(frozen=True)
class CvfRecord:
    title: str
    authors: str | None
    abstract: str | None
    conference: str
    year: int
    source_url: str
    pdf_url: str | None
    keywords: list[str]
    parser_version: str
    parse_warnings: list[str]
~~~

Implement pure functions parse_index(html, base_url) and parse_detail(html, conference, year, source_url). Normalize whitespace, resolve relative links with urllib.parse.urljoin, and return no duplicate URLs.

- [ ] Step 4: Implement a cache-aware rate-limited client

Implement CvfCrawler with:

~~~python
class CvfCrawler:
    def __init__(self, cache_dir: Path, delay: float = 0.25, workers: int = 4,
                 timeout: float = 20.0, max_retries: int = 3):
        self.cache_dir = cache_dir
        self.delay = delay
        self.workers = workers
        self.timeout = timeout
        self.max_retries = max_retries

    def crawl_event(self, conference: str, year: int) -> list[CvfRecord]:
        raise NotImplementedError

    def crawl(self, conferences: list[str], years: list[int], limit: int | None = None,
              resume: bool = False) -> CrawlSummary:
        raise NotImplementedError
~~~

Use httpx.Client, a descriptive User-Agent, exponential retry delays, one shared rate limiter, and an HTML cache keyed by SHA-256 URL hash. A failed page is recorded in the manifest and does not abort other events. HTTP 404 for an unavailable event is a skipped event, not a parser exception.

- [ ] Step 5: Run parser tests

Run:

~~~powershell
python -m pytest tests/test_cvf_crawler.py -q
~~~

Expected: all parser tests pass without network access.

- [ ] Step 6: Commit the parser unit

~~~powershell
git add backend/app/crawlers backend/tests/fixtures backend/tests/test_cvf_crawler.py
git commit -m "feat: add deterministic CVF metadata parser"
~~~

---

### Task 3: Add the crawl command and CSV manifest output

**Files:**
- Create: backend/scripts/crawl_cvf.py
- Modify: backend/app/crawlers/cvf.py
- Create: backend/tests/test_crawl_command.py

- [ ] Step 1: Write command-level tests

Test a temporary cache with a fake crawler and assert that the command writes UTF-8 CSV columns:

~~~python
EXPECTED_COLUMNS = [
    "title", "paper_code", "abstract", "authors", "conference", "year",
    "source", "source_url", "keywords", "crawled_at", "parser_version",
]
~~~

Also assert that a second run with resume does not fetch a cached URL twice.

- [ ] Step 2: Implement event discovery

Use these event candidates:

~~~python
EVENTS = [
    ("CVPR", 2022), ("CVPR", 2023), ("CVPR", 2024), ("CVPR", 2025),
    ("ICCV", 2023), ("ICCV", 2025),
    ("ECCV", 2022), ("ECCV", 2024),
]
~~~

Try the CVF Open Access event URL for each candidate. Keep unavailable candidates in the manifest with status skipped and an HTTP reason.

- [ ] Step 3: Implement the command arguments

The command must support:

~~~text
--venues CVPR ICCV ECCV
--years 2022 2023 2024 2025
--out ../data/cvf_2022_2025.csv
--cache ../data/raw/cvf
--delay 0.25
--workers 4
--limit 20
--resume
--dry-run
~~~

The default run writes the CSV and adjacent manifest JSON. Dry-run discovers and parses but does not write SQLite.

- [ ] Step 4: Write a summary that cannot be mistaken for completion

Print:

~~~text
events_seen=8
event_skipped=0
detail_discovered=integer
records_parsed=integer
duplicates=integer
parse_errors=integer
missing_abstract=integer
csv=output_csv_path
manifest=output_manifest_path
~~~

Do not print a fabricated target count or call the crawl complete unless all discovered detail URLs have a terminal status.

- [ ] Step 5: Run command tests and a bounded network dry run

Run:

~~~powershell
python -m pytest tests/test_crawl_command.py -q
python scripts/crawl_cvf.py --years 2024 --venues CVPR --limit 2 --dry-run --cache ../data/raw/cvf-test
~~~

Expected: command tests pass; the dry run either parses two public pages or reports a concrete network error without creating synthetic records.

- [ ] Step 6: Commit the command

~~~powershell
git add backend/app/crawlers/cvf.py backend/scripts/crawl_cvf.py backend/tests/test_crawl_command.py
git commit -m "feat: add resumable CVF crawl command"
~~~

---

### Task 4: Extend the database and import path for crawl provenance

**Files:**
- Modify: backend/app/models.py
- Modify: backend/app/schemas.py
- Modify: backend/app/db.py
- Modify: backend/app/services/papers.py
- Create: backend/tests/test_schema_migration.py
- Modify: backend/tests/test_papers_api.py

- [ ] Step 1: Write migration and provenance tests

Add a test that creates a v1-style Paper table, calls init_db, and asserts that crawled_at and parser_version columns exist. Add an API test that creates a CVF paper and asserts the response preserves source, source_url, and parser_version.

- [ ] Step 2: Add model fields and indexes

Add nullable fields to Paper:

~~~python
crawled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
parser_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
~~~

Add indexes for conference/year and normalized_title. Do not change the existing duplicate constraint.

- [ ] Step 3: Add additive SQLite migration logic

After Base.metadata.create_all(engine), inspect the paper table. For each missing additive column, execute one explicit ALTER TABLE statement inside engine.begin(). Never drop or rename existing columns. The migration list must contain crawled_at and parser_version only.

- [ ] Step 4: Extend schemas and CSV import

Add optional crawled_at and parser_version fields to PaperCreate, PaperUpdate, and PaperRead. The CSV importer must parse ISO timestamps when present and default source to csv when absent. Existing fixture imports must continue to work unchanged.

- [ ] Step 5: Run migration and paper tests

Run:

~~~powershell
python -m pytest tests/test_schema_migration.py tests/test_papers_api.py -q
~~~

Expected: all selected tests pass, including old CSV tests.

- [ ] Step 6: Commit the provenance unit

~~~powershell
git add backend/app/models.py backend/app/schemas.py backend/app/db.py backend/app/services/papers.py backend/tests/test_schema_migration.py backend/tests/test_papers_api.py
git commit -m "feat: persist crawl provenance metadata"
~~~

---

### Task 5: Add statistics services and API endpoints for the extensions

**Files:**
- Modify: backend/app/services/metrics.py
- Modify: backend/app/api/stats.py
- Modify: backend/app/api/papers.py
- Modify: backend/app/services/papers.py
- Modify: backend/app/schemas.py
- Create: backend/tests/test_extensions_api.py

- [ ] Step 1: Write failing endpoint tests

Cover these cases:

~~~python
def test_topic_inspector_returns_related_papers(client, seeded_papers):
    response = client.get("/api/stats/topics/transformer/inspector")
    assert response.status_code == 200
    assert response.json()["keyword"] == "transformer"
    assert response.json()["representative_papers"]


def test_evolution_returns_sorted_year_frames(client, seeded_papers):
    response = client.get("/api/stats/evolution?limit=10")
    assert response.status_code == 200
    assert response.json()["years"] == sorted(response.json()["years"])
    assert all(len(frame["topics"]) <= 10 for frame in response.json()["frames"])


def test_quality_audit_reports_missing_fields(client, seeded_papers):
    response = client.get("/api/stats/quality")
    assert response.status_code == 200
    assert response.json()["total"] > 0
    assert "keyword_coverage" in response.json()


def test_papers_export_csv_and_bibtex(client, seeded_papers):
    csv_response = client.get("/api/papers/export?format=csv&conference=CVPR")
    bib_response = client.get("/api/papers/export?format=bibtex&conference=CVPR")
    assert csv_response.status_code == 200
    assert "text/csv" in csv_response.headers["content-type"]
    assert bib_response.status_code == 200
    assert "@inproceedings" in bib_response.text
~~~

Run the new tests and confirm they fail before implementation.

- [ ] Step 2: Implement pure metric builders

Add these functions to metrics.py:

~~~python
def build_topic_inspector(rows, keyword, total_papers):
    raise NotImplementedError

def build_yearly_evolution(rows, limit=10):
    raise NotImplementedError

def build_quality_audit(rows):
    raise NotImplementedError
~~~

Use the existing calculate_heat definition. Sort years numerically, topics by heat descending then name, and keep representative papers deterministic by year descending and id ascending.

- [ ] Step 3: Add API response schemas

Define typed response models for inspector, evolution frames, quality audit, and export query validation. Reject export formats other than csv and bibtex with HTTP 422.

- [ ] Step 4: Add routes with stable route ordering

Register stats routes before any parameterized stats route. Register /api/papers/export before /api/papers/{paper_id}. Return 404 for an unknown inspected keyword and 200 with empty frames for an empty dataset.

- [ ] Step 5: Implement streamed exports

CSV must emit UTF-8 with a header containing title, authors, conference, year, abstract, keywords, source, and source_url. BibTeX keys must be deterministic from first author surname, year, and normalized title. Escape braces, backslashes, and line breaks.

- [ ] Step 6: Run endpoint tests

Run:

~~~powershell
python -m pytest tests/test_extensions_api.py tests/test_stats_api.py tests/test_papers_api.py -q
~~~

Expected: all selected tests pass.

- [ ] Step 7: Commit the API extension

~~~powershell
git add backend/app/services/metrics.py backend/app/api/stats.py backend/app/api/papers.py backend/app/services/papers.py backend/app/schemas.py backend/tests/test_extensions_api.py
git commit -m "feat: add topic evolution quality and export APIs"
~~~

---

### Task 6: Rebuild the shared Vue shell against the Stitch layout

**Files:**
- Modify: frontend/src/styles/tokens.css
- Modify: frontend/src/styles/base.css
- Modify: frontend/src/components/AppShell.vue
- Create: frontend/src/components/TelemetryBar.vue
- Create: frontend/src/components/ConferenceChips.vue
- Modify: frontend/src/components/MetricCard.vue
- Modify: frontend/src/router.js
- Create: frontend/src/components/AppShell.spec.js

- [ ] Step 1: Add a failing shell contract test

Mount AppShell with a slot and assert:

~~~javascript
expect(wrapper.find(".topbar").exists()).toBe(true)
expect(wrapper.find(".sidebar").exists()).toBe(true)
expect(wrapper.text()).toContain("CVINSIGHT")
expect(wrapper.text()).toContain("Navigation Matrix")
expect(wrapper.findAll(".conference-chip")).toHaveLength(4)
~~~

Run the test and record the current failure.

- [ ] Step 2: Replace the design tokens

Use DESIGN.md values for surface, text, semantic colors, typography, 2/4/6/8px radii, and 4/8/12/20/24/32px spacing. Add font stacks for Noto Serif, Inter, and JetBrains Mono with system fallbacks. Add tabular number styling.

- [ ] Step 3: Rebuild AppShell structure

Implement independently written Vue markup with:

- fixed 64px topbar;
- logo/brand block with CVINSIGHT and OBSERVATORY;
- central search field with > prefix, shortcut marker, and ConferenceChips;
- right telemetry count, timezone/live label, and profile marker;
- fixed 256px sidebar beginning below the topbar;
- icon/index nav items with active surface-container-high state;
- engine build and coordinate footer;
- responsive compact sidebar at <=900px.

Use RouterLink and router navigation; do not copy the Stitch HTML or inline script.

- [ ] Step 4: Add TelemetryBar and ConferenceChips

TelemetryBar emits toggle-drawer and threshold events. ConferenceChips emits update:modelValue and renders all-conference, CVPR, ICCV, ECCV states with the correct semantic colors.

- [ ] Step 5: Run shell tests and production compilation

Run:

~~~powershell
Set-Location frontend
npm run test -- --run
npm run build
~~~

Expected: the new shell test and existing PaperTable/formatHeat tests pass; Vite build succeeds.

- [ ] Step 6: Commit the shared visual system

~~~powershell
git add frontend/src/styles frontend/src/components/AppShell.vue frontend/src/components/TelemetryBar.vue frontend/src/components/ConferenceChips.vue frontend/src/components/MetricCard.vue frontend/src/router.js frontend/src/components/AppShell.spec.js
git commit -m "feat: rebuild observatory shell from reference tokens"
~~~

---

### Task 7: Rebuild overview and implement the topic inspector

**Files:**
- Create: frontend/src/components/TopicInspectorDrawer.vue
- Create: frontend/src/components/TopicInspectorDrawer.spec.js
- Modify: frontend/src/views/OverviewView.vue
- Modify: frontend/src/components/KeywordGraph.vue
- Modify: frontend/src/api.js

- [ ] Step 1: Write drawer interaction tests

Test that a selected topic renders its title, emits close, and renders representative papers; test that an error response shows a recoverable error state.

- [ ] Step 2: Add the API client method

Add:

~~~javascript
statsApi.topicInspector = (keyword) =>
  client.get("/stats/topics/" + encodeURIComponent(keyword) + "/inspector")
~~~

Keep API paths relative to /api.

- [ ] Step 3: Rebuild OverviewView with the reference topology

Place the page in this order:

1. TelemetryBar.
2. Four observatory metric cards with coordinate marks and metadata strips.
3. Twelve-column layout with five-column topic ranking and seven-column graph/inspector area.
4. Explicit source/metric badges and no hard-coded paper counts.
5. Topic rows with conference mini-bars, paper count, heat and velocity when returned.
6. Graph click and topic-row click both open the inspector.

- [ ] Step 4: Implement TopicInspectorDrawer

Use a fixed right-side Tier 3 panel with backdrop blur, close button, topic metadata, conference breakdown, yearly sparkline, related-keyword buttons, and representative-paper links. Keep the panel independent from the overview data request so it can show a loading state.

- [ ] Step 5: Run focused tests and build

Run:

~~~powershell
npm run test -- --run src/components/TopicInspectorDrawer.spec.js
npm run build
~~~

Expected: drawer tests pass and Vite build succeeds.

- [ ] Step 6: Commit the overview extension

~~~powershell
git add frontend/src/views/OverviewView.vue frontend/src/components/KeywordGraph.vue frontend/src/components/TopicInspectorDrawer.vue frontend/src/components/TopicInspectorDrawer.spec.js frontend/src/api.js
git commit -m "feat: add topic inspector and observatory overview"
~~~

---

### Task 8: Implement animated annual keyword evolution

**Files:**
- Create: frontend/src/components/EvolutionPanel.vue
- Create: frontend/src/components/EvolutionPanel.spec.js
- Modify: frontend/src/views/TrendsView.vue
- Modify: frontend/src/components/TrendChart.vue
- Modify: frontend/src/api.js

- [ ] Step 1: Write evolution state tests

Use a payload with years 2022 and 2023 and assert:

~~~javascript
expect(wrapper.find(".evolution-year").text()).toContain("2022")
await wrapper.get("[aria-label='下一年']").trigger("click")
expect(wrapper.find(".evolution-year").text()).toContain("2023")
await wrapper.get("[aria-label='播放']").trigger("click")
expect(wrapper.find("[aria-label='暂停']").exists()).toBe(true)
~~~

- [ ] Step 2: Add the evolution API client

Add:

~~~javascript
statsApi.evolution = (params = {}) => client.get("/stats/evolution", { params })
~~~

- [ ] Step 3: Implement EvolutionPanel

Keep current frame index, playing state, and speed in local refs. Use setInterval only while playing; clear it on pause and onBeforeUnmount. Render ten rows max, animate bar width and numeric labels, and show an empty-state message when the selected year has no topics.

- [ ] Step 4: Rebuild TrendsView hierarchy

Match the Stitch trend page with conference/year controls, temporal strip, large chart card, evolution panel, methodology card, and boundary note. Existing line chart remains the continuous comparison; EvolutionPanel supplies the annual animation requested by the assignment.

- [ ] Step 5: Run focused tests and build

Run:

~~~powershell
npm run test -- --run src/components/EvolutionPanel.spec.js
npm run build
~~~

Expected: focused tests pass and Vite build succeeds.

- [ ] Step 6: Commit the annual evolution feature

~~~powershell
git add frontend/src/components/EvolutionPanel.vue frontend/src/components/EvolutionPanel.spec.js frontend/src/views/TrendsView.vue frontend/src/components/TrendChart.vue frontend/src/api.js
git commit -m "feat: add animated annual keyword evolution"
~~~

---

### Task 9: Add exports, quality audit, and reference-aligned data pages

**Files:**
- Create: frontend/src/components/DataQualityCard.vue
- Modify: frontend/src/views/PapersView.vue
- Modify: frontend/src/views/ImportView.vue
- Modify: frontend/src/views/AboutView.vue
- Modify: frontend/src/components/PaperTable.vue
- Modify: frontend/src/api.js

- [ ] Step 1: Add export controls

Add two ghost actions to PapersView:

~~~text
[ EXPORT CSV ]
[ EXPORT BIBTEX ]
~~~

Use the current filters, request the matching endpoint as a blob, create an object URL, trigger a download, and revoke the URL in finally. Disable the buttons while downloading.

- [ ] Step 2: Add DataQualityCard

Render total papers, abstract coverage, source-link coverage, keyword coverage, source breakdown, and conference/year matrix. Use quality API data only; if the endpoint fails, show the existing error treatment.

- [ ] Step 3: Align ImportView and AboutView with the reference

ImportView receives the original two-column acquisition workspace, source status badge, CSV result matrix, and pipeline explanation. AboutView receives five pipeline modules, methodology formula, boundary cards, dynamic quality card, and disclaimer. Remove invented health percentages and predicted counts.

- [ ] Step 4: Align PaperTable with the reference paper matrix

Keep CRUD actions, but add compact conference chips, year/ID telemetry, source marker, abstract availability marker, and an “了解更多” path to the selected paper. Preserve empty/loading/error states.

- [ ] Step 5: Run frontend tests and build

Run:

~~~powershell
npm run test -- --run
npm run build
~~~

Expected: all frontend tests pass and build succeeds.

- [ ] Step 6: Commit the exports and quality extension

~~~powershell
git add frontend/src/components/DataQualityCard.vue frontend/src/views/PapersView.vue frontend/src/views/ImportView.vue frontend/src/views/AboutView.vue frontend/src/components/PaperTable.vue frontend/src/api.js
git commit -m "feat: add exports and data quality observatory"
~~~

---

### Task 10: Execute the real crawl and import approximately 1,500 records

**Files:**
- Create data/raw/cvf/.gitkeep
- Create data/cvf_2022_2025.csv by the crawl command
- Create data/cvf_2022_2025.manifest.json by the crawl command
- Modify backend/cvinsight.db locally only; keep it ignored

- [ ] Step 1: Verify the bounded crawl first

Run from backend:

~~~powershell
python scripts/crawl_cvf.py --years 2024 --venues CVPR --limit 20 --cache ../data/raw/cvf --out ../data/cvf_smoke.csv
~~~

Check the output counts and inspect the first three rows:

~~~powershell
Get-Content ../data/cvf_smoke.csv -TotalCount 4
~~~

Expected: titles, authors, conference, year, abstracts or explicit missing values, CVF source URLs, and parser_version are present.

- [ ] Step 2: Run the full crawl with a durable cache

Run:

~~~powershell
python scripts/crawl_cvf.py --years 2022 2023 2024 2025 --venues CVPR ICCV ECCV --cache ../data/raw/cvf --out ../data/cvf_2022_2025.csv --delay 0.25 --workers 4 --resume
~~~

Record the terminal summary in docs/blog-draft.md. The target is approximately 1,500 records, not a license to duplicate records. Record the exact actual count and all skipped event/parse counts.

- [ ] Step 3: Import the crawl output

Run:

~~~powershell
python scripts/seed_demo.py --file ../data/cvf_2022_2025.csv
~~~

The script must report created, skipped, and errors. If the existing script does not accept a file argument, add the argument before this step and retain the default demo fixture behavior.

- [ ] Step 4: Verify data volume and coverage

Run:

~~~powershell
python -c "from app.db import RuntimeSession; from app.models import Paper; from sqlalchemy import func; s=RuntimeSession(); print(s.query(func.count(Paper.id)).scalar()); s.close()"
python -m pytest -q
~~~

Expected: paper count is at least 100 times the original fixture count if public records are available; tests pass against the migrated local database.

- [ ] Step 5: Commit only reproducible crawl metadata

Do not commit the raw HTML cache or local SQLite database. Commit the manifest, CSV only if its size is acceptable for the course repository, and the updated data-source documentation:

~~~powershell
git add data/cvf_2022_2025.manifest.json data/cvf_2022_2025.csv docs/blog-draft.md README.md
git commit -m "data: import crawled CVF conference corpus"
~~~

If the CSV is too large for CodeArts, commit the manifest and an exact reproduction command instead, and document the repository size constraint.

---

### Task 11: Full visual, functional, and release verification

**Files:**
- Modify: docs/blog-draft.md
- Modify: docs/ai-collaboration.md
- Modify: docs/psp.md
- Modify: README.md

- [ ] Step 1: Run the complete local verification

~~~powershell
Set-Location backend
python -m pytest -q
Set-Location ../frontend
npm run test -- --run
npm run build
Set-Location ..
docker compose config --quiet
~~~

Expected: backend tests pass, all frontend tests pass, production build succeeds, Compose parses.

- [ ] Step 2: Start the production-style local server

~~~powershell
Set-Location backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
~~~

Check /, /api/health, /api/docs, /papers, /trends, /import, and /about. Record screenshots for the 14-item blog checklist and specifically capture the topic inspector and annual animation.

- [ ] Step 3: Review against the reference

Compare each page against the corresponding Stitch screenshot:

- topbar height, sidebar width, logo/brand hierarchy;
- search and conference chip order;
- metric card border, metadata strip, and typography;
- 12-column composition and panel proportions;
- ranking rows, graph area, inspector drawer;
- trend temporal controls and evolution panel;
- import/papers/about pipeline sections.

Fix only measurable mismatches found in this review, then rerun the affected test/build commands.

- [ ] Step 4: Update evidence documents

Record exact crawl count, event coverage, parser version, missing-field counts, test counts, build result, and local URL. Record only verified evidence; do not replace missing values with invented cloud claims; keep the cloud deployment section explicitly pending until it is actually run.

- [ ] Step 5: Commit documentation evidence

~~~powershell
git add README.md docs/blog-draft.md docs/ai-collaboration.md docs/psp.md
git commit -m "docs: record crawl and extension verification evidence"
~~~

- [ ] Step 6: Merge and publish the next release

~~~powershell
git checkout main
git merge --no-ff dev -m "merge: release CVInsight extensions"
git tag -a v1.1.0 -m "CVInsight visual fidelity and data extensions"
git push first dev main v1.1.0
~~~

Expected: CodeArts receives the new dev and main heads plus v1.1.0; verify with git ls-remote.

---

## Self-review checklist

- Visual fidelity: Tasks 6–9 cover the shell and all five Stitch page mappings.
- “了解更多”: Task 5 API plus Task 7 drawer.
- 年度热词演变: Task 5 API plus Task 8 animation.
- 更多功能: Task 5 export/quality API plus Task 9 UI.
- 100x real crawl: Tasks 2–4 implement parser/crawl/provenance; Task 10 runs and records the actual corpus.
- No direct Stitch HTML: Task 6 explicitly requires independently written Vue markup.
- Tests: every new parser/API/interactive feature has a failing-first test task and focused test command.
- Deployment evidence: Task 11 records only locally verified facts; cloud deployment remains an explicit external action.
- Every step is concrete: each task names exact files, commands, expected output, and a commit message.



