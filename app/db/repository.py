import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


DB_PATH = Path("data/agent.db")


def get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(r["name"] == column for r in rows)


def init_db() -> None:
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS todos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task TEXT NOT NULL,
                done INTEGER NOT NULL DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS evaluations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_name TEXT NOT NULL,
                student_code TEXT,
                mode TEXT NOT NULL,
                score REAL NOT NULL,
                max_score REAL NOT NULL,
                feedback TEXT NOT NULL,
                code_transcription TEXT NOT NULL,
                strengths_json TEXT NOT NULL,
                improvements_json TEXT NOT NULL,
                rubric_breakdown_json TEXT NOT NULL,
                rubric_text TEXT NOT NULL,
                image_filename TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        if not _column_exists(conn, "evaluations", "activity_name"):
            conn.execute(
                "ALTER TABLE evaluations ADD COLUMN activity_name TEXT NOT NULL DEFAULT 'Actividad no definida'"
            )
        if not _column_exists(conn, "evaluations", "semester"):
            conn.execute(
                "ALTER TABLE evaluations ADD COLUMN semester TEXT NOT NULL DEFAULT 'Semestre no definido'"
            )
        conn.commit()


def save_message(role: str, content: str) -> None:
    with get_conn() as conn:
        conn.execute("INSERT INTO messages(role, content) VALUES(?, ?)", (role, content))
        conn.commit()


def search_messages(query: str, limit: int = 5) -> List[Tuple[int, str, str, str]]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT id, role, content, created_at
            FROM messages
            WHERE content LIKE ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (f"%{query}%", limit),
        ).fetchall()
    return [(r["id"], r["role"], r["content"], r["created_at"]) for r in rows]


def add_todo(task: str) -> int:
    with get_conn() as conn:
        cur = conn.execute("INSERT INTO todos(task, done) VALUES(?, 0)", (task,))
        conn.commit()
        return int(cur.lastrowid)


def list_todos(limit: int = 20) -> List[Tuple[int, str, int, str]]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT id, task, done, created_at
            FROM todos
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [(r["id"], r["task"], r["done"], r["created_at"]) for r in rows]


def save_evaluation(record: Dict[str, Any]) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO evaluations (
                student_name, student_code, mode, score, max_score, feedback,
                code_transcription, strengths_json, improvements_json,
                rubric_breakdown_json, rubric_text, image_filename, activity_name, semester
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(record.get("student_name", "")).strip(),
                str(record.get("student_code", "")).strip(),
                str(record.get("mode", "")).strip(),
                float(record.get("score", 0)),
                float(record.get("max_score", 0)),
                str(record.get("feedback", "")),
                str(record.get("code_transcription", "")),
                str(record.get("strengths_json", "[]")),
                str(record.get("improvements_json", "[]")),
                str(record.get("rubric_breakdown_json", "[]")),
                str(record.get("rubric_text", "")),
                str(record.get("image_filename", "")),
                str(record.get("activity_name", "Actividad no definida")).strip(),
                str(record.get("semester", "Semestre no definido")).strip(),
            ),
        )
        conn.commit()
        return int(cur.lastrowid)


def list_evaluations(student_name: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
    with get_conn() as conn:
        if student_name and student_name.strip():
            rows = conn.execute(
                """
                SELECT id, student_name, student_code, activity_name, semester, mode, score, max_score, created_at
                FROM evaluations
                WHERE student_name LIKE ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (f"%{student_name.strip()}%", limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT id, student_name, student_code, activity_name, semester, mode, score, max_score, created_at
                FROM evaluations
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
    return [dict(r) for r in rows]


def list_student_summary(student_name: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    with get_conn() as conn:
        if student_name and student_name.strip():
            rows = conn.execute(
                """
                SELECT
                    student_name,
                    COALESCE(NULLIF(student_code, ''), '-') AS student_code,
                    COUNT(*) AS evaluations,
                    ROUND(AVG(score), 2) AS avg_score,
                    ROUND(MAX(score), 2) AS best_score,
                    MAX(created_at) AS last_date
                FROM evaluations
                WHERE student_name LIKE ?
                GROUP BY student_name, student_code
                ORDER BY last_date DESC
                LIMIT ?
                """,
                (f"%{student_name.strip()}%", limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT
                    student_name,
                    COALESCE(NULLIF(student_code, ''), '-') AS student_code,
                    COUNT(*) AS evaluations,
                    ROUND(AVG(score), 2) AS avg_score,
                    ROUND(MAX(score), 2) AS best_score,
                    MAX(created_at) AS last_date
                FROM evaluations
                GROUP BY student_name, student_code
                ORDER BY last_date DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
    return [dict(r) for r in rows]


def list_student_alerts(student_name: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    with get_conn() as conn:
        if student_name and student_name.strip():
            rows = conn.execute(
                """
                SELECT student_name, COALESCE(NULLIF(student_code, ''), '-') AS student_code,
                       score, max_score, activity_name, semester, created_at
                FROM evaluations
                WHERE student_name LIKE ?
                ORDER BY student_name, datetime(created_at) ASC, id ASC
                """,
                (f"%{student_name.strip()}%",),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT student_name, COALESCE(NULLIF(student_code, ''), '-') AS student_code,
                       score, max_score, activity_name, semester, created_at
                FROM evaluations
                ORDER BY student_name, datetime(created_at) ASC, id ASC
                """
            ).fetchall()

    grouped: Dict[str, List[sqlite3.Row]] = {}
    for row in rows:
        key = f"{row['student_name']}::{row['student_code']}"
        grouped.setdefault(key, []).append(row)

    alerts: List[Dict[str, Any]] = []
    for items in grouped.values():
        if len(items) < 3:
            continue
        last_three = items[-3:]
        scores = [float(r["score"]) for r in last_three]
        non_improving = scores[-1] <= scores[-2] <= scores[-3] or scores[-1] <= scores[0]
        drop = round(scores[-1] - scores[0], 2)
        if non_improving:
            latest = last_three[-1]
            alerts.append(
                {
                    "student_name": latest["student_name"],
                    "student_code": latest["student_code"],
                    "semester": latest["semester"],
                    "last_activity": latest["activity_name"],
                    "recent_scores": " -> ".join(f"{s:.2f}" for s in scores),
                    "trend_delta": drop,
                    "alert": "Sin mejora en ultimas 3 actividades",
                }
            )

    alerts.sort(key=lambda x: (x["student_name"], x["semester"]))
    return alerts[:limit]

