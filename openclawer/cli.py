"""openclawer CLI — deterministic clean / cross-check / update.

  openclawer init       --topic X [--root DIR]
  openclawer tier-assign --topic X [--root DIR]      # fill blank `tier` in provenance.csv
  openclawer crosscheck --topic X [--tolerance 0.05] [--root DIR]
  openclawer update     --topic X --date YYYY-MM-DD  [--root DIR]
  openclawer tier       --source "..." [--url "..."] [--topic X]   # one-off lookup

Search/fan-out is platform-specific and intentionally NOT part of this CLI: feed
your platform's web-search results into <root>/<topic>/provenance.csv, then run
the deterministic steps above.
"""
import argparse
import csv
import os
import shutil

from . import core, tierlib

TEMPLATE = os.path.join(os.path.dirname(__file__), "..", "templates", "sources.example.yaml")


def _patterns_for(topic, root):
    return tierlib.load_authority_tiers(os.path.join(core.topic_dir(topic, root), "sources.yaml"))


def cmd_init(a):
    tdir = core.topic_dir(a.topic, a.root)
    for sub in ("raw", "clean", "crosscheck"):
        os.makedirs(os.path.join(tdir, sub), exist_ok=True)
    dst = os.path.join(tdir, "sources.yaml")
    if not os.path.exists(dst) and os.path.exists(TEMPLATE):
        shutil.copy(TEMPLATE, dst)
    print(f"initialized {tdir}\n  edit {dst} (queries + authority_tiers), then add provenance.csv")


def cmd_tier_assign(a):
    tdir = core.topic_dir(a.topic, a.root)
    prov = os.path.join(tdir, "provenance.csv")
    if not os.path.exists(prov):
        raise SystemExit(f"no provenance.csv at {prov}")
    pats = _patterns_for(a.topic, a.root)
    with open(prov, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
        cols = rows[0].keys() if rows else []
    if "tier" not in cols:
        raise SystemExit("provenance.csv has no `tier` column")
    n = 0
    for r in rows:
        if not str(r.get("tier", "")).strip():
            r["tier"] = tierlib.tier_of(r.get("source", ""), r.get("url", ""), pats)
            n += 1
    with open(prov, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(cols))
        w.writeheader()
        w.writerows(rows)
    print(f"assigned tier to {n} blank rows in {prov}")


def cmd_crosscheck(a):
    r = core.crosscheck(a.topic, a.root, a.tolerance)
    print(f"clean:     {r['clean']}  ({r['n_cells']} cells)")
    print(f"conflicts: {r['conflicts']}  ({r['n_conflicts']} same-year disagreements)")
    for c in r["conflict_rows"]:
        print(f"  ! {c['subject']}/{c['field']}/{c['variant']}/{c['scope']}/{c['kind']} "
              f"({c['data_year']}): {c['source_a']}(t{c['tier_a']})={c['value_a']} "
              f"vs {c['source_b']}(t{c['tier_b']})={c['value_b']} [{c['pct_diff']}%]")


def cmd_update(a):
    r = core.update(a.topic, a.date, a.root)
    print(f"compared against: {r['prev'] or '(none — first snapshot)'}")
    print(f"added={r['added']} changed={r['changed']} removed={r['removed']}")
    print(f"changelog: {r['changelog']}\nsnapshot:  {r['snapshot']}")


def cmd_tier(a):
    pats = _patterns_for(a.topic, a.root) if a.topic else None
    print(tierlib.tier_of(a.source, a.url or "", pats))


def main(argv=None):
    p = argparse.ArgumentParser(prog="openclawer", description="deterministic clean/cross-check/update")
    p.add_argument("--root", default=None, help="data root (default $OPENCLAWER_ROOT or ~/data-pipeline)")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("init"); sp.add_argument("--topic", required=True); sp.set_defaults(fn=cmd_init)
    sp = sub.add_parser("tier-assign"); sp.add_argument("--topic", required=True); sp.set_defaults(fn=cmd_tier_assign)
    sp = sub.add_parser("crosscheck"); sp.add_argument("--topic", required=True)
    sp.add_argument("--tolerance", type=float, default=0.05); sp.set_defaults(fn=cmd_crosscheck)
    sp = sub.add_parser("update"); sp.add_argument("--topic", required=True)
    sp.add_argument("--date", required=True); sp.set_defaults(fn=cmd_update)
    sp = sub.add_parser("tier"); sp.add_argument("--source", required=True)
    sp.add_argument("--url", default=""); sp.add_argument("--topic", default=None); sp.set_defaults(fn=cmd_tier)

    a = p.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
