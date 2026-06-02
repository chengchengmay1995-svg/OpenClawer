# OpenClawer  ·  `datapipe`

> Repo name is **OpenClawer**; the Python package / command it installs is **`datapipe`**.

Portable **collect → clean → cross-check → update** engine for building a clean,
multi-source-verified dataset on a topic. Records every value with provenance,
resolves multi-source conflicts by an authority tier, and does idempotent
incremental updates with a changelog.

## 用途 · What it's for

**中文**：OpenClawer(包名 `datapipe`)是一个"搜集 → 清洗 → 交叉核对 → 定期更新"的数据核查工具。
它的核心价值不在爬虫本身,而在于把来自**多个来源的同一信息按统一口径对齐**(精度 / 范围 / 实际vs目标 / 年份)后做交叉核对,
按来源**可信度分级**(tier 1 最可信)自动定值并保留所有分歧痕迹,并支持**幂等的增量更新 + 变更日志**。
适合需要从公开信息构建一张"干净、可追溯、多源验证"的数据表并定期维护的场景(行业数据库、指标核查等)。

**English**: OpenClawer (Python package `datapipe`) is a collect → clean → cross-check → update toolkit
for building a clean, **multi-source-verified** dataset. Its value isn't crawling itself but
**canonicalizing the same fact across sources to one comparable basis** (precision / scope /
actual-vs-target / year), cross-checking them, **resolving conflicts by source-credibility tier**
(tier 1 = most credible) while keeping every disagreement on record, plus **idempotent incremental
updates with a changelog**. Use it whenever you need a clean, traceable, multi-source-verified table
built from public information and kept up to date.

## 安装与分享 · Install & Share

**中文**
```bash
# 公开库:直接装
pip install git+https://github.com/chengchengmay1995-svg/OpenClawer.git
# 私有库:先让仓库主在 Settings → Collaborators 把你加为协作者,再用 SSH 装
pip install git+ssh://git@github.com/chengchengmay1995-svg/OpenClawer.git
```
装好后:包名是 `datapipe`,命令 `datapipe ...`(若 `datapipe` 没进 PATH,用 `python3 -m datapipe.cli ...`)。
**分享**:公开库直接发链接;私有库到 GitHub 仓库 **Settings → Collaborators** 添加对方账号。

**English**
```bash
# Public repo — just install:
pip install git+https://github.com/chengchengmay1995-svg/OpenClawer.git
# Private repo — owner adds you under Settings → Collaborators, then install via SSH:
pip install git+ssh://git@github.com/chengchengmay1995-svg/OpenClawer.git
```
After install the package is `datapipe` (command `datapipe ...`, or `python3 -m datapipe.cli ...`
if the console script isn't on PATH). **To share:** public repo → send the link; private repo →
add collaborators under GitHub **Settings → Collaborators**.

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
