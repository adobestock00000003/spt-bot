from __future__ import annotations

import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
DATA_DIR = Path(os.getenv("DATA_DIR", str(BASE_DIR / "data"))).resolve()
TEMPLATE_PATH = Path(
    os.getenv("TEMPLATE_PATH", str(BASE_DIR / "templates" / "SPT_template.docx"))
).resolve()
TNDE_TEMPLATE_PATH = Path(
    os.getenv("TNDE_TEMPLATE_PATH", str(BASE_DIR / "templates" / "SPT_template_TNDE.docx"))
).resolve()
EMPLOYEE_SEED_PATH = BASE_DIR / "seeds" / "employees.json"
APP_TIMEZONE = os.getenv("APP_TIMEZONE", "Asia/Jakarta")


def parse_admin_ids() -> set[int]:
    raw = os.getenv("ADMIN_IDS", "")
    result: set[int] = set()
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        try:
            result.add(int(item))
        except ValueError:
            pass
    return result


ADMIN_IDS = parse_admin_ids()
DATABASE_PATH = DATA_DIR / "spt_bot.db"
DOCUMENTS_DIR = DATA_DIR / "documents"

DEFAULT_NUMBER_PREFIX = "000.1.2.3"
DEFAULT_NUMBER_SUFFIX = "118.4"
DEFAULT_ISSUE_CITY = "Surabaya"

DEFAULT_LEGAL_BASES = [
    "Peraturan Daerah Provinsi Jawa Timur Nomor 6 Tahun 2025 Tanggal 31 Desember 2025 tentang Anggaran Pendapatan dan Belanja Provinsi Jawa Timur Tahun Anggaran 2026;",
    "Peraturan Gubernur Jawa Timur Nomor 41 Tahun 2025 Tanggal 31 Desember 2025 tentang Penjabaran Perubahan Anggaran Pendapatan dan Belanja Daerah Provinsi Jawa Timur Tahun Anggaran 2026;",
    "Dokumen Pelaksanaan Anggaran (DPA) Nomor: DPA/A.1/2.22.3.26.0.00.03.0000/001/2026 Tanggal 1 Januari 2026.",
]

DEFAULT_OPTIONAL_LEGAL_BASE_4 = "Undangan dari Pemerintah Kabupaten Ponorogo;"


def ensure_directories() -> None:
    """Create persistent data folders before the bot/database starts."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)
