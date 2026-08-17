# Specification — DMLT Consolidation Study Assistant

> **Guidelines**: Read [guidelines.md](./guidelines.md) before executing ANY tasks below.

Check off items as completed.

---

## Solution Overview

Two assets are built in parallel:

| Asset | Type | Purpose |
|-------|------|---------|
| `dmlt-consolidation-cap` | CAP App (Node.js + React UI) | File upload UI, run management, HANA persistence, Excel download |
| `dmlt-consolidation-agent` | AI Agent (Python, A2A) | Deterministic calculations, AI analysis, Excel generation |

**Data flow:**
```
User uploads 5 JSON files via Upload UI
        ↓
CAP Backend validates & stores files → creates Run record
        ↓
CAP Backend calls Agent /invoke with run payload
        ↓
Agent: validate → calculate (5 rules) → AI analyse (5 sections) → generate Excel
        ↓
Agent POSTs results + Excel back to CAP Backend
        ↓
CAP Backend stores results, marks Run COMPLETE
        ↓
User downloads Excel report from Upload UI
```

---

## Solution Setup

- [ ] Create asset directories:
  ```
  mkdir -p assets/dmlt-consolidation-cap
  mkdir -p assets/dmlt-consolidation-agent
  ```
- [ ] Invoke `setup-solution` skill to create `solution.yaml` and `asset.yaml` files for both assets
- [ ] Validate `solution.yaml` and both `asset.yaml` files exist and are well-formed

---

## Asset Implementation

- [ ] Execute `specification/dmlt-consolidation-cap/specification.md` (all items)
- [ ] Execute `specification/dmlt-consolidation-agent/specification.md` (all items)

---

## Cross-Asset Compatibility Check

- [ ] Verify the agent's A2A `/invoke` endpoint accepts the payload shape that the CAP backend sends:
  - CAP sends: `{ runid, sections: { master: [...], growth: [...], system: [...], org: [...], nriv: [...] } }`
  - Agent expects: same shape in `validate_run_payload`
- [ ] Verify the agent's callback POST matches the CAP endpoint:
  - Agent POSTs to: `{CAP_URL}/api/runs/{runid}/results`
  - CAP accepts: `{ calculationResults: [...], aiFindings: [...], excelBase64: "..." }`
- [ ] Verify environment variables are consistent:
  - CAP: `AGENT_URL` points to agent port 8000
  - Agent: `CAP_URL` points to CAP port 4004
- [ ] Run both services locally and execute a full end-to-end test:
  - Upload all 5 files from `extractor_files/` via the Upload UI
  - Trigger analysis
  - Wait for COMPLETE status
  - Download and open Excel report — verify 6 sheets are populated
- [ ] Fix any interface mismatches before marking complete
