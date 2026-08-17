# DMLT Consolidation Agent

AI agent for DMLT (Data Migration & Landing Team) SAP system consolidation analysis.

## Architecture

```
CAP Backend (POST /invoke)
    → Agent pipeline:
        Phase 1: Deterministic calculations (5 tools)
        Phase 2: AI findings (5 tools)
        Phase 3: Excel report generation
    → POST callback to CAP /api/save-results
```

## Tools

### Deterministic (Phase 1)
| Tool | Input | Output |
|------|-------|--------|
| `calc_hardware_sizing` | master + system sections | Category KB/MB totals, system profiles |
| `calc_company_code_collisions` | org section | BUKRS collisions, name conflicts |
| `calc_number_range_conflicts` | nriv section | NR object conflicts, level discrepancies |
| `calc_growth_trends` | growth section | YoY growth, CAGR per table |
| `calc_system_profiles` | system + master | DB, release, unicode, volume per system |

### AI Analysis (Phase 2)
| Tool | Input | Output |
|------|-------|--------|
| `analyse_sizing` | sizing result | Findings: volume, HANA migration, unicode, release |
| `analyse_collisions` | collision result | Findings: blocking BUKRS issues |
| `analyse_nriv` | nriv result | Findings: duplicate document risk |
| `analyse_growth` | growth result | Findings: capacity planning |
| `generate_executive_summary` | all 5 results | Risk ranking, roadmap, recommendation |

### Excel (Phase 3)
| Tool | Input | Output |
|------|-------|--------|
| `generate_excel_report` | all sections | Base64-encoded 9-sheet .xlsx |

## Running locally

```bash
cd app
python main.py --host 0.0.0.0 --port 8000
```

## Running tests

```bash
cd /path/to/dmlt-consolidation-agent
python test_calc_tools.py
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `HOST` | `0.0.0.0` | Server bind host |
| `PORT` | `8000` | Server port |
| `CAP_URL` | `http://localhost:4004` | CAP backend URL |
| `PYTHONPATH` | `/tmp/pylibs` | Path with openpyxl |

## Key Decisions

- **No live SAP connectivity** — operates only on provided JSON sections
- **Deterministic first** — all 5 calc tools run before any AI analysis
- **Pipeline is direct** — main.py runs the pipeline directly (not via LangGraph)
  for deterministic phases; LangGraph is used only for conversational queries
- **Fire-and-forget** — CAP calls `/invoke` and agent POSTs back to `/api/save-results`
