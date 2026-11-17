"""Shared helpers: load the per-episode records written by run_diagnostic.py and Wilson intervals."""
import json
import math
from pathlib import Path


def load(root):
    """All records below <root>/<policy>/<task>/<job>/probe.jsonl, each tagged with its policy directory."""
    recs = []
    for f in sorted(Path(root).glob("*/*/*/probe.jsonl")):
        policy = f.parts[-4]
        for line in f.read_text().splitlines():
            if line.startswith("{"):
                r = json.loads(line)
                r["_policy"] = policy
                recs.append(r)
    return recs


def wilson(k, n, z=1.96):
    if n == 0:
        return float("nan"), float("nan")
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)


def pct(k, n):
    lo, hi = wilson(k, n)
    return f"{100 * k / n:.0f}% ({100 * lo:.0f}-{100 * hi:.0f})" if n else "-"
