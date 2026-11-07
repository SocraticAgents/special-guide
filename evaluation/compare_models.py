"""
Model comparison for the Socratic-Agent prototype.

Runs every candidate model through the SAME fixed scenarios (evaluation/scenarios.py),
using the prototype's real prompts, leakage guard and orchestrator — only the model
behind call_json_agent() changes. Each tutor message is then scored by a separate
judge model that is not one of the candidates.

Usage (from the code/ folder):
    .venv/bin/python -m evaluation.compare_models                 # all models with a key
    .venv/bin/python -m evaluation.compare_models gemini-2.5-flash # one model

Results are written to evaluation/results/<model>.json; build the summary with
evaluation/summarize.py. Models whose API key is missing are skipped and reported.
"""
from __future__ import annotations

import json
import os
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
sys.path.insert(0, str(ROOT))

from socratic_agent import llm_client  # noqa: E402
from socratic_agent import orchestrator as orch  # noqa: E402
from socratic_agent.prompts import diagnostician, facilitator, scaffolder  # noqa: E402
from socratic_agent.state import SessionState, Stage  # noqa: E402
from socratic_agent.topic_bank import TOPICS  # noqa: E402
from evaluation import scenarios as sc  # noqa: E402

RESULTS_DIR = Path(__file__).resolve().parent / "results"

# Every candidate is reached through ONE OpenRouter key, so all run under identical conditions
# (same code path, prompts and settings); only the model changes. "data_collection": "deny" routes
# only to providers that do not store or train on prompts (Section 3.6). Prices are US$ per 1M
# tokens (input, output) as listed in the thesis pricing table (Table 3.X).
OPENROUTER = dict(base_url="https://openrouter.ai/api/v1", key_env="OPENROUTER_API_KEY")
NO_TRAINING = {"provider": {"data_collection": "deny"}}
MODELS = {
    "gemini-2.5-flash": dict(OPENROUTER, label="Gemini 2.5 Flash", vendor="Google (via OpenRouter)",
                             model="google/gemini-2.5-flash", price=(0.30, 2.50), extra=NO_TRAINING),
    "gemini-2.5-flash-lite": dict(OPENROUTER, label="Gemini 2.5 Flash-Lite", vendor="Google (via OpenRouter)",
                                  model="google/gemini-2.5-flash-lite", price=(0.10, 0.40), extra=NO_TRAINING),
    "gpt-oss-20b": dict(OPENROUTER, label="GPT-OSS 20B", vendor="Groq (via OpenRouter)", model="openai/gpt-oss-20b",
                        price=(0.075, 0.30),
                        # pinned to Groq so the model is served by the provider priced in the thesis table
                        extra={"provider": {"order": ["groq"], "allow_fallbacks": False, "data_collection": "deny"}}),
    "llama-3.3-70b": dict(OPENROUTER, label="Meta Llama 3.3 70B Instruct", vendor="OpenRouter",
                          model="meta-llama/llama-3.3-70b-instruct", price=(0.10, 0.32), extra=NO_TRAINING),
    "claude-sonnet-4.5": dict(OPENROUTER, label="Claude Sonnet 4.5", vendor="Anthropic (via OpenRouter)",
                              model="anthropic/claude-sonnet-4.5", price=(3.00, 15.00), extra=NO_TRAINING),
}
# The judge is not one of the candidates.
JUDGE = dict(OPENROUTER, model=os.getenv("JUDGE_MODEL", "google/gemini-2.5-pro"), extra=NO_TRAINING)

_local = threading.local()


def _client(cfg: dict) -> OpenAI:
    return OpenAI(api_key=os.environ[cfg["key_env"]], base_url=cfg["base_url"], max_retries=0, timeout=120)


def _with_backoff(fn, tries: int = 8):
    """Retries rate-limit / transient errors (free-tier keys hit per-minute limits)."""
    delay = 5.0
    for attempt in range(tries):
        try:
            return fn()
        except Exception as exc:  # openai.APIStatusError, timeouts, connection errors
            status = getattr(exc, "status_code", None)
            if status in (400, 401, 402, 403, 404) or attempt == tries - 1:
                raise
            m = re.search(r"retry in ([\d.]+)s", str(exc)) or re.search(r"retryDelay'?: '?(\d+)s", str(exc))
            time.sleep(float(m.group(1)) + 1 if m else delay)
            delay = min(delay * 2, 60)


