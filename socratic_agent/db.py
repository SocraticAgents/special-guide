"""
Local persistence for Socratic-Agent sessions (SQLite, stdlib only).

This backs two things you asked for: the real-time diagnostic panel reads
straight from the in-memory SessionState (no DB needed for that), but the
teacher-facing dashboard (pages/1_Teacher_Dashboard.py) and any later Phase 3
analysis need a record that survives across students/sessions/app restarts —
that's what this module provides. SQLite keeps this a zero-service, "runs on
a laptop" setup, consistent with the proposal's tooling scope (Sec 3.5).

Ethical note (Sec 3.6): student name + ID are recorded only so a real pilot
session can be re-associated with informed consent while data collection is
happening. Everything downstream of here (the dashboard, any analysis
export) should prefer `student_id` over `name` and drop `name` before data
leaves the researcher's machine, to honor the proposal's anonymization
commitment. The dashboard's student table hides names behind an explicit
toggle for this reason.

Passwords are salted + PBKDF2-hashed (never stored in plaintext) via
`create_student`/`verify_student`, which is proportionate security for a
pilot-scale prototype guarding low-stakes accounts — not a claim of
production-grade auth (no rate limiting, no password reset flow, etc.).
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import uuid
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timezone

_DEFAULT_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "socratic_agent.db")
DB_PATH = os.getenv("SOCRATIC_AGENT_DB", _DEFAULT_DB_PATH)

_PBKDF2_ITERATIONS = 200_000

# Version of the consent text shown at sign-up (app.py). Bump it whenever that text changes,
# so every stored record is traceable to the exact wording that authorised it (Sec 3.6).
CONSENT_VERSION = "v1.0"

# Columns added after the first pilot build; init_db() adds them to an existing database.
_MIGRATIONS = {
    "students": {
        "participant_code": "TEXT",
        "consent_version": "TEXT",
        "consented_at": "TEXT",
    },
    "snapshots": {
        "not_mastered_json": "TEXT NOT NULL DEFAULT '[]'",
        "gate_rejections": "INTEGER NOT NULL DEFAULT 0",
        "support_violations": "INTEGER NOT NULL DEFAULT 0",
        "question_category": "TEXT",
        "drift_detected": "INTEGER NOT NULL DEFAULT 0",
        "diagnostic_evidence": "TEXT",
        # V1 learner model (socratic_agent/learner_model.py)
        "solo_source": "TEXT",
        "solo_movement": "TEXT",
        "support_ceiling": "TEXT",
        "fade_violations": "INTEGER NOT NULL DEFAULT 0",
        "objective_records_json": "TEXT NOT NULL DEFAULT '[]'",
        "solo_trajectory_json": "TEXT NOT NULL DEFAULT '[]'",
    },
}


class AuthError(RuntimeError):
    """Raised for sign-up/sign-in failures (student ID taken, wrong password, etc.)."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def _connect():
    os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS students (
                student_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                password_salt TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                student_id TEXT NOT NULL REFERENCES students(student_id),
                topic TEXT NOT NULL,
                started_at TEXT NOT NULL,
                ended_at TEXT,
                status TEXT NOT NULL DEFAULT 'in_progress'
            );

            CREATE TABLE IF NOT EXISTS turns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL REFERENCES sessions(session_id),
                turn_index INTEGER NOT NULL,
                role TEXT NOT NULL,
                agent TEXT,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL REFERENCES sessions(session_id),
                turn_index INTEGER NOT NULL,
                stage TEXT NOT NULL,
                objective_id TEXT,
                solo_level_estimate TEXT,
                misconceptions_json TEXT NOT NULL,
                scaffold_level_last TEXT,
                elenchus_rounds INTEGER NOT NULL,
                scaffold_rounds INTEGER NOT NULL,
                finished_objectives_json TEXT NOT NULL,
                leak_attempts INTEGER NOT NULL DEFAULT 0,
                leak_hard_blocks INTEGER NOT NULL DEFAULT 0,
                transfer_check_asked INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );

            -- One row per model call: token usage for the cost estimate (Sec 3.5) and
            -- latency for the responsiveness criterion (Table 4.30).
            CREATE TABLE IF NOT EXISTS llm_calls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL REFERENCES sessions(session_id),
                turn_index INTEGER NOT NULL,
                provider TEXT,
                model TEXT,
                prompt_tokens INTEGER,
                completion_tokens INTEGER,
                latency_ms INTEGER NOT NULL,
                ok INTEGER NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )
        for table, columns in _MIGRATIONS.items():
            existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
            for column, ddl in columns.items():
                if column not in existing:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")
        # Backfill participant codes for accounts created before codes existed.
        for row in conn.execute(
            "SELECT student_id FROM students WHERE participant_code IS NULL ORDER BY created_at"
        ).fetchall():
            conn.execute(
                "UPDATE students SET participant_code = ? WHERE student_id = ?",
                (_next_participant_code(conn), row["student_id"]),
            )


