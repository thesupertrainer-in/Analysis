# Product Requirements Document (PRD)

**Title:** SAP DMLT Consolidation Study Assistant  
**Date:** 2026-08-11  
**Owner:** SAP DMLT Consulting Team  
**Solution Category:** AI Agent, CAP App

---

## Product Purpose & Value Proposition

**Elevator Pitch:**  
SAP consultants conducting DMLT consolidation studies spend days manually processing complex SAP system extracts — this tool does it in minutes, with consistent, AI-enriched outputs every time.

**Business Need:**  
SAP system extracts (table volumes, growth trends, org structures, number ranges) are collected as JSON files during DMLT engagements. Today, consultants process these manually — running calculations in spreadsheets, writing observations by hand, and producing inconsistent reports across engagements. The tool automates ingestion, calculation, AI analysis, and Excel report generation in a single run.

**Expected Value:**  
- Reduce per-engagement analysis time significantly
- Eliminate inconsistency in findings and report formats across engagements
- Surface data quality issues that manual review may miss
- Enable trend comparison across runs and engagements over time

**Product Objectives (Prioritized):**
1. Accurately ingest and validate JSON extracts for any number of SAP systems per run
2. Execute pre-defined, deterministic calculation rules with full fidelity to user-specified logic
3. Generate AI-driven data quality findings and recommendations grounded in calculated results
4. Produce a single, professionally formatted Excel report matching the user-provided template
5. Store run history in HANA Cloud to support trend comparison across time and engagements

---

## User Profiles & Personas

### Primary Persona: Marcus — SAP DMLT Consultant

Marcus is a 35-year-old SAP consultant with 8 years of experience in landscape transformation projects. He manages 3-4 DMLT engagements simultaneously, each involving multiple SAP systems with thousands of tables, org units, and number ranges. He collects system extracts using the DMLT extractor tool and currently processes the resulting JSON files manually — running Excel formulas, writing findings by hand, and formatting reports for client delivery. He is technically proficient but spends too much time on repetitive analysis that should be automated. He needs a tool that does the heavy lifting so he can focus on interpretation and client advisory.

### Secondary Persona: Priya — SAP IT Architect

Priya is a 42-year-old IT architect at a large enterprise. She receives the consolidation study report from Marcus's team and uses it to make decisions about which SAP systems to merge, retire, or migrate. She does not run the analysis herself — she reads the report and acts on its findings. She needs clear, credible, well-structured outputs with explicit data quality flags and actionable recommendations she can present to her leadership.

### Other User Types

- **Engagement Manager**: Reviews AI recommendations before client delivery; signs off on findings
- **BTP Administrator**: Manages subscriptions, GitHub integration, and deployment; not a day-to-day user

---

## User Goals & Tasks

### For Marcus (DMLT Consultant):

**Goals:**
- Complete the data analysis phase of a DMLT engagement faster and with less manual effort
- Produce consistent, high-quality reports that meet client expectations every time
- Compare results across runs to identify trends without rebuilding analysis from scratch

**Key Tasks:**
- Upload JSON extract files (master, growth, system, org, nriv) for a run
- Trigger the analysis and wait for the Excel report to be generated
- Download the Excel report and review findings before client delivery
- Retrieve and compare previous run results

### For Priya (IT Architect):

**Goals:**
- Understand the data quality and volume characteristics of SAP systems being assessed
- Identify consolidation risks and opportunities backed by evidence

**Key Tasks:**
- Open and review the Excel report received from the consulting team
- Review data quality flags, AI findings, and charts per system and section

---

## Product Principles

1. **Rules before reasoning**: Deterministic calculations always run first; AI reasoning is applied only on top of confirmed calculation results — never to replace or guess calculation logic
2. **Template fidelity**: The Excel output must be indistinguishable from the user-provided template in layout, formatting, and branding — only data cells are populated
3. **Engagement-agnostic**: The tool must work for any number of SAP systems and any run configuration — no hardcoded assumptions about system count or structure
4. **Transparency**: Every AI finding must be traceable to the underlying data and calculation that produced it
5. **Run history as a feature**: Every run is stored — trend comparison is a first-class capability, not an afterthought

