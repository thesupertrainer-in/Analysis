"""
DMLT Consolidation — deterministic calculation engine.
=====================================================

This module is the single source of truth for every deterministic calculation
in the solution.  It is intentionally **self-contained**:

  * standard library only — no langchain, no pydantic, no openpyxl, no I/O
  * pure functions — plain ``list[dict]`` in, plain JSON-serialisable ``dict`` out
  * no globals, no caching, no randomness, no clock reads

Because of that, the internals below can be rewritten freely without touching
the CAP backend, the React UI, or the A2A tool wiring.  The only contract that
must hold is the shape of the returned dicts, documented on each function.

Consumers
---------
  * ``app/tools/calc_tools.py``          — thin LangChain ``StructuredTool`` wrappers
  * ``assets/dmlt-excel-generator/``     — collision / conflict detection + sizing

Input sections
--------------
Every extract file has the shape ``{runid, section, data: [...]}``; this module
operates on the ``data`` arrays only.  A run contains rows for several
``sidclnt`` values (SAP system + client, e.g. ``RQ1_500``) that are being
consolidated into one target system.

  master  sidclnt, tabname, bukrs, agg_level, category, clnt_dep,
          clnt_count, clnt_size, tab_total_cnt, tab_total_kb, delv_class
  growth  sidclnt, tabname, gjahr, doc_count
  system  sidclnt, sid, db_sys, rel, sp_level, unicode, addons,
          total_vol, occupied_vol
  org     sidclnt, from_type, from_id, to_type, to_id, from_text
  nriv    sidclnt, object, subobject, nrrangenr, fromnumber, tonumber, nrlevel
"""

from collections import defaultdict

__all__ = [
    "calculate_sizing",
    "calculate_collisions",
    "calculate_nriv_conflicts",
    "calculate_growth",
    "calculate_system_profiles",
    "run_all",
    "detect_collisions",
    "detect_conflicts",
]

#: How many entries the per-system "top tables" lists carry.
TOP_N = 10


# ---------------------------------------------------------------------------
# Coercion helpers — extracts arrive as JSON and are not always well typed
# ---------------------------------------------------------------------------

def _s(value) -> str:
    """Coerce to a stripped string; ``None`` becomes ``''``."""
    return "" if value is None else str(value).strip()


def _i(value) -> int:
    """Coerce to int, tolerating ``None``, floats and numeric strings."""
    if value is None or value == "":
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return 0


def _f(value) -> float:
    """Coerce to float, tolerating ``None`` and numeric strings."""
    if value is None or value == "":
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _norm_text(value) -> str:
    """
    Normalise a descriptive text for *equality comparison only*.

    Collapses internal whitespace and case-folds, so ``"SAP  A.G."`` and
    ``"sap a.g."`` compare equal.  Original spellings are always what gets
    reported back to the caller — this is only used to decide "same or not".
    """
    return " ".join(_s(value).split()).casefold()


# ---------------------------------------------------------------------------
# Rule 1 — Sizing
# ---------------------------------------------------------------------------

