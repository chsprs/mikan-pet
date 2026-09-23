# Checklist Pengujian dan Kualifikasi Rilis Mikan Pet

Dokumen ini adalah daftar uji manual dan tempat mencatat bukti rilis. Baris hanya boleh dinyatakan lulus bila benar-benar diuji pada lingkungan yang disebutkan.

## Matriks manual

| Area | Skenario | Bukti yang diperlukan | Status awal |
| --- | --- | --- | --- |
| OS x64 | Windows 10 22H2 x64 VM bersih: installer, launch, kontrol, persistensi, instance ganda, uninstall | Catatan VM dan hasil tiap langkah | Belum diverifikasi |
| OS x64 | Windows 11 x64 host fisik: installer, launch, kontrol, persistensi, instance ganda | Host, versi, dan hasil | Belum diverifikasi |
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
| Installer | Installer x64, Start Menu, pilihan shortcut Desktop | Artefak dan hasil install | Belum diverifikasi |
| Uninstall | Uninstaller menghapus `MikanPet.exe` | Bukti lokasi setelah uninstall | Belum diverifikasi |

## Perintah otomasi dan build

Jalankan dari PowerShell pada akar repositori:

```powershell
rg -n "MikanPet-Setup-x64.exe|scripts\\build.ps1|%APPDATA%\\MikanPet" README.md docs/testing-checklist.md
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m mikan_pet --smoke-test
.\scripts\build.ps1 -Python '.\.venv\Scripts\python.exe' -Architecture x64
git diff --check
git status --short
Get-FileHash '.\dist\MikanPet-Setup-x64.exe' -Algorithm SHA256
Get-Item '.\dist\MikanPet-Setup-x64.exe' | Select-Object FullName,Length,LastWriteTime
```

Rilis hanya menghasilkan satu paket distribusi Windows x64: `MikanPet-Setup-x64.exe`. Build lokal tidak ditandatangani kecuali parameter sertifikat diberikan; SmartScreen dapat memperingatkan **Unknown publisher**.

## Catatan hasil verifikasi

Hasil bertanggal, hash, lingkungan host, serta setiap celah pengujian ditambahkan di bawah ini oleh proses rilis.

### 2026-09-22 - Distribusi khusus Windows x64

- Versi lokal: 0.1.14.
- Seluruh 180 tes lulus, termasuk penolakan build dan executable non-x64.
- Build installer x64 berhasil; PE aplikasi terverifikasi sebagai 0x8664.
- Smoke test aplikasi dan GUI berhasil (exit code 0).
- Satu paket distribusi: `dist/MikanPet-Setup-x64.exe` (11.652.991 byte).
- SHA-256: `A865F9004EF9A46ADF41F1DD0CCA8DD10DE426A407F80FCA91A12D5C581B2440`.
- Build lokal tanpa parameter sertifikat; pengujian install/uninstall CI dan publikasi GitHub belum dijalankan pada pemeriksaan ini.

### 2026-09-22 - Animasi tambahan, tanpa build installer

- 12 pose tambahan: groom, stretch, scratch, tail, look, jump, music, yawn, sit, play, carried, land.
- 192 tes lulus. Dua tes `test_inno_*` dikecualikan karena keduanya mengompilasi installer.
- Regresi yang diperiksa: batas drag, goyangan sesuai arah, pendaratan dan pemulihan pose/timer, klik berulang, jeda perhatian kursor, serta musik dijeda saat diangkat atau melompat.
- Setiap frame tambahan diperiksa untuk batas 32 × 32, palet skin, pencerminan kiri/kanan, serta siluet tubuh yang tersambung. Bola benang diperlakukan sebagai objek terpisah.
- 2.352 gambar sprite berhasil dirender melalui Tk untuk seluruh pose, empat skin, dua arah, dan skala DPI 100/150/200%.
- Lembar frame Mikan, Byte, Mochi, dan Ash ditinjau secara visual; smoke test GUI dari source keluar dengan kode 0.
- Installer tidak dibangun ulang; executable distribusi yang sudah ada belum memuat perubahan animasi ini. Tidak ada commit, push, atau publikasi rilis pada pemeriksaan ini.

### 2026-09-23 - Penyempurnaan gerakan, tanpa build

- Menambah frame perantara untuk lompatan, pendaratan, grooming, peregangan, garukan, ekor, menguap, dan bola benang. Musik memakai anggukan lebih tenang dengan kedipan singkat.
- Tempo per frame: 90 ms untuk lompat/mendarat, 120 ms untuk aktivitas bertahap, dan 180 ms untuk pandangan/duduk/musik. Durasi total perilaku tetap konsisten.
- Kaki pose jongkok tetap di garis tanah; kepala saat melompat tetap identik dengan gambar asal yang hanya bergeser posisi.
- Animasi sekali jalan menahan frame terakhir, dan pemulihan setelah drag memakai waktu pose yang tersimpan. Goyangan menyaring jitter satu piksel tanpa menghambat perpindahan pet.
- 199 tes lulus; dua tes kompilasi installer tetap dikecualikan. Smoke test GUI dari source berhasil.
- 3.240 gambar berhasil dirender oleh Tk meliputi seluruh pose, empat skin, dua arah, serta DPI 100/150/200%. Lembar frame utama dan perbandingan lompat/diangkat/mendarat empat skin diperiksa secara visual.
- Pratinjau HTML diperbarui memakai tempo setiap pose yang sama dengan aplikasi.
- Tidak menjalankan build installer, commit, push, atau publikasi GitHub.

### 2026-09-23 - Preflight rilis v0.1.15

- Pengguna mengotorisasi build dan pembaruan GitHub.
- Empat file versi dan metadata paket lokal diselaraskan ke 0.1.15.
- Build lokal Windows x64 selesai, 201 tes lulus termasuk dua tes kompilasi installer. PE aplikasi 0x8664; smoke test executable dan GUI berhasil.
- SHA-256 installer build lokal (Python 3.14.6): `A750E82A26B0A035219E016294F2DF1504791D9909132F81A5D178B02D616F94`.
- Installer publik dibuat terpisah oleh GitHub Actions dengan Python 3.12; hash publik harus diverifikasi dari aset rilis, bukan hash build lokal ini.
- Secret sertifikat tidak tersedia pada pemeriksaan preflight; target rilis unsigned.
- Catatan perubahan lengkap disimpan di `docs/releases/v0.1.15.md`.
