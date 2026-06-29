# Perintah Konversi SEG-D

Project ini punya **3 cara** konversi Fairfield SEG-D ke SU/SEG-Y.

---

## 1. SeisUnix (`segdread`) → SU

```bash
# Start container
docker compose up -d
docker compose exec seisunix bash
```

Di dalam container:

```bash
# Cek ketersediaan
which segdread

# Satu file
segdread < /data/FFID_101.SEGD > /output/FFID_101.su

# Semua file
for f in /data/*.SEGD; do
  base=$(basename "$f" .SEGD)
  segdread < "$f" > "/output/${base}.su"
done

# Lihat hasil
surange /output/FFID_101.su
suxwigb < /output/FFID_101.su title="FFID_101" perc=99 &
```

---

## 2. Python/ObsPy (`convert_fairfield.py`) → SEG-Y

Jalanin service sekali jalan (auto-convert semua `*.SEGD` di `/data`):

```bash
docker compose --profile convert up
```

Manual dengan argumen kustom:

```bash
# Satu file
docker compose run --rm convert \
  python /scripts/convert_fairfield.py /data/FFID_101.SEGD -o /output/

# Semua file
docker compose run --rm convert \
  python /scripts/convert_fairfield.py /data/*.SEGD -o /output/

# Bisa juga SU format (via --format, lihat script)
```

Hasil: `output/*.segy`

---

## 3. C Standalone (`fairfield_segd2segy`) → SEG-Y

Tanpa dependensi ObsPy. Kompilasi langsung di host:

```bash
# Build
make

# Jalanin
./fairfield_segd2segy data/FFID_101.SEGD -o output/FFID_101.sgy -v
```

Argumen:

| Opsi | Fungsi |
|------|--------|
| `-v` | Verbose |
| `--gain` | Apply gain |
| `--ns N` | Override sample count |
| `--ffid N` | Override FFID number |

Atau kompilasi & jalankan di dalam container SeisUnix:

```bash
docker compose exec seisunix bash
gcc -o /usr/local/bin/fairfield_segd2segy /data/../fairfield_segd2segy.c -lm
fairfield_segd2segy /data/FFID_101.SEGD -o /output/FFID_101.sgy -v
```

---

## Ringkasan

| Metode | Output | Perintah |
|--------|--------|----------|
| **SeisUnix** | `.su` | `segdread < infile > outfile` (di dalam container) |
| **Python/ObsPy** | `.segy` | `docker compose --profile convert up` |
| **C murni** | `.sgy` | `./fairfield_segd2segy input -o output -v` |
