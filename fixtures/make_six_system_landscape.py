"""
Generate a synthetic 6-system DMLT extract set.
==============================================

Why this exists
---------------
The extracts shipped in ``extractor_files/`` are a **2-system** consolidation
(``ECQ_300`` + ``RQ1_500``).  Validating the "any number of systems" requirement
— and the specific scenario of company code 1000 colliding across three systems
— needs a landscape that the real extract does not contain.

This script writes a deterministic, clearly-synthetic 6-system extract set in
exactly the shape the CAP backend and the agent consume:
``{runid, section, data: [...]}``.

It is **test data only**.  Nothing here is derived from a customer system.

Usage
-----
    python make_six_system_landscape.py [--out DIR]

Guaranteed properties of the generated set
------------------------------------------
  * 6 systems: S01_100 … S06_100
  * company code 1000 present in S01/S02/S03 under three different entity
    names  -> exactly one collision
  * company code 2000 present in four systems under one name -> safe duplicate
  * several number-range keys overlapping and/or at differing levels
    -> multiple conflicts, covering LEVEL_MISMATCH, RANGE_OVERLAP and BOTH
  * S03_100 holds roughly two thirds of all rows -> a dominant largest system
  * one growth row per table per year carries gjahr 0, which the engine drops
"""

import argparse
import json
import os

RUNID = "SYNTH_6SYS"

SYSTEMS = ["S01_100", "S02_100", "S03_100", "S04_100", "S05_100", "S06_100"]

#: Relative table-volume weight per system.  S03 dominates deliberately.
WEIGHTS = {
    "S01_100": 1.0,
    "S02_100": 1.6,
    "S03_100": 22.0,
    "S04_100": 0.8,
    "S05_100": 1.2,
    "S06_100": 0.5,
}

CATEGORIES = ["APPL", "CUST", "CONF", "SYST"]

TABLES = [
    ("ACDOCA", "APPL", "A"), ("BSEG", "APPL", "A"), ("BKPF", "APPL", "A"),
    ("MSEG", "APPL", "A"), ("VBAK", "APPL", "A"), ("VBAP", "APPL", "A"),
    ("LIPS", "APPL", "A"), ("EKPO", "APPL", "A"), ("COEP", "APPL", "A"),
    ("MARA", "CUST", "A"), ("MARC", "CUST", "A"), ("KNA1", "CUST", "A"),
    ("LFA1", "CUST", "A"), ("T001", "CONF", "C"), ("T001W", "CONF", "C"),
    ("TCURR", "CONF", "C"), ("D010TAB", "SYST", "S"), ("REPOSRC", "SYST", "S"),
    ("DYNPSOURCE", "SYST", "S"), ("SOFFCONT1", "SYST", "S"),
]

GROWTH_TABLES = ["ACDOCA", "BSEG", "BKPF", "MSEG", "VBAK"]
YEARS = list(range(2015, 2027))


def _master() -> list:
    rows = []
    for sid in SYSTEMS:
        w = WEIGHTS[sid]
        for idx, (tab, cat, delv) in enumerate(TABLES):
            # Deterministic pseudo-volume — no RNG, so reruns are identical.
            base_rows = (idx + 1) * 137_000
            cnt = int(base_rows * w)
            kb = int(cnt * (0.35 + (idx % 5) * 0.11))
            rows.append({
                "runid": RUNID, "sidclnt": sid, "tabname": tab, "bukrs": "",
                "agg_level": "T", "delv_class": delv, "tabclass": "TRANSP",
                "modname": "FI", "component": "FI", "category": cat,
                "clnt_dep": "X", "clnt_count": cnt, "clnt_size": kb,
                "tab_total_cnt": cnt, "tab_total_kb": kb,
            })
            # A company-code split of the same table. agg_level "C" rows must be
            # ignored by the sizing rule; they are here to prove that.
            rows.append({
                "runid": RUNID, "sidclnt": sid, "tabname": tab, "bukrs": "1000",
                "agg_level": "C", "delv_class": delv, "tabclass": "TRANSP",
                "modname": "FI", "component": "FI", "category": cat,
                "clnt_dep": "X", "clnt_count": cnt // 2, "clnt_size": kb // 2,
                "tab_total_cnt": cnt // 2, "tab_total_kb": kb // 2,
            })
    return rows


def _growth() -> list:
    rows = []
    for sid in SYSTEMS:
        w = WEIGHTS[sid]
        for t_idx, tab in enumerate(GROWTH_TABLES):
            for y_idx, year in enumerate(YEARS):
                rows.append({
                    "runid": RUNID, "sidclnt": sid, "tabname": tab,
                    "gjahr": year,
                    "doc_count": int((t_idx + 1) * (y_idx + 1) * 90_000 * w),
                })
            # gjahr 0 = the extractor's "no fiscal year" bucket. The engine
            # must exclude these rows.
            rows.append({
                "runid": RUNID, "sidclnt": sid, "tabname": tab,
                "gjahr": 0, "doc_count": 7_777_777,
            })
    return rows


def _system() -> list:
    profiles = [
        ("S01_100", "S01", "HDB",    "755", "0012", "X"),
        ("S02_100", "S02", "HDB",    "755", "0012", "X"),
        ("S03_100", "S03", "HDB",    "108", "0003", "X"),
        ("S04_100", "S04", "ORACLE", "731", "0018", "X"),
        ("S05_100", "S05", "SYBASE", "617", "0026", "X"),
        ("S06_100", "S06", "MSSQL",  "617", "0026", ""),   # non-unicode
    ]
    rows = []
    for sid, sap_sid, db, rel, sp, uni in profiles:
        occupied = int(400_000 * WEIGHTS[sid])
        rows.append({
            "runid": RUNID, "sidclnt": sid, "sid": sap_sid, "db_sys": db,
            "rel": rel, "sp_level": sp, "kernel": "753", "unicode": uni,
            "addons": "LOCAL,HOME,SAP_BASIS",
            "total_vol": int(occupied / 0.72),
            "occupied_vol": occupied,
            "db_size": occupied, "size_tables": int(occupied * 0.6),
            "size_indexes": int(occupied * 0.3), "size_other": int(occupied * 0.1),
        })
    return rows


