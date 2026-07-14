from datetime import date
from pathlib import Path
import tempfile

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
            employees=[wisnu, riza],
            legal_bases=legal_bases + ["Undangan dari Pemerintah Kabupaten Ponorogo;"],
            purpose_text=purpose,
            output_dir=tmp_path,
        )
        assert docx.exists() and docx.stat().st_size > 0
        pdf = convert_docx_to_pdf(docx)

        stress_docx = generate_docx(
            full_number="000.1.2.3 / 124 / 118.4 / 2026",
            sequence_number=124,
            destination="Kabupaten Banyuwangi",
            activity="peliputan dan pembuatan konten promosi pariwisata",
            issue_date=date(2026, 7, 13),
            employees=all_employees[:12],
            legal_bases=legal_bases,
            purpose_text=(
                "Perjalanan Dinas ke Kabupaten Banyuwangi dalam rangka peliputan dan "
                "pembuatan konten promosi pariwisata selama 4 (empat) hari pada tanggal "
                "20-23 Juli 2026."
            ),
            output_dir=tmp_path,
        )
        assert stress_docx.exists() and stress_docx.stat().st_size > 0
        stress_pdf = convert_docx_to_pdf(stress_docx)

        tnde_docx = generate_tnde_docx(
            sequence_number=0,
            destination="Kabupaten Ponorogo",
            activity="pendampingan dan pembuatan konten video KYAI LODRA",
            issue_date=date(2026, 6, 10),
            employees=[wisnu, riza],
            legal_bases=legal_bases + ["Undangan dari Pemerintah Kabupaten Ponorogo;"],
            purpose_text=purpose,
            output_dir=tmp_path,
        )
        assert tnde_docx.exists() and tnde_docx.stat().st_size > 0
        tnde_pdf = convert_tnde_docx_to_pdf(tnde_docx)

        print(f"DOCX 2 pegawai OK: {docx}")
        print(f"PDF 2 pegawai: {pdf if pdf else 'LibreOffice tidak tersedia'}")
        print(f"DOCX 12 pegawai OK: {stress_docx}")
        print(f"PDF 12 pegawai: {stress_pdf if stress_pdf else 'LibreOffice tidak tersedia'}")
        print(f"DOCX TNDE OK: {tnde_docx}")
        print(f"PDF TNDE: {tnde_pdf if tnde_pdf else 'LibreOffice tidak tersedia'}")


if __name__ == "__main__":
    main()