---

## Business Context

**Current State:**  
Consultants manually process DMLT JSON extracts using Excel formulas and manual observation. Each engagement produces a different report format depending on the consultant. Analysis takes days and is prone to error and omission.

**Strategic Alignment:**  
Supports SAP's DMLT methodology by standardising and accelerating the consolidation study phase — a prerequisite for all landscape transformation projects.

**Success Criteria:**
- All five JSON sections (master, growth, system, org, nriv) ingested and validated without manual intervention
- Calculation rules executed with 100% fidelity to user-specified logic
- Excel report generated and downloadable per run, matching the provided template exactly
- AI findings present in the report for every run
- Run history accessible and comparable across engagements

---

## Goals and Non-Goals

### Goals (In Scope)

- Ingest and validate JSON extract files for one or more SAP systems per run
- Execute user-defined deterministic calculation rules against the ingested data
- Apply AI reasoning to assess data quality and generate findings and recommendations
- Generate a single Excel report per run, populated using the user-provided template
- Store run results in SAP HANA Cloud for historical trend comparison
- Expose the assistant via Joule Desktop for the internal SAP consulting team

### Non-Goals (Out of Scope)

- Direct connectivity to live SAP systems — the tool operates on pre-extracted JSON files only
- Modification of calculation logic at runtime — rules are hardcoded, not configurable by end users
- Generation or modification of the Excel template — the template is provided by the user upfront
- Real-time or streaming analysis — each run is a discrete, triggered event
- External client access — the tool is for internal SAP consulting team use only

---

## Requirements

### Must-Have Requirements

**R01: JSON Ingestion and Validation**
- **Problem to Solve**: Consultants need to feed raw JSON extract files into the tool without manual pre-processing
- **User Story**: As Marcus, I need to provide my JSON extract files (master, growth, system, org, nriv) and have the tool read and validate them, so that I know the data is complete and correctly structured before analysis begins
- **Acceptance Criteria**:
  - Given a set of JSON files for a run, when ingested, then all five sections are read and validated for schema correctness
  - Given a malformed or missing section, when ingested, then the tool reports the specific error clearly before proceeding
- **Maps to Objective**: Objective 1
- **Priority Rank**: 1

**R02: Pre-Deterministic Calculation Engine**
- **Problem to Solve**: Consultants need exact, repeatable calculations applied to the data — not approximations
- **User Story**: As Marcus, I need the tool to execute my specified calculation rules against the ingested data, so that the results are identical to what I would calculate manually
- **Acceptance Criteria**:
  - Given validated JSON data, when calculations run, then all user-specified rules are applied in full and results stored
  - Given the same input data, when calculations run twice, then the output is identical
- **Maps to Objective**: Objective 2
- **Priority Rank**: 2

**R03: AI Data Quality Analysis**
- **Problem to Solve**: Consultants need AI-generated findings that go beyond raw numbers to surface patterns and risks
- **User Story**: As Marcus, I need the AI to analyse the calculation results and produce data quality findings and recommendations, so that I can identify issues I might otherwise miss
- **Acceptance Criteria**:
  - Given completed calculation results, when AI analysis runs, then findings and recommendations are generated for each relevant section
  - Given an AI finding, when reviewed, then it references the specific data point or calculation that produced it
- **Maps to Objective**: Objective 3
- **Priority Rank**: 3

**R04: Excel Report Generation**
- **Problem to Solve**: Consultants need a client-ready report that matches the standard template — not a raw data dump
- **User Story**: As Marcus, I need the tool to generate a single Excel file per run, populated with statistics, charts, and AI findings in the exact format of my template, so that I can deliver it to the client without reformatting
- **Acceptance Criteria**:
  - Given a completed analysis run, when the report is generated, then the Excel file matches the provided template in layout, sheets, fonts, and chart structure
  - Given the Excel file, when downloaded, then all data cells are populated and no template cells are altered
- **Maps to Objective**: Objective 4
- **Priority Rank**: 4

