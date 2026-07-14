# Bot Surat Tugas — Bidang Pemasaran dan Kelembagaan Parekraf

Bot Telegram untuk membuat, menyimpan, mengunduh, menduplikasi, dan merevisi Surat Tugas berdasarkan template resmi Word yang diberikan.

## Fitur versi 2.5

- Pembuatan Surat Tugas melalui tombol Telegram.
- Multi-pilih pegawai dari 24 data pegawai pada Excel `DATA PEGAWAI BID PEMASARAN.xlsx`.
- Pencarian pegawai berdasarkan nama, jabatan, atau NIP/NPPK/NIPTT.
- Perhitungan durasi otomatis, termasuk bentuk terbilang: `4 (empat) hari`.
- Penyusunan otomatis narasi bagian `UNTUK`.
- Preview sebelum dokumen dibuat.
- Edit tujuan, kegiatan, tanggal, nomor, narasi, dan Dasar nomor 4 sebelum generate.
- Nomor surat dapat dilewati/dikosongkan sementara; dokumen mempertahankan ruang nomor yang lebar.
- Input Event/Acara dihapus; nama event dapat langsung ditulis sebagai bagian dari Kegiatan bila diperlukan.
- Nomor surat semi otomatis dengan format default `000.1.2.3 / [NOMOR] / 118.4 / [TAHUN]`.
- Output DOCX menggunakan template `SPT 2026 FIX` dan output PDF melalui LibreOffice.
- Dasar hukum utama memakai nomor 1-3 dari template 2026; Dasar nomor 4 bersifat opsional dan dapat digunakan, diedit, atau dihilangkan per surat.
- Isi surat menggunakan font Arial ukuran 12 pt.
- Layout daftar pegawai dibuat adaptif; setiap blok pegawai dijaga agar tidak terpotong di tengah saat berpindah halaman.
- Blok `UNTUK` dan tanda tangan mengalir otomatis ke halaman berikutnya jika jumlah pegawai banyak.
- Riwayat surat tersimpan di SQLite.
- Kirim ulang DOCX/PDF dari riwayat.
- Duplikat surat lama untuk kegiatan serupa.
- Revisi surat dengan versi baru.
- Data pegawai aktif/nonaktif.
- Tambah pegawai dari Telegram oleh admin.
- Dasar hukum utama 1-3 tersimpan di database dan dapat diedit oleh admin.
- Admin dan operator berbasis Telegram ID.
- Statistik sederhana.
- Penyimpanan persisten kompatibel dengan Railway Volume di `/data`.

### Penyempurnaan layout v2.5
- Satu baris kosong dipertahankan setelah **MEMERINTAHKAN** sebelum **KEPADA**.
- **KEPADA** memakai format asli template dan tidak ditulis ulang oleh generator.
- Jabatan Ali Afandi: **Kepala Bidang Pemasaran dan Kelembagaan Parekraf**.
- Baris penetapan tanggal sejajar dengan blok Kepala Dinas.


## Struktur proyek

```text
spt_telegram_bot/
├── main.py
├── config.py
├── database.py
├── utils.py
├── services/
│   └── document_service.py
├── templates/
│   └── SPT_template.docx
├── seeds/
│   ├── employees.json
│   └── DATA_PEGAWAI_BID_PEMASARAN.xlsx
├── samples/
│   └── contoh hasil DOCX/PDF
├── Dockerfile
├── railway.json
├── requirements.txt
├── .env.example
└── smoke_test.py
```

## Data pegawai

Database awal berisi 24 pegawai yang diambil dari sheet `update` pada file Excel sumber. Spasi pada NIP/NPPK yang hanya berupa angka dinormalisasi agar konsisten, sedangkan ID berformat khusus dengan tanda hubung tetap dipertahankan.

Contoh:

```text
ACHMAD RIZA MAULANA, S.T.
Jabatan      : Penata Layanan Operasional
Pangkat/Gol  : -/IX
NIP          : 199606062025211002
```

## Menjalankan lokal

1. Buat bot dari `@BotFather` dan salin token.
2. Salin `.env.example` menjadi `.env` atau set environment variable secara manual.
3. Isi `BOT_TOKEN` dan `ADMIN_IDS`.
4. Install dependency:

```bash
pip install -r requirements.txt
```

5. Jalankan:

```bash
python main.py
```

Untuk PDF, server perlu memiliki LibreOffice. Tanpa LibreOffice, DOCX tetap dapat dibuat.

## Perintah Telegram

- `/start` — buka menu utama.
- `/menu` — kembali ke menu utama.
- `/cancel` — batalkan alur yang sedang berjalan.
- `/id` — tampilkan Telegram ID pengguna.

## Hak akses

### Admin

- Semua fitur operator.
- Tambah/nonaktifkan pegawai.
- Edit dasar hukum utama 1-3.
- Atur nomor terakhir, prefix, dan suffix nomor surat.
- Tambah/nonaktifkan operator.

### Operator

- Buat Surat Tugas.
- Lihat riwayat.
- Download ulang dokumen.
- Duplikat dan revisi surat.
- Lihat data pegawai, dasar hukum, dan statistik.

## Penyimpanan

Semua data persisten disimpan di `DATA_DIR`.

Untuk Railway, gunakan:

```text
DATA_DIR=/data
```

Lalu mount Railway Volume ke:

```text
/data
```

Yang tersimpan di sana:

```text
/data/spt_bot.db
/data/documents/*.docx
/data/documents/*.pdf
```

Jangan menyimpan database hanya di filesystem sementara container karena data bisa hilang saat redeploy.

## Template Surat Tugas

Template aktif:

```text
templates/SPT_template.docx
```

Generator mempertahankan kop, logo, dan format utama template 2026. Bagian isi surat dibangun secara adaptif agar tetap rapi saat jumlah pegawai banyak. Font isi surat adalah Arial 12 pt. Bagian yang diubah otomatis:

- Nomor surat.
- Dasar hukum utama 1-3 dan Dasar nomor 4 opsional.
- Daftar pegawai.
- Bagian `UNTUK`.
- Tanggal penetapan.

## Uji cepat

```bash
python smoke_test.py
```

Tes akan membuat contoh 2 pegawai dan stress test 12 pegawai, lalu mencoba mengonversinya menjadi PDF.

## Catatan penting nomor surat

Nomor surat menggunakan mode semi otomatis. Bot memberi saran nomor berikutnya, tetapi operator tetap bisa mengganti nomor sebelum dokumen dibuat. Ini mencegah benturan jika penomoran juga digunakan oleh proses administrasi lain di luar bot.

### Aturan preservasi template (v2.4)
Bot tidak menghapus atau merapatkan paragraf kosong/space kosong yang sudah ada di template resmi. Normalisasi font ke Arial 12 hanya mengubah font, bukan jarak paragraf, line spacing, tab, indent, atau ruang tanda tangan. Jika template resmi memiliki ruang kosong yang disengaja, ruang tersebut dipertahankan.
