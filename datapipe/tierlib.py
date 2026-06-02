"""Source-credibility tier — shared by the cleaning step and cross-check.

INVERTED scale: **1 = most credible, 5 = least credible** (blank/unknown = worst).
This convention is fixed across the skill: lower tier number always wins.

`tier_of(source, url, patterns)` assigns a tier by matching source/url substrings.
- Pass `patterns` = the topic's `sources.yaml: authority_tiers` (list of
  {tier, match:[...]}) so credibility is topic-configurable and auditable.
- With no patterns it falls back to DEFAULT_PATTERNS (generic, China-DC flavored);
  override per topic in sources.yaml rather than editing this file.
"""

# Generic default ladder (inverted: 1 best). Override via sources.yaml authority_tiers.
DEFAULT_PATTERNS = [
    {"tier": 1, "match": ["gov.cn", ".gov.", "sasac", "ndrc", "cma.gov", "iea.org",
                           "政府", "发改委", "工信部", "气象局", "管委会", "数据局", "国资委", "统计局"]},
    {"tier": 2, "match": ["cninfo", "mrgg", "/finalpage/", "年报", "公告", "协会",
                           "信通院", "研究院", "超算中心官网", "超级计算中心官网"]},
    {"tier": 3, "match": ["cnki", "知网", "学报", "arxiv", "springer", "sciencedirect", "期刊", "journal"]},
    {"tier": 4, "match": ["sina", "新浪", "stcn", "证券时报", "jiemian", "界面", "caixin", "财新",
                          "yicai", "第一财经", "thepaper", "澎湃", "cnr", "央广", "cri.cn", "国际在线",
                          "chinadaily", "中国日报", "xinhua", "新华", "日报", "新闻网", "reuters", "bloomberg"]},
    {"tier": 5, "match": ["*"]},  # fallback: industry portals (DTDATA/IDC圈), PR pages, UGC
]

# tiers that should be checked before media-domain matches (a filing hosted on a
# media domain is still a filing). Keep filings(2)/gov(1)/academic(3) ahead of media(4).
_PRECEDENCE = [2, 1, 3, 4, 5]


def tier_of(source, url="", patterns=None):
    pats = patterns or DEFAULT_PATTERNS
    s = f"{source} {url}".lower()
    by_tier = {p["tier"]: [m.lower() for m in p.get("match", [])] for p in pats}
    worst = max(by_tier) if by_tier else 5
    order = [t for t in _PRECEDENCE if t in by_tier] + [t for t in sorted(by_tier) if t not in _PRECEDENCE]
    for t in order:
        ms = by_tier[t]
        if "*" in ms:
            continue
        if any(m in s for m in ms):
            return t
    # fallback: a tier whose match contains '*', else worst
    for t in sorted(by_tier):
        if "*" in by_tier[t]:
            return t
    return worst


def load_authority_tiers(path):
    """Read `authority_tiers` from a topic's sources.yaml. Returns None if the
    file/key is absent or pyyaml is unavailable (caller uses DEFAULT_PATTERNS)."""
    import os
    if not path or not os.path.exists(path):
        return None
    try:
        import yaml  # optional dependency
    except ImportError:
        return None
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("authority_tiers") or None


def confidence(tier, scope_mismatch, kind, verdict=None):
    """High = credible(tier<=2) + same scope + actual; Low = tier5/scope mismatch."""
    if verdict == "no-comparable":
        return "n/a"
    try:
        tier = int(tier)
    except (ValueError, TypeError):
        return "Low"
    if scope_mismatch or tier >= 5:
        return "Low"
    if tier <= 2 and kind == "实际":
        return "High"
    return "Med"
