# Optional telemetry — gracefully degraded in local dev
try:
    from sap_cloud_sdk.aicore import set_aicore_config
    from sap_cloud_sdk.core.telemetry import auto_instrument
    set_aicore_config()
    auto_instrument()
except Exception:
    pass

import json
import logging
import os
import sys

import click
import httpx
import uvicorn
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentSkill
from starlette.middleware.base import BaseHTTPMiddleware

# Optional OTEL starlette instrumentation
try:
    from opentelemetry.instrumentation.starlette import StarletteInstrumentor
    _HAS_OTEL_STARLETTE = True
except ImportError:
    _HAS_OTEL_STARLETTE = False

# Ensure app/ is on the path when running as a module
sys.path.insert(0, os.path.dirname(__file__))

from agent_executor import AgentExecutor  # noqa: E402

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

HOST     = os.environ.get("HOST",    "0.0.0.0")
PORT     = int(os.environ.get("PORT", "8000"))
CAP_URL  = os.environ.get("CAP_URL", "http://localhost:4004")


class DMTLInvokeMiddleware(BaseHTTPMiddleware):
    """
    Handles the fire-and-forget POST /invoke from the CAP startAnalysis action.

    Expected payload: { "message": "<json-string>" }
    Inner JSON: { run_ID, runid, sections, callbackUrl }
    """

    async def dispatch(self, request, call_next):
        if request.url.path == "/invoke" and request.method == "POST":
            try:
                body = await request.body()
                payload = json.loads(body)
                message_str = payload.get("message", "{}")
                try:
                    run_data = json.loads(message_str)
                except Exception:
                    run_data = {}

                sections     = run_data.get("sections", {})
                run_id       = run_data.get("run_ID", "")
                runid        = run_data.get("runid", "")
                callback_url = run_data.get("callbackUrl", "")

                logger.info("Received /invoke for run %s (%s)", runid, run_id)

                import asyncio
                asyncio.create_task(
                    _run_pipeline(run_id, runid, sections, callback_url)
                )

                from starlette.responses import JSONResponse
                return JSONResponse({"status": "accepted", "run_ID": run_id})

            except Exception as e:
                logger.exception("/invoke handler error")
                from starlette.responses import JSONResponse
                return JSONResponse({"error": str(e)}, status_code=500)

        return await call_next(request)


