"""
DD2 planned evaluation: agreement between the LLM's SOLO estimates and human rubric labels.

Input: solo_labelling.csv from evaluation.export_research_data, after a reviewer has filled
the empty `human_solo` column with one of the five SOLO levels (Table 4.9 rubric, coding
rules a and b). Rows left blank are skipped.

Reports exact agreement, adjacent agreement (within one level), quadratic-weighted kappa,
the direction of disagreements (LLM higher / lower), and lists every disagreement so it can
be discussed in the thesis rather than averaged away.

    python -m evaluation.solo_agreement evaluation/export/solo_labelling.csv
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

from evaluation.summarize import weighted_kappa
from socratic_agent.learner_model import SOLO_ORDER, solo_rank


def agreement(rows: list[dict]) -> dict:
    pairs = [(solo_rank(r["human_solo"].strip()), solo_rank(r["llm_solo_estimate"]), r) for r in rows
             if solo_rank(r.get("human_solo", "").strip()) is not None and solo_rank(r["llm_solo_estimate"]) is not None]
    n = len(pairs)
    if not n:
        return {"n": 0}
    exact = sum(h == m for h, m, _ in pairs)
    adjacent = sum(abs(h - m) <= 1 for h, m, _ in pairs)
    return {
        "n": n,
        "exact_agreement": round(exact / n, 3),
        "adjacent_agreement": round(adjacent / n, 3),
        "weighted_kappa": weighted_kappa([h for h, _, _ in pairs], [m for _, m, _ in pairs]),
        "llm_higher": sum(m > h for h, m, _ in pairs),
        "llm_lower": sum(m < h for h, m, _ in pairs),
        "disagreements": [
            {"session_id": r["session_id"], "turn_index": r["turn_index"], "student_response": r["student_response"],
             "human": SOLO_ORDER[h], "llm": SOLO_ORDER[m]}
            for h, m, r in pairs if h != m
        ],
    }


def main(path: str) -> None:
    with Path(path).open(encoding="utf-8") as f:
        result = agreement(list(csv.DictReader(f)))
    if not result["n"]:
        print("No rows with a valid human_solo label yet.")
        return
    for key in ("n", "exact_agreement", "adjacent_agreement", "weighted_kappa", "llm_higher", "llm_lower"):
        print(f"{key:>20}: {result[key]}")
    for d in result["disagreements"]:
        print(f"  turn {d['turn_index']}: human={d['human']:<17} llm={d['llm']:<17} {d['student_response'][:70]!r}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "evaluation/export/solo_labelling.csv")
