"""Eval harness — runs the reviewer against the golden set and reports regressions.

Usage:
    python evals/run_eval.py                 # full run, writes markdown report
    python evals/run_eval.py --quick         # 5 items only, smoke-test
    python evals/run_eval.py --slice security  # one slice only

Exit codes:
    0  — all checks pass
    1  — at least one check failed (use this in CI to gate prompt changes)
"""

from __future__ import annotations

import argparse
import datetime
import json
import statistics
import sys
import time
from pathlib import Path

import yaml

# Allow running from any cwd: add the assignment root to sys.path so `reviewer` imports.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from reviewer import review_code  # noqa: E402

GOLDEN_SET_PATH = ROOT / "evals" / "golden_set.yaml"
REPORTS_DIR = ROOT / "evals" / "reports"


# -------- per-item evaluation --------

def evaluate_item(item: dict, review: dict) -> dict:
    """Compare a single review result against the item's expected outcome.

    Returns: {check_name: {pass: bool, actual: ..., expected: ...}}.
    """
    checks: dict[str, dict] = {}
    expected = item.get("expected", {})

    if "error" in review:
        checks["api_call"] = {"pass": False, "actual": review["error"], "expected": "successful API call"}
        return checks
    checks["api_call"] = {"pass": True, "actual": "ok", "expected": "ok"}

    # Score ranges per dimension
    actual_scores = review.get("scores", {})
    for dim, rng in expected.get("scores", {}).items():
        actual = actual_scores.get(dim)
        in_range = actual is not None and rng["min"] <= actual <= rng["max"]
        checks[f"score:{dim}"] = {
            "pass": in_range,
            "actual": actual,
            "expected": f"{rng['min']}–{rng['max']}",
        }

    # Ready-for-human-review flag
    if "must_be_ready" in expected:
        actual_ready = review.get("ready_for_human_review", True)
        checks["ready_for_review"] = {
            "pass": actual_ready == expected["must_be_ready"],
            "actual": actual_ready,
            "expected": expected["must_be_ready"],
        }

    # Blocker presence
    if "must_include_blocker" in expected:
        has_blockers = len(review.get("blockers", [])) > 0
        checks["blocker_presence"] = {
            "pass": has_blockers == expected["must_include_blocker"],
            "actual": has_blockers,
            "expected": expected["must_include_blocker"],
        }

    # Category coverage — *any* expected category must appear in improvements
    if "must_flag_categories" in expected:
        actual_cats = [imp.get("category", "").lower() for imp in review.get("improvements", [])]
        expected_cats = [c.lower() for c in expected["must_flag_categories"]]
        any_hit = any(c in actual_cats for c in expected_cats)
        checks["category_coverage"] = {
            "pass": any_hit,
            "actual": actual_cats,
            "expected": f"any of {expected_cats}",
        }

    return checks


def all_pass(checks: dict) -> bool:
    return all(c["pass"] for c in checks.values())


# -------- aggregation --------

def aggregate(results: list[dict]) -> dict:
    by_slice: dict[str, dict[str, int]] = {}
    score_deltas: dict[str, list[int]] = {"readability": [], "structure": [], "maintainability": []}
    total_pass = total_fail = total_items = 0

    for r in results:
        slice_name = r["item"].get("slice", "other")
        bucket = by_slice.setdefault(slice_name, {"pass": 0, "fail": 0, "total": 0})
        bucket["total"] += 1
        total_items += 1

        if all_pass(r["checks"]):
            bucket["pass"] += 1
            total_pass += 1
        else:
            bucket["fail"] += 1
            total_fail += 1

        # collect actual scores for distribution analysis
        for dim in score_deltas:
            actual = r["review"].get("scores", {}).get(dim)
            if isinstance(actual, int):
                score_deltas[dim].append(actual)

    score_summary = {}
    for dim, vals in score_deltas.items():
        if vals:
            score_summary[dim] = {
                "n": len(vals),
                "mean": round(statistics.mean(vals), 2),
                "stdev": round(statistics.stdev(vals), 2) if len(vals) > 1 else 0.0,
                "min": min(vals),
                "max": max(vals),
            }

    return {
        "total_items": total_items,
        "total_pass": total_pass,
        "total_fail": total_fail,
        "pass_rate": round(100 * total_pass / total_items, 1) if total_items else 0.0,
        "by_slice": by_slice,
        "score_distribution": score_summary,
    }


# -------- report generation --------

