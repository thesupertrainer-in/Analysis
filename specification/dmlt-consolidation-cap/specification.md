# Specification: dmlt-consolidation-cap

> **Guidelines**: Read [guidelines.md](../guidelines.md) and [guidelines-cap.md](../guidelines-cap.md) before executing ANY tasks below. Follow all constraints described there throughout execution.

## Basic Setup

- [ ] Read `product-requirements-document.md` and `intent.md` for full context
- [ ] Invoke the `cap-development` skill from `assets/dmlt-consolidation-cap/` to set up the CAP project structure
- [ ] Install dependencies (`npm install`), validate the project starts (`cds watch`) and responds

---

## Data Model

- [ ] Define CDS entity `Runs` with fields:
  - `runid` : String (key)
  - `exportedOn` : String
  - `sidcltns` : String (comma-separated list of sidclnt values in the run)
  - `status` : String enum: `PENDING | INGESTING | CALCULATING | ANALYSING | COMPLETE | FAILED`
  - `errorMessage` : String (nullable)
  - `createdAt` : Timestamp
  - `excelPath` : String (nullable — path to generated Excel file once complete)

- [ ] Define CDS entity `RunSections` with fields:
  - `id` : UUID (key)
  - `run` : Association to `Runs`
  - `section` : String enum: `master | growth | system | org | nriv`
  - `rawData` : LargeString (full JSON array as string)
  - `recordCount` : Integer

- [ ] Define CDS entity `CalculationResults` with fields:
  - `id` : UUID (key)
  - `run` : Association to `Runs`
  - `calculationType` : String enum: `SIZING | COLLISIONS | CONFLICTS | GROWTH | SYSTEM_PROFILES`
  - `resultJson` : LargeString (serialised calculation output)
  - `calculatedAt` : Timestamp

- [ ] Define CDS entity `AIFindings` with fields:
  - `id` : UUID (key)
  - `run` : Association to `Runs`
  - `section` : String (matches calculationType)
  - `findingsJson` : LargeString (serialised AI findings array)
  - `generatedAt` : Timestamp

- [ ] Run `cds compile srv/` to validate models compile without errors

---

## File Upload Service (R01 — JSON Ingestion)

- [ ] Create a REST endpoint `POST /api/runs/upload` that:
  - Accepts a multipart form upload of exactly 5 JSON files (master, growth, system, org, nriv)
  - Each file has shape `{ "runid": "...", "section": "...", "data": [...] }`
  - Validates that all 5 sections are present; returns a clear error if any are missing
  - Validates each file parses as valid JSON; returns field-level errors for malformed files
  - Validates each file contains required fields per section:
    - `master`: sidclnt, tabname, bukrs, agg_level, category, clnt_dep, clnt_count, clnt_size, tab_total_cnt, tab_total_kb
    - `growth`: sidclnt, tabname, gjahr, doc_count
    - `system`: sidclnt, sid, db_sys, rel, sp_level, unicode, addons, total_vol, occupied_vol
    - `org`: sidclnt, from_type, from_id, to_type, to_id, from_text
    - `nriv`: sidclnt, object, subobject, nrrangenr, fromnumber, tonumber, nrlevel
  - On success: creates a `Runs` record with `status=PENDING`, persists all 5 `RunSections` records, returns `{ runid, status }`

- [ ] Create a REST endpoint `POST /api/runs/:runid/start` that:
  - Sets run `status=CALCULATING`
  - Calls the AI Agent's A2A `/invoke` endpoint (configurable URL via env var `AGENT_URL`) passing the run payload
  - Returns immediately with `{ runid, status: "CALCULATING" }`

- [ ] Create a REST endpoint `GET /api/runs/:runid/status` that:
  - Returns current run status, sidcltns, createdAt, errorMessage
  - If status is `COMPLETE`, includes `excelDownloadUrl`

- [ ] Create a REST endpoint `GET /api/runs` that:
  - Returns all runs ordered by `createdAt` descending
  - Returns: runid, exportedOn, sidcltns, status, createdAt, excelPath for each

- [ ] Create a REST endpoint `GET /api/runs/:runid/results` that:
  - Returns the full CalculationResults and AIFindings for a completed run
  - Supports run comparison by accepting optional `compareRunid` query param — returns both runs' results side by side

- [ ] Create a REST endpoint `GET /api/runs/:runid/download` that:
  - Streams the generated Excel file for download
  - Returns 404 with clear message if run is not yet complete

- [ ] Create a REST endpoint `POST /api/runs/:runid/results` (internal — called by AI Agent) that:
  - Accepts `{ calculationResults: [...], aiFindings: [...], excelBase64: "..." }`
  - Persists CalculationResults and AIFindings records
  - Decodes and saves the Excel file to disk (path: `uploads/<runid>/report.xlsx`)
  - Updates run `status=COMPLETE` and sets `excelPath`
  - If any error: sets `status=FAILED` and `errorMessage`

- [ ] Write custom handler tests for upload validation, status transitions, and results persistence

---

## Upload UI (React Frontend)

- [ ] Scaffold React frontend in `assets/dmlt-consolidation-cap/ui/` using the `cap-development` skill UI scaffolding
- [ ] Build **Run Upload Page** (`/`):
  - Page title: "DMLT Consolidation Study Assistant"
  - File drop zone or file picker accepting 5 JSON files
  - File list showing each uploaded file with its detected section name (parsed from JSON `section` field) and record count
  - Validation feedback: highlight missing sections or malformed files before submission
  - "Start Analysis" button — disabled until all 5 valid files are loaded
  - On submit: calls `POST /api/runs/upload` then `POST /api/runs/:runid/start`
  - After submit: redirects to Run Status Page

- [ ] Build **Run Status Page** (`/runs/:runid`):
  - Shows run ID, systems (sidcltns), created time
  - Live status indicator: Pending → Ingesting → Calculating → Analysing → Complete / Failed
  - Polls `GET /api/runs/:runid/status` every 5 seconds while status is not terminal
  - On `COMPLETE`: shows "Download Excel Report" button calling `GET /api/runs/:runid/download`
  - On `FAILED`: shows error message clearly

- [ ] Build **Run History Page** (`/runs`):
  - Table of all past runs: Run ID, Systems, Date, Status, Download link (if complete)
  - Clicking a row navigates to Run Status Page
  - "Compare" checkbox on two completed runs → navigates to Run Comparison Page

- [ ] Build **Run Comparison Page** (`/runs/compare?run1=:id&run2=:id`):
  - Side-by-side display of calculation results for two selected runs
  - Sizing comparison: total rows and KB per system per run
  - Collision count comparison
  - Conflict count comparison
  - Highlights differences between runs

- [ ] Ensure all pages use SAP UI5 Web Components for consistent styling (Shell, Cards, Tables, Buttons)

---

## Configuration

- [ ] Add environment variable documentation (no `.env` file):
  - `AGENT_URL` — URL of the AI Agent A2A endpoint (e.g. `http://localhost:8000`)
  - `UPLOADS_DIR` — Directory for storing uploaded JSON and generated Excel files (default: `uploads/`)

- [ ] Create `uploads/` directory in `.gitignore` (do not commit uploaded files)

---

## Validation

- [ ] Run `cds compile srv/` — confirm zero errors
- [ ] Run `cds watch` — confirm service starts on port 4004
- [ ] Curl `POST /api/runs/upload` with sample files from `extractor_files/` — confirm run is created
- [ ] Curl `GET /api/runs` — confirm run appears in history
- [ ] Write and run tests for all custom handler logic