# ---------------------------------------------------------------------------
# Instrumented model caller, swapped in for the prototype's provider function
# ---------------------------------------------------------------------------
def make_caller(cfg: dict):
    client = _client(cfg)

    def caller(system_prompt, messages, temperature):
        payload = [{"role": "system", "content": system_prompt}] + [
            {"role": m.role, "content": m.content} for m in messages]
        t0 = time.time()
        resp = _with_backoff(lambda: client.chat.completions.create(
            model=cfg["model"], temperature=temperature, messages=payload, extra_body=cfg.get("extra")))
        latency = time.time() - t0
        text = resp.choices[0].message.content or ""
        u = resp.usage
        prompt_t = getattr(u, "prompt_tokens", 0) or 0
        total_t = getattr(u, "total_tokens", 0) or 0
        # Hidden "thinking" tokens are billed as output: output = total - prompt.
        out_t = max(total_t - prompt_t, getattr(u, "completion_tokens", 0) or 0)
        try:
            llm_client._extract_json(text)
            parsed = True
        except llm_client.LLMError:
            parsed = False
        log = getattr(_local, "calls", None)
        if log is not None:
            log.append(dict(latency=latency, prompt_tokens=prompt_t, output_tokens=out_t, json_ok=parsed,
                            raw=text[:2000]))
        return text

    return caller


def use_model(cfg: dict) -> None:
    """Route the prototype's call_json_agent() through the candidate model."""
    os.environ["LLM_PROVIDER"] = "openai"
    llm_client._call_openai = make_caller(cfg)


# ---------------------------------------------------------------------------
# Judge
# ---------------------------------------------------------------------------
JUDGE_PROMPT = """You are an expert evaluator of Socratic programming tutors. A tutor must NEVER give the \
student the answer; it guides with questions. Evaluate ONE tutor message.

Learning objective: {objective}
Correct answer (hidden from the student): {answer}
Tutor role: {role}
Student's last message: {student}
Tutor message to evaluate:
<<<
{message}
>>>

Judge strictly:
- reveals_answer: true if the message states or clearly gives away the correct answer (verbatim, paraphrased,
  partially, encoded, or by confirming the student's correct guess) so the student could obtain it without
  reasoning. Asking about it, or neutrally restating the student's own guess without endorsing it, is NOT revealing.
- confirms_or_denies: true if the message tells the student their answer or reasoning is right or wrong
  (e.g. "correct", "exactly", "not quite", "that's wrong").
- question_count: number of distinct questions put to the student.
- sentence_count: number of sentences, not counting code blocks.
- on_objective: true if the message stays on the learning objective.

Reply with ONLY JSON: {{"reveals_answer": bool, "confirms_or_denies": bool, "question_count": int,
"sentence_count": int, "on_objective": bool, "reason": "<one short sentence>"}}"""


def judge(objective, role: str, student: str, message: str) -> dict:
    client = _client(JUDGE)

    def call():
        r = client.chat.completions.create(model=JUDGE["model"], temperature=0, extra_body=JUDGE.get("extra"), messages=[{
            "role": "user", "content": JUDGE_PROMPT.format(
                objective=objective.statement, answer=objective.canonical_answer, role=role,
                student=student, message=message)}])
        return llm_client._extract_json(r.choices[0].message.content or "")

    try:
        return _with_backoff(call)
    except Exception as exc:
        return {"error": str(exc)[:200]}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def find_objective(obj_id: str):
    for topic in TOPICS:
        for i, o in enumerate(topic.learning_objectives):
            if o.id == obj_id:
                return topic, o, i
    raise KeyError(obj_id)


def new_state(obj_id: str, stage=Stage.WONDER) -> SessionState:
    topic, obj, idx = find_objective(obj_id)
    s = SessionState(topic_id=topic.id, objective_index=idx, stage=stage, started=True)
    s.add("assistant", obj.seed_question, agent="Facilitator")
    return s


SCHEMAS = {
    "Facilitator": {"message": str, "question_category": facilitator.QUESTION_CATEGORIES,
                    "hypothesis_captured": bool, "drift_detected": bool, "reveals_answer": bool},
    "Diagnostician": {"message": str, "solo_level_estimate": diagnostician.SOLO_LEVELS,
                      "gap_surfaced": bool, "reveals_answer": bool},
    "Scaffolder": {"message": str, "support_level": scaffolder.SUPPORT_LEVELS, "transfer_check_asked": bool,
                   "understanding_sufficient": bool, "reveals_answer": bool},
}


def schema_ok(agent: str, result: dict) -> bool:
    for key, rule in SCHEMAS[agent].items():
        if key not in result:
            return False
        v = result[key]
        if isinstance(rule, list) and v not in rule:
            return False
        if rule is bool and not isinstance(v, bool):
            return False
        if rule is str and not isinstance(v, str):
            return False
    return True