def _next_participant_code(conn) -> str:
    """Sequential code (P01, P02, ...) — the only participant label used in analysis (Sec 3.6)."""
    n = conn.execute("SELECT COUNT(*) AS c FROM students WHERE participant_code IS NOT NULL").fetchone()["c"]
    return f"P{n + 1:02d}"


def _hash_password(password: str, salt: bytes | None = None) -> tuple[str, str]:
    """Returns (salt_hex, hash_hex). Salted PBKDF2 — proportionate to a BSc pilot
    prototype (not a production auth system, see README), but never plaintext."""
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ITERATIONS)
    return salt.hex(), digest.hex()


def create_student(student_id: str, name: str, password: str) -> None:
    """Sign-up: creates a new student. Raises AuthError if student_id is already taken.

    Only called after the consent box is ticked, so the consent version and time are
    stored with the account.
    """
    salt_hex, hash_hex = _hash_password(password)
    now = _now()
    try:
        with _connect() as conn:
            conn.execute(
                "INSERT INTO students (student_id, name, password_hash, password_salt, created_at, "
                "participant_code, consent_version, consented_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (student_id, name, hash_hex, salt_hex, now, _next_participant_code(conn),
                 CONSENT_VERSION, now),
            )
    except sqlite3.IntegrityError as exc:
        raise AuthError(f"Student ID '{student_id}' is already registered.") from exc


