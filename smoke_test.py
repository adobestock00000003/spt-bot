from datetime import date
from pathlib import Path
import tempfile
from zipfile import ZipFile

from database import Database
from services.document_service import (
    convert_docx_to_pdf,
    convert_tnde_docx_to_pdf,
    generate_docx,
    generate_tnde_docx,
)
from utils import build_purpose_text


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        database = Database(tmp_path / "test.db")
        database.initialize()
        legal_bases = [row["text"] for row in database.list_legal_bases()][:3]
        all_employees = [dict(row) for row in database.list_employees(active_only=True)]
        wisnu = next(emp for emp in all_employees if emp["name"].startswith("WISNU ADY"))
        riza = next(emp for emp in all_employees if emp["name"].startswith("ACHMAD RIZA"))

        start = date(2026, 6, 11)
        end = date(2026, 6, 14)
        purpose = build_purpose_text(
            "Kabupaten Ponorogo",
            "pendampingan dan pembuatan konten video KYAI LODRA",
            start,
            end,
        )

        docx = generate_docx(
            full_number=database.format_blank_full_number(2026),
            sequence_number=0,
            destination="Kabupaten Ponorogo",
            activity="pendampingan dan pembuatan konten video KYAI LODRA",
            issue_date=date(2026, 6, 10),
            issue_day_blank=False,
            employees=[wisnu, riza],
            legal_bases=legal_bases + ["Undangan dari Pemerintah Kabupaten Ponorogo;"],
            purpose_text=purpose,
            include_signature=True,
            output_dir=tmp_path,
        )
        assert docx.exists() and docx.stat().st_size > 0
        with ZipFile(docx) as archive:
            normal_media = [name for name in archive.namelist() if name.startswith("word/media/")]
            assert any("image" in name for name in normal_media), "Surat biasa harus memuat gambar tanda tangan."
        pdf = convert_docx_to_pdf(docx)

        unsigned_docx = generate_docx(
            full_number=database.format_blank_full_number(2026),
            sequence_number=0,
            destination="Kabupaten Ponorogo",
            activity="pendampingan dan pembuatan konten video KYAI LODRA",
            issue_date=date(2026, 6, 1),
            issue_day_blank=True,
            employees=[wisnu, riza],
            legal_bases=legal_bases + ["Undangan dari Pemerintah Kabupaten Ponorogo;"],
            purpose_text=purpose,
            include_signature=False,
            output_dir=tmp_path,
        )
        with ZipFile(unsigned_docx) as archive:
            document_xml = archive.read("word/document.xml")
            assert b"Tanda Tangan Kepala Dinas" not in document_xml, "Mode tanpa TTD tidak boleh memuat gambar tanda tangan."
        unsigned_pdf = convert_docx_to_pdf(unsigned_docx)

        stress_docx = generate_docx(
            full_number="000.1.2.3 / 124 / 118.4 / 2026",
            sequence_number=124,
            destination="Kabupaten Banyuwangi",
            activity="peliputan dan pembuatan konten promosi pariwisata",
            issue_date=date(2026, 7, 13),
            issue_day_blank=False,
            employees=all_employees[:12],
            legal_bases=legal_bases,
            purpose_text=(
                "Perjalanan Dinas ke Kabupaten Banyuwangi dalam rangka peliputan dan "
                "pembuatan konten promosi pariwisata selama 4 (empat) hari pada tanggal "
                "20-23 Juli 2026."
            ),
            include_signature=True,
            output_dir=tmp_path,
        )
        assert stress_docx.exists() and stress_docx.stat().st_size > 0
        stress_pdf = convert_docx_to_pdf(stress_docx)

        tnde_docx = generate_tnde_docx(
            sequence_number=0,
            destination="Kabupaten Ponorogo",
            activity="pendampingan dan pembuatan konten video KYAI LODRA",
            issue_date=date(2026, 6, 1),
            issue_day_blank=True,
            employees=[wisnu, riza],
            legal_bases=legal_bases + ["Undangan dari Pemerintah Kabupaten Ponorogo;"],
            purpose_text=purpose,
            output_dir=tmp_path,
        )
        assert tnde_docx.exists() and tnde_docx.stat().st_size > 0
        with ZipFile(tnde_docx) as archive:
            document_xml = archive.read("word/document.xml")
            assert b"Tanda Tangan Kepala Dinas" not in document_xml, "TNDE tidak boleh memakai gambar tanda tangan manual."
        tnde_pdf = convert_tnde_docx_to_pdf(tnde_docx)

        # Database regression: complete/re-export the same letter row without
        # increasing the number of stored letters.
        user_id = database.upsert_user(999001, "Smoke Tester", "admin", active=True)
        letter_id = database.create_letter(
            letter_uuid="smoke-completion-letter",
            sequence_number=0,
            full_number=database.format_blank_full_number(2026),
            destination="Kabupaten Ponorogo",
            activity="pendampingan dan pembuatan konten video KYAI LODRA",
            event_name="",
            purpose_text=purpose,
            start_date=start.isoformat(),
            end_date=end.isoformat(),
            duration_days=4,
            issue_date=date(2026, 6, 1).isoformat(),
            issue_day_blank=True,
            include_signature=False,
            employees=[wisnu, riza],
            legal_bases=legal_bases,
            created_by_user_id=user_id,
            version=1,
            docx_path=str(unsigned_docx),
            pdf_path=str(unsigned_pdf or ""),
        )
        before_count = database.statistics()["letters"]
        database.update_letter_completion(
            letter_id,
            sequence_number=123,
            full_number=database.format_full_number(123, 2026),
            issue_date=date(2026, 6, 10).isoformat(),
            issue_day_blank=False,
            include_signature=True,
            version=2,
            docx_path=str(docx),
            pdf_path=str(pdf or ""),
        )
        completed = database.get_letter(letter_id)
        assert database.statistics()["letters"] == before_count
        assert completed and completed["sequence_number"] == 123
        assert completed["issue_day_blank"] == 0
        assert completed["include_signature"] == 1
        assert completed["version"] == 2

        print(f"DOCX 2 pegawai OK: {docx}")
        print(f"PDF 2 pegawai dengan TTD: {pdf if pdf else 'LibreOffice tidak tersedia'}")
        print(f"DOCX 2 pegawai tanpa TTD OK: {unsigned_docx}")
        print(f"PDF 2 pegawai tanpa TTD: {unsigned_pdf if unsigned_pdf else 'LibreOffice tidak tersedia'}")
        print(f"DOCX 12 pegawai OK: {stress_docx}")
        print(f"PDF 12 pegawai: {stress_pdf if stress_pdf else 'LibreOffice tidak tersedia'}")
        print(f"DOCX TNDE OK: {tnde_docx}")
        print(f"PDF TNDE: {tnde_pdf if tnde_pdf else 'LibreOffice tidak tersedia'}")
        print("Database completion/re-export OK: surat diperbarui tanpa menambah riwayat")


if __name__ == "__main__":
    main()
