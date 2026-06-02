"""openclawer core — deterministic clean/cross-check/update engine.

Platform-agnostic, stdlib-only. The search/fan-out step is NOT here (it's
platform-specific); this engine takes a `provenance.csv` and produces the clean
table, conflicts, and idempotent update diffs.

Data root: $OPENCLAWER_ROOT or ~/data-pipeline ; per-topic dir <root>/<topic>/.
INVERTED tier scale: 1 = most credible … 5 = least (see tierlib).
"""
import csv
import glob
import os
import re
from collections import defaultdict

DEFAULT_ROOT = os.path.expanduser(os.environ.get("OPENCLAWER_ROOT", "~/data-pipeline"))

CELL_KEYS = ["subject", "field", "variant", "scope", "kind"]
TARGET_KINDS = {"目标", "规划", "在建", "target", "plan"}

CLEAN_COLS = ["subject", "field", "variant", "scope", "kind", "data_year",
              "value", "value_num", "unit", "chosen_source", "chosen_tier",
              "n_sources", "n_years", "status"]
CONFLICT_COLS = ["subject", "field", "variant", "scope", "kind", "data_year",
                 "value_a", "source_a", "tier_a",
                 "value_b", "source_b", "tier_b", "pct_diff"]
UPDATE_KEY = ("subject", "field", "variant", "scope", "kind")


def topic_dir(topic, root=None):
    return os.path.join(root or DEFAULT_ROOT, topic)


# ---------- helpers ----------
def to_float(s):
    try:
        return float(str(s).replace(",", "").strip())
    except (ValueError, AttributeError):
        return None


def to_int(s, default=0):
    try:
        return int(float(s))
    except (ValueError, TypeError):
        return default


def tier_rank(r):
    """Inverted scale: 1 = most credible. Blank/0 = least credible (99)."""
    t = to_int(r.get("tier"), 0)
    return t if t > 0 else 99


def disagrees(a, b, tol):
    fa, fb = to_float(a), to_float(b)
    if fa is not None and fb is not None:
        base = max(abs(fa), abs(fb))
        return (fa != fb) if base == 0 else abs(fa - fb) / base > tol
    return str(a).strip() != str(b).strip()


def pct_diff(a, b):
    fa, fb = to_float(a), to_float(b)
    if fa is None or fb is None:
        return ""
    base = max(abs(fa), abs(fb))
    return "0.0" if base == 0 else f"{abs(fa - fb) / base * 100:.1f}"


def pick(recs):
    """Most credible (lowest tier number), then latest fetched_date."""
    latest_first = sorted(recs, key=lambda r: r.get("fetched_date", ""), reverse=True)
    return min(latest_first, key=tier_rank)


