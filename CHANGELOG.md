## v3.4.0 — Lengkapi surat setelah export

- Menambahkan tombol **Lengkapi Nomor / Tanggal / TTD** setelah Surat Tugas standar selesai diekspor dan pada detail Riwayat Surat.
- Surat yang sama dapat diisi atau diubah nomor suratnya, tanggal penetapannya, serta pilihan memakai/tidak memakai tanda tangan Kepala Dinas.
- Export ulang memperbarui baris surat yang sama di database dan menaikkan versi dokumen; jumlah Surat Tugas di riwayat tidak bertambah.
- Data pegawai, tujuan, kegiatan, Dasar, dan narasi UNTUK tetap memakai snapshot surat lama sehingga tidak perlu membuat Surat Tugas dari awal.
- Bulan dan tahun penetapan tetap mengikuti bulan/tahun jadwal berangkat; hanya angka tanggal yang dapat diisi atau dikosongkan.
- Menambahkan penyimpanan status tanda tangan dan waktu pembaruan pada database dengan migrasi otomatis untuk Railway lama.
- File lama di volume tidak dihapus secara otomatis; Riwayat selalu menunjuk DOCX/PDF versi terbaru.

## v3.3.0 — Pembaruan Pangkat/Golongan Ismadi

- Pangkat/Golongan **ISMADI, SE., MM.** diubah dari **Penata (III/c)** menjadi **Penata Tk. I (III/d)**.
- Seed JSON dan Excel telah diperbarui.
- Database Railway lama dimigrasikan otomatis saat bot restart; volume `/data` tidak perlu dihapus.

# Changelog

## v3.2.0 — Tanggal penetapan opsional
- Tanggal (angka hari) penetapan surat dapat dilewati/dikosongkan terlebih dahulu.
- Bulan dan tahun penetapan selalu otomatis mengikuti bulan dan tahun jadwal berangkat.
- Jika dikosongkan, dokumen menampilkan ruang tanggal yang lebar sebelum nama bulan dan tahun, misalnya `pada tanggal          Juni 2026`.
- Input penetapan cukup berupa angka hari 1–31; format tanggal lengkap masih diterima, tetapi bulan/tahun tetap disamakan dengan jadwal berangkat.
- Preview, riwayat, revisi, duplikasi, export standar, dan TNDE mempertahankan status tanggal kosong.
- Migrasi database otomatis menambahkan kolom `issue_day_blank`; Volume `/data` lama tetap aman.

## v3.1.0

- Ukuran tanda tangan Kepala Dinas disesuaikan dengan contoh SPT 2026 FIX(1).
- Lebar tanda tangan diperbesar secara proporsional dari 1,45 inci menjadi 1,70 inci.
- Posisi tanda tangan dikoreksi ke kiri agar pusat goresan lebih presisi di atas nama Kepala Dinas.
- Pilihan tanda tangan tetap opsional untuk Surat Tugas standar.
- Export TNDE tetap tanpa gambar tanda tangan manual.
- Pagination safety dan ruang kosong template tetap dipertahankan.

## v3.0.0

- Tanda tangan Kepala Dinas pada Surat Tugas standar sekarang opsional dan dipilih secara eksplisit saat generate.
- Menambahkan pilihan `Pakai Tanda Tangan` atau `Tanpa Tanda Tangan`; export TNDE tetap selalu tanpa tanda tangan manual.
- Posisi tanda tangan dikoreksi secara optik ke kiri agar lebih presisi terhadap blok nama Kepala Dinas.
- Ukuran tanda tangan diperkecil dan posisi vertikal dinaikkan agar pas di ruang tanda tangan dan tidak menabrak nama pejabat.
- Nama file standar membedakan `_DENGAN_TTD` dan `_TANPA_TTD` agar dua mode tidak saling menimpa.
- Pagination safety dan preservasi blank space template tetap aktif.

## v2.9.0

- Menambahkan tanda tangan Kepala Dinas default dari file `TTD Bu Kadis.png`.
- Tanda tangan otomatis disisipkan hanya pada Surat Tugas biasa (DOCX/PDF).
- Export TNDE tetap tanpa gambar tanda tangan dan tetap memakai placeholder `${qrcode}`, `${PEJABAT}`, `${pangkat}`, dan `${nip}`.
- Gambar tanda tangan dibuat transparan dan hanya padding transparan yang dipangkas; goresan tanda tangan tidak diubah.
- Tanda tangan ditempatkan sebagai overlay pada ruang kosong resmi di blok Kepala Dinas sehingga space template tidak dihapus atau dipadatkan.
- Pagination dan pemeriksaan NIP Kepala Dinas tetap aktif untuk kasus pegawai banyak.

## v2.8.0

- Menambahkan export khusus **Versi TNDE** dari preview dan riwayat surat.
- Menambahkan template `SPT_template_TNDE.docx` berdasarkan contoh TNDE yang diberikan.
- Nomor dan identitas penandatangan TNDE dipertahankan sebagai placeholder `${nomor}`, `${qrcode}`, `${PEJABAT}`, `${pangkat}`, dan `${nip}`.
- Menambahkan footer informasi tanda tangan elektronik BSrE-BSSN beserta logo Balai Sertifikasi Elektronik.
- Export TNDE menghasilkan DOCX dan PDF preview.
- Data pegawai, Dasar nomor 4 opsional, UNTUK, dan tanggal penetapan tetap mengikuti data surat.
- Menambahkan safety pagination khusus TNDE agar blok tanda tangan tidak bertabrakan dengan footer.

## v2.7.0

- Memperbaiki kasus 4-5 pegawai ketika baris **NIP Kepala Dinas** dapat terpotong di bawah halaman.
- Jarak antardata pegawai dibuat adaptif: tetap lega untuk 1-3 pegawai dan sedikit lebih kompak mulai 4 pegawai, tanpa menghapus space kosong bawaan template.
- Menambahkan pemeriksaan geometri hasil PDF. Jika blok tanda tangan tidak muat utuh, bot otomatis memindahkan bagian **UNTUK + tanda tangan** ke halaman berikutnya.
- Template, blank space resmi, posisi KEPADA, dan ruang tanda tangan tetap dipertahankan.

## v2.6.0
- Menyesuaikan jarak setelah **MEMERINTAHKAN** agar pas seperti template contoh: tidak ada paragraf kosong tambahan yang memperlebar jarak.
- Menghapus spacer tambahan sebelum daftar pegawai sehingga blok **KEPADA** tetap rapat dan rapi.
- Format, teks, tab, dan tanda titik dua pada **KEPADA** tetap tidak diubah.

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