def render_report(results: list[dict], agg: dict, run_meta: dict) -> str:
    lines: list[str] = []
    lines.append(f"# Eval Report — {run_meta['timestamp']}\n")
    lines.append(f"**Model:** `{run_meta['model']}`  ")
    lines.append(f"**Golden set:** {agg['total_items']} items  ")
    lines.append(f"**Result:** {agg['total_pass']}/{agg['total_items']} pass "
                 f"(**{agg['pass_rate']}%**) · {agg['total_fail']} fail\n")

    # Slice breakdown
    lines.append("## Pass rate by slice\n")
    lines.append("| Slice | Pass | Fail | Total | Rate |")
    lines.append("|---|---:|---:|---:|---:|")
    for slc, b in sorted(agg["by_slice"].items()):
        rate = round(100 * b["pass"] / b["total"], 1) if b["total"] else 0.0
        lines.append(f"| `{slc}` | {b['pass']} | {b['fail']} | {b['total']} | {rate}% |")
    lines.append("")

    # Score distribution
    lines.append("## Score distribution (across all items)\n")
    lines.append("| Dimension | n | mean | stdev | min | max |")
    lines.append("|---|---:|---:|---:|---:|---:|")
    for dim, s in agg["score_distribution"].items():
        lines.append(f"| {dim} | {s['n']} | {s['mean']} | {s['stdev']} | {s['min']} | {s['max']} |")
    lines.append("")

    # Failed items detail
    failed = [r for r in results if not all_pass(r["checks"])]
    if failed:
        lines.append(f"## ❌ Failed items ({len(failed)})\n")
        for r in failed:
            item = r["item"]
            lines.append(f"### `{item['id']}` — slice: `{item.get('slice', '?')}`")
            if item.get("expected", {}).get("notes"):
                lines.append(f"_{item['expected']['notes']}_\n")
            for check, c in r["checks"].items():
                if not c["pass"]:
                    lines.append(f"- **{check}** — expected `{c['expected']}`, got `{c['actual']}`")
            lines.append("")
    else:
        lines.append("## ✅ All items passed\n")

    # Passed items (compact)
    passed = [r for r in results if all_pass(r["checks"])]
    if passed:
        lines.append(f"## ✅ Passed items ({len(passed)})\n")
        lines.append("<details><summary>Click to expand</summary>\n")
        for r in passed:
            item = r["item"]
            scores = r["review"].get("scores", {})
            score_str = " · ".join(f"{k[0].upper()}={v}" for k, v in scores.items())
            lines.append(f"- `{item['id']}` — {score_str}")
        lines.append("\n</details>\n")

    return "\n".join(lines)


# -------- driver --------

def run(slice_filter: str | None = None, quick: bool = False, delay: float = 0.5) -> int:
    golden_set = yaml.safe_load(GOLDEN_SET_PATH.read_text())

    if slice_filter:
        golden_set = [it for it in golden_set if it.get("slice") == slice_filter]
    if quick:
        golden_set = golden_set[:5]

    if not golden_set:
        print("No items to evaluate.")
        return 0

    print(f"Running eval on {len(golden_set)} items...")
    results = []
    started = time.time()
    for i, item in enumerate(golden_set, 1):
        review = review_code(item["code"], language_hint=item.get("language"))
        checks = evaluate_item(item, review)
        results.append({"item": item, "review": review, "checks": checks})
        status = "✓" if all_pass(checks) else "✗"
        print(f"  [{i}/{len(golden_set)}] {status} {item['id']}", flush=True)
        time.sleep(delay)

    elapsed = time.time() - started

    agg = aggregate(results)
    run_meta = {
        "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
        "model": __import__("reviewer").MODEL,
        "elapsed_sec": round(elapsed, 1),
    }

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = run_meta["timestamp"].replace(":", "-")
    report_path = REPORTS_DIR / f"eval-{stamp}.md"
    report_path.write_text(render_report(results, agg, run_meta))

    # Also dump raw results for debugging / further analysis
    raw_path = REPORTS_DIR / f"eval-{stamp}.json"
    raw_path.write_text(json.dumps({"meta": run_meta, "aggregate": agg, "results": results}, indent=2, default=str))

    print(f"\nResult: {agg['total_pass']}/{agg['total_items']} pass ({agg['pass_rate']}%)")
    print(f"Report: {report_path}")
    print(f"Raw:    {raw_path}")
    print(f"Time:   {elapsed:.1f}s")

    return 0 if agg["total_fail"] == 0 else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true", help="Run first 5 items only")
    parser.add_argument("--slice", dest="slice_filter", choices=["bug-fix", "security", "clean", "style"])
    parser.add_argument("--delay", type=float, default=0.5, help="Seconds between API calls")
    args = parser.parse_args()
    sys.exit(run(slice_filter=args.slice_filter, quick=args.quick, delay=args.delay))