**R05: Run History Storage and Retrieval**
- **Problem to Solve**: Consultants need to revisit and compare results across runs without re-running analysis
- **User Story**: As Marcus, I need each completed run to be saved, so that I can retrieve and compare results across engagements and time periods
- **Acceptance Criteria**:
  - Given a completed run, when stored, then all results and metadata (runid, exported_on, sidclnt values) are persisted in HANA Cloud
  - Given a previous run, when retrieved, then its results are identical to the original output
- **Maps to Objective**: Objective 5
- **Priority Rank**: 5

---

## Solution Architecture

**Architecture Overview:**  
A custom solution deployed on SAP BTP, consisting of a CAP backend for data ingestion and persistence, a Python AI agent for calculation and analysis, an Excel generator for report production, and Joule Desktop as the end-user interface.

**Key Components:**

- **CAP Backend (Node.js)**: Receives JSON extract files, validates structure, stores run data and history in SAP HANA Cloud, serves Excel download links to the Joule interface
- **AI Agent (Python, A2A protocol)**: Applies pre-deterministic calculation rules, performs AI-driven data quality analysis using SAP AI Core, generates findings and recommendations
- **Excel Generator (Python, openpyxl)**: Loads the user-provided Excel template, populates data cells with statistics and AI findings, embeds charts, returns the completed file
- **SAP HANA Cloud**: Persistent store for run data, calculation results, AI findings, and run history
- **Joule Desktop**: Chat-based interface through which consultants trigger runs, monitor progress, and download the Excel report

**Integration Points:**

- JSON files → CAP Backend: file upload or sync from GitHub repository
- CAP Backend → AI Agent: run payload passed for calculation and analysis
- AI Agent → Excel Generator: calculation results and findings passed for report population
- CAP Backend → HANA Cloud: run storage and retrieval
- CAP Backend → Joule Desktop: download link returned on run completion

**Deployment Environments:**

- Development/Test: SAP Build environment — full end-to-end testing before BTP deployment
- Production: SAP BTP Cloud Foundry — Joule Desktop access for the internal consulting team

### Agent Extensibility & Instrumentation

**Agent Extensibility:**
- The AI agent is built with extension points to allow new calculation rule sets to be added without modifying core agent logic
- The data quality analysis layer is modular — new section-specific analysis modules (e.g., for future JSON sections) can be added independently
- The Excel generator is template-driven — updating the template file updates the output format without code changes

**Business Step Instrumentation:**
- All five key milestones are instrumented with structured log statements
- Log pattern: `[MILESTONE_ID].[achieved|missed]: [description]`
- Enables monitoring and debugging of agent behaviour in production via SAP AI Launchpad

### Automation & Agent Behaviour

**Automation Level:** Hybrid — deterministic calculation engine + autonomous AI reasoning layer

**Actions the system performs without human approval:**
- JSON ingestion and schema validation
- Execution of pre-defined calculation rules
- AI data quality analysis and finding generation
- Excel report generation and storage
- Run history persistence

**Actions that require human review or approval:**
- Review of AI findings before client delivery (by Marcus or the Engagement Manager)
- Sign-off on the Excel report before sharing with the client

**Model or engine used:** SAP Generative AI Hub (via SAP AI Core) for AI reasoning and data quality analysis

**Knowledge & data sources accessed:**
- JSON extract files (provided per run): master, growth, system, org, nriv sections
- User-provided calculation rules (hardcoded in agent)
- HANA Cloud run history (for trend context)

**Tools or connectors invoked:**
- CAP Backend API: JSON ingestion, run storage, download link generation (read/write)
- SAP AI Core: LLM inference for data quality analysis (read-only, no side effects on SAP systems)
- Excel Generator: Report population from template (write — produces output file)

**Guardrails & fail-safes:**
- AI findings are always grounded in calculation results — the agent cannot produce findings without completed calculations
- No SAP system data is modified — the tool operates exclusively on extracted, read-only JSON data
- If ingestion fails, the run does not proceed to calculation — error reported immediately
- If AI analysis fails, the run logs the failure and the Excel report is generated with calculation results only, flagging the missing AI section

---

## Milestones

### M1: JSON Ingested