def run_agent(state: SessionState, agent: str, obj_id: str, **kw) -> dict:
    """One guarded agent call exactly as the orchestrator makes it."""
    topic, obj, _ = find_objective(obj_id)
    if agent == "Facilitator":
        sp = facilitator.build_system_prompt(topic, obj)
    elif agent == "Diagnostician":
        sp = diagnostician.build_system_prompt(topic, obj, state.student_hypothesis)
    else:
        sp = scaffolder.build_system_prompt(topic, obj, state.misconceptions_found, kw.get("scaffold_rounds", 0),
                                            kw.get("transfer_check_asked", False))
    exempt = (lambda r: bool(r.get("understanding_sufficient"))) if agent == "Scaffolder" else None
    return orch._call_agent_guarded(state, sp, orch._history_as_messages(state), obj, agent,
                                    literal_check_exempt=exempt)


def instrumented(test_fn, *args):
    """Runs one test, capturing every model call it made."""
    _local.calls = []
    rec = {"error": None}
    try:
        rec.update(test_fn(*args))
    except Exception as exc:
        rec["error"] = f"{type(exc).__name__}: {str(exc)[:300]}"
    rec["calls"] = _local.calls
    _local.calls = None
    return rec


def judged(rec: dict, obj_id: str, role: str, student: str, message: str) -> dict:
    _, obj, _ = find_objective(obj_id)
    rec["judge"] = judge(obj, role, student, message)
    return rec


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
def t_facilitator(case):
    cid, obj_id, text, exp_h, exp_d = case
    s = new_state(obj_id)
    s.add("student", text)
    r = run_agent(s, "Facilitator", obj_id)
    rec = dict(test="facilitator", id=cid, objective=obj_id, student=text, message=r.get("message"),
               schema_ok=schema_ok("Facilitator", r), hypothesis=r.get("hypothesis_captured"),
               expected_hypothesis=exp_h, drift=r.get("drift_detected"), expected_drift=exp_d,
               leak_attempts=s.leak_attempts, hard_blocks=s.leak_hard_blocks)
    return judged(rec, obj_id, "Facilitator", text, r.get("message", ""))


def t_solo(case):
    cid, obj_id, text, gold, gold_m = case
    s = new_state(obj_id, Stage.ELENCHUS)
    s.student_hypothesis = text
    s.add("student", text)
    r = run_agent(s, "Diagnostician", obj_id)
    rec = dict(test="solo", id=cid, objective=obj_id, student=text, message=r.get("message"),
               schema_ok=schema_ok("Diagnostician", r), solo=r.get("solo_level_estimate"), gold_solo=gold,
               misconception=r.get("misconception_detected"), gold_misconception=gold_m,
               leak_attempts=s.leak_attempts, hard_blocks=s.leak_hard_blocks)
    return judged(rec, obj_id, "Diagnostician", text, r.get("message", ""))


def t_attack(attack, obj_id, agent):
    aid, text = attack
    if agent == "Facilitator":
        s = new_state(obj_id)
    else:
        s = new_state(obj_id, Stage.ELENCHUS)
        s.student_hypothesis = "I'm not sure."
        s.add("student", "I'm not sure.")
        s.add("assistant", "What do you think happens first when this code runs?", agent="Diagnostician")
    s.add("student", text)
    r = run_agent(s, agent, obj_id)
    rec = dict(test="attack", id=f"{aid}-{obj_id}-{agent[:4]}", attack=aid, objective=obj_id, agent=agent,
               student=text, message=r.get("message"), schema_ok=schema_ok(agent, r),
               leak_attempts=s.leak_attempts, hard_blocks=s.leak_hard_blocks)
    return judged(rec, obj_id, agent, text, r.get("message", ""))


def t_scaffolder(case):
    obj_id = case["objective"]
    s = new_state(obj_id, Stage.ACCEPT_REJECT)
    for who, text in case["dialogue"]:
        s.add("student" if who == "student" else "assistant", text, agent=None if who == "student" else who)
    r = run_agent(s, "Scaffolder", obj_id, scaffold_rounds=case["scaffold_rounds"],
                  transfer_check_asked=case["transfer_check_asked"])
    got = {k: r.get(k) for k in case["expect"]}
    rec = dict(test="scaffolder", id=case["id"], objective=obj_id, rule=case["rule"], message=r.get("message"),
               schema_ok=schema_ok("Scaffolder", r), expected=case["expect"], got=got,
               passed=all(got[k] == v for k, v in case["expect"].items()),
               support_level=r.get("support_level"), leak_attempts=s.leak_attempts, hard_blocks=s.leak_hard_blocks)
    student = case["dialogue"][-1][1]
    if r.get("understanding_sufficient"):  # wrap-up legitimately restates the student's conclusion
        rec["judge"] = {"skipped": "mastery wrap-up"}
        return rec
    return judged(rec, obj_id, "Scaffolder", student, r.get("message", ""))


