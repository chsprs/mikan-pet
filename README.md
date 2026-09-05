# Mikan Pet untuk Windows

Mikan Pet adalah kucing pixel-art kecil yang berjalan di atas jendela biasa dan menyediakan kontrol media universal Windows.

## Instalasi

1. Jalankan `MikanPet-Setup-x64.exe`.
2. Ikuti wizard dan, bila diinginkan, pilih shortcut Desktop opsional.
3. Buka **Mikan Pet** dari Start Menu.

Installer memasang aplikasi untuk pengguna saat ini dan tidak memerlukan Python terpisah.

## Versi portabel

Ekstrak **semua** isi `MikanPet-portable-x64.zip` ke satu folder terlebih dahulu, lalu jalankan `MikanPet.exe` dari folder hasil ekstrak. Jangan menjalankan EXE langsung dari dalam arsip ZIP.

## Kontrol & Fitur

- Klik kucing untuk menampilkan atau menyembunyikan gelembung kontrol media.
- Seret kucing untuk memindahkannya. Pergerakan minimal 5 piksel logis setelah menekan mouse dihitung sebagai drag, bukan klik.
- Klik kanan kucing untuk membuka menu: mulai/berhenti berjalan, pilih skin, **Always on top**, reset posisi, **Periksa Pembaruan**, atau keluar.
- Tiga tombol media adalah **sebelumnya**, **putar/jeda**, dan **berikutnya**. Windows meneruskannya ke sesi media aktif.
- **Judul Lagu yang Diputar**: Mikan Pet secara otomatis mendeteksi sesi media Windows (GSMTC) dan menampilkan judul lagu beserta artis dalam gelembung mini di atas kucing.
- **Animasi Tidur Zzzz**: Ketika kucing tertidur (`SLEEP`), animasi huruf "Z" pixel-art naik secara prosedural.
- **Pembaruan Otomatis In-Place**: Klik kanan dan pilih **Periksa Pembaruan** untuk mengecek versi baru di GitHub Releases dan memperbarui aplikasi secara otomatis tanpa perlu menjalankan installer setup ulang.

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

Build pengembangan lokal ini **tidak ditandatangani**. Windows SmartScreen dapat menampilkan peringatan **Unknown publisher** sebelum instalasi atau eksekusi. Tidak ada klaim bahwa installer atau EXE ini memiliki tanda tangan kode; gunakan hanya artefak dari sumber yang Anda percayai.

## Pengembangan dan build

Jalankan perintah berikut dari PowerShell pada akar repositori.

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m mikan_pet
.\scripts\build.ps1 -Python '.\.venv\Scripts\python.exe'
```

Build menghasilkan `dist\MikanPet-Setup-x64.exe` dan `dist\MikanPet-portable-x64.zip`. Lihat `docs\testing-checklist.md` untuk prosedur verifikasi manual dan status rilis.

## Sistem yang didukung

Target paket adalah Windows 10 dan Windows 11 x64. Windows 11 pada ARM dapat menjalankan paket x64 melalui emulasi Windows; paket ARM64 native bukan bagian dari rilis ini. Windows 7/8, Windows 32-bit, macOS, dan Linux tidak didukung.