def calculate_sizing(master_data: list, system_data: list = None) -> dict:
    """
    Table-volume sizing per source system, plus the consolidated target.

    Only ``agg_level == "T"`` rows are used.  Those are the table-level totals;
    ``agg_level == "C"`` rows are the per-company-code splits of the same
    tables and would double-count if included.

    Returns
    -------
    {
      "calculationType": "SIZING",
      "systems": {
         "<sidclnt>": {
            "total_rows": int, "total_kb": float, "total_mb": float,
            "total_gb": float, "table_count": int,
            "top_tables_by_rows": [{"tabname","tab_total_cnt","tab_total_kb"}],
            "top_tables_by_size": [{"tabname","tab_total_kb","tab_total_cnt"}],
            "categories": {"<category>": {"rows","kb","mb"}},
         }, ...
      },
      "consolidated": {
         "total_rows","total_kb","total_mb","total_gb",
         "distinct_tables": int,
         "per_table": [{"tabname","total_rows","total_kb","system_count"}],
         "categories": {"<category>": {"rows","kb","mb"}},
      },
      "largest_system": {"sidclnt","total_rows","total_kb","share_of_rows_pct"},
      "sidcltns": [str], "categories": [str], "row_count_used": int,
    }
    """
    master_data = master_data or []
    t_rows = [r for r in master_data if _s(r.get("agg_level")).upper() == "T"]

    sys_rows: dict[str, int] = defaultdict(int)
    sys_kb: dict[str, float] = defaultdict(float)
    sys_tables: dict[str, int] = defaultdict(int)
    sys_cat_rows: dict[tuple, int] = defaultdict(int)
    sys_cat_kb: dict[tuple, float] = defaultdict(float)
    sys_table_rows: dict[tuple, int] = defaultdict(int)
    sys_table_kb: dict[tuple, float] = defaultdict(float)

    tbl_rows: dict[str, int] = defaultdict(int)
    tbl_kb: dict[str, float] = defaultdict(float)
    tbl_systems: dict[str, set] = defaultdict(set)

    cat_rows: dict[str, int] = defaultdict(int)
    cat_kb: dict[str, float] = defaultdict(float)

    for row in t_rows:
        sid = _s(row.get("sidclnt"))
        tab = _s(row.get("tabname"))
        cat = _s(row.get("category")) or "UNKNOWN"
        cnt = _i(row.get("tab_total_cnt"))
        kb = _f(row.get("tab_total_kb"))

        sys_rows[sid] += cnt
        sys_kb[sid] += kb
        sys_tables[sid] += 1
        sys_cat_rows[(sid, cat)] += cnt
        sys_cat_kb[(sid, cat)] += kb
        sys_table_rows[(sid, tab)] += cnt
        sys_table_kb[(sid, tab)] += kb

        tbl_rows[tab] += cnt
        tbl_kb[tab] += kb
        tbl_systems[tab].add(sid)

        cat_rows[cat] += cnt
        cat_kb[cat] += kb

    sidcltns = sorted(sys_rows.keys())

    systems: dict[str, dict] = {}
    for sid in sidcltns:
        tables = [
            (tab, sys_table_rows[(s, tab)], sys_table_kb[(s, tab)])
            for (s, tab) in sys_table_rows
            if s == sid
        ]
        # Deterministic tie-break: metric desc, then table name asc.
        by_rows = sorted(tables, key=lambda t: (-t[1], t[0]))[:TOP_N]
        by_size = sorted(tables, key=lambda t: (-t[2], t[0]))[:TOP_N]

        systems[sid] = {
            "total_rows": sys_rows[sid],
            "total_kb": round(sys_kb[sid], 2),
            "total_mb": round(sys_kb[sid] / 1024, 2),
            "total_gb": round(sys_kb[sid] / 1024 / 1024, 2),
            "table_count": sys_tables[sid],
            "top_tables_by_rows": [
                {"tabname": t, "tab_total_cnt": c, "tab_total_kb": round(k, 2)}
                for t, c, k in by_rows
            ],
            "top_tables_by_size": [
                {"tabname": t, "tab_total_kb": round(k, 2), "tab_total_cnt": c}
                for t, c, k in by_size
            ],
            "categories": {
                cat: {
                    "rows": sys_cat_rows[(s, cat)],
                    "kb": round(sys_cat_kb[(s, cat)], 2),
                    "mb": round(sys_cat_kb[(s, cat)] / 1024, 2),
                }
                for (s, cat) in sorted(sys_cat_kb)
                if s == sid
            },
        }

    total_rows = sum(sys_rows.values())
    total_kb = sum(sys_kb.values())

    per_table = sorted(
        (
            {
                "tabname": tab,
                "total_rows": tbl_rows[tab],
                "total_kb": round(tbl_kb[tab], 2),
                "system_count": len(tbl_systems[tab]),
            }
            for tab in tbl_rows
        ),
        key=lambda d: (-d["total_kb"], d["tabname"]),
    )

    largest = None
    if sidcltns:
        # Largest by row count; table name-free tie-break on sidclnt for determinism.
        top_sid = sorted(sidcltns, key=lambda s: (-sys_rows[s], s))[0]
        largest = {
            "sidclnt": top_sid,
            "total_rows": sys_rows[top_sid],
            "total_kb": round(sys_kb[top_sid], 2),
            "share_of_rows_pct": (
                round(sys_rows[top_sid] / total_rows * 100, 2) if total_rows else 0.0
            ),
        }

    return {
        "calculationType": "SIZING",
        "systems": systems,
        "consolidated": {
            "total_rows": total_rows,
            "total_kb": round(total_kb, 2),
            "total_mb": round(total_kb / 1024, 2),
            "total_gb": round(total_kb / 1024 / 1024, 2),
            "distinct_tables": len(tbl_rows),
            "per_table": per_table,
            "categories": {
                cat: {
                    "rows": cat_rows[cat],
                    "kb": round(cat_kb[cat], 2),
                    "mb": round(cat_kb[cat] / 1024, 2),
                }
                for cat in sorted(cat_kb)
            },
        },
        "largest_system": largest,
        "sidcltns": sidcltns,
        "categories": sorted(cat_kb),
        "row_count_used": len(t_rows),
    }


