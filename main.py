from __future__ import annotations

import asyncio
import html
import logging
import os
import uuid
from calendar import monthrange
from datetime import date
from pathlib import Path
from typing import Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from config import BOT_TOKEN, DATA_DIR, DOCUMENTS_DIR, DEFAULT_OPTIONAL_LEGAL_BASE_4
from database import Database
from services.document_service import (
    convert_docx_to_pdf,
    convert_tnde_docx_to_pdf,
    generate_docx,
    generate_tnde_docx,
)
from utils import (
    build_purpose_text,
    clean_rank,
    format_date_id,
    format_date_range_id,
    format_issue_date_id,
    format_month_year_id,
    parse_date_id,
)

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
)
logger = logging.getLogger("spt-bot")

db = Database()
PAGE_SIZE = 8


# ---------- Generic helpers ----------

def menu_button(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text, callback_data=data)


def esc(value: Any) -> str:
    return html.escape(str(value), quote=False)


def user_display_name(update: Update) -> str:
    user = update.effective_user
    if not user:
        return "Pengguna"
    return user.full_name or user.username or str(user.id)


def get_authorized_user(update: Update):
    user = update.effective_user
    if not user:
        return None
    row = db.get_user_by_telegram_id(user.id)
    if row and row["active"]:
        return row
    return None


def is_admin(update: Update) -> bool:
    row = get_authorized_user(update)
    return bool(row and row["role"] == "admin")


async def require_access(update: Update) -> Any | None:
    row = get_authorized_user(update)
    if row:
        return row
    telegram_id = update.effective_user.id if update.effective_user else "-"
    text = (
        "⛔ <b>Akses belum diberikan.</b>\n\n"
        f"Telegram ID Anda: <code>{telegram_id}</code>\n"
        "Minta admin menambahkan ID tersebut sebagai operator."
    )
    if update.callback_query:
        await update.callback_query.answer("Akses tidak tersedia.", show_alert=True)
    elif update.effective_message:
        await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML)
    return None


async def edit_or_reply(update: Update, text: str, keyboard: InlineKeyboardMarkup | None = None) -> None:
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        try:
            await query.edit_message_text(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
            return
        except Exception:
            pass
    if update.effective_message:
        await update.effective_message.reply_text(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)


def reset_flow(context: ContextTypes.DEFAULT_TYPE) -> None:
    for key in (
        "state",
        "draft",
        "pending",
        "employee_search",
        "edit_return",
        "edit_dates",
        "emp_edit_return",
        "edit_legal4_return",
    ):
        context.user_data.pop(key, None)


def main_menu_markup(admin: bool) -> InlineKeyboardMarkup:
    rows = [
        [menu_button("➕ Buat Surat Tugas", "create:start")],
        [
            menu_button("📋 Riwayat Surat", "history:list"),
            menu_button("👥 Data Pegawai", "employees:list:0"),
        ],
        [
            menu_button("📚 Dasar Hukum", "legal:list"),
            menu_button("🔢 Nomor Surat", "number:menu"),
        ],
        [menu_button("📊 Statistik", "stats:show")],
    ]
    if admin:
        rows.append([menu_button("⚙️ Kelola Pengguna", "admin:users")])
    return InlineKeyboardMarkup(rows)


async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = await require_access(update)
    if not user:
        return
    reset_flow(context)
    stats = db.statistics()
    text = (
        "📄 <b>BOT SURAT TUGAS</b>\n"
        "Bidang Pemasaran dan Kelembagaan Parekraf\n\n"
        f"Halo, <b>{esc(user_display_name(update))}</b>.\n"
        f"Surat tersimpan: <b>{stats['letters']}</b> • Pegawai aktif: <b>{stats['employees']}</b>"
    )
    await edit_or_reply(update, text, main_menu_markup(user["role"] == "admin"))


# ---------- Start / help ----------

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await show_main_menu(update, context)


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_access(update):
        return
    reset_flow(context)
    await update.effective_message.reply_text("✅ Proses dibatalkan.")
    await show_main_menu(update, context)


async def id_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if user:
        await update.effective_message.reply_text(f"Telegram ID Anda: {user.id}")


# ---------- Create letter ----------

def get_draft(context: ContextTypes.DEFAULT_TYPE) -> dict[str, Any]:
    draft = context.user_data.get("draft")
    if not isinstance(draft, dict):
        draft = {}
        context.user_data["draft"] = draft
    return draft


def selected_employee_ids(context: ContextTypes.DEFAULT_TYPE) -> list[int]:
    draft = get_draft(context)
    return [int(x) for x in draft.get("employee_ids", [])]


def set_selected_employee_ids(context: ContextTypes.DEFAULT_TYPE, ids: list[int]) -> None:
    get_draft(context)["employee_ids"] = ids


def employee_selection_markup(
    context: ContextTypes.DEFAULT_TYPE,
    page: int,
) -> tuple[str, InlineKeyboardMarkup]:
    search = context.user_data.get("employee_search")
    employees = db.list_employees(active_only=True, search=search)
    selected = set(selected_employee_ids(context))
    total_pages = max(1, (len(employees) + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))
    start = page * PAGE_SIZE
    current = employees[start : start + PAGE_SIZE]

    rows: list[list[InlineKeyboardButton]] = []
    for emp in current:
        checked = "✅" if emp["id"] in selected else "☐"
        label = f"{checked} {emp['name'][:37]}"
        rows.append([menu_button(label, f"create:emp:{emp['id']}:{page}")])

    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(menu_button("⬅️", f"create:emp_page:{page-1}"))
    nav.append(menu_button(f"{page+1}/{total_pages}", "noop"))
    if page < total_pages - 1:
        nav.append(menu_button("➡️", f"create:emp_page:{page+1}"))
    rows.append(nav)
    rows.append(
        [
            menu_button("🔎 Cari", "create:emp_search"),
            menu_button("🧹 Tampilkan Semua", "create:emp_clear_search"),
        ]
    )
    rows.append([menu_button(f"✅ Lanjut ({len(selected)} dipilih)", "create:emp_done")])
    rows.append([menu_button("❌ Batalkan", "create:cancel")])

    filter_text = f"\nFilter: <b>{esc(search)}</b>" if search else ""
    text = (
        "👥 <b>PILIH PEGAWAI</b>\n"
        "Pilih satu atau lebih pegawai. Tekan nama untuk mencentang/menghapus pilihan."
        f"{filter_text}\n\n"
        f"Terpilih: <b>{len(selected)}</b> pegawai"
    )
    return text, InlineKeyboardMarkup(rows)


async def create_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_access(update):
        return
    reset_flow(context)
    context.user_data["draft"] = {"employee_ids": [], "purpose_manual": False, "version": 1, "legal_base_4": None}
    text, keyboard = employee_selection_markup(context, 0)
    await edit_or_reply(update, text, keyboard)


async def create_employee_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE, employee_id: int, page: int) -> None:
    ids = selected_employee_ids(context)
    if employee_id in ids:
        ids.remove(employee_id)
    else:
        ids.append(employee_id)
    set_selected_employee_ids(context, ids)
    text, keyboard = employee_selection_markup(context, page)
    await edit_or_reply(update, text, keyboard)


