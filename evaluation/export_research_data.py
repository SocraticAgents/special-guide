"""
Anonymised research export (thesis Section 3.6).

The only supported route for data to leave the study database: writes CSV
files keyed by participant code (P01, P02, ...) and never writes the name or
the student ID. Accounts without a stored consent version are excluded.

Run from the code/ directory:
    python -m evaluation.export_research_data [output_dir]
"""
from __future__ import annotations

import csv
import json
import sqlite3
import sys
from pathlib import Path

from socratic_agent import db

QUERIES = {
    "sessions": """
        SELECT st.participant_code, se.session_id, se.topic, se.started_at, se.ended_at, se.status
        FROM sessions se JOIN students st ON st.student_id = se.student_id
        WHERE st.consent_version IS NOT NULL ORDER BY st.participant_code, se.started_at""",
    "turns": """
        SELECT st.participant_code, t.session_id, t.turn_index, t.role, t.agent, t.content, t.created_at
        FROM turns t JOIN sessions se ON se.session_id = t.session_id
        JOIN students st ON st.student_id = se.student_id
        WHERE st.consent_version IS NOT NULL ORDER BY t.session_id, t.turn_index, t.id""",
    "snapshots": """
        SELECT st.participant_code, sn.session_id, sn.turn_index, sn.stage, sn.objective_id,
               sn.solo_level_estimate, sn.misconceptions_json, sn.diagnostic_evidence,
               sn.scaffold_level_last, sn.elenchus_rounds, sn.scaffold_rounds, sn.transfer_check_asked,
               sn.finished_objectives_json, sn.not_mastered_json, sn.question_category, sn.drift_detected,
               sn.leak_attempts, sn.leak_hard_blocks, sn.gate_rejections, sn.support_violations
        FROM snapshots sn JOIN sessions se ON se.session_id = sn.session_id
        JOIN students st ON st.student_id = se.student_id
        WHERE st.consent_version IS NOT NULL ORDER BY sn.session_id, sn.turn_index, sn.id""",
    "llm_calls": """
        SELECT st.participant_code, c.session_id, c.turn_index, c.provider, c.model, c.prompt_tokens,
               c.completion_tokens, c.latency_ms, c.ok
        FROM llm_calls c JOIN sessions se ON se.session_id = c.session_id
        JOIN students st ON st.student_id = se.student_id
        WHERE st.consent_version IS NOT NULL ORDER BY c.session_id, c.id""",
}


def _write(path: Path, header: list[str], rows: list[list]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)
    print(f"wrote {path}")


def _export_learner_model(conn: sqlite3.Connection, out_dir: Path) -> None:
    """Learner-model exports.

    objective_outcomes.csv — one row per objective: mastered vs closed_at_cap (never merged).
    solo_labelling.csv — every LLM SOLO estimate next to the student response it rated, with
    an empty human_solo column for the human rater(s) (DD2: compare with rubric-based human
    labels and report disagreements). The LLM column is an estimate, not ground truth.
    """
    conn.row_factory = sqlite3.Row
    latest: dict[str, sqlite3.Row] = {}
    for row in conn.execute(
        "SELECT sn.*, st.participant_code FROM snapshots sn "
        "JOIN sessions se ON se.session_id = sn.session_id "
        "JOIN students st ON st.student_id = se.student_id "
        "WHERE st.consent_version IS NOT NULL ORDER BY sn.session_id, sn.turn_index, sn.id"
    ):
        latest[row["session_id"]] = row

    outcome_rows, solo_rows = [], []
    for session_id, snap in latest.items():
        for r in json.loads(snap["objective_records_json"] or "[]"):
            outcome_rows.append([
                snap["participant_code"], session_id, r["design_id"], r["objective_id"], r["status"],
                r["entry_solo"], r["exit_solo"], r["peak_solo"], r["solo_gain"], r["elenchus_exit"],
                "|".join(r["support_sequence"]), int(r["transfer_asked"]), "|".join(r["misconceptions"]),
                r["student_turns"],
            ])
        turns = {
            t["turn_index"]: t for t in conn.execute(
                "SELECT turn_index, role, content FROM turns WHERE session_id = ?", (session_id,)
            )
        }
        for obs in json.loads(snap["solo_trajectory_json"] or "[]"):
            idx = obs["turn_index"] - 1
            while idx >= 0 and idx in turns and turns[idx]["role"] != "student":
                idx -= 1
            student_text = turns[idx]["content"] if idx in turns else ""
            solo_rows.append([
                snap["participant_code"], session_id, obs["turn_index"], obs["objective_id"], obs["agent"],
                student_text, obs["level"], obs["movement"], obs["source"], "",
            ])

    _write(out_dir / "objective_outcomes.csv",
           ["participant_code", "session_id", "design_id", "objective_id", "status", "entry_solo",
            "exit_solo", "peak_solo", "solo_gain_llm_estimate", "elenchus_exit", "support_sequence",
            "transfer_asked", "misconceptions", "student_turns"], outcome_rows)
    _write(out_dir / "solo_labelling.csv",
           ["participant_code", "session_id", "turn_index", "objective_id", "rated_by_agent",
            "student_response", "llm_solo_estimate", "llm_movement", "source", "human_solo"], solo_rows)


def export(out_dir: Path) -> None:
    db.init_db()
    out_dir.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db.DB_PATH)
    try:
        for name, query in QUERIES.items():
            cursor = conn.execute(query)
            path = out_dir / f"{name}.csv"
            with path.open("w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([c[0] for c in cursor.description])
                writer.writerows(cursor)
            print(f"wrote {path}")
        _export_learner_model(conn, out_dir)
    finally:
        conn.close()
    print("Transcripts are free text: read them once before sharing (Sec 3.6) — students may name themselves.")


def export_zip_bytes() -> bytes:
    """Same anonymised export, packed as an in-memory .zip (used by the Teacher Dashboard download)."""
    import io
    import tempfile
    import zipfile

    with tempfile.TemporaryDirectory() as tmp:
        out_dir = Path(tmp)
        export(out_dir)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for path in sorted(out_dir.glob("*.csv")):
                zf.write(path, arcname=path.name)
    return buf.getvalue()


if __name__ == "__main__":
    export(Path(sys.argv[1]) if len(sys.argv) > 1 else Path("evaluation/export"))
