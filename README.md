# Socratic-Agent — Prototype

A lightweight, prompt-engineered multi-agent Socratic tutor spanning five introductory
Python topics, implementing the architecture from the BSc thesis proposal *"Socratic-Agent:
A Multi-Agent Framework to Enhance Student Learning Through Guided Thinking"* (Objective 2).

## The three agents

| Agent | Socratic stage owned | Theory grounding |
|---|---|---|
| **Socratic Facilitator** | Wonder / Hypothesis — opens the dialogue, picks the question category, elicits a clear hypothesis, guards against topic drift | Socratic Method, Constructivism |
| **Cognitive Diagnostic** | Elenchus — actively probes the hypothesis against a curated misconception bank, estimates SOLO level | SOLO Taxonomy, Cognitive Diagnostic Theory |
| **Scaffolding Curator** | Acceptance/Rejection + Action — calibrates hint / sub-question / worked example, judges when to stop | Zone of Proximal Development, Cognitive Load Theory |

All three call the **same external LLM API** with a different role-specific system
prompt each (no separate fine-tuned models — see `socratic_agent/llm_client.py`).

## Topic catalog (`socratic_agent/topic_bank.py`)

Five topics spanning Beginner → Intermediate, sourced from w3schools.com/python's own
tutorial ordering, so the pilot can be tried by students at different levels rather than
on one fixed topic:

| Topic | Difficulty | Objectives | Misconceptions |
|---|---|---|---|
| 🧮 Variables & Data Types | Beginner | 2 | 4 |
| 🔀 Conditionals (If/Elif/Else) | Beginner | 2 | 4 |
| 🔁 Loops (for/while) | Intermediate | 3 | 6 |
| 📋 Lists | Intermediate | 2 | 4 |
| 🧩 Functions | Intermediate | 2 | 4 |

Each `Topic` bundles its own learning objectives (with a seed question, canonical
answer, and protected literals for the leak guard below) and its own misconception
bank — the small, hand-curated grounding reference the Diagnostic agent uses to
*actively* test for known misconceptions, consistent with the proposal's lightweight,
prompt-only scope (no retrieval/RAG). Adding a 6th topic means adding one more `Topic`
entry — the agents and orchestrator code don't change.

**A safety note for anyone adding a topic**: `topic_bank.py` validates at import time
that no `protected_literals` entry appears verbatim inside its own `seed_question` —
this is exactly the bug class hit during development (a Conditionals objective's leak
guard false-triggered because the answer literal `"A"` was also literally present in
the seed code snippet, so the Facilitator quoting the code back looked like a leak).
If you add a topic with this collision, the app will fail fast at startup with a clear
error rather than silently mis-firing the guard during a real session.

## Orchestration

A stage-driven state machine (`socratic_agent/orchestrator.py`) picks exactly one
active agent per student turn:

```
WONDER  ──hypothesis_captured──►  ELENCHUS  ──gap_surfaced / 3 rounds──►  ACCEPT_REJECT
                                                                               │
                          transfer check asked, then passed / 3 rounds        │
                                                                               ▼
                                          next learning objective (→ WONDER) or DONE
```

Each agent returns structured JSON (message + control fields); the orchestrator reads
those fields to decide the transition. Round caps exist so the Diagnostician/Scaffolder
can't loop forever — a direct, lightweight answer to the cognitive-overload risk noted
in the proposal's literature review.

