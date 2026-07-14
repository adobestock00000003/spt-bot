# Changelog

## v2.0.0

- Mengganti template aktif ke `SPT 2026 FIX`.
- Dasar hukum default disesuaikan menjadi 3 dasar utama sesuai template 2026.
- Menambahkan Dasar nomor 4 opsional per surat: gunakan, edit, atau hilangkan.
- Preview menampilkan status/isi Dasar nomor 4.
- Font isi surat dinormalisasi ke Arial 12 pt.
- Layout daftar pegawai dirombak menjadi blok per pegawai yang tidak terpotong di tengah halaman.
- Output DOCX/PDF untuk jumlah pegawai banyak dibuat multi-halaman secara otomatis.
- Blok tanda tangan dibuat sebagai layout normal agar tidak bertumpuk atau bergeser saat halaman bertambah.
- Migrasi aman untuk database v1 yang masih memakai dasar hukum default lama.
- Smoke test ditambah untuk 2 pegawai dan 12 pegawai.

## v1.0.0

- Seed 24 data pegawai dari Excel Bidang Pemasaran.
- Template Surat Tugas resmi sebagai sumber DOCX.
- Multi-pilih dan pencarian pegawai.
- Durasi dan terbilang otomatis.
- Narasi `UNTUK` otomatis dan dapat diedit.
- Preview sebelum generate.
- DOCX + PDF.
- Riwayat, kirim ulang file, duplikat, dan revisi.
- Admin/operator.
- Pengelolaan pegawai, dasar hukum, dan nomor surat.
- SQLite persisten untuk Railway Volume.