def _org() -> list:
    """
    Company-code structure.

    1000 -> three systems, three different entity names  => 1 collision
    2000 -> four systems, one shared name                => safe duplicate
    30xx -> unique per system                            => neither
    """
    rows = []

    collision_names = {
        "S01_100": "Acme Manufacturing GmbH",
        "S02_100": "Acme Retail Ltd",
        "S03_100": "Acme Logistics S.A.",
    }
    for sid, name in collision_names.items():
        rows.append({
            "runid": RUNID, "sidclnt": sid, "from_type": "BUKRS",
            "from_id": "1000", "to_type": "CLIENT", "to_id": "100",
            "from_text": name, "to_text": "", "ktopl": "INT",
            "periv": "K4", "waers": "EUR", "land1": "DE",
        })

    for sid in ["S01_100", "S02_100", "S04_100", "S05_100"]:
        rows.append({
            "runid": RUNID, "sidclnt": sid, "from_type": "BUKRS",
            "from_id": "2000", "to_type": "CLIENT", "to_id": "100",
            "from_text": "Global Shared Services BV", "to_text": "",
            "ktopl": "INT", "periv": "K4", "waers": "EUR", "land1": "NL",
        })

    for i, sid in enumerate(SYSTEMS, start=1):
        rows.append({
            "runid": RUNID, "sidclnt": sid, "from_type": "BUKRS",
            "from_id": f"30{i:02d}", "to_type": "CLIENT", "to_id": "100",
            "from_text": f"Local Entity {i:02d} Ltd", "to_text": "",
            "ktopl": "INT", "periv": "K4", "waers": "EUR", "land1": "GB",
        })
        # Non-CLIENT edges reuse code 1000 with unrelated text — the rule must
        # ignore these rather than count them as further collisions.
        rows.append({
            "runid": RUNID, "sidclnt": sid, "from_type": "BUKRS",
            "from_id": "1000", "to_type": "COA", "to_id": "INT",
            "from_text": "Chart of accounts assignment", "to_text": "",
            "ktopl": "INT", "periv": "", "waers": "", "land1": "",
        })
        rows.append({
            "runid": RUNID, "sidclnt": sid, "from_type": "PLANT",
            "from_id": "1000", "to_type": "BUKRS", "to_id": "1000",
            "from_text": f"Plant {i:02d}", "to_text": "", "ktopl": "",
            "periv": "", "waers": "", "land1": "",
        })
    return rows


def _nriv() -> list:
    """
    Number ranges designed to exercise every conflict type.

      RF_BELEG/01   identical interval in all 6 systems, differing levels -> BOTH
      MATBELEG/01   overlapping intervals, identical levels         -> RANGE_OVERLAP
      DEBITOR/01    disjoint intervals, differing levels            -> LEVEL_MISMATCH
      KREDITOR/01   disjoint intervals, identical levels            -> no conflict
      SOLO_OBJ/01   present in one system only                      -> no conflict
      ALPHA_OBJ/01  alphanumeric upper bound                        -> not comparable
    """
    rows = []

    def add(sid, obj, rng, frm, to, lvl):
        rows.append({
            "runid": RUNID, "sidclnt": sid, "object": obj, "subobject": "",
            "nrrangenr": rng, "fromnumber": frm, "tonumber": to,
            "nrlevel": lvl, "externind": "", "object_text": obj,
        })

    for i, sid in enumerate(SYSTEMS):
        # BOTH — same interval everywhere, each system at a different level
        add(sid, "RF_BELEG", "01", "0100000000", "0199999999",
            f"{(i + 1) * 1000:020d}")

        # RANGE_OVERLAP — staggered but overlapping windows, same level
        start = 200_000_000 + i * 5_000_000
        add(sid, "MATBELEG", "01", f"{start:010d}", f"{start + 20_000_000:010d}",
            f"{0:020d}")

        # LEVEL_MISMATCH — cleanly separated windows, differing levels
        d_start = 400_000_000 + i * 10_000_000
        add(sid, "DEBITOR", "01", f"{d_start:010d}", f"{d_start + 9_999_999:010d}",
            f"{(i + 1) * 55:020d}")

        # clean — separated windows, identical level
        k_start = 600_000_000 + i * 10_000_000
        add(sid, "KREDITOR", "01", f"{k_start:010d}",
            f"{k_start + 9_999_999:010d}", f"{0:020d}")

        # alphanumeric bound — cannot be compared arithmetically
        add(sid, "ALPHA_OBJ", "01", "0000000001", "ZZZZZZZZZZ", f"{0:020d}")

    # single-system object
    add("S04_100", "SOLO_OBJ", "01", "0000000001", "0000999999", f"{42:020d}")
    return rows


SECTIONS = {
    "master": _master,
    "growth": _growth,
    "system": _system,
    "org": _org,
    "nriv": _nriv,
}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__),
                                                  "six_system"),
                    help="Output directory (default: ./six_system)")
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    for name, builder in SECTIONS.items():
        data = builder()
        path = os.path.join(args.out, f"{name}.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"runid": RUNID, "section": name, "data": data}, fh, indent=1)
        print(f"  {name:8} {len(data):>6,} rows -> {path}")

    print(f"\nWrote synthetic {len(SYSTEMS)}-system landscape to {args.out}")


if __name__ == "__main__":
    main()