# ---------------------------------------------------------------------------
# Rule 2 — Company-code collisions
# ---------------------------------------------------------------------------

def calculate_collisions(org_data: list) -> dict:
    """
    Company-code (BUKRS) collisions across the source systems.

    Scope is ``from_type == "BUKRS"`` **and** ``to_type == "CLIENT"``.  That
    edge is the one that carries the company-code master text; the BUKRS→COA
    and BUKRS→CTRLAREA edges repeat the same code with unrelated texts and
    would produce phantom collisions.

    Grouped by ``from_id``.  A code is a **collision** when it exists in more
    than one ``sidclnt`` under more than one distinct ``from_text`` — the same
    number means different legal entities, so it must be renumbered before the
    merge.  Same code + same text in several systems is a **safe duplicate**.

    Texts are compared case- and whitespace-insensitively; blank texts are not
    counted as a distinct meaning (they are missing data, not a different
    entity) and are reported separately via ``codes_missing_text``.

    Returns
    -------
    {
      "calculationType": "COMPANY_CODE_COLLISIONS",
      "collisions": [{"from_id", "systems":[{"sidclnt","from_text"}],
                      "distinct_texts":[str], "system_count": int}],
      "safe_duplicates": [{"from_id","from_text","sidcltns":[str]}],
      "total_bukrs_count": int, "collision_count": int,
      "safe_duplicate_count": int, "codes_missing_text": [str],
      "sidcltns": [str],
    }
    """
    org_data = org_data or []

    rows = [
        r for r in org_data
        if _s(r.get("from_type")).upper() == "BUKRS"
        and _s(r.get("to_type")).upper() == "CLIENT"
    ]

    # from_id -> sidclnt -> from_text  (first non-blank text per system wins)
    code_map: dict[str, dict[str, str]] = defaultdict(dict)
    for r in rows:
        code = _s(r.get("from_id"))
        sid = _s(r.get("sidclnt"))
        txt = _s(r.get("from_text"))
        if not code or not sid:
            continue
        if sid not in code_map[code] or (txt and not code_map[code][sid]):
            code_map[code][sid] = txt

    collisions: list[dict] = []
    safe_duplicates: list[dict] = []
    missing_text: list[str] = []
    all_sids: set = set()

    for code in sorted(code_map):
        smap = code_map[code]
        all_sids.update(smap)

        if any(not t for t in smap.values()):
            missing_text.append(code)

        if len(smap) < 2:
            continue

        distinct = sorted({_norm_text(t) for t in smap.values() if _s(t)})

        if len(distinct) > 1:
            collisions.append({
                "from_id": code,
                "systems": [
                    {"sidclnt": sid, "from_text": smap[sid]}
                    for sid in sorted(smap)
                ],
                "distinct_texts": sorted(
                    {_s(t) for t in smap.values() if _s(t)}
                ),
                "system_count": len(smap),
            })
        else:
            sample = next((_s(t) for t in smap.values() if _s(t)), "")
            safe_duplicates.append({
                "from_id": code,
                "from_text": sample,
                "sidcltns": sorted(smap),
            })

    return {
        "calculationType": "COMPANY_CODE_COLLISIONS",
        "collisions": collisions,
        "safe_duplicates": safe_duplicates,
        "total_bukrs_count": len(code_map),
        "collision_count": len(collisions),
        "safe_duplicate_count": len(safe_duplicates),
        "codes_missing_text": missing_text,
        "sidcltns": sorted(all_sids),
    }


# ---------------------------------------------------------------------------
# Rule 3 — Number-range conflicts
# ---------------------------------------------------------------------------

def _as_number(value):
    """
    Return ``int(value)`` for a purely numeric interval bound, else ``None``.

    SAP number ranges may be alphanumeric (``ZZZZZZZZZZ``).  Those cannot be
    compared arithmetically, so overlap is left undecided for them rather than
    guessed at.
    """
    text = _s(value)
    if text.isdigit():
        return int(text)
    return None