**Mastery gate**: the Scaffolder cannot set `understanding_sufficient=true` on the first
correct answer alone. It must first pose one transfer/generalization question ("what if
the condition were `i <= 3` instead?") and see the student apply the same reasoning to
that new case — ties the mastery claim to SOLO's Extended Abstract level rather than to
self-judgment on the original example, which the student could get right by pattern-
matching rather than genuine understanding. Tracked via `state.transfer_check_asked`.

**Answer-leakage guard** (`socratic_agent/guardrail.py`): every agent message passes
through two checks before it ever reaches the student — the agent's own `reveals_answer`
self-report (checked against the objective's canonical answer, catches paraphrase) and a
deterministic literal-string safety net (catches verbatim slips the self-check misses).
Either tripping triggers one regeneration with a repair instruction; if that also leaks,
a hardcoded fallback line is substituted rather than ever showing the leak. Session-wide
`leak_attempts` / `leak_hard_blocks` counters are persisted and shown both live (sidebar)
and aggregated across all students (Teacher Dashboard) — a direct evaluation metric
mirroring the "leak-robustness" methodology in the proposal's own literature review
(Table 2.5.2.1).

## Setup

```bash
cd socratic-agent
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in credentials for your chosen LLM_PROVIDER (anthropic | openai | openrouter)
streamlit run app.py
```

`LLM_PROVIDER=openrouter` uses OpenRouter's OpenAI-compatible endpoint (works with any
model slug it hosts, e.g. `anthropic/claude-sonnet-4.5`) — see `.env.example`.

**If you edit anything under `socratic_agent/` while the app is already running**,
fully restart `streamlit run app.py` (Ctrl+C, then rerun) rather than relying on
Streamlit's save-triggered rerun — its autoreload doesn't reliably reinitialize a
package module that's already been imported, only the top-level script.

## Student flow: sign up / sign in → pick a topic → chat

`app.py` opens on **Sign in** / **Sign up** tabs. Sign-up takes a full name, student ID,
and password (PBKDF2-hashed + salted in SQLite via `socratic_agent/db.py` — never
plaintext; proportionate security for a pilot prototype, not a production auth claim —
no rate limiting or password reset flow) plus a consent checkbox, satisfying the
informed-consent step in the proposal's ethical considerations (Sec 3.6). After signing
in, the student sees a **topic picker** (one card per topic, with difficulty badge and
a short "how this tutor works" explainer) before any tutoring starts. From the chat
screen's sidebar, **Change topic** returns to the picker without signing out, and
**New session** restarts the same topic.

Every turn and every agent's diagnostic snapshot (stage, SOLO estimate, misconceptions
found, support level) is written to the local SQLite database as the session runs, in
addition to being shown live in the sidebar's **Diagnostic panel**.

## Teacher Dashboard (`pages/1_Teacher_Dashboard.py`)

A second page (Streamlit's multipage convention — it appears automatically in the
sidebar nav) reads that same SQLite data across *all* students/sessions:

- Overview metrics (students, sessions, completion rate), a **sessions-by-topic** bar
  chart (shows whether the topic variety is actually being exercised across the pilot),
  and a bar chart of which misconceptions came up most often across everyone — the
  single most useful "which concepts trip students up" signal for an instructor.
- A student table + drill-down: pick a student → pick one of their sessions (labeled
  with its topic) → see the SOLO-level trajectory over the session as a line chart, the
  misconceptions surfaced, objectives completed, and the full transcript.
- Gated by a shared passcode (`TEACHER_PASSCODE` in `.env`, default `teach123` — change
  it before running a real pilot). This is a shared passcode, not per-teacher accounts;
  proportionate for a ~10-20 student BSc pilot, not meant as production-grade auth.
- **Anonymization**: the student table hides names behind a "Show names" toggle
  (default off) and shows student ID instead, so a glance at the dashboard — or a
  screenshot of it — stays consistent with the proposal's anonymization commitment.
  Prefer `student_id` over `name` in anything exported from here for the thesis writeup.

## Project layout

```
app.py                          Streamlit chat UI: auth gate + topic picker + chat + live diagnostic panel
pages/
  1_Teacher_Dashboard.py        Cross-student/session/topic dashboard (reads the same SQLite DB)
socratic_agent/
  llm_client.py                 Provider-agnostic call (anthropic/openai/openrouter) + JSON parsing/repair
  guardrail.py                  Answer-leakage guard: self-report + literal safety net
  db.py                         SQLite persistence: students (with password hashing), sessions, turns, snapshots
  state.py                      SessionState (topic_id, stage, round caps, transfer-check flag)
  topic_bank.py                 5-topic catalog: learning objectives (+ canonical answers), misconception banks
  orchestrator.py               The stage state machine described above, topic-aware
  prompts/
    _shared.py                  Leak self-check instruction shared by all three agents
    facilitator.py              System prompt + schema for the Facilitator
    diagnostician.py            System prompt + schema for the Diagnostician
    scaffolder.py                System prompt + schema for the Scaffolder
```

## What's deliberately out of scope (for now)

- The Phase 3 pre/post quiz and Likert/open-ended feedback survey are separate
  instruments per the proposal and are not built into this app yet.
- No retrieval/RAG — each topic's misconception bank in `topic_bank.py` is small and
  hand-curated, consistent with the proposal's lightweight, prompt-only scope.
- The teacher passcode is not real per-teacher authentication (shared passcode, no
  accounts) — deliberately proportionate to a pilot-scale BSc prototype. Student
  accounts *do* use salted+hashed passwords (see above), but still without rate
  limiting or password reset — adequate for a pilot, not a production claim.

## Known open question (flagged in the proposal itself, Sec 2.9.2)

How reliably the Diagnostician infers *implicit* misconceptions (rather than ones the
student states outright) is treated as an open empirical question to observe during
Phase 3, not an assumption baked into the design.