async def create_employee_search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data["state"] = "create_employee_search"
    await edit_or_reply(
        update,
        "🔎 <b>Cari Pegawai</b>\n\nKetik nama, jabatan, atau NIP/NPPK yang ingin dicari.",
        InlineKeyboardMarkup([[menu_button("⬅️ Kembali", "create:emp_page:0")]]),
    )


async def create_employee_done(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    ids = selected_employee_ids(context)
    if not ids:
        await update.callback_query.answer("Pilih minimal satu pegawai.", show_alert=True)
        return
    if context.user_data.pop("emp_edit_return", False):
        await show_preview(update, context)
        return
    context.user_data["state"] = "create_destination"
    await edit_or_reply(
        update,
        "📍 <b>TUJUAN PERJALANAN</b>\n\nKetik tujuan, contoh:\n<code>Kabupaten Ponorogo</code>",
        InlineKeyboardMarkup([[menu_button("❌ Batalkan", "create:cancel")]]),
    )


async def ask_activity(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data["state"] = "create_activity"
    await update.effective_message.reply_text(
        "📝 <b>KEGIATAN</b>\n\nKetik kegiatan, contoh:\n"
        "<code>pendampingan dan pembuatan konten video KYAI LODRA</code>",
        parse_mode=ParseMode.HTML,
    )


async def ask_start_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data["state"] = "create_start_date"
    await update.effective_message.reply_text(
        "📅 <b>TANGGAL BERANGKAT</b>\n\nGunakan format <code>DD-MM-YYYY</code>.\nContoh: <code>11-06-2026</code>",
        parse_mode=ParseMode.HTML,
    )


async def ask_end_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data["state"] = "create_end_date"
    await update.effective_message.reply_text(
        "📅 <b>TANGGAL PULANG</b>\n\nGunakan format <code>DD-MM-YYYY</code>.",
        parse_mode=ParseMode.HTML,
    )


def issue_date_from_day(start_date: date, day: int) -> date:
    if day < 1:
        raise ValueError("Tanggal penetapan harus antara 1 dan 31.")
    try:
        return date(start_date.year, start_date.month, day)
    except ValueError as exc:
        last_day = monthrange(start_date.year, start_date.month)[1]
        raise ValueError(
            f"Tanggal penetapan tidak valid. Bulan {format_month_year_id(start_date)} hanya sampai tanggal {last_day}."
        ) from exc


def parse_issue_day_for_start(text: str, start_date: date) -> date:
    value = text.strip()
    if value.isdigit():
        day = int(value)
    else:
        # Tetap menerima format tanggal lengkap, tetapi bulan/tahun selalu
        # mengikuti jadwal berangkat sesuai aturan Surat Tugas.
        day = parse_date_id(value).day
    return issue_date_from_day(start_date, day)


def sync_issue_date_to_start(draft: dict[str, Any]) -> None:
    start_date = draft.get("start_date")
    if not isinstance(start_date, date):
        return
    if draft.get("issue_day_blank"):
        draft["issue_date"] = date(start_date.year, start_date.month, 1)
        return
    current = draft.get("issue_date")
    preferred_day = current.day if isinstance(current, date) else start_date.day
    last_day = monthrange(start_date.year, start_date.month)[1]
    draft["issue_date"] = date(
        start_date.year, start_date.month, min(preferred_day, last_day)
    )


def letter_year(draft: dict[str, Any]) -> int:
    start_date = draft.get("start_date")
    return start_date.year if isinstance(start_date, date) else date.today().year


async def ask_issue_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    draft = get_draft(context)
    start_date = draft["start_date"]
    context.user_data["state"] = "create_issue_date"
    await update.effective_message.reply_text(
        "🖊 <b>TANGGAL PENETAPAN SURAT</b>\n\n"
        f"Ketik <b>angka tanggal saja</b> (1-{monthrange(start_date.year, start_date.month)[1]}). "
        f"Bulan dan tahun otomatis mengikuti jadwal berangkat: "
        f"<b>{format_month_year_id(start_date)}</b>.\n\n"
        "Tanggal boleh dilewati terlebih dahulu; hanya angka tanggal yang dikosongkan, "
        "sedangkan bulan dan tahun tetap dicetak.",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(
            [
                [menu_button(
                    f"📅 Gunakan tanggal berangkat ({format_date_id(start_date)})",
                    "create:issue_start",
                )],
                [menu_button(
                    f"⏭ Kosongkan tanggal ({format_month_year_id(start_date)})",
                    "create:issue_blank",
                )],
            ]
        ),
    )


def default_legal_base_4(draft: dict[str, Any]) -> str:
    destination = str(draft.get("destination") or "").strip()
    if destination:
        return f"Undangan dari Pemerintah {destination};"
    return DEFAULT_OPTIONAL_LEGAL_BASE_4


async def ask_legal_base_4(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    draft = get_draft(context)
    suggestion = draft.get("legal_base_4") or default_legal_base_4(draft)
    draft["legal_base_4_suggestion"] = suggestion
    context.user_data["state"] = None
    await edit_or_reply(
        update,
        "📚 <b>DASAR NOMOR 4</b>\n\n"
        f"Usulan:\n<code>{esc(suggestion)}</code>\n\n"
        "Dasar nomor 4 bersifat opsional. Gunakan, edit, atau hilangkan dari Surat Tugas.",
        InlineKeyboardMarkup(
            [
                [menu_button("✅ Gunakan", "create:legal4_use")],
                [menu_button("✏️ Edit Dasar 4", "create:legal4_edit")],
                [menu_button("🗑 Hilangkan", "create:legal4_remove")],
            ]
        ),
    )


async def finish_legal_base_4(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.user_data.pop("edit_legal4_return", False):
        await show_preview(update, context)
    else:
        await ask_number(update, context)


async def ask_number(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    draft = get_draft(context)
    suggested = db.suggest_next_sequence()
    draft["suggested_sequence"] = suggested
    full = db.format_full_number(suggested, letter_year(draft))
    context.user_data["state"] = "create_number"
    await edit_or_reply(
        update,
        "🔢 <b>NOMOR SURAT</b>\n\n"
        f"Saran nomor berikutnya:\n<code>{full}</code>\n\n"
        "Tekan Gunakan, ketik nomor urut lain, atau tekan Lewati jika nomor belum tersedia. "
        "Jika dilewati, bagian nomor pada dokumen akan dibiarkan kosong dengan ruang yang cukup lebar.",
        InlineKeyboardMarkup(
            [
                [menu_button(f"✅ Gunakan {suggested}", "create:number_suggested")],
                [menu_button("⏭ Lewati / Kosongkan Nomor", "create:number_blank")],
            ]
        ),
    )


def refresh_auto_purpose(draft: dict[str, Any]) -> None:
    if draft.get("purpose_manual"):
        return
    required = ("destination", "activity", "start_date", "end_date")
    if all(draft.get(key) for key in required):
        draft["purpose_text"] = build_purpose_text(
            draft["destination"],
            draft["activity"],
            draft["start_date"],
            draft["end_date"],
        )


def preview_text(context: ContextTypes.DEFAULT_TYPE) -> str:
    draft = get_draft(context)
    employees = [db.get_employee(i) for i in draft.get("employee_ids", [])]
    employees = [e for e in employees if e]
    employee_lines = "\n".join(f"{i}. {esc(e['name'])}" for i, e in enumerate(employees, start=1))
    duration = (draft["end_date"] - draft["start_date"]).days + 1
    number_display = draft["full_number"] if int(draft.get("sequence_number") or 0) > 0 else "Belum ada nomor (dikosongkan)"
    return (
        "🔍 <b>PREVIEW SURAT TUGAS</b>\n\n"
        f"<b>Nomor</b>\n<code>{esc(number_display)}</code>\n\n"
        f"<b>Pegawai ({len(employees)})</b>\n{employee_lines}\n\n"
        f"<b>Tujuan</b>\n{esc(draft['destination'])}\n\n"
        f"<b>Tanggal</b>\n{format_date_range_id(draft['start_date'], draft['end_date'])}\n"
        f"Durasi: <b>{duration} hari</b>\n\n"
        f"<b>Tanggal Penetapan</b>\n{format_issue_date_id(draft['issue_date'], bool(draft.get('issue_day_blank')))}\n\n"
        f"<b>Dasar 4</b>\n{esc(draft.get('legal_base_4') or 'Dihilangkan')}\n\n"
        f"<b>UNTUK</b>\n{esc(draft['purpose_text'])}"
    )


def preview_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [menu_button("✅ Buat DOCX + PDF", "create:generate")],
            [menu_button("🧾 Export Versi TNDE", "create:generate_tnde")],
            [
                menu_button("👥 Edit Pegawai", "create:edit_employees"),
                menu_button("📍 Edit Tujuan", "create:edit_destination"),
            ],
            [menu_button("📝 Edit Kegiatan", "create:edit_activity")],
            [
                menu_button("📅 Edit Tanggal", "create:edit_dates"),
                menu_button("🖊 Edit Penetapan", "create:edit_issue"),
            ],
            [menu_button("📚 Edit Dasar 4", "create:edit_legal4")],
            [
                menu_button("🔢 Edit Nomor", "create:edit_number"),
                menu_button("✍️ Edit Narasi", "create:edit_purpose"),
            ],
            [menu_button("↻ Buat Ulang Narasi Otomatis", "create:purpose_auto")],
            [menu_button("❌ Batalkan", "create:cancel")],
        ]
    )


async def show_preview(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data["state"] = None
    await edit_or_reply(update, preview_text(context), preview_markup())


async def ask_signature_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Ask explicitly whether the standard SPT should contain the manual signature."""
    if not await require_access(update):
        return
    await edit_or_reply(
        update,
        "✍️ <b>PILIH TANDA TANGAN</b>\n\n"
        "Gunakan tanda tangan Kepala Dinas pada Surat Tugas versi standar?\n\n"
        "Pilihan ini <b>tidak berlaku untuk TNDE</b>.",
        InlineKeyboardMarkup(
            [
                [menu_button("✍️ Pakai Tanda Tangan", "create:generate_signed")],
                [menu_button("🚫 Tanpa Tanda Tangan", "create:generate_unsigned")],
                [menu_button("⬅️ Kembali ke Preview", "create:preview")],
            ]
        ),
    )


async def generate_letter(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    include_signature: bool,
) -> None:
    user = await require_access(update)
    if not user:
        return
    query = update.callback_query
    await query.answer("Membuat dokumen...")
    draft = get_draft(context)
    employees_rows = [db.get_employee(i) for i in draft.get("employee_ids", [])]
    employees = [dict(row) for row in employees_rows if row]
    legal_rows = db.list_legal_bases(active_only=True)
    primary_legal_bases = list(draft.get("legal_bases") or [row["text"] for row in legal_rows])[:3]
    legal_bases = primary_legal_bases
    if draft.get("legal_base_4"):
        legal_bases.append(str(draft["legal_base_4"]).strip())
    issue_city = db.get_setting("issue_city", "Surabaya")

    try:
        docx_path = await asyncio.to_thread(
            generate_docx,
            full_number=draft["full_number"],
            sequence_number=draft["sequence_number"],
            destination=draft["destination"],
            activity=draft["activity"],
            issue_date=draft["issue_date"],
            issue_day_blank=bool(draft.get("issue_day_blank")),
            employees=employees,
            legal_bases=legal_bases,
            purpose_text=draft["purpose_text"],
            include_signature=include_signature,
            version=int(draft.get("version", 1)),
            issue_city=issue_city,
        )
        pdf_path = await asyncio.to_thread(convert_docx_to_pdf, docx_path)

        letter_id = db.create_letter(
            letter_uuid=str(uuid.uuid4()),
            sequence_number=int(draft["sequence_number"]),
            full_number=draft["full_number"],
            destination=draft["destination"],
            activity=draft["activity"],
            event_name="",
            purpose_text=draft["purpose_text"],
            start_date=draft["start_date"].isoformat(),
            end_date=draft["end_date"].isoformat(),
            duration_days=(draft["end_date"] - draft["start_date"]).days + 1,
            issue_date=draft["issue_date"].isoformat(),
            issue_day_blank=bool(draft.get("issue_day_blank")),
            employees=employees,
            legal_bases=legal_bases,
            created_by_user_id=user["id"],
            version=int(draft.get("version", 1)),
            parent_letter_id=draft.get("parent_letter_id"),
            docx_path=str(docx_path),
            pdf_path=str(pdf_path) if pdf_path else "",
        )
        db.update_letter_paths(letter_id, str(docx_path), str(pdf_path) if pdf_path else "")
    except Exception as exc:
        logger.exception("Gagal membuat surat")
        await query.message.reply_text(f"❌ Gagal membuat dokumen: {exc}")
        return

    number_result = draft["full_number"] if int(draft.get("sequence_number") or 0) > 0 else "Belum ada nomor (dikosongkan)"
    signature_result = "Dengan tanda tangan Kepala Dinas" if include_signature else "Tanpa tanda tangan"
    await query.message.reply_text(
        "✅ <b>Surat Tugas berhasil dibuat.</b>\n\n"
        f"Nomor: <code>{esc(number_result)}</code>\n"
        f"Tanda tangan: <b>{esc(signature_result)}</b>",
        parse_mode=ParseMode.HTML,
    )
    with open(docx_path, "rb") as fh:
        await query.message.reply_document(document=fh, filename=Path(docx_path).name, caption="📄 File Word")
    if pdf_path and Path(pdf_path).exists():
        with open(pdf_path, "rb") as fh:
            await query.message.reply_document(document=fh, filename=Path(pdf_path).name, caption="📕 File PDF")
    else:
        await query.message.reply_text(
            "⚠️ File Word berhasil dibuat, tetapi konversi PDF tidak tersedia di server ini."
        )
    reset_flow(context)
    await query.message.reply_text(
        "Pilih tindakan selanjutnya:",
        reply_markup=InlineKeyboardMarkup(
            [
                [menu_button("🧾 Export Versi TNDE", f"history:tnde:{letter_id}")],
                [menu_button("📋 Lihat Riwayat", "history:list")],
                [menu_button("➕ Buat Surat Lagi", "create:start")],
                [menu_button("🏠 Menu Utama", "menu:home")],
            ]
        ),
    )


async def generate_tnde_export(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Generate the current draft as a TNDE-ready DOCX/PDF without changing history."""
    if not await require_access(update):
        return
    query = update.callback_query
    await query.answer("Membuat versi TNDE...")
    draft = get_draft(context)
    employees_rows = [db.get_employee(i) for i in draft.get("employee_ids", [])]
    employees = [dict(row) for row in employees_rows if row]
    legal_rows = db.list_legal_bases(active_only=True)
    primary_legal_bases = list(
        draft.get("legal_bases") or [row["text"] for row in legal_rows]
    )[:3]
    legal_bases = list(primary_legal_bases)
    if draft.get("legal_base_4"):
        legal_bases.append(str(draft["legal_base_4"]).strip())
    issue_city = db.get_setting("issue_city", "Surabaya")

    try:
        docx_path = await asyncio.to_thread(
            generate_tnde_docx,
            sequence_number=int(draft.get("sequence_number") or 0),
            destination=draft["destination"],
            activity=draft["activity"],
            issue_date=draft["issue_date"],
            issue_day_blank=bool(draft.get("issue_day_blank")),
            employees=employees,
            legal_bases=legal_bases,
            purpose_text=draft["purpose_text"],
            version=int(draft.get("version", 1)),
            issue_city=issue_city,
        )
        pdf_path = await asyncio.to_thread(convert_tnde_docx_to_pdf, docx_path)
    except Exception as exc:
        logger.exception("Gagal membuat versi TNDE")
        await query.message.reply_text(f"❌ Gagal membuat versi TNDE: {exc}")
        return

    await query.message.reply_text(
        "✅ <b>Versi TNDE berhasil dibuat.</b>\n\n"
        "Placeholder <code>${nomor}</code>, <code>${qrcode}</code>, "
        "<code>${PEJABAT}</code>, <code>${pangkat}</code>, dan "
        "<code>${nip}</code> sengaja dipertahankan untuk diproses oleh TNDE.",
        parse_mode=ParseMode.HTML,
    )
    with open(docx_path, "rb") as fh:
        await query.message.reply_document(
            document=fh, filename=Path(docx_path).name, caption="🧾 File Word TNDE"
        )
    if pdf_path and Path(pdf_path).exists():
        with open(pdf_path, "rb") as fh:
            await query.message.reply_document(
                document=fh, filename=Path(pdf_path).name, caption="🧾 Preview PDF TNDE"
            )
    else:
        await query.message.reply_text(
            "⚠️ File Word TNDE berhasil dibuat, tetapi konversi PDF tidak tersedia di server ini."
        )
    await query.message.reply_text(
        "Draft tetap aktif. Anda masih bisa membuat versi standar atau mengedit data.",
        reply_markup=InlineKeyboardMarkup(
            [
                [menu_button("✅ Buat Versi Standar", "create:generate")],
                [menu_button("🔍 Kembali ke Preview", "create:preview")],
                [menu_button("🏠 Menu Utama", "menu:home")],
            ]
        ),
    )


async def export_tnde_from_history(update: Update, letter_id: int) -> None:
    """Regenerate a TNDE-ready export from the immutable letter snapshot."""
    if not await require_access(update):
        return
    query = update.callback_query
    item = db.get_letter(letter_id)
    if not item:
        await query.answer("Surat tidak ditemukan.", show_alert=True)
        return
    await query.answer("Membuat versi TNDE...")
    issue_city = db.get_setting("issue_city", "Surabaya")
    try:
        docx_path = await asyncio.to_thread(
            generate_tnde_docx,
            sequence_number=int(item.get("sequence_number") or 0),
            destination=item["destination"],
            activity=item["activity"],
            issue_date=date.fromisoformat(item["issue_date"]),
            issue_day_blank=bool(item.get("issue_day_blank")),
            employees=list(item.get("employees") or []),
            legal_bases=list(item.get("legal_bases") or []),
            purpose_text=item["purpose_text"],
            version=int(item.get("version") or 1),
            issue_city=issue_city,
        )
        pdf_path = await asyncio.to_thread(convert_tnde_docx_to_pdf, docx_path)
    except Exception as exc:
        logger.exception("Gagal export TNDE dari riwayat")
        await query.message.reply_text(f"❌ Gagal membuat versi TNDE: {exc}")
        return

    with open(docx_path, "rb") as fh:
        await query.message.reply_document(
            document=fh, filename=Path(docx_path).name, caption="🧾 File Word TNDE"
        )
    if pdf_path and Path(pdf_path).exists():
        with open(pdf_path, "rb") as fh:
            await query.message.reply_document(
                document=fh, filename=Path(pdf_path).name, caption="🧾 Preview PDF TNDE"
            )


# ---------- History ----------

async def show_history(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_access(update):
        return
    rows = db.list_letters(limit=12)
    keyboard: list[list[InlineKeyboardButton]] = []
    for row in rows:
        sequence_label = row["sequence_number"] if int(row["sequence_number"] or 0) > 0 else "Tanpa nomor"
        label = f"📄 {sequence_label} • {row['destination'][:28]}"
        keyboard.append([menu_button(label, f"history:view:{row['id']}")])
    keyboard.append([menu_button("🏠 Menu Utama", "menu:home")])
    text = "📋 <b>RIWAYAT SURAT TUGAS</b>\n\n"
    text += "Pilih surat untuk melihat detail." if rows else "Belum ada Surat Tugas yang tersimpan."
    await edit_or_reply(update, text, InlineKeyboardMarkup(keyboard))


async def show_letter_detail(update: Update, context: ContextTypes.DEFAULT_TYPE, letter_id: int) -> None:
    if not await require_access(update):
        return
    item = db.get_letter(letter_id)
    if not item:
        await update.callback_query.answer("Surat tidak ditemukan.", show_alert=True)
        return
    employees = "\n".join(
        f"{i}. {esc(emp.get('name',''))}" for i, emp in enumerate(item["employees"], start=1)
    )
    detail_number = item["full_number"] if int(item.get("sequence_number") or 0) > 0 else "Belum ada nomor (dikosongkan)"
    text = (
        "📄 <b>DETAIL SURAT TUGAS</b>\n\n"
        f"<b>Nomor</b>\n<code>{esc(detail_number)}</code>\n\n"
        f"<b>Tujuan</b>\n{esc(item['destination'])}\n\n"
        f"<b>Pegawai</b>\n{employees}\n\n"
        f"<b>Tanggal</b>\n{item['start_date']} s.d. {item['end_date']}\n\n"
        f"<b>Tanggal Penetapan</b>\n"
        f"{format_issue_date_id(date.fromisoformat(item['issue_date']), bool(item.get('issue_day_blank')))}\n\n"
        f"<b>UNTUK</b>\n{esc(item['purpose_text'])}\n\n"
        f"Versi: <b>{item['version']}</b> • Dibuat oleh: {esc(item['creator_name'])}"
    )
    rows = [
        [
            menu_button("📄 Kirim DOCX", f"history:send_docx:{letter_id}"),
            menu_button("📕 Kirim PDF", f"history:send_pdf:{letter_id}"),
        ],
        [menu_button("🧾 Export Versi TNDE", f"history:tnde:{letter_id}")],
        [
            menu_button("📋 Duplikat", f"history:duplicate:{letter_id}"),
            menu_button("✏️ Revisi", f"history:revise:{letter_id}"),
        ],
        [menu_button("⬅️ Kembali", "history:list")],
    ]
    await edit_or_reply(update, text, InlineKeyboardMarkup(rows))


async def send_history_file(update: Update, letter_id: int, kind: str) -> None:
    if not await require_access(update):
        return
    item = db.get_letter(letter_id)
    if not item:
        await update.callback_query.answer("Surat tidak ditemukan.", show_alert=True)
        return
    path = Path(item["docx_path"] if kind == "docx" else item["pdf_path"])
    await update.callback_query.answer()
    if not path.exists():
        await update.callback_query.message.reply_text("⚠️ File tidak ditemukan pada penyimpanan server.")
        return
    with open(path, "rb") as fh:
        await update.callback_query.message.reply_document(document=fh, filename=path.name)


def load_letter_to_draft(context: ContextTypes.DEFAULT_TYPE, item: dict[str, Any], revision: bool) -> None:
    employee_ids = [int(emp["id"]) for emp in item["employees"] if emp.get("id")]
    start = date.fromisoformat(item["start_date"])
    end = date.fromisoformat(item["end_date"])
    saved_legal_bases = list(item.get("legal_bases") or [])
    legacy_snapshot = (
        len(saved_legal_bases) >= 5
        and any("Nomor 9 Tahun 2024" in str(base) for base in saved_legal_bases)
    )
    if legacy_snapshot:
        saved_legal_bases = []
    optional_legal_base_4 = saved_legal_bases[3] if len(saved_legal_bases) > 3 else None
    stored_issue_date = date.fromisoformat(item["issue_date"])
    issue_day_blank = bool(item.get("issue_day_blank"))
    preferred_issue_day = stored_issue_date.day if not issue_day_blank else 1
    try:
        issue_date = issue_date_from_day(start, preferred_issue_day)
    except ValueError:
        issue_date = start
        issue_day_blank = False
    if revision:
        sequence = int(item["sequence_number"])
        full_number = (
            item["full_number"] if sequence > 0
            else db.format_blank_full_number(start.year)
        )
        version = int(item["version"]) + 1
        parent_letter_id = int(item["id"])
        primary_legal_bases = saved_legal_bases[:3] or None
    else:
        sequence = db.suggest_next_sequence()
        full_number = db.format_full_number(sequence, start.year)
        version = 1
        parent_letter_id = None
        primary_legal_bases = None
    context.user_data["draft"] = {
        "employee_ids": employee_ids,
        "destination": item["destination"],
        "activity": item["activity"],
        "start_date": start,
        "end_date": end,
        "issue_date": issue_date,
        "issue_day_blank": issue_day_blank,
        "sequence_number": sequence,
        "full_number": full_number,
        "purpose_text": build_purpose_text(
            item["destination"], item["activity"], start, end
        ),
        "purpose_manual": False,
        "version": version,
        "parent_letter_id": parent_letter_id,
        "legal_base_4": optional_legal_base_4,
    }
    if primary_legal_bases:
        context.user_data["draft"]["legal_bases"] = primary_legal_bases


# ---------- Employees ----------

async def show_employees(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 0) -> None:
    if not await require_access(update):
        return
    employees = db.list_employees(active_only=False)
    total_pages = max(1, (len(employees) + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))
    current = employees[page * PAGE_SIZE : (page + 1) * PAGE_SIZE]
    rows: list[list[InlineKeyboardButton]] = []
    for emp in current:
        status = "🟢" if emp["active"] else "🔴"
        rows.append([menu_button(f"{status} {emp['name'][:38]}", f"employees:view:{emp['id']}:{page}")])
    nav = []
    if page > 0:
        nav.append(menu_button("⬅️", f"employees:list:{page-1}"))
    nav.append(menu_button(f"{page+1}/{total_pages}", "noop"))
    if page < total_pages - 1:
        nav.append(menu_button("➡️", f"employees:list:{page+1}"))
    rows.append(nav)
    if is_admin(update):
        rows.append([menu_button("➕ Tambah Pegawai", "employees:add")])
    rows.append([menu_button("🏠 Menu Utama", "menu:home")])
    await edit_or_reply(
        update,
        f"👥 <b>DATA PEGAWAI</b>\n\nTotal: <b>{len(employees)}</b> data. 🟢 aktif • 🔴 nonaktif",
        InlineKeyboardMarkup(rows),
    )


async def show_employee_detail(update: Update, employee_id: int, page: int) -> None:
    if not await require_access(update):
        return
    emp = db.get_employee(employee_id)
    if not emp:
        await update.callback_query.answer("Pegawai tidak ditemukan.", show_alert=True)
        return
    status = "Aktif" if emp["active"] else "Tidak aktif"
    text = (
        "👤 <b>DETAIL PEGAWAI</b>\n\n"
        f"<b>{esc(emp['name'])}</b>\n"
        f"Jabatan: {esc(emp['position'])}\n"
        f"Pangkat/Gol: {esc(clean_rank(emp['rank']))}\n"
        f"NIP/NPPK/NIPTT: <code>{esc(emp['identifier'])}</code>\n"
        f"Status: <b>{status}</b>"
    )
    rows = []
    if is_admin(update):
        action = "🚫 Nonaktifkan" if emp["active"] else "✅ Aktifkan"
        rows.append([menu_button(action, f"employees:toggle:{employee_id}:{page}")])
    rows.append([menu_button("⬅️ Kembali", f"employees:list:{page}")])
    await edit_or_reply(update, text, InlineKeyboardMarkup(rows))


async def start_add_employee(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update):
        await update.callback_query.answer("Hanya admin.", show_alert=True)
        return
    context.user_data["pending"] = {"type": "employee_add"}
    context.user_data["state"] = "employee_add_name"
    await edit_or_reply(update, "➕ <b>TAMBAH PEGAWAI</b>\n\nKetik nama lengkap pegawai.")


# ---------- Legal bases ----------

async def show_legal_bases(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_access(update):
        return
    bases = db.list_legal_bases(active_only=False)[:3]
    rows: list[list[InlineKeyboardButton]] = []
    text_lines = ["📚 <b>DASAR HUKUM UTAMA (1-3)</b>", "", "Dasar nomor 4 dipilih/edit/dihilangkan saat membuat Surat Tugas.", ""]
    for base in bases:
        status = "🟢" if base["active"] else "🔴"
        text_lines.append(f"<b>{base['sort_order']}.</b> {status} {esc(base['text'])}")
        if is_admin(update):
            rows.append([menu_button(f"✏️ Edit Dasar {base['sort_order']}", f"legal:edit:{base['id']}")])
    rows.append([menu_button("🏠 Menu Utama", "menu:home")])
    await edit_or_reply(update, "\n\n".join(text_lines), InlineKeyboardMarkup(rows))


# ---------- Number settings ----------

async def show_number_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_access(update):
        return
    prefix = db.get_setting("number_prefix")
    suffix = db.get_setting("number_suffix")
    last = db.get_setting("last_sequence", "0")
    suggested = db.suggest_next_sequence()
    year = date.today().year
    text = (
        "🔢 <b>PENGATURAN NOMOR SURAT</b>\n\n"
        f"Format: <code>{prefix} / [NOMOR] / {suffix} / [TAHUN]</code>\n"
        f"Nomor terakhir tercatat: <b>{last}</b>\n"
        f"Saran berikutnya: <code>{db.format_full_number(suggested, year)}</code>"
    )
    rows = []
    if is_admin(update):
        rows.extend(
            [
                [menu_button("✏️ Atur Nomor Terakhir", "number:set_last")],
                [
                    menu_button("✏️ Ubah Prefix", "number:set_prefix"),
                    menu_button("✏️ Ubah Suffix", "number:set_suffix"),
                ],
            ]
        )
    rows.append([menu_button("🏠 Menu Utama", "menu:home")])
    await edit_or_reply(update, text, InlineKeyboardMarkup(rows))


# ---------- Stats ----------

async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_access(update):
        return
    stats = db.statistics()
    text = (
        "📊 <b>STATISTIK BOT</b>\n\n"
        f"📄 Surat Tugas tersimpan: <b>{stats['letters']}</b>\n"
        f"👥 Pegawai aktif: <b>{stats['employees']}</b>\n"
        f"📍 Tujuan berbeda: <b>{stats['destinations']}</b>\n"
        f"👤 Pengguna aktif: <b>{stats['users']}</b>"
    )
    await edit_or_reply(update, text, InlineKeyboardMarkup([[menu_button("🏠 Menu Utama", "menu:home")]]))


# ---------- Admin users ----------

async def show_users(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update):
        await update.callback_query.answer("Hanya admin.", show_alert=True)
        return
    users = db.list_users()
    rows: list[list[InlineKeyboardButton]] = []
    lines = ["⚙️ <b>KELOLA PENGGUNA</b>", ""]
    for user in users:
        status = "🟢" if user["active"] else "🔴"
        role = "ADMIN" if user["role"] == "admin" else "OPERATOR"
        lines.append(f"{status} <b>{esc(user['display_name'])}</b> • {role}\n<code>{user['telegram_id']}</code>")
        if user["role"] != "admin":
            action = "Nonaktifkan" if user["active"] else "Aktifkan"
            rows.append([menu_button(f"{action}: {user['display_name'][:25]}", f"admin:toggle_user:{user['id']}")])
    rows.append([menu_button("➕ Tambah Operator", "admin:add_user")])
    rows.append([menu_button("🏠 Menu Utama", "menu:home")])
    await edit_or_reply(update, "\n\n".join(lines), InlineKeyboardMarkup(rows))


# ---------- Text state router ----------

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_access(update):
        return
    text = (update.effective_message.text or "").strip()
    state = context.user_data.get("state")
    draft = get_draft(context)

    try:
        if state == "create_employee_search":
            context.user_data["employee_search"] = text
            context.user_data["state"] = None
            fake_text, keyboard = employee_selection_markup(context, 0)
            await update.effective_message.reply_text(fake_text, parse_mode=ParseMode.HTML, reply_markup=keyboard)
            return

        if state == "create_destination":
            previous_destination = str(draft.get("destination") or "").strip()
            previous_auto_base_4 = (
                draft.get("legal_base_4") == f"Undangan dari Pemerintah {previous_destination};"
                if previous_destination else False
            )
            draft["destination"] = text
            if previous_auto_base_4:
                draft["legal_base_4"] = default_legal_base_4(draft)
            refresh_auto_purpose(draft)
            if context.user_data.pop("edit_return", False):
                await show_preview(update, context)
            else:
                await ask_activity(update, context)
            return

        if state == "create_activity":
            draft["activity"] = text
            refresh_auto_purpose(draft)
            if context.user_data.pop("edit_return", False):
                await show_preview(update, context)
            else:
                await ask_start_date(update, context)
            return

        if state == "create_start_date":
            value = parse_date_id(text)
            draft["start_date"] = value
            await ask_end_date(update, context)
            return

        if state == "create_end_date":
            value = parse_date_id(text)
            if value < draft["start_date"]:
                raise ValueError("Tanggal pulang tidak boleh lebih awal dari tanggal berangkat.")
            draft["end_date"] = value
            refresh_auto_purpose(draft)
            if context.user_data.get("edit_dates"):
                sync_issue_date_to_start(draft)
                sequence = int(draft.get("sequence_number") or 0)
                draft["full_number"] = (
                    db.format_full_number(sequence, letter_year(draft))
                    if sequence > 0
                    else db.format_blank_full_number(letter_year(draft))
                )
            if context.user_data.pop("edit_dates", False):
                await show_preview(update, context)
            else:
                await ask_issue_date(update, context)
            return

        if state == "create_issue_date":
            draft["issue_date"] = parse_issue_day_for_start(text, draft["start_date"])
            draft["issue_day_blank"] = False
            if context.user_data.pop("edit_return", False):
                sequence = int(draft.get("sequence_number") or 0)
                draft["full_number"] = (
                    db.format_full_number(sequence, letter_year(draft))
                    if sequence > 0 else db.format_blank_full_number(letter_year(draft))
                )
                await show_preview(update, context)
            else:
                await ask_legal_base_4(update, context)
            return

        if state == "create_legal_base_4":
            draft["legal_base_4"] = text
            await finish_legal_base_4(update, context)
            return

        if state == "create_number":
            sequence = int(text)
            if sequence <= 0:
                raise ValueError("Nomor urut harus lebih dari 0.")
            draft["sequence_number"] = sequence
            draft["full_number"] = db.format_full_number(sequence, letter_year(draft))
            await show_preview(update, context)
            return

        if state == "create_purpose":
            draft["purpose_text"] = text
            draft["purpose_manual"] = True
            await show_preview(update, context)
            return

        if state == "employee_add_name":
            context.user_data["pending"]["name"] = text
            context.user_data["state"] = "employee_add_gender"
            await update.effective_message.reply_text("Ketik jenis kelamin: L atau P")
            return

        if state == "employee_add_gender":
            value = text.upper()
            if value not in {"L", "P"}:
                raise ValueError("Jenis kelamin harus L atau P.")
            context.user_data["pending"]["gender"] = value
            context.user_data["state"] = "employee_add_position"
            await update.effective_message.reply_text("Ketik jabatan pegawai.")
            return

        if state == "employee_add_position":
            context.user_data["pending"]["position"] = text
            context.user_data["state"] = "employee_add_rank"
            await update.effective_message.reply_text("Ketik pangkat/golongan, contoh: Penata (III/c) atau -/IX")
            return

        if state == "employee_add_rank":
            context.user_data["pending"]["rank"] = clean_rank(text)
            context.user_data["state"] = "employee_add_identifier"
            await update.effective_message.reply_text("Ketik NIP/NPPK/NIPTT. Gunakan - bila tidak ada.")
            return

        if state == "employee_add_identifier":
            pending = context.user_data.get("pending", {})
            identifier = text.replace(" ", "") if text.replace(" ", "").isdigit() else text
            emp_id = db.add_employee(
                pending["name"], pending["gender"], pending["position"], pending["rank"], identifier
            )
            context.user_data.pop("pending", None)
            context.user_data["state"] = None
            await update.effective_message.reply_text("✅ Pegawai berhasil ditambahkan.")
            await show_employee_detail_from_message(update, emp_id)
            return

        if state == "legal_edit":
            pending = context.user_data.get("pending", {})
            db.update_legal_base(int(pending["legal_id"]), text)
            context.user_data.pop("pending", None)
            context.user_data["state"] = None
            await update.effective_message.reply_text("✅ Dasar hukum berhasil diperbarui.")
            await show_main_menu(update, context)
            return

        if state == "legal_add":
            db.add_legal_base(text)
            context.user_data["state"] = None
            await update.effective_message.reply_text("✅ Dasar hukum berhasil ditambahkan.")
            await show_main_menu(update, context)
            return

        if state == "number_set_last":
            value = int(text)
            if value < 0:
                raise ValueError("Nomor terakhir tidak boleh negatif.")
            db.set_setting("last_sequence", str(value))
            context.user_data["state"] = None
            await update.effective_message.reply_text("✅ Nomor terakhir diperbarui.")
            await show_main_menu(update, context)
            return

        if state == "number_set_prefix":
            db.set_setting("number_prefix", text)
            context.user_data["state"] = None
            await update.effective_message.reply_text("✅ Prefix nomor diperbarui.")
            await show_main_menu(update, context)
            return

        if state == "number_set_suffix":
            db.set_setting("number_suffix", text)
            context.user_data["state"] = None
            await update.effective_message.reply_text("✅ Suffix nomor diperbarui.")
            await show_main_menu(update, context)
            return

        if state == "admin_add_user_id":
            telegram_id = int(text)
            context.user_data["pending"] = {"telegram_id": telegram_id}
            context.user_data["state"] = "admin_add_user_name"
            await update.effective_message.reply_text("Ketik nama operator.")
            return

        if state == "admin_add_user_name":
            pending = context.user_data.get("pending", {})
            db.upsert_user(int(pending["telegram_id"]), text, "operator", active=True)
            context.user_data.pop("pending", None)
            context.user_data["state"] = None
            await update.effective_message.reply_text("✅ Operator berhasil ditambahkan.")
            await show_main_menu(update, context)
            return

        await update.effective_message.reply_text(
            "Gunakan tombol menu agar alur lebih rapi.",
            reply_markup=main_menu_markup(is_admin(update)),
        )
    except ValueError as exc:
        await update.effective_message.reply_text(f"⚠️ {exc}\nSilakan coba lagi.")
    except Exception as exc:
        logger.exception("Kesalahan saat memproses teks")
        await update.effective_message.reply_text(f"❌ Terjadi kesalahan: {exc}")


async def show_employee_detail_from_message(update: Update, employee_id: int) -> None:
    emp = db.get_employee(employee_id)
    if not emp:
        return
    await update.effective_message.reply_text(
        "👤 <b>DATA PEGAWAI</b>\n\n"
        f"<b>{esc(emp['name'])}</b>\n"
        f"Jabatan: {esc(emp['position'])}\n"
        f"Pangkat/Gol: {esc(emp['rank'])}\n"
        f"NIP/NPPK/NIPTT: <code>{esc(emp['identifier'])}</code>",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([[menu_button("👥 Kembali ke Data Pegawai", "employees:list:0")]]),
    )


# ---------- Callback router ----------

async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    data = query.data or ""

    if data == "noop":
        await query.answer()
        return
    if data == "menu:home":
        await show_main_menu(update, context)
        return

    if not await require_access(update):
        return

    # Create
    if data == "create:start":
        await create_start(update, context)
    elif data.startswith("create:emp:"):
        _, _, emp_id, page = data.split(":")
        await create_employee_toggle(update, context, int(emp_id), int(page))
    elif data.startswith("create:emp_page:"):
        page = int(data.rsplit(":", 1)[1])
        text, keyboard = employee_selection_markup(context, page)
        await edit_or_reply(update, text, keyboard)
    elif data == "create:emp_search":
        await create_employee_search(update, context)
    elif data == "create:emp_clear_search":
        context.user_data.pop("employee_search", None)
        text, keyboard = employee_selection_markup(context, 0)
        await edit_or_reply(update, text, keyboard)
    elif data == "create:emp_done":
        await create_employee_done(update, context)
    elif data in {"create:issue_start", "create:issue_blank", "create:issue_today"}:
        draft = get_draft(context)
        start_date = draft["start_date"]
        if data == "create:issue_blank":
            draft["issue_date"] = date(start_date.year, start_date.month, 1)
            draft["issue_day_blank"] = True
        elif data == "create:issue_start":
            draft["issue_date"] = start_date
            draft["issue_day_blank"] = False
        else:
            # Backward compatibility for an old Telegram button already visible
            # in a user's chat: use today's day, but keep the travel month/year.
            last_day = monthrange(start_date.year, start_date.month)[1]
            draft["issue_date"] = date(
                start_date.year, start_date.month, min(date.today().day, last_day)
            )
            draft["issue_day_blank"] = False
        if context.user_data.pop("edit_return", False):
            sequence = int(draft.get("sequence_number") or 0)
            draft["full_number"] = (
                db.format_full_number(sequence, letter_year(draft))
                if sequence > 0 else db.format_blank_full_number(letter_year(draft))
            )
            await show_preview(update, context)
        else:
            await ask_legal_base_4(update, context)
    elif data == "create:legal4_use":
        draft = get_draft(context)
        draft["legal_base_4"] = draft.get("legal_base_4_suggestion") or default_legal_base_4(draft)
        await finish_legal_base_4(update, context)
    elif data == "create:legal4_edit":
        context.user_data["state"] = "create_legal_base_4"
        current = get_draft(context).get("legal_base_4") or get_draft(context).get("legal_base_4_suggestion") or default_legal_base_4(get_draft(context))
        await edit_or_reply(
            update,
            "✏️ <b>EDIT DASAR NOMOR 4</b>\n\n"
            f"Saat ini:\n<code>{esc(current)}</code>\n\n"
            "Ketik isi Dasar nomor 4 yang baru.",
        )
    elif data == "create:legal4_remove":
        draft = get_draft(context)
        draft["legal_base_4"] = None
        await finish_legal_base_4(update, context)
    elif data == "create:number_blank":
        draft = get_draft(context)
        draft["sequence_number"] = 0
        draft["full_number"] = db.format_blank_full_number(letter_year(draft))
        await show_preview(update, context)
    elif data == "create:number_suggested":
        draft = get_draft(context)
        sequence = int(draft.get("suggested_sequence") or db.suggest_next_sequence())
        draft["sequence_number"] = sequence
        draft["full_number"] = db.format_full_number(sequence, letter_year(draft))
        await show_preview(update, context)
    elif data == "create:generate":
        await ask_signature_choice(update, context)
    elif data == "create:generate_signed":
        await generate_letter(update, context, include_signature=True)
    elif data == "create:generate_unsigned":
        await generate_letter(update, context, include_signature=False)
    elif data == "create:generate_tnde":
        await generate_tnde_export(update, context)
    elif data == "create:preview":
        await show_preview(update, context)
    elif data == "create:cancel":
        reset_flow(context)
        await show_main_menu(update, context)
    elif data == "create:edit_employees":
        context.user_data["emp_edit_return"] = True
        context.user_data.pop("employee_search", None)
        text, keyboard = employee_selection_markup(context, 0)
        await edit_or_reply(update, text, keyboard)
    elif data == "create:edit_destination":
        context.user_data["state"] = "create_destination"
        context.user_data["edit_return"] = True
        await edit_or_reply(update, "📍 Ketik tujuan baru.")
    elif data == "create:edit_activity":
        context.user_data["state"] = "create_activity"
        context.user_data["edit_return"] = True
        await edit_or_reply(update, "📝 Ketik kegiatan baru.")
    elif data == "create:edit_dates":
        context.user_data["state"] = "create_start_date"
        context.user_data["edit_dates"] = True
        await edit_or_reply(update, "📅 Ketik tanggal berangkat baru (DD-MM-YYYY).")
    elif data == "create:edit_issue":
        context.user_data["edit_return"] = True
        await ask_issue_date(update, context)
    elif data == "create:edit_legal4":
        context.user_data["edit_legal4_return"] = True
        await ask_legal_base_4(update, context)
    elif data == "create:edit_number":
        context.user_data["state"] = "create_number"
        await edit_or_reply(
            update,
            "🔢 Ketik nomor urut surat yang baru atau kosongkan jika nomor belum tersedia.",
            InlineKeyboardMarkup([[menu_button("⏭ Kosongkan Nomor", "create:number_blank")]]),
        )
    elif data == "create:edit_purpose":
        context.user_data["state"] = "create_purpose"
        await edit_or_reply(update, "✍️ Ketik narasi lengkap untuk bagian UNTUK.")
    elif data == "create:purpose_auto":
        draft = get_draft(context)
        draft["purpose_manual"] = False
        refresh_auto_purpose(draft)
        await show_preview(update, context)

    # History
    elif data == "history:list":
        await show_history(update, context)
    elif data.startswith("history:view:"):
        await show_letter_detail(update, context, int(data.rsplit(":", 1)[1]))
    elif data.startswith("history:send_docx:"):
        await send_history_file(update, int(data.rsplit(":", 1)[1]), "docx")
    elif data.startswith("history:send_pdf:"):
        await send_history_file(update, int(data.rsplit(":", 1)[1]), "pdf")
    elif data.startswith("history:tnde:"):
        await export_tnde_from_history(update, int(data.rsplit(":", 1)[1]))
    elif data.startswith("history:duplicate:"):
        item = db.get_letter(int(data.rsplit(":", 1)[1]))
        if not item:
            await query.answer("Surat tidak ditemukan.", show_alert=True)
            return
        reset_flow(context)
        load_letter_to_draft(context, item, revision=False)
        await show_preview(update, context)
    elif data.startswith("history:revise:"):
        item = db.get_letter(int(data.rsplit(":", 1)[1]))
        if not item:
            await query.answer("Surat tidak ditemukan.", show_alert=True)
            return
        reset_flow(context)
        load_letter_to_draft(context, item, revision=True)
        await show_preview(update, context)

    # Employees
    elif data.startswith("employees:list:"):
        await show_employees(update, context, int(data.rsplit(":", 1)[1]))
    elif data.startswith("employees:view:"):
        _, _, emp_id, page = data.split(":")
        await show_employee_detail(update, int(emp_id), int(page))
    elif data.startswith("employees:toggle:"):
        if not is_admin(update):
            await query.answer("Hanya admin.", show_alert=True)
            return
        _, _, emp_id, page = data.split(":")
        emp = db.get_employee(int(emp_id))
        if emp:
            db.set_employee_active(int(emp_id), not bool(emp["active"]))
        await show_employee_detail(update, int(emp_id), int(page))
    elif data == "employees:add":
        await start_add_employee(update, context)

    # Legal bases
    elif data == "legal:list":
        await show_legal_bases(update, context)
    elif data.startswith("legal:edit:"):
        if not is_admin(update):
            await query.answer("Hanya admin.", show_alert=True)
            return
        legal_id = int(data.rsplit(":", 1)[1])
        context.user_data["pending"] = {"legal_id": legal_id}
        context.user_data["state"] = "legal_edit"
        await edit_or_reply(update, "✏️ Ketik isi dasar hukum yang baru.")
    elif data == "legal:add":
        if not is_admin(update):
            await query.answer("Hanya admin.", show_alert=True)
            return
        context.user_data["state"] = "legal_add"
        await edit_or_reply(update, "➕ Ketik dasar hukum baru.")

    # Number settings
    elif data == "number:menu":
        await show_number_menu(update, context)
    elif data == "number:set_last":
        if not is_admin(update):
            await query.answer("Hanya admin.", show_alert=True)
            return
        context.user_data["state"] = "number_set_last"
        await edit_or_reply(update, "Ketik nomor urut terakhir yang sudah digunakan, contoh: 122")
    elif data == "number:set_prefix":
        if not is_admin(update):
            await query.answer("Hanya admin.", show_alert=True)
            return
        context.user_data["state"] = "number_set_prefix"
        await edit_or_reply(update, "Ketik prefix nomor surat, contoh: 000.1.2.3")
    elif data == "number:set_suffix":
        if not is_admin(update):
            await query.answer("Hanya admin.", show_alert=True)
            return
        context.user_data["state"] = "number_set_suffix"
        await edit_or_reply(update, "Ketik suffix nomor surat, contoh: 118.4")

    # Stats
    elif data == "stats:show":
        await show_stats(update, context)

    # Admin users
    elif data == "admin:users":
        await show_users(update, context)
    elif data == "admin:add_user":
        if not is_admin(update):
            await query.answer("Hanya admin.", show_alert=True)
            return
        context.user_data["state"] = "admin_add_user_id"
        await edit_or_reply(update, "Ketik Telegram ID operator yang akan ditambahkan.")
    elif data.startswith("admin:toggle_user:"):
        if not is_admin(update):
            await query.answer("Hanya admin.", show_alert=True)
            return
        user_id = int(data.rsplit(":", 1)[1])
        users = {u["id"]: u for u in db.list_users()}
        target = users.get(user_id)
        if target and target["role"] != "admin":
            db.set_user_active(user_id, not bool(target["active"]))
        await show_users(update, context)
    else:
        await query.answer("Menu tidak dikenali.")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception("Unhandled exception", exc_info=context.error)
    try:
        if isinstance(update, Update) and update.effective_message:
            await update.effective_message.reply_text(
                "❌ Terjadi kesalahan tak terduga. Coba kembali ke /start."
            )
    except Exception:
        pass


def build_application() -> Application:
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN belum diisi. Set environment variable BOT_TOKEN.")
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("menu", start_command))
    application.add_handler(CommandHandler("cancel", cancel_command))
    application.add_handler(CommandHandler("id", id_command))
    application.add_handler(CallbackQueryHandler(callback_router))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.add_error_handler(error_handler)
    return application


def ensure_runtime_directories() -> None:
    """Create persistent folders without depending on a helper in config.py."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)


def main() -> None:
    ensure_runtime_directories()
    db.initialize()
    application = build_application()
    logger.info("Bot Surat Tugas v3.2.0 mulai berjalan")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
