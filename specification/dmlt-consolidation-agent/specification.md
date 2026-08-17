# Specification: dmlt-consolidation-agent

> **Guidelines**: Read [guidelines.md](../guidelines.md) and [guidelines-agent.md](../guidelines-agent.md) before executing ANY tasks below. Follow all constraints described there throughout execution.

## Basic Setup

- [ ] Read `product-requirements-document.md` and `intent.md` for full context
- [ ] Bootstrap agent code in `assets/dmlt-consolidation-agent/` using skill `sap-agent-bootstrap` (invoke from inside `assets/dmlt-consolidation-agent/`, use copy commands — do NOT create files manually)
- [ ] Install dependencies, validate the agent starts and responds at `/.well-known/agent.json`

---

## Project-Specific Tasks

### Agent Identity & System Prompt

- [ ] Set agent name: `DMLT Consolidation Study Assistant`
- [ ] Set agent description: `Analyses SAP system extract data for DMLT consolidation studies. Runs deterministic calculations on table volumes, org structure, number ranges, and growth trends, then applies AI reasoning to generate data quality findings and an Excel report.`
- [ ] Write system prompt in `app/agent.py` `@prompt_section` that:
  - States the agent's purpose: analyse DMLT JSON extract data and produce a structured consolidation study report
  - Instructs the agent: "Always run deterministic calculations first and with 100% fidelity before any AI reasoning. Never invent, estimate, or approximate calculation results."
  - Instructs the agent: "Every AI finding must reference the specific data point or calculation result that produced it. Never generate unsupported findings."
  - Instructs the agent: "You operate only on the JSON data provided in the run payload. Never assume or invent data about SAP systems."
  - Instructs the agent: "Do not hallucinate data. If a section's data is empty or missing, say so explicitly in the findings."

---

### Tool: Validate Run Payload

- [ ] Create tool `validate_run_payload(run_payload: dict) -> dict`:
  - Input: full run payload from CAP backend `{ runid, sections: { master: [...], growth: [...], system: [...], org: [...], nriv: [...] } }`
  - Validates each section is present and non-empty
  - Validates required fields per section (see CAP spec for field lists)
  - Returns `{ valid: bool, errors: [{ section, message }], sidcltns: [str], record_counts: { section: int } }`
  - Deterministic — identical input always returns identical output

---

### Tool: Calculate Sizing

- [ ] Create tool `calculate_sizing(master_data: list) -> dict`:
  - Uses ONLY rows where `agg_level == "T"` (table-level totals, not company-code splits) for system totals
  - Calculates per system (sidclnt):
    - Total row count (`sum of tab_total_cnt`)
    - Total size in KB (`sum of tab_total_kb`)
    - Top 10 tables by row count (tabname, tab_total_cnt, tab_total_kb)
    - Top 10 tables by size KB (tabname, tab_total_kb, tab_total_cnt)
  - Calculates consolidated estimates (sum across ALL systems):
    - Total consolidated row count
    - Total consolidated size KB
    - Per-table consolidated count: for each unique tabname, sum tab_total_cnt across systems
    - Per-table consolidated size: for each unique tabname, sum tab_total_kb across systems
  - Identifies the largest system by total row count (candidate shell/target system)
  - Returns structured dict with all above results keyed by sidclnt and a `consolidated` key
  - Deterministic — no randomness, no AI calls

---

### Tool: Calculate Company Code Collisions

- [ ] Create tool `calculate_collisions(org_data: list) -> dict`:
  - Filters org rows where `from_type == "BUKRS"` (company codes)
  - Groups by `from_id` (company code number) across all sidclnt values
  - A collision exists when the same `from_id` appears in more than one sidclnt with a DIFFERENT `from_text` (company code name)
  - For each collision:
    - Records: company code (`from_id`), list of `{ sidclnt, from_text }` showing the different meanings
  - Also identifies exact duplicates (same from_id, same from_text across systems) — these are safe merges, not collisions
  - Returns `{ collisions: [...], safe_duplicates: [...], total_bukrs_count: int, collision_count: int }`
  - Deterministic

