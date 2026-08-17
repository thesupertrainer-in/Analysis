---
name: dmlt-analysis
description: DMLT consolidation analysis skill — provides step-by-step guidance for running the full analysis pipeline
---

# DMLT Consolidation Analysis Skill

## Pipeline Steps

1. **calc_hardware_sizing** — compute table volumes by category (APPL, CUST, USR, ARCH)
2. **calc_company_code_collisions** — detect BUKRS conflicts across source systems
3. **calc_number_range_conflicts** — detect number-range interval overlaps
4. **calc_growth_trends** — YoY document growth and CAGR per table
5. **calc_system_profiles** — DB type, release, unicode, addon, volume per system
6. **analyse_sizing** → findings on hardware/DB requirements
7. **analyse_collisions** → risk assessment for BUKRS conflicts
8. **analyse_nriv** → number-range remediation recommendations
9. **analyse_growth** → capacity planning findings
10. **generate_executive_summary** → consolidated risk ranking + roadmap
11. **generate_excel_report** → 9-sheet Excel workbook

## Inputs Required
- `sections_json`: JSON with keys master, growth, system, org, nriv

## Key Rules
- Always complete ALL steps in order
- Never skip calc steps before analysis steps
- Pass exact calc tool output to analysis tools — never estimate
