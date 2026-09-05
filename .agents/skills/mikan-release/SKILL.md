---
name: mikan-release
description: Use when bumping versions, pushing updates to GitHub, releasing new Windows binaries, or managing the auto-update pipeline for Mikan Pet
---

# Mikan Pet Release & GitHub Push Workflow

## Overview
Panduan operasional standar untuk mempublikasikan pembaruan Mikan Pet ke GitHub, membangun binary Windows (Installer & Portable), serta memastikan pipeline auto-updater in-place berfungsi tanpa kendala bagi pengguna akhir.

## When to Use
- Mengirim fitur baru, skin baru, atau bugfix ke repositori GitHub.
- Merilis versi baru aplikasi (`vX.Y.Z`) agar dapat diunduh oleh pengguna.
- Memastikan pembaruan otomatis (in-place auto-updater) mendeteksi rilis baru.

**When NOT to Use:**
- Eksperimen lokal yang belum siap rilis (gunakan branch kerja biasa tanpa tag).
- Perubahan kecil pada dokumentasi yang tidak memerlukan bump versi aplikasi.

---

## Quick Reference

| Kebutuhan | Perintah / Tindakan |
|---|---|
| **Rilis Otomatis (Rekomendasi)** | `powershell -ExecutionPolicy Bypass -File scripts/release.ps1 -Version "0.1.6" -Message "feat: deskripsi perubahan"` |
| **Pemeriksaan Tes Manual** | `.\.venv\Scripts\python.exe -m unittest discover -s tests` |
| **Uji Build & Smoke Test GUI** | `powershell -ExecutionPolicy Bypass -File scripts/build.ps1 -Python ".\.venv\Scripts\python.exe" -SkipInstaller` |
| **Cek Status CI/CD GitHub** | `gh run list --limit 3` atau `gh run watch <run_id>` |
| **Verifikasi Catatan Rilis** | `gh release view vX.Y.Z` |

---

## 4 File Wajib Sinkronisasi Versi

Setiap kali versi aplikasi dinaikkan, 4 berkas berikut **wajib sama persis**:

1. [pyproject.toml](file:///d:/BACKUP/Documents/aplikasi%20AI/PET/pyproject.toml) -> `version = "X.Y.Z"`
2. [mikan_pet/__init__.py](file:///d:/BACKUP/Documents/aplikasi%20AI/PET/mikan_pet/__init__.py) -> `__version__ = "X.Y.Z"`
3. [mikan_pet/app.py](file:///d:/BACKUP/Documents/aplikasi%20AI/PET/mikan_pet/app.py) -> `VERSION = "X.Y.Z"`
4. [installer/MikanPet.iss](file:///d:/BACKUP/Documents/aplikasi%20AI/PET/installer/MikanPet.iss) -> `#define MyAppVersion "X.Y.Z"`

*(Catatan: Script `scripts/release.ps1` memperbarui keempat file ini secara otomatis).*

---

## Alur Rilis Step-by-Step (The Iron Pipeline)

```
1. Verifikasi Kode & Tes (169/169 Lolos)
         │
         ▼
2. Sinkronisasi Versi (4 File di atas)
         │
         ▼
3. Komit & Buat Tag Git (vX.Y.Z)
         │
         ▼
4. Push ke GitHub (main + tags)
         │
         ▼
5. Tunggu GitHub Actions Selesai (Status OK, ~2 menit)
         │
         ▼
6. Verifikasi Aset & Catatan Rilis di GitHub
         │
         ▼
7. Verifikasi Auto-Updater dari Aplikasi Desktop
```

---

## Cara Kerja Auto-Updater Mikan Pet

1. **Pengecekan Versi:**
   - Aplikasi memanggil GitHub API: `GET https://api.github.com/repos/chsprs/mikan-pet/releases/latest`.
   - Membandingkan `release.version` dengan `__version__` lokal via tuple integer (`(0, 1, 5) > (0, 1, 4)`).
2. **Pengunduhan di Latar Belakang:**
   - Mengunduh berkas `MikanPet-portable-x64.zip` ke folder sementara `%TEMP%\mikan_update_<version>`.
   - Menampilkan notifikasi info ke pengguna bahwa download sedang berlangsung.
3. **In-Place Replacement:**
   - Menulis skrip `_mikan_update.cmd`.
   - Menghentikan proses `MikanPet.exe` lama (`taskkill`).
   - Menyalin berkas baru dengan `xcopy /E /I /Y /Q /H /R`.
   - Menjalankan kembali executable baru dengan flag direktori kerja: `start "" /D "{install_dir}" "{target_exe}"`.
   - Menghapus skrip sementara secara bersih.

---

## Tabel Rasionalisasi & Kesalahan Umum

| Alasan / Godaan | Realita & Bahaya | Solusi Wajib |
|---|---|---|
| *"Saya push langsung tanpa cek tes, kodenya sepele"* | Kode sepele sering memecahkan regresi sprite atau updater. | Selalu jalankan tes unit sebelum push. |
| *"Saya sudah push, jadi saya beritahu user rilis sudah siap"* | GitHub Actions butuh 1-2 menit untuk build Windows. Jika user coba update seketika, rilis belum ada dan updater menolak. | **Pantau CI sampai berstatus [ok]** sebelum mengonfirmasi ke pengguna. |
| *"Lupa push tag (`git push` tanpa `--tags`)"* | Workflow release GitHub Actions hanya terpicu oleh tag `v*`. Tanpa tag, rilis tidak terbuat. | Selalu gunakan `git push origin main --tags`. |
| *"Catatan rilis di GitHub kosong"* | GitHub `generate_release_notes` default butuh Pull Request. | Pastikan workflow `.github/workflows/release.yml` menyertakan step pembuatan catatan komit (`body_path: release_notes.md`). |

---

## Red Flags - STOP dan Verifikasi!

- Memberi tahu pengguna "pembaruan sudah bisa diunduh" padahal workflow GitHub Actions masih kuning/running.
- `gh release view vX.Y.Z` menghasilkan output "release not found".
- Tag di git lokal belum dipush ke remote origin.
- Salah satu dari 4 file versi tidak sinkron.

---

## Verification Checklist

Sebelum menyatakan rilis selesai ke pengguna:
- [ ] Semua 169 unit test lolos di lokal.
- [ ] Empat file versi sinkron di angka versi yang sama.
- [ ] Komit dan tag `vX.Y.Z` sudah ada di GitHub (`git push origin main --tags`).
- [ ] Workflow GitHub Actions berstatus hijau / `[ok]` (`gh run list`).
- [ ] Halaman rilis GitHub memuat berkas `MikanPet-Setup-x64.exe` dan `MikanPet-portable-x64.zip`.
- [ ] Catatan rilis di GitHub memuat ringkasan fitur & komit yang jelas.
