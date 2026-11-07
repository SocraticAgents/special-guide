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

## V1 verification tests

`tests/test_v1_verification.py` reproduces the deterministic checks of thesis Table 4.28
(T01–T18) with the LLM replaced by a scripted stub, plus the V1.1 acceptance tests from
Table 4.29 (whole-token leak matching, mastery gate incl. justified transfer, not-mastered
recording, SOLO rated by the Curator, support starting at hint and rising one level at a time),
answer separation (Table 4.A) and consent/participant codes (Sec 3.6):

```bash
python -m unittest tests.test_v1_verification -v
```

`python -m evaluation.export_research_data` writes the anonymised CSV export (participant
code only, no name or student ID; accounts without a stored consent version are excluded).

## V1 learner model, honest claims, design-matrix verification

V1 implements the Part A design matrix (DD1–DD6) and keeps three claims honest in code:

| Claim | What the code actually does | Where |
|---|---|---|
| SOLO level | An **LLM estimate** of one response (Diagnostician in Elenchus, Curator during support), stored with `source="llm_estimate"`. There is no trained SOLO classifier. Only the *movement* between two estimates (up / jump_up / stable / down) is computed in code. | `learner_model.py`, `state.record_solo` |
| Scaffolding | The Curator **chooses** the support level (prompt). The orchestrator **bounds** it: first move = hint; rise at most one level; fade one level on a turn whose own SOLO estimate went up. Rules informed by ZPD/fading — not a ZPD measurement. Breaches are regenerated once, then counted (`support_violations`, `fade_violations`). | `learner_model.support_ceiling`, `orchestrator._scaffolder_turn` |
| Mastery | Every objective ends **MASTERED** (transfer question asked earlier + justified relational-or-higher transfer answer) or **CLOSED_AT_CAP** (support round limit; *not* mastery, shown to the student as "parked"). The two are never merged in the UI, dashboard or export. | `learner_model.ObjectiveRecord`, `orchestrator._close_objective` |

Objectives carry their thesis Table 4.2 IDs (`design_id`, LO1–LO11). The design matrix lives in
`socratic_agent/design_matrix.py`; a test checks that every test it names exists.

**Student progress and motivation (DD7 / FR13).** `socratic_agent/progress.py` turns the stored
objective records into a feedback card when an objective closes, seven milestones that reward
learning behaviour (never speed), a session summary, the **My Progress** page
(`pages/0_My_Progress.py`) and one suggested next step, including a one-objective retry of a
parked objective. All of it is template-based — no LLM call — so it cannot leak an answer, and
mastered and parked are always shown separately.

**Demo mode.** `SOCRATIC_AGENT_DEMO=1` replays the scripted walkthrough through the real
orchestrator instead of calling the LLM (Loops topic; a "Play scripted walkthrough" button
appears in the sidebar). Use it with a throw-away `SOCRATIC_AGENT_DB`, never the pilot database.

**Thesis documents** (`thesis_docs/`): `make_figures.py` (Figure 4.2 and Part B figures),
`take_screenshots.py` (headless Chrome against demo mode), `build_chapter4.py` (merges the
hand-written design in `writting/Chapter 4.docx` with the generated implementation sections into
`writting/Chapter 4 - System Design and Initial Results.docx`, formatted to the Research Office
guidelines; refuses to build if any test fails), `apply_part_a_corrections.py` and `add_hypotheses.py` (one-off
records of edits made to the Word drafts).

Full thesis draft (`writting/Socratic_Agent_Revised_Draft_2026-11-07.docx`), in order:
1. `build_chapter4.py` – rebuild Chapter 4 (Harvard citations, guideline format);
2. `merge_into_draft.py` – replace Chapter 4 in the draft (needs `pip install docxcompose`; when re-running,
   first restore `thesis_docs/backups/draft.before-ch4-merge.docx`);
3. `format_draft.py` – format the whole draft to the guidelines, add missing captions, fill the table
   of contents and lists (page numbers measured with LibreOffice; update fields in Word after edits)
   and add the Harvard reference list from `references.py` (when re-running, first restore
   `thesis_docs/backups/draft.before-format.docx`).

```
python -m unittest tests.test_v1_verification tests.test_v1_design tests.test_v1_progress -v   # 68 tests, no API key needed
python -m evaluation.walkthrough      # one complete scripted scenario through the real orchestrator
python -m evaluation.export_research_data   # + objective_outcomes.csv, solo_labelling.csv
python -m evaluation.solo_agreement evaluation/export/solo_labelling.csv   # DD2: LLM vs human SOLO labels
```

## Setup

```bash
cd socratic-agent
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in credentials for your chosen LLM_PROVIDER (anthropic | openai | openrouter | gemini)
streamlit run app.py
```

`LLM_PROVIDER=openrouter` uses OpenRouter's OpenAI-compatible endpoint (works with any
model slug it hosts, e.g. `anthropic/claude-sonnet-4.5`) — see `.env.example`.

`LLM_PROVIDER=gemini` uses Google's OpenAI-compatible Gemini endpoint with `GEMINI_API_KEY`;
the model is set by `GEMINI_MODEL` (default `gemini-2.5-flash`).

**If you edit anything under `socratic_agent/` while the app is already running**,
fully restart `streamlit run app.py` (Ctrl+C, then rerun) rather than relying on
Streamlit's save-triggered rerun — its autoreload doesn't reliably reinitialize a
package module that's already been imported, only the top-level script.

## Deploying (Streamlit Community Cloud)

Vercel can't host this app: Streamlit needs a long-running server with WebSockets, and
SQLite needs a writable disk.

1. At share.streamlit.io → **New app** → repo `SocraticAgents/special-guide`, branch `main`,
   main file `app.py`. Under **Advanced settings**, pick Python 3.13.
2. Paste the keys from `.streamlit/secrets.toml.example` (with real values) into **Secrets**.
3. Deploy. Dependencies come from `requirements.txt`.

**Data caveat:** the SQLite file (`data/socratic_agent.db`) starts empty on Cloud and is
**wiped on every restart or redeploy**. Use Cloud for demos only. For real study data,
host on a service with a persistent disk (e.g. Render: start command
`streamlit run app.py --server.port $PORT --server.address 0.0.0.0`, plus
`SOCRATIC_AGENT_DB=/var/data/socratic_agent.db` pointing at the mounted disk).

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
