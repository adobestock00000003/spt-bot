# Tutorial Deploy Bot Surat Tugas ke Railway

## 1. Buat bot Telegram

1. Buka Telegram dan cari `@BotFather`.
2. Jalankan `/newbot`.
3. Tentukan nama dan username bot.
4. Salin token bot.

Token akan digunakan sebagai variable `BOT_TOKEN` di Railway.

## 2. Siapkan Telegram ID admin

Bot menyediakan perintah `/id` yang tetap dapat dipakai untuk melihat Telegram ID.

Cara praktis:

1. Deploy bot terlebih dahulu dengan `ADMIN_IDS` sementara memakai Telegram ID yang sudah diketahui, atau gunakan bot pencari Telegram ID yang Anda percayai.
2. Setelah bot aktif, kirim `/id`.
3. Simpan angka Telegram ID tersebut ke variable `ADMIN_IDS` di Railway.

Contoh:

```text
ADMIN_IDS=123456789
```

Bila admin lebih dari satu:

```text
ADMIN_IDS=123456789,987654321
```

## 3. Upload proyek ke GitHub

Struktur minimal yang harus ada:

```text
main.py
config.py
database.py
utils.py
services/
templates/
seeds/
Dockerfile
requirements.txt
railway.json
```

Jangan upload file `.env` yang berisi token asli.

## 4. Buat project Railway

1. Login ke Railway.
2. Pilih **New Project**.
3. Pilih **Deploy from GitHub Repo**.
4. Pilih repository bot.
5. Railway akan membaca `Dockerfile` dan membangun aplikasi.

## 5. Tambahkan Variables

Buka service bot → **Variables** dan tambahkan:

```text
BOT_TOKEN=TOKEN_DARI_BOTFATHER
ADMIN_IDS=TELEGRAM_ID_ANDA
DATA_DIR=/data
APP_TIMEZONE=Asia/Jakarta
```

`LOG_LEVEL=INFO` bersifat opsional.

## 6. Pasang Railway Volume

Ini wajib agar database, riwayat, DOCX, dan PDF tidak hilang ketika service restart atau redeploy.

1. Buka project Railway.
2. Pilih service bot.
3. Buka menu penyimpanan/volume pada service.
4. Tambahkan Volume.
5. Set mount path:

```text
/data
```

Pastikan variable:

```text
DATA_DIR=/data
```

Bot kemudian menyimpan:

```text
/data/spt_bot.db
/data/documents/
```

## 7. Redeploy

Setelah variable dan volume terpasang:

1. Lakukan redeploy/restart service.
2. Buka logs.
3. Pastikan muncul log:

```text
Bot Surat Tugas mulai berjalan
```

## 8. Tes bot

Di Telegram:

```text
/start
```

Menu yang seharusnya muncul:

```text
➕ Buat Surat Tugas
📋 Riwayat Surat
👥 Data Pegawai
📚 Dasar Hukum
🔢 Nomor Surat
📊 Statistik
⚙️ Kelola Pengguna   ← admin
```

## 9. Tambahkan operator

Sebagai admin:

1. Buka `⚙️ Kelola Pengguna`.
2. Pilih `➕ Tambah Operator`.
3. Masukkan Telegram ID operator.
4. Masukkan nama operator.

Operator kemudian dapat menggunakan bot tanpa mengubah variable Railway.


## Update dari versi 1 ke versi 2

Untuk pengguna yang sudah memakai bot versi 1 di Railway:

1. Ganti source code/repository dengan versi 2 ini.
2. **Jangan hapus Railway Volume `/data`** agar database dan riwayat surat lama tetap tersimpan.
3. Redeploy service.
4. Saat startup, bot akan memigrasikan dasar hukum default lama ke 3 dasar utama template 2026 **hanya bila data dasar hukum masih sama dengan default versi 1**. Data yang sudah pernah dikustomisasi admin tidak ditimpa otomatis.
5. Surat baru akan menampilkan pilihan Dasar nomor 4: **Gunakan**, **Edit**, atau **Hilangkan**.

## 10. Backup

Database utama berada di:

```text
/data/spt_bot.db
```

Dokumen berada di:

```text
/data/documents/
```

Untuk keamanan administrasi, lakukan backup Volume Railway secara berkala sesuai prosedur penyimpanan yang digunakan instansi.

## Troubleshooting

### Bot menjawab “Akses belum diberikan”

Pastikan Telegram ID ada di `ADMIN_IDS` atau sudah ditambahkan melalui menu admin.

### DOCX berhasil tetapi PDF tidak muncul

Periksa build Docker. `Dockerfile` sudah memasang `libreoffice-writer`. Cek logs apabila instalasi atau konversi gagal.

### Data hilang setelah redeploy

Biasanya Volume belum terpasang ke `/data` atau `DATA_DIR` tidak menggunakan `/data`.

### Bot tidak merespons

Periksa:

- `BOT_TOKEN` benar.
- Service status aktif.
- Logs tidak menunjukkan token invalid.
- Hanya satu instance bot yang menggunakan polling dengan token yang sama.
