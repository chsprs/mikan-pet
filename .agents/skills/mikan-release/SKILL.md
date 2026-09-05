---
name: mikan-release
description: Use for an explicitly authorized Mikan Pet version bump, GitHub push, or Windows x64 installer release, or for auditing that single-asset release and its updater path. Do not use for ordinary local edits that are not being published.
---

# Mikan Pet Release

Panduan untuk merilis Mikan Pet sebagai satu installer Windows x64 di GitHub dan memastikan jalur update aplikasi sesuai dengan kebijakan tersebut.

## Kebijakan Distribusi

GitHub Release publik hanya membutuhkan satu aset:

```text
MikanPet-Setup-x64.exe
```

Jangan menjadikan ARM64, portable ZIP, `SHA256SUMS.txt`, atau provenance attestation sebagai syarat release maupun aset tambahan. Bila workflow, script release, atau updater lama masih menghasilkan atau mencari aset tersebut, selaraskan implementasinya dengan kebijakan ini sebelum mengumumkan release.

## Batas Otorisasi

- Audit, pemeriksaan status, dan validasi lokal bersifat read-only.
- Hanya commit, push, tag, membuat/mengubah GitHub Release, atau mengatur GitHub secret bila pengguna secara eksplisit meminta publikasi atau perubahan eksternal tersebut.
- Jangan menghapus atau memindahkan tag yang sudah dipush tanpa izin eksplisit. Untuk release gagal, perbaiki di `main` dan gunakan versi patch berikutnya.
- Jangan mengklaim binary ditandatangani jika certificate secrets tidak tersedia.

## Sumber Kebenaran

- `scripts/release.ps1`: bump versi, tes, commit, tag, push, menunggu workflow, lalu memeriksa aset release.
- `scripts/build.ps1`: build installer x64 lokal dan signing opsional.
- `.github/workflows/release.yml`: build, smoke test, dan publish installer x64 tunggal.
- File versi yang harus sama:
  - `pyproject.toml` — `version = "X.Y.Z"`
  - `mikan_pet/__init__.py` — `__version__ = "X.Y.Z"`
  - `mikan_pet/app.py` — `VERSION = "X.Y.Z"`
  - `installer/MikanPet.iss` — `#define MyAppVersion "X.Y.Z"`

Jangan gunakan jumlah tes, durasi workflow, atau nomor versi contoh sebagai syarat tetap; semuanya dapat berubah.

## Alur Rilis

### 1. Preflight

Pastikan worktree hanya berisi perubahan yang memang akan dirilis:

```powershell
git status --short --branch
git fetch --tags origin
git tag --list "vX.Y.Z"
git ls-remote --tags origin "refs/tags/vX.Y.Z"
gh release view "vX.Y.Z"
```

`scripts/release.ps1` memakai `git add -A`, sehingga file tidak terkait atau untracked ikut masuk ke commit. Berhenti dan pisahkan perubahan jika scope belum bersih.

Pilih versi SemVer baru dan pastikan tag/release itu belum ada. Jalankan tes dan build installer x64 bila perubahan menyentuh runtime, packaging, updater, aset, atau startup:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
powershell -ExecutionPolicy Bypass -File scripts/build.ps1 -Python ".\.venv\Scripts\python.exe" -Architecture x64
```

### 2. Selaraskan Pipeline Sebelum Publish

Sebelum rilis, pastikan semua bagian berikut hanya merujuk `MikanPet-Setup-x64.exe`:

- `scripts/release.ps1` memverifikasi satu aset itu saja.
- Workflow membangun dan mengunggah installer x64, bukan matriks ARM64 atau portable ZIP.
- Release GitHub tidak mengunggah checksum atau aset lain.
- Updater tidak mencari portable ZIP/ARM64 dan tidak mencoba ekstraksi ZIP.

Perubahan kebijakan aset bukan izin otomatis untuk memodifikasi pipeline atau mempublikasikan release; lakukan perubahan itu hanya sesuai permintaan pengguna.

### 3. Publikasikan

Gunakan script resmi setelah implementasi selaras dengan kebijakan satu aset:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/release.ps1 -Version "X.Y.Z" -Message "feat: ringkasan perubahan"
```

Jangan menjalankan perintah ini untuk audit saja: perintah tersebut mengubah file, membuat commit/tag, dan mendorongnya ke GitHub.

### 4. Verifikasi GitHub Actions

Cocokkan run dengan commit tag; jangan hanya mengambil run terbaru jika ada workflow lain yang berjalan:

```powershell
gh run list --workflow release.yml --limit 5
gh run view <run_id> --json status,conclusion,url,headSha,event,jobs
git rev-list -n 1 "vX.Y.Z"
```

