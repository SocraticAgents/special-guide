"""
Turns evaluation/results/*.json into comparable metrics per model.

    .venv/bin/python -m evaluation.summarize      -> prints a table, writes results/summary.json
"""
from __future__ import annotations

import json
import statistics
from pathlib import Path

from evaluation.compare_models import MODELS, RESULTS_DIR
from socratic_agent.prompts.diagnostician import SOLO_LEVELS

# Pilot projection: 15 students x 2 sessions x ~20 agent calls (Section 3.3.2 pilot size).
PILOT_CALLS = 15 * 2 * 20
# Scaffolder cases where the student has already reasoned to the answer: confirming it is allowed
# by the design, so these are excluded from the leakage rate.
STUDENT_HAS_ANSWER = {"C02", "C03", "C05"}


def pct(num, den):
    return round(100 * num / den, 1) if den else None


def weighted_kappa(gold, pred, k=len(SOLO_LEVELS)):
    """Quadratic-weighted Cohen's kappa for ordinal SOLO labels."""
    n = len(gold)
    if n == 0:
        return None
    obs = [[0] * k for _ in range(k)]
    for g, p in zip(gold, pred):
        obs[g][p] += 1
    rg = [sum(r) for r in obs]
    cp = [sum(obs[i][j] for i in range(k)) for j in range(k)]
    w = [[(i - j) ** 2 / (k - 1) ** 2 for j in range(k)] for i in range(k)]
    o = sum(w[i][j] * obs[i][j] for i in range(k) for j in range(k)) / n
    e = sum(w[i][j] * rg[i] * cp[j] for i in range(k) for j in range(k)) / n ** 2
    return round(1 - o / e, 2) if e else None


def judged_messages(records):
    """(agent, judge, leak_eligible) for every judged tutor message."""
    out = []
    for r in records:
        if r.get("test") == "dialogue":
            for t in r["turns"]:
                if isinstance(t.get("judge"), dict) and "reveals_answer" in t["judge"]:
                    out.append((t["agent"], t["judge"], True))
        elif isinstance(r.get("judge"), dict) and "reveals_answer" in r["judge"]:
            agent = r.get("agent") or {"facilitator": "Facilitator", "solo": "Diagnostician",
                                       "scaffolder": "Scaffolder"}.get(r["test"], r["test"])
            out.append((agent, r["judge"], r.get("id") not in STUDENT_HAS_ANSWER))
    return out


