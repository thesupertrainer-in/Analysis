# Agent Guidelines

Technical constraints and patterns for building Pro-Code AI Agents. Follow these throughout specification execution.

## Tech Stack

- Python 3.13
- Agent framework defined in the `sap-agent-bootstrap` skill
- Agent2Agent (A2A) protocol
- Local execution only (in-memory storage, no deployment)

## Key Constraints

- NEVER use `create_react_agent` from langgraph — use `from langchain.agents import create_agent`
- NEVER call SAP APIs directly — all API consumption goes through MCP servers
- No `.env` files (environment variables supplied at runtime)
- Update `requirements.txt` for any new dependencies
- Never modify `sys.path`
- No `src.` import patterns

## Agent Instrumentation

- ALL business logic steps MUST be instrumented with structured logging and OpenTelemetry spans
- Log pattern: `[MILESTONE_ID].[achieved|missed]: [description]`
- NEVER use `with tracer.start_as_current_span(...)` inside async generators — extract business logic into a plain async helper first
- Ensure `auto_instrument()` is called at top of `main.py` before any AI framework imports

## Testing

- All generated tests go in `assets/<asset-name>/tests/`
- Unit tests: exactly one per tool; run each immediately after writing
- Integration test: one end-to-end test exercising the full agent graph
- AI Core / LLM calls MUST be mocked in all tests
- ALWAYS invoke as just `pytest` from asset root — no extra flags
- Coverage must be ≥ 70%