---

### Tool: Calculate Number Range Conflicts

- [ ] Create tool `calculate_nriv_conflicts(nriv_data: list) -> dict`:
  - Groups nriv rows by `object + nrrangenr` key
  - A conflict exists when the same `object + nrrangenr` appears in more than one sidclnt AND either:
    - The `nrlevel` (current level pointer) differs between systems, OR
    - The `fromnumber`–`tonumber` ranges overlap between systems
  - Range overlap check: two ranges [a,b] and [c,d] overlap if `a <= d AND c <= b`
  - For each conflict:
    - Records: object, nrrangenr, list of `{ sidclnt, fromnumber, tonumber, nrlevel }` per system
    - Tags conflict type: `LEVEL_MISMATCH`, `RANGE_OVERLAP`, or `BOTH`
  - Returns `{ conflicts: [...], total_objects: int, conflict_count: int }`
  - Deterministic

---

### Tool: Calculate Growth Trends

- [ ] Create tool `calculate_growth(growth_data: list) -> dict`:
  - Groups by `tabname + sidclnt`, sorts by `gjahr` ascending
  - For each table+system combination:
    - Lists all years and doc_counts in order
    - Calculates year-on-year growth rate for each consecutive year pair: `(current - previous) / previous * 100`
    - Identifies steep recent growth: last 3 years average YoY growth > 20%
    - Identifies archiving candidates: last year with data is more than 5 years ago OR last 3 years avg growth is negative
    - Identifies missing years: gaps in the gjahr sequence (e.g. 2010 present, 2011 missing, 2012 present)
  - Returns `{ tables: [...], steep_growth_tables: [...], archiving_candidates: [...], data_quality_flags: [...] }`
  - Deterministic

---

### Tool: Calculate System Profiles

- [ ] Create tool `calculate_system_profiles(system_data: list) -> dict`:
  - Builds a comparison table of all systems: sidclnt, sid, db_sys, rel, sp_level, unicode, addons, total_vol, occupied_vol
  - Detects heterogeneity flags:
    - Mixed databases: more than one distinct `db_sys` value across systems
    - Mixed releases: more than one distinct `rel` value
    - Mixed unicode settings: both `X` and blank/null `unicode` values present
    - Mixed SP levels: more than one distinct `sp_level` value
  - Calculates utilisation per system: `occupied_vol / total_vol * 100` (as percentage)
  - Returns `{ systems: [...], heterogeneity_flags: [...], utilisation: { sidclnt: pct } }`
  - Deterministic

---

### Tool: Generate Excel Report

- [ ] Create tool `generate_excel_report(run_id: str, calculation_results: dict) -> str`:
  - Uses `openpyxl` to build a workbook entirely in code (no template file dependency for now — template will be integrated later when provided by user)
  - Creates 6 sheets in this order:
    1. **Summary** — run metadata (runid, date, systems), headline numbers (total rows, total KB, collision count, conflict count, steep-growth table count), AI findings summary per section
    2. **Sizing** — per-system totals table; top 10 tables by rows; top 10 tables by size; consolidated totals row; largest system highlighted
    3. **Collisions** — collision list table (company code, systems, meanings); safe duplicates table; counts
    4. **Conflicts** — conflict list table (object, nrrangenr, per-system ranges and levels, conflict type); counts
    5. **Growth** — per-table growth trend data; steep growth table list; archiving candidates list; data quality flags
    6. **System Profiles** — system comparison table; heterogeneity flags; utilisation percentages
  - Applies consistent formatting:
    - Header rows: bold, light blue fill (`#D9E1F2`), border
    - Alternating row colours for data tables
    - Column widths auto-fitted to content
    - Numbers formatted with thousand separators
    - Percentages formatted as `##.#%`
  - Includes AI findings in each sheet: dedicate a section below each data table for "AI Findings & Recommendations" with finding text and the data reference that produced it
  - Saves file to `outputs/<run_id>/report.xlsx` (creates directory if needed)
  - Returns the absolute file path
  - Add `openpyxl` to `requirements.txt`