- **Description**: All JSON section files for the run have been successfully read and validated
- **Achieved when**: All five sections (master, growth, system, org, nriv) pass schema validation for all sidclnt values in the run
- **Log on achievement**: `M1.achieved: JSON ingestion complete — [n] sections validated for [sidclnt list]`
- **Log on miss**: `M1.missed: JSON ingestion failed — [section name] [error detail]`

### M2: Calculations Complete

- **Description**: All pre-deterministic calculation rules have been executed against the validated data
- **Achieved when**: Every calculation rule in the rule set has been applied and results stored without error
- **Log on achievement**: `M2.achieved: Calculations complete — [n] rules applied across [n] systems`
- **Log on miss**: `M2.missed: Calculation engine failed — rule [rule id] error: [detail]`

### M3: AI Analysis Complete

- **Description**: The AI layer has produced data quality findings and recommendations based on calculation results
- **Achieved when**: AI findings are generated for all relevant sections and stored in the run record
- **Log on achievement**: `M3.achieved: AI analysis complete — [n] findings generated across [n] sections`
- **Log on miss**: `M3.missed: AI analysis did not complete — [reason]`

### M4: Excel Report Generated

- **Description**: The Excel report has been produced, populated, and is ready for download
- **Achieved when**: Excel file is generated matching the template, all data cells populated, download link available
- **Log on achievement**: `M4.achieved: Excel report generated — file available at [download path]`
- **Log on miss**: `M4.missed: Excel generation failed — [reason]`

### M5: Run Stored

- **Description**: The completed run — including all inputs, calculation results, AI findings, and the Excel report reference — has been persisted to HANA Cloud
- **Achieved when**: Run record is written to HANA Cloud and retrievable by runid
- **Log on achievement**: `M5.achieved: Run stored — runid [runid] persisted to HANA Cloud`
- **Log on miss**: `M5.missed: Run storage failed — runid [runid] [error detail]`

---

## Risks, Assumptions, and Dependencies

### Risks

- **Joule Studio subscription not yet active**: The team cannot access the tool via Joule Desktop until the subscription is activated in BTP — mitigate by testing fully in SAP Build first
- **Calculation rules not yet provided**: The calculation engine cannot be built until the user provides the full rule set — this is a hard blocker for R02
- **Excel template not yet provided**: The Excel generator cannot be built until the template is shared — this is a hard blocker for R04
- **AI finding quality depends on rule output quality**: If calculation rules produce incorrect results, AI findings will be unreliable — rule correctness must be validated before AI layer testing

### Assumptions

- JSON extract files follow a consistent schema (runid, exported_on, master, growth, system, org, nriv arrays) as observed in sample data
- The user will provide complete calculation rules and the Excel template before development of those components begins
- SAP AI Core entitlement is active and an AI Core service instance exists in the BTP subaccount
- The consulting team has access to Joule Desktop once the Joule Studio subscription is activated

### Dependencies

- SAP AI Core service instance (confirmed entitlement; instance activation to be verified)
- SAP HANA Cloud (subscription confirmed)
- Joule Studio subscription (entitlement confirmed; subscription activation pending)
- User-provided calculation rules (pending)
- User-provided Excel template (pending)
- GitHub or direct paste for JSON file delivery (GitHub GHES destination configuration pending BTP admin)

---

## Appendix

### Glossary

- **DMLT**: Data Migration & Landscape Transformation — SAP methodology for consolidating and simplifying SAP system landscapes
- **sidclnt**: System ID + Client combination — uniquely identifies an SAP system instance in the extract data
- **runid**: Unique identifier for a single analysis run
- **master**: JSON section containing SAP table volume data per system
- **growth**: JSON section containing year-on-year document count data
- **system**: JSON section containing SAP system profile and database metadata
- **org**: JSON section containing organisational structure hierarchy edges (company codes, controlling areas, plants, etc.)
- **nriv**: JSON section containing SAP number range interval data

### References

- SAP BTP: https://www.sap.com/products/technology-platform.html
- SAP AI Core: https://help.sap.com/docs/sap-ai-core
- SAP HANA Cloud: https://www.sap.com/products/technology-platform/hana.html
- Joule Studio: https://help.sap.com/docs/joule