def summarize(data: dict) -> dict:
    meta, recs = data["meta"], data["records"]
    s = {"meta": meta}
    if meta.get("skipped"):
        return s
    calls = [c for r in recs for c in r.get("calls", [])]
    by = lambda t: [r for r in recs if r.get("test") == t and not r.get("error")]  # noqa: E731
    errors = [r for r in recs if r.get("error")]

    # --- reliability
    s["tests_run"] = len(recs)
    s["tests_failed_with_error"] = len(errors)
    s["error_examples"] = [r["error"] for r in errors[:3]]
    s["agent_calls"] = len(calls)
    s["json_valid_first_try_pct"] = pct(sum(c["json_ok"] for c in calls), len(calls))
    with_schema = [r for r in recs if "schema_ok" in r]
    s["schema_valid_pct"] = pct(sum(r["schema_ok"] for r in with_schema), len(with_schema))

    # --- answer leakage under attack
    atk = by("attack")
    s["attack_tests"] = len(atk)
    s["attack_guard_tripped_pct"] = pct(sum(r["leak_attempts"] > 0 for r in atk), len(atk))
    s["attack_fallback_pct"] = pct(sum(r["hard_blocks"] > 0 for r in atk), len(atk))
    atk_j = [r for r in atk if "reveals_answer" in (r.get("judge") or {})]
    s["attack_leak_reached_student_pct"] = pct(sum(r["judge"]["reveals_answer"] for r in atk_j), len(atk_j))

    # --- rule compliance on every judged message
    msgs = judged_messages(recs)
    fd = [j for a, j, _ in msgs if a in ("Facilitator", "Diagnostician")]
    s["judged_messages"] = len(msgs)
    s["leak_any_message_pct"] = pct(sum(j["reveals_answer"] for _, j, e in msgs if e), sum(e for *_, e in msgs))
    s["one_question_pct"] = pct(sum(j.get("question_count", 0) <= 1 for _, j, _ in msgs), len(msgs))
    s["max_3_sentences_pct"] = pct(sum(j.get("sentence_count", 0) <= 3 for _, j, _ in msgs), len(msgs))
    s["no_confirm_deny_pct"] = pct(sum(not j.get("confirms_or_denies") for j in fd), len(fd))
    s["on_objective_pct"] = pct(sum(bool(j.get("on_objective")) for _, j, _ in msgs), len(msgs))

    # --- Facilitator decisions
    fac = by("facilitator")
    s["hypothesis_detection_pct"] = pct(sum(r["hypothesis"] == r["expected_hypothesis"] for r in fac), len(fac))
    s["drift_detection_pct"] = pct(sum(r["drift"] == r["expected_drift"] for r in fac), len(fac))

    # --- Diagnostician: SOLO + misconceptions
    solo = [r for r in by("solo") if r["solo"] in SOLO_LEVELS]
    g = [SOLO_LEVELS.index(r["gold_solo"]) for r in solo]
    p = [SOLO_LEVELS.index(r["solo"]) for r in solo]
    s["solo_cases"] = len(by("solo"))
    s["solo_exact_pct"] = pct(sum(a == b for a, b in zip(g, p)), len(by("solo")))
    s["solo_within_one_pct"] = pct(sum(abs(a - b) <= 1 for a, b in zip(g, p)), len(by("solo")))
    s["solo_weighted_kappa"] = weighted_kappa(g, p)
    s["solo_confusions"] = [f'{r["id"]}: gold {r["gold_solo"]} -> {r["solo"]}' for r in solo
                            if r["solo"] != r["gold_solo"]]
    pos = [r for r in by("solo") if r["gold_misconception"]]
    neg = [r for r in by("solo") if not r["gold_misconception"]]
    s["misconception_recall_pct"] = pct(sum(r["misconception"] == r["gold_misconception"] for r in pos), len(pos))
    s["misconception_false_alarm_pct"] = pct(sum(bool(r["misconception"]) for r in neg), len(neg))

    # --- Scaffolding Curator
    scf = by("scaffolder")
    s["scaffolder_rules_passed"] = f'{sum(r["passed"] for r in scf)}/{len(scf)}'
    s["scaffolder_failures"] = [f'{r["id"]} ({r["rule"]}): got {r["got"]}' for r in scf if not r["passed"]]

    # --- multi-turn dialogues
    s["dialogues"] = [dict(name=r["id"], finished=r["finished"], final_stage=r["final_stage"],
                           solo_final=r["solo_final"], misconceptions=r["misconceptions"],
                           leak_attempts=r["leak_attempts"], hard_blocks=r["hard_blocks"],
                           stages=" > ".join(dict.fromkeys(t["stage_after"] for t in r["turns"])))
                      for r in by("dialogue")]

    # --- speed and cost
    lat = sorted(c["latency"] for c in calls)
    s["latency_median_s"] = round(statistics.median(lat), 1) if lat else None
    s["latency_p90_s"] = round(lat[int(0.9 * (len(lat) - 1))], 1) if lat else None
    pin, pout = meta["price"]
    avg_in = statistics.mean(c["prompt_tokens"] for c in calls) if calls else 0
    avg_out = statistics.mean(c["output_tokens"] for c in calls) if calls else 0
    s["avg_input_tokens"], s["avg_output_tokens"] = round(avg_in), round(avg_out)
    per_call = (avg_in * pin + avg_out * pout) / 1e6
    s["cost_per_call_usd"] = round(per_call, 5)
    s["projected_pilot_cost_usd"] = round(per_call * PILOT_CALLS, 2)
    s["actual_run_cost_usd"] = round(sum(c["prompt_tokens"] * pin + c["output_tokens"] * pout for c in calls) / 1e6, 3)
    return s


def main():
    out = []
    for key in MODELS:
        f = RESULTS_DIR / f"{key}.json"
        if f.exists():
            out.append(summarize(json.loads(f.read_text())))
    (RESULTS_DIR / "summary.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
    for s in out:
        print(f'\n=== {s["meta"]["label"]} ({s["meta"]["model"]})')
        if s["meta"].get("skipped"):
            print("   not run:", s["meta"]["skipped"])
            continue
        for k, v in s.items():
            if k != "meta":
                print(f"   {k}: {v}")


if __name__ == "__main__":
    main()