---

### AI Analysis Tools (on top of calculation results)

- [ ] Create tool `analyse_sizing(sizing_results: dict) -> list`:
  - Receives output of `calculate_sizing`
  - Generates findings for:
    - Volume imbalance: if largest system is >3x the smallest, flag for consolidation planning
    - Tables dominating storage: if top 3 tables account for >60% of total KB, flag for archiving review
    - Zero-count large tables: any table with 0 rows but non-zero KB (data quality issue)
    - Consolidated size risk: if total consolidated size > any single system's total_vol
  - Each finding: `{ type, severity: HIGH|MEDIUM|LOW, message, data_reference }`

- [ ] Create tool `analyse_collisions(collision_results: dict) -> list`:
  - Receives output of `calculate_collisions`
  - Generates findings for:
    - Any collision found: flag as HIGH severity — these must be renumbered before consolidation
    - High collision count: if > 10 collisions, flag consolidation complexity as HIGH
    - Safe duplicate count: note that safe duplicates simplify consolidation
  - Each finding: `{ type, severity, message, data_reference }`

- [ ] Create tool `analyse_conflicts(conflict_results: dict) -> list`:
  - Receives output of `calculate_nriv_conflicts`
  - Generates findings for:
    - Any RANGE_OVERLAP conflict: HIGH severity — ranges will collide on merge
    - Any LEVEL_MISMATCH conflict: MEDIUM severity — current levels differ, must be aligned
    - High conflict count: if > 20 conflicts, flag as HIGH complexity
    - Objects with both overlap and level mismatch: flag as CRITICAL
  - Each finding: `{ type, severity, message, data_reference }`

- [ ] Create tool `analyse_growth(growth_results: dict) -> list`:
  - Receives output of `calculate_growth`
  - Generates findings for:
    - Steep growth tables: flag for capacity planning before migration
    - Archiving candidates: flag for archiving before migration to reduce migration volume
    - Missing year gaps: flag as data quality issue — extractor may have missed data
    - Tables with zero doc_count in recent years but large historical data: flag as inactive
  - Each finding: `{ type, severity, message, data_reference }`

- [ ] Create tool `analyse_system_profiles(profile_results: dict) -> list`:
  - Receives output of `calculate_system_profiles`
  - Generates findings for:
    - Mixed databases: HIGH severity — requires DB migration as part of consolidation
    - Mixed releases: MEDIUM severity — must align SAP releases before technical merge
    - Mixed unicode: HIGH severity — unicode conversion required
    - Mixed SP levels: LOW severity — note SP alignment recommendation
    - Low utilisation system (<30%): flag as candidate for decommission rather than merge
    - High utilisation system (>85%): flag for storage expansion before consolidation
  - Each finding: `{ type, severity, message, data_reference }`

---

### Main Agent Flow (stream / invoke)

- [ ] Implement `_run_agent(run_payload: dict) -> dict` async helper (NOT a generator) that executes the full pipeline:
  1. **M1 — Validate & Ingest**: Call `validate_run_payload` → log `M1.achieved` or `M1.missed`
  2. **M2 — Calculations**: Call all 5 calculation tools in sequence → store results → log `M2.achieved` or `M2.missed`
  3. **M3 — AI Analysis**: Call all 5 analysis tools → store findings → log `M3.achieved` or `M3.missed`
  4. **M4 — Excel**: Call `generate_excel_report` with calculation results + AI findings → log `M4.achieved` or `M4.missed`
  5. **M5 — Callback**: POST results back to CAP backend at `{CAP_URL}/api/runs/{runid}/results` with `{ calculationResults, aiFindings, excelBase64 }` → log `M5.achieved` or `M5.missed`
  - Returns `{ runid, status, findings_count, excel_path }`