def verify_student(student_id: str, password: str) -> str:
    """Sign-in: returns the student's name on success. Raises AuthError on failure."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT name, password_hash, password_salt FROM students WHERE student_id = ?",
            (student_id,),
        ).fetchone()
    if row is None:
        raise AuthError("No account found with that student ID.")
    _, expected_hash = _hash_password(password, bytes.fromhex(row["password_salt"]))
    if not hmac.compare_digest(expected_hash, row["password_hash"]):
        raise AuthError("Incorrect password.")
    return row["name"]


def create_session(student_id: str, topic: str) -> str:
    session_id = str(uuid.uuid4())
    with _connect() as conn:
        conn.execute(
            "INSERT INTO sessions (session_id, student_id, topic, started_at, status) "
            "VALUES (?, ?, ?, ?, 'in_progress')",
            (session_id, student_id, topic, _now()),
        )
    return session_id


def end_session(session_id: str, status: str = "completed") -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE sessions SET ended_at = ?, status = ? WHERE session_id = ?",
            (_now(), status, session_id),
        )


def log_turn(session_id: str, turn_index: int, role: str, agent: str | None, content: str) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT INTO turns (session_id, turn_index, role, agent, content, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (session_id, turn_index, role, agent, content, _now()),
        )


def log_snapshot(session_id: str, turn_index: int, state) -> None:
    from socratic_agent.topic_bank import get_topic, objective_by_index

    topic = get_topic(state.topic_id)
    objective = objective_by_index(topic, state.objective_index) if topic else None
    with _connect() as conn:
        conn.execute(
            "INSERT INTO snapshots (session_id, turn_index, stage, objective_id, "
            "solo_level_estimate, misconceptions_json, scaffold_level_last, elenchus_rounds, "
            "scaffold_rounds, finished_objectives_json, leak_attempts, leak_hard_blocks, "
            "transfer_check_asked, not_mastered_json, gate_rejections, support_violations, "
            "question_category, drift_detected, diagnostic_evidence, solo_source, solo_movement, "
            "support_ceiling, fade_violations, objective_records_json, solo_trajectory_json, "
            "created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                session_id,
                turn_index,
                state.stage.value,
                objective.id if objective else None,
                state.solo_level_estimate,
                json.dumps(state.misconceptions_found),
                state.scaffold_level_last,
                state.elenchus_rounds,
                state.scaffold_rounds,
                json.dumps(state.finished_objectives),
                state.leak_attempts,
                state.leak_hard_blocks,
                int(state.transfer_check_asked),
                json.dumps(state.not_mastered_objectives),
                state.gate_rejections,
                state.support_violations,
                state.question_category_last,
                int(state.drift_detected_last),
                state.diagnostic_evidence,
                "llm_estimate" if state.solo_level_estimate else None,
                state.solo_movement_last,
                state.support_ceiling_last,
                state.fade_violations,
                json.dumps([r.as_dict() for r in state.objective_records]),
                json.dumps([asdict(o) for o in state.solo_trajectory]),
                _now(),
            ),
        )


def log_llm_calls(session_id: str, turn_index: int, calls: list[dict]) -> None:
    if not calls:
        return
    with _connect() as conn:
        conn.executemany(
            "INSERT INTO llm_calls (session_id, turn_index, provider, model, prompt_tokens, "
            "completion_tokens, latency_ms, ok, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
            [
                (session_id, turn_index, c["provider"], c["model"], c["prompt_tokens"],
                 c["completion_tokens"], c["latency_ms"], int(c["ok"]), _now())
                for c in calls
            ],
        )


# --- read helpers for the teacher dashboard -----------------------------------------

def list_students():
    with _connect() as conn:
        return conn.execute(
            "SELECT s.student_id, s.name, s.participant_code, s.consent_version, s.created_at, "
            "COUNT(se.session_id) AS n_sessions, "
            "MAX(se.started_at) AS last_active "
            "FROM students s LEFT JOIN sessions se ON se.student_id = s.student_id "
            "GROUP BY s.student_id ORDER BY last_active DESC"
        ).fetchall()


def list_sessions(student_id: str | None = None):
    with _connect() as conn:
        if student_id:
            return conn.execute(
                "SELECT * FROM sessions WHERE student_id = ? ORDER BY started_at DESC", (student_id,)
            ).fetchall()
        return conn.execute("SELECT * FROM sessions ORDER BY started_at DESC").fetchall()


def get_transcript(session_id: str):
    with _connect() as conn:
        return conn.execute(
            "SELECT * FROM turns WHERE session_id = ? ORDER BY turn_index, id", (session_id,)
        ).fetchall()


def get_snapshots(session_id: str):
    with _connect() as conn:
        return conn.execute(
            "SELECT * FROM snapshots WHERE session_id = ? ORDER BY turn_index, id", (session_id,)
        ).fetchall()


def misconception_frequency() -> dict[str, int]:
    """How many distinct sessions each misconception showed up in (session-level, not per-turn)."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT session_id, misconceptions_json FROM snapshots ORDER BY session_id, turn_index"
        ).fetchall()
    latest_per_session: dict[str, list[str]] = {}
    for row in rows:
        latest_per_session[row["session_id"]] = json.loads(row["misconceptions_json"])
    counts: dict[str, int] = {}
    for mids in latest_per_session.values():
        for mid in mids:
            counts[mid] = counts.get(mid, 0) + 1
    return counts


def leak_stats() -> dict[str, int]:
    """Answer-leakage guard outcomes, aggregated from each session's latest snapshot.

    total_attempts: how many times, across all sessions, an agent's draft was caught
    by the guard (self-report or literal match) and had to be regenerated.
    total_hard_blocks: how many of those the regenerated retry ALSO leaked, requiring
    the hardcoded fallback message.
    sessions_with_leak_attempt: how many distinct sessions had at least one such catch —
    the closest analogue to the "leak rate" metric used in the literature (Table 2.5.2.1).
    """
    with _connect() as conn:
        rows = conn.execute(
            "SELECT session_id, leak_attempts, leak_hard_blocks FROM snapshots "
            "ORDER BY session_id, turn_index"
        ).fetchall()
    latest_per_session: dict[str, sqlite3.Row] = {}
    for row in rows:
        latest_per_session[row["session_id"]] = row
    total_attempts = sum(r["leak_attempts"] for r in latest_per_session.values())
    total_hard_blocks = sum(r["leak_hard_blocks"] for r in latest_per_session.values())
    sessions_with_attempt = sum(1 for r in latest_per_session.values() if r["leak_attempts"] > 0)
    return {
        "total_attempts": total_attempts,
        "total_hard_blocks": total_hard_blocks,
        "sessions_with_leak_attempt": sessions_with_attempt,
        "total_sessions": len(latest_per_session),
    }


