"""
Bridge to the canonical DMLT calculation engine.

The engine itself lives with the agent asset, at
``assets/dmlt-consolidation-agent/app/calc_engine.py``.  This module loads it
by explicit file path and re-exports it, so the Excel generator and the agent
share one implementation of the collision / conflict / sizing rules and can
never drift apart.

The module is deliberately *not* called ``calc_engine`` — that name belongs to
the engine itself, and reusing it here would shadow the real module.

Usage inside the generator:

    from dmlt_calc import detect_collisions, detect_conflicts, calculate_sizing
"""
import importlib.util
import os

_HERE = os.path.dirname(os.path.abspath(__file__))

#: Canonical engine location, relative to this file.
ENGINE_PATH = os.path.normpath(
    os.path.join(_HERE, os.pardir, "dmlt-consolidation-agent", "app", "calc_engine.py")
)

if not os.path.isfile(ENGINE_PATH):     # pragma: no cover — deployment misconfiguration
    raise ImportError(
        f"DMLT calculation engine not found at {ENGINE_PATH}. The Excel generator "
        "must sit alongside the dmlt-consolidation-agent asset."
    )

_spec = importlib.util.spec_from_file_location("dmlt_calc_engine", ENGINE_PATH)
_engine = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_engine)

# ── re-exports ────────────────────────────────────────────────────────────────
calculate_sizing = _engine.calculate_sizing
calculate_collisions = _engine.calculate_collisions
calculate_nriv_conflicts = _engine.calculate_nriv_conflicts
calculate_growth = _engine.calculate_growth
calculate_system_profiles = _engine.calculate_system_profiles
run_all = _engine.run_all
detect_collisions = _engine.detect_collisions
detect_conflicts = _engine.detect_conflicts

__all__ = [
    "calculate_sizing",
    "calculate_collisions",
    "calculate_nriv_conflicts",
    "calculate_growth",
    "calculate_system_profiles",
    "run_all",
    "detect_collisions",
    "detect_conflicts",
    "ENGINE_PATH",
]
