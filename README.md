# datapipe

Portable **collect → clean → cross-check → update** engine for building a clean,
multi-source-verified dataset on a topic. Records every value with provenance,
resolves multi-source conflicts by an authority tier, and does idempotent
incremental updates with a changelog.

## Two layers (why this is portable)

| Layer | What | Portability |
|---|---|---|
| **Deterministic core** (this package) | clean / cross-check / update + credibility tiering | stdlib-only, runs on **any platform** |
| **Search / fan-out** | finding the public data points | platform-specific — *not* in this package |

The valuable, error-prone logic (口径归一 canonicalization, tiering, cross-check,
idempotent update) is pure and cross-platform. The only platform-specific part is
*how you search the web*. So: **feed your platform's web-search results into
`<root>/<topic>/provenance.csv`, then run the deterministic steps here.** Use it
from a Claude skill, a CLI, another agent, or a cron job — same engine.

## Install

```bash
# console command (needs recent pip):
pip install /path/to/datapipe            # then:  datapipe ...
# or zero-install, works anywhere:
python3 -m datapipe.cli ...
# optional: read authority_tiers from sources.yaml
pip install /path/to/datapipe[yaml]
```

## Usage

```bash
datapipe init        --topic dc_yrd          # scaffold <root>/dc_yrd/ + sources.yaml
# (your platform fills <root>/dc_yrd/provenance.csv via web search)
datapipe tier-assign --topic dc_yrd          # fill blank `tier` via tierlib + sources.yaml
datapipe crosscheck  --topic dc_yrd          # -> clean/<topic>.csv + crosscheck/conflicts.csv
datapipe update      --topic dc_yrd --date 2026-06-02   # diff vs last snapshot -> CHANGELOG.md
datapipe tier        --source "新浪财经" --url sina.com.cn   # one-off lookup -> 4
```

Data root: `$DATAPIPE_ROOT` or `~/data-pipeline`; override per call with `--root`.

## Data contract — `<root>/<topic>/`

```
sources.yaml              # queries + authority_tiers (see templates/)
provenance.csv            # the ledger: one row per (subject × field × source)
clean/<topic>.csv         # chosen values, one row per cell, with `status`
clean/<topic>_<date>.csv  # dated snapshot for diffing
crosscheck/conflicts.csv  # same-year, same-口径 disagreements
CHANGELOG.md              # per-update diffs
```

`provenance.csv` columns:
`subject, field, value, value_num, unit, variant, scope, kind, data_year, source, tier, url, fetched_date, ref, note`

**The one rule that matters most:** two rows are compared only when
`(subject, field, variant, scope, kind)` match — `variant` (precision/type, e.g.
FP16/FP32/通用/智能), `scope` (省级/市级/集群/项目), `kind` (实际/目标). Different
口径 → never compared (avoids false conflicts). Rows across `data_year` in one
cell are a time series; the latest is the clean value.

## Authority tier — INVERTED scale

**1 = most credible … 5 = least** (blank = worst). Lowest number wins on conflict.
Defaults are generic (see `datapipe/tierlib.py`); override per topic in
`sources.yaml: authority_tiers`. CSVs are written `utf-8-sig` (Excel-safe for CJK).

## CSV files are UTF-8 with BOM
So Excel shows Chinese correctly. All outputs use `utf-8-sig`.