def _ranges_overlap(a_from, a_to, b_from, b_to):
    """
    ``True``/``False`` when both intervals are numeric, ``None`` when at least
    one bound is alphanumeric and no arithmetic comparison is possible.
    """
    a0, a1 = _as_number(a_from), _as_number(a_to)
    b0, b1 = _as_number(b_from), _as_number(b_to)
    if None in (a0, a1, b0, b1):
        return None
    return a0 <= b1 and b0 <= a1


def calculate_nriv_conflicts(nriv_data: list) -> dict:
    """
    Number-range interval conflicts across the source systems.

    Grouped by ``object + nrrangenr``.  A group is a conflict when it appears
    in more than one ``sidclnt`` **and** either

      * ``nrlevel`` (the current number pointer) differs between systems, or
      * the ``fromnumber``–``tonumber`` intervals overlap
        (``[a,b]`` and ``[c,d]`` overlap iff ``a <= d and c <= b``).

    Merely existing in several systems is not a conflict — identical intervals
    at an identical level merge cleanly.

    Conflict ``type`` is ``LEVEL_MISMATCH``, ``RANGE_OVERLAP`` or ``BOTH``.

    Returns
    -------
    {
      "calculationType": "NUMBER_RANGE_CONFLICTS",
      "conflicts": [{"object","nrrangenr","type",
                     "systems":[{"sidclnt","fromnumber","tonumber","nrlevel"}]}],
      "total_objects": int, "total_intervals": int, "conflict_count": int,
      "level_mismatch_count": int, "range_overlap_count": int, "both_count": int,
      "non_numeric_ranges": int, "sidcltns": [str],
    }
    """
    nriv_data = nriv_data or []

    key_map: dict[tuple, dict[str, dict]] = defaultdict(dict)
    all_sids: set = set()
    non_numeric = 0

    for r in nriv_data:
        obj = _s(r.get("object"))
        rng = _s(r.get("nrrangenr"))
        sid = _s(r.get("sidclnt"))
        if not sid:
            continue
        all_sids.add(sid)
        if _as_number(r.get("fromnumber")) is None or _as_number(r.get("tonumber")) is None:
            non_numeric += 1
        # First row per (object, range, system) is representative.
        key_map[(obj, rng)].setdefault(sid, r)

    conflicts: list[dict] = []
    for (obj, rng) in sorted(key_map):
        reps = key_map[(obj, rng)]
        if len(reps) < 2:
            continue

        sids = sorted(reps)

        # -- level mismatch: compare numerically when possible, else textually
        levels = set()
        for sid in sids:
            raw = _s(reps[sid].get("nrlevel"))
            levels.add(_i(raw) if raw.isdigit() else raw)
        level_mismatch = len(levels) > 1

        # -- range overlap: all distinct system pairs
        range_overlap = False
        for i, a_sid in enumerate(sids):
            a = reps[a_sid]
            for b_sid in sids[i + 1:]:
                b = reps[b_sid]
                if _ranges_overlap(
                    a.get("fromnumber"), a.get("tonumber"),
                    b.get("fromnumber"), b.get("tonumber"),
                ) is True:
                    range_overlap = True
                    break
            if range_overlap:
                break

        if not (level_mismatch or range_overlap):
            continue

        if level_mismatch and range_overlap:
            ctype = "BOTH"
        elif level_mismatch:
            ctype = "LEVEL_MISMATCH"
        else:
            ctype = "RANGE_OVERLAP"

        conflicts.append({
            "object": obj,
            "nrrangenr": rng,
            "type": ctype,
            "systems": [
                {
                    "sidclnt": sid,
                    "fromnumber": _s(reps[sid].get("fromnumber")),
                    "tonumber": _s(reps[sid].get("tonumber")),
                    "nrlevel": _s(reps[sid].get("nrlevel")),
                }
                for sid in sids
            ],
        })

    by_type = defaultdict(int)
    for c in conflicts:
        by_type[c["type"]] += 1

    return {
        "calculationType": "NUMBER_RANGE_CONFLICTS",
        "conflicts": conflicts,
        "total_objects": len({obj for obj, _ in key_map}),
        "total_intervals": len(nriv_data),
        "conflict_count": len(conflicts),
        "level_mismatch_count": by_type["LEVEL_MISMATCH"],
        "range_overlap_count": by_type["RANGE_OVERLAP"],
        "both_count": by_type["BOTH"],
        "non_numeric_ranges": non_numeric,
        "sidcltns": sorted(all_sids),
    }