# ---------- cross-check ----------
def crosscheck(topic, root=None, tolerance=0.05):
    tdir = topic_dir(topic, root)
    prov_path = os.path.join(tdir, "provenance.csv")
    if not os.path.exists(prov_path):
        raise SystemExit(f"no provenance.csv at {prov_path}")
    with open(prov_path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    cells = defaultdict(list)
    for r in rows:
        cells[tuple(r.get(k, "") for k in CELL_KEYS)].append(r)

    clean_rows, conflict_rows = [], []
    for key, recs in sorted(cells.items()):
        subject, field, variant, scope, kind = key
        years = sorted({r.get("data_year", "") for r in recs})
        latest_year = years[-1]
        latest_recs = [r for r in recs if r.get("data_year", "") == latest_year]
        chosen = pick(latest_recs)

        disagreeing = False
        seen_pairs = set()
        for i, a in enumerate(latest_recs):
            for b in latest_recs[i + 1:]:
                if a["source"] == b["source"]:
                    continue
                if disagrees(a["value"], b["value"], tolerance):
                    disagreeing = True
                    pair = tuple(sorted([a["source"], b["source"]]))
                    if pair in seen_pairs:
                        continue
                    seen_pairs.add(pair)
                    hi, lo = (a, b) if tier_rank(a) <= tier_rank(b) else (b, a)
                    conflict_rows.append({
                        "subject": subject, "field": field, "variant": variant,
                        "scope": scope, "kind": kind, "data_year": latest_year,
                        "value_a": hi["value"], "source_a": hi["source"], "tier_a": to_int(hi.get("tier")),
                        "value_b": lo["value"], "source_b": lo["source"], "tier_b": to_int(lo.get("tier")),
                        "pct_diff": pct_diff(hi["value"], lo["value"]),
                    })

        n_latest = len({r["source"] for r in latest_recs})
        status = ("target" if kind in TARGET_KINDS else
                  "conflict" if disagreeing else
                  "verified" if n_latest >= 2 else "unverified")
        clean_rows.append({
            "subject": subject, "field": field, "variant": variant,
            "scope": scope, "kind": kind, "data_year": latest_year,
            "value": chosen["value"], "value_num": chosen.get("value_num", ""),
            "unit": chosen.get("unit", ""),
            "chosen_source": chosen["source"], "chosen_tier": to_int(chosen.get("tier")),
            "n_sources": len({r["source"] for r in recs}),
            "n_years": len(years), "status": status,
        })

    clean_dir = os.path.join(tdir, "clean")
    cc_dir = os.path.join(tdir, "crosscheck")
    os.makedirs(clean_dir, exist_ok=True)
    os.makedirs(cc_dir, exist_ok=True)
    clean_path = os.path.join(clean_dir, f"{topic}.csv")
    conflicts_path = os.path.join(cc_dir, "conflicts.csv")
    _write(clean_path, CLEAN_COLS, clean_rows)
    _write(conflicts_path, CONFLICT_COLS, conflict_rows)
    return {"clean": clean_path, "conflicts": conflicts_path,
            "n_cells": len(clean_rows), "n_conflicts": len(conflict_rows),
            "conflict_rows": conflict_rows, "clean_rows": clean_rows}


# ---------- update ----------
def _keylabel(k):
    return " / ".join(p for p in k if p and p != "-")


def _load_keyed(path):
    if not os.path.exists(path):
        return {}
    with open(path, newline="", encoding="utf-8-sig") as f:
        return {tuple(r.get(c, "") for c in UPDATE_KEY): r for r in csv.DictReader(f)}


def _latest_snapshot(clean_dir, topic):
    pat = re.compile(rf"^{re.escape(topic)}_(\d{{4}}-\d{{2}}-\d{{2}})\.csv$")
    dated = [(m.group(1), p) for p in glob.glob(os.path.join(clean_dir, f"{topic}_*.csv"))
             if (m := pat.match(os.path.basename(p)))]
    return max(dated)[1] if dated else None


def update(topic, date, root=None):
    tdir = topic_dir(topic, root)
    clean_dir = os.path.join(tdir, "clean")
    current_path = os.path.join(clean_dir, f"{topic}.csv")
    if not os.path.exists(current_path):
        raise SystemExit(f"no clean table at {current_path}; run crosscheck first")

    current = _load_keyed(current_path)
    prev_path = _latest_snapshot(clean_dir, topic)
    prev = _load_keyed(prev_path) if prev_path else {}

    added, changed, removed = [], [], []
    for k, row in current.items():
        if k not in prev:
            added.append((k, row))
        elif row.get("value") != prev[k].get("value"):
            changed.append((k, prev[k], row))
    for k, row in prev.items():
        if k not in current:
            removed.append((k, row))

    lines = [f"\n## {date}\n"]
    if not (added or changed or removed):
        lines.append("- no changes\n")
    for k, row in added:
        lines.append(f"- ADD {_keylabel(k)}: {row.get('value')} "
                     f"({row.get('chosen_source')}, t{row.get('chosen_tier')}, {row.get('status')})\n")
    for k, old, new in changed:
        lines.append(f"- CHG {_keylabel(k)}: {old.get('value')} -> {new.get('value')} "
                     f"({new.get('chosen_source')}, t{new.get('chosen_tier')}, {new.get('status')})\n")
    for k, row in removed:
        lines.append(f"- DEL {_keylabel(k)}: was {row.get('value')}\n")

    changelog = os.path.join(tdir, "CHANGELOG.md")
    with open(changelog, "a", encoding="utf-8-sig") as f:
        f.writelines(lines)
    snapshot = os.path.join(clean_dir, f"{topic}_{date}.csv")
    with open(current_path, newline="", encoding="utf-8-sig") as src, \
         open(snapshot, "w", newline="", encoding="utf-8-sig") as dst:
        dst.write(src.read())
    return {"prev": prev_path, "added": len(added), "changed": len(changed),
            "removed": len(removed), "changelog": changelog, "snapshot": snapshot}


def _write(path, cols, rows):
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