Release baru siap setelah job build, smoke install-launch-uninstall x64 (bila dikonfigurasi), dan publish release selesai hijau.

### 5. Verifikasi Release dan Updater

```powershell
gh release view "vX.Y.Z" --json tagName,isDraft,isPrerelease,url,body,assets
gh api repos/chsprs/mikan-pet/releases/latest --jq .tag_name
git status --short --branch
git ls-remote origin refs/heads/main "refs/tags/vX.Y.Z"
```

Release wajib non-draft, non-prerelease, menjadi hasil endpoint `/releases/latest`, dan memiliki tepat satu aset bernama `MikanPet-Setup-x64.exe`.

## Kontrak Auto-Updater

- Updater memanggil `GET https://api.github.com/repos/chsprs/mikan-pet/releases/latest`.
- Update hanya mendukung Windows x64 dan mengunduh `MikanPet-Setup-x64.exe`.
- Jika respons GitHub menyediakan digest SHA-256 untuk installer, verifikasi installer sebelum dijalankan.
- Setelah pengguna menyetujui, updater menutup aplikasi bila perlu, menjalankan installer x64 secara aman, lalu membiarkan installer menyelesaikan pembaruan.
- Jangan mempertahankan logika pemilihan ARM64, unduh portable ZIP, atau ekstraksi ZIP.

Tag tanpa GitHub Release tidak akan dilihat oleh updater karena updater mengikuti `/releases/latest`, bukan daftar tag Git.

## Signing Windows

Signing bersifat opsional dan aktif hanya ketika kedua GitHub Actions secret ini tersedia:

- `WINDOWS_CERT_BASE64`
- `WINDOWS_CERT_PASSWORD`

Nama secret dapat diaudit dengan `gh secret list`; nilainya tidak boleh dicetak atau diminta di log. Bila salah satu tidak ada, release dapat tetap diterbitkan sebagai unsigned. Laporkan status tersebut secara jujur dan jangan membuat sertifikat self-signed sebagai pengganti production signing.

## Catatan Rilis dan Release Gagal

- Baca kembali `body` release dari GitHub; keberhasilan action tidak membuktikan catatan rilis sudah lengkap.
- Gunakan teks ASCII-safe atau UTF-8 tanpa BOM untuk file catatan yang dikonsumsi GitHub Actions.
- Jika ada tag gagal di antara dua release yang dipublikasikan, generator berbasis tag bisa melewatkan commit. Pastikan catatan mencakup semua perubahan sejak release terakhir yang benar-benar dipublikasikan.
- Jika tag sudah dipush tetapi workflow gagal, perbaiki penyebab di `main`, naikkan patch version, lalu rilis tag baru. Biarkan tag lama sebagai rekam jejak kecuali pengguna secara eksplisit meminta penghapusan.

## Red Flags

Berhenti dan selidiki jika:

- worktree memuat perubahan atau file untracked di luar scope release;
- salah satu dari empat file versi tidak sinkron;
- tag lokal/remote atau GitHub Release untuk versi target sudah ada;
- run yang dipantau tidak cocok dengan commit tag;
- build atau smoke test x64 gagal;
- release tidak muncul di `/releases/latest`;
- aset release bukan tepat satu `MikanPet-Setup-x64.exe`;
- updater masih meminta ZIP atau aset ARM64;
- release diklaim signed tanpa kedua certificate secrets.

## Checklist Selesai

- [ ] Pengguna secara eksplisit mengotorisasi commit/push/release.
- [ ] Worktree diperiksa dan hanya memuat scope yang disengaja.
- [ ] Seluruh tes lokal lolos; build installer x64 dijalankan bila relevan.
- [ ] Empat file versi sinkron dengan tag `vX.Y.Z`.
- [ ] Pipeline hanya membangun dan mempublikasikan `MikanPet-Setup-x64.exe`.
- [ ] Commit `main` dan tag ada di remote serta menunjuk commit yang benar.
- [ ] Run `release.yml` untuk commit itu selesai hijau.
- [ ] Smoke install-launch-uninstall x64 hijau bila dikonfigurasi.
- [ ] Release bukan draft/prerelease dan memiliki tepat satu aset installer x64.
- [ ] Catatan rilis lengkap sejak release terakhir yang dipublikasikan.
- [ ] Endpoint `/releases/latest` mengembalikan versi baru.
- [ ] Status signed atau unsigned dilaporkan sesuai fakta.
- [ ] `git status --short --branch` menunjukkan kondisi akhir yang diharapkan.