# ---------------------------------------------------------------------------
# Rule 4 — Growth
# ---------------------------------------------------------------------------

def calculate_growth(growth_data: list) -> dict:
    """
    Document growth per table per fiscal year, summed across all systems.

    Rows with ``gjahr == 0`` are excluded — that is the extractor's "no fiscal
    year assigned" bucket, not a real year, and it would distort both the
    year axis and the year-on-year rates.

    Returns
    -------
    {
      "calculationType": "GROWTH",
      "years": [int],
      "tables": [{"tabname",
                  "by_year": {"<year>": int},
                  "total_docs": int,
                  "first_year": int, "last_year": int,
                  "yoy": [{"from_year","to_year","from_count","to_count","growth_pct"}],
                  "missing_years": [int]}],
      "by_system": {"<sidclnt>": {"<tabname>": {"<year>": int}}},
      "year_totals": {"<year>": int},
      "total_docs": int, "excluded_zero_year_rows": int,
      "sidcltns": [str], "tabnames": [str],
    }
    """
    growth_data = growth_data or []

    table_year: dict[str, dict[int, int]] = defaultdict(lambda: defaultdict(int))
    sys_table_year: dict[str, dict[str, dict[int, int]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(int))
    )
    year_totals: dict[int, int] = defaultdict(int)
    all_sids: set = set()
    excluded = 0

    for r in growth_data:
        year = _i(r.get("gjahr"))
        if year == 0:                      # excluded by rule
            excluded += 1
            continue
        tab = _s(r.get("tabname"))
        sid = _s(r.get("sidclnt"))
        cnt = _i(r.get("doc_count"))

        all_sids.add(sid)
        table_year[tab][year] += cnt       # summed across systems
        sys_table_year[sid][tab][year] += cnt
        year_totals[year] += cnt

    tables: list[dict] = []
    for tab in sorted(table_year):
        years = sorted(table_year[tab])
        counts = table_year[tab]

        yoy: list[dict] = []
        for i in range(1, len(years)):
            prev_y, curr_y = years[i - 1], years[i]
            prev_c, curr_c = counts[prev_y], counts[curr_y]
            yoy.append({
                "from_year": prev_y,
                "to_year": curr_y,
                "from_count": prev_c,
                "to_count": curr_c,
                "growth_pct": (
                    round((curr_c - prev_c) / prev_c * 100, 2) if prev_c else None
                ),
            })

        missing = (
            [y for y in range(years[0], years[-1] + 1) if y not in counts]
            if years else []
        )

        tables.append({
            "tabname": tab,
            "by_year": {str(y): counts[y] for y in years},
            "total_docs": sum(counts.values()),
            "first_year": years[0] if years else None,
            "last_year": years[-1] if years else None,
            "yoy": yoy,
            "missing_years": missing,
        })

    return {
        "calculationType": "GROWTH",
        "years": sorted(year_totals),
        "tables": tables,
        "by_system": {
            sid: {
                tab: {str(y): c for y, c in sorted(years.items())}
                for tab, years in sorted(sys_table_year[sid].items())
            }
            for sid in sorted(sys_table_year)
        },
        "year_totals": {str(y): year_totals[y] for y in sorted(year_totals)},
        "total_docs": sum(year_totals.values()),
        "excluded_zero_year_rows": excluded,
        "sidcltns": sorted(all_sids),
        "tabnames": sorted(table_year),
    }


# ---------------------------------------------------------------------------
# Rule 5 — System profiles
# ---------------------------------------------------------------------------

