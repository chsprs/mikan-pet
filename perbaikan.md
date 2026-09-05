# Dokumen Rekomendasi & Rencana Perbaikan Mikan Pet

Dokumen ini menyajikan hasil analisis mendalam terhadap basis kode **Mikan Pet** (v0.1.2), mencakup arsitektur, keandalan sistem Windows, performa runtime, tata kelola packaging, dan rincian langkah mitigasi teknis.

---

## 1. Ikhtisar Arsitektur & Status Saat Ini

Mikan Pet adalah aplikasi desktop pet dan pengontrol media universal untuk platform Windows yang dibangun di atas Python, Tkinter, dan `pywin32`.

### Komponen Utama:
- **Core Domain (`mikan_pet/core/`)**: FSM state controller murni tanpa dependensi GUI, sistem perenderan raster pixel-art berdasar representasi ASCII template, perhitungan layout matriks DPI logis ke fisik.
- **UI Subsystem (`mikan_pet/ui/`)**: Window Tkinter frameless dengan colorkey transparency (`-transparentcolor`), per-monitor DPI subclassing Win32 (`WM_DPICHANGED`), canvas caching PhotoImage.
- **OS Services (`mikan_pet/services/`)**: Windows GSMTC media polling, Win32 keystroke emulation, named mutex single-instance lock, multi-monitor work-area tracking, persistent JSON settings, dan GitHub Releases updater.

Secara umum, arsitektur modul telah memiliki pemisahan tanggung jawab (separation of concerns) yang rapi dan cakupan unit test tinggi (163 tests passing). Namun, terdapat beberapa kelemahan arsitektural dan implementasi spesifik platform Windows yang perlu diperbaiki.

---

## 2. Temuan Prioritas Tinggi (High Priority)

### 2.1 Subprocess Polling GSMTC Membebani CPU & Memori
- **File**: `mikan_pet/services/media_info.py:42-87`
- **Masalah**:
  Metode `WindowsGsmtcBackend.query_current_track()` menjalankan perintah:
  ```python
  subprocess.run(
      ["powershell", "-NoProfile", "-NonInteractive", "-Command", self._SCRIPT],
      ...
  )
  ```
  setiap 3 detik (`poll_interval_seconds = 3.0`) via worker thread.
- **Dampak**:
  1. Cold-start proses `powershell.exe` membutuhkan waktu 300ms–800ms dan mengalokasikan memori 30–60 MB per spawn.
  2. Terjadi spike CPU berkala setiap 3 detik. Pada laptop berdaya baterai atau CPU low-end, hal ini menyebabkan boros daya dan stutter pada animasi desktop.
  3. Membuka handle proses dan thread baru secara konstan meningkatkan overhead handle kernel Windows.
- **Rekomendasi Solusi**:
  - **Opsi A (Rekomendasi Utama)**: Gunakan binding WinRT native langsung melalui library `winsdk` (`winsdk.windows.media.control`) atau `winrt-runtime` + `winrt-Windows.Media.Control`. Melalui API ini, GSMTC dapat mendengarkan event perubahan media secara asinkron tanpa polling berkala (`CurrentSessionChanged` / `MediaPropertiesChanged`).
  - **Opsi B (Solusi Ringan Tanpa Dependensi Baru)**: Jika tidak ingin menambah dependensi wheel biner baru, jalankan satu proses latar PowerShell persisten (persistent runspace / standard input-output loop) yang tetap hidup selama aplikasi berjalan, bukan spawn proses baru tiap 3 detik.

---

### 2.2 Skrip In-Place Updater Rentan Gagal dan Mengabaikan UAC
- **File**: `mikan_pet/services/updater.py:102-128`
- **Masalah**:
  1. Skrip pembaruan sementara `_mikan_update.cmd` digenerate sebagai berikut:
     ```cmd
     @echo off
     timeout /t 1 /nobreak >nul
     taskkill /F /PID {os.getpid()} >nul 2>&1
     xcopy "{staging_dir}\*" "{install_dir}\\" /E /Y /Q >nul
     rmdir /S /Q "{staging_dir}"
     start "" "{install_dir / target_exe_name}"
     (goto) 2>nul & del "%~f0"
     ```
  2. Jika aplikasi terpasang di direktori sistem (misalnya pengguna memasang di direktori yang memerlukan hak admin, atau proteksi folder UAC), perintah `xcopy` akan gagal tanpa penanganan error (`Access Denied`), menyebabkan file binary terkorupsi parsial.
  3. `timeout /t 1` tidak menjamin handle file binary `MikanPet.exe` dan modul DLL `.pyd` sudah dilepas oleh OS, sehingga `xcopy` dapat terkunci (`File in use`).
  4. Penggunaan `taskkill /F` pada proses sendiri bersifat brutal sebelum resource release standar selesai.
