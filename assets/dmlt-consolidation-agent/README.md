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

## Layout

```
app/
├── calc_engine.py        deterministic calculation engine (stdlib only)
├── tools/
│   ├── calc_tools.py     thin LangChain wrappers over calc_engine
│   └── excel_tool.py     launches the generator as a subprocess
└── excel_generator/      Excel report generator
    ├── generate_report.py    CLI entry point
    ├── dmlt_calc.py          loads ../calc_engine.py — one shared engine
    ├── verify_report.py      recalculation / formula-error checker
    ├── styles.py
    └── sheets/               one module per worksheet
```

The generator lives **inside `app/`** on purpose. `asset.yaml` builds this
asset with `buildPath: "."`, so the Docker build context is this directory —
anything outside it cannot be `COPY`ed into the image. Keeping the generator
under `app/` means the Dockerfile's `COPY app/ ./app/` ships it, and
`excel_tool.py` resolves the same relative path locally and in the container.
Moving it back out to a sibling directory breaks Excel generation in any
deployed container. The Dockerfile asserts its presence at build time.

## Running locally

```bash
cd app
python main.py --host 0.0.0.0 --port 8000
```

## Running tests

```bash
cd /path/to/dmlt-consolidation-agent
pytest test_calc_engine.py test_calc_tools.py
```

`test_calc_engine.py` needs only the standard library; `test_calc_tools.py`
skips itself when the agent framework is not installed.

To generate a report outside the agent and check that every formula
recalculates without errors:

```bash
cd app/excel_generator
python generate_report.py --master m.json --growth g.json --system s.json \
                          --org o.json --nriv n.json --out report.xlsx
python verify_report.py report.xlsx      # needs LibreOffice + uno bindings
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