def calculate_system_profiles(system_data: list, master_data: list = None) -> dict:
    """
    Technical profile per system: database, release, support-package, unicode.

    ``master_data`` is optional; when supplied, each profile also carries the
    table volume measured for that system (``agg_level == "T"`` rows only).

    Heterogeneity flags name the dimensions on which the landscape is not
    uniform — each is a distinct piece of consolidation work.

    Returns
    -------
    {
      "calculationType": "SYSTEM_PROFILES",
      "systems": [{"sidclnt","sid","db_sys","rel","sp_level","unicode",
                   "is_unicode","addons","addon_count",
                   "total_vol","occupied_vol","utilisation_pct",
                   "data_kb","data_mb"}],
      "distinct": {"db_sys":[...], "rel":[...], "sp_level":[...], "unicode":[...]},
      "heterogeneity_flags": [str],
      "utilisation": {"<sidclnt>": float},
      "system_count": int, "sidcltns": [str],
    }
    """
    system_data = system_data or []
    master_data = master_data or []

    data_kb: dict[str, float] = defaultdict(float)
    for r in master_data:
        if _s(r.get("agg_level")).upper() == "T":
            data_kb[_s(r.get("sidclnt"))] += _f(r.get("tab_total_kb"))

    profiles: list[dict] = []
    for r in sorted(system_data, key=lambda x: _s(x.get("sidclnt"))):
        sid = _s(r.get("sidclnt"))
        total_vol = _f(r.get("total_vol"))
        occupied = _f(r.get("occupied_vol"))
        addons = [a for a in (_s(r.get("addons")).split(",")) if a]

        profiles.append({
            "sidclnt": sid,
            "sid": _s(r.get("sid")),
            "db_sys": _s(r.get("db_sys")),
            "rel": _s(r.get("rel")),
            "sp_level": _s(r.get("sp_level")),
            "unicode": _s(r.get("unicode")),
            "is_unicode": _s(r.get("unicode")).upper() == "X",
            "addons": addons,
            "addon_count": len(addons),
            "total_vol": total_vol,
            "occupied_vol": occupied,
            "utilisation_pct": (
                round(occupied / total_vol * 100, 2) if total_vol else None
            ),
            "data_kb": round(data_kb.get(sid, 0.0), 2),
            "data_mb": round(data_kb.get(sid, 0.0) / 1024, 2),
        })

    distinct = {
        "db_sys": sorted({p["db_sys"] for p in profiles}),
        "rel": sorted({p["rel"] for p in profiles}),
        "sp_level": sorted({p["sp_level"] for p in profiles}),
        "unicode": sorted({p["unicode"] for p in profiles}),
    }

    flags: list[str] = []
    if len(distinct["db_sys"]) > 1:
        flags.append("MIXED_DATABASES")
    if len(distinct["rel"]) > 1:
        flags.append("MIXED_RELEASES")
    if len(distinct["sp_level"]) > 1:
        flags.append("MIXED_SP_LEVELS")
    if len({p["is_unicode"] for p in profiles}) > 1:
        flags.append("MIXED_UNICODE")

    return {
        "calculationType": "SYSTEM_PROFILES",
        "systems": profiles,
        "distinct": distinct,
        "heterogeneity_flags": flags,
        "utilisation": {
            p["sidclnt"]: p["utilisation_pct"]
            for p in profiles
            if p["utilisation_pct"] is not None
        },
        "system_count": len(profiles),
        "sidcltns": [p["sidclnt"] for p in profiles],
    }


# ---------------------------------------------------------------------------
# Convenience entry point
# ---------------------------------------------------------------------------

def run_all(sections: dict) -> dict:
    """
    Run all five rules over a ``{master, growth, system, org, nriv}`` mapping.

    Missing sections are treated as empty lists so a partial payload still
    produces a well-formed result rather than raising.
    """
    sections = sections or {}
    master = sections.get("master") or []
    growth = sections.get("growth") or []
    system = sections.get("system") or []
    org = sections.get("org") or []
    nriv = sections.get("nriv") or []

    return {
        "sizing": calculate_sizing(master, system),
        "collisions": calculate_collisions(org),
        "conflicts": calculate_nriv_conflicts(nriv),
        "growth": calculate_growth(growth),
        "system_profiles": calculate_system_profiles(system, master),
    }


# ---------------------------------------------------------------------------
# Back-compat aliases used by the Excel generator sheets
# ---------------------------------------------------------------------------

def detect_collisions(org_data: list) -> list:
    """
    Collision list in the shape the Excel sheets consume:
    ``[{"bukrs", "systems": [{"sidclnt", "name"}]}]``, sorted by code.
    """
    return [
        {
            "bukrs": c["from_id"],
            "systems": [
                {"sidclnt": s["sidclnt"], "name": s["from_text"]}
                for s in c["systems"]
            ],
        }
        for c in calculate_collisions(org_data)["collisions"]
    ]


def detect_conflicts(nriv_data: list) -> list:
    """
    Conflict list in the shape the Excel sheets consume:
    ``[{"object", "nrrangenr", "type", "systems": [...]}]``.
    """
    return calculate_nriv_conflicts(nriv_data)["conflicts"]