- **Rekomendasi Solusi**:
  1. Tambahkan pengecekan izin tulis (`os.access(install_dir, os.W_OK)`). Jika tidak memiliki izin tulis, jalankan skrip updater menggunakan `ShellExecute` dengan kata kerja `runas` untuk meminta elevasi hak administrator (UAC prompt).
  2. Tambahkan retry loop di dalam skrip updater batch/PowerShell untuk menunggu pelepasan file lock sebelum melakukan penyalinan.
  3. Berikan log atau pesan error jika proses penyalinan berkas pembaruan gagal, alih-alih keluar secara hening (`>nul`).

---

### 2.3 Inkonsistensi Versi dan Metadata Antar Berkas
- **File**:
  - `installer/MikanPet.iss:2`: `#define MyAppVersion "0.1.0"` (Ketinggalan versi).
  - `pyproject.toml:7`: `version = "0.1.2"`.
  - `mikan_pet/app.py:24`: `VERSION = "0.1.2"`.
  - `README.md:27-34`: Hanya mendokumentasikan 3 skin (`Mikan`, `Byte`, `Mochi`), sedangkan di `mikan_pet/core/types.py` dan `mikan_pet/core/sprites.py` sudah terdapat skin ke-4: `SkinId.ASH` ("Ash").
- **Dampak**:
  1. Installer hasil kompilasi Inno Setup menuliskan metadata versi lama (`0.1.0`) ke registry Windows dan panel "Add/Remove Programs".
  2. Dokumentasi pengguna tidak lengkap mengenai variasi skin yang tersedia.
- **Rekomendasi Solusi**:
  1. Sinkronisasi `MyAppVersion` di `installer/MikanPet.iss` menjadi `0.1.2` (atau parameterkan saat build melalui script `scripts/build.ps1` via switch `/DMyAppVersion=...`).
  2. Perbarui `README.md` pada bagian skin dengan menambahkan profil skin **Ash** (kucing abu-abu / calico lembut).

---

## 3. Temuan Prioritas Sedang (Medium Priority)

### 3.1 Pemotongan Elemen Bubble Lagu pada Sudut Layar (Canvas Clipping)
- **File**: `mikan_pet/ui/pet_window.py:590-609`
- **Masalah**:
  1. Bounding box window dan canvas Tkinter dihitung oleh `calculate_window_layout()` hanya berdasarkan ukuran sprite pet dan kontrol tombol media.
  2. Teks bubble lagu (`track_bubble`) digambar di kanvas pada koordinat statis `(72, 18)` atau `(100, 68)`.
  3. Ketika judul lagu panjang (hingga 22-24 karakter) dan posisi pet berada di sudut layar atau mode collapsed, tepi bubble track info berisiko terpotong (clipped) di batas kanvas jendela transparan.
- **Rekomendasi Solusi**:
  1. Sertakan estimasi lebar/tinggi track bubble ke dalam metrik ukuran kanvas saat track bubble aktif, atau
  2. Berikan deteksi koordinat dinamis: jika teks melebihi lebar kanvas atau mendekati tepi layar atas/kanan, pindahkan orientasi bubble ke sisi bawah atau sejajarkan rata kanan.

---