def _latest_snapshots(conn) -> dict[str, sqlite3.Row]:
    rows = conn.execute("SELECT * FROM snapshots ORDER BY session_id, turn_index, id").fetchall()
    latest: dict[str, sqlite3.Row] = {}
    for row in rows:
        latest[row["session_id"]] = row
    return latest


def objective_stats() -> dict[str, int]:
    """Mastered vs. closed-at-the-cap objectives, plus hard-block counters (Table 4.E)."""
    with _connect() as conn:
        latest = _latest_snapshots(conn)
    closed = sum(len(json.loads(r["finished_objectives_json"])) for r in latest.values())
    not_mastered = sum(len(json.loads(r["not_mastered_json"] or "[]")) for r in latest.values())
    return {
        "closed": closed,
        "mastered": closed - not_mastered,
        "not_mastered": not_mastered,
        "gate_rejections": sum(r["gate_rejections"] for r in latest.values()),
        "support_violations": sum(r["support_violations"] for r in latest.values()),
        "fade_violations": sum((r["fade_violations"] or 0) for r in latest.values()),
    }


def objective_outcomes() -> list[dict]:
    """One row per objective attempted, from each session's latest snapshot.

    status is "mastered" (gate passed) or "closed_at_cap" (NOT mastery) or "in_progress".
    entry/exit/peak SOLO are LLM estimates (source "llm_estimate"), not classifier output.
    """
    with _connect() as conn:
        latest = _latest_snapshots(conn)
        topics = {r["session_id"]: r["topic"] for r in conn.execute("SELECT session_id, topic FROM sessions")}
    rows = []
    for session_id, snap in latest.items():
        for rec in json.loads(snap["objective_records_json"] or "[]"):
            rows.append({"session_id": session_id, "topic": topics.get(session_id), **rec})
    return rows


def student_objective_records(student_id: str) -> list[dict]:
    """Every objective record of one student across sessions, oldest session first.

    Feeds the student's own progress page (socratic_agent/progress.py).
    """
    with _connect() as conn:
        sessions = conn.execute(
            "SELECT session_id, topic, started_at FROM sessions WHERE student_id = ? ORDER BY started_at, rowid",
            (student_id,),
        ).fetchall()
        out = []
        for s in sessions:
            snap = conn.execute(
                "SELECT objective_records_json FROM snapshots WHERE session_id = ? ORDER BY turn_index DESC, id DESC LIMIT 1",
                (s["session_id"],),
            ).fetchone()
            if snap is None:
                continue
            for rec in json.loads(snap["objective_records_json"] or "[]"):
                out.append({"session_id": s["session_id"], "topic": s["topic"], "started_at": s["started_at"], **rec})
    return out


def usage_stats() -> dict[str, float | int | None]:
    """Token usage and latency across all recorded model calls (Sec 3.5, Table 4.30)."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT session_id, prompt_tokens, completion_tokens, latency_ms, ok FROM llm_calls"
        ).fetchall()
    if not rows:
        return {"calls": 0}
    latencies = sorted(r["latency_ms"] for r in rows if r["ok"])
    sessions = {r["session_id"] for r in rows}
    prompt = sum(r["prompt_tokens"] or 0 for r in rows)
    completion = sum(r["completion_tokens"] or 0 for r in rows)
    return {
        "calls": len(rows),
        "failed_calls": sum(1 for r in rows if not r["ok"]),
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "sessions": len(sessions),
        "prompt_tokens_per_session": prompt / len(sessions),
        "completion_tokens_per_session": completion / len(sessions),
        "median_call_latency_ms": latencies[len(latencies) // 2] if latencies else None,
    }


def completion_stats() -> tuple[int, int]:
    """Returns (total_sessions, completed_sessions)."""
    with _connect() as conn:
        total = conn.execute("SELECT COUNT(*) AS c FROM sessions").fetchone()["c"]
        completed = conn.execute(
            "SELECT COUNT(*) AS c FROM sessions WHERE status = 'completed'"
        ).fetchone()["c"]
    return total, completed
