from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from config import (
    ADMIN_IDS,
    DATABASE_PATH,
    DEFAULT_ISSUE_CITY,
    DEFAULT_LEGAL_BASES,
    DEFAULT_NUMBER_PREFIX,
    DEFAULT_NUMBER_SUFFIX,
    EMPLOYEE_SEED_PATH,
)


class Database:
    def __init__(self, path: Path = DATABASE_PATH) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def initialize(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id INTEGER NOT NULL UNIQUE,
                    display_name TEXT NOT NULL DEFAULT '',
                    role TEXT NOT NULL CHECK(role IN ('admin','operator')) DEFAULT 'operator',
                    active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS employees (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_order INTEGER NOT NULL DEFAULT 0,
                    name TEXT NOT NULL,
                    gender TEXT NOT NULL DEFAULT '',
                    position TEXT NOT NULL,
                    rank TEXT NOT NULL DEFAULT '',
                    identifier TEXT NOT NULL DEFAULT '',
                    active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS legal_bases (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sort_order INTEGER NOT NULL,
                    text TEXT NOT NULL,
                    active INTEGER NOT NULL DEFAULT 1,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS letters (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    letter_uuid TEXT NOT NULL UNIQUE,
                    sequence_number INTEGER NOT NULL,
                    full_number TEXT NOT NULL,
                    destination TEXT NOT NULL,
                    activity TEXT NOT NULL,
                    event_name TEXT NOT NULL DEFAULT '',
                    purpose_text TEXT NOT NULL,
                    start_date TEXT NOT NULL,
                    end_date TEXT NOT NULL,
                    duration_days INTEGER NOT NULL,
                    issue_date TEXT NOT NULL,
                    issue_day_blank INTEGER NOT NULL DEFAULT 0,
                    include_signature INTEGER NOT NULL DEFAULT 0,
                    employee_snapshot_json TEXT NOT NULL,
                    legal_snapshot_json TEXT NOT NULL,
                    created_by INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT '',
                    version INTEGER NOT NULL DEFAULT 1,
                    parent_letter_id INTEGER,
                    status TEXT NOT NULL DEFAULT 'active',
                    docx_path TEXT NOT NULL DEFAULT '',
                    pdf_path TEXT NOT NULL DEFAULT '',
                    FOREIGN KEY(created_by) REFERENCES users(id),
                    FOREIGN KEY(parent_letter_id) REFERENCES letters(id)
                );

                CREATE INDEX IF NOT EXISTS idx_letters_created_at ON letters(created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_letters_sequence ON letters(sequence_number);
                CREATE INDEX IF NOT EXISTS idx_employees_active_name ON employees(active, name);
                """
            )

        self._migrate_letter_completion_columns()
        self._seed_settings()
        self._seed_employees()
        self._seed_legal_bases()
        self._migrate_legacy_default_legal_bases()
        self._migrate_ali_afandi_position_casing()
        self._migrate_ismadi_rank()
        self._migrate_chandra_rank()
        self._sync_admins_from_env()

    def _migrate_letter_completion_columns(self) -> None:
        """Add completion/re-export fields without deleting existing Railway data."""
        with self.connect() as conn:
            columns = {row["name"] for row in conn.execute("PRAGMA table_info(letters)").fetchall()}
            if "issue_day_blank" not in columns:
                conn.execute(
                    "ALTER TABLE letters ADD COLUMN issue_day_blank INTEGER NOT NULL DEFAULT 0"
                )
            if "include_signature" not in columns:
                conn.execute(
                    "ALTER TABLE letters ADD COLUMN include_signature INTEGER NOT NULL DEFAULT 0"
                )
            if "updated_at" not in columns:
                conn.execute(
                    "ALTER TABLE letters ADD COLUMN updated_at TEXT NOT NULL DEFAULT ''"
                )
            conn.execute(
                "UPDATE letters SET updated_at=created_at WHERE updated_at='' OR updated_at IS NULL"
            )

    def _seed_settings(self) -> None:
        defaults = {
            "number_prefix": DEFAULT_NUMBER_PREFIX,
            "number_suffix": DEFAULT_NUMBER_SUFFIX,
            "issue_city": DEFAULT_ISSUE_CITY,
            "last_sequence": "0",
        }
        with self.connect() as conn:
            for key, value in defaults.items():
                conn.execute(
                    "INSERT OR IGNORE INTO settings(key, value) VALUES (?, ?)",
                    (key, value),
                )

    def _seed_employees(self) -> None:
        with self.connect() as conn:
            count = conn.execute("SELECT COUNT(*) FROM employees").fetchone()[0]
            if count:
                return
            data = json.loads(EMPLOYEE_SEED_PATH.read_text(encoding="utf-8"))
            now = datetime.now().isoformat(timespec="seconds")
            conn.executemany(
                """
                INSERT INTO employees(
                    source_order, name, gender, position, rank, identifier,
                    active, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        item.get("order", 0),
                        item["name"],
                        item.get("gender", ""),
                        item["position"],
                        item.get("rank", ""),
                        item.get("identifier", ""),
                        1 if item.get("active", True) else 0,
                        now,
                        now,
                    )
                    for item in data
                ],
            )

    def _seed_legal_bases(self) -> None:
        with self.connect() as conn:
            count = conn.execute("SELECT COUNT(*) FROM legal_bases").fetchone()[0]
            if count:
                return
            now = datetime.now().isoformat(timespec="seconds")
            conn.executemany(
                "INSERT INTO legal_bases(sort_order, text, active, updated_at) VALUES (?, ?, 1, ?)",
                [(i, text, now) for i, text in enumerate(DEFAULT_LEGAL_BASES, start=1)],
            )

    def _migrate_legacy_default_legal_bases(self) -> None:
        """Update untouched v1 default legal bases to the 2026 template defaults.

        Existing databases are preserved when the admin has customized the legal bases.
        """
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT id, sort_order, text, active FROM legal_bases ORDER BY sort_order, id"
            ).fetchall()
            texts = [str(row["text"]) for row in rows]
            looks_like_v1_defaults = (
                len(rows) == 5
                and any("Nomor 9 Tahun 2024" in text for text in texts)
                and any("Nomor : 88 Tahun 2023" in text or "Nomor 88 Tahun 2023" in text for text in texts)
                and any("DPA /A.1/2." in text or "DPA /A.1/2" in text for text in texts)
            )
            if not looks_like_v1_defaults:
                return
            conn.execute("DELETE FROM legal_bases")
            now = datetime.now().isoformat(timespec="seconds")
            conn.executemany(
                "INSERT INTO legal_bases(sort_order, text, active, updated_at) VALUES (?, ?, 1, ?)",
                [(i, text, now) for i, text in enumerate(DEFAULT_LEGAL_BASES, start=1)],
            )

    def _migrate_ali_afandi_position_casing(self) -> None:
        """Keep Ali Afandi's job-title capitalization in the requested official form.

        This also updates existing Railway databases, not only fresh seed data.
        """
        requested = "Kepala Bidang Pemasaran dan Kelembagaan Parekraf"
        now = datetime.now().isoformat(timespec="seconds")
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE employees
                SET position=?, updated_at=?
                WHERE UPPER(name) LIKE 'ALI AFANDI%'
                  AND position <> ?
                """,
                (requested, now, requested),
            )

    def _migrate_ismadi_rank(self) -> None:
        """Update Ismadi's rank in fresh and existing Railway databases."""
        requested = "Penata Tk. I (III/d)"
        now = datetime.now().isoformat(timespec="seconds")
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE employees
                SET rank=?, updated_at=?
                WHERE UPPER(name) LIKE 'ISMADI%'
                  AND rank <> ?
                """,
                (requested, now, requested),
            )

    def _migrate_chandra_rank(self) -> None:
        """Update Chandra Nurhidayat's rank in fresh and existing Railway databases."""
        requested = "Penata Tk. I (III/d)"
        now = datetime.now().isoformat(timespec="seconds")
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE employees
                SET rank=?, updated_at=?
                WHERE UPPER(name) LIKE 'CHANDRA NURHIDAYAT%'
                  AND rank <> ?
                """,
                (requested, now, requested),
            )

    def _sync_admins_from_env(self) -> None:
        for telegram_id in ADMIN_IDS:
            self.upsert_user(telegram_id, f"Admin {telegram_id}", "admin", active=True)

    # Users
    def upsert_user(
        self,
        telegram_id: int,
        display_name: str,
        role: str = "operator",
        active: bool = True,
    ) -> int:
        now = datetime.now().isoformat(timespec="seconds")
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO users(telegram_id, display_name, role, active, created_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(telegram_id) DO UPDATE SET
                    display_name=excluded.display_name,
                    role=excluded.role,
                    active=excluded.active
                """,
                (telegram_id, display_name, role, int(active), now),
            )
            row = conn.execute(
                "SELECT id FROM users WHERE telegram_id=?", (telegram_id,)
            ).fetchone()
            return int(row["id"])

    def get_user_by_telegram_id(self, telegram_id: int) -> sqlite3.Row | None:
        with self.connect() as conn:
            return conn.execute(
                "SELECT * FROM users WHERE telegram_id=?", (telegram_id,)
            ).fetchone()

    def list_users(self) -> list[sqlite3.Row]:
        with self.connect() as conn:
            return conn.execute(
                "SELECT * FROM users ORDER BY role='admin' DESC, display_name COLLATE NOCASE"
            ).fetchall()

    def set_user_active(self, user_id: int, active: bool) -> None:
        with self.connect() as conn:
            conn.execute("UPDATE users SET active=? WHERE id=?", (int(active), user_id))

    # Employees
    def list_employees(
        self,
        active_only: bool = True,
        search: str | None = None,
    ) -> list[sqlite3.Row]:
        sql = "SELECT * FROM employees WHERE 1=1"
        params: list[Any] = []
        if active_only:
            sql += " AND active=1"
        if search:
            sql += " AND (name LIKE ? OR position LIKE ? OR identifier LIKE ?)"
            term = f"%{search}%"
            params.extend([term, term, term])
        sql += " ORDER BY source_order, name COLLATE NOCASE"
        with self.connect() as conn:
            return conn.execute(sql, params).fetchall()

    def get_employee(self, employee_id: int) -> sqlite3.Row | None:
        with self.connect() as conn:
            return conn.execute(
                "SELECT * FROM employees WHERE id=?", (employee_id,)
            ).fetchone()

    def add_employee(
        self,
        name: str,
        gender: str,
        position: str,
        rank: str,
        identifier: str,
    ) -> int:
        now = datetime.now().isoformat(timespec="seconds")
        with self.connect() as conn:
            max_order = conn.execute(
                "SELECT COALESCE(MAX(source_order), 0) FROM employees"
            ).fetchone()[0]
            cur = conn.execute(
                """
                INSERT INTO employees(
                    source_order, name, gender, position, rank, identifier,
                    active, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)
                """,
                (max_order + 1, name, gender, position, rank, identifier, now, now),
            )
            return int(cur.lastrowid)

    def update_employee(self, employee_id: int, **fields: str) -> None:
        allowed = {"name", "gender", "position", "rank", "identifier"}
        updates = {k: v for k, v in fields.items() if k in allowed}
        if not updates:
            return
        updates["updated_at"] = datetime.now().isoformat(timespec="seconds")
        assignments = ", ".join(f"{k}=?" for k in updates)
        values = list(updates.values()) + [employee_id]
        with self.connect() as conn:
            conn.execute(f"UPDATE employees SET {assignments} WHERE id=?", values)

    def set_employee_active(self, employee_id: int, active: bool) -> None:
        with self.connect() as conn:
            conn.execute(
                "UPDATE employees SET active=?, updated_at=? WHERE id=?",
                (int(active), datetime.now().isoformat(timespec="seconds"), employee_id),
            )

    # Legal bases
    def list_legal_bases(self, active_only: bool = True) -> list[sqlite3.Row]:
        sql = "SELECT * FROM legal_bases"
        if active_only:
            sql += " WHERE active=1"
        sql += " ORDER BY sort_order, id"
        with self.connect() as conn:
            return conn.execute(sql).fetchall()

    def update_legal_base(self, legal_id: int, text: str) -> None:
        with self.connect() as conn:
            conn.execute(
                "UPDATE legal_bases SET text=?, updated_at=? WHERE id=?",
                (text, datetime.now().isoformat(timespec="seconds"), legal_id),
            )

    def add_legal_base(self, text: str) -> int:
        with self.connect() as conn:
            max_order = conn.execute(
                "SELECT COALESCE(MAX(sort_order), 0) FROM legal_bases"
            ).fetchone()[0]
            cur = conn.execute(
                "INSERT INTO legal_bases(sort_order, text, active, updated_at) VALUES (?, ?, 1, ?)",
                (max_order + 1, text, datetime.now().isoformat(timespec="seconds")),
            )
            return int(cur.lastrowid)

    def set_legal_base_active(self, legal_id: int, active: bool) -> None:
        with self.connect() as conn:
            conn.execute(
                "UPDATE legal_bases SET active=?, updated_at=? WHERE id=?",
                (int(active), datetime.now().isoformat(timespec="seconds"), legal_id),
            )

    # Settings / numbering
    def get_setting(self, key: str, default: str = "") -> str:
        with self.connect() as conn:
            row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
            return str(row["value"]) if row else default

    def set_setting(self, key: str, value: str) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO settings(key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value
                """,
                (key, value),
            )

    def suggest_next_sequence(self) -> int:
        last_setting = int(self.get_setting("last_sequence", "0") or 0)
        with self.connect() as conn:
            row = conn.execute(
                "SELECT COALESCE(MAX(sequence_number), 0) AS n FROM letters"
            ).fetchone()
            last_db = int(row["n"])
        return max(last_setting, last_db) + 1

    def format_full_number(self, sequence_number: int | str, year: int) -> str:
        prefix = self.get_setting("number_prefix", DEFAULT_NUMBER_PREFIX)
        suffix = self.get_setting("number_suffix", DEFAULT_NUMBER_SUFFIX)
        return f"{prefix} / {sequence_number} / {suffix} / {year}"

    def format_blank_full_number(self, year: int) -> str:
        # Non-breaking spaces keep a visibly wide blank area in Word/PDF.
        return self.format_full_number("\u00A0" * 12, year)

    # Letters
    def create_letter(
        self,
        *,
        letter_uuid: str,
        sequence_number: int,
        full_number: str,
        destination: str,
        activity: str,
        event_name: str,
        purpose_text: str,
        start_date: str,
        end_date: str,
        duration_days: int,
        issue_date: str,
        issue_day_blank: bool = False,
        include_signature: bool = False,
        employees: list[dict[str, Any]],
        legal_bases: list[str],
        created_by_user_id: int,
        version: int = 1,
        parent_letter_id: int | None = None,
        docx_path: str = "",
        pdf_path: str = "",
    ) -> int:
        now = datetime.now().isoformat(timespec="seconds")
        with self.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO letters(
                    letter_uuid, sequence_number, full_number, destination, activity,
                    event_name, purpose_text, start_date, end_date, duration_days,
                    issue_date, issue_day_blank, include_signature,
                    employee_snapshot_json, legal_snapshot_json,
                    created_by, created_at, updated_at, version, parent_letter_id,
                    docx_path, pdf_path
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    letter_uuid,
                    sequence_number,
                    full_number,
                    destination,
                    activity,
                    event_name,
                    purpose_text,
                    start_date,
                    end_date,
                    duration_days,
                    issue_date,
                    int(bool(issue_day_blank)),
                    int(bool(include_signature)),
                    json.dumps(employees, ensure_ascii=False),
                    json.dumps(legal_bases, ensure_ascii=False),
                    created_by_user_id,
                    now,
                    now,
                    version,
                    parent_letter_id,
                    docx_path,
                    pdf_path,
                ),
            )
            conn.execute(
                """
                INSERT INTO settings(key, value) VALUES ('last_sequence', ?)
                ON CONFLICT(key) DO UPDATE SET value=
                    CASE
                        WHEN CAST(excluded.value AS INTEGER) > CAST(settings.value AS INTEGER)
                        THEN excluded.value ELSE settings.value END
                """,
                (str(sequence_number),),
            )
            return int(cur.lastrowid)

    def update_letter_paths(self, letter_id: int, docx_path: str, pdf_path: str) -> None:
        with self.connect() as conn:
            conn.execute(
                "UPDATE letters SET docx_path=?, pdf_path=?, updated_at=? WHERE id=?",
                (docx_path, pdf_path, datetime.now().isoformat(timespec="seconds"), letter_id),
            )

    def update_letter_completion(
        self,
        letter_id: int,
        *,
        sequence_number: int,
        full_number: str,
        issue_date: str,
        issue_day_blank: bool,
        include_signature: bool,
        version: int,
        docx_path: str,
        pdf_path: str,
    ) -> None:
        """Update the same stored letter after its number/date/signature is finalized.

        This intentionally does not create a new letter row, so the history count and
        the letter identity remain unchanged. The document version is incremented and
        the latest DOCX/PDF paths become the active files in history.
        """
        now = datetime.now().isoformat(timespec="seconds")
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE letters
                SET sequence_number=?, full_number=?, issue_date=?, issue_day_blank=?,
                    include_signature=?, version=?, docx_path=?, pdf_path=?, updated_at=?
                WHERE id=?
                """,
                (
                    int(sequence_number),
                    full_number,
                    issue_date,
                    int(bool(issue_day_blank)),
                    int(bool(include_signature)),
                    int(version),
                    docx_path,
                    pdf_path,
                    now,
                    int(letter_id),
                ),
            )
            if int(sequence_number) > 0:
                conn.execute(
                    """
                    INSERT INTO settings(key, value) VALUES ('last_sequence', ?)
                    ON CONFLICT(key) DO UPDATE SET value=
                        CASE
                            WHEN CAST(excluded.value AS INTEGER) > CAST(settings.value AS INTEGER)
                            THEN excluded.value ELSE settings.value END
                    """,
                    (str(sequence_number),),
                )

    def get_letter(self, letter_id: int) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT l.*, u.display_name AS creator_name
                FROM letters l
                JOIN users u ON u.id=l.created_by
                WHERE l.id=?
                """,
                (letter_id,),
            ).fetchone()
        if not row:
            return None
        item = dict(row)
        item["employees"] = json.loads(item.pop("employee_snapshot_json"))
        item["legal_bases"] = json.loads(item.pop("legal_snapshot_json"))
        return item

    def list_letters(self, limit: int = 10, search: str | None = None) -> list[sqlite3.Row]:
        sql = """
            SELECT l.id, l.sequence_number, l.full_number, l.destination, l.activity, l.event_name,
                   l.start_date, l.end_date, l.issue_date, l.issue_day_blank, l.version, l.created_at,
                   u.display_name AS creator_name
            FROM letters l
            JOIN users u ON u.id=l.created_by
            WHERE l.status='active'
        """
        params: list[Any] = []
        if search:
            sql += (
                " AND (l.full_number LIKE ? OR l.destination LIKE ? OR "
                "l.activity LIKE ? OR l.event_name LIKE ?)"
            )
            term = f"%{search}%"
            params.extend([term, term, term, term])
        sql += " ORDER BY l.created_at DESC, l.id DESC LIMIT ?"
        params.append(limit)
        with self.connect() as conn:
            return conn.execute(sql, params).fetchall()

    def statistics(self) -> dict[str, int]:
        with self.connect() as conn:
            letters = conn.execute("SELECT COUNT(*) FROM letters WHERE status='active'").fetchone()[0]
            employees = conn.execute("SELECT COUNT(*) FROM employees WHERE active=1").fetchone()[0]
            destinations = conn.execute(
                "SELECT COUNT(DISTINCT destination) FROM letters WHERE status='active'"
            ).fetchone()[0]
            users = conn.execute("SELECT COUNT(*) FROM users WHERE active=1").fetchone()[0]
        return {
            "letters": int(letters),
            "employees": int(employees),
            "destinations": int(destinations),
            "users": int(users),
        }
