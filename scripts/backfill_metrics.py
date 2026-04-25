#!/usr/bin/env python3
"""One-time script to backfill token/cost estimates for early metric runs.

Runs before 2026-03-26 have zero token counts (tracking wasn't implemented yet).
This script estimates tokens using per-topic median tokens-per-article ratios
from the known-data period, then computes costs using gemini-2.5-pro rates.

Usage:
    uv run python scripts/backfill_metrics.py

The script modifies metrics/history.jsonl in-place. Review the diff before committing.
"""

import json
import statistics
from pathlib import Path

METRICS_FILE = Path(__file__).parent.parent / "metrics" / "history.jsonl"

# gemini-2.5-pro pricing (same as config.py)
INPUT_RATE = 1.25  # $/1M tokens
OUTPUT_RATE = 10.00  # $/1M tokens


def estimate_cost(prompt_tokens: int, completion_tokens: int) -> float:
    return (prompt_tokens * INPUT_RATE + completion_tokens * OUTPUT_RATE) / 1_000_000


def main() -> None:
    lines = METRICS_FILE.read_text(encoding="utf-8").splitlines()
    runs = [json.loads(line) for line in lines if line.strip()]

    # Split into known-data (has real tokens) vs zero-data runs
    known_runs = [r for r in runs if r.get("total_tokens", 0) > 0]
    zero_runs = [r for r in runs if r.get("total_tokens", 0) == 0]

    print(f"Total runs: {len(runs)}")
    print(f"Runs with real token data: {len(known_runs)}")
    print(f"Runs to backfill: {len(zero_runs)}")

    if not known_runs:
        print("No known-data runs found. Nothing to do.")
        return

    # Compute per-topic median tokens-per-article ratios from known data
    ratios: dict[str, dict[str, list[float]]] = {}
    for run in known_runs:
        for topic in run.get("topics", []):
            name = topic["topic"]
            articles = topic.get("articles_fetched", 0)
            if articles == 0:
                continue
            ratios.setdefault(name, {"prompt": [], "completion": []})
            ratios[name]["prompt"].append(topic["prompt_tokens"] / articles)
            ratios[name]["completion"].append(topic["completion_tokens"] / articles)

    median_ratios: dict[str, tuple[float, float]] = {}
    for name, data in ratios.items():
        median_prompt = statistics.median(data["prompt"])
        median_completion = statistics.median(data["completion"])
        median_ratios[name] = (median_prompt, median_completion)
        print(
            f"  {name}: median prompt/article={median_prompt:.1f}, "
            f"completion/article={median_completion:.1f}"
        )

    # Backfill zero-token runs
    backfilled = 0
    for run in zero_runs:
        run_total_prompt = 0
        run_total_completion = 0
        run_total_tokens = 0

        for topic in run.get("topics", []):
            name = topic["topic"]
            articles = topic.get("articles_fetched", 0)
            if articles == 0 or name not in median_ratios:
                topic.setdefault("cost", 0.0)
                continue

            prompt_ratio, completion_ratio = median_ratios[name]
            est_prompt = round(prompt_ratio * articles)
            est_completion = round(completion_ratio * articles)
            est_total = est_prompt + est_completion
            est_cost = estimate_cost(est_prompt, est_completion)

            topic["prompt_tokens"] = est_prompt
            topic["completion_tokens"] = est_completion
            topic["total_tokens"] = est_total
            topic["cost"] = est_cost

            run_total_prompt += est_prompt
            run_total_completion += est_completion
            run_total_tokens += est_total

        run["total_prompt_tokens"] = run_total_prompt
        run["total_completion_tokens"] = run_total_completion
        run["total_tokens"] = run_total_tokens
        run["total_cost"] = sum(t.get("cost", 0.0) for t in run.get("topics", []))
        backfilled += 1

    # Write back
    output_lines = [json.dumps(r, ensure_ascii=False) for r in runs]
    METRICS_FILE.write_text("\n".join(output_lines) + "\n", encoding="utf-8")

    print(f"\nBackfilled {backfilled} runs. Review with: git diff metrics/history.jsonl")

    # Print a sample
    if zero_runs:
        sample = zero_runs[0]
        print(f"\nSample (first backfilled run, {sample['run_date']}):")
        for t in sample.get("topics", []):
            print(
                f"  {t['topic']}: {t['articles_fetched']} articles, "
                f"prompt={t['prompt_tokens']}, completion={t['completion_tokens']}, "
                f"cost=${t['cost']:.4f}"
            )
        print(f"  total_cost=${sample['total_cost']:.4f}")


if __name__ == "__main__":
    main()