async def _run_pipeline(run_id: str, runid: str, sections: dict, callback_url: str):
    """Run the full DMLT analysis pipeline and POST results back to CAP."""
    import json as _json

    logger.info("Pipeline starting for run %s", runid)

    try:
        sections_json = _json.dumps(sections)

        # ── Phase 1: Deterministic calculations ────────────────────────────
        from tools.calc_tools import (
            _calc_sizing, _calc_collisions, _calc_nriv_conflicts,
            _calc_growth, _calc_system_profiles,
        )

        def parse_result(raw: str) -> dict:
            obj = _json.loads(raw)
            return obj.get("result", obj) if obj.get("success") else {}

        sizing_raw  = _calc_sizing(sections_json)
        colls_raw   = _calc_collisions(sections_json)
        nriv_raw    = _calc_nriv_conflicts(sections_json)
        growth_raw  = _calc_growth(sections_json)
        systems_raw = _calc_system_profiles(sections_json)

        raw_list = [sizing_raw, colls_raw, nriv_raw, growth_raw, systems_raw]

        calc_results = {
            "sizing":     parse_result(sizing_raw),
            "collisions": parse_result(colls_raw),
            "nriv":       parse_result(nriv_raw),
            "growth":     parse_result(growth_raw),
            "systems":    parse_result(systems_raw),
        }

        calc_list = []
        for r in raw_list:
            obj = _json.loads(r)
            if obj.get("success"):
                calc_list.append({
                    "calculationType": obj.get("result", {}).get("calculationType", ""),
                    "result": obj.get("result", {}),
                })

        logger.info("Phase 1 complete — %d calc results", len(calc_list))

        # ── Phase 2: AI analysis ───────────────────────────────────────────
        from tools.ai_analysis_tools import (
            _analyse_sizing, _analyse_collisions, _analyse_nriv,
            _analyse_growth, _generate_executive_summary,
        )

        ai_findings = []
        for fn, key in [
            (_analyse_sizing,             "sizing"),
            (_analyse_collisions,         "collisions"),
            (_analyse_nriv,               "nriv"),
            (_analyse_growth,             "growth"),
        ]:
            try:
                result = _json.loads(fn(_json.dumps(calc_results[key])))
                ai_findings.append(result)
            except Exception as e:
                logger.warning("AI analysis %s failed: %s", key, e)

        try:
            summary = _json.loads(_generate_executive_summary(_json.dumps(calc_results)))
            ai_findings.append(summary)
        except Exception as e:
            logger.warning("Executive summary failed: %s", e)

        logger.info("Phase 2 complete — %d AI findings", len(ai_findings))

        # ── Phase 3: Excel generation ──────────────────────────────────────
        from tools.excel_tool import _generate_excel
        excel_b64 = ""
        try:
            excel_raw = _generate_excel(sections_json, run_label=runid)
            excel_obj = _json.loads(excel_raw)
            if excel_obj.get("success"):
                excel_b64 = excel_obj.get("excelBase64", "")
                logger.info("Phase 3 complete — Excel generated (%d bytes b64)", len(excel_b64))
            else:
                logger.warning("Excel generation failed: %s", excel_obj.get("error"))
        except Exception as e:
            logger.warning("Excel tool error: %s", e)

        # ── Phase 4: POST callback ─────────────────────────────────────────
        if callback_url:
            cb_payload = {
                "runid":              run_id,
                "calculationResults": _json.dumps(calc_list),
                "aiFindings":         _json.dumps(ai_findings),
                "excelBase64":        excel_b64,
            }
            async with httpx.AsyncClient(timeout=300) as client:
                resp = await client.post(callback_url, json=cb_payload)
                logger.info("Callback %s → HTTP %d", callback_url, resp.status_code)
        else:
            logger.warning("No callbackUrl — results not posted back")

        logger.info("Pipeline complete for run %s", runid)

    except Exception as e:
        logger.exception("Pipeline FAILED for run %s: %s", runid, e)
        if callback_url:
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    await client.post(callback_url, json={
                        "runid":              run_id,
                        "calculationResults": "[]",
                        "aiFindings":         "[]",
                        "excelBase64":        "",
                    })
            except Exception:
                pass


def build_app():
    """Factory for uvicorn app discovery (module:build_app pattern)."""
    skill = AgentSkill(
        id="dmlt-consolidation-agent",
        name="dmlt-consolidation-agent",
        description="DMLT Consolidation Study Assistant — analyses SAP system consolidation feasibility",
        tags=["dmlt", "consolidation", "sap", "analysis"],
        examples=[
            "Analyse the DMLT consolidation data and generate an Excel report",
            "What are the blocking issues for this SAP consolidation?",
        ],
    )
    agent_card = AgentCard(
        name="dmlt-consolidation-agent",
        description="DMLT Consolidation Study Assistant — analyses SAP system consolidation feasibility",
        url=os.environ.get("AGENT_PUBLIC_URL", f"http://{HOST}:{PORT}/"),
        version="1.0.0",
        default_input_modes=["text", "text/plain"],
        default_output_modes=["text", "text/plain"],
        capabilities=AgentCapabilities(streaming=True, push_notifications=False),
        skills=[skill],
    )
    server = A2AStarletteApplication(
        agent_card=agent_card,
        http_handler=DefaultRequestHandler(
            agent_executor=AgentExecutor(),
            task_store=InMemoryTaskStore(),
        ),
    )
    app = server.build()
    app.add_middleware(DMTLInvokeMiddleware)

    if _HAS_OTEL_STARLETTE:
        StarletteInstrumentor().instrument_app(app)

    return app


@click.command()
@click.option("--host", default=HOST)
@click.option("--port", default=PORT)
def main(host: str, port: int):
    logger.info("Starting DMLT agent at http://%s:%d", host, port)
    app = build_app()
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