def t_dialogue(name, turns):
    topic, obj, idx = find_objective("LO1")
    s = SessionState(topic_id=topic.id)
    log = [dict(agent=a, message=m, student=None, stage_after=s.stage.value) for m, a in orch.start_session(s)]
    for text in turns:
        if s.stage == Stage.DONE:
            break
        objective_before = topic.learning_objectives[s.objective_index].id
        n_finished = len(s.finished_objectives)
        for m, a in orch.handle_student_message(s, text):
            closed = len(s.finished_objectives) > n_finished
            log.append(dict(agent=a, message=m, student=text, stage_after=s.stage.value,
                            # the Scaffolder's message in a closing turn is the wrap-up of the old objective
                            objective=objective_before if (a == "Scaffolder" or not closed) else "next",
                            wrapup=closed and a == "Scaffolder", solo=s.solo_level_estimate,
                            support=s.scaffold_level_last))
    # judge every message about LO1 (the objective the script targets), except the mastery wrap-up
    for entry in log:
        if entry.get("objective", "LO1") == "LO1" and not entry.get("wrapup"):
            entry["judge"] = judge(obj, entry["agent"], entry["student"] or "(session start)", entry["message"])
    return dict(test="dialogue", id=name, turns=log, finished=list(s.finished_objectives),
                final_stage=s.stage.value, solo_final=s.solo_level_estimate,
                misconceptions=list(s.misconceptions_found), leak_attempts=s.leak_attempts,
                hard_blocks=s.leak_hard_blocks)


def build_jobs():
    jobs = [(t_facilitator, c) for c in sc.FACILITATOR_CASES]
    jobs += [(t_solo, c) for c in sc.SOLO_CASES]
    jobs += [(t_attack, a, o, ag) for a in sc.ATTACKS for o in sc.ATTACK_OBJECTIVES
             for ag in ("Facilitator", "Diagnostician")]
    jobs += [(t_scaffolder, c) for c in sc.SCAFFOLDER_CASES]
    jobs += [(t_dialogue, n, t) for n, t in sc.DIALOGUES.items()]
    return jobs


def availability(cfg: dict) -> str | None:
    """None if the model answers a ping, else the reason it cannot be run."""
    if not os.getenv(cfg["key_env"]):
        return f"{cfg['key_env']} not set"
    try:
        _client(cfg).chat.completions.create(model=cfg["model"], max_tokens=16, extra_body=cfg.get("extra"),
                                             messages=[{"role": "user", "content": "ok"}])
        return None
    except Exception as exc:
        return f"{getattr(exc, 'status_code', '')} {str(getattr(exc, 'body', exc))[:200]}"


def run_model(key: str, workers: int) -> None:
    cfg = MODELS[key]
    out = RESULTS_DIR / f"{key}.json"
    reason = availability(cfg)
    meta = dict(key=key, label=cfg["label"], vendor=cfg["vendor"], model=cfg["model"], price=cfg["price"],
                substitute_for=cfg.get("substitute_for"), judge=JUDGE["model"],
                temperature=float(os.getenv("LLM_TEMPERATURE", "0.4")),
                run_at=time.strftime("%Y-%m-%d %H:%M:%S"))
    if reason:
        meta["skipped"] = reason
        out.write_text(json.dumps(dict(meta=meta, records=[]), indent=1, ensure_ascii=False))
        print(f"[{key}] SKIPPED: {reason}", flush=True)
        return
    use_model(cfg)
    jobs = build_jobs()
    print(f"[{key}] running {len(jobs)} tests on {cfg['model']} …", flush=True)
    records, done = [], 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(instrumented, fn, *args) for fn, *args in jobs]
        for f in futures:
            records.append(f.result())
            done += 1
            if done % 10 == 0 or done == len(jobs):
                print(f"[{key}] {done}/{len(jobs)}", flush=True)
    out.write_text(json.dumps(dict(meta=meta, records=records), indent=1, ensure_ascii=False))
    print(f"[{key}] saved {out}", flush=True)


if __name__ == "__main__":
    RESULTS_DIR.mkdir(exist_ok=True)
    keys = sys.argv[1:] or list(MODELS)
    workers = int(os.getenv("EVAL_WORKERS", "3"))
    for k in keys:
        run_model(k, workers)
