from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime

MONTHS_ID = {
    1: "Januari",
    2: "Februari",
    3: "Maret",
    4: "April",
    5: "Mei",
    6: "Juni",
    7: "Juli",
    8: "Agustus",
    9: "September",
    10: "Oktober",
    11: "November",
    12: "Desember",
}

ONES_ID = {
    0: "nol",
    1: "satu",
    2: "dua",
    3: "tiga",
    4: "empat",
    5: "lima",
    6: "enam",
    7: "tujuh",
    8: "delapan",
    9: "sembilan",
    10: "sepuluh",
    11: "sebelas",
}


def parse_date_id(text: str) -> date:
    value = text.strip()
    for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    raise ValueError("Gunakan format tanggal DD-MM-YYYY, contoh 11-06-2026.")


def format_date_id(value: date) -> str:
    return f"{value.day} {MONTHS_ID[value.month]} {value.year}"


def format_month_year_id(value: date) -> str:
    return f"{MONTHS_ID[value.month]} {value.year}"


def format_issue_date_id(value: date, day_blank: bool = False) -> str:
    if day_blank:
        return f"Tanggal dikosongkan — {format_month_year_id(value)}"
    return format_date_id(value)


def format_date_range_id(start: date, end: date) -> str:
    if start == end:
        return format_date_id(start)
    if start.year == end.year and start.month == end.month:
        return f"{start.day}-{end.day} {MONTHS_ID[start.month]} {start.year}"
    if start.year == end.year:
        return (
            f"{start.day} {MONTHS_ID[start.month]}-"
            f"{end.day} {MONTHS_ID[end.month]} {start.year}"
        )
    return f"{format_date_id(start)}-{format_date_id(end)}"


def number_to_words_id(number: int) -> str:
    if number < 0:
        return "minus " + number_to_words_id(abs(number))
    if number <= 11:
        return ONES_ID[number]
    if number < 20:
        return number_to_words_id(number - 10) + " belas"
    if number < 100:
        tens, remainder = divmod(number, 10)
        result = number_to_words_id(tens) + " puluh"
        if remainder:
            result += " " + number_to_words_id(remainder)
        return result
    if number < 200:
        remainder = number - 100
        return "seratus" + (" " + number_to_words_id(remainder) if remainder else "")
    if number < 1000:
        hundreds, remainder = divmod(number, 100)
        result = number_to_words_id(hundreds) + " ratus"
        if remainder:
            result += " " + number_to_words_id(remainder)
        return result
    return str(number)


def build_purpose_text(
    destination: str,
    activity: str,
    start_date: date,
    end_date: date,
) -> str:
    duration = (end_date - start_date).days + 1
    text = f"Perjalanan Dinas ke {destination} dalam rangka {activity.strip()}"
    text += (
        f" selama {duration} ({number_to_words_id(duration)}) hari "
        f"pada tanggal {format_date_range_id(start_date, end_date)}."
    )
    return text


def slugify(value: str, max_length: int = 70) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    ascii_value = re.sub(r"[^A-Za-z0-9]+", "_", ascii_value).strip("_")
    return ascii_value[:max_length] or "SURAT_TUGAS"


def clean_rank(value: str) -> str:
    return re.sub(r"\s*/\s*", "/", value.strip())
