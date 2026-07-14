# Changelog

## v2.6.0
- Menyesuaikan jarak setelah **MEMERINTAHKAN** agar pas seperti template contoh: tidak ada paragraf kosong tambahan yang memperlebar jarak.
- Menghapus spacer tambahan sebelum daftar pegawai sehingga blok **KEPADA** tetap rapat dan rapi.
- Format, teks, tab, dan tanda titik dua pada **KEPADA** tetap tidak diubah.

# Changelog

## v2.5.0
- Menambahkan satu baris kosong setelah **MEMERINTAHKAN** sebelum blok **KEPADA**.
- Mempertahankan teks dan format **KEPADA** dari template resmi tanpa menulis ulang isinya.
- Daftar pegawai dinamis dipindahkan ke bawah blok KEPADA agar tetap rapi untuk sedikit maupun banyak pegawai.
- Jabatan Ali Afandi diperbarui menjadi **Kepala Bidang Pemasaran dan Kelembagaan Parekraf**, termasuk migrasi database Railway yang sudah ada.
- Baris **Ditetapkan di** dan **pada tanggal** disejajarkan dengan sisi kiri blok **KEPALA DINAS / KEBUDAYAAN DAN PARIWISATA / PROVINSI JAWA TIMUR**.
- Semua preservasi ruang kosong template dari v2.4 tetap dipertahankan.

## v2.4.0
- Nomor surat dapat dilewati atau dikosongkan sementara.
- Saat nomor kosong, format dokumen tetap menampilkan ruang nomor yang lebar di antara prefix dan suffix.
- Nomor kosong disimpan aman sebagai sequence 0 dan tidak mengubah nomor terakhir yang sudah digunakan.
- Menu/input Event dihapus dari alur pembuatan dan edit surat.
- Narasi UNTUK otomatis sekarang dibentuk langsung dari tujuan, kegiatan, dan tanggal.
- Nama file untuk surat tanpa nomor menggunakan penanda TANPA_NOMOR.
- Spasi dan ruang kosong bawaan template tetap dipertahankan.

# v2.2.0

- Hotfix Railway: `main.py` tidak lagi mengimpor `ensure_directories` dari `config.py`.
- Direktori `/data` dan `/data/documents` dibuat langsung oleh `main.py`.
- Log startup menampilkan `Bot Surat Tugas v2.2.0 mulai berjalan`.

## v2.1 - Railway startup hotfix

- Memperbaiki `ImportError: cannot import name 'ensure_directories' from 'config'`.
- Menambahkan kembali `ensure_directories()` untuk membuat `DATA_DIR` dan folder dokumen sebelum database/bot dijalankan.
- Tidak mengubah struktur database, sehingga Railway Volume `/data` versi sebelumnya tetap dapat digunakan.
- Smoke test generator DOCX/PDF untuk 2 dan 12 pegawai berhasil.

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

## v2.3.0 - Template Space Preserved
- Spasi kosong, paragraf kosong, dan jarak paragraf bawaan template tidak lagi dinormalisasi/dihapus.
- Font isi tetap Arial 12 tanpa mengubah layout, tab, indent, line spacing, atau blank space template.
- Blok tanda tangan hanya mengganti kota dan tanggal; layout, ruang tanda tangan, dan objek bawaan template dipertahankan.
- File contoh di folder `samples` dipertahankan sesuai contoh pengguna, termasuk ruang kosong yang memang disengaja.