- [ ] Implement `stream(query, context_id, ext_impl)` that calls `_run_agent()` and yields the result
- [ ] Implement `invoke(query, context_id)` that calls `_run_agent()` and returns the result directly

- [ ] Add OpenTelemetry spans for each milestone using decorator form on `_run_agent` helper sub-steps
- [ ] Ensure `auto_instrument()` is called at top of `main.py` before any AI framework imports

---

### Runtime Skill: Calculation Rules Reference

- [ ] Create `app/skills/calculation-rules/SKILL.md` with:
  - Frontmatter: `name: calculation-rules`, `description: Reference for all deterministic calculation rules used in DMLT consolidation analysis`
  - Body documenting all 5 calculation rules with field definitions, formulas, and examples
  - This skill is loaded on demand by the agent for reasoning context

---

### CAP Backend Integration

- [ ] Read `CAP_URL` from environment variable (default: `http://localhost:4004`)
- [ ] After completing Excel generation, POST results to `{CAP_URL}/api/runs/{runid}/results`:
  - Body: `{ calculationResults: [...], aiFindings: [...], excelBase64: "<base64 encoded xlsx>" }`
- [ ] Handle callback failure gracefully: log `M5.missed` with error detail, return error in agent response

---

### asset.yaml

- [ ] Create `assets/dmlt-consolidation-agent/asset.yaml`:

```yaml
apiVersion: asset.sap/v1
kind: Asset
type: ai-agent
metadata:
  name: dmlt-consolidation-agent
components:
  - name: agent
    buildPath: .
    provides:
      endpoints:
        - path: /.well-known/agent.json
          port: 8000
          protocol: http
        - path: /invoke
          port: 8000
          protocol: http
    port: 8000
```

- [ ] No MCP server dependencies — this agent operates entirely on the JSON payload passed in the request body; no SAP system connectivity required

---

## Delete Template Skill

- [ ] Delete the template runtime skill: `rm -rf assets/dmlt-consolidation-agent/app/skills/template-skill/`

---

## Instrumentation Checklist

- [ ] Verify M1–M5 log statements exist: `grep -r "M[0-9]\.achieved" assets/dmlt-consolidation-agent/app/`
- [ ] Verify decorator imports: `grep -r "sap_cloud_sdk.agent_decorators" assets/dmlt-consolidation-agent/app/`
- [ ] Verify exactly 3 decorated functions in `agent.py`: `grep -c "^@agent_model\|^@agent_config\|^@prompt_section" assets/dmlt-consolidation-agent/app/agent.py` → must return 3

---

## Testing

- [ ] `conftest.py` sets `IBD_TESTING=true` only
- [ ] Write unit test for `validate_run_payload` — test valid input, missing section, malformed fields
- [ ] Write unit test for `calculate_sizing` — test with sample master data; verify totals, top-10, consolidated, largest system
- [ ] Write unit test for `calculate_collisions` — test collision detection (same BUKRS, different text) and safe duplicate detection
- [ ] Write unit test for `calculate_nriv_conflicts` — test LEVEL_MISMATCH, RANGE_OVERLAP, and BOTH scenarios
- [ ] Write unit test for `calculate_growth` — test YoY calculation, steep growth flag, archiving candidate flag, missing year detection
- [ ] Write unit test for `calculate_system_profiles` — test heterogeneity flags, utilisation calculation
- [ ] Write unit test for `generate_excel_report` — verify 6 sheets are created, file is saved to correct path
- [ ] Write unit tests for each AI analysis tool — verify finding types and severities are produced correctly
- [ ] Write one integration test: pass a complete sample run payload (using data from `extractor_files/`) through the full `_run_agent()` pipeline with LLM mocked — verify all 5 milestones are logged and Excel file is produced
- [ ] Run `pytest` from `assets/dmlt-consolidation-agent/` — fix any failures
- [ ] Confirm coverage ≥ 70%
- [ ] Run final `pytest` (no args) to generate `test_report.json`
- [ ] Verify `test_report.json` exists: `ls assets/dmlt-consolidation-agent/test_report.json`
