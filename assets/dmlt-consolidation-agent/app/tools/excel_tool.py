"""
Excel generation tool — wraps the existing Excel generator.

Calls generate_report.py with the sections data and returns the Excel
as a base64-encoded string for callback to the CAP backend.
"""
import base64
import json
import logging
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Path to Excel generator (relative to agent asset root)
_AGENT_ROOT = Path(__file__).parent.parent.parent
_GENERATOR_ROOT = _AGENT_ROOT.parent / "dmlt-excel-generator"
_GENERATE_SCRIPT = _GENERATOR_ROOT / "generate_report.py"


class ExcelGenInput(BaseModel):
    sections_json: str = Field(
        description="JSON string with keys master, growth, system, org, nriv"
    )
    run_label: str = Field(
        default="",
        description="Optional run label to embed in the Cover sheet (e.g. RUN_02)"
    )


def _generate_excel(sections_json: str, run_label: str = "") -> str:
    """
    Generate Excel workbook from JSON sections.

    Returns base64-encoded .xlsx content, or error JSON on failure.
    """
    try:
        sections = json.loads(sections_json)

        # Write each section to a temp file
        tmp_dir = tempfile.mkdtemp(prefix="dmlt_excel_")
        file_paths: dict[str, str] = {}

        for name in ["master", "growth", "system", "org", "nriv"]:
            data = sections.get(name, [])
            if not isinstance(data, list):
                data = []
            # Wrap as the generator expects: {"runid": ..., "section": ..., "data": [...]}
            runid = (data[0].get("runid") if data else None) or run_label or "UNKNOWN"
            payload = {"runid": runid, "section": name, "data": data}
            fpath = os.path.join(tmp_dir, f"{name}.json")
            with open(fpath, "w") as f:
                json.dump(payload, f)
            file_paths[name] = fpath

        out_path = os.path.join(tmp_dir, "report.xlsx")

        # Locate Python with openpyxl
        pypath = os.environ.get("PYTHONPATH", "/tmp/pylibs")
        py_exe = sys.executable

        cmd = [
            py_exe,
            str(_GENERATE_SCRIPT),
            "--master", file_paths["master"],
            "--growth", file_paths["growth"],
            "--system", file_paths["system"],
            "--org",    file_paths["org"],
            "--nriv",   file_paths["nriv"],
            "--out",    out_path,
        ]

        env = os.environ.copy()
        if pypath and pypath not in env.get("PYTHONPATH", ""):
            env["PYTHONPATH"] = pypath + ":" + env.get("PYTHONPATH", "")

        result = subprocess.run(
            cmd,
            capture_output=True, text=True, timeout=300, env=env
        )

        if result.returncode != 0:
            logger.error("Excel generator error: %s", result.stderr)
            return json.dumps({
                "success": False,
                "error":   f"Excel generator failed: {result.stderr[-500:]}",
            })

        if not os.path.exists(out_path):
            return json.dumps({"success": False, "error": "Output file not created"})

        with open(out_path, "rb") as f:
            excel_b64 = base64.b64encode(f.read()).decode()

        logger.info("Excel generated successfully: %s (%d bytes)",
                    out_path, os.path.getsize(out_path))

        return json.dumps({
            "success":    True,
            "excelBase64": excel_b64,
            "sizeBytes":  os.path.getsize(out_path),
        })

    except Exception as e:
        logger.exception("generate_excel failed")
        return json.dumps({"success": False, "error": str(e)})


def get_excel_tool() -> list[StructuredTool]:
    return [
        StructuredTool(
            name="generate_excel_report",
            description=(
                "Generate a 9-sheet Excel workbook from the JSON sections data. "
                "Returns base64-encoded .xlsx content. "
                "Input: sections_json with master, growth, system, org, nriv arrays."
            ),
            args_schema=ExcelGenInput,
            func=_generate_excel,
            handle_tool_error=True,
        )
    ]
