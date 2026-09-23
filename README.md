# Mikan Pet untuk Windows

Mikan Pet adalah kucing pixel-art kecil yang berjalan di atas jendela biasa dan menyediakan kontrol media universal Windows.

## Instalasi

1. Jalankan `MikanPet-Setup-x64.exe` pada Windows 10/11 x64.
2. Ikuti wizard dan, bila diinginkan, pilih shortcut Desktop opsional.
3. Buka **Mikan Pet** dari Start Menu.

Installer memasang aplikasi untuk pengguna saat ini dan tidak memerlukan Python terpisah.

## Kontrol & Fitur

- Klik kucing untuk menampilkan atau menyembunyikan gelembung kontrol media.
- Seret kucing untuk memindahkannya. Pergerakan minimal 5 piksel logis setelah menekan mouse dihitung sebagai drag, bukan klik.
- Klik kanan kucing untuk membuka menu: mulai/berhenti berjalan, pilih skin, **Always on top**, reset posisi, **Periksa Pembaruan**, atau keluar.
- Tiga tombol media adalah **sebelumnya**, **putar/jeda**, dan **berikutnya**. Windows meneruskannya ke sesi media aktif.
- **Judul Lagu yang Diputar**: Mikan Pet secara otomatis mendeteksi sesi media Windows (GSMTC) dan menampilkan judul lagu beserta artis dalam gelembung mini di atas kucing.
- **Animasi Tidur Zzzz**: Ketika kucing tertidur (`SLEEP`), animasi huruf "Z" pixel-art naik secara prosedural.
- **Pembaruan melalui Installer**: Klik kanan dan pilih **Periksa Pembaruan** untuk mengecek versi baru di GitHub Releases. Setelah disetujui, aplikasi mengunduh dan menjalankan installer x64. SHA-256 diverifikasi bila digest tersedia dari GitHub.

## Animasi tambahan

Kucing bergantian duduk melihat sekitar, membersihkan wajah, menggaruk telinga, mengibas ekor dan telinga, serta menerkam bola benang. Sebelum tidur kucing menguap, lalu meregangkan badan setelah bangun. Aktivitas tetap berjalan saat mode berjalan dihentikan, tanpa mengubah posisi pet.

- Kursor yang mendekat saat istirahat menarik pandangan kucing, dengan jeda agar tidak terus menginterupsi aktivitas.
- Klik memicu lompatan kecil sekaligus menampilkan/menyembunyikan kontrol media.
- Setelah ambang drag terlewati, kucing menggantung dengan kaki rileks dan badan bergoyang mengikuti arah gerakan. Saat dilepas, kucing mendarat lalu melanjutkan pose dan mode sebelumnya.
- Ketika media sedang diputar, kucing sesekali mengangguk di sela aktivitas. Gerakan mengikuti status pemutaran, bukan sinkronisasi ketukan audio.
- Semua frame tambahan memakai kanvas 32 × 32 dan palet empat skin asli. Bentuk kepala dipertahankan tanpa peregangan gambar.
- Lompatan dan pendaratan memakai frame perantara yang lebih rapat. Gerakan kecil kursor tidak membuat badan bergetar, dan aktivitas yang terpotong drag dilanjutkan dari tahap sebelumnya.

Pratinjau semua frame dan animasi tanpa membuat installer:

```powershell
.\.venv\Scripts\python.exe -m scripts.preview_animations "$env:TEMP\MikanPet-animation-preview"
```

Buka `index.html` di folder keluaran untuk memilih skin, arah, jeda, atau melihat frame satu per satu.

## Skin

Tersedia empat variasi skin pixel-art 3/4 yang dapat diganti langsung tanpa restart melalui menu klik kanan:

- **Mikan** — kucing tabby oranye dengan belang punggung dan perut krem.
- **Byte** — kucing hitam arang pekat dengan mata emas amber.
- **Mochi** — kucing putih bersih dengan mata biru langit.
- **Ash** — kucing tabby abu-abu dengan corak perut merah muda.

## Pengaturan

Preferensi, posisi, skin, status berjalan, gelembung kontrol, dan Always on top tersimpan di `%APPDATA%\MikanPet\settings.json`. Posisi yang tidak lagi terlihat setelah konfigurasi monitor berubah akan dipulihkan ke area layar utama yang aman.

## Pemecahan masalah

- Kontrol media hanya bekerja bila Windows memiliki sesi media aktif, misalnya Spotify, YouTube di browser, atau pemutar media native. Bila tidak ada sesi yang memenuhi syarat, tombol akan menjadi no-op tanpa pesan kesalahan.
- Jika kucing berada di luar layar, klik kanan lalu pilih **Reset posisi**.
- Hanya satu Mikan Pet dapat berjalan. Peluncuran kedua akan keluar tanpa membuat kucing kedua.
- Untuk menutup aplikasi, klik kanan kucing dan pilih **Keluar**.

## Catatan keamanan

Build rilis hanya ditandatangani Authenticode bila maintainer telah mengonfigurasi secret `WINDOWS_CERT_BASE64` dan `WINDOWS_CERT_PASSWORD` di GitHub Actions. Tanpa sertifikat tersebut, Windows SmartScreen dapat menampilkan peringatan **Unknown publisher**. Rilis publik berisi tepat satu aset: `MikanPet-Setup-x64.exe`.

## Pengembangan dan build

Jalankan perintah berikut dari PowerShell pada akar repositori.

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m mikan_pet
.\scripts\build.ps1 -Python '.\.venv\Scripts\python.exe' -Architecture x64
```

Paket distribusi berada di `dist\MikanPet-Setup-x64.exe`. Folder `dist\MikanPet` merupakan input internal untuk pembuatan installer.

## Alur Rilis & Push GitHub

Untuk merilis versi baru ke GitHub secara otomatis (sinkronisasi versi, tes unit, git commit, tag, push, dan pantauan CI):

```powershell
powershell -ExecutionPolicy Bypass -File scripts/release.ps1 -Version "0.1.6" -Message "feat: deskripsi perubahan"
```

Skrip ini akan secara otomatis:
1. Memperbarui nomor versi di 4 berkas (`pyproject.toml`, `__init__.py`, `app.py`, `MikanPet.iss`).
2. Menjalankan seluruh tes unit.
3. Melakukan git commit dan tag `vX.Y.Z`.
4. Mendorong commit dan tag ke GitHub (`git push origin main vX.Y.Z`).
5. Memantau workflow GitHub Actions hingga installer Windows x64 selesai dibangun dan dipublikasikan di GitHub Releases.

Detail dan panduan lengkap dapat dilihat pada skill `.agents/skills/mikan-release/SKILL.md`.

## Sistem yang didukung

Aplikasi hanya mendukung Windows 10/11 x64 dengan distribusi installer `MikanPet-Setup-x64.exe`.