### 3.2 Fixed Tick Rate (50ms / 20 FPS) saat Kucing Diam atau Tidur
- **File**: `mikan_pet/ui/pet_window.py:41, 630-657`
- **Masalah**:
  Konstanta `TICK_MS = 50` memicu tick loop setiap 50 milidetik secara konstan, bahkan ketika:
  - Mode pet dihentikan (`MotionMode.STOPPED`).
  - Animasi dalam keadaan tidur (`Pose.SLEEP`) yang pergantian framenya sangat lambat (frame interval 180ms).
  Setiap 50ms, fungsi melakukan:
  - `_reconcile_position()`
  - query work area monitor
  - pembaruan Tkinter geometry
  - `update_idletasks()`
- **Rekomendasi Solusi**:
  Terapkan **adaptive tick rate**:
  - Saat `MotionMode.AUTOMATIC` dan berjalan (`Pose.WALK`): `50ms` (20 FPS) untuk pergerakan halus.
  - Saat `MotionMode.DRAGGING`: `16ms` (60 FPS) agar dragging mouse sangat responsif.
  - Saat `Pose.IDLE` atau `Pose.SLEEP`: perlambat interval tick menjadi `150ms` – `200ms` karena tidak ada pergeseran koordinat posisi, hanya pergantian frame animasi periodik.

---

### 3.3 Penanganan Unhandled Exception & Logging File
- **File**: `mikan_pet/ui/pet_window.py:717-735`
- **Masalah**:
  `_report_callback_exception` hanya menampilkan messagebox dialog kesalahan umum tanpa menulis jejak stack trace (`traceback`) ke berkas log lokal.
- **Rekomendasi Solusi**:
  Tambahkan modul logging standar Python (`logging.FileHandler`) yang menulis berkas log rotasi ke `%APPDATA%\MikanPet\logs\mikan_pet.log` sehingga memudahkan pelaporan bug ketika terjadi crash atau kendala DPI pada perangkat pengguna.

---

## 4. Temuan Prioritas Rendah & Pemeliharaan (Low Priority)

### 4.1 Pembersihan Artefak Cache pada Repositori
- **Temuan**:
  Terdapat file residual build lokal di direktori kerja seperti `.superpowers/`, cache `.pyc`, dan berkas build lama.
- **Rekomendasi**:
  Pastikan `.gitignore` mencakup pola direktori internal toolchain dan lakukan `git clean` pada pipeline sebelum build rilis.

### 4.2 Parameterisasi Build Script Inno Setup
- **File**: `scripts/build.ps1`
- **Rekomendasi**:
  Ubah pemanggilan `ISCC.exe` agar mengoper argumen versi secara dinamis langsung dari `pyproject.toml` atau `mikan_pet/app.py`:
  ```powershell
  $version = & $Python -c "import mikan_pet; print(mikan_pet.__version__)"
  Invoke-Checked $iscc @("/DMyAppVersion=$version", '/Qp', (Join-Path $ProjectRoot 'installer\MikanPet.iss'))
  ```

---

## 5. Rencana Aksi & Matriks Implementasi

| No | Komponen | Tindakan Perbaikan | Estimasi Dampak | Tingkat Kesulitan |
|---|---|---|---|---|
| 1 | `installer/MikanPet.iss` & `README.md` | Sinkronisasi versi `0.1.2` dan dokumentasi skin `Ash` | Metadata konsisten, dokumentasi akurat | Sangat Rendah |
| 2 | `scripts/build.ps1` | Passing dynamic version flag ke Inno Setup (`/DMyAppVersion=...`) | Menghilangkan duplikasi versi manual | Rendah |
| 3 | `mikan_pet/services/media_info.py` | Optimasi GSMTC polling: persistent bridge atau native WinRT bindings | Mengeliminasi CPU/RAM spike tiap 3 detik | Sedang |
| 4 | `mikan_pet/services/updater.py` | Validasi write access, UAC elevation prompt, file lock retry loop | Pembaruan in-place 100% andal di seluruh path | Sedang |
| 5 | `mikan_pet/ui/pet_window.py` | Adaptive tick rate (50ms saat bergerak, 150-200ms saat diam/tidur) | Penghematan daya baterai dan CPU | Rendah |
| 6 | `mikan_pet/ui/pet_window.py` | Boundary safety & auto-flip untuk bubble judul lagu | Mencegah teks terpotong di tepi layar | Sedang |

Dokumen ini dapat digunakan sebagai acuan langsung untuk tiket perbaikan dan refactoring berikutnya.
