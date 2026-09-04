# Checklist Pengujian dan Kualifikasi Rilis Mikan Pet

Dokumen ini adalah daftar uji manual dan tempat mencatat bukti rilis. Baris hanya boleh dinyatakan lulus bila benar-benar diuji pada lingkungan yang disebutkan.

## Matriks manual

| Area | Skenario | Bukti yang diperlukan | Status awal |
| --- | --- | --- | --- |
| OS x64 | Windows 10 22H2 x64 VM bersih: installer, launch, kontrol, persistensi, instance ganda, uninstall | Catatan VM dan hasil tiap langkah | Belum diverifikasi |
| OS x64 | Windows 11 x64 host fisik: installer/portable, launch, kontrol, persistensi, instance ganda | Host, versi, dan hasil | Belum diverifikasi |
| ARM | Windows 11 ARM melalui emulasi x64 | Perangkat/VM ARM dan hasil launch | Belum diverifikasi |
| DPI | 100% scaling | Pet tetap tajam, ukuran/hit target benar | Belum diverifikasi |
| DPI | 150% scaling | Pet tetap tajam, ukuran/hit target benar | Belum diverifikasi |
| DPI | 200% scaling | Pet tetap tajam, ukuran/hit target benar | Belum diverifikasi |
| Monitor | Satu monitor: roaming/reversal di batas work area, drag, reset posisi | Rekaman observasi | Belum diverifikasi |
| Monitor | Lebih dari satu monitor: drag/transfer antarlayar | Rekaman observasi | Belum diverifikasi |
| Mixed DPI | Dua monitor dengan DPI berbeda: lintas dua arah, ukuran tajam, tetap on-screen, hit target dapat dipakai | Konfigurasi dan observasi | Belum diverifikasi |
| Interaksi | Transparansi, always-on-top, jalan, reversal, idle, blink, sleep, stopped, klik show/hide, drag threshold | Rekaman observasi | Belum diverifikasi |
| Skin | Mikan, Byte, Mochi berubah tanpa restart | Rekaman observasi | Belum diverifikasi |
| Media | Spotify: previous/play-pause/next pada sesi aktif | Sesi disposable dan hasil | Belum diverifikasi |
| Media | YouTube di browser: previous/play-pause/next pada sesi aktif | Sesi disposable dan hasil | Belum diverifikasi |
| Media | Satu pemutar media native: previous/play-pause/next pada sesi aktif | Sesi disposable dan hasil | Belum diverifikasi |
| Persistensi | Posisi, skin, motion, controls, topmost bertahan setelah Keluar dan relaunch | Konfigurasi sebelum/sesudah | Belum diverifikasi |
| Instance ganda | Peluncuran kedua tidak membuat pet kedua | Jumlah jendela/proses | Belum diverifikasi |
| Installer | `MikanPet-Setup-x64.exe`, Start Menu, pilihan shortcut Desktop | Artefak dan hasil install | Belum diverifikasi |
| Portable | Ekstrak semua isi `MikanPet-portable-x64.zip`, lalu launch EXE hasil ekstrak | Lokasi ekstrak dan hasil | Belum diverifikasi |
| Uninstall | Uninstaller menghapus `MikanPet.exe` | Bukti lokasi setelah uninstall | Belum diverifikasi |

## Perintah otomasi dan build

Jalankan dari PowerShell pada akar repositori:

```powershell
rg -n "MikanPet-Setup-x64.exe|MikanPet-portable-x64.zip|scripts\\build.ps1|%APPDATA%\\MikanPet" README.md docs/testing-checklist.md
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m mikan_pet --smoke-test
.\scripts\build.ps1 -Python '.\.venv\Scripts\python.exe'
git diff --check
git status --short
Get-FileHash '.\dist\MikanPet-Setup-x64.exe' -Algorithm SHA256
Get-FileHash '.\dist\MikanPet-portable-x64.zip' -Algorithm SHA256
Get-Item '.\dist\MikanPet-Setup-x64.exe','.\dist\MikanPet-portable-x64.zip' | Select-Object FullName,Length,LastWriteTime
```

Artefak yang diharapkan adalah `dist\MikanPet-Setup-x64.exe` dan `dist\MikanPet-portable-x64.zip`. Build lokal tidak ditandatangani; SmartScreen dapat memperingatkan **Unknown publisher**.

## Catatan hasil verifikasi

Hasil bertanggal, hash, lingkungan host, serta setiap celah pengujian ditambahkan di bawah ini oleh proses rilis.
